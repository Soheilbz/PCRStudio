"""RPA multiplex panel evidence.

The final RPA panel is empirical. Peer sequences are retained to enable later
interaction review, but this helper never ranks peer assays or invents a
sequence-only multiplex pass/fail threshold.
"""
from __future__ import annotations
import hashlib, json
from typing import Any
from .scientific_integrity import strict

RPA_MULTIPLEX_SOFTWARE_MAX_TARGETS=5

def resolve(panel: Any, *, enabled: bool) -> dict[str,Any] | None:
    if not enabled and panel in (None, [], ''):
        return None
    if not enabled and panel not in (None, [], ''):
        raise ValueError('rpa_multiplex_panel requires rpa_multiplex=true')
    if not isinstance(panel,list) or not panel:
        if strict():
            raise ValueError('Scientific-Strict RPA multiplex requires selected peer assays plus empirical evidence references; sequence-only multiplex is not validated RPA')
        panel=[]
    if len(panel) >= RPA_MULTIPLEX_SOFTWARE_MAX_TARGETS:
        raise ValueError('RPA multiplex planning accepts at most four peer assays (five total including the current target); this is a planning bound, not wet-lab qualification')
    normalized=[]; seen=set(); missing=[]
    for index,row in enumerate(panel):
        if not isinstance(row,dict): raise ValueError('each rpa_multiplex_panel row must be an object')
        target=str(row.get('target') or '').strip()
        f=''.join(str(row.get('forward_primer') or row.get('forwardPrimer') or '').split()).upper()
        r=''.join(str(row.get('reverse_primer') or row.get('reversePrimer') or '').split()).upper()
        if not target or target in seen: raise ValueError('RPA multiplex target identities must be non-empty and unique')
        seen.add(target)
        if not f or not r or any(base not in 'ACGT' for base in f+r): raise ValueError(f'RPA peer {target} requires unambiguous selected forward/reverse primers')
        evidence=str(row.get('empirical_evidence_ref') or row.get('empiricalEvidenceRef') or '').strip()
        if not evidence: missing.append(target)
        normalized.append({'target':target,'forward_primer':f,'reverse_primer':r,'detection_identity':str(row.get('detection_identity') or row.get('detectionIdentity') or '').strip() or None,'empirical_evidence_ref':evidence or None})
    if strict() and missing:
        raise ValueError('Scientific-Strict RPA multiplex requires empirical evidence reference for every selected peer assay; missing: '+', '.join(missing))
    digest=hashlib.sha256(json.dumps(normalized,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {
      'status':'empirical-panel-context-complete' if normalized and not missing else 'development-panel-context-incomplete',
      'panel':normalized,'panel_sha256':digest,'target_count':1+len(normalized),
      'software_planning_bound':RPA_MULTIPLEX_SOFTWARE_MAX_TARGETS,'wet_lab_qualified_plex':None,
      'peer_empirical_evidence_complete':not missing,
      'selection_authority':'empirical-only; PCRStudio does not rank peer RPA assays as a multiplex panel',
      'decision_impact':'evidence-only',
    }


def extend_order_sheet(order_sheet: list[dict[str, Any]], context: dict[str, Any] | None) -> None:
    """Add empirically selected peer primers to the physical RPA panel evidence.

    This mutates only ordering/validation provenance.  It does not score or
    re-rank RPA assays from sequence.
    """
    if not context or not isinstance(order_sheet, list):
        return
    for row in order_sheet:
        if isinstance(row, dict) and row.get("kind") == "primer":
            row["tube"] = "rpa-multiplex-1"
            row["pool"] = 0
    for peer in context.get("panel") or []:
        target = str(peer.get("target") or "rpa-peer").strip() or "rpa-peer"
        for suffix, sequence in (("F", peer.get("forward_primer")), ("R", peer.get("reverse_primer"))):
            seq = str(sequence or "").upper()
            order_sheet.append({
                "name": f"{target}_{suffix}",
                "sequence": seq,
                "annealing_sequence": seq,
                "tail_sequence": "",
                "kind": "primer",
                "length": len(seq),
                "gc_percent": round(100.0 * sum(base in {"G", "C"} for base in seq) / max(len(seq), 1), 1),
                "tube": "rpa-multiplex-1",
                "pool": 0,
                "empirical_evidence_ref": peer.get("empirical_evidence_ref"),
                "note": "User-selected empirical RPA peer assay; retained for whole-panel independent interaction review and never sequence-only ranked as an RPA multiplex assay.",
            })
