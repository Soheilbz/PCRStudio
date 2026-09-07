//! Assay profiles: the named things a person chooses between.
//!
//! A profile is an engine plus a point in the remaining facets plus the limits
//! and the wording. It carries no logic, which is why it lives in a data file
//! rather than in this one — adding an assay should be a reviewed entry, not a
//! deployment of new code.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Goal, Modifier, Status};

/// The profile file this build ships, read at compile time.
const PROFILES: &str = include_str!("../profiles.toml");

/// One named assay.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Profile {
    /// Stable, url-safe identifier. Also the route segment.
    pub id: String,
    /// Name shown wherever the assay appears.
    pub name: String,
    /// One line describing what it designs.
    pub summary: String,
    /// What sets this assay apart from the ones beside it, and when to reach
    /// for it.
    ///
    /// Required, not optional. Several assays run the same engine and read
    /// almost alike from their summaries; without this a person choosing
    /// between them is guessing, and guessing at the bench costs an order of
    /// oligos.
    pub guidance: String,
    /// How the design is checked before any bench validation is performed.
    /// This is module-owned explanatory text, not a claim that an in-silico
    /// result replaces an experimental assay.
    pub checks: String,
    /// Which search runs.
    pub engine: EngineId,
    /// Which group it appears under.
    pub goal: Goal,
    /// How finished it is.
    pub status: Status,
    /// Modifiers this assay may be combined with.
    ///
    /// A subset of what the engine accepts — checked when the registry is
    /// built, never at request time.
    #[serde(default)]
    pub modifiers: Vec<Modifier>,
    /// What this assay differs from the engine's own defaults by.
    ///
    /// This is what makes Colony PCR a different assay from Standard PCR
    /// rather than the same search under a second name: both run the
    /// flanking-pair engine, and without this they behave identically, which
    /// they should not. A crude colony lysate cannot give a four-kilobase
    /// product however good the primers are.
    #[serde(default)]
    pub defaults: ProfileDefaults,
    /// Inputs this assay cannot be run without.
    ///
    /// Different from a constraint. A constraint is a number the search works
    /// inside; this is a question the assay is not the assay without an answer
    /// to. Species-specific PCR is defined by what it must *not* amplify, so a
    /// run with no background is not a permissive run of that assay -- it is a
    /// different assay wearing its name, and the primers it produces are
    /// specific to nothing in particular.
    ///
    /// Declared here rather than checked inside an engine because it is a
    /// property of the assay: two assays on the same engine can differ on it,
    /// and one place that enforces every assay's requirements is one place to
    /// get right.
    #[serde(default)]
    pub requires: Vec<Requirement>,
    /// What this assay needs of the enzyme, so the offer can be narrowed.
    ///
    /// Stated as activities rather than as a list of enzyme names, and the
    /// difference is the point. A list of names is twenty-one places to be
    /// wrong and goes stale the day a tenth enzyme arrives; an activity is a
    /// fact about the enzyme, recorded once beside the enzyme, and every
    /// assay's offer follows from it.
    ///
    /// Empty means every enzyme, which is what an empty list already means for
    /// `purposes` — and is the honest default: narrowing an assay's list is a
    /// claim about what that assay requires, and a claim nobody has researched
    /// should not be put in front of somebody at a bench.
    #[serde(default)]
    pub enzyme: Vec<EnzymeNeed>,
}

fn toml_number(value: &toml::Value) -> Option<f64> {
    value
        .as_float()
        .or_else(|| value.as_integer().map(|number| number as f64))
}

impl Profile {
    /// Everything this assay's enzyme must be, declared and implied.
    ///
    /// The implied one is thermostability, and it is derived rather than
    /// written into nineteen profiles. A reaction that cycles to 95 degrees
    /// needs an enzyme that survives being cycled to 95 degrees; LAMP needs a
    /// strand-displacing enzyme, while RPA needs a complete recombinase-
    /// compatible chemistry because opening the duplex is handled by the
    /// recombinase system. So those requirements are explicit here, and the
    /// implied thermostability means a tenth enzyme that works warm and dies
    /// at 95 cannot be offered to a thermocycled assay because somebody forgot
    /// a line.
    ///
    /// The two are still different facts, which is why they are different
    /// variants: an enzyme could displace strands *and* survive cycling, and
    /// this would go on offering it to both.
    #[must_use]
    pub fn enzyme_needs(&self) -> Vec<EnzymeNeed> {
        let mut needs = self.enzyme.clone();
        if !needs.contains(&EnzymeNeed::StrandDisplacing)
            && !needs.contains(&EnzymeNeed::Thermostable)
            && !needs.contains(&EnzymeNeed::RpaCompatible)
        {
            needs.push(EnzymeNeed::Thermostable);
        }
        needs
    }
}

/// One activity an assay's enzyme must, or must not, have.
///
/// A closed set for the same reason `Requirement` is: a profile cannot ask for
/// a property nothing records. Each variant carries the assay that motivated
/// it, because each is a claim about chemistry rather than a preference, and a
/// claim without its reason beside it is one nobody can check or overturn.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EnzymeNeed {
    /// Opens double-stranded DNA ahead of itself.
    ///
    /// What makes an isothermal reaction possible at all: LAMP and RPA never
    /// heat the template apart, so the polymerase has to. Taq in a LAMP tube
    /// produces nothing whatever the primers are.
    StrandDisplacing,
    /// Survives being cycled to 95 degrees, over and over.
    ///
    /// Not the same as working warm. *Bst* runs at 65 and is inactivated
    /// around 80; the recombinase enzymes work at body temperature. Both are
    /// useless in anything with a denaturation step.
    Thermostable,
    /// Chews through a probe in its path as it extends.
    ///
    /// For a hydrolysis-probe assay this activity *is* the read-out — the
    /// signal is the polymerase destroying the probe — so an enzyme without it
    /// amplifies correctly and reports nothing.
    FivePrimeExonuclease,
    /// Does *not* chew through a downstream primer as it extends.
    ///
    /// A single-tube nested reaction holds both primer pairs at once, so an
    /// enzyme with that activity destroys the inner primers while extending
    /// the outer product.
    NoFivePrimeExonuclease,
    /// Resects a mismatched 3' end rather than extending from it.
    ///
    /// What makes a long PCR work. Taq alone past about three kilobases gives
    /// truncated products rather than a band, and what fixes it is a second
    /// enzyme in much smaller amounts providing exactly this.
    Proofreading,
    /// Does *not* resect a mismatched 3' end.
    ///
    /// An allele-specific design *is* a deliberate 3' mismatch, so an enzyme
    /// that proofreads removes the base the discrimination rests on — and then
    /// both alleles amplify equally well and every sample reads as a
    /// heterozygote, which is a result somebody acts on.
    NoProofreading,
    /// Is a complete recombinase-polymerase amplification chemistry.
    ///
    /// Strand displacement by itself is not enough to make RPA: the reaction
    /// also needs the recombinase/SSB system and a polymerase validated for
    /// that system. This capability keeps an LAMP mix such as Bst from being
    /// presented as an RPA substitute merely because both reactions displace
    /// strands.
    RpaCompatible,
}

impl EnzymeNeed {
    /// The activity flag this reads, and whether it must be set or clear.
    #[must_use]
    pub const fn wants(self) -> (&'static str, bool) {
        match self {
            Self::StrandDisplacing => ("strand_displacing", true),
            Self::Thermostable => ("thermostable", true),
            Self::FivePrimeExonuclease => ("five_prime_exonuclease", true),
            Self::NoFivePrimeExonuclease => ("five_prime_exonuclease", false),
            Self::Proofreading => ("proofreading", true),
            Self::NoProofreading => ("proofreading", false),
            Self::RpaCompatible => ("rpa_compatible", true),
        }
    }

    /// Why this assay needs it, in words somebody at a bench would use.
    #[must_use]
    pub const fn why(self) -> &'static str {
        match self {
            Self::StrandDisplacing => concat!(
                "This reaction never heats the template apart, so the ",
                "polymerase has to open it as it goes. An enzyme that cannot ",
                "produces nothing here, whatever the primers are."
            ),
            Self::Thermostable => concat!(
                "This reaction denatures at 95 degrees, over and over. An ",
                "enzyme that works warm is not the same as one that survives ",
                "that."
            ),
            Self::FivePrimeExonuclease => concat!(
                "The signal here is the polymerase chewing through the probe. ",
                "An enzyme without that activity amplifies correctly and ",
                "reports nothing."
            ),
            Self::NoFivePrimeExonuclease => concat!(
                "Both primer pairs are in one tube from the start, so an ",
                "enzyme that chews through what is in front of it destroys the ",
                "inner primers while extending the outer product."
            ),
            Self::Proofreading => concat!(
                "Taq on its own runs out past about three kilobases and gives ",
                "a smear of truncated products rather than a band. What fixes ",
                "it is an enzyme that trims the mismatched ends it leaves ",
                "behind, so the extension can carry on."
            ),
            Self::NoProofreading => concat!(
                "This design is a deliberate mismatch at the primer's 3' end. ",
                "An enzyme that trims mismatched ends removes exactly that ",
                "base, and then both alleles amplify equally well and every ",
                "sample reads as a heterozygote."
            ),
            Self::RpaCompatible => concat!(
                "RPA is a recombinase-assisted reaction, not merely a warm ",
                "strand-displacing polymerase. The complete chemistry has to ",
                "be validated for recombinase loading, single-strand binding ",
                "and extension at the stated hold."
            ),
        }
    }
}

/// An input an assay cannot do without.
///
/// A closed set rather than free text, so a profile cannot ask for something
/// nothing knows how to check.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Requirement {
    /// Sequence the design must be checked against and stay silent on.
    Background,
    /// Intended-target strains/variants the assay claims it should continue to amplify.
    Inclusivity,
}

impl Requirement {
    /// The request field that satisfies this.
    #[must_use]
    pub const fn field(self) -> &'static str {
        match self {
            Self::Background => "background",
            Self::Inclusivity => "inclusivity",
        }
    }

    /// What to say when it is missing, in the words of the assay rather than
    /// of the validator.
    #[must_use]
    pub const fn why(self) -> &'static str {
        match self {
            Self::Background => concat!(
                "This assay is defined by what it must not amplify, so it needs ",
                "the sequences it has to stay silent on. Paste the relatives, the ",
                "host genome, or whatever else is in the tube. Without one, ",
                "nothing here would be specific to anything in particular."
            ),
            Self::Inclusivity => concat!(
                "An executable species-specific design also needs intended-target diversity, ",
                "not one representative template. Provide a bounded FASTA panel of ",
                "the strains/variants the assay is required to amplify."
            ),
        }
    }
}
/// Optional lower and upper bounds for one numeric assay setting.
///
/// An omitted bound means that side is not constrained by the profile.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct NumericEnvelope {
    /// The lowest permitted value, when the profile declares one.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min: Option<f64>,
    /// The highest permitted value, when the profile declares one.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max: Option<f64>,
}

/// The numbers and choices one assay differs by.
///
/// Free-form on purpose. The field names belong to the worker, which owns the
/// constraint and cycling vocabularies and refuses a name it does not know — a
/// second copy of those lists here could only go stale, and a stale copy that
/// silently drops a setting is worse than no copy at all. What is checked here
/// is the shape: that a name could be a name and a value could be a value.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProfileDefaults {
    /// The enzyme this assay is normally run with.
    ///
    /// Long-range PCR is not ordinary PCR with a bigger number in it: it is a
    /// different enzyme, with a different extension rate and, for some, a
    /// two-step programme.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// Additional polymerase/reaction presets explicitly reviewed as equivalent
    /// for this exact assay profile. Capability similarity alone is not enough
    /// in Scientific-Strict mode; alternatives belong here only after a sourced
    /// assay-specific review.
    #[serde(default)]
    pub allowed_polymerases: Vec<String>,
    /// Assay chemistry identity, separate from the thermodynamic/polymerase preset.
    ///
    /// This exists because a reader/platform label is not a chemistry model. KASP,
    /// for example, is endpoint competitive allele-specific PCR with FRET cassettes;
    /// it must never be represented as an intercalating-dye qPCR polymerase alias.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub chemistry_family: Option<String>,
    /// The purpose selected when a new project has not supplied one.
    ///
    /// This is separate from `purposes`: a colony screen can serve several
    /// downstream uses, but its first question should still be the screening
    /// one rather than the generic amplification window.
    #[serde(default)]
    pub default_purpose: Option<String>,
    /// Which downstream uses this assay can serve.
    ///
    /// Empty means all of them. A list is a refusal: asking a colony screen to
    /// produce a three-kilobase cloning product is not a preference to be
    /// balanced, it is a request the assay cannot meet, and saying so up front
    /// is better than quietly returning something neither party wanted.
    #[serde(default)]
    pub purposes: Vec<String>,
    /// What a pair must satisfy, by the worker's own constraint names.
    #[serde(default)]
    pub constraints: BTreeMap<String, toml::Value>,
    /// Changes to a thermal programme that are owned by a sourced, named
    /// assay/profile rather than guessed from primer Tm or product length.
    /// Pre-analytical preparation steps (for example colony lysis) are kept in
    /// their own assay/SOP provenance and are not encoded as generic cycling.
    #[serde(default)]
    pub cycling: BTreeMap<String, toml::Value>,
    /// Override semantics for selected numeric search fields. Values are
    /// `locked`, `bounded` (the caller may tighten but not widen the profile
    /// envelope), or `recommended` (a transparent starting/tuning value).
    #[serde(default)]
    pub constraint_policy: BTreeMap<String, String>,
    /// Optional outer qualification envelope for a tunable numeric field.
    ///
    /// This is deliberately separate from `constraints`: a supplier may say
    /// "30–35 nt is preferred" while the reviewed branch can still explore a
    /// wider range. The preferred values remain the search defaults; this map
    /// only prevents an explicit override from extrapolating beyond the
    /// versioned branch while keeping the same chemistry/protocol identity.
    #[serde(default)]
    pub constraint_envelope: BTreeMap<String, NumericEnvelope>,
    /// Override semantics for selected reaction-condition fields.
    #[serde(default)]
    pub condition_policy: BTreeMap<String, String>,
}

impl Profile {
    /// Reject an id that would not survive a URL.
    ///
    /// # Errors
    ///
    /// [`CoreError::InvalidRequest`] naming the offending id.
    pub fn check_id(&self) -> Result<()> {
        if self.id.is_empty() {
            return Err(CoreError::InvalidRequest(
                "a profile id must not be empty".into(),
            ));
        }
        if !self
            .id
            .chars()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-')
        {
            return Err(CoreError::InvalidRequest(format!(
                "the profile id `{}` must contain only lowercase letters, digits and hyphens",
                self.id
            )));
        }
        Ok(())
    }

    /// Whether the defaults could be sent to a worker at all.
    ///
    /// # Errors
    ///
    /// [`CoreError::InvalidRequest`] naming the offending key. A default that
    /// cannot be a setting name is a mistake in `profiles.toml`, and this is
    /// checked when the registry is built so it never reaches a request.
    pub fn check_defaults(&self) -> Result<()> {
        if self
            .defaults
            .default_purpose
            .as_deref()
            .is_some_and(|purpose| purpose.trim().is_empty())
        {
            return Err(CoreError::InvalidRequest(format!(
                "`{}` has an empty default purpose",
                self.id
            )));
        }
        if self
            .defaults
            .chemistry_family
            .as_deref()
            .is_some_and(|value| value.trim().is_empty())
        {
            return Err(CoreError::InvalidRequest(format!(
                "`{}` has an empty chemistry family",
                self.id
            )));
        }
        if let Some(default) = self.defaults.default_purpose.as_deref() {
            if !self.defaults.purposes.is_empty()
                && !self
                    .defaults
                    .purposes
                    .iter()
                    .any(|purpose| purpose == default)
            {
                return Err(CoreError::InvalidRequest(format!(
                    "`{}` defaults to `{default}`, which it does not offer",
                    self.id
                )));
            }
        }
        for (table, policies) in [
            ("constraintPolicy", &self.defaults.constraint_policy),
            ("conditionPolicy", &self.defaults.condition_policy),
        ] {
            for (key, policy) in policies {
                if !matches!(policy.as_str(), "locked" | "bounded" | "recommended") {
                    return Err(CoreError::InvalidRequest(format!(
                        "`{}` gives {table}.{key} unknown override policy `{policy}`; use locked, bounded or recommended",
                        self.id
                    )));
                }
            }
        }
        for (key, envelope) in &self.defaults.constraint_envelope {
            if envelope.min.is_none() && envelope.max.is_none() {
                return Err(CoreError::InvalidRequest(format!(
                    "`{}` gives constraintEnvelope.{key} no min or max",
                    self.id
                )));
            }
            if envelope
                .min
                .zip(envelope.max)
                .is_some_and(|(minimum, maximum)| minimum > maximum)
            {
                return Err(CoreError::InvalidRequest(format!(
                    "`{}` gives constraintEnvelope.{key} min greater than max",
                    self.id
                )));
            }
            if let Some(value) = self.defaults.constraints.get(key).and_then(toml_number) {
                if envelope.min.is_some_and(|minimum| value < minimum)
                    || envelope.max.is_some_and(|maximum| value > maximum)
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "`{}` gives constraints.{key}={value} outside its declared constraintEnvelope",
                        self.id
                    )));
                }
            }
        }
        let tables = [
            ("constraints", &self.defaults.constraints),
            ("cycling", &self.defaults.cycling),
        ];
        for (table, entries) in tables {
            for (key, value) in entries {
                if key.is_empty()
                    || !key
                        .chars()
                        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_')
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "`{}` names `{key}` under {table}, which cannot be a setting                          name: those are lowercase with underscores",
                        self.id
                    )));
                }
                if !(value.is_integer() || value.is_float() || value.is_str()) {
                    return Err(CoreError::InvalidRequest(format!(
                        "`{}` gives {table}.{key} a value that is neither a number nor                          a name",
                        self.id
                    )));
                }
            }
        }
        Ok(())
    }
}

#[derive(Debug, Deserialize)]
struct ProfileFile {
    #[serde(default)]
    profile: Vec<Profile>,
}

/// Every assay this build ships.
///
/// # Errors
///
/// [`CoreError::InvalidRequest`] if the profile file does not parse, which is
/// a build-time mistake reaching runtime.
pub fn catalogue() -> Result<Vec<Profile>> {
    let parsed: ProfileFile = toml::from_str(PROFILES).map_err(|error| {
        CoreError::InvalidRequest(format!("profiles.toml is malformed: {error}"))
    })?;
    Ok(parsed.profile)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn profile(id: &str) -> Profile {
        Profile {
            id: id.to_owned(),
            name: "Test".into(),
            summary: "s".into(),
            guidance: "g".into(),
            checks: "c".into(),
            engine: EngineId::FlankingPair,
            goal: Goal::Amplify,
            status: Status::Planned,
            modifiers: Vec::new(),
            defaults: ProfileDefaults::default(),

            requires: Vec::new(),
            enzyme: Vec::new(),
        }
    }

    #[test]
    fn a_default_named_like_a_constraint_is_accepted() {
        let mut p = profile("colony-pcr");
        p.defaults
            .constraints
            .insert("product_max".into(), toml::Value::Integer(1200));
        p.check_defaults().expect("a plain constraint name");
    }

    #[test]
    fn a_default_purpose_must_be_one_of_the_offered_purposes() {
        let mut p = profile("colony-pcr");
        p.defaults.default_purpose = Some("cloning".into());
        p.defaults.purposes = vec!["general".into(), "screen".into()];
        let message = p
            .check_defaults()
            .expect_err("a hidden purpose is not a usable default")
            .to_string();
        assert!(message.contains("cloning"), "{message}");
    }

    #[test]
    fn a_whitespace_default_purpose_is_refused_at_build_time() {
        let mut p = profile("colony-pcr");
        p.defaults.default_purpose = Some("  \t".into());
        let message = p
            .check_defaults()
            .expect_err("whitespace is not a purpose")
            .to_string();
        assert!(message.contains("empty"), "{message}");
    }

    #[test]
    fn a_default_that_could_not_be_a_constraint_name_is_refused_at_build_time() {
        // A profile setting a field the worker has no name for would simply
        // never take effect, which is the hardest kind of mistake to notice:
        // the assay looks configured and behaves as though it is not.
        let mut p = profile("colony-pcr");
        p.defaults
            .constraints
            .insert("productMax".into(), toml::Value::Integer(1200));
        let message = p
            .check_defaults()
            .expect_err("camelCase is not ours")
            .to_string();
        assert!(message.contains("productMax"), "{message}");
    }

    #[test]
    fn a_default_that_is_neither_a_number_nor_a_name_is_refused() {
        let mut p = profile("colony-pcr");
        p.defaults
            .constraints
            .insert("product_max".into(), toml::Value::Boolean(true));
        assert!(p.check_defaults().is_err());
    }

    #[test]
    fn the_shipped_catalogue_has_defaults_that_could_reach_a_worker() {
        for profile in catalogue().expect("the catalogue parses") {
            profile.check_defaults().expect(&profile.id);
        }
    }
}
