//! Domain core for PCRStudio.
//!
//! This crate holds the part of the program that would survive being lifted
//! out of whatever is serving it, and the shape it holds it in.
//!
//! There are three layers, and only the first is expensive. An **engine** is
//! one search — one pairing of what you start from with what shape the answer
//! has — and the list of them is closed. A **modifier** is something applied
//! to an engine rather than listed beside it, so a thing that can be combined
//! never appears as an alternative. An **assay profile** is a named engine
//! plus its limits and its wording, and lives in a data file because adding
//! one should be a reviewed entry rather than a deployment.
//!
//! The registry joins them and refuses to start if the join does not hold.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod coordinates;
pub mod engine;
pub mod engines;
pub mod error;
pub mod profile;
pub mod registry;
pub mod taxonomy;
pub mod units;
pub mod worker;

pub use engine::{
    default_engines, default_engines_with_worker, Engine, EngineDescription, UnbuiltEngine,
};
pub use engines::{
    ConsensusPair, ConsensusPairRequest, DiscriminatingPair, DiscriminatingPairRequest, Edit,
    FlankingPair, FlankingPairRequest, Fragment, JunctionPrimers, JunctionPrimersRequest, LoopSet,
    LoopSetRequest, MutagenicPair, MutagenicPairRequest, Nested, NestedRequest, OutwardPair,
    OutwardPairRequest, PairAndProbe, PairAndProbeRequest, SinglePrimer, SinglePrimerRequest,
    TilingScheme, TilingSchemeRequest,
};
pub use error::{CoreError, Result};
pub use profile::{catalogue, EnzymeNeed, Profile, ProfileDefaults};
pub use registry::Registry;
pub use taxonomy::{EngineId, Goal, Modifier, Status};
pub use worker::{ScientificWorker, Worker};

/// A registry holding every engine and assay this build ships.
///
/// # Errors
///
/// Propagates any failure from [`Registry::add_profile`] — a duplicate id, an
/// engine this build lacks, or a modifier the engine does not accept. Each is
/// a mistake in `profiles.toml` and each stops the process on purpose.
pub fn default_registry() -> Result<Registry> {
    default_registry_with_worker(Worker::unbound())
}

/// Build the shipped registry against an explicit scientific execution port.
///
/// Application and transport crates use this constructor so the domain core
/// never selects Python, spawns a process, or otherwise owns infrastructure.
///
/// # Errors
/// Propagates catalogue/registry consistency failures.
pub fn default_registry_with_worker(worker: Worker) -> Result<Registry> {
    let mut registry = Registry::new();

    for engine in default_engines_with_worker(worker) {
        registry.add_engine(engine);
    }
    for profile in catalogue()? {
        registry.add_profile(profile)?;
    }

    Ok(registry)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn the_shipped_catalogue_satisfies_every_check() {
        // The real assertion is that this does not error: every assay names an
        // engine that exists and only asks for what that engine accepts.
        let registry = default_registry().expect("profiles.toml is consistent with the engines");
        assert!(!registry.is_empty());
        assert_eq!(registry.engine_count(), EngineId::all().len());
    }

    #[test]
    fn every_assay_has_a_url_safe_id_and_a_summary() {
        for profile in catalogue().expect("catalogue parses") {
            profile.check_id().expect("ids are url-safe");
            assert!(!profile.name.is_empty(), "{} has no name", profile.id);
            assert!(!profile.summary.is_empty(), "{} has no summary", profile.id);
            // Several assays share an engine and read alike from a summary
            // alone. The guidance is what tells them apart, so a short one is
            // as good as none.
            assert!(
                profile.guidance.len() > 80,
                "{} has no useful guidance",
                profile.id
            );
        }
    }

    #[test]
    fn assays_come_back_sorted_so_the_sidebar_is_stable() {
        let registry = default_registry().expect("catalogue registers");
        let ids: Vec<_> = registry.profiles().into_iter().map(|p| p.id).collect();
        let mut sorted = ids.clone();
        sorted.sort();
        assert_eq!(ids, sorted);
    }

    #[test]
    fn every_goal_has_at_least_one_assay_under_it() {
        // An empty group in the sidebar reads as a missing feature rather than
        // as a deliberate omission.
        let registry = default_registry().expect("catalogue registers");
        for goal in Goal::all() {
            assert!(
                !registry.profiles_for(*goal).is_empty(),
                "nothing is registered under {}",
                goal.label()
            );
        }
    }

    #[test]
    fn an_assay_asking_for_a_modifier_its_engine_refuses_stops_the_build() {
        let mut registry = Registry::new();
        for engine in default_engines() {
            registry.add_engine(engine);
        }

        // A tiling scheme assigns its own alternating pools; multiplexing it
        // would be a second algorithm redoing the first one's work.
        let impossible = Profile {
            id: "multiplexed-tiling".into(),
            name: "Multiplexed tiling".into(),
            summary: "…".into(),
            guidance: "…".into(),
            checks: "…".into(),
            engine: EngineId::TilingScheme,
            goal: Goal::Sequence,
            status: Status::Planned,
            defaults: crate::ProfileDefaults::default(),
            modifiers: vec![Modifier::Multiplex],
            requires: Vec::new(),
            enzyme: Vec::new(),
        };

        let error = registry.add_profile(impossible).expect_err("refused");
        assert!(matches!(error, CoreError::IncompatibleModifier(_)));
        assert!(error.to_string().contains("Multiplexed"));
        assert!(error.to_string().contains("Tiling scheme"));
    }

    #[test]
    fn an_assay_naming_an_engine_this_build_lacks_stops_the_build() {
        let mut registry = Registry::new();
        // No engines added at all.
        let orphan = Profile {
            id: "orphan".into(),
            name: "Orphan".into(),
            summary: "…".into(),
            guidance: "…".into(),
            checks: "…".into(),
            engine: EngineId::FlankingPair,
            goal: Goal::Amplify,
            status: Status::Planned,
            defaults: crate::ProfileDefaults::default(),
            modifiers: vec![],
            requires: Vec::new(),
            enzyme: Vec::new(),
        };

        let error = registry.add_profile(orphan).expect_err("refused");
        assert!(matches!(error, CoreError::UnknownEngine(_)));
    }

    #[test]
    fn registering_the_same_id_twice_is_refused() {
        let mut registry = Registry::new();
        for engine in default_engines() {
            registry.add_engine(engine);
        }
        let assay = || Profile {
            id: "standard-pcr".into(),
            name: "Standard PCR".into(),
            summary: "…".into(),
            guidance: "…".into(),
            checks: "…".into(),
            engine: EngineId::FlankingPair,
            goal: Goal::Amplify,
            status: Status::Planned,
            defaults: crate::ProfileDefaults::default(),
            modifiers: vec![],
            requires: Vec::new(),
            enzyme: Vec::new(),
        };

        registry.add_profile(assay()).expect("first");
        let error = registry.add_profile(assay()).expect_err("second");
        assert_eq!(error, CoreError::DuplicateProfile("standard-pcr".into()));
    }

    #[test]
    fn an_id_that_would_break_a_route_is_refused() {
        let mut registry = Registry::new();
        for engine in default_engines() {
            registry.add_engine(engine);
        }
        for bad in ["", "Standard PCR", "standard_pcr", "qPCR"] {
            let profile = Profile {
                id: bad.into(),
                name: "x".into(),
                summary: "y".into(),
                guidance: "z".into(),
                checks: "w".into(),
                engine: EngineId::FlankingPair,
                goal: Goal::Amplify,
                status: Status::Planned,
                defaults: crate::ProfileDefaults::default(),
                modifiers: vec![],
                requires: Vec::new(),
                enzyme: Vec::new(),
            };
            assert!(
                registry.add_profile(profile).is_err(),
                "id `{bad}` should have been refused"
            );
        }
    }

    #[test]
    fn unknown_ids_report_the_id_they_were_given() {
        let registry = default_registry().expect("catalogue registers");
        let error = registry
            .profile("does-not-exist")
            .expect_err("no such assay");
        assert_eq!(error, CoreError::UnknownProfile("does-not-exist".into()));
    }

    #[test]
    fn a_named_but_unwritten_engine_refuses_to_pretend_it_designed_anything() {
        // Asserted of the placeholder type itself rather than of whichever
        // engine happens to be unwritten today.
        //
        // This test used to reach for `lamp`, and went red the day the loop-set
        // engine was built — a test failing on work being finished. Every one of
        // the eleven engines now computes, so there is no unwritten one left to
        // name, and the property being protected was never about any of them: it
        // is that the placeholder this build ships for the *next* engine refuses
        // rather than returning an empty result that reads like a design.
        let unbuilt = UnbuiltEngine::new(EngineId::FlankingPair, &[]);
        let error = unbuilt
            .design(json!({ "template": "ACGTACGTACGTACGTACGT" }))
            .expect_err("a placeholder designs nothing");
        assert!(
            matches!(error, CoreError::NotImplemented(_)),
            "{error:?} is not NotImplemented"
        );
    }

    #[test]
    fn every_engine_in_the_vocabulary_now_computes() {
        // True as of the cycle that built the last of them, and worth pinning:
        // if an engine is ever removed from the registry, this says so rather
        // than the failure surfacing as a 501 in front of somebody.
        let registry = default_registry().expect("catalogue registers");
        for id in EngineId::all() {
            let described = registry
                .engine_description(*id)
                .unwrap_or_else(|| panic!("{} is not registered", id.label()));
            assert!(
                described.implemented,
                "{} is named but not written",
                id.label()
            );
        }
    }

    #[test]
    fn the_flanking_pair_engine_is_the_one_that_computes() {
        let registry = default_registry().expect("catalogue registers");
        let engine = registry.engine_for("standard-pcr").expect("registered");
        assert_eq!(engine.id(), EngineId::FlankingPair);

        // It refuses an empty request rather than answering NotImplemented,
        // which is how you tell a written engine from a named one.
        let error = engine
            .design(json!({ "template": "" }))
            .expect_err("nothing to design against");
        assert!(matches!(error, CoreError::InvalidRequest(_)));
    }

    #[test]
    fn every_written_engine_is_the_one_its_assays_actually_reach() {
        // The point of the split: one implementation reached through several
        // assay names. If this stops holding, the catalogue is lying.
        //
        // It has stopped holding once, silently: two engines were written,
        // tested, and never added to the registry, so every request for them
        // answered NotImplemented while their own unit tests passed. Walking
        // every engine in the vocabulary rather than a hand-kept list means
        // the next engine cannot be forgotten the same way.
        let registry = default_registry().expect("catalogue registers");
        assert_eq!(
            registry.engine_count(),
            EngineId::all().len(),
            "an engine exists that default_registry never registered"
        );
        for id in EngineId::all() {
            let engine = registry.engine_by_id(*id).unwrap_or_else(|| {
                panic!("{} is named but was never registered", id.label());
            });
            // An empty template is refused by an engine that computes and
            // answered NotImplemented from one that only has a name, which is
            // how you tell them apart from outside.
            let error = engine
                .design(json!({ "template": "" }))
                .expect_err("empty template");
            assert!(
                matches!(error, CoreError::InvalidRequest(_)),
                "{} answered {error:?} -- it is written but not registered",
                id.label()
            );
        }
    }

    #[test]
    fn several_assays_share_one_engine_which_is_the_whole_point() {
        let registry = default_registry().expect("catalogue registers");
        let on_flanking_pair: Vec<_> = registry
            .profiles()
            .into_iter()
            .filter(|p| p.engine == EngineId::FlankingPair)
            .map(|p| p.id)
            .collect();

        // If this ever drops to one, the taxonomy has stopped earning its keep.
        assert!(
            on_flanking_pair.len() >= 5,
            "only {on_flanking_pair:?} share the flanking-pair engine"
        );
    }

    #[test]
    fn errors_serialise_with_a_kind_the_interface_can_branch_on() {
        let json = serde_json::to_value(CoreError::UnknownProfile("x".into()))
            .expect("CoreError is serialisable");
        assert_eq!(json, json!({ "kind": "unknownProfile", "detail": "x" }));
    }
}
