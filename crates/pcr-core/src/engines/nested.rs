//! Two rounds, the second reading inside the first.
//!
//! A nested design is two pairs in one fixed relationship — the inner pair
//! strictly inside the outer one — and that relationship is what the request
//! has to be able to express. It needs two sets of constraints rather than one,
//! because the two rounds are not the same reaction: the outer product is what
//! a gel shows from round one and the inner is what people actually read.
//!
//! That is why it is its own engine rather than a modifier on `flanking-pair`.
//! One request, one answer, two pairs, and an ordering between them that no
//! amount of parameter-passing on a single-pair engine could express.
//!
//! Nothing scientific happens in this file. It checks the request and hands it
//! to the worker.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::common::{
    check_excluded, check_how_many, check_target_bounds, check_target_pair, check_template,
    excluded_to_worker,
};
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

include!("nested_authority.generated.rs");

/// Modifiers this engine will be combined with.
///
/// Not multiplex: two nested designs in one tube is four pairs whose second
/// round would amplify across each other's first products.
const ACCEPTS: &[Modifier] = &[Modifier::ReverseTranscription, Modifier::VariantMasking];

/// The longest template this will take in one request.
const MAX_TEMPLATE_BASES: usize = 1_000_000;

/// The most nested designs one request may ask for.
///
/// The same ceiling the pair engines apply to a `run`; naming it here too
/// means a request that asks past it is refused before a process is started.
const MAX_HOW_MANY: u8 = 50;

/// Which primer the second round may reuse from the first.
const SHARES: [&str; 3] = ["nothing", "forward", "reverse"];

/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct NestedRequest {
    /// The sequence to amplify from.
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
    /// First base the inner product must contain, zero-based.
    #[serde(default)]
    pub target_start: Option<usize>,
    /// How many bases from `target_start` the inner product must contain.
    #[serde(default)]
    pub target_length: Option<usize>,
    /// What the first round's pair must satisfy.
    #[serde(default)]
    pub outer: Option<serde_json::Value>,
    /// What the second round's pair must satisfy.
    #[serde(default)]
    pub inner: Option<serde_json::Value>,
    /// Which primer the second round reuses: nothing, forward, or reverse.
    #[serde(default)]
    pub shares: Option<String>,
    /// How far inside the outer primers the inner ones must sit.
    #[serde(default)]
    pub margin: Option<usize>,
    /// Whether both rounds happen in one tube.
    ///
    /// Generation-1 has no executable one-tube protocol. The field is retained
    /// as an explicit topology guard so unsupported direct/API requests fail
    /// closed instead of being approximated as the supported two-tube assay.
    #[serde(default)]
    pub single_tube: Option<bool>,
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
    /// How many nested designs to aim for.
    #[serde(default)]
    pub how_many: Option<u8>,
    /// Whether the tube starts from RNA rather than DNA.
    ///
    /// Eight assays declare the reverse-transcription modifier and none could
    /// say so, which made it a label rather than a setting. It puts a hold in
    /// front of the programme — a one-step RT-PCR whose first denaturation
    /// never happens amplifies nothing.
    #[serde(default)]
    pub from_rna: Option<bool>,
    /// Optional named carry-over prevention chemistry between rounds.
    ///
    /// This is intentionally not defaulted: dUTP/UNG is a protocol overlay,
    /// not an automatic property of every nested reaction.
    #[serde(default)]
    pub carryover_prevention: Option<String>,
    /// How Round 1 product reaches Round 2.
    #[serde(default)]
    pub transfer_mode: Option<String>,
    /// Exact named cleanup authority when the transfer mode uses one.
    #[serde(default)]
    pub cleanup_protocol: Option<String>,
    /// Physical volume of first-round material transferred, in microlitres.
    #[serde(default)]
    pub transfer_volume_ul: Option<f64>,
    /// Explicit dilution factor for diluted-transfer; must exceed one.
    #[serde(default)]
    pub transfer_dilution_factor: Option<f64>,
    /// Caller-validated SOP reference for custom transfer.
    #[serde(default)]
    pub custom_transfer_sop: Option<String>,
    /// Independent reaction identities for the two rounds.
    #[serde(default)]
    pub round1_polymerase: Option<String>,
    #[serde(default)]
    /// Polymerase identity for round two.
    pub round2_polymerase: Option<String>,
    #[serde(default)]
    /// Reaction conditions for round one.
    pub round1_conditions: Option<serde_json::Value>,
    #[serde(default)]
    /// Reaction conditions for round two.
    pub round2_conditions: Option<serde_json::Value>,
    #[serde(default)]
    /// Thermal program for round one.
    pub round1_thermal_program: Option<serde_json::Value>,
    #[serde(default)]
    /// Thermal program for round two.
    pub round2_thermal_program: Option<serde_json::Value>,
    /// Empirical round/transfer/contamination observations. They never change
    /// primer ranking in the original design request.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
    /// Stretches no primer of either round may overlap.
    ///
    /// Both rounds, deliberately: excluding a stretch from the inner pair only
    /// would leave the outer round free to sit on it, and the outer product is
    /// what the inner round then reads from.
    #[serde(default)]
    pub excluded: Option<Vec<(usize, usize)>>,
    /// Sequence these four oligos must not also find.
    ///
    /// This engine took none, and the gap was recorded rather than papered
    /// over: nesting is often *chosen* because the target is rare in a large
    /// background, which is exactly when a specificity check matters most. An
    /// outer pair with a second site gives the inner round a second template
    /// to work on, and the second round makes it plentiful.
    #[serde(default)]
    pub background: Option<String>,
}

/// A nested search, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct Nested {
    worker: Worker,
}

impl Nested {
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

impl Engine for Nested {
    fn id(&self) -> EngineId {
        EngineId::Nested
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
        self.worker.call("nested", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<NestedRequest> {
    let parsed: NestedRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

impl NestedRequest {
    /// Whether this request could describe a nested design at all.
    ///
    /// Every check is the shared one from [`super::common`], so a rule means
    /// the same thing on every engine that carries the field.
    fn check(&self) -> Result<()> {
        let template_bases = check_template(&self.template, MAX_TEMPLATE_BASES)?;
        let assay_id = self
            .assay
            .as_ref()
            .and_then(|assay| assay.get("id"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default();
        if self.single_tube == Some(true) {
            return Err(CoreError::InvalidRequest(
                "One-tube nested PCR is not an executable Generation-1 topology. Use the supported two-tube workflow; enabling a one-tube assay requires a separate named, sourced and versioned protocol contract.".to_owned(),
            ));
        }
        if assay_id == "nested-pcr" {
            if self.shares.is_none() {
                return Err(CoreError::InvalidRequest("nested-pcr requires explicit `shares`; use `nothing` for a fully nested second round rather than omitting the relationship.".to_owned()));
            }
            if self.margin.is_none() {
                return Err(CoreError::InvalidRequest("nested-pcr requires explicit `margin`; zero is valid but must be recorded rather than inferred from absence.".to_owned()));
            }
            match self.single_tube {
                Some(false) => {}
                Some(true) => return Err(CoreError::InvalidRequest(
                    "singleTube=true is not executable for nested-pcr; use the supported two-tube topology.".to_owned(),
                )),
                None => return Err(CoreError::InvalidRequest(
                    "nested-pcr requires explicit `singleTube=false` for the supported two-tube Gen-1 topology; omission is not topology evidence.".to_owned(),
                )),
            }
            if self.carryover_prevention.is_none() {
                return Err(CoreError::InvalidRequest(
                    "nested-pcr requires explicit `carryoverPrevention`; use `not-selected` when no carry-over strategy was chosen.".to_owned(),
                ));
            }
        }
        if let Some(shares) = &self.shares {
            if !SHARES.contains(&shares.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{shares}` is not something the second round can reuse. It \
                     reuses: {}.",
                    SHARES.join(", ")
                )));
            }
        }
        if let Some(selection) = &self.carryover_prevention {
            let canonical = if selection == "dUTP-UNG" {
                "dutp-ung-strategy-only"
            } else {
                selection.as_str()
            };
            if !NESTED_CARRYOVER_STRATEGIES.contains(&canonical) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{selection}` is not a supported carry-over strategy. Choose a generated authority ID: {}.",
                    NESTED_CARRYOVER_STRATEGIES.join(", ")
                )));
            }
        }
        let transfer = self.transfer_mode.as_deref().unwrap_or("direct-transfer");
        if !NESTED_TRANSFER_MODES.contains(&transfer) {
            return Err(CoreError::InvalidRequest(format!(
                "`{transfer}` is not a reviewed Round-1 to Round-2 transfer mode. Choose: {}.",
                NESTED_TRANSFER_MODES.join(", ")
            )));
        }
        let cleanup = self.cleanup_protocol.as_deref().unwrap_or("not-selected");
        if !NESTED_CLEANUP_PROTOCOLS.contains(&cleanup) {
            return Err(CoreError::InvalidRequest(format!(
                "`{cleanup}` is not a reviewed nested cleanup protocol. Choose: {}.",
                NESTED_CLEANUP_PROTOCOLS.join(", ")
            )));
        }
        let implied_cleanup = match transfer {
            "msz-exonuclease-i" => Some("neb-msz-exonuclease-i"),
            "thermolabile-exonuclease-i" => Some("neb-thermolabile-exonuclease-i"),
            _ => None,
        };
        if let Some(expected) = implied_cleanup {
            if cleanup != "not-selected" && cleanup != expected {
                return Err(CoreError::InvalidRequest(format!(
                    "Transfer mode `{transfer}` requires cleanup protocol `{expected}`; another Exonuclease I authority is not substituted."
                )));
            }
        } else if cleanup != "not-selected" {
            return Err(CoreError::InvalidRequest(
                "A named Exonuclease I cleanup protocol requires its matching cleanup transfer mode.".to_owned(),
            ));
        }
        if transfer == "diluted-transfer" {
            match self.transfer_dilution_factor {
                Some(value) if value > 1.0 => {}
                _ => {
                    return Err(CoreError::InvalidRequest(
                        "diluted-transfer requires `transferDilutionFactor` > 1.".to_owned(),
                    ))
                }
            }
        }
        if matches!(self.transfer_volume_ul, Some(value) if value <= 0.0) {
            return Err(CoreError::InvalidRequest(
                "`transferVolumeUl` must be positive when supplied.".to_owned(),
            ));
        }
        if transfer == "custom-sop"
            && self
                .custom_transfer_sop
                .as_deref()
                .unwrap_or("")
                .trim()
                .is_empty()
        {
            return Err(CoreError::InvalidRequest(
                "custom-sop transfer requires a non-empty `customTransferSop` provenance reference.".to_owned(),
            ));
        }
        check_target_pair(self.target_start, self.target_length)?;
        if let Some((start, length)) = self.target_start.zip(self.target_length) {
            check_target_bounds(start, length, template_bases)?;
        }
        if let Some(regions) = &self.excluded {
            check_excluded(regions, template_bases)?;
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
        put("lowercase_masking", self.lowercase_masking.map(Into::into));
        put("name", self.name.clone().map(Into::into));
        put("assay", self.assay.clone());
        put("target_start", self.target_start.map(Into::into));
        put("target_length", self.target_length.map(Into::into));
        put("outer", self.outer.clone());
        put("inner", self.inner.clone());
        put("shares", self.shares.clone().map(Into::into));
        put("margin", self.margin.map(Into::into));
        put("single_tube", self.single_tube.map(Into::into));
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("how_many", self.how_many.map(Into::into));
        put("from_rna", self.from_rna.map(Into::into));
        let carryover = self.carryover_prevention.clone().map(|value| {
            if value == "dUTP-UNG" {
                "dutp-ung-strategy-only".to_owned()
            } else {
                value
            }
        });
        put("carryover_prevention", carryover.map(Into::into));
        put("transfer_mode", self.transfer_mode.clone().map(Into::into));
        put(
            "cleanup_protocol",
            self.cleanup_protocol.clone().map(Into::into),
        );
        put(
            "transfer_volume_ul",
            self.transfer_volume_ul.map(Into::into),
        );
        put(
            "transfer_dilution_factor",
            self.transfer_dilution_factor.map(Into::into),
        );
        put(
            "custom_transfer_sop",
            self.custom_transfer_sop.clone().map(Into::into),
        );
        put(
            "round1_polymerase",
            self.round1_polymerase.clone().map(Into::into),
        );
        put(
            "round2_polymerase",
            self.round2_polymerase.clone().map(Into::into),
        );
        put("round1_conditions", self.round1_conditions.clone());
        put("round2_conditions", self.round2_conditions.clone());
        put(
            "round1_thermal_program",
            self.round1_thermal_program.clone(),
        );
        put(
            "round2_thermal_program",
            self.round2_thermal_program.clone(),
        );
        put("workflow_evidence", self.workflow_evidence.clone());
        put("background", self.background.clone().map(Into::into));
        put("excluded", excluded_to_worker(self.excluded.as_ref()));

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_two_rounds_reach_the_worker_as_two_sets_of_constraints() {
        // The point of the engine: the rounds are not the same reaction, so a
        // single set of constraints could not describe both.
        let parsed = parse(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "outer": { "product_min": 800 },
            "inner": { "product_min": 300 },
            "shares": "forward",
            "margin": 25,
        }))
        .expect("a well-formed request");

        let payload = parsed.to_worker();
        assert_eq!(payload["outer"]["product_min"], 800);
        assert_eq!(payload["inner"]["product_min"], 300);
        assert_eq!(payload["shares"], "forward");
        assert_eq!(payload["margin"], 25);
    }

    #[test]
    fn sharing_something_that_is_not_a_primer_is_refused_with_the_list() {
        let error = parse(&json!({ "template": "ACGTACGT", "shares": "middle" }))
            .expect_err("there is no middle primer");
        let message = error.to_string();
        assert!(
            message.contains("middle") && message.contains("forward"),
            "{message}"
        );
    }

    #[test]
    fn half_a_target_is_refused_rather_than_ignored() {
        let error =
            parse(&json!({ "template": "ACGTACGT", "targetStart": 4 })).expect_err("half a target");
        assert!(error.to_string().contains("without a length"));
    }

    #[test]
    fn a_target_past_the_end_is_refused_rather_than_silently_clipped() {
        let error = parse(&json!({
            "template": "ACGTACGTAC",
            "targetStart": 4,
            "targetLength": 40,
        }))
        .expect_err("this protects nothing");
        assert!(error.to_string().contains("past the end"), "{error}");
    }

    #[test]
    fn an_avoided_region_past_the_end_is_refused() {
        let error = parse(&json!({
            "template": "ACGTACGTAC",
            "excluded": [[8, 40]],
        }))
        .expect_err("this protects nothing");
        assert!(error.to_string().contains("past the end"), "{error}");
    }

    #[test]
    fn avoided_regions_reach_the_worker_in_its_own_vocabulary() {
        let parsed = parse(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "excluded": [[4, 6]],
        }))
        .expect("a well-formed request");
        assert_eq!(parsed.to_worker()["excluded"], json!([[4, 6]]));
    }

    #[test]
    fn asking_for_more_designs_than_this_returns_is_refused_before_a_process_starts() {
        // The pair engines range-check `howMany`; this one did not, so the
        // same request was refused on one page and answered on another.
        let error = parse(&json!({ "template": "ACGTACGT", "howMany": 51 }))
            .expect_err("more than the ceiling");
        assert!(error.to_string().contains("up to 50"), "{error}");
    }

    #[test]
    fn an_unknown_carryover_prevention_selection_is_refused() {
        let error = parse(&json!({
            "template": "ACGTACGT",
            "carryoverPrevention": "guess"
        }))
        .expect_err("protocol overlays must be named");
        assert!(
            error.to_string().contains("supported carry-over strategy"),
            "{error}"
        );
    }
}
