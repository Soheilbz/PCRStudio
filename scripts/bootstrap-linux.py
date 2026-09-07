#!/usr/bin/env python3
"""One-command PCRStudio production bootstrap for Debian/Ubuntu Linux x86_64.

The bootstrap is intentionally fail-closed. It can install the minimum Docker
host dependencies, creates file-backed secrets, builds the exact API/Web
images, qualifies the bundled scientific toolchain, optionally builds an
approved specificity database inside that same API image, starts the stack and
verifies application + scientific readiness. No scientific freeze is approved
until the image-level smoke gate has passed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
SECRETS = LOCAL / "secrets"
DEPLOY = LOCAL / "deploy"
DEFAULT_ENV = ROOT / ".env"


def run(argv: Iterable[str], *, capture: bool = False, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    args = [str(x) for x in argv]
    print(">", shlex.join(args))
    cp = subprocess.run(args, cwd=ROOT, text=True, capture_output=capture, env=env, check=False)
    if check and cp.returncode:
        if capture:
            if cp.stdout: print(cp.stdout, end="")
            if cp.stderr: print(cp.stderr, end="", file=sys.stderr)
        raise SystemExit(f"command failed ({cp.returncode}): {shlex.join(args)}")
    return cp


def require_linux() -> None:
    if not sys.platform.startswith("linux"):
        raise SystemExit("PCRStudio production bootstrap supports Linux only.")
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        raise SystemExit(f"Pinned scientific artifacts require Linux x86_64; detected {machine!r}.")


def read_os_release() -> dict[str, str]:
    out: dict[str, str] = {}
    path = Path("/etc/os-release")
    if path.is_file():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" not in raw: continue
            k, v = raw.split("=", 1)
            out[k] = v.strip().strip('"')
    return out


def sudo_prefix() -> list[str]:
    if os.geteuid() == 0:
        return []
    sudo = shutil.which("sudo")
    if not sudo:
        raise SystemExit("system package installation needs root or sudo")
    return [sudo]


def parse_compose_version(raw: str) -> tuple[int, int, int] | None:
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", raw.strip())
    return tuple(map(int, match.groups())) if match else None


def existing_docker_prefix() -> list[str] | None:
    """Return an already-usable Docker/Compose command without mutating host packages."""
    docker = shutil.which("docker")
    if not docker:
        return None
    candidates: list[list[str]] = [[docker]]
    if os.geteuid() != 0 and shutil.which("sudo"):
        candidates.append(["sudo", docker])
    for prefix in candidates:
        info = subprocess.run([*prefix, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        compose = subprocess.run(
            [*prefix, "compose", "version", "--short"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        version = parse_compose_version(compose.stdout) if compose.returncode == 0 else None
        if info.returncode == 0 and version is not None and version >= (2, 24, 4):
            return prefix
    return None


def install_system_dependencies() -> None:
    # The default bootstrap is safe on an already-managed Docker host: never
    # replace a sufficient engine/plugin merely because --install-system-deps
    # was requested by bootstrap.sh.
    if existing_docker_prefix() is not None:
        print("Docker Engine + Compose >=2.24.4 are already usable; leaving host packages unchanged")
        return

    info = read_os_release()
    distro = info.get("ID", "").strip().lower()
    if distro not in {"debian", "ubuntu"}:
        raise SystemExit(
            f"automatic official Docker repository setup supports Debian/Ubuntu only; detected {distro or 'unknown'}"
        )
    codename = (info.get("UBUNTU_CODENAME") if distro == "ubuntu" else None) or info.get("VERSION_CODENAME")
    if not codename or not re.fullmatch(r"[a-z0-9._-]+", codename):
        raise SystemExit("could not determine a safe Debian/Ubuntu release codename from /etc/os-release")
    dpkg = shutil.which("dpkg")
    if not dpkg:
        raise SystemExit("dpkg is required for automatic Debian/Ubuntu Docker installation")
    arch_cp = subprocess.run([dpkg, "--print-architecture"], capture_output=True, text=True, check=False)
    arch = arch_cp.stdout.strip()
    if arch_cp.returncode != 0 or not re.fullmatch(r"[a-z0-9_-]+", arch):
        raise SystemExit("could not determine dpkg architecture")

    sudo = sudo_prefix()
    run([*sudo, "apt-get", "update"])
    run([*sudo, "apt-get", "install", "-y", "ca-certificates", "curl"])
    run([*sudo, "install", "-m", "0755", "-d", "/etc/apt/keyrings"])

    # Docker's supported apt-repository flow. The GPG key itself is fetched
    # over HTTPS from download.docker.com and then installed as a root-owned,
    # world-readable keyring; no convenience install script is executed.
    with tempfile.TemporaryDirectory(prefix="pcrstudio-docker-repo-") as tmp:
        key = Path(tmp) / "docker.asc"
        run(["curl", "-fsSL", f"https://download.docker.com/linux/{distro}/gpg", "-o", str(key)])
        if not key.is_file() or key.stat().st_size < 1000:
            raise SystemExit("Docker repository signing key download is unexpectedly empty")
        run([*sudo, "install", "-o", "root", "-g", "root", "-m", "0644", str(key), "/etc/apt/keyrings/docker.asc"])

        source = Path(tmp) / "docker.sources"
        source.write_text(
            "Types: deb\n"
            f"URIs: https://download.docker.com/linux/{distro}\n"
            f"Suites: {codename}\n"
            "Components: stable\n"
            f"Architectures: {arch}\n"
            "Signed-By: /etc/apt/keyrings/docker.asc\n",
            encoding="utf-8",
        )
        run([*sudo, "install", "-o", "root", "-g", "root", "-m", "0644", str(source), "/etc/apt/sources.list.d/docker.sources"])

    # Docker documents these distro packages as conflicting with Docker CE.
    # Removing packages does not delete /var/lib/docker; this path is entered
    # only after explicit --install-system-deps and only when no sufficient
    # existing Docker installation was usable.
    run([
        *sudo, "apt-get", "remove", "-y",
        "docker.io", "docker-compose", "docker-compose-v2", "docker-doc",
        "docker-buildx", "podman-docker", "containerd", "runc",
    ], check=False)
    run([*sudo, "apt-get", "update"])
    run([
        *sudo, "apt-get", "install", "-y",
        "docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin",
    ])
    if shutil.which("systemctl"):
        run([*sudo, "systemctl", "enable", "--now", "docker"])


def docker_prefix() -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise SystemExit("docker is unavailable; rerun with --install-system-deps or install Docker Engine + Compose v2")
    direct = subprocess.run([docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if direct:
        prefix = [docker]
    elif os.geteuid() != 0 and shutil.which("sudo") and subprocess.run(["sudo", "docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        prefix = ["sudo", "docker"]
    else:
        raise SystemExit("Docker daemon is unavailable or the current user has no permission to use it")
    cp = subprocess.run([*prefix, "compose", "version", "--short"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if cp.returncode:
        raise SystemExit("Docker Compose v2+ (`docker compose`) is required")
    raw_version = cp.stdout.strip().lstrip("v")
    version = parse_compose_version(raw_version)
    if version is None:
        raise SystemExit(f"could not parse Docker Compose version: {cp.stdout.strip()!r}")
    if version < (2, 24, 4):
        raise SystemExit(f"Docker Compose >= 2.24.4 is required by the private-profile !override contract; found {raw_version}")
    print(f"Docker Compose {raw_version}")
    return prefix


def nearest_existing_parent(path: Path) -> Path:
    candidate = path.resolve()
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return candidate


def disk_free_bytes(path: Path) -> int:
    target = nearest_existing_parent(path)
    return shutil.disk_usage(target).free


def docker_root_dir(docker: list[str]) -> Path:
    cp = subprocess.run(
        [*docker, "info", "--format", "{{.DockerRootDir}}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if cp.returncode == 0 and cp.stdout.strip():
        return Path(cp.stdout.strip())
    return Path("/var/lib/docker")


def preflight_disk_capacity(
    docker: list[str],
    *,
    reference_fasta: Path | None,
    scientific_db_dir: Path,
    runner_scratch_dir: Path,
) -> dict[str, int | str | bool]:
    """Fail before an expensive build when the host cannot safely stage it.

    The Docker build allowance covers Rust/Node/scientific build layers and
    transient package caches. The local-data allowance covers database indexes,
    runner scratch, manifests and one operational reserve. Reference indexes can
    expand several-fold, so a 6x multiplier is intentionally conservative.
    """
    gib = 1024 ** 3
    fasta_bytes = 0
    if reference_fasta is not None:
        reference_fasta = reference_fasta.expanduser().resolve()
        if not reference_fasta.is_file():
            raise SystemExit(f"reference FASTA does not exist or is not a regular file: {reference_fasta}")
        fasta_bytes = reference_fasta.stat().st_size
        if fasta_bytes <= 0:
            raise SystemExit("reference FASTA is empty")

    docker_root = nearest_existing_parent(docker_root_dir(docker))
    local_root = nearest_existing_parent(scientific_db_dir)
    scratch_root = nearest_existing_parent(runner_scratch_dir)
    docker_required = 10 * gib
    local_required = 4 * gib + fasta_bytes * 6
    scratch_required = 2 * gib

    roots = {
        "docker": (docker_root, docker_required),
        "scientific_data": (local_root, local_required),
        "runner_scratch": (scratch_root, scratch_required),
    }
    by_device: dict[int, dict[str, object]] = {}
    for role, (path, required) in roots.items():
        st = path.stat()
        bucket = by_device.setdefault(st.st_dev, {"path": path, "required": 0, "roles": []})
        bucket["required"] = int(bucket["required"]) + required
        cast_roles = bucket["roles"]
        assert isinstance(cast_roles, list)
        cast_roles.append(role)

    checks: list[dict[str, object]] = []
    for bucket in by_device.values():
        path = bucket["path"]
        assert isinstance(path, Path)
        required = int(bucket["required"])
        free = shutil.disk_usage(path).free
        roles = list(bucket["roles"])
        checks.append({
            "path": str(path),
            "roles": roles,
            "free_bytes": free,
            "required_bytes": required,
            "ok": free >= required,
        })
        if free < required:
            raise SystemExit(
                "insufficient free disk for Linux production bootstrap on "
                f"{path}: need at least {required / gib:.1f} GiB for {','.join(roles)}, "
                f"found {free / gib:.1f} GiB"
            )

    return {
        "reference_fasta_bytes": fasta_bytes,
        "docker_root": str(docker_root),
        "scientific_db_root": str(local_root),
        "runner_scratch_root": str(scratch_root),
        "checks": checks,
        "ok": True,
    }


def atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush(); os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        os.chmod(path, mode)
    finally:
        tmp.unlink(missing_ok=True)


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file(): return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k): out[k] = v.strip().strip('"').strip("'")
    return out


def write_env(path: Path, values: dict[str, str]) -> None:
    order = [
        "SITE_DOMAIN", "SITE_URL", "PCRSTUDIO_COMPOSE_PROJECT", "POSTGRES_USER", "POSTGRES_DB",
        "PCR_POSTGRES_PASSWORD_FILE", "PCR_DATABASE_URL_FILE_HOST", "PCR_NEXT_SERVER_ACTIONS_KEY_FILE",
        "PCR_OPERATOR_TOKEN_FILE_HOST", "PCR_NCBI_API_KEY_FILE_HOST",
        "PCRSTUDIO_BUILD_ID", "PCR_SCIENTIFIC_DB_DIR",
        "PCR_SCIENTIFIC_DB_ID", "PCR_SCIENTIFIC_DB_SHA256", "PCR_SCIENTIFIC_DB_SCOPE",
        "PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256",
        "PCRSTUDIO_QUALIFIED_MAFFT_ARCHIVE_SHA256", "PCRSTUDIO_QUALIFIED_MAFFT_BUNDLE_SHA256",
        "PCR_RESOURCE_PROFILE", "PCR_DB_MEMORY_LIMIT", "PCR_API_MEMORY_LIMIT",
        "PCR_RUNNER_MEMORY_LIMIT", "PCR_WEB_MEMORY_LIMIT", "PCR_CADDY_MEMORY_LIMIT",
        "PCR_API_MAX_CONCURRENT_WORKERS", "PCR_API_MAX_QUEUED_WORKERS",
        "PCR_RUNNER_MAX_CONCURRENT_WORKERS", "PCR_RUNNER_MAX_QUEUED_WORKERS",
        "PCR_RUNNER_POLL_MILLISECONDS", "PCR_WORKER_TIMEOUT_SECONDS", "PCR_DB_ACQUIRE_TIMEOUT_SECONDS",
        "PCR_CORS_ORIGINS", "PCR_NCBI_EMAIL",
        "PCR_EDGE_SUBNET", "PCR_APP_SUBNET", "PCR_DATA_SUBNET",
        "PCRSTUDIO_BACKUP_RETENTION_DAYS", "RUST_LOG",
    ]
    lines = ["# Generated/maintained by scripts/bootstrap-linux.py; chmod 0600."]
    for key in order:
        if key in values: lines.append(f"{key}={values[key]}")
    for key in sorted(set(values) - set(order)):
        lines.append(f"{key}={values[key]}")
    atomic_write(path, "\n".join(lines) + "\n", 0o600)


def host_memory_bytes() -> int:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemTotal:"):
                parts = line.split()
                return int(parts[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def resource_profile_for_memory(total_bytes: int) -> tuple[str, dict[str, str]]:
    gib = total_bytes / (1024 ** 3) if total_bytes else 0.0
    if total_bytes and gib < 4.0:
        raise SystemExit(
            f"PCRStudio scientific production bootstrap requires at least 4 GiB RAM; detected {gib:.1f} GiB"
        )
    if not total_bytes or gib < 8.0:
        return "compact", {
            "PCR_DB_MEMORY_LIMIT": "512m",
            "PCR_API_MEMORY_LIMIT": "768m",
            "PCR_RUNNER_MEMORY_LIMIT": "1536m",
            "PCR_WEB_MEMORY_LIMIT": "512m",
            "PCR_CADDY_MEMORY_LIMIT": "128m",
            "PCR_API_MAX_CONCURRENT_WORKERS": "1",
            "PCR_API_MAX_QUEUED_WORKERS": "32",
            "PCR_RUNNER_MAX_CONCURRENT_WORKERS": "1",
            "PCR_RUNNER_MAX_QUEUED_WORKERS": "128",
        }
    if gib < 16.0:
        return "standard", {
            "PCR_DB_MEMORY_LIMIT": "1g",
            "PCR_API_MEMORY_LIMIT": "1g",
            "PCR_RUNNER_MEMORY_LIMIT": "3g",
            "PCR_WEB_MEMORY_LIMIT": "768m",
            "PCR_CADDY_MEMORY_LIMIT": "192m",
            "PCR_API_MAX_CONCURRENT_WORKERS": "2",
            "PCR_API_MAX_QUEUED_WORKERS": "64",
            "PCR_RUNNER_MAX_CONCURRENT_WORKERS": "2",
            "PCR_RUNNER_MAX_QUEUED_WORKERS": "256",
        }
    return "large", {
        "PCR_DB_MEMORY_LIMIT": "2g",
        "PCR_API_MEMORY_LIMIT": "2g",
        "PCR_RUNNER_MEMORY_LIMIT": "6g",
        "PCR_WEB_MEMORY_LIMIT": "1g",
        "PCR_CADDY_MEMORY_LIMIT": "256m",
        "PCR_API_MAX_CONCURRENT_WORKERS": "2",
        "PCR_API_MAX_QUEUED_WORKERS": "64",
        "PCR_RUNNER_MAX_CONCURRENT_WORKERS": "4",
        "PCR_RUNNER_MAX_QUEUED_WORKERS": "256",
    }


def configure_resource_profile(values: dict[str, str]) -> tuple[str, int, int]:
    total = host_memory_bytes()
    cpus = max(1, os.cpu_count() or 1)
    profile, defaults = resource_profile_for_memory(total)
    # Memory profiles provide upper bounds; do not create more concurrent
    # scientific workers than the host can schedule sensibly. One CPU remains
    # a valid compact deployment with one runner worker.
    defaults["PCR_RUNNER_MAX_CONCURRENT_WORKERS"] = str(
        min(int(defaults["PCR_RUNNER_MAX_CONCURRENT_WORKERS"]), max(1, cpus - 1))
    )
    defaults["PCR_API_MAX_CONCURRENT_WORKERS"] = str(
        min(int(defaults["PCR_API_MAX_CONCURRENT_WORKERS"]), max(1, cpus // 2))
    )
    configured_profile = values.get("PCR_RESOURCE_PROFILE", "").strip().lower()
    if configured_profile and configured_profile not in {"compact", "standard", "large", "custom"}:
        raise SystemExit("PCR_RESOURCE_PROFILE must be compact, standard, large, or custom")
    # Explicit limits always win; profile names are evidence, not a mechanism
    # that overwrites operator-reviewed values. Any override makes it custom.
    overridden = False
    for key, default in defaults.items():
        if values.get(key, "").strip():
            overridden = overridden or values[key].strip() != default
        else:
            values[key] = default
    resolved = "custom" if overridden or configured_profile == "custom" else profile
    values["PCR_RESOURCE_PROFILE"] = resolved
    return resolved, total, cpus


def validate_domain(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    if len(value) > 253 or not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value):
        raise SystemExit(f"invalid public DNS hostname: {value!r}")
    if value == "example.org" or value.endswith(".example.org") or value.endswith(".example.com") or value.endswith(".example.net"):
        raise SystemExit("refusing placeholder public domain; pass the real DNS hostname or use --private")
    return value


def validate_compose_project(value: str) -> str:
    value = value.strip().lower()
    # Docker Compose project names are intentionally conservative here because
    # they become durable prefixes for networks/volumes/containers.
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", value):
        raise SystemExit("PCRSTUDIO_COMPOSE_PROJECT must match [a-z0-9][a-z0-9_-]{0,62}")
    return value


def docker_subnets(docker: list[str], project_name: str) -> list[ipaddress._BaseNetwork]:
    """Return occupied networks, excluding this checkout's own Compose networks.

    Docker also installs host routes for bridge networks. Those routes are
    excluded when they correspond exactly to a same-project subnet so rerunning
    bootstrap is idempotent instead of reporting its own previous networks as a
    collision.
    """
    networks: list[ipaddress._BaseNetwork] = []
    own: set[ipaddress._BaseNetwork] = set()
    cp = run([*docker, "network", "ls", "-q"], capture=True, check=False)
    ids = cp.stdout.split() if cp.returncode == 0 else []
    if ids:
        info = run([*docker, "network", "inspect", *ids], capture=True, check=False)
        if info.returncode == 0:
            try:
                for item in json.loads(info.stdout):
                    labels = item.get("Labels") or {}
                    workdir = labels.get("com.docker.compose.project.working_dir")
                    project = (labels.get("com.docker.compose.project") or "").strip().lower()
                    is_own = project == project_name
                    if not is_own and workdir:
                        try:
                            is_own = Path(workdir).resolve() == ROOT.resolve()
                        except OSError:
                            is_own = False
                    for cfg in (item.get("IPAM") or {}).get("Config") or []:
                        raw = cfg.get("Subnet")
                        if raw:
                            try:
                                net = ipaddress.ip_network(raw, strict=False)
                            except ValueError:
                                continue
                            if is_own:
                                own.add(net)
                            else:
                                networks.append(net)
            except json.JSONDecodeError:
                pass
    ip = shutil.which("ip")
    if ip:
        cp = subprocess.run([ip, "-j", "route"], capture_output=True, text=True)
        if cp.returncode == 0:
            try:
                for row in json.loads(cp.stdout):
                    raw = row.get("dst")
                    if raw and raw != "default":
                        try:
                            net = ipaddress.ip_network(raw, strict=False)
                        except ValueError:
                            continue
                        if net not in own:
                            networks.append(net)
            except json.JSONDecodeError:
                pass
    return networks


RFC1918_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"
))


def validate_compose_subnet(key: str, raw: str) -> ipaddress.IPv4Network:
    """Return one canonical, usable RFC1918 IPv4 network for a trust zone."""
    try:
        network = ipaddress.ip_network(raw, strict=True)
    except ValueError as exc:
        raise SystemExit(f"{key} must be a canonical IPv4 CIDR (network address, not a host address): {raw}") from exc
    if not isinstance(network, ipaddress.IPv4Network):
        raise SystemExit(f"{key} must be an IPv4 RFC1918 network: {raw}")
    if not 16 <= network.prefixlen <= 28:
        raise SystemExit(f"{key} prefix must be between /16 and /28: {raw}")
    if not any(network.subnet_of(private) for private in RFC1918_NETWORKS):
        raise SystemExit(f"{key} must be contained in RFC1918 address space: {raw}")
    return network


def choose_subnets(docker: list[str], values: dict[str, str], force: bool) -> None:
    project_name = validate_compose_project(values.get("PCRSTUDIO_COMPOSE_PROJECT", "pcrstudio"))
    values["PCRSTUDIO_COMPOSE_PROJECT"] = project_name
    occupied = docker_subnets(docker, project_name)
    keys = ["PCR_EDGE_SUBNET", "PCR_APP_SUBNET", "PCR_DATA_SUBNET"]
    candidates = [
        *(f"172.{n}.0.0/24" for n in range(28, 16, -1)),
        *(f"10.25{n}.0.0/24" for n in range(1, 5)),
    ]
    chosen: list[ipaddress._BaseNetwork] = []
    for key in keys:
        raw = values.get(key, "").strip()
        if raw and not force:
            net = validate_compose_subnet(key, raw)
            conflicts = [x for x in occupied + chosen if x.version == net.version and x.overlaps(net)]
            if conflicts:
                raise SystemExit(f"{key}={net} overlaps existing route/network {conflicts[0]}; rerun with --reselect-subnets")
            chosen.append(net); continue
        for candidate in candidates:
            net = ipaddress.ip_network(candidate)
            if all(not (x.version == net.version and x.overlaps(net)) for x in occupied + chosen):
                values[key] = str(net); chosen.append(net); break
        else:
            raise SystemExit(f"could not select a non-conflicting subnet for {key}")


def ensure_runner_scratch(values: dict[str, str]) -> Path:
    raw = values.get("PCR_RUNNER_SCRATCH_DIR", "./.local/runner-scratch")
    path = (ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    local_root = LOCAL.resolve()
    if path != local_root and local_root not in path.parents:
        raise SystemExit(f"bootstrap-managed runner scratch must live under {local_root}: {path}")
    path.mkdir(parents=True, exist_ok=True)
    # Runtime UID is fixed by docker/api.Dockerfile. Use install/chown through
    # sudo when the invoking user cannot change ownership directly.
    try:
        os.chown(path, 10001, 10001)
        os.chmod(path, 0o700)
    except PermissionError:
        sudo = sudo_prefix()
        run([*sudo, "chown", "10001:10001", str(path)])
        run([*sudo, "chmod", "0700", str(path)])
    return path


PCR_RUNTIME_GID = 10001


def make_runtime_secret_readable(path: Path) -> None:
    """Keep a host-owned secret private while allowing the unprivileged PCR runtime to read it.

    Compose implements file-backed secrets as bind mounts on Linux, so source
    uid/gid/mode are preserved and Compose cannot remap them. The bootstrap
    user remains the owner; only the fixed PCR runtime group gets read access.
    """
    if not path.is_file():
        raise SystemExit(f"runtime secret is not a regular file: {path}")
    try:
        os.chown(path, -1, PCR_RUNTIME_GID)
        os.chmod(path, 0o640)
    except PermissionError:
        sudo = sudo_prefix()
        run([*sudo, "chown", f":{PCR_RUNTIME_GID}", str(path)])
        run([*sudo, "chmod", "0640", str(path)])
    mode = stat.S_IMODE(path.stat().st_mode)
    if path.stat().st_gid != PCR_RUNTIME_GID or mode != 0o640:
        raise SystemExit(
            f"runtime secret must be host-owner/PCR-group readable (gid={PCR_RUNTIME_GID}, mode=0640): {path}"
        )


def validate_optional_service_secret(name: str, value: str) -> None:
    """Validate optional HTTP-header credentials before Compose starts.

    These values eventually become HTTP header values, so the bootstrap and
    server deliberately share the same conservative contract: visible ASCII
    only, no whitespace, with service-specific length bounds.
    """
    if not value:
        return
    visible_ascii = value.isascii() and all(33 <= ord(ch) <= 126 for ch in value)
    if name == "PCR_OPERATOR_TOKEN":
        if not 24 <= len(value) <= 512 or not visible_ascii:
            raise SystemExit(
                "operator token must contain 24..=512 visible ASCII characters with no whitespace"
            )
        return
    if name == "PCR_NCBI_API_KEY":
        if len(value) > 512 or not visible_ascii:
            raise SystemExit(
                "NCBI API key must contain 1..=512 visible ASCII characters with no whitespace"
            )
        return
    raise AssertionError(f"unknown optional service secret policy: {name}")


def ensure_secrets(values: dict[str, str]) -> None:
    SECRETS.mkdir(parents=True, exist_ok=True); os.chmod(SECRETS, 0o700)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,62}", values.get("POSTGRES_USER", "")):
        raise SystemExit("POSTGRES_USER must be a simple PostgreSQL identifier")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,62}", values.get("POSTGRES_DB", "")):
        raise SystemExit("POSTGRES_DB must be a simple PostgreSQL identifier")
    secret_root = SECRETS.resolve()
    password_path = (ROOT / values["PCR_POSTGRES_PASSWORD_FILE"]).resolve()
    url_path = (ROOT / values["PCR_DATABASE_URL_FILE_HOST"]).resolve()
    actions_path = (ROOT / values["PCR_NEXT_SERVER_ACTIONS_KEY_FILE"]).resolve()
    operator_path = (ROOT / values["PCR_OPERATOR_TOKEN_FILE_HOST"]).resolve()
    ncbi_key_path = (ROOT / values["PCR_NCBI_API_KEY_FILE_HOST"]).resolve()
    for candidate in (password_path, url_path, actions_path, operator_path, ncbi_key_path):
        if candidate.parent != secret_root:
            raise SystemExit(f"bootstrap-managed secret must live directly under {secret_root}: {candidate}")
    if not password_path.is_file():
        atomic_write(password_path, secrets.token_urlsafe(48) + "\n", 0o600)
    else:
        os.chmod(password_path, 0o600)
    password = password_path.read_text(encoding="utf-8").strip()
    if len(password) < 32: raise SystemExit("existing PostgreSQL secret is too short; expected at least 32 characters")
    user = values["POSTGRES_USER"]; db = values["POSTGRES_DB"]
    url = f"postgres://{urllib.parse.quote(user, safe='')}:{urllib.parse.quote(password, safe='')}@db:5432/{urllib.parse.quote(db, safe='')}"
    atomic_write(url_path, url + "\n", 0o600)
    # Migrate the legacy .env value once, then remove it from the persisted
    # environment. BuildKit consumes only the file-backed secret.
    legacy_key = values.pop("NEXT_SERVER_ACTIONS_ENCRYPTION_KEY", "").strip()
    if legacy_key and not actions_path.exists():
        atomic_write(actions_path, legacy_key + "\n", 0o600)
    if not actions_path.is_file():
        atomic_write(actions_path, base64.b64encode(secrets.token_bytes(32)).decode("ascii") + "\n", 0o600)
    else:
        os.chmod(actions_path, 0o600)
    key = actions_path.read_text(encoding="utf-8").strip()
    try:
        decoded = base64.b64decode(key, validate=True)
    except Exception as exc:
        raise SystemExit("Server Actions key file must contain canonical base64") from exc
    if len(decoded) not in {16, 24, 32} or base64.b64encode(decoded).decode("ascii") != key:
        raise SystemExit("Server Actions key file must decode to exactly 16, 24, or 32 AES key bytes")

    # Optional service credentials are file-backed as well. Migrate legacy .env
    # values exactly once; an empty private file represents a disabled optional
    # capability and remains a valid Docker secret source.
    for legacy_name, secret_path, label in (
        ("PCR_OPERATOR_TOKEN", operator_path, "operator token"),
        ("PCR_NCBI_API_KEY", ncbi_key_path, "NCBI API key"),
    ):
        legacy = values.pop(legacy_name, "").strip()
        if legacy:
            if secret_path.exists():
                existing = secret_path.read_text(encoding="utf-8").rstrip("\r\n")
                if existing and existing != legacy:
                    raise SystemExit(
                        f"conflicting legacy {legacy_name} and file-backed {label}; keep one value"
                    )
                if not existing:
                    atomic_write(secret_path, legacy + "\n", 0o600)
            else:
                atomic_write(secret_path, legacy + "\n", 0o600)
        elif not secret_path.exists():
            atomic_write(secret_path, "", 0o600)
        else:
            os.chmod(secret_path, 0o600)
        configured = secret_path.read_text(encoding="utf-8").removesuffix("\n").removesuffix("\r")
        validate_optional_service_secret(legacy_name, configured)

    # API, migrator, and runner execute as uid/gid 10001. File-backed Compose
    # secrets are bind mounts on Linux, so grant only that runtime group read
    # permission while preserving host-user ownership and write authority.
    for runtime_secret in (url_path, operator_path, ncbi_key_path):
        make_runtime_secret_readable(runtime_secret)


def compose(docker: list[str], private: bool) -> list[str]:
    cmd = [*docker, "compose", "--env-file", str(DEFAULT_ENV), "-f", "compose.yaml"]
    if private: cmd += ["-f", "compose.vm.yaml"]
    return cmd


def api_image_id(docker: list[str], private: bool) -> str:
    cp = run([*compose(docker, private), "images", "-q", "api"], capture=True)
    image = cp.stdout.strip().splitlines()[0] if cp.stdout.strip() else ""
    if not image: raise SystemExit("could not resolve built API image id")
    return image


def qualify_image(docker: list[str], image: str) -> dict[str, str]:
    cmd = [*docker, "run", "--rm", "--entrypoint", "/usr/local/bin/pcrstudio-entrypoint", image,
           "/opt/worker/bin/python", "/opt/pcrstudio/scripts/container-scientific-smoke.py"]
    cp = run(cmd, capture=True)
    print(cp.stdout, end="")
    markers: dict[str, str] = {}
    for key in ("SCIENTIFIC_FREEZE_SHA256", "MAFFT_ARCHIVE_SHA256", "MAFFT_BUNDLE_SHA256"):
        match = re.search(rf"^{key}=([0-9a-f]{{64}})$", cp.stdout, re.M)
        if not match:
            raise SystemExit(f"scientific container smoke passed without emitting {key}")
        markers[key] = match.group(1)
    return markers


def approve_immutable_scientific_identity(
    values: dict[str, str], qualification: dict[str, str], *, allow_change: bool
) -> str:
    """Approve a first scientific identity, but never silently bless drift."""
    bindings = {
        "PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256": qualification["SCIENTIFIC_FREEZE_SHA256"],
        "PCRSTUDIO_QUALIFIED_MAFFT_ARCHIVE_SHA256": qualification["MAFFT_ARCHIVE_SHA256"],
        "PCRSTUDIO_QUALIFIED_MAFFT_BUNDLE_SHA256": qualification["MAFFT_BUNDLE_SHA256"],
    }
    changes: list[str] = []
    for key, current in bindings.items():
        previous = values.get(key, "").strip()
        if previous and not re.fullmatch(r"[0-9a-f]{64}", previous):
            raise SystemExit(f"{key} must be a canonical lowercase SHA-256 digest")
        if previous and previous != current:
            changes.append(f"{key}: {previous} -> {current}")
    if changes and not allow_change:
        raise SystemExit(
            "scientific runtime identity drifted from the previously qualified deployment; "
            "review dependency/tool changes and rerun with --approve-scientific-environment-change if intentional:\n  "
            + "\n  ".join(changes)
        )
    for key, current in bindings.items():
        values[key] = current
    return qualification["SCIENTIFIC_FREEZE_SHA256"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_database_manifest(manifest: Path, database_id: str, scope: str, expected_digest: str | None = None) -> str:
    if not manifest.is_file():
        raise SystemExit(f"specificity database manifest is missing: {manifest}")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"specificity database manifest is unreadable/invalid: {manifest}") from exc
    digest = str(data.get("fasta_sha256") or "").lower()
    if data.get("database_id") != database_id or data.get("scope") != scope or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit("specificity database manifest identity/scope/hash is invalid")
    if expected_digest and digest != expected_digest.lower():
        raise SystemExit("specificity database manifest fingerprint does not match .env")
    indexed = manifest.parent / str(data.get("indexed_fasta") or "")
    if not indexed.is_file() or sha256_file(indexed) != digest:
        raise SystemExit("indexed specificity FASTA is missing or does not match manifest fingerprint")
    artifacts = data.get("index_artifacts") or []
    if not artifacts:
        raise SystemExit("specificity database manifest has no index artifacts")
    seen: set[str] = set()
    for row in artifacts:
        name = str(row.get("name") or "")
        if not name or name in seen or Path(name).name != name:
            raise SystemExit("specificity database manifest contains an invalid/duplicate artifact name")
        seen.add(name)
        p = manifest.parent / name
        expected = str(row.get("sha256") or "").lower()
        if not p.is_file() or not re.fullmatch(r"[0-9a-f]{64}", expected) or sha256_file(p) != expected:
            raise SystemExit(f"specificity database artifact is missing/corrupt: {name}")
    return digest


def build_database(docker: list[str], image: str, fasta: Path, database_id: str, scope: str, dbdir: Path) -> tuple[str, Path]:
    fasta = fasta.expanduser().resolve()
    if not fasta.is_file(): raise SystemExit(f"reference FASTA not found: {fasta}")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", database_id): raise SystemExit("database id must match [A-Za-z0-9._-]+")
    dbdir.mkdir(parents=True, exist_ok=True)
    cmd = [*docker, "run", "--rm", "--user", "0:0", "--entrypoint", "/usr/local/bin/pcrstudio-entrypoint",
           "-v", f"{fasta}:/input/reference.fasta:ro", "-v", f"{dbdir}:/opt/pcrstudio/db", image,
           "/opt/worker/bin/python", "/opt/pcrstudio/scripts/configure-specificity-database.py",
           "/input/reference.fasta", database_id, "--scope", scope, "--output-root", "/opt/pcrstudio/db",
           "--env-output", f"/opt/pcrstudio/db/{database_id}.specificity.env", "--force"]
    run(cmd)
    manifest = dbdir / database_id / f"{database_id}.manifest.json"
    if not manifest.is_file(): raise SystemExit(f"database build produced no manifest: {manifest}")
    digest = validate_database_manifest(manifest, database_id, scope)
    return digest, manifest


def quiesce_and_backup_if_running(docker: list[str], private: bool, build_identity: str) -> Path | None:
    """Quiesce application writers, then snapshot the existing database before rollout."""
    cp = run([*compose(docker, private), "ps", "-q", "db"], capture=True, check=False)
    if cp.returncode != 0 or not cp.stdout.strip():
        return None
    probe = run([*compose(docker, private), "exec", "-T", "db", "pg_isready"], capture=True, check=False)
    if probe.returncode != 0:
        raise SystemExit("an existing PCRStudio database container was found but is not ready; refusing rollout without a pre-deploy backup")
    # Freeze all application writers before the rollback snapshot. PostgreSQL
    # remains online so pg_dump can capture one exact pre-rollout state. If
    # stopping or backup fails, bootstrap aborts before migration and leaves the
    # application quiesced rather than serving against an unprotected rollout.
    run([*compose(docker, private), "stop", "caddy", "web", "api", "runner"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"pre-deploy-{stamp}-{build_identity[:12]}.dump"
    run([str(ROOT / "scripts" / "backup-db.sh"), name])
    backup = LOCAL / "backups" / name
    sidecar = Path(str(backup) + ".sha256")
    if not backup.is_file() or not sidecar.is_file():
        raise SystemExit("pre-deploy backup command returned success without dump/checksum artifacts")
    return backup


def verify_scientific_ready(docker: list[str], private: bool) -> dict:
    cp = run([*compose(docker, private), "exec", "-T", "api", "curl", "-fsS", "http://127.0.0.1:8080/ready/scientific"], capture=True)
    try: payload = json.loads(cp.stdout)
    except json.JSONDecodeError: raise SystemExit(f"/ready/scientific returned non-JSON: {cp.stdout[:500]!r}")
    if payload.get("ready") is not True:
        raise SystemExit("/ready/scientific is not ready after bootstrap: " + json.dumps(payload, sort_keys=True)[:1500])
    return payload


def verify_runner(docker: list[str], private: bool) -> dict:
    # PID 1 must be the dedicated runner, and the same immutable scientific
    # image must pass its smoke gate from inside the runner container.
    run([*compose(docker, private), "exec", "-T", "runner", "sh", "-ec",
         "grep -aq pcr-runner /proc/1/cmdline && test -w /var/lib/pcrstudio/scratch"])
    cp = run([*compose(docker, private), "exec", "-T", "runner",
              "/opt/worker/bin/python", "/opt/pcrstudio/scripts/container-scientific-smoke.py"], capture=True)
    match = re.search(r"^SCIENTIFIC_FREEZE_SHA256=([0-9a-f]{64})$", cp.stdout, re.M)
    if not match:
        raise SystemExit("runner scientific smoke passed without emitting a freeze fingerprint")
    return {"ready": True, "scientific_python_freeze_sha256": match.group(1)}


def systemd_quote(path: Path) -> str:
    # systemd expands percent specifiers even in quoted arguments. JSON gives us
    # correct C-style escaping for spaces/quotes/backslashes; double `%` keeps a
    # literal path component intact.
    return json.dumps(str(path.resolve()).replace("%", "%%"))


def install_systemd_automation(retention_days: int) -> list[str]:
    if not 1 <= retention_days <= 3650:
        raise SystemExit("backup retention must be between 1 and 3650 days")
    systemctl = shutil.which("systemctl")
    if not systemctl or not Path("/run/systemd/system").exists():
        print("! systemd is not active; Docker restart policies remain enabled but backup timers were not installed")
        return []
    sudo = sudo_prefix()
    unit_dir = Path("/etc/systemd/system")
    staging = LOCAL / "systemd"
    staging.mkdir(parents=True, exist_ok=True)
    qroot = systemd_quote(ROOT)
    qbackup = systemd_quote(ROOT / "scripts" / "backup-db.sh")
    qprune = systemd_quote(ROOT / "scripts" / "prune-backups.sh")
    qdrill = systemd_quote(ROOT / "scripts" / "backup-restore-drill.sh")
    common = f"""[Unit]\nAfter=docker.service network-online.target\nRequires=docker.service\nConditionPathExists={ROOT / '.env'}\n\n[Service]\nType=oneshot\nWorkingDirectory={qroot}\nUMask=0077\nNoNewPrivileges=true\nPrivateTmp=true\nProtectSystem=full\nProtectKernelTunables=true\nProtectKernelModules=true\nProtectControlGroups=true\nRestrictSUIDSGID=true\n"""
    files = {
        "pcrstudio-backup.service": common + f"Environment=PCRSTUDIO_BACKUP_RETENTION_DAYS={retention_days}\nExecStart=/bin/bash {qbackup}\nExecStartPost=/bin/bash {qprune}\nTimeoutStartSec=1h\n",
        "pcrstudio-backup.timer": """[Unit]\nDescription=Daily PCRStudio PostgreSQL backup\n\n[Timer]\nOnCalendar=*-*-* 02:20:00 UTC\nPersistent=true\nRandomizedDelaySec=10m\nUnit=pcrstudio-backup.service\n\n[Install]\nWantedBy=timers.target\n""",
        "pcrstudio-restore-drill.service": common + f"ExecStart=/bin/bash {qdrill}\nTimeoutStartSec=2h\n",
        "pcrstudio-restore-drill.timer": """[Unit]\nDescription=Weekly PCRStudio backup restore drill\n\n[Timer]\nOnCalendar=Sun *-*-* 03:20:00 UTC\nPersistent=true\nRandomizedDelaySec=15m\nUnit=pcrstudio-restore-drill.service\n\n[Install]\nWantedBy=timers.target\n""",
    }
    installed: list[str] = []
    for name, content in files.items():
        local = staging / name
        atomic_write(local, content, 0o644)
        run([*sudo, "install", "-o", "root", "-g", "root", "-m", "0644", str(local), str(unit_dir / name)])
        installed.append(name)
    run([*sudo, systemctl, "daemon-reload"])
    run([*sudo, systemctl, "enable", "--now", "pcrstudio-backup.timer", "pcrstudio-restore-drill.timer"])
    run([*sudo, systemctl, "list-timers", "--no-pager", "pcrstudio-backup.timer", "pcrstudio-restore-drill.timer"], check=False)
    return installed


def main() -> int:
    require_linux()
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", action="store_true", help="loopback-only HTTP bootstrap (compose.vm.yaml)")
    ap.add_argument("--domain", help="public DNS hostname; required unless --private or already present in .env")
    ap.add_argument("--reference-fasta", type=Path, help="approved/reference FASTA used to build specificity indexes")
    ap.add_argument("--database-id", default="reference")
    ap.add_argument("--database-scope", choices=["production", "approved-reference"], default="approved-reference")
    ap.add_argument("--install-system-deps", action="store_true")
    ap.add_argument("--reselect-subnets", action="store_true")
    ap.add_argument("--skip-up", action="store_true", help="build/qualify assets but do not start the services")
    ap.add_argument("--no-systemd-automation", action="store_true", help="do not install daily backup/weekly restore-drill timers")
    ap.add_argument("--backup-retention-days", type=int, default=14, help="days to retain scheduled database backups (default: 14)")
    ap.add_argument(
        "--approve-scientific-environment-change",
        action="store_true",
        help="explicitly accept a changed scientific Python freeze or MAFFT archive/bundle identity on an existing deployment",
    )
    args = ap.parse_args()

    if args.install_system_deps: install_system_dependencies()

    # Refuse to build an image from a tree whose deterministic release manifest
    # no longer describes its bytes. This gate is Python-only and therefore does
    # not make the host install Node/Rust just to bootstrap containers.
    baseline_manifest = ROOT / "release" / "baseline" / "R15-FILE-MANIFEST.json"
    run([
        sys.executable,
        "scripts/generate-release-manifests.py",
        "--baseline-manifest",
        str(baseline_manifest),
        "--check",
    ])
    build_identity = sha256_file(ROOT / "release" / "FILE-MANIFEST.json")

    docker = docker_prefix()
    values = parse_env(DEFAULT_ENV)
    values["PCRSTUDIO_BUILD_ID"] = build_identity
    values["PCRSTUDIO_COMPOSE_PROJECT"] = validate_compose_project(values.get("PCRSTUDIO_COMPOSE_PROJECT", "pcrstudio"))
    values.setdefault("POSTGRES_USER", "pcr"); values.setdefault("POSTGRES_DB", "pcrstudio")
    values.setdefault("PCR_POSTGRES_PASSWORD_FILE", "./.local/secrets/postgres_password")
    values.setdefault("PCR_DATABASE_URL_FILE_HOST", "./.local/secrets/database_url")
    values.setdefault("PCR_NEXT_SERVER_ACTIONS_KEY_FILE", "./.local/secrets/next_server_actions_key")
    values.setdefault("PCR_OPERATOR_TOKEN_FILE_HOST", "./.local/secrets/operator_token")
    values.setdefault("PCR_NCBI_API_KEY_FILE_HOST", "./.local/secrets/ncbi_api_key")
    values.setdefault("PCR_SCIENTIFIC_DB_DIR", "./.local/scientific-db")
    values.setdefault("PCR_RUNNER_SCRATCH_DIR", "./.local/runner-scratch")
    values.setdefault("PCR_SCIENTIFIC_DB_SCOPE", args.database_scope)
    values.setdefault("RUST_LOG", "pcr_server=info,tower_http=info")
    if not 1 <= args.backup_retention_days <= 3650:
        raise SystemExit("--backup-retention-days must be between 1 and 3650")
    values["PCRSTUDIO_BACKUP_RETENTION_DAYS"] = str(args.backup_retention_days)
    resource_profile, host_memory, host_cpus = configure_resource_profile(values)
    if args.private:
        values["SITE_DOMAIN"] = "localhost"
        values["SITE_URL"] = "http://127.0.0.1:8080"
    else:
        domain = validate_domain(args.domain or values.get("SITE_DOMAIN", ""))
        values["SITE_DOMAIN"] = domain; values["SITE_URL"] = f"https://{domain}"
    choose_subnets(docker, values, args.reselect_subnets)
    ensure_secrets(values)
    scratch_dir = ensure_runner_scratch(values)
    dbdir = (ROOT / values["PCR_SCIENTIFIC_DB_DIR"]).resolve(); dbdir.mkdir(parents=True, exist_ok=True)
    disk_preflight = preflight_disk_capacity(
        docker,
        reference_fasta=args.reference_fasta,
        scientific_db_dir=dbdir,
        runner_scratch_dir=scratch_dir,
    )
    write_env(DEFAULT_ENV, values)

    # Compose validation happens before the expensive image build.
    run([*compose(docker, args.private), "config", "-q"])
    run([*compose(docker, args.private), "pull", "db", "caddy"])
    run([*compose(docker, args.private), "build", "--pull", "api", "web"])
    image = api_image_id(docker, args.private)

    qualification = qualify_image(docker, image)
    freeze = approve_immutable_scientific_identity(
        values, qualification, allow_change=args.approve_scientific_environment_change
    )

    if args.reference_fasta:
        digest, manifest = build_database(docker, image, args.reference_fasta, args.database_id, args.database_scope, dbdir)
        values["PCR_SCIENTIFIC_DB_ID"] = args.database_id
        values["PCR_SCIENTIFIC_DB_SHA256"] = digest
        values["PCR_SCIENTIFIC_DB_SCOPE"] = args.database_scope
    else:
        database_id = values.get("PCR_SCIENTIFIC_DB_ID", "").strip()
        database_digest = values.get("PCR_SCIENTIFIC_DB_SHA256", "").strip().lower()
        database_scope = values.get("PCR_SCIENTIFIC_DB_SCOPE", "").strip()
        if not database_id or not re.fullmatch(r"[0-9a-f]{64}", database_digest):
            raise SystemExit("first production bootstrap requires --reference-fasta (or a preconfigured fingerprinted DB in .env)")
        if database_scope not in {"production", "approved-reference"}:
            raise SystemExit("preconfigured specificity database scope must be production or approved-reference")
        manifest = dbdir / database_id / f"{database_id}.manifest.json"
        validate_database_manifest(manifest, database_id, database_scope, database_digest)
    write_env(DEFAULT_ENV, values)

    ready_payload = None
    runner_payload = None
    installed_automation: list[str] = []
    pre_deploy_backup: Path | None = None
    if not args.skip_up:
        pre_deploy_backup = quiesce_and_backup_if_running(docker, args.private, build_identity)
        run([*compose(docker, args.private), "up", "-d", "--wait"])
        ready_payload = verify_scientific_ready(docker, args.private)
        runner_payload = verify_runner(docker, args.private)
        if runner_payload["scientific_python_freeze_sha256"] != freeze:
            raise SystemExit("runner scientific environment fingerprint differs from qualified API image")
        if not args.no_systemd_automation:
            installed_automation = install_systemd_automation(args.backup_retention_days)

    DEPLOY.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": "1.0.0",
        "status": "pass",
        "platform": "linux",
        "architecture": platform.machine(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "api_image_id": image,
        "source_manifest_sha256": build_identity,
        "scientific_python_freeze_sha256": freeze,
        "mafft_archive_sha256": qualification["MAFFT_ARCHIVE_SHA256"],
        "mafft_bundle_sha256": qualification["MAFFT_BUNDLE_SHA256"],
        "scientific_database_id": values.get("PCR_SCIENTIFIC_DB_ID"),
        "scientific_database_sha256": values.get("PCR_SCIENTIFIC_DB_SHA256"),
        "scientific_database_scope": values.get("PCR_SCIENTIFIC_DB_SCOPE"),
        "scientific_manifest": str(manifest.relative_to(ROOT)) if manifest and manifest.is_relative_to(ROOT) else (manifest.name if manifest else None),
        "subnets": {k: values[k] for k in ("PCR_EDGE_SUBNET", "PCR_APP_SUBNET", "PCR_DATA_SUBNET")},
        "resource_profile": resource_profile,
        "host_memory_bytes": host_memory or None,
        "host_logical_cpus": host_cpus,
        "memory_limits": {k: values[k] for k in ("PCR_DB_MEMORY_LIMIT", "PCR_API_MEMORY_LIMIT", "PCR_RUNNER_MEMORY_LIMIT", "PCR_WEB_MEMORY_LIMIT", "PCR_CADDY_MEMORY_LIMIT")},
        "disk_preflight": disk_preflight,
        "scientific_ready": ready_payload,
        "runner": runner_payload,
        "job_execution_mode": "external",
        "runner_scratch_dir": str(scratch_dir.relative_to(ROOT)) if scratch_dir.is_relative_to(ROOT) else str(scratch_dir),
        "systemd_automation_units": installed_automation,
        "backup_retention_days": args.backup_retention_days,
        "pre_deploy_backup": (str(pre_deploy_backup.relative_to(ROOT)) if pre_deploy_backup and pre_deploy_backup.is_relative_to(ROOT) else (str(pre_deploy_backup) if pre_deploy_backup else None)),
        "pre_deploy_backup_sha256": (sha256_file(pre_deploy_backup) if pre_deploy_backup else None),
    }
    atomic_write(DEPLOY / "linux-bootstrap-evidence.json", json.dumps(evidence, indent=2, sort_keys=True) + "\n", 0o600)
    print("\nPCRStudio Linux bootstrap PASS")
    print(f"  API image: {image}")
    print(f"  source manifest: {build_identity}")
    print(f"  science freeze: {freeze}")
    print(f"  database: {values.get('PCR_SCIENTIFIC_DB_ID')} {values.get('PCR_SCIENTIFIC_DB_SHA256')}")
    print(f"  evidence: {DEPLOY / 'linux-bootstrap-evidence.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
