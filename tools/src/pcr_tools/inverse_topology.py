"""Exact full-reference topology for standard two-flank inverse PCR.

Topology resolution is deliberately separate from primer ranking.  When the
caller supplies the complete reference molecule, PCRStudio can resolve the
anchor placement, flanking restriction cuts, exact circularized fragment, and
source-coordinate segments without inventing an enzyme ranking or wet-lab
suitability claim.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from .design import clean_template
from .restriction import BY_NAME, Enzyme, sites
from .thermo import reverse_complement


class InverseTopologyError(ValueError):
    """The supplied full-reference context does not resolve one exact topology."""


def _occurrences(sequence: str, query: str) -> list[int]:
    hits: list[int] = []
    start = 0
    while True:
        at = sequence.find(query, start)
        if at < 0:
            return hits
        hits.append(at)
        start = at + 1


def _normalise_reference(reference: str, anchor: str) -> tuple[str, int, str]:
    ref = clean_template(reference).upper()
    known = clean_template(anchor).upper()
    if not ref:
        raise InverseTopologyError("inverse_reference_sequence is empty")
    if len(ref) < len(known):
        raise InverseTopologyError("inverse_reference_sequence is shorter than the known anchor")
    forward = _occurrences(ref, known)
    reverse_known = reverse_complement(known)
    reverse = [] if reverse_known == known else _occurrences(ref, reverse_known)
    total = [(at, "forward") for at in forward] + [(at, "reverse") for at in reverse]
    if not total:
        raise InverseTopologyError(
            "the known anchor does not occur exactly in inverse_reference_sequence; exact topology is not inferred from an approximate match"
        )
    if len(total) != 1:
        raise InverseTopologyError(
            f"the known anchor has {len(total)} exact placements in inverse_reference_sequence; full-reference topology is ambiguous"
        )
    at, orientation = total[0]
    if orientation == "forward":
        return ref, at, orientation
    normalized = reverse_complement(ref)
    normalized_at = len(ref) - (at + len(known))
    return normalized, normalized_at, orientation


def _distance_clockwise(start: int, end: int, length: int) -> int:
    return (end - start) % length


def _fragment_for_anchor(
    reference: str,
    *,
    anchor_start: int,
    anchor_length: int,
    enzyme: Enzyme,
    circular: bool,
) -> dict[str, Any]:
    cuts = sites(reference, enzyme, circular=circular)
    anchor_end = anchor_start + anchor_length
    internal = [cut for cut in cuts if anchor_start < cut < anchor_end]
    if internal:
        raise InverseTopologyError(
            f"{enzyme.name} cuts inside the full-reference anchor at {internal[:8]}; standard two-flank inverse PCR requires one intact anchor fragment"
        )
    if not cuts:
        raise InverseTopologyError(f"{enzyme.name} has no cut in inverse_reference_sequence")

    if circular:
        left_candidates = [cut for cut in cuts if cut <= anchor_start]
        left = max(left_candidates) if left_candidates else max(cuts)
        right_candidates = [cut for cut in cuts if cut >= anchor_end]
        right = min(right_candidates) if right_candidates else min(cuts)
        fragment_len = _distance_clockwise(left, right, len(reference))
        if fragment_len == 0:
            fragment_len = len(reference)
        offset = _distance_clockwise(left, anchor_start, len(reference))
        if offset + anchor_length > fragment_len:
            raise InverseTopologyError("selected cut pair does not contain the complete known anchor")
        if left < right:
            fragment = reference[left:right]
            segments = [{"source_start": left, "source_end": right, "length": right - left}]
        else:
            fragment = reference[left:] + reference[:right]
            segments = [
                {"source_start": left, "source_end": len(reference), "length": len(reference) - left},
                {"source_start": 0, "source_end": right, "length": right},
            ]
    else:
        left_candidates = [cut for cut in cuts if cut <= anchor_start]
        right_candidates = [cut for cut in cuts if cut >= anchor_end]
        if not left_candidates or not right_candidates:
            raise InverseTopologyError(
                f"{enzyme.name} does not provide a flanking cut on both sides of the anchor in the supplied linear reference"
            )
        left, right = max(left_candidates), min(right_candidates)
        if right <= left:
            raise InverseTopologyError("linear reference produced a non-positive restriction fragment")
        fragment = reference[left:right]
        fragment_len = len(fragment)
        offset = anchor_start - left
        segments = [{"source_start": left, "source_end": right, "length": right - left}]

    upstream = offset
    downstream = fragment_len - (offset + anchor_length)
    if upstream < 0 or downstream < 0:
        raise InverseTopologyError("full-reference restriction fragment does not contain the complete anchor")
    return {
        "enzyme": enzyme.name,
        "cut_count": len(cuts),
        "cut_positions": cuts,
        "left_flanking_cut": left,
        "right_flanking_cut": right,
        "fragment_length": fragment_len,
        "anchor_offset": offset,
        "anchor_length": anchor_length,
        "upstream_flank_length": upstream,
        "downstream_flank_length": downstream,
        "unknown_flank_total": upstream + downstream,
        "source_segments": segments,
        "origin_spanning": len(segments) > 1,
        "ligation_junction": {
            "left_source_cut": left,
            "right_source_cut": right,
            "circle_coordinate": 0,
            "status": "sequence-resolved",
        },
        "circle_sha256": sha256(fragment.encode("ascii")).hexdigest(),
        "_circle_sequence": fragment,
    }


def exact_topology(reference: str, anchor: str, enzyme_name: str, *, circular: bool = False) -> dict[str, Any]:
    if enzyme_name not in BY_NAME:
        raise InverseTopologyError(f"unknown restriction enzyme `{enzyme_name}`")
    normalized, anchor_start, submitted_orientation = _normalise_reference(reference, anchor)
    fragment = _fragment_for_anchor(
        normalized,
        anchor_start=anchor_start,
        anchor_length=len(clean_template(anchor)),
        enzyme=BY_NAME[enzyme_name],
        circular=circular,
    )
    fragment.update({
        "status": "exact",
        "reference_length": len(normalized),
        "reference_circular": bool(circular),
        "anchor_start": anchor_start,
        "anchor_end": anchor_start + len(clean_template(anchor)),
        "submitted_anchor_orientation": submitted_orientation,
        "coordinate_system": "0-based half-open on normalized known-anchor orientation",
        "decision_impact": "topology-validation",
    })
    return fragment


def public_topology(topology: dict[str, Any]) -> dict[str, Any]:
    """Return topology evidence without exposing the internal circle sequence."""
    return {key: value for key, value in topology.items() if key != "_circle_sequence"}


def screen_enzyme_cohort(reference: str, anchor: str, names: list[str], *, circular: bool = False) -> list[dict[str, Any]]:
    """Measure an explicit enzyme cohort while preserving caller order.

    No cross-enzyme biological score is manufactured: buffer compatibility,
    methylation, star activity and laboratory constraints remain independent
    evidence.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in names:
        name = str(raw).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        if name not in BY_NAME:
            out.append({"enzyme": name, "designable": False, "reason": "unknown-enzyme"})
            continue
        try:
            topology = exact_topology(reference, anchor, name, circular=circular)
            out.append({
                "enzyme": name,
                "designable": True,
                "fragment_length": topology["fragment_length"],
                "upstream_flank_length": topology["upstream_flank_length"],
                "downstream_flank_length": topology["downstream_flank_length"],
                "origin_spanning": topology["origin_spanning"],
                "reason": None,
            })
        except InverseTopologyError as exc:
            out.append({"enzyme": name, "designable": False, "reason": str(exc)})
    return out
