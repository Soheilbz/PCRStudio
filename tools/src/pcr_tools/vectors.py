"""The primers that are already in the freezer.

Every cloning laboratory owns a handful of universal primers — the M13 pair,
the promoter primers — and screening a colony usually means using one of them
rather than ordering anything new. A tool that only ever designs fresh primers
is making people pay for oligos they already have.

Two rules govern this file, and both come from the same place: a primer library
is a list of sequences somebody will order or use without checking, so a wrong
entry is not a bug report, it is a wasted week.

The first is that no sequence here is shipped on the strength of a catalogue
number. Every one was checked against a real vector record, and where a
sequence could not be placed it is not here. The positions in the comments are
measured, not quoted.

The second is that the library never speaks about the user's own vector.
Plasmids are edited constantly and a primer that sits once in pUC19 may sit
twice, or nowhere, in the derivative on somebody's bench. So `check_against`
takes the sequence they actually have and reports where each primer really
falls in it — and the answer "not in this vector" is as useful as a position.
"""

from __future__ import annotations

from dataclasses import dataclass

from .thermo import analyse, count_overlapping, reverse_complement


@dataclass(frozen=True)
class UniversalPrimer:
    """One primer people already own."""

    name: str
    sequence: str
    #: Which way it reads, on the strand it is written for.
    reads: str
    family: str
    note: str = ""

    @property
    def length(self) -> int:
        return len(self.sequence)

    def melting_temperature(self, **conditions: float) -> float:
        return analyse(self.sequence, **conditions).tm


#: What a cloning bench already has.
#:
#: Every M13/pUC entry was found exactly once in pUC19 (L09137.2) and nowhere
#: in pBR322 (J01749.1), which is right: pBR322 carries no lac region. The
#: promoter primers are absent from both, which is also right — they belong to
#: pET, pBluescript and pGEM. Those are measurements, made against the cached
#: records in this repository, not claims taken from a catalogue.
#:
#: Where two lengths of the "same" primer are both in circulation, both are
#: here under their own lengths, because they melt several degrees apart and
#: quoting one annealing temperature for both would be wrong for one of them.
UNIVERSAL: tuple[UniversalPrimer, ...] = (
    # The M13/pUC family. Positions given are where each was found in pUC19.
    UniversalPrimer(
        "M13 Forward (-40), 17-mer",
        "GTTTTCCCAGTCACGAC",
        "forward",
        "M13/pUC",
        "Found at 358 in pUC19. Melts near 53, which is cool for a modern "
        "reaction: the partner primer has to be designed down to it.",
    ),
    UniversalPrimer(
        "M13 Forward (-47), 24-mer",
        "CGCCAGGGTTTTCCCAGTCACGAC",
        "forward",
        "M13/pUC",
        "Found at 351 in pUC19. The warmest of the M13 forwards at about 68, "
        "which makes it the easiest to pair with an ordinary insert primer.",
    ),
    UniversalPrimer(
        "M13 Forward (-20), 16-mer",
        "GTAAAACGACGGCCAG",
        "forward",
        "M13/pUC",
        "Found at 378 in pUC19.",
    ),
    UniversalPrimer(
        "M13 Forward (-20), 17-mer",
        "GTAAAACGACGGCCAGT",
        "forward",
        "M13/pUC",
        "Found at 378 in pUC19. The one most people mean by 'M13 forward'.",
    ),
    UniversalPrimer(
        "M13 Forward (-21), 18-mer",
        "TGTAAAACGACGGCCAGT",
        "forward",
        "M13/pUC",
        "Found at 377 in pUC19.",
    ),
    UniversalPrimer(
        "M13/pUC Forward, 23-mer",
        "CCCAGTCACGACGTTGTAAAACG",
        "forward",
        "M13/pUC",
        "Found at 363 in pUC19.",
    ),
    UniversalPrimer(
        "M13 Reverse, 17-mer",
        "CAGGAAACAGCTATGAC",
        "reverse",
        "M13/pUC",
        "Its site is at 464 in pUC19. Melts near 49, the coolest here.",
    ),
    UniversalPrimer(
        "M13 Reverse, 22-mer",
        "TCACACAGGAAACAGCTATGAC",
        "reverse",
        "M13/pUC",
        "Its site is at 464 in pUC19.",
    ),
    UniversalPrimer(
        "M13 Reverse (-48), 24-mer",
        "AGCGGATAACAATTTCACACAGGA",
        "reverse",
        "M13/pUC",
        "Its site is at 476 in pUC19.",
    ),
    UniversalPrimer(
        "M13/pUC Reverse, 23-mer",
        "AGCGGATAACAATTTCACACAGG",
        "reverse",
        "M13/pUC",
        "Its site is at 477 in pUC19.",
    ),
    # Promoter primers. Absent from pUC19 and pBR322, which is why the library
    # checks against whatever vector the user has rather than assuming.
    UniversalPrimer(
        "T7 promoter",
        "TAATACGACTCACTATAGGG",
        "forward",
        "promoter",
        "For pET and other T7 vectors. Not present in pUC19 or pBR322.",
    ),
    UniversalPrimer(
        "T7 terminator",
        "GCTAGTTATTGCTCAGCGG",
        "reverse",
        "promoter",
        "The other end of a pET insert.",
    ),
    UniversalPrimer(
        "T3 promoter",
        "ATTAACCCTCACTAAAGGGA",
        "forward",
        "promoter",
        "For pBluescript and its relatives.",
    ),
    UniversalPrimer(
        "SP6 promoter, 19-mer",
        "TATTTAGGTGACACTATAG",
        "forward",
        "promoter",
        "For pGEM and relatives. Melts near 45, which is very cool: an "
        "ordinary partner primer will not anneal with it.",
    ),
    UniversalPrimer(
        "SP6 promoter, 18-mer",
        "ATTTAGGTGACACTATAG",
        "forward",
        "promoter",
        "The shorter variant, one base cooler still.",
    ),
)

BY_NAME = {primer.name: primer for primer in UNIVERSAL}


@dataclass(frozen=True)
class Placement:
    """Where one universal primer actually falls in one vector."""

    name: str
    sequence: str
    reads: str
    family: str
    #: How many places it could sit, counting both strands.
    occurrences: int
    #: Where, when there is exactly one. Zero-based, on the plus strand.
    at: int | None
    tm: float
    usable: bool
    why: str
    note: str = ""


def check_against(
    vector: str,
    *,
    primers: tuple[UniversalPrimer, ...] = UNIVERSAL,
    **conditions: float,
) -> list[Placement]:
    """Where each universal primer really sits in the vector somebody has.

    Never assume. Plasmids are edited constantly, and a primer that sits once
    in the published pUC19 may sit twice, or nowhere, in the derivative on
    somebody's bench — and a screen designed against the wrong assumption gives
    a band nobody can interpret.

    Returns:
        Every primer, usable ones first, each with where it was found and why
        it can or cannot be used here.
    """
    sequence = "".join(base for base in vector.upper() if base.isalpha())
    found: list[Placement] = []

    for primer in primers:
        forward = count_overlapping(sequence, primer.sequence)
        reverse = count_overlapping(sequence, reverse_complement(primer.sequence))
        total = forward + reverse

        if total == 1:
            at = (
                sequence.find(primer.sequence)
                if forward
                else sequence.find(reverse_complement(primer.sequence))
            )
            usable, why = True, "sits in exactly one place in this vector"
        elif total == 0:
            at, usable = None, False
            why = "is not in this vector at all"
        else:
            at, usable = None, False
            why = (
                f"sits in {total} places in this vector, so a product using it "
                "would not tell you which one it came from"
            )

        found.append(
            Placement(
                name=primer.name,
                sequence=primer.sequence,
                reads=primer.reads,
                family=primer.family,
                occurrences=total,
                at=at,
                tm=primer.melting_temperature(**conditions),
                usable=usable,
                why=why,
                note=primer.note,
            )
        )

    found.sort(key=lambda place: (not place.usable, place.name))
    return found


#: How far either side of a fixed primer's melting temperature its partner may
#: sit.
#:
#: The pair still has to anneal together, so what matters is that the two are
#: close — and with one of them fixed, "close" is a window around it rather
#: than the engine's own. Three degrees, which is the pair tolerance the engine
#: already applies, so this is that rule restated for the case where one side
#: cannot move.
PARTNER_TOLERANCE = 3.0


def partner_window(primer: UniversalPrimer, **conditions: float) -> dict[str, float]:
    """The melting-temperature window a partner for this primer has to fit.

    The engine's default window is 57 to 63, and several of these primers melt
    below all of it — the 17-mer M13 reverse is near 49. Designing a partner in
    the default window and annealing the pair at the cooler one's temperature
    means the warm primer binds everywhere; annealing at the warm one's means
    the cool primer does not bind at all. Neither is a reaction.

    So a fixed primer moves the window rather than being refused by it.
    """
    tm = primer.melting_temperature(**conditions)
    return {
        "tm_min": round(tm - PARTNER_TOLERANCE, 1),
        "tm_opt": round(tm, 1),
        "tm_max": round(tm + PARTNER_TOLERANCE, 1),
    }


def placement_to_dict(place: Placement) -> dict[str, object]:
    """One placement as plain data."""
    return {
        "name": place.name,
        "sequence": place.sequence,
        "reads": place.reads,
        "family": place.family,
        "occurrences": place.occurrences,
        "at": place.at,
        "tm": place.tm,
        "usable": place.usable,
        "why": place.why,
        "note": place.note,
    }
