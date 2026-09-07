from __future__ import annotations

import pytest

from pcr_tools.flanking_numeric_recipes import generated_catalogue, resolve_numeric_recipe
from pcr_tools.flanking_request import _flanking_numeric_context


def test_onetaq_standard_25_ul_derives_half_volume_master_mix() -> None:
    recipe = resolve_numeric_recipe(
        "neb-onetaq-hot-start-m0484",
        "standard-pcr",
        scenario={"reaction_volume_uL": 25.0},
    )
    assert recipe["values"]["master_mix_uL"] == pytest.approx(12.5)
    assert recipe["values"]["primer_each_uM"] == pytest.approx(0.2)
    assert recipe["origins"]["reaction_volume_uL"] == "user-override-within-source-bound"
    assert recipe["sequence_decision_impact"] == "none"


def test_onetaq_gc_enhancer_is_source_bounded() -> None:
    recipe = resolve_numeric_recipe(
        "neb-onetaq-hot-start-gc-m0485",
        "standard-pcr",
        scenario={"additive": "high-gc-enhancer"},
        overrides={"high_gc_enhancer_percent": 15.0},
    )
    assert recipe["values"]["high_gc_enhancer_percent"] == pytest.approx(15.0)
    assert recipe["ranges"]["high_gc_enhancer_percent"] == [10.0, 20.0]
    with pytest.raises(ValueError):
        resolve_numeric_recipe(
            "neb-onetaq-hot-start-gc-m0485",
            "standard-pcr",
            scenario={"additive": "high-gc-enhancer"},
            overrides={"high_gc_enhancer_percent": 25.0},
        )


def test_pcrbio_colony_overlay_resolves_only_when_declared() -> None:
    baseline = resolve_numeric_recipe("pcrbio-hs-taq-mix-pb10-22", "standard-pcr")
    direct = resolve_numeric_recipe(
        "pcrbio-hs-taq-mix-pb10-22",
        "standard-pcr",
        scenario={"preparation": "direct-colony"},
    )
    assert "initial_denaturation_time_min" not in baseline["values"]
    assert direct["values"]["initial_denaturation_temperature_c"] == pytest.approx(95.0)
    assert direct["values"]["initial_denaturation_time_min"] == pytest.approx(10.0)


def test_powertrack_requires_source_cycling_branch_and_resolves_20_ul() -> None:
    unresolved = resolve_numeric_recipe("thermo-powertrack-sybr-a46xxx", "qpcr-sybr")
    assert any(row["id"] == "powertrack-cycling-profile" for row in unresolved["unresolved_numeric_dependencies"])
    recipe = resolve_numeric_recipe(
        "thermo-powertrack-sybr-a46xxx",
        "qpcr-sybr",
        scenario={
            "reaction_volume_uL": 20.0,
            "cycling_profile": "fast",
            "template_fraction_percent": 15.0,
        },
        overrides={"primer_each_nM": 500.0},
    )
    assert recipe["values"]["master_mix_uL"] == pytest.approx(10.0)
    assert "yellow_sample_buffer_uL" not in recipe["values"]
    assert recipe["values"]["denaturation_time_sec"] == pytest.approx(5.0)
    assert recipe["values"]["anneal_extend_time_sec"] == pytest.approx(30.0)
    assert recipe["values"]["template_fraction_percent"] == pytest.approx(15.0)
    with pytest.raises(ValueError):
        resolve_numeric_recipe(
            "thermo-powertrack-sybr-a46xxx",
            "qpcr-sybr",
            scenario={"template_fraction_percent": 25.0},
        )



def test_powertrack_yellow_sample_buffer_is_optional_and_stoichiometric() -> None:
    without = resolve_numeric_recipe(
        "thermo-powertrack-sybr-a46xxx",
        "qpcr-sybr",
        scenario={"cycling_profile": "fast", "reaction_volume_uL": 20.0},
    )
    assert "yellow_sample_buffer_uL" not in without["values"]

    with_20 = resolve_numeric_recipe(
        "thermo-powertrack-sybr-a46xxx",
        "qpcr-sybr",
        scenario={"cycling_profile": "fast", "reaction_volume_uL": 20.0, "additive": "yellow-sample-buffer"},
    )
    assert with_20["values"]["yellow_sample_buffer_x_final"] == pytest.approx(1.0)
    assert with_20["values"]["yellow_sample_buffer_uL"] == pytest.approx(0.5)
    assert "powertrack-yellow-sample-buffer" in with_20["applied_overlays"]

    with_10 = resolve_numeric_recipe(
        "thermo-powertrack-sybr-a46xxx",
        "qpcr-sybr",
        scenario={"cycling_profile": "standard", "reaction_volume_uL": 10.0, "additive": "yellow-sample-buffer"},
    )
    assert with_10["values"]["yellow_sample_buffer_uL"] == pytest.approx(0.25)

    with pytest.raises(ValueError):
        resolve_numeric_recipe(
            "neb-onetaq-hot-start-m0484",
            "standard-pcr",
            scenario={"additive": "yellow-sample-buffer"},
        )


def test_thermo_lyo_ready_rpa_projects_proteins_bounded_conditions_and_rt_components() -> None:
    baseline = resolve_numeric_recipe("thermo-lyo-ready-rpa", "rpa")
    assert baseline["values"]["reaction_volume_uL"] == pytest.approx(20.0)
    assert baseline["values"]["primer_each_nM"] == pytest.approx(300.0)
    assert baseline["values"]["uvsx_mg_per_mL"] == pytest.approx(0.03)
    assert baseline["values"]["uvsy_mg_per_mL"] == pytest.approx(0.03)
    assert baseline["values"]["gene32_mg_per_mL"] == pytest.approx(0.4)
    assert baseline["values"]["bst_polymerase_U_per_uL"] == pytest.approx(0.15)
    assert baseline["ranges"]["hold_temperature_c"] == [34.0, 45.0]
    assert baseline["ranges"]["hold_time_min"] == [10.0, 25.0]
    assert baseline["ranges"]["bst_polymerase_U_per_uL"] == [0.015, 0.15]

    multiplex = resolve_numeric_recipe(
        "thermo-lyo-ready-rpa",
        "rpa",
        scenario={"multiplex": True, "temperature_c": 40.0, "time_min": 25.0, "bst_units_per_uL": 0.05},
    )
    assert multiplex["values"]["primer_each_nM"] == pytest.approx(100.0)
    assert multiplex["values"]["hold_temperature_c"] == pytest.approx(40.0)
    assert multiplex["values"]["hold_time_min"] == pytest.approx(25.0)
    assert multiplex["values"]["bst_polymerase_U_per_uL"] == pytest.approx(0.05)

    rt = resolve_numeric_recipe("thermo-lyo-ready-rpa", "rpa", scenario={"from_rna": True})
    assert rt["values"]["reverse_transcriptase_U_per_uL"] == pytest.approx(2.0)
    assert rt["values"]["rnase_inhibitor_U_per_uL"] == pytest.approx(1.6)
    assert rt["values"]["rnase_h_U_per_uL"] == pytest.approx(0.1)

    with pytest.raises(ValueError):
        resolve_numeric_recipe("thermo-lyo-ready-rpa", "rpa", scenario={"temperature_c": 46.0})

def test_kod_long_length_drives_only_documented_extension_regime() -> None:
    short = resolve_numeric_recipe("toyobo-kod-long-kml101", "long-range-pcr", scenario={"target_length_kb": 8.0})
    long = resolve_numeric_recipe("toyobo-kod-long-kml101", "long-range-pcr", scenario={"target_length_kb": 12.0})
    assert short["values"]["extension_seconds_per_kb"] == pytest.approx(5.0)
    assert short["values"]["extension_time_sec"] == pytest.approx(40.0)
    assert long["values"]["extension_seconds_per_kb"] == pytest.approx(10.0)
    assert long["values"]["extension_time_sec"] == pytest.approx(120.0)
    with pytest.raises(ValueError):
        resolve_numeric_recipe("toyobo-kod-long-kml101", "long-range-pcr", scenario={"target_length_kb": 51.0})


def test_qiacuity_refuses_to_invent_nanoplate_reaction_volume() -> None:
    unresolved = resolve_numeric_recipe("qiagen-qiacuity-eg", "digital-pcr")
    assert "reaction_volume_uL" not in unresolved["values"]
    assert any(row["id"] == "qiacuity-nanoplate-format" for row in unresolved["unresolved_numeric_dependencies"])
    resolved = resolve_numeric_recipe(
        "qiagen-qiacuity-eg", "digital-pcr", scenario={"partition_format_detail": "26k"}
    )
    assert resolved["values"]["reaction_volume_uL"] == pytest.approx(40.0)


def test_wrong_module_and_unreviewed_reaction_volume_fail_closed() -> None:
    with pytest.raises(ValueError):
        resolve_numeric_recipe("thermo-powertrack-sybr-a46xxx", "standard-pcr")
    with pytest.raises(ValueError):
        resolve_numeric_recipe(
            "thermo-powertrack-sybr-a46xxx", "qpcr-sybr", scenario={"reaction_volume_uL": 15.0}
        )


def test_generated_catalogue_covers_every_new_runtime_identity() -> None:
    catalogue = generated_catalogue()
    for protocol in {
        "neb-onetaq-hot-start-m0484",
        "neb-onetaq-hot-start-gc-m0485",
        "neb-onetaq-hot-start-quickload-m0488",
        "neb-onetaq-hot-start-quickload-gc-m0489",
        "pcrbio-hs-taq-mix-pb10-22",
        "thermo-powertrack-sybr-a46xxx",
        "toyobo-kod-long-kml101",
    }:
        assert protocol in catalogue["protocol_metadata"]
        assert protocol in catalogue["baselines"]


def test_colony_vendor_protocols_keep_distinct_source_conditioned_lysis_times() -> None:
    m0482 = resolve_numeric_recipe("neb-onetaq-m0482-colony", "colony-pcr", scenario={"preparation": "direct-transfer"})
    assert m0482["values"]["initial_denaturation_temperature_c"] == pytest.approx(94.0)
    assert m0482["values"]["initial_denaturation_time_min"] == pytest.approx(5.0)

    m0488 = resolve_numeric_recipe("neb-onetaq-hotstart-m0488-colony", "colony-pcr", scenario={"preparation": "direct-transfer"})
    assert "initial_denaturation_time_min" not in m0488["values"]
    assert m0488["ranges"]["initial_denaturation_time_min"] == [2.0, 5.0]
    assert any(row["id"] == "m0488-colony-lysis-time" for row in m0488["unresolved_numeric_dependencies"])

    m0488_resolved = resolve_numeric_recipe(
        "neb-onetaq-hotstart-m0488-colony",
        "colony-pcr",
        scenario={"preparation": "direct-transfer", "initial_denaturation_time_min": 3.0},
    )
    assert m0488_resolved["values"]["initial_denaturation_time_min"] == pytest.approx(3.0)


def test_pcrbio_liquid_culture_branch_records_source_input_volume() -> None:
    recipe = resolve_numeric_recipe(
        "pcrbio-hs-taq-pb10-22-colony",
        "colony-pcr",
        scenario={"preparation": "liquid-culture"},
    )
    assert recipe["values"]["reaction_volume_uL"] == pytest.approx(50.0)
    assert recipe["values"]["liquid_culture_input_uL"] == pytest.approx(5.0)
    assert recipe["values"]["initial_denaturation_time_min"] == pytest.approx(10.0)


def test_worker_numeric_context_accepts_snake_case_rpa_and_rejects_cross_assay_leakage() -> None:
    context = _flanking_numeric_context(
        {
            "primer_each_nm": 150.0,
            "rpa_temperature_c": 40.0,
            "rpa_time_min": 25.0,
            "rpa_bst_units_per_ul": 0.05,
            "rpa_multiplex": True,
        },
        assay_id="rpa",
    )
    assert context is not None
    assert context["rpa_temperature_c"] == pytest.approx(40.0)
    assert context["rpa_multiplex"] is True

    with pytest.raises(ValueError, match="RPA numeric context"):
        _flanking_numeric_context({"rpa_temperature_c": 40.0}, assay_id="qpcr-sybr")
    with pytest.raises(ValueError, match="yellow-sample-buffer"):
        _flanking_numeric_context({"additive": "yellow-sample-buffer"}, assay_id="standard-pcr")
    with pytest.raises(ValueError, match="unknown"):
        _flanking_numeric_context({"rpaTemperatureC": 40.0}, assay_id="rpa")
