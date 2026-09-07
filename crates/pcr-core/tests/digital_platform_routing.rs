use pcr_core::{Engine, FlankingPair};
use serde_json::json;

#[test]
fn qx600_and_qx_one_accept_the_reviewed_qx200_evagreen_chemistry() {
    let engine = FlankingPair::new();
    for platform in ["bio-rad-qx600", "bio-rad-qx-one"] {
        engine
            .validate(&json!({
                "template": "ACGTACGTACGT",
                "assay": {"id": "digital-pcr"},
                "digitalProtocol": "bio-rad-qx200-evagreen",
                "digitalPartitionFormat": "droplet",
                "digitalPlatformId": platform,
                "digitalFragmentationState": "not-assessed",
            }))
            .expect("reviewed QX200 EvaGreen chemistry is source-backed for QX600/QX ONE");
    }
}

#[test]
fn qx_continuum_routes_to_pair_and_probe_instead_of_inventing_dye_chemistry() {
    let error = FlankingPair::new()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
            "digitalProtocol": "not-selected",
            "digitalPartitionFormat": "droplet",
            "digitalPlatformId": "bio-rad-qx-continuum",
            "digitalFragmentationState": "not-assessed",
        }))
        .expect_err("QX Continuum reviewed route is probe-oriented");
    assert!(error.to_string().contains("Pair+Probe"), "{error}");
}
