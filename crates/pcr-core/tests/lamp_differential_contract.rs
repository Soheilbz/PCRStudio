//! Cross-language LAMP authority/differential contract.
//!
//! Python and Web execute the same machine-readable differential corpus against
//! their numeric resolvers. Rust owns request vocabulary/compatibility rather
//! than bench numeric resolution, so this test independently consumes the same
//! corpus plus the canonical LAMP authority and verifies that every differential
//! case is representable by Rust's generated protocol vocabulary and that the
//! source-backed numeric/stage facts used by the other consumers remain identical.

use serde_json::Value;
use std::{collections::BTreeSet, fs, path::PathBuf};

include!("../src/engines/lamp_protocol_ids.generated.rs");

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

fn number_at(row: &Value, path: &[&str]) -> f64 {
    let mut current = row;
    for key in path {
        current = current
            .get(*key)
            .unwrap_or_else(|| panic!("missing authority path {}", path.join(".")));
    }
    current
        .as_f64()
        .unwrap_or_else(|| panic!("authority path {} is not numeric", path.join(".")))
}

fn assert_close(actual: f64, expected: f64, label: &str) {
    assert!(
        (actual - expected).abs() <= 1e-12,
        "{label}: expected {expected}, got {actual}"
    );
}

#[test]
fn generated_rust_protocol_ids_exactly_match_canonical_authority() {
    let authority = json("contracts/chemistry/lamp-protocols.json");
    let canonical: BTreeSet<String> = authority["protocols"]
        .as_object()
        .expect("canonical protocols must be an object")
        .keys()
        .cloned()
        .collect();
    let generated: BTreeSet<String> = LAMP_PROTOCOLS
        .iter()
        .copied()
        .filter(|id| *id != "not-selected")
        .map(str::to_owned)
        .collect();
    assert_eq!(generated, canonical);
}

#[test]
fn rust_consumes_shared_lamp_differential_corpus_without_numeric_drift() {
    let authority = json("contracts/chemistry/lamp-protocols.json");
    let corpus = json("contracts/chemistry/lamp-differential-corpus.json");
    let protocols = authority["protocols"]
        .as_object()
        .expect("canonical protocols must be an object");
    let rust_ids: BTreeSet<&str> = LAMP_PROTOCOLS.iter().copied().collect();

    for case in corpus["cases"]
        .as_array()
        .expect("differential cases must be an array")
    {
        let case_id = case["id"].as_str().expect("case id");
        let protocol_id = case["protocol"].as_str().expect("protocol id");
        assert!(
            rust_ids.contains(protocol_id),
            "{case_id}: protocol absent from generated Rust vocabulary: {protocol_id}"
        );
        let protocol = protocols
            .get(protocol_id)
            .unwrap_or_else(|| panic!("{case_id}: protocol absent from canonical authority"));
        assert_eq!(
            protocol["sequence_decision_impact"].as_str(),
            Some("none"),
            "{case_id}: bench chemistry must not alter sequence ranking"
        );

        let values = case["expected_values"]
            .as_object()
            .expect("expected_values must be an object");
        for (key, expected_value) in values {
            let expected = expected_value
                .as_f64()
                .unwrap_or_else(|| panic!("{case_id}/{key}: expected numeric value"));
            match key.as_str() {
                "reaction_volume_uL" => assert_close(
                    number_at(protocol, &["reaction_volume_uL"]),
                    expected,
                    &format!("{case_id}/{key}"),
                ),
                "hold_temperature_c" => assert_close(
                    number_at(protocol, &["hold_temperature_c"]),
                    expected,
                    &format!("{case_id}/{key}"),
                ),
                "hold_time_min" => assert_close(
                    number_at(protocol, &["hold_time_min"]),
                    expected,
                    &format!("{case_id}/{key}"),
                ),
                "lyophilized_beads_per_reaction" | "primer_mix_10x_uL" => assert_close(
                    number_at(protocol, &["chemistry", key]),
                    expected,
                    &format!("{case_id}/{key}"),
                ),
                "fip_bip_uM" => {
                    assert_close(
                        number_at(protocol, &["role_concentrations_uM", "FIP"]),
                        expected,
                        &format!("{case_id}/{key}/FIP"),
                    );
                    assert_close(
                        number_at(protocol, &["role_concentrations_uM", "BIP"]),
                        expected,
                        &format!("{case_id}/{key}/BIP"),
                    );
                }
                "f3_b3_uM" => {
                    assert_close(
                        number_at(protocol, &["role_concentrations_uM", "F3"]),
                        expected,
                        &format!("{case_id}/{key}/F3"),
                    );
                    assert_close(
                        number_at(protocol, &["role_concentrations_uM", "B3"]),
                        expected,
                        &format!("{case_id}/{key}/B3"),
                    );
                }
                "loop_uM" => {
                    assert_close(
                        number_at(protocol, &["role_concentrations_uM", "LF"]),
                        expected,
                        &format!("{case_id}/{key}/LF"),
                    );
                    assert_close(
                        number_at(protocol, &["role_concentrations_uM", "LB"]),
                        expected,
                        &format!("{case_id}/{key}/LB"),
                    );
                }
                other => panic!("{case_id}: Rust differential consumer has no mapping for {other}"),
            }
        }

        let unresolved = case["expected_unresolved"]
            .as_array()
            .expect("expected_unresolved must be an array");
        for dependency in unresolved {
            match dependency.as_str().expect("unresolved dependency id") {
                "vazyme-rp712-exact-recipe" => {
                    let status = protocol["numeric_authority_status"]
                        .as_str()
                        .expect("RP712 numeric authority status");
                    assert!(
                        status.contains("unresolved"),
                        "{case_id}: RP712 exact vendor recipe must remain unresolved"
                    );
                }
                other => panic!("{case_id}: unrecognized unresolved dependency {other}"),
            }
        }

        let stages: BTreeSet<&str> = case["expected_thermal_stage_ids"]
            .as_array()
            .expect("expected_thermal_stage_ids must be an array")
            .iter()
            .map(|v| v.as_str().expect("thermal stage id"))
            .collect();
        if stages.contains("isothermal-amplification") {
            assert!(
                protocol.get("hold_time_min").is_some(),
                "{case_id}: isothermal stage requires an authority hold time"
            );
        }
        if stages.contains("carryover-preincubation") {
            let strategy = case["python_scenario"]["preincubation_strategy"]
                .as_str()
                .expect("preincubation scenario");
            assert_eq!(strategy, "takara-ung-25c-10min");
            assert!(
                protocol["carryover_prevention"]["optional_pre_hold"].is_object(),
                "{case_id}: preincubation stage must be backed by canonical optional_pre_hold authority"
            );
        }
    }
}
