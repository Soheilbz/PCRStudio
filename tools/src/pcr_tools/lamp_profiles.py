"""PrimerExplorer V5 public-rule Loop Set profile authority.

This module contains only deterministic target-composition/profile selection.
It is intentionally independent from candidate enumeration and thermodynamic
execution so exact Automatic-Judgment boundaries can be tested without
Primer3 or other native tools.
"""

from __future__ import annotations

from dataclasses import dataclass

from .degenerate import EXPANSION
from .lamp_errors import LoopSetError


@dataclass(frozen=True)
class Window:
    """Source-backed bounds for one LAMP primer-region class."""

    tm_min: float | None
    tm_max: float | None
    length_min: int
    length_max: int


@dataclass(frozen=True)
class Windows:
    """One PrimerExplorer V5 public-rule-compatible parameter set."""

    id: str
    name: str
    outer: Window
    inner: Window
    loop: Window
    gc_min: float | None
    gc_max: float | None
    why: str


# PrimerExplorer V5 normal Expert Mode (Figure 1.6): F1c/B1c 20–22 nt,
# 64–66 °C; F2/B2 and F3/B3 18–20 nt, 59–61 °C; primer GC 40–65%.
# Its separate loop-primer screen uses LF/LB 15–25 nt, 60–66 °C and 40–65% GC.
LOOP_PRIMER_WINDOW = Window(tm_min=60.0, tm_max=66.0, length_min=15, length_max=25)

NORMAL = Windows(
    id="normal",
    name="Balanced target",
    outer=Window(tm_min=59.0, tm_max=61.0, length_min=18, length_max=20),
    inner=Window(tm_min=64.0, tm_max=66.0, length_min=20, length_max=22),
    loop=LOOP_PRIMER_WINDOW,
    gc_min=40.0,
    gc_max=65.0,
    why=(
        "PrimerExplorer V5 Normal conditions: role-specific regular-primer windows "
        "plus the separate V5 loop-primer envelope."
    ),
)

AT_RICH = Windows(
    id="at-rich",
    name="AT-rich target",
    outer=Window(tm_min=55.0, tm_max=58.0, length_min=18, length_max=25),
    inner=Window(tm_min=60.0, tm_max=63.0, length_min=20, length_max=25),
    loop=LOOP_PRIMER_WINDOW,
    gc_min=None,
    gc_max=45.0,
    why=(
        "PrimerExplorer V5 AT-rich conditions selected by target composition; "
        "regular primers run longer/cooler, while loop primers use their separate "
        "loop-primer envelope."
    ),
)

# The public V5 guide gives a broad GC-rich envelope (Tm <68 °C, 15–22 nt,
# primer GC >60%) but no second role-specific lower-Tm edge in the cited
# material. Keep one-sided source bounds rather than inventing a lower edge.
GC_RICH = Windows(
    id="gc-rich",
    name="GC-rich target",
    outer=Window(tm_min=None, tm_max=68.0, length_min=15, length_max=22),
    inner=Window(tm_min=None, tm_max=68.0, length_min=15, length_max=22),
    loop=LOOP_PRIMER_WINDOW,
    gc_min=60.0,
    gc_max=None,
    why=(
        "PrimerExplorer V5 GC-rich broad envelope (shorter primers, Tm below "
        "68 °C, primer GC above 60%). Exact unpublished role-specific lower "
        "edges are not fabricated."
    ),
)

SETS = (NORMAL, AT_RICH, GC_RICH)
BY_ID = {one.id: one for one in SETS}

# Whole-target PrimerExplorer V5 Automatic Judgment boundaries.
AT_RICH_AT_OR_BELOW = 45.0
GC_RICH_AT_OR_ABOVE = 60.0

# Loop primers use their own V5 generation envelope rather than inheriting the
# regular-primer profile selected from whole-target composition.
LOOP_GC_MIN = 40.0
LOOP_GC_MAX = 65.0


def target_gc_interval(template: str) -> tuple[float, float]:
    """Return possible whole-target GC percentage under IUPAC ambiguity."""

    sequence = template.upper()
    if not sequence:
        raise LoopSetError("Automatic Judgment requires a non-empty target sequence.")
    minimum_gc = 0
    maximum_gc = 0
    for base in sequence:
        choices = EXPANSION.get(base)
        if choices is None:
            raise LoopSetError(f"Automatic Judgment cannot interpret `{base}` as a DNA/IUPAC base.")
        minimum_gc += int(all(choice in "GC" for choice in choices))
        maximum_gc += int(any(choice in "GC" for choice in choices))
    length = len(sequence)
    return (100.0 * minimum_gc / length, 100.0 * maximum_gc / length)


def windows_for(template: str, named: str | None = None) -> Windows:
    """Resolve a named set or PrimerExplorer V5 Automatic Judgment.

    Ambiguous targets are auto-classified only when every concrete sequence
    represented by the IUPAC target lies in the same documented profile.
    """

    if named:
        if named not in BY_ID:
            raise LoopSetError(
                f"`{named}` is not a parameter set this knows. It knows: "
                + ", ".join(sorted(BY_ID))
                + "."
            )
        return BY_ID[named]

    gc_min, gc_max = target_gc_interval(template)
    if gc_max <= AT_RICH_AT_OR_BELOW:
        return AT_RICH
    if gc_min >= GC_RICH_AT_OR_ABOVE:
        return GC_RICH
    if gc_min > AT_RICH_AT_OR_BELOW and gc_max < GC_RICH_AT_OR_ABOVE:
        return NORMAL
    raise LoopSetError(
        "PrimerExplorer V5 Automatic Judgment is ambiguous for this IUPAC target: "
        f"possible whole-target GC is {gc_min:.2f}–{gc_max:.2f}%, which crosses "
        "the 45%/60% parameter-set boundaries. Supply `parameter_set` explicitly "
        "instead of letting PCRStudio guess."
    )
