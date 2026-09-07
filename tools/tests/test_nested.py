"""Nested PCR: the one relationship that defines the assay, and the rest.

Almost everything about nested PCR is a preference. One thing is not:

    forward outer  <  forward inner  <  reverse inner  <  reverse outer

A design that breaks that ordering is not a nested design, whatever it is
called, and a second round whose primers are not inside the first product does
not do the thing nested PCR exists to do. So most of what is checked here is
that ordering, from several directions, on a real genomic sequence with real
introns rather than on random bases that would let any arrangement look fine.

The rest is about what happens when it cannot be satisfied, which is the common
case in practice and the one a tool is judged on.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.design import Constraints
from pcr_tools.nested import (
    NestedError,
    Nesting,
    design_nested,
    nest_to_dict,
)
from pcr_tools.presets import polymerase
from pcr_tools.thermo import reverse_complement

REACTION = polymerase("taq-standard").reaction

#: Genomic TP53 rather than the transcript: introns, real exon boundaries, and
#: room for two pairs, which is what a nested design needs.
TEMPLATE = record("NG_017013.2").sequence()[:8000]

OUTER = Constraints(product_min=800, product_max=1500)
INNER = Constraints(product_min=300, product_max=700)


def nested(**overrides):
    request = {
        "outer": OUTER,
        "inner": INNER,
        "target_start": 4000,
        "target_length": 100,
        "conditions": REACTION.as_conditions(),
        "how_many": 3,
    }
    request.update(overrides)
    return design_nested(TEMPLATE, **request)


# ── The ordering ───────────────────────────────────────────────────────────


def test_a_real_template_gives_designs_whose_ordering_holds():
    result = nested()
    assert result.nests, "genomic TP53 has room for a nested design"
    for nest in result.nests:
        assert nest.ordering_holds()


def test_the_inner_primers_do_not_overlap_the_outer_ones():
    """Overlapping is not nesting.

    An inner primer sitting on top of an outer one would be amplified by the
    first round as part of its own primer site, so the second round would add
    no specificity at all -- which is the only reason to run it.
    """
    for nest in nested().nests:
        outer_left_ends = nest.outer.left_at.start + nest.outer.left_at.length
        inner_right_ends = nest.inner.right_at.start + nest.inner.right_at.length
        assert nest.inner.left_at.start >= outer_left_ends
        assert inner_right_ends <= nest.outer.right_at.start


def test_both_rounds_contain_the_target():
    """The outer round contains it because the inner one does, necessarily."""
    for nest in nested().nests:
        for pair in (nest.outer, nest.inner):
            starts = pair.left_at.start
            ends = pair.right_at.start + pair.right_at.length
            assert starts <= 4000 and 4100 <= ends


def test_the_inner_product_is_shorter_than_the_outer_one():
    for nest in nested().nests:
        assert nest.inner.product_size < nest.outer.product_size


def test_how_far_the_second_round_moved_in_is_reported_at_both_ends():
    """The number somebody asks when deciding whether a design is really nested.

    Two pairs that merely overlap are not a nested design, and the distance
    each end moved inward is how you tell at a glance.
    """
    for nest in nested().nests:
        moved = nest_to_dict(nest)["moved_in"]
        assert moved["left"] > 0 and moved["right"] > 0


# ── Semi-nested ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("shares", ["forward", "reverse"])
def test_a_semi_nested_design_really_reuses_that_primer(shares: str):
    """Common where one flank is short and only one end can move inward."""
    result = nested(nesting=Nesting(shares=shares), how_many=2)
    assert result.nests, f"no semi-nested design sharing the {shares} primer"

    for nest in result.nests:
        if shares == "forward":
            assert nest.outer.left.sequence == nest.inner.left.sequence
            assert nest.outer.right.sequence != nest.inner.right.sequence
        else:
            assert nest.outer.right.sequence == nest.inner.right.sequence
            assert nest.outer.left.sequence != nest.inner.left.sequence
        assert nest.ordering_holds()


def test_a_fully_nested_design_shares_neither_primer():
    for nest in nested().nests:
        assert nest.outer.left.sequence != nest.inner.left.sequence
        assert nest.outer.right.sequence != nest.inner.right.sequence


# ── A margin, when somebody asks for one ───────────────────────────────────


def test_a_margin_pushes_the_inner_primers_further_in():
    """There is no published number for this, so there is no default above zero.

    It is exposed because people ask for it, and whoever sets one owns the
    reason. What the code owes them is that the number does what it says.
    """
    close = nested(nesting=Nesting(margin=0), how_many=1)
    far = nested(nesting=Nesting(margin=150), how_many=1)
    assert close.nests and far.nests

    for nest in far.nests:
        gap = nest.inner.left_at.start - (nest.outer.left_at.start + nest.outer.left_at.length)
        assert gap >= 150


# ── What happens when it cannot be done ────────────────────────────────────


def test_an_outer_pair_with_no_room_inside_is_counted_and_explained():
    """The half of the answer that sends somebody somewhere useful.

    "No nested design exists" and "each outer pair we tried was about eighty
    bases too short" are different problems with different fixes, and a tool
    that reports the first when it means the second wastes an afternoon.
    """
    result = design_nested(
        TEMPLATE,
        outer=Constraints(product_min=400, product_max=600),
        # More inner product than the outer pair can possibly hold. The
        # impossibility is arithmetic -- an inner product of 600 cannot sit
        # strictly inside an outer one capped at 600 -- rather than a fact
        # about which outer pairs the search happens to return, which moved
        # when the salt-correction model did (design.py).
        inner=Constraints(product_min=600, product_max=600),
        conditions=REACTION.as_conditions(),
        how_many=3,
    )
    assert result.nests == []
    assert result.rejected, "something must say why"
    assert result.outer_considered > 0

    reasons = {entry["reason"] for entry in result.rejected}
    assert "no room for an inner product" in reasons
    detail = next(
        entry["detail"]
        for entry in result.rejected
        if entry["reason"] == "no room for an inner product"
    )
    assert "600" in detail, "the message names the number that did not fit"


def test_it_does_not_give_up_on_the_first_outer_pair():
    """Primer3's best outer pair can be the one with no room inside it.

    Taking it and stopping would report that no nested design exists when
    several do, which is the failure this walk down the candidates prevents.
    """
    result = nested(how_many=3)
    # Either several were found, or the ones that failed were each accounted
    # for -- both are honest; silently trying one is not.
    assert len(result.nests) + len(result.rejected) > 1


# ── Nestings that could not exist ──────────────────────────────────────────


def test_sharing_something_that_is_not_a_primer_is_refused():
    with pytest.raises(NestedError, match="reuses"):
        Nesting(shares="middle").check()


def test_a_negative_margin_is_refused_as_the_opposite_of_nesting():
    with pytest.raises(NestedError, match="opposite of nesting"):
        Nesting(margin=-10).check()


# ── Supported two-tube topology ────────────────────────────────────────────


def test_two_tube_nesting_is_the_current_topology():
    Nesting(single_tube=False).check()


def test_a_delivered_nest_whose_outer_round_is_cooler_carries_a_note():
    """The inverted case, end to end: designed, and said on the design.

    A cool outer window with a hot inner window used to be refused pair by
    pair; every outer candidate came back "the outer pair does not anneal
    hotter than the inner" and no nest existed at all. Each of those pairs was
    buildable -- the assay works in two tubes -- so now they are delivered,
    each carrying the note that says what practice would have preferred.
    """
    result = nested(
        nesting=Nesting(),
        outer=Constraints(product_min=800, product_max=1500, tm_min=50.0, tm_opt=53.0, tm_max=56.0),
        inner=Constraints(product_min=300, product_max=700, tm_min=58.0, tm_opt=60.0, tm_max=63.0),
        how_many=2,
    )
    assert result.nests, (
        f"a cool outer round and a hot inner round must still give designs; "
        f"got {len(result.rejected)} refusals"
    )
    for entry in result.rejected:
        assert entry["reason"] != "the outer pair does not anneal hotter than the inner"
    for nest in result.nests:
        outer_cooler = min(nest.outer.left.tm, nest.outer.right.tm)
        inner_warmer = max(nest.inner.left.tm, nest.inner.right.tm)
        assert outer_cooler < inner_warmer, "these windows should deliver inverted pairs"
        assert nest.tm_note, "an inverted nest without its note hides the one thing worth knowing"
        reported = nest_to_dict(nest)["tm_note"]
        assert "independent annealing temperatures" in reported


def test_every_delivered_nest_keeps_the_hierarchy_or_says_otherwise():
    """Each nest either matches two-step practice or carries the reason not to.

    Two-step practice prefers an outer pair hotter than the inner one. Two
    tubes do not require it -- each round anneals at its own step -- so a
    delivered pair that came out cooler outside than in is recorded on the
    design rather than thrown away. What may never happen is an inverted pair
    shipped in silence.
    """
    for nest in nested().nests:
        outer_cooler = min(nest.outer.left.tm, nest.outer.right.tm)
        inner_warmer = max(nest.inner.left.tm, nest.inner.right.tm)
        if outer_cooler >= inner_warmer:
            assert nest.tm_note is None, "a note on a nest that needs no caveat"
        else:
            assert nest.tm_note, (
                f"outer melts down to {outer_cooler:.1f} but the inner round "
                f"reaches {inner_warmer:.1f}, and nothing says so"
            )


def test_an_outer_round_that_melts_below_the_inner_is_described_not_scored():
    """`cooler_outer_note` names both numbers and what they cost."""
    from pcr_tools.nested import cooler_outer_note

    hot = _a_round("GCTAGCATCGACGTACGGATCG", "CATTTCTGGAATTGCGCGCC")
    cool = _a_round("ACATCGCATTTGAAACCCAG", "TACTGCCCTCTCTGTTTCTC")

    # Practice's arrangement draws no comment.
    assert cooler_outer_note(hot, cool) is None

    message = cooler_outer_note(cool, hot)
    assert message is not None
    assert "outer" in message and "inner" in message
    assert "independent annealing temperatures" in message
    assert any(character.isdigit() for character in message)


# ── The outer product as a background for the inner round ──────────────────


def _a_round(left_sequence: str, right_sequence: str):
    """A measured CandidatePair from two fixed sequences, for check tests."""
    from pcr_tools.design import CandidatePair, Placement
    from pcr_tools.thermo import DEFAULT_CONDITIONS, analyse

    left = analyse(left_sequence, **DEFAULT_CONDITIONS)
    right = analyse(right_sequence, **DEFAULT_CONDITIONS)
    return CandidatePair(
        left=left,
        right=right,
        left_at=Placement(start=0, length=left.length),
        right_at=Placement(start=199, length=right.length),
        product_size=220,
        penalty=0.5,
        tm_difference=abs(left.tm - right.tm),
        cross_dimer_dg=-1.0,
        amplicon="ACGT" * 55,
    )


INNER_LEFT = "ACATCGCATTTGAAACCCAG"
INNER_RIGHT = "TACTGCCCTCTCTGTTTCTC"
ISLAND_DESERT = "AT" * 40


def _an_amplicon(left_copies: int) -> str:
    """An outer product holding `left_copies` inner-left sites and one right.

    The right primer's site is embedded as its reverse complement, which is
    how a right primer meets a plus strand: the scanner reports that window
    reading back, and `Placement` reports it by its highest base.
    """
    return (
        ISLAND_DESERT
        + (INNER_LEFT + ISLAND_DESERT) * left_copies
        + reverse_complement(INNER_RIGHT)
        + ISLAND_DESERT
    )


def _inner_pair(amplicon: str, *, offset: int):
    """The inner pair whose intended sites are the first left copy and the right."""
    from dataclasses import replace

    pair = _a_round(INNER_LEFT, INNER_RIGHT)
    return replace(
        pair,
        left_at=replace(pair.left_at, start=offset + len(ISLAND_DESERT)),
        # The right primer is reported by its highest plus-strand base, which
        # is where its embedded window ends.
        right_at=replace(
            pair.right_at,
            start=offset + len(amplicon) - len(ISLAND_DESERT) - 1,
        ),
    )


def test_an_inner_primer_on_its_own_site_is_left_alone():
    """The intended sites sit inside the outer product by definition.

    Nesting *is* an inner primer inside the outer product; only second sites
    are intruders. A scan that accused a primer of its own place would reject
    every design there is.
    """
    from pcr_tools.nested import foreign_sites_in_outer_product
    from pcr_tools.presets import polymerase

    amplicon = _an_amplicon(left_copies=1)
    inner = _inner_pair(amplicon, offset=30)

    found = foreign_sites_in_outer_product(inner, 30, amplicon, polymerase("taq-standard").reaction)
    assert found == [], [(s.role, s.orientation, s.three_prime_at) for s in found]


def test_a_second_site_in_the_outer_product_is_found_and_reported_worst_first():
    """The naive inner primer that ruins a nest is now found before it ships."""
    from pcr_tools.nested import foreign_sites_in_outer_product
    from pcr_tools.presets import polymerase

    # The inner-left site appears twice in what round one amplifies.
    amplicon = _an_amplicon(left_copies=2)
    inner = _inner_pair(amplicon, offset=25)

    intruders = foreign_sites_in_outer_product(
        inner, 25, amplicon, polymerase("taq-standard").reaction
    )
    assert intruders, "the duplicated site went unnoticed"
    assert all(site.role == "left" for site in intruders), [
        (site.role, site.orientation) for site in intruders
    ]
    # Worst binding first, so the sentence quotes the most dangerous copy.
    assert [site.dg for site in intruders] == sorted(site.dg for site in intruders)


def test_an_inner_primer_duplicated_in_the_outer_product_is_refused():
    """A template whose naive inner primer double-binds round one's product.

    The duplicate sits in the margin gap, outside the stretch the inner search
    may pick from, so Primer3 sees one clean site and answers happily -- and
    the scan against the outer product is what catches it. Every candidate
    anchors on the repeated site, so this outer pair yields no nest, and the
    rejection names why instead of shrinking into "no inner pair survived".
    """

    def desert(n: int) -> str:
        return ("AT" * n)[:n]

    x = "ACATCGCATTTGAAACCCAG"
    y = "TACTGCCCTCTCTGTTTCTC"
    outer_left = "ACCTGTGCCGTTGACGTTTG"
    outer_right = "CACCTGTTAGAAACGTCGCG"

    duplicated = (
        desert(20)
        + outer_left
        + desert(40)
        + x  # the copy in the margin gap: invisible to the inner search
        + desert(140)
        + x  # the copy the inner search is meant to find
        + desert(280)
        + y
        + desert(180)
        + outer_right
        + desert(30)
    )
    single = (
        desert(20)
        + outer_left
        + desert(180)
        + x
        + desert(280)
        + y
        + desert(180)
        + outer_right
        + desert(30)
    )
    outer = Constraints(product_min=600, product_max=780, tm_min=60.0, tm_opt=62.5)

    dirty = design_nested(
        duplicated,
        outer=outer,
        inner=Constraints(product_min=250, product_max=800),
        nesting=Nesting(margin=100),
        conditions=REACTION.as_conditions(),
        how_many=2,
    )
    clean = design_nested(
        single,
        outer=outer,
        inner=Constraints(product_min=250, product_max=800),
        nesting=Nesting(margin=100),
        conditions=REACTION.as_conditions(),
        how_many=2,
    )

    reasons = {entry["reason"] for entry in dirty.rejected}
    assert "an inner primer has a second site in the outer product" in reasons, dirty.rejected
    assert dirty.nests == [], "a nest whose primer double-binds round one was offered"

    # The same layout without the duplicate designs normally, which is what
    # pins the refusal to the second site rather than to the layout.
    assert clean.nests, "the control template lost its nest"

    detail = next(
        entry["detail"]
        for entry in dirty.rejected
        if entry["reason"] == "an inner primer has a second site in the outer product"
    )
    assert "outer product" in detail
    assert any(character.isdigit() for character in detail)


# ── Carry-over prevention ──────────────────────────────────────────────────


def test_one_tube_is_refused_as_a_noncurrent_topology_in_every_policy_mode(monkeypatch):
    """Policy mode must never turn a different assay topology back on."""
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "permissive")
    with pytest.raises(NestedError, match="not an executable Generation-1 topology"):
        Nesting(single_tube=True).check()
