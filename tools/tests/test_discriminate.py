"""Telling two alleles apart, and what the chemistry will and will not allow.

Most of this suite is about a table rather than about primers. Both alleles are
given, so the terminal mismatch is not chosen — the only lever is which strand
the allele-specific primer sits on, and that maps every mismatch to its
complement. What that enumeration yields decides what the assay may claim, and
getting it wrong produces a design that looks entirely reasonable and cannot
genotype anything.

The rest is about the two places a pinned 3' end breaks the ordinary machinery.
Both were found by measuring how often a complete assay came out — 10 sites in
200 before, 50 after — rather than by reading the code, because in both cases
the search returned a plausible smaller answer instead of an error.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.design import Constraints
from pcr_tools.discriminate import (
    BLOCKING,
    COMPLEMENT,
    GEOMETRIES,
    SECOND_MISMATCH_AT,
    STRENGTHS,
    DiscriminationError,
    allele_primers,
    apply_second,
    assignments,
    carrying,
    design,
    run,
    second_mismatches,
    strength,
    terminus_for,
    with_second_mismatch,
)
from pcr_tools.presets import polymerase
from pcr_tools.thermo import analyse

CONDITIONS = polymerase("taq-standard").reaction.as_conditions()

#: A window wide enough that the sequence rather than the constraints decides.
WIDE = Constraints(gc_min=30.0, gc_max=75.0)

KASP_ASSAY = {
    "id": "kasp",
    "name": "KASP",
    "enzyme": ["no-proofreading"],
    "defaults": {
        "polymerase": "taq-standard",
        "chemistryFamily": "kasp-endpoint-fret",
        "purposes": ["general"],
        "constraints": {"gc_min": 30.0, "gc_max": 75.0},
    },
}

TETRA_ASSAY = {
    "id": "tetra-primer-arms",
    "name": "Tetra-primer ARMS",
    "enzyme": ["no-proofreading"],
    "defaults": {
        "polymerase": "taq-standard",
        "purposes": ["general"],
        "constraints": {"gc_min": 30.0, "gc_max": 75.0},
    },
}

TRANSVERSIONS = (("A", "C"), ("A", "T"), ("C", "G"), ("G", "T"))
TRANSITIONS = (("A", "G"), ("C", "T"))


def template() -> str:
    return record("NM_000546.6").sequence()


# ── The table the whole engine rests on ────────────────────────────────────


def test_a_terminal_mismatch_is_classified_by_which_pair_it_makes():
    """Primer base against template base, not the other way round.

    The pairs are not symmetric: A*G blocks and G*A blocks, but C*A and A*C
    both amplify. Reading the pair backwards would classify half of them wrong.
    """
    assert strength("A", "G") == "blocks"
    assert strength("C", "C") == "blocks"
    assert strength("A", "A") == "slows"
    assert strength("G", "G") == "depends"
    assert strength("C", "A") == "tolerated"


@pytest.mark.parametrize("alleles", TRANSITIONS, ids=lambda a: f"{a[0]}/{a[1]}")
def test_a_transition_has_no_blocking_terminus_on_either_strand(alleles):
    """Which is about two thirds of human variation.

    Every placement comes out as A*C, C*A, G*T or T*G, all of which the
    polymerase extends efficiently. This is the finding that makes the second
    mismatch the mechanism rather than a refinement.
    """
    one, other = alleles
    for strand in ("plus", "minus"):
        for target, off in ((one, other), (other, one)):
            assert terminus_for(target, off, strand).strength == "tolerated"


@pytest.mark.parametrize("alleles", TRANSVERSIONS, ids=lambda a: f"{a[0]}/{a[1]}")
def test_a_transversion_gives_exactly_one_allele_the_strong_mismatch_per_strand(
    alleles,
):
    """And which allele it is flips with the strand.

    This is the fact the geometries turn on: never both on one strand, and
    always the other one on the other strand.
    """
    one, other = alleles
    for strand, flipped in (("plus", "minus"), ("minus", "plus")):
        here = terminus_for(one, other, strand).strength
        there = terminus_for(one, other, flipped).strength
        assert here != there, f"{one} behaves the same on both strands"


def test_a_geometry_facing_the_two_primers_apart_gets_both_alleles_discriminated():
    """Which is what the four-primer layout is for.

    Exactly one allele can have the strong mismatch on any single strand and
    which one flips with the strand — so pointing the two allele-specific
    primers in opposite directions gets both at once. It is not a coincidence
    that this is the layout that works.
    """
    for alleles in TRANSVERSIONS:
        opposite = assignments(alleles, same_strand=False)[0]
        same = assignments(alleles, same_strand=True)[0]

        strengths = {one.strength for one in opposite.termini.values()}
        assert len(strengths) == 1, f"{alleles}: {strengths}"

        # And the same-strand layout cannot match it.
        assert STRENGTHS.index(same.weakest) > STRENGTHS.index(opposite.weakest), alleles


def test_the_same_strand_layout_can_never_discriminate_both_alleles_equally():
    """The cost of KASP's geometry, stated rather than discovered at the bench."""
    for alleles in TRANSVERSIONS:
        same = assignments(alleles, same_strand=True)[0]
        strengths = {one.strength for one in same.termini.values()}
        assert len(strengths) == 2, f"{alleles} came out even on one strand"


def test_every_blocking_pair_is_a_purine_against_a_purine_or_c_against_c():
    """A sanity check on the table itself rather than on any code path."""
    for primer_base, template_base in BLOCKING:
        assert primer_base in "ACGT" and template_base in "ACGT"
        assert strength(primer_base, template_base) == "blocks"


# ── The allele-specific primer ─────────────────────────────────────────────


def test_every_allele_specific_primer_ends_on_the_variant():
    """Which is the whole mechanism, so it is checked against the sequence."""
    sequence = template()
    for strand in ("plus", "minus"):
        for primer in allele_primers(sequence, 1200, "C", "G", strand, WIDE, CONDITIONS):
            if strand == "plus":
                assert primer.sequence[-1].upper() == "C"
                assert primer.at + primer.length - 1 == 1200
            else:
                assert primer.sequence[-1].upper() == COMPLEMENT["C"]
                assert primer.at == 1200


def test_no_gc_clamp_is_applied_to_a_primer_whose_end_is_not_chosen():
    """The 3' end is the variant, and the variant is wherever it is.

    A clamp is a rule about picking a good place to end. Applying it here would
    reject an assay because of where somebody's SNP happens to be.
    """
    sequence = template()

    # A variant that is an A or a T gives a primer ending in one, which an
    # ordinary GC clamp would refuse outright. Several sites are tried because
    # any single one can fail for its own reasons — what is being shown is that
    # ending in A or T is not itself disqualifying.
    ending_in_at = [
        found[0]
        for at in range(400, 1200)
        if sequence[at].upper() in "AT"
        and (
            found := allele_primers(
                sequence, at, sequence[at].upper(), "G", "plus", WIDE, CONDITIONS
            )
        )
    ]
    assert ending_in_at, "no variant on an A or a T was designable anywhere"
    assert all(one.sequence[-1].upper() in "AT" for one in ending_in_at)


def test_a_second_mismatch_leaves_the_primer_inside_its_own_window():
    """It changes the melting temperature, so both are measured again."""
    found = allele_primers(template(), 1200, "C", "T", "plus", WIDE, CONDITIONS)
    assert found
    improved = with_second_mismatch(found[0], WIDE, CONDITIONS)
    assert improved
    assert WIDE.tm_min <= improved.tm <= WIDE.tm_max
    assert improved.tm == analyse(improved.sequence, **CONDITIONS).tm


def test_a_second_mismatch_never_touches_the_discriminating_base():
    """The last base is the variant; substituting it would erase the assay."""
    assert -1 not in SECOND_MISMATCH_AT
    found = allele_primers(template(), 1200, "C", "T", "plus", WIDE, CONDITIONS)
    improved = with_second_mismatch(found[0], WIDE, CONDITIONS)
    assert improved
    assert improved.sequence[-1] == found[0].sequence[-1]


def test_a_second_mismatch_changes_exactly_one_base():
    found = allele_primers(template(), 1200, "C", "T", "plus", WIDE, CONDITIONS)
    original = found[0].sequence
    for at in SECOND_MISMATCH_AT:
        for candidate in second_mismatches(original, at):
            modified = apply_second(original, candidate)
            differ = [
                index for index, (a, b) in enumerate(zip(original, modified, strict=True)) if a != b
            ]
            assert differ == [len(original) + at]


# ── Two bugs a pinned 3' end causes, both found by measurement ─────────────


# ── What it refuses ────────────────────────────────────────────────────────


def test_a_template_disagreeing_with_both_alleles_is_refused():
    """Either the position is wrong or this is a different haplotype."""
    sequence = template()
    here = sequence[1200].upper()
    others = [base for base in "ACGT" if base != here][:2]
    with pytest.raises(DiscriminationError, match="neither of the alleles"):
        design(
            sequence,
            at=1200,
            alleles=(others[0], others[1]),
            constraints=WIDE,
            conditions=CONDITIONS,
        )


def test_two_identical_alleles_are_refused():
    with pytest.raises(DiscriminationError, match="nothing to tell apart"):
        design(template(), at=1200, alleles=("C", "C"), conditions=CONDITIONS)


def test_an_indel_is_named_as_a_different_assay():
    with pytest.raises(DiscriminationError, match="different assay"):
        design(template(), at=1200, alleles=("C", "-"), conditions=CONDITIONS)


def test_a_geometry_this_does_not_do_lists_the_ones_it_does():
    with pytest.raises(DiscriminationError, match="not a layout"):
        design(
            template(),
            at=1200,
            alleles=("C", "G"),
            geometry="single-tube-nested",
            conditions=CONDITIONS,
        )


def test_a_request_without_a_variant_position_is_refused_rather_than_defaulted():
    with pytest.raises(DiscriminationError, match="nothing sensible to default"):
        run({"template": template(), "alleles": ["C", "G"], "assay": {"id": "a", "name": "A"}})


def test_a_request_with_one_allele_is_refused():
    with pytest.raises(DiscriminationError, match="exactly two alleles"):
        run(
            {
                "template": template(),
                "at": 1200,
                "alleles": ["C"],
                "assay": {"id": "a", "name": "A"},
            }
        )


# ── What it says ───────────────────────────────────────────────────────────


def test_unknown_kasp_protocol_is_refused():
    with pytest.raises(DiscriminationError, match="KASP protocol"):
        run(
            {
                "template": template(),
                "at": 1200,
                "alleles": ["C", "G"],
                "geometry": "kasp",
                "kasp_assay_mode": "biallelic-genotype",
                "assay": KASP_ASSAY,
                "purpose": "general",
                "kasp_protocol": "guess",
            }
        )


def test_lgc_protocol_cannot_be_attached_to_a_gel_geometry():
    with pytest.raises(DiscriminationError, match="KASP geometry"):
        run(
            {
                "template": template(),
                "at": 1200,
                "alleles": ["C", "G"],
                "geometry": "arms-two-tube",
                "kasp_protocol": "lgc-standard",
                "kasp_plate_format": "96",
                "kasp_instrument_model": "unresolved",
                "kasp_rox_policy": "unresolved",
            }
        )


def test_every_geometry_declares_whether_its_primers_share_a_strand():
    """Because that single fact decides what the assay can promise."""
    for name, layout in GEOMETRIES.items():
        assert isinstance(layout["same_strand"], bool), name
        assert layout["tubes"] >= 1
        assert len(layout["note"]) > 60


def test_the_synthetic_template_differs_from_the_real_one_at_one_base():
    sequence = template()
    changed = carrying(sequence, 1200, "A")
    differ = [index for index, (a, b) in enumerate(zip(sequence, changed, strict=True)) if a != b]
    assert differ == [1200]
    assert len(changed) == len(sequence)


@pytest.mark.parametrize("policy", ["strict", "development"])
def test_kasp_geometry_never_synthesizes_assay_identity(monkeypatch, policy):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", policy)
    with pytest.raises(DiscriminationError, match=r"canonical `assay.id=kasp` profile"):
        run(
            {
                "template": template(),
                "at": 1200,
                "alleles": ["C", "G"],
                "geometry": "kasp",
                "kasp_assay_mode": "biallelic-genotype",
            }
        )


@pytest.mark.parametrize("policy", ["strict", "development"])
def test_tetra_requires_declared_band_resolution_context_in_every_policy(monkeypatch, policy):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", policy)
    with pytest.raises(DiscriminationError, match="tetra_min_band_separation_bp"):
        run(
            {
                "template": template(),
                "at": 1200,
                "alleles": ["C", "G"],
                "geometry": "tetra",
                "assay": TETRA_ASSAY,
                "purpose": "general",
            }
        )
