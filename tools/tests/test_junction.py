"""Primers that carry the joins, and the geometry that decides which one does.

An assembly design is a set problem wearing a primer problem's clothes. Each
overlap can be perfect on its own and the set still be wrong — an overlap that
occurs twice joins the wrong fragments, and two overlaps that anneal to each
other join fragments that were never meant to meet. So most of what is tested
here is the set rather than the oligos.

The other half is the tail geometry, which is the part an implementation gets
subtly wrong and which no thermodynamic measure would catch: a tail on the wrong
primer, or on the right primer in the wrong orientation, produces an oligo that
looks entirely reasonable and an assembly that does not close.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.design import Constraints
from pcr_tools.junction import (
    ASSEMBLY_CROSS_TALK_TM,
    BY_ID,
    JunctionError,
    Plan,
    Segment,
    around,
    clashes,
    ends_badly,
    method,
    occurrences,
    wallace,
    windows_for,
)
from pcr_tools.presets import polymerase
from pcr_tools.thermo import reverse_complement

CONDITIONS = polymerase("proofreading").reaction.as_conditions()


def puc() -> str:
    return record("L09137.2").sequence()


def tp53() -> str:
    return record("NM_000546.6").sequence()


def two_fragments() -> Plan:
    return Plan(
        segments=[
            Segment(name="vector", kind="amplified", sequence=puc()[:1800]),
            Segment(name="insert", kind="amplified", sequence=tp53()[200:1000]),
        ],
        circular=True,
    )


def assembly_constraints() -> Constraints:
    """A permissive fixture window for endpoint-primer geometry tests."""
    return Constraints(
        product_min=200,
        product_max=10_000,
        tm_min=54.0,
        tm_max=70.0,
        tm_pair_max_difference=12.0,
        gc_min=30.0,
        gc_max=70.0,
        gc_clamp=0,
        max_end_gc=5,
    )


def assembly_constraint_dict() -> dict[str, int | float]:
    return {
        field: getattr(assembly_constraints(), field) for field in Constraints.__dataclass_fields__
    }


# ── The chemistry is required ──────────────────────────────────────────────


def test_an_assembly_without_a_named_chemistry_is_refused():
    """There is nothing to default to: they are four different enzymes.

    Gibson wants at least forty bases, NEBuilder fifteen to thirty, In-Fusion
    exactly fifteen and never above twenty-one. A tool that picks one silently
    is designing for a kit somebody may not own.
    """
    with pytest.raises(JunctionError, match="nothing to default it to"):
        method(None)


def test_the_refusal_names_every_chemistry_it_knows():
    with pytest.raises(JunctionError) as raised:
        method(None)
    for known in BY_ID:
        assert known in str(raised.value)


def test_the_four_chemistries_do_not_agree_on_the_overlap():
    """Pinned because averaging them would be the tempting mistake.

    A middle value suits none of them: it is too short for Gibson's protocol and
    outside what In-Fusion recommends at the same time.
    """
    lengths = {one.id: (one.overlap_min, one.overlap_max) for one in BY_ID.values()}
    assert lengths["gibson"][0] > lengths["nebuilder"][1]
    assert lengths["in-fusion"][1] < lengths["nebuilder"][1]


# ── The gate is in the unit it was published in ────────────────────────────


def test_the_overlap_is_gated_by_the_two_four_rule_not_the_thermodynamic_model():
    """Because that is the unit the 48 °C floor was stated in.

    The Wallace rule is a poor model of melting, which is not the point. The
    vendors' figure was published in it, so checking it in any other unit is
    checking a different number against the same threshold.
    """
    assert wallace("AAAA") == 8.0
    assert wallace("GGGG") == 16.0
    assert wallace("ACGT") == 12.0


def test_a_palindromic_repeat_is_warm_by_the_wrong_measure_and_short_by_the_right_one():
    """The NotI tandem repeat the manuals warn about.

    Twelve bases, so it fails the length floor outright — which is the point of
    that floor being an independent gate rather than a consequence of the
    temperature one.
    """
    notI = "GCGGCCGCGGCC"
    assert wallace(notI) >= 48.0
    assert len(notI) < BY_ID["nebuilder"].overlap_min


def test_an_overlap_ending_in_a_homopolymer_is_refused_with_the_mechanism():
    assert "out of register" in ends_badly("AAAAACGTACGTACGT")
    assert "out of register" in ends_badly("ACGTACGTACGTTTTTT")
    assert ends_badly("ACGTACGTACGTACGT") == ""


# ── The geometry ───────────────────────────────────────────────────────────


def test_a_fixed_fragment_forces_the_whole_overlap_onto_its_neighbour():
    """It has no primer, so it cannot carry a tail.

    This is the rule the vendors state as three separate cases; it falls out of
    one fact rather than needing to be special-cased.
    """
    plan = Plan(
        segments=[
            Segment(name="cut-vector", kind="fixed", sequence=puc()[:1800]),
            Segment(name="insert", kind="amplified", sequence=tp53()[200:1000]),
        ],
        circular=True,
    )
    found, _ = windows_for(
        plan.construct(),
        1800,
        plan.segments[0],
        plan.segments[1],
        BY_ID["nebuilder"],
        CONDITIONS,
    )
    assert found
    for overlap in found:
        # Everything comes from the fixed fragment, because the amplified one
        # is the only side with a primer to put a tail on.
        assert overlap.from_downstream == 0
        assert overlap.from_upstream == overlap.length


def test_two_fixed_fragments_cannot_be_joined_and_the_refusal_says_why():
    plan = Plan(
        segments=[
            Segment(name="one", kind="fixed", sequence=puc()[:900]),
            Segment(name="two", kind="fixed", sequence=tp53()[200:900]),
        ],
        circular=False,
    )
    found, why = windows_for(
        plan.construct(),
        900,
        plan.segments[0],
        plan.segments[1],
        BY_ID["nebuilder"],
        CONDITIONS,
        circular=False,
    )
    assert not found
    assert "neither has a primer" in why
    assert "has to be amplified" in why


# ── The tails go on the right primers, the right way round ─────────────────


# ── The set, which is why this is one search ───────────────────────────────


def test_an_overlap_occurring_twice_in_the_construct_is_a_clash():
    """Because the fragments could then join in more than one arrangement."""
    repeated = "ACGTACGTACGTACGTACGTACGT"
    construct = repeated + "TTTTGGGGCCCCAAAATTTTGGGG" + repeated + "GGGGCCCCTTTTAAAA"
    from pcr_tools.junction import Overlap

    overlap = Overlap(
        sequence=repeated,
        at=0,
        from_upstream=12,
        from_downstream=12,
        wallace_tm=wallace(repeated),
        hairpin_tm=0.0,
    )
    found = clashes({0: overlap}, construct, circular=False)
    assert found
    assert "occurs" in found[0].why


def test_a_circular_construct_is_searched_across_its_own_join():
    """And an overlap is not reported twice for it.

    The off-by-one here reports a phantom second copy of every overlap that
    spans the origin, and a phantom copy reads as a design to reject.
    """
    # Deliberately not self-complementary. The first sequence tried here was
    # AAAACCCCGGGGTTTT, which is its own reverse complement — so it really does
    # occur twice, once on each strand, and the search was right to say so.
    # Both strands are searched because a fragment that can join in the flipped
    # orientation is a fragment that will.
    construct = "ATCGGATCCTAGCATTGACCTGAAAGCTTCC"
    assert construct != reverse_complement(construct)

    once = occurrences(construct, "ATCGGATCC", circular=True)
    assert len(once) == 1

    # A window that exists only by wrapping is found exactly once, not twice.
    wrapped = around(construct, len(construct) - 4, 8, circular=True)
    assert wrapped == "TTCCATCG"  # the last four bases, then the first four
    assert len(occurrences(construct, wrapped, circular=True)) == 1


def test_a_circular_plan_has_one_more_junction_than_a_linear_one():
    """The last fragment meets the first, and that join is real."""
    circular = two_fragments()
    linear = Plan(segments=circular.segments, circular=False)
    assert len(circular.junctions()) == len(linear.junctions()) + 1


# ── The three scales, never added together ─────────────────────────────────


# ── Plans that could not be assemblies ─────────────────────────────────────


def test_one_fragment_is_not_an_assembly():
    with pytest.raises(JunctionError, match="is a PCR"):
        Plan(segments=[Segment("only", "amplified", puc()[:900])]).check()


def test_a_plan_with_nothing_amplified_has_no_primers_to_design():
    with pytest.raises(JunctionError, match="has to be made by PCR"):
        Plan(
            segments=[
                Segment("one", "fixed", puc()[:900]),
                Segment("two", "fixed", tp53()[200:900]),
            ]
        ).check()


def test_two_fragments_sharing_a_name_are_refused():
    with pytest.raises(JunctionError, match="share a name"):
        Plan(
            segments=[
                Segment("same", "amplified", puc()[:900]),
                Segment("same", "amplified", tp53()[200:900]),
            ]
        ).check()


def test_a_kind_this_does_not_assemble_lists_the_ones_it_does():
    with pytest.raises(JunctionError, match="not a kind of fragment"):
        Segment("odd", "ligated", "ACGTACGT").check()


def test_the_cross_talk_threshold_is_a_temperature_against_the_reaction():
    """Rather than a free energy at a temperature nobody runs the assembly at."""
    assert ASSEMBLY_CROSS_TALK_TM < BY_ID["nebuilder"].assembly_temperature


# ── Sequence added at a join, which is on neither fragment ─────────────────

#: A six-histidine tag: the thing people actually add at a junction, and the
#: thing the vendors specifically refuse to let you make an overlap out of.
HIS_TAG = "CATCACCATCACCATCAC"


def with_a_tag() -> Plan:
    return Plan(
        segments=[
            Segment(name="vector", kind="amplified", sequence=puc()[:1800]),
            Segment(name="his-tag", kind="literal", sequence=HIS_TAG),
            Segment(name="insert", kind="amplified", sequence=tp53()[200:1000]),
        ],
        circular=True,
    )


def test_a_literal_does_not_make_a_junction_of_its_own():
    """There is no molecule there to join to.

    Counting it as a fragment reports two joins where there is one, and reports
    each of them shorter than the overlap the two products actually share —
    measured before this was fixed, two joins of 30 bases against a real shared
    region of 42, which for a chemistry refusing anything above 21 is a design
    silently out of spec.
    """
    plan = with_a_tag()
    junctions = plan.junctions()

    # Two real fragments in a circle: two joins, not three.
    assert len(junctions) == 2
    assert {one.upstream for one in junctions} == {"vector", "insert"}
    assert all("his-tag" not in (one.upstream, one.downstream) for one in junctions)


def test_the_tag_is_folded_into_the_join_between_its_neighbours():
    plan = with_a_tag()
    joined = next(
        one for one in plan.junctions() if (one.upstream, one.downstream) == ("vector", "insert")
    )
    assert joined.interposed == HIS_TAG
    assert joined.interposed_names == ["his-tag"]


def test_an_overlap_too_long_to_fold_says_so_rather_than_reading_as_clean():
    """Zero because nothing looked is not zero because nothing was found.

    An overlap past primer3's limit comes back with `hairpin_tm` of zero, which
    is the same number a clean one carries. The flag is what tells them apart,
    and without it the longest overlaps — the ones most likely to fold — would
    read as the safest.
    """
    from pcr_tools.thermo import FOLDABLE_BASES, analyse, folded

    short = analyse("ACGTACGTACGTACGTACGT")
    assert folded(short) is True

    long_one = analyse("ACGT" * 20)  # 80 bases
    assert len(long_one.sequence) > FOLDABLE_BASES
    assert folded(long_one) is False
    # Composition and melting temperature are still real.
    assert long_one.gc_percent == 50.0
    assert long_one.tm > 0
    # The structures are absent, not measured as clean.
    assert long_one.hairpin.found is False
    assert long_one.hairpin.dg == 0.0
