"""One primer, and the placement that is the whole design.

A sequencing primer has no partner, so every pair-level idea is gone and what
is left is where it sits. That makes the coordinates the thing most worth
testing: a primer that is beautiful by every thermodynamic measure and thirty
bases from its target is a wasted reaction, and an off-by-one in a reverse
primer's position reads exactly like a correct one until somebody orders it.

So every position claimed here is checked against the sequence rather than
against the arithmetic that produced it.
"""

from __future__ import annotations

import itertools

import pytest
from corpus import record

from pcr_tools.design import Constraints
from pcr_tools.presets import polymerase
from pcr_tools.single import (
    ACCURACY,
    DEAD_ZONE,
    READ_LENGTH,
    SinglePrimerError,
    candidate_to_dict,
    design,
    race_adapter,
    race_direction,
    run,
    sequencing_context,
    sequencing_protocol,
    window_for,
)
from pcr_tools.thermo import reverse_complement

CONDITIONS = polymerase("taq-standard").reaction.as_conditions()


RACE_CONTEXT = {
    "race_direction": "5prime",
    "race_adapter": "generacer-kit-25-0355-vl",
    "race_substrate": "total-rna",
    "race_preparation": "test-RACE-SOP",
    "race_round": "primary",
}


def test_named_bigdye_overlay_is_explicit_and_versioned():
    protocol = sequencing_protocol("bigdye-v3-1")
    assert protocol is not None
    assert protocol["source_url"].endswith("product/4337455")
    assert protocol["primer_input_pmol"] == 3.2
    assert "primer_stock_uM" not in protocol
    assert protocol["source_publication"] == "MAN1000355"
    assert protocol["source_revision"] == "B"
    assert protocol["source_revision_date"] == "2026-07-17"
    assert protocol["cycling"]["cycles"] == 25
    assert protocol["cycling"]["extend"] == {"temperature_c": 60, "seconds": 240}


def test_unselected_sequencing_overlay_is_absent():
    assert sequencing_protocol(None) is None


def test_race_requires_substrate_preparation_round_and_explicit_adapter():
    partner = race_adapter(
        RACE_CONTEXT["race_adapter"],
        direction=RACE_CONTEXT["race_direction"],
        round_name=RACE_CONTEXT["race_round"],
    )
    assert partner["sequence"]
    assert sequencing_context({}, assay_id="race") is None
    assert "candidate-transcript-end" in "candidate-transcript-end"
















def template() -> str:
    return record("NM_000546.6").sequence()


# ── The window ─────────────────────────────────────────────────────────────


def test_a_forward_primer_sits_before_its_target_and_a_reverse_one_after():
    forward = window_for(3000, 1200, 200, "forward")
    reverse = window_for(3000, 1200, 200, "reverse")

    assert forward.region[0] + forward.region[1] <= 1200
    assert reverse.region[0] >= 1400


def test_the_window_keeps_the_target_clear_of_the_unreadable_start():
    """The first few dozen bases of a trace come back as a smear.

    A primer placed right against its target reads the target in exactly the
    part of the trace nobody can call.
    """
    window = window_for(3000, 1200, 200, "forward")
    nearest_the_primer_may_end = window.region[0] + window.region[1]
    assert 1200 - nearest_the_primer_may_end >= DEAD_ZONE


def test_the_window_keeps_the_whole_target_inside_the_read():
    """Reaching the target's start is not enough — the read has to cover it."""
    window = window_for(3000, 1200, 200, "forward")
    furthest_the_primer_may_sit = window.region[0]
    covered = 1200 + 200 - furthest_the_primer_may_sit
    assert covered <= READ_LENGTH


def test_a_target_too_long_for_one_read_is_refused_with_the_arithmetic():
    """Two reads, or a walk. Not one primer placed optimistically."""
    with pytest.raises(SinglePrimerError, match="cannot be read in one go"):
        window_for(3000, 1000, READ_LENGTH, "forward")


def test_a_target_outside_the_template_is_refused():
    with pytest.raises(SinglePrimerError, match="not inside"):
        window_for(1000, 900, 300, "forward")


def test_a_direction_that_is_not_a_direction_is_refused():
    with pytest.raises(SinglePrimerError, match="not a direction"):
        window_for(3000, 1200, 200, "sideways")


def test_an_explicit_zero_dead_zone_is_preserved():
    window = window_for(3000, 1200, 200, "forward", dead_zone=0)

    assert window.nearest == 0


def test_a_negative_dead_zone_is_refused():
    with pytest.raises(SinglePrimerError, match="cannot be negative"):
        window_for(3000, 1200, 200, "forward", dead_zone=-1)


# ── Where the primers actually are ─────────────────────────────────────────


@pytest.mark.parametrize("direction", ["forward", "reverse"])
def test_every_primer_is_found_at_the_position_it_reports(direction: str):
    """The check that catches an off-by-one in a coordinate transform.

    Rather than trusting the arithmetic, this reads the bases at the reported
    position and requires them to be the primer — on the plus strand for a
    forward primer, and as its complement for a reverse one.
    """
    sequence = template()
    found, _, _ = design(
        sequence,
        target_start=1200,
        target_length=250,
        direction=direction,
        conditions=CONDITIONS,
        how_many=3,
    )
    assert found, f"no {direction} primer for a target with room on both sides"

    for candidate in found:
        here = sequence[candidate.at : candidate.at + candidate.length]
        expected = (
            candidate.sequence if direction == "forward" else reverse_complement(candidate.sequence)
        )
        assert here == expected, candidate


@pytest.mark.parametrize("direction", ["forward", "reverse"])
def test_every_primer_lands_inside_its_own_window(direction: str):
    sequence = template()
    found, window, _ = design(
        sequence,
        target_start=1200,
        target_length=250,
        direction=direction,
        conditions=CONDITIONS,
        how_many=3,
    )
    low, span = window.region
    for candidate in found:
        assert low <= candidate.at
        assert candidate.at + candidate.length <= low + span


@pytest.mark.parametrize("direction", ["forward", "reverse"])
def test_how_far_the_target_is_and_what_is_left_after_it(direction: str):
    """The two numbers somebody uses to decide whether one read will do."""
    found, window, _ = design(
        template(),
        target_start=1200,
        target_length=250,
        direction=direction,
        conditions=CONDITIONS,
        how_many=3,
    )
    for candidate in found:
        assert candidate.reaches >= window.nearest
        assert candidate.spare >= 0
        entry = candidate_to_dict(candidate, window, **CONDITIONS)
        assert str(candidate.reaches) in entry["note"]


# ── When it cannot be done ─────────────────────────────────────────────────


def test_a_target_too_close_to_the_end_says_to_read_the_other_way():
    """A refusal that names the way out rather than only the wall."""
    with pytest.raises(SinglePrimerError, match="other direction"):
        design(template(), target_start=20, target_length=100, conditions=CONDITIONS)


def test_reading_the_other_way_then_works():
    """Which is what makes the refusal above worth its wording."""
    found, _, _ = design(
        template(),
        target_start=20,
        target_length=100,
        direction="reverse",
        conditions=CONDITIONS,
        how_many=2,
    )
    assert found


# ── What is not here ───────────────────────────────────────────────────────


def test_nothing_about_a_pair_appears_in_a_single_primer_result():
    """There is no partner, so there is no product and nothing to match against.

    Worth pinning because the temptation to reuse the pair result shape is
    real, and a product size of zero reads as a measurement rather than as an
    absence.
    """
    found, window, _ = design(
        template(),
        target_start=1200,
        target_length=250,
        conditions=CONDITIONS,
        how_many=1,
    )
    entry = candidate_to_dict(found[0], window, **CONDITIONS)
    for absent in ("product_size", "tm_difference", "cross_dimer_dg", "right"):
        assert absent not in entry


# ── Placement is the ranking, not a tiebreak ───────────────────────────────


def test_the_best_candidate_is_not_merely_the_prettiest_oligo_in_the_window():
    """The defect this engine's own docstring existed to prevent.

    Ranking on Primer3's penalty alone finds the best oligo anywhere legal,
    which on pUC19 reading 400..454 was one sitting 372 bases from its target —
    burning 330 bases of read the user paid for, while a primer 93 bases away
    scored 0.272 against its 0.007. Both are fine oligos. Only one is the
    design, and the difference is placement.
    """
    found, window, _ = design(
        record("L09137.2").sequence(),
        target_start=400,
        target_length=54,
        direction="forward",
        conditions=CONDITIONS,
        how_many=5,
    )
    assert found

    for candidate in found:
        # Within one band of the ideal placement rather than anywhere legal.
        assert candidate.reaches < window.nearest + ACCURACY * 2, (
            f"a primer {candidate.reaches} bases from its target, when the ideal is "
            f"{window.nearest} and the window allows up to {window.furthest}"
        )


@pytest.mark.parametrize("direction", ["forward", "reverse"])
def test_no_two_candidates_are_the_same_design_nudged_along(direction: str):
    """Primer3 thins pairs by 3' end and does not thin a primer list.

    Its documentation scopes the setting to "when returning multiple primer
    pairs", and measured here a list came back with 3' ends at 307 and 308 —
    two of five options that were one design. A list of five that is really
    three is worse than a list of three, because nobody counts them.
    """
    found, _, _ = design(
        record("L09137.2").sequence(),
        target_start=400,
        target_length=54,
        direction=direction,
        conditions=CONDITIONS,
        how_many=5,
    )
    ends = [
        candidate.at + candidate.length - 1 if direction == "forward" else candidate.at
        for candidate in found
    ]
    for one, other in itertools.combinations(ends, 2):
        assert abs(one - other) >= Constraints().min_three_prime_distance, (
            f"3' ends at {one} and {other} are the same design nudged over"
        )


def test_how_far_the_search_had_to_widen_is_reported():
    """A primer found only after the band grew eightfold is a different fact.

    The person reading the result is the one who decides whether it will do, so
    the search saying how hard it had to look is part of the answer.
    """
    found, window, _ = design(
        record("L09137.2").sequence(),
        target_start=400,
        target_length=54,
        direction="forward",
        conditions=CONDITIONS,
        how_many=2,
    )
    assert window.widened == 0, "an ordinary target should not need widening"
    assert window.searched[1] > 0
    entry = candidate_to_dict(found[0], window, **CONDITIONS)
    assert entry["window"]["widened"] == 0
    assert entry["window"]["searched"] == list(window.searched)


# ── The adapter the kit supplies ───────────────────────────────────────────


def test_a_benign_gene_specific_primer_passes_the_selected_partner_screen():
    """An ordinary GSP is screened against the exact partner in its selected tube."""
    from pcr_tools.single import adapter_screen

    found, _, _ = design(
        template(),
        target_start=1200,
        target_length=250,
        conditions=CONDITIONS,
        how_many=1,
    )
    partner = race_adapter(
        "generacer-kit-25-0355-vl",
        direction="5prime",
        round_name="primary",
    )
    assert partner is not None
    out = adapter_screen(found[0].sequence, partner=partner, **CONDITIONS)
    assert out["partner"] == "GeneRacer 5′ Primer"
    assert not out["flagged"], out["note"]


def test_versioned_generacer_primary_partner_is_exact_and_provenanced():
    partner = race_adapter(
        "generacer-kit-25-0355-vl",
        direction="5prime",
        round_name="primary",
    )
    assert partner is not None
    assert partner["sequence"] == "CGACTGGAGCACGAGGACACTGA"
    assert partner["source_identity"] == "GeneRacer Kit manual/support"
    assert partner["source_reviewed_date"] == "2026-09-05"


def test_family_only_generacer_and_aap_are_refused_as_ambiguous():
    for ambiguous in ("generacer", "AAP"):
        with pytest.raises(SinglePrimerError, match="ambiguous, non-executable"):
            race_adapter(ambiguous, direction="5prime", round_name="primary")


def test_a_primer_complementary_to_the_selected_versioned_partner_is_flagged():
    partner = race_adapter(
        "generacer-kit-25-0355-vl",
        direction="5prime",
        round_name="primary",
    )
    assert partner is not None
    from pcr_tools.single import adapter_screen

    out = adapter_screen(reverse_complement(partner["sequence"]), partner=partner, **CONDITIONS)
    assert out["flagged"]
    assert out["partner"] == "GeneRacer 5′ Primer"


def test_current_firstchoice_partners_are_exact_and_versioned():
    primary = race_adapter(
        "firstchoice-rlm-race",
        direction="5prime",
        round_name="primary",
    )
    nested = race_adapter(
        "firstchoice-rlm-race",
        direction="3prime",
        round_name="nested",
    )
    assert primary is not None and nested is not None
    assert primary["sequence"] == "GCTGATGGCGATGAATGAACACTG"
    assert nested["sequence"] == "CGCGGATCCGAATTAATACGACTCACTATAGG"
    assert primary["source_revision"] == "Rev A"
    assert primary["source_revision_date"] == "2025-06-09"


def test_race_named_chemistry_and_adapter_cannot_cross_wire():
    request = {
        "assay": {"id": "race"},
        "template": template(),
        "target_start": 1200,
        "target_length": 250,
        "race_direction": "5prime",
        "race_chemistry": "firstchoice-rlm-race",
        "race_adapter": "generacer-kit-25-0355-vl",
        "race_substrate": "total-rna",
        "race_preparation": "test-RACE-SOP",
        "race_round": "primary",
    }
    with pytest.raises(SinglePrimerError, match="different RACE branches"):
        run(request)
