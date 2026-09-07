//! Dedicated durable-job runner for production Linux deployments.

use std::time::Duration;

use pcr_accounts::Accounts;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

const DEFAULT_POLL_MS: u64 = 1000;
const MIN_POLL_MS: u64 = 100;
const MAX_POLL_MS: u64 = 60_000;
const HEARTBEAT_INTERVAL: Duration = Duration::from_secs(5);

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| "pcr_runner=info,pcr_application=info".into());
    if std::env::var("PCR_LOG_FORMAT").is_ok_and(|value| value.eq_ignore_ascii_case("json")) {
        tracing_subscriber::registry()
            .with(filter)
            .with(
                tracing_subscriber::fmt::layer()
                    .json()
                    .flatten_event(true)
                    .with_current_span(true)
                    .with_span_list(false),
            )
            .init();
    } else {
        tracing_subscriber::registry()
            .with(filter)
            .with(tracing_subscriber::fmt::layer())
            .init();
    }

    match std::env::args().nth(1).as_deref() {
        None => {}
        Some("healthcheck") => return run_healthcheck().await,
        Some(argument) => {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                format!("unknown pcr-runner command {argument:?}"),
            )
            .into());
        }
    }

    validate_execution_environment()?;
    let database_url = database_url()?;
    let poll = poll_interval()?;
    let build_identity = build_identity()?;
    let freeze = approved_scientific_freeze()?;
    let accounts = Accounts::connect_without_migrations(&database_url).await?;
    let worker = pcr_application::scientific::worker_from_env();
    let registry = pcr_core::default_registry_with_worker(worker.clone())?;

    // A runner must prove the exact worker and strict toolchain before it is
    // allowed to advertise capacity in PostgreSQL. Otherwise API readiness
    // could accept a process that is alive but scientifically unusable.
    tokio::task::spawn_blocking(move || pcr_application::scientific::preflight_runner(&worker))
        .await
        .map_err(|error| {
            std::io::Error::other(format!("runner scientific preflight panicked: {error}"))
        })?
        .map_err(|error| {
            std::io::Error::other(format!("runner scientific preflight failed: {error}"))
        })?;

    let runner_id = runner_instance_id()?;
    let foundation = pcr_storage::FoundationStorage::new(accounts.pool());
    let worker_ceiling = pcr_application::Gate::shared().permits();
    let worker_capacity = i32::try_from(worker_ceiling).map_err(|_| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "runner worker ceiling does not fit i32",
        )
    })?;
    let state = pcr_application::jobs::JobExecutionState::from_accounts(&accounts, registry);

    // Registration is intentionally performed by the executor loop itself.
    // API readiness therefore means a runner has completed scientific
    // preflight *and* successfully entered the PostgreSQL polling path.
    heartbeat_runner(
        &foundation,
        &runner_id,
        &build_identity,
        worker_capacity,
        Some(&freeze),
    )
    .await?;

    tracing::info!(
        runner_id = %runner_id,
        build_identity = %build_identity,
        poll_milliseconds = poll.as_millis() as u64,
        worker_ceiling,
        "PCRStudio scientific runner ready"
    );

    let shutdown = shutdown_signal();
    tokio::pin!(shutdown);
    let mut heartbeat = tokio::time::interval(HEARTBEAT_INTERVAL);
    heartbeat.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    let mut polling = tokio::time::interval(poll);
    polling.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    loop {
        tokio::select! {
            () = &mut shutdown => break,
            _ = heartbeat.tick() => {
                // Heartbeat and queue polling deliberately share this one task.
                // If an executor iteration wedges, this branch cannot run and
                // API readiness expires rather than advertising a zombie
                // runner. Keeping a separate five-second tick also prevents a
                // deliberately slow queue poll interval from causing false
                // readiness flaps.
                if let Err(error) = heartbeat_runner(
                    &foundation,
                    &runner_id,
                    &build_identity,
                    worker_capacity,
                    Some(&freeze),
                ).await {
                    tracing::error!(%error, runner_id=%runner_id, "runner heartbeat failed");
                }
            }
            _ = polling.tick() => {
                pcr_application::jobs::recover_and_dispatch_once(&state).await;
            }
        }
    }

    tracing::info!("runner shutdown requested; cancelling local scientific workers");
    pcr_application::jobs::signal_all_local_cancellations();

    // Drain cooperative worker cancellation inside Docker's 45-second grace
    // period. A stubborn native process cannot hold shutdown indefinitely; its
    // database lease expires and another runner may safely recover the job.
    let remaining = pcr_application::jobs::drain_local_jobs(Duration::from_secs(30)).await;
    if remaining != 0 {
        tracing::warn!(
            remaining,
            "runner shutdown deadline reached with local jobs still registered"
        );
    }
    if let Err(error) = foundation.unregister_runner(&runner_id).await {
        tracing::warn!(%error, runner_id=%runner_id, "could not remove runner heartbeat on shutdown");
    }
    Ok(())
}

async fn heartbeat_runner(
    storage: &pcr_storage::FoundationStorage,
    runner_id: &str,
    build_identity: &str,
    worker_capacity: i32,
    freeze: Option<&str>,
) -> Result<(), pcr_storage::StorageError> {
    storage
        .heartbeat_runner(
            runner_id,
            env!("CARGO_PKG_VERSION"),
            build_identity,
            worker_capacity,
            freeze,
        )
        .await
}

async fn run_healthcheck() -> Result<(), Box<dyn std::error::Error>> {
    let database_url = database_url()?;
    let accounts = Accounts::connect_without_migrations(&database_url).await?;
    let storage = pcr_storage::FoundationStorage::new(accounts.pool());
    let runner_id = runner_instance_id()?;
    let build_identity = build_identity()?;
    let freeze = approved_scientific_freeze()?;
    let fresh = storage
        .runner_is_fresh(
            &runner_id,
            pcr_storage::RUNNER_HEARTBEAT_FRESH_SECONDS,
            env!("CARGO_PKG_VERSION"),
            &build_identity,
            Some(&freeze),
        )
        .await?;
    if !fresh {
        return Err(std::io::Error::other(format!(
            "runner {runner_id:?} has no fresh matching PostgreSQL heartbeat"
        ))
        .into());
    }
    Ok(())
}

fn runner_instance_id() -> Result<String, Box<dyn std::error::Error>> {
    let raw = std::env::var("PCR_RUNNER_INSTANCE_ID")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .or_else(|| std::env::var("HOSTNAME").ok().filter(|value| !value.trim().is_empty()))
        .or_else(|| {
            std::fs::read_to_string("/etc/hostname")
                .ok()
                .map(|value| value.trim().to_owned())
                .filter(|value| !value.is_empty())
        })
        .ok_or_else(|| {
            std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "runner needs PCR_RUNNER_INSTANCE_ID, HOSTNAME, or /etc/hostname for stable health identity",
            )
        })?;
    let raw = raw.trim();
    if raw.len() > 128
        || !raw
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b':'))
    {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "runner instance identity must be <=128 ASCII hostname/id characters",
        )
        .into());
    }
    Ok(format!("linux:{raw}"))
}

fn build_identity() -> Result<String, Box<dyn std::error::Error>> {
    let value = std::env::var("PCRSTUDIO_BUILD_ID")
        .map_err(|_| {
            std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "PCRSTUDIO_BUILD_ID is required for the dedicated production runner",
            )
        })?
        .trim()
        .to_owned();
    let value = pcr_security::canonical_sha256(&value).ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "PCRSTUDIO_BUILD_ID must be a lowercase SHA-256 hex digest",
        )
    })?;
    Ok(value.to_owned())
}

fn approved_scientific_freeze() -> Result<String, Box<dyn std::error::Error>> {
    let value = std::env::var("PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256")
        .map_err(|_| std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256 is required for the dedicated production runner",
        ))?;
    let value = pcr_security::canonical_sha256(&value).ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256 must be a lowercase SHA-256 hex digest",
        )
    })?;
    Ok(value.to_owned())
}

fn validate_execution_environment() -> Result<(), Box<dyn std::error::Error>> {
    validate_bounded_integer("PCR_MAX_CONCURRENT_WORKERS", 1, 16)?;
    validate_bounded_integer("PCR_MAX_QUEUED_WORKERS", 0, 1024)?;
    validate_bounded_integer("PCR_WORKER_TIMEOUT_SECONDS", 1, 299)?;
    Ok(())
}

fn validate_bounded_integer(
    name: &'static str,
    minimum: u64,
    maximum: u64,
) -> Result<(), Box<dyn std::error::Error>> {
    let Some(raw) = std::env::var(name).ok() else {
        return Ok(());
    };
    let value: u64 = raw.trim().parse().map_err(|_| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("{name} must be an integer from {minimum} to {maximum}; got {raw:?}"),
        )
    })?;
    if !(minimum..=maximum).contains(&value) {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("{name} must be an integer from {minimum} to {maximum}; got {value}"),
        )
        .into());
    }
    Ok(())
}

fn database_url() -> Result<String, Box<dyn std::error::Error>> {
    pcr_storage::database_url_from_environment()?.ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "PCR_DATABASE_URL_FILE (preferred) or PCR_DATABASE_URL is required for pcr-runner",
        )
        .into()
    })
}

fn poll_interval() -> Result<Duration, Box<dyn std::error::Error>> {
    let raw = std::env::var("PCR_RUNNER_POLL_MILLISECONDS")
        .unwrap_or_else(|_| DEFAULT_POLL_MS.to_string());
    let value: u64 = raw.trim().parse().map_err(|_| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("PCR_RUNNER_POLL_MILLISECONDS must be an integer, got {raw:?}"),
        )
    })?;
    if !(MIN_POLL_MS..=MAX_POLL_MS).contains(&value) {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!(
                "PCR_RUNNER_POLL_MILLISECONDS must be {MIN_POLL_MS}..={MAX_POLL_MS}, got {value}"
            ),
        )
        .into());
    }
    Ok(Duration::from_millis(value))
}

async fn shutdown_signal() {
    let ctrl_c = async {
        if let Err(error) = tokio::signal::ctrl_c().await {
            tracing::error!(%error, "could not install Ctrl-C handler");
            std::future::pending::<()>().await;
        }
    };

    #[cfg(unix)]
    let terminate = async {
        match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            Ok(mut stream) => {
                stream.recv().await;
            }
            Err(error) => {
                tracing::error!(%error, "could not install SIGTERM handler");
                std::future::pending::<()>().await;
            }
        }
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        () = ctrl_c => tracing::info!("received Ctrl-C"),
        () = terminate => tracing::info!("received SIGTERM"),
    }
}
