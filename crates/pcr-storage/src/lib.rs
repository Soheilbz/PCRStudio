//! PCRStudio's ordered database migration authority and immutable foundation
//! storage primitives. The migration directory is embedded by sqlx.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Postgres, Transaction};

mod create_run_input;
pub use create_run_input::CreateRunJobInput;
mod records;
pub use records::{AssayQualification, Attachment, DurableExecutionMetrics, RunnerStatus};

/// Storage-layer failure.
#[derive(Debug, thiserror::Error)]
pub enum StorageError {
    /// A migration could not be applied.
    #[error("database migrations failed: {0}")]
    Migration(String),
    /// A query against Foundation storage failed.
    #[error("database storage operation failed: {0}")]
    Query(String),
    /// A requested owned record does not exist.
    #[error("storage record was not found")]
    NotFound,
    /// Input violates a storage-level invariant.
    #[error("invalid storage input: {0}")]
    Invalid(String),
    /// An idempotency key was reused for a different immutable request.
    #[error("storage conflict: {0}")]
    Conflict(String),
    /// A bounded per-account execution-job quota was reached.
    #[error("storage quota exceeded: {0}")]
    Quota(String),
}

/// Storage result.
pub type Result<T> = std::result::Result<T, StorageError>;

/// Resolve the canonical database connection secret for every PCRStudio process.
///
/// Database connection credentials use the same mutually-exclusive direct/file
/// secret authority as every other deployment secret. Surrounding deployment
/// whitespace is removed consistently and an explicitly selected blank file
/// fails closed.
///
/// # Errors
/// Returns [`pcr_security::SecretSourceError`] when deployment secret resolution
/// fails.
pub fn database_url_from_environment(
) -> std::result::Result<Option<String>, pcr_security::SecretSourceError> {
    let value = pcr_security::secret_from_environment("PCR_DATABASE_URL", "PCR_DATABASE_URL_FILE")?;
    Ok(normalize_database_url_secret(value))
}

fn normalize_database_url_secret(value: Option<String>) -> Option<String> {
    value.and_then(|value| {
        let trimmed = value.trim();
        (!trimmed.is_empty()).then(|| trimmed.to_owned())
    })
}

fn query(error: sqlx::Error) -> StorageError {
    StorageError::Query(error.to_string())
}

/// Apply the single canonical PCRStudio migration history.
///
/// # Errors
/// Returns [`StorageError::Migration`] if schema migration cannot be applied,
/// [`StorageError::Invalid`] when historical rows violate current relational
/// invariants, or [`StorageError::Query`] if the post-migration audit/validation
/// itself cannot be completed.
pub async fn migrate(pool: &PgPool) -> Result<()> {
    sqlx::migrate!("./migrations")
        .run(pool)
        .await
        .map_err(|error| StorageError::Migration(error.to_string()))?;
    validate_post_migration_invariants(pool).await
}

/// Audit historical rows covered by constraints that were introduced with
/// `NOT VALID`, then validate those constraints once the data is known clean.
///
/// `0011_r17_rev4_job_safety.sql` intentionally used PostgreSQL's staged
/// constraint-validation path so an existing database could be upgraded before
/// historical ownership inconsistencies were investigated. Production Linux
/// migration ownership is stricter: the canonical [`migrate`] operation runs
/// this audit after every schema migration, so production, development and test
/// callers all converge on the same validated relational state before they can
/// use the store. Any legacy row that violates the current ownership model
/// therefore blocks the migration boundary itself.
///
/// # Errors
/// Returns [`StorageError::Invalid`] with aggregate violation counts when legacy
/// data is inconsistent, or [`StorageError::Query`] if the audit/validation SQL
/// itself fails.
async fn validate_post_migration_invariants(pool: &PgPool) -> Result<()> {
    let (attachment_missing_project,): (i64,) = sqlx::query_as(
        "SELECT count(*)::bigint FROM attachments WHERE run_id IS NOT NULL AND project_id IS NULL",
    )
    .fetch_one(pool)
    .await
    .map_err(query)?;

    let (attachment_project_owner_mismatch,): (i64,) = sqlx::query_as(
        "SELECT count(*)::bigint
         FROM attachments a
         LEFT JOIN projects_all p ON p.id=a.project_id AND p.user_id=a.user_id
         WHERE a.project_id IS NOT NULL AND p.id IS NULL",
    )
    .fetch_one(pool)
    .await
    .map_err(query)?;

    let (attachment_run_project_mismatch,): (i64,) = sqlx::query_as(
        "SELECT count(*)::bigint
         FROM attachments a
         LEFT JOIN runs r ON r.id=a.run_id AND r.project_id=a.project_id
         WHERE a.run_id IS NOT NULL AND r.id IS NULL",
    )
    .fetch_one(pool)
    .await
    .map_err(query)?;

    let (qualification_project_owner_mismatch,): (i64,) = sqlx::query_as(
        "SELECT count(*)::bigint
         FROM assay_qualifications q
         LEFT JOIN projects_all p ON p.id=q.project_id AND p.user_id=q.user_id
         WHERE p.id IS NULL",
    )
    .fetch_one(pool)
    .await
    .map_err(query)?;

    let (qualification_run_project_mismatch,): (i64,) = sqlx::query_as(
        "SELECT count(*)::bigint
         FROM assay_qualifications q
         LEFT JOIN runs r ON r.id=q.run_id AND r.project_id=q.project_id
         WHERE r.id IS NULL",
    )
    .fetch_one(pool)
    .await
    .map_err(query)?;

    let (run_job_missing_project,): (i64,) =
        sqlx::query_as("SELECT count(*)::bigint FROM run_jobs WHERE project_id IS NULL")
            .fetch_one(pool)
            .await
            .map_err(query)?;

    let (run_job_project_owner_mismatch,): (i64,) = sqlx::query_as(
        "SELECT count(*)::bigint
         FROM run_jobs j
         LEFT JOIN projects_all p ON p.id=j.project_id AND p.user_id=j.user_id
         WHERE p.id IS NULL",
    )
    .fetch_one(pool)
    .await
    .map_err(query)?;

    let (run_job_run_project_mismatch,): (i64,) = sqlx::query_as(
        "SELECT count(*)::bigint
         FROM run_jobs j
         LEFT JOIN runs r ON r.id=j.run_id AND r.project_id=j.project_id
         WHERE j.run_id IS NOT NULL AND r.id IS NULL",
    )
    .fetch_one(pool)
    .await
    .map_err(query)?;

    let total = attachment_missing_project
        + attachment_project_owner_mismatch
        + attachment_run_project_mismatch
        + qualification_project_owner_mismatch
        + qualification_run_project_mismatch
        + run_job_missing_project
        + run_job_project_owner_mismatch
        + run_job_run_project_mismatch;
    if total != 0 {
        return Err(StorageError::Invalid(format!(
            "historical ownership audit failed before constraint validation: \
attachments_without_project={attachment_missing_project}, \
attachment_project_owner_mismatch={attachment_project_owner_mismatch}, \
attachment_run_project_mismatch={attachment_run_project_mismatch}, \
qualification_project_owner_mismatch={qualification_project_owner_mismatch}, \
qualification_run_project_mismatch={qualification_run_project_mismatch}, \
run_job_missing_project={run_job_missing_project}, \
run_job_project_owner_mismatch={run_job_project_owner_mismatch}, \
run_job_run_project_mismatch={run_job_run_project_mismatch}"
        )));
    }

    // Validation does not rewrite the table and is safe after the aggregate
    // audit above. Keep each statement explicit so an operator can identify
    // exactly which invariant PostgreSQL rejected if catalog state drifted.
    for statement in [
        "ALTER TABLE attachments VALIDATE CONSTRAINT attachments_run_requires_project",
        "ALTER TABLE attachments VALIDATE CONSTRAINT attachments_project_owner_fk",
        "ALTER TABLE attachments VALIDATE CONSTRAINT attachments_run_project_fk",
        "ALTER TABLE assay_qualifications VALIDATE CONSTRAINT assay_qualifications_project_owner_fk",
        "ALTER TABLE assay_qualifications VALIDATE CONSTRAINT assay_qualifications_run_project_fk",
        "ALTER TABLE run_jobs VALIDATE CONSTRAINT run_jobs_project_required",
        "ALTER TABLE run_jobs VALIDATE CONSTRAINT run_jobs_project_owner_fk",
        "ALTER TABLE run_jobs VALIDATE CONSTRAINT run_jobs_run_project_fk",
    ] {
        sqlx::query(statement).execute(pool).await.map_err(query)?;
    }

    // Do not make the list above a loophole for a future staged migration.
    // Every canonical migration caller must leave the active application schema
    // fully validated. A future NOT VALID FK/CHECK therefore needs an explicit
    // audit/validation path here instead of silently surviving until a restore
    // drill happens to notice it.
    let remaining: Vec<(String, String)> = sqlx::query_as(
        "SELECT c.conrelid::regclass::text, c.conname
         FROM pg_constraint c
         JOIN pg_namespace n ON n.oid=c.connamespace
         WHERE NOT c.convalidated
           AND c.contype IN ('c','f')
           AND n.nspname=current_schema()
         ORDER BY c.conrelid::regclass::text, c.conname",
    )
    .fetch_all(pool)
    .await
    .map_err(query)?;
    if !remaining.is_empty() {
        let names = remaining
            .into_iter()
            .map(|(table, constraint)| format!("{table}.{constraint}"))
            .collect::<Vec<_>>()
            .join(", ");
        return Err(StorageError::Invalid(format!(
            "migration left unvalidated relational constraints in the active schema: {names}"
        )));
    }
    Ok(())
}

/// Maximum queued/running jobs retained for one account at once.
pub const MAX_ACTIVE_RUN_JOBS_PER_USER: i64 = 8;
/// Maximum total job records retained for one account. Older terminal rows are
/// purged before new insertion; this is a hard backstop against metadata growth.
pub const MAX_RETAINED_RUN_JOBS_PER_USER: i64 = 128;
/// Maximum serialized request payload accepted by the durable job store.
pub const MAX_RUN_JOB_REQUEST_BYTES: usize = pcr_contracts::MAX_RUN_JOB_REQUEST_BYTES;
/// Maximum durable job label retained before the eventual run is saved.
pub const MAX_RUN_JOB_LABEL_BYTES: usize = pcr_contracts::MAX_RUN_LABEL_BYTES;
/// Maximum progress/error JSON retained for one job.
pub const MAX_RUN_JOB_AUX_BYTES: usize = pcr_contracts::MAX_RUN_JOB_AUX_BYTES;
/// Maximum retained durable-job JSON/text footprint per account.
pub const MAX_RUN_JOB_DATA_BYTES_PER_USER: i64 = pcr_contracts::MAX_ACCOUNT_JOB_DATA_BYTES as i64;
/// Terminal jobs older than this are housekeeping data, not scientific history.
/// Completed runs remain immutable in the runs table.
pub const RUN_JOB_RETENTION_DAYS: i32 = 14;
/// Running executors renew this short lease. A crashed process therefore makes
/// its job reclaimable without waiting for a human retry.
pub const RUN_JOB_LEASE_SECONDS: i64 = 15;
/// Runner heartbeat freshness required by production API readiness.
pub const RUNNER_HEARTBEAT_FRESH_SECONDS: i64 = 15;
/// Runner registrations older than this are operational residue and can be purged.
pub const RUNNER_REGISTRATION_RETENTION_SECONDS: i64 = 86_400;

/// One durable design-execution job.
#[derive(Clone, sqlx::FromRow)]
pub struct RunJob {
    /// Stable identifier.
    pub id: String,
    /// Internal owner identifier used for persistence/executor authorization.
    pub user_id: String,
    /// Project receiving the saved run. Database migration validation guarantees this is never null.
    pub project_id: String,
    /// Canonical module id.
    pub module_id: String,
    /// Canonical engine id.
    pub engine_id: String,
    /// Hash over canonical request + contract identity, before tool execution.
    pub request_fingerprint: String,
    /// Optional caller idempotency key.
    pub idempotency_key: Option<String>,
    /// User-visible run label.
    pub label: String,
    /// Raw immutable request executed by the job. This remains persistence-only
    /// and is intentionally absent from [`RunJobState`]/HTTP polling responses.
    pub request: serde_json::Value,
    /// Saved run id after completion.
    pub run_id: Option<String>,
    /// Durable status vocabulary.
    pub status: String,
    /// Last measured execution stage; never a fabricated percentage.
    pub stage: String,
    /// Stage facts/worker telemetry safe for the authenticated owner.
    pub progress: serde_json::Value,
    /// Machine-readable failure payload when failed.
    pub error: Option<serde_json::Value>,
    /// Creation time.
    pub created_at: DateTime<Utc>,
    /// First running time.
    pub started_at: Option<DateTime<Utc>>,
    /// Terminal time.
    pub finished_at: Option<DateTime<Utc>>,
    /// Last status/progress change.
    pub updated_at: DateTime<Utc>,
}

/// Lightweight control-plane projection of a durable execution job.
///
/// The scientific request, owner id and idempotency key remain in [`RunJob`]
/// for executors and creation semantics. Polling/cancellation must not hydrate
/// those potentially multi-MiB persistence-only fields.
#[derive(Debug, Clone, sqlx::FromRow)]
pub struct RunJobState {
    /// Stable identifier.
    pub id: String,
    /// Project receiving the saved run.
    pub project_id: String,
    /// Canonical module id.
    pub module_id: String,
    /// Canonical engine id.
    pub engine_id: String,
    /// Hash over canonical request + contract identity.
    pub request_fingerprint: String,
    /// User-visible run label.
    pub label: String,
    /// Saved run id after completion.
    pub run_id: Option<String>,
    /// Durable status vocabulary.
    pub status: String,
    /// Last measured execution stage.
    pub stage: String,
    /// Stage facts/worker telemetry safe for the authenticated owner.
    pub progress: serde_json::Value,
    /// Machine-readable failure payload when failed.
    pub error: Option<serde_json::Value>,
    /// Creation time.
    pub created_at: DateTime<Utc>,
    /// First running time.
    pub started_at: Option<DateTime<Utc>>,
    /// Terminal time.
    pub finished_at: Option<DateTime<Utc>>,
    /// Last status/progress change.
    pub updated_at: DateTime<Utc>,
}

impl From<RunJob> for RunJobState {
    fn from(job: RunJob) -> Self {
        Self {
            id: job.id,
            project_id: job.project_id,
            module_id: job.module_id,
            engine_id: job.engine_id,
            request_fingerprint: job.request_fingerprint,
            label: job.label,
            run_id: job.run_id,
            status: job.status,
            stage: job.stage,
            progress: job.progress,
            error: job.error,
            created_at: job.created_at,
            started_at: job.started_at,
            finished_at: job.finished_at,
            updated_at: job.updated_at,
        }
    }
}

/// Result of idempotent job creation.
#[derive(Clone)]
pub struct CreatedRunJob {
    /// Existing or newly-created durable job.
    pub job: RunJob,
    /// True only when this call inserted it and should start execution.
    pub created: bool,
}

/// Immutable deduplicated sequence content.
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct SequenceAsset {
    /// Stable id.
    pub id: String,
    /// Owner id.
    pub user_id: String,
    /// SHA-256 of exact stored sequence text.
    pub sha256: String,
    /// Character length.
    pub length: i64,
    /// Declared alphabet (`dna`, `rna`, ...).
    pub alphabet: String,
    /// Exact stored content.
    pub content: String,
    /// Creation time.
    pub created_at: DateTime<Utc>,
}

/// One internal reference produced while large nucleotide text is moved out of
/// a JSON document. Public project/run/job DTOs never expose this shape.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SequenceAssetReference {
    /// RFC 6901-style path of the replaced JSON string.
    pub field_path: String,
    /// Content-addressed asset row used at that path.
    pub asset_id: String,
}

#[derive(Debug, Clone)]
enum DocumentPathPart {
    Key(String),
    Index(usize),
}

#[derive(Debug, Clone)]
struct SequenceCandidate {
    path: Vec<DocumentPathPart>,
    field_path: String,
    content: String,
    alphabet: &'static str,
}

#[derive(Debug, Clone)]
struct SequenceSentinel {
    path: Vec<DocumentPathPart>,
    id: String,
    sha256: String,
    length: i64,
}

fn pointer_escape(value: &str) -> String {
    value.replace('~', "~0").replace('/', "~1")
}

fn pointer_for(path: &[DocumentPathPart]) -> String {
    if path.is_empty() {
        return "/".to_owned();
    }
    path.iter()
        .map(|part| match part {
            DocumentPathPart::Key(key) => pointer_escape(key),
            DocumentPathPart::Index(index) => index.to_string(),
        })
        .fold(String::new(), |mut out, part| {
            out.push('/');
            out.push_str(&part);
            out
        })
}

fn nucleotide_document_alphabet(value: &str) -> Option<&'static str> {
    if value.len() < pcr_contracts::MAX_SEQUENCE_ASSET_EXTERNALIZE_BYTES
        || value.len() > pcr_contracts::MAX_SEQUENCE_BYTES
    {
        return None;
    }
    let mut bases = 0usize;
    let mut invalid = 0usize;
    let mut has_u = false;
    let mut has_t = false;
    let mut fasta = false;
    for line in value.lines() {
        if line.trim_start().starts_with('>') {
            fasta = true;
            continue;
        }
        for ch in line.chars() {
            if ch.is_whitespace() || matches!(ch, '-' | '.' | '*') {
                continue;
            }
            if matches!(
                ch.to_ascii_uppercase(),
                'A' | 'C'
                    | 'G'
                    | 'T'
                    | 'U'
                    | 'R'
                    | 'Y'
                    | 'S'
                    | 'W'
                    | 'K'
                    | 'M'
                    | 'B'
                    | 'D'
                    | 'H'
                    | 'V'
                    | 'N'
            ) {
                bases = bases.saturating_add(1);
                has_u |= ch.eq_ignore_ascii_case(&'u');
                has_t |= ch.eq_ignore_ascii_case(&'t');
            } else {
                invalid = invalid.saturating_add(1);
            }
        }
    }
    if bases < 256 || invalid.saturating_mul(100) > bases.saturating_add(invalid).saturating_mul(2)
    {
        return None;
    }
    if fasta {
        Some("nucleotide-fasta")
    } else if has_u && !has_t {
        Some("rna")
    } else {
        Some("dna")
    }
}

fn collect_sequence_candidates(
    value: &serde_json::Value,
    path: &mut Vec<DocumentPathPart>,
    out: &mut Vec<SequenceCandidate>,
) {
    match value {
        serde_json::Value::String(text) => {
            if let Some(alphabet) = nucleotide_document_alphabet(text) {
                out.push(SequenceCandidate {
                    field_path: pointer_for(path),
                    path: path.clone(),
                    content: text.clone(),
                    alphabet,
                });
            }
        }
        serde_json::Value::Array(values) => {
            for (index, child) in values.iter().enumerate() {
                path.push(DocumentPathPart::Index(index));
                collect_sequence_candidates(child, path, out);
                path.pop();
            }
        }
        serde_json::Value::Object(values) => {
            if values.contains_key("$pcrstudioSequenceAsset") {
                return;
            }
            for (key, child) in values {
                path.push(DocumentPathPart::Key(key.clone()));
                collect_sequence_candidates(child, path, out);
                path.pop();
            }
        }
        _ => {}
    }
}

fn sequence_asset_sentinel(asset: &SequenceAsset) -> serde_json::Value {
    serde_json::json!({
        "$pcrstudioSequenceAsset": {
            "version": 1,
            "id": asset.id,
            "sha256": asset.sha256,
            "length": asset.length,
            "alphabet": asset.alphabet,
        }
    })
}

fn set_document_path(
    root: &mut serde_json::Value,
    path: &[DocumentPathPart],
    replacement: serde_json::Value,
) -> Result<()> {
    if path.is_empty() {
        *root = replacement;
        return Ok(());
    }
    let mut current = root;
    for part in &path[..path.len() - 1] {
        current = match part {
            DocumentPathPart::Key(key) => current.get_mut(key),
            DocumentPathPart::Index(index) => current.get_mut(*index),
        }
        .ok_or_else(|| {
            StorageError::Invalid(
                "sequence-asset document path disappeared during projection".into(),
            )
        })?;
    }
    let Some(last) = path.last() else {
        return Err(StorageError::Invalid(
            "sequence-asset path is unexpectedly empty".into(),
        ));
    };
    match last {
        DocumentPathPart::Key(key) => {
            let object = current.as_object_mut().ok_or_else(|| {
                StorageError::Invalid("sequence-asset parent is not an object".into())
            })?;
            if !object.contains_key(key) {
                return Err(StorageError::Invalid(
                    "sequence-asset key disappeared during projection".into(),
                ));
            }
            object.insert(key.clone(), replacement);
        }
        DocumentPathPart::Index(index) => {
            let array = current.as_array_mut().ok_or_else(|| {
                StorageError::Invalid("sequence-asset parent is not an array".into())
            })?;
            let slot = array.get_mut(*index).ok_or_else(|| {
                StorageError::Invalid("sequence-asset index disappeared during projection".into())
            })?;
            *slot = replacement;
        }
    }
    Ok(())
}

fn collect_sequence_sentinels(
    value: &serde_json::Value,
    path: &mut Vec<DocumentPathPart>,
    out: &mut Vec<SequenceSentinel>,
) -> Result<()> {
    match value {
        serde_json::Value::Array(values) => {
            for (index, child) in values.iter().enumerate() {
                path.push(DocumentPathPart::Index(index));
                collect_sequence_sentinels(child, path, out)?;
                path.pop();
            }
        }
        serde_json::Value::Object(values) => {
            if let Some(raw) = values.get("$pcrstudioSequenceAsset") {
                let raw = raw.as_object().ok_or_else(|| {
                    StorageError::Invalid(
                        "sequence-asset sentinel payload must be an object".into(),
                    )
                })?;
                if raw.get("version").and_then(serde_json::Value::as_i64) != Some(1) {
                    return Err(StorageError::Invalid(
                        "unsupported sequence-asset sentinel version".into(),
                    ));
                }
                let id = raw
                    .get("id")
                    .and_then(serde_json::Value::as_str)
                    .ok_or_else(|| {
                        StorageError::Invalid("sequence-asset sentinel is missing id".into())
                    })?;
                let sha256 = raw
                    .get("sha256")
                    .and_then(serde_json::Value::as_str)
                    .ok_or_else(|| {
                        StorageError::Invalid("sequence-asset sentinel is missing sha256".into())
                    })?;
                let length = raw
                    .get("length")
                    .and_then(serde_json::Value::as_i64)
                    .ok_or_else(|| {
                        StorageError::Invalid("sequence-asset sentinel is missing length".into())
                    })?;
                if uuid::Uuid::parse_str(id).is_err()
                    || sha256.len() != 64
                    || !sha256.bytes().all(|byte| byte.is_ascii_hexdigit())
                    || length < 0
                {
                    return Err(StorageError::Invalid(
                        "sequence-asset sentinel identity is malformed".into(),
                    ));
                }
                out.push(SequenceSentinel {
                    path: path.clone(),
                    id: id.to_owned(),
                    sha256: sha256.to_ascii_lowercase(),
                    length,
                });
                return Ok(());
            }
            for (key, child) in values {
                path.push(DocumentPathPart::Key(key.clone()));
                collect_sequence_sentinels(child, path, out)?;
                path.pop();
            }
        }
        _ => {}
    }
    Ok(())
}

async fn put_sequence_asset_in_transaction(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    alphabet: &str,
    content: &str,
) -> Result<SequenceAsset> {
    let digest = hex::encode(Sha256::digest(content.as_bytes()));
    let id = uuid::Uuid::new_v4().to_string();
    let length = i64::try_from(content.chars().count()).unwrap_or(i64::MAX);
    sqlx::query_as::<_, SequenceAsset>(
        "INSERT INTO sequence_assets (id,user_id,sha256,length,alphabet,content)
         VALUES ($1,$2,$3,$4,$5,$6)
         ON CONFLICT (user_id,sha256) DO UPDATE SET sha256=EXCLUDED.sha256
         RETURNING id,user_id,sha256,length,alphabet,content,created_at",
    )
    .bind(id)
    .bind(user_id)
    .bind(digest)
    .bind(length)
    .bind(alphabet)
    .bind(content)
    .fetch_one(&mut **transaction)
    .await
    .map_err(query)
}

/// Replace large nucleotide/FASTA strings with private content-addressed asset
/// sentinels in the same transaction that persists the owner document.
///
/// Small strings and non-sequence text are left untouched. The returned JSON is
/// an internal storage projection and must be hydrated before crossing a public
/// project/run/job boundary.
pub async fn externalize_sequence_assets(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    value: &serde_json::Value,
) -> Result<(serde_json::Value, Vec<SequenceAssetReference>)> {
    let mut candidates = Vec::new();
    collect_sequence_candidates(value, &mut Vec::new(), &mut candidates);
    if candidates.is_empty() {
        return Ok((value.clone(), Vec::new()));
    }
    let mut projected = value.clone();
    let mut references = Vec::with_capacity(candidates.len());
    for candidate in candidates {
        let asset = put_sequence_asset_in_transaction(
            transaction,
            user_id,
            candidate.alphabet,
            &candidate.content,
        )
        .await?;
        set_document_path(
            &mut projected,
            &candidate.path,
            sequence_asset_sentinel(&asset),
        )?;
        references.push(SequenceAssetReference {
            field_path: candidate.field_path,
            asset_id: asset.id,
        });
    }
    Ok((projected, references))
}

async fn hydrate_sequence_assets_with_transaction(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    value: &serde_json::Value,
) -> Result<serde_json::Value> {
    let mut sentinels = Vec::new();
    collect_sequence_sentinels(value, &mut Vec::new(), &mut sentinels)?;
    if sentinels.is_empty() {
        return Ok(value.clone());
    }
    let mut hydrated = value.clone();
    for sentinel in sentinels {
        let asset = sqlx::query_as::<_, SequenceAsset>(
            "SELECT id,user_id,sha256,length,alphabet,content,created_at
             FROM sequence_assets WHERE user_id=$1 AND id=$2",
        )
        .bind(user_id)
        .bind(&sentinel.id)
        .fetch_optional(&mut **transaction)
        .await
        .map_err(query)?
        .ok_or_else(|| {
            StorageError::Invalid("sequence-asset reference points to missing owned content".into())
        })?;
        if asset.sha256 != sentinel.sha256 || asset.length != sentinel.length {
            return Err(StorageError::Invalid(
                "sequence-asset reference identity does not match stored content".into(),
            ));
        }
        set_document_path(
            &mut hydrated,
            &sentinel.path,
            serde_json::Value::String(asset.content),
        )?;
    }
    Ok(hydrated)
}

/// Hydrate private sequence-asset sentinels while already inside the owner's
/// persistence transaction.
pub async fn hydrate_sequence_assets_in_transaction(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    value: &serde_json::Value,
) -> Result<serde_json::Value> {
    hydrate_sequence_assets_with_transaction(transaction, user_id, value).await
}

/// Hydrate private sequence-asset sentinels from a standalone read path.
pub async fn hydrate_sequence_assets(
    pool: &PgPool,
    user_id: &str,
    value: &serde_json::Value,
) -> Result<serde_json::Value> {
    let mut transaction = pool.begin().await.map_err(query)?;
    let hydrated =
        hydrate_sequence_assets_with_transaction(&mut transaction, user_id, value).await?;
    transaction.commit().await.map_err(query)?;
    Ok(hydrated)
}

/// Replace the asset references owned by one project draft atomically.
pub async fn sync_project_sequence_asset_refs(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    project_id: &str,
    references: &[SequenceAssetReference],
) -> Result<()> {
    sqlx::query("DELETE FROM project_sequence_asset_refs WHERE project_id=$1 AND user_id=$2")
        .bind(project_id)
        .bind(user_id)
        .execute(&mut **transaction)
        .await
        .map_err(query)?;
    for reference in references {
        sqlx::query(
            "INSERT INTO project_sequence_asset_refs (project_id,user_id,field_path,asset_id)
             VALUES ($1,$2,$3,$4)",
        )
        .bind(project_id)
        .bind(user_id)
        .bind(&reference.field_path)
        .bind(&reference.asset_id)
        .execute(&mut **transaction)
        .await
        .map_err(query)?;
    }
    Ok(())
}

/// Replace the asset references for one immutable run document side.
pub async fn sync_run_sequence_asset_refs(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    project_id: &str,
    run_id: &str,
    document_kind: &str,
    references: &[SequenceAssetReference],
) -> Result<()> {
    if !matches!(document_kind, "request" | "result") {
        return Err(StorageError::Invalid(
            "run sequence-asset document kind is invalid".into(),
        ));
    }
    sqlx::query("DELETE FROM run_sequence_asset_refs WHERE run_id=$1 AND document_kind=$2")
        .bind(run_id)
        .bind(document_kind)
        .execute(&mut **transaction)
        .await
        .map_err(query)?;
    for reference in references {
        sqlx::query(
            "INSERT INTO run_sequence_asset_refs (run_id,project_id,user_id,document_kind,field_path,asset_id)
             VALUES ($1,$2,$3,$4,$5,$6)",
        )
        .bind(run_id)
        .bind(project_id)
        .bind(user_id)
        .bind(document_kind)
        .bind(&reference.field_path)
        .bind(&reference.asset_id)
        .execute(&mut **transaction)
        .await
        .map_err(query)?;
    }
    Ok(())
}

/// Replace the sequence assets retained by one durable-job request.
pub async fn sync_run_job_sequence_asset_refs(
    transaction: &mut Transaction<'_, Postgres>,
    user_id: &str,
    job_id: &str,
    references: &[SequenceAssetReference],
) -> Result<()> {
    sqlx::query("DELETE FROM run_job_sequence_asset_refs WHERE job_id=$1 AND user_id=$2")
        .bind(job_id)
        .bind(user_id)
        .execute(&mut **transaction)
        .await
        .map_err(query)?;
    for reference in references {
        sqlx::query(
            "INSERT INTO run_job_sequence_asset_refs (job_id,user_id,field_path,asset_id)
             VALUES ($1,$2,$3,$4)",
        )
        .bind(job_id)
        .bind(user_id)
        .bind(&reference.field_path)
        .bind(&reference.asset_id)
        .execute(&mut **transaction)
        .await
        .map_err(query)?;
    }
    Ok(())
}

/// Neutral Foundation storage adapter.
#[derive(Debug, Clone)]
pub struct FoundationStorage {
    pool: PgPool,
}

impl FoundationStorage {
    /// Use an existing application pool.
    #[must_use]
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    /// Atomically reserve the next outbound slot for one shared external service.
    ///
    /// PostgreSQL is the coordination authority, so horizontally scaled API
    /// replicas consume one service-wide budget instead of one budget per
    /// process. Reservations are bounded by `maximum_wait`: once the shared
    /// queue is farther in the future, the request is rejected without
    /// extending that queue. This prevents a burst of callers from reserving
    /// minutes of future upstream capacity and turning rate limiting into a
    /// self-inflicted availability outage. A replica that crashes after a
    /// successful reservation wastes at most one interval.
    ///
    /// # Errors
    /// Returns [`StorageError::Invalid`] for an unsafe namespace/interval,
    /// [`StorageError::Quota`] when the shared reservation horizon is full, or
    /// [`StorageError::Query`] if PostgreSQL cannot reserve the slot.
    pub async fn reserve_external_service_slot(
        &self,
        namespace: &str,
        minimum_gap: std::time::Duration,
        maximum_wait: std::time::Duration,
    ) -> Result<std::time::Duration> {
        if namespace.is_empty()
            || namespace.len() > 64
            || !namespace
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || b"._:-".contains(&byte))
        {
            return Err(StorageError::Invalid(
                "external-service namespace must be 1-64 ASCII token characters".into(),
            ));
        }
        let milliseconds = i64::try_from(minimum_gap.as_millis())
            .map_err(|_| StorageError::Invalid("external-service interval is too large".into()))?;
        let maximum_wait_ms = i64::try_from(maximum_wait.as_millis()).map_err(|_| {
            StorageError::Invalid("external-service wait horizon is too large".into())
        })?;
        if !(1..=60_000).contains(&milliseconds) {
            return Err(StorageError::Invalid(
                "external-service interval must be between 1 ms and 60 s".into(),
            ));
        }
        if !(0..=60_000).contains(&maximum_wait_ms) {
            return Err(StorageError::Invalid(
                "external-service wait horizon must be between 0 and 60 s".into(),
            ));
        }

        let wait_ms: Option<i64> = sqlx::query_scalar(
            "WITH reserved AS (
                INSERT INTO external_service_slots (namespace,next_allowed_at,updated_at)
                VALUES ($1, now() + ($2 * INTERVAL '1 millisecond'), now())
                ON CONFLICT (namespace) DO UPDATE
                SET next_allowed_at = GREATEST(external_service_slots.next_allowed_at, now())
                                      + ($2 * INTERVAL '1 millisecond'),
                    updated_at = now()
                WHERE GREATEST(external_service_slots.next_allowed_at, now())
                      <= now() + ($3 * INTERVAL '1 millisecond')
                RETURNING next_allowed_at - ($2 * INTERVAL '1 millisecond') AS reserved_at
             )
             SELECT GREATEST(0, CEIL(EXTRACT(EPOCH FROM (reserved_at - now())) * 1000))::bigint
             FROM reserved",
        )
        .bind(namespace)
        .bind(milliseconds)
        .bind(maximum_wait_ms)
        .fetch_optional(&self.pool)
        .await
        .map_err(query)?;
        let wait_ms = wait_ms.ok_or_else(|| {
            StorageError::Quota("external-service reservation horizon is full".into())
        })?;
        Ok(std::time::Duration::from_millis(
            u64::try_from(wait_ms).unwrap_or(u64::MAX),
        ))
    }

    /// Create an execution job, or return the already-created job for the same
    /// owner/project/idempotency key.
    ///
    /// Creation is serialized per account so active-count and byte quotas are
    /// true under concurrency rather than advisory estimates. Terminal rows are
    /// pruned before quota checks; completed scientific runs live independently.
    pub async fn create_run_job(&self, input: CreateRunJobInput<'_>) -> Result<CreatedRunJob> {
        let (
            user_id,
            project_id,
            module_id,
            engine_id,
            request_fingerprint,
            idempotency_key,
            label,
            request,
        ) = input.parts();
        if !request.is_object() {
            return Err(StorageError::Invalid(
                "run-job request must be a JSON object".into(),
            ));
        }
        let request_bytes = serde_json::to_vec(request)
            .map_err(|error| {
                StorageError::Invalid(format!("run-job request is not serializable: {error}"))
            })?
            .len();
        if request_bytes > MAX_RUN_JOB_REQUEST_BYTES {
            return Err(StorageError::Quota(format!(
                "A durable design job may contain at most {MAX_RUN_JOB_REQUEST_BYTES} request bytes."
            )));
        }
        if label.len() > MAX_RUN_JOB_LABEL_BYTES {
            return Err(StorageError::Quota(format!(
                "A durable job label may contain at most {MAX_RUN_JOB_LABEL_BYTES} bytes."
            )));
        }
        if let Some(key) = idempotency_key {
            if key.is_empty() || key.len() > 128 || key.chars().any(char::is_control) {
                return Err(StorageError::Invalid(
                    "idempotency key must be 1-128 printable characters".into(),
                ));
            }
        }

        let mut transaction = self.pool.begin().await.map_err(query)?;
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 2))")
            .bind(user_id)
            .execute(&mut *transaction)
            .await
            .map_err(query)?;

        if let Some(key) = idempotency_key {
            if let Some(job) = sqlx::query_as::<_, RunJob>(
                "SELECT id,user_id,project_id,module_id,engine_id,request_fingerprint,idempotency_key,label,request,run_id,status,stage,progress,error,created_at,started_at,finished_at,updated_at
                 FROM run_jobs WHERE user_id=$1 AND project_id=$2 AND idempotency_key=$3",
            )
            .bind(user_id)
            .bind(project_id)
            .bind(key)
            .fetch_optional(&mut *transaction)
            .await
            .map_err(query)?
            {
                if job.request_fingerprint != request_fingerprint
                    || job.module_id != module_id
                    || job.engine_id != engine_id
                {
                    return Err(StorageError::Conflict(
                        "Idempotency-Key was already used for a different design request".into(),
                    ));
                }
                transaction.commit().await.map_err(query)?;
                return Ok(CreatedRunJob { job, created: false });
            }
        }

        let owned: bool = sqlx::query_scalar(
            "SELECT EXISTS(SELECT 1 FROM projects WHERE user_id=$1 AND id=$2 AND module_id=$3)",
        )
        .bind(user_id)
        .bind(project_id)
        .bind(module_id)
        .fetch_one(&mut *transaction)
        .await
        .map_err(query)?;
        if !owned {
            return Err(StorageError::NotFound);
        }

        let (stored_request, sequence_references) =
            externalize_sequence_assets(&mut transaction, user_id, request).await?;

        sqlx::query(
            "DELETE FROM run_jobs WHERE user_id=$1 AND status IN ('completed','failed','cancelled')
             AND finished_at IS NOT NULL AND finished_at <= now() - make_interval(days => $2)",
        )
        .bind(user_id)
        .bind(RUN_JOB_RETENTION_DAYS)
        .execute(&mut *transaction)
        .await
        .map_err(query)?;

        let active: i64 = sqlx::query_scalar("SELECT count(*) FROM run_jobs WHERE user_id=$1 AND status IN ('queued','running','cancel_requested')")
            .bind(user_id)
            .fetch_one(&mut *transaction)
            .await
            .map_err(query)?;
        if active >= MAX_ACTIVE_RUN_JOBS_PER_USER {
            return Err(StorageError::Quota(format!(
                "This account may have at most {MAX_ACTIVE_RUN_JOBS_PER_USER} active design jobs at once."
            )));
        }

        let total: i64 = sqlx::query_scalar("SELECT count(*) FROM run_jobs WHERE user_id=$1")
            .bind(user_id)
            .fetch_one(&mut *transaction)
            .await
            .map_err(query)?;
        if total >= MAX_RETAINED_RUN_JOBS_PER_USER {
            let remove = total - MAX_RETAINED_RUN_JOBS_PER_USER + 1;
            sqlx::query(
                "DELETE FROM run_jobs WHERE id IN (
                    SELECT id FROM run_jobs WHERE user_id=$1
                    AND status IN ('completed','failed','cancelled')
                    ORDER BY finished_at ASC NULLS FIRST, created_at ASC LIMIT $2
                 )",
            )
            .bind(user_id)
            .bind(remove)
            .execute(&mut *transaction)
            .await
            .map_err(query)?;
        }

        let job_bytes: i64 = sqlx::query_scalar(
            "SELECT
                COALESCE((
                    SELECT sum(
                        pg_column_size(j.request)::bigint + pg_column_size(j.progress)::bigint +
                        COALESCE(pg_column_size(j.error),0)::bigint + octet_length(j.label)::bigint +
                        octet_length(j.module_id)::bigint + octet_length(j.engine_id)::bigint
                    ) FROM run_jobs j WHERE j.user_id=$1
                ),0)::bigint
                + COALESCE((
                    SELECT sum(octet_length(a.content))
                    FROM run_job_sequence_asset_refs ref
                    JOIN sequence_assets a ON a.id=ref.asset_id AND a.user_id=ref.user_id
                    WHERE ref.user_id=$1
                ),0)::bigint",
        )
        .bind(user_id)
        .fetch_one(&mut *transaction)
        .await
        .map_err(query)?;
        let incoming_job_bytes = request_bytes
            .saturating_add(label.len())
            .saturating_add(module_id.len())
            .saturating_add(engine_id.len())
            .saturating_add(256);
        if job_bytes.saturating_add(i64::try_from(incoming_job_bytes).unwrap_or(i64::MAX))
            > MAX_RUN_JOB_DATA_BYTES_PER_USER
        {
            return Err(StorageError::Quota(format!(
                "This account has reached its {MAX_RUN_JOB_DATA_BYTES_PER_USER}-byte durable-job storage limit."
            )));
        }

        let id = uuid::Uuid::new_v4().to_string();
        let inserted = sqlx::query_as::<_, RunJob>(
            "INSERT INTO run_jobs (id,user_id,project_id,module_id,engine_id,request_fingerprint,idempotency_key,label,request,status,stage,progress)
             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'queued','queued',$10)
             ON CONFLICT (user_id,project_id,idempotency_key) WHERE idempotency_key IS NOT NULL
             DO UPDATE SET updated_at=run_jobs.updated_at
             RETURNING id,user_id,project_id,module_id,engine_id,request_fingerprint,idempotency_key,label,request,run_id,status,stage,progress,error,created_at,started_at,finished_at,updated_at",
        )
        .bind(&id)
        .bind(user_id)
        .bind(project_id)
        .bind(module_id)
        .bind(engine_id)
        .bind(request_fingerprint)
        .bind(idempotency_key)
        .bind(label.trim())
        .bind(&stored_request)
        .bind(serde_json::json!({"measured": true, "stage": "queued"}))
        .fetch_one(&mut *transaction)
        .await
        .map_err(query)?;
        if inserted.request_fingerprint != request_fingerprint
            || inserted.module_id != module_id
            || inserted.engine_id != engine_id
        {
            return Err(StorageError::Conflict(
                "Idempotency-Key was concurrently reused for a different design request".into(),
            ));
        }
        let created = inserted.id == id;
        sync_run_job_sequence_asset_refs(
            &mut transaction,
            user_id,
            &inserted.id,
            &sequence_references,
        )
        .await?;
        transaction.commit().await.map_err(query)?;
        Ok(CreatedRunJob {
            job: inserted,
            created,
        })
    }

    /// Read one owner/project-scoped job lifecycle without hydrating its request.
    pub async fn run_job_state(
        &self,
        user_id: &str,
        project_id: &str,
        id: &str,
    ) -> Result<RunJobState> {
        sqlx::query_as::<_, RunJobState>(
            "SELECT id,project_id,module_id,engine_id,request_fingerprint,label,run_id,status,stage,progress,error,created_at,started_at,finished_at,updated_at
             FROM run_jobs WHERE user_id=$1 AND project_id=$2 AND id=$3",
        )
        .bind(user_id)
        .bind(project_id)
        .bind(id)
        .fetch_optional(&self.pool)
        .await
        .map_err(query)?
        .ok_or(StorageError::NotFound)
    }

    /// Atomically claim a queued job for one executor and start its lease.
    /// False means another executor claimed it or the owner cancelled it first.
    pub async fn mark_run_job_running(
        &self,
        user_id: &str,
        id: &str,
        executor_id: &str,
    ) -> Result<bool> {
        Ok(sqlx::query(
            "UPDATE run_jobs SET status='running',stage='executing',started_at=COALESCE(started_at,now()),updated_at=now(),
                    executor_id=$3, lease_expires_at=now() + ($4::bigint * interval '1 second'), progress=$5
             WHERE user_id=$1 AND id=$2 AND status='queued'",
        )
        .bind(user_id)
        .bind(id)
        .bind(executor_id)
        .bind(RUN_JOB_LEASE_SECONDS)
        .bind(serde_json::json!({"measured": true, "stage": "executing"}))
        .execute(&self.pool)
        .await
        .map_err(query)?
        .rows_affected()
            == 1)
    }

    /// Renew a running job lease and report whether cancellation was requested.
    /// `None` means this executor no longer owns an active lease and must stop.
    pub async fn heartbeat_run_job(
        &self,
        user_id: &str,
        id: &str,
        executor_id: &str,
    ) -> Result<Option<bool>> {
        let status: Option<String> = sqlx::query_scalar(
            "UPDATE run_jobs SET lease_expires_at=now() + ($4::bigint * interval '1 second'), updated_at=now()
             WHERE user_id=$1 AND id=$2 AND executor_id=$3 AND status IN ('running','cancel_requested')
             RETURNING status",
        )
        .bind(user_id)
        .bind(id)
        .bind(executor_id)
        .bind(RUN_JOB_LEASE_SECONDS)
        .fetch_optional(&self.pool)
        .await
        .map_err(query)?;
        Ok(status.map(|value| value == "cancel_requested"))
    }

    /// Update a queued job with a measured scheduler stage.
    ///
    /// Running rows are executor-owned and may only be mutated through the
    /// lease-scoped helpers below; a duplicate dispatcher must not overwrite
    /// the active executor's stage/progress.
    pub async fn update_run_job_stage(
        &self,
        user_id: &str,
        id: &str,
        stage: &str,
        progress: &serde_json::Value,
    ) -> Result<()> {
        if stage.trim().is_empty() || stage.len() > 80 {
            return Err(StorageError::Invalid(
                "job stage must be 1-80 characters".into(),
            ));
        }
        if serde_json::to_vec(progress).map_or(usize::MAX, |bytes| bytes.len())
            > MAX_RUN_JOB_AUX_BYTES
        {
            return Err(StorageError::Quota(format!(
                "Job progress may contain at most {MAX_RUN_JOB_AUX_BYTES} bytes."
            )));
        }
        let affected = sqlx::query(
            "UPDATE run_jobs SET stage=$3,progress=$4,updated_at=now()
             WHERE user_id=$1 AND id=$2 AND status='queued'",
        )
        .bind(user_id)
        .bind(id)
        .bind(stage)
        .bind(progress)
        .execute(&self.pool)
        .await
        .map_err(query)?
        .rows_affected();
        if affected == 1 {
            Ok(())
        } else {
            Err(StorageError::NotFound)
        }
    }

    /// Request cancellation inside one owner/project boundary. Queued work
    /// becomes terminal immediately; running work moves to `cancel_requested`
    /// until the worker is killed/reaped. The returned control-plane snapshot
    /// deliberately excludes the immutable scientific request.
    pub async fn request_run_job_cancel(
        &self,
        user_id: &str,
        project_id: &str,
        id: &str,
    ) -> Result<RunJobState> {
        sqlx::query_as::<_, RunJobState>(
            "UPDATE run_jobs
             SET status=CASE WHEN status='queued' THEN 'cancelled' WHEN status='running' THEN 'cancel_requested' ELSE status END,
                 stage=CASE WHEN status='queued' THEN 'cancelled' WHEN status='running' THEN 'cancelling' ELSE stage END,
                 finished_at=CASE WHEN status='queued' THEN now() ELSE finished_at END,
                 updated_at=now()
             WHERE user_id=$1 AND project_id=$2 AND id=$3
             RETURNING id,project_id,module_id,engine_id,request_fingerprint,label,run_id,status,stage,progress,error,created_at,started_at,finished_at,updated_at",
        )
        .bind(user_id)
        .bind(project_id)
        .bind(id)
        .fetch_optional(&self.pool)
        .await
        .map_err(query)?
        .ok_or(StorageError::NotFound)
    }

    /// Whether a running worker should cooperatively stop.
    pub async fn run_job_cancel_requested(&self, user_id: &str, id: &str) -> Result<bool> {
        let status: Option<String> =
            sqlx::query_scalar("SELECT status FROM run_jobs WHERE user_id=$1 AND id=$2")
                .bind(user_id)
                .bind(id)
                .fetch_optional(&self.pool)
                .await
                .map_err(query)?;
        match status.as_deref() {
            Some("cancel_requested" | "cancelled") => Ok(true),
            Some(_) => Ok(false),
            None => Err(StorageError::NotFound),
        }
    }

    /// Mark a still-queued malformed/unrunnable job failed with a redacted error.
    /// Running work is lease-owned and must use `fail_run_job_for_executor`.
    pub async fn fail_run_job(
        &self,
        user_id: &str,
        id: &str,
        error_value: &serde_json::Value,
    ) -> Result<()> {
        if serde_json::to_vec(error_value).map_or(usize::MAX, |bytes| bytes.len())
            > MAX_RUN_JOB_AUX_BYTES
        {
            return Err(StorageError::Quota(format!(
                "Job error payload may contain at most {MAX_RUN_JOB_AUX_BYTES} bytes."
            )));
        }
        sqlx::query(
            "UPDATE run_jobs SET status='failed',stage='failed',error=$3,finished_at=now(),updated_at=now(),executor_id=NULL,lease_expires_at=NULL
             WHERE user_id=$1 AND id=$2 AND status='queued'",
        )
        .bind(user_id)
        .bind(id)
        .bind(error_value)
        .execute(&self.pool)
        .await
        .map_err(query)?;
        Ok(())
    }

    /// Mark a running job failed only if this exact executor still owns the
    /// unexpired lease. A stale/crashed executor must never overwrite a job
    /// that has already been reclaimed by another process.
    pub async fn fail_run_job_for_executor(
        &self,
        user_id: &str,
        id: &str,
        executor_id: &str,
        error_value: &serde_json::Value,
    ) -> Result<bool> {
        if serde_json::to_vec(error_value).map_or(usize::MAX, |bytes| bytes.len())
            > MAX_RUN_JOB_AUX_BYTES
        {
            return Err(StorageError::Quota(format!(
                "Job error payload may contain at most {MAX_RUN_JOB_AUX_BYTES} bytes."
            )));
        }
        Ok(sqlx::query(
            "UPDATE run_jobs SET status='failed',stage='failed',error=$4,finished_at=now(),updated_at=now(),executor_id=NULL,lease_expires_at=NULL
             WHERE user_id=$1 AND id=$2 AND executor_id=$3 AND status='running' AND lease_expires_at > now()",
        )
        .bind(user_id)
        .bind(id)
        .bind(executor_id)
        .bind(error_value)
        .execute(&self.pool)
        .await
        .map_err(query)?
        .rows_affected()
            == 1)
    }

    /// Mark cancellation acknowledged only if this executor still owns the
    /// cancelling row. This keeps a duplicate dispatcher from declaring a
    /// remote worker cancelled before that worker has actually stopped.
    pub async fn cancel_run_job_for_executor(
        &self,
        user_id: &str,
        id: &str,
        executor_id: &str,
    ) -> Result<bool> {
        Ok(sqlx::query(
            "UPDATE run_jobs SET status='cancelled',stage='cancelled',finished_at=now(),updated_at=now(),executor_id=NULL,lease_expires_at=NULL
             WHERE user_id=$1 AND id=$2 AND executor_id=$3 AND status='cancel_requested'",
        )
        .bind(user_id)
        .bind(id)
        .bind(executor_id)
        .execute(&self.pool)
        .await
        .map_err(query)?
        .rows_affected()
            == 1)
    }

    /// Reclaim expired executor leases without hydrating scientific requests.
    ///
    /// Recovery is a durable state mutation, not a dispatch source: the next
    /// bounded queue read decides what this runner can actually execute. Keeping
    /// the UPDATE result as a row count avoids loading up to 256 multi-MiB
    /// request payloads merely to throw them away.
    pub async fn recover_stale_run_jobs(&self) -> Result<u64> {
        let mut transaction = self.pool.begin().await.map_err(query)?;
        let cancelled = sqlx::query(
            "WITH stale AS (
                 SELECT id FROM run_jobs
                 WHERE status='cancel_requested' AND (lease_expires_at IS NULL OR lease_expires_at < now())
                 ORDER BY COALESCE(lease_expires_at, updated_at), id
                 LIMIT 256 FOR UPDATE SKIP LOCKED
             )
             UPDATE run_jobs AS job
             SET status='cancelled',stage='cancelled',finished_at=COALESCE(job.finished_at,now()),
                 executor_id=NULL,lease_expires_at=NULL,updated_at=now()
             FROM stale WHERE job.id=stale.id",
        )
        .execute(&mut *transaction)
        .await
        .map_err(query)?
        .rows_affected();
        let requeued = sqlx::query(
            "WITH stale AS (
                 SELECT id FROM run_jobs
                 WHERE status='running' AND (lease_expires_at IS NULL OR lease_expires_at < now())
                 ORDER BY COALESCE(lease_expires_at, updated_at), id
                 LIMIT 256 FOR UPDATE SKIP LOCKED
             )
             UPDATE run_jobs AS job
             SET status='queued',stage='recovered-after-restart',executor_id=NULL,lease_expires_at=NULL,updated_at=now(),
                 progress=jsonb_build_object('measured',true,'stage','recovered-after-restart')
             FROM stale WHERE job.id=stale.id",
        )
        .execute(&mut *transaction)
        .await
        .map_err(query)?
        .rows_affected();
        transaction.commit().await.map_err(query)?;
        Ok(cancelled.saturating_add(requeued))
    }

    /// List only as many queued jobs as the caller can dispatch immediately.
    ///
    /// A run-job request may be several MiB. Loading a fixed 256-row backlog
    /// therefore turns a harmless queue poll into a multi-GiB allocation even
    /// though one runner can execute only a small bounded number of jobs. The
    /// durable queue stays in PostgreSQL; callers ask only for their current
    /// free dispatch capacity.
    pub async fn queued_run_jobs(&self, dispatch_capacity: usize) -> Result<Vec<RunJob>> {
        if !(1..=16).contains(&dispatch_capacity) {
            return Err(StorageError::Invalid(format!(
                "queued job dispatch capacity must be 1..=16, got {dispatch_capacity}"
            )));
        }
        let limit = i64::try_from(dispatch_capacity).map_err(|_| {
            StorageError::Invalid("queued job dispatch capacity does not fit i64".into())
        })?;
        let mut jobs = sqlx::query_as::<_, RunJob>(
            "SELECT id,user_id,project_id,module_id,engine_id,request_fingerprint,idempotency_key,label,request,run_id,status,stage,progress,error,created_at,started_at,finished_at,updated_at
             FROM run_jobs WHERE status='queued' ORDER BY created_at ASC LIMIT $1",
        )
        .bind(limit)
        .fetch_all(&self.pool)
        .await
        .map_err(query)?;
        for job in &mut jobs {
            job.request = hydrate_sequence_assets(&self.pool, &job.user_id, &job.request).await?;
        }
        Ok(jobs)
    }

    /// Cross-process durable queue and runner telemetry for operator diagnostics.
    ///
    /// The database is the coordination authority for external execution, so
    /// production observability must read this state rather than infer runner
    /// health from the API process's local admission gate.
    pub async fn durable_execution_metrics(&self) -> Result<DurableExecutionMetrics> {
        let (queued_jobs, running_jobs, cancel_requested_jobs, oldest_queued_seconds): (
            i64,
            i64,
            i64,
            f64,
        ) = sqlx::query_as(
            "SELECT
                 count(*) FILTER (WHERE status='queued')::bigint,
                 count(*) FILTER (WHERE status='running')::bigint,
                 count(*) FILTER (WHERE status='cancel_requested')::bigint,
                 COALESCE(
                     EXTRACT(EPOCH FROM (now() - MIN(created_at) FILTER (WHERE status='queued'))),
                     0
                 )::double precision
             FROM run_jobs",
        )
        .fetch_one(&self.pool)
        .await
        .map_err(query)?;

        let (fresh_runner_instances, fresh_runner_capacity): (i64, i64) = sqlx::query_as(
            "SELECT count(*)::bigint, COALESCE(sum(worker_capacity),0)::bigint
             FROM runner_instances
             WHERE heartbeat_at > now() - ($1::bigint * interval '1 second')",
        )
        .bind(RUNNER_HEARTBEAT_FRESH_SECONDS)
        .fetch_one(&self.pool)
        .await
        .map_err(query)?;

        Ok(DurableExecutionMetrics {
            queued_jobs,
            running_jobs,
            cancel_requested_jobs,
            oldest_queued_seconds,
            fresh_runner_instances,
            fresh_runner_capacity,
        })
    }

    /// Register or refresh one dedicated scientific runner.
    ///
    /// The row is operational presence only; durable jobs remain authoritative
    /// in `run_jobs`. A random process id prevents a restarted container from
    /// inheriting the liveness identity of the process it replaced.
    pub async fn heartbeat_runner(
        &self,
        id: &str,
        release_version: &str,
        build_identity: &str,
        worker_capacity: i32,
        scientific_freeze_sha256: Option<&str>,
    ) -> Result<()> {
        if pcr_security::canonical_sha256(build_identity).is_none() {
            return Err(StorageError::Invalid(
                "runner build identity must be a lowercase SHA-256 hex digest".into(),
            ));
        }
        if !(1..=16).contains(&worker_capacity) {
            return Err(StorageError::Invalid(format!(
                "runner worker capacity must be 1..=16, got {worker_capacity}"
            )));
        }
        if scientific_freeze_sha256
            .is_some_and(|value| pcr_security::canonical_sha256(value).is_none())
        {
            return Err(StorageError::Invalid(
                "runner scientific freeze must be a lowercase SHA-256 hex digest".into(),
            ));
        }
        sqlx::query(
            "INSERT INTO runner_instances
                 (id,release_version,build_identity,worker_capacity,scientific_freeze_sha256,started_at,heartbeat_at)
             VALUES ($1,$2,$3,$4,$5,now(),now())
             ON CONFLICT (id) DO UPDATE SET
                 release_version=EXCLUDED.release_version,
                 build_identity=EXCLUDED.build_identity,
                 worker_capacity=EXCLUDED.worker_capacity,
                 scientific_freeze_sha256=EXCLUDED.scientific_freeze_sha256,
                 heartbeat_at=now()",
        )
        .bind(id)
        .bind(release_version)
        .bind(build_identity)
        .bind(worker_capacity)
        .bind(scientific_freeze_sha256)
        .execute(&self.pool)
        .await
        .map_err(query)?;
        Ok(())
    }

    /// Aggregate runners whose heartbeat is fresh and, when supplied, whose
    /// scientific Python freeze exactly matches the API's approved freeze.
    pub async fn active_runner_status(
        &self,
        freshness_seconds: i64,
        expected_release_version: &str,
        expected_build_identity: &str,
        expected_freeze_sha256: Option<&str>,
    ) -> Result<RunnerStatus> {
        if freshness_seconds <= 0 || freshness_seconds > 300 {
            return Err(StorageError::Invalid(
                "runner readiness freshness must be 1..=300 seconds".into(),
            ));
        }
        let (instances, worker_capacity): (i64, i64) = sqlx::query_as(
            "SELECT count(*)::bigint, COALESCE(sum(worker_capacity),0)::bigint
             FROM runner_instances
             WHERE heartbeat_at > now() - ($1::bigint * interval '1 second')
               AND release_version = $2
               AND build_identity = $3
               AND ($4::text IS NULL OR scientific_freeze_sha256 = $4)",
        )
        .bind(freshness_seconds)
        .bind(expected_release_version)
        .bind(expected_build_identity)
        .bind(expected_freeze_sha256)
        .fetch_one(&self.pool)
        .await
        .map_err(query)?;
        Ok(RunnerStatus {
            instances,
            worker_capacity,
        })
    }

    /// Whether one exact runner instance is fresh and matches this release.
    ///
    /// Container healthchecks use the instance-scoped form rather than the
    /// aggregate readiness query so one healthy replica cannot accidentally
    /// mask a different wedged runner container.
    pub async fn runner_is_fresh(
        &self,
        id: &str,
        freshness_seconds: i64,
        expected_release_version: &str,
        expected_build_identity: &str,
        expected_freeze_sha256: Option<&str>,
    ) -> Result<bool> {
        if id.trim().is_empty() {
            return Err(StorageError::Invalid("runner id cannot be empty".into()));
        }
        if freshness_seconds <= 0 || freshness_seconds > 300 {
            return Err(StorageError::Invalid(
                "runner readiness freshness must be 1..=300 seconds".into(),
            ));
        }
        sqlx::query_scalar(
            "SELECT EXISTS(
                 SELECT 1 FROM runner_instances
                 WHERE id=$1
                   AND heartbeat_at > now() - ($2::bigint * interval '1 second')
                   AND release_version=$3
                   AND build_identity=$4
                   AND ($5::text IS NULL OR scientific_freeze_sha256=$5)
             )",
        )
        .bind(id)
        .bind(freshness_seconds)
        .bind(expected_release_version)
        .bind(expected_build_identity)
        .bind(expected_freeze_sha256)
        .fetch_one(&self.pool)
        .await
        .map_err(query)
    }

    /// Remove one cleanly-stopped runner registration immediately.
    pub async fn unregister_runner(&self, id: &str) -> Result<()> {
        sqlx::query("DELETE FROM runner_instances WHERE id=$1")
            .bind(id)
            .execute(&self.pool)
            .await
            .map_err(query)?;
        Ok(())
    }

    /// Purge stale runner registrations left by crashes or forced container kills.
    pub async fn purge_stale_runners(&self) -> Result<u64> {
        Ok(sqlx::query(
            "DELETE FROM runner_instances
             WHERE heartbeat_at <= now() - ($1::bigint * interval '1 second')",
        )
        .bind(RUNNER_REGISTRATION_RETENTION_SECONDS)
        .execute(&self.pool)
        .await
        .map_err(query)?
        .rows_affected())
    }

    /// Purge terminal job envelopes after their retention window. Saved runs
    /// and their provenance are independent and are never removed here.
    pub async fn purge_terminal_run_jobs(&self) -> Result<u64> {
        Ok(sqlx::query(
            "DELETE FROM run_jobs WHERE status IN ('completed','failed','cancelled')
             AND finished_at IS NOT NULL AND finished_at <= now() - make_interval(days => $1)",
        )
        .bind(RUN_JOB_RETENTION_DAYS)
        .execute(&self.pool)
        .await
        .map_err(query)?
        .rows_affected())
    }

    /// Remove deduplicated sequence blobs no longer referenced by a project,
    /// durable job, or immutable run. Foreign-key cascades remove references
    /// first; this pass performs the final content garbage collection.
    pub async fn purge_unreferenced_sequence_assets(&self) -> Result<u64> {
        Ok(sqlx::query(
            "DELETE FROM sequence_assets a
             WHERE NOT EXISTS (SELECT 1 FROM project_sequence_asset_refs p WHERE p.asset_id=a.id AND p.user_id=a.user_id)
               AND NOT EXISTS (SELECT 1 FROM run_sequence_asset_refs r WHERE r.asset_id=a.id AND r.user_id=a.user_id)
               AND NOT EXISTS (SELECT 1 FROM run_job_sequence_asset_refs j WHERE j.asset_id=a.id AND j.user_id=a.user_id)",
        )
        .execute(&self.pool)
        .await
        .map_err(query)?
        .rows_affected())
    }

    /// Store or reuse exact sequence content by owner and SHA-256.
    pub async fn put_sequence_asset(
        &self,
        user_id: &str,
        alphabet: &str,
        content: &str,
    ) -> Result<SequenceAsset> {
        let digest = hex::encode(Sha256::digest(content.as_bytes()));
        let id = uuid::Uuid::new_v4().to_string();
        let length = i64::try_from(content.chars().count()).unwrap_or(i64::MAX);
        sqlx::query_as::<_, SequenceAsset>(
            "INSERT INTO sequence_assets (id,user_id,sha256,length,alphabet,content)
             VALUES ($1,$2,$3,$4,$5,$6)
             ON CONFLICT (user_id,sha256) DO UPDATE SET sha256=EXCLUDED.sha256
             RETURNING id,user_id,sha256,length,alphabet,content,created_at",
        )
        .bind(id)
        .bind(user_id)
        .bind(digest)
        .bind(length)
        .bind(alphabet)
        .bind(content)
        .fetch_one(&self.pool)
        .await
        .map_err(query)
    }

    /// Record hashed attachment metadata. Raw bytes stay in the configured immutable blob store.
    #[allow(clippy::too_many_arguments)]
    pub async fn add_attachment(
        &self,
        user_id: &str,
        project_id: Option<&str>,
        run_id: Option<&str>,
        sha256: &str,
        media_type: &str,
        file_name: &str,
        byte_length: i64,
        storage_key: &str,
    ) -> Result<Attachment> {
        if byte_length < 0 || sha256.len() != 64 || !sha256.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(StorageError::Invalid(
                "attachment hash/length is invalid".into(),
            ));
        }
        if run_id.is_some() && project_id.is_none() {
            return Err(StorageError::Invalid(
                "an attachment linked to a run must also name that run's project".into(),
            ));
        }
        if let Some(project_id) = project_id {
            let owned: bool = if let Some(run_id) = run_id {
                sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM projects p JOIN runs r ON r.project_id=p.id WHERE p.user_id=$1 AND p.id=$2 AND r.id=$3)")
                    .bind(user_id)
                    .bind(project_id)
                    .bind(run_id)
                    .fetch_one(&self.pool)
                    .await
                    .map_err(query)?
            } else {
                sqlx::query_scalar(
                    "SELECT EXISTS(SELECT 1 FROM projects WHERE user_id=$1 AND id=$2)",
                )
                .bind(user_id)
                .bind(project_id)
                .fetch_one(&self.pool)
                .await
                .map_err(query)?
            };
            if !owned {
                return Err(StorageError::NotFound);
            }
        }
        let id = uuid::Uuid::new_v4().to_string();
        sqlx::query_as::<_, Attachment>(
            "INSERT INTO attachments (id,user_id,project_id,run_id,sha256,media_type,file_name,byte_length,storage_key)
             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
             RETURNING id,user_id,project_id,run_id,sha256,media_type,file_name,byte_length,storage_key,created_at",
        )
        .bind(id)
        .bind(user_id)
        .bind(project_id)
        .bind(run_id)
        .bind(sha256.to_ascii_lowercase())
        .bind(media_type)
        .bind(file_name)
        .bind(byte_length)
        .bind(storage_key)
        .fetch_one(&self.pool)
        .await
        .map_err(query)
    }

    /// Add immutable wet-lab qualification evidence to a historical run.
    #[allow(clippy::too_many_arguments)]
    pub async fn add_qualification(
        &self,
        user_id: &str,
        project_id: &str,
        run_id: &str,
        sop_id: Option<&str>,
        instrument_identity: Option<&str>,
        kit_lot: Option<&str>,
        operator_ref: Option<&str>,
        experiment_date: Option<NaiveDate>,
        matrix: Option<&str>,
        lod_summary: Option<&serde_json::Value>,
        reproducibility_summary: Option<&serde_json::Value>,
        acceptance_criteria: &serde_json::Value,
        evidence: &serde_json::Value,
    ) -> Result<AssayQualification> {
        let id = uuid::Uuid::new_v4().to_string();
        sqlx::query_as::<_, AssayQualification>(
            "INSERT INTO assay_qualifications (id,user_id,project_id,run_id,sop_id,instrument_identity,kit_lot,operator_ref,experiment_date,matrix,lod_summary,reproducibility_summary,acceptance_criteria,evidence)
             SELECT $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14
             WHERE EXISTS (SELECT 1 FROM projects p JOIN runs r ON r.project_id=p.id WHERE p.user_id=$2 AND p.id=$3 AND r.id=$4)
             RETURNING id,user_id,project_id,run_id,evidence_schema_version,sop_id,instrument_identity,kit_lot,operator_ref,experiment_date,matrix,lod_summary,reproducibility_summary,acceptance_criteria,evidence,created_at",
        )
        .bind(id)
        .bind(user_id)
        .bind(project_id)
        .bind(run_id)
        .bind(sop_id)
        .bind(instrument_identity)
        .bind(kit_lot)
        .bind(operator_ref)
        .bind(experiment_date)
        .bind(matrix)
        .bind(lod_summary)
        .bind(reproducibility_summary)
        .bind(acceptance_criteria)
        .bind(evidence)
        .fetch_optional(&self.pool)
        .await
        .map_err(query)?
        .ok_or(StorageError::NotFound)
    }

    /// List qualification records for an owned run.
    pub async fn qualifications(
        &self,
        user_id: &str,
        project_id: &str,
        run_id: &str,
    ) -> Result<Vec<AssayQualification>> {
        sqlx::query_as::<_, AssayQualification>(
            "SELECT q.id,q.user_id,q.project_id,q.run_id,q.evidence_schema_version,q.sop_id,q.instrument_identity,q.kit_lot,q.operator_ref,q.experiment_date,q.matrix,q.lod_summary,q.reproducibility_summary,q.acceptance_criteria,q.evidence,q.created_at
             FROM assay_qualifications q JOIN projects p ON p.id=q.project_id
             WHERE p.user_id=$1 AND q.project_id=$2 AND q.run_id=$3 ORDER BY q.created_at DESC",
        )
        .bind(user_id)
        .bind(project_id)
        .bind(run_id)
        .fetch_all(&self.pool)
        .await
        .map_err(query)
    }
}

#[cfg(test)]
#[path = "storage_tests.rs"]
mod tests;
