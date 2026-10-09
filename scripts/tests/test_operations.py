"""Exercise persistent local configuration and deployment security rules."""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "init_local.py"
SPEC = importlib.util.spec_from_file_location("local_initializer", SOURCE)
assert SPEC and SPEC.loader
INITIALIZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INITIALIZER)


class LocalConfigurationTests(unittest.TestCase):
    def test_repeat_configuration_preserves_secrets_and_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / ".local"
            with patch.dict(os.environ, {"PROJECT_NAMESPACE": "pcrstudio_synthetic", "LOCAL_UID": "1000", "LOCAL_GID": "1000"}):
                INITIALIZER.initialize(state)
            self.assertEqual(32, len(base64.urlsafe_b64decode((state / "secrets/mfa_encryption_key").read_text())))
            self.assertNotEqual((state / "secrets/mfa_encryption_key").read_text(), (state / "secrets/django_secret_key").read_text())
            expected = {path.name: path.read_bytes() for path in (state / "secrets").iterdir()}
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o440 for path in (state / "secrets").iterdir()))
            (state / "secrets/django_secret_key").chmod(0o400)
            modes = {path.name: path.stat().st_mode for path in (state / "secrets").iterdir()}
            configuration = (state / "compose.env").read_bytes()
            (state / "artifacts" / "preserved-data").write_text("synthetic state")
            with patch.dict(os.environ, {"PROJECT_NAMESPACE": "different", "LOCAL_UID": "2000", "LOCAL_GID": "2000"}):
                INITIALIZER.initialize(state)
            self.assertEqual(expected, {path.name: path.read_bytes() for path in (state / "secrets").iterdir()})
            self.assertEqual(modes, {path.name: path.stat().st_mode for path in (state / "secrets").iterdir()})
            self.assertEqual(configuration, (state / "compose.env").read_bytes())
            self.assertEqual("synthetic state", (state / "artifacts" / "preserved-data").read_text())
            self.assertEqual(0o700, state.stat().st_mode & 0o777)
            self.assertEqual(0o700, (state / "secrets").stat().st_mode & 0o777)
            self.assertEqual(0o600, (state / "compose.env").stat().st_mode & 0o777)

    def test_legacy_secret_permissions_tighten_once_without_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / ".local"
            with patch.dict(os.environ, {"PROJECT_NAMESPACE": "pcrstudio_synthetic", "LOCAL_UID": "1000", "LOCAL_GID": "1000"}):
                INITIALIZER.initialize(state)
            expected = {path.name: path.read_bytes() for path in (state / "secrets").iterdir()}
            configuration = (state / "compose.env").read_bytes()
            for path, mode in zip((state / "secrets").iterdir(), (0o644, 0o444, 0o640, 0o400, 0o440, 0o440), strict=True):
                path.chmod(mode)
            with patch.dict(os.environ, {"PROJECT_NAMESPACE": "different", "LOCAL_UID": "2000", "LOCAL_GID": "2000"}):
                INITIALIZER.initialize(state)
                modes = {path.name: path.stat().st_mode for path in (state / "secrets").iterdir()}
                INITIALIZER.initialize(state)
            self.assertEqual(expected, {path.name: path.read_bytes() for path in (state / "secrets").iterdir()})
            self.assertEqual(configuration, (state / "compose.env").read_bytes())
            self.assertEqual(modes, {path.name: path.stat().st_mode for path in (state / "secrets").iterdir()})
            self.assertEqual(1, sum(mode & 0o777 == 0o400 for mode in modes.values()))
            self.assertEqual(5, sum(mode & 0o777 == 0o440 for mode in modes.values()))

    def test_empty_existing_secret_is_not_rotated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "secrets").mkdir()
            (state / "secrets/django_secret_key").touch()
            with self.assertRaisesRegex(RuntimeError, "refusing to replace"):
                INITIALIZER.initialize(state)
            self.assertEqual(b"", (state / "secrets/django_secret_key").read_bytes())


class BootstrapRegistryTests(unittest.TestCase):
    def run_bootstrap(self, profile: str | None, build_network: str | None = None) -> tuple[subprocess.CompletedProcess[str], list[dict]]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copyfile(SOURCE.parents[1] / "bootstrap", root / "bootstrap")
            state = root / ".local"
            state.mkdir()
            (state / "secrets").mkdir()
            configuration = b"COMPOSE_PROJECT_NAME=pcrstudio_preserved\nLOCAL_UID=1000\nLOCAL_GID=1000\n"
            (state / "compose.env").write_bytes(configuration)
            (state / "secrets/django_secret_key").write_bytes(b"preserved synthetic secret\n")
            docker = root / "docker_mock.py"
            docker.write_text(
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "with Path(os.environ['DOCKER_CALLS']).open('a') as output:\n"
                "    output.write(json.dumps({'arguments': sys.argv[1:], 'registry': os.environ.get('PCRSTUDIO_OFFICIAL_IMAGE_REGISTRY'), 'build_network': os.environ.get('PCRSTUDIO_BUILD_NETWORK')}) + '\\n')\n"
            )
            environment = {**os.environ, "DOCKER_MOCK": str(docker), "MOCK_PYTHON_EXECUTABLE": sys.executable, "DOCKER_CALLS": str(root / "calls.jsonl"), "PCRSTUDIO_OFFICIAL_IMAGE_REGISTRY": "unverified.example"}
            environment.pop("PCRSTUDIO_IMAGE_REGISTRY", None)
            environment.pop("PCRSTUDIO_BUILD_NETWORK", None)
            if profile is not None:
                environment["PCRSTUDIO_IMAGE_REGISTRY"] = profile
            if build_network is not None:
                environment["PCRSTUDIO_BUILD_NETWORK"] = build_network
            # /tmp remains noexec in the tools container; invoke the mock through Python.
            process = subprocess.run(["sh", "-c", 'docker() { "$MOCK_PYTHON_EXECUTABLE" "$DOCKER_MOCK" "$@"; }; . "$0"', str(root / "bootstrap"), "doctor"], env=environment, capture_output=True, text=True, check=False)
            self.assertEqual(configuration, (state / "compose.env").read_bytes())
            self.assertEqual(b"preserved synthetic secret\n", (state / "secrets/django_secret_key").read_bytes())
            calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()] if (root / "calls.jsonl").exists() else []
            return process, calls

    def test_default_registry_preserves_local_state(self) -> None:
        process, calls = self.run_bootstrap(None)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertTrue(calls)
        self.assertTrue(all(call["registry"] == "public.ecr.aws/docker" for call in calls))
        self.assertTrue(all(call["build_network"] == "host" for call in calls))
        initializer = next(call for call in calls if call["arguments"][0] == "run")
        self.assertIn("public.ecr.aws/docker/library/python:3.13.16-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641", initializer["arguments"])

    def test_dockerhub_registry_applies_to_initializer_and_compose(self) -> None:
        process, calls = self.run_bootstrap("dockerhub", "default")
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertTrue(calls)
        self.assertTrue(all(call["registry"] == "docker.io" for call in calls))
        self.assertTrue(all(call["build_network"] == "default" for call in calls))
        initializer = next(call for call in calls if call["arguments"][0] == "run")
        self.assertIn("docker.io/library/python:3.13.16-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641", initializer["arguments"])

    def test_unknown_registry_fails_before_docker(self) -> None:
        process, calls = self.run_bootstrap("unverified")
        self.assertEqual(2, process.returncode)
        self.assertIn("must be ecr or dockerhub", process.stderr)
        self.assertEqual([], calls)

    def test_unknown_build_network_fails_before_docker(self) -> None:
        process, calls = self.run_bootstrap("dockerhub", "unverified")
        self.assertEqual(2, process.returncode)
        self.assertIn("must be host or default", process.stderr)
        self.assertEqual([], calls)
