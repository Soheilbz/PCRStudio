"""A 5' addition that belongs to a downstream step rather than to the template.

Two assays here produce primers that almost never go into a tube as designed. A
tiling scheme is pooled and sequenced, so every oligo carries the platform's
adapter; a degenerate pair is usually read by Sanger off a universal primer, so
every oligo carries M13. In both cases the tail is fixed by whatever comes
after the PCR, and the design has nothing to say about what it should be.

So this does not hold a catalogue. It takes what somebody gives it, checks the
two things that are checkable, and is careful about which melting temperature
it quotes — because a tail is not on the template in the first round, and a
temperature computed over the whole molecule is not the primer-template
screening value. Neither value by itself is a bench cycling authority.
"""

from __future__ import annotations

from typing import Any

from .thermo import analyse

#: Longest tail this will attach.
#:
#: Comfortably past any adapter in ordinary use — the longest Illumina overhang
#: is 34 bases — while still refusing a whole sequence pasted into the box by
#: mistake, which is the failure that would otherwise be discovered on an
#: invoice.
LONGEST = 80


class TailError(ValueError):
    """A tail that could not be attached."""


def clean(text: str | None) -> str:
    """One tail, upper-cased, or empty.

    Raises:
        TailError: for anything that is not plain unambiguous DNA, or is longer
            than an adapter could reasonably be.
    """
    if not text:
        return ""
    tail = "".join(text.split()).upper()
    strange = sorted({base for base in tail if base not in "ACGT"})
    if strange:
        raise TailError(
            "A 5' tail has to be plain A, C, G and T. This one contains "
            + ", ".join(strange)
            + ". A degenerate base in a tail is a pool of different adapters, "
            "which is not what an adapter is for."
        )
    if len(tail) > LONGEST:
        raise TailError(
            f"That tail is {len(tail)} bases and this attaches up to {LONGEST}. "
            "The longest adapter in ordinary use is 34; anything much past that "
            "is usually a sequence pasted into the wrong box."
        )
    return tail


def describe(tail: str, annealing: str, role: str, **conditions: float) -> dict[str, Any]:
    """What was added to one primer, and whose temperature is being quoted."""
    whole = analyse(tail + annealing, **conditions)
    part = analyse(annealing, **conditions)
    return {
        "role": role,
        "tail": tail,
        "length": len(tail),
        "annealing": annealing,
        "annealing_tm": round(part.tm, 1),
        "whole_tm": round(whole.tm, 1),
        "note": (
            f"{len(tail)} bases in front, which are not on the template. The "
            f"first-round primer-template segment is {len(annealing)} bases with a "
            f"screening Tm of {round(part.tm, 1)} °C. Do not infer a bench block "
            f"temperature from that value without the named amplification protocol. "
            f"The whole molecule melts at {round(whole.tm, 1)} °C, which is what "
            f"it does from the second round on, once the tail has a copy of "
            f"itself to bind."
        ),
    }
