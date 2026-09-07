from __future__ import annotations

import math

import pytest

from pcr_tools.cloning_coding import resolve_cloning_coding_context
from pcr_tools.dpcr_quantification import DpcrQuantificationError, quantify_dpcr
from pcr_tools.restriction_calculators import (
    dna_fmol,
    enzyme_volume_ul,
    final_glycerol_percent,
    insert_mass_ng,
    plan_double_digest,
)
from pcr_tools.restriction_performance import PERFORMANCE_BY_NAME, plan_neb_double_digest
from pcr_tools.rpa_screening import screening_cohort
from pcr_tools.species_panel import (
    SpeciesPanelError,
    manifest_sha256,
    parse_accession_version_manifest,
    parse_record_metadata_manifest,
    record_metadata_sha256,
    surveillance_diff,
    validate_record_metadata,
)


def test_dpcr_poisson_and_ci_are_finite_for_unsaturated_run():
    result = quantify_dpcr(
        accepted_partitions=20_000,
        positive_partitions=2_000,
        partition_volume_nl=0.85,
        dilution_factor=2,
        analysed_volume_ul=8.5,
    )
    assert result.positive_fraction == pytest.approx(0.1)
    assert result.lambda_copies_per_partition == pytest.approx(-math.log(0.9))
    assert result.copies_per_ul > 0
    assert result.ci95_copies_per_ul[0] < result.copies_per_ul < result.ci95_copies_per_ul[1]
    assert result.copies_per_reaction == pytest.approx(result.copies_per_ul * 8.5)
    assert result.design_decision_impact == "none"


def test_dpcr_refuses_saturation_and_unknown_partition_volume():
    with pytest.raises(DpcrQuantificationError, match="saturated"):
        quantify_dpcr(accepted_partitions=100, positive_partitions=100, partition_volume_nl=1)
    with pytest.raises(DpcrQuantificationError, match="partition_volume"):
        quantify_dpcr(accepted_partitions=100, positive_partitions=10, partition_volume_nl=0)


def test_restriction_molar_and_volume_calculators():
    assert dna_fmol(mass_ng=50, length_bp=2500) == pytest.approx(30.30303, rel=1e-5)
    assert insert_mass_ng(
        vector_mass_ng=50,
        vector_length_bp=5000,
        insert_length_bp=1000,
        insert_to_vector_molar_ratio=3,
    ) == pytest.approx(30)
    assert enzyme_volume_ul(required_units=10, stock_units_per_ul=20) == pytest.approx(0.5)
    assert final_glycerol_percent(enzyme_volumes_ul=[1, 1], reaction_volume_ul=50) == pytest.approx(
        2.0
    )


def test_double_digest_is_source_fact_driven_and_fail_closed():
    a = {
        "name": "A",
        "temperature_c": 37,
        "buffers": {"rCutSmart": 100, "r3.1": 50},
        "heat_inactivation": "65C/20m",
    }
    b = {
        "name": "B",
        "temperature_c": 37,
        "buffers": {"rCutSmart": 100, "r3.1": 10},
        "heat_inactivation": None,
    }
    plan = plan_double_digest(first=a, second=b)
    assert plan["mode"] == "simultaneous" and plan["buffer"] == "rCutSmart"
    with pytest.raises(ValueError, match="buffer/activity"):
        plan_double_digest(first={"name": "A", "temperature_c": 37}, second=b)


def test_species_manifest_requires_accession_versions_and_diff_is_version_aware():
    old = parse_accession_version_manifest("NC_000001.11\nNZ_CP000001.1\n")
    assert manifest_sha256(old) == manifest_sha256(tuple(old))
    with pytest.raises(SpeciesPanelError, match="versioned accession"):
        parse_accession_version_manifest("NC_000001\n")
    diff = surveillance_diff(old, ("NC_000001.12", "NZ_CP000002.1"))
    assert ("NC_000001.11", "NC_000001.12") in diff.version_changed
    assert "NZ_CP000002.1" in diff.added
    assert "NZ_CP000001.1" in diff.removed


def test_current_restriction_performance_snapshot_covers_curated_geometry_registry():
    import json
    from importlib.resources import files

    geometry = json.loads(
        files("pcr_tools")
        .joinpath("data/restriction_enzyme_registry.json")
        .read_text(encoding="utf-8")
    )
    assert set(PERFORMANCE_BY_NAME) == {row["name"] for row in geometry["enzymes"]}
    plan = plan_neb_double_digest("XhoI", "NdeI")
    assert plan["mode"] == "simultaneous"
    assert plan["buffer"] in {"r2.1", "r3.1", "rCutSmart"}
    # ApaI and BglII do not share a >=50% buffer in the pinned supplier snapshot.
    sequential = plan_neb_double_digest("ApaI", "BglII")
    assert sequential["mode"] == "sequential-required"


def test_species_snapshot_hashes_are_order_comment_and_whitespace_invariant():
    a = parse_accession_version_manifest("# panel\nNC_000002.2\nNC_000001.1\n")
    b = parse_accession_version_manifest(" NC_000001.1 note\n\nNC_000002.2\n")
    assert a == b == ("NC_000001.1", "NC_000002.2")
    assert manifest_sha256(a) == manifest_sha256(b)

    rows_a = parse_record_metadata_manifest(
        "b\tNC_000002.2\texclusivity\tlinear\t\tnear\n"
        "a\tNC_000001.1\tinclusivity\tcircular\t2\tcore\n"
    )
    rows_b = parse_record_metadata_manifest(
        "# same evidence, different order\n"
        "a\tNC_000001.1\tinclusivity\tcircular\t2.0\tcore\n"
        "b\tNC_000002.2\texclusivity\tlinear\t\tnear\n"
    )
    assert record_metadata_sha256(rows_a) == record_metadata_sha256(rows_b)
    summary = validate_record_metadata(
        rows_a,
        accessions=a,
        inclusivity_record_ids=("a",),
        exclusivity_record_ids=("b",),
    )
    assert summary["topology_counts"]["circular"] == 1
    assert summary["population_weighting_status"].startswith("complete-user-declared")


def test_rpa_screening_cohort_is_deterministic_and_never_reorders_primary_ranking():
    ranked = [
        {
            "candidate": i,
            "score": 100.0 - i,
            "left_at": {"start": i * 5},
            "right_at": {"start": 200 + i * 7},
            "amplicon": "A" * 150,
        }
        for i in range(8)
    ]
    first = screening_cohort(ranked, maximum=4, min_coordinate_distance=20)
    second = screening_cohort(list(ranked), maximum=4, min_coordinate_distance=20)
    assert first == second
    ranks = [row["primary_rank"] for row in first["pairs"]]
    assert ranks == sorted(ranks)
    assert first["decision_impact"] == "none-on-primary-ranking"


def test_cloning_coding_context_validates_exact_insert_frame_without_changing_sequence_decision():
    insert = "ATG" + "GCC" * 9 + "TAA"
    preserved = resolve_cloning_coding_context(
        {
            "cloning_coding_intent": "preserve-orf",
            "cloning_cds_start": 0,
            "cloning_cds_end": len(insert),
            "cloning_stop_codon_policy": "preserve",
        },
        insert_sequence=insert,
    )
    assert preserved["terminal_stop_present"] is True
    assert preserved["sequence_decision_impact"] == "none"
    with pytest.raises(ValueError, match="does not include the terminal stop"):
        resolve_cloning_coding_context(
            {
                "cloning_coding_intent": "preserve-orf",
                "cloning_cds_start": 0,
                "cloning_cds_end": len(insert),
                "cloning_stop_codon_policy": "remove",
            },
            insert_sequence=insert,
        )
    in_frame = resolve_cloning_coding_context(
        {
            "cloning_coding_intent": "in-frame-fusion",
            "cloning_cds_start": 0,
            "cloning_cds_end": len(insert) - 3,
            "cloning_stop_codon_policy": "remove",
            "cloning_vector_junction_frame": 0,
        },
        insert_sequence=insert,
    )
    assert in_frame["phase_status"].startswith("declared-phase-compatible")
    with pytest.raises(ValueError, match="out of frame"):
        resolve_cloning_coding_context(
            {
                "cloning_coding_intent": "in-frame-fusion",
                "cloning_cds_start": 0,
                "cloning_cds_end": len(insert) - 3,
                "cloning_stop_codon_policy": "remove",
                "cloning_vector_junction_frame": 1,
            },
            insert_sequence=insert,
        )


def test_dpcr_and_restriction_calculators_obey_basic_metamorphic_properties():
    concentrations = [
        quantify_dpcr(
            accepted_partitions=20_000, positive_partitions=p, partition_volume_nl=0.85
        ).copies_per_ul
        for p in (100, 500, 1_000, 5_000)
    ]
    assert concentrations == sorted(concentrations)
    base = insert_mass_ng(
        vector_mass_ng=25,
        vector_length_bp=5000,
        insert_length_bp=1000,
        insert_to_vector_molar_ratio=3,
    )
    assert insert_mass_ng(
        vector_mass_ng=50,
        vector_length_bp=5000,
        insert_length_bp=1000,
        insert_to_vector_molar_ratio=3,
    ) == pytest.approx(base * 2)
    assert insert_mass_ng(
        vector_mass_ng=25,
        vector_length_bp=5000,
        insert_length_bp=1000,
        insert_to_vector_molar_ratio=6,
    ) == pytest.approx(base * 2)


def test_shared_python_browser_numeric_differential_corpus_matches_python_authority():
    import json
    from pathlib import Path

    from pcr_tools.flanking_numeric_recipes import resolve_numeric_recipe

    root = Path(__file__).resolve().parents[2]
    corpus = json.loads(
        (root / "contracts/chemistry/flanking-differential-corpus.json").read_text(encoding="utf-8")
    )
    for case in corpus["cases"]:
        result = resolve_numeric_recipe(
            case["protocol"], case["module"], scenario=case.get("python_scenario") or {}
        )
        for key, expected in case.get("expected_values", {}).items():
            assert result["values"].get(key) == pytest.approx(expected), f"{case['id']}:{key}"
        unresolved = {row["id"] for row in result["unresolved_numeric_dependencies"]}
        assert set(case.get("expected_unresolved", [])) <= unresolved, case["id"]
        assert result["sequence_decision_impact"] == "none"


def test_digital_consumable_platform_matrix_is_fail_closed_and_m0689_colony_is_executable():
    from pcr_tools.registries.flanking_protocols import colony_context, digital_context

    qx700 = {
        "digital_partition_format": "droplet",
        "digital_platform_id": "bio-rad-qx700",
        "digital_platform_name": "Bio-Rad QX700",
        "digital_fragmentation_state": "not-assessed",
        "digital_protocol": "bio-rad-qx700-naica-evagreen",
        "flanking_numeric_context": {"digital_consumable_id": "qx700-rdg16"},
    }
    result = digital_context(qx700, assay_id="digital-pcr")
    assert result and result["consumable_id"] == "qx700-rdg16"

    nio = dict(qx700)
    nio["digital_platform_id"] = "bio-rad-nio"
    nio.pop("digital_platform_name")
    nio_result = digital_context(nio, assay_id="digital-pcr")
    assert nio_result and nio_result["platform_name"] == "Bio-Rad Nio"
    assert nio_result["consumable_id"] == "qx700-rdg16"

    naica = dict(qx700)
    naica["digital_platform_id"] = "bio-rad-naica"
    naica.pop("digital_platform_name")
    naica["flanking_numeric_context"] = {"digital_consumable_id": "naica-sapphire-chip"}
    naica_result = digital_context(naica, assay_id="digital-pcr")
    assert naica_result and naica_result["platform_name"] == "Bio-Rad naica"
    assert naica_result["consumable_id"] == "naica-sapphire-chip"

    dedicated_wrong_platform = dict(nio)
    dedicated_wrong_platform["digital_protocol"] = "bio-rad-qx700-evagreen-supermix"
    with pytest.raises(ValueError, match="not source-backed"):
        digital_context(dedicated_wrong_platform, assay_id="digital-pcr")

    qx600 = {
        "digital_partition_format": "droplet",
        "digital_platform_id": "bio-rad-qx600",
        "digital_fragmentation_state": "not-assessed",
        "digital_protocol": "not-selected",
    }
    qx600_result = digital_context(qx600, assay_id="digital-pcr")
    assert qx600_result and qx600_result["platform_name"] == "Bio-Rad QX600"
    qx600_evagreen = dict(qx600)
    qx600_evagreen["digital_protocol"] = "bio-rad-qx200-evagreen"
    assert (
        digital_context(qx600_evagreen, assay_id="digital-pcr")["protocol_id"]
        == "bio-rad-qx200-evagreen"
    )

    qx_one_evagreen = dict(qx600_evagreen)
    qx_one_evagreen["digital_platform_id"] = "bio-rad-qx-one"
    assert (
        digital_context(qx_one_evagreen, assay_id="digital-pcr")["platform_name"]
        == "Bio-Rad QX ONE"
    )

    qx_continuum = dict(qx600)
    qx_continuum["digital_platform_id"] = "bio-rad-qx-continuum"
    with pytest.raises(ValueError, match=r"Pair\+Probe"):
        digital_context(qx_continuum, assay_id="digital-pcr")
    conflicting_name = dict(qx600)
    conflicting_name["digital_platform_name"] = "Bio-Rad QX700"
    with pytest.raises(ValueError, match="different platform name"):
        digital_context(conflicting_name, assay_id="digital-pcr")

    absolute_q = dict(qx600)
    absolute_q["digital_platform_id"] = "thermo-absolute-q"
    with pytest.raises(ValueError, match=r"Pair\+Probe"):
        digital_context(absolute_q, assay_id="digital-pcr")

    invalid = dict(qx700)
    invalid["flanking_numeric_context"] = {"digital_consumable_id": "qiacuity-26k"}
    with pytest.raises(ValueError, match="not source-backed"):
        digital_context(invalid, assay_id="digital-pcr")

    colony = colony_context(
        {
            "colony_host_class": "bacterial",
            "colony_preparation": "direct-transfer",
            "colony_protocol_id": "neb-onetaq-m0689-colony",
        },
        assay_id="colony-pcr",
    )
    assert colony and colony["protocol_id"] == "neb-onetaq-m0689-colony"
    assert "Supplemental Colony-PCR Protocol" in colony["protocol_name"]


def test_species_accession_authority_fails_closed_on_suppressed_replaced_and_snapshot_drift():
    from pcr_tools.species_panel import (
        parse_accession_authority_manifest,
        validate_accession_authority,
    )

    current = parse_accession_authority_manifest(
        "NC_000001.1\t562\tcurrent\t\tRefSeq-232\tTaxonomy-2026-09\n"
        "NC_000002.2\t562\tcurrent\t\tRefSeq-232\tTaxonomy-2026-09\n"
    )
    summary = validate_accession_authority(
        current,
        accessions=("NC_000001.1", "NC_000002.2"),
        target_taxid=562,
        sequence_database_snapshot="RefSeq-232",
        taxonomy_snapshot="Taxonomy-2026-09",
    )
    assert summary["status_counts"]["current"] == 2
    assert summary["all_records_match_target_taxid"] is True

    suppressed = parse_accession_authority_manifest(
        "NC_000001.1\t562\tsuppressed\t\tRefSeq-232\tTaxonomy-2026-09\n"
    )
    with pytest.raises(SpeciesPanelError, match="suppressed"):
        validate_accession_authority(
            suppressed,
            accessions=("NC_000001.1",),
            target_taxid=562,
            sequence_database_snapshot="RefSeq-232",
            taxonomy_snapshot="Taxonomy-2026-09",
        )

    replaced = parse_accession_authority_manifest(
        "NC_000001.1\t562\treplaced\tNC_000001.2\tRefSeq-232\tTaxonomy-2026-09\n"
    )
    with pytest.raises(SpeciesPanelError, match=r"NC_000001.1->NC_000001.2"):
        validate_accession_authority(
            replaced,
            accessions=("NC_000001.1",),
            target_taxid=562,
            sequence_database_snapshot="RefSeq-232",
            taxonomy_snapshot="Taxonomy-2026-09",
        )

    with pytest.raises(SpeciesPanelError, match="sequence-database snapshot"):
        validate_accession_authority(
            current,
            accessions=("NC_000001.1", "NC_000002.2"),
            target_taxid=562,
            sequence_database_snapshot="RefSeq-233",
            taxonomy_snapshot="Taxonomy-2026-09",
        )
