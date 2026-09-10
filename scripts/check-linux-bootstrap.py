#!/usr/bin/env python3
"""Dependency-free regression checks for Linux bootstrap/provision invariants."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_system_exit(fn, value: str) -> None:
    try:
        fn(value)
    except SystemExit:
        return
    raise AssertionError(f"expected rejection for {value!r}")


def main() -> int:
    bootstrap = load("pcrstudio_bootstrap_linux", ROOT / "scripts" / "bootstrap-linux.py")
    provision = load("pcrstudio_provision_tools", ROOT / "scripts" / "provision-tools.py")

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
    assert "if source != target:" in pull_agent
    release_version = load("pcrstudio_release_version", ROOT / "scripts" / "validate-release-version.py")
    assert release_version.VERSION_RE.fullmatch("1.0.1")

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

    print("Linux bootstrap/provision source regression PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
