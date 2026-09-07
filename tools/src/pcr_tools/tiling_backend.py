"""Explicit tiled-scheme backend dispatcher.

No backend substitution is silent. ``compare`` runs both independent engines
and retains PrimalScheme3 as the orderable primary view while attaching a
separate Olivar comparison; scores and primer choices are never averaged.
"""

from __future__ import annotations

from typing import Any

from .olivar_adapter import run as run_olivar
from .primalscheme_adapter import PrimalSchemeImportError
from .primalscheme_adapter import run as run_primalscheme
from .tiling_evidence import (
    TilingEvidenceError,
    parse_depth_tsv,
    repair_handoff,
    scheme_diff,
    version_transition,
)
from .tool_runtime import tool_status


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "backend": result.get("primary_backend"),
        "coverage": result.get("coverage"),
        "tile_count": len(result.get("tiles") or []),
        "pool_count": len(result.get("pools") or {}),
        "gap_count": len(result.get("gaps") or []),
        "variant_risk": result.get("variant_risk"),
        "orderability": result.get("orderability"),
        "order_sheet": result.get("order_sheet") or [],
    }


def _finish(request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    result["managed_tools"] = {
        tool: tool_status(tool)
        for tool in ("primalscheme3", "olivar", "mafft", "primerpooler", "ncbi_blast_plus")
    }
    evidence = None
    if request.get("tilingDepthTsv") not in (None, ""):
        try:
            evidence = parse_depth_tsv(
                str(request.get("tilingDepthTsv")),
                threshold=float(
                    request.get("tilingDropoutThreshold")
                    if request.get("tilingDropoutThreshold") is not None
                    else 20.0
                ),
            )
        except (TilingEvidenceError, TypeError, ValueError) as exc:
            raise PrimalSchemeImportError(str(exc)) from exc
        result["observed_depth_evidence"] = evidence
        result["dropout_repair_handoff"] = repair_handoff(
            evidence,
            existing_bed=str(
                request.get("existingBed")
                or ((result.get("scheme_artifacts") or {}).get("primer_bed") or {}).get("content")
                or ""
            ),
        )
    old_bed = str(request.get("existingBed") or "")
    new_bed = str(
        ((result.get("scheme_artifacts") or {}).get("primer_bed") or {}).get("content") or ""
    )
    if old_bed and new_bed:
        diff = scheme_diff(old_bed, new_bed)
        result["scheme_version_diff"] = diff
        result["version_transition"] = version_transition(
            str(request.get("schemeVersion") or "v0.0.0"), diff
        )
    return result


def run(request: dict[str, Any]) -> dict[str, Any]:
    backend = str(request.get("tilingBackend") or "primalscheme3").strip().lower()
    if backend == "primalscheme3":
        return _finish(request, run_primalscheme(request))
    if backend == "olivar":
        return _finish(request, run_olivar(request))
    if backend == "compare":
        if str(request.get("tilingOperation") or "") != "scheme-create":
            raise PrimalSchemeImportError(
                "tilingBackend=compare is qualified for scheme-create only; lifecycle repair/replace remains PrimalScheme3-specific."
            )
        primal_request = dict(request)
        primal_request["tilingBackend"] = "primalscheme3"
        olivar_request = dict(request)
        olivar_request["tilingBackend"] = "olivar"
        primary = run_primalscheme(primal_request)
        secondary = run_olivar(olivar_request)
        primary["backend_comparison"] = {
            "mode": "side-by-side-no-score-blending",
            "primary": _summary(primary),
            "secondary": _summary(secondary),
            "interpretation": (
                "PrimalScheme3 and Olivar are independent design engines. PCRStudio does not average their scores, pools, risk values, or primer sequences; disagreement is design-sensitivity evidence for review."
            ),
        }
        primary["primary_backend"]["comparison_backend"] = "olivar-1.3.3"
        return _finish(request, primary)
    if backend == "internal-development":
        raise PrimalSchemeImportError(
            "internal-development is not a Scientific-Strict primary backend. Select primalscheme3, olivar, or compare."
        )
    raise PrimalSchemeImportError(
        f"unknown tilingBackend {backend!r}; use primalscheme3, olivar, or compare"
    )
