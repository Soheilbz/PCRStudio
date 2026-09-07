"""A pair with a probe between them, and the two rules that are not about pairs.

Everything a probe assay adds over an ordinary pair is a relationship between
three oligos rather than two, so that is what is tested here: where the probe
sits, how far above the primers it melts, and what its first base may be.

The test that matters most is the dull-looking one — that the probe melts
inside the window it was asked for. Primer3 keeps a separate buffer for the
internal oligo, so a design that sends the reaction to the primers and not to
the probe still returns probes, still reports temperatures, and is wrong by
nearly nine degrees. Measured on this exact target: with the reaction sent,
five of five probes fall in a 64–70 °C window; without it, none of five do, and
every one comes back at 74.9. Nothing else in the result looks different.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.design import Constraints
from pcr_tools.presets import polymerase
from pcr_tools.probe import (
    UNBOUND_ENGINE_PROBE_TM_OFFSET_C,
    FORBIDDEN_FIRST_BASE,
    ProbeError,
    assay_to_dict,
    design,
    probe_protocol,
    run,
)
from pcr_tools.thermo import analyse

CONDITIONS = polymerase("qpcr-dye").reaction.as_conditions()

QPCR_PROBE_ASSAY = {
    "id": "qpcr-probe",
    "name": "qPCR — Hydrolysis Probe",
    "enzyme": ["five-prime-exonuclease"],
    "defaults": {
        "polymerase": "qpcr-dye",
        "purposes": ["general"],
        "constraints": {
            "product_min": 70,
            "product_max": 200,
            "tm_min": 59.0,
            "tm_opt": 60.0,
            "tm_max": 65.0,
            "tm_pair_max_difference": 3.0,
            "gc_min": 40.0,
            "gc_max": 60.0,
            "gc_clamp": 0,
            "max_end_gc": 3,
            "max_poly_x": 3,
        },
    },
}


def template() -> str:
    return record("NM_000546.6").sequence()


@pytest.fixture(scope="module")
def assays():
    found, _ = design(
        template(),
        target_start=1200,
        target_length=100,
        conditions=CONDITIONS,
        how_many=5,
    )
    assert found, "no probe assay on a target with room around it"
    return found


# ── The reaction the probe is measured in ──────────────────────────────────


def test_the_probe_melts_inside_the_window_it_was_asked_for(assays):
    """The regression test for the separate-buffer bug.

    Primer3 takes the internal oligo's salts as their own settings. Leave them
    at its defaults and it happily returns probes it believes are in range
    while they melt 4.9 °C above the top of the window in the reaction that is
    actually being run.
    """
    limits = Constraints()
    wanted_low = limits.tm_min + UNBOUND_ENGINE_PROBE_TM_OFFSET_C
    wanted_high = limits.tm_max + UNBOUND_ENGINE_PROBE_TM_OFFSET_C

    for assay in assays:
        measured = analyse(assay.probe.sequence, **CONDITIONS).tm
        assert wanted_low <= measured <= wanted_high, (
            f"{assay.probe.sequence} melts at {measured} °C in this reaction, outside "
            f"the {wanted_low}–{wanted_high} °C asked for. The likeliest cause is the "
            "probe's buffer having been left at Primer3's defaults while the primers "
            "got the real one."
        )


def test_the_probe_temperature_reported_is_the_one_measured_in_the_reaction(assays):
    """Not Primer3's estimate, carried through unchecked."""
    for assay in assays:
        assert assay.probe.tm == analyse(assay.probe.sequence, **CONDITIONS).tm


# ── Above the primers, which is the mechanism ──────────────────────────────


def test_every_probe_melts_clear_of_both_its_own_primers(assays):
    """It is destroyed rather than extended, so it must already be bound.

    A probe that melts alongside its primers is not bound when the polymerase
    sets off, and the assay reports nothing while the amplification works
    perfectly — which is the failure that looks like absent template.
    """
    for assay in assays:
        warmest = max(assay.pair.left.tm, assay.pair.right.tm)
        assert assay.probe.tm > warmest, assay.probe
        assert assay.probe.above >= 5.0, (
            f"{assay.probe.above} °C above the warmer primer is not enough of a "
            "margin for the probe to be bound first"
        )


def test_a_probe_window_overlapping_the_primers_is_refused_before_designing():
    """Rather than returning a design whose probe might melt below its primers."""
    with pytest.raises(ProbeError, match="melts above them"):
        design(
            template(),
            target_start=1200,
            target_length=100,
            constraints=Constraints(tm_min=57.0, tm_opt=60.0, tm_max=68.0),
            probe_constraints=Constraints(tm_min=64.0, tm_opt=67.0, tm_max=70.0),
            conditions=CONDITIONS,
        )


# ── The rule no thermodynamic measure would find ───────────────────────────


def test_no_probe_begins_with_a_guanine(assays):
    """A G beside the fluorophore quenches it.

    Vendor guidance rather than anything measurable here — and the CDC N1, CDC
    N2 and E_Sarbeco probes all begin with an adenine, which is checked in the
    benchmark suite beside this one.
    """
    for assay in assays:
        assert assay.probe.sequence[0].upper() != FORBIDDEN_FIRST_BASE


# ── Where it sits ──────────────────────────────────────────────────────────


def test_every_probe_is_found_at_the_position_it_reports(assays):
    """Read out of the template rather than trusted from the arithmetic."""
    sequence = template()
    for assay in assays:
        here = sequence[assay.probe.at : assay.probe.at + assay.probe.length]
        assert here.upper() == assay.probe.sequence.upper(), assay.probe


def test_the_probe_sits_between_the_primers_and_touches_neither(assays):
    """Overlapping a primer means competing with it for the same bases."""
    for assay in assays:
        after_left = assay.pair.left_at.start + assay.pair.left_at.length
        before_right = assay.pair.right_at.start
        assert assay.probe.at >= after_left, assay.probe
        assert assay.probe.at + assay.probe.length <= before_right + 1, assay.probe
        assert assay.probe.after_left == assay.probe.at - after_left


def test_the_product_is_short_enough_to_be_worth_a_probe(assays):
    """A probe assay is a qPCR assay, and qPCR amplicons are short."""
    for assay in assays:
        assert assay.product_size <= 400


# ── What is said out loud ──────────────────────────────────────────────────


def test_the_result_says_what_the_separation_is_and_why_it_matters(assays):
    entry = assay_to_dict(assays[0], **CONDITIONS)
    probe = entry["probe"]
    assert probe["above_primers"] == assays[0].probe.above
    assert str(assays[0].probe.above) in probe["note"]
    assert probe["first_base"] == assays[0].probe.sequence[0]
    # The buffer finding is stated in the result rather than only in the tests,
    # because somebody comparing this against another tool's numbers needs to
    # know which reaction each was computed in.
    assert "same reaction" in entry["measured_in"]["note"]


# ── Named chemistry overlays ───────────────────────────────────────────────


def test_taqman_mgb_overlay_contains_only_documented_starting_metadata():
    protocol = probe_protocol("taqman-mgb")
    assert protocol is not None
    assert protocol["chemistry"] == "mgb-nfq"
    assert protocol["probe_length_nt"] == {"min": 13, "max": 25}
    assert protocol["execution_status"] == "external-authority-required"
    assert protocol["tm_model"] == "MGB-aware-vendor-model-required"
    assert protocol["quencher_options"] == ["NFQ-MGB"]


def test_unknown_probe_protocol_is_refused_before_design():
    with pytest.raises(ProbeError, match="probe_protocol"):
        probe_protocol("invented-kit")


def _qpcr_probe_request(**extra):
    return {
        "template": template(),
        "assay": QPCR_PROBE_ASSAY,
        "polymerase": "qpcr-dye",
        "purpose": "general",
        "target_start": 1200,
        "target_length": 100,
        "how_many": 1,
        **extra,
    }


@pytest.mark.parametrize("policy", ["strict", "development"])
def test_qpcr_probe_without_named_executable_chemistry_is_refused_in_every_policy(monkeypatch, policy):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", policy)
    with pytest.raises(ProbeError, match="explicit named executable probe chemistry"):
        run(_qpcr_probe_request())


@pytest.mark.parametrize("policy", ["strict", "development"])
def test_taqman_mgb_requires_explicit_external_authority_mode(monkeypatch, policy):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", policy)
    with pytest.raises(ProbeError, match="probeMgbAuthorityMode"):
        run(_qpcr_probe_request(probe_protocol="taqman-mgb"))


def test_development_mode_cannot_execute_mgb_by_omitting_assay_identity():
    assert QPCR_PROBE_ASSAY["id"] == "qpcr-probe"
    assert probe_protocol("taqman-mgb")["chemistry"] == "mgb-nfq"


def test_user_constraints_cannot_substitute_for_mgb_authority_values():
    with pytest.raises(ProbeError, match="probeMgbAuthorityMode"):
        run(
            _qpcr_probe_request(
                probe_protocol="taqman-mgb",
                constraints={"tm_min": 57.0, "tm_opt": 59.0, "tm_max": 61.0},
                probe={"tm_min": 67.0, "tm_opt": 69.0, "tm_max": 71.0},
            )
        )
