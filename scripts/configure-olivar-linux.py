#!/usr/bin/env python3
"""Bind an explicitly managed Linux Olivar 1.3.3 executable to PCRStudio."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "src"))
from pcr_tools.process_boundary import (  # noqa: E402
    ProcessOutputLimitExceeded,
    ProcessTransportError,
    run_bounded_text,
)
LOCAL = ROOT / ".local" / "tools"
CONFIG = LOCAL / "olivar.json"
SCHEMA_VERSION = "1.0.0"
OLIVAR_VERSION = "1.3.3"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_executable(raw: str) -> Path:
    candidate = Path(raw).expanduser() if "/" in raw else Path(shutil.which(raw) or "")
    if not candidate.is_file():
        raise SystemExit(
            "Olivar executable not found. Install Olivar 1.3.3 in a Linux "
            "Conda/Bioconda environment and pass --executable."
        )
    return candidate.resolve()


def observed_version(executable: Path) -> str:
    try:
        completed = run_bounded_text(
            [str(executable), "--version"],
            timeout=10,
            stdout_limit=64 * 1024,
            stderr_limit=64 * 1024,
        )
    except subprocess.TimeoutExpired as error:
        raise SystemExit("Olivar --version did not finish within 10 seconds") from error
    except (ProcessOutputLimitExceeded, ProcessTransportError) as error:
        raise SystemExit(f"Olivar --version violated the process boundary: {error}") from error
    return f"{completed.stdout} {completed.stderr}".strip()


def write_config(executable: Path) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tool_id": "olivar",
        "version": OLIVAR_VERSION,
        "executable": str(executable),
        "sha256": sha256(executable),
    }
    LOCAL.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(CONFIG)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default=os.environ.get("PCRSTUDIO_OLIVAR", "olivar"))
    args = parser.parse_args()

    executable = resolve_executable(args.executable)
    version_output = observed_version(executable)
    if OLIVAR_VERSION not in version_output:
        raise SystemExit(
            f"Olivar version contract requires {OLIVAR_VERSION}; observed: {version_output!r}"
        )
    write_config(executable)
    print(f"Bound Olivar {OLIVAR_VERSION}: {executable}")


if __name__ == "__main__":
    main()
