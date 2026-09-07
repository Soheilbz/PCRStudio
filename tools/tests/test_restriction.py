"""Where an enzyme cuts, and how big a circle that makes.

The recognition sites in this module are data somebody typed, so most of what
is checked here is checked against a fact from outside the project: pUC19's
multiple cloning site. Ten of these enzymes are the polylinker, in a published
order, each cutting once. If the table were wrong, that would not hold.

The rest is two things that are easy to get wrong. Sites overlap, and a scan
that consumes its match undercounts them. And the expected fragment size is not
four-to-the-power-of-the-site-length: that is the average fragment, and the
fragment somebody's insertion sits in is longer, because a long fragment covers
more bases and so catches more insertions.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.restriction import (
    BY_NAME,
    ENZYMES,
    Enzyme,
    RestrictionError,
    choose_enzyme,
    fragment_sizes,
    sites,
)

#: The pUC19 polylinker, in the order it is published in.
POLYLINKER = (
    "EcoRI",
    "SacI",
    "KpnI",
    "SmaI",
    "BamHI",
    "XbaI",
    "SalI",
    "PstI",
    "SphI",
    "HindIII",
)


def puc19() -> str:
    return record("L09137.2").sequence()


# ── Against a fact from outside this project ───────────────────────────────


def test_every_polylinker_enzyme_cuts_puc19_exactly_once():
    """If the recognition sites were wrong, this would not hold."""
    for name in POLYLINKER:
        found = sites(puc19(), BY_NAME[name], circular=True)
        assert len(found) == 1, f"{name} cut {len(found)} times"


def test_the_polylinker_comes_out_in_the_order_it_is_published_in():
    """A stronger check than the count: the sites are where they should be.

    Ten enzymes each cutting once could still be ten wrong sites. Ten cutting
    once, in the published order, within fifty bases of each other, could not.
    """
    at = [sites(puc19(), BY_NAME[name], circular=True)[0] for name in POLYLINKER]
    assert at == sorted(at), "the cloning site is not in its published order"
    assert at[-1] - at[0] < 60, "these should all be inside one polylinker"


# ── Counting ───────────────────────────────────────────────────────────────


def test_overlapping_sites_are_all_found():
    """A scan that consumes its match would report one of these two."""
    assert len(sites("GGATCCGGATCC", BY_NAME["BamHI"])) == 2


def test_a_non_palindromic_site_is_found_in_either_orientation():
    # The catalogue currently contains palindromic cutters, so use a small
    # synthetic enzyme to pin the strand-orientation rule without pretending
    # it is a supplier-specific enzyme record. End-geometry claims for
    # non-palindromic/Type-IIS sites remain outside flanking-pair cloning.
    enzyme = Enzyme("Synthetic non-palindrome", "ACCT", 1)

    assert sites("ACCT", enzyme) == [1]
    assert sites("AGGT", enzyme) == [3]


def test_an_ambiguous_site_matches_every_base_it_stands_for():
    """HinfI reads GANTC, so both of these are sites."""
    assert len(sites("GAATCGACTC", BY_NAME["HinfI"])) == 2


def test_a_site_straddling_the_join_of_a_circle_is_found():
    """A plasmid's map starts somewhere arbitrary; an enzyme does not care."""
    # BamHI's GGATCC split across the join: the sequence ends GGA and begins TCC.
    sequence = "TCC" + "AAAA" * 10 + "GGA"
    assert sites(sequence, BY_NAME["BamHI"], circular=False) == []
    assert len(sites(sequence, BY_NAME["BamHI"], circular=True)) == 1


def test_no_site_is_reported_twice_when_a_circle_is_scanned():
    linear = sites(puc19(), BY_NAME["Sau3AI"], circular=False)
    circular = sites(puc19(), BY_NAME["Sau3AI"], circular=True)
    assert len(circular) - len(linear) <= 1
    assert len(circular) == len(set(circular))


def test_a_site_written_in_something_that_is_not_iupac_is_refused():
    with pytest.raises(RestrictionError, match="not a recognition site"):
        Enzyme("MadeUp", "GGZZCC", 1).pattern()


def test_empty_recognition_site_is_refused():
    with pytest.raises(RestrictionError, match="empty recognition site"):
        Enzyme("MadeUp", "", 0).pattern()


def test_cut_coordinate_outside_site_is_refused():
    with pytest.raises(RestrictionError, match="outside its"):
        Enzyme("MadeUp", "GAATTC", 7).pattern()


# ── Fragment sizes ─────────────────────────────────────────────────────────


def test_the_fragment_holding_a_random_base_is_bigger_than_the_average_one():
    """The distinction that decides whether an inverse PCR is the size planned.

    A long fragment covers more bases, so a randomly chosen site — which is
    what an insertion is — falls in one more often. Quoting the plain average
    is how somebody chooses an enzyme and gets twice the product they expected.
    """
    measured = fragment_sizes(puc19(), BY_NAME["Sau3AI"], circular=True)
    assert measured.mean_at_a_random_base > measured.mean
    # And on a real plasmid the difference is not a rounding error.
    assert measured.mean_at_a_random_base > 2 * measured.mean


def test_a_rarer_cutter_gives_larger_fragments():
    frequent = fragment_sizes(puc19(), BY_NAME["Sau3AI"], circular=True)
    rare = fragment_sizes(puc19(), BY_NAME["HaeIII"], circular=True)
    assert frequent.cuts > rare.cuts
    assert frequent.median < rare.median


def test_one_cut_in_a_circle_gives_one_fragment_the_size_of_the_circle():
    measured = fragment_sizes(puc19(), BY_NAME["EcoRI"], circular=True)
    assert measured.cuts == 1
    assert measured.median == len(puc19())


def test_an_enzyme_that_does_not_cut_has_nothing_to_measure():
    with pytest.raises(RestrictionError, match="0 time"):
        fragment_sizes("ACGT" * 100, BY_NAME["NotI"])


# ── Ranking ────────────────────────────────────────────────────────────────


def test_enzymes_that_cut_once_come_first_and_say_why():
    ranked = choose_enzyme(puc19())
    assert ranked[0].usable
    usable = [entry for entry in ranked if entry.usable]
    assert {entry.enzyme for entry in usable} >= set(POLYLINKER)
    for entry in ranked:
        assert entry.why, f"{entry.enzyme} was ranked without a reason"


def test_an_enzyme_that_cuts_several_times_is_marked_unusable_with_the_count():
    ranked = {entry.enzyme: entry for entry in choose_enzyme(puc19())}
    assert not ranked["Sau3AI"].usable
    assert "times" in ranked["Sau3AI"].why




def test_every_shipped_enzyme_has_a_site_that_parses():
    for enzyme in ENZYMES:
        enzyme.pattern()
        assert 0 <= enzyme.cuts_after <= enzyme.length


def test_nothing_can_be_ranked_against_an_empty_sequence():
    with pytest.raises(RestrictionError, match="no sequence"):
        choose_enzyme("   ")
