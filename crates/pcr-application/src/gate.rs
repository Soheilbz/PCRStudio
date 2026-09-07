//! A ceiling on how much worker work this process runs at once.
//!
//! Every design forks a Python interpreter that runs a real search. Without a
//! bound here the number of interpreters running is the number of requests in
//! flight — which is whatever callers make it, and the rate limiter can only
//! slow a polite caller down. This is the bound that holds against everybody:
//! the Nth simultaneous design waits for a permit instead of starting an
//! interpreter, and the server stays responsive while it waits.
//!
//! The size comes from `PCR_MAX_CONCURRENT_WORKERS` and defaults to the
//! machine's own parallelism, because each interpreter burns roughly one core
//! while it searches. More than that and designs slow each other down without
//! finishing sooner; fewer than that and the machine is idle while callers
//! queue.

use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Instant;

use pcr_core::CoreError;
use tokio::sync::Semaphore;

/// How many worker processes may run at once.
#[derive(Clone, Debug)]
pub struct Gate {
    permits: Arc<Semaphore>,
    queue: Arc<Semaphore>,
    capacity: usize,
    running_weight: Arc<AtomicUsize>,
    queued_jobs: Arc<AtomicUsize>,
    started_jobs: Arc<AtomicU64>,
    completed_jobs: Arc<AtomicU64>,
    failed_jobs: Arc<AtomicU64>,
    cancelled_jobs: Arc<AtomicU64>,
    queue_wait_milliseconds_total: Arc<AtomicU64>,
    queue_wait_samples: Arc<AtomicU64>,
    worker_runtime_milliseconds_total: Arc<AtomicU64>,
    worker_runtime_samples: Arc<AtomicU64>,
}

const DEFAULT_QUEUE_LIMIT: usize = 256;

/// Snapshot of the weighted worker scheduler without user/scientific data.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GateSnapshot {
    /// Total resource units configured for this process.
    pub capacity: usize,
    /// Resource units currently available.
    pub available: usize,
    /// Resource units held by running jobs.
    pub running_weight: usize,
    /// Number of requests waiting for resource units.
    pub queued_jobs: usize,
    /// Scientific jobs that actually acquired capacity and started.
    pub started_jobs: u64,
    /// Started scientific jobs that returned normally, including domain errors.
    pub completed_jobs: u64,
    /// Started jobs that returned an error or panicked, excluding cancellation.
    pub failed_jobs: u64,
    /// Jobs cancelled either while queued or after execution began.
    pub cancelled_jobs: u64,
    /// Aggregate queue-wait time for queued acquisitions.
    pub queue_wait_milliseconds_total: u64,
    /// Number of queue waits represented in the aggregate.
    pub queue_wait_samples: u64,
    /// Aggregate wall time of started scientific jobs.
    pub worker_runtime_milliseconds_total: u64,
    /// Number of started jobs represented in the runtime aggregate.
    pub worker_runtime_samples: u64,
}

impl Gate {
    /// Allow `permits` jobs at once.
    #[must_use]
    pub fn new(permits: usize) -> Self {
        Self::with_queue(permits, DEFAULT_QUEUE_LIMIT)
    }

    fn with_queue(permits: usize, queue_limit: usize) -> Self {
        // A semaphore of zero would refuse everything forever; one is the
        // honest floor.
        let permits = permits.max(1);
        Self {
            permits: Arc::new(Semaphore::new(permits)),
            capacity: permits,
            // This semaphore counts waiters only; running jobs are counted by
            // `permits`. Keeping the two separate means a worker completing
            // cannot accidentally create an extra queue slot.
            queue: Arc::new(Semaphore::new(queue_limit)),
            running_weight: Arc::new(AtomicUsize::new(0)),
            queued_jobs: Arc::new(AtomicUsize::new(0)),
            started_jobs: Arc::new(AtomicU64::new(0)),
            completed_jobs: Arc::new(AtomicU64::new(0)),
            failed_jobs: Arc::new(AtomicU64::new(0)),
            cancelled_jobs: Arc::new(AtomicU64::new(0)),
            queue_wait_milliseconds_total: Arc::new(AtomicU64::new(0)),
            queue_wait_samples: Arc::new(AtomicU64::new(0)),
            worker_runtime_milliseconds_total: Arc::new(AtomicU64::new(0)),
            worker_runtime_samples: Arc::new(AtomicU64::new(0)),
        }
    }

    /// The process's one gate.
    ///
    /// A ceiling only holds if there is exactly one of it: two gates of N
    /// permits each are 2N interpreters waiting to happen. Request-driven
    /// design/sequence work and startup catalogue warming use this shared gate.
    /// Readiness keeps one deliberately reserved operational probe outside the
    /// request queue so saturation cannot make a healthy instance fail its
    /// orchestrator check.
    #[must_use]
    pub fn shared() -> Self {
        static GATE: std::sync::OnceLock<Gate> = std::sync::OnceLock::new();
        GATE.get_or_init(Self::from_env).clone()
    }

    /// Size from the environment, falling back to the machine's parallelism.
    ///
    /// Deliberately not an error when unset: a deployment that never thinks
    /// about it still gets a sane number.
    #[must_use]
    pub fn from_env() -> Self {
        let configured = std::env::var("PCR_MAX_CONCURRENT_WORKERS")
            .ok()
            .and_then(|value| value.trim().parse::<usize>().ok())
            .map(|value| value.clamp(1, 16));
        let detected = std::thread::available_parallelism()
            .map(std::num::NonZeroUsize::get)
            .unwrap_or(2);
        let queue_limit = std::env::var("PCR_MAX_QUEUED_WORKERS")
            .ok()
            .and_then(|value| value.trim().parse::<usize>().ok())
            .map_or(DEFAULT_QUEUE_LIMIT, |value| value.min(1024));
        Self::with_queue(configured.unwrap_or(detected.clamp(1, 16)), queue_limit)
    }

    /// Configured ceiling on jobs that may run at once.
    ///
    /// This is deliberately not `Semaphore::available_permits()`: observability
    /// must report the configured capacity even while a warm-up or request is
    /// actively holding a permit.
    #[must_use]
    pub fn permits(&self) -> usize {
        self.capacity
    }

    /// Point-in-time resource scheduler statistics for operator diagnostics.
    #[must_use]
    pub fn snapshot(&self) -> GateSnapshot {
        GateSnapshot {
            capacity: self.capacity,
            available: self.permits.available_permits(),
            running_weight: self.running_weight.load(Ordering::Relaxed),
            queued_jobs: self.queued_jobs.load(Ordering::Relaxed),
            started_jobs: self.started_jobs.load(Ordering::Relaxed),
            completed_jobs: self.completed_jobs.load(Ordering::Relaxed),
            failed_jobs: self.failed_jobs.load(Ordering::Relaxed),
            cancelled_jobs: self.cancelled_jobs.load(Ordering::Relaxed),
            queue_wait_milliseconds_total: self
                .queue_wait_milliseconds_total
                .load(Ordering::Relaxed),
            queue_wait_samples: self.queue_wait_samples.load(Ordering::Relaxed),
            worker_runtime_milliseconds_total: self
                .worker_runtime_milliseconds_total
                .load(Ordering::Relaxed),
            worker_runtime_samples: self.worker_runtime_samples.load(Ordering::Relaxed),
        }
    }

    fn elapsed_milliseconds(started: Instant) -> u64 {
        u64::try_from(started.elapsed().as_millis()).unwrap_or(u64::MAX)
    }

    fn record_queue_wait(&self, started: Instant) {
        self.queue_wait_milliseconds_total
            .fetch_add(Self::elapsed_milliseconds(started), Ordering::Relaxed);
        self.queue_wait_samples.fetch_add(1, Ordering::Relaxed);
    }

    fn record_started_job(&self) {
        self.started_jobs.fetch_add(1, Ordering::Relaxed);
    }

    fn record_finished_job<T>(&self, started: Instant, answer: &Result<T, CoreError>) {
        self.worker_runtime_milliseconds_total
            .fetch_add(Self::elapsed_milliseconds(started), Ordering::Relaxed);
        self.worker_runtime_samples.fetch_add(1, Ordering::Relaxed);
        self.completed_jobs.fetch_add(1, Ordering::Relaxed);
        match answer {
            Ok(_) => {}
            Err(CoreError::Cancelled) => {
                self.cancelled_jobs.fetch_add(1, Ordering::Relaxed);
            }
            Err(_) => {
                self.failed_jobs.fetch_add(1, Ordering::Relaxed);
            }
        }
    }

    /// Run a job with a canonical relative resource weight.
    ///
    /// A heavy assay consumes multiple permits so four light searches cannot be
    /// oversubscribed by four simultaneous BLAST/tiling/LAMP jobs. On hosts
    /// with fewer permits than the canonical weight, the job consumes the
    /// entire host rather than waiting forever for permits that can never
    /// exist.
    pub async fn run_weighted<F, T>(&self, weight: usize, job: F) -> Result<T, CoreError>
    where
        F: FnOnce() -> Result<T, CoreError> + Send + 'static,
        T: Send + 'static,
    {
        let weight = weight.clamp(1, self.capacity);
        let permits = weight as u32;
        let permit = match self.permits.clone().try_acquire_many_owned(permits) {
            Ok(permit) => permit,
            Err(_) => {
                let queued = self.queue.clone().try_acquire_owned().map_err(|_| {
                    CoreError::WorkerBusy(
                        "the design service is at capacity; wait a moment and try again".to_owned(),
                    )
                })?;
                self.queued_jobs.fetch_add(1, Ordering::Relaxed);
                let queued_at = Instant::now();
                let acquired = self.permits.clone().acquire_many_owned(permits).await;
                self.record_queue_wait(queued_at);
                self.queued_jobs.fetch_sub(1, Ordering::Relaxed);
                let permit = acquired
                    .map_err(|_| CoreError::ToolFailed("the server is shutting down".to_owned()))?;
                drop(queued);
                permit
            }
        };

        let running_weight = self.running_weight.clone();
        running_weight.fetch_add(weight, Ordering::Relaxed);
        self.record_started_job();
        let runtime_started = Instant::now();
        let joined = tokio::task::spawn_blocking(move || {
            let _held = permit;
            let result = job();
            running_weight.fetch_sub(weight, Ordering::Relaxed);
            result
        })
        .await;
        match joined {
            Ok(answer) => {
                self.record_finished_job(runtime_started, &answer);
                answer
            }
            Err(joined) => {
                // A panic occurs before the closure decrements the counter. Correct
                // the diagnostic accounting here; semaphore permits are released
                // by unwinding the blocking closure.
                self.running_weight.fetch_sub(weight, Ordering::Relaxed);
                self.worker_runtime_milliseconds_total.fetch_add(
                    Self::elapsed_milliseconds(runtime_started),
                    Ordering::Relaxed,
                );
                self.worker_runtime_samples.fetch_add(1, Ordering::Relaxed);
                self.failed_jobs.fetch_add(1, Ordering::Relaxed);
                Err(CoreError::ToolFailed(format!(
                    "a design task did not finish: {joined}"
                )))
            }
        }
    }

    /// Run a weighted job that can be cancelled while queued or while its
    /// scientific subprocess is active.
    ///
    /// `on_start` is awaited only after worker capacity has been acquired and
    /// immediately before the blocking scientific closure starts. Durable-job
    /// callers use that boundary to transition PostgreSQL from `queued` to
    /// `running`, so a long scheduler wait is never falsely reported as active
    /// execution.
    pub async fn run_weighted_cancellable_with_start<F, T, S, SF>(
        &self,
        weight: usize,
        token: pcr_worker_client::CancellationToken,
        on_start: S,
        job: F,
    ) -> Result<T, CoreError>
    where
        F: FnOnce() -> Result<T, CoreError> + Send + 'static,
        T: Send + 'static,
        S: FnOnce() -> SF + Send,
        SF: std::future::Future<Output = Result<(), CoreError>> + Send,
    {
        let weight = weight.clamp(1, self.capacity);
        let permits = weight as u32;
        let permit = match self.permits.clone().try_acquire_many_owned(permits) {
            Ok(permit) => permit,
            Err(_) => {
                let queued = self.queue.clone().try_acquire_owned().map_err(|_| {
                    CoreError::WorkerBusy(
                        "the design service is at capacity; wait a moment and try again".to_owned(),
                    )
                })?;
                self.queued_jobs.fetch_add(1, Ordering::Relaxed);
                let queued_at = Instant::now();
                // Keep one acquire future registered in Tokio's semaphore queue.
                // Repeated try_acquire polling can starve an older multi-permit
                // waiter behind a stream of one-permit jobs. Cancellation remains
                // responsive via a small ticker without forfeiting queue fairness.
                let acquired = {
                    let acquire = self.permits.clone().acquire_many_owned(permits);
                    tokio::pin!(acquire);
                    loop {
                        tokio::select! {
                            result = &mut acquire => {
                                break result.map_err(|_| CoreError::ToolFailed("the server is shutting down".to_owned()))?;
                            }
                            () = tokio::time::sleep(std::time::Duration::from_millis(25)) => {
                                if token.is_cancelled() {
                                    self.record_queue_wait(queued_at);
                                    self.cancelled_jobs.fetch_add(1, Ordering::Relaxed);
                                    self.queued_jobs.fetch_sub(1, Ordering::Relaxed);
                                    drop(queued);
                                    return Err(CoreError::Cancelled);
                                }
                            }
                        }
                    }
                };
                self.record_queue_wait(queued_at);
                self.queued_jobs.fetch_sub(1, Ordering::Relaxed);
                drop(queued);
                acquired
            }
        };

        if token.is_cancelled() {
            self.cancelled_jobs.fetch_add(1, Ordering::Relaxed);
            drop(permit);
            return Err(CoreError::Cancelled);
        }
        if let Err(error) = on_start().await {
            drop(permit);
            return Err(error);
        }
        if token.is_cancelled() {
            self.cancelled_jobs.fetch_add(1, Ordering::Relaxed);
            drop(permit);
            return Err(CoreError::Cancelled);
        }

        let running_weight = self.running_weight.clone();
        running_weight.fetch_add(weight, Ordering::Relaxed);
        self.record_started_job();
        let runtime_started = Instant::now();
        let cancellation = token.clone();
        let joined = tokio::task::spawn_blocking(move || {
            let _held = permit;
            let result = pcr_worker_client::with_cancellation(cancellation, job);
            running_weight.fetch_sub(weight, Ordering::Relaxed);
            result
        })
        .await;
        match joined {
            Ok(answer) => {
                self.record_finished_job(runtime_started, &answer);
                answer
            }
            Err(joined) => {
                self.running_weight.fetch_sub(weight, Ordering::Relaxed);
                self.worker_runtime_milliseconds_total.fetch_add(
                    Self::elapsed_milliseconds(runtime_started),
                    Ordering::Relaxed,
                );
                self.worker_runtime_samples.fetch_add(1, Ordering::Relaxed);
                self.failed_jobs.fetch_add(1, Ordering::Relaxed);
                Err(CoreError::ToolFailed(format!(
                    "a design task did not finish: {joined}"
                )))
            }
        }
    }

    /// Run a weighted cancellable job with no durable start hook.
    pub async fn run_weighted_cancellable<F, T>(
        &self,
        weight: usize,
        token: pcr_worker_client::CancellationToken,
        job: F,
    ) -> Result<T, CoreError>
    where
        F: FnOnce() -> Result<T, CoreError> + Send + 'static,
        T: Send + 'static,
    {
        self.run_weighted_cancellable_with_start(weight, token, || async { Ok(()) }, job)
            .await
    }

    /// Run one blocking job off the async runtime's threads, holding a permit
    /// for as long as it runs.
    ///
    /// Request-driven calls into the Python worker are blocking by construction
    /// — the worker is a subprocess driven over pipes — so those paths go
    /// through here. Readiness is the documented reserved-probe exception. Two failures are distinguished: waiting for a
    /// permit cannot fail except while the process is shutting down, and a job
    /// that panicked is reported as what it is rather than lost to a join
    /// error.
    ///
    /// # Errors
    ///
    /// [`CoreError::ToolFailed`] when the process is shutting down or the job
    /// itself failed; the job's own error is passed through untouched.
    pub async fn run<F, T>(&self, job: F) -> Result<T, CoreError>
    where
        F: FnOnce() -> Result<T, CoreError> + Send + 'static,
        T: Send + 'static,
    {
        self.run_weighted(1, job).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[tokio::test]
    async fn a_permit_is_held_for_the_whole_job_so_the_ceiling_holds() {
        let gate = Gate::new(1);
        let concurrent = Arc::new(AtomicUsize::new(0));
        let seen = Arc::new(AtomicUsize::new(0));

        let mut handles = Vec::new();
        for _ in 0..4 {
            let gate = gate.clone();
            let concurrent = concurrent.clone();
            let seen = seen.clone();
            handles.push(tokio::spawn(async move {
                gate.run(move || {
                    let now = concurrent.fetch_add(1, Ordering::SeqCst) + 1;
                    seen.fetch_max(now, Ordering::SeqCst);
                    std::thread::sleep(std::time::Duration::from_millis(30));
                    concurrent.fetch_sub(1, Ordering::SeqCst);
                    Ok(())
                })
                .await
                .expect("one permit at a time");
            }));
        }
        for handle in handles {
            handle.await.expect("tasks join");
        }

        assert_eq!(seen.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn reported_permits_are_the_ceiling_not_the_currently_available_count() {
        let gate = Gate::new(2);
        let _held = gate
            .permits
            .clone()
            .try_acquire_owned()
            .expect("one permit");
        assert_eq!(gate.permits(), 2);
    }

    #[tokio::test]
    async fn a_panicking_job_is_reported_not_lost() {
        let gate = Gate::new(2);
        let error = gate
            .run(|| -> Result<(), CoreError> { panic!("worker went wrong") })
            .await
            .expect_err("a panic becomes an error");
        assert!(matches!(error, CoreError::ToolFailed(_)));
        // And the permit came back with it.
        assert_eq!(gate.permits(), 2);
    }

    #[tokio::test]
    async fn a_heavy_cancellable_waiter_keeps_fifo_priority_over_later_light_jobs() {
        let gate = Gate::with_queue(4, 16);
        let held = gate
            .permits
            .clone()
            .acquire_many_owned(4)
            .await
            .expect("reserve the whole gate");
        let order = Arc::new(std::sync::Mutex::new(Vec::<usize>::new()));

        let heavy_gate = gate.clone();
        let heavy_order = order.clone();
        let heavy = tokio::spawn(async move {
            heavy_gate
                .run_weighted_cancellable(
                    4,
                    pcr_worker_client::CancellationToken::new(),
                    move || {
                        heavy_order.lock().expect("order lock").push(4);
                        Ok(())
                    },
                )
                .await
        });

        // Let the four-permit acquire reach the semaphore queue before lighter
        // followers are submitted. Fairness means later one-permit work cannot
        // repeatedly steal partial capacity from the older heavy waiter.
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        let mut lights = Vec::new();
        for _ in 0..4 {
            let light_gate = gate.clone();
            let light_order = order.clone();
            lights.push(tokio::spawn(async move {
                light_gate
                    .run_weighted(1, move || {
                        light_order.lock().expect("order lock").push(1);
                        Ok(())
                    })
                    .await
            }));
        }

        drop(held);
        heavy.await.expect("heavy joins").expect("heavy runs");
        for light in lights {
            light.await.expect("light joins").expect("light runs");
        }
        assert_eq!(order.lock().expect("order lock").first().copied(), Some(4));
    }

    #[tokio::test]
    async fn operator_metrics_count_success_and_failure_without_request_data() {
        let gate = Gate::new(2);
        gate.run(|| Ok::<_, CoreError>(()))
            .await
            .expect("successful worker job");
        let failure = gate
            .run(|| Err::<(), _>(CoreError::InvalidRequest("test".to_owned())))
            .await;
        assert!(matches!(failure, Err(CoreError::InvalidRequest(_))));

        let snapshot = gate.snapshot();
        assert_eq!(snapshot.started_jobs, 2);
        assert_eq!(snapshot.completed_jobs, 2);
        assert_eq!(snapshot.failed_jobs, 1);
        assert_eq!(snapshot.cancelled_jobs, 0);
        assert_eq!(snapshot.worker_runtime_samples, 2);
    }

    #[tokio::test]
    async fn a_burst_is_refused_once_the_bounded_queue_is_full() {
        let gate = Gate::with_queue(1, 0);
        let started = Arc::new(tokio::sync::Notify::new());
        let first_started = started.clone();
        let first_gate = gate.clone();
        let first = tokio::spawn(async move {
            first_gate
                .run(move || {
                    first_started.notify_one();
                    std::thread::sleep(std::time::Duration::from_millis(40));
                    Ok(())
                })
                .await
        });
        started.notified().await;
        let second = gate.run(|| Ok(()));
        let second = second.await;
        let first = first.await.expect("first task joins");
        assert!(first.is_ok());
        assert!(matches!(second, Err(CoreError::WorkerBusy(_))));
    }
}
