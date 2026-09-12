#!/usr/bin/env python3
"""Keep PCRStudio's Docker builder and reconstructible images bounded."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = "pcrstudio"
BUILDKIT_CONFIG = ROOT / "docker" / "buildkitd.toml"
BUILDKIT_IMAGE = "moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
DEFAULT_MAX_USED_SPACE = "8GB"
BUILDKIT_GC_MARKER = 'maxUsedSpace = "8GB"'


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


def systemd_quote(value: str) -> str:
    """Quote one systemd unit argument (not shell syntax)."""
    if any(char in value for char in ("\0", "\n", "\r")):
        raise SystemExit("systemd command arguments cannot contain NUL or newline characters")
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("%", "%%")
        .replace("$", "$$")
    )
    return f'"{escaped}"'


def systemd_path(value: str) -> str:
    """Escape a path-valued unit setting; these settings are not argv strings."""
    if any(char in value for char in ("\0", "\n", "\r")):
        raise SystemExit("systemd paths cannot contain NUL or newline characters")
    return (
        value.replace("\\", "\\x5c")
        .replace(" ", "\\x20")
        .replace("\t", "\\x09")
        .replace("%", "%%")
    )


def user_timer_units(
    root: Path = ROOT, python: str | Path = sys.executable
) -> tuple[str, str, str, str]:
    """Return deterministic, repository-specific user service/timer units."""
    root = root.resolve()
    python = Path(python).resolve()
    slug = re.sub(r"[^a-z0-9-]+", "-", root.name.lower()).strip("-") or "workspace"
    identity = hashlib.sha256(os.fsencode(root)).hexdigest()[:12]
    stem = f"pcrstudio-docker-maintenance-{slug}-{identity}"
    service = f"""[Unit]
Description=Bound the PCRStudio Docker BuildKit cache

[Service]
Type=oneshot
WorkingDirectory={systemd_path(str(root))}
ExecStart={systemd_quote(str(python))} {systemd_quote(str(root / 'scripts' / 'docker-maintenance.py'))} prune --max-used-space 8GB
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
"""
    timer = f"""[Unit]
Description=Daily PCRStudio Docker cache maintenance

[Timer]
OnCalendar=*-*-* 04:30:00
Persistent=true
RandomizedDelaySec=20m
Unit={stem}.service

[Install]
WantedBy=timers.target
"""
    return f"{stem}.service", service, f"{stem}.timer", timer


def install_user_timer() -> str:
    """Install a daily timer for only this checkout's dedicated BuildKit builder."""
    docker = shutil.which("docker")
    if not docker or subprocess.run(
        [docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    ).returncode:
        raise SystemExit(
            "automatic user cleanup needs direct Docker access (without sudo) "
            "from the scheduled account"
        )
    systemctl = shutil.which("systemctl")
    if not systemctl or subprocess.run(
        [systemctl, "--user", "show-environment"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode:
        raise SystemExit(
            "a running systemd user manager is required for automatic cleanup; "
            "use the host's existing PCRStudio storage-guard timer on servers"
        )

    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    unit_dir = config_home / "systemd" / "user"
    service_name, service, timer_name, timer = user_timer_units()
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name, content in ((service_name, service), (timer_name, timer)):
        fd, temporary_name = tempfile.mkstemp(prefix=f".{name}.", dir=unit_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, unit_dir / name)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    for args in (
        [systemctl, "--user", "daemon-reload"],
        [systemctl, "--user", "enable", "--now", timer_name],
    ):
        result = subprocess.run(args, check=False)
        if result.returncode:
            raise SystemExit(f"command failed ({result.returncode}): {' '.join(args)}")
    print(f"Enabled daily PCRStudio cache maintenance: {timer_name}")
    return timer_name


def ensure_builder(docker: list[str]) -> None:
    inspected = subprocess.run(
        [*docker, "buildx", "inspect", BUILDER], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if inspected.returncode or BUILDKIT_IMAGE not in inspected.stdout or BUILDKIT_GC_MARKER not in inspected.stdout:
        if inspected.returncode == 0:
            run(docker, ["buildx", "rm", "--force", BUILDER])
        run(docker, ["buildx", "create", "--name", BUILDER, "--driver", "docker-container",
                     "--driver-opt", f"image={BUILDKIT_IMAGE}", "--config", str(BUILDKIT_CONFIG)])
    run(docker, ["buildx", "inspect", "--bootstrap", BUILDER])
    print(f"PCRStudio Docker builder ready: {BUILDER} (GC target {DEFAULT_MAX_USED_SPACE})")


def prune(docker: list[str], max_used_space: str) -> None:
    inspect = subprocess.run(
        [*docker, "buildx", "inspect", BUILDER], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if inspect.returncode:
        print(f"PCRStudio Docker builder {BUILDER!r} is not present; no shared cache was touched")
        return
    run(docker, ["buildx", "du", "--builder", BUILDER])
    run(docker, ["buildx", "prune", "--builder", BUILDER, "--all", "--max-used-space", max_used_space, "--force"])
    run(docker, ["image", "prune", "--force", "--filter", "label=org.pcrstudio.product=PCRStudio"])
    run(docker, ["buildx", "du", "--builder", BUILDER])


def report(docker: list[str]) -> None:
    run(docker, ["system", "df"])
    run(docker, ["buildx", "du", "--builder", BUILDER])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ensure", "setup", "prune", "report"])
    parser.add_argument("--max-used-space", default=DEFAULT_MAX_USED_SPACE)
    args = parser.parse_args()
    docker = docker_prefix()
    if args.command == "ensure":
        ensure_builder(docker)
    elif args.command == "setup":
        ensure_builder(docker)
        install_user_timer()
    elif args.command == "prune":
        prune(docker, args.max_used_space)
    else:
        report(docker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
