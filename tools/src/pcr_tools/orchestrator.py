"""Common orchestration envelope for all eleven design engines."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from . import validation_plan
from .external_validation import validate_result
from .fingerprints import toolchain_fingerprint
from .method_fidelity import active_for_run as method_fidelity_for_run
from .method_fidelity import enforce_scientific_strict as enforce_method_fidelity
from .method_fidelity import references_for_module as method_fidelity_references_for_module
from .method_fidelity import registry_identity as method_fidelity_registry_identity
from .runtime_contract import (
    assay_identity,
    engine_contract,
    module_contract,
    resolved_parameters,
    validate_required_context,
)
from .scientific_authority import for_module as scientific_authorities_for_module
from .scientific_integrity import provenance_block as scientific_integrity_block
from .scientific_integrity import require_named_assay
from .tiling_backend import run as run_tiling_backend
from .tool_runtime import ToolRuntimeError, require_engine_toolchain, toolchain_mode

Handler = Callable[[dict[str, Any]], dict[str, Any]]


def orchestrate(command: str, request: dict[str, Any], handler: Handler) -> dict[str, Any]:
    """Run one engine with measured stages and cross-engine invariants.

    Stage telemetry is elapsed time and bounded counts only. It never contains
    template/primer sequence, sample names, paths, or other user payload.
    """
    started = perf_counter()
    stages: list[dict[str, Any]] = []

    def stage(name: str, since: float, **facts: Any) -> float:
        now = perf_counter()
        row: dict[str, Any] = {"name": name, "duration_ms": round((now - since) * 1000.0, 3)}
        row.update(facts)
        stages.append(row)
        return now

    mark = started
    require_named_assay(request, command=command, require_profile_authority=True)
    module_id, engine_id = assay_identity(request, command)
    if module_id:
        validate_required_context(request, module_id)
    require_engine_toolchain(engine_id, module_id, request)
    mark = stage("input-validation-and-tool-preflight", mark)

    if command == "tiling":
        answer = run_tiling_backend(request)
    else:
        answer = handler(request)
    if not isinstance(answer, dict):
        raise ValueError(f"worker command `{command}` did not return an object")
    candidate_count = 0
    for key in ("sets", "pairs", "assays", "tiles", "primers", "junctions"):
        value = answer.get(key)
        if isinstance(value, list):
            candidate_count = len(value)
            break
    mark = stage("scientific-design", mark, primary_result_count=candidate_count)

    returned_engine = str(answer.get("engine") or "")
    if returned_engine and engine_id and returned_engine != engine_id:
        raise ValueError(
            f"worker command `{command}` declared `{engine_id}` but returned `{returned_engine}`"
        )
    engine_id = returned_engine or engine_id
    if not engine_id:
        raise ValueError(f"worker command `{command}` did not resolve an engine")

    answer["runtime_contract"] = engine_contract(engine_id, module_id)
    answer["module_contract"] = module_contract(module_id) if module_id else {}
    answer["runtime_contract"]["resolved_parameters"] = resolved_parameters(request, answer)
    mark = stage("contract-and-parameter-resolution", mark)

    answer["toolchain_validation"] = validate_result(
        command=command,
        request=request,
        result=answer,
        engine_id=engine_id,
        module_id=module_id,
    )
    mark = stage("independent-toolchain-validation", mark)

    answer.setdefault("validation", validation_plan.for_assay(module_id) if module_id else None)
    answer["scientific_integrity"] = scientific_integrity_block()
    validation = answer["toolchain_validation"]
    selected_oligos = int(validation.get("selected_oligos") or 0)
    why_nothing = str(answer.get("why_nothing") or "").strip()
    computational_complete = selected_oligos > 0 and not why_nothing
    if (
        toolchain_mode() == "strict"
        and computational_complete
        and validation["status"]
        in {"verification-incomplete", "validator-error", "evidence-collected-limited"}
    ):
        raise ToolRuntimeError(
            "design refused: strict external toolchain validation did not complete; "
            "repair the configured tools/databases and retry"
        )
    external_complete = (
        validation["status"] in {"evidence-collected", "not-applicable"}
        and validation.get("interpretation_complete") is True
    )
    answer["verification"] = {
        "status": "computational-incomplete"
        if not computational_complete
        else validation["status"],
        "computational_design_complete": computational_complete,
        "external_evidence_complete": external_complete,
        "wet_lab_validated": False,
        "selected_oligos": selected_oligos,
        "note": (
            "PCRStudio reports computational design, independent in-silico evidence, and wet-lab "
            "validation as separate claims. Software output is never labelled wet-lab validated."
        ),
    }
    mark = stage("verification-envelope", mark)

    provenance = answer.setdefault("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("result provenance must be an object")
    provenance["scientific_authorities"] = scientific_authorities_for_module(module_id)
    active_methods = method_fidelity_for_run(module_id, command, request, answer)
    enforce_method_fidelity(active_methods, context=f"{module_id or engine_id}:{command}")
    provenance["method_fidelity"] = active_methods
    provenance["method_fidelity_references"] = method_fidelity_references_for_module(module_id)
    provenance["method_fidelity_scope"] = "active-run-methods-plus-separate-reference-authorities"
    provenance["method_fidelity_registry"] = method_fidelity_registry_identity()
    provenance["toolchain_fingerprint"] = toolchain_fingerprint(answer)
    stage("result-assembly", mark)
    answer["execution_telemetry"] = {
        "schema_version": "1.0.0",
        "measured": True,
        "stages": stages,
        "total_duration_ms": round((perf_counter() - started) * 1000.0, 3),
        "privacy": "No sequence, target/sample name, filesystem path, or raw request value is recorded.",
    }
    return answer
