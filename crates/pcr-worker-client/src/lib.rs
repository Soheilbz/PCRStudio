//! Supervised Rust ↔ Python scientific-worker process boundary.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

//! Running the Python worker, and reading what it says back.
//!
//! The worker is a separate process rather than a linked library, and the
//! reason is a licence: it imports Primer3, which is GPLv2, and everything in
//! this crate is MIT. A program that runs another program and reads its output
//! is not a derivative work of it. The same boundary buys something practical
//! as well — a tool behind a pipe can be replaced in an afternoon.
//!
//! One JSON object goes in on stdin, one comes back on stdout. A failure comes
//! back as `{"error": {"kind": ..., "detail": ...}}` with a non-zero exit, so
//! this side branches on a vocabulary rather than parsing prose.
//!
//! Three properties of this file are load-bearing for the whole service:
//!
//! - **The timeout is real.** A design that never comes back would otherwise
//!   hold its thread forever, and enough of those is a dead server.
//! - **All three pipes move at once.** Writing the request to completion
//!   before reading anything deadlocks the moment the worker emits more than
//!   one pipe-buffer of output before finishing its input — so each pipe gets
//!   its own thread.
//! - **A failed call leaves no child behind.** Every early return either has
//!   no child yet or kills the one it has.

use std::cell::RefCell;
use std::io::{Read, Write};
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use serde::Deserialize;

/// Worker process/IPC failure independent of PCR domain errors.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum WorkerClientError {
    /// Caller supplied a request rejected by the worker boundary/scientific input layer.
    #[error("invalid worker request: {0}")]
    InvalidRequest(String),
    /// Requested operation/tool is not implemented in this deployment.
    #[error("worker capability is unavailable: {0}")]
    NotImplemented(String),
    /// Process, protocol, timeout, crash, or unexpected worker failure.
    #[error("worker process failed: {0}")]
    ToolFailed(String),
    /// A caller explicitly cancelled the running scientific job.
    #[error("worker request was cancelled")]
    Cancelled,
}

/// Worker-client result.
pub type Result<T> = std::result::Result<T, WorkerClientError>;

/// How often a waiting caller re-checks whether the child has finished.
const POLL_INTERVAL: Duration = Duration::from_millis(20);

/// Maximum worker protocol output retained in memory. A legitimate Foundation
/// response is far smaller than this; the cap prevents a broken/native tool
/// from turning stdout into an API-process OOM. The tail is retained so the
/// final JSON document remains available when harmless banners precede it.
const MAX_STDOUT_BYTES: usize = pcr_contracts::MAX_WORKER_STDOUT_BYTES;

/// Maximum diagnostic stderr retained in memory. Only the tail is useful for
/// operator diagnostics and user-safe summaries; unbounded diagnostics are a
/// resource-exhaustion vector.
const MAX_STDERR_BYTES: usize = pcr_contracts::MAX_WORKER_STDERR_BYTES;

/// Cooperative cancellation handle for a running worker process.
#[derive(Debug, Clone, Default)]
pub struct CancellationToken(Arc<AtomicBool>);

impl CancellationToken {
    /// Create a token in the not-cancelled state.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Request cancellation. Repeated calls are harmless.
    pub fn cancel(&self) {
        self.0.store(true, Ordering::Release);
    }

    /// Whether cancellation has been requested.
    #[must_use]
    pub fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::Acquire)
    }
}

thread_local! {
    static ACTIVE_CANCELLATION: RefCell<Option<CancellationToken>> = const { RefCell::new(None) };
}

/// Execute a domain operation with a cancellation token visible to every
/// worker subprocess started on this blocking thread.
///
/// Engines do not need to accept cancellation as a scientific parameter: the
/// process adapter observes it while waiting on the child and kills that child
/// promptly. The previous thread-local value is restored even for nesting.
pub fn with_cancellation<T>(token: CancellationToken, operation: impl FnOnce() -> T) -> T {
    struct Restore(Option<CancellationToken>);
    impl Drop for Restore {
        fn drop(&mut self) {
            ACTIVE_CANCELLATION.with(|slot| *slot.borrow_mut() = self.0.take());
        }
    }
    let previous = ACTIVE_CANCELLATION.with(|slot| slot.borrow_mut().replace(token));
    let _restore = Restore(previous);
    operation()
}

fn cancellation_requested() -> bool {
    ACTIVE_CANCELLATION.with(|slot| {
        slot.borrow()
            .as_ref()
            .is_some_and(CancellationToken::is_cancelled)
    })
}

/// The environment variables a worker child receives, by name.
///
/// The interpreter gets the few things it genuinely needs to start and to
/// answer: where its runtime lives, where scratch files go, which locale to
/// encode with. Everything else the API process carries — database URLs most
/// of all — stops at this process boundary. The worker computes numbers from
/// the request we hand it; it never needs to know where results are stored,
/// and a child that cannot leak what it was never told cannot be turned into
/// the path that leaks it.
///
/// `PYTHONPATH` and friends are deliberately absent: code search paths are
/// how an inherited environment becomes injected behaviour.
const CHILD_ENV_ALLOWLIST: &[&str] = &[
    // Runtime and tool lookup.
    "PATH",
    // PCRStudio's generation-1 toolchain.  These are configuration paths and
    // snapshot identities, not application secrets.  Passing only named
    // variables preserves the worker sandbox while allowing native Linux
    // validators to be pinned explicitly and fingerprinted.
    "PCRSTUDIO_SCIENTIFIC_POLICY",
    "PCRSTUDIO_EXTERNAL_VALIDATION",
    "PCRSTUDIO_TOOLCHAIN_MODE",
    "PCRSTUDIO_MFEPRIMER",
    "PCRSTUDIO_MFEPRIMER_SHA256",
    "PCRSTUDIO_MFEPRIMER_DATABASES",
    "PCRSTUDIO_MFEPRIMER_DATABASES_SHA256",
    "PCRSTUDIO_MFEPRIMER_DATABASES_SCOPE",
    "PCRSTUDIO_MFEPRIMER_DATABASES_MANIFEST",
    "PCRSTUDIO_BLASTN",
    "PCRSTUDIO_BLASTN_SHA256",
    "PCRSTUDIO_BLAST_DATABASE",
    "PCRSTUDIO_BLAST_DATABASE_SHA256",
    "PCRSTUDIO_BLAST_DATABASE_SCOPE",
    "PCRSTUDIO_BLAST_DATABASE_MANIFEST",
    "PCRSTUDIO_BLAST_THREADS",
    "PCRSTUDIO_PRIMERPOOLER",
    "PCRSTUDIO_PRIMERPOOLER_SHA256",
    "PCRSTUDIO_PRIMALSCHEME3",
    "PCRSTUDIO_PRIMALSCHEME3_SHA256",
    "PCRSTUDIO_PYDNA_PYTHON",
    "PCRSTUDIO_PYDNA_PYTHON_SHA256",
    "PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE",
    "PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE_SHA256",
    "PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256",
    "PCRSTUDIO_MAFFT",
    "PCRSTUDIO_MAFFT_SHA256",
    "PCRSTUDIO_MAFFT_ARCHIVE_SHA256",
    "PCRSTUDIO_MAFFT_BUNDLE_ROOT",
    "PCRSTUDIO_MAFFT_BUNDLE_SHA256",
    "PCRSTUDIO_TILING_BACKEND",
    "MPLCONFIGDIR",
    // Scratch space and home, for libraries that write temp files.
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    // Locale, so text encodings do not depend on the parent's mood.
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
];

/// The parent environment filtered down to [`CHILD_ENV_ALLOWLIST`].
fn child_environment(parent: impl Iterator<Item = (String, String)>) -> Vec<(String, String)> {
    parent
        .filter(|(key, _)| CHILD_ENV_ALLOWLIST.contains(&key.as_str()))
        .collect()
}

/// Which interpreter to run, and what it may take.
#[derive(Debug, Clone)]
pub struct Worker {
    /// Path to a Python interpreter with `pcrstudio-tools` installed.
    python: String,
    /// How long one call may take before it is abandoned.
    ///
    /// Abandoned means killed: the child is not left running to burn CPU on an
    /// answer nobody will read.
    timeout: Duration,
}

impl Default for Worker {
    fn default() -> Self {
        Self::from_env()
    }
}

/// What the worker sends when something went wrong.
#[derive(Debug, Deserialize)]
struct WorkerError {
    kind: String,
    detail: String,
    #[serde(default)]
    code: Option<String>,
}

#[derive(Debug, Deserialize)]
struct WorkerFailure {
    error: WorkerError,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct IpcResponse {
    protocol_version: String,
    result_schema: i32,
    request_id: String,
    ok: bool,
    #[serde(default)]
    payload: Option<serde_json::Value>,
    #[serde(default)]
    error: Option<WorkerError>,
}

fn next_request_id() -> String {
    static COUNTER: AtomicU64 = AtomicU64::new(1);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    format!("{}-{n}", std::process::id())
}

fn request_module(request: &serde_json::Value) -> Option<&str> {
    request
        .get("assay")
        .and_then(|value| value.get("id"))
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
}

#[derive(Debug, Default)]
struct BoundedOutput {
    bytes: Vec<u8>,
    truncated: bool,
    read_error: Option<String>,
}

/// Drain one pipe to EOF on its own thread while retaining only a bounded tail.
///
/// The tail is retained only for safe diagnostics. Crossing the budget is a
/// protocol failure even when the final bytes happen to contain valid JSON; a
/// worker must not be allowed to hide abnormal/unbounded chatter behind a
/// success-shaped final envelope.
fn drain<R>(
    pipe: Option<R>,
    limit: usize,
    output_limit_exceeded: Arc<AtomicBool>,
) -> thread::JoinHandle<BoundedOutput>
where
    R: Read + Send + 'static,
{
    thread::spawn(move || {
        let Some(mut pipe) = pipe else {
            return BoundedOutput::default();
        };
        let mut output = BoundedOutput {
            bytes: Vec::with_capacity(limit.min(64 * 1024)),
            truncated: false,
            read_error: None,
        };
        let mut chunk = [0_u8; 8192];
        loop {
            let read = match pipe.read(&mut chunk) {
                Ok(0) => break,
                Ok(read) => read,
                Err(error) if error.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(error) => {
                    output.read_error = Some(error.to_string());
                    break;
                }
            };
            if limit == 0 {
                output.truncated = true;
                output_limit_exceeded.store(true, Ordering::Release);
                continue;
            }

            // Keep at most the final `limit` bytes for diagnostics, but signal
            // overflow only when the cumulative stream actually crosses the
            // ceiling. An exact-limit write is valid and must not be rejected.
            let overflow = output
                .bytes
                .len()
                .saturating_add(read)
                .saturating_sub(limit);
            if output.truncated || overflow > 0 {
                if !output.truncated {
                    output.truncated = true;
                    output_limit_exceeded.store(true, Ordering::Release);
                }
                if read >= limit {
                    output.bytes.clear();
                    output.bytes.extend_from_slice(&chunk[read - limit..read]);
                } else {
                    let discard = output
                        .bytes
                        .len()
                        .saturating_add(read)
                        .saturating_sub(limit);
                    if discard > 0 {
                        output.bytes.drain(..discard.min(output.bytes.len()));
                    }
                    output.bytes.extend_from_slice(&chunk[..read]);
                }
            } else {
                output.bytes.extend_from_slice(&chunk[..read]);
            }
        }
        output
    })
}

impl Worker {
    /// Look for the repository-local worker environment from the current
    /// directory upward. The API and the Rust integration tests are both
    /// normally launched from the repository root, but walking ancestors
    /// also keeps this useful when a command starts in a child directory.
    fn project_python() -> Option<PathBuf> {
        let current = std::env::current_dir().ok()?;
        for directory in current.ancestors() {
            let candidate = directory.join("tools/.venv/bin/python");
            if candidate.is_file() {
                return Some(candidate);
            }
        }
        None
    }

    /// Read the interpreter from the environment.
    ///
    /// `PCR_PYTHON` names it. When it is absent, prefer the repository-local
    /// tools virtual environment so dependency resolution remains bound to the
    /// repository. The final `python3` fallback supports installed/container runtimes.
    #[must_use]
    pub fn from_env() -> Self {
        let python = std::env::var("PCR_PYTHON")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .or_else(|| Self::project_python().map(|path| path.to_string_lossy().into_owned()))
            .unwrap_or_else(|| "python3".to_owned());
        Self {
            python,
            timeout: Duration::from_secs(
                std::env::var("PCR_WORKER_TIMEOUT_SECONDS")
                    .ok()
                    .and_then(|v| v.trim().parse().ok())
                    .unwrap_or(120),
            ),
        }
    }

    /// Name the interpreter directly. For tests, and for a deployment that
    /// knows where its virtual environment is.
    #[must_use]
    pub fn new(python: impl Into<String>) -> Self {
        Self {
            python: python.into(),
            ..Self::from_env()
        }
    }

    /// Name the interpreter directly *and* set the timeout. Tests use short
    /// ones.
    #[must_use]
    pub fn with_timeout(python: impl Into<String>, timeout: Duration) -> Self {
        Self {
            python: python.into(),
            timeout,
        }
    }

    /// How long a call may run.
    #[must_use]
    pub fn timeout(&self) -> Duration {
        self.timeout
    }

    /// Run one command and return what it answered.
    ///
    /// # Errors
    ///
    /// [`WorkerClientError::ToolFailed`] if the worker could not be started, died,
    /// overran its timeout, or answered something that is not JSON. Otherwise
    /// whatever the worker's own error vocabulary maps to.
    pub fn call(&self, command: &str, request: &serde_json::Value) -> Result<serde_json::Value> {
        let request_id = next_request_id();
        let module = request_module(request).map(str::to_owned);
        let engine = module
            .as_deref()
            .and_then(pcr_contracts::engine_for_module)
            .or_else(|| pcr_contracts::engine_for_command(command))
            .unwrap_or("utility")
            .to_owned();
        let envelope = serde_json::json!({
            "protocolVersion": pcr_contracts::IPC_PROTOCOL_VERSION,
            "requestSchema": pcr_contracts::REQUEST_SCHEMA_VERSION,
            "resultSchema": pcr_contracts::RESULT_SCHEMA_VERSION,
            "requestId": request_id,
            "command": command,
            "engine": engine,
            "module": module,
            "payload": request,
        });
        let payload = serde_json::to_vec(&envelope).map_err(|error| {
            WorkerClientError::ToolFailed(format!("request envelope was not serialisable: {error}"))
        })?;
        let answer = self.run(["-m", "pcr_tools", command], &payload)?;
        let response: IpcResponse = serde_json::from_value(answer).map_err(|error| {
            WorkerClientError::ToolFailed(format!(
                "worker did not answer with the Generation 1 foundation IPC envelope: {error}"
            ))
        })?;
        if response.protocol_version != pcr_contracts::IPC_PROTOCOL_VERSION {
            return Err(WorkerClientError::ToolFailed(format!(
                "worker IPC protocol mismatch: expected {}, got {}",
                pcr_contracts::IPC_PROTOCOL_VERSION,
                response.protocol_version
            )));
        }
        if response.result_schema != pcr_contracts::RESULT_SCHEMA_VERSION {
            return Err(WorkerClientError::ToolFailed(format!(
                "worker result schema mismatch: expected {}, got {}",
                pcr_contracts::RESULT_SCHEMA_VERSION,
                response.result_schema
            )));
        }
        if response.request_id != request_id {
            return Err(WorkerClientError::ToolFailed(
                "worker response requestId did not match the request".to_owned(),
            ));
        }
        if !response.ok {
            let error = response.error.ok_or_else(|| {
                WorkerClientError::ToolFailed(
                    "worker failure envelope omitted its structured error".to_owned(),
                )
            })?;
            return Err(map_error(&error.kind, error.detail, error.code));
        }
        response.payload.ok_or_else(|| {
            WorkerClientError::ToolFailed("worker success envelope omitted its payload".to_owned())
        })
    }

    /// Run one interpreter invocation and return what it answered.
    ///
    /// `call` goes through the dispatcher module; this lower-level form exists
    /// for tests, which speak to a bare interpreter to prove the pipe and
    /// timeout machinery itself.
    fn run<'a>(
        &self,
        args: impl IntoIterator<Item = &'a str>,
        payload: &[u8],
    ) -> Result<serde_json::Value> {
        let mut command = Command::new(&self.python);
        command
            .args(args)
            .env_clear()
            .envs(child_environment(std::env::vars()))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(unix)]
        {
            // Every scientific request owns a POSIX process group. Native
            // tools launched by Python inherit that group, so timeout, cancel
            // and shutdown terminate the complete computation tree rather
            // than only the interpreter process.
            command.process_group(0);
        }
        let mut child = command.spawn().map_err(|error| {
            WorkerClientError::ToolFailed(format!(
                "could not start the design worker with `{}`: {error}. \
                     Set PCR_PYTHON to a Python that has pcrstudio-tools installed.",
                self.python
            ))
        })?;

        // From here on, every return path owes the child a death.
        let result = self.drive(&mut child, payload);

        let child_still_running = result.is_err() && !matches!(child.try_wait(), Ok(Some(_)));
        if child_still_running && Self::reap(&mut child).is_none() {
            // The child would not die on request. There is nothing further to
            // do about it here — the next readiness probe or process-wide
            // teardown is the backstop — but the log line matters more than
            // the error's own text, because an unkillable worker is a host
            // problem, not a request problem.
            tracing::error!(
                event = "scientific_worker_reap_failed",
                "the design worker survived being killed; check the host for orphaned interpreters"
            );
        }

        result
    }

    /// Feed the child, wait for it within the timeout, collect its answer.
    fn drive(&self, child: &mut std::process::Child, payload: &[u8]) -> Result<serde_json::Value> {
        let mut stdin = child.stdin.take().ok_or_else(|| {
            WorkerClientError::ToolFailed("the design worker refused its own stdin".to_owned())
        })?;
        let output_limit_exceeded = Arc::new(AtomicBool::new(false));
        let stdout = drain(
            child.stdout.take(),
            MAX_STDOUT_BYTES,
            Arc::clone(&output_limit_exceeded),
        );
        let stderr = drain(
            child.stderr.take(),
            MAX_STDERR_BYTES,
            Arc::clone(&output_limit_exceeded),
        );

        // Writing happens off this thread so that a worker which answers (or
        // complains) loudly cannot fill its output pipes and stop reading
        // while we are still sending — each side then waits for the other
        // forever. Dropping `stdin` at the end of the closure closes our end,
        // which is what tells the worker the request is complete.
        let owned = payload.to_vec();
        let writer = thread::spawn(move || stdin.write_all(&owned));

        // Poll rather than block, because a blocked wait cannot be told about
        // cancellation, the deadline, or a process that has crossed its output
        // budget. Every stop reason converges on the same cleanup path below so
        // no error branch can forget to reap a child or join a pipe helper.
        enum WaitOutcome {
            Exited(ExitStatus),
            Cancelled,
            TimedOut,
            OutputLimit,
            WaitFailed(String),
        }

        let deadline = Instant::now() + self.timeout;
        let outcome = loop {
            match child.try_wait() {
                Ok(Some(status)) => break WaitOutcome::Exited(status),
                Ok(None) if cancellation_requested() => break WaitOutcome::Cancelled,
                Ok(None) if output_limit_exceeded.load(Ordering::Acquire) => {
                    break WaitOutcome::OutputLimit;
                }
                Ok(None) if Instant::now() >= deadline => break WaitOutcome::TimedOut,
                Ok(None) => thread::sleep(POLL_INTERVAL),
                Err(error) => break WaitOutcome::WaitFailed(error.to_string()),
            }
        };

        match &outcome {
            WaitOutcome::Exited(_) => {
                // The Python parent has exited, but a faulty native tool could
                // still share this request's process group and pipe handles.
                Self::kill_process_group(child.id(), "-KILL");
            }
            _ => {
                Self::terminate_tree(child);
            }
        }

        // The process/group is gone now, so all helpers must be able to finish.
        // A blocked stdin writer receives EPIPE instead of surviving the call.
        let writer = writer.join();
        let stdout = stdout.join();
        let stderr = stderr.join();

        match &outcome {
            WaitOutcome::Cancelled => return Err(WorkerClientError::Cancelled),
            WaitOutcome::TimedOut => {
                return Err(WorkerClientError::ToolFailed(format!(
                    "the design worker ran past {}s and was stopped",
                    self.timeout.as_secs()
                )));
            }
            WaitOutcome::WaitFailed(error) => {
                return Err(WorkerClientError::ToolFailed(format!(
                    "the design worker could not be waited on: {error}"
                )));
            }
            WaitOutcome::OutputLimit | WaitOutcome::Exited(_) => {}
        }

        // A helper thread is part of the protocol transport, not a best-effort
        // logger. Panics and pipe I/O errors must therefore fail closed rather
        // than being converted into empty output that could mask a broken
        // request/response exchange. Output-limit termination is reported first
        // because killing the process group can legitimately make the writer
        // observe EPIPE while the real cause is already known.
        let stdout = stdout.map_err(|_| {
            WorkerClientError::ToolFailed(
                "the design worker stdout reader stopped unexpectedly".to_owned(),
            )
        })?;
        let stderr = stderr.map_err(|_| {
            WorkerClientError::ToolFailed(
                "the design worker stderr reader stopped unexpectedly".to_owned(),
            )
        })?;

        let stdout_truncated = stdout.truncated;
        let stderr_truncated = stderr.truncated;
        if stdout_truncated || stderr_truncated {
            let stream = match (stdout_truncated, stderr_truncated) {
                (true, true) => "stdout and stderr",
                (true, false) => "stdout",
                (false, true) => "stderr",
                (false, false) => unreachable!(),
            };
            return Err(WorkerClientError::ToolFailed(format!(
                "the design worker exceeded its bounded {stream} protocol output"
            )));
        }

        if let Some(error) = stdout.read_error.as_deref() {
            return Err(WorkerClientError::ToolFailed(format!(
                "the design worker stdout could not be read: {error}"
            )));
        }
        if let Some(error) = stderr.read_error.as_deref() {
            return Err(WorkerClientError::ToolFailed(format!(
                "the design worker stderr could not be read: {error}"
            )));
        }

        if let Err(error) = writer.map_err(|_| {
            WorkerClientError::ToolFailed(
                "the design worker stdin writer stopped unexpectedly".to_owned(),
            )
        })? {
            return Err(WorkerClientError::ToolFailed(format!(
                "the design worker request could not be written completely: {error}"
            )));
        }

        let stdout = String::from_utf8_lossy(&stdout.bytes);
        let stderr = String::from_utf8_lossy(&stderr.bytes);

        let WaitOutcome::Exited(status) = outcome else {
            return Err(WorkerClientError::ToolFailed(
                "the design worker stopped without an exit status".to_owned(),
            ));
        };

        if stdout.trim().is_empty() {
            let tail = stderr.lines().last().unwrap_or("no output at all");
            return Err(WorkerClientError::ToolFailed(format!(
                "the design worker said nothing: {tail}"
            )));
        }

        // The answer is the worker's last word. Anything it printed earlier is
        // chatter, not protocol — progress notes, a library banner — and the
        // document to judge is the last complete JSON value in the stream.
        let answer = last_json_document(&stdout).ok_or_else(|| {
            WorkerClientError::ToolFailed(format!(
                "the design worker's answer was not JSON: {}",
                summarise(&stdout)
            ))
        })?;

        // A failure is still JSON, so it is parsed before the exit code is
        // consulted — the structured reason is better than the number. The
        // current worker includes the negotiated protocol fields on failures,
        // so checking only the legacy unversioned shape would discard the
        // useful diagnostic and reduce every handler error to "exit status 1".
        if let Ok(response) = serde_json::from_value::<IpcResponse>(answer.clone()) {
            if !response.ok {
                let error = response.error.ok_or_else(|| {
                    WorkerClientError::ToolFailed(
                        "worker failure envelope omitted its structured error".to_owned(),
                    )
                })?;
                return Err(map_error(&error.kind, error.detail, error.code));
            }
        } else if let Ok(failure) = serde_json::from_value::<WorkerFailure>(answer.clone()) {
            return Err(map_error(
                &failure.error.kind,
                failure.error.detail,
                failure.error.code,
            ));
        }
        // A success-shaped payload cannot override a failing process exit. This
        // keeps the process boundary fail-closed when a wrapper prints stale or
        // partial JSON before terminating abnormally.
        if !status.success() {
            return Err(WorkerClientError::ToolFailed(format!(
                "the design worker exited with {status}"
            )));
        }

        Ok(answer)
    }

    /// Send a signal to the complete POSIX process group for one request.
    ///
    /// `kill(1)` is used rather than `libc::kill` so this crate can retain
    /// `forbid(unsafe_code)`. The Linux runtime image installs `procps`, which
    /// provides the utility. A failed group signal is harmless when the group
    /// has already disappeared; the direct-child fallback in
    /// [`Self::terminate_tree`] still guarantees the interpreter is reaped.
    fn kill_process_group(process_group: u32, signal: &str) {
        #[cfg(unix)]
        {
            let group = format!("-{process_group}");
            let _ = Command::new("/usr/bin/kill")
                .args([signal, "--", &group])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }
        #[cfg(not(unix))]
        {
            let _ = (process_group, signal);
        }
    }

    /// Terminate a complete worker process tree and reap the interpreter.
    ///
    /// SIGTERM gives Python and native tools a short cooperative cleanup
    /// window. SIGKILL is the bounded backstop. This prevents BLAST/MAFFT or
    /// other grandchildren surviving a cancelled/timed-out API request.
    fn terminate_tree(child: &mut Child) -> Option<ExitStatus> {
        let process_group = child.id();
        Self::kill_process_group(process_group, "-TERM");

        let deadline = Instant::now() + Duration::from_millis(500);
        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    // A grandchild can outlive the Python parent while keeping
                    // the same process group. Kill the rest before returning.
                    Self::kill_process_group(process_group, "-KILL");
                    return Some(status);
                }
                Ok(None) if Instant::now() < deadline => thread::sleep(POLL_INTERVAL),
                Ok(None) | Err(_) => break,
            }
        }

        Self::kill_process_group(process_group, "-KILL");
        // If the group utility was unavailable or failed, never leave the
        // direct interpreter behind. Child::kill is the final local backstop.
        let _ = child.kill();
        child.wait().ok()
    }

    /// Kill and wait. Returns the exit status when the kill worked.
    fn reap(child: &mut Child) -> Option<ExitStatus> {
        Self::terminate_tree(child)
    }
}

/// The last complete JSON object written to a stream.
///
/// The common case is the whole stream being one document. Otherwise locate
/// the balanced object suffix in one reverse pass and parse exactly once. The
/// previous implementation reparsed the entire remaining suffix at every `{`,
/// which made brace-heavy worker chatter quadratic in the retained stdout size.
fn last_json_document(stdout: &str) -> Option<serde_json::Value> {
    if let Ok(value) = serde_json::from_str(stdout) {
        return Some(value);
    }
    let trimmed = stdout.trim_end();
    let bytes = trimmed.as_bytes();
    if bytes.last().copied() != Some(b'}') {
        return None;
    }

    let mut depth = 0usize;
    let mut in_string = false;
    for index in (0..bytes.len()).rev() {
        let byte = bytes[index];
        if byte == b'"' {
            let mut slashes = 0usize;
            let mut cursor = index;
            while cursor > 0 && bytes[cursor - 1] == b'\\' {
                slashes += 1;
                cursor -= 1;
            }
            if slashes.is_multiple_of(2) {
                in_string = !in_string;
            }
            continue;
        }
        if in_string {
            continue;
        }
        match byte {
            b'}' => depth = depth.checked_add(1)?,
            b'{' => {
                depth = depth.checked_sub(1)?;
                if depth == 0 {
                    return serde_json::from_str(&trimmed[index..]).ok();
                }
            }
            _ => {}
        }
    }
    None
}

/// A short quotation of output that was supposed to be JSON but wasn't.
///
/// For the log rather than the wire: enough to recognise what answered,
/// never enough to be mistaken for the answer itself.
fn summarise(stdout: &str) -> String {
    let flat = stdout.split_whitespace().collect::<Vec<_>>().join(" ");
    let mut cut = flat.chars().take(80);
    let head: String = (&mut cut).collect();
    if cut.next().is_some() {
        format!("{head}…")
    } else if head.is_empty() {
        "nothing readable".to_owned()
    } else {
        head
    }
}

/// Translate the worker's vocabulary into this crate's.
///
/// Kept as a function so the mapping is one readable table rather than being
/// spread through the call site.
fn map_error(kind: &str, detail: String, code: Option<String>) -> WorkerClientError {
    let detail = match code {
        Some(code) if !code.is_empty() => format!("{detail} (code: {code})"),
        _ => detail,
    };
    match kind {
        // Both of these are things the person asking can fix, so they are
        // bad requests rather than failures.
        "invalidRequest" | "backgroundTooLarge" => WorkerClientError::InvalidRequest(detail),
        "notImplemented" | "toolMissing" => WorkerClientError::NotImplemented(detail),
        // A tool that is not installed is not a failure of the run; it is a
        // fact about this build, and the message says what to install.
        _ => WorkerClientError::ToolFailed(detail),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn json(value: serde_json::Value) -> serde_json::Value {
        value
    }

    #[test]
    fn a_worker_child_inherits_only_what_the_allowlist_names() {
        let parent = [
            ("PATH".to_owned(), "/usr/bin".to_owned()),
            (
                "PCR_DATABASE_URL".to_owned(),
                "postgres://pcr:not-for-the-worker@db/pcrstudio".to_owned(),
            ),
            ("PYTHONPATH".to_owned(), "/somewhere/hostile".to_owned()),
            (
                "PCRSTUDIO_SCIENTIFIC_POLICY".to_owned(),
                "strict".to_owned(),
            ),
            (
                "PCRSTUDIO_MFEPRIMER".to_owned(),
                "/opt/pcrstudio/tools/mfeprimer".to_owned(),
            ),
            (
                "PCRSTUDIO_MFEPRIMER_DATABASES_SCOPE".to_owned(),
                "approved-reference".to_owned(),
            ),
            (
                "PCRSTUDIO_MFEPRIMER_DATABASES_MANIFEST".to_owned(),
                "/opt/pcrstudio/tools/db/manifest.json".to_owned(),
            ),
            (
                "PCRSTUDIO_PYDNA_PYTHON".to_owned(),
                "/opt/pcrstudio/tools/science-venv/bin/python".to_owned(),
            ),
            ("AWS_SESSION_TOKEN".to_owned(), "waffles".to_owned()),
        ];

        let mut child = child_environment(parent.into_iter());
        child.sort();
        let names: Vec<_> = child.iter().map(|(key, _)| key.as_str()).collect();
        assert_eq!(
            names,
            [
                "PATH",
                "PCRSTUDIO_MFEPRIMER",
                "PCRSTUDIO_MFEPRIMER_DATABASES_MANIFEST",
                "PCRSTUDIO_MFEPRIMER_DATABASES_SCOPE",
                "PCRSTUDIO_PYDNA_PYTHON",
                "PCRSTUDIO_SCIENTIFIC_POLICY",
            ]
        );
    }

    #[test]
    fn a_missing_interpreter_says_what_to_set() {
        let worker = Worker::new("definitely-not-a-python-on-this-machine");
        let error = worker
            .call("run", &json(serde_json::json!({})))
            .expect_err("there is no such interpreter");
        assert!(matches!(error, WorkerClientError::ToolFailed(_)));
        assert!(error.to_string().contains("PCR_PYTHON"));
    }

    #[test]
    fn the_workers_vocabulary_maps_onto_ours() {
        assert!(matches!(
            map_error("invalidRequest", "x".into(), None),
            WorkerClientError::InvalidRequest(_)
        ));
        // A background too large is the caller's problem, not a crash.
        assert!(matches!(
            map_error("backgroundTooLarge", "x".into(), None),
            WorkerClientError::InvalidRequest(_)
        ));
        // Anything we have not seen before is a failure, not a silent success.
        assert!(matches!(
            map_error("somethingNew", "x".into(), None),
            WorkerClientError::ToolFailed(_)
        ));
    }

    #[test]
    fn final_json_scan_handles_chatter_and_braces_inside_strings() {
        let payload = r#"banner { not json }\nmore chatter\n{"protocolVersion":1,"detail":"a { brace } and \"quote\""}"#;
        let answer = last_json_document(payload).expect("final object is recovered");
        assert_eq!(answer["protocolVersion"], 1);
        assert_eq!(answer["detail"], "a { brace } and \"quote\"");
    }

    #[test]
    fn final_json_scan_is_not_confused_by_many_chatter_braces() {
        let mut payload = "{".repeat(50_000);
        payload.push_str(r#"{"protocolVersion":1}"#);
        assert_eq!(last_json_document(&payload).unwrap()["protocolVersion"], 1);
    }

    #[test]
    fn bounded_pipe_accepts_the_exact_limit_and_flags_only_real_overflow() {
        use std::io::Cursor;

        let exact_flag = Arc::new(AtomicBool::new(false));
        let exact = drain(
            Some(Cursor::new(vec![b'x'; 8_192])),
            8_192,
            Arc::clone(&exact_flag),
        )
        .join()
        .expect("bounded reader thread completes");
        assert_eq!(exact.bytes.len(), 8_192);
        assert!(!exact.truncated);
        assert!(exact.read_error.is_none());
        assert!(!exact_flag.load(Ordering::Acquire));

        let overflow_flag = Arc::new(AtomicBool::new(false));
        let overflow = drain(
            Some(Cursor::new(vec![b'y'; 8_193])),
            8_192,
            Arc::clone(&overflow_flag),
        )
        .join()
        .expect("bounded reader thread completes");
        assert_eq!(overflow.bytes.len(), 8_192);
        assert!(overflow.truncated);
        assert!(overflow.read_error.is_none());
        assert!(overflow_flag.load(Ordering::Acquire));
    }

    mod posix_only {
        //! Interpreter-backed tests need a script interpreter. These run where
        //! Linux qualification requires `python3` and exercises interpreter-backed
        //! worker cancellation, output and isolation behavior end to end.

        use super::*;

        const PYTHON: &str = "python3";

        fn script(worker: &Worker, source: &str) -> Result<serde_json::Value> {
            worker.run(["-c", source], b"{}".as_slice())
        }

        #[test]
        fn a_worker_that_never_answers_is_killed_at_the_deadline() {
            // Sleep far past a two-second budget, print nothing.
            let worker = Worker::with_timeout(PYTHON, Duration::from_secs(2));
            let started = Instant::now();
            let error = script(&worker, "import time; time.sleep(60)")
                .expect_err("a sleeping worker must not come back");
            assert!(
                matches!(error, WorkerClientError::ToolFailed(ref m) if m.contains("was stopped")),
                "got: {error}"
            );
            // Generous ceiling: the machine may be slow to schedule, but it
            // must not be sixty seconds slow.
            assert!(started.elapsed() < Duration::from_secs(30));
        }

        #[cfg(target_os = "linux")]
        #[test]
        fn timeout_terminates_native_grandchildren_in_the_worker_process_group() {
            let pid_file = std::env::temp_dir().join(format!(
                "pcrstudio-worker-tree-{}-{}.pid",
                std::process::id(),
                next_request_id()
            ));
            let pid_file_literal = serde_json::to_string(&pid_file.to_string_lossy())
                .expect("temporary pid path is JSON encodable");
            let source = format!(
                "import pathlib, subprocess, time; p = subprocess.Popen(['sleep', '60']); pathlib.Path({pid_file_literal}).write_text(str(p.pid)); time.sleep(60)"
            );
            let worker = Worker::with_timeout(PYTHON, Duration::from_secs(2));

            let error = script(&worker, &source)
                .expect_err("the worker and its native grandchild must time out");
            assert!(
                matches!(error, WorkerClientError::ToolFailed(ref m) if m.contains("was stopped")),
                "got: {error}"
            );

            let grandchild_pid: u32 = std::fs::read_to_string(&pid_file)
                .expect("Python wrote the native grandchild pid")
                .trim()
                .parse()
                .expect("grandchild pid is numeric");
            let _ = std::fs::remove_file(&pid_file);

            // A killed process may remain momentarily as a zombie until PID 1
            // reaps it. Zombie is terminal and therefore acceptable; any other
            // /proc state means the scientific grandchild survived cancellation.
            let stat_path = PathBuf::from(format!("/proc/{grandchild_pid}/stat"));
            if let Ok(stat) = std::fs::read_to_string(&stat_path) {
                let state = stat.split_whitespace().nth(2);
                assert_eq!(
                    state,
                    Some("Z"),
                    "native grandchild {grandchild_pid} survived worker timeout in state {state:?}"
                );
            }
        }

        #[test]
        fn a_flooded_stderr_is_stopped_at_the_output_boundary() {
            // More than the diagnostic budget, followed by a long sleep. The
            // worker must be killed because it crossed the output boundary,
            // not left alive until the ordinary request timeout expires.
            let source =
                "import sys, time; sys.stderr.write('x' * 500_000); sys.stderr.flush(); time.sleep(60)";
            let worker = Worker::with_timeout(PYTHON, Duration::from_secs(15));
            let started = Instant::now();
            let error = script(&worker, source).expect_err("stderr overflow must stop the worker");
            assert!(
                matches!(error, WorkerClientError::ToolFailed(ref m) if m.contains("bounded stderr protocol output")),
                "got: {error}"
            );
            assert!(started.elapsed() < Duration::from_secs(10));
        }

        #[test]
        fn a_large_answer_and_a_large_request_move_at_once() {
            // The interpreter writes far more than a pipe buffer *before*
            // reading its stdin, then answers with what it got. Either side
            // blocking while the other waits is the deadlock this file exists
            // to make impossible.
            let source = "import sys, json; \
                          sys.stdout.write('y' * 400_000); sys.stdout.flush(); \
                          request = sys.stdin.buffer.read(); \
                          sys.stdout.write(json.dumps({'got': len(request)}))";
            let worker = Worker::with_timeout(PYTHON, Duration::from_secs(15));
            let payload = "n".repeat(300_000).into_bytes();
            let answer = worker.run(["-c", source], &payload).expect("round trip");
            assert_eq!(answer["got"], 300_000);
        }
    }
}
