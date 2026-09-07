"""Bounded ABIF/AB1 Sanger trace evidence parser.

Only the small tag set required for review is decoded.  The parser is deliberately
bounded and evidence-only: chromatogram quality can validate a completed run but
never changes the primer ranking that produced it.
"""

from __future__ import annotations

import base64
import struct
from typing import Any


class SangerTraceError(ValueError):
    pass


MAX_AB1_BYTES = 4 * 1024 * 1024
MAX_AB1_LABEL = "4 MiB"
MAX_POINTS = 200_000
MAX_BASES = 50_000
MIXED_PEAK_SECONDARY_RATIO = 0.35
_DIR = struct.Struct(">4sIHHIIII")


def _decode_base64(payload: str) -> bytes:
    compact = "".join(str(payload or "").split())
    # Bound transport before allocating decoded bytes.  Base64 expands input by
    # 4/3; four extra characters allow final padding.
    max_encoded = ((MAX_AB1_BYTES + 2) // 3) * 4 + 4
    if len(compact) > max_encoded:
        raise SangerTraceError(f"AB1 base64 payload exceeds the {MAX_AB1_LABEL} limit")
    try:
        data = base64.b64decode(compact, validate=True)
    except Exception as exc:
        raise SangerTraceError("sequencing_trace_ab1_base64 is not valid base64") from exc
    if len(data) > MAX_AB1_BYTES:
        raise SangerTraceError(f"AB1 payload exceeds the {MAX_AB1_LABEL} limit")
    return data


def _entry(data: bytes, offset: int) -> tuple[str, int, int, int, int, int, int]:
    if offset < 0 or offset + _DIR.size > len(data):
        raise SangerTraceError("ABIF directory entry lies outside the file")
    raw = _DIR.unpack_from(data, offset)
    tag = raw[0].decode("ascii", errors="replace")
    return tag, raw[1], raw[2], raw[3], raw[4], raw[5], raw[6]


def _payload(data: bytes, entry: tuple[str, int, int, int, int, int, int]) -> bytes:
    _tag, _num, _etype, _esize, count, size, where = entry
    if count < 0 or size < 0 or size > MAX_AB1_BYTES:
        raise SangerTraceError("ABIF tag declares an invalid data size")
    if size <= 4:
        return struct.pack(">I", where)[:size]
    if where < 0 or where + size > len(data):
        raise SangerTraceError("ABIF tag payload lies outside the file")
    return data[where : where + size]


def _directory(data: bytes) -> dict[tuple[str, int], tuple[str, int, int, int, int, int, int]]:
    if len(data) < 34 or data[:4] != b"ABIF":
        raise SangerTraceError("trace is not an ABIF/AB1 file")
    root = _entry(data, 6)
    _tag, _num, _etype, esize, count, size, where = root
    if esize != _DIR.size or count > 10_000 or size != count * _DIR.size:
        raise SangerTraceError("ABIF root directory is malformed or unreasonably large")
    out: dict[tuple[str, int], tuple[str, int, int, int, int, int, int]] = {}
    for index in range(count):
        item = _entry(data, where + index * _DIR.size)
        out[(item[0], item[1])] = item
    return out


def _text(data: bytes, directory: dict, tag: str, number: int) -> str | None:
    item = directory.get((tag, number))
    if not item:
        return None
    raw = _payload(data, item).rstrip(b"\0")
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _u8(data: bytes, directory: dict, tag: str, number: int) -> list[int] | None:
    item = directory.get((tag, number))
    if not item:
        return None
    raw = _payload(data, item)
    return list(raw[:MAX_BASES])


def _u16(data: bytes, directory: dict, tag: str, number: int, *, limit: int) -> list[int] | None:
    item = directory.get((tag, number))
    if not item:
        return None
    raw = _payload(data, item)
    if len(raw) % 2:
        raise SangerTraceError(f"ABIF {tag}{number} has odd byte length")
    count = min(len(raw) // 2, limit)
    return list(struct.unpack(f">{count}H", raw[: count * 2]))


def _longest_q20(qualities: list[int]) -> dict[str, int] | None:
    best_start = best_end = run_start = 0
    in_run = False
    for index, q in enumerate([*qualities, 0]):
        if index < len(qualities) and q >= 20:
            if not in_run:
                run_start = index
                in_run = True
        elif in_run:
            if index - run_start > best_end - best_start:
                best_start, best_end = run_start, index
            in_run = False
    if best_end <= best_start:
        return None
    return {"start": best_start, "end": best_end, "length": best_end - best_start}


def parse_ab1_base64(payload: str, *, filename: str | None = None) -> dict[str, Any]:
    data = _decode_base64(payload)
    directory = _directory(data)
    bases = _text(data, directory, "PBAS", 2) or _text(data, directory, "PBAS", 1) or ""
    bases = bases.strip().upper()[:MAX_BASES]
    positions = (
        _u16(data, directory, "PLOC", 2, limit=MAX_BASES)
        or _u16(data, directory, "PLOC", 1, limit=MAX_BASES)
        or []
    )
    qualities = _u8(data, directory, "PCON", 2) or _u8(data, directory, "PCON", 1) or []
    order = (_text(data, directory, "FWO_", 1) or "GATC").strip().upper()
    if len(order) != 4 or set(order) != set("ACGT"):
        order = "GATC"
    traces: dict[str, list[int]] = {}
    for channel, number in zip(order, range(9, 13), strict=True):
        values = _u16(data, directory, "DATA", number, limit=MAX_POINTS)
        if values is not None:
            traces[channel] = values
    n = min(
        len(bases),
        len(positions) if positions else len(bases),
        len(qualities) if qualities else len(bases),
    )
    bases = bases[:n]
    positions = positions[:n] if positions else []
    qualities = qualities[:n] if qualities else []
    mixed: list[dict[str, Any]] = []
    if positions and traces:
        for index, (base, point) in enumerate(zip(bases, positions, strict=True)):
            if point >= MAX_POINTS:
                continue
            heights = {b: vals[point] for b, vals in traces.items() if point < len(vals)}
            if len(heights) < 2:
                continue
            ranked = sorted(heights.items(), key=lambda item: item[1], reverse=True)
            primary_base, primary = ranked[0]
            secondary_base, secondary = ranked[1]
            ratio = (secondary / primary) if primary > 0 else 0.0
            if ratio >= MIXED_PEAK_SECONDARY_RATIO:
                mixed.append(
                    {
                        "base_index": index,
                        "basecall": base,
                        "primary_channel": primary_base,
                        "secondary_channel": secondary_base,
                        "secondary_ratio": round(ratio, 4),
                    }
                )
    q20 = _longest_q20(qualities) if qualities else None
    mean_q = (sum(qualities) / len(qualities)) if qualities else None
    return {
        "schema": "pcrstudio.sanger-abif-evidence.v1",
        "status": "reviewed-abif",
        "filename": str(filename or "").strip() or None,
        "file_bytes": len(data),
        "basecalls": bases,
        "base_count": len(bases),
        "positions": positions,
        "qualities": qualities,
        "mean_phred": round(mean_q, 3) if mean_q is not None else None,
        "q20_interval": q20,
        "q20_interval_semantics": "longest-contiguous-phred-q20-or-higher-run",
        "mixed_peak_secondary_ratio_threshold": MIXED_PEAK_SECONDARY_RATIO,
        "mixed_peaks": mixed,
        "trace_order": order,
        "traces": traces,
        "decision_impact": "evidence-only",
        "note": "AB1 review is post-run evidence only; it never changes the primer ranking that produced the sequencing reaction.",
    }
