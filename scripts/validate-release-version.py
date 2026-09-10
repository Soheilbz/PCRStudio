#!/usr/bin/env python3
"""Validate the public SemVer identity of the checked-out release source."""
from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    identity = tomllib.loads((ROOT / "release/release.toml").read_text(encoding="utf-8"))
    version = identity.get("public_version")
    tag = identity.get("public_tag")
    if identity.get("versioning_scheme") != "semver-2.0.0":
        raise SystemExit("release versioning scheme must be semver-2.0.0")
    if not isinstance(version, str) or VERSION_RE.fullmatch(version) is None:
        raise SystemExit("public_version must be a stable MAJOR.MINOR.PATCH value")
    if tag != f"v{version}" or args.tag != tag:
        raise SystemExit(f"release tag {args.tag!r} does not match canonical public tag {tag!r}")
    print(f"release version PASS: {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
