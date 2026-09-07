use super::*;
use serde_json::json;

fn engine() -> FlankingPair {
    FlankingPair::new()
}

#[test]
fn known_digital_platforms_resolve_canonical_names_without_free_text() {
    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "assay": {"id": "digital-pcr"},
        "digitalProtocol": "not-selected",
        "digitalPartitionFormat": "droplet",
        "digitalPlatformId": "bio-rad-qx600",
        "digitalFragmentationState": "not-assessed",
    }))
    .expect("known platform identity must not require free-text name");
    assert_eq!(parsed.to_worker()["digital_platform_name"], "Bio-Rad QX600");

    let conflict = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
            "digitalProtocol": "not-selected",
            "digitalPartitionFormat": "droplet",
            "digitalPlatformId": "bio-rad-qx600",
            "digitalPlatformName": "Bio-Rad QX700",
            "digitalFragmentationState": "not-assessed",
        }))
        .expect_err("conflicting platform name must fail closed");
    assert!(
        conflict
            .to_string()
            .contains("different digitalPlatformName"),
        "{conflict}"
    );
}

#[test]
fn digital_pcr_requires_explicit_partition_platform_and_fragmentation_handoff() {
    let missing = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
        }))
        .expect_err("missing dPCR run context");
    assert!(
        missing.to_string().contains("digitalPartitionFormat"),
        "{missing}"
    );

    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "assay": {"id": "digital-pcr"},
        "digitalPartitionFormat": "chip",
        "digitalPlatformId": "other-validated",
        "digitalPlatformName": "validated chip platform",
        "digitalFragmentationState": "not-required",
    }))
    .expect("explicit dPCR handoff");
    let payload = parsed.to_worker();
    assert_eq!(payload["digital_partition_format"], "chip");
    assert_eq!(payload["digital_platform_id"], "other-validated");
    assert_eq!(payload["digital_platform_name"], "validated chip platform");
    assert_eq!(payload["digital_fragmentation_state"], "not-required");
}
