//! What every engine's request check shares.
//!
//! Each adapter owns its own request shape, but several checks recur across
//! them -- an empty template, a target split in half, an avoided region past
//! the end. When those checks were written per engine they *diverged*: one
//! validated its excluded regions and six forwarded malformed ones, four range-
//! checked `how_many` and five did not. Every divergence was a caller whose
//! request meant one thing on one assay page and another on the rest.
//!
//! One implementation lives here, and every engine calls it. A new engine gets
//! the same guarantees for free, and a fix to a check lands everywhere at once.

use crate::error::{CoreError, Result};

/// The part of a pasted record that the worker will treat as sequence text.
///
/// The worker accepts raw sequence, FASTA and the usual GenBank `ORIGIN`
/// block. Rust does not own the complete parser, but it must use the same
/// coordinate frame for its cheap early bounds checks. Counting the FASTA
/// description, GenBank `LOCUS` metadata or line coordinates here would make
/// a target be judged against a different template from the one Primer3 sees.
fn sequence_payload(template: &str) -> String {
    let lines: Vec<&str> = template.lines().collect();

    if template.trim_start().starts_with('>') {
        let mut body = String::new();
        let mut in_first_record = false;
        for line in lines {
            if line.trim_start().starts_with('>') {
                if in_first_record {
                    break;
                }
                in_first_record = true;
                continue;
            }
            if in_first_record {
                body.push_str(line);
                body.push('\n');
            }
        }
        return body;
    }

    if let Some(origin) = lines
        .iter()
        .position(|line| line.trim().eq_ignore_ascii_case("ORIGIN"))
    {
        let mut body = String::new();
        for line in lines.into_iter().skip(origin + 1) {
            if line.trim() == "//" {
                break;
            }
            body.push_str(line);
            body.push('\n');
        }
        return body;
    }

    template.to_owned()
}

/// The length a bounds check should measure against.
///
/// Positions are counted in sequence letters, not bytes, whitespace, record
/// headers, punctuation or GenBank coordinates. The worker applies the same
/// extraction before it validates the alphabet, so early target and size
/// checks cannot disagree with the actual design coordinate frame.
#[must_use]
pub fn base_count(template: &str) -> usize {
    sequence_payload(template)
        .chars()
        .filter(|character| character.is_alphabetic())
        .count()
}

/// Whether the sequence payload explicitly contains RNA uracil.
///
/// The Python intake normalises `U` to `T` but records that the original
/// molecule was RNA and automatically enables reverse transcription. Rust
/// performs the cheap request checks before spawning that worker, so it must
/// make the same decision here; otherwise a direct API caller can receive a
/// different answer from the web path for the same template.
#[must_use]
pub fn contains_rna_base(template: &str) -> bool {
    sequence_payload(template)
        .chars()
        .any(|character| character.eq_ignore_ascii_case(&'u'))
}

/// Whether this plausibly holds a sequence somebody means to design against.
///
/// A cheap first net for paste errors -- an email address in the wrong box, a
/// name instead of a sequence -- caught here rather than after paying for a
/// process spawn. It cannot judge chemistry, so it is deliberately coarse: a
/// paste qualifies when ordinary bases make up a solid share of it, or when
/// nearly everything in it is a legal base under the wider IUPAC code, which
/// is how a deliberately degenerate alignment reads. Prose fails both ways --
/// English text is mostly letters no base abbreviates.
fn looks_like_a_sequence(template: &str) -> bool {
    const ORDINARY_BASES: &[char] = &['A', 'C', 'G', 'T', 'U', 'N'];
    const ANY_BASE: &[char] = &[
        'A', 'C', 'G', 'T', 'U', 'R', 'Y', 'S', 'W', 'K', 'M', 'B', 'D', 'H', 'V', 'N',
    ];

    let characters: Vec<char> = sequence_payload(template)
        .chars()
        .filter(|character| character.is_alphabetic())
        .collect();
    if characters.is_empty() {
        return false;
    }
    let ordinary = characters
        .iter()
        .filter(|c| ORDINARY_BASES.contains(&c.to_ascii_uppercase()))
        .count();
    let any_base = characters
        .iter()
        .filter(|c| ANY_BASE.contains(&c.to_ascii_uppercase()))
        .count();
    ordinary * 10 >= characters.len() * 3 || any_base * 20 >= characters.len() * 19
}

/// Check a template: present, plausible, and within this endpoint's ceiling.
///
/// Returns the base count, since nearly every caller needs it for the checks
/// that follow and counting twice would be two ways to disagree.
///
/// # Errors
///
/// [`CoreError::InvalidRequest`] with a message naming what was wrong.
pub fn check_template(template: &str, max_bases: usize) -> Result<usize> {
    if template.trim().is_empty() {
        return Err(CoreError::InvalidRequest(
            "No sequence was given to design against.".to_owned(),
        ));
    }
    if !looks_like_a_sequence(template) {
        return Err(CoreError::InvalidRequest(
            "That does not look like a nucleotide sequence. Paste the bases \
             themselves, or a FASTA or GenBank record containing them."
                .to_owned(),
        ));
    }
    let count = base_count(template);
    if count > max_bases {
        return Err(CoreError::InvalidRequest(format!(
            "The template is {count} bases. This endpoint takes up to \
             {max_bases}; anything larger should be a region rather than a \
             whole sequence."
        )));
    }
    Ok(count)
}

/// Check a target given as a start and a length.
///
/// Both halves or neither: half of one is a request that would be silently
/// ignored, which is worse than being refused.
///
/// # Errors
///
/// [`CoreError::InvalidRequest`] when only one half was sent, or the target
/// is empty.
pub fn check_target_pair(start: Option<usize>, length: Option<usize>) -> Result<()> {
    match (start, length) {
        (Some(_), None) => Err(CoreError::InvalidRequest(
            "A target start was given without a length.".to_owned(),
        )),
        (None, Some(_)) => Err(CoreError::InvalidRequest(
            "A target length was given without a start.".to_owned(),
        )),
        (Some(_), Some(0)) => Err(CoreError::InvalidRequest(
            "A target of zero bases cannot be included in anything.".to_owned(),
        )),
        _ => Ok(()),
    }
}

/// Check a target against the template it names positions in.
///
/// A target that starts past the end is somebody counting in a different
/// frame, and the cost of not saying so is a design that protects nothing.
///
/// # Errors
///
/// [`CoreError::InvalidRequest`] when the target runs off the template.
pub fn check_target_bounds(start: usize, length: usize, template_bases: usize) -> Result<()> {
    if start.saturating_add(length) > template_bases {
        return Err(CoreError::InvalidRequest(format!(
            "The target runs to base {}, past the end of a {}-base template.",
            start.saturating_add(length),
            template_bases
        )));
    }
    Ok(())
}

/// Check stretches no primer may overlap.
///
/// A region of no width excludes nothing, and one that starts past the end
/// excludes nothing either. Both are a caller believing a stretch is protected
/// when it is not, so both are refused before a process starts.
///
/// # Errors
///
/// [`CoreError::InvalidRequest`] naming the first offending region.
pub fn check_excluded(regions: &[(usize, usize)], template_bases: usize) -> Result<()> {
    for (index, (start, length)) in regions.iter().enumerate() {
        let number = index + 1;
        if *length == 0 {
            return Err(CoreError::InvalidRequest(format!(
                "Avoided region {number} is zero bases long, so it rules nothing out."
            )));
        }
        if start.saturating_add(*length) > template_bases {
            return Err(CoreError::InvalidRequest(format!(
                "Avoided region {number} runs to base {}, past the end of a \
                 {}-base template.",
                start.saturating_add(*length),
                template_bases
            )));
        }
    }
    Ok(())
}

/// Check positions measured on the template: known variants and their kin.
///
/// A variant off the end of the template masks nothing while looking exactly
/// like masking something clean.
///
/// # Errors
///
/// [`CoreError::InvalidRequest`] naming the first offending position.
pub fn check_positions(positions: &[usize], template_bases: usize, noun: &str) -> Result<()> {
    for position in positions {
        if *position >= template_bases {
            return Err(CoreError::InvalidRequest(format!(
                "A known {noun} at base {} is past the end of a {}-base template.",
                position.saturating_add(1),
                template_bases
            )));
        }
    }
    Ok(())
}

/// Check how many answers were asked for.
///
/// Zero asks for nothing and costs a process to say so; more than the ceiling
/// asks the worker for work nobody will read.
///
/// # Errors
///
/// [`CoreError::InvalidRequest`] naming the accepted range.
pub fn check_how_many(how_many: u8, ceiling: u8) -> Result<()> {
    if how_many == 0 {
        return Err(CoreError::InvalidRequest(
            "`howMany` has to be at least 1.".to_owned(),
        ));
    }
    if how_many > ceiling {
        return Err(CoreError::InvalidRequest(format!(
            "`howMany` is {how_many}. This endpoint returns up to {ceiling} \
             at once; ask for the rest in a second run."
        )));
    }
    Ok(())
}

/// Excluded regions in the worker's vocabulary.
///
/// Written once because multiple engines forward them and they must all speak
/// the same shape -- `[start, length]` pairs, absent when absent, never null.
#[must_use]
pub fn excluded_to_worker(regions: Option<&Vec<(usize, usize)>>) -> Option<serde_json::Value> {
    regions.map(|regions| {
        serde_json::Value::Array(
            regions
                .iter()
                .map(|(start, length)| serde_json::json!([start, length]))
                .collect(),
        )
    })
}

/// Validate the shared manufacturing/readout annotation block used by LAMP and RPA.
///
/// These annotations are provenance only.  They do not make a modified-probe
/// chemistry executable and they never alter sequence ranking by themselves.
pub fn check_modified_oligos(value: &serde_json::Value) -> Result<()> {
    let items = value.as_array().ok_or_else(|| {
        CoreError::InvalidRequest(
            "modifiedOligos must be an array of oligo annotation objects.".to_owned(),
        )
    })?;
    if items.len() > 24 {
        return Err(CoreError::InvalidRequest(
            "modifiedOligos may contain at most 24 entries.".to_owned(),
        ));
    }
    const ALLOWED: &[&str] = &[
        "role",
        "sequence",
        "fivePrimeLabel",
        "threePrimeBlock",
        "fluorophore",
        "quencher",
        "affinityLabel",
        "lateralFlowLabel",
        "cleavageSite",
        "manufacturerNotes",
        "internalModifications",
    ];
    const MOD_ALLOWED: &[&str] = &["kind", "position", "identity"];
    const MOD_KINDS: &[&str] = &[
        "thf",
        "dSpacer",
        "fluorophore",
        "quencher",
        "other-reviewed",
    ];
    for (index, item) in items.iter().enumerate() {
        let object = item.as_object().ok_or_else(|| {
            CoreError::InvalidRequest(format!("modifiedOligos[{index}] must be an object."))
        })?;
        if let Some(key) = object.keys().find(|key| !ALLOWED.contains(&key.as_str())) {
            return Err(CoreError::InvalidRequest(format!(
                "modifiedOligos[{index}] contains unknown field {key}."
            )));
        }
        let role = object
            .get("role")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        if role.is_empty()
            || role.len() > 40
            || !role
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
        {
            return Err(CoreError::InvalidRequest(format!(
                "modifiedOligos[{index}].role must be a 1–40 character identifier."
            )));
        }
        if let Some(sequence) = object.get("sequence").and_then(serde_json::Value::as_str) {
            if sequence.is_empty()
                || sequence.len() > 500
                || !sequence
                    .chars()
                    .all(|c| matches!(c.to_ascii_uppercase(), 'A' | 'C' | 'G' | 'T'))
            {
                return Err(CoreError::InvalidRequest(format!(
                    "modifiedOligos[{index}].sequence must contain 1–500 A/C/G/T bases."
                )));
            }
        }
        for key in [
            "fivePrimeLabel",
            "threePrimeBlock",
            "fluorophore",
            "quencher",
            "affinityLabel",
            "lateralFlowLabel",
        ] {
            if let Some(text) = object.get(key) {
                if text.as_str().is_none_or(|value| value.len() > 80) {
                    return Err(CoreError::InvalidRequest(format!(
                        "modifiedOligos[{index}].{key} must be text no longer than 80 characters."
                    )));
                }
            }
        }
        if let Some(notes) = object.get("manufacturerNotes") {
            if notes.as_str().is_none_or(|value| value.len() > 500) {
                return Err(CoreError::InvalidRequest(format!("modifiedOligos[{index}].manufacturerNotes must be text no longer than 500 characters.")));
            }
        }
        if let Some(site) = object.get("cleavageSite") {
            if site.as_u64().is_none_or(|value| value > 499) {
                return Err(CoreError::InvalidRequest(format!("modifiedOligos[{index}].cleavageSite must be a non-negative integer below 500.")));
            }
        }
        if let Some(raw_mods) = object.get("internalModifications") {
            let mods = raw_mods.as_array().ok_or_else(|| {
                CoreError::InvalidRequest(format!(
                    "modifiedOligos[{index}].internalModifications must be an array."
                ))
            })?;
            if mods.len() > 12 {
                return Err(CoreError::InvalidRequest(format!(
                    "modifiedOligos[{index}].internalModifications may contain at most 12 entries."
                )));
            }
            for (mod_index, raw_mod) in mods.iter().enumerate() {
                let modification = raw_mod.as_object().ok_or_else(|| CoreError::InvalidRequest(format!("modifiedOligos[{index}].internalModifications[{mod_index}] must be an object.")))?;
                if let Some(key) = modification
                    .keys()
                    .find(|key| !MOD_ALLOWED.contains(&key.as_str()))
                {
                    return Err(CoreError::InvalidRequest(format!("modifiedOligos[{index}].internalModifications[{mod_index}] contains unknown field {key}.")));
                }
                let kind = modification
                    .get("kind")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("");
                if !MOD_KINDS.contains(&kind) {
                    return Err(CoreError::InvalidRequest(format!("modifiedOligos[{index}].internalModifications[{mod_index}].kind is not recognised.")));
                }
                if modification
                    .get("position")
                    .and_then(serde_json::Value::as_u64)
                    .is_none_or(|value| value > 499)
                {
                    return Err(CoreError::InvalidRequest(format!("modifiedOligos[{index}].internalModifications[{mod_index}].position must be a non-negative integer below 500.")));
                }
                if modification
                    .get("identity")
                    .is_some_and(|value| value.as_str().is_none_or(|text| text.len() > 80))
                {
                    return Err(CoreError::InvalidRequest(format!("modifiedOligos[{index}].internalModifications[{mod_index}].identity must be text no longer than 80 characters.")));
                }
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn counts_are_in_bases_not_bytes() {
        // Two punctuation characters and ten bases: raw text length says
        // twelve, while the worker's coordinate frame contains ten bases.
        assert_eq!(base_count("ACGTACGTAC\u{2019}\u{2019}"), 10);
    }

    #[test]
    fn formatted_records_are_measured_without_their_metadata() {
        let fasta = ">a deliberately long description with letters\nACGTAC\n>second\nGGGG";
        assert_eq!(base_count(fasta), 6);

        let genbank = "LOCUS       example  6 bp\nORIGIN\n        1 acgtac\n//";
        assert_eq!(base_count(genbank), 6);
    }

    #[test]
    fn coordinates_and_punctuation_do_not_change_sequence_positions() {
        assert_eq!(base_count("1 acgtac 6"), 6);
        assert_eq!(base_count("ACGT-123"), 4);
    }

    #[test]
    fn an_empty_template_is_refused_and_a_full_one_is_measured() {
        assert!(check_template("   ", 100).is_err());
        assert_eq!(check_template("ACGTACGT", 100).expect("measured"), 8);
    }

    #[test]
    fn paste_errors_are_caught_before_a_process_is_paid_for() {
        let error = check_template("soheil@example.com", 100)
            .expect_err("an email address is not a sequence");
        assert!(error.to_string().contains("does not look like"));
        assert!(check_template("hello world", 100).is_err());
        // The net is deliberately coarse near its boundary -- English prose
        // leans on a, c, g, t and n more than intuition suggests -- but an
        // address, a name, or a URL in the sequence box never gets as far as
        // costing a process spawn. The worker remains the authority on what
        // is chemically meaningful.
    }

    #[test]
    fn real_file_formats_are_never_refused_by_the_plausibility_net() {
        let fasta = ">NM_000546.6 Homo sapiens TP53\nATGGAGGAGCCGCAGTCAGAT\n..60..";
        assert!(check_template(fasta, 100_000).is_ok());
        let genbank =
            "LOCUS       NM_000546          120 bp    mRNA\nORIGIN\n        1 atggaggagc\n//";
        assert!(check_template(genbank, 100_000).is_ok());
        let degenerate = "RYKMSWBDHVN";
        assert!(check_template(degenerate, 100).is_ok());
    }

    #[test]
    fn half_a_target_and_an_empty_one_are_both_refused() {
        assert!(check_target_pair(Some(4), None).is_err());
        assert!(check_target_pair(None, Some(4)).is_err());
        assert!(check_target_pair(Some(4), Some(0)).is_err());
        assert!(check_target_pair(Some(4), Some(8)).is_ok());
        assert!(check_target_pair(None, None).is_ok());
    }

    #[test]
    fn a_target_past_the_end_is_refused_without_overflowing() {
        assert!(check_target_bounds(4, 8, 10).is_err());
        // A usize::MAX length saturates instead of panicking in debug builds.
        assert!(check_target_bounds(4, usize::MAX, 10).is_err());
        assert!(check_target_bounds(0, 10, 10).is_ok());
    }

    #[test]
    fn excluded_regions_are_judged_the_same_everywhere() {
        assert!(check_excluded(&[(2, 0)], 10).is_err());
        assert!(check_excluded(&[(8, 40)], 10).is_err());
        // Saturation again, rather than a debug-build panic in the message.
        assert!(check_excluded(&[(8, usize::MAX)], 10).is_err());
        assert!(check_excluded(&[(2, 4)], 10).is_ok());
    }

    #[test]
    fn positions_off_the_template_name_themselves() {
        assert!(check_positions(&[3], 10, "variant").is_ok());
        let error = check_positions(&[12], 10, "variant").expect_err("past the end");
        assert!(error.to_string().contains("variant"));
    }

    #[test]
    fn how_many_has_a_floor_and_a_ceiling() {
        assert!(check_how_many(0, 10).is_err());
        assert!(check_how_many(11, 10).is_err());
        assert!(check_how_many(1, 10).is_ok());
        assert!(check_how_many(10, 10).is_ok());
    }

    #[test]
    fn rna_detection_uses_the_first_fasta_record_and_genbank_origin() {
        assert!(contains_rna_base(">rna\nACUG\n>ignored\nAAAA"));
        assert!(contains_rna_base(
            "LOCUS       rna\nORIGIN\n        1 acug\n//"
        ));
        assert!(!contains_rna_base(">dna\nACGT\n"));
    }

    #[test]
    fn excluded_regions_travel_as_pairs_and_absent_stays_absent() {
        let regions = vec![(4, 6)];
        assert_eq!(excluded_to_worker(Some(&regions)), Some(json!([[4, 6]])));
        assert_eq!(excluded_to_worker(None), None);
    }
}
