"""Optional independent pydna 5.5.16 simulation.

This adapter is deliberately advisory. PCRStudio engines remain the design
authority. Most bound engines use independent PCR-product simulation; the
restriction-cloning branch additionally performs an explicitly typed
restriction-digest/ligation construct simulation against the exact supplied
recipient vector. Missing pydna never blocks a normal design, and a simulation
failure is reported rather than translated into an unexplained primer rejection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime_contract import ENGINE_BINDINGS
from .tool_runtime import run_tool, tool_status
from .inverse_topology import InverseTopologyError, exact_topology


def _clean(value: Any) -> str:
    return "".join(str(value or "").split()).upper().replace("U", "T")


def _pydna_operation(engine_id: str) -> str:
    for binding in ENGINE_BINDINGS.get(engine_id, ()):
        if str(binding.get("tool_id")) == "pydna":
            operations = tuple(str(value) for value in binding.get("operations", ()))
            if len(operations) != 1:
                raise ValueError(f"{engine_id}/pydna must declare exactly one operation; got {operations}")
            return operations[0]
    raise ValueError(f"{engine_id} does not declare a pydna binding")


def _pcr_product(
    forward: str,
    reverse: str,
    template: str,
    *,
    circular: bool,
    engine_id: str,
    module_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bridge = Path(__file__).with_name("pydna_bridge.py")
    payload = json.dumps({
        "operation": "pcr-product",
        "forward": forward,
        "reverse": reverse,
        "template": template,
        "circular": circular,
    })
    completed, run = run_tool(
        "pydna",
        [str(bridge)],
        role="OPTIONAL",
        operation_id=_pydna_operation(engine_id),
        engine_id=engine_id,
        module_id=module_id,
        stdin=payload,
        timeout_seconds=60,
    )
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, dict):
        raise ValueError("pydna bridge returned a non-object result")
    return parsed, run


def validate(request: dict[str, Any], result: dict[str, Any], engine_id: str) -> dict[str, Any]:
    """Return independent pydna evidence for the three Atlas-bound engines."""
    status = tool_status("pydna")
    assay = request.get("assay") if isinstance(request.get("assay"), dict) else {}
    module_id = str(assay.get("id") or "")
    restriction_cloning = engine_id == "flanking-pair" and module_id == "restriction-cloning"
    base: dict[str, Any] = {
        "tool_id": "pydna",
        "configured_version": "5.5.16",
        "status": "not-applicable",
        "purpose": (
            "independent restriction-digest/ligation construct simulation"
            if restriction_cloning else
            "independent PCR-product simulation"
        ),
        "decision_impact": "advisory-independent-simulation",
        "interpretation_contract": (
            "pydna-independent-restriction-construct-simulation-v1"
            if restriction_cloning else
            "pydna-independent-pcr-product-simulation-v2"
        ),
        "evidence": {},
        "tool_run": None,
        "warnings": [],
    }
    if engine_id not in {"junction-primers", "outward-pair", "mutagenic-pair"} and not restriction_cloning:
        base["evidence"] = {"reason": "engine/module does not bind executable pydna validation in the generation-1 Atlas"}
        return base
    if not status.get("available"):
        base["evidence"] = {"reason": "optional pydna distribution is unavailable"}
        base["warnings"].append("Optional pydna 5.5.16 simulation did not run; primary PCRStudio design remains available.")
        return base
    if status.get("version_matches_contract") is False:
        base["status"] = "error"
        base["warnings"].append("Installed pydna version does not match the generation-1 5.5.16 contract.")
        return base

    simulations: list[dict[str, Any]] = []
    tool_runs: list[dict[str, Any]] = []

    def simulate(forward: str, reverse: str, template: str, *, circular: bool) -> dict[str, Any]:
        product, run = _pcr_product(
            forward,
            reverse,
            template,
            circular=circular,
            engine_id=engine_id,
            module_id=module_id,
        )
        tool_runs.append(run)
        return product

    try:
        if restriction_cloning:
            pairs = result.get("pairs") or []
            vector = _clean(request.get("cloning_vector"))
            insert = _clean(request.get("template"))
            cloning = result.get("cloning") if isinstance(result.get("cloning"), dict) else {}
            tails = request.get("tails") if isinstance(request.get("tails"), dict) else {}
            if pairs and vector and insert:
                pair = pairs[0]
                tailed = pair.get("tailed") if isinstance(pair.get("tailed"), dict) else {}
                forward = _clean((tailed.get("left") or {}).get("sequence"))
                reverse = _clean((tailed.get("right") or {}).get("sequence"))
                bridge = Path(__file__).with_name("pydna_bridge.py")
                payload = json.dumps({
                    "operation": "restriction-ligation-construct",
                    "forward": forward,
                    "reverse": reverse,
                    "template": insert,
                    "vector": vector,
                    "forward_enzyme": tails.get("forward_enzyme"),
                    "reverse_enzyme": tails.get("reverse_enzyme"),
                })
                completed, run = run_tool(
                    "pydna", [str(bridge)], role="OPTIONAL",
                    operation_id=_pydna_operation(engine_id),
                    engine_id=engine_id, module_id=module_id, stdin=payload, timeout_seconds=60,
                )
                parsed = json.loads(completed.stdout)
                if not isinstance(parsed, dict):
                    raise ValueError("pydna restriction bridge returned a non-object result")
                tool_runs.append(run)
                simulations.append({"candidate_rank": 1, **parsed})
                cloning_directional = cloning.get("directional")
                if parsed.get("unique_construct") is False and cloning_directional is True:
                    base["warnings"].append(
                        "Sequence-level vector geometry suggested a directional branch, but independent pydna simulation did not recover one unique circular construct; review digest/ligation evidence."
                    )
            else:
                base["evidence"] = {"reason": "restriction-cloning pydna simulation requires a selected tailed pair plus exact insert/vector sequences"}
                return base
        elif engine_id == "mutagenic-pair":
            pairs = result.get("pairs") or []
            template = _clean(request.get("template"))
            if pairs and template:
                pair = pairs[0]
                simulations.append({
                    "candidate_rank": 1,
                    **simulate(
                        _clean((pair.get("forward") or {}).get("sequence")),
                        _clean((pair.get("reverse") or {}).get("sequence")),
                        template,
                        circular=False,
                    ),
                })
        elif engine_id == "outward-pair":
            branch = str((result.get("experiment_contract") or {}).get("branch") or "")
            template = _clean(request.get("template"))
            pairs = result.get("pairs") or []
            circular_template = ""
            if branch == "restriction-self-ligation" and pairs and request.get("inverse_reference_sequence") and request.get("enzyme"):
                try:
                    resolved = exact_topology(
                        str(request.get("inverse_reference_sequence")),
                        template, str(request.get("enzyme")),
                        circular=bool(request.get("inverse_reference_circular", False)),
                    )
                    circular_template = _clean(resolved.get("_circle_sequence"))
                except InverseTopologyError as exc:
                    base["status"] = "error"
                    base["evidence"] = {"reason": str(exc), "branch": branch}
                    return base
            elif branch == "supplied-circular-template" and pairs:
                circular_template = template
            if pairs and circular_template:
                pair = pairs[0]
                simulations.append({
                    "candidate_rank": 1,
                    **simulate(
                        _clean((pair.get("left") or {}).get("sequence")),
                        _clean((pair.get("right") or {}).get("sequence")),
                        circular_template, circular=True,
                    ),
                })
            else:
                base["evidence"] = {
                    "reason": "complete circular template sequence is not known; pydna will not invent the unknown flank",
                    "branch": branch or "unresolved",
                }
                return base
        elif engine_id == "junction-primers":
            segments = request.get("segments") or []
            order = result.get("order_sheet") or []
            by_fragment: dict[str, list[dict[str, Any]]] = {}
            for oligo in order:
                if isinstance(oligo, dict) and oligo.get("tube"):
                    by_fragment.setdefault(str(oligo["tube"]), []).append(oligo)
            for segment in segments:
                if not isinstance(segment, dict) or str(segment.get("kind") or "amplified") != "amplified":
                    continue
                name = str(segment.get("name") or "")
                primers = by_fragment.get(name, [])
                template = _clean(segment.get("template") or segment.get("sequence"))
                if len(primers) == 2 and template:
                    simulations.append({
                        "fragment": name,
                        **simulate(
                            _clean(primers[0].get("sequence")),
                            _clean(primers[1].get("sequence")),
                            template,
                            circular=False,
                        ),
                    })

        if simulations:
            base["status"] = "evidence-collected"
            base["tool_run"] = tool_runs[0] if len(tool_runs) == 1 else None
            base["evidence"] = {
                "simulations": simulations,
                "tool_runs": tool_runs,
                "sequence_disclosure": "product sequences represented by SHA-256 only in common provenance",
                "interpretation": (
                    "independent pydna restriction-digest/ligation construct simulation; it remains advisory and does not model methylation, star activity, supplier buffer compatibility or wet-lab yield"
                    if restriction_cloning else
                    "independent PCR-product simulation in the isolated scientific-tools environment; it does not simulate complete construct topology or wet-lab validation"
                ),
                "package_identity": {
                    "version": simulations[0].get("pydna_version"),
                    "record_sha256": simulations[0].get("pydna_record_sha256"),
                },
            }
        else:
            base["evidence"] = {"reason": "no independently simulatable selected product was present"}
    except Exception as error:
        base["status"] = "error"
        base["warnings"].append(f"pydna independent simulation failed without changing the primary design: {error}")
    return base
