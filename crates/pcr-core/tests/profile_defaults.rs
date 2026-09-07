//! Every setting a profile names must be one the worker actually has.
//!
//! `profiles.toml` names constraints and thermal-programme fields in a file
//! Rust does not interpret and Python does not read until a request arrives.
//! A typo — `prodcut_max` — would be accepted here, forwarded, and refused
//! only when somebody happened to run that one assay. Worse, a name that is
//! merely *stale* rather than misspelt would be refused with a message about
//! the worker when the mistake is in the catalogue.
//!
//! So the valid names are derived from the worker rather than copied: this
//! asks it what it has and checks the catalogue against the answer. One
//! subprocess, not one per profile.

use std::collections::BTreeSet;

use pcr_core::{catalogue, EngineId};

/// The worker's own vocabulary, or `None` when there is no worker to ask.
///
/// Deliberately no interpreter fallback here: this vocabulary check should
/// never start a system Python or guess at an environment. The check runs
/// only where `PCR_PYTHON` names a real interpreter - CI sets it, local runs
/// copy it - and skips quietly where nobody did. The production worker has a
/// separate repository-local venv fallback in the application worker adapter.
fn vocabulary() -> Option<(BTreeSet<String>, BTreeSet<String>, BTreeSet<String>)> {
    let python = std::env::var("PCR_PYTHON")
        .ok()
        .filter(|value| !value.trim().is_empty())?;
    let worker = pcr_worker_client::Worker::new(python);
    let answer = worker.call("presets", &serde_json::json!({})).ok()?;

    let constraints = answer
        .get("constraints")?
        .as_object()?
        .keys()
        .cloned()
        .collect();
    let cycling = answer
        .get("cycling")?
        .as_array()?
        .iter()
        .filter_map(|name| name.as_str().map(str::to_owned))
        .collect();
    let purposes = answer
        .get("purposes")?
        .as_array()?
        .iter()
        .filter_map(|purpose| purpose.get("id")?.as_str().map(str::to_owned))
        .collect();

    Some((constraints, cycling, purposes))
}

#[test]
fn every_profile_names_settings_the_worker_has() {
    let Some((constraints, cycling, purposes)) = vocabulary() else {
        if std::env::var("PCR_PYTHON").is_ok_and(|value| !value.trim().is_empty()) {
            panic!("PCR_PYTHON is configured, so the worker vocabulary contract must run");
        }
        eprintln!("SKIPPED: set PCR_PYTHON to run the worker vocabulary contract");
        return;
    };

    for profile in catalogue().expect("the catalogue parses") {
        // The consensus engine has its own constraint vocabulary, published
        // separately; checking it against this one would be wrong rather than
        // merely useless.
        if profile.engine != EngineId::FlankingPair {
            continue;
        }

        for name in profile.defaults.constraints.keys() {
            assert!(
                constraints.contains(name),
                "`{}` sets the constraint `{name}`, which the worker does not have. \
                 It has: {}",
                profile.id,
                constraints.iter().cloned().collect::<Vec<_>>().join(", ")
            );
        }
        for name in profile.defaults.cycling.keys() {
            assert!(
                cycling.contains(name),
                "`{}` changes `{name}` in the thermal programme, which the worker \
                 does not programme. It programmes: {}",
                profile.id,
                cycling.iter().cloned().collect::<Vec<_>>().join(", ")
            );
        }
        for name in &profile.defaults.purposes {
            assert!(
                purposes.contains(name),
                "`{}` offers the purpose `{name}`, which the worker does not have. \
                 It has: {}",
                profile.id,
                purposes.iter().cloned().collect::<Vec<_>>().join(", ")
            );
        }
    }
}

/// Nothing may claim to be implemented while its engine is not.
///
/// `planned` means named and routable with nothing behind it; anything above
/// that is a claim that the assay runs. A profile on an unwritten engine
/// answers `NotImplemented` to every request, so a status above `planned`
/// there is a promise the catalogue cannot keep — and status is the field a
/// bench scientist reads to decide whether to trust an answer.
#[test]
fn no_assay_claims_more_than_its_engine_can_do() {
    use pcr_core::{default_registry, Status};

    let registry = default_registry().expect("the catalogue registers");
    for profile in registry.profiles() {
        if profile.status == Status::Planned {
            continue;
        }
        let engine = registry.engine_for(&profile.id).expect("registered");
        // An engine that computes refuses an empty template; one that is only
        // named answers NotImplemented. That is how they are told apart.
        let error = engine
            .design(serde_json::json!({ "template": "" }))
            .expect_err("an empty template is never designable");
        assert!(
            !matches!(error, pcr_core::CoreError::NotImplemented(_)),
            "`{}` is marked {} but its {} engine is not written",
            profile.id,
            profile.status.label(),
            profile.engine.label()
        );
    }
}

/// Every engine whose worker shares the same preamble accepts the same request.
///
/// Three engines call one function to read the enzyme, the purpose, the salt
/// concentrations and the constraints out of a request. An engine that does not
/// *accept* one of those fields refuses a request its own worker was perfectly
/// able to answer — and because each engine's request type is written by hand,
/// there is nothing but this test to keep them in step.
///
/// Found the hard way: inverse PCR refused `purpose`, which the worker reads,
/// so a form that offered the choice produced an error nobody could act on.
#[test]
fn the_engines_that_share_a_preamble_accept_the_same_fields() {
    use pcr_core::{default_registry, EngineId};

    // What the shared preamble reads under these exact names. `constraints` is
    // deliberately absent: the nested engine has two rounds and names them
    // `outer` and `inner`, so one set could not describe both -- which is a
    // real difference rather than a field somebody forgot.
    let shared = serde_json::json!({
        "polymerase": "taq-standard",
        "purpose": "general",
        "conditions": { "dv_conc": 2.0 },
        "name": "check",
    });

    // What each engine needs on top, to get past its own required fields.
    let extra: &[(EngineId, serde_json::Value)] = &[
        (EngineId::FlankingPair, serde_json::json!({})),
        (
            EngineId::OutwardPair,
            serde_json::json!({
                "enzyme": "EcoRI",
                "inverseBranch": "restriction-self-ligation"
            }),
        ),
        (EngineId::Nested, serde_json::json!({})),
    ];

    let registry = default_registry().expect("the catalogue registers");
    for (engine_id, additions) in extra {
        let profile = registry
            .profiles()
            .into_iter()
            .find(|profile| profile.engine == *engine_id)
            .expect("every one of these has an assay");
        let engine = registry.engine_for(&profile.id).expect("registered");

        let mut request = shared.as_object().expect("an object").clone();
        request.insert("template".into(), "ACGTACGTACGTACGTACGTACGT".into());
        for (key, value) in additions.as_object().expect("an object") {
            request.insert(key.clone(), value.clone());
        }

        engine
            .validate(&serde_json::Value::Object(request))
            .unwrap_or_else(|error| {
                panic!(
                    "the {} engine refused a field its worker reads: {error}",
                    engine_id.label()
                )
            });
    }
}
