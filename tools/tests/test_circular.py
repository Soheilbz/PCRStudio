"""A template that comes back round, and the two things that depend on it.

A plasmid has no ends, but the string somebody pastes does. Everything that
walks that string treats the first base as a boundary, and the first base is
wherever the file happens to begin — so which primers a scan can see, and which
stretch a tiling scheme leaves uncovered, depend on an arbitrary choice made by
whoever exported the sequence.
"""

from __future__ import annotations

import pathlib
import random
import typing

import pytest

from pcr_tools import screen
from pcr_tools.presets import polymerase
from pcr_tools.thermo import reverse_complement

CORPUS = pathlib.Path(__file__).parent / "corpus"


def _puc() -> str:
    raw = (CORPUS / "L09137.2.fasta").read_text().splitlines()
    return "".join(line.strip() for line in raw if not line.startswith(">"))


PUC = _puc()


def test_a_primer_across_the_join_is_invisible_on_a_line_and_found_on_a_circle():
    """The whole reason the flag exists.

    The primer here is built to straddle the join: half of it is the last bases
    of the file and half is the first. On a linear scan it matches nothing, and
    a design that used it would be reported as sitting nowhere in the plasmid
    it came from.
    """
    across = PUC[-12:] + PUC[:12]
    reaction = polymerase("taq-standard").reaction

    linear, _, fold = screen.contigs_for({}, template=PUC, name="pUC19")
    assert fold is None
    flat = screen.oligos({"probe": across}, linear, reaction=reaction, fold_at=fold)
    assert flat["site_count"] == 0, "a linear scan cannot see across the join"

    circle, _, fold = screen.contigs_for({"circular": True}, template=PUC, name="pUC19")
    assert fold == len(PUC)
    found = screen.oligos({"probe": across}, circle, reaction=reaction, fold_at=fold)
    assert found["site_count"] == 1, "on a circle it sits in exactly one place"


def test_a_primer_at_the_origin_is_not_counted_twice():
    """The other half, and the one that would invent a second band.

    Closing the circle means repeating its first bases at its end. A primer
    that sits inside that repeat without crossing the join would be found once
    where it really is and once in the copy — and two sites facing each other
    is how this scan reports an unwanted product.
    """
    at_the_start = PUC[:22]
    reaction = polymerase("taq-standard").reaction

    contigs, _, fold = screen.contigs_for({"circular": True}, template=PUC, name="pUC19")
    found = screen.oligos({"probe": at_the_start}, contigs, reaction=reaction, fold_at=fold)
    assert found["site_count"] == 1, "one primer, one place, however the string was cut"


def test_a_circle_shorter_than_the_join_window_is_left_alone():
    """No wrap where a wrap would overlap itself.

    Repeating sixty bases of a fifty-base circle would put the whole sequence
    in twice, and every primer on it would appear to sit in two places.
    """
    short = PUC[:50]
    contigs, _, fold = screen.contigs_for({"circular": True}, template=short, name="tiny")
    assert fold is None
    assert len(contigs[0].sequence) == len(short)


def test_a_circular_screen_finds_and_can_excuse_a_product_over_the_origin():
    generator = random.Random(31)
    circle = "".join(generator.choices("ACGT", k=240))
    left_start = 180
    right_start = 20
    left = circle[left_start : left_start + 20]
    right = reverse_complement(circle[right_start : right_start + 20])
    product_size = 100
    intended = "".join(
        circle[(left_start + offset) % len(circle)] for offset in range(product_size)
    )
    reaction = polymerase("taq-standard").reaction

    contigs, _, fold = screen.contigs_for({"circular": True}, template=circle, name="circle")
    result = screen.oligos(
        {"left": left, "right": right},
        contigs,
        reaction=reaction,
        max_product=120,
        intended_products=[intended],
        fold_at=fold,
    )

    assert fold == len(circle)
    assert result["background_bases"] == len(circle)
    assert result["product_count"] == 0


def test_a_circular_report_counts_the_real_molecule_not_the_repeated_head():
    contigs, template_only, fold = screen.contigs_for(
        {"circular": True}, template=PUC, name="pUC19"
    )

    report = screen.summary(contigs, template_only, fold_at=fold)

    assert report["bases"] == len(PUC)


class TestTiling:
    """A scheme over a circular genome has no last tile."""

    LIMITS: typing.ClassVar = {"product_min": 300, "product_max": 500}

    def _run(self, circular: bool) -> dict:
        from pcr_tools.tiling import run

        return run({"template": PUC, "circular": circular, "constraints": self.LIMITS})

    def test_a_linear_walk_leaves_the_join_uncovered(self):
        """Not a bug in the walk — a consequence of pretending a circle is a line.

        This is the assertion that makes the next one mean something: without
        it, a circular scheme covering everything could be a scheme that was
        always going to cover everything.
        """
        laid = self._run(circular=False)
        assert laid["coverage"]["percent"] < 100.0
        assert not any(tile["crosses_the_join"] for tile in laid["tiles"])

    def test_a_circular_walk_closes(self):
        laid = self._run(circular=True)
        assert laid["coverage"]["percent"] == 100.0

        closing = [tile for tile in laid["tiles"] if tile["crosses_the_join"]]
        assert len(closing) == 1, "one tile spans the join, and only one"
        # It really does wrap: it ends past the last base of the sequence.
        assert closing[0]["end"] > len(PUC)
        assert closing[0]["start"] < len(PUC)

    def test_closing_costs_at_most_one_more_amplicon_and_says_so(self):
        """What closing actually costs, measured rather than assumed.

        The first version of this test asserted one extra amplicon, and on
        pUC19 there is none: the last tile was going to be placed anyway and
        now it wraps instead of stopping short. That is the point of stopping
        the walk when it passes the first tile's start rather than at the end
        of the string — the earlier version placed a ninth tile over ground the
        eighth already covered, and coverage read 100% either way, so the
        redundant pair was an order somebody would never have needed.
        """
        linear = self._run(circular=False)
        circle = self._run(circular=True)
        assert len(circle["tiles"]) <= len(linear["tiles"]) + 1

        # And no tile is laid over ground another one already covers entirely.
        spans = [(tile["start"], tile["end"]) for tile in circle["tiles"]]
        for index, (start, end) in enumerate(spans):
            others = spans[:index] + spans[index + 1 :]
            assert not any(other[0] <= start and end <= other[1] for other in others)

        said = " ".join(circle["how_it_was_laid_out"])
        assert "circle" in said.lower()
        assert "join" in said.lower()


@pytest.mark.parametrize("circular", [False, True])
def test_the_flag_never_changes_how_many_bases_are_claimed(circular: bool):
    """Coverage is a fraction of the plasmid, not of the string that was walked.

    The circular walk searches a template with its own head repeated on the
    end. If that repeat leaked into the denominator, a scheme covering the
    whole plasmid would report about 84%.
    """
    from pcr_tools.tiling import run

    laid = run(
        {
            "template": PUC,
            "circular": circular,
            "constraints": {"product_min": 300, "product_max": 500},
        }
    )
    assert laid["coverage"]["of"] == len(PUC)
