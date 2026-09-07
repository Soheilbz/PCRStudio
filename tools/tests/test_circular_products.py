"""A product, and a read, that go round the join rather than stopping at it.

The scan learned to look across the join first; the search did not. So a
plasmid could be told it was a circle and still never be offered a product
spanning its origin — and the origin is wherever whoever exported the file
happened to start it. The same was true of a sequencing primer: reading a
target forty bases into pUC19 was refused for want of somewhere to put a
primer, while on the molecule there are two and a half thousand bases in front
of it, written after it rather than before.
"""

from __future__ import annotations

import pathlib

import pytest

CORPUS = pathlib.Path(__file__).parent / "corpus"


def _corpus(accession: str) -> str:
    raw = (CORPUS / f"{accession}.fasta").read_text().splitlines()
    return "".join(line.strip() for line in raw if not line.startswith(">"))


PUC = _corpus("L09137.2")

#: Sizes that leave the search room to wrap without producing a product longer
#: than the plasmid, which would be a different kind of nonsense.
SIZES = {"product_min": 300, "product_max": 600}


def reverse_complement(sequence: str) -> str:
    return sequence[::-1].translate(str.maketrans("ACGT", "TGCA"))


class TestAPair:
    def _run(self, circular: bool, how_many: int = 20) -> dict:
        from pcr_tools.pipeline import run

        return run(
            {
                "template": PUC,
                "circular": circular,
                "how_many": how_many,
                "constraints": SIZES,
            }
        )

    def test_a_line_never_produces_one(self):
        """The control. Without it, the next test could be measuring nothing."""
        answer = self._run(circular=False)
        assert answer["pairs"]
        assert not any(pair["crosses_the_join"] for pair in answer["pairs"])

    def test_a_circle_does(self):
        answer = self._run(circular=True)
        wrapped = [pair for pair in answer["pairs"] if pair["crosses_the_join"]]
        assert wrapped, "a plasmid this size has products over its origin"

        for pair in wrapped:
            # The signature of a wrap, and the reason it is reported rather
            # than inferred: the right primer is at a *lower* base than the
            # left, which is true of the molecule and reads as a bug.
            assert pair["right_at"]["start"] < pair["left_at"]["start"]

    def test_the_wrapped_product_is_a_real_molecule(self):
        """Not merely a pair of coordinates that add up.

        Everything here is checkable against the plasmid itself: the primers
        sit where they are said to, and the amplicon is the sequence between
        them going the long way round.
        """
        answer = self._run(circular=True)
        wrapped = [pair for pair in answer["pairs"] if pair["crosses_the_join"]]
        assert wrapped

        doubled = PUC + PUC
        for pair in wrapped:
            left, right = pair["left"]["sequence"], pair["right"]["sequence"]
            at = pair["left_at"]["start"]

            assert PUC[at : at + len(left)] == left, "the left primer sits where it says"
            assert pair["amplicon"] in doubled, "the product exists on the circle"
            assert pair["amplicon"].startswith(left)
            assert pair["amplicon"].endswith(reverse_complement(right))
            assert len(pair["amplicon"]) == pair["product_size"]

    def test_no_pair_is_offered_twice(self):
        """The search runs against the sequence with its own head repeated.

        A pair found entirely inside that repeat is the same design as one near
        the origin, found a second time in the copy. Two identical designs
        offered as alternatives is worse than one.
        """
        answer = self._run(circular=True)
        seen = [(p["left"]["sequence"], p["right"]["sequence"]) for p in answer["pairs"]]
        assert len(seen) == len(set(seen))

        for pair in answer["pairs"]:
            assert pair["left_at"]["start"] < len(PUC), (
                "a coordinate past the end of the plasmid is one from the repeat"
            )

    def test_a_circle_no_longer_than_its_product_is_not_wrapped(self):
        """The guard, and what it is guarding against.

        The search runs against the sequence with enough of its own beginning
        repeated to hold the longest product asked for. If the circle were not
        longer than that product, a "product" could go round it more than once
        — which is not a band anybody gets. So a circle that short is searched
        as the line it effectively is.

        A 700-base circle with a 600-base ceiling *is* wrapped, and correctly:
        a product from base 690 round to 590 is 600 bases and passes the origin
        exactly once. The first version of this test asserted otherwise and was
        wrong about the chemistry rather than about the code.
        """
        from pcr_tools.pipeline import run

        answer = run(
            {
                "template": PUC[:500],
                "circular": True,
                "how_many": 3,
                "constraints": {"product_min": 300, "product_max": 600},
            }
        )
        assert not any(pair["crosses_the_join"] for pair in answer["pairs"])

    def test_circular_target_coordinates_cannot_start_in_search_scaffolding(self):
        """The repeated head is internal Primer3 scaffolding, not user coordinates."""
        from pcr_tools.pipeline import run

        with pytest.raises(ValueError, match="canonical template frame"):
            run(
                {
                    "template": PUC,
                    "circular": True,
                    "target_start": len(PUC),
                    "target_length": 10,
                    "constraints": SIZES,
                }
            )

    def test_circular_target_cannot_span_more_than_one_turn(self):
        from pcr_tools.pipeline import run

        with pytest.raises(ValueError, match="more than one traversal"):
            run(
                {
                    "template": PUC,
                    "circular": True,
                    "target_start": len(PUC) - 5,
                    "target_length": len(PUC) + 1,
                    "constraints": SIZES,
                }
            )

    def test_circular_excluded_coordinates_cannot_start_in_search_scaffolding(self):
        from pcr_tools.pipeline import run

        with pytest.raises(ValueError, match="canonical template frame"):
            run(
                {
                    "template": PUC,
                    "circular": True,
                    "excluded": [[len(PUC), 5]],
                    "constraints": SIZES,
                }
            )


class TestARead:
    def _run(self, circular: bool, target_start: int = 40) -> dict:
        from pcr_tools.single import run

        return run(
            {
                "template": PUC,
                "target_start": target_start,
                "target_length": 200,
                "direction": "forward",
                "how_many": 3,
                "circular": circular,
            }
        )

    def test_a_target_at_the_origin_is_unreachable_on_a_line(self):
        """Which is true of the file and false of the molecule."""
        from pcr_tools.single import SinglePrimerError

        with pytest.raises(SinglePrimerError, match="too close to that end"):
            self._run(circular=False)

    def test_and_reachable_on_a_circle(self):
        answer = self._run(circular=True)
        assert answer["primers"], "there are two and a half thousand bases in front of it"
        assert all(primer["wrapped_to_reach"] for primer in answer["primers"])

    def test_the_wrapped_primer_sits_where_it_says_and_reaches_what_it_says(self):
        """Both numbers are checkable against the plasmid.

        The distance especially: a primer at base 2657 reading a target at base
        40 is either fifty bases away round the join or two and a half thousand
        the other way, and only one of those is what the polymerase does.
        """
        answer = self._run(circular=True)
        for primer in answer["primers"]:
            at, sequence = primer["at"], primer["sequence"]
            assert PUC[at : at + len(sequence)] == sequence

            three_prime = at + len(sequence) - 1
            assert primer["reaches"] == (40 - three_prime) % len(PUC)

    def test_a_target_in_the_middle_needs_no_wrap(self):
        """The flag has to be false when nothing wrapped, or it says nothing."""
        answer = self._run(circular=True, target_start=1200)
        assert answer["primers"]
        assert not any(primer["wrapped_to_reach"] for primer in answer["primers"])
