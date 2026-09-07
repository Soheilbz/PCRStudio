"""Generation-1 qPCR-probe closure helpers.

These helpers keep optical authority, multiplex interaction diagnostics and
combined-signal reasoning separate from sequence ranking.  No universal
spectral or heterodimer rejection threshold is manufactured here.
"""

from __future__ import annotations

import json
from typing import Any

import primer3

from .thermo import reverse_complement


class ProbeClosureError(ValueError):
    pass


def _object(value: Any, *, name: str) -> dict[str, Any] | None:
    if value in (None, "", {}):
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ProbeClosureError(f"{name} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ProbeClosureError(f"{name} must be a JSON object")
    return value


def optical_authority(
    value: Any, *, panel: Any = None, reporter: str | None = None
) -> dict[str, Any]:
    payload = _object(value, name="probe_optical_authority_payload")
    if payload is None:
        return {
            "status": "unresolved-no-authority",
            "decision_impact": "validation-only",
            "note": "Instrument identity alone is not a spectral authority. Supply a versioned channel/reporter map to validate multiplex optics.",
        }
    if payload.get("schema") != "pcrstudio.qpcr-optical-profile.v1":
        raise ProbeClosureError(
            "probe optical authority requires schema pcrstudio.qpcr-optical-profile.v1"
        )
    authority_id = str(payload.get("authority_id") or "").strip()
    instrument = str(payload.get("instrument") or "").strip()
    version = str(payload.get("version") or "").strip()
    channels = payload.get("channels")
    if (
        not authority_id
        or not instrument
        or not version
        or not isinstance(channels, list)
        or not channels
    ):
        raise ProbeClosureError(
            "optical authority requires authority_id, instrument, version and non-empty channels"
        )
    allowed: dict[str, set[str]] = {}
    for row in channels:
        if not isinstance(row, dict):
            raise ProbeClosureError("each optical channel must be an object")
        name = str(row.get("channel") or "").strip()
        reporters = row.get("reporters")
        if not name or not isinstance(reporters, list) or not reporters:
            raise ProbeClosureError("each optical channel requires channel and reporters[]")
        allowed[name] = {str(x).strip() for x in reporters if str(x).strip()}
    validations: list[dict[str, Any]] = []
    if reporter:
        compatible = sorted(channel for channel, rs in allowed.items() if reporter in rs)
        validations.append(
            {
                "target": "current-assay",
                "reporter": reporter,
                "compatible_channels": compatible,
                "valid": bool(compatible),
            }
        )
        if not compatible:
            raise ProbeClosureError(
                f"reporter `{reporter}` is not present in the supplied optical authority"
            )
    seen_channels: set[str] = set()
    for raw in panel or []:
        if not isinstance(raw, dict):
            continue
        target = str(raw.get("target") or raw.get("id") or "panel-target")
        channel = str(raw.get("channel") or "").strip()
        rep = str(raw.get("reporter") or "").strip()
        valid = bool(channel and rep and channel in allowed and rep in allowed[channel])
        validations.append(
            {"target": target, "channel": channel or None, "reporter": rep or None, "valid": valid}
        )
        if channel:
            if channel in seen_channels:
                raise ProbeClosureError(
                    f"multiplex optical channel `{channel}` is assigned more than once"
                )
            seen_channels.add(channel)
        if channel and rep and not valid:
            raise ProbeClosureError(
                f"multiplex target `{target}` maps reporter `{rep}` to unsupported channel `{channel}`"
            )
    return {
        "status": "validated-authority",
        "schema": payload["schema"],
        "authority_id": authority_id,
        "instrument": instrument,
        "version": version,
        "validations": validations,
        "decision_impact": "validation-only",
        "note": "Compatibility is evaluated only against the supplied versioned optical authority; calibration/compensation is not inferred.",
    }


def multiplex_interactions(
    panel: Any,
    current: dict[str, str],
    *,
    mv_conc: float = 50.0,
    dv_conc: float = 1.5,
    dntp_conc: float = 0.6,
    dna_conc: float = 50.0,
) -> dict[str, Any] | None:
    if not panel:
        return None
    if not isinstance(panel, list):
        raise ProbeClosureError("probe_multiplex_panel must be an array")
    oligos: list[tuple[str, str]] = [
        (f"current:{role}", seq) for role, seq in current.items() if seq
    ]
    for idx, row in enumerate(panel):
        if not isinstance(row, dict):
            continue
        label = str(row.get("target") or row.get("id") or f"target-{idx + 1}")
        # Rust nested structs serialize camelCase; older Python callers may use snake_case.
        values = {
            "forward": row.get("forward_primer") or row.get("forwardPrimer"),
            "reverse": row.get("reverse_primer") or row.get("reversePrimer"),
            "probe": row.get("probe_sequence") or row.get("probeSequence"),
        }
        for role, seq in values.items():
            cleaned = "".join(str(seq or "").split()).upper().replace("U", "T")
            if cleaned:
                oligos.append((f"{label}:{role}", cleaned))
    if len(oligos) <= len(current):
        return {
            "status": "unresolved-peer-oligo-sequences-not-supplied",
            "pairs": [],
            "decision_impact": "diagnostic-only",
        }
    pairs = []
    for i, (an, a) in enumerate(oligos):
        for bn, b in oligos[i + 1 :]:
            if an.split(":", 1)[0] == bn.split(":", 1)[0]:
                continue
            try:
                dg = (
                    float(
                        primer3.calcHeterodimer(
                            a,
                            b,
                            mv_conc=mv_conc,
                            dv_conc=dv_conc,
                            dntp_conc=dntp_conc,
                            dna_conc=dna_conc,
                        ).dg
                    )
                    / 1000.0
                )
            except Exception as exc:
                pairs.append(
                    {"a": an, "b": bn, "status": "calculation-error", "detail": str(exc)[:240]}
                )
                continue
            pairs.append({"a": an, "b": bn, "heterodimer_dg_kcal_mol": round(dg, 3)})
    pairs.sort(key=lambda row: row.get("heterodimer_dg_kcal_mol", 999.0))
    return {
        "status": "calculated",
        "pairs": pairs,
        "decision_impact": "diagnostic-only",
        "threshold": "none-universal",
        "note": "All-vs-all peer interaction evidence is reported without inventing a universal rejection threshold.",
    }


def combined_signal(off_targets: dict[str, Any], probe: str, contigs: list[Any]) -> dict[str, Any]:
    """Count off-target products whose extracted sequence also contains probe or RC."""
    products = off_targets.get("products") if isinstance(off_targets, dict) else None
    if not isinstance(products, list):
        return {
            "status": "unresolved",
            "compatible_product_count": None,
            "decision_impact": "validation-only",
        }
    by_name = {str(c.name): str(c.sequence).upper() for c in contigs}
    p = probe.upper()
    rc = reverse_complement(p)
    compatible = []
    for row in products:
        if not isinstance(row, dict):
            continue
        seq = by_name.get(str(row.get("contig") or ""), "")
        try:
            start = max(0, int(row.get("start")) - 1)
            end = int(row.get("end"))
        except Exception:
            continue
        product = seq[start:end]
        if p in product or rc in product:
            compatible.append(
                {
                    "contig": row.get("contig"),
                    "start": row.get("start"),
                    "end": row.get("end"),
                    "size": row.get("size"),
                }
            )
    return {
        "status": "computed",
        "compatible_product_count": len(compatible),
        "compatible_products": compatible,
        "decision_impact": "validation-only",
        "note": "A compatible signal requires an amplifiable product and a probe site on that product; this is not a fluorescence probability model.",
    }
