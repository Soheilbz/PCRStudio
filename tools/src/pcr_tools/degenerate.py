"""Primers that are deliberately several primers at once.

A degenerate primer is not one oligo. It is a mixture, synthesised by feeding
more than one base at a given cycle, and every position that varies multiplies
how many distinct molecules end up in the tube. That multiplication is the
whole difficulty and it is why this module exists as something separate:

- **Degeneracy changes effective member abundance.** Every variable position
  increases the number of concrete oligos represented by the mixture. The
  usable total degeneracy depends on synthesis/formulation, total concentration,
  target abundance and assay conditions, so the worker uses an explicit
  profile-selected budget rather than claiming a universal biological ceiling.

- **The extending end deserves a declared policy.** Terminal mismatches can be
  especially consequential, so a reviewed profile may require conserved bases
  at the 3' end. A degenerate base itself is not a mismatch: the mixture can
  contain a perfectly matched member for each represented allele. The conserved
  length is therefore a design policy, not a polymerase law.

- **Melting temperature becomes a range.** The AT-richest variant and the
  GC-richest variant of one primer can differ by many degrees, and the
  annealing temperature has to suit the whole mixture rather than its average.

The mixture cardinality, exact member thermodynamics (within the declared
computational ceiling), and supplied-panel coverage are measured explicitly.
Profile budgets and ranking weights remain declared design policies rather than
being presented as biological laws.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import product

#: What each IUPAC code stands for.
EXPANSION: dict[str, str] = {
    "A": "A",
    "C": "C",
    "G": "G",
    "T": "T",
    "R": "AG",
    "Y": "CT",
    "S": "CG",
    "W": "AT",
    "K": "GT",
    "M": "AC",
    "B": "CGT",
    "D": "AGT",
    "H": "ACT",
    "V": "ACG",
    "N": "ACGT",
}

#: The reverse: a set of bases to the code that means it.
CODE_FOR: dict[frozenset[str], str] = {frozenset(bases): code for code, bases in EXPANSION.items()}

COMPLEMENT_CODE: dict[str, str] = {
    code: CODE_FOR[frozenset({"ACGT"["TGCA".index(b)] for b in bases})]
    for code, bases in EXPANSION.items()
}

#: Profile-level starting budget for exact degenerate-primer search. Literature
#: and design tools use different user-selected maxima; 64 is not a universal
#: biological ceiling. The canonical assay profile owns the release value.
DEFAULT_MAX_DEGENERACY = 64

#: Profile-level starting policy for ambiguity at the extending end. Avoiding
#: ambiguity in the terminal three bases is established vendor guidance, but
#: the exact conserved length is method/family dependent rather than universal.
DEFAULT_CONSERVED_END = 3


def code_for(bases: set[str] | frozenset[str]) -> str:
    """The IUPAC code standing for exactly these bases."""
    return CODE_FOR.get(frozenset(bases), "N")


def degeneracy(primer: str) -> int:
    """How many distinct molecules this mixture holds."""
    total = 1
    for base in primer.upper():
        total *= len(EXPANSION.get(base, "ACGT"))
    return total


def is_degenerate(primer: str) -> bool:
    """Whether any position varies at all."""
    return any(len(EXPANSION.get(base, "ACGT")) > 1 for base in primer.upper())


def expand(primer: str, *, limit: int = 4096) -> Iterator[str]:
    """Every concrete oligo in the mixture.

    Raises:
        ValueError: when the mixture is larger than `limit`, which is the point
            at which enumerating it is the wrong thing to be doing.
    """
    size = degeneracy(primer)
    if size > limit:
        raise ValueError(f"{size}-fold degenerate is more than the {limit} this will enumerate")

    for combination in product(*(EXPANSION.get(base, "ACGT") for base in primer.upper())):
        yield "".join(combination)


def extremes(primer: str) -> tuple[str, str]:
    """The AT-richest and GC-richest members of the mixture.

    These bound the melting temperature of the whole mixture closely enough to
    be worth using when enumerating it would be wasteful. Not exactly — the
    nearest-neighbour model depends on which bases sit next to which, not only
    on how many are G or C — so where the mixture is small enough to enumerate,
    it is enumerated instead.
    """
    coolest: list[str] = []
    warmest: list[str] = []
    for base in primer.upper():
        bases = EXPANSION.get(base, "ACGT")
        coolest.append("A" if "A" in bases else "T" if "T" in bases else bases[0])
        warmest.append("G" if "G" in bases else "C" if "C" in bases else bases[0])
    return "".join(coolest), "".join(warmest)


def reverse_complement(primer: str) -> str:
    """The other strand, read 5' to 3', keeping the codes meaningful."""
    return "".join(COMPLEMENT_CODE.get(base, "N") for base in reversed(primer.upper()))


def matches(primer: str, window: str) -> bool:
    """Whether every base of a concrete window is inside the mixture."""
    if len(primer) != len(window):
        return False
    return all(
        base in EXPANSION.get(code, "")
        for code, base in zip(primer.upper(), window.upper(), strict=True)
    )


def gc_range(primer: str) -> tuple[float, float]:
    """The lowest and highest GC percentage in the mixture."""
    lowest = 0
    highest = 0
    for base in primer.upper():
        bases = EXPANSION.get(base, "ACGT")
        if all(b in "GC" for b in bases):
            lowest += 1
            highest += 1
        elif any(b in "GC" for b in bases):
            highest += 1
    length = len(primer) or 1
    return round(100.0 * lowest / length, 1), round(100.0 * highest / length, 1)


def longest_run(primer: str) -> int:
    """The longest run of one code. A run of `N` is as bad as a run of `A`."""
    best = 0
    current = 0
    previous = ""
    for base in primer.upper():
        current = current + 1 if base == previous else 1
        previous = base
        best = max(best, current)
    return best
