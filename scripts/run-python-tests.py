#!/usr/bin/env python3
"""Run the complete locked Python test suite from any supported checkout.

CI exposes uv on PATH, while the Linux bootstrap keeps its copy under
.local/uv-venv so a developer does not need a machine-wide installation.
Resolve both locations here so local and CI use the same command.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def find_uv() -> str:
    configured = os.environ.get("PCRSTUDIO_UV", "").strip()
    candidates = [Path(configured)] if configured else []
    on_path = shutil.which("uv")
    if on_path:
        candidates.append(Path(on_path))
    candidates.append(ROOT / ".local" / "uv-venv" / "bin" / "uv")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise SystemExit(
        "uv is required for the locked Python test gate; run ./bootstrap.sh --local "
        "or install uv, then retry"
    )


def main() -> int:
    command = [
        find_uv(),
        "run",
        "--project",
        str(ROOT / "tools"),
        "--frozen",
        "--extra",
        "dev",
        "pytest",
        str(ROOT / "tools" / "tests"),
        "-q",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
