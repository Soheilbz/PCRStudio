//! Which enzymes an assay offers, and which it will run.
//!
//! Every module offered every enzyme, so a LAMP design could be run with a
//! proofreading polymerase — which produces nothing at all, because that
//! reaction never heats the template apart and that enzyme cannot open it.
//! Three of these were already refused *after* somebody chose, inside the
//! worker, which is the right check in the wrong place: a choice that cannot
//! work should not be on the list.
//!
//! What is asserted here is the property rather than any particular enzyme. A
//! list of enzyme names in a test is the same hand-synced thing as a list of
//! enzyme names in a profile, and would go stale the day a tenth arrived.
//!
//! The one list that *is* written out is `RESEARCHED` — which assays narrow
//! their enzymes at all. That is deliberate: each entry is a claim about
//! chemistry somebody read a paper to make, and adding one should be an act
//! rather than a line slipped into a data file.

use pcr_core::{default_registry, EnzymeNeed, Registry};

/// Every assay, and what it says it needs of an enzyme.
fn registry() -> Registry {
    default_registry().expect("profiles.toml is valid, or the process would not start")
}

#[test]
fn everything_that_cycles_needs_an_enzyme_that_survives_cycling() {
    // Derived rather than written into nineteen profiles, so a tenth enzyme
    // that works warm and dies at 95 cannot be offered to a thermocycled assay
    // because somebody forgot a line.
    let registry = registry();
    let mut cycled = 0;
    for profile in registry.profiles() {
        let id = profile.id.clone();
        let needs = profile.enzyme_needs();

        if profile.enzyme.contains(&EnzymeNeed::StrandDisplacing)
            || profile.enzyme.contains(&EnzymeNeed::RpaCompatible)
        {
            assert!(
                !needs.contains(&EnzymeNeed::Thermostable),
                "{id} does not cycle, so it must not demand an enzyme that survives it"
            );
        } else {
            cycled += 1;
            assert!(
                needs.contains(&EnzymeNeed::Thermostable),
                "{id} denatures at 95 degrees, over and over"
            );
        }
    }
    // The failure mode of the loop above is a registry that returned nothing.
    assert!(cycled >= 15, "only {cycled} assays were checked");
}

/// Every assay that narrows its enzymes, and the source that justifies it.
///
/// A hand-written list, deliberately, and the only one in this file. Each entry
/// is a claim about chemistry that somebody read a paper to make, and the point
/// of listing them is that adding a claim has to be a deliberate act rather
/// than a line slipped into a data file. A test that merely counted them would
/// wave through a wrong eighth claim as readily as a right one.
///
/// The sources are in `profiles.toml` beside each requirement, and the whole
/// set is written up in `docs/audits/controls-pass.md`.
const RESEARCHED: &[(&str, EnzymeNeed)] = &[
    // Isothermal: nothing heats the template apart, so the polymerase must.
    ("lamp", EnzymeNeed::StrandDisplacing),
    ("rpa", EnzymeNeed::RpaCompatible),
    // The activity is the read-out rather than a side effect.
    ("qpcr-probe", EnzymeNeed::FivePrimeExonuclease),
    // Taq alone runs out past about three kilobases.
    ("long-range-pcr", EnzymeNeed::Proofreading),
    // The design *is* a 3' mismatch; proofreading removes it and every sample
    // reads as a heterozygote.
    ("arms-pcr", EnzymeNeed::NoProofreading),
    ("kasp", EnzymeNeed::NoProofreading),
    ("tetra-primer-arms", EnzymeNeed::NoProofreading),
];

#[test]
fn only_the_researched_assays_narrow_their_enzymes() {
    let claiming: Vec<(String, Vec<EnzymeNeed>)> = registry()
        .profiles()
        .into_iter()
        .filter(|profile| !profile.enzyme.is_empty())
        .map(|profile| (profile.id.clone(), profile.enzyme.clone()))
        .collect();

    let mut expected: Vec<(String, Vec<EnzymeNeed>)> = RESEARCHED
        .iter()
        .map(|(id, need)| ((*id).to_owned(), vec![*need]))
        .collect();
    expected.sort_by(|a, b| a.0.cmp(&b.0));

    let mut found = claiming;
    found.sort_by(|a, b| a.0.cmp(&b.0));

    assert_eq!(
        found, expected,
        "an assay narrowed its enzymes without a source beside the claim, or a \
         researched one stopped narrowing. Both are decisions somebody has to \
         make on purpose."
    );
}

#[test]
fn an_assay_that_says_nothing_offers_everything() {
    // The honest default, and it has to stay the default.
    //
    // The fourteen that say nothing were researched too, and the answer was
    // that fidelity is a preference rather than a requirement there: a cloning
    // reaction run with Taq works and its product carries errors, which is a
    // different thing from a LAMP reaction run with Taq, which produces
    // nothing. Narrowing on a preference would take a real choice away.
    let quiet: Vec<_> = registry()
        .profiles()
        .into_iter()
        .filter(|profile| profile.enzyme.is_empty())
        .collect();

    assert_eq!(
        quiet.len(),
        registry().profiles().len() - RESEARCHED.len(),
        "the two halves of the catalogue should account for all of it"
    );

    for profile in quiet {
        // Thermostability, and nothing else.
        assert_eq!(profile.enzyme_needs(), vec![EnzymeNeed::Thermostable]);
    }
}

#[test]
fn every_need_says_why_in_words_somebody_at_a_bench_would_use() {
    // The reason travels with the requirement because a shortened list is a
    // statement rather than an absence: somebody who came here knowing which
    // enzyme they use has to be told it is not offered, and told why.
    for need in [
        EnzymeNeed::StrandDisplacing,
        EnzymeNeed::Thermostable,
        EnzymeNeed::FivePrimeExonuclease,
        EnzymeNeed::NoFivePrimeExonuclease,
        EnzymeNeed::Proofreading,
        EnzymeNeed::NoProofreading,
        EnzymeNeed::RpaCompatible,
    ] {
        let why = need.why();
        assert!(why.len() > 60, "{need:?} explains nothing");
        assert!(
            !why.contains("must") && !why.contains("required"),
            "{need:?} reads as a validator rather than as chemistry"
        );
    }
}

#[test]
fn every_assay_can_still_run_the_enzyme_it_names() {
    // The way this whole thing would fail silently: an assay narrowed to a set
    // its own default is not in, so the page opens on an enzyme it will refuse.
    //
    // The catalogue lives in the Python worker, so this is the one test here
    // that needs it. Under a bare `cargo test` there is none, and rather than
    // passing vacuously it says it did not run — an empty loop that reports
    // success is the shape of test this file exists to avoid.
    let registry = registry();
    let mut checked = 0;
    for profile in registry.profiles() {
        let id = profile.id.clone();
        let Some(named) = profile.defaults.polymerase.clone() else {
            continue;
        };
        let engine = registry.engine_for(&id).expect("every assay has one");
        let Ok(Some(presets)) = engine.presets() else {
            if std::env::var("PCR_PYTHON").is_ok_and(|value| !value.trim().is_empty()) {
                panic!("PCR_PYTHON is configured, so {id} must expose its enzyme catalogue");
            }
            eprintln!("SKIPPED: set PCR_PYTHON to run the enzyme catalogue contract");
            return;
        };
        checked += 1;

        let entry = presets
            .get("polymerases")
            .and_then(|all| all.as_array())
            .and_then(|all| {
                all.iter()
                    .find(|one| one.get("id").and_then(|v| v.as_str()) == Some(named.as_str()))
                    .cloned()
            })
            .unwrap_or_else(|| panic!("{id} names `{named}`, which is not in the catalogue"));

        for need in profile.enzyme_needs() {
            let (activity, wanted) = need.wants();
            let has = entry
                .pointer(&format!("/does/{activity}"))
                .and_then(|v| v.as_bool());
            assert_ne!(
                has,
                Some(!wanted),
                "{id} defaults to `{named}`, which its own requirement rules out"
            );
        }
    }
    assert!(checked >= 15, "only {checked} assays were checked");
}
