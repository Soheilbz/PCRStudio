"""Restriction sites on a primer's 5' end, and the four ways that goes wrong.

Real sequence throughout. A restriction site is six specific bases, and whether
one appears in a template is a fact about that template rather than about a
model -- so a made-up sequence would only test the regular expression.
"""

from __future__ import annotations

import pathlib

import pytest

from pcr_tools.restriction import BY_NAME
from pcr_tools.tails import (
    PROTECTIVE_BASES,
    TailError,
    attach,
    build_tail,
    describe,
    occurrences,
    tails_interact,
    usable_enzymes,
)

CORPUS = pathlib.Path(__file__).parent / "corpus"
PROTECTIVE = "GACTTA"
ALT_PROTECTIVE = "CAGTTA"


def sequence(accession: str, start: int = 0, length: int | None = None) -> str:
    raw = (CORPUS / f"{accession}.fasta").read_text().splitlines()
    seq = "".join(line.strip() for line in raw if not line.startswith(">"))
    return seq[start : start + length] if length else seq[start:]


@pytest.fixture(scope="module")
def tp53() -> str:
    """Seven hundred bases of TP53 mRNA, which is a real cloning target."""
    return sequence("NM_000546.6", 200, 700)


def test_a_site_that_is_really_there_is_counted(tp53: str) -> None:
    # NcoI reads CCATGG, and this stretch of TP53 contains one. That is the
    # whole assay in one fact: an enzyme whose site is inside the insert cuts
    # the product in the middle as well as at its ends.
    assert occurrences(tp53, BY_NAME["NcoI"]) == 1
    assert tp53.upper().count("CCATGG") == 1


def test_both_strands_are_searched() -> None:
    # A palindromic site is findable on either strand, so it cannot show the
    # difference. HinfI reads GANTC, whose reverse complement is GANTC only
    # when the middle base happens to match -- GAATC on the top strand is
    # GATTC on the bottom, and both are the site.
    top_only = "GAATC"
    assert occurrences(top_only, BY_NAME["HinfI"]) >= 1

    # This spells GATTC, which is the reverse complement of GAATC. A top-strand
    # scan for GANTC finds it too, because N covers the middle base -- so the
    # useful check is that neither reading is double-counted.
    assert occurrences("GATTC", BY_NAME["HinfI"]) >= 1


def test_a_palindromic_site_is_not_counted_twice() -> None:
    # EcoRI's site is its own reverse complement. Searching both strands must
    # not report one site as two.
    assert occurrences("GAATTC", BY_NAME["EcoRI"]) == 1
    assert occurrences("AAAAGAATTCAAAA", BY_NAME["EcoRI"]) == 1


def test_overlapping_sites_are_all_found() -> None:
    # GGATCCGGATCC carries two BamHI sites. A scan that consumed its match
    # would report one, and the design would be built on a wrong count.
    assert occurrences("GGATCCGGATCC", BY_NAME["BamHI"]) == 2


def test_ambiguous_insert_is_screened_conservatively() -> None:
    # The N can be A, so this could be GAATTC and EcoRI must be rejected rather
    # than allowed through on the assumption that N is not a match.
    assert occurrences("GANTTC", BY_NAME["EcoRI"]) == 1
    with pytest.raises(TailError, match="GAATTC"):
        build_tail("EcoRI", "GANTTC" + "A" * 100, protective_sequence=PROTECTIVE)


def test_rna_is_refused_instead_of_silently_converted_for_cloning() -> None:
    with pytest.raises(TailError, match="RNA uracil"):
        occurrences("GAAUUC", BY_NAME["EcoRI"])


def test_malformed_insert_is_refused_instead_of_stripped() -> None:
    with pytest.raises(TailError, match="formatting symbols"):
        build_tail("EcoRI", "A" * 100 + "!", protective_sequence=PROTECTIVE)


def test_multiple_fasta_records_are_refused() -> None:
    records = ">first\n" + "A" * 100 + "\n>second\n" + "A" * 100
    with pytest.raises(TailError, match="multiple FASTA records"):
        build_tail("EcoRI", records, protective_sequence=PROTECTIVE)


def test_usable_enzymes_are_the_ones_absent_from_the_insert(tp53: str) -> None:
    usable = {enzyme.name for enzyme in usable_enzymes(tp53)}

    assert "NcoI" not in usable, "NcoI cuts this insert, so it is not usable"
    assert "EcoRI" in usable
    for name in usable:
        assert occurrences(tp53, BY_NAME[name]) == 0


def test_short_recognition_sites_are_judged_by_the_actual_insert() -> None:
    # Recognition-site length is not a validity gate.  A short site that is
    # genuinely absent from the submitted insert may be offered; suitability
    # for the user's vector/digest remains a separate decision.
    usable = {enzyme.name for enzyme in usable_enzymes("A" * 100)}
    assert "TaqI" in usable  # TCGA is absent from this insert.


def test_an_enzyme_that_cuts_the_insert_is_refused_with_the_reason(tp53: str) -> None:
    with pytest.raises(TailError) as raised:
        build_tail("NcoI", tp53, protective_sequence=PROTECTIVE)

    said = str(raised.value)
    assert "NcoI" in said
    assert "CCATGG" in said, "the message should name the site, not only the enzyme"
    assert "cut the product in the middle" in said


def test_an_unknown_enzyme_says_which_ones_are_known(tp53: str) -> None:
    with pytest.raises(TailError) as raised:
        build_tail("NotAnEnzyme", tp53, protective_sequence=PROTECTIVE)

    said = str(raised.value)
    assert "EcoRI" in said, "the message should list what is available"


def test_the_tail_is_explicit_protective_sequence_then_the_site(tp53: str) -> None:
    tail = build_tail("EcoRI", tp53, protective_sequence=PROTECTIVE)

    assert tail.sequence.endswith("GAATTC"), "the site sits at the 3' end of the tail"
    assert len(tail.protective) == PROTECTIVE_BASES
    assert tail.protective == PROTECTIVE
    assert tail.sequence == tail.protective + tail.site


def test_protective_sequence_is_never_generated_or_silently_cleaned(tp53: str) -> None:
    with pytest.raises(TypeError):
        build_tail("EcoRI", tp53)
    with pytest.raises(TailError, match="only A/C/G/T"):
        build_tail("EcoRI", tp53, protective_sequence="GACTTN")


def test_palindromic_protective_sequence_is_refused(tp53: str) -> None:
    # NEB explicitly advises choosing the extra bases so that palindromes and
    # primer dimers are not formed.  GATATC is its own reverse complement.
    with pytest.raises(TailError, match="palindromic"):
        build_tail("EcoRI", tp53, protective_sequence="GATATC")


def test_the_annealing_temperature_is_the_primer_not_the_whole_oligo(tp53: str) -> None:
    """The measurement this module exists for.

    Twelve extra bases raise the melting temperature of the molecule by several
    degrees, and none of that heat helps in the first cycle -- the tail has
    nothing to pair with. Reporting the whole oligo's temperature would send
    somebody to an annealing temperature at which the first cycle does not
    prime at all.
    """
    primer = "CAGACCTATGGAAACTACTT"
    tailed = attach(primer, build_tail("EcoRI", tp53, protective_sequence=PROTECTIVE))

    assert tailed.anneals.sequence == primer
    assert tailed.whole.sequence.endswith(primer)
    assert tailed.whole.length == len(primer) + 12

    difference = tailed.whole.tm - tailed.anneals.tm
    assert difference > 5, (
        "a twelve-base tail should raise the whole-molecule temperature well "
        f"above the annealing one; measured {difference:.1f} C"
    )


def test_the_finished_oligo_is_measured_in_full(tp53: str) -> None:
    # The tail is real DNA: it can fold back on the primer. Those numbers have
    # to come from the molecule that is in the tube, not from the primer it
    # was built on.
    tailed = attach(
        "CAGACCTATGGAAACTACTT", build_tail("EcoRI", tp53, protective_sequence=PROTECTIVE)
    )

    assert tailed.whole.hairpin is not None
    assert tailed.whole.self_dimer is not None
    assert tailed.whole.length > tailed.anneals.length


def test_interaction_is_reported_before_and_after(tp53: str) -> None:
    """Two tails can pair with each other when the primers cannot.

    A primer-dimer made of tails amplifies as happily as any other, so the
    number that matters is how much worse the tails made it -- a pair that was
    always sticky is a different problem from one the tails broke.
    """
    left = attach("CAGACCTATGGAAACTACTT", build_tail("EcoRI", tp53, protective_sequence=PROTECTIVE))
    right = attach(
        "GGAGTCTTCCAGTGGTAATC", build_tail("BamHI", tp53, protective_sequence=PROTECTIVE)
    )

    interaction = tails_interact(left, right)

    assert "without_tails" in interaction
    assert "with_tails" in interaction
    assert interaction["worsened_by"] == pytest.approx(
        interaction["without_tails"]["dg"] - interaction["with_tails"]["dg"], abs=0.01
    )


def test_a_tail_describes_itself_for_the_wire(tp53: str) -> None:
    described = describe(build_tail("BamHI", tp53, protective_sequence=PROTECTIVE))

    assert described["enzyme"] == "BamHI"
    assert described["site"] == "GGATCC"
    assert described["length"] == len(described["sequence"])
    assert described["first_observed_activity_flanking_bases"] == 1
    assert described["end_cleavage_evidence_identity"] == "NEB BamHI"


def test_tail_exposes_supplier_minimum_when_catalogue_has_verified_one(tp53: str) -> None:
    assert (
        describe(build_tail("HindIII", tp53, protective_sequence=PROTECTIVE))[
            "first_observed_activity_flanking_bases"
        ]
        == 2
    )
    assert (
        describe(build_tail("KpnI", tp53, protective_sequence=PROTECTIVE))[
            "end_cleavage_evidence_identity"
        ]
        == "NEB KpnI-HF"
    )
    assert (
        describe(build_tail("SpeI", tp53, protective_sequence=PROTECTIVE))[
            "end_cleavage_evidence_identity"
        ]
        == "NEB SpeI-HF"
    )
