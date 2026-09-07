#!/usr/bin/env python3
"""Canonical machine-readable PCRStudio toolchain configuration codec."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _validated_environment(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("toolchain environment must be a JSON object")
    environment: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or _KEY.fullmatch(key) is None:
            raise ValueError(f"invalid toolchain environment key: {key!r}")
        if not isinstance(value, str):
            raise ValueError(f"toolchain environment value for {key} must be a string")
        if any(ch in value for ch in ("\0", "\r", "\n")):
            raise ValueError(f"toolchain environment value for {key} contains a line/control delimiter")
        environment[key] = value
    return environment


def render_toolchain_config(environment: dict[str, str]) -> str:
    """Return deterministic JSON for one validated environment map."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "environment": _validated_environment(environment),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def read_toolchain_config(path: Path) -> dict[str, str]:
    """Read a strict toolchain JSON file and return a fresh environment map."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"toolchain configuration is unreadable/invalid JSON: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "environment"}:
        raise ValueError("toolchain configuration has an invalid top-level field set")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"toolchain configuration schema must be {SCHEMA_VERSION}; got {payload['schema_version']!r}"
        )
    return _validated_environment(payload["environment"])


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 identity of a regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
