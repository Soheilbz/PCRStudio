//! The vocabulary every assay is described in.
//!
//! Three closed sets. Closed is the point: an assay that does not fit one of
//! these is a conversation, not a quiet addition. The sets come from a survey
//! of the published methods, where an engine is one combination of *what you
//! start from* and *what shape the answer has* — the two things that make a
//! search unreusable.

use serde::{Deserialize, Serialize};

/// What a design has to be checked against.
///
/// This is the only facet the interface groups by, and it is easy to read as
/// *what you do with the tube afterwards*. It is not that. Almost any assay
/// here can be used to find out whether an organism is present, so "what it is
/// used for" would put nearly the whole catalogue under one heading and
/// classify nothing.
///
/// A goal is the constraint that changes the search. Standard PCR is checked
/// against its template and nothing else; species-specific PCR is the same
/// engine checked against a background of relatives that must not amplify.
/// Same output, different question, so they are different assays — and that
/// difference is what this facet records. [`Goal::rule`] states each one.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Goal {
    /// Get a copy of a region.
    Amplify,
    /// Measure how much is there.
    Quantify,
    /// Tell two alleles apart.
    Genotype,
    /// Find out whether an organism is present.
    Detect,
    /// Read a genome, or a stretch of one.
    Sequence,
    /// Join fragments into a construct.
    Assemble,
    /// Change a sequence on purpose.
    Engineer,
}

impl Goal {
    /// Every goal, in the order the interface presents them.
    #[must_use]
    pub const fn all() -> &'static [Self] {
        &[
            Self::Amplify,
            Self::Quantify,
            Self::Genotype,
            Self::Detect,
            Self::Sequence,
            Self::Assemble,
            Self::Engineer,
        ]
    }

    /// Human-readable label.
    #[must_use]
    pub const fn label(self) -> &'static str {
        match self {
            Self::Amplify => "Amplify a region",
            Self::Quantify => "Quantify",
            Self::Genotype => "Genotype a variant",
            Self::Detect => "Detect an organism",
            Self::Sequence => "Sequence a genome",
            Self::Assemble => "Clone or assemble",
            Self::Engineer => "Engineer a change",
        }
    }

    /// What a design under this goal is checked against.
    ///
    /// The sentence that decides which group an assay belongs in. It lives
    /// here rather than in the interface because it is the definition of the
    /// term, not a caption for one screen.
    #[must_use]
    pub const fn rule(self) -> &'static str {
        match self {
            Self::Amplify => {
                "Checked against the template alone: one clean product from one known sequence."
            }
            Self::Quantify => {
                "Checked for even amplification over a short product, because the signal is the                  measurement rather than a band at the end."
            }
            Self::Genotype => {
                "Checked against both alleles at once: the design has to work on one and fail on                  the other."
            }
            Self::Detect => {
                "Checked against a background of related organisms that must not amplify, not                  only against the target."
            }
            Self::Sequence => {
                "Checked across a whole region rather than one site: coverage and overlap decide                  the design before any single pair does."
            }
            Self::Assemble => {
                "Checked as part of a construct: the ends have to join what comes next, not only                  bind the template."
            }
            Self::Engineer => {
                "Checked against a template it deliberately disagrees with, at the position being                  changed."
            }
        }
    }
}

include!("../generated/engine_id.generated.rs");

/// Something applied *to* an engine rather than listed beside it.
///
/// The distinction is the whole point of the taxonomy: a thing that can be
/// combined must never appear as an alternative, or it ends up belonging in
/// three places at once.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Modifier {
    /// Design a set of assays that can share one tube.
    Multiplex,
    /// The template is RNA; design over the transcript and mind the junctions.
    ReverseTranscription,
    /// Design against the sequence as it reads after bisulfite treatment.
    BisulfiteConversion,
    /// Carry a 5-prime tail that takes no part in annealing to the target.
    Tails,
    /// Avoid placing a primer over known variation.
    VariantMasking,
}

impl Modifier {
    /// Every modifier this build knows how to name.
    #[must_use]
    pub const fn all() -> &'static [Self] {
        &[
            Self::Multiplex,
            Self::ReverseTranscription,
            Self::BisulfiteConversion,
            Self::Tails,
            Self::VariantMasking,
        ]
    }

    /// Human-readable label.
    #[must_use]
    pub const fn label(self) -> &'static str {
        match self {
            Self::Multiplex => "Multiplexed",
            Self::ReverseTranscription => "From RNA",
            Self::BisulfiteConversion => "Bisulfite-converted",
            Self::Tails => "With 5-prime tails",
            Self::VariantMasking => "Variant-aware",
        }
    }
}

/// How finished an assay is.
///
/// Shown everywhere the assay appears. It is the only thing standing between
/// someone at a bench and a number they should not trust.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Named and routable, with no implementation behind it.
    Planned,
    /// Computes, and checked against sequence rather than against a bench.
    ///
    /// Every one of the twenty-one is here, and the word is load-bearing.
    /// Restated precisely because the old wording — "not yet checked against a
    /// reference result" — had stopped being true: these *are* checked, against
    /// real GenBank records with recorded golden answers and against published
    /// primer pairs. What has never happened is somebody running the oligos.
    ///
    /// So the claim is: the arithmetic is checked and the chemistry is not.
    Experimental,
    /// The same, plus primers from it ordered and run at a bench.
    ///
    /// Nothing is here, and promoting something is not a coding decision. What
    /// it takes is stated in [`Self::promotion`] rather than left for whoever
    /// next feels confident: a test suite going green is evidence about this
    /// program, and `stable` is a claim about a reaction.
    Stable,
}

impl Status {
    /// Every status, in the order they progress.
    #[must_use]
    pub const fn all() -> &'static [Self] {
        &[Self::Planned, Self::Experimental, Self::Stable]
    }

    /// Human-readable label.
    #[must_use]
    pub const fn label(self) -> &'static str {
        match self {
            Self::Planned => "Planned",
            Self::Experimental => "Experimental",
            Self::Stable => "Stable",
        }
    }

    /// What this word claims, in the words somebody at a bench would use.
    ///
    /// Published because a badge reading "Experimental" with nothing behind it
    /// is not a claim anybody can act on, and the people this is for are
    /// deciding whether to order oligos from it.
    #[must_use]
    pub const fn means(self) -> &'static str {
        match self {
            Self::Planned => concat!(
                "Listed for planning only; a design result is not available for this ",
                "assay yet."
            ),
            Self::Experimental => concat!(
                "PCRStudio has a defined, reviewable computational workflow for this assay, but ",
                "this status does not mean it has been validated in your lab. Review the sequence, ",
                "chemistry, controls and output, then verify it with an appropriate bench run ",
                "before relying on it."
            ),
            Self::Stable => concat!(
                "The computational workflow and bench validation for this assay have been documented. ",
                "Confirm that your sequence, chemistry and instrument match the validated scope."
            ),
        }
    }

    /// What it would take to promote this, so nobody has to guess.
    ///
    /// Every assay in this build is `Experimental`, and the reason is not that
    /// the work is unfinished — it is that `Stable` is a claim about a bench
    /// and this project has not been to one. Written down because an open
    /// question with no criterion attached gets closed by whoever is most
    /// confident rather than by whoever has the evidence.
    ///
    /// These sentences are shown to whoever is deciding whether to order
    /// oligos, so they say what evidence is wanted and not how this repository
    /// is arranged. For whoever makes the change: the README lists every
    /// assay's status and `readme_matches_the_registry` fails when the two stop
    /// agreeing — treat that failure as the reminder it was written to be.
    #[must_use]
    pub const fn promotion(self) -> Option<&'static str> {
        match self {
            Self::Planned => Some("A working design workflow and a documented result on a real sequence."),
            Self::Experimental => Some(concat!(
                "Run representative designs with a named chemistry, record the observed product or ",
                "readout, and keep the sequence and run conditions with the result."
            )),
            Self::Stable => None,
        }
    }
}
