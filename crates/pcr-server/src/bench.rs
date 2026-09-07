//! What is already on the bench, and what a set of reactions does together.
//!
//! Four endpoints that belong to no single engine.
//!
//! Two of them answer questions about things somebody already has: which
//! restriction enzymes could open a region they are holding, and which of the
//! universal primers in their freezer actually sit in the vector they are
//! using. Both refuse to answer in the abstract — an enzyme is ranked against
//! the sequence supplied, and a primer is placed in the vector supplied,
//! because a plasmid on a bench is rarely the one in the catalogue.
//!
//! A third answers the question a design tool is not usually asked and people
//! most often have: *these are the primers I was given — are they any good?*
//! Nobody is going to redesign them, and somebody is about to spend a week on
//! them.
//!
//! The last is multiplex, which is a modifier rather than an engine and so
//! has nowhere else to live. It is checked against the assay it is asked for:
//! not every assay can be multiplexed, and the registry already knows which.

use axum::extract::{Path, State};
use axum::routing::post;
use axum::{Json, Router};
use pcr_core::{CoreError, EngineId, Modifier, Registry, Worker};
use serde::Deserialize;
use std::sync::Arc;

use crate::error::ApiError;
use crate::gate::Gate;
use crate::http_routes;
use crate::routes::{assay_payload, ensure_release_executable, validate_requirements};

/// What these endpoints need: a worker, the catalogue to check against, and
/// the gate that bounds how many workers run at once.
#[derive(Clone)]
pub struct BenchState {
    worker: Worker,
    registry: Registry,
    gate: Arc<Gate>,
}

/// A region to look for restriction sites in.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct EnzymeRequest {
    /// The region somebody is holding.
    pub template: String,
    /// A larger sequence to estimate fragment sizes from, when the region is
    /// too short to say anything useful. The plasmid or genome it came from.
    #[serde(default)]
    pub background: Option<String>,
    /// Which question is being asked of the catalogue.
    ///
    /// `inverse-flank` for standard two-flank inverse PCR, `absent` for
    /// cloning, or `open-once` only for a separately modelled one-cut
    /// workflow. The scientific question is required and is never inferred.
    pub purpose: String,
}

/// A pair somebody already has, and what to check it against.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CheckRequest {
    /// Optional canonical module profile whose assay envelope should be used.
    #[serde(default)]
    pub module_id: Option<String>,
    /// The sequence these primers were made for. Required: a primer against
    /// the wrong template measures exactly as well as one against the right
    /// template, right up until the reaction produces nothing.
    pub template: String,
    /// Explicit interpretation of lowercase template bases. Scientific-Strict
    /// refuses lowercase input when this is absent rather than guessing from
    /// the percentage of lowercase sequence.
    #[serde(default)]
    pub lowercase_masking: Option<bool>,
    /// The forward primer, as it would be ordered.
    pub left: String,
    /// The reverse primer, likewise. Which is which is read from the strand
    /// each one sits on rather than from these names, so a pair pasted the
    /// other way round gives the same answer.
    pub right: String,
    /// Sequence they must not also amplify.
    #[serde(default)]
    pub background: Option<String>,
    /// The window to hold them to, which is rarely the default one: these
    /// primers were made for a reaction somebody else chose.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// What the product is for, which sets the window they are held to.
    #[serde(default)]
    pub purpose: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// Whole-primer mismatch budget for specificity-v5 discovery.
    #[serde(default)]
    pub max_mismatches: Option<u8>,
}

/// A vector to place the universal primers in.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct VectorRequest {
    /// The vector actually in use. Without it this returns the catalogue and
    /// says so, because a primer's position in the published plasmid is not a
    /// fact about the derivative on somebody's bench.
    #[serde(default)]
    pub vector: Option<String>,
    /// What to call it in the answer.
    #[serde(default)]
    pub vector_name: Option<String>,
    /// Salt and oligo concentrations, so the melting temperatures quoted are
    /// the ones this reaction would see.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
}

/// Run one worker command for a bench endpoint, off the async runtime's
/// threads and under the shared permit ceiling.
async fn ask_worker(
    state: BenchState,
    command: &'static str,
    request: serde_json::Value,
) -> Result<serde_json::Value, ApiError> {
    Ok(state
        .gate
        .run(move || state.worker.call(command, &request))
        .await?)
}

async fn rank_enzymes(
    State(state): State<BenchState>,
    Json(request): Json<EnzymeRequest>,
) -> Result<Json<serde_json::Value>, ApiError> {
    if request.template.trim().is_empty() {
        return Err(CoreError::InvalidRequest(
            "No sequence was given to look for restriction sites in.".to_owned(),
        )
        .into());
    }
    let request = serde_json::json!({
        "template": request.template,
        "background": request.background,
        "purpose": request.purpose,
    });
    Ok(Json(ask_worker(state, "enzymes", request).await?))
}

async fn place_vector_primers(
    State(state): State<BenchState>,
    Json(request): Json<VectorRequest>,
) -> Result<Json<serde_json::Value>, ApiError> {
    let request = serde_json::json!({
        "vector": request.vector,
        "vector_name": request.vector_name,
        "conditions": request.conditions,
    });
    Ok(Json(ask_worker(state, "vector_primers", request).await?))
}

async fn check_pair(
    State(state): State<BenchState>,
    Json(request): Json<CheckRequest>,
) -> Result<Json<serde_json::Value>, ApiError> {
    if request.template.trim().is_empty() {
        return Err(CoreError::InvalidRequest(
            "A pair can only be checked against the template it was made for.".to_owned(),
        )
        .into());
    }
    let assay = if let Some(module_id) = request.module_id.as_deref() {
        let profile = state.registry.profile(module_id)?.clone();
        ensure_release_executable(&profile)?;
        if profile.engine != EngineId::FlankingPair {
            return Err(CoreError::InvalidRequest(format!(
                "existing-pair evaluation currently accepts flanking-pair assays; `{}` uses {}",
                profile.id,
                profile.engine.label()
            ))
            .into());
        }
        Some(assay_payload(&profile))
    } else {
        None
    };
    let request = serde_json::json!({
        "template": request.template,
        "lowercase_masking": request.lowercase_masking,
        "left": request.left,
        "right": request.right,
        "background": request.background,
        "constraints": request.constraints,
        "polymerase": request.polymerase,
        "purpose": request.purpose,
        "conditions": request.conditions,
        "max_mismatches": request.max_mismatches,
        "assay": assay,
    });
    Ok(Json(ask_worker(state, "check", request).await?))
}

const MULTIPLEX_PUBLIC_FIELDS: &[&str] = &[
    "readout",
    "readoutProfile",
    "fromRna",
    "standardPcrProtocol",
    "colonyHostClass",
    "colonyPreparation",
    "colonyProtocolId",
    "colonyProtocolName",
    "colonyProtocolProvenance",
    "targets",
    "candidatesPerTarget",
    "perTube",
    "rounds",
    "seed",
    "optimizerMode",
];

const MULTIPLEX_TARGET_PUBLIC_FIELDS: &[&str] = &[
    "name",
    "template",
    "background",
    "inclusivity",
    "inclusivityPanelProvenance",
    "backgroundPanelProvenance",
    "speciesPanelSelectionRationale",
    "speciesTargetTaxid",
    "speciesTaxonomySnapshot",
    "speciesDatabaseSnapshot",
    "speciesPanelAccessionManifest",
    "speciesPanelRecordMetadataManifest",
    "speciesPanelRetrievedDate",
    "constraints",
    "tube",
    "primerConcentrationNm",
    "empiricalEvidenceRef",
];

fn validate_multiplex_outer_fields(
    object: &serde_json::Map<String, serde_json::Value>,
) -> Result<(), CoreError> {
    let mut unknown = object
        .keys()
        .filter(|key| !MULTIPLEX_PUBLIC_FIELDS.contains(&key.as_str()))
        .cloned()
        .collect::<Vec<_>>();
    unknown.sort();
    if !unknown.is_empty() {
        return Err(CoreError::InvalidRequest(format!(
            "unknown multiplex request field(s): {}",
            unknown.join(", ")
        )));
    }
    Ok(())
}

fn validate_multiplex_target_fields(
    index: usize,
    object: &serde_json::Map<String, serde_json::Value>,
) -> Result<(), CoreError> {
    let mut unknown = object
        .keys()
        .filter(|key| !MULTIPLEX_TARGET_PUBLIC_FIELDS.contains(&key.as_str()))
        .cloned()
        .collect::<Vec<_>>();
    unknown.sort();
    if !unknown.is_empty() {
        return Err(CoreError::InvalidRequest(format!(
            "multiplex target {} has unsupported field(s): {}. Design that target separately or add an explicit set-level contract before multiplexing it.",
            index + 1,
            unknown.join(", ")
        )));
    }
    Ok(())
}

fn validate_multiplex_targets_shape(
    object: &serde_json::Map<String, serde_json::Value>,
) -> Result<(), CoreError> {
    let Some(value) = object.get("targets") else {
        return Err(CoreError::InvalidRequest(
            "multiplex requests require a `targets` array".to_owned(),
        ));
    };
    let Some(targets) = value.as_array() else {
        return Err(CoreError::InvalidRequest(
            "multiplex `targets` must be an array".to_owned(),
        ));
    };
    if !(2..=32).contains(&targets.len()) {
        return Err(CoreError::InvalidRequest(format!(
            "multiplex requests require 2 to 32 targets; {} supplied",
            targets.len()
        )));
    }
    Ok(())
}

fn take_multiplex_from_rna(
    object: &mut serde_json::Map<String, serde_json::Value>,
) -> Result<bool, CoreError> {
    match object.remove("fromRna") {
        None => Ok(false),
        Some(value) => value.as_bool().ok_or_else(|| {
            CoreError::InvalidRequest("fromRna must be a boolean when supplied".to_owned())
        }),
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ColonyMultiplexContext {
    host_class: String,
    preparation: String,
    protocol_id: String,
    protocol_name: Option<String>,
    protocol_provenance: Option<String>,
}

fn take_colony_multiplex_context(
    module_id: &str,
    object: &mut serde_json::Map<String, serde_json::Value>,
) -> Result<Option<ColonyMultiplexContext>, CoreError> {
    const FIELDS: &[&str] = &[
        "colonyHostClass",
        "colonyPreparation",
        "colonyProtocolId",
        "colonyProtocolName",
        "colonyProtocolProvenance",
    ];
    let any_present = FIELDS.iter().any(|key| object.contains_key(*key));
    if module_id != "colony-pcr" {
        if any_present {
            return Err(CoreError::InvalidRequest(
                "colonyHostClass/colonyPreparation/colonyProtocolId/colonyProtocolName/colonyProtocolProvenance are only valid when multiplexing colony-pcr.".to_owned(),
            ));
        }
        return Ok(None);
    }

    let take_required_text = |object: &mut serde_json::Map<String, serde_json::Value>,
                              key: &str|
     -> Result<String, CoreError> {
        let Some(value) = object.remove(key) else {
            return Err(CoreError::InvalidRequest(format!(
                "colony-pcr multiplexing requires shared `{key}`"
            )));
        };
        let Some(value) = value
            .as_str()
            .map(str::trim)
            .filter(|value| !value.is_empty())
        else {
            return Err(CoreError::InvalidRequest(format!(
                "colony-pcr multiplexing requires `{key}` to be non-empty text"
            )));
        };
        Ok(value.to_owned())
    };

    let host_class = take_required_text(object, "colonyHostClass")?;
    let preparation = take_required_text(object, "colonyPreparation")?;
    let protocol_id = take_required_text(object, "colonyProtocolId")?;
    let protocol_name = object.remove("colonyProtocolName").and_then(|v| {
        v.as_str()
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .map(str::to_owned)
    });
    let protocol_provenance = object.remove("colonyProtocolProvenance").and_then(|v| {
        v.as_str()
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .map(str::to_owned)
    });
    if protocol_id == "custom-sop" && (protocol_name.is_none() || protocol_provenance.is_none()) {
        return Err(CoreError::InvalidRequest(
            "colonyProtocolId=custom-sop requires colonyProtocolName and colonyProtocolProvenance in multiplex mode.".to_owned(),
        ));
    }

    Ok(Some(ColonyMultiplexContext {
        host_class,
        preparation,
        protocol_id,
        protocol_name,
        protocol_provenance,
    }))
}

fn take_standard_pcr_multiplex_protocol(
    module_id: &str,
    object: &mut serde_json::Map<String, serde_json::Value>,
) -> Result<Option<String>, CoreError> {
    let present = object.contains_key("standardPcrProtocol");
    if module_id != "standard-pcr" {
        if present {
            return Err(CoreError::InvalidRequest(
                "standardPcrProtocol is only valid when multiplexing standard-pcr.".to_owned(),
            ));
        }
        return Ok(None);
    }
    let Some(value) = object.remove("standardPcrProtocol") else {
        return Ok(None);
    };
    let Some(protocol) = value
        .as_str()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    else {
        return Err(CoreError::InvalidRequest(
            "standardPcrProtocol must be non-empty text when supplied; use `not-selected` for design/screening without a named bench protocol.".to_owned(),
        ));
    };
    Ok((protocol != "not-selected").then(|| protocol.to_owned()))
}

async fn design_multiplex(
    State(state): State<BenchState>,
    Path(id): Path<String>,
    Json(mut request): Json<serde_json::Value>,
) -> Result<Json<serde_json::Value>, ApiError> {
    let profile = state.registry.profile(&id)?.clone();
    // `Planned` is a catalogue/reference state. Multiplex is a separate worker
    // path, so it must enforce the same release gate as ordinary design rather
    // than relying on the UI or on today's modifier assignments.
    ensure_release_executable(&profile)?;

    // Not every assay can share a tube, and the catalogue already says which.
    // A nested design multiplexed is four pairs whose second round would
    // amplify across each other's first products; a tiling scheme assigns its
    // own pools and would be doing the same work twice.
    if !profile.modifiers.contains(&Modifier::Multiplex) {
        // `InvalidRequest` rather than `IncompatibleModifier`: that variant is
        // reserved for a mistake in the catalogue, which stops the process at
        // startup and so is reported as a server fault. This is somebody asking
        // for a combination that does not exist, which is their request.
        return Err(CoreError::InvalidRequest(format!(
            "`{}` cannot be multiplexed. The assays that can are the ones whose \
             reactions are independent of each other.",
            profile.id
        ))
        .into());
    }

    let Some(object) = request.as_object_mut() else {
        return Err(CoreError::InvalidRequest("a request is an object".into()).into());
    };
    validate_multiplex_outer_fields(object)?;
    validate_multiplex_targets_shape(object)?;

    let from_rna = take_multiplex_from_rna(object)?;
    if from_rna && !profile.modifiers.contains(&Modifier::ReverseTranscription) {
        return Err(CoreError::InvalidRequest(format!(
            "{} does not support reverse transcription; remove `fromRna` from the multiplex request.",
            profile.name
        ))
        .into());
    }
    let colony_context = take_colony_multiplex_context(&profile.id, object)?;
    let standard_pcr_protocol = take_standard_pcr_multiplex_protocol(&profile.id, object)?;

    // The assay travels with every target, exactly as it does for a single
    // design, so a multiplexed colony screen still gets its lysis step.
    let assay = assay_payload(&profile);
    if let Some(targets) = object.get_mut("targets").and_then(|t| t.as_array_mut()) {
        for (index, target) in targets.iter_mut().enumerate() {
            let Some(entry) = target.as_object_mut() else {
                return Err(CoreError::InvalidRequest(format!(
                    "multiplex target {} must be an object",
                    index + 1
                ))
                .into());
            };
            validate_multiplex_target_fields(index, entry)?;
            validate_requirements(&profile, entry)?;
            translate_species_target_context(&profile.id, entry)?;
            entry.insert("assay".to_owned(), assay.clone());
            entry.insert("multiplex_context".to_owned(), true.into());
            if from_rna {
                entry.insert("from_rna".to_owned(), true.into());
            }
            if let Some(protocol) = &standard_pcr_protocol {
                entry.insert("standard_pcr_protocol".to_owned(), protocol.clone().into());
            }
            if let Some(context) = &colony_context {
                entry.insert(
                    "colony_host_class".to_owned(),
                    context.host_class.clone().into(),
                );
                entry.insert(
                    "colony_preparation".to_owned(),
                    context.preparation.clone().into(),
                );
                entry.insert(
                    "colony_protocol_id".to_owned(),
                    context.protocol_id.clone().into(),
                );
                if let Some(value) = &context.protocol_name {
                    entry.insert("colony_protocol_name".to_owned(), value.clone().into());
                }
                if let Some(value) = &context.protocol_provenance {
                    entry.insert(
                        "colony_protocol_provenance".to_owned(),
                        value.clone().into(),
                    );
                }
            }
        }
    }

    translate_multiplex_request(object);
    Ok(Json(ask_worker(state, "multiplex", request).await?))
}

/// Translate and validate the per-target biological-panel provenance that is
/// unique to species-specific multiplex PCR. Unlike ordinary single-target
/// design, multiplex targets bypass `FlankingPairRequest::to_worker`, so this
/// boundary must not silently drop the camelCase public fields.
fn translate_species_target_context(
    profile_id: &str,
    entry: &mut serde_json::Map<String, serde_json::Value>,
) -> Result<(), CoreError> {
    if let Some(value) = entry.remove("primerConcentrationNm") {
        let Some(number) = value
            .as_f64()
            .filter(|number| number.is_finite() && *number > 0.0)
        else {
            return Err(CoreError::InvalidRequest(
                "primerConcentrationNm must be a positive finite number when supplied".to_owned(),
            ));
        };
        entry.insert("primer_concentration_nm".to_owned(), number.into());
    }
    if let Some(value) = entry.remove("empiricalEvidenceRef") {
        let Some(text) = value
            .as_str()
            .map(str::trim)
            .filter(|text| !text.is_empty())
        else {
            return Err(CoreError::InvalidRequest(
                "empiricalEvidenceRef must be non-empty text when supplied".to_owned(),
            ));
        };
        entry.insert("empirical_evidence_ref".to_owned(), text.to_owned().into());
    }
    let text_mappings = [
        ("inclusivityPanelProvenance", "inclusivity_panel_provenance"),
        ("backgroundPanelProvenance", "background_panel_provenance"),
        (
            "speciesPanelSelectionRationale",
            "species_panel_selection_rationale",
        ),
        ("speciesTaxonomySnapshot", "species_taxonomy_snapshot"),
        ("speciesDatabaseSnapshot", "species_database_snapshot"),
        (
            "speciesPanelAccessionManifest",
            "species_panel_accession_manifest",
        ),
        (
            "speciesPanelRecordMetadataManifest",
            "species_panel_record_metadata_manifest",
        ),
        ("speciesPanelRetrievedDate", "species_panel_retrieved_date"),
    ];
    if profile_id == "species-specific-pcr" {
        for (public, worker) in text_mappings {
            let Some(value) = entry.remove(public) else {
                return Err(CoreError::InvalidRequest(format!(
                    "species-specific multiplex targets require non-empty `{public}`"
                )));
            };
            let Some(text) = value
                .as_str()
                .map(str::trim)
                .filter(|text| !text.is_empty())
            else {
                return Err(CoreError::InvalidRequest(format!(
                    "species-specific multiplex targets require non-empty `{public}`"
                )));
            };
            entry.insert(worker.to_owned(), text.to_owned().into());
        }
        let Some(value) = entry.remove("speciesTargetTaxid") else {
            return Err(CoreError::InvalidRequest(
                "species-specific multiplex targets require speciesTargetTaxid".to_owned(),
            ));
        };
        let Some(taxid) = value.as_u64().filter(|value| *value > 0) else {
            return Err(CoreError::InvalidRequest(
                "speciesTargetTaxid must be a positive integer".to_owned(),
            ));
        };
        entry.insert("species_target_taxid".to_owned(), taxid.into());
    } else if text_mappings
        .iter()
        .any(|(public, worker)| entry.contains_key(*public) || entry.contains_key(*worker))
        || entry.contains_key("speciesTargetTaxid")
        || entry.contains_key("species_target_taxid")
    {
        return Err(CoreError::InvalidRequest(
            "species panel snapshot/provenance fields belong only to the `species-specific-pcr` multiplex assay".to_owned(),
        ));
    }
    Ok(())
}

/// Translate the public API's camelCase multiplex controls to the worker's
/// snake_case vocabulary before spawning it. The worker intentionally accepts
/// a JSON object because each target carries the shared design request, but it
/// does not know the HTTP naming convention. Leaving this boundary implicit
/// made `candidatesPerTarget` and `perTube` look accepted while silently
/// falling back to their worker defaults.
fn translate_multiplex_request(object: &mut serde_json::Map<String, serde_json::Value>) {
    for (public, worker) in [
        ("candidatesPerTarget", "candidates_per_target"),
        ("perTube", "per_tube"),
        ("readoutProfile", "readout_profile"),
        ("optimizerMode", "optimizer_mode"),
    ] {
        if let Some(value) = object.remove(public) {
            object.entry(worker.to_owned()).or_insert(value);
        }
    }
}

/// The bench endpoints, mounted under whatever prefix the caller chooses.
pub fn routes(registry: Registry) -> Router {
    Router::new()
        .route(http_routes::CHECK_PRIMERS, post(check_pair))
        .route(http_routes::ENZYMES, post(rank_enzymes))
        .route(http_routes::VECTOR_PRIMERS, post(place_vector_primers))
        .route(http_routes::MODULE_MULTIPLEX, post(design_multiplex))
        .with_state(BenchState {
            worker: pcr_application::scientific::worker_from_env(),
            registry,
            // The process's one gate, not a private ceiling: bench work is
            // worker work, and the number that matters is how many
            // interpreters exist in total.
            gate: Arc::new(Gate::shared()),
        })
}

#[cfg(test)]
mod tests {
    use super::{
        take_colony_multiplex_context, take_multiplex_from_rna,
        take_standard_pcr_multiplex_protocol, translate_multiplex_request,
        translate_species_target_context, validate_multiplex_outer_fields,
        validate_multiplex_target_fields, validate_multiplex_targets_shape,
    };
    use serde_json::json;

    #[test]
    fn multiplex_outer_boundary_rejects_unknown_public_fields() {
        let value = json!({
            "readout": "ngs",
            "targets": [],
            "perTubes": 2
        });
        let object = value.as_object().expect("object");
        let error = validate_multiplex_outer_fields(object)
            .expect_err("unknown public multiplex field must fail closed");
        assert!(error.to_string().contains("perTubes"), "{error}");
    }

    #[test]
    fn multiplex_target_boundary_rejects_unmodelled_tail_fields() {
        let value = json!({
            "name": "amplicon-a",
            "template": "ACGTACGT",
            "tails": {"left": "AAAAAA", "right": "CCCCCC"}
        });
        let target = value.as_object().expect("object");
        let error = validate_multiplex_target_fields(0, target)
            .expect_err("unmodelled target tails must fail closed before the worker call");
        assert!(error.to_string().contains("tails"), "{error}");
    }

    #[test]
    fn multiplex_from_rna_refuses_non_boolean_input() {
        let mut object = json!({"fromRna": "true"})
            .as_object()
            .expect("object")
            .clone();
        let error = take_multiplex_from_rna(&mut object)
            .expect_err("strings must not masquerade as boolean RT requests");
        assert!(error.to_string().contains("must be a boolean"), "{error}");
    }

    #[test]
    fn foreign_shared_context_is_rejected_even_when_malformed_or_empty() {
        let mut colony = json!({"colonyHostClass": 12})
            .as_object()
            .expect("object")
            .clone();
        assert!(take_colony_multiplex_context("standard-pcr", &mut colony).is_err());

        let mut protocol = json!({"standardPcrProtocol": 12})
            .as_object()
            .expect("object")
            .clone();
        assert!(take_standard_pcr_multiplex_protocol("colony-pcr", &mut protocol).is_err());
    }

    #[test]
    fn standard_pcr_protocol_refuses_non_text_instead_of_becoming_unselected() {
        let mut object = json!({"standardPcrProtocol": 12})
            .as_object()
            .expect("object")
            .clone();
        let error = take_standard_pcr_multiplex_protocol("standard-pcr", &mut object)
            .expect_err("malformed protocol field must fail closed");
        assert!(
            error.to_string().contains("must be non-empty text"),
            "{error}"
        );
    }

    #[test]
    fn multiplex_target_shape_is_rejected_before_worker_spawn() {
        let missing = json!({"readout": "agarose"})
            .as_object()
            .expect("object")
            .clone();
        assert!(validate_multiplex_targets_shape(&missing).is_err());

        let wrong_type = json!({"targets": "not-an-array"})
            .as_object()
            .expect("object")
            .clone();
        assert!(validate_multiplex_targets_shape(&wrong_type).is_err());

        let one = json!({"targets": [{}]})
            .as_object()
            .expect("object")
            .clone();
        assert!(validate_multiplex_targets_shape(&one).is_err());

        let two = json!({"targets": [{}, {}]})
            .as_object()
            .expect("object")
            .clone();
        validate_multiplex_targets_shape(&two).expect("two targets are a valid multiplex shape");
    }

    #[test]
    fn multiplex_controls_are_translated_before_the_worker_call() {
        let mut object = json!({
            "readout": "agarose",
            "candidatesPerTarget": 17,
            "perTube": 4,
        })
        .as_object()
        .expect("object")
        .clone();

        translate_multiplex_request(&mut object);

        assert_eq!(object["candidates_per_target"], 17);
        assert_eq!(object["per_tube"], 4);
        assert!(object.get("candidatesPerTarget").is_none());
        assert!(object.get("perTube").is_none());
    }

    #[test]
    fn standard_pcr_multiplex_consumes_one_shared_named_protocol() {
        let mut object = serde_json::json!({
            "standardPcrProtocol": "promega-gotaq-m300"
        })
        .as_object()
        .expect("object")
        .clone();
        let protocol = take_standard_pcr_multiplex_protocol("standard-pcr", &mut object)
            .expect("valid shared protocol");
        assert_eq!(protocol.as_deref(), Some("promega-gotaq-m300"));
        assert!(object.get("standardPcrProtocol").is_none());
    }

    #[test]
    fn standard_pcr_multiplex_rejects_protocol_field_on_other_assays() {
        let mut object = serde_json::json!({
            "standardPcrProtocol": "neb-taq-m0273"
        })
        .as_object()
        .expect("object")
        .clone();
        let error = take_standard_pcr_multiplex_protocol("colony-pcr", &mut object)
            .expect_err("foreign protocol field must fail closed");
        assert!(error.to_string().contains("standardPcrProtocol"), "{error}");
    }

    #[test]
    fn colony_multiplex_requires_shared_crude_template_provenance() {
        let mut object = serde_json::json!({}).as_object().expect("object").clone();
        let error = take_colony_multiplex_context("colony-pcr", &mut object)
            .expect_err("missing colony context must fail closed");
        assert!(error.to_string().contains("colonyHostClass"), "{error}");
    }

    #[test]
    fn colony_multiplex_context_is_consumed_for_target_injection() {
        let mut object = serde_json::json!({
            "colonyHostClass": "bacterial",
            "colonyPreparation": "direct-transfer",
            "colonyProtocolId": "custom-sop",
            "colonyProtocolName": "lab colony-screen SOP",
            "colonyProtocolProvenance": "lab QA system / rev 3 / 2026-08-01"
        })
        .as_object()
        .expect("object")
        .clone();
        let context = take_colony_multiplex_context("colony-pcr", &mut object)
            .expect("valid shared colony context")
            .expect("colony context returned");
        assert_eq!(context.host_class, "bacterial");
        assert_eq!(context.preparation, "direct-transfer");
        assert_eq!(context.protocol_id, "custom-sop");
        assert_eq!(
            context.protocol_name.as_deref(),
            Some("lab colony-screen SOP")
        );
        assert_eq!(
            context.protocol_provenance.as_deref(),
            Some("lab QA system / rev 3 / 2026-08-01")
        );
        assert!(object.get("colonyHostClass").is_none());
        assert!(object.get("colonyPreparation").is_none());
        assert!(object.get("colonyProtocolId").is_none());
        assert!(object.get("colonyProtocolName").is_none());
        assert!(object.get("colonyProtocolProvenance").is_none());
    }

    #[test]
    fn species_multiplex_panel_provenance_is_required_and_translated() {
        let mut target = json!({
            "inclusivityPanelProvenance": "NCBI RefSeq release X; accessions A.1/B.1",
            "backgroundPanelProvenance": "NCBI RefSeq release X; near-neighbours C.1/D.1",
            "speciesPanelSelectionRationale": "target diversity plus closest phylogenetic neighbours",
            "speciesTargetTaxid": 562,
            "speciesTaxonomySnapshot": "NCBI Taxonomy 2026-09-04",
            "speciesDatabaseSnapshot": "NCBI RefSeq release X",
            "speciesPanelAccessionManifest": "NC_000001.1\nNC_000002.1\nNC_000003.1\nNC_000004.1",
            "speciesPanelRecordMetadataManifest": "target-a\tNC_000001.1\tinclusivity\tlinear\ntarget-b\tNC_000002.1\tinclusivity\tlinear\nnear-a\tNC_000003.1\texclusivity\tlinear\nnear-b\tNC_000004.1\texclusivity\tlinear",
            "speciesPanelRetrievedDate": "2026-09-04"
        })
        .as_object()
        .expect("object")
        .clone();

        translate_species_target_context("species-specific-pcr", &mut target)
            .expect("traceable species panel context");
        assert_eq!(
            target["inclusivity_panel_provenance"],
            "NCBI RefSeq release X; accessions A.1/B.1"
        );
        assert!(target.get("inclusivityPanelProvenance").is_none());
        assert_eq!(target["species_target_taxid"], 562);
        assert!(target
            .get("species_panel_record_metadata_manifest")
            .is_some());

        let mut missing = json!({}).as_object().expect("object").clone();
        let error = translate_species_target_context("species-specific-pcr", &mut missing)
            .expect_err("missing provenance must fail closed");
        assert!(
            error.to_string().contains("inclusivityPanelProvenance"),
            "{error}"
        );
    }

    #[test]
    fn colony_multiplex_context_is_refused_for_other_modules() {
        let mut object = serde_json::json!({
            "colonyHostClass": "bacterial"
        })
        .as_object()
        .expect("object")
        .clone();
        let error = take_colony_multiplex_context("standard-pcr", &mut object)
            .expect_err("colony context must not leak into another assay");
        assert!(error.to_string().contains("only valid"), "{error}");
    }

    #[test]
    fn an_existing_worker_key_wins_over_a_duplicate_public_key() {
        let mut object = json!({
            "candidatesPerTarget": 17,
            "candidates_per_target": 5,
        })
        .as_object()
        .expect("object")
        .clone();

        translate_multiplex_request(&mut object);

        assert_eq!(object["candidates_per_target"], 5);
    }
}
