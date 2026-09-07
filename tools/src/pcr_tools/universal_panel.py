"""Panel, formulation and bounded target/non-target evidence for Universal Primers.

This layer is deliberately separate from the alignment-window search. It adds
sampling-frame/QC/formulation evidence and optional target-vs-nontarget checks
without turning a supplied panel into a population claim.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from .consensus import GAPS
from .degenerate import expand, matches, reverse_complement
from .fetch import NUCLEIC_ALPHABET
from .universal import MAX_EXACT_VARIANTS

CONSENSUS_POLICIES = (
    "strict-all-members",
    "coverage-threshold",
    "majority",
    "weighted",
    "stratified",
)
FORMULATION_MODES = (
    "mixed-base-synthesis",
    "defined-oligo-pool",
    "discrete-subprimer-mixture",
    "user-defined-formulation",
)


def parse_panel_metadata(raw: Any, names: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Parse per-record metadata from JSON text/object and reject unknown records.

    The accepted shape is either ``{"records": {name: {...}}}`` or directly a
    mapping from record name to metadata. Numeric ``weight`` must be positive;
    ``stratum`` is an optional string. Nothing here interprets a user weight as
    population prevalence.
    """
    if raw in (None, "", {}):
        return {}
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"panel_metadata is not valid JSON: {exc.msg}") from exc
    elif isinstance(raw, dict):
        payload = raw
    else:
        raise ValueError("panel_metadata must be a JSON object or JSON text")
    records = payload.get("records", payload)
    if not isinstance(records, dict):
        raise ValueError("panel_metadata records must be an object keyed by FASTA record name")
    known = set(names)
    extra = sorted(set(records) - known)
    if extra:
        raise ValueError(
            "panel_metadata contains record(s) absent from the alignment: " + ", ".join(extra)
        )
    cleaned: dict[str, dict[str, Any]] = {}
    for name, value in records.items():
        if not isinstance(value, dict):
            raise ValueError(f"panel_metadata[{name!r}] must be an object")
        item = dict(value)
        if "weight" in item:
            weight = item["weight"]
            if (
                isinstance(weight, bool)
                or not isinstance(weight, (int, float))
                or float(weight) <= 0
            ):
                raise ValueError(f"panel_metadata[{name!r}].weight must be a positive number")
            item["weight"] = float(weight)
        if "stratum" in item and (
            not isinstance(item["stratum"], str) or not item["stratum"].strip()
        ):
            raise ValueError(f"panel_metadata[{name!r}].stratum must be non-empty text")
        cleaned[name] = item
    return cleaned


def panel_qc(records: list[tuple[str, str]], metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Return deterministic, descriptive panel QC without hidden exclusion rules."""
    normalized: list[tuple[str, str]] = []
    for name, sequence in records:
        row = "".join(c for c in sequence.upper() if not c.isspace()).replace("U", "T")
        normalized.append((name, row))
    seq_counts = Counter(seq for _, seq in normalized)
    duplicate_groups: dict[str, list[str]] = defaultdict(list)
    for name, seq in normalized:
        if seq_counts[seq] > 1:
            duplicate_groups[seq].append(name)
    lengths = [len(seq) for _, seq in normalized]
    per_record = []
    for name, seq in normalized:
        gaps = sum(base in GAPS for base in seq)
        ambiguities = sum(base not in "ACGT" and base not in GAPS for base in seq)
        invalid = sorted(set(seq) - NUCLEIC_ALPHABET)
        per_record.append(
            {
                "name": name,
                "length": len(seq),
                "gap_bases": gaps,
                "gap_fraction": round(gaps / max(1, len(seq)), 6),
                "ambiguous_bases": ambiguities,
                "invalid_symbols": invalid,
                "metadata_present": name in metadata,
                "stratum": metadata.get(name, {}).get("stratum"),
                "weight": metadata.get(name, {}).get("weight", 1.0),
            }
        )
    return {
        "records": per_record,
        "duplicate_sequence_groups": [
            {"records": sorted(names), "count": len(names)}
            for names in sorted(duplicate_groups.values(), key=lambda x: tuple(x))
        ],
        "length_min": min(lengths) if lengths else 0,
        "length_max": max(lengths) if lengths else 0,
        "metadata_records": sum(name in metadata for name, _ in normalized),
        "sampling_frame_claim": "descriptive-supplied-panel-only",
        "note": "No record is silently excluded by panel QC. Exact duplicates, gaps, ambiguities and metadata coverage are reported for review; population prevalence is not inferred from user weights.",
    }


def _member_list(iupac: str) -> list[str] | None:
    try:
        return list(expand(iupac.upper(), limit=MAX_EXACT_VARIANTS))
    except ValueError:
        return None


def formulation_for_pair(pair: dict[str, Any], mode: str, total_nm: float | None) -> dict[str, Any]:
    if mode not in FORMULATION_MODES:
        raise ValueError("formulation_mode must be one of: " + ", ".join(FORMULATION_MODES))
    if total_nm is not None and total_nm <= 0:
        raise ValueError("formulation_total_concentration_nm must be positive when supplied")
    primers = {}
    for role in ("left", "right"):
        site = pair[role]
        deg = int(site["degeneracy"])
        members = _member_list(site["sequence"])
        primers[role] = {
            "iupac": site["sequence"],
            "degeneracy": deg,
            "concrete_members": members
            if mode in {"defined-oligo-pool", "discrete-subprimer-mixture"}
            else None,
            "exact_members_enumerated": members is not None,
            "declared_total_concentration_nM": total_nm,
            "nominal_equal_member_concentration_nM": round(total_nm / deg, 6)
            if total_nm is not None
            else None,
        }
    return {
        "mode": mode,
        "primers": primers,
        "abundance_model": "nominal-equal-member-only-when-explicitly-calculated",
        "claim_boundary": "Mixed-base synthesis does not establish equal concrete-member abundance. Defined/discrete pools report exact members only when the degeneracy is within PCRStudio's exact enumeration guard.",
    }


def _scan_one_primer(iupac: str, sequence: str) -> list[int]:
    seq = sequence.upper().replace("U", "T")
    length = len(iupac)
    found = []
    for start in range(0, max(0, len(seq) - length + 1)):
        if matches(iupac, seq[start : start + length]):
            found.append(start)
    return found


def scan_nontarget_pair(
    pair: dict[str, Any], records: list[tuple[str, str]], product_min: int, product_max: int
) -> dict[str, Any]:
    """Exact IUPAC-compatible product scan over a finite supplied non-target panel."""
    left = pair["left"]["sequence"].upper()
    right = pair["right"]["sequence"].upper()
    reverse_binding = reverse_complement(right)
    hits = []
    for name, raw in records:
        seq = "".join(c for c in raw.upper() if not c.isspace()).replace("U", "T").replace("-", "")
        if not seq:
            continue
        left_sites = _scan_one_primer(left, seq)
        right_sites = _scan_one_primer(reverse_binding, seq)
        products = []
        for left in left_sites:
            for r in right_sites:
                size = r + len(right) - left
                if r >= left + len(left) and product_min <= size <= product_max:
                    products.append({"start": left, "end": r + len(right), "size": size})
        if products:
            hits.append({"record": name, "products": products[:20], "product_count": len(products)})
    return {
        "records_tested": len(records),
        "records_with_exact_compatible_product": len(hits),
        "hits": hits,
        "model": "exact-IUPAC finite-panel scan",
        "claim_boundary": "This is bounded specificity evidence against the supplied records only; it is not a global database search or empirical exclusivity claim.",
    }


def coverage_evidence(
    pair: dict[str, Any], names: list[str], rows: list[str], metadata: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Per-record, weighted and stratified exact coverage for one pair."""
    left = pair["left"]
    right = pair["right"]
    l0 = int(left["start"]) - 1
    r0 = int(right["start"]) - 1
    covered = []
    total_weight = 0.0
    covered_weight = 0.0
    strata = defaultdict(
        lambda: {"covered": 0, "total": 0, "covered_weight": 0.0, "total_weight": 0.0}
    )
    for name, row in zip(names, rows, strict=True):
        weight = float(metadata.get(name, {}).get("weight", 1.0))
        stratum = str(metadata.get(name, {}).get("stratum") or "unstratified")
        total_weight += weight
        strata[stratum]["total"] += 1
        strata[stratum]["total_weight"] += weight
        ok = matches(left["sequence"], row[l0 : l0 + int(left["length"])]) and matches(
            reverse_complement(right["sequence"]), row[r0 : r0 + int(right["length"])]
        )
        if ok:
            covered.append(name)
            covered_weight += weight
            strata[stratum]["covered"] += 1
            strata[stratum]["covered_weight"] += weight
    return {
        "covered_records": covered,
        "covered_count": len(covered),
        "total_records": len(names),
        "weighted_coverage": round(covered_weight / total_weight, 6) if total_weight else None,
        "strata": {
            key: {
                **value,
                "coverage": round(value["covered"] / value["total"], 6) if value["total"] else None,
                "weighted_coverage": round(value["covered_weight"] / value["total_weight"], 6)
                if value["total_weight"]
                else None,
            }
            for key, value in sorted(strata.items())
        },
        "population_inference": "not-established",
    }


def alternative_alignment_evidence(
    pair: dict[str, Any], alternative_records: list[tuple[str, str]]
) -> dict[str, Any]:
    """Measure whether the reported IUPAC pair still covers the same-name alternative MSA at the same columns.

    This deliberately does not remap gapped coordinates with an invented heuristic. Width or name mismatches
    produce an unresolved result instead of false stability.
    """
    names = [n for n, _ in alternative_records]
    rows = [
        "".join(c for c in s.upper() if not c.isspace()).replace("U", "T")
        for _, s in alternative_records
    ]
    if not rows or len({len(r) for r in rows}) != 1:
        return {
            "status": "unresolved",
            "reason": "alternative alignment rows do not share one width",
        }
    l0 = int(pair["left"]["start"]) - 1
    r0 = int(pair["right"]["start"]) - 1
    max_end = max(l0 + int(pair["left"]["length"]), r0 + int(pair["right"]["length"]))
    if max_end > len(rows[0]):
        return {
            "status": "unresolved",
            "reason": "candidate coordinates exceed alternative alignment width",
        }
    covered = []
    for name, row in zip(names, rows, strict=True):
        ok = matches(
            pair["left"]["sequence"], row[l0 : l0 + int(pair["left"]["length"])]
        ) and matches(
            reverse_complement(pair["right"]["sequence"]),
            row[r0 : r0 + int(pair["right"]["length"])],
        )
        if ok:
            covered.append(name)
    fraction = len(covered) / len(rows)
    return {
        "status": "stable-at-reported-columns" if fraction == 1.0 else "alignment-sensitive",
        "covered": len(covered),
        "of": len(rows),
        "coverage": round(fraction, 6),
        "claim_boundary": "Column-coordinate sensitivity evidence only; PCRStudio does not claim that two aligners define identical biological homology.",
    }


def split_pool_alternative(
    pair: dict[str, Any],
    names: list[str],
    rows: list[str],
) -> dict[str, Any]:
    """Return a deterministic greedy concrete-member alternative to a degenerate pool.

    This is a formulation diagnostic, not a claim of a globally minimum oligo
    set.  It only operates when every concrete member is exactly enumerable.
    Ties are broken lexicographically so the result is reproducible.
    """
    plans: dict[str, Any] = {}
    for role in ("left", "right"):
        site = pair[role]
        members = _member_list(str(site["sequence"]))
        if members is None:
            plans[role] = {
                "status": "unresolved-exact-expansion-cap",
                "selected_members": [],
                "claim_boundary": "No sampled or approximate member pool is substituted for exact enumeration.",
            }
            continue
        start = int(site["start"]) - 1
        length = int(site["length"])
        coverage_by_member: dict[str, set[str]] = {}
        for member in sorted(set(members)):
            expected = member if role == "left" else reverse_complement(member)
            coverage_by_member[member] = {
                name
                for name, row in zip(names, rows, strict=True)
                if row[start : start + length].upper().replace("U", "T") == expected
            }
        universe = set().union(*coverage_by_member.values()) if coverage_by_member else set()
        uncovered = set(universe)
        chosen: list[dict[str, Any]] = []
        while uncovered:
            ranked = sorted(
                (
                    (-len(hits & uncovered), member, hits & uncovered)
                    for member, hits in coverage_by_member.items()
                    if hits & uncovered
                ),
                key=lambda item: (item[0], item[1]),
            )
            if not ranked:
                break
            _, member, newly = ranked[0]
            chosen.append({"sequence": member, "newly_covered_records": sorted(newly)})
            uncovered -= newly
        plans[role] = {
            "status": "complete" if not uncovered else "incomplete",
            "original_degeneracy": int(site["degeneracy"]),
            "concrete_members_enumerated": len(members),
            "selected_member_count": len(chosen),
            "selected_members": chosen,
            "covered_records": sorted(universe - uncovered),
            "uncovered_records": sorted(uncovered),
        }
    return {
        "mode": "discrete-subprimer-mixture-alternative",
        "algorithm": "deterministic-greedy-set-cover",
        "primers": plans,
        "ranking_decision_impact": "none",
        "claim_boundary": (
            "Greedy set cover minimizes neither synthesis cost nor wet-lab bias and does not prove a globally minimum pool. "
            "It is an exact-members formulation alternative over the supplied alignment only."
        ),
    }


def amplicon_informativeness(
    pair: dict[str, Any],
    names: list[str],
    rows: list[str],
) -> dict[str, Any]:
    """Describe within-amplicon variation independently from primer conservation."""
    left = pair["left"]
    right = pair["right"]
    start = int(left["start"]) - 1
    end = int(right["start"]) - 1 + int(right["length"])
    if not rows or start < 0 or end <= start or end > min(len(row) for row in rows):
        return {
            "status": "unresolved",
            "reason": "reported primer coordinates do not define a common alignment interval",
        }
    entropies: list[float] = []
    variable_columns = 0
    informative_columns = 0
    for column in range(start, end):
        observed = [row[column].upper().replace("U", "T") for row in rows]
        bases = [base for base in observed if base in "ACGT"]
        if not bases:
            entropies.append(0.0)
            continue
        counts = Counter(bases)
        if len(counts) > 1:
            variable_columns += 1
        if len(counts) > 1 and len(bases) == len(observed):
            informative_columns += 1
        total = len(bases)
        entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
        entropies.append(entropy)
    amplicons = [
        row[start:end].replace("-", "").replace(".", "").upper().replace("U", "T") for row in rows
    ]
    unique = len(set(amplicons))
    return {
        "status": "descriptive-supplied-alignment",
        "alignment_start": start + 1,
        "alignment_end": end,
        "alignment_span": end - start,
        "record_count": len(names),
        "unique_ungapped_amplicons": unique,
        "variable_columns": variable_columns,
        "fully_occupied_variable_columns": informative_columns,
        "mean_shannon_entropy_bits": round(sum(entropies) / len(entropies), 6)
        if entropies
        else 0.0,
        "max_shannon_entropy_bits": round(max(entropies), 6) if entropies else 0.0,
        "ranking_decision_impact": "none",
        "claim_boundary": (
            "This describes sequence diversity inside the supplied aligned amplicon. It is not taxonomic resolution, clinical discrimination, "
            "or a guarantee that Sanger/NGS reads will distinguish every member."
        ),
    }
