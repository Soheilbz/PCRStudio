"""RPA candidate-generation and source-backed empirical assay-development plan.

TwistAmp assay development is empirical: in-silico tools can prepare a candidate
pool, but cannot select/validate the final RPA assay.  This module therefore
keeps quick pair ranking diagnostic and separately exposes the manufacturer
8-10 forward by 8-10 reverse matrix that must be screened experimentally.
"""
from __future__ import annotations

from typing import Any


def _oligo_pool(ranked: list[dict[str, Any]], side: str, *, maximum: int = 10) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, entry in enumerate(ranked, start=1):
        oligo = entry.get(side)
        if not isinstance(oligo, dict):
            continue
        sequence = str(oligo.get("sequence") or "").upper()
        if not sequence or sequence in seen:
            continue
        location = entry.get(f"{side}_at") if isinstance(entry.get(f"{side}_at"), dict) else {}
        selected.append({
            "sequence": sequence,
            "source_pair_rank": rank,
            "start": int(location.get("start") or 0),
            "length": len(sequence),
        })
        seen.add(sequence)
        if len(selected) >= maximum:
            break
    return selected


def screening_cohort(
    ranked: list[dict[str, Any]],
    *,
    maximum: int = 10,
    min_coordinate_distance: int = 12,
    require_matrix_ready: bool = False,
) -> dict[str, Any]:
    if maximum < 1:
        raise ValueError("RPA screening cohort maximum must be positive")
    maximum = min(maximum, 10)
    selected: list[dict[str, Any]] = []
    seen_candidates: set[int] = set()

    def coords(entry: dict[str, Any]) -> tuple[int, int]:
        left = int(entry["left_at"]["start"])
        right = int(entry["right_at"]["start"])
        return left, right

    for rank, entry in enumerate(ranked, start=1):
        candidate = int(entry.get("candidate", rank - 1))
        if candidate in seen_candidates:
            continue
        left, right = coords(entry)
        if selected and not all(
            abs(left - int(row["left_start"])) + abs(right - int(row["right_start"])) >= min_coordinate_distance
            for row in selected
        ):
            continue
        selected.append({
            "candidate": candidate, "primary_rank": rank, "score": float(entry.get("score", 0.0)),
            "left_start": left, "right_start": right,
            "amplicon_length": len(str(entry.get("amplicon", ""))) if entry.get("amplicon") else None,
        })
        seen_candidates.add(candidate)
        if len(selected) >= maximum:
            break

    if len(selected) < min(maximum, len(ranked)):
        for rank, entry in enumerate(ranked, start=1):
            candidate = int(entry.get("candidate", rank - 1))
            if candidate in seen_candidates:
                continue
            left, right = coords(entry)
            selected.append({
                "candidate": candidate, "primary_rank": rank, "score": float(entry.get("score", 0.0)),
                "left_start": left, "right_start": right,
                "amplicon_length": len(str(entry.get("amplicon", ""))) if entry.get("amplicon") else None,
            })
            seen_candidates.add(candidate)
            if len(selected) >= maximum:
                break

    forward_candidates = _oligo_pool(ranked, "left", maximum=10)
    reverse_candidates = _oligo_pool(ranked, "right", maximum=10)
    matrix_ready = 8 <= len(forward_candidates) <= 10 and 8 <= len(reverse_candidates) <= 10
    matrix_size = len(forward_candidates) * len(reverse_candidates)
    if require_matrix_ready and not matrix_ready:
        raise ValueError(
            "Scientific-Strict RPA requires enough distinct in-silico candidates to prepare the source-backed minimum 8-forward by 8-reverse empirical screening matrix; widen the target/search window rather than treating a smaller Primer3 short-list as the RPA method."
        )
    return {
        "status": "quick-in-silico-candidate-generation-only",
        "decision_impact": "none-on-primary-ranking",
        "selection_method": "primary-rank-with-coordinate-diversity-preference-v1",
        "minimum_coordinate_distance": min_coordinate_distance,
        "recommended_characterisation_count": len(selected),
        "pairs": selected,
        "full_empirical_assay_development": {
            "authority": "TwistAmp Assay Design Manual INASDM v1.0",
            "source_url": "https://www.globalpointofcare.abbott/content/dam/ardx/globalpointofcare/lp/2025/twistdx/support/docs/manuals/INASDM%20v1.0%20TwistAmp%20DNA%20Amplification%20Kits%20-%20Assay%20Design%20Manual%20INASDM.pdf",
            "forward_candidates_recommended": [8, 10],
            "reverse_candidates_recommended": [8, 10],
            "pair_matrix_recommended": [64, 100],
            "prepared_forward_candidates": forward_candidates,
            "prepared_reverse_candidates": reverse_candidates,
            "prepared_matrix_pair_count": matrix_size,
            "matrix_ready": matrix_ready,
            "selection_basis": "empirical amplification speed/sensitivity screening",
            "sequence_prediction_equivalence": False,
            "status": "external-empirical-evidence-required" if matrix_ready else "candidate-pool-insufficient-for-source-backed-8x8-minimum",
            "note": "The manufacturer states that no automated primer-design software can reliably predict optimal RPA performance. PCRStudio prepares up to 10 unique candidates per orientation, but final assay selection requires experimental screening of the complete declared forward-by-reverse matrix.",
        },
        "claim_boundary": "PCRStudio/Primer3 supplies candidate oligos only. It does not identify a validated or optimal RPA primer pair from sequence scores and does not replace the source-backed empirical 8-10 by 8-10 screening matrix.",
    }

def screening_cohort_for_current_mode(ranked: list[dict[str, Any]], *, maximum: int = 10) -> dict[str, Any]:
    """Build the RPA screen and enforce the empirical-matrix floor only in Scientific-Strict runs."""
    from .scientific_integrity import strict
    return screening_cohort(ranked, maximum=maximum, require_matrix_ready=strict())

