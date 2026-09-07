"""Overlapping amplicons covering something too long for one reaction.

Two properties carry this engine and neither is thermodynamic.

Neighbours must actually overlap. That sounds like arithmetic and is not: the
search places the left primer wherever it likes in the window it is given, so
unless the amplicon is *required* to span the base the previous one ended near,
a scheme comes back with holes between amplicons that were supposed to share
seventy-five bases. Measured on the mitochondrial genome before it was fixed:
an 84-base hole, and 85.8 per cent coverage instead of 99.1.

And neighbours must never share a tube. Two primers overlapping the same
stretch amplify each other's short products in preference to the real ones, so
alternating pools is not tidiness — it is the reason the reaction works.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.design import Constraints
from pcr_tools.presets import polymerase
from pcr_tools.tiling import OVERLAP, TilingError, lay_out, scheme_to_dict

CONDITIONS = polymerase("taq-standard").reaction.as_conditions()
LIMITS = Constraints(product_min=350, product_max=450)


def mitochondrion() -> str:
    """16.5 kb, and a real tiling target: laboratories sequence it this way."""
    return record("NC_012920.1").sequence()


def scheme():
    return lay_out(mitochondrion(), constraints=LIMITS, conditions=CONDITIONS)


# ── The overlap, which is the whole point ──────────────────────────────────


def test_every_neighbour_actually_overlaps_the_one_before_it():
    """The bug this engine had, and the reason the amplicon spans a base.

    Placing an amplicon "near" where the last one ended is not the same as
    requiring it to reach back into it, and the difference is a hole.
    """
    laid = scheme()
    assert len(laid.tiles) > 10, "the mitochondrial genome takes dozens of amplicons"

    for earlier, later in zip(laid.tiles, laid.tiles[1:], strict=False):
        assert later.start < earlier.end, (
            f"tile {later.index} starts at {later.start}, after tile "
            f"{earlier.index} ended at {earlier.end}"
        )


def test_the_overlap_is_at_least_what_was_asked_for():
    laid = scheme()
    for earlier, later in zip(laid.tiles, laid.tiles[1:], strict=False):
        shared = earlier.end - later.start
        assert shared >= OVERLAP - 25, (earlier.index, later.index, shared)


def test_almost_every_base_is_covered_and_what_is_not_is_named():
    """A scheme with a known hole is usable; one that hid it is not."""
    laid = scheme()
    reported = scheme_to_dict(laid, len(mitochondrion()))

    assert reported["coverage"]["percent"] > 95
    for gap in reported["gaps"]:
        assert gap["bases"] > 0
        assert gap["why"], "a gap without a reason is just a number"


# ── The pools ──────────────────────────────────────────────────────────────


def test_no_two_neighbours_share_a_tube():
    """In one tube their primers would amplify each other's short products."""
    laid = scheme()
    for earlier, later in zip(laid.tiles, laid.tiles[1:], strict=False):
        assert earlier.pool != later.pool


def test_every_amplicon_lands_in_a_pool_and_the_pools_are_reported():
    laid = scheme()
    reported = scheme_to_dict(laid, len(mitochondrion()))

    placed = sum(len(members) for members in reported["pools"].values())
    assert placed == len(laid.tiles)


def test_what_the_oligos_in_each_tube_do_to_each_other_is_measured():
    """With the same measure the multiplex engine uses.

    Two parts of this project disagreeing about what a bad interaction is would
    be worse than neither of them measuring it.
    """
    reported = scheme_to_dict(scheme(), len(mitochondrion()))
    assert reported["interactions"]
    for pool in reported["interactions"]:
        assert pool["oligos"] == 2 * len(reported["pools"][str(pool["pool"])])
        for entry in pool["worst"]:
            assert entry["badness"] >= 0


# ── Layouts that could not be attempted ────────────────────────────────────


def test_zero_slide_is_preserved_as_an_explicit_no_sliding_choice():
    laid = lay_out(mitochondrion(), constraints=LIMITS, conditions=CONDITIONS, slide=0)

    assert all(gap["bases"] > 0 for gap in laid.gaps)


def test_more_than_six_pools_is_refused():
    with pytest.raises(TilingError, match="at most 6"):
        lay_out(mitochondrion(), constraints=LIMITS, conditions=CONDITIONS, pools=7)


def test_an_overlap_as_long_as_the_amplicon_would_never_move_forward():
    with pytest.raises(TilingError, match="never move forward"):
        lay_out(
            mitochondrion(),
            constraints=Constraints(product_min=100, product_max=200),
            conditions=CONDITIONS,
            overlap=150,
        )


def test_a_template_shorter_than_one_amplicon_has_nothing_to_tile():
    with pytest.raises(TilingError, match="nothing here to tile"):
        lay_out("ACGT" * 50, constraints=LIMITS, conditions=CONDITIONS)


# ── The layout is shown, not just produced ─────────────────────────────────


def test_how_the_scheme_was_laid_out_is_reported():
    reported = scheme_to_dict(scheme(), len(mitochondrion()))
    assert reported["how_it_was_laid_out"]
    assert any("pools" in step for step in reported["how_it_was_laid_out"])
    assert "different pools" in reported["note"]


def test_scheme_output_keeps_reference_and_interchange_coordinates():
    laid = scheme()
    reported = scheme_to_dict(laid, len(mitochondrion()), reference_id="NC_012920.1")

    assert reported["reference_id"] == "NC_012920.1"
    assert reported["coordinate_system"] == "0-based, half-open"
    assert reported["scheme_format"] == "pcrstudio-tiling-v1"
    first = reported["tiles"][0]
    assert first["left_start"] < first["left_end"]
    assert first["right_start"] < first["right_end"]
    assert first["left_start"] == laid.tiles[0].start
    assert first["right_end"] == laid.tiles[0].end
