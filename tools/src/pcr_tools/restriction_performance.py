"""Versioned current-supplier reaction facts for the curated restriction set.

This module is intentionally dependency-light: it validates the supplier-performance
snapshot against the packaged geometry registry JSON without importing the Primer3-
dependent restriction-design engine. That keeps source qualification and registry
parity checks executable in environments without primer3-py.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from .restriction_calculators import plan_double_digest

PERFORMANCE_RESOURCE = "data/restriction_enzyme_performance_neb_2025_26.json"
GEOMETRY_RESOURCE = "data/restriction_enzyme_registry.json"


class RestrictionPerformanceError(ValueError):
    """Raised when the curated supplier-performance snapshot is incomplete or invalid."""


def _read_json(resource: str) -> dict[str, Any]:
    doc = json.loads(files("pcr_tools").joinpath(*resource.split("/")).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise RestrictionPerformanceError(f"{resource} must contain a JSON object")
    return doc


def _load() -> dict[str, Any]:
    doc = _read_json(PERFORMANCE_RESOURCE)
    geometry = _read_json(GEOMETRY_RESOURCE)
    if doc.get("schema_version") != "1.0.0" or not isinstance(doc.get("enzymes"), dict):
        raise RestrictionPerformanceError("restriction performance snapshot is malformed")
    geometry_rows = geometry.get("enzymes")
    if not isinstance(geometry_rows, list):
        raise RestrictionPerformanceError("restriction geometry registry is malformed")
    geometry_names = {
        row.get("name")
        for row in geometry_rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    if len(geometry_names) != len(geometry_rows):
        raise RestrictionPerformanceError(
            "restriction geometry registry has missing/duplicate names"
        )
    performance_names = set(doc["enzymes"])
    unknown = sorted(performance_names - geometry_names)
    missing = sorted(geometry_names - performance_names)
    if unknown or missing:
        raise RestrictionPerformanceError(
            f"restriction performance/geometry registries drifted: unknown={unknown}, missing={missing}"
        )
    for name, row in doc["enzymes"].items():
        if (
            not isinstance(row, dict)
            or not row.get("evidence_identity")
            or not isinstance(row.get("activity_percent"), dict)
        ):
            raise RestrictionPerformanceError(
                f"{name} is missing exact performance evidence identity/activity data"
            )
        temp = row.get("incubation_temperature_c")
        if not isinstance(temp, (int, float)) or isinstance(temp, bool) or temp <= 0:
            raise RestrictionPerformanceError(f"{name} has invalid incubation temperature")
        for buffer_id, activity in row["activity_percent"].items():
            if (
                not isinstance(buffer_id, str)
                or not isinstance(activity, (int, float))
                or isinstance(activity, bool)
            ):
                raise RestrictionPerformanceError(f"{name} has invalid buffer/activity data")
            if activity < 0 or activity > 100:
                raise RestrictionPerformanceError(
                    f"{name} has out-of-range activity for {buffer_id}"
                )
    return doc


PERFORMANCE_SNAPSHOT = _load()
PERFORMANCE_BY_NAME: dict[str, dict[str, Any]] = PERFORMANCE_SNAPSHOT["enzymes"]


def enzyme_performance(name: str) -> dict[str, Any]:
    try:
        return dict(PERFORMANCE_BY_NAME[name])
    except KeyError as exc:
        raise RestrictionPerformanceError(f"no current performance snapshot for {name}") from exc


def plan_neb_double_digest(
    first_name: str,
    second_name: str,
    *,
    minimum_activity_percent: float = 50.0,
) -> dict[str, Any]:
    def row(name: str) -> dict[str, Any]:
        performance = enzyme_performance(name)
        return {
            "name": f"{name} / evidence={performance['evidence_identity']}",
            "temperature_c": performance["incubation_temperature_c"],
            "buffers": performance["activity_percent"],
            "heat_inactivation": performance.get("heat_inactivation"),
        }

    answer = plan_double_digest(
        first=row(first_name),
        second=row(second_name),
        minimum_common_buffer_activity_percent=minimum_activity_percent,
    )
    answer.update(
        {
            "source_snapshot": PERFORMANCE_SNAPSHOT["snapshot_id"],
            "source_url": PERFORMANCE_SNAPSHOT["source_url"],
            "first_enzyme": first_name,
            "second_enzyme": second_name,
            "methylation_star_activity_status": (
                "not-inferred-from-this-snapshot; review exact current supplier evidence"
            ),
        }
    )
    return answer
