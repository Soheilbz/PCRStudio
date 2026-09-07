from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcr_tools.flanking_numeric_recipes import resolve_numeric_recipe
from pcr_tools.junction import protocol as assembly_protocol
from pcr_tools.lamp_numeric_recipes import LAMP_NUMERIC_BASELINES
from pcr_tools.mutagenesis_workflows import EditSpec, quikchange_single
from pcr_tools.mutagenic import Q5_SEARCH_PRIMER_LENGTH_MAX
from pcr_tools.nested import NESTED_AUTHORITY
from pcr_tools.registries.authorities import (
    ASSEMBLY_AUTHORITY,
    DISCRIMINATING_AUTHORITY,
    MUTAGENESIS_AUTHORITY,
)
from pcr_tools.registries.flanking_protocols import (
    COLONY_PROTOCOLS,
    DIGITAL_PROTOCOLS,
    LONG_RANGE_PROTOCOLS,
    QPCR_PROTOCOLS,
    RPA_PROTOCOLS,
    STANDARD_PCR_PROTOCOLS,
)

ROOT = Path(__file__).resolve().parents[2]


def test_flanking_protocol_families_are_disjoint_and_numeric_requests_fail_cross_module() -> None:
    groups = {
        "standard-pcr": set(STANDARD_PCR_PROTOCOLS) - {"not-selected"},
        "qpcr-sybr": set(QPCR_PROTOCOLS) - {"not-selected"},
        "rpa": set(RPA_PROTOCOLS) - {"not-selected"},
        "long-range-pcr": set(LONG_RANGE_PROTOCOLS) - {"not-selected"},
        "digital-pcr": set(DIGITAL_PROTOCOLS) - {"not-selected"},
        "colony-pcr": set(COLONY_PROTOCOLS) - {"custom-sop"},
    }
    seen: dict[str, str] = {}
    for module, protocol_ids in groups.items():
        for protocol_id in protocol_ids:
            assert protocol_id not in seen, (protocol_id, seen.get(protocol_id), module)
            seen[protocol_id] = module
    # Representative cross-module request: qPCR chemistry must never resolve as Standard PCR.
    with pytest.raises(ValueError):
        resolve_numeric_recipe("thermo-powertrack-sybr-a46xxx", "standard-pcr")


def test_lamp_canonical_record_owns_m1712_hold_and_supplement_does_not_override_it() -> None:
    authority = json.loads(
        (ROOT / "contracts/chemistry/lamp-protocols.json").read_text(encoding="utf-8")
    )
    record = authority["protocols"]["neb-m1712"]
    assert record["hold_temperature_c"] == 65
    assert record["hold_time_min"] == 20
    supplement = LAMP_NUMERIC_BASELINES.get("neb-m1712", {})
    assert "hold_temperature_c" not in supplement
    assert "hold_time_min" not in supplement
    assert "reaction_volume_uL" not in supplement


def test_gibson_and_nebuilder_numeric_branches_are_distinct_authorities() -> None:
    gibson = ASSEMBLY_AUTHORITY["records"]["neb-e5510"]
    assert gibson["branches"]["2-3-fragments"]["overlap_bp_min"] == 15
    assert gibson["branches"]["2-3-fragments"]["overlap_bp_max"] == 25
    assert gibson["branches"]["4-6-fragments"]["overlap_bp_min"] == 20
    assert gibson["branches"]["4-6-fragments"]["overlap_bp_max"] == 80
    resolved_gibson = assembly_protocol("neb-e5510", 5)
    assert resolved_gibson is not None
    assert resolved_gibson["overlap_bp"] == {"min": 20, "max": 80}
    resolved_nebuilder = assembly_protocol("neb-nebuilder-e2621", 5)
    assert resolved_nebuilder is not None
    assert resolved_nebuilder["overlap_bp"] == {"min": 20, "max": 30}
    assert resolved_nebuilder["id"] != resolved_gibson["id"]
    assert resolved_nebuilder["selection"] != resolved_gibson["selection"]


def test_q5_vendor_boundary_and_quikchange_search_cap_are_not_conflated() -> None:
    q5 = MUTAGENESIS_AUTHORITY["records"]["neb-q5-e0554"]
    assert q5["routine_insertion_max_nt"] == 100
    assert q5["split_insertion_per_primer_max_nt"] == 50
    assert "not a maximum" in q5["documented_successful_plasmid_claim_boundary"]
    assert Q5_SEARCH_PRIMER_LENGTH_MAX == 60
    # QuikChange implementation may search beyond the preferred 45-nt range, but must label 60 nt as an internal search cap.
    template = "ACGT" * 100
    result = quikchange_single(template, EditSpec(kind="substitute", at=100, replacing=1, to="T"))
    if result["orderable"]:
        authority = result["authority"]
        assert authority["search_primer_length_max_nt"] == 60
        assert authority["search_length_is_vendor_limit"] is False
    else:
        assert result["search_primer_length_max_nt"] == 60
        assert result["search_length_is_vendor_limit"] is False


def test_kasp_v5_never_inherits_historical_v4_reaction_numbers() -> None:
    records = DISCRIMINATING_AUTHORITY["records"]
    current = records["lgc-kasp-tf-v5"]
    historical = records["lgc-standard"]
    assert "legacy_numeric" not in current
    assert historical["execution_status"] == "historical"
    assert "legacy_numeric" in historical
    tails = DISCRIMINATING_AUTHORITY["kasp_chemistry"]["reporter_tails"]
    assert {item["dye"] for item in tails} == {"FAM", "HEX"}


def test_nested_cleanup_values_remain_protocol_specific() -> None:
    records = NESTED_AUTHORITY["records"]
    msz = records["neb-msz-exonuclease-i"]
    thermo = records["neb-thermolabile-exonuclease-i"]
    assert (msz["incubation_c"], msz["incubation_min"]) == (55, 15)
    assert (thermo["incubation_c"], thermo["incubation_min"]) == (37, 10)
    assert records["dutp-ung-strategy-only"]["execution_status"] == "strategy-only"
    assert records["one-tube-reference-only"]["execution_status"] == "reference-only"


def test_consensus_alignment_roles_and_population_claim_boundary_are_canonical() -> None:
    authority = json.loads(
        (ROOT / "contracts/chemistry/consensus-profiles.json").read_text(encoding="utf-8")
    )
    assert authority["records"]["mafft-7.526"]["tool_role"] == "PRIMARY"
    assert authority["records"]["muscle-5.3-audit"]["execution_status"] == "diagnostic-only"
    assert (
        authority["records"]["muscle-5.3-audit"]["sequence_decision_impact"]
        == "none-on-primary-ranking"
    )
    assert "Population-wide universality" in authority["policies"]["population_claim"]
