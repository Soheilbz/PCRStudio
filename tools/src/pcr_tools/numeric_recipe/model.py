"""Assay-neutral numeric-recipe value model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NumericResolution:
    """Resolved values plus source/provenance facts, independent of assay."""

    values: dict[str, float] = field(default_factory=dict)
    origins: dict[str, str] = field(default_factory=dict)
    ranges: dict[str, list[float]] = field(default_factory=dict)
    applied_overlays: list[dict[str, str]] = field(default_factory=list)
    unresolved_numeric_dependencies: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def set_value(self, key: str, value: float, origin: str) -> None:
        self.values[str(key)] = float(value)
        self.origins[str(key)] = origin

    def unset(self, key: str) -> None:
        self.values.pop(str(key), None)
        self.origins.pop(str(key), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "values": self.values,
            "origins": self.origins,
            "ranges": self.ranges,
            "applied_overlays": self.applied_overlays,
            "unresolved_numeric_dependencies": self.unresolved_numeric_dependencies,
            "warnings": self.warnings,
        }
