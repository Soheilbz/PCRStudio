"""External MGB-aware Tm authority exchange.

PCRStudio never estimates MGB-modified probe Tm with ordinary-DNA nearest-
neighbour thermodynamics.  It exports stable candidate identities and accepts
calculated values only when the external result is cryptographically bound to
that exact candidate set and carries explicit authority provenance.
"""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from .design import clean_template
from .thermo import reverse_complement


class MgbAuthorityError(ValueError):
    pass


def _candidate_id(sequence: str, start: int, strand: str) -> str:
    payload = f"mgb-v1\0{sequence}\0{start}\0{strand}".encode("ascii")
    return "mgb-" + sha256(payload).hexdigest()[:24]


def _canonical(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: item[key] for key in ("candidate_id", "sequence", "template_start", "length", "strand")}
        for item in cands
    ]


def candidate_set_sha256(cands: list[dict[str, Any]]) -> str:
    return sha256(json.dumps(_canonical(cands), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def candidates(template: str, *, start: int, end: int, minimum: int = 13, maximum: int = 25) -> list[dict[str, Any]]:
    seq = clean_template(template).upper()
    if start < 0 or end > len(seq) or end <= start:
        raise MgbAuthorityError("MGB candidate interval is outside the amplicon/template")
    if minimum < 8 or maximum > 60 or minimum > maximum:
        raise MgbAuthorityError("MGB candidate length bounds are invalid")
    found: list[dict[str, Any]] = []
    for strand in ("forward", "reverse"):
        source = seq if strand == "forward" else reverse_complement(seq)
        interval_start, interval_end = ((start, end) if strand == "forward" else (len(seq) - end, len(seq) - start))
        for length in range(minimum, maximum + 1):
            for at in range(interval_start, interval_end - length + 1):
                oligo = source[at : at + length]
                if not oligo or oligo[0] == "G":
                    continue
                original_start = at if strand == "forward" else len(seq) - (at + length)
                found.append({
                    "candidate_id": _candidate_id(oligo, original_start, strand),
                    "sequence": oligo,
                    "template_start": original_start,
                    "length": length,
                    "strand": strand,
                })
    midpoint = (start + end) / 2.0
    found.sort(key=lambda item: (abs((item["template_start"] + item["length"] / 2) - midpoint), item["length"], item["candidate_id"]))
    return found[:96]


def exchange_manifest(cands: list[dict[str, Any]], *, authority_id: str, mode: str = "export-candidates") -> dict[str, Any]:
    canonical = _canonical(cands)
    return {
        "schema": "pcrstudio.mgb-authority-exchange.v1",
        "mode": mode,
        "authority_id": authority_id,
        "candidate_set_sha256": candidate_set_sha256(cands),
        "candidates": canonical,
        "decision_impact": "external-authority-required",
        "note": "No PCRStudio Tm is calculated for MGB-modified probes. Return candidate_id plus MGB-aware Tm from the named external authority and preserve candidate_set_sha256.",
    }


def apply_import(cands: list[dict[str, Any]], payload: Any, *, authority_id: str) -> dict[str, Any]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MgbAuthorityError(f"probe_mgb_authority_payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != "pcrstudio.mgb-authority-result.v1":
        raise MgbAuthorityError("MGB import requires schema pcrstudio.mgb-authority-result.v1")
    if str(payload.get("authority_id") or "") != authority_id:
        raise MgbAuthorityError("MGB authority_id does not match the selected reviewed MGB authority")
    expected_hash = candidate_set_sha256(cands)
    supplied_hash = str(payload.get("candidate_set_sha256") or "").strip()
    if supplied_hash != expected_hash:
        raise MgbAuthorityError("MGB candidate_set_sha256 does not match this exported candidate set")
    tool = str(payload.get("tool") or "").strip()
    version = str(payload.get("version") or "").strip()
    calculated_at = str(payload.get("calculated_at") or "").strip()
    if not tool or not version or not calculated_at:
        raise MgbAuthorityError("MGB import requires tool, version and calculated_at provenance")
    target_raw = payload.get("target_tm_c", 69.0)
    if isinstance(target_raw, bool) or not isinstance(target_raw, (int, float)) or not 30 <= float(target_raw) <= 100:
        raise MgbAuthorityError("MGB target_tm_c must be numeric between 30 and 100 C")
    target = float(target_raw)
    by_id = {item["candidate_id"]: item for item in cands}
    rows = payload.get("candidates")
    if not isinstance(rows, list) or not rows:
        raise MgbAuthorityError("MGB import contains no calculated candidates")
    scored: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise MgbAuthorityError("each MGB imported candidate must be an object")
        cid = str(row.get("candidate_id") or "")
        if cid in seen or cid not in by_id:
            raise MgbAuthorityError(f"MGB imported candidate_id `{cid}` is duplicate or not in the exported candidate set")
        seen.add(cid)
        tm = row.get("tm_c")
        if isinstance(tm, bool) or not isinstance(tm, (int, float)) or not 30 <= float(tm) <= 100:
            raise MgbAuthorityError(f"MGB candidate `{cid}` has an invalid tm_c")
        scored.append({**by_id[cid], "tm": float(tm), "tm_source": "external-mgb-authority"})
    scored.sort(key=lambda item: (abs(item["tm"] - target), item["length"], item["candidate_id"]))
    return {
        "schema": "pcrstudio.mgb-authority-resolution.v1",
        "status": "authority-values-imported",
        "authority_id": authority_id,
        "candidate_set_sha256": expected_hash,
        "tool": tool,
        "version": version,
        "calculated_at": calculated_at,
        "target_tm_c": target,
        "ranked_candidates": scored,
        "decision_impact": "mgb-tm-ranking-only",
        "note": "Ranking uses only imported MGB-aware Tm values plus stable candidate geometry; PCRStudio did not calculate MGB Tm.",
    }
