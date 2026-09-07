//! One primer, reading into something rather than amplifying across it.
//!
//! A sequencing primer reads a trace outward from where it sits; a RACE primer
//! amplifies towards an end nobody has sequenced yet, against a partner that
//! comes out of a kit. In both, exactly one oligo is being designed.
//!
//! That is what makes this its own engine rather than half of `flanking-pair`.
//! Every pair-level idea is gone — no product, no matched temperatures, no
//! cross-dimer. Placement is assay-specific: Sanger uses an explicit facility
//! read envelope, while RACE searches a declared region of known sequence for a
//! gene-specific primer oriented toward the requested transcript end. Those two
//! geometries must not share hidden 40/800-base constants.
//!
//! So the target is required here, and required in a way it is not elsewhere. A
//! flanking pair asked for no target designs across the middle of the template,
//! which is a reasonable default. A single primer asked for no target has
//! nothing to be near or far from, and every primer on the template is equally
//! good — so there is no default to fall back to.
//!
//! Nothing scientific happens in this file. It checks the request and hands it
//! to the worker.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::common::{
    check_excluded, check_how_many, check_target_bounds, check_template, excluded_to_worker,
};
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

include!("race_authority.generated.rs");
include!("sequencing_authority.generated.rs");

/// Modifiers this engine will be combined with.
///
/// Tails, because a RACE primer is usually the anchor-tailed one. Not
/// multiplex: there is no pair to keep out of another pair's way, and a
/// sequencing reaction holds one primer by definition.
const ACCEPTS: &[Modifier] = &[Modifier::Tails, Modifier::VariantMasking];

/// The longest template this will take in one request.
const MAX_TEMPLATE_BASES: usize = 1_000_000;

/// The most primers one request may ask for.
const MOST_PRIMERS: u8 = 10;

/// Which way a primer reads.
const DIRECTIONS: &[&str] = &["forward", "reverse"];

/// Named sequencing chemistry overlays accepted by the worker.
const SEQUENCING_PROTOCOLS: &[&str] = SEQUENCING_CHEMISTRY_PROTOCOLS;
/// Instrument family is provenance for trace interpretation, not primer ranking.
const SEQUENCING_INSTRUMENTS: &[&str] = &[
    "unresolved",
    "seqstudio",
    "seqstudio-flex",
    "3500",
    "3500xl",
    "3730",
    "3730xl",
    "other",
];

/// Named RACE partner systems accepted by the release worker.
/// The executable GeneRacer branch is pinned to Thermo Fisher GeneRacer Kit
/// manual 25-0355 Version L. The family-only `generacer` identity is ambiguous
/// because Thermo Fisher also publishes a distinct 25-nt 5′ primer in RACE
/// Ready/support material. Legacy AAP is likewise not an executable identity.
const GENERACER_25_0355_VL: &str = "generacer-kit-25-0355-vl";
const FIRSTCHOICE_RLM_RACE: &str = "firstchoice-rlm-race";
const SMARTER_RACE_CURRENT: &str = "smarter-race-current";
const RACE_ADAPTERS: &[&str] = &[
    "not-selected",
    GENERACER_25_0355_VL,
    FIRSTCHOICE_RLM_RACE,
    SMARTER_RACE_CURRENT,
    "custom",
];
const RACE_CHEMISTRY_IDS: &[&str] = RACE_CHEMISTRIES;
const UNSUPPORTED_AMBIGUOUS_RACE_ADAPTERS: &[&str] = &["generacer", "AAP"];
/// Transcript end being chased by a RACE gene-specific primer.
/// Biological material/provenance declared for a RACE run.
const RACE_SUBSTRATES_LOCAL: &[&str] = RACE_SUBSTRATES;
/// Whether this design is the primary or a nested confirmation round.
const RACE_ROUNDS_LOCAL: &[&str] = RACE_ROUNDS;

/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SinglePrimerRequest {
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
    #[serde(default)]
    pub assay: Option<serde_json::Value>,
    /// Where the stretch the read has to cover begins, zero-based.
    ///
    /// Required, unlike everywhere else — see the module note.
    pub target_start: usize,
    /// How long that stretch is.
    pub target_length: usize,
    /// Which way the primer reads.
    #[serde(default)]
    pub direction: Option<String>,
    /// How much of the trace comes back unreadable, when it is known.
    ///
    /// Left alone for almost every request. A service provider who quotes a
    /// different figure is the reason it can be set at all.
    #[serde(default)]
    pub dead_zone: Option<usize>,
    /// How far the read stays legible, when it is known.
    #[serde(default)]
    pub read_length: Option<usize>,
    /// Optional named cycle-sequencing chemistry overlay.
    #[serde(default)]
    pub sequencing_protocol: Option<String>,
    /// Provider/design envelope. Submission quantities remain non-ranking metadata.
    #[serde(default)]
    pub sequencing_design_profile: Option<String>,
    /// Provider/service provenance. May mirror the design profile but is not inferred as a bench SOP.
    #[serde(default)]
    pub sequencing_provider: Option<String>,
    /// Diagnostic exact-binding scan against the curated universal-primer library.
    #[serde(default)]
    pub sequencing_universal_primer_scan: Option<bool>,
    /// Request a route-only opposite-direction confirmation plan.
    #[serde(default)]
    pub sequencing_bidirectional: Option<bool>,
    /// Plan sequential overlapping Sanger reads across a long target.
    #[serde(default)]
    pub sequencing_primer_walking: Option<bool>,
    /// Requested overlap between planned Sanger read windows.
    #[serde(default)]
    pub sequencing_walking_overlap: Option<usize>,
    /// Base64 ABI/AB1 trace evidence; bounded and parsed by the worker.
    #[serde(default)]
    pub sequencing_trace_ab1_base64: Option<String>,
    /// Trace filename retained as evidence provenance.
    #[serde(default)]
    pub sequencing_trace_filename: Option<String>,
    /// Instrument family used for capillary readout; `unresolved` is an explicit valid state.
    #[serde(default)]
    pub sequencing_instrument: Option<String>,
    /// Free-text identity when sequencingInstrument=`other`.
    #[serde(default)]
    pub sequencing_instrument_name: Option<String>,
    /// Optional facility/provider SOP identifier for the trace handoff.
    #[serde(default)]
    pub sequencing_facility_sop: Option<String>,
    /// Named RACE chemistry family. Chemistry and exact PCR partner are resolved separately.
    #[serde(default)]
    pub race_chemistry: Option<String>,
    /// Historical/exact RACE adapter selector retained for compatibility.
    #[serde(default)]
    pub race_adapter: Option<String>,
    /// Required for the RACE profile: which transcript end is being chased.
    #[serde(default)]
    pub race_direction: Option<String>,
    /// Biological substrate/source used to prepare the RACE template.
    #[serde(default)]
    pub race_substrate: Option<String>,
    /// Free-text preparation provenance (kit/SOP/template-switch/RT branch).
    #[serde(default)]
    pub race_preparation: Option<String>,
    /// Primary amplification or nested confirmation round.
    #[serde(default)]
    pub race_round: Option<String>,
    /// Explicit poly(A) state for 3-prime RACE chemistries that require it.
    #[serde(default)]
    pub race_polyadenylated: Option<bool>,
    /// Custom/current-protocol-provided RACE partner sequence when the exact partner is caller supplied.
    #[serde(default)]
    pub race_partner_sequence: Option<String>,
    /// Revision/identifier of the caller-supplied RACE SOP/manual that authorizes the exact partner.
    #[serde(default)]
    pub race_sop_revision: Option<String>,
    /// SHA-256 of the caller-reviewed RACE SOP/manual bytes or an approved local authority snapshot.
    #[serde(default)]
    pub race_sop_sha256: Option<String>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// What the product is for, which sets the sizes and the tolerances.
    #[serde(default)]
    pub purpose: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// What the primer has to satisfy.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// How many distinct primers to aim for.
    #[serde(default)]
    pub how_many: Option<u8>,
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
    /// Empirical RACE/Sanger evidence; never mutates ranking.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
}

/// A single-primer search, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct SinglePrimer {
    worker: Worker,
}

impl SinglePrimer {
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

impl Engine for SinglePrimer {
    fn id(&self) -> EngineId {
        EngineId::SinglePrimer
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
        self.worker.call("single", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<SinglePrimerRequest> {
    let parsed: SinglePrimerRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

fn authority_record(authority_json: &str, record_id: &str) -> Result<serde_json::Value> {
    let authority: serde_json::Value = serde_json::from_str(authority_json).map_err(|error| {
        CoreError::ToolFailed(format!(
            "generated single-primer authority is invalid JSON: {error}"
        ))
    })?;
    authority["records"]
        .get(record_id)
        .cloned()
        .ok_or_else(|| CoreError::InvalidRequest(format!("unknown authority record `{record_id}`")))
}

impl SinglePrimerRequest {
    /// Whether this request could describe a single-primer design at all.
    ///
    /// The template, `howMany` and the avoided regions are the shared checks
    /// from [`super::common`], so a rule means the same thing on every engine
    /// that carries the field. The target is required here rather than
    /// optional, so its own checks stay local — and since it names positions
    /// on the template, it is bounds-checked against it like everywhere else.
    fn check(&self) -> Result<()> {
        let template_bases = check_template(&self.template, MAX_TEMPLATE_BASES)?;
        if self.target_length == 0 {
            return Err(CoreError::InvalidRequest(
                "A target of no bases gives the primer nothing to be placed relative \
                 to. A single primer is defined by what it reads into."
                    .to_owned(),
            ));
        }
        check_target_bounds(self.target_start, self.target_length, template_bases)?;
        if let Some(direction) = self.direction.as_deref() {
            if !direction.is_empty() && !DIRECTIONS.contains(&direction) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{direction}` is not a direction to read in. It reads forward or \
                     reverse."
                )));
            }
        }
        if self.dead_zone.is_some() && self.read_length.is_some() {
            let smear = self.dead_zone.unwrap_or_default();
            let reach = self.read_length.unwrap_or_default();
            if smear >= reach {
                return Err(CoreError::InvalidRequest(format!(
                    "The read is given as unreadable for its first {smear} bases and \
                     legible for {reach}, which leaves nothing to read."
                )));
            }
        }
        if let Some(wanted) = self.how_many {
            check_how_many(wanted, MOST_PRIMERS)?;
        }
        if let Some(protocol) = &self.sequencing_protocol {
            if !SEQUENCING_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{protocol}` is not a sequencing protocol this engine knows. It knows: {}.",
                    SEQUENCING_PROTOCOLS.join(", ")
                )));
            }
        }
        if let Some(profile) = self.sequencing_design_profile.as_deref() {
            if !SEQUENCING_DESIGN_PROFILES.contains(&profile) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{profile}` is not a sequencing design profile; current profiles: {}",
                    SEQUENCING_DESIGN_PROFILES.join(", ")
                )));
            }
            let rec = authority_record(SEQUENCING_AUTHORITY_JSON, profile)?;
            if rec["execution_status"].as_str() != Some("executable") {
                return Err(CoreError::InvalidRequest(format!(
                    "sequencing design profile `{profile}` is not executable"
                )));
            }
        }
        if let Some(instrument) = &self.sequencing_instrument {
            if !SEQUENCING_INSTRUMENTS.contains(&instrument.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{instrument}` is not a sequencing instrument family this engine knows. It knows: {}.",
                    SEQUENCING_INSTRUMENTS.join(", ")
                )));
            }
        }
        if let Some(chemistry) = self.race_chemistry.as_deref() {
            if !RACE_CHEMISTRY_IDS.contains(&chemistry) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{chemistry}` is not a RACE chemistry; current chemistries: {}",
                    RACE_CHEMISTRY_IDS.join(", ")
                )));
            }
            let rec = authority_record(RACE_AUTHORITY_JSON, chemistry)?;
            if !matches!(
                rec["execution_status"].as_str(),
                Some("executable" | "executable-if-complete")
            ) {
                return Err(CoreError::InvalidRequest(format!(
                    "RACE chemistry `{chemistry}` is {} and cannot execute without exact partner/manual authority.",
                    rec["execution_status"].as_str().unwrap_or("non-executable")
                )));
            }
        }
        let caller_supplied_race_authority = matches!(
            self.race_chemistry.as_deref(),
            Some("custom") | Some(SMARTER_RACE_CURRENT)
        ) || matches!(
            self.race_adapter.as_deref(),
            Some("custom") | Some(SMARTER_RACE_CURRENT)
        );
        if caller_supplied_race_authority {
            if self
                .race_sop_revision
                .as_deref()
                .is_none_or(|value| value.trim().is_empty())
            {
                return Err(CoreError::InvalidRequest(
                    "custom/SMARTer RACE with a caller-supplied exact partner requires `raceSopRevision`; authority identity is not inferred.".to_owned(),
                ));
            }
            let digest = self.race_sop_sha256.as_deref().unwrap_or("");
            if digest.len() != 64 || !digest.bytes().all(|byte| byte.is_ascii_hexdigit()) {
                return Err(CoreError::InvalidRequest(
                    "custom/SMARTer RACE with a caller-supplied exact partner requires `raceSopSha256` as a 64-character SHA-256 digest.".to_owned(),
                ));
            }
        } else if self.race_sop_revision.is_some() || self.race_sop_sha256.is_some() {
            return Err(CoreError::InvalidRequest(
                "raceSopRevision/raceSopSha256 are only valid for custom or smarter-race-current caller-supplied authority branches.".to_owned(),
            ));
        }
        if let Some(adapter) = &self.race_adapter {
            if UNSUPPORTED_AMBIGUOUS_RACE_ADAPTERS.contains(&adapter.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "raceAdapter=`{adapter}` is an ambiguous, non-executable identity in the current contract; use `{GENERACER_25_0355_VL}` for the GeneRacer Kit 25-0355 Version L branch, or `custom` with the exact PCR-partner sequence."
                )));
            }
            if !RACE_ADAPTERS.contains(&adapter.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{adapter}` is not a RACE adapter this engine knows. It knows: {}.",
                    RACE_ADAPTERS.join(", ")
                )));
            }
            if (adapter == GENERACER_25_0355_VL || adapter == FIRSTCHOICE_RLM_RACE)
                && (self.race_direction.is_none() || self.race_round.is_none())
            {
                return Err(CoreError::InvalidRequest(format!(
                    "raceAdapter=`{adapter}` requires explicit raceDirection and raceRound so the exact versioned kit PCR partner can be resolved."
                )));
            }
        }
        if let (Some(chemistry), Some(adapter)) =
            (self.race_chemistry.as_deref(), self.race_adapter.as_deref())
        {
            if adapter != "not-selected"
                && matches!(
                    chemistry,
                    GENERACER_25_0355_VL | FIRSTCHOICE_RLM_RACE | SMARTER_RACE_CURRENT | "custom"
                )
                && adapter != chemistry
            {
                return Err(CoreError::InvalidRequest(
                    "raceChemistry and raceAdapter identify different RACE branches; cross-wiring exact kit/SOP PCR partners is not allowed.".to_owned(),
                ));
            }
        }
        if let Some(direction) = &self.race_direction {
            if !RACE_DIRECTIONS.contains(&direction.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{direction}` is not a RACE direction this engine knows. It knows: {}.",
                    RACE_DIRECTIONS.join(", ")
                )));
            }
        }
        if let Some(substrate) = &self.race_substrate {
            if !RACE_SUBSTRATES_LOCAL.contains(&substrate.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{substrate}` is not a RACE substrate this engine knows. It knows: {}.",
                    RACE_SUBSTRATES_LOCAL.join(", ")
                )));
            }
        }
        if let Some(round) = &self.race_round {
            if !RACE_ROUNDS_LOCAL.contains(&round.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{round}` is not a RACE round this engine knows. It knows: {}.",
                    RACE_ROUNDS_LOCAL.join(", ")
                )));
            }
        }
        let assay_id = self
            .assay
            .as_ref()
            .and_then(|assay| assay.get("id"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default();
        if assay_id == "sequencing-primer" {
            if self
                .direction
                .as_deref()
                .filter(|value| !value.is_empty())
                .is_none()
            {
                return Err(CoreError::InvalidRequest(
                    "Scientific-Strict sequencing-primer requires explicit `direction`: forward or reverse; read orientation is not inferred from omission.".to_owned(),
                ));
            }
            if self.dead_zone.is_none() || self.read_length.is_none() {
                return Err(CoreError::InvalidRequest(
                    "Scientific-Strict sequencing-primer requires explicit `deadZone` and `readLength` from the sequencing provider/instrument/SOP; PCRStudio does not assume 40/800.".to_owned(),
                ));
            }
            if let Some(overlap) = self.sequencing_walking_overlap {
                if overlap == 0 || overlap > 10_000 {
                    return Err(CoreError::InvalidRequest(
                        "sequencingWalkingOverlap must be 1..=10000 bases when supplied."
                            .to_owned(),
                    ));
                }
                if self.sequencing_primer_walking != Some(true) {
                    return Err(CoreError::InvalidRequest(
                        "sequencingWalkingOverlap requires sequencingPrimerWalking=true."
                            .to_owned(),
                    ));
                }
            }
            if self.sequencing_primer_walking == Some(true)
                && self.sequencing_walking_overlap.is_none()
            {
                return Err(CoreError::InvalidRequest(
                    "sequencingPrimerWalking=true requires explicit sequencingWalkingOverlap; overlap is not inferred.".to_owned(),
                ));
            }
            if let Some(trace) = self.sequencing_trace_ab1_base64.as_deref() {
                const MAX_AB1_BASE64_CHARS: usize = 5_592_412;
                let compact_len = trace.chars().filter(|ch| !ch.is_whitespace()).count();
                if compact_len == 0 || compact_len > MAX_AB1_BASE64_CHARS {
                    return Err(CoreError::InvalidRequest(
                        "sequencingTraceAb1Base64 is empty or exceeds the bounded 4 MiB decoded AB1 envelope.".to_owned(),
                    ));
                }
            }
            if self
                .sequencing_trace_filename
                .as_deref()
                .is_some_and(|name| name.len() > 255)
            {
                return Err(CoreError::InvalidRequest(
                    "sequencingTraceFilename is limited to 255 characters.".to_owned(),
                ));
            }
            if self.sequencing_instrument.as_deref() == Some("other")
                && self
                    .sequencing_instrument_name
                    .as_deref()
                    .is_none_or(|value| value.trim().is_empty())
            {
                return Err(CoreError::InvalidRequest(
                    "sequencingInstrument=other requires non-empty `sequencingInstrumentName`."
                        .to_owned(),
                ));
            }
        } else if self.sequencing_instrument.is_some()
            || self.sequencing_instrument_name.is_some()
            || self.sequencing_facility_sop.is_some()
            || self.sequencing_primer_walking.is_some()
            || self.sequencing_walking_overlap.is_some()
            || self.sequencing_trace_ab1_base64.is_some()
            || self.sequencing_trace_filename.is_some()
        {
            return Err(CoreError::InvalidRequest(
                "sequencingInstrument/sequencingInstrumentName/sequencingFacilitySop belong to the `sequencing-primer` assay.".to_owned(),
            ));
        }
        if self.sequencing_instrument.as_deref() != Some("other")
            && self.sequencing_instrument_name.is_some()
        {
            return Err(CoreError::InvalidRequest(
                "sequencingInstrumentName is only valid when sequencingInstrument=`other`."
                    .to_owned(),
            ));
        }
        if assay_id == "race" && (self.dead_zone.is_some() || self.read_length.is_some()) {
            return Err(CoreError::InvalidRequest(
                "deadZone/readLength are Sanger placement inputs and are not valid for RACE."
                    .to_owned(),
            ));
        }
        if assay_id == "race" && self.circular.unwrap_or(false) {
            return Err(CoreError::InvalidRequest(
                "RACE requires a linear transcript/cDNA coordinate context; circular is invalid."
                    .to_owned(),
            ));
        }
        if assay_id == "race" && self.race_direction.is_none() {
            return Err(CoreError::InvalidRequest(
                "RACE requires an explicit `raceDirection`: choose `5prime` or `3prime`."
                    .to_owned(),
            ));
        }
        if assay_id == "race"
            && self
                .race_chemistry
                .as_deref()
                .is_none_or(|chemistry| chemistry == "not-selected")
            && self
                .race_adapter
                .as_deref()
                .is_none_or(|adapter| adapter == "not-selected")
        {
            return Err(CoreError::InvalidRequest(
                "RACE requires explicit raceChemistry (or a historical exact raceAdapter for migration).".to_owned(),
            ));
        }
        if caller_supplied_race_authority {
            let sequence = self
                .race_partner_sequence
                .as_deref()
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .ok_or_else(|| {
                    CoreError::InvalidRequest(
                        "raceAdapter=custom or smarter-race-current requires a non-empty `racePartnerSequence`.".to_owned(),
                    )
                })?;
            if sequence.len() > 200
                || sequence
                    .chars()
                    .any(|base| !matches!(base.to_ascii_uppercase(), 'A' | 'C' | 'G' | 'T'))
            {
                return Err(CoreError::InvalidRequest(
                    "racePartnerSequence must be 1–200 unambiguous DNA bases (A/C/G/T).".to_owned(),
                ));
            }
        } else if self.race_partner_sequence.is_some() {
            return Err(CoreError::InvalidRequest(
                "racePartnerSequence is only valid for custom or smarter-race-current caller-supplied authority branches.".to_owned(),
            ));
        }
        if assay_id == "race" && self.race_substrate.is_none() {
            return Err(CoreError::InvalidRequest(
                "RACE requires `raceSubstrate`: choose `total-rna`, `mrna` or `cdna`.".to_owned(),
            ));
        }
        if assay_id == "race"
            && self
                .race_preparation
                .as_deref()
                .is_none_or(|value| value.trim().is_empty())
        {
            return Err(CoreError::InvalidRequest(
                "RACE requires non-empty `racePreparation` provenance (kit/SOP/RT or template-switch branch).".to_owned(),
            ));
        }
        if assay_id == "race" && self.race_round.is_none() {
            return Err(CoreError::InvalidRequest(
                "RACE requires `raceRound`: choose `primary` or `nested`.".to_owned(),
            ));
        }
        if assay_id == "race"
            && self.race_chemistry.as_deref() == Some(SMARTER_RACE_CURRENT)
            && self.race_direction.as_deref() == Some("3prime")
            && self.race_polyadenylated != Some(true)
        {
            return Err(CoreError::InvalidRequest(
                "SMARTer 3-prime RACE requires explicit racePolyadenylated=true.".to_owned(),
            ));
        }
        if self
            .race_partner_sequence
            .as_deref()
            .is_some_and(|v| v.trim().is_empty())
        {
            return Err(CoreError::InvalidRequest(
                "racePartnerSequence cannot be empty when supplied.".to_owned(),
            ));
        }
        if assay_id != "race" && self.race_polyadenylated.is_some() {
            return Err(CoreError::InvalidRequest(
                "racePolyadenylated belongs to the `race` assay.".to_owned(),
            ));
        }
        if self.race_direction.is_some() && !matches!(assay_id, "" | "race") {
            return Err(CoreError::InvalidRequest(
                "`raceDirection` belongs to the `race` assay.".to_owned(),
            ));
        }
        if let Some(race_direction) = self.race_direction.as_deref() {
            let expected = match race_direction {
                "5prime" => "reverse",
                "3prime" => "forward",
                _ => {
                    return Err(CoreError::InvalidRequest(format!(
                        "unsupported RACE direction `{race_direction}`"
                    )))
                }
            };
            if let Some(direction) = self.direction.as_deref() {
                if !direction.is_empty() && direction != expected {
                    return Err(CoreError::InvalidRequest(format!(
                        "RACE `{race_direction}` reads `{expected}`; it cannot be combined with `{direction}`."
                    )));
                }
            }
        }
        if let Some(regions) = &self.excluded {
            check_excluded(regions, template_bases)?;
        }
        Ok(())
    }

    /// This request in the worker's own vocabulary.
    fn to_worker(&self) -> serde_json::Value {
        let mut payload = serde_json::Map::new();
        payload.insert("template".into(), self.template.clone().into());
        payload.insert("target_start".into(), self.target_start.into());
        payload.insert("target_length".into(), self.target_length.into());

        let mut put = |key: &str, value: Option<serde_json::Value>| {
            if let Some(value) = value {
                payload.insert(key.to_owned(), value);
            }
        };
        put("lowercase_masking", self.lowercase_masking.map(Into::into));
        put("name", self.name.clone().map(Into::into));
        put("assay", self.assay.clone());
        put("direction", self.direction.clone().map(Into::into));
        put("dead_zone", self.dead_zone.map(Into::into));
        put("read_length", self.read_length.map(Into::into));
        put(
            "sequencing_protocol",
            self.sequencing_protocol.clone().map(Into::into),
        );
        put(
            "sequencing_design_profile",
            self.sequencing_design_profile.clone().map(Into::into),
        );
        put(
            "sequencing_provider",
            self.sequencing_provider.clone().map(Into::into),
        );
        put(
            "sequencing_universal_primer_scan",
            self.sequencing_universal_primer_scan.map(Into::into),
        );
        put(
            "sequencing_bidirectional",
            self.sequencing_bidirectional.map(Into::into),
        );
        put(
            "sequencing_primer_walking",
            self.sequencing_primer_walking.map(Into::into),
        );
        put(
            "sequencing_walking_overlap",
            self.sequencing_walking_overlap.map(Into::into),
        );
        put(
            "sequencing_trace_ab1_base64",
            self.sequencing_trace_ab1_base64.clone().map(Into::into),
        );
        put(
            "sequencing_trace_filename",
            self.sequencing_trace_filename.clone().map(Into::into),
        );
        put(
            "sequencing_instrument",
            self.sequencing_instrument.clone().map(Into::into),
        );
        put(
            "sequencing_instrument_name",
            self.sequencing_instrument_name.clone().map(Into::into),
        );
        put(
            "sequencing_facility_sop",
            self.sequencing_facility_sop.clone().map(Into::into),
        );
        put(
            "race_chemistry",
            self.race_chemistry.clone().map(Into::into),
        );
        put("race_adapter", self.race_adapter.clone().map(Into::into));
        put(
            "race_direction",
            self.race_direction.clone().map(Into::into),
        );
        put(
            "race_substrate",
            self.race_substrate.clone().map(Into::into),
        );
        put(
            "race_preparation",
            self.race_preparation.clone().map(Into::into),
        );
        put("race_round", self.race_round.clone().map(Into::into));
        put(
            "race_polyadenylated",
            self.race_polyadenylated.map(Into::into),
        );
        put(
            "race_partner_sequence",
            self.race_partner_sequence.clone().map(Into::into),
        );
        put(
            "race_sop_revision",
            self.race_sop_revision.clone().map(Into::into),
        );
        put(
            "race_sop_sha256",
            self.race_sop_sha256.clone().map(Into::into),
        );
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("how_many", self.how_many.map(Into::into));
        put("background", self.background.clone().map(Into::into));
        put("excluded", excluded_to_worker(self.excluded.as_ref()));
        put("circular", self.circular.map(Into::into));
        put("workflow_evidence", self.workflow_evidence.clone());

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(value: serde_json::Value) -> Result<SinglePrimerRequest> {
        parse(&value)
    }

    #[test]
    fn a_design_without_a_target_is_refused_rather_than_defaulted() {
        // Everywhere else a missing target means "somewhere sensible". Here
        // there is nowhere sensible: every primer on the template would be
        // equally good, which is the same as none being good.
        let error =
            request(json!({ "template": "ACGTACGTACGT" })).expect_err("no target start or length");
        assert!(
            error.to_string().contains("targetStart"),
            "it names the missing field: {error}"
        );
    }

    #[test]
    fn a_target_of_no_bases_says_what_a_single_primer_is_for() {
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "targetStart": 10,
            "targetLength": 0,
        }))
        .expect_err("an empty target");
        assert!(error.to_string().contains("reads into"), "{error}");
    }

    #[test]
    fn a_direction_that_is_not_a_direction_is_refused_by_name() {
        let error = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "direction": "sideways",
        }))
        .expect_err("not a direction");
        assert!(error.to_string().contains("sideways"), "{error}");
    }

    #[test]
    fn a_read_that_is_unreadable_for_longer_than_it_is_legible_is_refused() {
        let error = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "deadZone": 900,
            "readLength": 800,
        }))
        .expect_err("nothing left to read");
        assert!(error.to_string().contains("nothing to read"), "{error}");
    }

    #[test]
    fn an_unknown_sequencing_protocol_is_refused() {
        let error = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "sequencingProtocol": "invented-kit",
        }))
        .expect_err("unknown sequencing protocol");
        assert!(error.to_string().contains("sequencing protocol"), "{error}");
    }

    #[test]
    fn a_named_sequencing_protocol_reaches_the_worker() {
        let parsed = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "sequencingProtocol": "bigdye-v3-1",
        }))
        .expect("named sequencing protocol");
        assert_eq!(parsed.to_worker()["sequencing_protocol"], "bigdye-v3-1");
    }

    #[test]
    fn an_unknown_race_adapter_is_refused() {
        let error = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "raceAdapter": "unknown-anchor",
        }))
        .expect_err("unknown RACE adapter");
        assert!(error.to_string().contains("RACE adapter"), "{error}");
    }

    #[test]
    fn a_versioned_named_race_adapter_reaches_the_worker() {
        let parsed = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "raceDirection": "5prime",
            "raceRound": "primary",
            "raceAdapter": "generacer-kit-25-0355-vl",
        }))
        .expect("versioned named RACE adapter");
        assert_eq!(
            parsed.to_worker()["race_adapter"],
            "generacer-kit-25-0355-vl"
        );
    }

    #[test]
    fn ambiguous_family_only_generacer_and_aap_are_refused() {
        for ambiguous in ["generacer", "AAP"] {
            let error = request(json!({
                "template": "ACGT".repeat(25),
                "targetStart": 10,
                "targetLength": 50,
                "raceAdapter": ambiguous,
            }))
            .expect_err("ambiguous RACE adapter");
            assert!(
                error.to_string().contains("ambiguous, non-executable"),
                "{error}"
            );
        }
    }

    #[test]
    fn a_race_direction_reaches_the_worker() {
        let parsed = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "assay": {"id": "race"},
            "raceDirection": "5prime",
            "raceAdapter": "generacer-kit-25-0355-vl",
            "raceSubstrate": "total-rna",
            "racePreparation": "test-RACE-SOP",
            "raceRound": "primary",
        }))
        .expect("named RACE direction");
        assert_eq!(parsed.to_worker()["race_direction"], "5prime");
    }

    #[test]
    fn a_race_profile_without_direction_is_refused() {
        let error = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "assay": {"id": "race"},
        }))
        .expect_err("RACE direction");
        assert!(error.to_string().contains("raceDirection"), "{error}");
    }

    #[test]
    fn a_race_direction_cannot_disagree_with_a_low_level_read_direction() {
        let error = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "assay": {"id": "race"},
            "raceDirection": "3prime",
            "raceAdapter": "generacer-kit-25-0355-vl",
            "raceSubstrate": "total-rna",
            "racePreparation": "test-RACE-SOP",
            "raceRound": "primary",
            "direction": "reverse",
        }))
        .expect_err("contradictory RACE direction");
        assert!(error.to_string().contains("cannot be combined"), "{error}");
    }

    #[test]
    fn race_profile_requires_adapter_substrate_preparation_and_round() {
        let base = json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "assay": {"id": "race"},
            "raceDirection": "5prime",
        });
        let error = request(base).expect_err("missing adapter");
        assert!(error.to_string().contains("raceAdapter"), "{error}");

        let parsed = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "assay": {"id": "race"},
            "raceDirection": "5prime",
            "raceChemistry": "custom",
            "raceAdapter": "custom",
            "racePartnerSequence": "ACGTACGTACGT",
            "raceSopRevision": "local-SOP-rev-1",
            "raceSopSha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "raceSubstrate": "cdna",
            "racePreparation": "template-switch SOP",
            "raceRound": "nested",
        }))
        .expect("complete RACE context");
        let payload = parsed.to_worker();
        assert_eq!(payload["race_substrate"], "cdna");
        assert_eq!(payload["race_round"], "nested");
        assert_eq!(payload["race_partner_sequence"], "ACGTACGTACGT");
        assert_eq!(payload["race_sop_revision"], "local-SOP-rev-1");
        assert_eq!(
            payload["race_sop_sha256"],
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        );
    }

    #[test]
    fn smarter_race_requires_content_addressed_sop_and_rejects_cross_wiring() {
        let missing = request(json!({
            "template": "ACGT".repeat(40),
            "targetStart": 20,
            "targetLength": 80,
            "assay": {"id": "race"},
            "raceDirection": "3prime",
            "raceChemistry": "smarter-race-current",
            "racePartnerSequence": "ACGTACGTACGT",
            "raceSubstrate": "cdna",
            "racePreparation": "SMARTer template-switch SOP",
            "raceRound": "primary",
            "racePolyadenylated": true,
        }))
        .expect_err("SMARTer without content-addressed SOP");
        assert!(missing.to_string().contains("raceSopRevision"), "{missing}");

        let crosswired = request(json!({
            "template": "ACGT".repeat(40),
            "targetStart": 20,
            "targetLength": 80,
            "assay": {"id": "race"},
            "raceDirection": "3prime",
            "raceChemistry": "smarter-race-current",
            "raceAdapter": "custom",
            "racePartnerSequence": "ACGTACGTACGT",
            "raceSopRevision": "SMARTer-current-local-copy",
            "raceSopSha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "raceSubstrate": "cdna",
            "racePreparation": "SMARTer template-switch SOP",
            "raceRound": "primary",
            "racePolyadenylated": true,
        }))
        .expect_err("cross-wired chemistry and adapter");
        assert!(
            crosswired.to_string().contains("different RACE branches"),
            "{crosswired}"
        );
    }

    #[test]
    fn sequencing_instrument_handoff_is_explicit_but_may_remain_unresolved() {
        let parsed = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "assay": {"id": "sequencing-primer"},
            "direction": "forward",
            "deadZone": 40,
            "readLength": 800,
            "sequencingInstrument": "unresolved",
        }))
        .expect("explicit unresolved instrument");
        assert_eq!(parsed.to_worker()["sequencing_instrument"], "unresolved");

        let error = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
            "assay": {"id": "sequencing-primer"},
            "direction": "forward",
            "deadZone": 40,
            "readLength": 800,
            "sequencingInstrument": "other",
        }))
        .expect_err("other instrument without identity");
        assert!(
            error.to_string().contains("sequencingInstrumentName"),
            "{error}"
        );
    }

    #[test]
    fn the_target_reaches_the_worker_as_two_required_fields() {
        let parsed = request(json!({
            "template": "ACGT".repeat(25),
            "targetStart": 10,
            "targetLength": 50,
        }))
        .expect("a well-formed request");

        let payload = parsed.to_worker();
        assert_eq!(payload["target_start"], 10);
        assert_eq!(payload["target_length"], 50);
        // Never sent as null: the worker has its own figures for these and a
        // null would overwrite them.
        assert!(payload.get("dead_zone").is_none());
        assert!(payload.get("read_length").is_none());
    }

    #[test]
    fn a_target_past_the_end_of_the_template_is_refused_rather_than_silently_clipped() {
        // A primer placed relative to a stretch that is not there protects
        // nothing; the request names positions on this template, so they are
        // checked against it.
        let error = request(json!({
            "template": "ACGTACGTACGT",
            "targetStart": 10,
            "targetLength": 50,
        }))
        .expect_err("runs off the template");
        assert!(error.to_string().contains("past the end"), "{error}");
    }

    #[test]
    fn an_avoided_region_past_the_end_is_refused() {
        let error = request(json!({
            "template": "ACGTACGTAC",
            "targetStart": 2,
            "targetLength": 4,
            "excluded": [[8, 40]],
        }))
        .expect_err("this protects nothing");
        assert!(error.to_string().contains("past the end"), "{error}");
    }
}
