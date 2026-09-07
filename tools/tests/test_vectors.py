"""The primers already in the freezer, and never assuming where they sit.

A primer library is a list of sequences somebody will use without checking, so
a wrong entry is a wasted week rather than a bug report. Nothing here is
shipped on a catalogue number: every sequence is checked against a real vector
record, and the tests are those checks.

The other half is a refusal to assume. Plasmids are edited constantly, and a
primer sitting once in the published pUC19 may sit twice, or nowhere, in the
derivative on somebody's bench.
"""

from __future__ import annotations

from corpus import record

from pcr_tools.vectors import (
    BY_NAME,
    UNIVERSAL,
    check_against,
    partner_window,
)


def puc19() -> str:
    return record("L09137.2").sequence()


def pbr322() -> str:
    return record("J01749.1").sequence()


# ── Every shipped sequence, against a real record ──────────────────────────


def test_every_m13_primer_sits_exactly_once_in_puc19():
    """The measurement each of these is shipped on."""
    placed = {place.name: place for place in check_against(puc19())}
    for primer in UNIVERSAL:
        if primer.family != "M13/pUC":
            continue
        assert placed[primer.name].occurrences == 1, primer.name
        assert placed[primer.name].usable


def test_the_m13_forwards_and_reverses_face_each_other_across_the_cloning_site():
    """A stronger check than counting: they are where they should be.

    Ten primers each occurring once could still be ten wrong places. Ten
    occurring once, with every forward before every reverse and all of them
    inside a hundred and thirty bases, could not.
    """
    placed = [p for p in check_against(puc19()) if p.usable and p.family == "M13/pUC"]
    forwards = [p.at for p in placed if p.reads == "forward"]
    reverses = [p.at for p in placed if p.reads == "reverse"]

    assert forwards and reverses
    assert max(forwards) < min(reverses), "the forwards must lie before the reverses"
    assert max(reverses) - min(forwards) < 130


def test_none_of_them_is_in_pbr322():
    """Which is right: pBR322 carries no lac region and no M13 sites.

    A library that reported a hit here would be reporting a coincidence, and
    somebody would design a screen around it.
    """
    assert [place for place in check_against(pbr322()) if place.usable] == []


def test_the_promoter_primers_are_absent_from_both_and_say_so():
    """They belong to pET, pBluescript and pGEM, not to these two."""
    for vector in (puc19(), pbr322()):
        placed = {place.name: place for place in check_against(vector)}
        for primer in UNIVERSAL:
            if primer.family != "promoter":
                continue
            assert not placed[primer.name].usable
            assert "not in this vector" in placed[primer.name].why


# ── Never assuming ─────────────────────────────────────────────────────────


def test_a_primer_that_sits_twice_is_refused_with_the_count():
    """An edited plasmid is the normal case, not the exception.

    A product from a primer with two sites does not tell you which one it came
    from, so the screen it was designed for cannot be read.
    """
    primer = BY_NAME["M13 Forward (-20), 17-mer"]
    doubled = puc19() + primer.sequence

    placed = {place.name: place for place in check_against(doubled)}
    assert not placed[primer.name].usable
    assert placed[primer.name].occurrences == 2
    assert "2 places" in placed[primer.name].why


def test_a_primer_found_on_the_other_strand_still_counts():
    from pcr_tools.thermo import reverse_complement

    primer = BY_NAME["T7 promoter"]
    vector = "ACGT" * 200 + reverse_complement(primer.sequence) + "ACGT" * 200

    placed = {place.name: place for place in check_against(vector)}
    assert placed[primer.name].usable
    assert placed[primer.name].at is not None


def test_overlapping_sites_are_all_counted():
    """A site repeated end to end is several sites, not one and a bit.

    str.count reads non-overlapping runs only: five bases inside seven
    counted as two, and a primer that really sits three times would have
    been reported as sitting twice.
    """
    from pcr_tools.vectors import UniversalPrimer

    run = UniversalPrimer("homopolymer site", "AAAAA", "forward", "supplied")
    placed = check_against("AAAAAAA", primers=(run,))[0]
    assert placed.occurrences == 3
    assert "3 places" in placed.why


# ── The window a fixed primer imposes ──────────────────────────────────────


def test_a_fixed_primer_moves_the_window_rather_than_being_refused_by_it():
    """Several of these melt below the engine's whole default window.

    Designing a partner in the default 57-63 and annealing at the cool
    primer's temperature means the warm one binds everywhere; annealing at the
    warm one's means the cool one does not bind at all. Neither is a reaction.
    """
    cool = BY_NAME["M13 Reverse, 17-mer"]
    assert cool.melting_temperature() < 57.0

    window = partner_window(cool)
    assert window["tm_max"] < 57.0, "the window has to follow the primer down"
    assert window["tm_min"] < window["tm_opt"] < window["tm_max"]


def test_a_warm_fixed_primer_moves_the_window_up_instead():
    warm = BY_NAME["M13 Forward (-47), 24-mer"]
    assert warm.melting_temperature() > 63.0
    assert partner_window(warm)["tm_min"] > 63.0


def test_the_window_is_centred_on_the_primer_it_is_for():
    for primer in UNIVERSAL:
        window = partner_window(primer)
        assert window["tm_opt"] == round(primer.melting_temperature(), 1)


# ── The library itself ─────────────────────────────────────────────────────


def test_no_two_entries_share_a_name_or_a_sequence():
    """Two names for one oligo is how somebody orders it twice."""
    assert len({primer.name for primer in UNIVERSAL}) == len(UNIVERSAL)
    assert len({primer.sequence for primer in UNIVERSAL}) == len(UNIVERSAL)


def test_every_entry_is_dna_and_says_which_way_it_reads():
    for primer in UNIVERSAL:
        assert set(primer.sequence) <= set("ACGT"), primer.name
        assert primer.reads in {"forward", "reverse"}
        assert primer.note, f"{primer.name} is shipped without a word about it"
