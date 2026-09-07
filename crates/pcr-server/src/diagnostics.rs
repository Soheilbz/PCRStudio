//! Operator-only diagnostics and Prometheus-compatible scheduler metrics.
//!
//! These endpoints intentionally expose no request bodies, sequences, project
//! names, user identifiers, paths, or database credentials. They are disabled
//! unless `PCR_OPERATOR_TOKEN` is configured and are authenticated with a
//! constant-time comparison of `x-pcrstudio-operator-token`.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::OnceLock;
use std::time::Instant;

use axum::extract::State;
use axum::http::Request;
use axum::http::{HeaderMap, StatusCode};
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use axum::Json;

use crate::gate::Gate;

/// Header carrying the operator token. It is intentionally not accepted by
/// browser CORS; diagnostics are for the host/operator channel.
const OPERATOR_HEADER: &str = "x-pcrstudio-operator-token";

#[derive(Clone)]
pub(crate) struct DiagnosticsState {
    gate: Gate,
    accounts: pcr_accounts::Accounts,
    operator_token: Option<String>,
}

impl DiagnosticsState {
    pub(crate) fn new(
        gate: Gate,
        accounts: pcr_accounts::Accounts,
        operator_token: Option<String>,
    ) -> Self {
        Self {
            gate,
            accounts,
            operator_token,
        }
    }

    fn authorized(&self, headers: &HeaderMap) -> bool {
        let Some(expected) = self.operator_token.as_deref() else {
            return false;
        };
        let Some(given) = headers
            .get(OPERATOR_HEADER)
            .and_then(|value| value.to_str().ok())
        else {
            return false;
        };
        pcr_security::constant_time_equal(expected.as_bytes(), given.as_bytes())
    }
}

fn uptime_seconds() -> u64 {
    static START: OnceLock<Instant> = OnceLock::new();
    START.get_or_init(Instant::now).elapsed().as_secs()
}

static HTTP_REQUESTS_TOTAL: AtomicU64 = AtomicU64::new(0);
static HTTP_SERVER_ERRORS_TOTAL: AtomicU64 = AtomicU64::new(0);
static HTTP_DURATION_MILLISECONDS_TOTAL: AtomicU64 = AtomicU64::new(0);
static HTTP_DURATION_SAMPLES: AtomicU64 = AtomicU64::new(0);

fn elapsed_milliseconds(started: Instant) -> u64 {
    u64::try_from(started.elapsed().as_millis()).unwrap_or(u64::MAX)
}

/// Record low-cardinality HTTP service telemetry without paths, identities, or
/// scientific request content. Request tracing remains responsible for detailed
/// per-request diagnostics.
pub(crate) async fn observe_http(request: Request<axum::body::Body>, next: Next) -> Response {
    let started = Instant::now();
    HTTP_REQUESTS_TOTAL.fetch_add(1, Ordering::Relaxed);
    let response = next.run(request).await;
    HTTP_DURATION_MILLISECONDS_TOTAL.fetch_add(elapsed_milliseconds(started), Ordering::Relaxed);
    HTTP_DURATION_SAMPLES.fetch_add(1, Ordering::Relaxed);
    if response.status().is_server_error() {
        HTTP_SERVER_ERRORS_TOTAL.fetch_add(1, Ordering::Relaxed);
    }
    response
}

fn not_found() -> Response {
    // Do not reveal whether the endpoint exists but is disabled, or a supplied
    // token was wrong. The operator has the deployment configuration already.
    StatusCode::NOT_FOUND.into_response()
}

async fn durable_execution(
    accounts: &pcr_accounts::Accounts,
) -> Result<pcr_storage::DurableExecutionMetrics, Response> {
    pcr_storage::FoundationStorage::new(accounts.pool())
        .durable_execution_metrics()
        .await
        .map_err(|_| StatusCode::SERVICE_UNAVAILABLE.into_response())
}

pub(crate) async fn diagnostics(
    State(state): State<DiagnosticsState>,
    headers: HeaderMap,
) -> Response {
    if !state.authorized(&headers) {
        return not_found();
    }
    let durable = match durable_execution(&state.accounts).await {
        Ok(value) => value,
        Err(response) => return response,
    };
    let scheduler = state.gate.snapshot();
    let (database_pool_size, database_pool_idle) = state.accounts.pool_utilization();
    let tools = pcr_contracts::tool_ids()
        .into_iter()
        .filter_map(|id| {
            pcr_contracts::tool(id).map(|metadata| {
                serde_json::json!({
                    "id": id,
                    "version": metadata.get("version"),
                    "executionScope": metadata.get("execution_scope"),
                    "artifactSha256Required": metadata.get("artifact_sha256_required"),
                })
            })
        })
        .collect::<Vec<_>>();
    Json(serde_json::json!({
        "service": {"name": "PCRStudio", "version": env!("CARGO_PKG_VERSION")},
        "foundation": {
            "moduleContractVersion": pcr_contracts::MODULE_CONTRACT_VERSION,
            "ipcProtocolVersion": pcr_contracts::IPC_PROTOCOL_VERSION,
            "draftSchemaVersion": pcr_contracts::DRAFT_SCHEMA_VERSION,
            "requestSchemaVersion": pcr_contracts::REQUEST_SCHEMA_VERSION,
            "resultSchemaVersion": pcr_contracts::RESULT_SCHEMA_VERSION,
        },
        "uptimeSeconds": uptime_seconds(),
        "interactiveScheduler": scheduler,
        "durableExecution": durable,
        "databasePool": {
            "size": database_pool_size,
            "idle": database_pool_idle,
            "inUse": (database_pool_size as usize).saturating_sub(database_pool_idle),
        },
        "tools": tools,
        "privacy": "no-user-or-sequence-data",
    }))
    .into_response()
}

pub(crate) async fn metrics(State(state): State<DiagnosticsState>, headers: HeaderMap) -> Response {
    if !state.authorized(&headers) {
        return not_found();
    }
    let durable = match durable_execution(&state.accounts).await {
        Ok(value) => value,
        Err(response) => return response,
    };
    let snapshot = state.gate.snapshot();
    let (database_pool_size, database_pool_idle) = state.accounts.pool_utilization();
    let database_pool_in_use = (database_pool_size as usize).saturating_sub(database_pool_idle);
    let body = format!(
        concat!(
            "# HELP pcrstudio_uptime_seconds Process uptime in seconds.\n",
            "# TYPE pcrstudio_uptime_seconds gauge\n",
            "pcrstudio_uptime_seconds {}\n",
            "# HELP pcrstudio_worker_capacity Weighted scientific worker capacity.\n",
            "# TYPE pcrstudio_worker_capacity gauge\n",
            "pcrstudio_worker_capacity {}\n",
            "# HELP pcrstudio_worker_available Available weighted worker units.\n",
            "# TYPE pcrstudio_worker_available gauge\n",
            "pcrstudio_worker_available {}\n",
            "# HELP pcrstudio_worker_running_weight Running weighted worker units.\n",
            "# TYPE pcrstudio_worker_running_weight gauge\n",
            "pcrstudio_worker_running_weight {}\n",
            "# HELP pcrstudio_worker_queued_jobs Requests currently waiting for capacity.\n",
            "# TYPE pcrstudio_worker_queued_jobs gauge\n",
            "pcrstudio_worker_queued_jobs {}\n",
            "# HELP pcrstudio_worker_started_jobs_total Scientific jobs that acquired capacity and started.\n",
            "# TYPE pcrstudio_worker_started_jobs_total counter\n",
            "pcrstudio_worker_started_jobs_total {}\n",
            "# HELP pcrstudio_worker_completed_jobs_total Started scientific jobs that returned normally.\n",
            "# TYPE pcrstudio_worker_completed_jobs_total counter\n",
            "pcrstudio_worker_completed_jobs_total {}\n",
            "# HELP pcrstudio_worker_failed_jobs_total Started scientific jobs that failed or panicked.\n",
            "# TYPE pcrstudio_worker_failed_jobs_total counter\n",
            "pcrstudio_worker_failed_jobs_total {}\n",
            "# HELP pcrstudio_worker_cancelled_jobs_total Jobs cancelled while queued or executing.\n",
            "# TYPE pcrstudio_worker_cancelled_jobs_total counter\n",
            "pcrstudio_worker_cancelled_jobs_total {}\n",
            "# HELP pcrstudio_worker_queue_wait_milliseconds_total Aggregate scheduler queue wait in milliseconds.\n",
            "# TYPE pcrstudio_worker_queue_wait_milliseconds_total counter\n",
            "pcrstudio_worker_queue_wait_milliseconds_total {}\n",
            "# HELP pcrstudio_worker_queue_wait_samples_total Number of queued acquisitions measured.\n",
            "# TYPE pcrstudio_worker_queue_wait_samples_total counter\n",
            "pcrstudio_worker_queue_wait_samples_total {}\n",
            "# HELP pcrstudio_worker_runtime_milliseconds_total Aggregate worker wall time in milliseconds.\n",
            "# TYPE pcrstudio_worker_runtime_milliseconds_total counter\n",
            "pcrstudio_worker_runtime_milliseconds_total {}\n",
            "# HELP pcrstudio_worker_runtime_samples_total Number of worker runtimes measured.\n",
            "# TYPE pcrstudio_worker_runtime_samples_total counter\n",
            "pcrstudio_worker_runtime_samples_total {}\n",
            "# HELP pcrstudio_durable_queued_jobs Durable jobs waiting in PostgreSQL.\n",
            "# TYPE pcrstudio_durable_queued_jobs gauge\n",
            "pcrstudio_durable_queued_jobs {}\n",
            "# HELP pcrstudio_durable_running_jobs Durable jobs currently leased to runners.\n",
            "# TYPE pcrstudio_durable_running_jobs gauge\n",
            "pcrstudio_durable_running_jobs {}\n",
            "# HELP pcrstudio_durable_cancel_requested_jobs Durable jobs awaiting cancellation completion.\n",
            "# TYPE pcrstudio_durable_cancel_requested_jobs gauge\n",
            "pcrstudio_durable_cancel_requested_jobs {}\n",
            "# HELP pcrstudio_durable_oldest_queued_seconds Age of the oldest queued durable job.\n",
            "# TYPE pcrstudio_durable_oldest_queued_seconds gauge\n",
            "pcrstudio_durable_oldest_queued_seconds {:.3}\n",
            "# HELP pcrstudio_durable_runner_instances Fresh durable scientific runner processes.\n",
            "# TYPE pcrstudio_durable_runner_instances gauge\n",
            "pcrstudio_durable_runner_instances {}\n",
            "# HELP pcrstudio_durable_runner_capacity Aggregate worker capacity advertised by fresh runners.\n",
            "# TYPE pcrstudio_durable_runner_capacity gauge\n",
            "pcrstudio_durable_runner_capacity {}\n",
            "# HELP pcrstudio_http_requests_total HTTP requests observed by the API process.\n",
            "# TYPE pcrstudio_http_requests_total counter\n",
            "pcrstudio_http_requests_total {}\n",
            "# HELP pcrstudio_http_server_errors_total HTTP responses with 5xx status.\n",
            "# TYPE pcrstudio_http_server_errors_total counter\n",
            "pcrstudio_http_server_errors_total {}\n",
            "# HELP pcrstudio_http_duration_milliseconds_total Aggregate HTTP request duration in milliseconds.\n",
            "# TYPE pcrstudio_http_duration_milliseconds_total counter\n",
            "pcrstudio_http_duration_milliseconds_total {}\n",
            "# HELP pcrstudio_http_duration_samples_total Number of HTTP request durations measured.\n",
            "# TYPE pcrstudio_http_duration_samples_total counter\n",
            "pcrstudio_http_duration_samples_total {}\n",
            "# HELP pcrstudio_database_pool_size PostgreSQL connections currently held by the pool.\n",
            "# TYPE pcrstudio_database_pool_size gauge\n",
            "pcrstudio_database_pool_size {}\n",
            "# HELP pcrstudio_database_pool_idle Idle PostgreSQL connections currently in the pool.\n",
            "# TYPE pcrstudio_database_pool_idle gauge\n",
            "pcrstudio_database_pool_idle {}\n",
            "# HELP pcrstudio_database_pool_in_use PostgreSQL connections currently checked out.\n",
            "# TYPE pcrstudio_database_pool_in_use gauge\n",
            "pcrstudio_database_pool_in_use {}\n"
        ),
        uptime_seconds(),
        snapshot.capacity,
        snapshot.available,
        snapshot.running_weight,
        snapshot.queued_jobs,
        snapshot.started_jobs,
        snapshot.completed_jobs,
        snapshot.failed_jobs,
        snapshot.cancelled_jobs,
        snapshot.queue_wait_milliseconds_total,
        snapshot.queue_wait_samples,
        snapshot.worker_runtime_milliseconds_total,
        snapshot.worker_runtime_samples,
        durable.queued_jobs,
        durable.running_jobs,
        durable.cancel_requested_jobs,
        durable.oldest_queued_seconds,
        durable.fresh_runner_instances,
        durable.fresh_runner_capacity,
        HTTP_REQUESTS_TOTAL.load(Ordering::Relaxed),
        HTTP_SERVER_ERRORS_TOTAL.load(Ordering::Relaxed),
        HTTP_DURATION_MILLISECONDS_TOTAL.load(Ordering::Relaxed),
        HTTP_DURATION_SAMPLES.load(Ordering::Relaxed),
        database_pool_size,
        database_pool_idle,
        database_pool_in_use,
    );
    (
        [(
            axum::http::header::CONTENT_TYPE,
            "text/plain; version=0.0.4; charset=utf-8",
        )],
        body,
    )
        .into_response()
}
