"""Our designs against published ones, on the same target, measured the same way.

The question this suite exists to answer is not "did we reproduce somebody
else's primers". We almost never will, and that is not a fault: Primer3
optimises on its own penalty, many valid pairs live in the same window, and a
different answer to the same question is what a search is for.

The question is whether our answer is *defensible* beside theirs. So both are
put through the same checker under the same reaction and the same window, and
the comparison is reported criterion by criterion. Where ours is better it says
so; where it is worse it says that too, and the test fails only on the things
that decide whether a reaction works at all.

That distinction is the whole point. A benchmark that demanded identity would
fail on every correct answer. One that demanded nothing would pass on every
wrong one. What is asserted here is the middle: our pair must be a pair somebody
could defend at a bench meeting against the one in the paper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from corpus import record

from pcr_tools.design import Constraints, design
from pcr_tools.presets import polymerase
from pcr_tools.validate import run as check


@dataclass(frozen=True)
class Measured:
    """One pair, measured the way the other one was."""

    left: str
    right: str
    product: int
    #: The two melting temperatures.
    tm: tuple[float, float]
    #: How far apart they are, which decides whether one anneals when the other
    #: does.
    apart: float
    #: The two primers against each other, as a melting temperature.
    cross_dimer: float
    #: The warmest of the two hairpins, in degrees.
    #:
    #: A structure is judged by whether it survives the reaction, not by how
    #: tightly it binds at thirty-seven degrees. Comparing free energies made
    #: this benchmark fail a perfectly good pair: ours had a self-dimer at
    #: -5.94 kcal/mol against the published pair's -2.58, and both melt far
    #: below the temperature the primers anneal at, so neither exists.
    hairpin: float
    #: The warmest of the two self-dimers, likewise.
    self_dimer: float
    #: The stickier of the two 3' ends. Extension starts there, so an end that
    #: grips too well grips somewhere wrong as well.
    three_prime: float
    #: Measurements that fell outside the window both were held to.
    outside: tuple[str, ...]


def measure(template: str, left: str, right: str, window: dict[str, Any]) -> Measured:
    """Put one pair through the checker, in the window the other one used."""
    answer = check({"template": template, "left": left, "right": right, "constraints": window})
    one, other = answer["primers"]["left"], answer["primers"]["right"]
    pair = {entry["name"]: entry["value"] for entry in answer["pair"]["checks"]}

    return Measured(
        left=left,
        right=right,
        product=answer["product"]["size"],
        tm=(one["tm"], other["tm"]),
        apart=pair["Melting temperatures apart"],
        cross_dimer=pair["Cross-dimer"],
        hairpin=max(one["hairpin"]["tm"], other["hairpin"]["tm"]),
        self_dimer=max(one["self_dimer"]["tm"], other["self_dimer"]["tm"]),
        three_prime=min(one["three_prime_dg"], other["three_prime_dg"]),
        outside=tuple(
            entry["name"]
            for role in ("left", "right")
            for entry in answer["primers"][role]["checks"]
            if not entry["inside"]
        ),
    )


def report(published: Measured, ours: Measured) -> str:
    """The head-to-head, for a person reading a failure."""
    rows = [
        ("product, bp", published.product, ours.product, "either"),
        ("melting temperatures apart", published.apart, ours.apart, "lower"),
        ("cross-dimer melts at", published.cross_dimer, ours.cross_dimer, "lower"),
        ("warmest hairpin", published.hairpin, ours.hairpin, "lower"),
        ("warmest self-dimer", published.self_dimer, ours.self_dimer, "lower"),
        (
            "stickiest 3' end, kcal/mol",
            published.three_prime,
            ours.three_prime,
            "higher",
        ),
    ]
    lines = [f"{'':30} {'published':>12} {'ours':>12}  better is"]
    for name, theirs, mine, better in rows:
        lines.append(f"{name:30} {theirs:>12} {mine:>12}  {better}")
    return "\n".join(lines)


#: How far below the annealing temperature every structure must melt.
#:
#: The quantity that decides whether a structure is there when the primers try
#: to bind, rather than how tightly it binds at thirty-seven degrees. Five
#: degrees, matching the margin the search itself is now held to.
MARGIN = 5.0


def compare(
    accession: str,
    published: tuple[str, str],
    window: dict[str, Any],
    *,
    how_many: int = 5,
) -> tuple[Measured, Measured]:
    """Design against the same target and measure both the same way."""
    sequence = record(accession).sequence()
    fasta = record(accession).fasta()

    theirs = measure(fasta, published[0], published[1], window)
    found = design(
        sequence,
        constraints=Constraints(**window),
        conditions=polymerase("taq-standard").reaction.as_conditions(),
        how_many=how_many,
    )
    assert found.pairs, f"the window admits nothing on {accession}"
    ours = measure(fasta, found.pairs[0].left.sequence, found.pairs[0].right.sequence, window)
    return theirs, ours


# ── The malaria 18S nest, outer round ──────────────────────────────────────

#: The window these primers were designed in, as far as it can be reconstructed
#: from their own properties. Wide, because a window narrow enough to exclude
#: them would make the comparison meaningless.
MALARIA_WINDOW = {
    "length_min": 17,
    "length_max": 32,
    "tm_min": 45.0,
    "tm_opt": 55.0,
    "tm_max": 65.0,
    "gc_min": 20.0,
    "gc_max": 70.0,
    "product_min": 900,
    "product_max": 1300,
    "gc_clamp": 0,
}

MALARIA_OUTER = ("TTAAAATTGTTGCAGTTAAAACG", "CCTGTTGTTGCCTTAAACTTC")




def test_our_pair_is_better_than_the_published_one_at_matching_temperatures():
    """Where a search beats hand design, and by how much.

    This is what Primer3's penalty optimises hardest, and it shows: the
    published pair is 2.4 degrees apart and ours is a tenth of one. Recorded
    because a benchmark that only ever checks for regressions never notices
    what the tool is actually good at.
    """
    theirs, ours = compare("M19173.1", MALARIA_OUTER, MALARIA_WINDOW)
    assert ours.apart < theirs.apart, report(theirs, ours)


def test_no_structure_in_either_pair_survives_the_reaction():
    """The check that replaced a comparison of free energies.

    Both pairs carry hairpins and self-dimers with negative free energies. None
    of them is there when the primers anneal, and that — not how tightly they
    bind at thirty-seven degrees — is what decides whether they matter.
    """
    theirs, ours = compare("M19173.1", MALARIA_OUTER, MALARIA_WINDOW)
    detail = report(theirs, ours)

    # Roughly where these primers anneal. Anything melting below it is gone.
    annealing = min(*theirs.tm, *ours.tm) - 5.0
    for measured in (theirs, ours):
        assert measured.hairpin < annealing, detail
        assert measured.self_dimer < annealing, detail
        assert measured.cross_dimer < annealing, detail


def test_every_structure_clears_the_annealing_temperature_by_a_margin():
    """Not merely gone by then — gone with room to spare.

    This is the assertion that found something. Before the search derived its
    structure ceiling from the window rather than leaving Primer3's fixed 47
    degrees, our pair carried a hairpin melting at 45 against an annealing
    temperature of 49.6 — under the line by four degrees, which is not a margin.
    """
    theirs, ours = compare("M19173.1", MALARIA_OUTER, MALARIA_WINDOW)
    detail = report(theirs, ours)

    for measured in (theirs, ours):
        annealing = min(measured.tm) - 5.0
        assert measured.hairpin <= annealing - MARGIN, detail
        assert measured.self_dimer <= annealing - MARGIN, detail
        assert measured.cross_dimer <= annealing - MARGIN, detail


def test_the_published_pair_measures_the_same_however_it_is_reached():
    """A guard on the harness rather than on the design.

    If `measure` ever disagreed with itself, every comparison above would be
    meaningless without saying so.
    """
    first, _ = compare("M19173.1", MALARIA_OUTER, MALARIA_WINDOW)
    second = measure(record("M19173.1").fasta(), *MALARIA_OUTER, window=MALARIA_WINDOW)
    assert first == second
