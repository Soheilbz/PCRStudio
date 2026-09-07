//! Four core oligos, with up to two optional loop primers, for amplification without a thermal cycler.
//!
//! LAMP holds one temperature. There is no melting step, so nothing separates
//! the strands for a primer to find — the reaction makes its own
//! single-stranded DNA by folding into loops, and the primers are what build
//! those loops.
//!
//! Two things about the request are unlike every other engine here.
//!
//! Conventional PCR product-size semantics do not transfer directly to LAMP.
//! The assay can be read by fluorescence, colour or turbidity depending on the
//! chemistry, and the relevant design geometry is whether the six core target
//! regions (plus optional loop-primer sites) can be placed in the required order.
//! The worker checks that geometry explicitly rather than pretending there is
//! one universal gel-band product-size rule.
//!
//! And the parameter set is chosen from the template rather than given. One
//! held temperature cannot serve every composition: an AT-rich target cannot
//! reach the ordinary melting window at any sensible length and a GC-rich one
//! overshoots it. The worker picks between three published sets by the
//! template's own GC content and says which one it used, because a design read
//! under a different set from the one it was made under has temperatures that
//! do not mean what they appear to.
//!
//! Nothing scientific happens in this file. It checks the request and hands it
//! to the worker.

use super::lamp_multiplex::{self, LampMultiplexTarget};
use serde::{Deserialize, Serialize};
use serde_json::json;

use super::common::{
    check_excluded, check_how_many, check_modified_oligos, check_template, excluded_to_worker,
};
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

/// Modifiers this engine will be combined with.
///
/// Reverse transcription, because most field LAMP assays read RNA. Variant
/// masking, because a set covers six required target regions plus up to two
/// optional loop-primer sites, and a polymorphism under any used site can cost
/// the reaction one of its ordered oligos.
///
/// Not multiplex: distinguishing two LAMP products in one tube means reading
/// two colours or two melt peaks, and the design question that raises is not
/// the one the multiplex modifier answers.
///
/// Not tails: two of the four core oligos already are composites, and their halves
/// are chosen by the geometry rather than by anything a caller adds.
const ACCEPTS: &[Modifier] = &[Modifier::ReverseTranscription, Modifier::VariantMasking];

/// The longest template this will take in one request.
///
/// A LAMP set spans a few hundred bases. The Python enumerator uses bounded,
/// spatially stratified half/join search plus indexed coordinate lookups, so a
/// large template remains an explicit bounded-search problem rather than an
/// unreported exhaustive/global-optimum claim.
const MAX_TEMPLATE_BASES: usize = 100_000;

/// The most sets one request may ask for.
const MOST_SETS: u8 = 10;

// Closed vocabularies and protocol compatibility are generated from
// contracts/chemistry/lamp-protocols.json. Keeping the include in this module
// makes Rust preflight consume the same authority as Python and Web.
include!("lamp_protocol_ids.generated.rs");

/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LoopSetRequest {
    /// The template, in any shape the worker resolves.
    pub template: String,
    /// Whether the submitted target is circular. Gen-1 LAMP refuses circular
    /// targets because a linearized representation can hide a six-region locus
    /// that crosses the coordinate origin.
    #[serde(default)]
    pub circular: Option<bool>,
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
    #[serde(default)]
    pub assay: Option<serde_json::Value>,
    /// Design a new LAMP set or validate one supplied explicitly by the caller.
    #[serde(default)]
    pub mode: Option<String>,
    /// Existing F3/B3/FIP/BIP (+ optional LF/LB) sequences for validation mode.
    #[serde(default)]
    pub existing_set: Option<serde_json::Value>,
    /// Optional explicit PrimerExplorer V5 parameter-set override.
    ///
    /// None means the source-backed V5 Automatic Judgment: whole-target GC
    /// selects AT-rich at <=45%, GC-rich at >=60%, otherwise Normal.
    #[serde(default)]
    pub parameter_set: Option<String>,
    /// Named kit-level concentration and incubation overlay.
    #[serde(default)]
    pub lamp_protocol: Option<String>,
    /// How amplification will be observed. This is provenance/compatibility
    /// metadata, not a sequence-ranking shortcut.
    #[serde(default)]
    pub lamp_readout: Option<String>,
    /// Exact readout chemistry, kept separate from the broad instrument/readout branch.
    #[serde(default)]
    pub lamp_readout_chemistry: Option<String>,
    #[serde(default)]
    /// Sample matrix identity.
    pub lamp_sample_matrix: Option<String>,
    #[serde(default)]
    /// Sample preparation identity.
    pub lamp_sample_preparation: Option<String>,
    #[serde(default)]
    /// LAMP formulation identity.
    pub lamp_formulation: Option<String>,
    #[serde(default)]
    /// Confirmation mode identity.
    pub lamp_confirmation_mode: Option<String>,
    #[serde(default)]
    /// Detection topology identity.
    pub lamp_detection_topology: Option<String>,
    /// Specialized modified-primer/probe peer-panel evidence; never mutates standard LAMP set ranking.
    #[serde(default)]
    pub lamp_multiplex_plan: Option<Vec<LampMultiplexTarget>>,
    #[serde(default)]
    /// Design-intent identity.
    pub lamp_design_intent: Option<String>,
    /// Integrated design, core-first selection, or loop-primer addition to a fixed core.
    #[serde(default)]
    pub lamp_design_stage: Option<String>,
    /// Exact F3/B3/FIP/BIP/LF/LB sequences used by fixed-primer anchoring.
    #[serde(default)]
    pub lamp_fixed_primers: Option<serde_json::Value>,
    /// Positional REF/ALT anchor for mutation-specific LAMP candidate filtering.
    #[serde(default)]
    pub lamp_variant: Option<serde_json::Value>,
    /// Shared manufacturing/readout annotations; provenance only unless a separately versioned topology executes them.
    #[serde(default)]
    pub modified_oligos: Option<serde_json::Value>,
    #[serde(default)]
    /// Loop-primer policy identity.
    pub lamp_loop_policy: Option<String>,
    /// Source-bounded numeric bench optimization. Provenance only; never sequence ranking.
    #[serde(default)]
    pub lamp_bench_optimization: Option<serde_json::Value>,
    /// Source-backed conditional numeric reaction context; all are chemistry/provenance only.
    #[serde(default)]
    pub lamp_carryover_strategy: Option<String>,
    #[serde(default)]
    /// Reconstitution multiplier.
    pub lamp_reconstitution_x: Option<String>,
    #[serde(default)]
    /// Specificity additive identity.
    pub lamp_specificity_additive: Option<String>,
    #[serde(default)]
    /// Acceleration additive identity.
    pub lamp_acceleration_additive: Option<String>,
    #[serde(default)]
    /// Primer kinetics profile identity.
    pub lamp_primer_kinetics_profile: Option<String>,
    #[serde(default)]
    /// Preincubation strategy identity.
    pub lamp_preincubation_strategy: Option<String>,
    #[serde(default)]
    /// Sample buffer identity.
    pub lamp_sample_buffer_type: Option<String>,
    #[serde(default)]
    /// Instrument profile identity.
    pub lamp_instrument_profile: Option<String>,
    #[serde(default)]
    /// Sample input percentage.
    pub lamp_sample_input_percent: Option<f64>,
    #[serde(default)]
    /// Sample buffer pH.
    pub lamp_sample_buffer_ph: Option<f64>,
    #[serde(default)]
    /// Sample buffer percentage.
    pub lamp_sample_buffer_percent: Option<f64>,
    #[serde(default)]
    /// Transport medium percentage.
    pub lamp_transport_medium_percent: Option<f64>,
    #[serde(default)]
    /// Bile salt concentration in milligrams per millilitre.
    pub lamp_bile_salt_mg_ml: Option<f64>,
    #[serde(default)]
    /// Cary-Blair medium percentage.
    pub lamp_cary_blair_percent: Option<f64>,
    #[serde(default)]
    /// Upstream guanidine concentration in millimolar.
    pub lamp_upstream_guanidine_mm: Option<f64>,
    /// Versioned LAMP geometry policy. The default preserves the reviewed
    /// PrimerExplorer V5 envelope; newer evidence profiles are explicit opt-in.
    #[serde(default)]
    pub lamp_geometry_profile: Option<String>,
    /// Optional synthetic junction between F1c/F2 and B1c/B2. `none` preserves
    /// compatibility; `tttt` is an explicit literature-backed research variant.
    #[serde(default)]
    pub lamp_inner_linker: Option<String>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// What the product is for, which sets the sizes and the tolerances.
    #[serde(default)]
    pub purpose: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// How many distinct sets to aim for.
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
    /// Sequence these oligos must not also find.
    ///
    /// The page asked for it and the engine had nowhere to put it, so a pasted
    /// genome was dropped on the way in and the result said nothing about it —
    /// which reads exactly like a design that came back clean.
    #[serde(default)]
    pub background: Option<String>,
    /// Optional homologous intended-target FASTA used for position-aware
    /// inclusivity ranking. This is deliberately separate from `background`:
    /// one asks what must still amplify; the other asks what must stay silent.
    /// The worker aligns this panel with the design template under the pinned
    /// MAFFT authority and fails closed if that authority is unavailable.
    #[serde(default)]
    pub inclusivity: Option<String>,
    /// Stretches none of the ordered oligos in the selected 4–6-primer set may overlap.
    ///
    /// Every used role, not only the ones a variant sits under. A loop set is read as
    /// turbidity or a colour change rather than as a band, so an oligo that
    /// fails on half the samples does not show up as a fainter signal — it
    /// shows up as a negative.
    #[serde(default)]
    pub excluded: Option<Vec<(usize, usize)>>,
    /// Adjustments to whichever parameter set is in force.
    ///
    /// The three published sets exist because the reaction is held at one
    /// temperature and a target's composition decides which window an oligo
    /// can reach. They are the right default and they are not the only
    /// geometry anybody runs — a target that is AT-rich in one half and
    /// GC-rich in the other fits none of them, and a kit with a different
    /// polymerase moves the whole band. Until this there was no way to say so:
    /// the only control was which of three.
    ///
    /// Loose on purpose. The worker owns which fields exist and what each is
    /// bounded by, and refuses anything else by name — duplicating that list
    /// here would be a second place for it to be wrong.
    #[serde(default)]
    pub windows: Option<serde_json::Value>,
    /// Assay-specific experimental validation evidence. Stored and returned for
    /// provenance only; it never participates in LAMP candidate ranking.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
}

/// A loop-mediated design, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct LoopSet {
    worker: Worker,
}

impl LoopSet {
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

impl Engine for LoopSet {
    fn id(&self) -> EngineId {
        EngineId::LoopSet
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
        self.worker.call("loop_set", &parsed.to_worker())
    }
}

fn lamp_bench_range(protocol: &str, key: &str) -> Option<(f64, f64)> {
    match (protocol, key) {
        ("neb-m9204" | "neb-m9205", "magnesium_mM") => Some((6.0, 8.0)),
        ("neb-m9204" | "neb-m9205", "polymerase_units") => Some((8.0, 15.0)),
        ("neb-m9204" | "neb-m9205", "hold_temperature_c") => Some((50.0, 70.0)),
        ("neb-m9204" | "neb-m9205", "fluorescent_dye_x") => Some((0.1, 1.0)),
        ("thermo-a56656", "polymerase_units") => Some((1.0, 6.0)),
        ("thermo-a56656", "hold_temperature_c") => Some((35.0, 75.0)),
        ("vazyme-rp711", "hold_temperature_c") => Some((60.0, 65.0)),
        ("vazyme-rp711", "hold_time_min") => Some((30.0, 60.0)),
        ("vazyme-rp711", "fluorescent_dye_x") => Some((0.1, 1.0)),
        _ => None,
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<LoopSetRequest> {
    let parsed: LoopSetRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

impl LoopSetRequest {
    /// Whether this request could describe a loop-mediated design at all.
    ///
    /// The template and the avoided regions are the shared checks from
    /// [`super::common`], so a rule means the same thing on every engine
    /// that carries the field.
    fn check(&self) -> Result<()> {
        let template_bases = check_template(&self.template, MAX_TEMPLATE_BASES)?;
        if self.circular == Some(true) {
            return Err(CoreError::InvalidRequest(
                "Gen-1 LAMP loop-set does not support circular target topology; linearizing a circular molecule can hide an origin-spanning six-region locus.".into(),
            ));
        }
        let mode = self.mode.as_deref().unwrap_or("design");
        if !matches!(mode, "design" | "validate-existing") {
            return Err(CoreError::InvalidRequest(
                "LAMP mode must be `design` or `validate-existing`.".to_owned(),
            ));
        }
        if mode == "validate-existing" {
            let set = self.existing_set.as_ref().and_then(serde_json::Value::as_object).ok_or_else(|| {
                CoreError::InvalidRequest(
                    "validate-existing LAMP mode requires `existingSet` with F3/B3/FIP/BIP sequences and F1c split lengths.".to_owned(),
                )
            })?;
            for key in ["f3", "b3", "fip", "bip", "fipF1cLength", "bipB1cLength"] {
                if !set.contains_key(key) {
                    return Err(CoreError::InvalidRequest(format!(
                        "validate-existing LAMP mode requires existingSet.{key}"
                    )));
                }
            }
        } else if self.existing_set.is_some() {
            return Err(CoreError::InvalidRequest(
                "existingSet is accepted only when LAMP mode=`validate-existing`.".to_owned(),
            ));
        }
        if let Some(named) = self.parameter_set.as_deref() {
            if !named.is_empty() && !PARAMETER_SETS.contains(&named) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{named}` is not a parameter set this knows. It knows: {}. When omitted, the worker selects one from the template's GC content.",
                    PARAMETER_SETS.join(", "),
                )));
            }
        }
        if let Some(protocol) = &self.lamp_protocol {
            if !LAMP_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "protocol {protocol} is not a LAMP protocol this knows. It knows: {}.",
                    LAMP_PROTOCOLS.join(", ")
                )));
            }
        }
        if let Some(wanted) = self.how_many {
            check_how_many(wanted, MOST_SETS)?;
        }
        if let Some(regions) = &self.excluded {
            check_excluded(regions, template_bases)?;
        }
        if let Some(readout) = self.lamp_readout.as_deref() {
            if !LAMP_READOUTS.contains(&readout) {
                return Err(CoreError::InvalidRequest(format!(
                    "lampReadout {readout} is not recognised. It knows: {}.",
                    LAMP_READOUTS.join(", ")
                )));
            }
        }
        for (label, value, allowed) in [
            (
                "lampReadoutChemistry",
                self.lamp_readout_chemistry.as_deref(),
                LAMP_READOUT_CHEMISTRIES,
            ),
            (
                "lampSampleMatrix",
                self.lamp_sample_matrix.as_deref(),
                LAMP_SAMPLE_MATRICES,
            ),
            (
                "lampSamplePreparation",
                self.lamp_sample_preparation.as_deref(),
                LAMP_SAMPLE_PREPARATIONS,
            ),
            (
                "lampFormulation",
                self.lamp_formulation.as_deref(),
                LAMP_FORMULATIONS,
            ),
            (
                "lampConfirmationMode",
                self.lamp_confirmation_mode.as_deref(),
                LAMP_CONFIRMATION_MODES,
            ),
            (
                "lampDetectionTopology",
                self.lamp_detection_topology.as_deref(),
                LAMP_DETECTION_TOPOLOGIES,
            ),
            (
                "lampDesignIntent",
                self.lamp_design_intent.as_deref(),
                LAMP_DESIGN_INTENTS,
            ),
            (
                "lampDesignStage",
                self.lamp_design_stage.as_deref(),
                LAMP_DESIGN_STAGES,
            ),
            (
                "lampLoopPolicy",
                self.lamp_loop_policy.as_deref(),
                LAMP_LOOP_POLICIES,
            ),
            (
                "lampCarryoverStrategy",
                self.lamp_carryover_strategy.as_deref(),
                LAMP_CARRYOVER_STRATEGIES,
            ),
            (
                "lampReconstitutionX",
                self.lamp_reconstitution_x.as_deref(),
                LAMP_RECONSTITUTION_OPTIONS,
            ),
            (
                "lampSpecificityAdditive",
                self.lamp_specificity_additive.as_deref(),
                LAMP_SPECIFICITY_ADDITIVES,
            ),
            (
                "lampAccelerationAdditive",
                self.lamp_acceleration_additive.as_deref(),
                LAMP_ACCELERATION_ADDITIVES,
            ),
            (
                "lampPrimerKineticsProfile",
                self.lamp_primer_kinetics_profile.as_deref(),
                LAMP_PRIMER_KINETICS_PROFILES,
            ),
            (
                "lampPreincubationStrategy",
                self.lamp_preincubation_strategy.as_deref(),
                LAMP_PREINCUBATION_STRATEGIES,
            ),
            (
                "lampSampleBufferType",
                self.lamp_sample_buffer_type.as_deref(),
                LAMP_SAMPLE_BUFFER_TYPES,
            ),
            (
                "lampInstrumentProfile",
                self.lamp_instrument_profile.as_deref(),
                LAMP_INSTRUMENT_PROFILES,
            ),
        ] {
            if let Some(value) = value {
                if !allowed.contains(&value) {
                    return Err(CoreError::InvalidRequest(format!(
                        "{label} `{value}` is not recognised. It knows: {}.",
                        allowed.join(", ")
                    )));
                }
            }
        }
        let topology = self
            .lamp_detection_topology
            .as_deref()
            .unwrap_or("nonspecific-dsdna");
        lamp_multiplex::validate(self.lamp_multiplex_plan.as_deref(), topology)?;
        if !["nonspecific-dsdna", "multiplex-modified-primer-probe"].contains(&topology) {
            return Err(CoreError::InvalidRequest("Gen-1 LAMP executes standard nonspecific-dsDNA design plus evidence-bound multiplex modified-primer/probe planning; other modified-probe/lateral-flow branches remain fail closed.".to_owned()));
        }
        if self.lamp_design_intent.as_deref() == Some("panel-conservation-aware")
            && self.inclusivity.as_deref().unwrap_or("").trim().is_empty()
        {
            return Err(CoreError::InvalidRequest(
                "panel-conservation-aware LAMP design requires an explicit inclusivity panel."
                    .to_owned(),
            ));
        }
        let intent = self.lamp_design_intent.as_deref().unwrap_or("standard");
        if intent == "fixed-primer-anchor" {
            let fixed = self
                .lamp_fixed_primers
                .as_ref()
                .and_then(serde_json::Value::as_object)
                .ok_or_else(|| {
                    CoreError::InvalidRequest(
                        "fixed-primer-anchor requires a non-empty lampFixedPrimers object."
                            .to_owned(),
                    )
                })?;
            if fixed.is_empty() {
                return Err(CoreError::InvalidRequest(
                    "lampFixedPrimers cannot be empty.".to_owned(),
                ));
            }
            for (role, value) in fixed {
                if !LAMP_FIXED_PRIMER_ROLES.contains(&role.as_str()) {
                    return Err(CoreError::InvalidRequest(format!(
                        "Unknown fixed LAMP primer role `{role}`."
                    )));
                }
                let sequence = value.as_str().unwrap_or("");
                if sequence.is_empty()
                    || !sequence
                        .chars()
                        .all(|base| matches!(base.to_ascii_uppercase(), 'A' | 'C' | 'G' | 'T'))
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "lampFixedPrimers.{role} must be an unambiguous DNA sequence."
                    )));
                }
            }
        } else if self.lamp_fixed_primers.is_some() {
            return Err(CoreError::InvalidRequest(
                "lampFixedPrimers is accepted only with lampDesignIntent=`fixed-primer-anchor`."
                    .to_owned(),
            ));
        }
        if intent == "mutation-anchored-specific" {
            let variant=self.lamp_variant.as_ref().and_then(serde_json::Value::as_object).ok_or_else(|| CoreError::InvalidRequest("mutation-anchored-specific requires lampVariant with position/ref/alt/anchor.".to_owned()))?;
            let anchor = variant
                .get("anchor")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("");
            if !LAMP_MUTATION_ANCHORS.contains(&anchor) {
                return Err(CoreError::InvalidRequest(format!(
                    "lampVariant.anchor is not recognised. It knows: {}.",
                    LAMP_MUTATION_ANCHORS.join(", ")
                )));
            }
            for allele in ["ref", "alt"] {
                let base = variant
                    .get(allele)
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("");
                if base.len() != 1
                    || !base
                        .chars()
                        .all(|c| matches!(c.to_ascii_uppercase(), 'A' | 'C' | 'G' | 'T'))
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "lampVariant.{allele} must be one A/C/G/T base."
                    )));
                }
            }
            if variant
                .get("position")
                .and_then(serde_json::Value::as_u64)
                .is_none()
            {
                return Err(CoreError::InvalidRequest(
                    "lampVariant.position must be a non-negative 0-based integer.".to_owned(),
                ));
            }
        } else if self.lamp_variant.is_some() {
            return Err(CoreError::InvalidRequest(
                "lampVariant is accepted only with lampDesignIntent=`mutation-anchored-specific`."
                    .to_owned(),
            ));
        }
        let stage = self.lamp_design_stage.as_deref().unwrap_or("integrated");
        if stage == "add-loops" {
            if intent != "fixed-primer-anchor" {
                return Err(CoreError::InvalidRequest(
                    "lampDesignStage=`add-loops` requires fixed-primer-anchor intent.".to_owned(),
                ));
            }
            let Some(fixed) = self
                .lamp_fixed_primers
                .as_ref()
                .and_then(serde_json::Value::as_object)
            else {
                return Err(CoreError::InvalidRequest(
                    "add-loops requires fixed core primers.".to_owned(),
                ));
            };
            for role in ["F3", "B3", "FIP", "BIP"] {
                if !fixed.contains_key(role) {
                    return Err(CoreError::InvalidRequest(format!(
                        "add-loops requires fixed core primer {role}."
                    )));
                }
            }
        }
        let protocol = self.lamp_protocol.as_deref().unwrap_or("not-selected");
        let from_rna = self.from_rna.unwrap_or(false);
        if from_rna && LAMP_DNA_ONLY_PROTOCOLS.contains(&protocol) {
            return Err(CoreError::InvalidRequest(format!(
                "LAMP protocol {protocol} is DNA-only under its reviewed authority."
            )));
        }
        if !from_rna && LAMP_RNA_ONLY_PROTOCOLS.contains(&protocol) {
            return Err(CoreError::InvalidRequest(format!(
                "LAMP protocol {protocol} is RNA-only under its reviewed RT-LAMP authority."
            )));
        }
        let readout = self.lamp_readout.as_deref().unwrap_or("not-specified");
        let chemistry = self
            .lamp_readout_chemistry
            .as_deref()
            .unwrap_or("not-specified");
        if LAMP_FORBIDDEN_READOUT_PAIRS.contains(&(protocol, readout)) {
            return Err(CoreError::InvalidRequest(
                "The selected named protocol excludes this readout under its reviewed authority."
                    .to_owned(),
            ));
        }
        if LAMP_FORBIDDEN_CHEMISTRY_PAIRS.contains(&(protocol, chemistry)) {
            let detail = if protocol == "neb-m1712" && chemistry == "hydroxynaphthol-blue" {
                "poor contrast with the selected M1712 mix"
            } else {
                "the selected named protocol excludes this readout chemistry under its reviewed authority"
            };
            return Err(CoreError::InvalidRequest(detail.to_owned()));
        }
        if let Some((_, branch)) = LAMP_READOUT_CHEMISTRY_BRANCHES
            .iter()
            .find(|(named, _)| *named == chemistry)
        {
            if readout != "not-specified" && readout != *branch {
                return Err(CoreError::InvalidRequest(format!(
                    "lampReadoutChemistry `{chemistry}` belongs to `{branch}`, not `{readout}`."
                )));
            }
        }
        let carryover = self
            .lamp_carryover_strategy
            .as_deref()
            .unwrap_or("protocol-default");
        if carryover != "protocol-default" && !matches!(protocol, "neb-m9204" | "neb-m9205") {
            return Err(CoreError::InvalidRequest(
                "The numeric dUTP/UDG overlay is reviewed only for M9204/M9205.".to_owned(),
            ));
        }
        let reconstitution = self
            .lamp_reconstitution_x
            .as_deref()
            .unwrap_or("protocol-default");
        if reconstitution != "protocol-default" && protocol != "neb-l4401" {
            return Err(CoreError::InvalidRequest(
                "Explicit 2X/4X reconstitution authority is reviewed only for L4401.".to_owned(),
            ));
        }
        if self.lamp_specificity_additive.as_deref().unwrap_or("none") != "none"
            && protocol != "neb-e1700"
        {
            return Err(CoreError::InvalidRequest(
                "Tte UvrD numeric authority is scoped to the reviewed E1700 example.".to_owned(),
            ));
        }
        if self.lamp_acceleration_additive.as_deref().unwrap_or("none") != "none"
            && (!matches!(protocol, "neb-m1800" | "neb-m1804") || readout != "colorimetric")
        {
            return Err(CoreError::InvalidRequest("40 mM guanidine acceleration is reviewed only for NEB M1800/M1804 colorimetric LAMP.".to_owned()));
        }
        if self
            .lamp_primer_kinetics_profile
            .as_deref()
            .unwrap_or("protocol-default")
            != "protocol-default"
            && !matches!(
                protocol,
                "optigene-iso001" | "optigene-iso001-rt" | "optigene-iso004" | "optigene-iso004-rt"
            )
        {
            return Err(CoreError::InvalidRequest(
                "OptiGene primer kinetics profiles are scoped to ISO-001/ISO-004 liquid branches."
                    .to_owned(),
            ));
        }
        if self
            .lamp_preincubation_strategy
            .as_deref()
            .unwrap_or("protocol-default")
            != "protocol-default"
            && protocol != "takara-rr385"
        {
            return Err(CoreError::InvalidRequest(
                "The 25C/10 min pre-incubation branch is specific to Takara RR385.".to_owned(),
            ));
        }
        if chemistry == "eiken-fd-lmp221" {
            if !matches!(protocol, "eiken-lmp204" | "eiken-lmp207" | "eiken-lmp244") {
                return Err(CoreError::InvalidRequest("Eiken LMP221 reagent is source-backed only for the reviewed Eiken kit branches.".to_owned()));
            }
            if matches!(
                self.lamp_sample_buffer_type.as_deref(),
                Some("te" | "chelating-other")
            ) {
                return Err(CoreError::InvalidRequest("Eiken LMP221 is incompatible with TE/chelating buffer context because Mn chelation can release calcein.".to_owned()));
            }
        }
        if self
            .lamp_instrument_profile
            .as_deref()
            .unwrap_or("not-specified")
            .starts_with("vazyme-")
            && protocol != "vazyme-rp711"
        {
            return Err(CoreError::InvalidRequest(
                "Vazyme instrument-conditioned dye values require RP711.".to_owned(),
            ));
        }
        if self.lamp_instrument_profile.as_deref() == Some("agdia-amplifire")
            && protocol != "agdia-lmx54700"
        {
            return Err(CoreError::InvalidRequest(
                "The AmpliFire numeric run profile is source-backed here only for Agdia LMX 54700."
                    .to_owned(),
            ));
        }
        let has_ph_context = self.lamp_sample_buffer_ph.is_some()
            || self.lamp_sample_buffer_percent.is_some()
            || self.lamp_upstream_guanidine_mm.is_some();
        if has_ph_context
            && (!matches!(protocol, "neb-m1800" | "neb-m1804") || readout != "colorimetric")
        {
            return Err(CoreError::InvalidRequest("Sample pH/buffer fraction and upstream guanidine numeric authority is scoped to NEB pH-colorimetric LAMP.".to_owned()));
        }
        let formulation = self.lamp_formulation.as_deref().unwrap_or("not-specified");
        if formulation != "not-specified" {
            if protocol == "not-selected" {
                return Err(CoreError::InvalidRequest(
                    "An explicit LAMP formulation requires a named reviewed protocol authority."
                        .to_owned(),
                ));
            }
            let permitted = LAMP_PROTOCOL_FORMULATION_PAIRS.contains(&(protocol, formulation));
            if !permitted {
                return Err(CoreError::InvalidRequest(format!("LAMP protocol {protocol} does not carry reviewed `{formulation}` formulation authority.")));
            }
        }
        let prep = self
            .lamp_sample_preparation
            .as_deref()
            .unwrap_or("not-specified");
        let matrix = self
            .lamp_sample_matrix
            .as_deref()
            .unwrap_or("not-specified");
        if matches!(prep, "direct-addition" | "koh-lyse-and-lamp") {
            if protocol == "not-selected" || matches!(matrix, "not-specified" | "crude-unspecified")
            {
                return Err(CoreError::InvalidRequest("Direct-sample LAMP requires a named reviewed protocol and explicit specimen matrix.".to_owned()));
            }
            if prep == "koh-lyse-and-lamp" && matrix != "koh-lysate" {
                return Err(CoreError::InvalidRequest(
                    "KOH Lyse & LAMP requires lampSampleMatrix=`koh-lysate`.".to_owned(),
                ));
            }
            let permitted = LAMP_DIRECT_SAMPLE_PAIRS.contains(&(protocol, matrix));
            if !permitted {
                return Err(CoreError::InvalidRequest(format!("LAMP protocol {protocol} does not carry reviewed direct-sample authority for matrix `{matrix}`.")));
            }
        }
        for (label, number) in [
            ("lampSampleInputPercent", self.lamp_sample_input_percent),
            ("lampSampleBufferPercent", self.lamp_sample_buffer_percent),
            (
                "lampTransportMediumPercent",
                self.lamp_transport_medium_percent,
            ),
            ("lampBileSaltMgMl", self.lamp_bile_salt_mg_ml),
            ("lampCaryBlairPercent", self.lamp_cary_blair_percent),
            ("lampUpstreamGuanidineMm", self.lamp_upstream_guanidine_mm),
        ] {
            if let Some(v) = number {
                if !v.is_finite() || v < 0.0 {
                    return Err(CoreError::InvalidRequest(format!(
                        "{label} must be non-negative and finite."
                    )));
                }
            }
        }
        if let Some(v) = self.lamp_transport_medium_percent {
            if !matches!(protocol, "meridian-mdx134" | "meridian-mdx135") || v > 50.0 {
                return Err(CoreError::InvalidRequest(
                    "Transport-medium percentage is reviewed only up to 50% for MDX134/MDX135."
                        .to_owned(),
                ));
            }
        }
        if let Some(v) = self.lamp_bile_salt_mg_ml {
            if protocol != "meridian-mdx144" || v > 2.0 {
                return Err(CoreError::InvalidRequest(
                    "Bile-salt authority is reviewed only for MDX144 up to 2 mg/mL.".to_owned(),
                ));
            }
        }
        if let Some(v) = self.lamp_cary_blair_percent {
            if protocol != "meridian-mdx144" || v > 40.0 {
                return Err(CoreError::InvalidRequest(
                    "Cary-Blair authority is reviewed only for MDX144 up to 40%.".to_owned(),
                ));
            }
        }
        if let Some(value) = &self.lamp_bench_optimization {
            let object = value.as_object().ok_or_else(|| {
                CoreError::InvalidRequest(
                    "lampBenchOptimization requires a named protocol JSON object.".to_owned(),
                )
            })?;
            if protocol == "not-selected" {
                return Err(CoreError::InvalidRequest(
                    "lampBenchOptimization requires a named protocol.".to_owned(),
                ));
            }
            for (key, raw) in object {
                let number = raw.as_f64().ok_or_else(|| {
                    CoreError::InvalidRequest(format!(
                        "lampBenchOptimization.{key} must be numeric."
                    ))
                })?;
                let range = lamp_bench_range(protocol, key).ok_or_else(|| CoreError::InvalidRequest(format!("Protocol {protocol} does not publish a reviewed optimization envelope for {key}.")))?;
                if number < range.0 || number > range.1 {
                    return Err(CoreError::InvalidRequest(format!("lampBenchOptimization.{key}={number} is outside reviewed {}–{} for {protocol}.", range.0, range.1)));
                }
            }
        }
        if let Some(value) = &self.modified_oligos {
            check_modified_oligos(value)?;
        }
        if let Some(profile) = self.lamp_geometry_profile.as_deref() {
            if !LAMP_GEOMETRY_PROFILES.contains(&profile) {
                return Err(CoreError::InvalidRequest(format!(
                    "lampGeometryProfile {profile} is not recognised. It knows: {}.",
                    LAMP_GEOMETRY_PROFILES.join(", ")
                )));
            }
        }
        if let Some(evidence) = &self.workflow_evidence {
            let object = evidence.as_object().ok_or_else(|| {
                CoreError::InvalidRequest(
                    "workflowEvidence must be a flat JSON object of scalar evidence values."
                        .to_owned(),
                )
            })?;
            if object.len() > 64 {
                return Err(CoreError::InvalidRequest(
                    "workflowEvidence may contain at most 64 fields.".to_owned(),
                ));
            }
            for (key, value) in object {
                if key.is_empty()
                    || key.len() > 80
                    || !(value.is_null()
                        || value.is_boolean()
                        || value.is_number()
                        || value.is_string())
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "workflowEvidence.{key} must be a scalar value with a key no longer than 80 characters."
                    )));
                }
                if value.as_str().is_some_and(|text| text.len() > 8_000) {
                    return Err(CoreError::InvalidRequest(format!(
                        "workflowEvidence.{key} exceeds the 8000-character evidence limit."
                    )));
                }
            }
        }
        if let Some(linker) = self.lamp_inner_linker.as_deref() {
            if !LAMP_INNER_LINKERS.contains(&linker) {
                return Err(CoreError::InvalidRequest(format!(
                    "lampInnerLinker {linker} is not recognised. It knows: {}.",
                    LAMP_INNER_LINKERS.join(", ")
                )));
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
        put("circular", self.circular.map(Into::into));
        put("lowercase_masking", self.lowercase_masking.map(Into::into));
        put("name", self.name.clone().map(Into::into));
        put("assay", self.assay.clone());
        put("mode", self.mode.clone().map(Into::into));
        put(
            "existing_set",
            self.existing_set.as_ref().map(|value| {
                let Some(source) = value.as_object() else {
                    return value.clone();
                };
                let mut block = serde_json::Map::new();
                for (wire, worker) in [
                    ("f3", "f3"),
                    ("b3", "b3"),
                    ("fip", "fip"),
                    ("bip", "bip"),
                    ("lf", "lf"),
                    ("lb", "lb"),
                    ("fipF1cLength", "fip_f1c_length"),
                    ("bipB1cLength", "bip_b1c_length"),
                ] {
                    if let Some(entry) = source.get(wire) {
                        block.insert(worker.to_owned(), entry.clone());
                    }
                }
                serde_json::Value::Object(block)
            }),
        );
        put("parameter_set", self.parameter_set.clone().map(Into::into));
        put("lamp_protocol", self.lamp_protocol.clone().map(Into::into));
        put("lamp_readout", self.lamp_readout.clone().map(Into::into));
        put(
            "lamp_readout_chemistry",
            self.lamp_readout_chemistry.clone().map(Into::into),
        );
        put(
            "lamp_sample_matrix",
            self.lamp_sample_matrix.clone().map(Into::into),
        );
        put(
            "lamp_sample_preparation",
            self.lamp_sample_preparation.clone().map(Into::into),
        );
        put(
            "lamp_formulation",
            self.lamp_formulation.clone().map(Into::into),
        );
        put(
            "lamp_confirmation_mode",
            self.lamp_confirmation_mode.clone().map(Into::into),
        );
        put(
            "lamp_detection_topology",
            self.lamp_detection_topology.clone().map(Into::into),
        );
        put(
            "lamp_multiplex_plan",
            self.lamp_multiplex_plan
                .as_ref()
                .and_then(|plan| serde_json::to_value(plan).ok()),
        );
        put(
            "lamp_design_intent",
            self.lamp_design_intent.clone().map(Into::into),
        );
        put(
            "lamp_design_stage",
            self.lamp_design_stage.clone().map(Into::into),
        );
        put("lamp_fixed_primers", self.lamp_fixed_primers.clone());
        put("lamp_variant", self.lamp_variant.clone());
        put("modified_oligos", self.modified_oligos.clone());
        put(
            "lamp_loop_policy",
            self.lamp_loop_policy.clone().map(Into::into),
        );
        put(
            "lamp_bench_optimization",
            self.lamp_bench_optimization.clone(),
        );
        put(
            "lamp_carryover_strategy",
            self.lamp_carryover_strategy.clone().map(Into::into),
        );
        put(
            "lamp_reconstitution_x",
            self.lamp_reconstitution_x.clone().map(Into::into),
        );
        put(
            "lamp_specificity_additive",
            self.lamp_specificity_additive.clone().map(Into::into),
        );
        put(
            "lamp_acceleration_additive",
            self.lamp_acceleration_additive.clone().map(Into::into),
        );
        put(
            "lamp_primer_kinetics_profile",
            self.lamp_primer_kinetics_profile.clone().map(Into::into),
        );
        put(
            "lamp_preincubation_strategy",
            self.lamp_preincubation_strategy.clone().map(Into::into),
        );
        put(
            "lamp_sample_buffer_type",
            self.lamp_sample_buffer_type.clone().map(Into::into),
        );
        put(
            "lamp_instrument_profile",
            self.lamp_instrument_profile.clone().map(Into::into),
        );
        put(
            "lamp_sample_input_percent",
            self.lamp_sample_input_percent.map(Into::into),
        );
        put(
            "lamp_sample_buffer_ph",
            self.lamp_sample_buffer_ph.map(Into::into),
        );
        put(
            "lamp_sample_buffer_percent",
            self.lamp_sample_buffer_percent.map(Into::into),
        );
        put(
            "lamp_transport_medium_percent",
            self.lamp_transport_medium_percent.map(Into::into),
        );
        put(
            "lamp_bile_salt_mg_ml",
            self.lamp_bile_salt_mg_ml.map(Into::into),
        );
        put(
            "lamp_cary_blair_percent",
            self.lamp_cary_blair_percent.map(Into::into),
        );
        put(
            "lamp_upstream_guanidine_mM",
            self.lamp_upstream_guanidine_mm.map(Into::into),
        );
        put(
            "lamp_geometry_profile",
            self.lamp_geometry_profile.clone().map(Into::into),
        );
        put(
            "lamp_inner_linker",
            self.lamp_inner_linker.clone().map(Into::into),
        );
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("how_many", self.how_many.map(Into::into));
        put("from_rna", self.from_rna.map(Into::into));
        put("background", self.background.clone().map(Into::into));
        put("inclusivity", self.inclusivity.clone().map(Into::into));
        put("windows", self.windows.clone());
        put("workflow_evidence", self.workflow_evidence.clone());
        put("excluded", excluded_to_worker(self.excluded.as_ref()));

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(value: serde_json::Value) -> Result<LoopSetRequest> {
        parse(&value)
    }

    #[test]
    fn a_circular_lamp_target_is_refused_before_worker_execution() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "circular": true,
        }))
        .expect_err("circular LAMP is unsupported in Gen-1");
        assert!(
            error.to_string().contains("circular target topology"),
            "{error}"
        );
    }

    #[test]
    fn an_explicit_linear_topology_reaches_the_worker() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "circular": false,
        }))
        .expect("linear LAMP target");
        assert_eq!(parsed.to_worker()["circular"], false);
    }

    #[test]
    fn a_parameter_set_this_does_not_know_lists_the_ones_it_does() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "parameterSet": "isothermal-ish",
        }))
        .expect_err("not a set");
        let message = error.to_string();
        for named in PARAMETER_SETS {
            assert!(message.contains(named), "{named} not offered: {message}");
        }
        assert!(
            message.contains("GC content"),
            "and says what happens if it is left out: {message}"
        );
    }

    #[test]
    fn the_parameter_set_is_not_sent_when_it_was_not_asked_for() {
        // The worker picks from the template's own composition, and a null
        // would read as a choice rather than as an absence.
        let parsed = request(json!({ "template": "ACGTACGTACGT" })).expect("bare request");
        assert!(parsed.to_worker().get("parameter_set").is_none());
    }

    #[test]
    fn an_unknown_lamp_protocol_is_refused() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "lampProtocol": "guess",
        }))
        .expect_err("kit protocols must be named");
        assert!(error.to_string().contains("LAMP protocol"), "{error}");
    }

    #[test]
    fn a_named_lamp_protocol_reaches_the_worker() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "lampProtocol": "neb-e1700",
        }))
        .expect("a named kit protocol");
        assert_eq!(parsed.to_worker()["lamp_protocol"], "neb-e1700");
    }

    #[test]
    fn a_current_bst_xt_and_cross_vendor_lamp_protocol_reach_the_worker() {
        for named in [
            "neb-m1712",
            "neb-l4401",
            "thermo-a5180x",
            "nippon-ne6041",
            "eiken-lmp207",
            "eiken-lmp247",
        ] {
            let parsed = request(json!({
                "template": "ACGTACGTACGT",
                "lampProtocol": named,
            }))
            .expect("reviewed named LAMP protocol");
            assert_eq!(parsed.to_worker()["lamp_protocol"], named);
        }
    }

    #[test]
    fn advanced_lamp_fields_reach_the_worker_without_cross_engine_aliases() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "lampGeometryProfile": "pcrstudio-evidence-2026",
            "lampInnerLinker": "tttt",
            "inclusivity": ">strain-a\nACGTACGTACGT",
        }))
        .expect("reviewed LAMP advanced fields");
        let payload = parsed.to_worker();
        assert_eq!(payload["lamp_geometry_profile"], "pcrstudio-evidence-2026");
        assert_eq!(payload["lamp_inner_linker"], "tttt");
        assert_eq!(payload["inclusivity"], ">strain-a\nACGTACGTACGT");
    }

    #[test]
    fn unknown_lamp_geometry_and_linker_are_refused_before_worker_execution() {
        let geometry = request(json!({
            "template": "ACGTACGTACGT",
            "lampGeometryProfile": "future-unreviewed",
        }))
        .expect_err("unknown geometry must fail closed");
        assert!(
            geometry.to_string().contains("lampGeometryProfile"),
            "{geometry}"
        );

        let linker = request(json!({
            "template": "ACGTACGTACGT",
            "lampInnerLinker": "poly-a",
        }))
        .expect_err("unknown linker must fail closed");
        assert!(linker.to_string().contains("lampInnerLinker"), "{linker}");
    }

    #[test]
    fn a_genome_sized_template_is_refused_with_the_reason() {
        let error = request(json!({ "template": "A".repeat(MAX_TEMPLATE_BASES + 1) }))
            .expect_err("too long");
        assert!(error.to_string().contains("region"), "{error}");
    }

    #[test]
    fn a_loop_set_takes_no_product_size() {
        // There is no band. The read-out is turbidity or a colour change, and
        // what the amplicon length constrains is whether the six core regions (plus optional loop sites) fit
        // at all — which the worker checks as arithmetic.
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "constraints": { "productMin": 200 },
        }))
        .expect_err("a product size on a reaction with no band");
        assert!(error.to_string().contains("constraints"), "{error}");
    }

    #[test]
    fn a_loop_set_is_not_offered_tails() {
        // Two of its four core oligos already are composites, and their halves are
        // chosen by the geometry rather than by anything a caller adds.
        assert!(!ACCEPTS.contains(&Modifier::Tails));
    }

    #[test]
    fn the_template_reaches_the_worker_and_nothing_else_does() {
        let parsed = request(json!({ "template": "ACGTACGTACGT", "howMany": 3 }))
            .expect("a well-formed request");
        let payload = parsed.to_worker();
        assert_eq!(payload["template"], "ACGTACGTACGT");
        assert_eq!(payload["how_many"], 3);
        assert!(payload.get("polymerase").is_none());
    }

    #[test]
    fn an_avoided_region_past_the_end_is_refused_rather_than_silently_clipped() {
        // A set covers six core regions plus optional loop sites; an exclusion past the end protected
        // nothing while reading exactly like protecting something.
        let error = request(json!({
            "template": "ACGTACGTAC",
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
        }))
        .expect("a well-formed request");
        assert_eq!(parsed.to_worker()["excluded"], json!([[4, 6]]));
    }

    #[test]
    fn r8_protocol_substrate_capabilities_fail_closed_before_worker_execution() {
        for protocol in [
            "optigene-iso004",
            "optigene-dr004",
            "optigene-iso004-lyo",
            "meridian-mdx118",
        ] {
            let error = request(json!({
                "template": "ACGTACGTACGT",
                "fromRna": true,
                "lampProtocol": protocol,
            }))
            .expect_err("DNA-only chemistry must reject RNA input");
            assert!(
                error.to_string().contains("DNA-only"),
                "{protocol}: {error}"
            );
        }

        let error = request(json!({
            "template": "ACGTACGTACGT",
            "fromRna": false,
            "lampProtocol": "eiken-lmp244",
        }))
        .expect_err("RNA-only chemistry must reject DNA input");
        assert!(error.to_string().contains("RNA-only"), "{error}");
    }

    #[test]
    fn r8_scenario_fields_reach_the_worker_in_worker_vocabulary() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "fromRna": false,
            "lampProtocol": "meridian-mdx126",
            "lampReadout": "fluorescence",
            "lampReadoutChemistry": "syto82",
            "lampSampleMatrix": "blood-plasma-serum",
            "lampSamplePreparation": "direct-addition",
            "lampFormulation": "air-dryable",
            "lampConfirmationMode": "sequence-confirmation",
            "lampDetectionTopology": "nonspecific-dsdna",
            "lampDesignIntent": "standard",
            "lampLoopPolicy": "require-six"
        }))
        .expect("reviewed legacy scenario");
        let payload = parsed.to_worker();
        assert_eq!(payload["lamp_protocol"], "meridian-mdx126");
        assert_eq!(payload["lamp_readout_chemistry"], "syto82");
        assert_eq!(payload["lamp_sample_matrix"], "blood-plasma-serum");
        assert_eq!(payload["lamp_sample_preparation"], "direct-addition");
        assert_eq!(payload["lamp_formulation"], "air-dryable");
        assert_eq!(payload["lamp_loop_policy"], "require-six");
    }

    #[test]
    fn r8_panel_intent_and_modified_detection_topologies_fail_closed() {
        let panel = request(json!({
            "template": "ACGTACGTACGT",
            "lampDesignIntent": "panel-conservation-aware",
        }))
        .expect_err("panel-aware design needs an inclusivity panel");
        assert!(panel.to_string().contains("inclusivity panel"), "{panel}");

        let topology = request(json!({
            "template": "ACGTACGTACGT",
            "lampDetectionTopology": "sequence-specific-probe",
        }))
        .expect_err("planned topology must not execute in Gen-1");
        assert!(topology.to_string().contains("fail closed"), "{topology}");
    }

    #[test]
    fn r8_direct_matrix_formulation_and_readout_contradictions_fail_closed() {
        let direct = request(json!({
            "template": "ACGTACGTACGT",
            "lampProtocol": "meridian-mdx126",
            "lampSampleMatrix": "saliva-sputum",
            "lampSamplePreparation": "direct-addition",
        }))
        .expect_err("direct specimen matrix must match named authority");
        assert!(
            direct.to_string().contains("direct-sample authority"),
            "{direct}"
        );

        let formulation = request(json!({
            "template": "ACGTACGTACGT",
            "lampProtocol": "meridian-mdx126",
            "lampFormulation": "lyophilized",
        }))
        .expect_err("unreviewed formulation must fail");
        assert!(
            formulation.to_string().contains("formulation authority"),
            "{formulation}"
        );

        let takara = request(json!({
            "template": "ACGTACGTACGT",
            "lampProtocol": "takara-rr385",
            "lampReadout": "turbidity",
        }))
        .expect_err("Takara pyrophosphatase excludes turbidity");
        assert!(
            takara.to_string().contains("excludes this readout"),
            "{takara}"
        );

        let m1712 = request(json!({
            "template": "ACGTACGTACGT",
            "lampProtocol": "neb-m1712",
            "lampReadout": "colorimetric",
            "lampReadoutChemistry": "hydroxynaphthol-blue",
        }))
        .expect_err("M1712 HNB is source-backed incompatible");
        assert!(m1712.to_string().contains("poor contrast"), "{m1712}");
    }

    #[test]
    fn r9_vazyme_instrument_and_numeric_context_reach_worker() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "lampProtocol": "vazyme-rp711",
            "lampReadout": "fluorescence",
            "lampReadoutChemistry": "supplied-intercalating-dye",
            "lampFormulation": "liquid",
            "lampInstrumentProfile": "vazyme-slan96p",
            "lampBenchOptimization": {"fluorescent_dye_x": 0.4}
        }))
        .expect("source-bounded Vazyme request");
        let payload = parsed.to_worker();
        assert_eq!(payload["lamp_protocol"], "vazyme-rp711");
        assert_eq!(payload["lamp_instrument_profile"], "vazyme-slan96p");
        assert_eq!(payload["lamp_bench_optimization"]["fluorescent_dye_x"], 0.4);
    }

    #[test]
    fn r9_agdia_rna_and_amplifire_reach_worker() {
        let parsed = request(json!({
            "template": "ACGTACGTACGT",
            "fromRna": true,
            "lampProtocol": "agdia-lmx54700",
            "lampReadout": "fluorescence",
            "lampReadoutChemistry": "supplied-intercalating-dye",
            "lampInstrumentProfile": "agdia-amplifire"
        }))
        .expect("source-bounded Agdia request");
        let payload = parsed.to_worker();
        assert_eq!(payload["lamp_protocol"], "agdia-lmx54700");
        assert_eq!(payload["lamp_instrument_profile"], "agdia-amplifire");
        assert_eq!(payload["from_rna"], true);
    }

    #[test]
    fn r9_unsourced_mdx126_bench_override_fails_closed() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "lampProtocol": "meridian-mdx126",
            "lampBenchOptimization": {"magnesium_mM": 8.0}
        }))
        .expect_err("a fixed baseline is not an optimization envelope");
        assert!(
            error
                .to_string()
                .contains("does not publish a reviewed optimization envelope"),
            "{error}"
        );
    }
}
