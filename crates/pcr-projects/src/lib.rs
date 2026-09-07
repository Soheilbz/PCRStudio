//! Projects and saved design runs. Every read/write is user-scoped, and the
//! storage migration authority remains in `pcr-storage`.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::HashMap;

pub mod schema;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Postgres, Transaction};

mod save_run_input;
pub use save_run_input::SaveRunForJobInput;

/// How many projects one account may keep.
///
/// A free service needs a number here, and a number chosen now is kinder than
/// a quota introduced later. Well above what a working scientist accumulates.
pub const MAX_PROJECTS_PER_USER: i64 = 200;

/// How many runs one project keeps before the oldest are dropped.
///
/// A run holds a whole result, so this is the difference between a project and
/// an unbounded log. The oldest go first, because the interesting one is
/// almost always the most recent.
pub const MAX_RUNS_PER_PROJECT: i64 = 50;

/// The longest a project name may be.
pub const MAX_NAME: usize = 120;

/// The largest one stored run may be, across its request and its result.
///
/// The canonical foundation limit is sized from the durable-job request and
/// bounded scientific stdout ceilings, with explicit framing headroom. Large
/// nucleotide strings are stored by sequence-asset reference rather than being
/// duplicated inside every run document.
pub const MAX_RUN_DOCUMENT_BYTES: usize = pcr_contracts::MAX_RUN_DOCUMENT_BYTES;

/// The largest a project's notes may be.
pub const MAX_NOTES_BYTES: usize = pcr_contracts::MAX_PROJECT_NOTES_BYTES;

/// The largest a run's label may be.
pub const MAX_LABEL_BYTES: usize = pcr_contracts::MAX_RUN_LABEL_BYTES;
/// Sentinel used only when legacy export.v1 omitted project-level draft provenance.
/// Zero means "unknown/unrecorded", never "schema v1".
pub const LEGACY_UNRECORDED_DRAFT_SCHEMA_VERSION: i32 = 0;

/// The largest a project's saved draft may be.
///
/// The canonical limit admits the largest supported logical sequence so the
/// store can externalize it into the sequence-asset boundary before writing
/// the compact project document.
pub const MAX_SETTINGS_BYTES: usize = pcr_contracts::MAX_PROJECT_SETTINGS_BYTES;

/// Maximum projects a valid account export can contain.
///
/// A server-produced export can never exceed the live project quota. Rejecting
/// a larger document before iterating it keeps import from becoming an
/// authenticated CPU/transaction amplification path made of thousands of tiny
/// synthetic projects.
pub const MAX_IMPORT_PROJECTS: usize = MAX_PROJECTS_PER_USER as usize;

/// Maximum live project/run backup footprint held by one account.
///
/// Accounting includes request/result content plus conservative provenance and
/// JSON-framing headroom. The canonical foundation contract guarantees this
/// stays below the authenticated backup-document ceiling, and export performs
/// a final exact serialized-size check.
/// Deleted projects do not count while deleted; restoring them must fit again.
pub const MAX_ACCOUNT_DATA_BYTES: i64 = pcr_contracts::MAX_ACCOUNT_PROJECT_DATA_BYTES as i64;

/// A failure from the project store.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, thiserror::Error)]
#[serde(tag = "kind", content = "detail", rename_all = "camelCase")]
pub enum ProjectError {
    /// No such project, or it belongs to somebody else. Deliberately one case.
    #[error("no such project")]
    NotFound,

    /// A name that would not survive being displayed.
    #[error("{0}")]
    InvalidName(String),

    /// A project or run field is larger or shaped differently than storage allows.
    #[error("{0}")]
    InvalidData(String),

    /// This account already has as many projects as it may keep.
    #[error("{0}")]
    TooManyProjects(String),

    /// The account already holds as much live project/run data as the backup
    /// contract permits.
    #[error("{0}")]
    StorageLimit(String),

    /// The caller edited an older snapshot after this project changed elsewhere.
    #[error("{0}")]
    Conflict(String),

    /// A document handed to the importer that is not one of ours.
    ///
    /// Its own case rather than reusing `InvalidName`, because the two have
    /// different fixes: one means rename the project, the other means choose a
    /// different file, and an interface cannot say which unless the error says
    /// which.
    #[error("{0}")]
    NotAnExport(String),

    /// The database refused or was unreachable.
    #[error("the project store failed: {0}")]
    Store(String),
}

/// Result alias for the project store.
pub type Result<T> = std::result::Result<T, ProjectError>;

fn store(error: sqlx::Error) -> ProjectError {
    ProjectError::Store(error.to_string())
}

fn asset_store(error: pcr_storage::StorageError) -> ProjectError {
    match error {
        pcr_storage::StorageError::Invalid(detail) => ProjectError::InvalidData(detail),
        pcr_storage::StorageError::Quota(detail) => ProjectError::StorageLimit(detail),
        other => ProjectError::Store(other.to_string()),
    }
}

/// One project.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Project {
    /// Stable identifier, also the route segment.
    pub id: String,
    /// What the person called it.
    pub name: String,
    /// Anything they wanted to write down beside it.
    pub notes: String,
    /// Which assay this project designs for.
    pub module_id: String,
    /// What has been filled in so far, step by step.
    pub settings: serde_json::Value,
    /// Schema version of the raw saved draft.
    pub draft_schema_version: i32,
    /// Module-contract version that interpreted the saved draft.
    pub module_contract_version: String,
    /// When it was made.
    pub created_at: DateTime<Utc>,
    /// When anything about it last changed.
    pub updated_at: DateTime<Utc>,
    /// How many runs are kept in it.
    pub run_count: i64,
}

/// One completed design, kept whole.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Run {
    /// Stable identifier.
    pub id: String,
    /// Which project it belongs to.
    pub project_id: String,
    /// What the person called this attempt, if anything.
    pub label: String,
    /// Exactly what was asked for. Without this the result cannot be repeated.
    pub request: serde_json::Value,
    /// Exactly what came back.
    pub result: serde_json::Value,
    /// Schema version of the raw request payload.
    pub request_schema_version: i32,
    /// Schema version of the raw result payload.
    pub result_schema_version: i32,
    /// Module-contract version used for the run.
    pub module_contract_version: String,
    /// Toolchain fingerprint, absent on legacy historical runs.
    pub toolchain_fingerprint: Option<String>,
    /// Canonical request/contract/toolchain fingerprint, absent on legacy runs.
    pub run_fingerprint: Option<String>,
    /// Engine identity recorded at save time.
    pub engine_id: Option<String>,
    /// Module identity recorded at save time.
    pub module_id: Option<String>,
    /// Immutable derived primary-result count.
    pub result_count: i64,
    /// Immutable derived primary-result unit.
    pub result_unit: String,
    /// Immutable derived target display name.
    pub target_name: String,
    /// When it ran.
    pub created_at: DateTime<Utc>,
}

/// A run without its result, for listing without moving megabytes.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunSummary {
    /// Stable identifier.
    pub id: String,
    /// What the person called this attempt.
    pub label: String,
    /// When it ran.
    pub created_at: DateTime<Utc>,
    /// How many pairs it produced.
    pub pair_count: i64,
    /// How many primary outputs it produced, using the engine's own shape.
    pub result_count: i64,
    /// The name of the primary output unit (`pair`, `set`, `assay`, ...).
    pub result_unit: String,
    /// What the template was called.
    pub target_name: String,
    /// Whether a share link currently exists for it.
    ///
    /// Whether, not which: the token is stored only as its hash and cannot be
    /// read back. An interface can therefore offer to withdraw or replace a
    /// link, and cannot offer to show you one you have lost.
    pub shared: bool,
}

/// Somewhere to keep projects.
#[derive(Debug, Clone)]
pub struct Projects {
    pool: PgPool,
}

/// Trim a name and refuse one that could not be shown.
///
/// # Errors
///
/// [`ProjectError::InvalidName`] saying which rule was broken.
pub fn check_name(name: &str) -> Result<String> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err(ProjectError::InvalidName("A project needs a name.".into()));
    }
    if trimmed.chars().count() > MAX_NAME {
        return Err(ProjectError::InvalidName(format!(
            "A project name may be up to {MAX_NAME} characters."
        )));
    }
    // A name is shown in a list and in a breadcrumb. Control characters would
    // break both, and nobody types them on purpose.
    if trimmed.chars().any(char::is_control) {
        return Err(ProjectError::InvalidName(
            "A project name cannot contain control characters.".into(),
        ));
    }
    Ok(trimmed.to_owned())
}

/* ── Bringing an export back in ────────────────────────────────────────── */

/// One project as it arrives from an export.
///
/// The v2 export carries the immutable persistence versions and timestamps that
/// make a backup a reproducibility artifact rather than merely copied JSON.
/// v1 lacked only the project-level version fields; those remain optional so a
/// historical v1 backup can still be restored without relabelling its runs.
/// Missing draft provenance is stored with the explicit zero sentinel rather
/// than guessed as schema v1 or relabelled as the current schema.
#[derive(Debug, Clone, Deserialize)]
pub struct Incoming {
    /// The id it had where it came from. Kept when globally free.
    pub id: String,
    /// What it was called where it came from.
    pub name: String,
    /// Anything written beside it.
    #[serde(default)]
    pub notes: String,
    /// Which assay it designs for.
    pub module_id: String,
    /// The draft — sequence, constraints and reaction settings.
    #[serde(default)]
    pub settings: serde_json::Value,
    /// Exact stored draft schema version. Missing only in legacy export.v1.
    #[serde(default)]
    pub draft_schema_version: Option<i32>,
    /// Exact module-contract identity. Missing only in legacy export.v1.
    #[serde(default)]
    pub module_contract_version: Option<String>,
    /// Original creation time.
    pub created_at: DateTime<Utc>,
    /// Original last-update time.
    pub updated_at: DateTime<Utc>,
    /// Its saved runs, newest first, as the export writes them.
    #[serde(default)]
    pub runs: Vec<IncomingRun>,
}

/// One immutable historical run inside an incoming project.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IncomingRun {
    /// Original run id. Preserved when globally free.
    pub id: String,
    /// Original project id in the export. It is validated but remapped on insert
    /// when a project id collides globally.
    pub project_id: String,
    /// What it was called, if anything.
    #[serde(default)]
    pub label: String,
    /// Exact request that produced the result.
    pub request: serde_json::Value,
    /// Exact result returned by the historical run.
    pub result: serde_json::Value,
    /// Original request schema version.
    pub request_schema_version: i32,
    /// Original result schema version.
    pub result_schema_version: i32,
    /// Original module-contract identity.
    pub module_contract_version: String,
    /// Original toolchain fingerprint, absent on legacy history.
    pub toolchain_fingerprint: Option<String>,
    /// Original canonical run fingerprint, absent on legacy history.
    pub run_fingerprint: Option<String>,
    /// Original engine identity.
    pub engine_id: Option<String>,
    /// Original module identity.
    pub module_id: Option<String>,
    /// Immutable derived result count.
    pub result_count: i64,
    /// Immutable derived result unit.
    pub result_unit: String,
    /// Immutable derived target display name.
    pub target_name: String,
    /// Original run creation time.
    pub created_at: DateTime<Utc>,
}

/// What an import did, so the answer can say more than "ok".
#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Imported {
    /// Projects created.
    pub projects: usize,
    /// Runs created inside them.
    pub runs: usize,
    /// Projects already held under the same id, and so left alone.
    pub already_here: usize,
    /// Projects that were here but deleted, and have been brought back.
    ///
    /// Its own number rather than folded into `projects`, because the two are
    /// different news: one is "your backup arrived", the other is "the thing
    /// you deleted is back", and somebody restoring after a mistake is looking
    /// for the second.
    pub restored: usize,
    /// Projects that did not fit under the ceiling.
    pub refused: usize,
}

/// The size of a JSON value on its way through, in bytes.
fn json_size(value: &serde_json::Value) -> usize {
    serde_json::to_vec(value).map_or(usize::MAX, |bytes| bytes.len())
}

fn check_project_data(notes: Option<&str>, settings: Option<&serde_json::Value>) -> Result<()> {
    if let Some(notes) = notes {
        if notes.len() > MAX_NOTES_BYTES {
            return Err(ProjectError::InvalidData(format!(
                "A project's notes may be at most {MAX_NOTES_BYTES} bytes."
            )));
        }
    }
    if let Some(settings) = settings {
        if !settings.is_object() {
            return Err(ProjectError::InvalidData(
                "A project's draft must be a JSON object.".into(),
            ));
        }
        if json_size(settings) > MAX_SETTINGS_BYTES {
            return Err(ProjectError::InvalidData(format!(
                "A project's draft may be at most {MAX_SETTINGS_BYTES} bytes."
            )));
        }
    }
    Ok(())
}

fn check_run_data(
    label: &str,
    request: &serde_json::Value,
    result: &serde_json::Value,
) -> Result<()> {
    if label.trim().len() > MAX_LABEL_BYTES {
        return Err(ProjectError::InvalidData(format!(
            "A run's label may be at most {MAX_LABEL_BYTES} bytes."
        )));
    }
    if !request.is_object() || !result.is_object() {
        return Err(ProjectError::InvalidData(
            "A saved run's request and result must be JSON objects.".into(),
        ));
    }
    if json_size(request).saturating_add(json_size(result)) > MAX_RUN_DOCUMENT_BYTES {
        return Err(ProjectError::InvalidData(format!(
            "One saved run may be at most {MAX_RUN_DOCUMENT_BYTES} bytes."
        )));
    }
    Ok(())
}

/// Check one incoming project against what this store will hold.
///
/// Run before anything is written, so a refused document costs nothing — not
/// half an import that fails partway through with rows already committed.
///
/// # Errors
///
/// [`ProjectError::NotAnExport`] naming the rule the document broke.
fn check_incoming(project: &Incoming) -> Result<()> {
    if uuid::Uuid::parse_str(&project.id).is_err() {
        return Err(ProjectError::NotAnExport(
            "A project id in an export must be a UUID produced by PCRStudio.".into(),
        ));
    }
    if project.runs.len() > MAX_RUNS_PER_PROJECT as usize {
        return Err(ProjectError::NotAnExport(format!(
            "An exported project may contain at most {MAX_RUNS_PER_PROJECT} runs."
        )));
    }
    if project.module_id.len() > 120
        || project
            .module_contract_version
            .as_deref()
            .is_some_and(|value| value.is_empty() || value.len() > 128)
        || project.draft_schema_version.is_some_and(|value| value < 1)
    {
        return Err(ProjectError::NotAnExport(
            "A project's module identity/provenance is outside the supported backup bounds.".into(),
        ));
    }
    if project.notes.len() > MAX_NOTES_BYTES {
        return Err(ProjectError::NotAnExport(format!(
            "A project's notes may be at most {MAX_NOTES_BYTES} bytes."
        )));
    }

    // The draft is read back as an object by everything around it, so anything
    // else would trade one kind of breakage for another.
    if !project.settings.is_object() {
        return Err(ProjectError::NotAnExport(
            "A project's draft must be a JSON object.".into(),
        ));
    }
    if json_size(&project.settings) > MAX_SETTINGS_BYTES {
        return Err(ProjectError::NotAnExport(format!(
            "A project's draft may be at most {MAX_SETTINGS_BYTES} bytes."
        )));
    }

    for run in &project.runs {
        if uuid::Uuid::parse_str(&run.id).is_err() {
            return Err(ProjectError::NotAnExport(
                "A run id in an export must be a UUID produced by PCRStudio.".into(),
            ));
        }
        if run.project_id != project.id {
            return Err(ProjectError::NotAnExport(
                "A saved run's projectId must match the project that contains it.".into(),
            ));
        }
        if run.request_schema_version < 1
            || run.result_schema_version < 1
            || run.module_contract_version.trim().is_empty()
            || run.module_contract_version.len() > 128
            || run
                .toolchain_fingerprint
                .as_deref()
                .is_some_and(|value| value.len() > 256)
            || run
                .run_fingerprint
                .as_deref()
                .is_some_and(|value| value.len() > 256)
            || run
                .engine_id
                .as_deref()
                .is_some_and(|value| value.len() > 120)
            || run
                .module_id
                .as_deref()
                .is_some_and(|value| value.len() > 120)
        {
            return Err(ProjectError::NotAnExport(
                "A saved run is missing valid historical schema/contract provenance.".into(),
            ));
        }
        if run.result_count < 0 || run.result_unit.len() > 120 || run.target_name.len() > 4096 {
            return Err(ProjectError::NotAnExport(
                "A saved run has invalid immutable summary metadata.".into(),
            ));
        }
        if run.label.len() > MAX_LABEL_BYTES {
            return Err(ProjectError::NotAnExport(format!(
                "A run's label may be at most {MAX_LABEL_BYTES} bytes."
            )));
        }
        // Both halves are read back as objects — the request to be re-run, the
        // result by the summary query above — so anything else would trade one
        // kind of breakage for another.
        for (side, value) in [("request", &run.request), ("result", &run.result)] {
            if !value.is_object() {
                return Err(ProjectError::NotAnExport(format!(
                    "A saved run's {side} must be a JSON object."
                )));
            }
        }
        let document = json_size(&run.request) + json_size(&run.result);
        if document > MAX_RUN_DOCUMENT_BYTES {
            return Err(ProjectError::NotAnExport(format!(
                "One saved run may be at most {MAX_RUN_DOCUMENT_BYTES} bytes."
            )));
        }
    }

    Ok(())
}

fn incoming_data_bytes(projects: &[Incoming]) -> usize {
    projects.iter().fold(0usize, |total, project| {
        let project_bytes = project
            .name
            .len()
            .saturating_add(project.notes.len())
            .saturating_add(project.module_id.len())
            .saturating_add(
                project
                    .module_contract_version
                    .as_deref()
                    .map_or(0, str::len),
            )
            .saturating_add(512)
            .saturating_add(json_size(&project.settings));
        project
            .runs
            .iter()
            .fold(total.saturating_add(project_bytes), |subtotal, run| {
                subtotal
                    .saturating_add(run.id.len())
                    .saturating_add(run.project_id.len())
                    .saturating_add(run.label.len())
                    .saturating_add(run.module_contract_version.len())
                    .saturating_add(run.toolchain_fingerprint.as_deref().map_or(0, str::len))
                    .saturating_add(run.run_fingerprint.as_deref().map_or(0, str::len))
                    .saturating_add(run.engine_id.as_deref().map_or(0, str::len))
                    .saturating_add(run.module_id.as_deref().map_or(0, str::len))
                    .saturating_add(run.result_unit.len())
                    .saturating_add(run.target_name.len())
                    .saturating_add(1024)
                    .saturating_add(json_size(&run.request))
                    .saturating_add(json_size(&run.result))
            })
    })
}

async fn account_data_bytes(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
) -> Result<i64> {
    sqlx::query_scalar::<_, i64>(
        "SELECT
             COALESCE((
                 SELECT sum(
                     octet_length(p.name) + octet_length(p.notes) +
                     octet_length(p.module_id) + octet_length(p.settings::text) +
                     octet_length(p.module_contract_version) + 512
                 )::bigint
                   FROM projects_all p
                  WHERE p.user_id = $1 AND p.deleted_at IS NULL
             ), 0)::bigint
             +
             COALESCE((
                 SELECT sum(
                     octet_length(r.label) + octet_length(r.request::text) +
                     octet_length(r.result::text) + octet_length(r.id) + octet_length(r.project_id) +
                     octet_length(r.module_contract_version) + COALESCE(octet_length(r.toolchain_fingerprint),0) +
                     COALESCE(octet_length(r.run_fingerprint),0) + COALESCE(octet_length(r.engine_id),0) +
                     COALESCE(octet_length(r.module_id),0) + octet_length(r.result_unit) + octet_length(r.target_name) + 1024
                 )::bigint
                   FROM runs r
                   JOIN projects_all p ON p.id = r.project_id
                  WHERE p.user_id = $1 AND p.deleted_at IS NULL
             ), 0)::bigint
             +
             COALESCE((
                 SELECT sum(octet_length(a.content))::bigint
                   FROM project_sequence_asset_refs ref
                   JOIN sequence_assets a ON a.id=ref.asset_id AND a.user_id=ref.user_id
                   JOIN projects_all p ON p.id=ref.project_id AND p.user_id=ref.user_id
                  WHERE ref.user_id=$1 AND p.deleted_at IS NULL
             ),0)::bigint
             +
             COALESCE((
                 SELECT sum(octet_length(a.content))::bigint
                   FROM run_sequence_asset_refs ref
                   JOIN sequence_assets a ON a.id=ref.asset_id AND a.user_id=ref.user_id
                   JOIN projects_all p ON p.id=ref.project_id AND p.user_id=ref.user_id
                  WHERE ref.user_id=$1 AND p.deleted_at IS NULL
             ),0)::bigint",
    )
    .bind(user_id)
    .fetch_one(&mut **transaction)
    .await
    .map_err(store)
}

async fn enforce_account_data_limit(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
) -> Result<()> {
    let bytes = account_data_bytes(transaction, user_id).await?;
    if bytes > MAX_ACCOUNT_DATA_BYTES {
        return Err(ProjectError::StorageLimit(format!(
            "This account has reached its {MAX_ACCOUNT_DATA_BYTES}-byte live project-data limit. Delete data or runs before adding more."
        )));
    }
    Ok(())
}

#[derive(Debug)]
struct RunMetadata {
    module_id: String,
    engine_id: Option<String>,
    result_count: i64,
    result_unit: String,
    target_name: String,
    toolchain_fingerprint: Option<String>,
    run_fingerprint: String,
}

fn canonical_json(value: &serde_json::Value) -> serde_json::Value {
    match value {
        serde_json::Value::Array(values) => {
            serde_json::Value::Array(values.iter().map(canonical_json).collect())
        }
        serde_json::Value::Object(values) => {
            let mut keys: Vec<_> = values.keys().collect();
            keys.sort_unstable();
            serde_json::Value::Object(
                keys.into_iter()
                    .map(|key| (key.clone(), canonical_json(&values[key])))
                    .collect(),
            )
        }
        other => other.clone(),
    }
}

fn sha256_json(value: &serde_json::Value) -> String {
    let bytes = serde_json::to_vec(&canonical_json(value)).unwrap_or_default();
    hex::encode(Sha256::digest(bytes))
}

/// Stable pre-execution fingerprint for an owned scientific request.
///
/// Unlike [`Run::run_fingerprint`], this deliberately excludes toolchain and
/// result metadata because it exists before execution. It is therefore safe
/// for durable-job idempotency and duplicate-work detection, while a completed
/// run still receives the stronger fingerprint that includes its toolchain.
#[must_use]
pub fn request_fingerprint(module_id: &str, request: &serde_json::Value) -> String {
    let document = serde_json::json!({
        "request": canonical_json(request),
        "module": module_id,
        "engine": pcr_contracts::engine_for_module(module_id),
        "moduleContractVersion": schema::CURRENT_MODULE_CONTRACT_VERSION,
        "requestSchemaVersion": schema::CURRENT_REQUEST_SCHEMA_VERSION,
    });
    sha256_json(&document)
}

fn primary_result(result: &serde_json::Value) -> (i64, String) {
    for (key, unit) in [
        ("sets", "set"),
        ("pairs", "pair"),
        ("assays", "assay"),
        ("tiles", "tile"),
        ("primers", "primer"),
        ("junctions", "junction"),
    ] {
        if let Some(values) = result.get(key).and_then(serde_json::Value::as_array) {
            return (
                i64::try_from(values.len()).unwrap_or(i64::MAX),
                unit.to_owned(),
            );
        }
    }
    (0, "result".to_owned())
}

fn target_name(result: &serde_json::Value) -> String {
    result
        .get("target")
        .and_then(|value| value.get("name"))
        .and_then(serde_json::Value::as_str)
        .unwrap_or_default()
        .to_owned()
}

fn toolchain_fingerprint(result: &serde_json::Value) -> Option<String> {
    let provenance = result.get("provenance")?;
    provenance
        .get("toolchain_fingerprint")
        .or_else(|| provenance.get("toolchainFingerprint"))
        .and_then(serde_json::Value::as_str)
        .map(str::to_owned)
}

fn run_metadata(
    module_id: &str,
    request: &serde_json::Value,
    result: &serde_json::Value,
) -> RunMetadata {
    let (result_count, result_unit) = primary_result(result);
    let toolchain_fingerprint = toolchain_fingerprint(result);
    let engine_id = pcr_contracts::engine_for_module(module_id).map(str::to_owned);
    let fingerprint_document = serde_json::json!({
        "request": canonical_json(request),
        "module": module_id,
        "engine": engine_id,
        "moduleContractVersion": schema::CURRENT_MODULE_CONTRACT_VERSION,
        "toolchainFingerprint": toolchain_fingerprint,
    });
    RunMetadata {
        module_id: module_id.to_owned(),
        engine_id,
        result_count,
        result_unit,
        target_name: target_name(result),
        toolchain_fingerprint,
        run_fingerprint: sha256_json(&fingerprint_document),
    }
}

impl Projects {
    /// Use an existing pool. The accounts store owns the connection.
    #[must_use]
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    /// Start a project for one person.
    ///
    /// # Errors
    ///
    /// [`ProjectError::InvalidName`] for a name that could not be shown, or
    /// [`ProjectError::TooManyProjects`] once the quota is reached.
    pub async fn create(&self, user_id: &str, name: &str, module_id: &str) -> Result<Project> {
        self.create_with_data(user_id, name, module_id, "", &serde_json::json!({}))
            .await
    }

    /// Start a project with its initial notes and draft in the same transaction.
    ///
    /// Duplicate/fork flows use this instead of creating an empty shell and
    /// patching it in a second request. A failure can therefore never leave a
    /// half-created live project behind.
    pub async fn create_with_data(
        &self,
        user_id: &str,
        name: &str,
        module_id: &str,
        notes: &str,
        settings: &serde_json::Value,
    ) -> Result<Project> {
        let name = check_name(name)?;
        check_project_data(Some(notes), Some(settings))?;

        // The quota check and insert must be one serialised operation. Without
        // this per-user transaction lock, two requests can both observe 199
        // projects and commit project 200 and 201.
        let mut transaction = self.pool.begin().await.map_err(store)?;
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
            .bind(user_id)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;
        let existing: i64 = sqlx::query_scalar("SELECT count(*) FROM projects WHERE user_id = $1")
            .bind(user_id)
            .fetch_one(&mut *transaction)
            .await
            .map_err(store)?;
        if existing >= MAX_PROJECTS_PER_USER {
            return Err(ProjectError::TooManyProjects(format!(
                "This account already has {MAX_PROJECTS_PER_USER} projects. \
                 Delete one before starting another."
            )));
        }

        let id = uuid::Uuid::new_v4().to_string();
        let (stored_settings, sequence_references) =
            pcr_storage::externalize_sequence_assets(&mut transaction, user_id, settings)
                .await
                .map_err(asset_store)?;
        sqlx::query(
            "INSERT INTO projects (id, user_id, name, notes, module_id, settings, draft_schema_version, module_contract_version)              VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
        )
            .bind(&id)
            .bind(user_id)
            .bind(&name)
            .bind(notes)
            .bind(module_id)
            .bind(&stored_settings)
            .bind(schema::CURRENT_DRAFT_SCHEMA_VERSION)
            .bind(schema::CURRENT_MODULE_CONTRACT_VERSION)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;
        pcr_storage::sync_project_sequence_asset_refs(
            &mut transaction,
            user_id,
            &id,
            &sequence_references,
        )
        .await
        .map_err(asset_store)?;

        enforce_account_data_limit(&mut transaction, user_id).await?;
        let project = Self::project_in_transaction(&mut transaction, user_id, &id).await?;
        transaction.commit().await.map_err(store)?;

        Ok(project)
    }

    /// Every project this person has, most recently touched first.
    ///
    /// # Errors
    ///
    /// [`ProjectError::Store`] if the database refused.
    pub async fn list(&self, user_id: &str) -> Result<Vec<Project>> {
        let rows = sqlx::query_as::<_, ProjectRow>(
            "SELECT p.id, p.name, p.notes, p.module_id, p.settings, p.draft_schema_version, p.module_contract_version, p.created_at, p.updated_at,
                    (SELECT count(*) FROM runs r WHERE r.project_id = p.id) AS run_count
             FROM projects p
             WHERE p.user_id = $1
             ORDER BY p.updated_at DESC",
        )
        .bind(user_id)
        .fetch_all(&self.pool)
        .await
        .map_err(store)?;

        let mut projects = Vec::with_capacity(rows.len());
        for row in rows {
            projects.push(hydrate_project_row(&self.pool, user_id, row).await?);
        }
        Ok(projects)
    }

    /// One project belonging to this person.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] whether it does not exist or belongs to
    /// somebody else — the two are not distinguished on purpose.
    pub async fn get(&self, user_id: &str, id: &str) -> Result<Project> {
        let row = sqlx::query_as::<_, ProjectRow>(
            "SELECT p.id, p.name, p.notes, p.module_id, p.settings, p.draft_schema_version, p.module_contract_version, p.created_at, p.updated_at,
                    (SELECT count(*) FROM runs r WHERE r.project_id = p.id) AS run_count
             FROM projects p
             WHERE p.user_id = $1 AND p.id = $2",
        )
        .bind(user_id)
        .bind(id)
        .fetch_optional(&self.pool)
        .await
        .map_err(store)?;

        let row = row.ok_or(ProjectError::NotFound)?;
        hydrate_project_row(&self.pool, user_id, row).await
    }

    /// Change what is set on a project. Anything left as `None` is untouched.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] or [`ProjectError::InvalidName`].
    pub async fn update(
        &self,
        user_id: &str,
        id: &str,
        name: Option<&str>,
        notes: Option<&str>,
        settings: Option<&serde_json::Value>,
        expected_updated_at: Option<DateTime<Utc>>,
    ) -> Result<Project> {
        let name = name.map(check_name).transpose()?;
        check_project_data(notes, settings)?;

        let mut transaction = self.pool.begin().await.map_err(store)?;
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
            .bind(user_id)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;

        let (stored_settings, sequence_references) = if let Some(settings) = settings {
            let (stored, references) =
                pcr_storage::externalize_sequence_assets(&mut transaction, user_id, settings)
                    .await
                    .map_err(asset_store)?;
            (Some(stored), Some(references))
        } else {
            (None, None)
        };

        let affected = sqlx::query(
            "UPDATE projects
             SET name = COALESCE($3, name),
                 notes = COALESCE($4, notes),
                 settings = COALESCE($5, settings),
                 draft_schema_version = CASE WHEN $5::jsonb IS NULL THEN draft_schema_version ELSE $7 END,
                 module_contract_version = CASE WHEN $5::jsonb IS NULL THEN module_contract_version ELSE $8 END,
                 updated_at = now()
             WHERE user_id = $1 AND id = $2
               AND ($6::timestamptz IS NULL OR updated_at = $6)",
        )
        .bind(user_id)
        .bind(id)
        .bind(name.as_deref())
        .bind(notes)
        .bind(stored_settings.as_ref())
        .bind(expected_updated_at)
        .bind(schema::CURRENT_DRAFT_SCHEMA_VERSION)
        .bind(schema::CURRENT_MODULE_CONTRACT_VERSION)
        .execute(&mut *transaction)
        .await
        .map_err(store)?
        .rows_affected();

        if affected == 0 {
            let exists = sqlx::query_scalar::<_, bool>(
                "SELECT EXISTS(SELECT 1 FROM projects WHERE user_id = $1 AND id = $2)",
            )
            .bind(user_id)
            .bind(id)
            .fetch_one(&mut *transaction)
            .await
            .map_err(store)?;
            return if exists && expected_updated_at.is_some() {
                Err(ProjectError::Conflict(
                    "This project changed in another tab or browser. Reload it before saving over the newer version.".to_owned(),
                ))
            } else {
                Err(ProjectError::NotFound)
            };
        }
        if let Some(references) = sequence_references.as_deref() {
            pcr_storage::sync_project_sequence_asset_refs(
                &mut transaction,
                user_id,
                id,
                references,
            )
            .await
            .map_err(asset_store)?;
        }
        enforce_account_data_limit(&mut transaction, user_id).await?;
        let project = Self::project_in_transaction(&mut transaction, user_id, id).await?;
        transaction.commit().await.map_err(store)?;
        Ok(project)
    }

    /// The pool behind this store.
    ///
    /// For tests that need to reach past the API — ageing a deletion so a purge
    /// can be checked without waiting a month is the only current use.
    #[must_use]
    pub fn pool(&self) -> &sqlx::PgPool {
        &self.pool
    }

    /// How long a deleted project can still be brought back.
    ///
    /// Long enough that somebody who notices the next morning still can, short
    /// enough that "delete" remains a real answer to "remove my data". The
    /// account-wide export and the account deletion both ignore the window —
    /// asking for everything to go means everything, immediately.
    pub const UNDO_WINDOW_DAYS: i32 = 30;

    /// Delete a project and everything kept in it.
    ///
    /// Recoverable for [`Self::UNDO_WINDOW_DAYS`] and then not: the row is
    /// marked rather than removed, and every ordinary query reads through a
    /// view that cannot see marked rows. The runs are untouched, because they
    /// reference the underlying table — so an undo restores the project with
    /// its history rather than an empty shell of it.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if there was nothing to delete.
    pub async fn delete(&self, user_id: &str, id: &str) -> Result<()> {
        let mut transaction = self.pool.begin().await.map_err(store)?;
        let affected = sqlx::query(
            "UPDATE projects_all SET deleted_at = now()
              WHERE user_id = $1 AND id = $2 AND deleted_at IS NULL",
        )
        .bind(user_id)
        .bind(id)
        .execute(&mut *transaction)
        .await
        .map_err(store)?
        .rows_affected();

        if affected == 0 {
            return Err(ProjectError::NotFound);
        }

        // Deletion is also revocation. A share URL handed to somebody else
        // must not spring back to life merely because the owner later undoes
        // the project deletion. The runs themselves stay for undo; only the
        // externally-held capabilities are destroyed.
        sqlx::query("UPDATE runs SET share_hash = NULL, shared_at = NULL WHERE project_id = $1")
            .bind(id)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;

        transaction.commit().await.map_err(store)?;
        Ok(())
    }

    /// Bring back a project deleted within the window.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] when there is nothing to bring back — which
    /// covers a project that was never deleted, one that belongs to somebody
    /// else, and one deleted long enough ago to have been purged. Those are
    /// deliberately the same answer: distinguishing them would say whether a
    /// stranger's project exists.
    pub async fn restore(&self, user_id: &str, id: &str) -> Result<Project> {
        // Restore competes with create/import for the same live-project quota.
        // Serialize all three on the same per-user advisory lock so two
        // concurrent requests cannot both observe the last free slot.
        let mut transaction = self.pool.begin().await.map_err(store)?;
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
            .bind(user_id)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;

        let existing: i64 = sqlx::query_scalar("SELECT count(*) FROM projects WHERE user_id = $1")
            .bind(user_id)
            .fetch_one(&mut *transaction)
            .await
            .map_err(store)?;
        if existing >= MAX_PROJECTS_PER_USER {
            return Err(ProjectError::TooManyProjects(format!(
                "This account already has {MAX_PROJECTS_PER_USER} projects. Delete one before restoring another."
            )));
        }

        let affected = sqlx::query(
            "UPDATE projects_all SET deleted_at = NULL, updated_at = now()
              WHERE user_id = $1
                AND id = $2
                AND deleted_at IS NOT NULL
                AND deleted_at > now() - make_interval(days => $3)",
        )
        .bind(user_id)
        .bind(id)
        .bind(Self::UNDO_WINDOW_DAYS)
        .execute(&mut *transaction)
        .await
        .map_err(store)?
        .rows_affected();

        if affected == 0 {
            return Err(ProjectError::NotFound);
        }
        enforce_account_data_limit(&mut transaction, user_id).await?;
        let project = Self::project_in_transaction(&mut transaction, user_id, id).await?;
        transaction.commit().await.map_err(store)?;
        Ok(project)
    }

    /// Remove for good everything deleted longer ago than the window.
    ///
    /// Returns how many went. Called on a schedule rather than on a timer per
    /// project: a deletion that has to hold a task open for thirty days is a
    /// deletion that does not survive a restart.
    ///
    /// # Errors
    ///
    /// [`ProjectError::Store`] if the database is unreachable.
    pub async fn purge_deleted(&self) -> Result<u64> {
        Ok(sqlx::query(
            "DELETE FROM projects_all
              WHERE deleted_at IS NOT NULL
                AND deleted_at <= now() - make_interval(days => $1)",
        )
        .bind(Self::UNDO_WINDOW_DAYS)
        .execute(&self.pool)
        .await
        .map_err(store)?
        .rows_affected())
    }

    /// Keep one run, dropping the oldest if the project is full.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if the project is not this person's.
    pub async fn save_run(
        &self,
        user_id: &str,
        project_id: &str,
        label: &str,
        request: &serde_json::Value,
        result: &serde_json::Value,
    ) -> Result<Run> {
        let (run, _) = self
            .save_run_with_project(user_id, project_id, label, request, result)
            .await?;
        Ok(run)
    }

    /// Keep one run and return the project snapshot changed by that same write.
    ///
    /// Both response objects are materialised before commit. This matters to an
    /// HTTP caller: if a database outage starts immediately after the commit, a
    /// successful write must not be reported as a failure merely because the
    /// response tried to read the project in a second transaction.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if the project is not this person's.
    pub async fn save_run_with_project(
        &self,
        user_id: &str,
        project_id: &str,
        label: &str,
        request: &serde_json::Value,
        result: &serde_json::Value,
    ) -> Result<(Run, Project)> {
        check_run_data(label, request, result)?;

        let mut transaction = self.pool.begin().await.map_err(store)?;
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
            .bind(user_id)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;
        let id = self
            .save_run_in_transaction(
                &mut transaction,
                user_id,
                project_id,
                label,
                request,
                result,
            )
            .await?;
        let run = Self::run_in_transaction(&mut transaction, user_id, &id).await?;
        let project = Self::project_in_transaction(&mut transaction, user_id, project_id).await?;
        transaction.commit().await.map_err(store)?;
        Ok((run, project))
    }

    /// Save a completed durable-job result and mark the job completed in the
    /// same PostgreSQL transaction. `None` means cancellation won the row lock
    /// or this executor no longer owns a live lease, so no run was written.
    ///
    /// This atomic boundary is what makes restart recovery safe: there is no
    /// state in which a run committed but its job still looks runnable.
    pub async fn save_run_for_job_with_project(
        &self,
        input: SaveRunForJobInput<'_>,
    ) -> Result<Option<(Run, Project)>> {
        let (user_id, project_id, job_id, executor_id, label, request, result, progress) =
            input.parts();
        check_run_data(label, request, result)?;
        let mut transaction = self.pool.begin().await.map_err(store)?;
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
            .bind(user_id)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;

        let status: Option<String> = sqlx::query_scalar(
            "SELECT status FROM run_jobs
             WHERE user_id=$1 AND id=$2 AND project_id=$3 AND executor_id=$4
               AND lease_expires_at > now()
             FOR UPDATE",
        )
        .bind(user_id)
        .bind(job_id)
        .bind(project_id)
        .bind(executor_id)
        .fetch_optional(&mut *transaction)
        .await
        .map_err(store)?;
        if status.as_deref() != Some("running") {
            return Ok(None);
        }

        let id = self
            .save_run_in_transaction(
                &mut transaction,
                user_id,
                project_id,
                label,
                request,
                result,
            )
            .await?;
        let affected = sqlx::query(
            "UPDATE run_jobs SET status='completed',stage='completed',run_id=$4,progress=$5,error=NULL,
                    finished_at=now(),updated_at=now(),executor_id=NULL,lease_expires_at=NULL
             WHERE user_id=$1 AND id=$2 AND status='running' AND executor_id=$3",
        )
        .bind(user_id)
        .bind(job_id)
        .bind(executor_id)
        .bind(&id)
        .bind(progress)
        .execute(&mut *transaction)
        .await
        .map_err(store)?
        .rows_affected();
        if affected != 1 {
            return Ok(None);
        }
        let run = Self::run_in_transaction(&mut transaction, user_id, &id).await?;
        let project = Self::project_in_transaction(&mut transaction, user_id, project_id).await?;
        transaction.commit().await.map_err(store)?;
        Ok(Some((run, project)))
    }

    async fn project_in_transaction(
        transaction: &mut Transaction<'_, Postgres>,
        user_id: &str,
        id: &str,
    ) -> Result<Project> {
        let row = sqlx::query_as::<_, ProjectRow>(
            "SELECT p.id, p.name, p.notes, p.module_id, p.settings, p.draft_schema_version, p.module_contract_version, p.created_at, p.updated_at,
                    (SELECT count(*) FROM runs r WHERE r.project_id = p.id) AS run_count
             FROM projects p
             WHERE p.user_id = $1 AND p.id = $2",
        )
        .bind(user_id)
        .bind(id)
        .fetch_optional(&mut **transaction)
        .await
        .map_err(store)?;

        let row = row.ok_or(ProjectError::NotFound)?;
        hydrate_project_row_in_transaction(transaction, user_id, row).await
    }

    async fn run_in_transaction(
        transaction: &mut Transaction<'_, Postgres>,
        user_id: &str,
        run_id: &str,
    ) -> Result<Run> {
        let row = sqlx::query_as::<_, RunRow>(
            "SELECT r.id, r.project_id, r.label, r.request, r.result, r.request_schema_version, r.result_schema_version, r.module_contract_version, r.toolchain_fingerprint, r.run_fingerprint, r.engine_id, r.module_id, r.result_count, r.result_unit, r.target_name, r.created_at
             FROM runs r
             JOIN projects p ON p.id = r.project_id
             WHERE p.user_id = $1 AND r.id = $2",
        )
        .bind(user_id)
        .bind(run_id)
        .fetch_optional(&mut **transaction)
        .await
        .map_err(store)?;

        let row = row.ok_or(ProjectError::NotFound)?;
        hydrate_run_row_in_transaction(transaction, user_id, row).await
    }

    async fn restore_run_in_transaction(
        &self,
        transaction: &mut Transaction<'_, Postgres>,
        user_id: &str,
        project_id: &str,
        run: &IncomingRun,
    ) -> Result<String> {
        let owned: bool =
            sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM projects WHERE id=$1 AND user_id=$2)")
                .bind(project_id)
                .bind(user_id)
                .fetch_one(&mut **transaction)
                .await
                .map_err(store)?;
        if !owned {
            return Err(ProjectError::NotFound);
        }

        let taken: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM runs WHERE id=$1)")
            .bind(&run.id)
            .fetch_one(&mut **transaction)
            .await
            .map_err(store)?;
        let id = if taken {
            uuid::Uuid::new_v4().to_string()
        } else {
            run.id.clone()
        };

        let (stored_request, request_refs) =
            pcr_storage::externalize_sequence_assets(transaction, user_id, &run.request)
                .await
                .map_err(asset_store)?;
        let (stored_result, result_refs) =
            pcr_storage::externalize_sequence_assets(transaction, user_id, &run.result)
                .await
                .map_err(asset_store)?;

        sqlx::query(
            "INSERT INTO runs (id, project_id, label, request, result, request_schema_version, result_schema_version,
                 module_contract_version, toolchain_fingerprint, run_fingerprint, engine_id, module_id,
                 result_count, result_unit, target_name, created_at)
             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)",
        )
        .bind(&id)
        .bind(project_id)
        .bind(&run.label)
        .bind(&stored_request)
        .bind(&stored_result)
        .bind(run.request_schema_version)
        .bind(run.result_schema_version)
        .bind(&run.module_contract_version)
        .bind(&run.toolchain_fingerprint)
        .bind(&run.run_fingerprint)
        .bind(&run.engine_id)
        .bind(&run.module_id)
        .bind(run.result_count)
        .bind(&run.result_unit)
        .bind(&run.target_name)
        .bind(run.created_at)
        .execute(&mut **transaction)
        .await
        .map_err(store)?;
        pcr_storage::sync_run_sequence_asset_refs(
            transaction,
            user_id,
            project_id,
            &id,
            "request",
            &request_refs,
        )
        .await
        .map_err(asset_store)?;
        pcr_storage::sync_run_sequence_asset_refs(
            transaction,
            user_id,
            project_id,
            &id,
            "result",
            &result_refs,
        )
        .await
        .map_err(asset_store)?;
        enforce_account_data_limit(transaction, user_id).await?;
        Ok(id)
    }

    async fn save_run_in_transaction(
        &self,
        transaction: &mut Transaction<'_, Postgres>,
        user_id: &str,
        project_id: &str,
        label: &str,
        request: &serde_json::Value,
        result: &serde_json::Value,
    ) -> Result<String> {
        // Enforce the run ceiling under concurrency. Without this lock, two
        // transactions can each insert and trim against a snapshot that does
        // not yet contain the other's row, leaving more than the advertised
        // maximum after both commit.
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 1))")
            .bind(project_id)
            .execute(&mut **transaction)
            .await
            .map_err(store)?;

        let owned_module: Option<String> =
            sqlx::query_scalar("SELECT module_id FROM projects WHERE id = $1 AND user_id = $2")
                .bind(project_id)
                .bind(user_id)
                .fetch_optional(&mut **transaction)
                .await
                .map_err(store)?;
        let Some(module_id) = owned_module else {
            return Err(ProjectError::NotFound);
        };

        let metadata = run_metadata(&module_id, request, result);
        let (stored_request, request_refs) =
            pcr_storage::externalize_sequence_assets(transaction, user_id, request)
                .await
                .map_err(asset_store)?;
        let (stored_result, result_refs) =
            pcr_storage::externalize_sequence_assets(transaction, user_id, result)
                .await
                .map_err(asset_store)?;
        let id = uuid::Uuid::new_v4().to_string();
        sqlx::query(
            "INSERT INTO runs (id, project_id, label, request, result, request_schema_version, result_schema_version, module_contract_version, toolchain_fingerprint, run_fingerprint, engine_id, module_id, result_count, result_unit, target_name)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)",
        )
        .bind(&id)
        .bind(project_id)
        .bind(label.trim())
        .bind(&stored_request)
        .bind(&stored_result)
        .bind(schema::CURRENT_REQUEST_SCHEMA_VERSION)
        .bind(schema::CURRENT_RESULT_SCHEMA_VERSION)
        .bind(schema::CURRENT_MODULE_CONTRACT_VERSION)
        .bind(&metadata.toolchain_fingerprint)
        .bind(&metadata.run_fingerprint)
        .bind(&metadata.engine_id)
        .bind(&metadata.module_id)
        .bind(metadata.result_count)
        .bind(&metadata.result_unit)
        .bind(&metadata.target_name)
        .execute(&mut **transaction)
        .await
        .map_err(store)?;
        pcr_storage::sync_run_sequence_asset_refs(
            transaction,
            user_id,
            project_id,
            &id,
            "request",
            &request_refs,
        )
        .await
        .map_err(asset_store)?;
        pcr_storage::sync_run_sequence_asset_refs(
            transaction,
            user_id,
            project_id,
            &id,
            "result",
            &result_refs,
        )
        .await
        .map_err(asset_store)?;

        // Oldest first, because the one somebody wants back is nearly always
        // the last one they ran.
        sqlx::query(
            "DELETE FROM runs
             WHERE project_id = $1
               AND id NOT IN (
                   SELECT id FROM runs WHERE project_id = $1
                   ORDER BY created_at DESC LIMIT $2
               )",
        )
        .bind(project_id)
        .bind(MAX_RUNS_PER_PROJECT)
        .execute(&mut **transaction)
        .await
        .map_err(store)?;

        sqlx::query("UPDATE projects SET updated_at = now() WHERE id = $1")
            .bind(project_id)
            .execute(&mut **transaction)
            .await
            .map_err(store)?;

        enforce_account_data_limit(transaction, user_id).await?;
        Ok(id)
    }

    /// Every run in a project, newest first, without their results.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if the project is not this person's.
    pub async fn runs(&self, user_id: &str, project_id: &str) -> Result<Vec<RunSummary>> {
        self.get(user_id, project_id).await?;

        /*
         * Results were written by engines across versions — plus, since
         * imports existed, by whatever a document claimed. Older rows do not
         * have the derived result metadata, so calculate a safe fallback for
         * those rows in the same query. Every JSON array length is guarded by
         * `jsonb_typeof`; one malformed legacy result must not take down the
         * whole project listing.
         */
        let rows = sqlx::query_as::<_, RunSummaryRow>(
            "WITH summaries AS (
                 SELECT id, label, created_at, target_name,
                        share_hash IS NOT NULL AS shared,
                        CASE
                            WHEN result_unit <> 'result' THEN result_count
                            WHEN jsonb_typeof(result -> 'sets') = 'array' THEN jsonb_array_length(result -> 'sets')
                            WHEN jsonb_typeof(result -> 'pairs') = 'array' THEN jsonb_array_length(result -> 'pairs')
                            WHEN jsonb_typeof(result -> 'assays') = 'array' THEN jsonb_array_length(result -> 'assays')
                            WHEN jsonb_typeof(result -> 'tiles') = 'array' THEN jsonb_array_length(result -> 'tiles')
                            WHEN jsonb_typeof(result -> 'primers') = 'array' THEN jsonb_array_length(result -> 'primers')
                            WHEN jsonb_typeof(result -> 'junctions') = 'array' THEN jsonb_array_length(result -> 'junctions')
                            ELSE 0
                        END AS result_count,
                        CASE
                            WHEN result_unit <> 'result' THEN result_unit
                            WHEN jsonb_typeof(result -> 'sets') = 'array' THEN 'set'
                            WHEN jsonb_typeof(result -> 'pairs') = 'array' THEN 'pair'
                            WHEN jsonb_typeof(result -> 'assays') = 'array' THEN 'assay'
                            WHEN jsonb_typeof(result -> 'tiles') = 'array' THEN 'tile'
                            WHEN jsonb_typeof(result -> 'primers') = 'array' THEN 'primer'
                            WHEN jsonb_typeof(result -> 'junctions') = 'array' THEN 'junction'
                            ELSE 'result'
                        END AS result_unit
                 FROM runs
                 WHERE project_id = $1
             )
             SELECT id, label, created_at,
                    CASE WHEN result_unit = 'pair' THEN result_count ELSE 0 END AS pair_count,
                    result_count,
                    result_unit,
                    target_name,
                    shared
             FROM summaries
             ORDER BY created_at DESC",
        )
        .bind(project_id)
        .fetch_all(&self.pool)
        .await
        .map_err(store)?;

        Ok(rows.into_iter().map(Into::into).collect())
    }

    /// One run, whole.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if it is not in one of this person's projects.
    pub async fn run(&self, user_id: &str, run_id: &str) -> Result<Run> {
        let row = sqlx::query_as::<_, RunRow>(
            "SELECT r.id, r.project_id, r.label, r.request, r.result, r.request_schema_version, r.result_schema_version, r.module_contract_version, r.toolchain_fingerprint, r.run_fingerprint, r.engine_id, r.module_id, r.result_count, r.result_unit, r.target_name, r.created_at
             FROM runs r
             JOIN projects p ON p.id = r.project_id
             WHERE p.user_id = $1 AND r.id = $2",
        )
        .bind(user_id)
        .bind(run_id)
        .fetch_optional(&self.pool)
        .await
        .map_err(store)?;

        let row = row.ok_or(ProjectError::NotFound)?;
        hydrate_run_row(&self.pool, user_id, row).await
    }

    /// One run addressed through a particular project.
    ///
    /// Nested HTTP resources must check both identifiers. Keeping this check
    /// in the store prevents a route from accidentally authorising a run that
    /// belongs to the caller but not to the project named in its URL.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if either identifier is not this person's
    /// matching project/run pair.
    pub async fn run_in_project(
        &self,
        user_id: &str,
        project_id: &str,
        run_id: &str,
    ) -> Result<Run> {
        let run = self.run(user_id, run_id).await?;
        if run.project_id == project_id {
            Ok(run)
        } else {
            Err(ProjectError::NotFound)
        }
    }

    /// Forget one run.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if it is not in one of this person's projects.
    pub async fn delete_run(&self, user_id: &str, project_id: &str, run_id: &str) -> Result<()> {
        let affected = sqlx::query(
            "DELETE FROM runs
             WHERE id = $1
               AND project_id = $2
               AND project_id IN (SELECT id FROM projects WHERE user_id = $3)",
        )
        .bind(run_id)
        .bind(project_id)
        .bind(user_id)
        .execute(&self.pool)
        .await
        .map_err(store)?
        .rows_affected();

        if affected == 0 {
            return Err(ProjectError::NotFound);
        }
        Ok(())
    }

    /// Bring projects back in from an export.
    ///
    /// The export was a one-way door until this existed: somebody could take
    /// their work out and never put it back — not into a new account, not into
    /// their own instance of a tool whose whole licence is that they may run
    /// one. A backup nothing can restore is a file, not a backup.
    ///
    /// Importing the same document twice does nothing the second time. That is
    /// the property that makes this safe to click when unsure, and it comes
    /// from keeping the original id: a project already held under that id is
    /// counted and skipped rather than duplicated.
    ///
    /// An id already taken by *somebody else* is a different case — ids are
    /// unique across the table, not per account — so the project comes in under
    /// a fresh one rather than being refused. The alternative would let a
    /// stranger's export decide whether yours could be restored.
    ///
    /// The project-count ceiling is honoured per project and refusals are
    /// reported. The account-data ceiling is different: exceeding it aborts the
    /// whole transaction, so a backup restore is never silently partial merely
    /// because this account already contains other live data.
    ///
    /// Before anything is written the whole document is measured against what
    /// this store will hold — shapes and sizes both. An export written by this
    /// server always fits; a file that does not was not one, or has been edited
    /// into something else, and saying so by name beats storing whatever it is.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotAnExport`] for a document that breaks those rules,
    /// naming which; [`ProjectError::Store`] if the database is unreachable.
    pub async fn import(&self, user_id: &str, incoming: &[Incoming]) -> Result<Imported> {
        let mut summary = Imported::default();

        if incoming.len() > MAX_IMPORT_PROJECTS {
            return Err(ProjectError::NotAnExport(format!(
                "An export may contain at most {MAX_IMPORT_PROJECTS} projects."
            )));
        }
        let incoming_bytes = incoming_data_bytes(incoming);
        if incoming_bytes > usize::try_from(MAX_ACCOUNT_DATA_BYTES).unwrap_or(usize::MAX) {
            return Err(ProjectError::NotAnExport(format!(
                "An export may contain at most {MAX_ACCOUNT_DATA_BYTES} bytes of live project data."
            )));
        }

        // Checked before the first row moves, so nothing lands when the
        // document is refused.
        for project in incoming {
            check_incoming(project)?;
        }

        let mut transaction = self.pool.begin().await.map_err(store)?;
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
            .bind(user_id)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;
        let mut held: i64 = sqlx::query_scalar("SELECT count(*) FROM projects WHERE user_id = $1")
            .bind(user_id)
            .fetch_one(&mut *transaction)
            .await
            .map_err(store)?;

        for project in incoming {
            /*
             * Already ours under this id — but in one of two states, and they
             * want opposite answers.
             *
             * Live: the document has been imported before, so there is nothing
             * to do and nothing to call an error either.
             *
             * Deleted: the row is still here holding the id, but the project is
             * gone as far as its owner is concerned. Skipping it would report
             * "already here" about something they cannot see — which is the
             * worst possible answer to somebody restoring a backup precisely
             * because they deleted it by mistake. So the deletion is lifted,
             * which is what importing a backup of it plainly means.
             */
            let existing: Option<(String, Option<DateTime<Utc>>)> = sqlx::query_as(
                "SELECT id, deleted_at FROM projects_all WHERE id = $1 AND user_id = $2",
            )
            .bind(&project.id)
            .bind(user_id)
            .fetch_optional(&mut *transaction)
            .await
            .map_err(store)?;

            if let Some((id, deleted_at)) = existing {
                if deleted_at.is_none() {
                    summary.already_here += 1;
                } else if held >= MAX_PROJECTS_PER_USER {
                    summary.refused += 1;
                } else {
                    let (stored_settings, sequence_references) =
                        pcr_storage::externalize_sequence_assets(
                            &mut transaction,
                            user_id,
                            &project.settings,
                        )
                        .await
                        .map_err(asset_store)?;
                    sqlx::query(
                        "UPDATE projects_all SET deleted_at=NULL,name=$2,notes=$3,module_id=$4,settings=$5,
                                draft_schema_version=$6,module_contract_version=$7,created_at=$8,updated_at=$9
                          WHERE id=$1",
                    )
                    .bind(&id)
                    .bind(&project.name)
                    .bind(&project.notes)
                    .bind(&project.module_id)
                    .bind(&stored_settings)
                    .bind(project.draft_schema_version.unwrap_or(LEGACY_UNRECORDED_DRAFT_SCHEMA_VERSION))
                    .bind(project.module_contract_version.as_deref().unwrap_or("legacy-export-v1-unrecorded"))
                    .bind(project.created_at)
                    .bind(project.updated_at)
                    .execute(&mut *transaction)
                    .await
                    .map_err(store)?;
                    pcr_storage::sync_project_sequence_asset_refs(
                        &mut transaction,
                        user_id,
                        &id,
                        &sequence_references,
                    )
                    .await
                    .map_err(asset_store)?;
                    enforce_account_data_limit(&mut transaction, user_id).await?;
                    summary.restored += 1;
                    held += 1;
                }
                continue;
            }

            if held >= MAX_PROJECTS_PER_USER {
                summary.refused += 1;
                continue;
            }

            let Ok(name) = check_name(&project.name) else {
                summary.refused += 1;
                continue;
            };

            // Free globally, or a new one. Keeping it where possible is what
            // makes a link somebody saved still work after a restore.
            let taken: Option<String> =
                sqlx::query_scalar("SELECT id FROM projects_all WHERE id = $1")
                    .bind(&project.id)
                    .fetch_optional(&mut *transaction)
                    .await
                    .map_err(store)?;
            let id = if taken.is_some() {
                uuid::Uuid::new_v4().to_string()
            } else {
                project.id.clone()
            };

            let (stored_settings, sequence_references) = pcr_storage::externalize_sequence_assets(
                &mut transaction,
                user_id,
                &project.settings,
            )
            .await
            .map_err(asset_store)?;
            sqlx::query(
                "INSERT INTO projects_all (id, user_id, name, notes, module_id, settings, draft_schema_version, module_contract_version, created_at, updated_at)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
            )
            .bind(&id)
            .bind(user_id)
            .bind(&name)
            .bind(&project.notes)
            .bind(&project.module_id)
            .bind(&stored_settings)
            .bind(project.draft_schema_version.unwrap_or(LEGACY_UNRECORDED_DRAFT_SCHEMA_VERSION))
            .bind(project.module_contract_version.as_deref().unwrap_or("legacy-export-v1-unrecorded"))
            .bind(project.created_at)
            .bind(project.updated_at)
            .execute(&mut *transaction)
            .await
            .map_err(store)?;
            pcr_storage::sync_project_sequence_asset_refs(
                &mut transaction,
                user_id,
                &id,
                &sequence_references,
            )
            .await
            .map_err(asset_store)?;

            enforce_account_data_limit(&mut transaction, user_id).await?;
            summary.projects += 1;
            held += 1;

            // Oldest first, so that if there are more than a project keeps, the
            // ones dropped are the ones that would have been dropped anyway.
            for run in project
                .runs
                .iter()
                // Exports are newest-first. Keep the newest ceiling, then
                // insert those oldest-first so storage chronology is preserved.
                .take(usize::try_from(MAX_RUNS_PER_PROJECT).unwrap_or(usize::MAX))
                .rev()
            {
                self.restore_run_in_transaction(&mut transaction, user_id, &id, run)
                    .await?;
                summary.runs += 1;
            }
        }

        transaction.commit().await.map_err(store)?;
        Ok(summary)
    }

    /// Make a link that shows one run to somebody with no account.
    ///
    /// The plain token is returned once and never stored — only its SHA-256 is,
    /// exactly as a session token is handled. A database dump therefore yields
    /// no working links.
    ///
    /// Re-sharing an already-shared run mints a fresh token and invalidates the
    /// old one. That is the behaviour somebody wants when they have shared a
    /// link with the wrong person: there is no separate "rotate", because the
    /// button they will reach for is the one they already know.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if the run is not this person's.
    pub async fn share_run(&self, user_id: &str, project_id: &str, run_id: &str) -> Result<String> {
        let token = pcr_security::BearerToken::generate();
        let affected = sqlx::query(
            "UPDATE runs r
                SET share_hash = $1, shared_at = now()
              WHERE r.id = $2
                AND r.project_id = $3
                AND EXISTS (
                    SELECT 1 FROM projects p
                     WHERE p.id = r.project_id AND p.user_id = $4
                )",
        )
        .bind(&token.hashed)
        .bind(run_id)
        .bind(project_id)
        .bind(user_id)
        .execute(&self.pool)
        .await
        .map_err(store)?
        .rows_affected();

        if affected == 0 {
            return Err(ProjectError::NotFound);
        }
        Ok(token.plain)
    }

    /// Withdraw the link.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if the run is not this person's.
    pub async fn unshare_run(&self, user_id: &str, project_id: &str, run_id: &str) -> Result<()> {
        let affected = sqlx::query(
            "UPDATE runs r
                SET share_hash = NULL, shared_at = NULL
              WHERE r.id = $1
                AND r.project_id = $2
                AND EXISTS (
                    SELECT 1 FROM projects p
                     WHERE p.id = r.project_id AND p.user_id = $3
                )",
        )
        .bind(run_id)
        .bind(project_id)
        .bind(user_id)
        .execute(&self.pool)
        .await
        .map_err(store)?
        .rows_affected();

        if affected == 0 {
            return Err(ProjectError::NotFound);
        }
        Ok(())
    }

    /// Whether this run currently has a link, without saying what it is.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] if the run is not this person's.
    pub async fn is_shared(&self, user_id: &str, project_id: &str, run_id: &str) -> Result<bool> {
        sqlx::query_scalar::<_, bool>(
            "SELECT r.share_hash IS NOT NULL
               FROM runs r
               JOIN projects p ON p.id = r.project_id
              WHERE p.user_id = $1 AND r.project_id = $2 AND r.id = $3",
        )
        .bind(user_id)
        .bind(project_id)
        .bind(run_id)
        .fetch_optional(&self.pool)
        .await
        .map_err(store)?
        .ok_or(ProjectError::NotFound)
    }

    /// The run behind a link.
    ///
    /// The one query in this store that takes no user id, because the token is
    /// the authorisation. It returns the run and nothing around it: not who
    /// owns it, not the project it sits in, not the other runs beside it.
    /// Somebody handed a link to one result has been given one result.
    ///
    /// A deleted project's runs are unreachable here too — the join is through
    /// the view, which cannot see deleted rows. Deleting a project therefore
    /// silently withdraws every link into it, which is the behaviour somebody
    /// deleting it would expect and would be alarmed to find missing.
    ///
    /// # Errors
    ///
    /// [`ProjectError::NotFound`] for a token that matches nothing.
    pub async fn run_by_share(&self, token: &str) -> Result<Run> {
        // Generated share tokens are 32 random bytes encoded as 64 hex chars.
        // Refuse any other path segment before querying so arbitrary URL text
        // never becomes an authorization candidate.
        if !pcr_security::looks_like_bearer_token(token) {
            return Err(ProjectError::NotFound);
        }
        let hashed = pcr_security::hash_bearer_token(token);

        let row = sqlx::query_as::<_, SharedRunRow>(
            "SELECT p.user_id, r.id, r.project_id, r.label, r.request, r.result, r.request_schema_version, r.result_schema_version, r.module_contract_version, r.toolchain_fingerprint, r.run_fingerprint, r.engine_id, r.module_id, r.result_count, r.result_unit, r.target_name, r.created_at
               FROM runs r
               JOIN projects p ON p.id = r.project_id
              WHERE r.share_hash = $1",
        )
        .bind(&hashed)
        .fetch_optional(&self.pool)
        .await
        .map_err(store)?
        .ok_or(ProjectError::NotFound)?;
        let user_id = row.user_id.clone();
        hydrate_run_row(&self.pool, &user_id, row.into_run_row()).await
    }

    /// Every project this person has, with every run inside each one.
    ///
    /// Two queries rather than one per project: an account near the
    /// two-hundred-project ceiling would otherwise mean two hundred round trips
    /// while somebody waits for a download of their own work.
    ///
    /// # Errors
    ///
    /// [`ProjectError::Store`] if the database will not answer.
    pub async fn everything(&self, user_id: &str) -> Result<Vec<(Project, Vec<Run>)>> {
        let projects = self.list(user_id).await?;

        let rows = sqlx::query_as::<_, RunRow>(
            "SELECT r.id, r.project_id, r.label, r.request, r.result, r.request_schema_version, r.result_schema_version, r.module_contract_version, r.toolchain_fingerprint, r.run_fingerprint, r.engine_id, r.module_id, r.result_count, r.result_unit, r.target_name, r.created_at
               FROM runs r
               JOIN projects p ON p.id = r.project_id
              WHERE p.user_id = $1
              ORDER BY r.created_at DESC",
        )
        .bind(user_id)
        .fetch_all(&self.pool)
        .await
        .map_err(store)?;

        let mut by_project: HashMap<String, Vec<Run>> = HashMap::new();
        for row in rows {
            let project_id = row.project_id.clone();
            let run = hydrate_run_row(&self.pool, user_id, row).await?;
            by_project.entry(project_id).or_default().push(run);
        }

        Ok(projects
            .into_iter()
            .map(|project| {
                let runs = by_project.remove(&project.id).unwrap_or_default();
                (project, runs)
            })
            .collect())
    }
}

#[derive(sqlx::FromRow)]
struct ProjectRow {
    id: String,
    name: String,
    notes: String,
    module_id: String,
    settings: serde_json::Value,
    draft_schema_version: i32,
    module_contract_version: String,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
    run_count: i64,
}

impl From<ProjectRow> for Project {
    fn from(row: ProjectRow) -> Self {
        Self {
            id: row.id,
            name: row.name,
            notes: row.notes,
            module_id: row.module_id,
            settings: row.settings,
            draft_schema_version: row.draft_schema_version,
            module_contract_version: row.module_contract_version,
            created_at: row.created_at,
            updated_at: row.updated_at,
            run_count: row.run_count,
        }
    }
}

#[derive(sqlx::FromRow)]
struct RunRow {
    id: String,
    project_id: String,
    label: String,
    request: serde_json::Value,
    result: serde_json::Value,
    request_schema_version: i32,
    result_schema_version: i32,
    module_contract_version: String,
    toolchain_fingerprint: Option<String>,
    run_fingerprint: Option<String>,
    engine_id: Option<String>,
    module_id: Option<String>,
    result_count: i64,
    result_unit: String,
    target_name: String,
    created_at: DateTime<Utc>,
}

impl From<RunRow> for Run {
    fn from(row: RunRow) -> Self {
        Self {
            id: row.id,
            project_id: row.project_id,
            label: row.label,
            request: row.request,
            result: row.result,
            request_schema_version: row.request_schema_version,
            result_schema_version: row.result_schema_version,
            module_contract_version: row.module_contract_version,
            toolchain_fingerprint: row.toolchain_fingerprint,
            run_fingerprint: row.run_fingerprint,
            engine_id: row.engine_id,
            module_id: row.module_id,
            result_count: row.result_count,
            result_unit: row.result_unit,
            target_name: row.target_name,
            created_at: row.created_at,
        }
    }
}

async fn hydrate_project_row(pool: &PgPool, user_id: &str, mut row: ProjectRow) -> Result<Project> {
    row.settings = pcr_storage::hydrate_sequence_assets(pool, user_id, &row.settings)
        .await
        .map_err(asset_store)?;
    Ok(row.into())
}

async fn hydrate_project_row_in_transaction(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    mut row: ProjectRow,
) -> Result<Project> {
    row.settings =
        pcr_storage::hydrate_sequence_assets_in_transaction(transaction, user_id, &row.settings)
            .await
            .map_err(asset_store)?;
    Ok(row.into())
}

async fn hydrate_run_row(pool: &PgPool, user_id: &str, mut row: RunRow) -> Result<Run> {
    row.request = pcr_storage::hydrate_sequence_assets(pool, user_id, &row.request)
        .await
        .map_err(asset_store)?;
    row.result = pcr_storage::hydrate_sequence_assets(pool, user_id, &row.result)
        .await
        .map_err(asset_store)?;
    Ok(row.into())
}

async fn hydrate_run_row_in_transaction(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    mut row: RunRow,
) -> Result<Run> {
    row.request =
        pcr_storage::hydrate_sequence_assets_in_transaction(transaction, user_id, &row.request)
            .await
            .map_err(asset_store)?;
    row.result =
        pcr_storage::hydrate_sequence_assets_in_transaction(transaction, user_id, &row.result)
            .await
            .map_err(asset_store)?;
    Ok(row.into())
}

#[derive(sqlx::FromRow)]
struct SharedRunRow {
    user_id: String,
    id: String,
    project_id: String,
    label: String,
    request: serde_json::Value,
    result: serde_json::Value,
    request_schema_version: i32,
    result_schema_version: i32,
    module_contract_version: String,
    toolchain_fingerprint: Option<String>,
    run_fingerprint: Option<String>,
    engine_id: Option<String>,
    module_id: Option<String>,
    result_count: i64,
    result_unit: String,
    target_name: String,
    created_at: DateTime<Utc>,
}

impl SharedRunRow {
    fn into_run_row(self) -> RunRow {
        RunRow {
            id: self.id,
            project_id: self.project_id,
            label: self.label,
            request: self.request,
            result: self.result,
            request_schema_version: self.request_schema_version,
            result_schema_version: self.result_schema_version,
            module_contract_version: self.module_contract_version,
            toolchain_fingerprint: self.toolchain_fingerprint,
            run_fingerprint: self.run_fingerprint,
            engine_id: self.engine_id,
            module_id: self.module_id,
            result_count: self.result_count,
            result_unit: self.result_unit,
            target_name: self.target_name,
            created_at: self.created_at,
        }
    }
}

#[derive(sqlx::FromRow)]
struct RunSummaryRow {
    id: String,
    label: String,
    created_at: DateTime<Utc>,
    pair_count: i64,
    result_count: i64,
    result_unit: String,
    target_name: String,
    shared: bool,
}

impl From<RunSummaryRow> for RunSummary {
    fn from(row: RunSummaryRow) -> Self {
        Self {
            id: row.id,
            label: row.label,
            created_at: row.created_at,
            pair_count: row.pair_count,
            result_count: row.result_count,
            result_unit: row.result_unit,
            shared: row.shared,
            target_name: row.target_name,
        }
    }
}

#[cfg(test)]
#[path = "project_tests.rs"]
mod tests;
