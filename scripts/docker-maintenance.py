#!/usr/bin/env python3
"""Keep PCRStudio's Docker builder and reconstructible images bounded."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = "pcrstudio"
BUILDKIT_CONFIG = ROOT / "docker" / "buildkitd.toml"
BUILDKIT_IMAGE = "moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
DEFAULT_MAX_USED_SPACE = "20GB"


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


def run(docker: list[str], args: list[str]) -> None:
    command = [*docker, *args]
    print(">", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, text=True, check=False)
    if result.returncode:
        raise SystemExit(f"command failed ({result.returncode})")


def ensure_builder(docker: list[str]) -> None:
    inspected = subprocess.run(
        [*docker, "buildx", "inspect", BUILDER], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if inspected.returncode or BUILDKIT_IMAGE not in inspected.stdout:
        if inspected.returncode == 0:
            run(docker, ["buildx", "rm", "--force", BUILDER])
        run(docker, ["buildx", "create", "--name", BUILDER, "--driver", "docker-container",
                     "--driver-opt", f"image={BUILDKIT_IMAGE}", "--config", str(BUILDKIT_CONFIG)])
    run(docker, ["buildx", "inspect", "--bootstrap", BUILDER])
    print(f"PCRStudio Docker builder ready: {BUILDER} (cache ceiling {DEFAULT_MAX_USED_SPACE})")


def prune(docker: list[str], max_used_space: str) -> None:
    inspect = subprocess.run(
        [*docker, "buildx", "inspect", BUILDER], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if inspect.returncode:
        print(f"PCRStudio Docker builder {BUILDER!r} is not present; no shared cache was touched")
        return
    run(docker, ["buildx", "prune", "--builder", BUILDER, "--all", "--max-used-space", max_used_space, "--force"])
    run(docker, ["image", "prune", "--force", "--filter", "label=org.pcrstudio.product=PCRStudio"])


def report(docker: list[str]) -> None:
    run(docker, ["system", "df"])
    run(docker, ["buildx", "du", "--builder", BUILDER])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ensure", "prune", "report"])
    parser.add_argument("--max-used-space", default=DEFAULT_MAX_USED_SPACE)
    args = parser.parse_args()
    docker = docker_prefix()
    if args.command == "ensure":
        ensure_builder(docker)
    elif args.command == "prune":
        prune(docker, args.max_used_space)
    else:
        report(docker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
