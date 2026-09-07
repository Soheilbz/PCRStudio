"""Assay-neutral baseline → overlay → bounded override resolver."""
from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .model import NumericResolution
from .provenance import USER_OVERRIDE_WITHIN_SOURCE_BOUND

Derivation = Callable[[NumericResolution, Mapping[str, Any]], None]


def matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def resolve(
    *,
    baseline: Mapping[str, float] | None = None,
    overlays: Iterable[Mapping[str, Any]] = (),
    ranges: Mapping[str, list[float]] | None = None,
    scenario: Mapping[str, Any] | None = None,
    overrides: Mapping[str, float] | None = None,
    derivations: Iterable[Derivation] = (),
    subject: str = "recipe",
) -> NumericResolution:
    """Apply generic numeric semantics without knowing any assay/vendor policy."""
    context = dict(scenario or {})
    resolution = NumericResolution(
        values={str(key): float(value) for key, value in dict(baseline or {}).items()},
        ranges=deepcopy(dict(ranges or {})),
    )
    resolution.origins = {key: "product-baseline" for key in resolution.values}

    for rule in overlays:
        if not matches(context, dict(rule.get("when") or {})):
            continue
        for key in rule.get("unset", []):
            resolution.unset(str(key))
        rule_id = str(rule.get("id") or "reviewed-overlay")
        for key, value in dict(rule.get("set") or {}).items():
            resolution.set_value(str(key), float(value), f"automatic:{rule_id}")
        for key, pair in dict(rule.get("ranges") or {}).items():
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f"{subject}.{key} overlay range must have exactly two endpoints")
            lo, hi = float(pair[0]), float(pair[1])
            if lo > hi:
                raise ValueError(f"{subject}.{key} overlay range is reversed")
            resolution.ranges[str(key)] = [lo, hi]
        resolution.applied_overlays.append(
            {"id": rule_id, "authority": str(rule.get("authority") or "reviewed-source")}
        )

    for key, raw in dict(overrides or {}).items():
        if key not in resolution.ranges:
            raise ValueError(f"{subject}.{key} has no reviewed optimization envelope.")
        value = float(raw)
        lo, hi = resolution.ranges[key]
        if not lo <= value <= hi:
            raise ValueError(f"{subject}.{key} is outside reviewed range {lo}–{hi}.")
        resolution.set_value(key, value, USER_OVERRIDE_WITHIN_SOURCE_BOUND)

    for derivation in derivations:
        derivation(resolution, context)
    return resolution
