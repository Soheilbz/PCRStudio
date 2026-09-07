"""Typed loader for Generation 1 foundation generated runtime contracts.

This module is intentionally data-only. Canonical authority lives in
``contracts/*.toml``; ``scripts/generate-foundation-contracts.py`` projects it
into package-local JSON so an installed worker never needs repository paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Final


def _load(name: str) -> dict[str, Any]:
    resource = files("pcr_tools").joinpath("data", name)
    with resource.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"generated contract {name} is not a JSON object")
    return value


FOUNDATION: Final[dict[str, Any]] = _load("foundation.generated.json")
MODULE_PAYLOAD: Final[dict[str, Any]] = _load("module-contracts.generated.json")
ENGINE_PAYLOAD: Final[dict[str, Any]] = _load("engine-contracts.generated.json")
TOOL_PAYLOAD: Final[dict[str, Any]] = _load("tool-contracts.generated.json")

MODULES: Final[dict[str, dict[str, Any]]] = dict(MODULE_PAYLOAD["modules"])
ENGINES: Final[dict[str, dict[str, Any]]] = dict(ENGINE_PAYLOAD["engines"])
TOOL_ROWS: Final[dict[str, dict[str, Any]]] = dict(TOOL_PAYLOAD["tools"])


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Exact scientific tool identity resolved from the canonical tool manifest."""

    tool_id: str
    version: str
    execution_scope: str
    env_var: str | None = None
    hash_env_var: str | None = None
    executable_names: tuple[str, ...] = ()
    artifact_sha256_required: bool = False
    source_ref: str = ""
    catalog_disposition: str = "OPTIONAL"
    readiness_requirement: str = "optional"


def _tool(row: dict[str, Any]) -> ToolSpec:
    return ToolSpec(
        tool_id=str(row["id"]),
        version=str(row["version"]),
        execution_scope=str(row["execution_scope"]),
        env_var=str(row["env_var"]) if row.get("env_var") else None,
        hash_env_var=str(row["hash_env_var"]) if row.get("hash_env_var") else None,
        executable_names=tuple(str(item) for item in row.get("executable_names", ())),
        artifact_sha256_required=bool(row.get("artifact_sha256_required")),
        source_ref=str(row.get("source_ref") or ""),
        catalog_disposition=str(row.get("catalog_disposition") or "OPTIONAL"),
        readiness_requirement=str(row.get("readiness_requirement") or "optional"),
    )


TOOLS: Final[dict[str, ToolSpec]] = {tool_id: _tool(row) for tool_id, row in TOOL_ROWS.items()}
MODULE_TO_ENGINE: Final[dict[str, str]] = {
    module_id: str(row["engine"]) for module_id, row in MODULES.items()
}
MODULE_TO_COMMAND: Final[dict[str, str]] = {
    module_id: str(row["command"]) for module_id, row in MODULES.items()
}
COMMAND_TO_ENGINE: Final[dict[str, str]] = {
    str(row["command"]): engine_id for engine_id, row in ENGINES.items()
}
ENGINE_BINDINGS: Final[dict[str, tuple[dict[str, Any], ...]]] = {
    engine_id: tuple(dict(binding) for binding in row.get("bindings", ()))
    for engine_id, row in ENGINES.items()
}
MODULE_CONTRACTS: Final[dict[str, dict[str, Any]]] = {
    module_id: {
        "engine": row["engine"],
        "command": row["command"],
        "required_context": tuple(row.get("required_context", ())),
        "conditional_required_context": tuple(
            {
                "when": dict(rule.get("when", {})),
                "required_context": tuple(rule.get("required_context", ())),
            }
            for rule in row.get("conditional_required_context", ())
        ),
        "wire_required_context": tuple(row.get("wire_required_context", ())),
        "wire_conditional_required_context": tuple(
            {
                "when": dict(rule.get("when", {})),
                "required_context": tuple(rule.get("required_context", ())),
            }
            for rule in row.get("wire_conditional_required_context", ())
        ),
        "wire_required_any_of": tuple(
            tuple(group) for group in row.get("wire_required_any_of", ())
        ),
        "gates": tuple(row.get("gates", ())),
        "fallback": row.get("fallback", ""),
    }
    for module_id, row in MODULES.items()
}

if len(MODULES) != 21 or len(ENGINES) != 11:
    raise RuntimeError(
        "generated Generation 1 foundation contract must remain 21 modules -> 11 engines"
    )
