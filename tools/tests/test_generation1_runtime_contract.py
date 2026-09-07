"""Generation-1 orchestration contract tests.

These tests are part of the Linux handoff and are intentionally not executed
inside the exchange environment. Codex should run them in the real repository
on Linux together with the existing suite.
"""

from pcr_tools.external_validation import selected_oligos
from pcr_tools.runtime_contract import (
    ENGINE_BINDINGS,
    MODULE_CONTRACTS,
    MODULE_TO_COMMAND,
    MODULE_TO_ENGINE,
    assay_identity,
    module_contract,
    validate_required_context,
)


def test_exactly_21_modules_resolve_to_exactly_11_engines() -> None:
    assert len(MODULE_TO_ENGINE) == 21
    assert len(set(MODULE_TO_ENGINE.values())) == 11
    assert set(MODULE_TO_ENGINE.values()) == set(ENGINE_BINDINGS)
    assert set(MODULE_TO_ENGINE) == set(MODULE_TO_COMMAND) == set(MODULE_CONTRACTS)


def test_runtime_module_contract_uses_cross_layer_canonical_fields() -> None:
    contract = module_contract("qpcr-probe")
    assert contract["module_id"] == "qpcr-probe"
    assert contract["engine"] == "pair-and-probe"
    assert contract["command"] == "probe"
    assert contract["required_context"] == [
        "probe_protocol",
        "probe_chemistry",
        "probe_reporter",
        "probe_quencher",
    ]
    assert contract["wire_required_context"] == contract["required_context"]
    assert contract["wire_required_any_of"] == []
    assert (
        contract["fallback"]
        == "never_mix_probe_chemistries_or_apply_mgb_vendor_tm_window_to_unmodified_dna_tm_model"
    )


def test_required_context_is_presence_based_not_string_typed() -> None:
    # Numeric zero and boolean false can be scientifically meaningful explicit
    # values (nested margin=0 and supported two-tube single_tube=false).  The
    # shared contract layer proves presence only; the owning engine validates
    # type/range/semantics.
    validate_required_context(
        {
            "shares": "nothing",
            "margin": 0,
            "single_tube": False,
            "carryover_prevention": "not-selected",
            "transfer_mode": "direct",
        },
        "nested-pcr",
    )


def test_required_context_refuses_missing_or_empty_values() -> None:
    for request in (
        {"shares": "nothing", "margin": 0, "single_tube": False, "transfer_mode": "direct"},
        {
            "shares": "nothing",
            "margin": 0,
            "single_tube": False,
            "carryover_prevention": "   ",
            "transfer_mode": "direct",
        },
    ):
        try:
            validate_required_context(request, "nested-pcr")
        except ValueError as error:
            assert "carryover_prevention" in str(error)
        else:
            raise AssertionError("missing/blank required context must fail closed")


def test_conditional_required_context_is_branch_aware() -> None:
    base = {
        "digital_partition_format": "chip",
        "digital_platform_id": "bio-rad-qx200",
        "digital_fragmentation_state": "not-assessed",
    }
    validate_required_context(base, "digital-pcr")

    try:
        validate_required_context(
            {**base, "digital_platform_id": "other-validated"},
            "digital-pcr",
        )
    except ValueError as error:
        assert "digital_platform_name" in str(error)
    else:
        raise AssertionError("conditional platform identity must fail closed")

    validate_required_context(
        {
            **base,
            "digital_platform_id": "other-validated",
            "digital_platform_name": "qualified platform",
        },
        "digital-pcr",
    )


def test_required_context_resolves_lower_camel_worker_aliases_and_refuses_conflicts() -> None:
    rust_payload = {
        "tilingBackend": "primalscheme3",
        "tilingOperation": "scheme-create",
        "tilingAlignmentMode": "minimap2",
        "overlap": 100,
        "pools": 2,
    }
    validate_required_context(rust_payload, "tiled-scheme")

    contradictory = {**rust_payload, "tiling_operation": "panel-create"}
    try:
        validate_required_context(contradictory, "tiled-scheme")
    except ValueError as error:
        assert "conflicting runtime context aliases" in str(error)
        assert "tiling_operation" in str(error)
        assert "tilingOperation" in str(error)
    else:
        raise AssertionError("contradictory snake/camel context aliases must fail closed")


def test_required_context_can_address_nested_runtime_objects() -> None:
    complete = {
        "restriction_digest_protocol": "neb-cutsmart-standard",
        "restriction_dephosphorylation_protocol": "none",
        "restriction_ligation_protocol": "neb-t4-dna-ligase-m0202",
        "tails": {
            "tail_protocol": "neb-general-6bp",
            "forward_enzyme": "EcoRI",
            "reverse_enzyme": "BamHI",
            "forward_protective_sequence": "GACTTA",
            "reverse_protective_sequence": "CAGTTA",
        },
    }
    validate_required_context(complete, "restriction-cloning")

    broken = {"tails": dict(complete["tails"])}
    del broken["tails"]["reverse_protective_sequence"]
    try:
        validate_required_context(broken, "restriction-cloning")
    except ValueError as error:
        assert "tails.reverse_protective_sequence" in str(error)
    else:
        raise AssertionError("nested restriction-tail evidence must fail closed")


def test_wire_context_is_explicit_for_nested_form_normalization() -> None:
    validate_required_context(
        {"flanking_numeric_context": {"additive": "high-gc-enhancer", "gc_enhancer_percent": 10.0}},
        "standard-pcr",
    )
    try:
        validate_required_context(
            {"flanking_numeric_context": {"additive": "high-gc-enhancer"}},
            "standard-pcr",
        )
    except ValueError as error:
        assert "flanking_numeric_context.gc_enhancer_percent" in str(error)
    else:
        raise AssertionError("nested wire requirement must fail closed")

    mutagenesis = {
        "mutagenesis_topology": "q5-back-to-back",
        "post_amplification_protocol": "neb-q5-e0554",
    }
    try:
        validate_required_context(mutagenesis, "site-directed-mutagenesis")
    except ValueError as error:
        assert "edit | edits | amino_acid_edit | library_edit" in str(error)
    else:
        raise AssertionError("mutagenesis wire representation must be explicit")
    validate_required_context(
        {**mutagenesis, "edit": {"kind": "substitute", "at": 4, "to": "T", "replacing": 1}},
        "site-directed-mutagenesis",
    )


def test_module_engine_identity_refuses_contradictory_payload() -> None:
    request = {"assay": {"id": "qpcr-probe", "engine": "flanking-pair"}}
    try:
        assay_identity(request, "probe")
    except ValueError as error:
        assert "pair-and-probe" in str(error)
    else:
        raise AssertionError("a contradictory module/engine payload must be refused")


def test_validator_boundary_separates_ordered_molecule_from_annealing_core() -> None:
    result = {
        "order_sheet": [
            {
                "name": "tailed_F",
                "sequence": "GGGGACGTACGT",
                "tail_sequence": "GGGG",
                "annealing_sequence": "ACGTACGT",
                "kind": "primer",
            },
            {
                "name": "probe_P",
                "sequence": "AACCGGTT",
                "annealing_sequence": "AACCGGTT",
                "tail_sequence": "",
                "kind": "probe",
            },
            {
                "name": "tailed_F",
                "sequence": "GGGGACGTACGT",
                "tail_sequence": "GGGG",
                "annealing_sequence": "ACGTACGT",
                "kind": "primer",
            },
        ]
    }
    assert selected_oligos(result) == [
        {
            "name": "tailed_F",
            "kind": "primer",
            "ordered_sequence": "GGGGACGTACGT",
            "annealing_sequence": "ACGTACGT",
            "tail_sequence": "GGGG",
            "pool": None,
            "tube": None,
            "note": None,
        },
        {
            "name": "probe_P",
            "kind": "probe",
            "ordered_sequence": "AACCGGTT",
            "annealing_sequence": "AACCGGTT",
            "tail_sequence": "",
            "pool": None,
            "tube": None,
            "note": None,
        },
    ]


def test_explicit_tail_contract_must_be_consistent() -> None:
    result = {
        "order_sheet": [
            {
                "name": "broken",
                "sequence": "TTTTACGT",
                "tail_sequence": "GGGG",
                "annealing_sequence": "ACGT",
            }
        ]
    }
    try:
        selected_oligos(result)
    except ValueError as error:
        assert "inconsistent" in str(error)
    else:
        raise AssertionError("an inconsistent tail/core contract must fail closed")
