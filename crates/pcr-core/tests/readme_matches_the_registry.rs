//! The README's counts, checked against what the registry actually holds.
//!
//! The README opens by saying how many design systems there are, how many
//! engines are behind them, and that every one of them computes. Those are the
//! three claims a stranger reads before deciding whether this is worth their
//! afternoon, and they are the three most likely to quietly stop being true —
//! the previous version of that paragraph said nothing computed, which had not
//! been so for months.
//!
//! A README cannot count anything for itself. This is the next best thing:
//! the numbers stay written down, and the day they stop matching, a test says
//! so rather than a reader finding out.

use pcr_core::default_registry;

/// The count the README states immediately before a phrase.
///
/// Read as "the word before these words" rather than "the first number on the
/// line", because the sentence carries two of them — twenty-one systems over
/// eleven engines — and a search that takes the first match will happily report
/// eleven systems and pass.
fn stated_before(phrase: &str) -> usize {
    let readme = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/../../README.md"))
        .expect("the README is beside the crates");

    // Written as words, because that is how the sentence reads. Deliberately a
    // short list: a README needing "one hundred and seventeen" spelled out is a
    // README that should be quoting a figure instead.
    const NUMBERS: &[(&str, usize)] = &[
        ("ten", 10),
        ("eleven", 11),
        ("twelve", 12),
        ("thirteen", 13),
        ("nineteen", 19),
        ("twenty", 20),
        ("twenty-one", 21),
        ("twenty-two", 22),
        ("twenty-three", 23),
    ];

    let at = readme
        .find(phrase)
        .unwrap_or_else(|| panic!("the README should still say `{phrase}`"));
    let before = readme[..at]
        .split_whitespace()
        .next_back()
        .unwrap_or_else(|| panic!("nothing precedes `{phrase}`"))
        .to_lowercase();

    NUMBERS
        .iter()
        .find(|(spelled, _)| *spelled == before)
        .map(|(_, value)| *value)
        .unwrap_or_else(|| panic!("`{before}` before `{phrase}` is not a number this test reads"))
}

#[test]
fn the_readme_counts_the_design_systems_the_registry_holds() {
    let registry = default_registry().expect("the registry loads");
    assert_eq!(
        stated_before("design systems over"),
        registry.profiles().len(),
        "the README's count of design systems has drifted from the registry"
    );
}

#[test]
fn the_readme_counts_the_engines_behind_them() {
    let registry = default_registry().expect("the registry loads");
    let engines: std::collections::HashSet<_> = registry
        .profiles()
        .iter()
        .map(|profile| profile.engine)
        .collect();

    assert_eq!(
        stated_before("engines, and every engine"),
        engines.len(),
        "the README's count of engines has drifted from the registry"
    );
}

#[test]
fn the_readme_does_not_claim_more_than_experimental() {
    /*
     * The status is the honest part of the whole document. "Experimental" means
     * implemented and tested against real sequences but not validated at a
     * bench, and the day one system is promoted the README must not still be
     * describing every one of them that way — nor, as the previous version did,
     * describing them all as computing nothing.
     */
    let registry = default_registry().expect("the registry loads");
    let all_experimental = registry
        .profiles()
        .iter()
        .all(|profile| format!("{:?}", profile.status).to_lowercase() == "experimental");

    let readme = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/../../README.md"))
        .expect("the README is beside the crates");

    // Whitespace flattened first, because the claim is a sentence and the
    // README wraps it wherever the line happens to run out.
    let prose = readme.split_whitespace().collect::<Vec<_>>().join(" ");

    assert_eq!(
        all_experimental,
        prose.contains("Every system is marked **experimental**"),
        "the README and the registry disagree about whether everything is still experimental"
    );
}
