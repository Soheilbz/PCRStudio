//! Primers that read outward from an intact known anchor into unknown flanks.
//!
//! CURRENT executes two explicit two-flank topologies: restriction digest + intramolecular
//! self-ligation, or an externally prepared supplied circular template. The submitted sequence is the complete
//! known anchor. The named restriction enzyme must have no recognition site in
//! that anchor; the digest sites that bound the recoverable fragment lie in the
//! unknown flanking DNA. After self-ligation one circle contains the intact
//! anchor, both flanks and the restriction-fragment ligation junction.
//!
//! This is its own engine because outward geometry changes what Primer3's
//! product span means. Primer3 can measure only the path through known sequence;
//! the final amplicon also traverses unknown flank sequence. A final product
//! length is therefore reported only when the complete self-ligated restriction
//! fragment length is supplied.
//!
//! Preparation identity is explicit rather than inferred: enzyme, branch, end
//! phosphate state, circularization provenance, linear-control provenance and
//! methylation branch travel with the design. This file validates that current
//! contract before handing it to the worker.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::common::{check_how_many, check_template};
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

include!("inverse_authority.generated.rs");

/// Modifiers this engine will be combined with.
///
/// Optional 5′ additions remain a profile capability; multiplex is excluded
/// because multiple outward pairs can create ambiguous cross-products across
/// circularized flank templates.
const ACCEPTS: &[Modifier] = &[Modifier::Tails, Modifier::VariantMasking];

/// The longest known region this will take in one request.
const MAX_KNOWN_BASES: usize = 1_000_000;

/// The most pairs one request may ask for.
///
/// The same ceiling the worker itself applies to a `run`; naming it here too
/// means a request that asks for two hundred is refused before a process is
/// started rather than answered with fifty by the far end.
const MAX_HOW_MANY: u8 = 50;

/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct OutwardPairRequest {
    /// The region the caller already knows, in any shape the worker resolves.
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
    /// Restriction enzyme used to generate the fragment. It must have zero
    /// recognition sites in the complete known anchor for the current branch.
    #[serde(default)]
    pub enzyme: Option<String>,
    /// The whole self-ligated circle, when it is known.
    ///
    /// Usually it is not, which is why it is optional and why no amplicon
    /// length is reported without it.
    #[serde(default)]
    pub circle_length: Option<usize>,
    /// Named preparation branch. It is experimental provenance, not inferred from a cut site.
    #[serde(default)]
    pub inverse_branch: Option<String>,
    /// Phosphate state of the two ligated digest ends; `unresolved` is explicit.
    #[serde(default)]
    pub left_end_phosphate: Option<String>,
    /// Phosphate state of the right ligated digest end; `unresolved` is explicit.
    #[serde(default)]
    pub right_end_phosphate: Option<String>,
    /// How circularization was established or prepared.
    #[serde(default)]
    pub circularization_provenance: Option<String>,
    /// Linear-control provenance. Absence must not be interpreted as a passed control.
    #[serde(default)]
    pub linear_control_provenance: Option<String>,
    /// Restriction/methylation compatibility branch retained as provenance.
    #[serde(default)]
    pub methylation_branch: Option<String>,
    /// Optional bounds on unknown flank when circle length is not known.
    #[serde(default)]
    pub unknown_flank_min: Option<usize>,
    /// Upper bound on the unknown flank, when the experiment provides one.
    #[serde(default)]
    pub unknown_flank_max: Option<usize>,
    /// Number of backup restriction enzymes to expose as a diagnostic cohort.
    #[serde(default)]
    pub enzyme_cohort_size: Option<u8>,
    /// Complete reference sequence for exact restriction-fragment topology.
    #[serde(default)]
    pub inverse_reference_sequence: Option<String>,
    /// Whether the complete reference molecule is circular.
    #[serde(default)]
    pub inverse_reference_circular: Option<bool>,
    /// Explicit caller-ordered enzyme cohort for exact full-reference feasibility.
    #[serde(default)]
    pub inverse_candidate_enzymes: Option<Vec<String>>,
    /// Workflow semantics only; does not change the outward-primer geometry.
    #[serde(default)]
    pub mapping_use_case: Option<String>,
    /// Empirical digest/circularization/PCR/sequencing evidence.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// What the product is for, which sets the sizes and the tolerances.
    ///
    /// Read by the same shared preamble every engine's worker uses, so an
    /// engine that did not accept it would refuse a request the worker was
    /// perfectly able to answer.
    #[serde(default)]
    pub purpose: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// What a pair has to satisfy.
    ///
    /// `product_min` and `product_max` here bound the span of *known* sequence
    /// left between the primers, not the amplicon.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// How many distinct pairs to aim for.
    #[serde(default)]
    pub how_many: Option<u8>,
    /// Sequence these oligos must not also find.
    ///
    /// The page asked for it and the engine had nowhere to put it, so a pasted
    /// genome was dropped on the way in and the result said nothing about it —
    /// which reads exactly like a design that came back clean.
    #[serde(default)]
    pub background: Option<String>,
}

/// An outward search, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct OutwardPair {
    worker: Worker,
}

impl OutwardPair {
    /// An engine that will call whatever `PCR_PYTHON` names.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Bind this engine to an explicit scientific execution port.
    #[must_use]
    pub fn with_worker(worker: Worker) -> Self {
        Self { worker }
    }
}

impl Engine for OutwardPair {
    fn id(&self) -> EngineId {
        EngineId::OutwardPair
    }

    fn accepts(&self) -> &'static [Modifier] {
        ACCEPTS
    }

    fn presets(&self) -> Result<Option<serde_json::Value>> {
        self.worker.call("presets", &json!({})).map(Some)
    }

    fn validate(&self, request: &serde_json::Value) -> Result<()> {
        parse(request).map(|_| ())
    }

    fn design(&self, request: serde_json::Value) -> Result<serde_json::Value> {
        let parsed = parse(&request)?;
        self.worker.call("inverse", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<OutwardPairRequest> {
    let parsed: OutwardPairRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

impl OutwardPairRequest {
    /// Whether this request could describe an inverse PCR at all.
    ///
    /// The template check is the shared one from [`super::common`], measured
    /// against this endpoint's own ceiling for the known region.
    fn check(&self) -> Result<()> {
        check_template(&self.template, MAX_KNOWN_BASES)?;
        let assay_id = self
            .assay
            .as_ref()
            .and_then(|assay| assay.get("id"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default();
        let named_enzyme = self
            .enzyme
            .as_deref()
            .is_some_and(|name| !name.trim().is_empty());
        let branch = self.inverse_branch.as_deref().unwrap_or("unresolved");
        if !INVERSE_BRANCHES.contains(&branch) || branch == "one-sided-internal-cut-reference" {
            return Err(CoreError::InvalidRequest(
                "inverse-pcr executes `restriction-self-ligation` and `supplied-circular-template`; one-sided/internal-cut strategies remain reference-only.".to_owned(),
            ));
        }
        if branch == "restriction-self-ligation" && !named_enzyme {
            return Err(CoreError::InvalidRequest(
                "restriction-self-ligation requires an explicit restriction-enzyme identity."
                    .to_owned(),
            ));
        }
        if branch == "supplied-circular-template" {
            if named_enzyme {
                return Err(CoreError::InvalidRequest(
                    "supplied-circular-template does not accept an enzyme; PCRStudio does not reinterpret an external digest.".to_owned(),
                ));
            }
            if self.circle_length.is_none() {
                return Err(CoreError::InvalidRequest(
                    "supplied-circular-template requires circleLength.".to_owned(),
                ));
            }
        }
        if assay_id == "inverse-pcr" {
            if self
                .circularization_provenance
                .as_deref()
                .is_none_or(|value| value.trim().is_empty())
            {
                return Err(CoreError::InvalidRequest(
                    "inverse-pcr requires circularizationProvenance for every executable branch."
                        .to_owned(),
                ));
            }
            if branch == "restriction-self-ligation" {
                for (label, value) in [
                    ("leftEndPhosphate", self.left_end_phosphate.as_deref()),
                    ("rightEndPhosphate", self.right_end_phosphate.as_deref()),
                    (
                        "linearControlProvenance",
                        self.linear_control_provenance.as_deref(),
                    ),
                    ("methylationBranch", self.methylation_branch.as_deref()),
                ] {
                    if value.is_none_or(|state| state.trim().is_empty()) {
                        return Err(CoreError::InvalidRequest(format!(
                            "restriction-self-ligation requires explicit `{label}`; use `unresolved` when evidence is unknown."
                        )));
                    }
                }
            }
        }
        for (label, state) in [
            ("leftEndPhosphate", self.left_end_phosphate.as_deref()),
            ("rightEndPhosphate", self.right_end_phosphate.as_deref()),
        ] {
            if let Some(state) = state {
                if !matches!(state, "phosphorylated" | "unphosphorylated" | "unresolved") {
                    return Err(CoreError::InvalidRequest(format!(
                        "{label} must be phosphorylated, unphosphorylated, or unresolved"
                    )));
                }
            }
        }
        if let (Some(low), Some(high)) = (self.unknown_flank_min, self.unknown_flank_max) {
            if low > high {
                return Err(CoreError::InvalidRequest(format!(
                    "unknownFlankMin ({low}) is above unknownFlankMax ({high})"
                )));
            }
        }
        if let Some(size) = self.enzyme_cohort_size {
            if !(1..=10).contains(&size) {
                return Err(CoreError::InvalidRequest(
                    "enzymeCohortSize must be 1..=10".to_owned(),
                ));
            }
        }
        if let Some(reference) = self.inverse_reference_sequence.as_deref() {
            check_template(reference, 5_000_000)?;
            if branch != "restriction-self-ligation" {
                return Err(CoreError::InvalidRequest(
                    "inverseReferenceSequence is only valid for restriction-self-ligation."
                        .to_owned(),
                ));
            }
        }
        if self.inverse_reference_circular.is_some() && self.inverse_reference_sequence.is_none() {
            return Err(CoreError::InvalidRequest(
                "inverseReferenceCircular requires inverseReferenceSequence.".to_owned(),
            ));
        }
        if let Some(names) = &self.inverse_candidate_enzymes {
            if self.inverse_reference_sequence.is_none() {
                return Err(CoreError::InvalidRequest(
                    "inverseCandidateEnzymes requires inverseReferenceSequence so feasibility is measured on the complete reference.".to_owned(),
                ));
            }
            if names.is_empty() || names.len() > 32 {
                return Err(CoreError::InvalidRequest(
                    "inverseCandidateEnzymes must contain 1..=32 explicit enzyme identities."
                        .to_owned(),
                ));
            }
            if names
                .iter()
                .any(|name| name.trim().is_empty() || name.len() > 64)
            {
                return Err(CoreError::InvalidRequest(
                    "inverseCandidateEnzymes contains an empty or unreasonably long enzyme identity.".to_owned(),
                ));
            }
        }
        if let Some(use_case) = self.mapping_use_case.as_deref() {
            if !matches!(
                use_case,
                "generic-flank" | "transposon-insertion" | "integration-site"
            ) {
                return Err(CoreError::InvalidRequest(
                    "mappingUseCase must be generic-flank, transposon-insertion, or integration-site".to_owned(),
                ));
            }
        }
        if let Some(how_many) = self.how_many {
            check_how_many(how_many, MAX_HOW_MANY)?;
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
        put("enzyme", self.enzyme.clone().map(Into::into));
        put("lowercase_masking", self.lowercase_masking.map(Into::into));
        put("name", self.name.clone().map(Into::into));
        put("assay", self.assay.clone());
        put("circle_length", self.circle_length.map(Into::into));
        put(
            "inverse_branch",
            self.inverse_branch.clone().map(Into::into),
        );
        put(
            "left_end_phosphate",
            self.left_end_phosphate.clone().map(Into::into),
        );
        put(
            "right_end_phosphate",
            self.right_end_phosphate.clone().map(Into::into),
        );
        put(
            "circularization_provenance",
            self.circularization_provenance.clone().map(Into::into),
        );
        put(
            "linear_control_provenance",
            self.linear_control_provenance.clone().map(Into::into),
        );
        put(
            "methylation_branch",
            self.methylation_branch.clone().map(Into::into),
        );
        put("unknown_flank_min", self.unknown_flank_min.map(Into::into));
        put("unknown_flank_max", self.unknown_flank_max.map(Into::into));
        put(
            "enzyme_cohort_size",
            self.enzyme_cohort_size.map(Into::into),
        );
        put(
            "inverse_reference_sequence",
            self.inverse_reference_sequence.clone().map(Into::into),
        );
        put(
            "inverse_reference_circular",
            self.inverse_reference_circular.map(Into::into),
        );
        put(
            "inverse_candidate_enzymes",
            self.inverse_candidate_enzymes
                .clone()
                .map(|v| serde_json::to_value(v).expect("enzyme cohort serializes")),
        );
        put(
            "mapping_use_case",
            self.mapping_use_case.clone().map(Into::into),
        );
        put("workflow_evidence", self.workflow_evidence.clone());
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("how_many", self.how_many.map(Into::into));
        put("background", self.background.clone().map(Into::into));

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(value: serde_json::Value) -> Result<OutwardPairRequest> {
        parse(&value)
    }

    #[test]
    fn a_design_without_an_enzyme_is_refused_rather_than_defaulted() {
        let error = request(json!({
            "template": "ACGTACGTACGTACGTACGT",
            "inverseBranch": "restriction-self-ligation",
        }))
        .expect_err("digest identity cannot be inferred");
        assert!(error.to_string().contains("restriction-enzyme"), "{error}");
    }

    #[test]
    fn the_named_enzyme_reaches_the_worker_under_its_own_name() {
        let parsed = request(json!({
            "template": "ACGTACGTACGTACGTACGT",
            "enzyme": "HindIII",
            "inverseBranch": "restriction-self-ligation",
            "circleLength": 4000
        }))
        .expect("a well-formed low-level request");
        let payload = parsed.to_worker();
        assert_eq!(payload["enzyme"], "HindIII");
        assert_eq!(payload["circle_length"], 4000);
        assert!(payload.get("cut_at").is_none());
        assert!(payload.get("side").is_none());
    }

    #[test]
    fn removed_split_anchor_fields_are_unknown_not_hidden_transport() {
        for (field, value) in [("cutAt", json!(8)), ("side", json!("downstream"))] {
            let mut body = json!({
                "template": "ACGTACGTACGTACGTACGT",
                "enzyme": "HindIII"
            });
            body.as_object_mut()
                .unwrap()
                .insert(field.to_owned(), value);
            let error = request(body).expect_err("removed current-surface field");
            assert!(error.to_string().contains("unknown field"), "{error}");
            assert!(error.to_string().contains(field), "{error}");
        }
    }

    #[test]
    fn the_named_inverse_profile_requires_current_preparation_provenance() {
        let body = json!({
            "template": "ACGTACGTACGTACGTACGT",
            "assay": {"id": "inverse-pcr"},
            "enzyme": "HindIII",
            "inverseBranch": "restriction-self-ligation",
            "leftEndPhosphate": "unresolved",
            "rightEndPhosphate": "unresolved",
            "circularizationProvenance": "unresolved",
            "linearControlProvenance": "unresolved",
            "methylationBranch": "unresolved"
        });
        request(body).expect("all current branch identity/provenance is explicit");
    }

    #[test]
    fn noncurrent_branch_is_refused() {
        let error = request(json!({
            "template": "ACGTACGTACGTACGTACGT",
            "enzyme": "HindIII",
            "inverseBranch": "supplied-circular-template"
        }))
        .expect_err("current engine has one executable topology");
        assert!(
            error.to_string().contains("does not accept an enzyme"),
            "{error}"
        );
    }

    #[test]
    fn asking_for_more_pairs_than_the_ceiling_is_refused_before_a_process_starts() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "enzyme": "HindIII",
            "inverseBranch": "restriction-self-ligation",
            "howMany": 51
        }))
        .expect_err("more than the ceiling");
        assert!(error.to_string().contains("howMany"), "{error}");
    }

    #[test]
    fn unknown_flank_bounds_cannot_be_reversed() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "enzyme": "HindIII",
            "inverseBranch": "restriction-self-ligation",
            "unknownFlankMin": 500,
            "unknownFlankMax": 100
        }))
        .expect_err("reversed interval");
        assert!(error.to_string().contains("unknownFlankMin"), "{error}");
    }
}
