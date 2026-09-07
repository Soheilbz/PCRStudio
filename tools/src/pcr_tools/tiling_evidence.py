"""Post-design tiling evidence and scheme-lifecycle helpers."""

from __future__ import annotations

import re
from statistics import mean
from typing import Any


class TilingEvidenceError(ValueError):
    pass


SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_depth_tsv(raw: str, *, dropout_threshold: float) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        raise TilingEvidenceError("tilingDepthTsv is empty")
    if not 0 <= float(dropout_threshold) <= 1_000_000_000:
        raise TilingEvidenceError("tilingDropoutThreshold must be a non-negative finite depth")
    lines = [
        line for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(lines) > 20_000:
        raise TilingEvidenceError("tilingDepthTsv is limited to 20,000 non-comment rows")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        parts = line.replace(",", "\t").split()
        if len(parts) < 2:
            raise TilingEvidenceError(
                f"tilingDepthTsv row {index} needs amplicon/name and numeric depth"
            )
        name, depth_raw = parts[0], parts[-1]
        if index == 1 and depth_raw.lower() in {"depth", "mean_depth", "coverage"}:
            continue
        try:
            depth = float(depth_raw)
        except ValueError as exc:
            raise TilingEvidenceError(f"tilingDepthTsv row {index} has non-numeric depth") from exc
        if depth < 0 or depth != depth or depth == float("inf"):
            raise TilingEvidenceError(f"tilingDepthTsv row {index} has invalid depth")
        rows.append({"amplicon": name, "depth": depth, "dropout": depth < float(dropout_threshold)})
    if not rows:
        raise TilingEvidenceError("tilingDepthTsv contains no measured rows")
    dropouts = [row for row in rows if row["dropout"]]
    return {
        "schema": "pcrstudio.tiling-depth-evidence.v1",
        "status": "observed-depth-imported",
        "dropout_threshold": float(dropout_threshold),
        "rows": rows,
        "summary": {
            "amplicons": len(rows),
            "mean_depth": mean(row["depth"] for row in rows),
            "minimum_depth": min(row["depth"] for row in rows),
            "dropout_count": len(dropouts),
        },
        "dropouts": dropouts,
        "decision_impact": "evidence-only",
        "note": "Observed depth identifies candidates for review/repair but does not retrospectively alter the saved design ranking.",
    }


def _bed_names(raw: str) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for line in str(raw or "").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        out[parts[3]] = tuple(parts)
    return out


def scheme_diff(existing_bed: str, new_bed: str) -> dict[str, Any] | None:
    old = _bed_names(existing_bed)
    new = _bed_names(new_bed)
    if not old or not new:
        return None
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(name for name in set(old) & set(new) if old[name] != new[name])
    return {
        "schema": "pcrstudio.scheme-diff.v1",
        "status": "compared",
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged_count": len(set(old) & set(new)) - len(changed),
        "decision_impact": "lifecycle-provenance",
    }


def version_transition(version: str | None, diff: dict[str, Any] | None) -> dict[str, Any] | None:
    if not version or diff is None:
        return None
    match = SEMVER.match(str(version).strip())
    if not match:
        raise TilingEvidenceError("schemeVersion must be semantic version MAJOR.MINOR.PATCH")
    major, minor, patch = map(int, match.groups())
    changed = bool(diff.get("added") or diff.get("removed") or diff.get("changed"))
    recommended = f"{major}.{minor + 1}.0" if changed else f"{major}.{minor}.{patch + 1}"
    return {
        "current": f"{major}.{minor}.{patch}",
        "recommended": recommended,
        "reason": "primer-set-change" if changed else "metadata/evidence-only-change",
        "auto_publish": False,
        "note": "Version transition is a recommendation; publication remains an explicit user action.",
    }


def repair_handoff(
    depth: dict[str, Any] | None, *, operation: str, existing_bed: str | None
) -> dict[str, Any] | None:
    if not depth or not depth.get("dropouts"):
        return None
    return {
        "schema": "pcrstudio.tiling-repair-handoff.v1",
        "status": "repair-review-available" if existing_bed else "existing-bed-required-for-repair",
        "source_operation": operation,
        "dropout_amplicons": [row["amplicon"] for row in depth["dropouts"]],
        "recommended_operation": "repair-mode",
        "decision_impact": "route-only",
        "causal_claim": "none",
        "note": "Observed dropout nominates amplicons for repair review; it does not prove a primer, variant, or interaction caused the dropout.",
    }
