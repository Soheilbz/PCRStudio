"""Reaction conditions, and the one that everybody enters wrong."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from pcr_tools.presets import (
    POLYMERASES,
    Cycling,
    Reaction,
    polymerase,
    polymerases_to_dict,
    thermodynamic_model,
)
from pcr_tools.provenance import provenance


def test_every_preset_describes_a_reaction_that_could_exist():
    for preset in POLYMERASES:
        preset.reaction.validate()


def test_dntp_is_the_sum_of_all_four_not_the_concentration_of_each():
    # 0.2 mM of each base is 0.8 here. Entering 0.2 describes a reaction nobody
    # runs, and shifts every melting temperature reported.
    standard = polymerase("taq-standard").reaction
    assert standard.dntp_conc == 0.8


def test_long_range_baseline_keeps_total_semantics_without_claiming_a_vendor_buffer():
    long_range = polymerase("long-range")

    # Primer3 receives the sum of all four dNTPs. The shared long-range
    # screening adapter must not present one supplier's per-base recipe as a
    # universal bench formulation; named protocol overlays own that detail.
    assert long_range.reaction.dntp_conc == 0.8
    assert "model inputs" in long_range.summary
    assert "not a reconstruction" in long_range.summary


def test_rpa_screening_proxy_does_not_claim_liquid_dntp_as_lyophilised_basic_formulation():
    rpa = polymerase("rpa")

    # Primer3 still needs a finite calculation context. The 1.8 mM value is
    # documented for Liquid Basic and may be used only as the disclosed
    # screening proxy; the selected lyophilised Basic bench protocol must not
    # claim that concentration as its formulation.
    assert rpa.reaction.dntp_conc == 1.8
    assert "Liquid Basic" in rpa.summary
    assert "not a claim" in rpa.summary


def test_dntp_above_magnesium_uses_primer3s_documented_fallback():
    reaction = Reaction(mv_conc=50.0, dv_conc=1.0, dntp_conc=2.0, dna_conc=200.0)
    reaction.validate()
    model = thermodynamic_model(reaction=reaction)
    assert model["divalent_cation_effect"] == "not-considered-by-primer3"
    assert "exceeds PRIMER_SALT_DIVALENT" in model["divalent_cation_note"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 10**1000, True])
def test_nonfinite_or_boolean_reaction_conditions_are_refused(value):
    with pytest.raises(ValueError, match="finite"):
        Reaction(mv_conc=value, dv_conc=1.0, dntp_conc=0.8, dna_conc=200.0).validate()


def test_nonfinite_or_negative_cycling_values_are_refused():
    ordinary = polymerase("taq-standard").cycling
    with pytest.raises(ValueError, match="finite"):
        Cycling(**{**asdict(ordinary), "denature_c": float("nan")}).validate()
    with pytest.raises(ValueError, match="negative"):
        Cycling(**{**asdict(ordinary), "anneal_seconds": -1}).validate()


def test_an_isothermal_programme_cannot_omit_its_hold_duration_or_temperature():
    rpa = polymerase("rpa").cycling
    with pytest.raises(ValueError, match="both"):
        Cycling(**{**asdict(rpa), "isothermal_seconds": None}).validate()
    with pytest.raises(ValueError, match="both"):
        Cycling(**{**asdict(rpa), "isothermal_c": None}).validate()


def test_cycling_does_not_accept_settings_that_the_renderer_would_ignore():
    ordinary = polymerase("taq-standard").cycling
    with pytest.raises(ValueError, match=r"only valid.*two-step"):
        Cycling(**{**asdict(ordinary), "anneal_extend_c": 68.0}).validate()

    with pytest.raises(ValueError, match=r"explicit.*hold temperature"):
        Cycling(**{**asdict(ordinary), "two_step": True}).validate()

    rpa = polymerase("rpa").cycling
    with pytest.raises(ValueError, match="cannot also be marked"):
        Cycling(**{**asdict(rpa), "two_step": True}).validate()

    with pytest.raises(ValueError, match="maximum extension time"):
        Cycling(**{**asdict(ordinary), "extend_seconds_max": 1}).validate()


def test_an_unknown_preset_lists_the_ones_that_exist():
    with pytest.raises(ValueError, match="taq-standard"):
        polymerase("nonesuch")


def test_no_preset_defaults_to_the_ordinary_reaction():
    assert polymerase(None).id == "taq-standard"
    assert polymerase("").id == "taq-standard"


def test_the_primer3_default_is_offered_but_marked_as_not_a_bench_condition():
    entry = next(p for p in polymerases_to_dict() if p["id"] == "primer3-default")
    assert "not a bench condition" in entry["summary"]


def test_the_form_can_render_the_presets_without_knowing_what_is_in_them():
    for entry in polymerases_to_dict():
        assert entry["name"] and entry["summary"]
        assert set(entry["reaction"]) == {"mv_conc", "dv_conc", "dntp_conc", "dna_conc"}
        assert entry["thermodynamics"]["oligo_concentration_parameter"] == "PRIMER_DNA_CONC"
        assert (
            entry["thermodynamics"]["oligo_concentration_role"]
            == "empirical_annealing_oligo_for_tm"
        )


def test_rpa_is_marked_as_complete_recombinase_chemistry_not_just_strand_displacement():
    entries = {entry["id"]: entry for entry in polymerases_to_dict()}

    assert entries["rpa"]["does"]["rpa_compatible"] is True
    assert entries["rpa"]["does"]["strand_displacing"] is True
    assert entries["rpa"]["does"]["five_prime_exonuclease"] is False
    assert entries["bst"]["does"]["rpa_compatible"] is False


def test_rpa_default_primer_concentration_matches_the_twistamp_starting_protocol():
    assert polymerase("rpa").reaction.dna_conc == 480.0


def test_rpa_tm_is_explicitly_labeled_as_a_screening_proxy():
    assert thermodynamic_model(polymerase("rpa"))["role"] == "screening-proxy"
    assert thermodynamic_model(polymerase("taq-standard"))["role"] == "design-and-report"




def test_thermodynamic_model_does_not_mislabel_primer3_oligo_input_as_mix_concentration():
    model = thermodynamic_model(polymerase("digital-pcr"))

    assert model["oligo_concentration_parameter"] == "PRIMER_DNA_CONC"
    assert model["oligo_concentration_role"] == "empirical_annealing_oligo_for_tm"
    assert "not necessarily" in model["oligo_concentration_note"]




def test_thermodynamic_model_exposes_explicit_primer3_low_level_controls():
    controls = thermodynamic_model(polymerase("taq-standard"))["primer3_low_level_controls"]
    assert controls == {
        "temp_c_default": 37.0,
        "max_loop": 30,
        "max_nn_length": 60,
        "output_structure": False,
        "temp_only": 0,
        "dmso_conc": 0.0,
        "dmso_fact": 0.6,
        "formamide_conc": 0.0,
        "annealing_temp_c": -10.0,
    }


def test_provenance_carries_the_same_low_level_controls_as_the_reaction_model():
    model = thermodynamic_model(polymerase("digital-pcr"))
    recorded = provenance(polymerase("digital-pcr").reaction.as_conditions())["model"]
    assert recorded["primer3_low_level_controls"] == model["primer3_low_level_controls"]
