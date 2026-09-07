from __future__ import annotations

import pytest

from pcr_tools.registries.restriction_workflows import generated_catalogue, resolve_restriction_workflow


def test_neb_standard_digest_stays_family_scoped() -> None:
    workflow = resolve_restriction_workflow(
        digest_protocol="neb-cutsmart-standard",
        dephosphorylation_protocol="none",
        ligation_protocol="neb-t4-dna-ligase-m0202",
    )
    digest = workflow["digest"]
    assert digest["values"]["reaction_volume_ul"] == pytest.approx(50.0)
    assert digest["values"]["enzyme_units_per_ug_starting"] == pytest.approx(10.0)
    assert "exact-enzyme incubation temperature" in digest["unresolved"]
    assert workflow["decision_impact"] == "none-on-primer-ranking"


def test_neb_timesaver_records_range_not_fixed_time() -> None:
    digest = resolve_restriction_workflow(
        digest_protocol="neb-cutsmart-timesaver",
        dephosphorylation_protocol="none",
        ligation_protocol="neb-quick-ligation-m2200",
    )["digest"]
    assert "digest_time_min" not in digest["values"]
    assert digest["ranges"]["digest_time_min"] == [5.0, 15.0]
    assert any("eligibility" in item for item in digest["unresolved"])


def test_fastdigest_public_family_recipe_does_not_invent_enzyme_specific_facts() -> None:
    digest = resolve_restriction_workflow(
        digest_protocol="thermo-fastdigest-universal",
        dephosphorylation_protocol="none",
        ligation_protocol="neb-quick-ligation-m2200",
    )["digest"]
    assert digest["values"]["plasmid_reaction_volume_ul"] == pytest.approx(20.0)
    assert digest["values"]["family_incubation_temperature_c"] == pytest.approx(37.0)
    assert digest["ranges"]["digest_time_min"] == [5.0, 15.0]
    assert any("methylation" in item for item in digest["unresolved"])


def test_quick_cip_keeps_cleanup_caveat() -> None:
    step = resolve_restriction_workflow(
        digest_protocol="neb-cutsmart-standard",
        dephosphorylation_protocol="neb-quick-cip-m0525",
        ligation_protocol="neb-t4-dna-ligase-m0202",
    )["dephosphorylation"]
    assert step["values"]["reaction_volume_ul"] == pytest.approx(20.0)
    assert step["values"]["incubation_temperature_c"] == pytest.approx(37.0)
    assert step["values"]["heat_inactivation_temperature_c"] == pytest.approx(80.0)
    assert step["unresolved"]


def test_t4_ligase_ratio_is_labelled_source_example() -> None:
    step = resolve_restriction_workflow(
        digest_protocol="neb-cutsmart-standard",
        dephosphorylation_protocol="none",
        ligation_protocol="neb-t4-dna-ligase-m0202",
    )["ligation"]
    assert step["values"]["ligase_units"] == pytest.approx(400.0)
    assert step["values"]["example_vector_insert_molar_ratio"] == "1:3"
    assert "sticky_end" in step["branches"]
    assert any("optimization" in item for item in step["unresolved"])


def test_quick_ligation_is_not_heat_inactivated() -> None:
    step = resolve_restriction_workflow(
        digest_protocol="neb-cutsmart-standard",
        dephosphorylation_protocol="none",
        ligation_protocol="neb-quick-ligation-m2200",
    )["ligation"]
    assert step["values"]["incubation_temperature_c"] == pytest.approx(25.0)
    assert step["values"]["incubation_time_min"] == pytest.approx(5.0)
    assert step["values"]["heat_inactivate"] is False


def test_missing_or_unknown_workflow_fails_closed() -> None:
    with pytest.raises(ValueError):
        resolve_restriction_workflow(
            digest_protocol=None,
            dephosphorylation_protocol="none",
            ligation_protocol="neb-quick-ligation-m2200",
        )
    with pytest.raises(ValueError):
        resolve_restriction_workflow(
            digest_protocol="magic-digest",
            dephosphorylation_protocol="none",
            ligation_protocol="neb-quick-ligation-m2200",
        )


def test_generated_catalogue_has_all_three_workflow_axes() -> None:
    catalogue = generated_catalogue()
    assert set(catalogue["digest"]) == {
        "neb-cutsmart-standard",
        "neb-cutsmart-timesaver",
        "thermo-fastdigest-universal",
    }
    assert set(catalogue["dephosphorylation"]) == {"none", "neb-quick-cip-m0525"}
    assert set(catalogue["ligation"]) == {"neb-t4-dna-ligase-m0202", "neb-quick-ligation-m2200"}
