//! A pair, and a third oligo between them that reports.
//!
//! A hydrolysis-probe assay reads fluorescence rather than a band, so what it
//! measures is not "was there a product" but "was there *this* product". The
//! probe is what makes that difference: it binds inside the amplicon and only a
//! polymerase copying through that exact stretch releases its signal.
//!
//! Two things about the request are unlike every other engine here.
//!
//! The probe carries its own constraints, and they are not the primers' with
//! different numbers. The low-level geometry worker retains an unbound search
//! heuristic for engine research. Routed `qpcr-probe` execution is chemistry-bound:
//! reviewed conventional Thermo Fisher and IDT profiles execute directly. The MGB
//! branch is executable only as a content-bound external-authority round trip: PCRStudio
//! exports candidates and accepts ranked MGB-aware Tm results only for the same candidate set.
//!
//! And the enzyme is part of the design rather than a preference. The signal is
//! the polymerase chewing through the probe with its 5' exonuclease; an enzyme
//! without one amplifies perfectly and reports nothing, which on a plate reads
//! as absent template. The worker refuses that combination by name.
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

include!("probe_authority.generated.rs");

/// Modifiers this engine will be combined with.
///
/// Multiplex, because separate colours in one tube is the reason to use a probe
/// at all. Reverse transcription, because most probe assays read RNA. Variant
/// masking, because a SNP under a probe silences it completely rather than
/// merely weakening it — the probe either matches or it does not.
///
/// Not tails: a probe assay's oligos carry a fluorophore and a quencher, and
/// added sequence between them changes what the reporter does.
const ACCEPTS: &[Modifier] = &[
    Modifier::Multiplex,
    Modifier::ReverseTranscription,
    Modifier::VariantMasking,
];

/// The longest template this will take in one request.
const MAX_TEMPLATE_BASES: usize = 1_000_000;

/// The most assays one request may ask for.
const MOST_ASSAYS: u8 = 10;

/// Historical aliases are accepted only so saved legacy requests reopen.
/// Current protocol vocabulary is generated from the canonical authority.
const PROBE_PROTOCOL_ALIASES: &[(&str, &str)] = &[("taqman-mgb", "taqman-mgb-reference")];

/// Worker-facing probe-window keys. Nested JSON values are not affected by
/// serde's top-level `camelCase` rename, so this list makes the wire contract
/// explicit instead of letting a plausible `tmMin` spelling survive Rust and
/// fail only after the Python worker is spawned.
const PROBE_CONSTRAINT_KEYS: &[&str] = &[
    "length_min",
    "length_opt",
    "length_max",
    "tm_min",
    "tm_opt",
    "tm_max",
    "tm_pair_max_difference",
    "gc_min",
    "gc_max",
    "product_min",
    "product_max",
    "max_poly_x",
    "min_three_prime_distance",
    "gc_clamp",
    "max_end_gc",
    "max_end_stability",
];

/// One optical identity in an optional multiplex panel. The panel describes
/// other assays sharing the tube; without their oligo sequences PCRStudio can
/// validate optical/chemistry conflicts but deliberately cannot claim
/// cross-assay dimer validation.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProbeMultiplexTarget {
    /// Stable target/display identity within the panel.
    pub target: String,
    /// Reporter assigned to this target.
    pub reporter: String,
    /// Terminal quencher assigned to this target.
    pub quencher: String,
    /// Optional internal quencher for double-quenched chemistry.
    #[serde(default)]
    pub internal_quencher: Option<String>,
    /// Optional instrument channel identity. Duplicate explicit channels are refused.
    #[serde(default)]
    pub channel: Option<String>,
    /// Optional peer forward primer sequence for all-vs-all multiplex diagnostics.
    #[serde(default)]
    pub forward_primer: Option<String>,
    /// Optional peer reverse primer sequence.
    #[serde(default)]
    pub reverse_primer: Option<String>,
    /// Optional peer probe sequence.
    #[serde(default)]
    pub probe_sequence: Option<String>,
}

/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PairAndProbeRequest {
    /// The template, in any shape the worker resolves.
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
    /// Where the region to amplify begins, zero-based.
    #[serde(default)]
    pub target_start: Option<usize>,
    /// How long that region is.
    #[serde(default)]
    pub target_length: Option<usize>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// What the product is for, which sets the sizes and the tolerances.
    #[serde(default)]
    pub purpose: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// What the two primers have to satisfy.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// What the probe has to satisfy, which is not what the primers satisfy.
    ///
    /// Optional low-level geometry window. Routed Generation-1 qPCR-probe
    /// execution does not derive release authority from this field.
    #[serde(default)]
    pub probe: Option<serde_json::Value>,
    /// Named probe chemistry profile from the canonical qPCR-probe authority.
    #[serde(default)]
    pub probe_protocol: Option<String>,
    /// Explicit chemistry identity; when supplied it must agree with the selected profile.
    #[serde(default)]
    pub probe_chemistry: Option<String>,
    /// 5-prime reporter label, validated against the selected chemistry.
    #[serde(default)]
    pub probe_reporter: Option<String>,
    /// Terminal quencher label.
    #[serde(default)]
    pub probe_quencher: Option<String>,
    /// Optional internal quencher for reviewed double-quenched profiles.
    #[serde(default)]
    pub probe_internal_quencher: Option<String>,
    /// Instrument/optical profile identity; retained as provenance unless a named instrument authority resolves it.
    #[serde(default)]
    pub probe_instrument_profile: Option<String>,
    /// Versioned optical channel/reporter authority payload.
    #[serde(default)]
    pub probe_optical_authority_payload: Option<serde_json::Value>,
    /// MGB authority exchange mode: export-candidates or import-results.
    #[serde(default)]
    pub probe_mgb_authority_mode: Option<String>,
    /// External MGB-aware authority result payload.
    #[serde(default)]
    pub probe_mgb_authority_payload: Option<serde_json::Value>,
    /// Transcript-design mode (for example genomic-neutral, exon-spanning, or exon-junction).
    #[serde(default)]
    pub probe_transcript_mode: Option<String>,
    /// Explicit transcript junction boundaries in zero-based template coordinates.
    #[serde(default)]
    pub probe_transcript_junctions: Option<Vec<usize>>,
    /// Probe-only variant positions in zero-based template coordinates.
    #[serde(default)]
    pub probe_variant_positions: Option<Vec<usize>>,
    /// Typed multiplex optical panel. Optical identity is validated against the
    /// selected authority; when peer oligo sequences are supplied the worker also
    /// reports all-vs-all interaction evidence without inventing a universal cutoff.
    #[serde(default)]
    pub probe_multiplex_panel: Option<Vec<ProbeMultiplexTarget>>,
    /// Empirical validation/run evidence. Never mutates the design ranking.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
    /// How many distinct assays to aim for.
    #[serde(default)]
    pub how_many: Option<u8>,
    /// Whether the tube starts from RNA rather than DNA.
    ///
    /// Records that the starting molecule is RNA. The generic modifier does
    /// not invent one-step/two-step identity or an RT hold; exact RT conditions
    /// require a separately named RT-capable chemistry.
    #[serde(default)]
    pub from_rna: Option<bool>,
    /// Sequence these oligos must not also find.
    ///
    /// The page asked for it and the engine had nowhere to put it, so a pasted
    /// genome was dropped on the way in and the result said nothing about it —
    /// which reads exactly like a design that came back clean.
    #[serde(default)]
    pub background: Option<String>,
    /// Whether the template is a circle.
    ///
    /// A plasmid has no ends, but the string somebody pastes does, and a primer
    /// sitting across the join falls in the gap between them — so which primers
    /// the specificity scan can see depends on where the file happens to begin,
    /// which is arbitrary. Saying so makes the scan wrap.
    #[serde(default)]
    pub circular: Option<bool>,
    /// Stretches no primer may overlap, each a zero-based start and a length.
    ///
    /// A repeat, a stretch of poor sequence, a variant a primer must not sit
    /// on. Distinct from a target, which says where a primer must *reach*.
    ///
    /// The page has offered this box on every assay with a region picker since
    /// it was written, and three engines had nowhere to put the answer — so
    /// somebody could mark a repeat and be handed a primer sitting on it.
    #[serde(default)]
    pub excluded: Option<Vec<(usize, usize)>>,
}

/// A probe-assay search, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct PairAndProbe {
    worker: Worker,
}

impl PairAndProbe {
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

impl Engine for PairAndProbe {
    fn id(&self) -> EngineId {
        EngineId::PairAndProbe
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
        self.worker.call("probe", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<PairAndProbeRequest> {
    let parsed: PairAndProbeRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

fn canonical_probe_protocol(raw: &str) -> &str {
    PROBE_PROTOCOL_ALIASES
        .iter()
        .find_map(|(old, new)| (*old == raw).then_some(*new))
        .unwrap_or(raw)
}

fn probe_authority_record(protocol: &str) -> Result<serde_json::Value> {
    let authority: serde_json::Value =
        serde_json::from_str(PROBE_AUTHORITY_JSON).map_err(|error| {
            CoreError::ToolFailed(format!(
                "generated probe authority is invalid JSON: {error}"
            ))
        })?;
    authority["records"].get(protocol).cloned().ok_or_else(|| {
        CoreError::InvalidRequest(format!("unknown qPCR-probe protocol `{protocol}`"))
    })
}

impl PairAndProbeRequest {
    /// Whether this request could describe a probe assay at all.
    ///
    /// The template, the target, `howMany` and the avoided regions are the
    /// shared checks from [`super::common`], so a rule means the same thing
    /// on every engine that carries the field.
    fn check(&self) -> Result<()> {
        let template_bases = check_template(&self.template, MAX_TEMPLATE_BASES)?;
        // Both or neither. A start without a length is a point, and a probe
        // assay amplifies across a region.
        check_target_pair(self.target_start, self.target_length)?;
        if let Some((start, length)) = self.target_start.zip(self.target_length) {
            check_target_bounds(start, length, template_bases)?;
        }
        if let Some(wanted) = self.how_many {
            check_how_many(wanted, MOST_ASSAYS)?;
        }
        if let Some(regions) = &self.excluded {
            check_excluded(regions, template_bases)?;
        }
        let raw_protocol = self.probe_protocol.as_deref().unwrap_or("not-selected");
        if raw_protocol == "not-selected" {
            return Err(CoreError::InvalidRequest(
                "qPCR Probe requires a named reviewed chemistry. Conventional hydrolysis profiles execute directly; MGB executes only through the external-authority round-trip.".to_owned(),
            ));
        }
        let protocol = canonical_probe_protocol(raw_protocol);
        if !PROBE_PROBE_PROTOCOLS.contains(&protocol) {
            return Err(CoreError::InvalidRequest(format!(
                "protocol `{raw_protocol}` is not a reviewed qPCR-probe profile; current profiles: {}",
                PROBE_PROBE_PROTOCOLS.join(", ")
            )));
        }
        let authority = probe_authority_record(protocol)?;
        let execution_status = authority["execution_status"]
            .as_str()
            .unwrap_or("non-executable");
        let is_mgb = authority["chemistry"].as_str() == Some("mgb-nfq");
        match execution_status {
            "executable" => {
                if self.probe_mgb_authority_mode.is_some()
                    || self.probe_mgb_authority_payload.is_some()
                {
                    return Err(CoreError::InvalidRequest(
                        "probeMgbAuthorityMode/probeMgbAuthorityPayload are only valid for the reviewed MGB external-authority branch.".to_owned(),
                    ));
                }
            }
            "external-authority-required" if is_mgb => {
                let mode = self.probe_mgb_authority_mode.as_deref().unwrap_or("");
                if !matches!(mode, "export-candidates" | "import-results") {
                    return Err(CoreError::InvalidRequest(
                        "MGB qPCR requires probeMgbAuthorityMode=`export-candidates` or `import-results`; PCRStudio does not calculate MGB Tm internally.".to_owned(),
                    ));
                }
                if mode == "import-results" && self.probe_mgb_authority_payload.is_none() {
                    return Err(CoreError::InvalidRequest(
                        "probeMgbAuthorityMode=`import-results` requires probeMgbAuthorityPayload from the declared MGB-aware authority.".to_owned(),
                    ));
                }
                if mode == "export-candidates" && self.probe_mgb_authority_payload.is_some() {
                    return Err(CoreError::InvalidRequest(
                        "probeMgbAuthorityPayload is not accepted while exporting candidates; import it only with probeMgbAuthorityMode=`import-results`.".to_owned(),
                    ));
                }
            }
            _ => {
                return Err(CoreError::InvalidRequest(format!(
                    "qPCR-probe protocol `{protocol}` is {execution_status} and cannot execute; no chemistry-specific Tm correction is inferred."
                )));
            }
        }
        for (label, value, ceiling) in [
            (
                "probeOpticalAuthorityPayload",
                self.probe_optical_authority_payload.as_ref(),
                512_000usize,
            ),
            (
                "probeMgbAuthorityPayload",
                self.probe_mgb_authority_payload.as_ref(),
                1_000_000usize,
            ),
        ] {
            if let Some(value) = value {
                let size = serde_json::to_vec(value)
                    .map_err(|error| {
                        CoreError::InvalidRequest(format!(
                            "{label} is not serializable JSON: {error}"
                        ))
                    })?
                    .len();
                if size > ceiling {
                    return Err(CoreError::InvalidRequest(format!(
                        "{label} is too large for an interactive request ({size} bytes; limit {ceiling})"
                    )));
                }
            }
        }
        if let Some(junctions) = &self.probe_transcript_junctions {
            if junctions.len() > 10_000
                || junctions
                    .iter()
                    .any(|&position| position == 0 || position >= template_bases)
            {
                return Err(CoreError::InvalidRequest(
                    "probeTranscriptJunctions must contain at most 10,000 unique interior zero-based boundaries.".to_owned(),
                ));
            }
            let unique: std::collections::BTreeSet<_> = junctions.iter().copied().collect();
            if unique.len() != junctions.len() {
                return Err(CoreError::InvalidRequest(
                    "probeTranscriptJunctions must not contain duplicate boundaries.".to_owned(),
                ));
            }
        }
        if let Some(variants) = &self.probe_variant_positions {
            if variants.len() > 100_000
                || variants.iter().any(|&position| position >= template_bases)
            {
                return Err(CoreError::InvalidRequest(
                    "probeVariantPositions must contain at most 100,000 zero-based positions within the submitted template.".to_owned(),
                ));
            }
            let unique: std::collections::BTreeSet<_> = variants.iter().copied().collect();
            if unique.len() != variants.len() {
                return Err(CoreError::InvalidRequest(
                    "probeVariantPositions must not contain duplicate positions.".to_owned(),
                ));
            }
        }
        if let Some(chemistry) = self.probe_chemistry.as_deref() {
            if authority["chemistry"].as_str() != Some(chemistry) {
                return Err(CoreError::InvalidRequest(format!(
                    "probeChemistry `{chemistry}` does not match protocol `{protocol}` ({}).",
                    authority["chemistry"].as_str().unwrap_or("unspecified")
                )));
            }
        }
        for (label, value, field) in [
            (
                "reporter",
                self.probe_reporter.as_deref(),
                "reporter_options",
            ),
            (
                "quencher",
                self.probe_quencher.as_deref(),
                "quencher_options",
            ),
        ] {
            if let Some(value) = value {
                let ok = authority[field]
                    .as_array()
                    .is_some_and(|items| items.iter().any(|item| item.as_str() == Some(value)));
                if !ok {
                    return Err(CoreError::InvalidRequest(format!(
                        "{label} `{value}` is not reviewed for qPCR-probe protocol `{protocol}`"
                    )));
                }
            }
        }
        if self.probe_internal_quencher.is_some()
            && authority["chemistry"].as_str() != Some("double-quenched-hydrolysis")
        {
            return Err(CoreError::InvalidRequest(
                "probeInternalQuencher is only valid for a reviewed double-quenched hydrolysis profile.".to_owned(),
            ));
        }
        if let Some(panel) = &self.probe_multiplex_panel {
            if panel.is_empty() {
                return Err(CoreError::InvalidRequest(
                    "probeMultiplexPanel must contain at least one peer target when supplied."
                        .to_owned(),
                ));
            }
            if panel.len() > 11 {
                return Err(CoreError::InvalidRequest(
                    "probeMultiplexPanel may contain at most 11 peer targets (12 total including the current assay); this is a software/planning bound, not a wet-lab qualification claim.".to_owned(),
                ));
            }
            let mut targets = std::collections::BTreeSet::new();
            let mut reporters = std::collections::BTreeSet::new();
            let mut channels = std::collections::BTreeSet::new();
            for item in panel {
                let target = item.target.trim();
                if target.is_empty() || !targets.insert(target.to_owned()) {
                    return Err(CoreError::InvalidRequest(
                        "probeMultiplexPanel target identities must be non-empty and unique."
                            .to_owned(),
                    ));
                }
                if !authority["reporter_options"]
                    .as_array()
                    .is_some_and(|items| {
                        items
                            .iter()
                            .any(|entry| entry.as_str() == Some(item.reporter.as_str()))
                    })
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "multiplex reporter `{}` is not reviewed for qPCR-probe protocol `{protocol}`",
                        item.reporter
                    )));
                }
                if !authority["quencher_options"]
                    .as_array()
                    .is_some_and(|items| {
                        items
                            .iter()
                            .any(|entry| entry.as_str() == Some(item.quencher.as_str()))
                    })
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "multiplex quencher `{}` is not reviewed for qPCR-probe protocol `{protocol}`",
                        item.quencher
                    )));
                }
                if !reporters.insert(item.reporter.clone()) {
                    return Err(CoreError::InvalidRequest(format!(
                        "multiplex reporter `{}` is assigned to more than one target; one optical reporter cannot distinguish two targets in the same panel.",
                        item.reporter
                    )));
                }
                if let Some(channel) = item
                    .channel
                    .as_deref()
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                {
                    if !channels.insert(channel.to_owned()) {
                        return Err(CoreError::InvalidRequest(format!(
                            "multiplex optical channel `{channel}` is assigned to more than one target."
                        )));
                    }
                }
                for (label, sequence) in [
                    ("forwardPrimer", item.forward_primer.as_deref()),
                    ("reversePrimer", item.reverse_primer.as_deref()),
                    ("probeSequence", item.probe_sequence.as_deref()),
                ] {
                    if let Some(sequence) = sequence {
                        let sequence = sequence.trim();
                        if sequence.is_empty()
                            || sequence.len() > 200
                            || sequence.chars().any(|base| {
                                !matches!(base.to_ascii_uppercase(), 'A' | 'C' | 'G' | 'T')
                            })
                        {
                            return Err(CoreError::InvalidRequest(format!(
                                "probeMultiplexPanel {label} must be 1–200 unambiguous DNA bases when supplied."
                            )));
                        }
                    }
                }
                if item.internal_quencher.is_some()
                    && authority["chemistry"].as_str() != Some("double-quenched-hydrolysis")
                {
                    return Err(CoreError::InvalidRequest(
                        "multiplex internalQuencher is only valid for the reviewed double-quenched hydrolysis profile.".to_owned(),
                    ));
                }
            }
        }
        if let Some(probe) = &self.probe {
            let object = probe.as_object().ok_or_else(|| {
                CoreError::InvalidRequest(
                    "`probe` must be an object of numeric snake_case constraint fields".to_owned(),
                )
            })?;
            for (key, value) in object {
                if !PROBE_CONSTRAINT_KEYS.contains(&key.as_str()) {
                    return Err(CoreError::InvalidRequest(format!(
                        "unknown probe constraint `{key}`; nested probe keys use the worker's snake_case vocabulary (for example `tm_min`)"
                    )));
                }
                if !value.is_number() {
                    return Err(CoreError::InvalidRequest(format!(
                        "probe constraint `{key}` must be numeric"
                    )));
                }
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
        put("target_start", self.target_start.map(Into::into));
        put("target_length", self.target_length.map(Into::into));
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("probe", self.probe.clone());
        let protocol = self
            .probe_protocol
            .as_deref()
            .map(canonical_probe_protocol)
            .map(str::to_owned);
        put("probe_protocol", protocol.map(Into::into));
        put(
            "probe_chemistry",
            self.probe_chemistry.clone().map(Into::into),
        );
        put(
            "probe_reporter",
            self.probe_reporter.clone().map(Into::into),
        );
        put(
            "probe_quencher",
            self.probe_quencher.clone().map(Into::into),
        );
        put(
            "probe_internal_quencher",
            self.probe_internal_quencher.clone().map(Into::into),
        );
        put(
            "probe_instrument_profile",
            self.probe_instrument_profile.clone().map(Into::into),
        );
        put(
            "probe_optical_authority_payload",
            self.probe_optical_authority_payload.clone(),
        );
        put(
            "probe_mgb_authority_mode",
            self.probe_mgb_authority_mode.clone().map(Into::into),
        );
        put(
            "probe_mgb_authority_payload",
            self.probe_mgb_authority_payload.clone(),
        );
        put(
            "probe_transcript_mode",
            self.probe_transcript_mode.clone().map(Into::into),
        );
        put(
            "probe_transcript_junctions",
            self.probe_transcript_junctions
                .clone()
                .map(|v| serde_json::to_value(v).expect("junctions serialize")),
        );
        put(
            "probe_variant_positions",
            self.probe_variant_positions
                .clone()
                .map(|v| serde_json::to_value(v).expect("variants serialize")),
        );
        put(
            "probe_multiplex_panel",
            self.probe_multiplex_panel.clone().map(|value| {
                serde_json::to_value(value).expect("typed multiplex panel serializes")
            }),
        );
        put("workflow_evidence", self.workflow_evidence.clone());
        put("how_many", self.how_many.map(Into::into));
        put("from_rna", self.from_rna.map(Into::into));
        put("background", self.background.clone().map(Into::into));
        put("excluded", excluded_to_worker(self.excluded.as_ref()));
        put("circular", self.circular.map(Into::into));

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(value: serde_json::Value) -> Result<PairAndProbeRequest> {
        parse(&value)
    }

    fn decode(value: serde_json::Value) -> Result<PairAndProbeRequest> {
        serde_json::from_value(value).map_err(|error| CoreError::InvalidRequest(error.to_string()))
    }

    #[test]
    fn a_target_start_without_a_length_is_refused() {
        let error = request(json!({ "template": "ACGTACGTACGT", "targetStart": 10 }))
            .expect_err("half a target");
        assert!(error.to_string().contains("without a length"), "{error}");
    }

    #[test]
    fn the_probe_window_reaches_the_worker_under_its_own_name() {
        // Nested JSON is worker vocabulary, so unlike top-level Rust fields it
        // is snake_case all the way from the web form to Python.
        let parsed = decode(json!({
            "template": "ACGTACGTACGT",
            "probe": { "tm_min": 66.0 },
        }))
        .expect("a structurally well-formed request");

        assert_eq!(parsed.to_worker()["probe"]["tm_min"], 66.0);
    }

    #[test]
    fn a_camel_case_probe_constraint_is_not_worker_vocabulary() {
        let parsed = decode(json!({
            "template": "ACGTACGTACGT",
            "probe": { "tmMin": 66.0 },
        }))
        .expect("top-level request decoding is separate from nested worker vocabulary");
        let _object = parsed
            .probe
            .as_ref()
            .and_then(serde_json::Value::as_object)
            .expect("probe object");
        assert!(!PROBE_CONSTRAINT_KEYS.contains(&"tmMin"));
        assert!(PROBE_CONSTRAINT_KEYS.contains(&"tm_min"));
    }

    #[test]
    fn nothing_is_sent_that_was_not_asked_for() {
        // An absent probe window must stay absent rather than arriving as
        // null: the worker derives one from the primers, and a null would
        // read as "no window" instead.
        let parsed =
            decode(json!({ "template": "ACGTACGTACGT" })).expect("bare structural request");
        let payload = parsed.to_worker();
        assert!(payload.get("probe").is_none());
        assert!(payload.get("target_start").is_none());
    }

    #[test]
    fn asking_for_more_assays_than_this_returns_says_so() {
        let error = request(json!({ "template": "ACGTACGTACGT", "howMany": 50 }))
            .expect_err("more than the ceiling");
        assert!(error.to_string().contains("up to 10"), "{error}");
    }

    #[test]
    fn a_probe_assay_is_not_offered_tails() {
        // The oligos carry a fluorophore and a quencher; sequence added
        // between them changes what the reporter does.
        assert!(!ACCEPTS.contains(&Modifier::Tails));
    }

    #[test]
    fn an_avoided_region_past_the_end_is_refused_rather_than_silently_clipped() {
        // Somebody could mark a repeat and be handed a primer sitting on it;
        // a region that protects nothing is refused before a process starts.
        let error = request(json!({
            "template": "ACGTACGTAC",
            "excluded": [[8, 40]],
        }))
        .expect_err("this protects nothing");
        assert!(error.to_string().contains("past the end"), "{error}");
    }

    #[test]
    fn avoided_regions_reach_the_worker_in_its_own_vocabulary() {
        let parsed = decode(json!({
            "template": "ACGTACGTACGTACGTACGT",
            "excluded": [[4, 6]],
        }))
        .expect("a structurally well-formed request");
        assert_eq!(parsed.to_worker()["excluded"], json!([[4, 6]]));
    }

    #[test]
    fn an_unknown_probe_protocol_is_refused() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "probeProtocol": "guess",
        }))
        .expect_err("unknown probe protocol");
        assert!(
            error.to_string().contains("reviewed qPCR-probe profile"),
            "{error}"
        );
    }

    #[test]
    fn the_named_mgb_branch_requires_an_explicit_external_authority_mode() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "probeProtocol": "taqman-mgb",
        }))
        .expect_err("MGB execution without an authority exchange mode must fail closed");
        assert!(
            error.to_string().contains("probeMgbAuthorityMode"),
            "{error}"
        );
        assert!(error.to_string().contains("MGB"), "{error}");
    }

    #[test]
    fn the_named_mgb_branch_can_export_candidates_without_an_import_payload() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "probeProtocol": "taqman-mgb",
            "probeMgbAuthorityMode": "export-candidates",
        }))
        .expect("the reviewed MGB branch may export candidates to its declared authority");
        assert_eq!(
            parsed.to_worker()["probe_mgb_authority_mode"],
            json!("export-candidates")
        );
        assert!(parsed
            .to_worker()
            .get("probe_mgb_authority_payload")
            .is_none());
    }

    #[test]
    fn the_named_mgb_import_requires_an_authority_payload() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "probeProtocol": "taqman-mgb",
            "probeMgbAuthorityMode": "import-results",
        }))
        .expect_err("an MGB import without authority results must fail closed");
        assert!(
            error.to_string().contains("probeMgbAuthorityPayload"),
            "{error}"
        );
    }

    #[test]
    fn multiplex_optics_refuse_duplicate_reporters() {
        let error = request(json!({
            "template": "ACGTACGTACGTACGTACGTACGT",
            "probeProtocol": "thermofisher-taqman-conventional",
            "probeChemistry": "conventional-hydrolysis",
            "probeReporter": "FAM",
            "probeQuencher": "QSY",
            "probeMultiplexPanel": [
                {"target":"A","reporter":"FAM","quencher":"QSY","channel":"FAM"},
                {"target":"B","reporter":"FAM","quencher":"QSY","channel":"VIC"}
            ]
        }))
        .expect_err("duplicate reporter must be refused");
        assert!(
            error.to_string().contains("more than one target"),
            "{error}"
        );
    }

    #[test]
    fn multiplex_optics_refuse_unreviewed_reporters() {
        let error = request(json!({
            "template": "ACGTACGTACGTACGTACGTACGT",
            "probeProtocol": "thermofisher-taqman-conventional",
            "probeChemistry": "conventional-hydrolysis",
            "probeReporter": "FAM",
            "probeQuencher": "QSY",
            "probeMultiplexPanel": [
                {"target":"A","reporter":"NOT-A-REVIEWED-DYE","quencher":"QSY","channel":"x"}
            ]
        }))
        .expect_err("unreviewed reporter must be refused");
        assert!(error.to_string().contains("not reviewed"), "{error}");
    }

    #[test]
    fn absence_of_probe_chemistry_is_a_typed_generation_one_refusal() {
        let error = request(json!({ "template": "ACGTACGTACGT" }))
            .expect_err("there is no executable probe chemistry");
        assert!(
            error.to_string().contains("named reviewed chemistry"),
            "{error}"
        );
    }
}
