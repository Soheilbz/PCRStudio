"""Canonical Generation-1 runtime contract for PCRStudio.

Architectural authority is generated from ``contracts/*.toml``. This module
contains only executable helpers and stable scientific boundary semantics; it
does not restate module, engine or tool registries by hand.
"""
from __future__ import annotations

from typing import Any, Final

from .contract_loader import (
    COMMAND_TO_ENGINE,
    ENGINE_BINDINGS,
    FOUNDATION,
    MODULE_CONTRACTS,
    MODULE_TO_COMMAND,
    MODULE_TO_ENGINE,
    TOOLS,
    ToolSpec,
)

CONTRACT_VERSION: Final = str(FOUNDATION["module_contract_version"])
PARAMETER_MAP_VERSION: Final = "generation1-current"
INPUT_SCHEMA_VERSION: Final = f"pcrstudio-worker-input-v{FOUNDATION['request_schema_version']}"
OUTPUT_SCHEMA_VERSION: Final = f"pcrstudio-worker-output-v{FOUNDATION['result_schema_version']}"
IPC_PROTOCOL_VERSION: Final = str(FOUNDATION["ipc_protocol_version"])

COORDINATE_CONTRACT: Final[dict[str, Any]] = {
    "version": str(FOUNDATION["coordinate_contract_version"]),
    "basis": 0,
    "interval": "half-open",
    "notation": "[start,end)",
    "oligo_sequence_orientation": "5prime-to-3prime",
    "strand_field_required": True,
    "single_base_position": "0-based",
    "junction_position": "boundary-between-bases",
    "source_coordinate_policy": "preserve raw source coordinates in adapter evidence; normalize before engine use",
}

PIPELINE_STAGES: Final[tuple[str, ...]] = (
    "api-schema-validation",
    "module-resolution",
    "input-normalization",
    "coordinate-normalization",
    "chemistry-and-parameter-resolution",
    "candidate-generation",
    "assay-hard-filters",
    "thermodynamic-and-structure-evaluation",
    "request-context-specificity-and-inclusivity",
    "deterministic-ranking",
    "bounded-search-expansion-with-unchanged-hard-gates",
    "independent-toolchain-validation",
    "verification-envelope",
    "result-schema-and-ui",
)

def assay_identity(request: dict[str, Any], command: str) -> tuple[str, str]:
    """Resolve module/engine identity and refuse contradictory payloads."""
    assay = request.get("assay") or {}
    if not isinstance(assay, dict):
        raise ValueError("`assay` must be an object")
    module_id = str(assay.get("id") or "")
    declared_engine = str(assay.get("engine") or "")
    expected_engine = MODULE_TO_ENGINE.get(module_id) if module_id else None
    command_engine = COMMAND_TO_ENGINE.get(command)
    engine_id = expected_engine or declared_engine or command_engine or ""
    if module_id and expected_engine is None:
        raise ValueError(f"unknown assay/module `{module_id}`")
    if expected_engine and declared_engine and expected_engine != declared_engine:
        raise ValueError(
            f"assay `{module_id}` belongs to `{expected_engine}`, not `{declared_engine}`"
        )
    if command_engine and engine_id and command_engine != engine_id:
        raise ValueError(
            f"worker command `{command}` implements `{command_engine}`, not `{engine_id}`"
        )
    if module_id:
        expected_command = MODULE_TO_COMMAND[module_id]
        if expected_command != command:
            raise ValueError(
                f"assay `{module_id}` is executed by worker command `{expected_command}`, not `{command}`"
            )
    return module_id, engine_id


def _camel_segment(part: str) -> str:
    """Lower-camel alias for one canonical snake_case context segment."""
    head, *tail = part.split("_")
    return head + "".join(piece[:1].upper() + piece[1:] for piece in tail)


def _context_value(request: dict[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve canonical dotted context across Python and Rust worker vocabularies.

    Runtime contracts use snake_case. Most Rust workers emit that vocabulary,
    while the PrimalScheme lifecycle adapter intentionally receives its public
    lower-camel fields. Treat those spellings as aliases, but never let two
    contradictory spellings choose a value by dictionary/order precedence.
    Falsy values remain valid recorded context.
    """
    value: Any = request
    traversed: list[str] = []
    for part in path.split("."):
        if not isinstance(value, dict):
            return False, None
        camel = _camel_segment(part)
        exact_present = part in value
        camel_present = camel != part and camel in value
        if exact_present and camel_present and value[part] != value[camel]:
            at = ".".join([*traversed, part])
            raise ValueError(
                f"conflicting runtime context aliases `{at}` and "
                f"`{'.'.join([*traversed, camel])}`; supply one unambiguous value"
            )
        if exact_present:
            value = value[part]
        elif camel_present:
            value = value[camel]
        else:
            return False, None
        traversed.append(part)
    return True, value


def _context_supplied(request: dict[str, Any], path: str) -> bool:
    present, value = _context_value(request, path)
    if not present or value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    # Numeric zero and boolean false are explicit, scientifically meaningful values.
    return True


def _require_context_path(request: dict[str, Any], module_id: str, path: str) -> None:
    if not _context_supplied(request, path):
        raise ValueError(
            f"assay `{module_id}` requires non-empty `{path}`; this requirement may not be relaxed"
        )


def validate_required_context(request: dict[str, Any], module_id: str) -> None:
    """Defence-in-depth for the explicit HTTP/worker wire contract.

    Browser semantic readiness is deliberately separate. Flat draft controls may
    be normalized into nested request objects, so runtime code must never infer
    wire paths from ``required_context`` naming conventions.
    """
    contract = MODULE_CONTRACTS.get(module_id) or {}
    for path in contract.get("wire_required_context", ()):
        _require_context_path(request, module_id, path)

    for rule in contract.get("wire_conditional_required_context", ()):
        when = rule.get("when", {})
        active = all(_context_value(request, path) == (True, expected) for path, expected in when.items())
        if not active:
            continue
        for path in rule.get("required_context", ()):
            _require_context_path(request, module_id, path)

    for group in contract.get("wire_required_any_of", ()):
        if not any(_context_supplied(request, path) for path in group):
            choices = " | ".join(str(path) for path in group)
            raise ValueError(
                f"assay `{module_id}` requires at least one wire representation: {choices}"
            )


def engine_contract(engine_id: str, module_id: str = "") -> dict[str, Any]:
    """Machine-readable engine contract attached to every design result."""
    return {
        "contract_version": CONTRACT_VERSION,
        "parameter_map_version": PARAMETER_MAP_VERSION,
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "module_id": module_id,
        "engine_id": engine_id,
        "coordinate_contract": dict(COORDINATE_CONTRACT),
        "pipeline_stages": list(PIPELINE_STAGES),
        "parameter_precedence": [
            "tool-hard-capability",
            "assay-hard-invariant",
            "locked-chemistry-profile",
            "policy-checked-user-override",
            "assay-recommended-default",
            "purpose-default",
            "pcrstudio-default",
            "explicitly-adopted-tool-default",
        ],
        "override_policy": {
            "default": "recommended-starting-value-user-tunable",
            "hard_capability": "forbidden",
            "hard_assay_invariant": "forbidden",
            "locked_chemistry": "forbidden",
            "bounded_numeric": "bounded",
            "recommended_numeric": "user-tunable-with-explicit-provenance",
        },
        "bindings": [dict(binding) for binding in ENGINE_BINDINGS.get(engine_id, ())],
    }


def module_contract(module_id: str) -> dict[str, Any]:
    """Return the canonical assay contract used by Python, API and UI.

    Field names intentionally mirror ``knowledge/runtime/module-contracts.json``
    and the TypeScript ``moduleContractSchema``.  Extra identity metadata is
    additive; consumers never have to translate a second vocabulary.
    """
    raw = MODULE_CONTRACTS.get(module_id)
    if raw is None:
        return {}
    contract = {
        "module_id": module_id,
        "engine": raw["engine"],
        "command": raw["command"],
        "required_context": list(raw.get("required_context", ())),
        "wire_required_context": list(raw.get("wire_required_context", ())),
        "wire_required_any_of": [list(group) for group in raw.get("wire_required_any_of", ())],
        "gates": list(raw.get("gates", ())),
        "fallback": raw.get("fallback", ""),
    }
    conditional = raw.get("conditional_required_context", ())
    if conditional:
        contract["conditional_required_context"] = [
            {
                "when": dict(rule.get("when", {})),
                "required_context": list(rule.get("required_context", ())),
            }
            for rule in conditional
        ]
    wire_conditional = raw.get("wire_conditional_required_context", ())
    if wire_conditional:
        contract["wire_conditional_required_context"] = [
            {
                "when": dict(rule.get("when", {})),
                "required_context": list(rule.get("required_context", ())),
            }
            for rule in wire_conditional
        ]
    return contract


def resolved_parameters(request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Explain resolved values *and* the policy that allowed each value.

    ``Settings.prepare`` is the authoritative resolver for the common engines
    and already records whether a field was locked, bounded or merely a
    recommended starting value. Prefer that exact record whenever the engine exposes it.
    The fallback below mirrors the same policy vocabulary so specialized
    engines cannot silently downgrade a hard profile to an unrestricted user
    override in provenance.
    """
    result_assay = result.get("assay") if isinstance(result.get("assay"), dict) else {}
    native = result_assay.get("parameter_resolution") if isinstance(result_assay, dict) else None
    if isinstance(native, dict) and isinstance(native.get("reaction"), dict) and isinstance(native.get("constraints"), dict):
        return native

    assay = request.get("assay") if isinstance(request.get("assay"), dict) else {}
    defaults = assay.get("defaults") if isinstance(assay.get("defaults"), dict) else {}
    assay_constraints = defaults.get("constraints") if isinstance(defaults.get("constraints"), dict) else {}
    constraint_policy = defaults.get("constraintPolicy") if isinstance(defaults.get("constraintPolicy"), dict) else {}
    condition_policy = defaults.get("conditionPolicy") if isinstance(defaults.get("conditionPolicy"), dict) else {}
    user_conditions = request.get("conditions") if isinstance(request.get("conditions"), dict) else {}
    user_constraints = request.get("constraints") if isinstance(request.get("constraints"), dict) else {}

    def policy_label(raw: Any) -> str:
        value = str(raw or "recommended").strip().lower()
        return {
            "locked": "locked-assay-invariant",
            "bounded": "bounded-to-assay-envelope",
            "recommended": "recommended-starting-value-user-tunable",
        }.get(value, "recommended-starting-value-user-tunable")

    reaction: dict[str, Any] = {}
    for name, value in (result.get("reaction") or {}).items():
        if not isinstance(value, (int, float, str, bool)) or name in {"polymerase", "polymerase_name"}:
            continue
        reaction[name] = {
            "value": value,
            "source": "policy-checked-user-override" if name in user_conditions else "resolved-chemistry-profile",
            "override_policy": policy_label(condition_policy.get(name)),
        }

    def explain_constraints(values: Any, supplied: Any) -> Any:
        if not isinstance(values, dict):
            return values
        answer: dict[str, Any] = {}
        for name, value in values.items():
            nested_supplied = supplied.get(name, {}) if isinstance(supplied, dict) else {}
            if isinstance(value, dict):
                answer[name] = explain_constraints(value, nested_supplied)
                continue
            if isinstance(supplied, dict) and name in supplied:
                source = "policy-checked-user-override"
            elif name in assay_constraints:
                source = "assay-recommended-default"
            else:
                source = "engine-resolved-default"
            answer[name] = {
                "value": value,
                "source": source,
                "override_policy": policy_label(constraint_policy.get(name)),
            }
        return answer

    return {"reaction": reaction, "constraints": explain_constraints(result.get("constraints") or {}, user_constraints)}
