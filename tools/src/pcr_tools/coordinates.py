"""Typed 0-based half-open coordinates used at scientific boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Strand = Literal["+", "-"]


@dataclass(frozen=True, slots=True, order=True)
class BaseIndex:
    """Zero-based base index."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("base index cannot be negative")


@dataclass(frozen=True, slots=True, order=True)
class Boundary:
    """Boundary between bases in a half-open coordinate system."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("boundary cannot be negative")


@dataclass(frozen=True, slots=True)
class HalfOpenInterval:
    """[start,end) interval; start <= end by construction."""

    start: Boundary
    end: Boundary

    def __post_init__(self) -> None:
        if self.end.value < self.start.value:
            raise ValueError("half-open interval end cannot precede start")

    @property
    def length(self) -> int:
        return self.end.value - self.start.value


@dataclass(frozen=True, slots=True)
class CircularPosition:
    """Normalized zero-based position on a circular reference."""

    value: int
    reference_length: int

    def __post_init__(self) -> None:
        if self.reference_length <= 0:
            raise ValueError("circular reference length must be positive")
        object.__setattr__(self, "value", self.value % self.reference_length)
