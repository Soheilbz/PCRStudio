//! Durable scientific job execution.
//!
//! PostgreSQL is the queue and lease authority.  This module contains no HTTP
//! code, so it can run either embedded for local development or in the
//! dedicated `pcr-runner` process used by production Linux deployments.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use pcr_accounts::Accounts;
use pcr_core::{CoreError, Registry};
use pcr_projects::Projects;
use pcr_storage::{FoundationStorage, RunJob, StorageError};

use crate::{design_for, Gate};

/// Runtime dependencies needed by one durable job executor.
#[derive(Clone)]
pub struct JobExecutionState {
    /// Project/run persistence.
    pub projects: Projects,
    /// Durable job/lease storage.
    pub storage: FoundationStorage,
    /// Canonical design registry.
    pub registry: Registry,
    /// Weighted process-local worker ceiling.
    pub gate: std::sync::Arc<Gate>,
}

impl JobExecutionState {
    /// Build execution state from the shared account/database pool.
    #[must_use]
    pub fn from_accounts(accounts: &Accounts, registry: Registry) -> Self {
        let pool = accounts.pool();
        Self {
            projects: Projects::new(pool.clone()),
            storage: FoundationStorage::new(pool),
            registry,
            gate: std::sync::Arc::new(Gate::shared()),
        }
    }
}

fn new_execution_id() -> String {
    uuid::Uuid::new_v4().to_string()
}

fn cancellation_registry() -> &'static Mutex<HashMap<String, pcr_worker_client::CancellationToken>>
{
    static REGISTRY: OnceLock<Mutex<HashMap<String, pcr_worker_client::CancellationToken>>> =
        OnceLock::new();
    REGISTRY.get_or_init(|| Mutex::new(HashMap::new()))
}

fn cancellation_key(user_id: &str, job_id: &str) -> String {
    format!("{user_id}:{job_id}")
}

struct CancellationRegistration(String);

impl Drop for CancellationRegistration {
    fn drop(&mut self) {
        let mut map = cancellation_registry()
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        map.remove(&self.0);
    }
}

fn register_cancellation(
    user_id: &str,
    job_id: &str,
    token: pcr_worker_client::CancellationToken,
) -> Option<CancellationRegistration> {
    let key = cancellation_key(user_id, job_id);
    let mut map = cancellation_registry()
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner);
    if map.contains_key(&key) {
        return None;
    }
    map.insert(key.clone(), token);
    Some(CancellationRegistration(key))
}

/// Signal a scientific job running in this process.
///
/// In the production split-process topology the API first writes
/// `cancel_requested` to PostgreSQL.  The runner observes that state through
/// its two-second lease heartbeat and then calls the same token locally.  This
/// helper keeps embedded development cancellation immediate without making an
/// in-memory registry part of durable truth.
pub fn signal_local_cancellation(user_id: &str, job_id: &str) {
    let key = cancellation_key(user_id, job_id);
    let token = cancellation_registry()
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
        .get(&key)
        .cloned();
    if let Some(token) = token {
        token.cancel();
    }
}

/// Cancel every scientific worker owned by this process.
///
/// Used during runner shutdown so Docker/systemd termination does not leave a
/// child interpreter or native tool running until the container grace period
/// expires. Durable rows remain recoverable because completion/failure writes
/// are lease-scoped.
pub fn signal_all_local_cancellations() {
    let tokens = cancellation_registry()
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
        .values()
        .cloned()
        .collect::<Vec<_>>();
    for token in tokens {
        token.cancel();
    }
}

/// Number of scientific jobs currently registered in this process.
///
/// This is process-local operational state only; PostgreSQL remains the
/// durable authority for job status and leases.
#[must_use]
pub fn local_active_job_count() -> usize {
    cancellation_registry()
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
        .len()
}

/// Wait for process-local scientific jobs to unregister after cancellation.
///
/// The deadline prevents shutdown from hanging forever on a native tool that
/// ignores termination. The caller can then exit and let the durable lease
/// expire/recover on another runner.
pub async fn drain_local_jobs(timeout: Duration) -> usize {
    let deadline = tokio::time::Instant::now() + timeout;
    loop {
        let remaining = local_active_job_count();
        if remaining == 0 || tokio::time::Instant::now() >= deadline {
            return remaining;
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
}

fn durable_core_error(error: &CoreError) -> serde_json::Value {
    let (code, kind, detail, stage, retryable) = match error {
        CoreError::UnknownProfile(_) => (
            "PROFILE_NOT_FOUND",
            "unknownProfile",
            error.to_string(),
            "validation",
            false,
        ),
        CoreError::InvalidRequest(_) => (
            "INVALID_REQUEST",
            "invalidRequest",
            error.to_string(),
            "validation",
            false,
        ),
        CoreError::NotImplemented(_) => (
            "CAPABILITY_NOT_IMPLEMENTED",
            "notImplemented",
            error.to_string(),
            "dispatch",
            false,
        ),
        CoreError::WorkerBusy(_) => (
            "WORKER_CAPACITY_EXHAUSTED",
            "workerBusy",
            "the design service is at capacity; try again shortly".to_owned(),
            "queue",
            true,
        ),
        CoreError::Cancelled => (
            "REQUEST_CANCELLED",
            "cancelled",
            "the running design was cancelled".to_owned(),
            "execution",
            false,
        ),
        CoreError::ToolFailed(_)
        | CoreError::DuplicateProfile(_)
        | CoreError::UnknownEngine(_)
        | CoreError::IncompatibleModifier(_) => (
            "SCIENTIFIC_EXECUTION_FAILED",
            "toolFailed",
            "this build could not complete the scientific request; try again in a moment"
                .to_owned(),
            "execution",
            true,
        ),
    };
    serde_json::json!({
        "code": code,
        "kind": kind,
        "detail": detail,
        "stage": stage,
        "retryable": retryable,
    })
}

/// Spawn one durable job attempt in this process.
///
/// PostgreSQL lease predicates, not the local task, decide which executor is
/// authoritative.  Starting the same queued job in two processes is therefore
/// safe: only one can transition it to `running` with a live executor lease.
pub fn spawn_run_job(state: JobExecutionState, user_id: String, job: RunJob) {
    tokio::spawn(async move {
        let project_id = job.project_id.clone();

        let cancellation = pcr_worker_client::CancellationToken::new();
        let Some(_registration) = register_cancellation(&user_id, &job.id, cancellation.clone())
        else {
            return;
        };

        let _ = state
            .storage
            .update_run_job_stage(
                &user_id,
                &job.id,
                "waiting-capacity",
                &serde_json::json!({"measured": true, "stage": "waiting-capacity"}),
            )
            .await;

        let weight =
            pcr_contracts::resource_weight_for_module(&job.module_id).unwrap_or(1) as usize;
        let gate = state.gate.clone();
        let registry = state.registry.clone();
        let module_id = job.module_id.clone();
        let request = job.request.clone();

        let start_storage = state.storage.clone();
        let start_user = user_id.clone();
        let start_job = job.id.clone();
        let execution_id = new_execution_id();
        let start_executor = execution_id.clone();
        let heartbeat_token = cancellation.clone();
        let result = gate
            .run_weighted_cancellable_with_start(
                weight,
                cancellation.clone(),
                move || {
                    let storage = start_storage.clone();
                    let user = start_user.clone();
                    let job_id = start_job.clone();
                    let executor = start_executor.clone();
                    let token = heartbeat_token.clone();
                    async move {
                        match storage
                            .mark_run_job_running(&user, &job_id, &executor)
                            .await
                        {
                            Ok(true) => {}
                            Ok(false) => return Err(CoreError::Cancelled),
                            Err(error) => {
                                tracing::error!(job_id=%job_id, %error, "durable job could not acquire its execution lease");
                                return Err(CoreError::ToolFailed(
                                    "the durable job store is unavailable".to_owned(),
                                ));
                            }
                        }

                        tokio::spawn(async move {
                            loop {
                                tokio::time::sleep(Duration::from_secs(2)).await;
                                match storage
                                    .heartbeat_run_job(&user, &job_id, &executor)
                                    .await
                                {
                                    Ok(Some(false)) => {}
                                    Ok(Some(true)) | Ok(None) => {
                                        token.cancel();
                                        break;
                                    }
                                    Err(error) => {
                                        tracing::error!(job_id=%job_id, %error, "durable job heartbeat failed; cancelling to preserve single-executor semantics");
                                        token.cancel();
                                        break;
                                    }
                                }
                            }
                        });
                        Ok(())
                    }
                },
                move || design_for(&registry, &module_id, request),
            )
            .await;

        let result = match result {
            Ok(result) => result,
            Err(CoreError::Cancelled) => {
                if cancellation.is_cancelled() {
                    match state
                        .storage
                        .run_job_cancel_requested(&user_id, &job.id)
                        .await
                    {
                        Ok(true) => {
                            let _ = state
                                .storage
                                .cancel_run_job_for_executor(&user_id, &job.id, &execution_id)
                                .await;
                        }
                        Ok(false) | Err(StorageError::NotFound) => {}
                        Err(error) => {
                            tracing::warn!(job_id=%job.id, %error, "could not confirm durable cancellation state");
                        }
                    }
                }
                return;
            }
            Err(error) => {
                tracing::error!(job_id=%job.id, error=%error, "durable design execution failed");
                if matches!(
                    state
                        .storage
                        .run_job_cancel_requested(&user_id, &job.id)
                        .await,
                    Ok(true)
                ) {
                    let _ = state
                        .storage
                        .cancel_run_job_for_executor(&user_id, &job.id, &execution_id)
                        .await;
                    return;
                }
                let safe = durable_core_error(&error);
                let _ = state
                    .storage
                    .fail_run_job_for_executor(&user_id, &job.id, &execution_id, &safe)
                    .await;
                return;
            }
        };

        match state
            .storage
            .run_job_cancel_requested(&user_id, &job.id)
            .await
        {
            Ok(true) => {
                let _ = state
                    .storage
                    .cancel_run_job_for_executor(&user_id, &job.id, &execution_id)
                    .await;
                return;
            }
            Err(StorageError::NotFound) => return,
            Ok(false) => {}
            Err(error) => {
                tracing::error!(job_id=%job.id, %error, "could not verify durable job cancellation state before persistence");
                let safe = serde_json::json!({
                    "code":"RUN_PERSISTENCE_UNAVAILABLE",
                    "kind":"storeFailure",
                    "detail":"The completed design could not be saved because the project store is unavailable. Try the job again.",
                    "retryable":true
                });
                let _ = state
                    .storage
                    .fail_run_job_for_executor(&user_id, &job.id, &execution_id, &safe)
                    .await;
                return;
            }
        }

        let progress = serde_json::json!({"measured": true, "stage": "completed"});
        match state
            .projects
            .save_run_for_job_with_project(pcr_projects::SaveRunForJobInput {
                user_id: &user_id,
                project_id: &project_id,
                job_id: &job.id,
                executor_id: &execution_id,
                label: &job.label,
                request: &job.request,
                result: &result,
                progress: &progress,
            })
            .await
        {
            Ok(Some((_run, _project))) => {}
            Ok(None) => {
                if matches!(
                    state
                        .storage
                        .run_job_cancel_requested(&user_id, &job.id)
                        .await,
                    Ok(true)
                ) {
                    let _ = state
                        .storage
                        .cancel_run_job_for_executor(&user_id, &job.id, &execution_id)
                        .await;
                }
            }
            Err(error) => {
                tracing::error!(job_id=%job.id, %error, "durable job result could not be persisted atomically");
                let safe = serde_json::json!({
                    "code": "RUN_PERSISTENCE_FAILED",
                    "kind": "storeFailure",
                    "detail": "The completed design could not be saved. Try the job again.",
                    "retryable": true
                });
                let _ = state
                    .storage
                    .fail_run_job_for_executor(&user_id, &job.id, &execution_id, &safe)
                    .await;
            }
        }
    });
}

/// Reclaim stale leases and dispatch the jobs visible in one queue pass.
///
/// This one-iteration primitive is public so a dedicated production runner
/// can couple its liveness heartbeat to *the same loop that polls PostgreSQL*.
/// A separate heartbeat task would be unsafe: it could continue advertising
/// healthy capacity after the executor loop had panicked or stopped polling.
pub async fn recover_and_dispatch_once(state: &JobExecutionState) {
    // Recovery changes durable state only. The subsequent ordered queue read is
    // the single dispatch source, so recovered rows are not mirrored into a
    // second process-local backlog or dispatched twice from two result sets.
    if let Err(error) = state.storage.recover_stale_run_jobs().await {
        tracing::warn!(%error, "could not recover expired durable-job leases");
    }

    let scheduler = state.gate.snapshot();
    // PostgreSQL is the durable queue. Never preload jobs into the Gate's local
    // waiting queue: a fleet of runners would otherwise mirror the same backlog
    // in every process. Existing local waiters retain semaphore fairness and no
    // additional rows are dispatched until they have acquired capacity.
    if scheduler.available == 0 || scheduler.queued_jobs != 0 {
        return;
    }

    let jobs = match state.storage.queued_run_jobs(scheduler.available).await {
        Ok(queued) => queued,
        Err(error) => {
            tracing::warn!(%error, "could not load queued durable jobs");
            return;
        }
    };

    let mut remaining_weight = scheduler.available;
    for job in jobs {
        let weight = (pcr_contracts::resource_weight_for_module(&job.module_id).unwrap_or(1)
            as usize)
            .clamp(1, scheduler.capacity);
        // Preserve the same FIFO/fairness semantics as Tokio's weighted
        // semaphore: do not let lighter later jobs bypass an older heavy job.
        if weight > remaining_weight {
            break;
        }
        remaining_weight -= weight;
        spawn_run_job(state.clone(), job.user_id.clone(), job);
        if remaining_weight == 0 {
            break;
        }
    }
}

/// Reclaim stale leases and dispatch queued jobs forever.
///
/// `poll_interval` is intentionally a small bounded duration. PostgreSQL is
/// durable authority; no in-memory notification is required for correctness.
/// Production uses [`recover_and_dispatch_once`] directly so runner presence
/// and executor polling share one liveness loop.
pub async fn job_recovery_loop(accounts: Accounts, registry: Registry, poll_interval: Duration) {
    let state = JobExecutionState::from_accounts(&accounts, registry);
    loop {
        recover_and_dispatch_once(&state).await;
        tokio::time::sleep(poll_interval).await;
    }
}
