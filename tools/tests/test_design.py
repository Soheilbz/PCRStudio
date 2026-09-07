"""What the design layer promises.

The template is generated from a fixed seed so the assertions are about
behaviour rather than about one lucky sequence.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from typing import Any

import pytest

from pcr_tools.design import Constraints, design
from pcr_tools.thermo import DEFAULT_CONDITIONS, SequenceError, pair_dimer


def a_template(length: int = 900, seed: int = 7) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


TEMPLATE = a_template()
TARGET_START, TARGET_LENGTH = 400, 100


def test_shared_settings_do_not_coerce_malformed_integer_inputs():
    from pcr_tools.settings import excluded_from, how_many_from

    with pytest.raises(ValueError, match=r"how_many.*integer"):
        how_many_from({"how_many": 3.9}, 5)
    with pytest.raises(ValueError, match=r"how_many.*integer"):
        how_many_from({"how_many": True}, 5)
    with pytest.raises(ValueError, match=r"excluded start.*integer"):
        excluded_from({"excluded": [[1.5, 10]]})
    with pytest.raises(ValueError, match=r"excluded.*list"):
        excluded_from({"excluded": "0,10"})


class TestDesign:
    def test_it_finds_pairs_that_flank_the_target(self):
        result = design(
            TEMPLATE, target_start=TARGET_START, target_length=TARGET_LENGTH, how_many=3
        )
        assert result.pairs, result.considered

        for pair in result.pairs:
            left_end = pair.left_at.start + pair.left_at.length
            assert left_end <= TARGET_START, "the left primer must sit before the target"
            assert pair.right_at.start >= TARGET_START + TARGET_LENGTH, (
                "the right primer must sit after the target"
            )

    def test_every_pair_returned_is_a_different_design(self):
        # Primer3 will happily return the same pair shifted by a base. Five
        # options that are one option is worse than one option, because it
        # looks like a choice.
        result = design(
            TEMPLATE, target_start=TARGET_START, target_length=TARGET_LENGTH, how_many=5
        )
        assert len(result.pairs) > 1

        ends = [(p.left_at.start + p.left_at.length, p.right_at.start) for p in result.pairs]
        assert len(set(ends)) == len(ends)
        for i, (left_a, right_a) in enumerate(ends):
            for left_b, right_b in ends[i + 1 :]:
                assert abs(left_a - left_b) >= 5 or abs(right_a - right_b) >= 5

    def test_the_pairs_honour_the_constraints_they_were_given(self):
        limits = Constraints(tm_min=58.0, tm_max=62.0, product_min=150, product_max=250)
        result = design(
            TEMPLATE,
            target_start=TARGET_START,
            target_length=TARGET_LENGTH,
            constraints=limits,
            how_many=3,
        )
        assert result.pairs, result.considered

        for pair in result.pairs:
            assert limits.product_min <= pair.product_size <= limits.product_max
            for oligo in (pair.left, pair.right):
                assert limits.tm_min <= oligo.tm <= limits.tm_max
                assert limits.length_min <= oligo.length <= limits.length_max
            assert pair.tm_difference <= limits.tm_pair_max_difference

    def test_constraints_that_contradict_each_other_are_refused_by_name(self):
        # Primer3 raises for this rather than returning nothing, and an
        # exception out of a subprocess is a far worse answer than a sentence.
        with pytest.raises(ValueError, match="cannot hold a primer"):
            design(TEMPLATE, constraints=Constraints(product_min=10, product_max=20))

        with pytest.raises(ValueError, match="melting temperature"):
            design(TEMPLATE, constraints=Constraints(tm_min=70.0, tm_max=60.0))

    def test_constraints_nothing_on_this_template_meets_come_back_empty(self):
        # Satisfiable in principle, unsatisfiable here: no 25-mer in this
        # sequence melts at 80 C. That is a different answer from "refused",
        # and Primer3's accounting is what says which.
        result = design(
            TEMPLATE,
            target_start=TARGET_START,
            target_length=TARGET_LENGTH,
            constraints=Constraints(tm_min=78.0, tm_opt=80.0, tm_max=85.0),
        )
        assert result.pairs == []
        assert "considered" in result.considered["left"]

    def test_a_target_outside_the_template_is_refused(self):
        with pytest.raises(ValueError, match="outside a template"):
            design(TEMPLATE, target_start=5000, target_length=10)

    def test_a_protein_sequence_is_refused_as_a_template(self):
        with pytest.raises(SequenceError, match="template"):
            design("MKVLAAGIVGL", target_start=0, target_length=2)

    def test_alignment_punctuation_is_refused_in_direct_design_calls(self):
        with pytest.raises(SequenceError, match="formatting symbols"):
            design("ACGT-ACGT")

    def test_gc_bounds_outside_0_to_100_are_refused(self):
        # GC content is a percentage, so the window has to sit inside 0 to 100.
        # The old check read as `not (0 <= gc_min) and (gc_max <= 100)`, which
        # refused a minimum below zero but let a maximum of 150 sail through
        # to Primer3.
        with pytest.raises(ValueError, match="between 0 and 100"):
            Constraints(gc_min=10.0, gc_max=150.0).validate()

        with pytest.raises(ValueError, match="between 0 and 100"):
            Constraints(gc_min=-5.0, gc_max=80.0).validate()

        Constraints(gc_min=20.0, gc_max=80.0).validate()

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 10**1000, True])
    def test_nonfinite_or_boolean_constraints_are_refused(self, value):
        with pytest.raises(ValueError, match="finite"):
            Constraints(tm_min=value).validate()

    @pytest.mark.parametrize(
        "field",
        [
            "length_min",
            "length_opt",
            "length_max",
            "product_min",
            "product_max",
            "max_poly_x",
            "min_three_prime_distance",
            "gc_clamp",
            "max_end_gc",
        ],
    )
    def test_count_and_length_constraints_reject_fractional_values(self, field):
        with pytest.raises(ValueError, match=f"constraint `{field}` must be an integer"):
            Constraints(**{field: 3.5}).validate()


class TestCommandLine:
    """The interface Rust actually calls."""

    def run(self, command: str, payload: dict) -> tuple[int, dict]:
        env = {**os.environ, "PCRSTUDIO_ALLOW_LEGACY_IPC": "1"}
        finished = subprocess.run(
            [sys.executable, "-m", "pcr_tools", command],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
        )
        return finished.returncode, json.loads(finished.stdout)

    def test_thermo_answers_with_one_report_per_oligo(self):
        code, answer = self.run("thermo", {"sequences": ["GTAAAACGACGGCCAGT"]})
        assert code == 0
        assert len(answer["oligos"]) == 1
        assert answer["oligos"][0]["sequence"] == "GTAAAACGACGGCCAGT"

    def test_two_oligos_also_get_their_cross_dimer(self):
        code, answer = self.run(
            "thermo", {"sequences": ["ATGCATGCATGCATGCATGC", "GCATGCATGCATGCATGCAT"]}
        )
        assert code == 0
        assert answer["cross_dimer"]["found"] is True

    def test_design_answers_with_pairs(self):
        code, answer = self.run(
            "design",
            {
                "template": TEMPLATE,
                "target_start": TARGET_START,
                "target_length": TARGET_LENGTH,
                "how_many": 3,
            },
        )
        assert code == 0
        assert 0 < len(answer["pairs"]) <= 3
        assert answer["pairs"][0]["left"]["sequence"]

    def test_a_bad_request_exits_non_zero_with_a_kind_to_branch_on(self):
        code, answer = self.run("design", {"template": 42})
        assert code == 1
        assert answer["error"]["kind"] == "invalidRequest"

    def test_an_unknown_constraint_is_named(self):
        code, answer = self.run("design", {"template": TEMPLATE, "constraints": {"tm_perfect": 60}})
        assert code == 1
        assert "tm_perfect" in answer["error"]["detail"]

    def test_how_many_past_the_ceiling_is_refused_by_name(self):
        # The bare design command goes through the same clamp as the run
        # pipeline: fifty is the ceiling everywhere. It used to be honoured
        # literally, which asked Primer3 for four times as many candidates and
        # made one form field a denial of service.
        code, answer = self.run(
            "design",
            {
                "template": TEMPLATE,
                "target_start": TARGET_START,
                "target_length": TARGET_LENGTH,
                "how_many": 500,
            },
        )
        assert code == 1
        assert answer["error"]["kind"] == "invalidRequest"
        assert "50" in answer["error"]["detail"]

    def test_a_how_many_that_is_not_a_number_is_refused(self):
        code, answer = self.run(
            "design",
            {
                "template": TEMPLATE,
                "target_start": TARGET_START,
                "target_length": TARGET_LENGTH,
                "how_many": "a handful",
            },
        )
        assert code == 1
        assert answer["error"]["kind"] == "invalidRequest"

    def test_an_oversize_template_is_refused_with_the_limit(self):
        code, answer = self.run("design", {"template": "ACGT" * 1_000_001})
        assert code == 1
        assert answer["error"]["kind"] == "invalidRequest"
        assert "4,000,000" in answer["error"]["detail"]

    def test_an_oversize_oligo_is_refused_with_the_limit(self):
        code, answer = self.run("thermo", {"sequences": ["ACGT" * 1_000_001]})
        assert code == 1
        assert answer["error"]["kind"] == "invalidRequest"
        assert "4,000,000" in answer["error"]["detail"]

    def test_unknown_conditions_are_named_as_a_bad_request(self):
        # Used to reach analyse(**conditions) and come back as toolFailed,
        # which told a form nothing it could act on.
        code, answer = self.run(
            "thermo",
            {
                "sequences": ["GTAAAACGACGGCCAGT"],
                "conditions": {"mg_conc": 2},
            },
        )
        assert code == 1
        assert answer["error"]["kind"] == "invalidRequest"
        assert "mg_conc" in answer["error"]["detail"]


class TestEndStabilityCeiling:
    """The 3' anchor ceiling: sent only when asked for, honoured when sent."""

    def test_unset_sends_nothing_so_existing_callers_do_not_move(self):
        # The whole point of the None default: Primer3 applies its own
        # guidance, and a caller that never heard of the field gets exactly
        # the settings dict it always got.
        settings = Constraints().to_primer3(DEFAULT_CONDITIONS, how_many=5)
        assert "PRIMER_MAX_END_STABILITY" not in settings

    def test_a_set_ceiling_reaches_the_settings_dict(self):
        settings = Constraints(max_end_stability=5.0).to_primer3(DEFAULT_CONDITIONS, how_many=5)
        assert settings["PRIMER_MAX_END_STABILITY"] == 5.0

    def test_a_negative_ceiling_is_refused(self):
        # The number is a magnitude of grip, not a signed energy: negative
        # would read as stronger-than-nothing, which is not a setting.
        with pytest.raises(ValueError, match="below nothing"):
            Constraints(max_end_stability=-1.0).validate()

    def test_a_strict_ceiling_actually_stops_the_search(self):
        """Not just the setting -- the search has to act on it.

        At a ceiling of effectively zero no primer's last five bases bind
        weakly enough, and Primer3 says so in its own accounting rather than
        merely coming back empty.
        """
        result = design(TEMPLATE, target_start=TARGET_START, target_length=TARGET_LENGTH)
        assert result.pairs, "the template must have primers without the ceiling"

        strict = design(
            TEMPLATE,
            target_start=TARGET_START,
            target_length=TARGET_LENGTH,
            constraints=Constraints(max_end_stability=0.001),
        )
        assert strict.pairs == []
        assert "stability" in strict.considered.get("left", ""), (
            "the refusal should name 3' stability as what bound: "
            + strict.considered.get("left", "")
        )


class TestRankingWeights:
    """Purpose weights travel into the search, and cannot masquerade as limits."""

    def test_weights_reach_primer3s_settings(self, monkeypatch):
        import primer3

        captured: dict[str, Any] = {}
        real = primer3.design_primers

        def watched(seq_args, global_args):
            captured.update(global_args)
            return real(seq_args, global_args)

        monkeypatch.setattr(primer3, "design_primers", watched)

        design(TEMPLATE, how_many=1, weights={"PRIMER_WT_TM_GT": 0.5})
        assert captured["PRIMER_WT_TM_GT"] == 0.5

    def test_unverified_primer3_weight_is_rejected_instead_of_ignored(self):
        with pytest.raises(ValueError, match="not supported by this adapter"):
            design(TEMPLATE, how_many=1, weights={"PRIMER_WT_PRODUCT_SIZE": 0.5})

    def test_no_weights_means_no_extra_settings(self, monkeypatch):
        import primer3

        captured: dict[str, Any] = {}
        real = primer3.design_primers

        def watched(seq_args, global_args):
            captured.update(global_args)
            return real(seq_args, global_args)

        monkeypatch.setattr(primer3, "design_primers", watched)

        design(TEMPLATE, how_many=1)
        assert not [key for key in captured if key.startswith("PRIMER_WT_")]

    def test_pair_task_and_template_alignment_are_explicit(self, monkeypatch):
        import primer3

        captured: dict[str, Any] = {}
        real = primer3.design_primers

        def watched(seq_args, global_args):
            captured.update(global_args)
            return real(seq_args, global_args)

        monkeypatch.setattr(primer3, "design_primers", watched)

        design(TEMPLATE, how_many=1)

        assert captured["PRIMER_TASK"] == "generic"
        assert captured["PRIMER_PICK_LEFT_PRIMER"] == 1
        assert captured["PRIMER_PICK_INTERNAL_OLIGO"] == 0
        assert captured["PRIMER_PICK_RIGHT_PRIMER"] == 1
        assert captured["PRIMER_PICK_ANYWAY"] == 0
        assert captured["PRIMER_THERMODYNAMIC_TEMPLATE_ALIGNMENT"] == 0


    def test_a_negative_weight_is_refused_before_it_reaches_primer3(self):
        # Measured: Primer3's core dies on an assertion (`sum >= 0.0`) for a
        # negative weight instead of reporting a refusal. Caught here instead.
        with pytest.raises(ValueError, match="below zero"):
            design(TEMPLATE, how_many=1, weights={"PRIMER_WT_TM_GT": -1.0})

    def test_something_that_is_not_a_weight_cannot_travel_as_one(self):
        # Weights bias ranking. A key without the WT prefix could rename a
        # hard limit, which would turn a hint into a silent constraint.
        with pytest.raises(ValueError, match="PRIMER_WT_"):
            design(TEMPLATE, how_many=1, weights={"PRIMER_MAX_SIZE": 10})


class TestStructureCeilings:
    """Every structure limit follows the window, including the pair's own.

    A hairpin, a self-dimer and a primer-dimer are the same argument: they
    matter only while the primers are annealing. Three of the five followed
    `tm_min` and two were left at Primer3's fixed 47, which only agreed with
    the rest at the default window.
    """
