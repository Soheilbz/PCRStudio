"""Lightweight unit-bearing quantities for reaction arithmetic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Unit = Literal["mM", "uM", "uL", "U", "U/mL", "C", "min", "x", "percent", "mg/mL"]


@dataclass(frozen=True, slots=True)
class Quantity:
    """A numeric value whose unit cannot silently disappear in derivations."""

    value: float
    unit: Unit

    def require(self, unit: Unit) -> float:
        if self.unit != unit:
            raise ValueError(f"unit mismatch: expected {unit}, got {self.unit}")
        return float(self.value)


def dilution_volume(reaction_volume: Quantity, final_x: Quantity, stock_x: Quantity) -> Quantity:
    """C1V1=C2V2 for fold-concentration reagents."""
    volume = reaction_volume.require("uL")
    final = final_x.require("x")
    stock = stock_x.require("x")
    if stock <= 0:
        raise ValueError("stock concentration must be positive")
    return Quantity(volume * final / stock, "uL")
