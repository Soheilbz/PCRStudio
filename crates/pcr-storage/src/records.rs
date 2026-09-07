//! Public Foundation record projections.

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};

/// Immutable hashed metadata for an externally stored attachment.
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct Attachment {
    /// Stable id.
    pub id: String,
    /// Owner id.
    pub user_id: String,
    /// Optional project id.
    pub project_id: Option<String>,
    /// Optional run id.
    pub run_id: Option<String>,
    /// SHA-256 of attachment bytes.
    pub sha256: String,
    /// MIME media type.
    pub media_type: String,
    /// Original display filename.
    pub file_name: String,
    /// Exact byte length.
    pub byte_length: i64,
    /// Opaque immutable object-store/filesystem key; never raw bytes in JSONB.
    pub storage_key: String,
    /// Creation time.
    pub created_at: DateTime<Utc>,
}

/// Qualification evidence attached to a historical design without mutating it.
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct AssayQualification {
    /// Stable id.
    pub id: String,
    /// Owner id.
    pub user_id: String,
    /// Project id.
    pub project_id: String,
    /// Historical run id being qualified.
    pub run_id: String,
    /// Evidence schema version.
    pub evidence_schema_version: i32,
    /// SOP identity.
    pub sop_id: Option<String>,
    /// Instrument identity.
    pub instrument_identity: Option<String>,
    /// Kit/lot identity.
    pub kit_lot: Option<String>,
    /// Non-secret operator reference.
    pub operator_ref: Option<String>,
    /// Experiment date.
    pub experiment_date: Option<NaiveDate>,
    /// Matrix identity.
    pub matrix: Option<String>,
    /// LoD evidence summary.
    pub lod_summary: Option<serde_json::Value>,
    /// Reproducibility evidence summary.
    pub reproducibility_summary: Option<serde_json::Value>,
    /// Declared acceptance criteria.
    pub acceptance_criteria: serde_json::Value,
    /// Remaining structured evidence.
    pub evidence: serde_json::Value,
    /// Creation time.
    pub created_at: DateTime<Utc>,
}

/// Aggregate status of dedicated scientific runners visible to PostgreSQL.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunnerStatus {
    /// Number of live runner processes matching the requested release freeze.
    pub instances: i64,
    /// Sum of their configured scientific worker ceilings.
    pub worker_capacity: i64,
}

/// Cross-process durable execution telemetry sourced from PostgreSQL.
///
/// Unlike in-process scheduler counters, these values describe the actual
/// external-runner topology and remain meaningful when API and runner are
/// different processes or replicas.
#[derive(Debug, Clone, Copy, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DurableExecutionMetrics {
    /// Jobs waiting to be claimed.
    pub queued_jobs: i64,
    /// Jobs currently leased to an executor.
    pub running_jobs: i64,
    /// Jobs whose owner requested cancellation.
    pub cancel_requested_jobs: i64,
    /// Oldest queued-job age in seconds, or zero when the queue is empty.
    pub oldest_queued_seconds: f64,
    /// Fresh runner processes regardless of release identity.
    pub fresh_runner_instances: i64,
    /// Aggregate worker capacity advertised by fresh runners.
    pub fresh_runner_capacity: i64,
}
