#!/usr/bin/env python3
"""Standard-library helpers shared by PCRStudio release tooling.

These functions deliberately avoid importing PCRStudio runtime modules. Release
qualification must be able to inspect a source tree whose native dependencies
have not yet been installed.
"""
from __future__ import annotations

import hashlib
import json
import os
import tomllib
from pathlib import Path
from typing import Iterable

SKIP_PARTS = frozenset({
    ".git", ".local", ".pnpm-store", "node_modules", "target", ".venv",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".pyright",
    ".next", "test-results", "playwright-report", "coverage", "dist", "build",
})
SKIP_SUFFIXES = frozenset({".pyc", ".pyo", ".tsbuildinfo"})
SKIP_FILES = frozenset({".env", ".DS_Store"})

# These are generated from the rest of the tree. Keeping them out of the source
# manifest avoids hash cycles while SHA256SUMS still authenticates them.
MANIFEST_EXCLUDED = frozenset({
    "release/FILE-MANIFEST.json",
    "release/SHA256SUMS.txt",
    "release/current/SBOM.cdx.json",
    "release/current/SOURCE-ATTESTATION.intoto.json",
})
PATCH_EXCLUDED = MANIFEST_EXCLUDED | frozenset({
    "release/PATCH-MANIFEST.json",
    "release/RUNTIME-CONTRACT-MANIFEST.json",
})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(payload))


def is_release_source(path: Path, root: Path, *, excluded: Iterable[str] = ()) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    rel = path.relative_to(root)
    if any(part in SKIP_PARTS for part in rel.parts):
        return False
    if path.name in SKIP_FILES or path.suffix in SKIP_SUFFIXES or path.suffix.lower() == ".zip":
        return False
    return rel.as_posix() not in set(excluded)


def source_files(root: Path, *, excluded: Iterable[str] = ()) -> dict[str, Path]:
    excluded_set = set(excluded)
    out: dict[str, Path] = {}
    for directory, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_PARTS)
        for name in sorted(filenames):
            path = Path(directory) / name
            if not is_release_source(path, root, excluded=excluded_set):
                continue
            out[path.relative_to(root).as_posix()] = path
    return out


def file_record(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON: {path}")
    return value


def load_release_identity(root: Path) -> dict[str, str]:
    """Load and validate the canonical release identity without runtime imports."""
    path = root / "release" / "release.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    required = (
        "schema_version", "release_id", "release_class", "archive_prefix",
        "archive_timestamp", "baseline_release", "baseline_kind",
        "foundation_release", "source_qualification_label", "current_report",
        "public_version", "public_tag", "versioning_scheme",
    )
    missing = [key for key in required if not isinstance(raw.get(key), str) or not raw[key].strip()]
    if missing:
        raise ValueError(f"release identity is missing non-empty string fields: {', '.join(missing)}")
    return {key: str(raw[key]) for key in required}
