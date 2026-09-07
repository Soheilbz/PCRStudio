"""Canonical hashes for reproducibility and safe duplicate detection."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_sha256(value: Any) -> str:
    """SHA-256 over canonical JSON (sorted keys, stable separators)."""
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_free_tool_validation(value: Any) -> Any:
    if isinstance(value, list):
        return [_path_free_tool_validation(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _path_free_tool_validation(item)
            for key, item in value.items()
            if key.lower() not in {"path", "executable", "cwd", "tempdir", "tmpdir"}
        }
    return value


def toolchain_fingerprint(result: dict[str, Any]) -> str:
    """Fingerprint only computational authority, never sequence/user payload."""
    provenance = result.get("provenance") if isinstance(result.get("provenance"), dict) else {}
    runtime = result.get("runtime_contract") if isinstance(result.get("runtime_contract"), dict) else {}
    validation = result.get("toolchain_validation") if isinstance(result.get("toolchain_validation"), dict) else {}
    integrity = result.get("scientific_integrity") if isinstance(result.get("scientific_integrity"), dict) else {}
    authority = {
        "runtime_contract_version": provenance.get("runtime_contract_version") or runtime.get("version"),
        "parameter_map_version": provenance.get("parameter_map_version"),
        "input_schema_version": provenance.get("input_schema_version"),
        "output_schema_version": provenance.get("output_schema_version"),
        "toolchain_manifest": provenance.get("toolchain_manifest"),
        "tool_versions": provenance.get("tool_versions"),
        "primer3_artifact": provenance.get("primer3_artifact"),
        "methods": provenance.get("methods"),
        "scientific_authorities": provenance.get("scientific_authorities"),
        "method_fidelity": provenance.get("method_fidelity"),
        "method_fidelity_references": provenance.get("method_fidelity_references"),
        "method_fidelity_scope": provenance.get("method_fidelity_scope"),
        "method_fidelity_registry": provenance.get("method_fidelity_registry"),
        "external_validation": _path_free_tool_validation(validation),
        "scientific_integrity": _path_free_tool_validation(integrity),
    }
    return canonical_sha256(authority)
