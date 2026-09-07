//! Overlapping amplicons covering something too long for one reaction.
//!
//! A whole viral genome, or a gene nobody can amplify in one piece, is
//! sequenced by tiling it: a series of amplicons that overlap their neighbours,
//! so every base is covered and the pieces can be put back together.
//!
//! Two things about the request are unlike every other engine here.
//!
//! There is no target. Every other engine is given a region and asked to
//! amplify across it; this one is given a length and asked to cover all of it,
//! which turns the search into a walk rather than a search. A `targetStart`
//! here would be meaningless, so the field does not exist.
//!
//! And the answer is not a list of pairs but a set of pools. Pool assignment
//! is part of the scheme-level multiplex design and is owned by the selected
//! PRIMARY tiling algorithm. Alternating pools are common in ARTIC-style
//! workflows, but PCRStudio must not turn that convention into a universal
//! requirement when the pinned PrimalScheme3 CLI permits other pool counts.
//!
//! Nothing scientific happens in this file. It checks the request and hands it
//! to the worker.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::common::{check_excluded, check_template, excluded_to_worker};
include!("tiling_authority.generated.rs");
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

/// Modifiers this engine will be combined with.
///
/// Gen-1 deliberately exposes no 5-prime-tail modifier here. PrimalScheme3
/// assigns pools and audits interactions on the annealing primers it designs;
/// adding adapters/barcodes afterwards changes the ordered molecules without
/// re-running the PRIMARY pool assignment on those modified oligos. Until a
/// tail-aware pooling/revalidation branch is qualified, Scientific-Strict
/// fails closed rather than presenting the original pools as unchanged.
///
/// Multiplex is also not a modifier: a tiled scheme is already a multiplex
/// design and its pool assignment is part of the PRIMARY scheme output.
const ACCEPTS: &[Modifier] = &[];

/// The longest template this will take in one request.
///
/// Large enough for any viral genome and for a bacterial chromosome, which is
/// the size at which tiling is still something a person does by hand.
const MAX_TEMPLATE_BASES: usize = 10_000_000;

/// A 5' addition used by engines whose current contract explicitly supports
/// downstream oligo tails. Kept here as a small shared transport type for the
/// consensus-pair engine; tiled-scheme itself no longer carries this field.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct FivePrimeTails {
    /// What goes in front of every forward oligo.
    #[serde(default)]
    pub forward: Option<String>,
    /// What goes in front of every reverse oligo.
    #[serde(default)]
    pub reverse: Option<String>,
}
/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TilingSchemeRequest {
    /// What to cover, in any shape the worker resolves.
    pub template: String,
    /// Whether lowercase letters in the submitted template are intentional
    /// soft masking. None means the caller did not resolve the ambiguity; the
    /// Scientific-Strict worker refuses lowercase input in that case instead of
    /// guessing from how much of the sequence happens to be lowercase.
    #[serde(default)]
    pub lowercase_masking: Option<bool>,
    /// What to call the scheme.
    #[serde(default)]
    pub name: Option<String>,
    /// Which assay this is, and the numbers that assay differs by.
    #[serde(default)]
    pub assay: Option<serde_json::Value>,
    /// Explicit PRIMARY tiled-design backend. No backend substitution is silent.
    #[serde(default)]
    pub tiling_backend: Option<String>,
    /// Which PrimalScheme lifecycle operation this request performs.
    ///
    /// `scheme-create` is the ordinary design path.  The other modes are
    /// deliberately explicit because repairing or replacing an existing
    /// scheme is a different scientific action from generating a new one.
    #[serde(default)]
    pub tiling_operation: Option<String>,
    /// Alignment authority for multi-sequence input.
    /// `auto` runs the pinned MAFFT-first policy; `prealigned` preserves a reviewed MSA.
    #[serde(default)]
    pub tiling_alignment_mode: Option<String>,
    /// Minimum observed base/variant frequency passed to the selected backend.
    #[serde(default)]
    pub tiling_min_base_frequency: Option<f64>,
    /// PrimalScheme-specific backtracking switch.
    #[serde(default)]
    pub tiling_backtrack: Option<bool>,
    /// PrimalScheme-specific high-GC primer profile switch.
    #[serde(default)]
    pub tiling_high_gc: Option<bool>,
    /// Deterministic Olivar seed.
    #[serde(default)]
    pub olivar_seed: Option<i64>,
    /// Olivar degenerate-base mode.
    #[serde(default)]
    pub olivar_degenerate_mode: Option<bool>,
    /// Olivar variant-aware tiling check.
    #[serde(default)]
    pub olivar_check_variants: Option<bool>,
    /// Future/multi-target typed inputs. Multi-reference output must be lossless before execution.
    #[serde(default)]
    pub tiling_targets: Option<serde_json::Value>,
    /// Scheme lifecycle/version identity; provenance only and never a primer-ranking weight.
    #[serde(default)]
    pub scheme_version: Option<String>,
    /// Circular reference topology, executable for PrimalScheme3 scheme-create only.
    #[serde(default)]
    pub circular: Option<bool>,
    /// Observed amplicon-depth TSV evidence.
    #[serde(default)]
    pub tiling_depth_tsv: Option<String>,
    /// Explicit observed-depth threshold used only for dropout evidence.
    #[serde(default)]
    pub tiling_dropout_threshold: Option<f64>,
    /// Measured run/dropout evidence; never mutates the primary design ranking.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
    /// Existing ARTIC/PrimalScheme primer BED content for lifecycle operations.
    #[serde(default)]
    pub existing_bed: Option<String>,
    /// PrimalScheme config.json content that belongs to the imported scheme.
    #[serde(default)]
    pub scheme_config: Option<String>,
    /// Optional region BED used by `panel-create`.
    #[serde(default)]
    pub region_bed: Option<String>,
    /// Panel-create mode.
    #[serde(default)]
    pub panel_mode: Option<String>,
    /// Primer-pair stem/name to replace in `scheme-replace`.
    #[serde(default)]
    pub primer_name: Option<String>,
    /// How much each amplicon must share with its neighbour.
    #[serde(default)]
    pub overlap: Option<usize>,
    /// How many tubes to split the scheme across.
    #[serde(default)]
    pub pools: Option<u32>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// What the product is for, which sets the sizes and the tolerances.
    #[serde(default)]
    pub purpose: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// What each pair has to satisfy.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// Stretches no tiled primer may overlap, each a zero-based start and length.
    ///
    /// The Python walker applies these against each local search window while
    /// preserving the coordinates in the whole-template contract.
    #[serde(default)]
    pub excluded: Option<Vec<(usize, usize)>>,
}

/// A tiling walk, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct TilingScheme {
    worker: Worker,
}

impl TilingScheme {
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

impl Engine for TilingScheme {
    fn id(&self) -> EngineId {
        EngineId::TilingScheme
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
        self.worker.call("tiling", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<TilingSchemeRequest> {
    let parsed: TilingSchemeRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

impl TilingSchemeRequest {
    /// Whether this request could describe a tiling scheme at all.
    ///
    /// The template and the avoided regions are the shared checks from
    /// [`super::common`], so a rule means the same thing on every engine
    /// that carries the field.
    fn check(&self) -> Result<()> {
        let template_bases = check_template(&self.template, MAX_TEMPLATE_BASES)?;
        if let Some(regions) = &self.excluded {
            check_excluded(regions, template_bases)?;
        }
        let assay_id = self
            .assay
            .as_ref()
            .and_then(|assay| assay.get("id"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default();
        let backend = if assay_id == "tiled-scheme" {
            self.tiling_backend
                .as_deref()
                .filter(|value| !value.is_empty())
                .ok_or_else(|| CoreError::InvalidRequest("tiled-scheme requires explicit `tilingBackend`: primalscheme3, olivar, or compare.".to_owned()))?
        } else {
            self.tiling_backend.as_deref().unwrap_or("primalscheme3")
        };
        if !matches!(
            backend,
            "primalscheme3" | "olivar" | "compare" | "internal-development"
        ) {
            return Err(CoreError::InvalidRequest(format!(
                "unknown tiling backend `{backend}`; use primalscheme3, olivar, or compare"
            )));
        }
        if backend == "internal-development" {
            return Err(CoreError::InvalidRequest(
                "internal-development is not a Scientific-Strict tiled-scheme PRIMARY backend."
                    .to_owned(),
            ));
        }
        if let Some(value) = self.tiling_min_base_frequency {
            if !(0.0..=1.0).contains(&value) {
                return Err(CoreError::InvalidRequest(
                    "tilingMinBaseFrequency must be between 0 and 1".to_owned(),
                ));
            }
        }
        if let Some(seed) = self.olivar_seed {
            if !(0..=2_147_483_647).contains(&seed) {
                return Err(CoreError::InvalidRequest(
                    "olivarSeed must be between 0 and 2147483647".to_owned(),
                ));
            }
        }
        if let Some(depth) = self.tiling_depth_tsv.as_deref() {
            const MAX_DEPTH_TSV_CHARS: usize = 5_000_000;
            if depth.len() > MAX_DEPTH_TSV_CHARS {
                return Err(CoreError::InvalidRequest(format!(
                    "tilingDepthTsv is too large for an interactive request ({} characters; limit {MAX_DEPTH_TSV_CHARS})",
                    depth.len()
                )));
            }
            if self.tiling_dropout_threshold.is_none() {
                return Err(CoreError::InvalidRequest(
                    "tilingDepthTsv requires explicit tilingDropoutThreshold; dropout is not inferred.".to_owned(),
                ));
            }
        } else if self.tiling_dropout_threshold.is_some() {
            return Err(CoreError::InvalidRequest(
                "tilingDropoutThreshold requires tilingDepthTsv.".to_owned(),
            ));
        }
        if let Some(threshold) = self.tiling_dropout_threshold {
            if !threshold.is_finite() || !(0.0..=1_000_000_000.0).contains(&threshold) {
                return Err(CoreError::InvalidRequest(
                    "tilingDropoutThreshold must be a finite value between 0 and 1,000,000,000."
                        .to_owned(),
                ));
            }
        }
        let operation = if assay_id == "tiled-scheme" {
            self.tiling_operation.as_deref().filter(|value| !value.is_empty()).ok_or_else(|| {
                CoreError::InvalidRequest("tiled-scheme requires explicit `tilingOperation`; lifecycle identity is not inferred from omission.".to_owned())
            })?
        } else {
            self.tiling_operation.as_deref().unwrap_or("scheme-create")
        };
        if !matches!(
            operation,
            "scheme-create" | "panel-create" | "repair-mode" | "scheme-replace"
        ) {
            return Err(CoreError::InvalidRequest(format!(
                "unknown tiling lifecycle operation `{operation}`; use scheme-create, panel-create, repair-mode or scheme-replace"
            )));
        }
        if self.circular == Some(true)
            && (backend != "primalscheme3" || operation != "scheme-create")
        {
            return Err(CoreError::InvalidRequest(
                "circular tiled-scheme is executable only for PrimalScheme3 scheme-create in the current upstream lifecycle.".to_owned(),
            ));
        }
        if assay_id == "tiled-scheme"
            && self
                .tiling_alignment_mode
                .as_deref()
                .filter(|value| !value.is_empty())
                .is_none()
        {
            return Err(CoreError::InvalidRequest(
                "tiled-scheme requires explicit `tilingAlignmentMode`: auto or prealigned; alignment authority is part of the scientific input.".to_owned(),
            ));
        }
        if let Some(alignment_mode) = self.tiling_alignment_mode.as_deref() {
            if !matches!(alignment_mode, "auto" | "prealigned") {
                return Err(CoreError::InvalidRequest(format!(
                    "unknown tiling alignment mode `{alignment_mode}`; use auto or prealigned"
                )));
            }
        }
        if let Some(mode) = self.panel_mode.as_deref() {
            if !matches!(mode, "region-only" | "entropy" | "equal") {
                return Err(CoreError::InvalidRequest(format!(
                    "unknown panel mode `{mode}`; use region-only, entropy or equal"
                )));
            }
        }
        const MAX_BED_CHARS: usize = 5_000_000;
        const MAX_CONFIG_CHARS: usize = 1_000_000;
        for (label, value, ceiling) in [
            ("existingBed", self.existing_bed.as_deref(), MAX_BED_CHARS),
            ("regionBed", self.region_bed.as_deref(), MAX_BED_CHARS),
            (
                "schemeConfig",
                self.scheme_config.as_deref(),
                MAX_CONFIG_CHARS,
            ),
        ] {
            if let Some(value) = value {
                if value.len() > ceiling {
                    return Err(CoreError::InvalidRequest(format!(
                        "`{label}` is too large for an interactive request ({} characters; limit {ceiling})",
                        value.len()
                    )));
                }
            }
        }
        if matches!(operation, "repair-mode" | "scheme-replace") {
            if self
                .existing_bed
                .as_deref()
                .is_none_or(|value| value.trim().is_empty())
            {
                return Err(CoreError::InvalidRequest(format!(
                    "{operation} requires the existing primer BED content"
                )));
            }
            if self
                .scheme_config
                .as_deref()
                .is_none_or(|value| value.trim().is_empty())
            {
                return Err(CoreError::InvalidRequest(format!(
                    "{operation} requires the original PrimalScheme config.json content"
                )));
            }
        }
        if operation == "scheme-replace"
            && self
                .primer_name
                .as_deref()
                .is_none_or(|value| value.trim().is_empty())
        {
            return Err(CoreError::InvalidRequest(
                "scheme-replace requires the primer-pair name/stem to replace".to_owned(),
            ));
        }
        if operation != "panel-create" && (self.region_bed.is_some() || self.panel_mode.is_some()) {
            return Err(CoreError::InvalidRequest(
                "regionBed/panelMode are only valid for panel-create; hidden lifecycle state must not alter another operation.".to_owned(),
            ));
        }
        if operation == "panel-create"
            && self
                .panel_mode
                .as_deref()
                .filter(|value| !value.is_empty())
                .is_none()
        {
            return Err(CoreError::InvalidRequest(
                "panel-create requires explicit `panelMode`: region-only, entropy, or equal."
                    .to_owned(),
            ));
        }
        if !matches!(operation, "repair-mode" | "scheme-replace") && self.scheme_config.is_some() {
            return Err(CoreError::InvalidRequest(
                "schemeConfig is only valid for repair-mode or scheme-replace.".to_owned(),
            ));
        }
        if operation == "scheme-create" && self.existing_bed.is_some() {
            return Err(CoreError::InvalidRequest(
                "existingBed is not a scheme-create input in PCRStudio's Gen-1 lifecycle contract; stale hidden state is refused rather than passed to PrimalScheme3.".to_owned(),
            ));
        }
        if operation != "scheme-replace" && self.primer_name.is_some() {
            return Err(CoreError::InvalidRequest(
                "primerName is only valid for scheme-replace.".to_owned(),
            ));
        }
        if matches!(backend, "olivar" | "compare") && operation != "scheme-create" {
            return Err(CoreError::InvalidRequest(format!(
                "tiling backend `{backend}` is qualified for scheme-create only; repair/replace lifecycle remains PrimalScheme3-specific"
            )));
        }
        if matches!(backend, "olivar" | "compare")
            && (self.region_bed.is_some() || self.panel_mode.is_some())
        {
            return Err(CoreError::InvalidRequest(
                "Olivar/compare does not consume PrimalScheme panel-create region inputs."
                    .to_owned(),
            ));
        }
        if backend == "olivar" && (self.overlap.is_some() || self.pools.is_some()) {
            return Err(CoreError::InvalidRequest(
                "overlap/pools are PrimalScheme lifecycle inputs and are not silently mapped to Olivar.".to_owned(),
            ));
        }
        match operation {
            "scheme-create" => {
                if matches!(backend, "primalscheme3" | "compare")
                    && (self.overlap.is_none() || self.pools.is_none())
                {
                    return Err(CoreError::InvalidRequest(
                        "scheme-create requires explicit `overlap` and `pools`; hidden tiling-geometry defaults are not allowed.".to_owned(),
                    ));
                }
            }
            "panel-create" => {
                if backend != "primalscheme3" {
                    return Err(CoreError::InvalidRequest("panel-create is PrimalScheme3-specific in the current qualified lifecycle.".to_owned()));
                }
                if self.overlap.is_some() {
                    return Err(CoreError::InvalidRequest(
                        "PrimalScheme3 panel-create has no executable overlap input; `overlap` is refused rather than ignored.".to_owned(),
                    ));
                }
                if self.pools.is_none() {
                    return Err(CoreError::InvalidRequest(
                        "panel-create requires explicit `pools`.".to_owned(),
                    ));
                }
            }
            "repair-mode" | "scheme-replace" => {
                if self.overlap.is_some() || self.pools.is_some() {
                    return Err(CoreError::InvalidRequest(format!(
                        "{operation} inherits geometry from its BED/config; overlap/pools are not executable inputs"
                    )));
                }
            }
            _ => {
                return Err(CoreError::InvalidRequest(format!(
                    "unsupported PrimalScheme3 operation `{operation}`"
                )))
            }
        }
        if let Some(pools) = self.pools {
            if pools < 1 {
                return Err(CoreError::InvalidRequest(
                    "PrimalScheme3 requires `n-pools` to be at least 1; PCRStudio does not impose an additional biological upper bound."
                        .to_owned(),
                ));
            }
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
        put("tilingBackend", self.tiling_backend.clone().map(Into::into));
        put(
            "tilingMinBaseFrequency",
            self.tiling_min_base_frequency.map(Into::into),
        );
        put("tilingBacktrack", self.tiling_backtrack.map(Into::into));
        put("tilingHighGc", self.tiling_high_gc.map(Into::into));
        put("olivarSeed", self.olivar_seed.map(Into::into));
        put(
            "olivarDegenerateMode",
            self.olivar_degenerate_mode.map(Into::into),
        );
        put(
            "olivarCheckVariants",
            self.olivar_check_variants.map(Into::into),
        );
        put("tilingTargets", self.tiling_targets.clone());
        put("schemeVersion", self.scheme_version.clone().map(Into::into));
        put("circular", self.circular.map(Into::into));
        put(
            "tilingDepthTsv",
            self.tiling_depth_tsv.clone().map(Into::into),
        );
        put(
            "tilingDropoutThreshold",
            self.tiling_dropout_threshold.map(Into::into),
        );
        put("workflowEvidence", self.workflow_evidence.clone());
        put(
            "tilingOperation",
            self.tiling_operation.clone().map(Into::into),
        );
        put(
            "tilingAlignmentMode",
            self.tiling_alignment_mode.clone().map(Into::into),
        );
        put("existingBed", self.existing_bed.clone().map(Into::into));
        put("schemeConfig", self.scheme_config.clone().map(Into::into));
        put("regionBed", self.region_bed.clone().map(Into::into));
        put("panelMode", self.panel_mode.clone().map(Into::into));
        put("primerName", self.primer_name.clone().map(Into::into));
        put("overlap", self.overlap.map(Into::into));
        put("pools", self.pools.map(Into::into));
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("excluded", excluded_to_worker(self.excluded.as_ref()));

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(value: serde_json::Value) -> Result<TilingSchemeRequest> {
        parse(&value)
    }

    #[test]
    fn a_single_pool_and_zero_min_overlap_are_valid_primary_tool_inputs() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "tilingOperation": "scheme-create",
            "overlap": 0,
            "pools": 1
        }))
        .expect("PrimalScheme3 3.3.0 accepts --min-overlap >= 0 and --n-pools >= 1");
        assert_eq!(parsed.overlap, Some(0));
        assert_eq!(parsed.pools, Some(1));
    }

    #[test]
    fn a_tiling_scheme_takes_no_target() {
        // There is no region to amplify across — the whole sequence is the
        // job. A `targetStart` would have nothing to mean, so `deny_unknown_
        // fields` refuses it rather than ignoring it.
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "targetStart": 10,
        }))
        .expect_err("a target on a scheme that covers everything");
        assert!(error.to_string().contains("targetStart"), "{error}");
    }

    #[test]
    fn a_tiling_scheme_is_not_offered_the_multiplex_modifier() {
        // It is already one. Offering the modifier would let somebody ask for
        // the pooling twice and get two different answers.
        assert!(!ACCEPTS.contains(&Modifier::Multiplex));
    }

    #[test]
    fn the_pooling_reaches_the_worker_under_its_own_name() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "pools": 3,
            "overlap": 100,
        }))
        .expect("a well-formed request");

        let payload = parsed.to_worker();
        assert_eq!(payload["pools"], 3);
        assert_eq!(payload["overlap"], 100);
    }

    #[test]
    fn an_avoided_region_past_the_end_is_refused_rather_than_silently_clipped() {
        // A scheme covers everything, so an exclusion is "cover this stretch
        // from outside it" — and one past the end protects nothing while
        // reading exactly like protecting something.
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "excluded": [[8, 40]],
        }))
        .expect_err("this protects nothing");
        assert!(error.to_string().contains("past the end"), "{error}");
    }

    #[test]
    fn avoided_regions_reach_the_worker_in_its_own_vocabulary() {
        let parsed = request(json!({
            "template": "ACGTACGTACGTACGTACGT",
            "excluded": [[4, 6]],
            "tilingOperation": "scheme-create",
            "overlap": 100,
            "pools": 2,
        }))
        .expect("a well-formed request");
        assert_eq!(parsed.to_worker()["excluded"], json!([[4, 6]]));
    }
}
