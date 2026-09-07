use super::*;

fn engine() -> FlankingPair {
    FlankingPair::new()
}

#[test]
fn an_empty_template_is_refused_before_a_process_starts() {
    let error = engine()
        .validate(&json!({ "template": "   " }))
        .expect_err("nothing to design against");
    assert!(matches!(error, CoreError::InvalidRequest(_)));
}

#[test]
fn a_field_nobody_recognises_is_refused_rather_than_ignored() {
    // A typo in a parameter name that is silently dropped is a run whose
    // settings are not the settings that were asked for.
    let error = engine()
        .validate(&json!({ "template": "ACGT", "polymerse": "taq-standard" }))
        .expect_err("unknown field");
    assert!(error.to_string().contains("polymerse"));
}

#[test]
fn half_a_target_is_refused_because_the_other_half_would_be_ignored() {
    let error = engine()
        .validate(&json!({ "template": "ACGT", "targetStart": 10 }))
        .expect_err("no length");
    assert!(error.to_string().contains("length"));
}

#[test]
fn a_template_too_large_for_one_request_says_how_large() {
    let error = engine()
        .validate(&json!({ "template": "A".repeat(MAX_TEMPLATE_BASES + 1) }))
        .expect_err("too big");
    assert!(error.to_string().contains("region"));
}

#[test]
fn the_wire_vocabulary_is_translated_rather_than_passed_through() {
    // camelCase on the wire, snake_case to the worker. Passing it through
    // unchanged is how `howMany` gets accepted at the edge and ignored at
    // the far end, which is a run with settings nobody chose.
    let parsed = parse(&json!({
        "template": "ACGTACGTACGTACGTACGT",
        "howMany": 3,
        "targetStart": 2,
        "targetLength": 4,
    }))
    .expect("a valid request");

    let payload = parsed.to_worker();
    assert_eq!(payload["how_many"], 3);
    assert_eq!(payload["target_start"], 2);
    assert_eq!(payload["target_length"], 4);
    assert!(payload.get("howMany").is_none());
}

#[test]
fn what_was_not_asked_for_is_not_sent() {
    // An absent field must stay absent rather than arriving as null, so
    // the worker's own defaults are what apply.
    let parsed = parse(&json!({ "template": "ACGT" })).expect("valid");
    let payload = parsed.to_worker();
    assert_eq!(payload.as_object().expect("an object").len(), 1);
}

#[test]
fn this_engine_still_declares_the_matrix_row_the_registry_checks() {
    assert_eq!(engine().id(), EngineId::FlankingPair);
    assert!(engine().accepts().contains(&Modifier::Multiplex));
}

#[test]
fn avoided_regions_reach_the_worker_in_its_own_vocabulary() {
    let request: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTACGTACGTACGT",
        "excluded": [[4, 6]],
    }))
    .expect("a well-formed request");
    request.check().expect("a region inside the template");
    assert_eq!(request.to_worker()["excluded"], json!([[4, 6]]));
}

#[test]
fn restriction_cloning_refuses_bare_primers() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "assay": {"id": "restriction-cloning"},
            "cloningVector": "ACGTACGTACGTACGTACGTACGT",
            "cloningVectorTopology": "circular",
            "restrictionDigestProtocol": "neb-cutsmart-standard",
            "restrictionDephosphorylationProtocol": "none",
            "restrictionLigationProtocol": "neb-t4-dna-ligase-m0202"
        }))
        .expect_err("restriction cloning without tails");
    assert!(
        error
            .to_string()
            .contains("two-ended restriction-tail strategy"),
        "{error}"
    );
}

#[test]
fn explicit_protective_sequences_reach_the_worker_without_being_dropped() {
    let parsed = parse(&json!({
        "template": "ACGTACGTACGTACGTACGT",
        "tails": {
            "tailProtocol": "neb-general-6bp",
            "forwardEnzyme": "EcoRI",
            "reverseEnzyme": "BamHI",
            "protectiveBases": 6,
            "forwardProtectiveSequence": "GACTTA",
            "reverseProtectiveSequence": "CAGTTA"
        },
    }))
    .expect("a valid request");

    let tails = parsed.to_worker()["tails"].clone();
    assert_eq!(tails["forward_protective_sequence"], "GACTTA");
    assert_eq!(tails["reverse_protective_sequence"], "CAGTTA");
}

#[test]
fn specificity_v5_mismatch_budget_reaches_the_worker_in_snake_case() {
    let parsed = parse(&json!({
        "template": "ACGTACGTACGTACGTACGT",
        "maxMismatches": 2,
    }))
    .expect("a valid request");

    let payload = parsed.to_worker();
    assert_eq!(payload["max_mismatches"], 2);
    assert!(payload.get("maxMismatches").is_none());
}

#[test]
fn removed_specificity_v4_clamp_is_refused_as_an_unknown_field() {
    let error = parse(&json!({
        "template": "ACGTACGTACGT",
        "clamp": 5,
    }))
    .expect_err("v5 has no exact-terminal-clamp request field");
    assert!(error.to_string().contains("unknown field"), "{error}");
}

#[test]
fn named_standard_pcr_protocols_reach_the_worker_without_aliasing() {
    for protocol in [
        "neb-taq-m0273",
        "neb-q5-hot-start-m0493",
        "neb-q5u-hot-start-m0515",
        "thermo-dreamtaq-hot-start-ep170x",
        "thermo-phusion-plus",
        "promega-gotaq-m300",
        "neb-onetaq-hot-start-m0484",
        "neb-onetaq-hot-start-gc-m0485",
        "neb-onetaq-hot-start-quickload-m0488",
        "neb-onetaq-hot-start-quickload-gc-m0489",
        "pcrbio-hs-taq-mix-pb10-22",
    ] {
        let parsed = parse(&json!({
            "template": "ACGTACGTACGT",
            "standardPcrProtocol": protocol,
            "assay": {"id": "standard-pcr"},
        }))
        .expect("reviewed Standard-PCR protocol");
        assert_eq!(parsed.to_worker()["standard_pcr_protocol"], protocol);
    }
}

#[test]
fn named_standard_pcr_protocol_is_refused_on_the_wrong_assay() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "standardPcrProtocol": "neb-q5-hot-start-m0493",
            "assay": {"id": "qpcr-sybr"},
        }))
        .expect_err("Standard-PCR protocol on qPCR");
    assert!(
        error.to_string().contains("requires `standard-pcr`"),
        "{error}"
    );
}

#[test]
fn unknown_standard_pcr_protocol_is_refused() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "standardPcrProtocol": "guess",
            "assay": {"id": "standard-pcr"},
        }))
        .expect_err("unknown Standard-PCR protocol");
    assert!(
        error.to_string().contains("Standard-PCR protocol"),
        "{error}"
    );
}

#[test]
fn an_unknown_qpcr_protocol_is_refused() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "qpcrProtocol": "guess",
        }))
        .expect_err("unknown qPCR protocol");
    assert!(error.to_string().contains("qPCR/SYBR protocol"), "{error}");
}

#[test]
fn current_qpcr_protocol_ids_reach_the_worker_without_aliasing() {
    for protocol in ["neb-luna-universal-m3003", "thermo-powerup-sybr-a2574x"] {
        let parsed = parse(&json!({
            "template": "ACGTACGTACGT",
            "qpcrProtocol": protocol,
            "assay": {"id": "qpcr-sybr"},
        }))
        .expect("current qPCR protocol");
        assert_eq!(parsed.to_worker()["qpcr_protocol"], protocol);
    }
}

#[test]
fn qiacuity_onestep_advanced_eg_binds_to_the_qiagen_chamber_platform() {
    let parsed = parse(&json!({
        "template": "ACGUACGUACGU",
        "fromRna": true,
        "digitalProtocol": "qiagen-qiacuity-onestep-advanced-eg",
        "digitalPlatformId": "qiagen-qiacuity",
        "digitalPlatformName": "QIAGEN QIAcuity",
        "digitalPartitionFormat": "chamber",
        "digitalFragmentationState": "not-required",
        "assay": {"id": "digital-pcr"},
    }))
    .expect("named QIAcuity OneStep Advanced EvaGreen RT-dPCR branch");
    assert_eq!(
        parsed.to_worker()["digital_protocol"],
        "qiagen-qiacuity-onestep-advanced-eg"
    );
    assert_eq!(parsed.to_worker()["from_rna"], true);

    let error = parse(&json!({
        "template": "ACGUACGUACGU",
        "fromRna": true,
        "digitalProtocol": "qiagen-qiacuity-onestep-advanced-eg",
        "digitalPlatformId": "qiagen-qiacuity",
        "digitalPlatformName": "QIAGEN QIAcuity",
        "digitalPartitionFormat": "droplet",
        "digitalFragmentationState": "not-required",
        "assay": {"id": "digital-pcr"},
    }))
    .expect_err("QIAcuity OneStep Advanced is not a droplet branch");
    assert!(error.to_string().contains("microchambers"), "{error}");
}

#[test]
fn luna_e3005_requires_rna_and_reaches_the_worker_as_its_own_one_step_branch() {
    let error = parse(&json!({
        "template": "ACGTACGTACGT",
        "qpcrProtocol": "neb-luna-one-step-rt-qpcr-e3005",
        "assay": {"id": "qpcr-sybr"},
    }))
    .expect_err("E3005 without RNA context");
    assert!(error.to_string().contains("fromRna=true"), "{error}");

    let parsed = parse(&json!({
        "template": "ACGUACGUACGU",
        "fromRna": true,
        "qpcrProtocol": "neb-luna-one-step-rt-qpcr-e3005",
        "assay": {"id": "qpcr-sybr"},
    }))
    .expect("named Luna one-step RT-qPCR branch");
    assert_eq!(
        parsed.to_worker()["qpcr_protocol"],
        "neb-luna-one-step-rt-qpcr-e3005"
    );
    assert_eq!(parsed.to_worker()["from_rna"], true);
}

#[test]
fn promega_a6020_requires_rna_and_reaches_the_worker_as_its_own_one_step_branch() {
    let error = parse(&json!({
        "template": "ACGTACGTACGT",
        "qpcrProtocol": "promega-gotaq-one-step-rt-qpcr-a6020",
        "assay": {"id": "qpcr-sybr"},
    }))
    .expect_err("A6020 without RNA context");
    assert!(error.to_string().contains("fromRna=true"), "{error}");

    let parsed = parse(&json!({
        "template": "ACGUACGUACGU",
        "fromRna": true,
        "qpcrProtocol": "promega-gotaq-one-step-rt-qpcr-a6020",
        "assay": {"id": "qpcr-sybr"},
    }))
    .expect("named GoTaq one-step RT-qPCR branch");
    assert_eq!(
        parsed.to_worker()["qpcr_protocol"],
        "promega-gotaq-one-step-rt-qpcr-a6020"
    );
    assert_eq!(parsed.to_worker()["from_rna"], true);
}

#[test]
fn current_long_range_protocol_ids_reach_the_worker_without_aliasing() {
    for protocol in [
        "neb-longamp-taq-m0323",
        "takara-primestar-gxl-r050a-standard",
        "qiagen-ultrarun-longrange-206442-206444",
        "neb-q5-xt-m2499",
        "promega-gotaq-long-m4021",
        "thermo-platinum-superfi-ii-longrange",
        "thermo-long-pcr-k018x",
    ] {
        let parsed = parse(&json!({
            "template": "ACGTACGTACGT",
            "longRangeProtocol": protocol,
            "assay": {"id": "long-range-pcr"},
        }))
        .expect("reviewed long-range protocol");
        assert_eq!(parsed.to_worker()["long_range_protocol"], protocol);
    }
}

#[test]
fn liquid_basic_rpa_protocol_reaches_the_worker_without_being_promoted_to_rt() {
    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "rpaProtocol": "twistamp-liquid-basic",
        "assay": {"id": "rpa"},
    }))
    .expect("Liquid Basic DNA branch");
    assert_eq!(parsed.to_worker()["rpa_protocol"], "twistamp-liquid-basic");
}

#[test]
fn thermo_lyo_ready_rpa_allows_the_named_rt_rpa_branch() {
    let parsed = parse(&json!({
        "template": "ACGUACGUACGU",
        "fromRna": true,
        "rpaProtocol": "thermo-lyo-ready-rpa",
        "assay": {"id": "rpa"},
    }))
    .expect("named Thermo RT-RPA branch");
    assert_eq!(parsed.to_worker()["rpa_protocol"], "thermo-lyo-ready-rpa");
    assert_eq!(parsed.to_worker()["from_rna"], true);
}

#[test]
fn twistamp_basic_rna_still_fails_closed() {
    let error = engine()
        .validate(&json!({
            "template": "ACGUACGUACGU",
            "fromRna": true,
            "rpaProtocol": "twistamp-basic",
            "assay": {"id": "rpa"},
        }))
        .expect_err("TwistAmp Basic must not inherit another vendor's RT branch");
    assert!(
        error.to_string().contains("thermo-lyo-ready-rpa"),
        "{error}"
    );
}

#[test]
fn naica_evagreen_supports_source_backed_qx700_nio_and_naica_contexts() {
    let wrong = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
            "digitalProtocol": "bio-rad-qx700-naica-evagreen",
            "digitalPartitionFormat": "chamber",
            "digitalPlatformId": "bio-rad-qx700",
            "digitalFragmentationState": "not-assessed",
        }))
        .expect_err("naica EvaGreen is not a chamber branch");
    assert!(wrong.to_string().contains("droplet"), "{wrong}");

    for (platform, consumable) in [
        ("bio-rad-qx700", "qx700-rdg16"),
        ("bio-rad-nio", "qx700-rdg16"),
        ("bio-rad-naica", "naica-sapphire-chip"),
    ] {
        let parsed = parse(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
            "digitalProtocol": "bio-rad-qx700-naica-evagreen",
            "digitalPartitionFormat": "droplet",
            "digitalPlatformId": platform,
            "digitalFragmentationState": "not-assessed",
            "flankingNumericContext": {"digitalConsumableId": consumable},
        }))
        .expect("source-backed naica EvaGreen platform/consumable branch");
        assert_eq!(
            parsed.to_worker()["digital_protocol"],
            "bio-rad-qx700-naica-evagreen"
        );
    }

    let dedicated_on_nio = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
            "digitalProtocol": "bio-rad-qx700-evagreen-supermix",
            "digitalPartitionFormat": "droplet",
            "digitalPlatformId": "bio-rad-nio",
            "digitalFragmentationState": "not-assessed",
            "flankingNumericContext": {"digitalConsumableId": "qx700-rdg16"},
        }))
        .expect_err("dedicated QX700 supermix must not be promoted to Nio");
    assert!(
        dedicated_on_nio.to_string().contains("not source-backed"),
        "{dedicated_on_nio}"
    );
}

#[test]
fn qx700_dedicated_evagreen_supermix_requires_qx700_droplet_context() {
    let wrong = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
            "digitalProtocol": "bio-rad-qx700-evagreen-supermix",
            "digitalPartitionFormat": "chamber",
            "digitalPlatformId": "bio-rad-qx700",
            "digitalFragmentationState": "not-assessed",
        }))
        .expect_err("QX700 dedicated EvaGreen supermix is a droplet branch");
    assert!(wrong.to_string().contains("droplet"), "{wrong}");

    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "assay": {"id": "digital-pcr"},
        "digitalProtocol": "bio-rad-qx700-evagreen-supermix",
        "digitalPartitionFormat": "droplet",
        "digitalPlatformId": "bio-rad-qx700",
        "digitalPlatformName": "Bio-Rad QX700",
        "digitalFragmentationState": "not-assessed",
    }))
    .expect("QX700 dedicated EvaGreen supermix branch");
    assert_eq!(
        parsed.to_worker()["digital_protocol"],
        "bio-rad-qx700-evagreen-supermix"
    );
}

#[test]
fn qiacuity_eg_requires_the_qiacuity_chamber_context() {
    let wrong = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
            "digitalProtocol": "qiagen-qiacuity-eg",
            "digitalPartitionFormat": "droplet",
            "digitalPlatformId": "qiagen-qiacuity",
            "digitalFragmentationState": "not-assessed",
        }))
        .expect_err("QIAcuity is a microchamber branch");
    assert!(wrong.to_string().contains("chamber"), "{wrong}");

    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "assay": {"id": "digital-pcr"},
        "digitalProtocol": "qiagen-qiacuity-eg",
        "digitalPartitionFormat": "chamber",
        "digitalPlatformId": "qiagen-qiacuity",
        "digitalPlatformName": "QIAGEN QIAcuity",
        "digitalFragmentationState": "not-assessed",
    }))
    .expect("QIAcuity EG branch");
    assert_eq!(parsed.to_worker()["digital_protocol"], "qiagen-qiacuity-eg");
}

#[test]
fn a_named_qpcr_protocol_requires_the_matching_assay_and_reaches_the_worker() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "qpcrProtocol": "bio-rad-itaq-sybr",
            "assay": {"id": "standard-pcr"},
        }))
        .expect_err("protocol on the wrong assay");
    assert!(
        error.to_string().contains("requires `qpcr-sybr`"),
        "{error}"
    );

    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "qpcrProtocol": "bio-rad-itaq-sybr",
        "assay": {"id": "qpcr-sybr"},
    }))
    .expect("named qPCR protocol");
    assert_eq!(parsed.to_worker()["qpcr_protocol"], "bio-rad-itaq-sybr");
}

#[test]
fn a_named_rpa_protocol_requires_the_matching_assay_and_reaches_the_worker() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "rpaProtocol": "twistamp-basic",
            "assay": {"id": "standard-pcr"},
        }))
        .expect_err("protocol on the wrong assay");
    assert!(
        error.to_string().contains("requires the `rpa` assay"),
        "{error}"
    );

    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "rpaProtocol": "twistamp-basic",
        "assay": {"id": "rpa"},
    }))
    .expect("named RPA protocol");
    assert_eq!(parsed.to_worker()["rpa_protocol"], "twistamp-basic");
}

#[test]
fn recognised_modified_rpa_branches_fail_closed_before_worker_handoff() {
    for protocol in [
        "twistamp-exo",
        "twistamp-nfo",
        "twistamp-fpg",
        "siba-reference",
    ] {
        let error = engine()
            .validate(&json!({
                "template": "ACGTACGTACGT",
                "rpaProtocol": protocol,
                "assay": {"id": "rpa"},
            }))
            .expect_err("modified RPA branch must not reach the plain-oligo worker");
        assert!(
            error
                .to_string()
                .contains("recognised for provenance but is not executable"),
            "{protocol}: {error}"
        );
    }
}

#[test]
fn two_named_flanking_pair_overlays_are_refused_at_the_boundary() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "qpcrProtocol": "bio-rad-itaq-sybr",
            "rpaProtocol": "twistamp-basic",
            "assay": {"id": "qpcr-sybr"},
        }))
        .expect_err("two chemistry overlays");
    assert!(
        error
            .to_string()
            .contains("only one named flanking-pair chemistry overlay"),
        "{error}"
    );
}

#[test]
fn a_named_digital_protocol_requires_the_matching_assay_and_reaches_the_worker() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "digitalProtocol": "bio-rad-qx200-evagreen",
            "assay": {"id": "standard-pcr"},
        }))
        .expect_err("protocol on the wrong assay");
    assert!(
        error.to_string().contains("requires `digital-pcr` assay"),
        "{error}"
    );

    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "digitalProtocol": "bio-rad-qx200-evagreen",
        "digitalPartitionFormat": "droplet",
        "digitalPlatformId": "bio-rad-qx200",
        "digitalPlatformName": "Bio-Rad QX200",
        "digitalFragmentationState": "not-assessed",
        "assay": {"id": "digital-pcr"},
    }))
    .expect("named digital protocol");
    assert_eq!(
        parsed.to_worker()["digital_protocol"],
        "bio-rad-qx200-evagreen"
    );
}

#[test]
fn qx200_overlay_is_droplet_specific() {
    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGT",
            "assay": {"id": "digital-pcr"},
            "digitalProtocol": "bio-rad-qx200-evagreen",
            "digitalPartitionFormat": "chip",
            "digitalPlatformId": "bio-rad-qx200",
            "digitalPlatformName": "Bio-Rad QX200",
            "digitalFragmentationState": "not-assessed",
        }))
        .expect_err("QX200 cannot be declared as chip dPCR");
    assert!(error.to_string().contains("droplet"), "{error}");
}

#[test]
fn species_inclusivity_panel_reaches_the_worker_without_being_confused_with_background() {
    let parsed = parse(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "background": ">relative\nTTTTTTTTTTTT",
            "assay": {"id": "species-specific-pcr"},
            "inclusivity": ">strain-a\nACGTACGTACGT\n>strain-b\nACGTACGAACGT",
            "inclusivityPanelProvenance": "RefSeq release X; A.1/B.1",
            "backgroundPanelProvenance": "RefSeq release X; C.1",
            "speciesPanelSelectionRationale": "target diversity and nearest neighbours",
            "speciesTargetTaxid": 562,
            "speciesTaxonomySnapshot": "NCBI Taxonomy snapshot 2026-09-04",
            "speciesDatabaseSnapshot": "RefSeq genomes release 232",
            "speciesPanelAccessionManifest": "GCF_000005845.2\nGCF_000008865.2\nGCF_000009865.1",
            "speciesPanelAccessionAuthorityManifest": "GCF_000005845.2\nGCF_000008865.2\nGCF_000009865.1",
            "speciesPanelRecordMetadataManifest": "strain-a\tGCF_000005845.2\tinclusivity\tlinear\nstrain-b\tGCF_000008865.2\tinclusivity\tlinear\nrelative\tGCF_000009865.1\texclusivity\tlinear",
            "speciesPanelRetrievedDate": "2026-09-04",
        }))
        .expect("a valid species-specific request");

    let payload = parsed.to_worker();
    assert_eq!(payload["background"], ">relative\nTTTTTTTTTTTT");
    assert_eq!(
        payload["inclusivity"],
        ">strain-a\nACGTACGTACGT\n>strain-b\nACGTACGAACGT"
    );
    assert_eq!(
        payload["inclusivity_panel_provenance"],
        "RefSeq release X; A.1/B.1"
    );
    assert_eq!(
        payload["background_panel_provenance"],
        "RefSeq release X; C.1"
    );
    assert_eq!(
        payload["species_panel_selection_rationale"],
        "target diversity and nearest neighbours"
    );
    assert_eq!(payload["species_target_taxid"], 562);
    assert_eq!(
        payload["species_taxonomy_snapshot"],
        "NCBI Taxonomy snapshot 2026-09-04"
    );
    assert_eq!(
        payload["species_database_snapshot"],
        "RefSeq genomes release 232"
    );
    assert_eq!(payload["species_panel_retrieved_date"], "2026-09-04");
}

#[test]
fn colony_vendor_protocol_is_typed_source_conditioned_and_reaches_the_worker() {
    let parsed = parse(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "assay": {"id": "colony-pcr"},
            "colonyHostClass": "bacterial",
            "colonyPreparation": "direct-transfer",
            "colonyProtocolId": "neb-onetaq-hotstart-m0488-colony",
            "flankingNumericContext": {"initialDenaturationTimeMin": 3.0, "preparation": "direct-transfer"}
        }))
        .expect("source-conditioned bacterial colony branch");
    let payload = parsed.to_worker();
    assert_eq!(
        payload["colony_protocol_id"],
        "neb-onetaq-hotstart-m0488-colony"
    );
    assert_eq!(payload["colony_host_class"], "bacterial");
    assert_eq!(payload["colony_preparation"], "direct-transfer");
    assert_eq!(
        payload["flanking_numeric_context"]["initial_denaturation_time_min"],
        3.0
    );
}

#[test]
fn rpa_numeric_context_deserializes_public_camelcase_and_serializes_worker_snake_case() {
    let parsed = parse(&json!({
        "template": "ACGTACGTACGTACGTACGT",
        "assay": {"id": "rpa"},
        "rpaProtocol": "thermo-lyo-ready-rpa",
        "flankingNumericContext": {
            "primerEachNm": 150.0,
            "rpaTemperatureC": 40.0,
            "rpaTimeMin": 25.0,
            "rpaBstUnitsPerUl": 0.05,
            "rpaMultiplex": true
        }
    }))
    .expect("source-conditioned RPA numeric context");
    let payload = parsed.to_worker();
    let context = &payload["flanking_numeric_context"];
    assert_eq!(context["primer_each_nm"], 150.0);
    assert_eq!(context["rpa_temperature_c"], 40.0);
    assert_eq!(context["rpa_time_min"], 25.0);
    assert_eq!(context["rpa_bst_units_per_ul"], 0.05);
    assert_eq!(context["rpa_multiplex"], true);
    assert!(context.get("rpaTemperatureC").is_none());
}

#[test]
fn powertrack_yellow_sample_buffer_is_qpcr_only() {
    let ok = parse(&json!({
        "template": "ACGTACGTACGTACGTACGT",
        "assay": {"id": "qpcr-sybr"},
        "qpcrProtocol": "thermo-powertrack-sybr-a46xxx",
        "flankingNumericContext": {"additive": "yellow-sample-buffer", "cyclingProfile": "fast"}
    }));
    assert!(ok.is_ok());

    let error = engine()
        .validate(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "assay": {"id": "standard-pcr"},
            "standardPcrProtocol": "neb-onetaq-hot-start-m0484",
            "flankingNumericContext": {"additive": "yellow-sample-buffer"}
        }))
        .expect_err("PowerTrack sample buffer must not leak into standard PCR");
    assert!(
        error.to_string().contains("yellow-sample-buffer"),
        "{error}"
    );
}

#[test]
fn colony_vendor_protocol_does_not_claim_unsupported_host_or_preparation() {
    for request in [
        json!({
            "template": "ACGTACGTACGT", "assay": {"id": "colony-pcr"},
            "colonyHostClass": "yeast", "colonyPreparation": "direct-transfer",
            "colonyProtocolId": "neb-onetaq-m0482-colony"
        }),
        json!({
            "template": "ACGTACGTACGT", "assay": {"id": "colony-pcr"},
            "colonyHostClass": "bacterial", "colonyPreparation": "liquid-culture",
            "colonyProtocolId": "neb-onetaq-m0482-colony"
        }),
    ] {
        assert!(
            parse(&request).is_err(),
            "unsupported vendor colony scope must fail closed: {request}"
        );
    }
}

#[test]
fn restriction_bench_workflow_authorities_reach_the_worker_without_merging_with_tail_geometry() {
    let parsed = parse(&json!({
        "template": "ACGTACGTACGTACGTACGT",
        "assay": {"id": "restriction-cloning"},
        "cloningVector": "ACGTACGTACGTACGTACGTACGT",
        "cloningVectorTopology": "circular",
        "restrictionDigestProtocol": "neb-cutsmart-standard",
        "restrictionDephosphorylationProtocol": "neb-quick-cip-m0525",
        "restrictionLigationProtocol": "neb-quick-ligation-m2200",
        "tails": {
            "tailProtocol": "neb-general-6bp",
            "forwardEnzyme": "EcoRI",
            "reverseEnzyme": "BamHI",
            "protectiveBases": 6,
            "forwardProtectiveSequence": "GACTTA",
            "reverseProtectiveSequence": "CAGTTA"
        }
    }))
    .expect("restriction cloning with explicit geometry and bench authorities");
    let payload = parsed.to_worker();
    assert_eq!(
        payload["restriction_digest_protocol"],
        "neb-cutsmart-standard"
    );
    assert_eq!(
        payload["restriction_dephosphorylation_protocol"],
        "neb-quick-cip-m0525"
    );
    assert_eq!(
        payload["restriction_ligation_protocol"],
        "neb-quick-ligation-m2200"
    );
    assert_eq!(payload["tails"]["forward_enzyme"], "EcoRI");
}

#[test]
fn transcript_junctions_are_explicit_and_reach_the_worker() {
    let parsed = parse(&json!({
        "template": "ACGTACGTACGT",
        "fromRna": true,
        "exonJunctions": [4, 8],
    }))
    .expect("valid transcript boundaries");
    assert_eq!(parsed.to_worker()["exon_junctions"], json!([4, 8]));
}

#[test]
fn transcript_junctions_need_coding_sequence_context() {
    for request in [
        json!({"template": "ACGTACGTACGT", "exonJunctions": [4]}),
        json!({"template": "ACGTACGTACGT", "fromRna": true, "exonJunctions": [0]}),
        json!({"template": "ACGTACGTACGT", "fromRna": true, "exonJunctions": [12]}),
        json!({"template": "ACGTACGTACGT", "fromRna": true, "exonJunctions": [4, 4]}),
    ] {
        assert!(
            parse(&request).is_err(),
            "request should be refused: {request}"
        );
    }
}

#[test]
fn rna_input_matches_the_worker_rt_contract_before_spawn() {
    let auto_rt = parse(&json!({
        "template": "ACUGACUGACUG",
        "exonJunctions": [4],
    }))
    .expect("RNA input auto-enables the RT context");
    assert_eq!(auto_rt.to_worker()["template"], "ACUGACUGACUG");

    let contradiction = parse(&json!({
        "template": "ACUGACUGACUG",
        "fromRna": false,
    }));
    assert!(contradiction.is_err());
}

#[test]
fn specificity_v5_mismatch_budget_has_the_same_operational_ceiling_as_the_worker() {
    let too_many_mismatches = parse(&json!({
        "template": "ACGTACGTACGT",
        "maxMismatches": 21,
    }));
    assert!(too_many_mismatches.is_err());
}

#[test]
fn an_avoided_region_past_the_end_is_refused_rather_than_silently_clipped() {
    let request: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTAC",
        "excluded": [[8, 40]],
    }))
    .expect("a well-formed request");
    let message = request
        .check()
        .expect_err("this protects nothing")
        .to_string();
    assert!(message.contains("past the end"), "{message}");
}

#[test]
fn an_avoided_region_of_no_width_is_refused() {
    let request: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTAC",
        "excluded": [[2, 0]],
    }))
    .expect("a well-formed request");
    assert!(request.check().is_err(), "zero bases rule nothing out");
}

#[test]
fn circular_target_may_cross_origin_but_not_use_search_scaffolding() {
    let crossing: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTAC",
        "circular": true,
        "targetStart": 8,
        "targetLength": 4,
    }))
    .expect("a well-formed circular request");
    crossing.check().expect("one origin crossing is valid");

    let copy_coordinate: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTAC",
        "circular": true,
        "targetStart": 10,
        "targetLength": 1,
    }))
    .expect("a well-formed request shape");
    assert!(copy_coordinate.check().is_err());

    let multi_turn: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTAC",
        "circular": true,
        "targetStart": 8,
        "targetLength": 11,
    }))
    .expect("a well-formed request shape");
    assert!(multi_turn.check().is_err());
}

#[test]
fn circular_excluded_region_may_cross_origin_but_not_exceed_one_turn() {
    let crossing: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTAC",
        "circular": true,
        "excluded": [[8, 4]],
    }))
    .expect("a well-formed circular request");
    crossing.check().expect("one origin crossing is valid");

    let copy_coordinate: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTAC",
        "circular": true,
        "excluded": [[10, 1]],
    }))
    .expect("a well-formed request shape");
    assert!(copy_coordinate.check().is_err());

    let multi_turn: FlankingPairRequest = serde_json::from_value(json!({
        "template": "ACGTACGTAC",
        "circular": true,
        "excluded": [[8, 11]],
    }))
    .expect("a well-formed request shape");
    assert!(multi_turn.check().is_err());
}
