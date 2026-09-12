#!/usr/bin/env python3
"""Keep PCRStudio from consuming the host filesystem to exhaustion.

The guard is intentionally project-scoped. It prunes only PCRStudio's bounded
BuildKit cache and owned backup artifacts. If the host remains below the
configured reserve, it stops new scientific work and, at the critical reserve,
stops the public application services so PostgreSQL data is not written against
an exhausted filesystem. It never runs a daemon-wide Docker prune.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024**3


def docker_prefix() -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise SystemExit("docker is unavailable")
    candidates = [[docker]]
    if os.geteuid() != 0 and shutil.which("sudo"):
        candidates.append(["sudo", docker])
    for prefix in candidates:
        if subprocess.run([*prefix, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return prefix
    raise SystemExit("Docker daemon is unavailable or the current user has no permission to use it")


def docker_root(docker: list[str]) -> Path:
    result = subprocess.run(
        [*docker, "info", "--format", "{{.DockerRootDir}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode or not result.stdout.strip():
        raise SystemExit("could not determine DockerRootDir")
    return Path(result.stdout.strip()).resolve()


def containerd_root() -> Path:
    """Include OCI content/snapshots that DockerRootDir may not contain."""
    config = Path("/etc/containerd/config.toml")
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return Path("/var/lib/containerd")
    match = re.search(r'(?m)^\s*root\s*=\s*"([^"\n]+)"\s*$', text)
    if match is None:
        return Path("/var/lib/containerd")
    root = Path(match.group(1))
    if not root.is_absolute():
        raise SystemExit("containerd root in /etc/containerd/config.toml must be absolute")
    return root


def parse_gib(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer number of GiB") from exc
    if not 1 <= value <= 64:
        raise SystemExit(f"{name} must be between 1 and 64 GiB")
    return value


def free_bytes(paths: list[Path]) -> tuple[int, dict[str, int]]:
    values: dict[str, int] = {}
    for path in paths:
        target = path if path.exists() else path.parent
        values[str(path)] = shutil.disk_usage(target).free
    return min(values.values()), values


def run(command: list[str], *, check: bool = True) -> int:
    print(">", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)
    if check and result.returncode:
        raise SystemExit(f"command failed ({result.returncode})")
    return result.returncode


def project_compose() -> Path:
    path = ROOT / "scripts" / "compose-linux.sh"
    if not path.is_file():
        raise SystemExit(f"missing Compose launcher: {path}")
    return path


def stop_services(docker: list[str], services: list[str]) -> None:
    # Prefer the canonical launcher so the deployment's persisted project name
    # and environment are respected. Docker is still passed for a clear guard
    # failure if Compose cannot be invoked.
    del docker
    run([str(project_compose()), "stop", *services], check=False)


def cleanup_owned_artifacts() -> list[str]:
    """Prune only repository-owned rebuild/retention artifacts and report failures."""
    cleanup = (
        (
            "PCRStudio Docker cache/image cleanup",
            [sys.executable, str(ROOT / "scripts" / "docker-maintenance.py"), "prune"],
        ),
        ("expired PCRStudio backup cleanup", [str(ROOT / "scripts" / "prune-backups.sh")]),
    )
    return [label for label, command in cleanup if run(command, check=False)]


def main() -> int:
    parser = argparse.ArgumentParser(description="enforce PCRStudio host storage reserves")
    parser.add_argument("--enforce", action="store_true", help="prune owned artifacts and apply service stop policy")
    parser.add_argument("--budget-gib", default=os.environ.get("PCRSTUDIO_STORAGE_BUDGET_GIB", "20"))
    parser.add_argument("--emergency-headroom-gib", default=os.environ.get("PCRSTUDIO_STORAGE_EMERGENCY_HEADROOM_GIB", "4"))
    args = parser.parse_args()
    budget = parse_gib(args.budget_gib, "--budget-gib")
    headroom = parse_gib(args.emergency_headroom_gib, "--emergency-headroom-gib")
    if headroom >= budget:
        raise SystemExit("emergency headroom must be lower than the storage budget")

    docker = docker_prefix()
    # Modern Docker may keep OCI blobs and overlay snapshots under containerd
    # rather than DockerRootDir. Monitor both ownership roots so the guard is
    # still meaningful when an operator uses separate mounts in guard-only
    # development mode.
    paths = [ROOT, docker_root(docker), containerd_root()]
    before, before_by_path = free_bytes(paths)
    capacities = {str(path): shutil.disk_usage(path if path.exists() else path.parent).total for path in paths}
    minimum = min((total - (budget - headroom) * GIB) // GIB for total in capacities.values())
    critical = min((total - budget * GIB) // GIB for total in capacities.values())
    if args.enforce:
        # Both operations are scoped to PCRStudio. In particular, never use
        # `docker system prune`, which could remove another application.
        cleanup_failures = cleanup_owned_artifacts()
    else:
        cleanup_failures = []
    after, after_by_path = free_bytes(paths)
    minimum_bytes = min(total - (budget - headroom) * GIB for total in capacities.values())
    critical_bytes = min(total - budget * GIB for total in capacities.values())

    action = "none"
    if after < critical_bytes:
        stop_services(docker, ["caddy", "web", "api", "runner"])
        action = "stopped-public-services-and-runner"
    elif after < minimum_bytes:
        stop_services(docker, ["runner"])
        action = "stopped-runner"

    print(
        "PCRStudio storage guard: "
        f"before={before / GIB:.2f}GiB after={after / GIB:.2f}GiB "
        f"budget={budget}GiB minimum_free={minimum}GiB critical_free={critical}GiB action={action}"
    )
    print(f"paths_before={before_by_path}")
    print(f"paths_after={after_by_path}")
    if cleanup_failures:
        print("storage cleanup failed: " + ", ".join(cleanup_failures), file=sys.stderr)
    return 1 if after < minimum_bytes or cleanup_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
