#!/usr/bin/env python3
"""Generate all Generation 1 foundation cross-layer contract projections.

Canonical inputs are intentionally split by concern:
- contracts/modules.toml: public workflow/runtime/page capability contract
- contracts/engines.toml: engine execution + tool bindings
- contracts/tools.toml: scientific tool identity/provisioning authority
- contracts/foundation.toml: version vocabulary for persistence/IPC/API

Scientific assay defaults remain in crates/pcr-core/profiles.toml; they are not
architectural metadata and are therefore not duplicated here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    Path("contracts/modules.toml"),
    Path("contracts/engines.toml"),
    Path("contracts/tools.toml"),
    Path("contracts/foundation.toml"),
]


def read_toml(rel: str) -> dict[str, Any]:
    with (ROOT / rel).open("rb") as handle:
        return tomllib.load(handle)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write(rel: str, value: Any, *, check: bool) -> bool:
    path = ROOT / rel
    rendered = dump(value)
    if check:
        return path.is_file() and path.read_text(encoding="utf-8") == rendered
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8", newline="\n")
    return True


def write_text(rel: str, rendered: str, *, check: bool) -> bool:
    path = ROOT / rel
    if check:
        return path.is_file() and path.read_text(encoding="utf-8") == rendered
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8", newline="\n")
    return True


def canonical_sources() -> dict[str, str]:
    return {path.as_posix(): sha(ROOT / path) for path in SOURCES}


def normalized_modules(raw: dict[str, Any]) -> dict[str, Any]:
    rows = raw.get("module") or []
    if len(rows) != 21:
        raise ValueError(f"Generation 1 foundation requires 21 modules, found {len(rows)}")
    out: dict[str, Any] = {}
    for row in rows:
        module_id = str(row["id"])
        if module_id in out:
            raise ValueError(f"duplicate module {module_id}")
        page = row.get("page") or {}
        rules = []
        for rule in row.get("conditional_required_context") or []:
            rules.append(
                {
                    "when": dict(rule.get("when") or {}),
                    "required_context": list(rule.get("required_context") or []),
                }
            )
        wire_rules = []
        for rule in row.get("wire_conditional_required_context") or []:
            wire_rules.append(
                {
                    "when": dict(rule.get("when") or {}),
                    "required_context": list(rule.get("required_context") or []),
                }
            )
        if "wire_required_context" not in row:
            raise ValueError(f"{module_id}: explicit wire_required_context is mandatory")
        wire_any = [list(group) for group in row.get("wire_required_any_of") or []]
        if any(not group for group in wire_any):
            raise ValueError(f"{module_id}: wire_required_any_of groups cannot be empty")
        out[module_id] = {
            "id": module_id,
            "engine": str(row["engine"]),
            "command": str(row["command"]),
            "status": str(row["status"]),
            "goal": str(row["goal"]),
            "input_model": str(row["input_model"]),
            "atlas_document": str(row["atlas_document"]),
            "resource_weight": int(row["resource_weight"]),
            "required_context": list(row.get("required_context") or []),
            "conditional_required_context": rules,
            "wire_required_context": list(row.get("wire_required_context") or []),
            "wire_conditional_required_context": wire_rules,
            "wire_required_any_of": wire_any,
            "gates": list(row.get("gates") or []),
            "fallback": str(row.get("fallback") or ""),
            "page": {
                "unit": {
                    "one": str(page.get("unit_one") or "result"),
                    "many": str(page.get("unit_many") or "results"),
                    "how": str(page.get("unit_how") or "") or None,
                },
                "asks": list(page.get("asks") or []),
                "tools": list(page.get("tools") or []),
                "initial": dict(page.get("initial") or {}),
                "fixed": dict(page.get("fixed") or {}),
            },
            "field_owners": dict(row.get("field_owners") or {}),
        }
    engines = {row["engine"] for row in out.values()}
    if len(engines) != 11:
        raise ValueError(f"Generation 1 foundation requires 11 engines, found {len(engines)}")
    return out


def normalized_engines(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in raw.get("engine") or []:
        engine_id = str(row["id"])
        if engine_id in out:
            raise ValueError(f"duplicate engine {engine_id}")
        out[engine_id] = {
            "id": engine_id,
            "display_order": int(row["display_order"]),
            "label": str(row["label"]),
            "input": str(row["input"]),
            "command": str(row["command"]),
            "resource_weight": int(row.get("resource_weight") or 1),
            "bindings": [
                {
                    "tool_id": str(binding["tool_id"]),
                    "role": str(binding["role"]),
                    "purposes": list(binding.get("purposes") or []),
                    "operations": list(binding.get("operations") or []),
                    "artifact_identity": str(binding.get("artifact_identity") or ""),
                }
                for binding in row.get("binding") or []
            ],
        }
    if len(out) != 11:
        raise ValueError(f"Generation 1 foundation requires 11 engine contracts, found {len(out)}")
    orders = sorted(int(row["display_order"]) for row in out.values())
    if orders != list(range(1, len(out) + 1)):
        raise ValueError(f"engine display_order must be a contiguous 1..{len(out)} sequence, got {orders}")
    return out


def normalized_tools(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in raw.get("tool") or []:
        tool_id = str(row["id"])
        if tool_id in out:
            raise ValueError(f"duplicate tool {tool_id}")
        out[tool_id] = {
            key: value
            for key, value in row.items()
            if key != "id" and value not in ("", [], None)
        }
        out[tool_id]["id"] = tool_id
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if a generated file would change")
    args = parser.parse_args()

    module_raw = read_toml("contracts/modules.toml")
    engine_raw = read_toml("contracts/engines.toml")
    tool_raw = read_toml("contracts/tools.toml")
    foundation = read_toml("contracts/foundation.toml")
    modules = normalized_modules(module_raw)
    engines = normalized_engines(engine_raw)
    tools = normalized_tools(tool_raw)
    sources = canonical_sources()

    for module in modules.values():
        engine = engines.get(module["engine"])
        if engine is None:
            raise ValueError(f"{module['id']}: unknown engine {module['engine']}")
        if engine["command"] != module["command"]:
            raise ValueError(f"{module['id']}: module/engine command drift")
        atlas = ROOT / module["atlas_document"]
        if not atlas.is_file():
            raise ValueError(f"{module['id']}: missing Atlas document {atlas}")
        for field, owner in module["field_owners"].items():
            if owner not in {"target", "design", "strategy", "constraints", "vector", "reaction", "specificity", "validation", "construct", "review"}:
                raise ValueError(f"{module['id']}.{field}: unknown page owner {owner}")
    for engine in engines.values():
        for binding in engine["bindings"]:
            tid = binding["tool_id"]
            if tid not in tools and not tid.startswith("pcrstudio_"):
                raise ValueError(f"{engine['id']}: binding references undeclared tool {tid}")

    module_payload = {
        "schema_version": module_raw["schema_version"],
        "contract_version": module_raw["contract_version"],
        "generation_policy": "Generated from contracts/modules.toml; do not hand-edit.",
        "canonical_sources": sources,
        "modules": modules,
    }
    engine_payload = {
        "schema_version": engine_raw["schema_version"],
        "contract_version": engine_raw["contract_version"],
        "generation_policy": "Generated from contracts/engines.toml; do not hand-edit.",
        "canonical_sources": sources,
        "engines": engines,
    }
    tool_payload = {
        "schema_version": tool_raw["schema_version"],
        "contract_version": tool_raw["contract_version"],
        "generation_policy": "Generated from contracts/tools.toml; do not hand-edit.",
        "canonical_sources": sources,
        "tools": tools,
    }
    foundation_payload = {
        "schema_version": foundation["schema_version"],
        "generation_policy": "Generated from contracts/foundation.toml; do not hand-edit.",
        "canonical_sources": sources,
        **foundation,
    }

    projections = {
        "module-contracts.generated.json": module_payload,
        "engine-contracts.generated.json": engine_payload,
        "tool-contracts.generated.json": tool_payload,
        "foundation.generated.json": foundation_payload,
    }
    targets: dict[str, Any] = {}
    for filename, payload in projections.items():
        for base in (
            "knowledge/runtime",
            "tools/src/pcr_tools/data",
            "web/src/lib/contracts",
            "crates/pcr-core/generated",
            "crates/pcr-contracts/generated",
        ):
            targets[f"{base}/{filename}"] = payload

    # Browser readiness and basic page capabilities are canonical projections.
    targets["web/src/lib/projects/required-context.generated.json"] = {
        "schema_version": "2.1.0",
        "generation_policy": "Generated from contracts/modules.toml; do not hand-edit.",
        "modules": {
            mid: {
                "required_context": value["required_context"],
                "conditional_required_context": value["conditional_required_context"],
                "wire_required_context": value["wire_required_context"],
                "wire_conditional_required_context": value["wire_conditional_required_context"],
                "wire_required_any_of": value["wire_required_any_of"],
                "field_owners": value["field_owners"],
            }
            for mid, value in modules.items()
        },
    }
    targets["web/src/components/design/page-capabilities.generated.json"] = {
        "schema_version": "1.0.0",
        "generation_policy": "Generated from contracts/modules.toml; human-facing step copy remains page-plan.ts.",
        "modules": {mid: value["page"] for mid, value in modules.items()},
    }

    # Compatibility projections consumed by existing runtime/qualification code.
    targets["knowledge/runtime/module-contracts.json"] = {
        "schema_version": "2.1.0",
        "runtime_contract_version": foundation["module_contract_version"],
        "parameter_map_version": "generation1-current",
        "coordinate_contract": {
            "version": foundation["coordinate_contract_version"],
            "basis": 0,
            "interval": "half-open",
            "notation": "[start,end)",
            "oligo_sequence_orientation": "5prime-to-3prime",
            "strand_field_required": True,
            "single_base_position": "0-based",
            "junction_position": "boundary-between-bases",
            "source_coordinate_policy": "preserve raw source coordinates in adapter evidence; normalize before engine use",
        },
        "pipeline": [
            "api-schema-validation", "module-resolution", "input-normalization",
            "coordinate-normalization", "chemistry-and-parameter-resolution",
            "candidate-generation", "assay-hard-filters",
            "thermodynamic-and-structure-evaluation",
            "request-context-specificity-and-inclusivity", "deterministic-ranking",
            "bounded-search-expansion-with-unchanged-hard-gates",
            "independent-toolchain-validation", "verification-envelope",
            "result-schema-and-ui",
        ],
        "modules": {
            mid: {
                "gates": value["gates"],
                "fallback": value["fallback"],
                "engine": value["engine"],
                "command": value["command"],
                **({"required_context": value["required_context"]} if value["required_context"] else {}),
                **({"conditional_required_context": value["conditional_required_context"]} if value["conditional_required_context"] else {}),
                **({"wire_required_context": value["wire_required_context"]} if value["wire_required_context"] else {}),
                **({"wire_conditional_required_context": value["wire_conditional_required_context"]} if value["wire_conditional_required_context"] else {}),
                **({"wire_required_any_of": value["wire_required_any_of"]} if value["wire_required_any_of"] else {}),
            }
            for mid, value in modules.items()
        },
    }
    targets["knowledge/atlas/contracts/engine-tool-contracts.json"] = {
        "schema_version": "2.0.0",
        "generation": "1",
        "status": "generated_canonical_projection",
        "effective_date": "2026-09-04",
        "role_semantics": "Execution-context roles are generated from contracts/engines.toml.",
        "engines": [
            {
                "engine_id": eid,
                "tool_contract_md": f"../engines/{eid}/01-tools.md",
                "bindings": value["bindings"],
            }
            for eid, value in engines.items()
        ],
    }
    targets["knowledge/atlas/contracts/toolchain-manifest.json"] = {
        "schema_version": "2.0.0",
        "generation": "1",
        "status": "generated_canonical_projection",
        "effective_date": "2026-09-04",
        "runtime_schema": "runtime-contract.schema.json",
        "tool_role_enum": ["PRIMARY", "CONDITIONAL_PRIMARY", "VALIDATOR", "FALLBACK", "OPTIONAL", "BENCHMARK", "REFERENCE", "WATCHLIST", "REJECT"],
        "coordinate_contract": {
            "internal_system": "zero_based_half_open", "interval": "[start0,end0)",
            "single_base_position": "zero_based", "strand_field": "explicit + or -; interval coordinates always increase on the reference",
            "oligo_sequence_orientation": "always stored 5-prime to 3-prime as synthesized/read",
            "source_coordinates": "raw source-tool/database coordinates must be retained; conversion occurs only in the adapter",
            "circular_targets": "normalize modulo reference length and represent origin-spanning regions as ordered segment arrays, never as end0 < start0",
        },
        "parameter_resolution_precedence": [
            "tool_hard_capability", "assay_hard_constraint", "chemistry_kit_profile_locked",
            "chemistry_kit_profile_bounded", "chemistry_kit_profile_recommended",
            "purpose_default_within_assay_contract", "pcrstudio_reviewed_default",
            "policy_checked_user_tightening_or_within_envelope_tuning",
            "tool_native_default_only_when_explicitly_documented_and_not_overridden",
        ],
        "override_policies": ["locked", "bounded", "recommended"],
        "artifact_identity_policy": "Every local production artifact resolves to an exact version/ref and SHA-256; remote references have no production artifact digest.",
        "tools": [
            {
                "tool_id": tid,
                "display_name": value.get("display_name", tid),
                "qualifiers": value.get("qualifiers", []),
                "version_policy": {
                    "mode": value.get("version_mode", "exact"),
                    "version": value["version"],
                    **({"minimum_supported": value["minimum_supported"]} if value.get("minimum_supported") else {}),
                    **({"excluded_range": value["excluded_range"]} if value.get("excluded_range") else {}),
                },
                "source_ref": value.get("source_ref", ""),
                "source_url": value.get("source_url", ""),
                "execution_scope": value["execution_scope"],
                "artifact_sha256_required": bool(value.get("artifact_sha256_required")),
                "catalog_disposition": value.get("catalog_disposition", "OPTIONAL"),
            }
            for tid, value in tools.items()
        ],
        "role_scope": "engine_resolved",
        "role_semantics": "Global tool identity is canonical in contracts/tools.toml; engine role is canonical in contracts/engines.toml.",
        "engine_binding_contract": {"path": "engine-tool-contracts.json", "schema": "engine-tool-contracts.schema.json", "version": "2.0.0"},
        "strict_override_semantics": {
            "locked": "cannot change in strict mode; select a different named/versioned profile",
            "bounded": "may tighten inside the reviewed envelope; widening requires a different named/versioned profile",
            "recommended": "may only move within an explicit source-backed envelope",
            "chemistry": "polymerase/buffer/reaction identity cannot be anonymously substituted in strict mode",
            "validation_wording": "policy-checked is not experimentally validated",
        },
        "scientific_policy_ceiling": "Strict scientific policy remains fail-closed across toolchain and validation modes.",
    }
    targets["tools/scientific-tools.json"] = {
        "schema_version": "2.0.0",
        "tools": {
            tid: {
                "version": value["version"],
                "role": value.get("catalog_disposition", "OPTIONAL"),
                "install_scope": value.get("install_scope", value["execution_scope"]),
                "source": value.get("package_source", value.get("source_ref", "")),
                **({"wheel_sha256": value["package_sha256"]} if value.get("package_sha256") else {}),
                **({"wheel_filename": value["package_filename"]} if value.get("package_filename") else {}),
            }
            for tid, value in tools.items()
            if value.get("package_sha256")
        },
        "policy": "Generated from contracts/tools.toml. Python scientific distributions are accepted only when exact version and approved artifact hash match.",
    }

    # Shared schemas for versioned IPC, validation and generic numeric recipes.
    targets["contracts/schemas/ipc-envelope.schema.json"] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "pcrstudio://schemas/ipc-envelope-v2",
        "title": "PCRStudio worker IPC envelope",
        "type": "object",
        "additionalProperties": False,
        "required": ["protocolVersion", "requestSchema", "resultSchema", "requestId", "command", "engine", "module", "payload"],
        "properties": {
            "protocolVersion": {"const": foundation["ipc_protocol_version"]},
            "requestSchema": {"type": "integer", "minimum": 1},
            "resultSchema": {"type": "integer", "minimum": 1},
            "requestId": {"type": "string", "minLength": 1, "maxLength": 128},
            "command": {"type": "string", "minLength": 1},
            "engine": {"type": "string", "minLength": 1},
            "module": {"type": ["string", "null"]},
            "payload": {"type": "object"},
        },
    }
    targets["contracts/schemas/validation-issue.schema.json"] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "pcrstudio://schemas/validation-issue-v1",
        "title": "PCRStudio ValidationIssue",
        "type": "object", "additionalProperties": False,
        "required": ["code", "severity", "ownerStep", "fieldPath", "message", "source", "blocking"],
        "properties": {
            "code": {"type": "string", "pattern": "^[A-Z0-9_]+$"},
            "severity": {"enum": ["info", "warning", "error"]},
            "ownerStep": {"enum": ["target", "design", "strategy", "constraints", "vector", "reaction", "specificity", "validation", "construct", "review", "execution"]},
            "fieldPath": {"type": ["string", "null"]},
            "message": {"type": "string", "minLength": 1},
            "source": {"type": "string", "minLength": 1},
            "blocking": {"type": "boolean"},
        },
    }
    targets["contracts/schemas/numeric-recipe.schema.json"] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "pcrstudio://schemas/numeric-recipe-v2",
        "title": "PCRStudio generic numeric recipe",
        "type": "object", "additionalProperties": False,
        "required": ["schemaVersion", "identity", "values", "ranges", "origins", "appliedOverlays", "unresolvedDependencies", "warnings", "decisionImpact"],
        "properties": {
            "schemaVersion": {"const": foundation["numeric_recipe_schema_version"]},
            "identity": {"type": "string", "minLength": 1},
            "values": {"type": "object", "additionalProperties": {"type": "number"}},
            "ranges": {"type": "object", "additionalProperties": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "number"}}},
            "origins": {"type": "object", "additionalProperties": {"type": "string"}},
            "appliedOverlays": {"type": "array", "items": {"type": "object"}},
            "unresolvedDependencies": {"type": "array", "items": {"type": "object"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "decisionImpact": {"enum": ["none", "ranking", "eligibility"]},
        },
    }

    # Cross-language differential corpus.  Every consumer receives the same
    # module/engine/command/resource identity plus exact required-context facts.
    # Unit tests in Python, Rust and Web consume this file independently so a
    # drift in any one implementation is caught without hand-maintained cases.
    engine_ids = [row["id"] for row in sorted(engines.values(), key=lambda row: int(row["display_order"]))]
    differential_cases = []
    for index, (mid, value) in enumerate(sorted(modules.items())):
        wrong_engine = engine_ids[(engine_ids.index(value["engine"]) + 1) % len(engine_ids)]
        differential_cases.append({
            "module": mid,
            "expectedEngine": value["engine"],
            "expectedCommand": value["command"],
            "resourceWeight": value["resource_weight"],
            "requiredContext": value["required_context"],
            "conditionalRequiredContext": value["conditional_required_context"],
            "wireRequiredContext": value["wire_required_context"],
            "wireConditionalRequiredContext": value["wire_conditional_required_context"],
            "wireRequiredAnyOf": value["wire_required_any_of"],
            "fieldOwners": value["field_owners"],
            "wrongEngine": wrong_engine,
            "caseId": f"module-contract-{index:02d}-{mid}",
        })
    differential_payload = {
        "schema_version": "1.1.0",
        "generation_policy": "Generated from contracts/modules.toml and contracts/engines.toml; do not hand-edit.",
        "cases": differential_cases,
    }
    for rel in (
        "contracts/differential-context.generated.json",
        "tools/src/pcr_tools/data/differential-context.generated.json",
        "web/src/lib/contracts/differential-context.generated.json",
        "crates/pcr-contracts/generated/differential-context.generated.json",
    ):
        targets[rel] = differential_payload

    bindings = {mid: {"engine": value["engine"], "command": value["command"], "resourceWeight": value["resource_weight"]} for mid, value in sorted(modules.items())}
    binding_text = (
        "// Generated from contracts/modules.toml and contracts/engines.toml; do not hand-edit.\n"
        + "export const ENGINE_IDS = "
        + json.dumps(engine_ids, ensure_ascii=False)
        + " as const;\n\n"
        + "export type EngineId = (typeof ENGINE_IDS)[number];\n\n"
        + "export const MODULE_BINDINGS = "
        + json.dumps(bindings, indent=2, ensure_ascii=False, sort_keys=True)
        + " as const;\n\n"
        + "export type ModuleId = keyof typeof MODULE_BINDINGS;\n"
        + "export type EngineFor<M extends ModuleId> = (typeof MODULE_BINDINGS)[M][\"engine\"];\n"
    )
    def rust_variant(engine_id: str) -> str:
        return "".join(part[:1].upper() + part[1:] for part in engine_id.split("-"))

    ordered_engines = sorted(engines.values(), key=lambda row: int(row["display_order"]))
    rust_engine_lines = [
        "// @generated by scripts/generate-foundation-contracts.py from contracts/engines.toml; do not edit.",
        "/// One canonical scientific design engine.",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]",
        "#[serde(rename_all = \"kebab-case\")]",
        "pub enum EngineId {",
    ]
    for engine in ordered_engines:
        rust_engine_lines.append(f"    /// {engine['label']}.")
        rust_engine_lines.append(f"    {rust_variant(str(engine['id']))},")
    rust_engine_lines += [
        "}", "", "impl EngineId {",
        "    /// Every engine in canonical display order.",
        "    #[must_use]",
        "    pub const fn all() -> &'static [Self] {",
        "        &[",
    ]
    for engine in ordered_engines:
        rust_engine_lines.append(f"            Self::{rust_variant(str(engine['id']))},")
    rust_engine_lines += ["        ]", "    }", "", "    /// Human-readable label.", "    #[must_use]", "    pub const fn label(self) -> &'static str {", "        match self {"]
    for engine in ordered_engines:
        rust_engine_lines.append(f"            Self::{rust_variant(str(engine['id']))} => {json.dumps(str(engine['label']))},")
    rust_engine_lines += ["        }", "    }", "", "    /// Canonical input shape.", "    #[must_use]", "    pub const fn input(self) -> &'static str {", "        match self {"]
    for engine in ordered_engines:
        rust_engine_lines.append(f"            Self::{rust_variant(str(engine['id']))} => {json.dumps(str(engine['input']))},")
    rust_engine_lines += ["        }", "    }", "}", ""]
    rust_engine_id = "\n".join(rust_engine_lines)

    limits = foundation.get("limits", {})
    required_limits = [
        "sequence_bytes", "sequence_asset_externalize_bytes", "server_action_bytes", "http_body_bytes", "account_import_bytes",
        "project_settings_bytes", "project_notes_bytes", "run_label_bytes",
        "run_job_request_bytes", "run_job_aux_bytes", "worker_stdout_bytes",
        "worker_stderr_bytes", "run_document_bytes", "account_project_data_bytes",
        "account_job_data_bytes", "backup_document_bytes",
    ]
    missing_limits = [name for name in required_limits if name not in limits]
    if missing_limits:
        raise ValueError(f"contracts/foundation.toml is missing canonical limits: {', '.join(missing_limits)}")
    if int(limits["run_document_bytes"]) < int(limits["run_job_request_bytes"]) + int(limits["worker_stdout_bytes"]):
        raise ValueError("run_document_bytes must cover max job request + max worker stdout")
    if int(limits["server_action_bytes"]) <= int(limits["sequence_bytes"]):
        raise ValueError("server_action_bytes must leave framing headroom above sequence_bytes")
    if int(limits["project_settings_bytes"]) <= int(limits["sequence_bytes"]):
        raise ValueError("project_settings_bytes must leave draft metadata headroom above sequence_bytes")
    if int(limits["backup_document_bytes"]) < int(limits["account_project_data_bytes"]):
        raise ValueError("backup_document_bytes must cover account_project_data_bytes")

    rust_foundation_lines = [
        "// @generated by scripts/generate-foundation-contracts.py; do not edit.",
        "/// Current module contract identity from contracts/foundation.toml.",
        f'pub const MODULE_CONTRACT_VERSION: &str = {json.dumps(str(foundation["module_contract_version"]))};',
        "/// Current IPC protocol identity from contracts/foundation.toml.",
        f'pub const IPC_PROTOCOL_VERSION: &str = {json.dumps(str(foundation["ipc_protocol_version"]))};',
        "/// Current draft persistence schema from contracts/foundation.toml.",
        f'pub const DRAFT_SCHEMA_VERSION: i32 = {int(foundation["draft_schema_version"])};',
        "/// Current request persistence schema from contracts/foundation.toml.",
        f'pub const REQUEST_SCHEMA_VERSION: i32 = {int(foundation["request_schema_version"])};',
        "/// Current result persistence schema from contracts/foundation.toml.",
        f'pub const RESULT_SCHEMA_VERSION: i32 = {int(foundation["result_schema_version"])};',
        "",
    ]
    for name in required_limits:
        rust_name = "MAX_" + name.upper()
        rust_foundation_lines += [
            f"/// Canonical `{name}` ceiling from contracts/foundation.toml.",
            f"pub const {rust_name}: usize = {int(limits[name])};",
        ]
    rust_foundation_lines.append("")
    rust_foundation = "\n".join(rust_foundation_lines)

    limit_names = {
        "sequence_bytes": "MAX_SEQUENCE_BYTES",
        "sequence_asset_externalize_bytes": "SEQUENCE_ASSET_EXTERNALIZE_BYTES",
        "server_action_bytes": "MAX_ACTION_BYTES",
        "http_body_bytes": "MAX_HTTP_BODY_BYTES",
        "account_import_bytes": "MAX_ACCOUNT_IMPORT_BYTES",
        "project_settings_bytes": "MAX_PROJECT_SETTINGS_BYTES",
        "project_notes_bytes": "MAX_PROJECT_NOTES_BYTES",
        "run_label_bytes": "MAX_RUN_LABEL_BYTES",
        "run_job_request_bytes": "MAX_RUN_JOB_REQUEST_BYTES",
        "run_job_aux_bytes": "MAX_RUN_JOB_AUX_BYTES",
        "worker_stdout_bytes": "MAX_WORKER_STDOUT_BYTES",
        "worker_stderr_bytes": "MAX_WORKER_STDERR_BYTES",
        "run_document_bytes": "MAX_RUN_DOCUMENT_BYTES",
        "account_project_data_bytes": "MAX_ACCOUNT_PROJECT_DATA_BYTES",
        "account_job_data_bytes": "MAX_ACCOUNT_JOB_DATA_BYTES",
        "backup_document_bytes": "MAX_BACKUP_DOCUMENT_BYTES",
    }
    limits_ts = "// @generated by scripts/generate-foundation-contracts.py from contracts/foundation.toml; do not edit.\n" + "\n".join(
        f"export const {limit_names[name]} = {int(limits[name])};" for name in required_limits
    ) + "\n"

    text_targets = {
        "web/src/lib/contracts/module-bindings.generated.ts": binding_text,
        "web/src/lib/contracts/limits.generated.ts": limits_ts,
        "crates/pcr-contracts/generated/foundation.generated.rs": rust_foundation,
        "crates/pcr-core/generated/engine_id.generated.rs": rust_engine_id,
    }

    # Every Foundation projection embeds the canonical source fingerprint set.
    # The graph therefore records the actual dependency relation instead of
    # guessing ownership from target filenames (which previously omitted valid
    # edges such as page-capabilities <- modules.toml).
    generated_outputs = sorted([*targets, *text_targets, "contracts/generated-graph.json"])
    graph = {
        "schema_version": "1.1.0",
        "sources": {source.as_posix(): generated_outputs for source in SOURCES},
        "all_generated_outputs": generated_outputs,
        "generator": "scripts/generate-foundation-contracts.py",
        "note": "Foundation projections embed all four canonical source hashes; any source change intentionally invalidates the generated set.",
    }
    targets["contracts/generated-graph.json"] = graph

    failures: list[str] = []
    for rel, payload in sorted(targets.items()):
        if not write(rel, payload, check=args.check):
            failures.append(rel)
    for rel, rendered in sorted(text_targets.items()):
        if not write_text(rel, rendered, check=args.check):
            failures.append(rel)
    if args.check and failures:
        print("FOUNDATION_GENERATED_DRIFT")
        for rel in failures:
            print(rel)
        return 1
    print(f"FOUNDATION_CONTRACTS={'CHECK-PASS' if args.check else 'GENERATED'} files={len(targets) + len(text_targets)} modules={len(modules)} engines={len(engines)} tools={len(tools)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
