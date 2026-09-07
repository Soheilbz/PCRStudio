"""Restriction-cloning coding/fusion intent validation.

This layer validates the exact final insert's coding boundaries and declared
fusion phase. It never reverse-translates tags/linkers and never substitutes
for independent final-construct sequencing/translation validation.
"""

from __future__ import annotations

from typing import Any

STOP_CODONS = {"TAA", "TAG", "TGA"}


def resolve_cloning_coding_context(
    request: dict[str, Any], *, insert_sequence: str
) -> dict[str, Any]:
    intent = str(request.get("cloning_coding_intent") or "noncoding")
    if intent not in {"noncoding", "preserve-orf", "in-frame-fusion"}:
        raise ValueError("unsupported cloning_coding_intent")
    stop_policy = str(
        request.get("cloning_stop_codon_policy")
        or ("not-applicable" if intent == "noncoding" else "preserve")
    )
    if stop_policy not in {"not-applicable", "preserve", "remove"}:
        raise ValueError("unsupported cloning_stop_codon_policy")
    fusion_tag = str(request.get("cloning_fusion_tag") or "").strip() or None
    linker_aa = str(request.get("cloning_linker_aa") or "").strip().upper() or None
    if linker_aa and any(not (c.isalpha() or c in "*-") for c in linker_aa):
        raise ValueError(
            "cloning_linker_aa must contain amino-acid letters only, with optional * or - notation"
        )

    if intent == "noncoding":
        if any(
            request.get(key) is not None
            for key in ("cloning_cds_start", "cloning_cds_end", "cloning_vector_junction_frame")
        ):
            raise ValueError("noncoding restriction cloning cannot carry CDS/frame coordinates")
        if stop_policy != "not-applicable":
            raise ValueError(
                "noncoding restriction cloning requires cloning_stop_codon_policy=not-applicable"
            )
        return {
            "intent": intent,
            "stop_codon_policy": stop_policy,
            "fusion_tag": fusion_tag,
            "linker_aa": linker_aa,
            "coding_validation_status": "not-applicable",
            "sequence_decision_impact": "none",
            "claim_boundary": "No protein-coding interpretation requested; primer ranking is unchanged.",
        }

    start = request.get("cloning_cds_start")
    end = request.get("cloning_cds_end")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
    ):
        raise ValueError(
            "coding restriction cloning requires integer cloning_cds_start/cloning_cds_end"
        )
    if not (0 <= start < end <= len(insert_sequence)):
        raise ValueError(
            f"cloning CDS interval must be within final insert 0..{len(insert_sequence)}"
        )
    cds = insert_sequence[start:end].upper()
    if len(cds) % 3:
        raise ValueError("declared cloning CDS length must be divisible by three")
    terminal_codon = cds[-3:] if len(cds) >= 3 else None
    terminal_is_stop = terminal_codon in STOP_CODONS if terminal_codon else False
    if stop_policy == "remove" and terminal_is_stop:
        raise ValueError(
            "cloning_stop_codon_policy=remove requires a final insert/CDS that does not include the terminal stop codon"
        )
    if stop_policy == "not-applicable":
        raise ValueError("coding restriction cloning requires preserve/remove stop-codon policy")

    phase = request.get("cloning_vector_junction_frame")
    phase_status = "not-requested"
    if intent == "in-frame-fusion":
        if isinstance(phase, bool) or not isinstance(phase, int) or phase not in {0, 1, 2}:
            raise ValueError("in-frame-fusion requires cloning_vector_junction_frame 0, 1 or 2")
        if (phase + start) % 3 != 0:
            raise ValueError(
                "declared insert CDS start is out of frame with the recipient-junction phase; require (junction_phase + cds_start) mod 3 = 0"
            )
        phase_status = "declared-phase-compatible-with-insert-cds-start"
    elif phase is not None:
        raise ValueError("cloning_vector_junction_frame is only valid for in-frame-fusion")

    return {
        "intent": intent,
        "cds_start": start,
        "cds_end": end,
        "cds_length_bp": len(cds),
        "terminal_codon": terminal_codon,
        "terminal_stop_present": terminal_is_stop,
        "stop_codon_policy": stop_policy,
        "vector_junction_frame": phase,
        "phase_status": phase_status,
        "fusion_tag": fusion_tag,
        "linker_aa": linker_aa,
        "coding_validation_status": "exact-final-insert-cds-boundaries-validated",
        "sequence_decision_impact": "none",
        "claim_boundary": (
            "Coding boundaries, codon divisibility and declared junction phase are checked on the exact final insert. "
            "Tag/linker labels are intent only; final vector-insert junction translation remains subject to independent construct simulation/sequencing."
        ),
    }
