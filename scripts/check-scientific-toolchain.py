#!/usr/bin/env python3
"""Linux release gate for exact PCRStudio scientific tool identities.

This is intentionally a read-only host check. It does not install, repair or
execute a design; it asks each configured tool only for identity/provenance and
validates the strict specificity/scientific-environment contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from pcr_tools.tool_runtime import toolchain_snapshot


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-feature", action="append", default=[])
    args = parser.parse_args()

    snapshot = toolchain_snapshot()
    errors: list[str] = []
    if snapshot.get("mode") != "strict":
        fail(errors, "PCRSTUDIO_TOOLCHAIN_MODE must resolve to strict")

    tools: dict[str, dict[str, Any]] = snapshot.get("tools") or {}
    requested_features = set(args.require_feature)
    for tool_id, status in sorted(tools.items()):
        requirement = str(status.get("readiness_requirement") or "optional")
        must_pass = requirement == "required" or tool_id in requested_features
        if not must_pass:
            continue
        if status.get("available") is not True:
            fail(errors, f"{tool_id}: unavailable")
        if status.get("version_matches_contract") is not True:
            fail(errors, f"{tool_id}: version mismatch/unresolved")
        if status.get("warnings"):
            fail(errors, f"{tool_id}: " + "; ".join(map(str, status.get("warnings") or [])))
        if status.get("expected_artifact_sha256_malformed") is True:
            fail(errors, f"{tool_id}: malformed expected artifact SHA-256")
        if status.get("expected_artifact_sha256") and status.get("artifact_hash_matches") is not True:
            fail(errors, f"{tool_id}: executable/wrapper artifact hash is not verified")

    unknown_features = requested_features.difference(tools)
    for feature in sorted(unknown_features):
        fail(errors, f"requested tool feature is not in the canonical manifest: {feature}")

    strict = snapshot.get("strict_execution") or {}
    if strict.get("ready") is not True:
        fail(errors, "strict scientific execution contract is not ready: " + ", ".join(map(str, strict.get("missing") or [])))

    if "olivar" in requested_features:
        freeze_raw = os.environ.get("PCRSTUDIO_OLIVAR_ENV_FREEZE", "").strip().strip('"')
        expected = os.environ.get("PCRSTUDIO_OLIVAR_ENV_FREEZE_SHA256", "").strip().lower()
        if not freeze_raw:
            fail(errors, "olivar: PCRSTUDIO_OLIVAR_ENV_FREEZE is missing")
        else:
            freeze = Path(freeze_raw).expanduser()
            if not freeze.is_file():
                fail(errors, "olivar: Conda explicit-environment freeze file is missing")
            elif len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
                fail(errors, "olivar: environment freeze SHA-256 is missing/malformed")
            elif sha256(freeze) != expected:
                fail(errors, "olivar: environment freeze SHA-256 mismatch")

    # Host paths are operationally useful during qualification but should not be
    # persisted in a distributable evidence bundle. Keep only the leaf name.
    public = json.loads(json.dumps(snapshot))
    for status in (public.get("tools") or {}).values():
        raw = status.get("path")
        if raw:
            status["path"] = f"<path:{Path(str(raw)).name}>"
    payload = {
        "schema_version": "1.0.0",
        "status": "pass" if not errors else "fail",
        "required_features": sorted(requested_features),
        "errors": errors,
        "toolchain": public,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Scientific toolchain PASS: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
