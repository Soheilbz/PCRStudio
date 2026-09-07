"""A mixture is several oligos, and the arithmetic of that."""

from __future__ import annotations

import pytest

from pcr_tools.degenerate import (
    code_for,
    degeneracy,
    expand,
    extremes,
    gc_range,
    longest_run,
    matches,
    reverse_complement,
)


def test_a_plain_primer_holds_one_molecule():
    assert degeneracy("ACGTACGT") == 1


def test_every_variable_position_multiplies():
    # This is the whole reason there is a budget: two doublings and a
    # four-way are already sixteen molecules at a sixteenth the concentration.
    assert degeneracy("RYN") == 2 * 2 * 4


def test_a_mixture_expands_to_exactly_its_members():
    assert sorted(expand("RA")) == ["AA", "GA"]
    assert len(list(expand("NN"))) == 16


def test_expanding_something_enormous_is_refused_rather_than_attempted():
    with pytest.raises(ValueError, match="enumerate"):
        list(expand("N" * 20, limit=4096))


def test_the_extremes_bound_the_mixture_by_gc():
    coolest, warmest = extremes("RYSWKM")
    # R is A or G: the cool end takes A, the warm end takes G.
    assert coolest.startswith("A")
    assert warmest.startswith("G")


def test_reverse_complement_keeps_the_codes_meaningful():
    # R is A-or-G; its complement is T-or-C, which is Y.
    assert reverse_complement("R") == "Y"
    assert reverse_complement("ACGTRY") == "RYACGT"


def test_a_code_stands_for_exactly_the_bases_it_was_built_from():
    assert code_for({"A", "G"}) == "R"
    assert code_for({"A", "C", "G", "T"}) == "N"
    assert code_for({"C"}) == "C"


def test_a_window_matches_only_if_every_base_is_inside_the_mixture():
    assert matches("ARC", "AAC")
    assert matches("ARC", "AGC")
    assert not matches("ARC", "ATC")
    assert not matches("ARC", "AA")


def test_gc_is_a_range_when_a_position_could_go_either_way():
    # S is G or C, so it is GC whichever way it falls. W is A or T, so never.
    low, high = gc_range("SSWW")
    assert (low, high) == (50.0, 50.0)
    # R is A or G, so it might be GC and might not.
    low, high = gc_range("RRRR")
    assert (low, high) == (0.0, 100.0)


def test_a_run_of_one_code_counts_however_ambiguous_it_is():
    assert longest_run("AAAAC") == 4
    assert longest_run("NNNNNC") == 5
