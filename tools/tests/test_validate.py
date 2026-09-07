"""Checking a pair somebody already has.

The question this answers is not the one a design tool is usually asked. The
primers come from a paper or a predecessor's notebook, nobody is going to
redesign them, and somebody is about to spend a week on them.

Two behaviours carry most of the weight and both are tested from several
directions.

It refuses to guess where a pair sits. A primer against the wrong template
looks exactly like a primer against the right one until the reaction fails, so
"not in this template" is an answer rather than a low score — and so is "in it
twice".

And it does not call anything bad. Every measurement is reported beside the
window a designed primer would have been held to, and a primer outside that
window is outside a window chosen for a different reaction. The M13 pair, which
half the world uses, sits outside the default window on both primers.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.thermo import reverse_complement
from pcr_tools.validate import ValidationError, place, run

#: The universal M13 pair, as it is sold and published.
M13_FORWARD = "GTAAAACGACGGCCAGT"
M13_REVERSE = "CAGGAAACAGCTATGAC"


def puc19() -> str:
    return record("L09137.2").fasta()


def checked(**overrides):
    request = {"template": puc19(), "left": M13_FORWARD, "right": M13_REVERSE}
    request.update(overrides)
    return run(request)


# ── Where the pair sits ────────────────────────────────────────────────────


def test_a_primer_is_found_on_whichever_strand_it_is_on():
    """A reverse primer is written as it would be ordered, so it appears in the
    template only as its own complement."""
    sequence = record("L09137.2").sequence()
    assert place(M13_FORWARD, sequence, "left").orientation == "forward"
    assert place(M13_REVERSE, sequence, "right").orientation == "reverse"


def test_a_primer_that_is_not_there_is_said_so_rather_than_scored_low():
    """The failure this exists to catch.

    A primer against the wrong template measures exactly as well as one against
    the right template — same melting temperature, same hairpin, same
    everything — right up until the reaction produces nothing.
    """
    with pytest.raises(ValidationError, match="not in this template"):
        checked(left="ACGTACGTACGTACGTACGT")


def test_the_refusal_names_the_likeliest_cause():
    """A tail is the commonest reason a real primer is not in its own template."""
    with pytest.raises(ValidationError, match="tail"):
        checked(left="ACGTACGTACGTACGTACGT")


def test_a_primer_in_two_places_is_reported_and_no_product_is_guessed():
    """Which product you would get depends on which site wins, so none is named."""
    doubled = record("L09137.2").sequence() + M13_FORWARD
    answer = run({"template": doubled, "left": M13_FORWARD, "right": M13_REVERSE})

    assert answer["primers"]["left"]["occurrences"] == 2
    assert answer["product"]["exists"] is False
    assert "2 places" in answer["product"]["note"]


def test_overlapping_matches_are_all_counted():
    """str.count misses overlaps: five As inside seven sit in three places.

    Counting non-overlapping runs reported two, and a primer that really sits
    three times would have been waved through as a single ambiguous site.
    """
    found = place("AAAAA", "AAAAAAA", "left")
    assert found.occurrences == 3
    assert found.at is None


def test_one_primer_on_its_own_is_refused():
    with pytest.raises(ValidationError, match="Both primers"):
        run({"template": puc19(), "left": M13_FORWARD})


# ── The product ────────────────────────────────────────────────────────────


def test_the_published_pair_gives_the_band_a_cloning_lab_reads():
    """103 bp across the empty pUC19 cloning site, which is the whole screen."""
    answer = checked()
    assert answer["product"]["exists"] is True
    assert 90 <= answer["product"]["size"] <= 120
    assert answer["product"]["sequence"].startswith(M13_FORWARD)
    assert answer["product"]["sequence"].endswith(reverse_complement(M13_REVERSE))


def test_two_primers_facing_the_same_way_make_no_product():
    """Both written for the same strand is a mistake somebody makes once."""
    sequence = record("L09137.2").sequence()
    other_forward = sequence[900:920]
    answer = run({"template": puc19(), "left": M13_FORWARD, "right": other_forward})

    assert answer["product"]["exists"] is False
    assert "same way" in answer["product"]["note"]


def test_which_primer_is_which_is_read_from_the_strand_not_the_label():
    """Calling one "left" does not make it the forward primer.

    Swapping the two labels changes nothing about the molecule, so the same
    product comes back — which is right, and worth pinning, because a tool that
    trusted the labels would report no product for a pair somebody happened to
    paste in the other order.
    """
    forwards = run({"template": puc19(), "left": M13_FORWARD, "right": M13_REVERSE})
    swapped = run({"template": puc19(), "left": M13_REVERSE, "right": M13_FORWARD})
    assert swapped["product"]["size"] == forwards["product"]["size"]


def test_primers_facing_away_from_each_other_are_named_as_such():
    """Not nothing: on a circle that is an inverse PCR.

    Built rather than relabelled — a genuinely outward pair needs the
    forward-reading primer downstream of the reverse-reading one.
    """
    sequence = record("L09137.2").sequence()
    outward_reverse = reverse_complement(sequence[100:120])
    answer = run({"template": puc19(), "left": M13_FORWARD, "right": outward_reverse})

    assert answer["product"]["exists"] is False
    assert "away from each other" in answer["product"]["note"]


# ── Measuring without judging ──────────────────────────────────────────────


def test_the_universal_pair_is_outside_the_default_window_and_is_not_condemned():
    """The case that shows what this is for.

    The M13 primers are 17-mers melting near 50 and 56 degrees. The default
    Standard PCR window wants 18 to 25 bases at 57 to 63. They are outside it
    on both primers, and they are also the most-used primers in molecular
    biology — so the answer has to be "outside this window, by this much"
    rather than a verdict.
    """
    answer = checked()
    outside = [
        entry["name"]
        for role in ("left", "right")
        for entry in answer["primers"][role]["checks"]
        if not entry["inside"]
    ]
    assert "Melting temperature" in outside
    # And nothing anywhere calls them bad.
    assert "score" not in answer
    assert "not ranked" in answer["note"] or "not a choice" in answer["note"]


def test_how_far_outside_is_reported_not_just_that_it_is():
    answer = checked()
    tm = next(
        entry
        for entry in answer["primers"]["right"]["checks"]
        if entry["name"] == "Melting temperature"
    )
    assert tm["inside"] is False
    assert tm["off_by"] > 0


def test_a_window_the_pair_does_fit_is_reported_as_fitting():
    """Given the window these primers were actually made for."""
    answer = checked(constraints={"length_min": 17, "tm_min": 48.0, "tm_opt": 53.0, "tm_max": 60.0})
    lengths = [
        entry
        for role in ("left", "right")
        for entry in answer["primers"][role]["checks"]
        if entry["name"] in {"Length", "Melting temperature"}
    ]
    assert all(entry["inside"] for entry in lengths)


# ── The rest of what a designed pair gets ──────────────────────────────────


def test_a_background_is_scanned_when_one_is_given_and_said_so_when_not():
    without = checked()
    assert without["off_targets"]["checked"] is False

    with_background = checked(background=">bg\n" + record("L09137.2").sequence())
    assert with_background["off_targets"]["checked"] is True


def test_existing_pair_checker_reports_the_specificity_v5_mismatch_budget():
    answer = checked(
        background=">bg\n" + record("L09137.2").sequence(),
        max_mismatches=1,
    )

    assert answer["off_targets"]["max_mismatches"] == 1
    assert answer["off_targets"]["method"]["version"] == 5


@pytest.mark.parametrize("field", ["max_mismatches"])
@pytest.mark.parametrize("bad", [True, 7.5, "7"])
def test_existing_pair_checker_does_not_coerce_discrete_specificity_controls(field, bad):
    with pytest.raises(ValueError, match="must be an integer"):
        checked(background=">bg\n" + record("L09137.2").sequence(), **{field: bad})


def test_existing_pair_checker_rejects_non_text_request_fields():
    with pytest.raises(ValueError, match="`left` must be text"):
        checked(left=123)
    with pytest.raises(ValueError, match="`background` must be text"):
        checked(background={"sequence": "ACGT"})


@pytest.mark.parametrize(
    ("field", "bad", "message"),
    [
        ("max_mismatches", -1, "at least 0"),
        ("max_mismatches", 21, "at most 20"),
    ],
)
def test_existing_pair_checker_validates_specificity_controls_without_background(
    field, bad, message
):
    with pytest.raises(ValueError, match=message):
        checked(**{field: bad})
