"""What a consensus is, and the case where building one would be dishonest."""

from __future__ import annotations

import pytest

from pcr_tools.consensus import ConsensusError, build


def test_agreeing_sequences_collapse_to_themselves():
    result = build(["ACGTACGT", "ACGTACGT"])
    assert result.sequence == "ACGTACGT"
    assert result.varied == 0
    assert result.identity == 100.0


def test_one_disagreeing_column_becomes_its_iupac_code():
    result = build(["ACGTACGT", "ACGTATGT"])
    assert result.sequence == "ACGTAYGT"  # C or T is Y
    assert result.varied == 1


def test_every_two_base_combination_has_a_code():
    pairs = {
        ("A", "G"): "R",
        ("C", "T"): "Y",
        ("G", "C"): "S",
        ("A", "T"): "W",
        ("G", "T"): "K",
        ("A", "C"): "M",
    }
    for (first, second), code in pairs.items():
        assert build([first * 4, second * 4]).sequence == code * 4


def test_a_gap_makes_the_column_uncertain_and_says_so():
    result = build(["ACGT", "AC-T"])
    assert result.gapped == 1
    assert result.varied == 1
    assert any("gap" in note for note in result.notes)


def test_unaligned_sequences_are_refused_rather_than_lined_up_from_the_left():
    # This is the whole point. A consensus of unaligned sequences is not an
    # approximation of the right answer; it is a different answer wearing its
    # shape, and it would produce primers nobody could use.
    with pytest.raises(ConsensusError, match="not been aligned"):
        build(["ACGTACGT", "ACGT"])


def test_one_sequence_is_not_a_consensus():
    with pytest.raises(ConsensusError, match="at least two"):
        build(["ACGTACGT"])


def test_the_result_warns_that_a_consensus_may_match_nothing():
    result = build(["ACGTACGT", "ACGTATGT"])
    assert any("may exist in none" in note for note in result.notes)


def test_the_sequences_that_went_in_are_named():
    result = build(["ACGT", "ACGT"], names=["isolate_1", "isolate_2"])
    assert any("isolate_1" in note for note in result.notes)


@pytest.mark.parametrize("bad", ["ACGT!", "ACGT12", "ACGT*"])
def test_invalid_alignment_symbols_are_refused_instead_of_deleted(bad):
    with pytest.raises(ConsensusError, match="invalid symbol"):
        build([bad, "ACGT"])


def test_iupac_and_rna_inputs_are_expanded_before_the_consensus_is_built():
    result = build(["AUGR", "AUGA"])
    assert result.sequence == "ATGR"
    assert result.varied == 1
