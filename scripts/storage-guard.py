#!/usr/bin/env python3
"""Keep PCRStudio's dedicated host within its managed storage budget.

The guard accounts for the product tree and both Docker/containerd stores,
cleans only reconstructible or retention-limited PCRStudio files, pauses
scientific work before the application budget is reached, and stops the stack
before host free space reaches the emergency floor. It never prunes another
project's Docker resources or application/database data.
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
    """Include OCI blobs and snapshots that DockerRootDir may not contain."""
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
    return root.resolve()


def parse_gib(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer number of GiB") from exc
    if not 1 <= value <= 64:
        raise SystemExit(f"{name} must be between 1 and 64 GiB")
    return value


def managed_paths(docker: list[str]) -> list[Path]:
    configured_root = os.environ.get("PCRSTUDIO_HOST_ROOT", "").strip()
    configured = Path(configured_root).expanduser() if configured_root else ROOT
    candidates = [configured.resolve(), docker_root(docker), containerd_root()]
    existing = [path for path in candidates if path.exists()]
    if not existing:
        raise SystemExit("none of the PCRStudio storage roots exist")
    # A child root is already counted by du when its parent is measured.
    unique: list[Path] = []
    for path in sorted(set(existing), key=lambda item: len(item.parts)):
        if not any(path == parent or parent in path.parents for parent in unique):
            unique.append(path)
    return unique


def managed_usage_bytes(paths: list[Path]) -> tuple[int, dict[str, int]]:
    """Count allocated bytes, not apparent sizes, without crossing mounts."""
    values: dict[str, int] = {}
    for path in paths:
        result = subprocess.run(
            ["du", "-sx", "--block-size=1", "--", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode:
            raise SystemExit(f"could not measure managed storage at {path}: {result.stderr.strip()}")
        try:
            values[str(path)] = int(result.stdout.split()[0])
        except (IndexError, ValueError) as exc:
            raise SystemExit(f"could not parse allocated storage usage for {path}") from exc
    return sum(values.values()), values


def host_free_bytes(paths: list[Path]) -> tuple[int, dict[str, int]]:
    values: dict[str, int] = {}
    for path in paths:
        values[str(path)] = shutil.disk_usage(path).free
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
    del docker
    if not (ROOT / ".env").exists():
        print("PCRStudio has no active deployment environment; no Compose services need stopping")
        return
    run([str(project_compose()), "stop", *services], check=False)


def cleanup_owned_artifacts(*, prune_docker: bool) -> list[str]:
    """Clean scoped staging/backup artifacts; prune builder cache only on pressure."""
    python = sys.executable
    configured_root = os.environ.get("PCRSTUDIO_HOST_ROOT", "").strip()
    state_dir = (Path(configured_root).expanduser() / "state") if configured_root else ROOT
    cleanup = [
        (
            "abandoned PCRStudio release downloads",
            [python, str(ROOT / "scripts" / "pull-release.py"), "--prune-staging", "--state-dir", str(state_dir)],
        ),
        ("PCRStudio backup retention", ["/bin/bash", str(ROOT / "scripts" / "prune-backups.sh")]),
    ]
    if prune_docker:
        cleanup.insert(
            1,
            (
                "PCRStudio Docker cache/image cleanup",
                [python, str(ROOT / "scripts" / "docker-maintenance.py"), "prune"],
            ),
        )
    return [label for label, command in cleanup if run(command, check=False)]


def main() -> int:
    parser = argparse.ArgumentParser(description="enforce PCRStudio managed storage and host-free reserves")
    parser.add_argument("--enforce", action="store_true", help="clean owned files and apply service-stop policy")
    parser.add_argument("--budget-gib", default=os.environ.get("PCRSTUDIO_STORAGE_BUDGET_GIB", "20"))
    parser.add_argument("--runner-stop-headroom-gib", default=os.environ.get("PCRSTUDIO_STORAGE_EMERGENCY_HEADROOM_GIB", "4"))
    parser.add_argument("--minimum-host-free-gib", default=os.environ.get("PCRSTUDIO_STORAGE_MIN_HOST_FREE_GIB", "8"))
    parser.add_argument("--critical-host-free-gib", default=os.environ.get("PCRSTUDIO_STORAGE_CRITICAL_HOST_FREE_GIB", "4"))
    parser.add_argument("--preflight-write-gib", help="verify that a bounded file operation fits without consuming the emergency reserve")
    args = parser.parse_args()
    budget = parse_gib(args.budget_gib, "--budget-gib")
    runner_headroom = parse_gib(args.runner_stop_headroom_gib, "--runner-stop-headroom-gib")
    minimum_free = parse_gib(args.minimum_host_free_gib, "--minimum-host-free-gib")
    critical_free = parse_gib(args.critical_host_free_gib, "--critical-host-free-gib")
    if runner_headroom >= budget:
        raise SystemExit("runner stop headroom must be lower than the application storage budget")
    if critical_free >= minimum_free:
        raise SystemExit("critical host-free threshold must be lower than the minimum host-free reserve")

    docker = docker_prefix()
    paths = managed_paths(docker)
    before_usage, usage_by_path = managed_usage_bytes(paths)
    before_free, free_by_path = host_free_bytes(paths)
    if args.preflight_write_gib is not None:
        requested = parse_gib(args.preflight_write_gib, "--preflight-write-gib")
        if before_usage + requested * GIB >= budget * GIB:
            raise SystemExit(
                f"operation may use {requested} GiB but PCRStudio is already using "
                f"{before_usage / GIB:.2f} GiB of its {budget} GiB managed budget"
            )
        if before_free < (requested + critical_free) * GIB:
            raise SystemExit(
                f"operation needs up to {requested} GiB while preserving {critical_free} GiB emergency host space; "
                f"only {before_free / GIB:.2f} GiB is free"
            )
        print(
            f"PCRStudio storage preflight PASS: operation allowance={requested}GiB "
            f"managed={before_usage / GIB:.2f}GiB free={before_free / GIB:.2f}GiB"
        )
        return 0
    pressure = (
        before_usage >= (budget - runner_headroom) * GIB
        or before_free <= 2 * minimum_free * GIB
    )
    cleanup_failures = cleanup_owned_artifacts(prune_docker=pressure) if args.enforce else []
    after_usage, usage_after_by_path = managed_usage_bytes(paths)
    after_free, free_after_by_path = host_free_bytes(paths)

    action = "none"
    critical = after_usage >= budget * GIB or after_free <= critical_free * GIB
    pause_science = after_usage >= (budget - runner_headroom) * GIB or after_free <= minimum_free * GIB
    if args.enforce and critical:
        stop_services(docker, ["caddy", "web", "api", "runner", "migrate", "db"])
        action = "stopped-application-to-protect-host"
    elif args.enforce and pause_science:
        stop_services(docker, ["runner"])
        action = "stopped-scientific-runner"

    print(
        "PCRStudio storage guard: "
        f"managed_before={before_usage / GIB:.2f}GiB managed_after={after_usage / GIB:.2f}GiB "
        f"budget={budget}GiB host_free={after_free / GIB:.2f}GiB "
        f"runner_threshold={budget - runner_headroom}GiB minimum_host_free={minimum_free}GiB "
        f"critical_host_free={critical_free}GiB action={action}"
    )
    print(f"managed_paths_before={usage_by_path}")
    print(f"managed_paths_after={usage_after_by_path}")
    print(f"host_free_before={free_by_path}")
    print(f"host_free_after={free_after_by_path}")
    if cleanup_failures:
        print("storage cleanup failed: " + ", ".join(cleanup_failures), file=sys.stderr)
    if after_usage > budget * GIB:
        print("PCRStudio managed storage exceeds its configured budget", file=sys.stderr)
    if after_free <= minimum_free * GIB:
        print("host free space is below the minimum configured reserve", file=sys.stderr)
    return 1 if after_usage >= budget * GIB or after_free <= minimum_free * GIB or cleanup_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
