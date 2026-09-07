#!/usr/bin/env python3
"""Build a deterministic PCRStudio source ZIP from the qualified tree."""
from __future__ import annotations

import argparse
import stat
import zipfile
from datetime import datetime
from pathlib import Path

from release_utils import load_release_identity, source_files, sha256

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = load_release_identity(ROOT)
DEFAULT_PREFIX = IDENTITY["archive_prefix"]
DEFAULT_NAME = f"{DEFAULT_PREFIX}.zip"
_stamp = datetime.fromisoformat(IDENTITY["archive_timestamp"])
FIXED_TIME = (_stamp.year, _stamp.month, _stamp.day, _stamp.hour, _stamp.minute, _stamp.second)


def build(output: Path, *, prefix: str = DEFAULT_PREFIX) -> tuple[int, str]:
    files = source_files(ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as zf:
        for rel, path in sorted(files.items()):
            info = zipfile.ZipInfo(f"{prefix}/{rel}", date_time=FIXED_TIME)
            info.create_system = 3
            executable = bool(path.stat().st_mode & stat.S_IXUSR)
            mode = 0o755 if executable else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return len(files), sha256(output)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=ROOT.parent / DEFAULT_NAME)
    ap.add_argument("--prefix", default=DEFAULT_PREFIX, help="Single root directory name stored inside the ZIP.")
    args = ap.parse_args()
    if not args.prefix or "/" in args.prefix or "\\" in args.prefix or args.prefix in {".", ".."}:
        raise SystemExit("archive prefix must be one non-empty directory name")
    count, digest = build(args.output.resolve(), prefix=args.prefix)
    print(f"built {args.output.resolve()} entries={count} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
