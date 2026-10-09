"""Fail when generated API contracts differ from committed consumer contracts."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def compare(expected: Path, generated: Path) -> None:
    if expected.suffix == ".json":
        matches = json.loads(expected.read_text()) == json.loads(generated.read_text())
    else:
        matches = expected.read_bytes() == generated.read_bytes()
    if not matches:
        raise SystemExit(f"Generated contract differs: {expected}. Export the backend schema and regenerate the frontend API types.")


if __name__ == "__main__":
    compare(Path(sys.argv[1]), Path(sys.argv[2]))
