//! The second engine that computes: one pair for a whole family.
//!
//! `flanking-pair` searches one sequence. This searches an alignment, and the
//! answer is a mixture rather than an oligo — a degenerate primer, written in
//! IUPAC, that fits every sequence in the alignment at once.
//!
//! That makes it a different engine rather than a setting on the first one.
//! Primer3 cannot design a mixture, so the search is ours; the constraints
//! that matter have no counterpart in ordinary design (how many molecules the
//! mixture may hold, how far its melting temperatures may spread, how much of
//! the 3' end must be identical in every sequence); and the input is not a
//! sequence but an alignment, which is a thing that can be wrong in ways a
//! sequence cannot.
//!
//! Nothing scientific happens in this file. It checks the request and hands it
//! to the worker.

use serde::{Deserialize, Serialize};

use super::common::{check_how_many, check_template};
use crate::engine::Engine;
use crate::engines::tiling_scheme::FivePrimeTails;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

include!("consensus_authority.generated.rs");

/// Modifiers this engine will be combined with.
///
/// Degeneracy is how a consensus pair tolerates variation. Masking variants
/// out instead would remove the thing it is built to cover, so
/// `VariantMasking` is absent on purpose.
const ACCEPTS: &[Modifier] = &[Modifier::ReverseTranscription];

/// The largest alignment this will accept in one request.
const MAX_ALIGNMENT_CHARACTERS: usize = 4_000_000;

/// The most pairs one request may ask for.
///
/// The same ceiling the worker itself applies to a `run`; naming it here too
/// means a request that asks for two hundred is refused before a process is
/// started rather than answered with fifty by the far end.
const MAX_HOW_MANY: u8 = 50;

/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ConsensusPairRequest {
    /// The aligned sequences, as FASTA. Every row the same length.
    pub template: String,
    /// Whether lowercase letters in the submitted template are intentional
    /// soft masking. None means the caller did not resolve the ambiguity; the
    /// Scientific-Strict worker refuses lowercase input in that case instead of
    /// guessing from how much of the sequence happens to be lowercase.
    #[serde(default)]
    pub lowercase_masking: Option<bool>,
    /// What to call the design.
    #[serde(default)]
    pub name: Option<String>,
    /// Which assay this is, and the numbers that assay differs by.
    ///
    /// Set by the route from the address, never by the caller.
    #[serde(default)]
    pub assay: Option<serde_json::Value>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// What a degenerate pair has to satisfy.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// How many distinct pairs to aim for.
    #[serde(default)]
    pub how_many: Option<u8>,
    /// Whether PCRStudio aligns the submitted family or trusts a caller-supplied alignment.
    /// `auto` is the normal pipeline; `prealigned` is an explicit provenance choice.
    #[serde(default)]
    pub alignment_mode: Option<String>,
    /// Explicit universal-primer consensus policy. Panel weights/strata are
    /// caller evidence and are never interpreted as population prevalence.
    #[serde(default)]
    pub consensus_policy: Option<String>,
    /// JSON object keyed by FASTA record id with optional weight/stratum and
    /// descriptive sampling metadata.
    #[serde(default)]
    pub panel_metadata: Option<serde_json::Value>,
    /// How a degenerate IUPAC primer is intended to be manufactured/pooled.
    #[serde(default)]
    pub formulation_mode: Option<String>,
    /// Optional declared total pool concentration used only for nominal
    /// equal-member concentration reporting.
    #[serde(default)]
    pub formulation_total_concentration_nm: Option<f64>,
    /// Finite user-supplied non-target FASTA panel for bounded specificity.
    #[serde(default)]
    pub nontarget: Option<String>,
    /// Optional caller-supplied alternative MSA for sensitivity evidence.
    #[serde(default)]
    pub alternative_alignment: Option<String>,
    /// Identity of the alternative-alignment validator/backend.
    #[serde(default)]
    pub alignment_audit_backend: Option<String>,
    /// Empirical validation observations; never a hidden ranking input.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
    /// Whether the tube starts from RNA rather than DNA.
    ///
    /// Eight assays declare the reverse-transcription modifier and none could
    /// say so, which made it a label rather than a setting. It puts a hold in
    /// front of the programme — a one-step RT-PCR whose first denaturation
    /// never happens amplifies nothing.
    #[serde(default)]
    pub from_rna: Option<bool>,
    /// What to put in front of every oligo, if anything.
    ///
    /// A degenerate pair is usually read by Sanger off a universal primer, so
    /// both oligos carry M13 or similar. Not on the template, so it takes no
    /// part in the first round's annealing — and a degenerate pool is already
    /// the coolest-member problem, which adding thirty unbound bases to the
    /// calculation would obscure entirely.
    #[serde(default)]
    pub tails: Option<FivePrimeTails>,
}

/// A degenerate pair search, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct ConsensusPair {
    worker: Worker,
}

impl ConsensusPair {
    /// An engine that will call whatever `PCR_PYTHON` names.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// An engine bound to a particular interpreter.
    #[must_use]
    pub fn with_worker(worker: Worker) -> Self {
        Self { worker }
    }
}

impl Engine for ConsensusPair {
    fn id(&self) -> EngineId {
        EngineId::ConsensusPair
    }

    fn accepts(&self) -> &'static [Modifier] {
        ACCEPTS
    }

    fn presets(&self) -> Result<Option<serde_json::Value>> {
        self.worker
            .call("universal_presets", &serde_json::json!({}))
            .map(Some)
    }

    fn validate(&self, request: &serde_json::Value) -> Result<()> {
        parse(request).map(|_| ())
    }

    fn design(&self, request: serde_json::Value) -> Result<serde_json::Value> {
        let parsed = parse(&request)?;
        self.worker.call("universal", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<ConsensusPairRequest> {
    let parsed: ConsensusPairRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

impl ConsensusPairRequest {
    /// Whether this request could describe a family at all.
    ///
    /// The template check is the shared one from [`super::common`], measured
    /// against this endpoint's own ceiling -- an alignment is several records
    /// in one string, so its limit is larger, but it is still one request.
    fn check(&self) -> Result<()> {
        check_template(&self.template, MAX_ALIGNMENT_CHARACTERS)?;
        // Caught here rather than in the worker so the message is about the
        // thing somebody can see, not about a column count they cannot.
        if self.template.matches('>').count() < 2 {
            return Err(CoreError::InvalidRequest(
                "This module designs one pair for a family, so it needs at least two \
                 sequences in FASTA. For a single sequence, Standard PCR is the module."
                    .to_owned(),
            ));
        }
        if let Some(how_many) = self.how_many {
            check_how_many(how_many, MAX_HOW_MANY)?;
        }
        let assay_id = self
            .assay
            .as_ref()
            .and_then(|assay| assay.get("id"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default();
        if assay_id == "universal-primers"
            && self
                .alignment_mode
                .as_deref()
                .filter(|value| !value.is_empty())
                .is_none()
        {
            return Err(CoreError::InvalidRequest(
                "universal-primers requires explicit `alignmentMode`: auto or prealigned; PCRStudio does not infer whether supplied gaps are scientific input.".to_owned(),
            ));
        }
        if let Some(mode) = self.alignment_mode.as_deref() {
            if !matches!(mode, "auto" | "prealigned") {
                return Err(CoreError::InvalidRequest(
                    "alignmentMode must be `auto` or `prealigned`".to_owned(),
                ));
            }
        }
        if let Some(policy) = self.consensus_policy.as_deref() {
            if !CONSENSUS_CONSENSUS_POLICIES.contains(&policy) {
                return Err(CoreError::InvalidRequest(format!(
                    "consensusPolicy must be one of: {}",
                    CONSENSUS_CONSENSUS_POLICIES.join(", ")
                )));
            }
        }
        if let Some(mode) = self.formulation_mode.as_deref() {
            if !CONSENSUS_FORMULATION_MODES.contains(&mode) {
                return Err(CoreError::InvalidRequest(format!(
                    "formulationMode must be one of: {}",
                    CONSENSUS_FORMULATION_MODES.join(", ")
                )));
            }
        }
        if let Some(value) = self.formulation_total_concentration_nm {
            if !value.is_finite() || value <= 0.0 {
                return Err(CoreError::InvalidRequest(
                    "formulationTotalConcentrationNm must be a finite positive number".to_owned(),
                ));
            }
        }
        if self.consensus_policy.as_deref() == Some("stratified") && self.panel_metadata.is_none() {
            return Err(CoreError::InvalidRequest(
                "stratified consensusPolicy requires panelMetadata with a stratum for every record"
                    .to_owned(),
            ));
        }
        Ok(())
    }

    /// This request in the worker's own vocabulary.
    fn to_worker(&self) -> serde_json::Value {
        let mut payload = serde_json::Map::new();
        payload.insert("template".into(), self.template.clone().into());

        let mut put = |key: &str, value: Option<serde_json::Value>| {
            if let Some(value) = value {
                payload.insert(key.to_owned(), value);
            }
        };
        put("lowercase_masking", self.lowercase_masking.map(Into::into));
        put("name", self.name.clone().map(Into::into));
        put("assay", self.assay.clone());
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("how_many", self.how_many.map(Into::into));
        put(
            "alignment_mode",
            self.alignment_mode.clone().map(Into::into),
        );
        put(
            "consensus_policy",
            self.consensus_policy.clone().map(Into::into),
        );
        put("panel_metadata", self.panel_metadata.clone());
        put(
            "formulation_mode",
            self.formulation_mode.clone().map(Into::into),
        );
        put(
            "formulation_total_concentration_nm",
            self.formulation_total_concentration_nm.map(Into::into),
        );
        put("nontarget", self.nontarget.clone().map(Into::into));
        put(
            "alternative_alignment",
            self.alternative_alignment.clone().map(Into::into),
        );
        put(
            "alignment_audit_backend",
            self.alignment_audit_backend.clone().map(Into::into),
        );
        put("workflow_evidence", self.workflow_evidence.clone());
        put("from_rna", self.from_rna.map(Into::into));
        put(
            "tails",
            self.tails.as_ref().map(|tails| {
                serde_json::json!({
                    "forward": tails.forward,
                    "reverse": tails.reverse,
                })
            }),
        );

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn engine() -> ConsensusPair {
        ConsensusPair::new()
    }

    #[test]
    fn one_sequence_is_refused_with_the_module_that_does_want_one() {
        let error = engine()
            .validate(&json!({ "template": ">only\nACGTACGT" }))
            .expect_err("a family needs more than one");
        assert!(error.to_string().contains("Standard PCR"));
    }

    #[test]
    fn two_sequences_are_accepted_at_this_level() {
        // Whether they are actually aligned is the worker's question; it can
        // count columns and this cannot.
        engine()
            .validate(&json!({ "template": ">a\nACGT\n>b\nACGT" }))
            .expect("two records is a family");
    }

    #[test]
    fn a_field_nobody_recognises_is_refused_rather_than_ignored() {
        let error = engine()
            .validate(&json!({ "template": ">a\nACGT\n>b\nACGT", "degenracy": 4 }))
            .expect_err("unknown field");
        assert!(error.to_string().contains("degenracy"));
    }

    #[test]
    fn asking_for_more_answers_than_the_ceiling_is_refused_here() {
        // `howMany` was forwarded unchecked; the worker would have answered
        // fifty and said nothing about the hundred asked for.
        let error = engine()
            .validate(&json!({ "template": ">a\nACGT\n>b\nACGT", "howMany": 51 }))
            .expect_err("more than the ceiling");
        assert!(error.to_string().contains("howMany"), "{error}");
    }

    #[test]
    fn a_paste_error_in_the_alignment_box_is_caught_before_a_process_starts() {
        let error = engine()
            .validate(&json!({ "template": "soheil@example.com" }))
            .expect_err("not an alignment");
        assert!(error.to_string().contains("does not look like"), "{error}");
    }

    #[test]
    fn this_engine_refuses_variant_masking() {
        // Degeneracy is how it tolerates variation. Masking the variants out
        // would remove exactly what it is built to cover.
        assert!(!engine().accepts().contains(&Modifier::VariantMasking));
        assert_eq!(engine().id(), EngineId::ConsensusPair);
    }
}
