//! The first engine that computes: a pair of primers either side of a target.
//!
//! Standard, long-range and colony PCR run on this, and so do qPCR with a dye,
//! digital PCR, species-specific PCR, RPA and restriction cloning. That is the
//! whole argument for splitting engines from assays — the search is written
//! once and the assays differ in what they refuse.
//!
//! Nothing scientific happens in this file. It checks the request, hands it to
//! the worker, and hands the answer back. The thermodynamics, the search, the
//! specificity scan and the folding all live in Python, where the libraries
//! that do them live.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::digital_multiplex::{self, DigitalMultiplexTarget};
use super::rpa_multiplex::{self, RpaMultiplexTarget};

use super::common::{
    check_excluded, check_how_many, check_modified_oligos, check_positions, check_target_bounds,
    check_target_pair, check_template, contains_rna_base, excluded_to_worker,
};
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

/// Modifiers this engine will be combined with.
const ACCEPTS: &[Modifier] = &[
    Modifier::Multiplex,
    Modifier::ReverseTranscription,
    Modifier::BisulfiteConversion,
    Modifier::Tails,
    Modifier::VariantMasking,
];

/// The largest template this will accept in one request.
///
/// Not a scientific limit. A template arrives in a JSON body and is held in
/// memory on both sides of a pipe, and a person who pastes a chromosome should
/// be told so rather than timing out.
const MAX_TEMPLATE_BASES: usize = 1_000_000;

/// Operational ceiling for mismatches outside the exact seed.
///
/// This is a resource boundary, not a biological acceptance rule. Beyond this
/// point the bounded scan becomes an almost-anywhere search and an indexed
/// alignment tool is the honest next step.
const MAX_MISMATCHES: u8 = 20;

// Canonical protocol/platform vocabulary is generated from
// contracts/chemistry/flanking-protocols.toml. Keeping these ids out of this
// hand-written preflight prevents Python/Rust/Web catalogue drift.
include!("flanking_protocol_ids.generated.rs");

/// The most pairs one request may ask for.
///
/// The same ceiling the worker itself applies to a `run`; naming it here too
/// means a request that asks for two hundred is refused before a process is
/// started rather than answered with fifty by the far end.
pub(crate) const MAX_HOW_MANY: u8 = 50;

/// Which enzymes each end should carry, and how much room to give them.
///
/// Both names are optional together: naming neither asks which enzymes *could*
/// be used on this template, and gets untailed primers with that list. That is
/// the honest answer to a question this side cannot settle -- which two are
/// right depends on the vector's cloning site, and nothing in this request
/// describes the vector.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TailRequest {
    /// Explicit supplier/end-cleavage authority for generated restriction tails.
    /// Generation 1 executes only the NEB general six-flanking-base branch.
    #[serde(default)]
    pub tail_protocol: Option<String>,
    /// The enzyme whose site goes on the forward primer.
    #[serde(default)]
    pub forward_enzyme: Option<String>,
    /// The enzyme whose site goes on the reverse primer. It may match the
    /// forward enzyme, in which case the result is explicitly non-directional.
    #[serde(default)]
    pub reverse_enzyme: Option<String>,
    /// How many bases to leave outside each site.
    ///
    /// Restriction sites need flanking sequence for end cleavage. Scientific-
    /// Strict Generation 1 executes only the explicitly named NEB general six-
    /// base branch; arbitrary values are not promoted to supplier guidance.
    #[serde(default)]
    pub protective_bases: Option<u8>,
    /// Exact protective DNA to place 5' of the forward restriction site.
    /// NEB supplies the six-base rule, not a universal sequence.
    #[serde(default)]
    pub forward_protective_sequence: Option<String>,
    /// Exact protective DNA to place 5' of the reverse restriction site.
    #[serde(default)]
    pub reverse_protective_sequence: Option<String>,
}

/// Which primer you already own, and which end of the insert it reads towards.
///
/// A name from the catalogue, or the bases themselves for a primer this build
/// has never heard of. Both are allowed because a cloning bench is full of
/// primers that predate any catalogue.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct VectorPrimerRequest {
    /// A name from the catalogue, or a label for a supplied sequence.
    #[serde(default)]
    pub name: Option<String>,
    /// The bases, for a primer that is not in the catalogue.
    #[serde(default)]
    pub sequence: Option<String>,
    /// Which end of the insert the vector primer approaches from.
    ///
    /// `start` is the ordinary case and the default: the vector primer reads
    /// forward into the beginning of the insert, so the primer designed here
    /// reads back towards it.
    #[serde(default)]
    pub reads_into: Option<String>,
    /// The plasmid, linearised where the insert goes in.
    ///
    /// Optional, and what it buys is the product size. The vector primer sits
    /// some distance from the cloning site and that distance belongs to a
    /// molecule the worker had never seen, so every screen it produced reported
    /// its product as unknown — which is the one number somebody holds a gel up
    /// against.
    #[serde(default)]
    pub vector: Option<String>,
    /// How many candidates to return.
    #[serde(default)]
    pub how_many: Option<u8>,
}

/// Source-conditioned reaction context for flanking-pair assays. These values
/// plan/record the bench recipe and never implicitly alter Primer3 ranking.
#[derive(Debug, Clone, Deserialize, Serialize, Default)]
#[serde(
    rename_all(deserialize = "camelCase", serialize = "snake_case"),
    deny_unknown_fields
)]
pub struct FlankingNumericContext {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Reaction volume in microlitres.
    pub reaction_volume_ul: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Primer concentration in micromolar.
    pub primer_each_um: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Primer concentration in nanomolar.
    pub primer_each_nm: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// GC enhancer percentage.
    pub gc_enhancer_percent: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Named reaction additive.
    pub additive: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Named cycling profile.
    pub cycling_profile: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Template fraction percentage.
    pub template_fraction_percent: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Target length in kilobases.
    pub target_length_kb: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Detailed partition-format identity.
    pub partition_format_detail: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Sample preparation identity.
    pub preparation: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Initial denaturation time in minutes.
    pub initial_denaturation_time_min: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// RPA reaction temperature in Celsius.
    pub rpa_temperature_c: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// RPA reaction time in minutes.
    pub rpa_time_min: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Bst activity in units per microlitre.
    pub rpa_bst_units_per_ul: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Whether the RPA reaction is multiplexed.
    pub rpa_multiplex: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Template input mass in nanograms.
    pub template_input_ng: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Template input volume in microlitres.
    pub template_input_ul: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Template class or material identity.
    pub template_class: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Whether high-molecular-weight template was verified.
    pub hmw_template_verified: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// qPCR instrument profile identity.
    pub qpcr_instrument_profile: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Digital assay consumable identity.
    pub digital_consumable_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Effective partition volume in nanolitres.
    pub effective_partition_volume_nl: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Fragmentation enzyme identity.
    pub fragmentation_enzyme: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    /// Colony sample input volume in microlitres.
    pub colony_sample_input_ul: Option<f64>,
}

/// What a caller has to send. Anything else is refused before a process starts.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct FlankingPairRequest {
    /// The sequence to amplify from, in any of the shapes the worker resolves.
    pub template: String,
    /// Whether lowercase letters in the submitted template are intentional
    /// soft masking. None means the caller did not resolve the ambiguity; the
    /// Scientific-Strict worker refuses lowercase input in that case instead of
    /// guessing from how much of the sequence happens to be lowercase.
    #[serde(default)]
    pub lowercase_masking: Option<bool>,
    /// What to call it. Ends up on the oligos in the order sheet.
    #[serde(default)]
    pub name: Option<String>,
    /// First base that must fall inside the product, zero-based.
    #[serde(default)]
    pub target_start: Option<usize>,
    /// How many bases from `target_start` must be included.
    #[serde(default)]
    pub target_length: Option<usize>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// What the product is for, which sets the sizes and the tolerances.
    ///
    /// Not checked against a list here. The names live in the worker, which
    /// publishes them through `presets` and refuses an unknown one by name --
    /// so a second copy of the list in this file could only ever go stale.
    #[serde(default)]
    pub purpose: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// What a pair has to satisfy.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// Sequence the primers must not also amplify.
    #[serde(default)]
    pub background: Option<String>,
    /// FASTA records of intended target strains/variants for an inclusivity
    /// screen. Species-specific PCR needs this separately from the exclusion
    /// background: a pair can reject every supplied relative and still miss a
    /// target strain that was never checked.
    #[serde(default)]
    pub inclusivity: Option<String>,
    /// Traceable origin/release/retrieval context for the intended-target panel.
    /// Kept separate from FASTA headers because a content label is not a
    /// database/release or isolate-identity provenance record.
    #[serde(default)]
    pub inclusivity_panel_provenance: Option<String>,
    /// Traceable origin/release/retrieval context for the exclusion panel.
    #[serde(default)]
    pub background_panel_provenance: Option<String>,
    /// Why the chosen intended targets and near neighbours represent the claim.
    #[serde(default)]
    pub species_panel_selection_rationale: Option<String>,
    /// NCBI taxonomy identifier declared for the intended biological target.
    #[serde(default)]
    pub species_target_taxid: Option<u64>,
    /// Pinned taxonomy authority/release/date used when the panel was curated.
    #[serde(default)]
    pub species_taxonomy_snapshot: Option<String>,
    /// Pinned sequence database/release used to curate inclusivity and exclusivity panels.
    #[serde(default)]
    pub species_database_snapshot: Option<String>,
    /// Accession.version manifest for the reviewed target and near-neighbour panel.
    #[serde(default)]
    pub species_panel_accession_manifest: Option<String>,
    /// Offline resolver snapshot: accession.version, TaxID, lifecycle status and optional replacement/database/taxonomy snapshot.
    #[serde(default)]
    pub species_panel_accession_authority_manifest: Option<String>,
    /// Per-record FASTA/accession role/topology/optional population-evidence metadata TSV.
    #[serde(default)]
    pub species_panel_record_metadata_manifest: Option<String>,
    /// ISO calendar date when the panel snapshot was retrieved/reviewed.
    #[serde(default)]
    pub species_panel_retrieved_date: Option<String>,
    /// Whole-primer mismatch budget used by specificity-v5 discovery.
    #[serde(default)]
    pub max_mismatches: Option<u8>,
    /// How many distinct pairs to aim for.
    #[serde(default)]
    pub how_many: Option<u8>,
    /// Which assay this is, and the numbers that assay differs by.
    ///
    /// Set by the route from the address, never by the caller. Passed through
    /// to the worker, which layers the assay's numbers under whatever the
    /// person actually typed.
    #[serde(default)]
    pub assay: Option<serde_json::Value>,
    /// Optional named Standard-PCR polymerase/protocol overlay. This is bench
    /// provenance only; the worker retains the shared Standard-PCR Primer3
    /// screening context unless a future separately versioned model says otherwise.
    #[serde(default)]
    pub standard_pcr_protocol: Option<String>,
    /// Optional named SYBR chemistry overlay; meaningful only for `qpcr-sybr`.
    #[serde(default)]
    pub qpcr_protocol: Option<String>,
    /// Optional named RPA kit overlay; meaningful only for `rpa`.
    #[serde(default)]
    pub rpa_protocol: Option<String>,
    /// Selected peer RPA assays for a multiplex empirical-evidence panel. Final RPA selection remains empirical.
    #[serde(default)]
    pub rpa_multiplex_panel: Option<Vec<RpaMultiplexTarget>>,
    /// Explicit long-range chemistry/protocol identity. Required for long-range-pcr.
    #[serde(default)]
    pub long_range_protocol: Option<String>,
    /// Optional named digital-PCR platform overlay; meaningful only for `digital-pcr`.
    #[serde(default)]
    pub digital_protocol: Option<String>,
    /// Source-conditioned reaction planning context. Never changes primer ranking silently.
    #[serde(default)]
    pub flanking_numeric_context: Option<FlankingNumericContext>,
    /// Shared modified-oligo manufacturing/readout annotations. They do not promote non-executable RPA probe chemistries.
    #[serde(default)]
    pub modified_oligos: Option<serde_json::Value>,
    /// Physical partition format used by the digital-PCR platform. Required for digital-pcr.
    #[serde(default)]
    pub digital_partition_format: Option<String>,
    /// Structured platform identity. Required for digital-pcr.
    #[serde(default)]
    pub digital_platform_id: Option<String>,
    /// Free-text platform/instrument identity, required only for `other-validated`.
    #[serde(default)]
    pub digital_platform_name: Option<String>,
    /// Exact instrument model within a platform family when multiplex capability is model-specific.
    #[serde(default)]
    pub digital_instrument_model: Option<String>,
    /// Explicit fragmentation state; never inferred from amplicon or template length.
    #[serde(default)]
    pub digital_fragmentation_state: Option<String>,
    /// Optional digital multiplex architecture. `none` keeps the dye branch simplex;
    /// other modes are planning/run-evidence metadata and never infer thresholds or clusters.
    #[serde(default)]
    pub digital_multiplex_mode: Option<String>,
    /// Typed targets sharing the dPCR run. Probe/channel/amplitude identities are run authority,
    /// not a claim that this flanking engine designed those peer probe assays.
    #[serde(default)]
    pub digital_multiplex_panel: Option<Vec<DigitalMultiplexTarget>>,
    /// Measured-run evidence payload (software/version, thresholds, rain/cluster review, counts).
    /// It is retained as evidence and must not change sequence ranking.
    #[serde(default)]
    pub digital_run_evidence: Option<serde_json::Value>,
    /// Stretches no primer may overlap, each a zero-based start and a length.
    ///
    /// A repeat, a stretch of poor sequence, a site already known to prime
    /// badly. Distinct from a target, which says where a primer must *reach*.
    #[serde(default)]
    pub excluded: Option<Vec<(usize, usize)>>,
    /// Positions this template is known to be polymorphic at, zero-based.
    ///
    /// Distinct from `excluded`, which forbids a primer from overlapping at
    /// all. A coordinate-only variant record has no allele, frequency or
    /// chemistry-specific mismatch evidence, so any candidate whose annealing
    /// core overlaps a supplied coordinate is removed in every policy mode.
    /// Policy selection never resurrects the former distance heuristic.
    ///
    /// This is what the `variant-masking` modifier was always supposed to
    /// mean. It was declared on this assay and read by nothing.
    #[serde(default)]
    pub variants: Option<Vec<usize>>,
    /// Restriction sites to put on the 5-prime ends, for cloning.
    ///
    /// Absent for every assay except restriction cloning, which is why it is
    /// optional rather than a second engine: the search for the pair is the
    /// same one, and what differs is a constraint on which enzymes may be used
    /// and an addition to what gets ordered.
    ///
    /// Passed through rather than validated here. Which enzymes exist, and
    /// whether either of their sites appears in the template, are questions
    /// the worker can answer and this crate cannot -- and a second copy of the
    /// enzyme catalogue in Rust could only ever go stale.
    #[serde(default)]
    pub tails: Option<TailRequest>,
    /// A primer already on the bench, to pair one insert primer against.
    ///
    /// For screening a colony with one primer in the vector, which is the only
    /// way this assay answers whether the insert went in the right way round:
    /// two primers inside the insert give the same band either way.
    #[serde(default)]
    pub vector_primer: Option<VectorPrimerRequest>,
    /// Exact recipient vector for the executable restriction-cloning branch.
    /// The sequence is used for cut-site analysis and independent construct
    /// simulation; it is not substituted for the submitted insert template.
    #[serde(default)]
    pub cloning_vector: Option<String>,
    /// Optional human-readable recipient-vector identity.
    #[serde(default)]
    pub cloning_vector_name: Option<String>,
    /// Recipient-vector topology. Gen-1 restriction cloning executes circular
    /// vectors only so digest/ligation topology is unambiguous.
    #[serde(default)]
    pub cloning_vector_topology: Option<String>,
    /// Canonical restriction-digest workflow authority for the bench plan.
    #[serde(default)]
    pub restriction_digest_protocol: Option<String>,
    /// Canonical vector dephosphorylation workflow (`none` is explicit).
    #[serde(default)]
    pub restriction_dephosphorylation_protocol: Option<String>,
    /// Canonical ligation workflow authority.
    #[serde(default)]
    pub restriction_ligation_protocol: Option<String>,
    /// Optional protein-coding/fusion intent for the final exact insert.
    #[serde(default)]
    pub cloning_coding_intent: Option<String>,
    /// 0-based CDS start on the final insert, after any donor-region extraction.
    #[serde(default)]
    pub cloning_cds_start: Option<usize>,
    /// 0-based half-open CDS end on the final insert.
    #[serde(default)]
    pub cloning_cds_end: Option<usize>,
    /// Whether a terminal stop codon is retained or deliberately absent.
    #[serde(default)]
    pub cloning_stop_codon_policy: Option<String>,
    /// Human-readable fusion-tag identity; no sequence is invented from this label.
    #[serde(default)]
    pub cloning_fusion_tag: Option<String>,
    /// Optional amino-acid linker intent. It is not reverse-translated by this module.
    #[serde(default)]
    pub cloning_linker_aa: Option<String>,
    /// Number of coding bases already present in the recipient codon at the insertion junction.
    #[serde(default)]
    pub cloning_vector_junction_frame: Option<u8>,
    /// Assay-specific experimental/QC evidence recorded alongside the run.
    /// This evidence is provenance only and never changes sequence ranking.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
    /// Colony-PCR host class. Required only for the colony-pcr assay.
    #[serde(default)]
    pub colony_host_class: Option<String>,
    /// How crude colony material is prepared before PCR. Required for colony-pcr.
    #[serde(default)]
    pub colony_preparation: Option<String>,
    /// Canonical source-backed colony workflow or `custom-sop`.
    #[serde(default)]
    pub colony_protocol_id: Option<String>,
    /// Named vendor/SOP identity for the selected colony preparation and cycling.
    #[serde(default)]
    pub colony_protocol_name: Option<String>,
    /// Source/revision/date or other traceable authority for that colony SOP.
    #[serde(default)]
    pub colony_protocol_provenance: Option<String>,
    /// Whether the tube starts from RNA rather than DNA.
    ///
    /// Assays that accept RNA must say so explicitly. This records substrate
    /// identity and enables transcript-specific checks; Scientific-Strict does
    /// not invent an RT temperature/time or one-step/two-step programme from
    /// this boolean. A named RT chemistry/SOP is separate authority.
    #[serde(default)]
    pub from_rna: Option<bool>,
    /// Zero-based boundaries between transcript bases that at least one
    /// primer in every returned pair must span. This is an annotation, not
    /// something that can be inferred from U-to-T normalisation.
    #[serde(default)]
    pub exon_junctions: Option<Vec<usize>>,
    /// Whether the template is a circle.
    ///
    /// A plasmid has no ends, but the string somebody pastes does, and a primer
    /// sitting across the join falls in the gap between them — so which primers
    /// the specificity scan can see depends on where the file happens to begin,
    /// which is arbitrary. Saying so makes the scan wrap.
    #[serde(default)]
    pub circular: Option<bool>,
}

/// A pair search, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct FlankingPair {
    worker: Worker,
}

impl FlankingPair {
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

impl Engine for FlankingPair {
    fn id(&self) -> EngineId {
        EngineId::FlankingPair
    }

    fn accepts(&self) -> &'static [Modifier] {
        ACCEPTS
    }

    fn validate(&self, request: &serde_json::Value) -> Result<()> {
        parse(request).map(|_| ())
    }

    fn presets(&self) -> Result<Option<serde_json::Value>> {
        self.worker
            .call("presets", &serde_json::json!({}))
            .map(Some)
    }

    fn design(&self, request: serde_json::Value) -> Result<serde_json::Value> {
        let parsed = parse(&request)?;
        self.worker.call("run", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<FlankingPairRequest> {
    let parsed: FlankingPairRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

impl FlankingPairRequest {
    /// Whether this request could be run at all.
    ///
    /// Every check is the shared one from [`super::common`], so a rule means
    /// the same thing on every assay that carries the field.
    fn check(&self) -> Result<()> {
        let template_bases = check_template(&self.template, MAX_TEMPLATE_BASES)?;
        let rna_input = contains_rna_base(&self.template);
        if rna_input && self.from_rna == Some(false) {
            return Err(CoreError::InvalidRequest(
                "The template contains RNA (U bases), but `fromRna` was set to false. \
                 RNA requires reverse transcription."
                    .to_owned(),
            ));
        }
        check_target_pair(self.target_start, self.target_length)?;
        if let Some((start, length)) = self.target_start.zip(self.target_length) {
            if self.circular == Some(true) {
                // Circular intervals live in the real molecule's canonical
                // coordinate frame. They may cross the arbitrary FASTA origin
                // once, but the repeated search head used by the Python worker
                // is scaffolding rather than a second valid coordinate range.
                if start >= template_bases {
                    return Err(CoreError::InvalidRequest(format!(
                        "targetStart {start} is outside the canonical circular template frame 0..{}",
                        template_bases.saturating_sub(1)
                    )));
                }
                if length > template_bases {
                    return Err(CoreError::InvalidRequest(format!(
                        "targetLength {length} exceeds the {template_bases}-base circular molecule; a target may cross the FASTA origin once but may not require more than one traversal"
                    )));
                }
            } else {
                check_target_bounds(start, length, template_bases)?;
            }
        }
        if let Some(regions) = &self.excluded {
            if self.circular == Some(true) {
                for (index, (start, length)) in regions.iter().enumerate() {
                    let number = index + 1;
                    if *length == 0 {
                        return Err(CoreError::InvalidRequest(format!(
                            "Avoided region {number} is zero bases long, so it rules nothing out."
                        )));
                    }
                    if *start >= template_bases {
                        return Err(CoreError::InvalidRequest(format!(
                            "Avoided region {number} starts at {start}, outside the canonical circular template frame 0..{}",
                            template_bases.saturating_sub(1)
                        )));
                    }
                    if *length > template_bases {
                        return Err(CoreError::InvalidRequest(format!(
                            "Avoided region {number} is {length} bases long, longer than the {template_bases}-base circular molecule; one region may cross the FASTA origin once but may not cover more than one traversal"
                        )));
                    }
                }
            } else {
                check_excluded(regions, template_bases)?;
            }
        }
        if let Some(positions) = &self.variants {
            check_positions(positions, template_bases, "variant")?;
        }
        if let Some(how_many) = self.how_many {
            check_how_many(how_many, MAX_HOW_MANY)?;
        }
        if let Some(junctions) = &self.exon_junctions {
            if junctions.is_empty() {
                return Err(CoreError::InvalidRequest(
                    "exonJunctions must contain at least one transcript boundary".to_owned(),
                ));
            }
            if self.from_rna != Some(true) && !rna_input {
                return Err(CoreError::InvalidRequest(
                    "exonJunctions requires fromRna=true or an RNA template".to_owned(),
                ));
            }
            if self.circular == Some(true) {
                return Err(CoreError::InvalidRequest(
                    "exonJunctions cannot be combined with a circular template".to_owned(),
                ));
            }
            for (index, junction) in junctions.iter().enumerate() {
                if *junction == 0 || *junction >= template_bases {
                    return Err(CoreError::InvalidRequest(format!(
                        "exonJunctions[{index}] must be a boundary between bases 1 and {}",
                        template_bases.saturating_sub(1)
                    )));
                }
            }
            let mut sorted = junctions.clone();
            sorted.sort_unstable();
            if sorted.windows(2).any(|pair| pair[0] == pair[1]) {
                return Err(CoreError::InvalidRequest(
                    "exonJunctions must not contain duplicate boundaries".to_owned(),
                ));
            }
        }
        let assay_id = self
            .assay
            .as_ref()
            .and_then(|assay| assay.get("id"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        if let Some(host) = &self.colony_host_class {
            if !COLONY_HOST_CLASSES.contains(&host.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{host}` is not a colony host class this engine knows. It knows: {}.",
                    COLONY_HOST_CLASSES.join(", ")
                )));
            }
        }
        if let Some(preparation) = &self.colony_preparation {
            if !COLONY_PREPARATIONS.contains(&preparation.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{preparation}` is not a colony preparation branch this engine knows. It knows: {}.",
                    COLONY_PREPARATIONS.join(", ")
                )));
            }
        }
        if assay_id == "restriction-cloning" {
            let donor_region_requested = self.target_start.is_some()
                || self.target_length.is_some()
                || self.circular == Some(true);
            if donor_region_requested {
                if self.circular != Some(true)
                    || self.target_start.is_none()
                    || self.target_length.is_none()
                {
                    return Err(CoreError::InvalidRequest(
                        "restriction-cloning donor-plasmid extraction requires circular=true plus both targetStart and targetLength; otherwise submit the exact linear insert sequence".to_owned(),
                    ));
                }
                let (Some(target_start), Some(target_length)) =
                    (self.target_start, self.target_length)
                else {
                    return Err(CoreError::InvalidRequest(
                        "restriction-cloning donor coordinates are incomplete".to_owned(),
                    ));
                };
                check_target_pair(Some(target_start), Some(target_length))?;
                check_target_bounds(target_start, target_length, template_bases)?;
                if target_length == 0 || target_length > template_bases {
                    return Err(CoreError::InvalidRequest(
                        "restriction-cloning donor targetLength must be 1..template length"
                            .to_owned(),
                    ));
                }
            }
            if self
                .excluded
                .as_ref()
                .is_some_and(|regions| !regions.is_empty())
            {
                return Err(CoreError::InvalidRequest(
                    "restriction-cloning pins primers to the exact insert boundaries (submitted directly or explicitly extracted from a circular donor); excluded primer-placement regions are not executable in this branch".to_owned(),
                ));
            }
        }

        if assay_id == "restriction-cloning" {
            let vector = self.cloning_vector.as_deref().map(str::trim).filter(|value| !value.is_empty()).ok_or_else(|| {
                CoreError::InvalidRequest(
                    "restriction-cloning requires the exact `cloningVector` recipient sequence for vector-site validation and construct simulation.".to_owned(),
                )
            })?;
            check_template(vector, MAX_TEMPLATE_BASES)?;
            if self.cloning_vector_topology.as_deref() != Some("circular") {
                return Err(CoreError::InvalidRequest(
                    "restriction-cloning Gen-1 requires `cloningVectorTopology=circular`; linear recipient-vector assembly is not an executable branch."
                        .to_owned(),
                ));
            }
        } else if self.cloning_vector.is_some()
            || self.cloning_vector_name.is_some()
            || self.cloning_vector_topology.is_some()
        {
            return Err(CoreError::InvalidRequest(
                "cloningVector/cloningVectorName/cloningVectorTopology belong to the `restriction-cloning` assay.".to_owned(),
            ));
        }

        if assay_id == "restriction-cloning" {
            let digest = self.restriction_digest_protocol.as_deref().ok_or_else(|| {
                CoreError::InvalidRequest(
                    "restriction-cloning requires `restrictionDigestProtocol`; digest chemistry is independent of primer-tail geometry.".to_owned(),
                )
            })?;
            let dephosphorylation = self.restriction_dephosphorylation_protocol.as_deref().ok_or_else(|| {
                CoreError::InvalidRequest("restriction-cloning requires explicit `restrictionDephosphorylationProtocol` (`none` is valid).".to_owned())
            })?;
            let ligation = self.restriction_ligation_protocol.as_deref().ok_or_else(|| {
                CoreError::InvalidRequest(
                    "restriction-cloning requires `restrictionLigationProtocol`; ligation conditions must have a named authority.".to_owned(),
                )
            })?;
            if !RESTRICTION_DIGEST_PROTOCOLS.contains(&digest) {
                return Err(CoreError::InvalidRequest(format!(
                    "unsupported restrictionDigestProtocol `{digest}`"
                )));
            }
            if !RESTRICTION_DEPHOSPHORYLATION_PROTOCOLS.contains(&dephosphorylation) {
                return Err(CoreError::InvalidRequest(format!(
                    "unsupported restrictionDephosphorylationProtocol `{dephosphorylation}`"
                )));
            }
            if !RESTRICTION_LIGATION_PROTOCOLS.contains(&ligation) {
                return Err(CoreError::InvalidRequest(format!(
                    "unsupported restrictionLigationProtocol `{ligation}`"
                )));
            }
        } else if self.restriction_digest_protocol.is_some()
            || self.restriction_dephosphorylation_protocol.is_some()
            || self.restriction_ligation_protocol.is_some()
        {
            return Err(CoreError::InvalidRequest(
                "restrictionDigestProtocol/restrictionDephosphorylationProtocol/restrictionLigationProtocol belong to restriction-cloning.".to_owned(),
            ));
        }

        let coding_context_supplied = self.cloning_coding_intent.is_some()
            || self.cloning_cds_start.is_some()
            || self.cloning_cds_end.is_some()
            || self.cloning_stop_codon_policy.is_some()
            || self.cloning_fusion_tag.is_some()
            || self.cloning_linker_aa.is_some()
            || self.cloning_vector_junction_frame.is_some();
        if assay_id == "restriction-cloning" {
            let intent = self.cloning_coding_intent.as_deref().unwrap_or("noncoding");
            if !["noncoding", "preserve-orf", "in-frame-fusion"].contains(&intent) {
                return Err(CoreError::InvalidRequest(
                    "unsupported cloningCodingIntent".to_owned(),
                ));
            }
            let stop =
                self.cloning_stop_codon_policy
                    .as_deref()
                    .unwrap_or(if intent == "noncoding" {
                        "not-applicable"
                    } else {
                        "preserve"
                    });
            if !["not-applicable", "preserve", "remove"].contains(&stop) {
                return Err(CoreError::InvalidRequest(
                    "unsupported cloningStopCodonPolicy".to_owned(),
                ));
            }
            if intent == "noncoding" {
                if self.cloning_cds_start.is_some()
                    || self.cloning_cds_end.is_some()
                    || self.cloning_vector_junction_frame.is_some()
                    || stop != "not-applicable"
                {
                    return Err(CoreError::InvalidRequest(
                        "cloningCodingIntent=noncoding cannot carry CDS/frame settings; clear them or choose a coding intent".to_owned(),
                    ));
                }
            } else {
                let start = self.cloning_cds_start.ok_or_else(|| {
                    CoreError::InvalidRequest(
                        "coding restriction cloning requires cloningCdsStart".to_owned(),
                    )
                })?;
                let end = self.cloning_cds_end.ok_or_else(|| {
                    CoreError::InvalidRequest(
                        "coding restriction cloning requires cloningCdsEnd".to_owned(),
                    )
                })?;
                if start >= end || end > template_bases {
                    return Err(CoreError::InvalidRequest("cloningCdsStart/cloningCdsEnd must define a non-empty 0-based half-open interval within the submitted final insert/donor sequence context".to_owned()));
                }
                if stop == "not-applicable" {
                    return Err(CoreError::InvalidRequest(
                        "coding restriction cloning requires preserve/remove stop-codon policy"
                            .to_owned(),
                    ));
                }
                if intent == "in-frame-fusion" {
                    let phase = self.cloning_vector_junction_frame.ok_or_else(|| {
                        CoreError::InvalidRequest(
                            "in-frame-fusion requires cloningVectorJunctionFrame 0, 1 or 2"
                                .to_owned(),
                        )
                    })?;
                    if phase > 2 {
                        return Err(CoreError::InvalidRequest(
                            "cloningVectorJunctionFrame must be 0, 1 or 2".to_owned(),
                        ));
                    }
                } else if self.cloning_vector_junction_frame.is_some() {
                    return Err(CoreError::InvalidRequest(
                        "cloningVectorJunctionFrame is only valid for in-frame-fusion".to_owned(),
                    ));
                }
            }
            if self.cloning_linker_aa.as_deref().is_some_and(|value| {
                !value
                    .chars()
                    .all(|c| c.is_ascii_alphabetic() || c == '*' || c == '-')
            }) {
                return Err(CoreError::InvalidRequest(
                    "cloningLinkerAa must contain amino-acid letters only (plus optional * or - notation)".to_owned(),
                ));
            }
        } else if coding_context_supplied {
            return Err(CoreError::InvalidRequest(
                "cloning coding/fusion fields belong to restriction-cloning".to_owned(),
            ));
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
                if key.is_empty() || key.len() > 80 {
                    return Err(CoreError::InvalidRequest(
                        "workflowEvidence keys must contain 1-80 characters.".to_owned(),
                    ));
                }
                if !(value.is_null()
                    || value.is_boolean()
                    || value.is_number()
                    || value.is_string())
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "workflowEvidence.{key} must be a scalar value; nested arrays/objects are not accepted."
                    )));
                }
                if value.as_str().is_some_and(|text| text.len() > 8_000) {
                    return Err(CoreError::InvalidRequest(format!(
                        "workflowEvidence.{key} exceeds the 8000-character evidence limit."
                    )));
                }
            }
        }

        if assay_id == "colony-pcr" {
            let host = self
                .colony_host_class
                .as_deref()
                .ok_or_else(|| CoreError::InvalidRequest("colony-pcr requires `colonyHostClass`; crude-template handling is host-dependent.".to_owned()))?;
            let preparation = self.colony_preparation.as_deref().ok_or_else(|| {
                CoreError::InvalidRequest(
                    "colony-pcr requires `colonyPreparation`; direct transfer, liquid culture and lysate branches are not interchangeable.".to_owned(),
                )
            })?;
            let protocol_id = self.colony_protocol_id.as_deref().unwrap_or_else(|| {
                if self
                    .colony_protocol_name
                    .as_deref()
                    .is_some_and(|v| !v.trim().is_empty())
                    && self
                        .colony_protocol_provenance
                        .as_deref()
                        .is_some_and(|v| !v.trim().is_empty())
                {
                    "custom-sop"
                } else {
                    ""
                }
            });
            if !COLONY_PROTOCOLS.contains(&protocol_id) {
                return Err(CoreError::InvalidRequest(format!(
                    "colony-pcr requires a recognized `colonyProtocolId`. It knows: {}.",
                    COLONY_PROTOCOLS.join(", ")
                )));
            }
            if protocol_id == "custom-sop" {
                for (field, value) in [
                    ("colonyProtocolName", self.colony_protocol_name.as_deref()),
                    (
                        "colonyProtocolProvenance",
                        self.colony_protocol_provenance.as_deref(),
                    ),
                ] {
                    if value.map(str::trim).is_none_or(|value| value.is_empty()) {
                        return Err(CoreError::InvalidRequest(format!(
                            "colonyProtocolId=custom-sop requires non-empty `{field}` so the local/laboratory workflow remains traceable."
                        )));
                    }
                }
            } else {
                if host != "bacterial" {
                    return Err(CoreError::InvalidRequest(format!(
                        "{protocol_id} is source-backed only for bacterial colony/culture input; use custom-sop with explicit provenance for host class `{host}`."
                    )));
                }
                let allowed_preparation = match protocol_id {
                    "pcrbio-hs-taq-pb10-22-colony" => {
                        matches!(preparation, "direct-transfer" | "liquid-culture")
                    }
                    "neb-onetaq-m0482-colony"
                    | "neb-onetaq-hotstart-m0488-colony"
                    | "neb-insert-screening-e1202"
                    | "neb-onetaq-m0689-colony" => preparation == "direct-transfer",
                    _ => false,
                };
                if !allowed_preparation {
                    return Err(CoreError::InvalidRequest(format!(
                        "colony preparation `{preparation}` is not source-backed for `{protocol_id}`; select a documented preparation or custom-sop."
                    )));
                }
            }
        } else if self.colony_host_class.is_some()
            || self.colony_preparation.is_some()
            || self.colony_protocol_id.is_some()
            || self.colony_protocol_name.is_some()
            || self.colony_protocol_provenance.is_some()
        {
            return Err(CoreError::InvalidRequest(
                "colonyHostClass/colonyPreparation/colonyProtocolId/colonyProtocolName/colonyProtocolProvenance belong to the `colony-pcr` assay.".to_owned(),
            ));
        }

        let species_snapshot_supplied = self.inclusivity_panel_provenance.is_some()
            || self.background_panel_provenance.is_some()
            || self.species_panel_selection_rationale.is_some()
            || self.species_target_taxid.is_some()
            || self.species_taxonomy_snapshot.is_some()
            || self.species_database_snapshot.is_some()
            || self.species_panel_accession_manifest.is_some()
            || self.species_panel_accession_authority_manifest.is_some()
            || self.species_panel_record_metadata_manifest.is_some()
            || self.species_panel_retrieved_date.is_some();
        if assay_id == "species-specific-pcr" {
            if self.species_target_taxid.is_none_or(|taxid| taxid == 0) {
                return Err(CoreError::InvalidRequest(
                    "species-specific-pcr requires positive `speciesTargetTaxid`; taxonomy scope must be declared rather than inferred from FASTA labels."
                        .to_owned(),
                ));
            }
            for (field, value) in [
                (
                    "inclusivityPanelProvenance",
                    self.inclusivity_panel_provenance.as_deref(),
                ),
                (
                    "backgroundPanelProvenance",
                    self.background_panel_provenance.as_deref(),
                ),
                (
                    "speciesPanelSelectionRationale",
                    self.species_panel_selection_rationale.as_deref(),
                ),
                (
                    "speciesTaxonomySnapshot",
                    self.species_taxonomy_snapshot.as_deref(),
                ),
                (
                    "speciesDatabaseSnapshot",
                    self.species_database_snapshot.as_deref(),
                ),
                (
                    "speciesPanelAccessionManifest",
                    self.species_panel_accession_manifest.as_deref(),
                ),
                (
                    "speciesPanelAccessionAuthorityManifest",
                    self.species_panel_accession_authority_manifest.as_deref(),
                ),
                (
                    "speciesPanelRecordMetadataManifest",
                    self.species_panel_record_metadata_manifest.as_deref(),
                ),
                (
                    "speciesPanelRetrievedDate",
                    self.species_panel_retrieved_date.as_deref(),
                ),
            ] {
                if value.map(str::trim).is_none_or(|value| value.is_empty()) {
                    return Err(CoreError::InvalidRequest(format!(
                        "species-specific-pcr requires non-empty `{field}` so the specificity panel and its database/taxonomy snapshot are reproducible rather than inferred."
                    )));
                }
            }
            if let Some(date) = self.species_panel_retrieved_date.as_deref() {
                let bytes = date.as_bytes();
                let iso_shape = bytes.len() == 10
                    && bytes[4] == b'-'
                    && bytes[7] == b'-'
                    && bytes
                        .iter()
                        .enumerate()
                        .all(|(i, b)| i == 4 || i == 7 || b.is_ascii_digit());
                if !iso_shape {
                    return Err(CoreError::InvalidRequest(
                        "speciesPanelRetrievedDate must use ISO YYYY-MM-DD form.".to_owned(),
                    ));
                }
            }
        } else if species_snapshot_supplied {
            return Err(CoreError::InvalidRequest(
                "species panel provenance/taxonomy/database snapshot fields belong to the `species-specific-pcr` assay.".to_owned(),
            ));
        }

        if self
            .max_mismatches
            .is_some_and(|mismatches| mismatches > MAX_MISMATCHES)
        {
            return Err(CoreError::InvalidRequest(format!(
                "maxMismatches cannot exceed {MAX_MISMATCHES} for this bounded scan"
            )));
        }
        let named_overlay_count = [
            self.standard_pcr_protocol.as_deref(),
            self.qpcr_protocol.as_deref(),
            self.rpa_protocol.as_deref(),
            self.long_range_protocol.as_deref(),
            self.digital_protocol.as_deref(),
        ]
        .into_iter()
        .filter(|protocol| protocol.is_some_and(|value| value != "not-selected"))
        .count();
        if named_overlay_count > 1 {
            return Err(CoreError::InvalidRequest(
                "select only one named flanking-pair chemistry overlay".to_owned(),
            ));
        }
        if let Some(protocol) = &self.standard_pcr_protocol {
            if !STANDARD_PCR_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "protocol {protocol} is not a Standard-PCR protocol this engine knows. It knows: {}.",
                    STANDARD_PCR_PROTOCOLS.join(", ")
                )));
            }
            if protocol != "not-selected" && assay_id != "standard-pcr" {
                return Err(CoreError::InvalidRequest(
                    "a named Standard-PCR chemistry overlay requires `standard-pcr` assay"
                        .to_owned(),
                ));
            }
            if protocol == "neb-multiplex-pcr-m0284" {
                return Err(CoreError::InvalidRequest(
                    "NEB Multiplex PCR 5X Master Mix M0284 is only executable through the Standard-PCR multiplex workflow".to_owned(),
                ));
            }
        }
        if let Some(protocol) = &self.qpcr_protocol {
            if !QPCR_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "protocol {protocol} is not a qPCR/SYBR protocol this knows. It knows: {}.",
                    QPCR_PROTOCOLS.join(", ")
                )));
            }
            if protocol != "not-selected" {
                let assay_id = self
                    .assay
                    .as_ref()
                    .and_then(|assay| assay.get("id"))
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("");
                if assay_id != "qpcr-sybr" {
                    return Err(CoreError::InvalidRequest(
                        "a named dye-qPCR overlay requires `qpcr-sybr` assay".to_owned(),
                    ));
                }
                if matches!(
                    protocol.as_str(),
                    "neb-luna-one-step-rt-qpcr-e3005" | "promega-gotaq-one-step-rt-qpcr-a6020"
                ) && self.from_rna != Some(true)
                    && !rna_input
                {
                    return Err(CoreError::InvalidRequest(format!(
                        "{protocol} is modeled as a one-step RT-qPCR branch and requires `fromRna=true` or an RNA target. Use a qPCR-only chemistry for DNA/cDNA input."
                    )));
                }
            }
        }
        if assay_id == "rpa" && (self.from_rna == Some(true) || rna_input) {
            let rpa_protocol = self.rpa_protocol.as_deref().unwrap_or("not-selected");
            if rpa_protocol != "thermo-lyo-ready-rpa" {
                return Err(CoreError::InvalidRequest(
                    "RNA-RPA requires the explicitly modeled `thermo-lyo-ready-rpa` RT-RPA branch; TwistAmp Basic/Liquid Basic remain DNA-only unless a separately named RT-addition recipe is represented.".to_owned(),
                ));
            }
        }
        if assay_id == "rpa"
            && self
                .rpa_protocol
                .as_deref()
                .map(str::trim)
                .is_none_or(|protocol| protocol.is_empty() || protocol == "not-selected")
        {
            return Err(CoreError::InvalidRequest(
                "rpa requires an explicit executable `rpaProtocol`; generation 1 supports TwistAmp Basic/Liquid Basic DNA and Thermo Lyo-ready RPA/RT-RPA rather than silently assuming a chemistry or RT branch.".to_owned(),
            ));
        }
        if self.rpa_multiplex_panel.is_some() && assay_id != "rpa" {
            return Err(CoreError::InvalidRequest(
                "rpaMultiplexPanel is only valid for the RPA module.".to_owned(),
            ));
        }
        if assay_id == "rpa" {
            rpa_multiplex::validate(self.rpa_multiplex_panel.as_deref())?;
        }
        if let Some(protocol) = &self.rpa_protocol {
            if !RPA_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "protocol {protocol} is not an RPA protocol this knows. It knows: {}.",
                    RPA_PROTOCOLS.join(", ")
                )));
            }
            if protocol != "not-selected" {
                let assay_id = self
                    .assay
                    .as_ref()
                    .and_then(|assay| assay.get("id"))
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("");
                if assay_id != "rpa" {
                    return Err(CoreError::InvalidRequest(
                        "an RPA chemistry branch requires the `rpa` assay".to_owned(),
                    ));
                }
                if !RPA_EXECUTABLE_PROTOCOLS.contains(&protocol.as_str()) {
                    return Err(CoreError::InvalidRequest(
                        "the selected RPA branch is recognised for provenance but is not executable in the Generation-1 plain-ACGT two-primer contract; Exo/Nfo/Fpg/SIBA require a typed modified-oligo/nuclease/readout architecture".to_owned(),
                    ));
                }
            }
        }
        if assay_id == "long-range-pcr"
            && self
                .long_range_protocol
                .as_deref()
                .map(str::trim)
                .is_none_or(|protocol| protocol.is_empty() || protocol == "not-selected")
        {
            return Err(CoreError::InvalidRequest(
                "long-range-pcr requires explicit `longRangeProtocol`; select a reviewed named chemistry because PCRStudio does not substitute a generic long-PCR cycling recipe.".to_owned(),
            ));
        }
        if let Some(protocol) = &self.long_range_protocol {
            if !LONG_RANGE_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "protocol {protocol} is not a long-range protocol this engine knows. It knows: {}.",
                    LONG_RANGE_PROTOCOLS.join(", ")
                )));
            }
            if protocol != "not-selected" && assay_id != "long-range-pcr" {
                return Err(CoreError::InvalidRequest(
                    "a named long-range PCR overlay requires `long-range-pcr` assay".to_owned(),
                ));
            }
        }
        if let Some(value) = &self.modified_oligos {
            check_modified_oligos(value)?;
        }
        if let Some(context) = &self.flanking_numeric_context {
            let numeric = [
                ("reactionVolumeUl", context.reaction_volume_ul),
                ("primerEachUm", context.primer_each_um),
                ("primerEachNm", context.primer_each_nm),
                ("gcEnhancerPercent", context.gc_enhancer_percent),
                ("templateFractionPercent", context.template_fraction_percent),
                ("targetLengthKb", context.target_length_kb),
                (
                    "initialDenaturationTimeMin",
                    context.initial_denaturation_time_min,
                ),
                ("rpaTemperatureC", context.rpa_temperature_c),
                ("rpaTimeMin", context.rpa_time_min),
                ("rpaBstUnitsPerUl", context.rpa_bst_units_per_ul),
                ("templateInputNg", context.template_input_ng),
                ("templateInputUl", context.template_input_ul),
                (
                    "effectivePartitionVolumeNl",
                    context.effective_partition_volume_nl,
                ),
                ("colonySampleInputUl", context.colony_sample_input_ul),
            ];
            for (name, value) in numeric {
                if let Some(value) = value {
                    if !value.is_finite() || value <= 0.0 {
                        return Err(CoreError::InvalidRequest(format!(
                            "`flankingNumericContext.{name}` must be finite and greater than zero"
                        )));
                    }
                }
            }
            if context.primer_each_um.is_some() && context.primer_each_nm.is_some() {
                return Err(CoreError::InvalidRequest(
                    "choose only one of flankingNumericContext.primerEachUm or primerEachNm"
                        .to_owned(),
                ));
            }
            if let Some(value) = &context.additive {
                if !["none", "high-gc-enhancer", "yellow-sample-buffer"].contains(&value.as_str()) {
                    return Err(CoreError::InvalidRequest(
                        "unsupported flankingNumericContext.additive".to_owned(),
                    ));
                }
            }
            if context.additive.as_deref() == Some("high-gc-enhancer") && assay_id != "standard-pcr"
            {
                return Err(CoreError::InvalidRequest(
                    "high-gc-enhancer is only valid for standard-pcr".to_owned(),
                ));
            }
            if context.additive.as_deref() == Some("yellow-sample-buffer")
                && assay_id != "qpcr-sybr"
            {
                return Err(CoreError::InvalidRequest(
                    "yellow-sample-buffer is only valid for qpcr-sybr".to_owned(),
                ));
            }
            if let Some(value) = &context.cycling_profile {
                if !["protocol-default", "fast", "standard"].contains(&value.as_str()) {
                    return Err(CoreError::InvalidRequest(
                        "unsupported flankingNumericContext.cyclingProfile".to_owned(),
                    ));
                }
            }
            if let Some(value) = &context.partition_format_detail {
                if !["not-specified", "8.5k", "26k"].contains(&value.as_str()) {
                    return Err(CoreError::InvalidRequest(
                        "unsupported flankingNumericContext.partitionFormatDetail".to_owned(),
                    ));
                }
            }
            if let Some(value) = &context.preparation {
                if ![
                    "protocol-default",
                    "direct-colony",
                    "direct-transfer",
                    "liquid-culture",
                    "water-lysate",
                    "buffer-lysate",
                    "host-specific-lysis",
                    "other",
                ]
                .contains(&value.as_str())
                {
                    return Err(CoreError::InvalidRequest(
                        "unsupported flankingNumericContext.preparation".to_owned(),
                    ));
                }
            }
            if context.gc_enhancer_percent.is_some() && assay_id != "standard-pcr" {
                return Err(CoreError::InvalidRequest(
                    "GC enhancer context is only valid for standard-pcr".to_owned(),
                ));
            }
            if context.target_length_kb.is_some() && assay_id != "long-range-pcr" {
                return Err(CoreError::InvalidRequest(
                    "targetLengthKb context is only valid for long-range-pcr".to_owned(),
                ));
            }
            if context.partition_format_detail.is_some() && assay_id != "digital-pcr" {
                return Err(CoreError::InvalidRequest(
                    "partitionFormatDetail context is only valid for digital-pcr".to_owned(),
                ));
            }
            if context.initial_denaturation_time_min.is_some() && assay_id != "colony-pcr" {
                return Err(CoreError::InvalidRequest(
                    "initialDenaturationTimeMin context is only valid for colony-pcr".to_owned(),
                ));
            }
            if (context.rpa_temperature_c.is_some()
                || context.rpa_time_min.is_some()
                || context.rpa_bst_units_per_ul.is_some()
                || context.rpa_multiplex.is_some())
                && assay_id != "rpa"
            {
                return Err(CoreError::InvalidRequest(
                    "RPA numeric context is only valid for rpa".to_owned(),
                ));
            }
            if context.template_fraction_percent.is_some() && assay_id != "qpcr-sybr" {
                return Err(CoreError::InvalidRequest(
                    "templateFractionPercent context is only valid for qpcr-sybr".to_owned(),
                ));
            }
            if context.cycling_profile.is_some() && assay_id != "qpcr-sybr" {
                return Err(CoreError::InvalidRequest(
                    "cyclingProfile context is only valid for qpcr-sybr".to_owned(),
                ));
            }
            if let Some(value) = &context.template_class {
                if ![
                    "genomic",
                    "hmw-genomic",
                    "plasmid",
                    "lambda",
                    "lower-complexity",
                    "cDNA",
                    "RNA",
                    "crude",
                    "other",
                ]
                .contains(&value.as_str())
                {
                    return Err(CoreError::InvalidRequest(
                        "unsupported flankingNumericContext.templateClass".to_owned(),
                    ));
                }
            }
            if let Some(value) = &context.qpcr_instrument_profile {
                if !QPCR_INSTRUMENT_PROFILES.contains(&value.as_str()) {
                    return Err(CoreError::InvalidRequest(format!(
                        "unsupported flankingNumericContext.qpcrInstrumentProfile; known values: {}",
                        QPCR_INSTRUMENT_PROFILES.join(", ")
                    )));
                }
                if assay_id != "qpcr-sybr" {
                    return Err(CoreError::InvalidRequest(
                        "qpcrInstrumentProfile is only valid for qpcr-sybr".to_owned(),
                    ));
                }
            }
            if let Some(value) = &context.digital_consumable_id {
                if !DIGITAL_CONSUMABLE_IDS.contains(&value.as_str()) {
                    return Err(CoreError::InvalidRequest(format!(
                        "unsupported flankingNumericContext.digitalConsumableId; known values: {}",
                        DIGITAL_CONSUMABLE_IDS.join(", ")
                    )));
                }
                if assay_id != "digital-pcr" {
                    return Err(CoreError::InvalidRequest(
                        "digitalConsumableId is only valid for digital-pcr".to_owned(),
                    ));
                }
            }
            if (context.effective_partition_volume_nl.is_some()
                || context.fragmentation_enzyme.is_some())
                && assay_id != "digital-pcr"
            {
                return Err(CoreError::InvalidRequest(
                    "digital partition/fragmentation context is only valid for digital-pcr"
                        .to_owned(),
                ));
            }
            if context.colony_sample_input_ul.is_some() && assay_id != "colony-pcr" {
                return Err(CoreError::InvalidRequest(
                    "colonySampleInputUl is only valid for colony-pcr".to_owned(),
                ));
            }
            if context.hmw_template_verified.is_some() && assay_id != "long-range-pcr" {
                return Err(CoreError::InvalidRequest(
                    "hmwTemplateVerified is only valid for long-range-pcr".to_owned(),
                ));
            }
            if context.primer_each_nm.is_some()
                && !["qpcr-sybr", "rpa", "digital-pcr"].contains(&assay_id)
            {
                return Err(CoreError::InvalidRequest(
                    "primerEachNm context is not valid for this flanking assay".to_owned(),
                ));
            }
        }
        if let Some(protocol) = &self.digital_protocol {
            if !DIGITAL_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "protocol {protocol} is not a digital-PCR protocol this knows. It knows: {}.",
                    DIGITAL_PROTOCOLS.join(", ")
                )));
            }
            if protocol != "not-selected" && assay_id != "digital-pcr" {
                return Err(CoreError::InvalidRequest(
                    "a named digital-PCR overlay requires `digital-pcr` assay".to_owned(),
                ));
            }
        }
        if let Some(format) = &self.digital_partition_format {
            if !DIGITAL_PARTITION_FORMATS.contains(&format.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{format}` is not a digital-PCR partition format this engine knows. It knows: {}.",
                    DIGITAL_PARTITION_FORMATS.join(", ")
                )));
            }
        }
        if let Some(platform_id) = &self.digital_platform_id {
            if !DIGITAL_PLATFORM_IDS.contains(&platform_id.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{platform_id}` is not a digital-PCR platform id this engine knows. It knows: {}.",
                    DIGITAL_PLATFORM_IDS.join(", ")
                )));
            }
        }
        if assay_id == "digital-pcr" {
            if let (Some(platform_id), Some(context)) =
                (&self.digital_platform_id, &self.flanking_numeric_context)
            {
                if let Some(consumable_id) = &context.digital_consumable_id {
                    let compatible =
                        DIGITAL_CONSUMABLE_PLATFORM_PAIRS
                            .iter()
                            .any(|(consumable, platform)| {
                                *consumable == consumable_id.as_str()
                                    && *platform == platform_id.as_str()
                            });
                    if !compatible {
                        return Err(CoreError::InvalidRequest(format!(
                            "digitalConsumableId={consumable_id} is not source-backed for digitalPlatformId={platform_id}."
                        )));
                    }
                }
            }
        }
        if let Some(state) = &self.digital_fragmentation_state {
            if !DIGITAL_FRAGMENTATION_STATES.contains(&state.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{state}` is not a digital-PCR fragmentation state this engine knows. It knows: {}.",
                    DIGITAL_FRAGMENTATION_STATES.join(", ")
                )));
            }
        }
        if assay_id == "digital-pcr" {
            if self.digital_partition_format.is_none() {
                return Err(CoreError::InvalidRequest(
                    "digital-pcr requires `digitalPartitionFormat`; droplet/chip/chamber assays are not interchangeable.".to_owned(),
                ));
            }
            let platform_id = self.digital_platform_id.as_deref().ok_or_else(|| {
                CoreError::InvalidRequest(
                    "digital-pcr requires `digitalPlatformId`; named and other validated platforms must not be inferred from free text.".to_owned(),
                )
            })?;
            let platform_route = DIGITAL_PLATFORM_ROUTES
                .iter()
                .find_map(|(known_id, route)| (*known_id == platform_id).then_some(*route))
                .ok_or_else(|| {
                    CoreError::InvalidRequest(format!(
                        "digital platform routing authority is incomplete for `{platform_id}`."
                    ))
                })?;
            if platform_route == "pair-probe" {
                return Err(CoreError::InvalidRequest(
                    "The selected digital platform is recognized, but its current validated chemistry is probe-oriented; route this assay to the Pair+Probe digital module rather than executing it in dye-based Flanking.".to_owned(),
                ));
            }
            if platform_id == "other-validated" {
                if self
                    .digital_platform_name
                    .as_deref()
                    .is_none_or(|value| value.trim().is_empty())
                {
                    return Err(CoreError::InvalidRequest(
                        "digitalPlatformName is required when digitalPlatformId is `other-validated`.".to_owned(),
                    ));
                }
            } else {
                let canonical = DIGITAL_PLATFORM_CANONICAL_NAMES
                    .iter()
                    .find(|(known_id, _)| *known_id == platform_id)
                    .map(|(_, name)| *name)
                    .ok_or_else(|| {
                        CoreError::InvalidRequest(format!(
                            "digital platform authority is incomplete for `{platform_id}`."
                        ))
                    })?;
                if let Some(name) = self.digital_platform_name.as_deref() {
                    let normalized = name.trim().to_ascii_lowercase();
                    if !normalized.is_empty()
                        && !DIGITAL_PLATFORM_NAME_ALIASES
                            .iter()
                            .any(|(known_id, alias)| {
                                *known_id == platform_id && *alias == normalized.as_str()
                            })
                    {
                        return Err(CoreError::InvalidRequest(format!(
                            "digitalPlatformId `{platform_id}` ({canonical}) cannot be combined with a different digitalPlatformName."
                        )));
                    }
                }
            }
            if self.digital_fragmentation_state.is_none() {
                return Err(CoreError::InvalidRequest(
                    "digital-pcr requires explicit `digitalFragmentationState`; fragmentation is platform/template-specific and cannot be inferred.".to_owned(),
                ));
            }
            digital_multiplex::validate(
                self.digital_multiplex_mode.as_deref(),
                self.digital_multiplex_panel.as_deref(),
                platform_id,
                self.digital_instrument_model.as_deref(),
                self.digital_protocol.as_deref(),
            )?;
            if let Some(protocol_id) = self.digital_protocol.as_deref() {
                if protocol_id != "not-selected" {
                    let mapped = DIGITAL_PROTOCOL_PLATFORM_PAIRS
                        .iter()
                        .any(|(protocol, _)| *protocol == protocol_id);
                    if mapped
                        && !DIGITAL_PROTOCOL_PLATFORM_PAIRS
                            .iter()
                            .any(|(protocol, platform)| {
                                *protocol == protocol_id && *platform == platform_id
                            })
                    {
                        return Err(CoreError::InvalidRequest(format!(
                            "digitalProtocol `{protocol_id}` is not source-backed for digitalPlatformId `{platform_id}`."
                        )));
                    }
                }
            }
            if self.digital_protocol.as_deref() == Some("bio-rad-qx200-evagreen")
                && self.digital_partition_format.as_deref() != Some("droplet")
            {
                return Err(CoreError::InvalidRequest(
                    "The reviewed Bio-Rad EvaGreen chemistry for QX200/QX600/QX ONE is a droplet-dPCR overlay; `digitalPartitionFormat` must be `droplet`."
                        .to_owned(),
                ));
            }
            if matches!(
                self.digital_protocol.as_deref(),
                Some("bio-rad-qx700-naica-evagreen" | "bio-rad-qx700-evagreen-supermix")
            ) && self.digital_partition_format.as_deref() != Some("droplet")
            {
                return Err(CoreError::InvalidRequest(
                    "The selected Bio-Rad EvaGreen chemistry is a droplet-dPCR overlay; `digitalPartitionFormat` must be `droplet`.".to_owned(),
                ));
            }
            if matches!(
                self.digital_protocol.as_deref(),
                Some("qiagen-qiacuity-eg" | "qiagen-qiacuity-onestep-advanced-eg")
            ) {
                if self.digital_platform_id.as_deref() != Some("qiagen-qiacuity") {
                    return Err(CoreError::InvalidRequest(
                        "The selected QIAcuity chemistry requires `digitalPlatformId=qiagen-qiacuity`.".to_owned(),
                    ));
                }
                if self.digital_partition_format.as_deref() != Some("chamber") {
                    return Err(CoreError::InvalidRequest(
                        "The selected QIAcuity chemistry uses fixed Nanoplate microchambers; `digitalPartitionFormat` must be `chamber`.".to_owned(),
                    ));
                }
            }
        } else if self.digital_partition_format.is_some()
            || self.digital_platform_id.is_some()
            || self.digital_platform_name.is_some()
            || self.digital_fragmentation_state.is_some()
            || self.digital_multiplex_mode.is_some()
            || self.digital_multiplex_panel.is_some()
            || self.digital_run_evidence.is_some()
        {
            return Err(CoreError::InvalidRequest(
                "digitalPartitionFormat/digitalPlatformId/digitalPlatformName/digitalFragmentationState/digitalMultiplexMode/digitalMultiplexPanel/digitalRunEvidence belong to the `digital-pcr` assay.".to_owned(),
            ));
        }
        if assay_id == "restriction-cloning" && self.tails.is_none() {
            return Err(CoreError::InvalidRequest(
                "restriction-cloning requires an explicit two-ended restriction-tail strategy; bare PCR primers are not an executable cloning product."
                    .to_owned(),
            ));
        }
        if let Some(tails) = &self.tails {
            let forward_named = tails
                .forward_enzyme
                .as_deref()
                .is_some_and(|value| !value.trim().is_empty());
            let reverse_named = tails
                .reverse_enzyme
                .as_deref()
                .is_some_and(|value| !value.trim().is_empty());
            if forward_named != reverse_named {
                return Err(CoreError::InvalidRequest(
                    "restriction tails require both forwardEnzyme and reverseEnzyme, or neither"
                        .to_owned(),
                ));
            }
            if assay_id == "restriction-cloning" && !forward_named {
                return Err(CoreError::InvalidRequest(
                    "restriction-cloning requires an enzyme on both primer ends; an untailed pair is diagnostic PCR, not a supplier-ready restriction-cloning design.".to_owned(),
                ));
            }
            if forward_named {
                if tails.tail_protocol.as_deref() != Some("neb-general-6bp") {
                    return Err(CoreError::InvalidRequest(
                        "named restriction tails require tailProtocol=`neb-general-6bp` in the Generation-1 Scientific-Strict branch".to_owned(),
                    ));
                }
                if tails.protective_bases.is_some_and(|bases| bases != 6) {
                    return Err(CoreError::InvalidRequest(
                        "protectiveBases must be 6 for tailProtocol=`neb-general-6bp`; another value requires a separately named supplier/enzyme-specific branch".to_owned(),
                    ));
                }
                for (field, value) in [
                    (
                        "forwardProtectiveSequence",
                        tails.forward_protective_sequence.as_deref(),
                    ),
                    (
                        "reverseProtectiveSequence",
                        tails.reverse_protective_sequence.as_deref(),
                    ),
                ] {
                    let Some(value) = value.map(str::trim).filter(|value| !value.is_empty()) else {
                        return Err(CoreError::InvalidRequest(format!(
                            "{field} is required: the NEB six-base rule defines length but not a universal protective sequence, so Scientific-Strict will not invent one"
                        )));
                    };
                    if value.len() != 6
                        || !value.bytes().all(|base| {
                            matches!(base.to_ascii_uppercase(), b'A' | b'C' | b'G' | b'T')
                        })
                    {
                        return Err(CoreError::InvalidRequest(format!(
                            "{field} must be exactly six explicit A/C/G/T bases for tailProtocol=`neb-general-6bp`"
                        )));
                    }
                }
            }
        }
        Ok(())
    }

    /// This request in the worker's own vocabulary.
    ///
    /// The wire speaks camelCase because the rest of the API does; the worker
    /// speaks snake_case because Python does. Translating here, once and
    /// visibly, is what stops a field being accepted at the edge and silently
    /// ignored at the far end -- which is a run whose settings are not the
    /// settings that were asked for.
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
        put("target_start", self.target_start.map(Into::into));
        put("target_length", self.target_length.map(Into::into));
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("assay", self.assay.clone());
        put(
            "standard_pcr_protocol",
            self.standard_pcr_protocol.clone().map(Into::into),
        );
        put("qpcr_protocol", self.qpcr_protocol.clone().map(Into::into));
        put("rpa_protocol", self.rpa_protocol.clone().map(Into::into));
        put(
            "rpa_multiplex_panel",
            self.rpa_multiplex_panel
                .as_ref()
                .and_then(|panel| serde_json::to_value(panel).ok()),
        );
        put(
            "long_range_protocol",
            self.long_range_protocol.clone().map(Into::into),
        );
        put(
            "digital_protocol",
            self.digital_protocol.clone().map(Into::into),
        );
        put(
            "flanking_numeric_context",
            self.flanking_numeric_context
                .as_ref()
                .and_then(|context| serde_json::to_value(context).ok()),
        );
        put("modified_oligos", self.modified_oligos.clone());
        put(
            "digital_partition_format",
            self.digital_partition_format.clone().map(Into::into),
        );
        put(
            "digital_platform_id",
            self.digital_platform_id.clone().map(Into::into),
        );
        let digital_platform_name = self.digital_platform_name.clone().or_else(|| {
            self.digital_platform_id.as_deref().and_then(|id| {
                DIGITAL_PLATFORM_CANONICAL_NAMES
                    .iter()
                    .find(|(known_id, _)| *known_id == id)
                    .map(|(_, name)| (*name).to_owned())
            })
        });
        put(
            "digital_platform_name",
            digital_platform_name.map(Into::into),
        );
        put(
            "digital_instrument_model",
            self.digital_instrument_model.clone().map(Into::into),
        );
        put(
            "digital_fragmentation_state",
            self.digital_fragmentation_state.clone().map(Into::into),
        );
        put(
            "digital_multiplex_mode",
            self.digital_multiplex_mode.clone().map(Into::into),
        );
        put(
            "digital_multiplex_panel",
            self.digital_multiplex_panel
                .as_ref()
                .and_then(|panel| serde_json::to_value(panel).ok()),
        );
        put("digital_run_evidence", self.digital_run_evidence.clone());
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("background", self.background.clone().map(Into::into));
        put("inclusivity", self.inclusivity.clone().map(Into::into));
        put(
            "inclusivity_panel_provenance",
            self.inclusivity_panel_provenance.clone().map(Into::into),
        );
        put(
            "background_panel_provenance",
            self.background_panel_provenance.clone().map(Into::into),
        );
        put(
            "species_panel_selection_rationale",
            self.species_panel_selection_rationale
                .clone()
                .map(Into::into),
        );
        put(
            "species_target_taxid",
            self.species_target_taxid.map(Into::into),
        );
        put(
            "species_taxonomy_snapshot",
            self.species_taxonomy_snapshot.clone().map(Into::into),
        );
        put(
            "species_database_snapshot",
            self.species_database_snapshot.clone().map(Into::into),
        );
        put(
            "species_panel_accession_manifest",
            self.species_panel_accession_manifest
                .clone()
                .map(Into::into),
        );
        put(
            "species_panel_accession_authority_manifest",
            self.species_panel_accession_authority_manifest
                .clone()
                .map(Into::into),
        );
        put(
            "species_panel_record_metadata_manifest",
            self.species_panel_record_metadata_manifest
                .clone()
                .map(Into::into),
        );
        put(
            "species_panel_retrieved_date",
            self.species_panel_retrieved_date.clone().map(Into::into),
        );
        put("max_mismatches", self.max_mismatches.map(Into::into));
        put("circular", self.circular.map(Into::into));
        put("how_many", self.how_many.map(Into::into));
        put(
            "colony_host_class",
            self.colony_host_class.clone().map(Into::into),
        );
        put(
            "colony_preparation",
            self.colony_preparation.clone().map(Into::into),
        );
        put(
            "colony_protocol_id",
            self.colony_protocol_id.clone().map(Into::into),
        );
        put(
            "colony_protocol_name",
            self.colony_protocol_name.clone().map(Into::into),
        );
        put(
            "colony_protocol_provenance",
            self.colony_protocol_provenance.clone().map(Into::into),
        );
        put("excluded", excluded_to_worker(self.excluded.as_ref()));
        put(
            "variants",
            self.variants
                .as_ref()
                .map(|positions| json!(positions.clone())),
        );

        // Translated field by field like the rest, rather than passed through:
        // the wire speaks camelCase and the worker speaks snake_case, and a
        // block that skipped this step would arrive with names the worker
        // silently ignores -- which reads, from the outside, exactly like a
        // request that asked for no tails at all.
        put(
            "tails",
            self.tails.as_ref().map(|tails| {
                let mut block = serde_json::Map::new();
                if let Some(protocol) = &tails.tail_protocol {
                    block.insert("tail_protocol".into(), protocol.clone().into());
                }
                if let Some(name) = &tails.forward_enzyme {
                    block.insert("forward_enzyme".into(), name.clone().into());
                }
                if let Some(name) = &tails.reverse_enzyme {
                    block.insert("reverse_enzyme".into(), name.clone().into());
                }
                if let Some(bases) = tails.protective_bases {
                    block.insert("protective_bases".into(), bases.into());
                }
                if let Some(sequence) = &tails.forward_protective_sequence {
                    block.insert(
                        "forward_protective_sequence".into(),
                        sequence.clone().into(),
                    );
                }
                if let Some(sequence) = &tails.reverse_protective_sequence {
                    block.insert(
                        "reverse_protective_sequence".into(),
                        sequence.clone().into(),
                    );
                }
                serde_json::Value::Object(block)
            }),
        );

        put(
            "cloning_vector",
            self.cloning_vector.clone().map(Into::into),
        );
        put(
            "cloning_vector_name",
            self.cloning_vector_name.clone().map(Into::into),
        );
        put(
            "cloning_vector_topology",
            self.cloning_vector_topology.clone().map(Into::into),
        );
        put(
            "restriction_digest_protocol",
            self.restriction_digest_protocol.clone().map(Into::into),
        );
        put(
            "restriction_dephosphorylation_protocol",
            self.restriction_dephosphorylation_protocol
                .clone()
                .map(Into::into),
        );
        put(
            "restriction_ligation_protocol",
            self.restriction_ligation_protocol.clone().map(Into::into),
        );
        put(
            "cloning_coding_intent",
            self.cloning_coding_intent.clone().map(Into::into),
        );
        put("cloning_cds_start", self.cloning_cds_start.map(Into::into));
        put("cloning_cds_end", self.cloning_cds_end.map(Into::into));
        put(
            "cloning_stop_codon_policy",
            self.cloning_stop_codon_policy.clone().map(Into::into),
        );
        put(
            "cloning_fusion_tag",
            self.cloning_fusion_tag.clone().map(Into::into),
        );
        put(
            "cloning_linker_aa",
            self.cloning_linker_aa.clone().map(Into::into),
        );
        put(
            "cloning_vector_junction_frame",
            self.cloning_vector_junction_frame.map(Into::into),
        );
        put("workflow_evidence", self.workflow_evidence.clone());

        put("from_rna", self.from_rna.map(Into::into));
        put(
            "exon_junctions",
            self.exon_junctions
                .as_ref()
                .map(|junctions| json!(junctions.clone())),
        );
        put(
            "vector_primer",
            self.vector_primer.as_ref().map(|vector| {
                let mut block = serde_json::Map::new();
                if let Some(name) = &vector.name {
                    block.insert("name".into(), name.clone().into());
                }
                if let Some(sequence) = &vector.sequence {
                    block.insert("sequence".into(), sequence.clone().into());
                }
                if let Some(end) = &vector.reads_into {
                    block.insert("reads_into".into(), end.clone().into());
                }
                if let Some(count) = vector.how_many {
                    block.insert("how_many".into(), count.into());
                }
                if let Some(plasmid) = &vector.vector {
                    block.insert("vector".into(), plasmid.clone().into());
                }
                serde_json::Value::Object(block)
            }),
        );

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
#[path = "flanking_pair_digital_tests.rs"]
mod digital_tests;

#[cfg(test)]
#[path = "flanking_pair_tests.rs"]
mod tests;
