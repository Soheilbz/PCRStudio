//! Unified cross-language contract for the current PCRStudio engine registry.
//!
//! The canonical engine list is contracts/engines.toml. This suite verifies
//! generated capability projections and domain-specific scientific boundaries
//! without grouping engines by the release in which they were introduced.

use serde_json::Value;
use std::{collections::BTreeSet, fs, path::PathBuf};

include!("../src/engines/consensus_authority.generated.rs");
include!("../src/engines/discriminating_authority.generated.rs");
include!("../src/engines/assembly_authority.generated.rs");
include!("../src/engines/mutagenesis_authority.generated.rs");
include!("../src/engines/nested_authority.generated.rs");
include!("../src/engines/inverse_authority.generated.rs");
include!("../src/engines/probe_authority.generated.rs");
include!("../src/engines/race_authority.generated.rs");
include!("../src/engines/sequencing_authority.generated.rs");
include!("../src/engines/tiling_authority.generated.rs");
include!("../src/engines/engine_capabilities.generated.rs");

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("pcr-core must live under <repo>/crates/pcr-core")
        .to_path_buf()
}

fn json(rel: &str) -> Value {
    let path = repo_root().join(rel);
    serde_json::from_str(
        &fs::read_to_string(&path)
            .unwrap_or_else(|e| panic!("failed to read {}: {e}", path.display())),
    )
    .unwrap_or_else(|e| panic!("failed to parse {}: {e}", path.display()))
}

fn strings(value: &Value) -> BTreeSet<String> {
    value
        .as_array()
        .expect("array expected")
        .iter()
        .map(|row| row.as_str().expect("string expected").to_owned())
        .collect()
}

fn rust_strings(values: &[&str]) -> BTreeSet<String> {
    values.iter().map(|value| (*value).to_owned()).collect()
}

fn embedded(value: &str) -> Value {
    serde_json::from_str(value).expect("generated authority JSON must parse")
}

#[test]
fn unified_capability_projection_matches_all_registered_engines() {
    let matrix = json("knowledge/runtime/engine-capability-matrix.generated.json");
    assert_eq!(
        matrix["authority_id"].as_str(),
        Some(ENGINE_CAPABILITY_AUTHORITY_ID)
    );
    assert_eq!(matrix["engine_count"].as_u64(), Some(ENGINE_COUNT as u64));
    assert_eq!(ENGINE_COUNT, 11);

    let mut expected = BTreeSet::new();
    for (engine, row) in matrix["engines"].as_object().expect("engines") {
        for (category, key) in [
            ("feature", "feature_capabilities"),
            ("tool", "tool_capabilities"),
        ] {
            for (capability, spec) in row[key].as_object().expect("capability map") {
                expected.insert((
                    engine.clone(),
                    category.to_owned(),
                    capability.clone(),
                    spec["status"].as_str().expect("status").to_owned(),
                ));
            }
        }
    }
    let generated: BTreeSet<(String, String, String, String)> = ENGINE_CAPABILITIES
        .iter()
        .map(|(engine, category, capability, status)| {
            (
                (*engine).to_owned(),
                (*category).to_owned(),
                (*capability).to_owned(),
                (*status).to_owned(),
            )
        })
        .collect();
    assert_eq!(generated, expected);
}

#[test]
fn engine_system_covers_exactly_the_current_registry_and_corpora_are_unique() {
    let system = json("knowledge/runtime/engine-system.generated.json");
    assert_eq!(system["engine_count"].as_u64(), Some(11));
    let engines = system["engines"].as_object().expect("engines");
    assert_eq!(engines.len(), 11);
    for (engine, row) in engines {
        let corpora = row["differential_corpora"]
            .as_array()
            .expect("differential_corpora");
        assert!(!corpora.is_empty(), "{engine}: missing differential corpus");
        for rel in corpora {
            let rel = rel.as_str().expect("corpus path");
            let corpus = json(rel);
            assert_eq!(
                corpus["engine"].as_str(),
                Some(engine.as_str()),
                "{rel}: engine drift"
            );
            let cases = corpus["cases"].as_array().expect("cases");
            let ids: BTreeSet<&str> = cases
                .iter()
                .map(|r| r["id"].as_str().expect("case id"))
                .collect();
            assert!(!cases.is_empty(), "{rel}: no cases");
            assert_eq!(ids.len(), cases.len(), "{rel}: duplicate case id");
        }
    }
}

#[test]
fn generated_json_authority_embeds_match_current_canonical_sources() {
    assert_eq!(
        embedded(INVERSE_AUTHORITY_JSON),
        json("contracts/chemistry/inverse-pcr-protocols.json")
    );
    assert_eq!(
        embedded(PROBE_AUTHORITY_JSON),
        json("contracts/chemistry/qpcr-probe-protocols.json")
    );
    assert_eq!(
        embedded(RACE_AUTHORITY_JSON),
        json("contracts/chemistry/race-protocols.json")
    );
    assert_eq!(
        embedded(SEQUENCING_AUTHORITY_JSON),
        json("contracts/chemistry/sequencing-profiles.json")
    );
    assert_eq!(
        embedded(TILING_AUTHORITY_JSON),
        json("contracts/chemistry/tiling-protocols.json")
    );
}
#[test]
fn generated_rust_vocabularies_match_canonical_authorities() {
    let consensus = json("contracts/chemistry/consensus-profiles.json");
    assert_eq!(
        rust_strings(CONSENSUS_ALIGNMENT_BACKENDS),
        strings(&consensus["groups"]["alignment_backends"])
    );
    assert_eq!(
        rust_strings(CONSENSUS_CONSENSUS_POLICIES),
        strings(&consensus["groups"]["consensus_policies"])
    );
    assert_eq!(
        rust_strings(CONSENSUS_FORMULATION_MODES),
        strings(&consensus["groups"]["formulation_modes"])
    );

    let discriminating = json("contracts/chemistry/discriminating-protocols.json");
    assert_eq!(
        rust_strings(DISCRIMINATING_GEOMETRIES),
        strings(&discriminating["groups"]["geometries"])
    );
    assert_eq!(
        rust_strings(DISCRIMINATING_VARIANT_CLASSES),
        strings(&discriminating["groups"]["variant_classes"])
    );
    assert_eq!(
        rust_strings(DISCRIMINATING_PROTOCOLS),
        strings(&discriminating["groups"]["protocols"])
    );
    assert_eq!(
        Some(DISCRIMINATING_MISMATCH_MODEL_ID),
        discriminating["mismatch_model"]["model_id"].as_str(),
        "generated Rust mismatch-model identity drift",
    );

    let assembly = json("contracts/chemistry/assembly-protocols.json");
    assert_eq!(
        rust_strings(ASSEMBLY_FRAGMENT_KINDS),
        strings(&assembly["groups"]["fragment_kinds"])
    );
    assert_eq!(
        rust_strings(ASSEMBLY_METHODS),
        strings(&assembly["groups"]["methods"])
    );
    assert_eq!(
        rust_strings(ASSEMBLY_PROTOCOLS),
        strings(&assembly["groups"]["protocols"])
    );

    let mutagenesis = json("contracts/chemistry/mutagenesis-protocols.json");
    assert_eq!(
        rust_strings(MUTAGENESIS_TOPOLOGY_FAMILIES),
        strings(&mutagenesis["groups"]["topology_families"])
    );
    assert_eq!(
        rust_strings(MUTAGENESIS_PROTOCOLS),
        strings(&mutagenesis["groups"]["protocols"])
    );

    let nested = json("contracts/chemistry/nested-protocols.json");
    assert_eq!(
        rust_strings(NESTED_TRANSFER_MODES),
        strings(&nested["groups"]["transfer_modes"])
    );
    assert_eq!(
        rust_strings(NESTED_CLEANUP_PROTOCOLS),
        strings(&nested["groups"]["cleanup_protocols"])
    );
}

#[test]
fn differential_corpora_are_bound_to_the_expected_engine_and_unique_cases() {
    let corpora = [
        (
            "consensus-pair",
            "contracts/chemistry/consensus-differential-corpus.json",
        ),
        (
            "discriminating-pair",
            "contracts/chemistry/discriminating-differential-corpus.json",
        ),
        (
            "junction-primers",
            "contracts/chemistry/junction-differential-corpus.json",
        ),
        (
            "mutagenic-pair",
            "contracts/chemistry/mutagenesis-differential-corpus.json",
        ),
        (
            "nested",
            "contracts/chemistry/nested-differential-corpus.json",
        ),
    ];
    for (engine, rel) in corpora {
        let corpus = json(rel);
        assert_eq!(corpus["engine"].as_str(), Some(engine));
        let cases = corpus["cases"].as_array().expect("cases");
        let ids: BTreeSet<&str> = cases
            .iter()
            .map(|row| row["id"].as_str().expect("case id"))
            .collect();
        assert_eq!(ids.len(), cases.len(), "{engine}: duplicate case id");
        assert!(!corpus["metamorphic"]
            .as_array()
            .expect("metamorphic")
            .is_empty());
    }
}

#[test]
fn nested_cleanup_corpus_matches_canonical_vendor_numeric_authority() {
    let authority = json("contracts/chemistry/nested-protocols.json");
    let corpus = json("contracts/chemistry/nested-differential-corpus.json");
    for case in corpus["cases"].as_array().expect("cases") {
        let case_id = case["id"].as_str().expect("id");
        let protocol = match case_id {
            "msz-cleanup" => Some("neb-msz-exonuclease-i"),
            "thermolabile-cleanup" => Some("neb-thermolabile-exonuclease-i"),
            _ => None,
        };
        let Some(protocol) = protocol else { continue };
        let record = &authority["records"][protocol];
        for key in [
            "enzyme_uL",
            "first_round_product_uL_max",
            "incubation_c",
            "incubation_min",
            "inactivation_c",
            "inactivation_min",
        ] {
            assert_eq!(case["expected"][key], record[key], "{case_id}/{key} drift");
        }
        assert_eq!(record["sequence_decision_impact"].as_str(), Some("none"));
    }
}

#[test]
fn mutagenesis_and_assembly_boundary_numbers_are_canonical_not_cross_inherited() {
    let mutagenesis = json("contracts/chemistry/mutagenesis-protocols.json");
    let q5 = &mutagenesis["records"]["neb-q5-e0554"];
    assert_eq!(q5["small_insertion_max_nt"].as_u64(), Some(6));
    assert_eq!(q5["routine_insertion_max_nt"].as_u64(), Some(100));
    assert_eq!(q5["split_insertion_per_primer_max_nt"].as_u64(), Some(50));
    assert_eq!(
        q5["purification_recommended_over_primer_nt"].as_u64(),
        Some(60)
    );

    let assembly = json("contracts/chemistry/assembly-protocols.json");
    for id in [
        "neb-nebuilder-e2621",
        "neb-nebuilder-e5520",
        "neb-nebuilder-e2623",
    ] {
        let record = &assembly["records"][id];
        assert_eq!(
            record["branches"]["2-3-fragments"]["overlap_bp_min"].as_u64(),
            Some(15)
        );
        assert_eq!(
            record["branches"]["4-6-fragments"]["overlap_bp_max"].as_u64(),
            Some(30)
        );
    }
    assert_ne!(
        assembly["records"]["neb-e5510"]["selection"],
        assembly["records"]["neb-nebuilder-e2621"]["selection"]
    );
}

#[test]
fn kasp_mode_scopes_and_presence_absence_contract_are_canonical() {
    let matrix = json("knowledge/runtime/engine-capability-matrix.generated.json");
    let caps = &matrix["engines"]["discriminating-pair"]["feature_capabilities"];
    assert_eq!(
        strings(&caps["kasp-biallelic-genotype"]["scope"]),
        BTreeSet::from(["mnv".to_owned(), "snv".to_owned()]),
    );
    assert_eq!(
        strings(&caps["kasp-plus-minus"]["scope"]),
        BTreeSet::from([
            "complex-replacement".to_owned(),
            "deletion".to_owned(),
            "insertion".to_owned(),
            "presence-absence".to_owned(),
        ]),
    );

    let corpus = json("contracts/chemistry/discriminating-differential-corpus.json");
    let cases = corpus["cases"].as_array().expect("cases");
    let by_id = |wanted: &str| {
        cases
            .iter()
            .find(|row| row["id"].as_str() == Some(wanted))
            .unwrap_or_else(|| panic!("missing {wanted}"))
    };
    let refusal = by_id("kasp-biallelic-indel-refusal");
    assert_eq!(
        refusal["request"]["kasp_assay_mode"].as_str(),
        Some("biallelic-genotype")
    );
    assert_eq!(refusal["expected"]["status"].as_str(), Some("refused"));

    let pa = by_id("kasp-plus-minus-presence-absence");
    assert_eq!(
        pa["request"]["kasp_assay_mode"].as_str(),
        Some("plus-minus-presence-absence")
    );
    assert_eq!(
        pa["request"]["variant"]["type"].as_str(),
        Some("presence-absence")
    );
    assert_eq!(pa["request"]["variant"]["ref"].as_str(), Some("ACGT"));
    assert_eq!(pa["request"]["variant"]["alt"].as_str(), Some(""));
    assert_eq!(
        pa["expected"]["variant_shape"].as_str(),
        Some("reference-present/alternate-absent")
    );
}

#[test]
fn qpcr_conventional_is_executable_and_mgb_requires_external_authority() {
    let probe = json("contracts/chemistry/qpcr-probe-protocols.json");
    assert_eq!(
        probe["records"]["thermofisher-taqman-conventional"]["execution_status"],
        "executable"
    );
    assert_eq!(
        probe["records"]["idt-primetime-conventional"]["execution_status"],
        "executable"
    );
    assert_eq!(
        probe["records"]["taqman-mgb-reference"]["execution_status"],
        "external-authority-required"
    );
    assert_eq!(
        probe["records"]["idt-primetime-conventional"]["probe_constraints"]["length_max"],
        28
    );
    assert!(
        probe["records"]["idt-primetime-conventional"]["probe_constraints"]
            .get("length_min")
            .is_none()
    );
    assert!(
        probe["records"]["idt-primetime-conventional"]["probe_constraints"]
            .get("length_opt")
            .is_none()
    );
    assert_eq!(
        probe["records"]["idt-primetime-conventional"]["probe_tm_delta_min_c"],
        6.0
    );
}

#[test]
fn race_named_kits_do_not_cross_wire() {
    let race = json("contracts/chemistry/race-protocols.json");
    let first = &race["records"]["firstchoice-rlm-race"];
    assert_eq!(first["execution_status"], "executable");
    assert_eq!(first["source_revision"], "Rev A");
    assert_eq!(
        first["partners"]["5prime:primary"]["sequence"],
        "GCTGATGGCGATGAATGAACACTG"
    );
    assert_eq!(
        first["partners"]["3prime:nested"]["sequence"],
        "CGCGGATCCGAATTAATACGACTCACTATAGG"
    );
    assert_eq!(
        race["records"]["smarter-race-source-limited"]["execution_status"],
        "source-limited"
    );
    assert_eq!(
        race["records"]["smarter-race-current"]["execution_status"],
        "executable-if-complete"
    );
    assert_ne!(
        first["partners"],
        race["records"]["generacer-kit-25-0355-vl"]["partners"]
    );
}

#[test]
fn inverse_and_tiling_keep_intentional_fail_closed_boundaries() {
    let inverse = json("contracts/chemistry/inverse-pcr-protocols.json");
    assert_eq!(
        inverse["records"]["one-sided-internal-cut-reference"]["execution_status"],
        "reference-only"
    );
    assert_eq!(
        inverse["records"]["restriction-self-ligation"]["execution_status"],
        "executable"
    );

    let tiling = json("contracts/chemistry/tiling-protocols.json");
    assert_eq!(
        tiling["records"]["primalscheme3-3.3.0"]["execution_status"],
        "executable-if-installed"
    );
    assert_eq!(
        tiling["records"]["olivar-1.3.3"]["execution_status"],
        "executable-if-installed"
    );
    assert_eq!(
        tiling["records"]["olivar-1.3.3"]["coordinate_system"],
        "1-based closed except BED export"
    );
    assert_eq!(
        tiling["records"]["artic-primer-bed-v3"]["coordinate_system"],
        "0-based half-open"
    );
}
