"""A LAMP set whose numbers are not one of the three published ones.

The three sets exist because the reaction is held at one temperature and a
target's composition decides which window an oligo can reach. They are the
right default. They are not the only geometry anybody runs: a target AT-rich in
one half and GC-rich in the other fits none of them, and a kit with a different
polymerase moves the whole band. Until this the only control was which of three.

What matters as much as the adjustment is that the result says it happened. The
temperatures in a parameter set are what somebody holds a block at, and a set
reported without that flag reads as published guidance whatever was typed over
it.
"""

from __future__ import annotations

import pathlib

import pytest

from pcr_tools.loop_set import LoopSetError, run

CORPUS = pathlib.Path(__file__).parent / "corpus"


def _corpus(accession: str, start: int, length: int) -> str:
    raw = (CORPUS / f"{accession}.fasta").read_text().splitlines()
    seq = "".join(line.strip() for line in raw if not line.startswith(">"))
    return seq[start : start + length]


TP53 = _corpus("NM_000546.6", 200, 1400)


def _design(**windows) -> dict:
    request = {"template": TP53, "how_many": 2}
    if windows:
        request["windows"] = windows
    return run(request)


class TestLeavingItAlone:
    """The default has to stay the default, or the rest is a regression."""

    def test_nothing_is_overruled_and_the_published_numbers_stand(self):
        answer = _design()
        chosen = answer["parameter_set"]

        assert chosen["overruled"] == []
        assert chosen["f2_b2_span"] == [120, 180]
        assert chosen["outer_gap"] == [0, 20]
        assert chosen["middle_gap"] == [0, 100]
        assert "Adjusted here" not in chosen["why"]

    def test_the_set_is_still_chosen_from_the_template(self):
        answer = _design()
        assert "composition" in answer["parameter_set"]["chosen_from"]


class TestAdjusting:
    def test_the_geometry_can_be_changed_and_is_obeyed(self):
        """Not merely accepted: the sets that come back have to fit inside it."""
        answer = _design(f2_b2_span=[140, 170])
        assert answer["parameter_set"]["f2_b2_span"] == [140, 170]

        assert answer["sets"], "no design to check the geometry against"
        for entry in answer["sets"]:
            assert 140 <= entry["f2_b2_span"] <= 170


class TestRefusing:
    """Every mistake refused by name, rather than producing an empty result.

    The failure this prevents is the one that reads as the template's fault: a
    set nothing can satisfy comes back with no designs and a sentence about how
    few candidates each stage produced, and nothing in it points at the number
    that was typed wrong.
    """

    @pytest.mark.parametrize(
        ("windows", "expected"),
        [
            ({"outer": {"tm_min": 90}}, "40.0 to 75.0"),
            ({"outer": {"tm_min": 65, "tm_max": 60}}, "backwards"),
            ({"outer": {"length_min": 30, "length_max": 20}}, "backwards"),
            ({"f2_b2_span": [40, 90]}, "100 to 400"),
            ({"f2_b2_span": [170, 140]}, "backwards"),
            ({"gc_min": 70, "gc_max": 30}, "backwards"),
        ],
    )
    def test_a_value_it_cannot_hold(self, windows: dict, expected: str):
        with pytest.raises(LoopSetError, match=expected):
            _design(**windows)

    def test_a_misspelt_field_names_what_there_is(self):
        with pytest.raises(LoopSetError, match="tm_mn"):
            _design(outer={"tm_mn": 60})

    def test_a_misspelt_block_names_what_there_is(self):
        with pytest.raises(LoopSetError, match="loop_spam") as raised:
            _design(loop_spam=[40, 60])
        assert "loop_span" in str(raised.value), "and says what was meant"
