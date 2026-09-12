#!/usr/bin/env python3
"""Dependency-free regression checks for Linux bootstrap/provision invariants."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # SourceFileLoader may materialize __pycache__ even under -B when used via
    # exec_module. These contract checks must leave the repository tree clean.
    sys.modules[name] = module
    try:
        code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def expect_system_exit(fn, value: str) -> None:
    try:
        fn(value)
    except SystemExit:
        return
    raise AssertionError(f"expected rejection for {value!r}")


def check_docker_save_integration(release_bundle) -> None:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("Docker is required for --docker-save-integration")

    image_tag = f"pcrstudio-release-contract:{uuid.uuid4().hex}"
    imported = False
    with tempfile.TemporaryDirectory(prefix="pcrstudio-docker-save-") as tmp:
        root_archive = Path(tmp) / "rootfs.tar"
        image_archive = Path(tmp) / "image.tar.gz"
        payload = b"pcrstudio docker-save archive contract\n"
        with tarfile.open(root_archive, "w") as archive:
            member = tarfile.TarInfo("contract.txt")
            member.size = len(payload)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(payload))

        try:
            subprocess.run(
                [docker, "image", "import", str(root_archive), image_tag],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
            )
            imported = True
            saved = subprocess.run(
                [docker, "image", "save", image_tag],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            with tarfile.open(fileobj=io.BytesIO(saved.stdout), mode="r:") as archive:
                entries = json.load(archive.extractfile("manifest.json"))
                entry = next(
                    item for item in entries if image_tag in item.get("RepoTags", [])
                )
                config_name = entry["Config"]
                config_stream = archive.extractfile(config_name)
                if config_stream is None:
                    raise AssertionError(f"docker save omitted config {config_name}")
                with config_stream:
                    expected_digest = "sha256:" + hashlib.sha256(config_stream.read()).hexdigest()
            image_archive.write_bytes(gzip.compress(saved.stdout, mtime=0))
            actual = release_bundle.docker_save_config_digests(image_archive)
            assert actual == {image_tag: expected_digest}, (actual, expected_digest)

            subprocess.run(
                [docker, "image", "rm", "--force", image_tag],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
            subprocess.run(
                [docker, "image", "load", "--input", str(image_archive)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            pull_release = load("pcrstudio_pull_release", ROOT / "scripts" / "pull-release.py")
            name, tag = image_tag.rsplit(":", 1)
            pull_release.image_ids(
                {"images": [{"name": name, "tag": tag, "image_id": expected_digest}]}
            )
        finally:
            if imported:
                subprocess.run(
                    [docker, "image", "rm", "--force", image_tag],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )


def check_download_retry_contract(provision) -> None:
    payload = b"content-addressed archive fixture\n"
    expected = hashlib.sha256(payload).hexdigest()
    primary = "https://primary.example.invalid/pinned.tgz"
    mirror = "https://mirror.example.invalid/pinned.tgz"
    requests: list[str] = []

    def fail_primary_then_serve_mirror(request, timeout):
        requests.append(request.full_url)
        if request.full_url == primary:
            raise provision.urllib.error.URLError(
                provision.socket.timeout("simulated connect timeout")
            )
        return io.BytesIO(payload)

    with tempfile.TemporaryDirectory(prefix="pcrstudio-download-contract-") as tmp:
        target = Path(tmp) / "pinned.tgz"
        with mock.patch.object(
            provision.urllib.request,
            "urlopen",
            side_effect=AssertionError("unpinned download must fail before network access"),
        ):
            try:
                provision.download(primary, target, "")
            except SystemExit as error:
                assert "exact lowercase SHA-256 pin" in str(error)
            else:
                raise AssertionError("provisioner accepted an artifact without a digest pin")

        with (
            mock.patch.object(
                provision.urllib.request,
                "urlopen",
                side_effect=fail_primary_then_serve_mirror,
            ),
            mock.patch.object(provision.time, "sleep") as sleep,
            redirect_stderr(io.StringIO()),
            redirect_stdout(io.StringIO()),
        ):
            assert provision.download(
                primary, target, expected, mirror_urls=(mirror,)
            ) == target
        assert target.read_bytes() == payload
        assert requests == [primary] * provision.DOWNLOAD_MAX_ATTEMPTS + [mirror]
        assert sleep.call_count == provision.DOWNLOAD_MAX_ATTEMPTS - 1

        # A valid local pinned artifact is reusable without a network call.
        with mock.patch.object(
            provision.urllib.request,
            "urlopen",
            side_effect=AssertionError("verified cache unexpectedly accessed network"),
        ):
            assert provision.download(primary, target, expected) == target

        # Corrupt content is fatal and must not trigger another source or retry.
        bad_target = Path(tmp) / "corrupt.tgz"
        with mock.patch.object(
            provision.urllib.request, "urlopen", return_value=io.BytesIO(b"tampered")
        ) as open_url:
            try:
                provision.download(
                    primary, bad_target, expected, mirror_urls=(mirror,)
                )
            except SystemExit as error:
                assert "SHA-256 mismatch" in str(error)
            else:
                raise AssertionError("download accepted bytes that violated its SHA-256 pin")
            assert open_url.call_count == 1
        assert not bad_target.exists()

        class DowngradedResponse(io.BytesIO):
            def geturl(self):
                return "http://mirror.example.invalid/pinned.tgz"

        with mock.patch.object(
            provision.urllib.request,
            "urlopen",
            return_value=DowngradedResponse(payload),
        ) as open_url:
            try:
                provision.download(
                    primary, Path(tmp) / "downgraded.tgz", expected
                )
            except SystemExit as error:
                assert "HTTPS" in str(error)
            else:
                raise AssertionError("download followed a redirect that downgraded TLS")
            assert open_url.call_count == 1

        # Permanent HTTP failures are diagnosed but never retried or hidden by
        # switching to another source.
        http_404 = provision.urllib.error.HTTPError(
            primary, 404, "Not Found", {}, None
        )
        with mock.patch.object(
            provision.urllib.request, "urlopen", side_effect=http_404
        ) as open_url:
            try:
                provision.download(
                    primary, Path(tmp) / "missing.tgz", expected, mirror_urls=(mirror,)
                )
            except SystemExit as error:
                assert "class=http-404" in str(error)
            else:
                raise AssertionError("download retried or hid a permanent 404")
            assert open_url.call_count == 1

        assert provision.download_failure_class(
            provision.urllib.error.URLError(
                provision.socket.gaierror(provision.socket.EAI_AGAIN, "temporary DNS failure")
            )
        ) == "dns-temporary"
        assert provision.download_failure_class(http_404) == "http-404"
        http_403 = provision.urllib.error.HTTPError(primary, 403, "Forbidden", {}, None)
        assert provision.download_failure_class(http_403) == "authentication-or-policy"
        http_407 = provision.urllib.error.HTTPError(primary, 407, "Proxy auth", {}, None)
        assert provision.download_failure_class(http_407) == "proxy-authentication"
        http_429 = provision.urllib.error.HTTPError(
            primary, 429, "Rate limited", {"Retry-After": "100"}, None
        )
        assert provision.download_failure_class(http_429) == "rate-limit"
        assert provision.retry_delay_seconds(http_429, 1) == 10.0
        cdn_522 = provision.urllib.error.HTTPError(primary, 522, "Origin timeout", {}, None)
        assert provision.download_failure_class(cdn_522) == "transient-cdn"
        assert provision.download_failure_class(
            provision.urllib.error.URLError(
                provision.ssl.SSLCertVerificationError(1, "invalid certificate")
            )
        ) == "tls-certificate"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docker-save-integration",
        action="store_true",
        help="exercise the digest reader against an image created and saved by the local Docker daemon",
    )
    args = parser.parse_args()

    bootstrap = load("pcrstudio_bootstrap_linux", ROOT / "scripts" / "bootstrap-linux.py")
    provision = load("pcrstudio_provision_tools", ROOT / "scripts" / "provision-tools.py")
    release_bundle = load("pcrstudio_release_bundle", ROOT / "scripts" / "release_bundle.py")
    ci_scope = load("pcrstudio_ci_scope", ROOT / "scripts" / "classify-ci-scope.py")
    ci_gate = load("pcrstudio_ci_gate", ROOT / "scripts" / "ci-qualification-gate.py")
    maintenance = load("pcrstudio_docker_maintenance", ROOT / "scripts" / "docker-maintenance.py")
    storage_guard_module = load("pcrstudio_storage_guard", ROOT / "scripts" / "storage-guard.py")
    pull_release_module = load("pcrstudio_pull_release", ROOT / "scripts" / "pull-release.py")

    # Developer cache cleanup is deterministic, per-checkout, and limited to
    # PCRStudio's dedicated builder; it must never become a daemon-wide prune.
    service_name, service_unit, timer_name, timer_unit = maintenance.user_timer_units(
        root=Path("/tmp/PCR Studio/$cache%"), python=Path("/usr/bin/python3")
    )
    assert service_name.endswith(".service") and timer_name.endswith(".timer")
    assert service_name.removesuffix(".service") == timer_unit.split("Unit=", 1)[1].splitlines()[0].removesuffix(".service")
    assert "WorkingDirectory=/tmp/PCR\\x20Studio/$cache%%" in service_unit
    assert "prune --max-used-space 8GB" in service_unit
    assert "NoNewPrivileges=true" in service_unit and "UMask=0077" in service_unit
    assert "Persistent=true" in timer_unit and "RandomizedDelaySec=20m" in timer_unit
    assert "docker system prune" not in service_unit
    buildkit_config = (ROOT / "docker" / "buildkitd.toml").read_text(encoding="utf-8")
    assert 'maxUsedSpace = "8GB"' in buildkit_config
    assert 'reservedSpace = "1GB"' in buildkit_config
    assert 'gckeepstorage' not in buildkit_config
    assert bootstrap.BUILDX_GC_MARKER == maintenance.BUILDKIT_GC_MARKER
    assert "export BUILDX_BUILDER=pcrstudio" in (ROOT / "scripts" / "compose-linux.sh").read_text(encoding="utf-8")
    try:
        maintenance.systemd_quote("unsafe\nunit")
    except SystemExit:
        pass
    else:
        raise AssertionError("systemd unit command accepted an injected newline")
    recorded_docker_commands: list[list[str]] = []
    with (
        mock.patch.object(
            maintenance.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["docker"], 0),
        ),
        mock.patch.object(
            maintenance,
            "run",
            side_effect=lambda docker, args: recorded_docker_commands.append([*docker, *args]),
        ),
    ):
        maintenance.prune(["docker"], "8GB")
    assert recorded_docker_commands == [
        ["docker", "buildx", "du", "--builder", "pcrstudio"],
        ["docker", "buildx", "prune", "--builder", "pcrstudio", "--all", "--max-used-space", "8GB", "--force"],
        ["docker", "image", "prune", "--force", "--filter", "label=org.pcrstudio.product=PCRStudio"],
        ["docker", "buildx", "du", "--builder", "pcrstudio"],
    ]
    guard_commands: list[tuple[list[str], bool]] = []

    def record_guard_command(command: list[str], *, check: bool = True) -> int:
        guard_commands.append((command, check))
        return 1 if len(guard_commands) == 1 else 0

    with mock.patch.object(storage_guard_module, "run", side_effect=record_guard_command):
        assert storage_guard_module.cleanup_owned_artifacts() == [
            "PCRStudio Docker cache/image cleanup"
        ]
    assert len(guard_commands) == 2 and all(not check for _, check in guard_commands)
    assert all(
        not any(command[index : index + 2] == ["system", "prune"] for index in range(len(command) - 1))
        for command, _ in guard_commands
    )
    guard_source = (ROOT / "scripts" / "storage-guard.py").read_text(encoding="utf-8")
    assert "storage cleanup failed:" in guard_source and "or cleanup_failures" in guard_source
    assert "def containerd_root()" in guard_source and "paths = [ROOT, docker_root(docker), containerd_root()]" in guard_source

    # Successful release activation retains current + previous rollback tags,
    # and only removes full-SHA tags from PCRStudio's four product images.
    current_sha, previous_sha, obsolete_sha = "a" * 40, "b" * 40, "c" * 40
    image_listing = "\n".join(
        (
            f"pcrstudio-api:{current_sha}",
            f"pcrstudio-web:{previous_sha}",
            f"pcrstudio-api:{obsolete_sha}",
            f"pcrstudio-runner:{obsolete_sha}",
            "pcrstudio-api:local",
            f"uniora-api:{obsolete_sha}",
            f"pcrstudio-migrate:{'d' * 40}",
        )
    )
    successful_docker_calls: list[list[str]] = []

    def record_image_cleanup(command: list[str], **_kwargs):
        successful_docker_calls.append(command)
        if command[1:3] == ["image", "ls"]:
            return subprocess.CompletedProcess(command, 0, stdout=image_listing, stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=f"Untagged: {command[-1]}\n", stderr="")

    with (
        mock.patch.object(pull_release_module.subprocess, "run", side_effect=record_image_cleanup),
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        assert pull_release_module.prune_old_release_images(current_sha, previous_sha) == []
    assert successful_docker_calls[0] == [
        "docker", "image", "ls", "--filter", "label=org.pcrstudio.product=PCRStudio",
        "--format", "{{.Repository}}:{{.Tag}}",
    ]
    assert [command[-1] for command in successful_docker_calls[1:]] == [
        f"pcrstudio-api:{obsolete_sha}", f"pcrstudio-migrate:{'d' * 40}",
        f"pcrstudio-runner:{obsolete_sha}"
    ]
    assert all("--force" not in command for command in successful_docker_calls)
    refused_removal = subprocess.CompletedProcess(
        ["docker", "image", "rm"], 1, stdout="", stderr="conflict: image is used by a container"
    )
    with (
        mock.patch.object(
            pull_release_module.subprocess,
            "run",
            side_effect=[
                subprocess.CompletedProcess(["docker", "image", "ls"], 0, stdout=f"pcrstudio-api:{obsolete_sha}\n", stderr=""),
                refused_removal,
            ],
        ),
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        assert pull_release_module.prune_old_release_images(current_sha, previous_sha) == [
            f"kept old image pcrstudio-api:{obsolete_sha}; Docker refused removal: conflict: image is used by a container"
        ]

    # Narrow CI paths require direct executable coverage; unknown and sensitive
    # product/tooling paths must retain the broad qualification gates.
    def assert_scope(
        paths: list[str],
        *,
        full: bool,
        web: bool,
        contracts: bool = False,
        docs: bool = False,
        action_pins: bool = False,
        action_pins_only: bool = False,
    ) -> None:
        assert ci_scope.classify_paths(paths, action_pins_only=action_pins_only) == {
            "full": full,
            "web": web,
            "contracts": contracts,
            "docs": docs,
            "action_pins": action_pins,
        }

    assert_scope([], full=True, web=True)
    assert_scope(["README.md"], full=False, web=False, docs=True)
    assert_scope(["docs/OPERATIONS.md"], full=False, web=False, docs=True)
    assert_scope(["scripts/release_bundle.py"], full=False, web=False, contracts=True)
    assert_scope(["scripts/check-linux-bootstrap.py"], full=False, web=False, contracts=True)
    assert_scope(["scripts/classify-ci-scope.py"], full=False, web=False, contracts=True)
    assert_scope([".github/workflows/production-deploy.yml"], full=False, web=False, contracts=True)
    assert_scope([
        ".github/dependabot.yml",
        "contracts/maintenance-exceptions.json",
        "scripts/audit/release.py",
    ], full=False, web=False, contracts=True)
    assert_scope([
        ".github/dependabot.yml", "crates/pcr-core/src/lib.rs",
    ], full=True, web=False)
    assert_scope(["scripts/bootstrap-linux.py"], full=True, web=False)
    assert_scope(["crates/pcr-core/src/lib.rs"], full=True, web=False)
    assert_scope(["web/src/app/page.tsx"], full=True, web=True)
    assert_scope([".github/workflows/ci.yml"], full=True, web=False)
    assert_scope(["release/current/README.md"], full=True, web=False)
    assert_scope(["new-unknown-config.toml"], full=True, web=True)
    assert_scope(
        ["README.md", "scripts/pull-release.py"], full=False, web=False, contracts=True,
    )
    assert_scope(
        ["docs/OPERATIONS.md", "crates/pcr-core/src/lib.rs"], full=True, web=False,
    )
    assert_scope(
        [".github/workflows/codeql.yml"],
        full=False, web=False, action_pins=True, action_pins_only=True,
    )
    assert_scope(
        [".github/workflows/production-deploy.yml"],
        full=False, web=False, action_pins=True, action_pins_only=True,
    )
    assert_scope(
        [".github/workflows/codeql.yml", "README.md"],
        full=False, web=False, docs=True, action_pins=True, action_pins_only=True,
    )

    codeql_pin_diff = """diff --git a/.github/workflows/codeql.yml b/.github/workflows/codeql.yml
@@ -1 +1 @@
-        uses: github/codeql-action/init@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
+        uses: github/codeql-action/init@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
"""
    assert ci_scope.is_action_pin_only_diff_text(codeql_pin_diff)
    assert not ci_scope.is_action_pin_only_diff_text(
        codeql_pin_diff + "+        timeout-minutes: 30\n"
    )
    assert not ci_scope.is_action_pin_only_diff_text(
        codeql_pin_diff.replace(
            "-        uses: github/codeql-action/init@",
            "-        uses: attacker/other-action@",
        )
    )
    assert not ci_scope.is_action_pin_only_diff_text(
        codeql_pin_diff.replace("b" * 40, "v5")
    )
    assert ci_gate.validate_results(
        full="false", web="false", changes="success", fast="success",
        source="skipped", image="skipped", browser="skipped",
    ) == []
    assert ci_gate.validate_results(
        full="false", web="false", changes="success", fast="success",
        source="failure", image="skipped", browser="skipped",
    )
    assert ci_gate.validate_results(
        full="true", web="false", changes="success", fast="success",
        source="success", image="failure", browser="skipped",
    )
    assert ci_gate.validate_results(
        full="true", web="true", changes="success", fast="success",
        source="success", image="success", browser="failure",
    )
    assert ci_gate.validate_results(
        full="false", web="true", changes="success", fast="success",
        source="skipped", image="skipped", browser="success",
    )
    assert provision.ARTIFACTS["mafft"]["sha256"] == "bf59d016f1b2030bc7fc83b7715ae1f0823570de3bd059c26eb522a72f9c2952"
    assert provision.ARTIFACTS["mafft"]["mirror_urls"] == (
        "https://mafft.cbrc.jp/alignment/software/mafft-7.526-linux.tgz",
    )
    provision.verify_contract_alignment()
    check_download_retry_contract(provision)

    # Public and private bootstrap examples are one configuration contract.
    # Private mode changes values (loopback origin), not the set of supported
    # deployment keys; keeping this executable prevents documentation drift.
    def env_example_keys(path: Path) -> set[str]:
        keys: set[str] = set()
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                keys.add(line.split("=", 1)[0])
        return keys

    public_keys = env_example_keys(ROOT / ".env.example")
    private_keys = env_example_keys(ROOT / ".env.vm.example")
    assert public_keys == private_keys, (
        f"deployment env examples drifted: public-only={sorted(public_keys-private_keys)}, "
        f"private-only={sorted(private_keys-public_keys)}"
    )
    assert "NEXT_SERVER_ACTIONS_ENCRYPTION_KEY" not in public_keys
    assert "PCR_NEXT_SERVER_ACTIONS_KEY_FILE" in public_keys
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["packageManager"] == "pnpm@11.26.0"
    npmrc = (ROOT / ".npmrc").read_text(encoding="utf-8")
    assert "registry=https://registry.npmjs.com/" in npmrc
    assert "fetch-retries=6" in npmrc
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert ci.count("--allow network.host") == 4, "every direct CI image build must allow the build-only host network entitlement"
    pull_agent = (ROOT / "scripts" / "pull-release.py").read_text(encoding="utf-8")
    assert 'Path("/etc/systemd/system/pcrstudio-release-pull.service")' in pull_agent
    assert 'Path("/srv/pcrstudio").mkdir(parents=True, exist_ok=True)' in pull_agent
    assert "def remove_empty_path(path: Path) -> None" in pull_agent
    assert "if source != target:" in pull_agent
    production = (ROOT / ".github" / "workflows" / "production-deploy.yml").read_text(encoding="utf-8")
    release_verify = production.split("name: Verify release identity and deployment inputs", 1)[1].split(
        "name: Build the qualified runtime image set", 1
    )[0]
    manifest_before_attestation = release_verify.index("scripts/generate-release-manifests.py")
    attestation = release_verify.index("scripts/generate-source-attestation.py")
    manifest_after_attestation = release_verify.rindex("scripts/generate-release-manifests.py")
    source_check = release_verify.index("scripts/qualify-source.py --no-write")
    release_check = release_verify.index("scripts/verify-release.py --root .")
    assert manifest_before_attestation < attestation < manifest_after_attestation < source_check < release_check
    assert "path: .release-tooling" in production
    assert "github.event.repository.default_branch" in production
    assert "persist-credentials: false" in production
    assert "git -C .release-tooling rev-parse HEAD" in production
    assert "--bundle-tool-source-sha \"$BUNDLE_TOOL_SOURCE_SHA\"" in production
    assert "create-deploy-manifest" in production
    release_version = load("pcrstudio_release_version", ROOT / "scripts" / "validate-release-version.py")
    assert release_version.VERSION_RE.fullmatch("1.0.1")

    # Regression for compressed docker-save bundles: inspect tar members only
    # in their forward stream order. This remains cheap and proves portable
    # image IDs without creating an expanded archive on disk.
    with tempfile.TemporaryDirectory(prefix="pcrstudio-release-bundle-") as tmp:
        archive_path = Path(tmp) / "images.tar.gz"
        source_sha = "a" * 40
        configs = {
            f"pcrstudio-api:{source_sha}": (
                b'{"architecture":"amd64","config":{"Labels":{"role":"api"}}}'
            ),
            f"pcrstudio-runner:{source_sha}": (
                b'{"architecture":"amd64","config":{"Labels":{"role":"runner"}}}'
            ),
            f"pcrstudio-migrate:{source_sha}": (
                b'{"architecture":"amd64","config":{"Labels":{"role":"migrate"}}}'
            ),
            f"pcrstudio-web:{source_sha}": (
                b'{"architecture":"amd64","config":{"Labels":{"role":"web"}}}'
            ),
        }
        entries = []
        members: list[tuple[str, bytes]] = []
        expected_digests = {}
        for index, (tag, content) in enumerate(configs.items()):
            config_digest = hashlib.sha256(content).hexdigest()
            config_name = (
                f"blobs/sha256/{config_digest}"
                if index == 1
                else config_digest + ".json"
            )
            entries.append({"Config": config_name, "RepoTags": [tag], "Layers": ["layer/layer.tar"]})
            members.append((config_name, content))
            expected_digests[tag] = "sha256:" + config_digest
        with (
            archive_path.open("wb") as compressed_file,
            gzip.GzipFile(fileobj=compressed_file, mode="wb", mtime=0) as compressed_stream,
            tarfile.open(fileobj=compressed_stream, mode="w") as archive,
        ):
            manifest = json.dumps(entries, separators=(",", ":")).encode("utf-8")
            # Put one config before the manifest to preserve order-agnostic coverage.
            archive_members = [
                members[0],
                ("manifest.json", manifest),
                *members[1:],
                ("layer/layer.tar", b"layer-bytes-" * 4096),
            ]
            for name, content in archive_members:
                info = tarfile.TarInfo(name)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
        assert release_bundle.docker_save_config_digests(archive_path) == expected_digests

        source_archive = Path(tmp) / "source.tar.gz"
        source_archive.write_bytes(b"exact immutable source archive fixture\n")
        manifest = release_bundle.build_deployment_manifest(
            release_ref="v1.0.1",
            source_sha=source_sha,
            bundle_tool_source_sha="b" * 40,
            source_archive=source_archive,
            image_archive=archive_path,
        )
        assert manifest["source_sha"] == source_sha
        assert manifest["bundle_tool_source_sha"] == "b" * 40
        assert {image["name"] for image in manifest["images"]} == {
            "pcrstudio-api",
            "pcrstudio-runner",
            "pcrstudio-migrate",
            "pcrstudio-web",
        }
        manifest_path = Path(tmp) / "deployment-manifest.json"
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "release_bundle.py"),
                "create-deploy-manifest",
                "--release-ref",
                "v1.0.1",
                "--source-sha",
                source_sha,
                "--bundle-tool-source-sha",
                "b" * 40,
                "--source-archive",
                str(source_archive),
                "--image-archive",
                str(archive_path),
                "--output",
                str(manifest_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest

    if args.docker_save_integration:
        check_docker_save_integration(release_bundle)

    assert bootstrap.validate_domain("PCR.Example-Research.org.") == "pcr.example-research.org"
    for bad in ("localhost", "pcrstudio.example.org", "-bad.example.org", "bad..example.org", "bad host.example.org"):
        expect_system_exit(bootstrap.validate_domain, bad)

    assert bootstrap.validate_compose_project("PCRStudio_2") == "pcrstudio_2"
    assert bootstrap.parse_compose_version("v2.24.4") == (2, 24, 4)
    assert bootstrap.parse_compose_version("5.5.0") == (5, 5, 0)
    assert bootstrap.parse_compose_version("unknown") is None
    assert bootstrap.validate_runner_scratch_size("128m") == "128m"
    assert bootstrap.validate_runner_scratch_size("2g") == "2g"
    for bad_scratch_size in ("127m", "9g", "0", "two-gigabytes", "2gb"):
        expect_system_exit(bootstrap.validate_runner_scratch_size, bad_scratch_size)
    assert bootstrap.validate_storage_budget("20", "4") == ("20", "4")
    assert bootstrap.validate_storage_enforcement("HARD-QUOTA") == "hard-quota"
    assert bootstrap.validate_storage_enforcement("guard-only") == "guard-only"
    expect_system_exit(bootstrap.validate_storage_enforcement, "best-effort")
    gib = 1024 ** 3
    quota_entries = [
        ("application", Path("/srv/pcrstudio"), 42, 20 * gib),
        ("docker", Path("/srv/pcrstudio-storage/docker"), 42, 20 * gib),
        ("containerd", Path("/srv/pcrstudio-storage/containerd"), 42, 20 * gib),
    ]
    quota_layout = bootstrap.evaluate_hard_storage_layout(
        quota_entries, root_device=1, quota_gib=20
    )
    assert quota_layout["status"] == "PASS" and quota_layout["failures"] == []
    assert bootstrap.evaluate_hard_storage_layout(
        quota_entries, root_device=42, quota_gib=20
    )["status"] == "FAIL"
    assert bootstrap.evaluate_hard_storage_layout(
        [*quota_entries[:2], ("containerd", Path("/var/lib/containerd"), 43, 20 * gib)],
        root_device=1,
        quota_gib=20,
    )["status"] == "FAIL"
    assert bootstrap.evaluate_hard_storage_layout(
        [(role, path, device, 21 * gib) for role, path, device, _ in quota_entries],
        root_device=1,
        quota_gib=20,
    )["status"] == "FAIL"
    assert bootstrap.systemd_quote(Path("/srv/pcrstudio-current")) == "/srv/pcrstudio-current"
    assert "--control-plane-only" in (ROOT / "scripts" / "bootstrap-linux.py").read_text(encoding="utf-8")
    assert "--offline-pinned-images" in (ROOT / "scripts" / "bootstrap-linux.py").read_text(encoding="utf-8")
    assert "def api_image_ref(docker: list[str], image_tag: str)" in (ROOT / "scripts" / "bootstrap-linux.py").read_text(encoding="utf-8")
    assert bootstrap.validate_image_tag("release-abc123") == "release-abc123"
    for bad_tag in ("", "has/slash", "has space", "-leading"):
        expect_system_exit(bootstrap.validate_image_tag, bad_tag)
    for bad_reserves in (("4", "4"), ("3", "1"), ("65", "4"), ("twenty", "4")):
        try:
            bootstrap.validate_storage_budget(*bad_reserves)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"invalid storage reserves accepted: {bad_reserves}")

    pinned = bootstrap.pinned_external_image_refs(ROOT)
    assert len(pinned) == 6, pinned
    assert any(ref.startswith("rust:1.94-bookworm@sha256:") for ref in pinned)
    assert any(ref.startswith("busybox:1.37.0-glibc@sha256:") for ref in pinned)
    assert any(ref.startswith("postgres:18-alpine@sha256:") for ref in pinned)
    assert any(ref.startswith("caddy:2-alpine@sha256:") for ref in pinned)
    assert bootstrap.registry_error_class("dial tcp: lookup auth.docker.io: no such host") == "dns"
    assert bootstrap.registry_error_class("denied: requested access to the resource is denied") == "auth"
    assert bootstrap.registry_error_class("toomanyrequests: rate limit exceeded") == "rate-limit"
    assert bootstrap.registry_error_class("TLS handshake timeout") == "tls"
    assert bootstrap.registry_error_class("i/o timeout") == "transient-network"
    assert bootstrap.registry_error_class("ConnectTimeoutError: fetch failed") == "transient-network"
    assert bootstrap.registry_error_class("UND_ERR_CONNECT_TIMEOUT") == "transient-network"
    assert bootstrap.registry_error_class("[28] Timeout was reached (Operation too slow)") == "transient-network"
    assert bootstrap.registry_error_class("manifest unknown") == "registry-or-pin"

    assert str(bootstrap.validate_compose_subnet("PCR_APP_SUBNET", "172.29.0.0/24")) == "172.29.0.0/24"
    assert str(bootstrap.validate_compose_subnet("PCR_DATA_SUBNET", "10.251.0.0/24")) == "10.251.0.0/24"
    for bad_subnet in (
        "172.29.0.42/24",  # host bits hidden by strict=False in the old bootstrap
        "0.0.0.0/0",
        "100.64.0.0/24",   # CGNAT is not RFC1918
        "192.0.2.0/24",    # TEST-NET is not RFC1918
        "172.29.0.0/30",   # too small for a durable Compose trust zone
        "2001:db8::/64",
    ):
        try:
            bootstrap.validate_compose_subnet("PCR_APP_SUBNET", bad_subnet)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"unsafe/noncanonical Compose subnet accepted: {bad_subnet}")
    assert bootstrap.resource_profile_for_memory(4 * 1024**3)[0] == "compact"
    assert bootstrap.resource_profile_for_memory(8 * 1024**3)[0] == "standard"
    assert bootstrap.resource_profile_for_memory(16 * 1024**3)[0] == "large"
    bootstrap.validate_optional_service_secret("PCR_OPERATOR_TOKEN", "a" * 24)
    bootstrap.validate_optional_service_secret("PCR_NCBI_API_KEY", "api-key_123")
    for name, invalid in (
        ("PCR_OPERATOR_TOKEN", "short"),
        ("PCR_OPERATOR_TOKEN", "a" * 23 + " "),
        ("PCR_NCBI_API_KEY", "key with spaces"),
        ("PCR_NCBI_API_KEY", "é"),
        ("PCR_OPERATOR_TOKEN", "é" * 24),
        ("PCR_NCBI_API_KEY", "x" * 513),
    ):
        try:
            bootstrap.validate_optional_service_secret(name, invalid)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"invalid optional service secret accepted: {name}={invalid!r}")
    try:
        bootstrap.resource_profile_for_memory(3 * 1024**3)
    except SystemExit:
        pass
    else:
        raise AssertionError("sub-4GiB production hosts must fail closed")

    q = {
        "SCIENTIFIC_FREEZE_SHA256": "a" * 64,
        "MAFFT_ARCHIVE_SHA256": "b" * 64,
        "MAFFT_BUNDLE_SHA256": "c" * 64,
    }
    identities: dict[str, str] = {}
    assert bootstrap.approve_immutable_scientific_identity(identities, q, allow_change=False) == "a" * 64
    drift = dict(q); drift["SCIENTIFIC_FREEZE_SHA256"] = "d" * 64
    try:
        bootstrap.approve_immutable_scientific_identity(identities, drift, allow_change=False)
    except SystemExit:
        pass
    else:
        raise AssertionError("scientific identity drift must fail closed without explicit approval")
    bootstrap.approve_immutable_scientific_identity(identities, drift, allow_change=True)
    assert identities["PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256"] == "d" * 64
    for bad in ("", "-pcrstudio", "PCR Studio", "a" * 64):
        expect_system_exit(bootstrap.validate_compose_project, bad)

    with tempfile.TemporaryDirectory(prefix="pcrstudio-bootstrap-source-") as tmp:
        root = Path(tmp)
        env = root / ".env"
        env.write_text("GOOD=value\nBAD-KEY=ignored\nQUOTED='hello world'\n# comment\n", encoding="utf-8")
        assert bootstrap.parse_env(env) == {"GOOD": "value", "QUOTED": "hello world"}

        secret = root / "secret"
        bootstrap.atomic_write(secret, "value\n", 0o600)
        assert secret.read_text(encoding="utf-8") == "value\n"
        assert stat.S_IMODE(secret.stat().st_mode) == 0o600

        # Compose file-backed secrets preserve host file metadata on Linux.
        # Test the permission primitive with this process' own group so the
        # regression remains sudo-free on developer machines.
        runtime_gid = bootstrap.PCR_RUNTIME_GID
        bootstrap.PCR_RUNTIME_GID = os.getgid()
        try:
            bootstrap.make_runtime_secret_readable(secret)
            assert secret.stat().st_gid == os.getgid()
            assert stat.S_IMODE(secret.stat().st_mode) == 0o640
        finally:
            bootstrap.PCR_RUNTIME_GID = runtime_gid

        bundle = root / "bundle"
        bundle.mkdir()
        (bundle / "bin").mkdir()
        tool = bundle / "bin" / "tool"
        tool.write_bytes(b"one")
        tool.chmod(0o755)
        first = provision.tree_sha256(bundle)
        assert len(first) == 64
        assert first == provision.tree_sha256(bundle)
        tool.write_bytes(b"two")
        assert provision.tree_sha256(bundle) != first
        tool.write_bytes(b"one")
        tool.chmod(0o644)
        assert provision.tree_sha256(bundle) != first, "bundle digest must bind executable modes"

        # Disk preflight must aggregate roles that share one filesystem and
        # account for reference-index expansion without touching Docker. The
        # test controls the reported capacity so it remains deterministic on
        # small CI containers whose real /tmp filesystem may be below the
        # production safety threshold.
        fasta = root / "reference.fasta"
        fasta.write_text(">ref\nACGTACGT\n", encoding="ascii")
        bootstrap.docker_root_dir = lambda _docker: root
        real_disk_usage = shutil.disk_usage
        disk_usage_type = type(real_disk_usage(root))
        shutil.disk_usage = lambda _path: disk_usage_type(32 * 1024**3, 0, 32 * 1024**3)
        try:
            disk = bootstrap.preflight_disk_capacity(
                ["docker"],
                reference_fasta=fasta,
                scientific_db_dir=root / "science-db",
            )
        finally:
            shutil.disk_usage = real_disk_usage
        assert disk["ok"] is True
        assert disk["reference_fasta_bytes"] == fasta.stat().st_size
        assert disk["checks"], disk

    suffix = " with real docker-save integration" if args.docker_save_integration else ""
    print(f"Linux bootstrap/provision source regression PASS{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
