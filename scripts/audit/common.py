"""Shared dependency-free helpers for PCRStudio static audits."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ERRORS: list[str] = []
WARNINGS: list[str] = []
GENERATED_PARTS = frozenset({
    ".git", ".local", ".venv", "node_modules", "target", ".next",
    ".pytest_cache", ".ruff_cache", "test-results", "playwright-report",
    "coverage", ".pnpm-store", ".cargo",
})

def is_generated(path: Path) -> bool:
    return any(part in GENERATED_PARTS for part in path.relative_to(ROOT).parts)

def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for directory, dirnames, filenames in os.walk(ROOT, topdown=True):
        dirnames[:] = [name for name in dirnames if name not in GENERATED_PARTS]
        files.extend(Path(directory) / name for name in filenames)
    return files

def error(message: str) -> None:
    ERRORS.append(message)

def warn(message: str) -> None:
    WARNINGS.append(message)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def profile_map() -> dict[str, dict[str, object]]:
    rows = tomllib.loads((ROOT / "crates/pcr-core/profiles.toml").read_text(encoding="utf-8"))["profile"]
    return {str(row["id"]): row for row in rows}

def parse_runtime_contract():
    """Load the generated Generation 1 foundation authority projection.

    Legacy code parsed literal registries out of runtime_contract.py. Generation 1 deliberately
    removed those duplicates, so static audit must inspect the generated
    canonical projections instead of requiring a second hand-maintained truth.
    """
    module_payload = json.loads((ROOT / "knowledge/runtime/module-contracts.generated.json").read_text(encoding="utf-8"))
    engine_payload = json.loads((ROOT / "knowledge/runtime/engine-contracts.generated.json").read_text(encoding="utf-8"))
    modules_raw = module_payload.get("modules", {})
    engines_raw = engine_payload.get("engines", {})
    modules = {module_id: row["engine"] for module_id, row in modules_raw.items()}
    contracts = {
        module_id: {
            "engine": row["engine"],
            "command": row["command"],
            "gates": tuple(row.get("gates", ())),
            "fallback": row.get("fallback", ""),
            "required_context": tuple(row.get("required_context", ())),
            "conditional_required_context": tuple(row.get("conditional_required_context", ())),
            "wire_required_context": tuple(row.get("wire_required_context", ())),
            "wire_conditional_required_context": tuple(row.get("wire_conditional_required_context", ())),
            "wire_required_any_of": tuple(tuple(group) for group in row.get("wire_required_any_of", ())),
        }
        for module_id, row in modules_raw.items()
    }
    bindings = {engine_id: list(row.get("bindings", ())) for engine_id, row in engines_raw.items()}
    return modules, contracts, bindings
