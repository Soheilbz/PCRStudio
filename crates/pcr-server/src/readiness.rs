//! Whether this instance should be sent traffic.
//!
//! Separate from liveness, and the distinction is the whole point of the file.
//! `/health` answers "is this process alive, or should it be restarted?" and
//! deliberately does no work — a liveness probe that touches the database will
//! restart a healthy server every time the database hiccups, which turns one
//! outage into two.
//!
//! `/ready` answers a narrower control-plane question: "can this instance serve
//! ordinary application traffic?" It checks PostgreSQL only. Scientific
//! execution is intentionally *not* part of this endpoint: users must still be
//! able to sign in, inspect projects and see a degraded scientific status while
//! a runner or native validator is being repaired.
//!
//! `/ready/scientific` is the release/operations gate. It additionally proves a
//! matching dedicated runner (when external execution is configured), starts
//! the Python worker, and validates the strict native toolchain/database
//! contract. Production bootstrap requires this stricter endpoint to be green
//! before it records a successful deployment.
//!
//! The **database** is checked with `SELECT 1`, which costs almost nothing and
//! proves the pool can hand out a live connection rather than merely that a URL
//! was parsed at startup. Scientific worker/toolchain probes are cached briefly
//! because each one crosses the process boundary and may execute native version
//! checks.

use std::time::{Duration, Instant};

use axum::extract::State;
use axum::http::StatusCode;
use axum::Json;
use pcr_accounts::Accounts;
use pcr_core::Worker;
use tokio::sync::{watch, Mutex};

/// How long a worker probe stands before it is asked again.
const WORKER_PROBE_TTL: Duration = Duration::from_secs(15);

#[derive(Default)]
struct ProbeState {
    last: Option<(Instant, Result<(), String>)>,
    in_flight: bool,
}

/// A cancellation-safe single-flight cache for one readiness subprocess.
///
/// The probe itself is spawned independently from the HTTP request that first
/// asked for it. If that caller disconnects, the subprocess is still allowed
/// to finish and publish its answer; the next caller therefore does not start
/// a duplicate process. `watch` is only a generation signal -- the answer
/// remains in `state`, so slow/new subscribers cannot miss the result.
struct ProbeCache {
    state: Mutex<ProbeState>,
    generation: watch::Sender<u64>,
}

type LastProbe = std::sync::Arc<ProbeCache>;

fn probe_cache() -> LastProbe {
    let (generation, _receiver) = watch::channel(0_u64);
    std::sync::Arc::new(ProbeCache {
        state: Mutex::new(ProbeState::default()),
        generation,
    })
}

/// Return a fresh cached probe or join exactly one replacement probe.
async fn cached_probe<F>(cache: &LastProbe, probe: F) -> Result<(), String>
where
    F: FnOnce() -> Result<(), String> + Send + 'static,
{
    let mut probe = Some(probe);

    loop {
        // Subscribe before inspecting state. If the in-flight probe finishes
        // between the state check and `changed().await`, watch remembers that
        // this receiver has not seen the new generation and wakes immediately.
        let mut generation = cache.generation.subscribe();
        let mut state = cache.state.lock().await;
        if let Some((taken, ref answer)) = state.last {
            if taken.elapsed() < WORKER_PROBE_TTL {
                return answer.clone();
            }
        }

        if !state.in_flight {
            let Some(probe) = probe.take() else {
                return Err("readiness single-flight lost its probe function".to_owned());
            };
            state.in_flight = true;
            drop(state);

            let cache = std::sync::Arc::clone(cache);
            tokio::spawn(async move {
                let answer = tokio::task::spawn_blocking(probe)
                    .await
                    .unwrap_or_else(|error| {
                        Err(format!("the readiness probe did not finish: {error}"))
                    });
                let mut state = cache.state.lock().await;
                state.last = Some((Instant::now(), answer));
                state.in_flight = false;
                drop(state);
                cache
                    .generation
                    .send_modify(|value| *value = value.wrapping_add(1));
            });
        } else {
            drop(state);
        }

        if generation.changed().await.is_err() {
            return Err("readiness single-flight notification channel closed".to_owned());
        }
    }
}

/// What the readiness endpoint needs to reach.
#[derive(Clone)]
pub struct Readiness {
    accounts: Accounts,
    foundation: pcr_storage::FoundationStorage,
    worker_command: Worker,
    worker: LastProbe,
    toolchain: LastProbe,
    require_runner: bool,
    approved_scientific_freeze: Option<String>,
    build_identity: Option<String>,
}

impl Readiness {
    /// Build a probe over the stores this server depends on.
    #[must_use]
    pub fn new(accounts: Accounts) -> Self {
        Self::with_worker(accounts, pcr_application::scientific::worker_from_env())
    }

    /// Build readiness for the configured durable-job execution topology.
    /// Production external mode requires a fresh runner heartbeat in PostgreSQL.
    #[must_use]
    pub fn with_runner_requirement(accounts: Accounts, require_runner: bool) -> Self {
        Self::with_worker_and_runner(
            accounts,
            pcr_application::scientific::worker_from_env(),
            require_runner,
        )
    }

    /// Build readiness with an explicit worker command.
    ///
    /// Production uses [`Self::new`], which snapshots `PCR_PYTHON` at startup.
    /// Tests use this constructor so a deliberately broken worker can be
    /// exercised without mutating process-global environment while the Rust
    /// test harness is running other tests in parallel.
    #[must_use]
    pub fn with_worker(accounts: Accounts, worker_command: Worker) -> Self {
        Self::with_worker_and_runner(accounts, worker_command, false)
    }

    fn with_worker_and_runner(
        accounts: Accounts,
        worker_command: Worker,
        require_runner: bool,
    ) -> Self {
        let foundation = pcr_storage::FoundationStorage::new(accounts.pool());
        let approved_scientific_freeze =
            std::env::var("PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256")
                .ok()
                .and_then(|value| pcr_security::canonical_sha256(&value).map(str::to_owned));
        let build_identity = std::env::var("PCRSTUDIO_BUILD_ID")
            .ok()
            .and_then(|value| pcr_security::canonical_sha256(&value).map(str::to_owned));
        Self {
            accounts,
            foundation,
            worker_command,
            worker: probe_cache(),
            toolchain: probe_cache(),
            require_runner,
            approved_scientific_freeze,
            build_identity,
        }
    }

    /// The database, proved rather than assumed.
    async fn database(&self) -> Result<(), String> {
        self.accounts
            .reachable()
            .await
            .map_err(|error| error.to_string())
    }

    /// Dedicated durable-job runner presence, when external execution is required.
    async fn runner(&self) -> Result<(), String> {
        if !self.require_runner {
            return Ok(());
        }
        let build_identity = self
            .build_identity
            .as_deref()
            .ok_or_else(|| "production build identity is unavailable".to_owned())?;
        let status = self
            .foundation
            .active_runner_status(
                pcr_storage::RUNNER_HEARTBEAT_FRESH_SECONDS,
                env!("CARGO_PKG_VERSION"),
                build_identity,
                self.approved_scientific_freeze.as_deref(),
            )
            .await
            .map_err(|error| error.to_string())?;
        if status.instances > 0 && status.worker_capacity > 0 {
            Ok(())
        } else {
            Err("no fresh scientific runner matching the approved runtime is registered".to_owned())
        }
    }

    /// The design worker, with the answer held briefly.
    async fn design_worker(&self) -> Result<(), String> {
        let worker = self.worker_command.clone();
        cached_probe(&self.worker, move || {
            pcr_application::scientific::probe_design_worker(&worker)
        })
        .await
    }

    /// The full scientific host contract, separate from basic application readiness.
    ///
    /// The worker's `toolchain` command is the existing authority for resolved
    /// versions, hashes and execution scopes. This probe does not install or
    /// mutate anything; it only refuses to call the host scientifically ready
    /// while a local/embedded generation-1 artifact is absent or mismatched.
    async fn scientific_toolchain(&self) -> Result<(), String> {
        let worker = self.worker_command.clone();
        cached_probe(&self.toolchain, move || {
            pcr_application::scientific::probe_scientific_toolchain(&worker)
        })
        .await
    }
}

/// Readiness: 200 when every dependency answers, 503 with which one did not.
///
/// The body names the failure rather than only the status, because the two
/// audiences differ: the orchestrator reads the code, and the person paged at
/// three in the morning reads the body.
pub async fn ready(State(state): State<Readiness>) -> (StatusCode, Json<serde_json::Value>) {
    // Control-plane readiness must not disappear just because scientific
    // capacity is temporarily degraded. The durable queue can safely accept
    // work while a runner restarts, and the UI remains useful for projects,
    // history and diagnostics. Full scientific availability has its own strict
    // endpoint below and is still mandatory for deployment qualification.
    let database = state.database().await;
    let ready = database.is_ok();
    if let Err(error) = &database {
        tracing::warn!(%error, "readiness database probe failed");
    }

    // Readiness is intentionally public to orchestrators. Do not return raw
    // driver errors here: those can contain host names or other deployment
    // detail. Operators get the detail in logs.
    (
        if ready {
            StatusCode::OK
        } else {
            StatusCode::SERVICE_UNAVAILABLE
        },
        Json(serde_json::json!({
            "ready": ready,
            "database": { "ok": database.is_ok() },
            "scientificReadiness": "/ready/scientific",
        })),
    )
}

/// Full scientific-host readiness.
///
/// This is deliberately stricter than `/ready`: login, projects and the UI can
/// remain available while a scientific host artifact is being repaired, but a
/// release/operations check can ask this endpoint whether every configured
/// generation-1 executable/package identity is actually qualified.
pub async fn scientific_ready(
    State(state): State<Readiness>,
) -> (StatusCode, Json<serde_json::Value>) {
    // Operational probes deliberately sit outside the request Gate so a fully
    // saturated design queue cannot make an otherwise healthy instance fail
    // orchestration. Run the two worker probes sequentially, though, so this
    // reserved lane can add at most one subprocess beyond the request ceiling.
    let scientific = async {
        let worker = state.design_worker().await;
        // Keep the two subprocess checks sequential so the reserved readiness
        // lane adds at most one worker beyond the request-driven Gate.
        let toolchain = state.scientific_toolchain().await;
        (worker, toolchain)
    };
    let (database, runner, (worker, toolchain)) =
        tokio::join!(state.database(), state.runner(), scientific);
    let ready = database.is_ok() && runner.is_ok() && worker.is_ok() && toolchain.is_ok();
    if let Err(error) = &database {
        tracing::warn!(%error, "scientific readiness database probe failed");
    }
    if let Err(error) = &worker {
        tracing::warn!(%error, "scientific readiness design-worker probe failed");
    }
    if let Err(error) = &runner {
        tracing::warn!(%error, "scientific readiness runner probe failed");
    }
    if let Err(error) = &toolchain {
        tracing::warn!(%error, "scientific readiness toolchain probe failed");
    }
    let describe = |result: &Result<(), String>| serde_json::json!({ "ok": result.is_ok() });
    (
        if ready {
            StatusCode::OK
        } else {
            StatusCode::SERVICE_UNAVAILABLE
        },
        Json(serde_json::json!({
            "ready": ready,
            "database": describe(&database),
            "designWorker": describe(&worker),
            "runner": { "ok": runner.is_ok(), "required": state.require_runner },
            "scientificToolchain": describe(&toolchain),
        })),
    )
}

#[cfg(test)]
mod tests {
    use super::{cached_probe, probe_cache, LastProbe};
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;
    use std::time::Duration;
    use tokio::sync::Barrier;

    #[tokio::test]
    async fn concurrent_readiness_checks_share_one_in_flight_probe() {
        let cache: LastProbe = probe_cache();
        let calls = Arc::new(AtomicUsize::new(0));
        let start = Arc::new(Barrier::new(3));
        let mut tasks = Vec::new();

        for _ in 0..2 {
            let cache = cache.clone();
            let calls = calls.clone();
            let start = start.clone();
            tasks.push(tokio::spawn(async move {
                start.wait().await;
                cached_probe(&cache, move || {
                    calls.fetch_add(1, Ordering::SeqCst);
                    std::thread::sleep(Duration::from_millis(30));
                    Ok(())
                })
                .await
            }));
        }

        start.wait().await;
        for task in tasks {
            assert!(task.await.expect("probe task joins").is_ok());
        }
        assert_eq!(calls.load(Ordering::SeqCst), 1);
    }
    #[tokio::test]
    async fn cancelled_caller_does_not_spawn_a_second_probe() {
        let cache: LastProbe = probe_cache();
        let calls = Arc::new(AtomicUsize::new(0));

        let first_cache = cache.clone();
        let first_calls = calls.clone();
        let first = tokio::spawn(async move {
            cached_probe(&first_cache, move || {
                first_calls.fetch_add(1, Ordering::SeqCst);
                std::thread::sleep(Duration::from_millis(60));
                Ok(())
            })
            .await
        });

        for _ in 0..50 {
            if calls.load(Ordering::SeqCst) == 1 {
                break;
            }
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
        assert_eq!(calls.load(Ordering::SeqCst), 1, "the first probe started");
        first.abort();

        let second_calls = calls.clone();
        let answer = cached_probe(&cache, move || {
            second_calls.fetch_add(1, Ordering::SeqCst);
            Ok(())
        })
        .await;

        assert!(answer.is_ok());
        assert_eq!(
            calls.load(Ordering::SeqCst),
            1,
            "caller cancellation must not duplicate the detached readiness probe"
        );
    }
}
