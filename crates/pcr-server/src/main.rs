use std::net::SocketAddr;

use pcr_accounts::Accounts;
use pcr_server::{app, Config};
use tokio::signal;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| "pcr_server=info,tower_http=info".into());
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

    let config = Config::from_env()?;

    let accounts = if config.database_migration_mode.runs_at_startup() {
        Accounts::connect(&config.database_url).await?
    } else {
        Accounts::connect_without_migrations(&config.database_url).await?
    };
    tracing::info!(
        migrations = if config.database_migration_mode.runs_at_startup() {
            "startup"
        } else {
            "external"
        },
        "account store ready"
    );

    // One loop for everything that has to happen on a clock. Hourly is far
    // more often than either job needs, and cheap enough that tuning it would
    // be the more expensive decision.
    tokio::spawn(housekeeping(accounts.clone()));

    /*
     * Warm the reaction catalogue while nothing is waiting on it.
     *
     * Building it means asking every engine, and every engine answers by
     * starting the worker — measured at 7.5 seconds cold and 70 milliseconds
     * warm. Left lazy, that whole cost lands on whoever opens the settings page
     * first after a deploy.
     *
     * Spawned rather than awaited, so a slow worker delays a dropdown and not
     * the server coming up.
     */
    let registry = pcr_application::scientific::registry_from_env()?;
    let embedded_job_loop = if config.job_execution_mode.is_embedded() {
        tracing::warn!(
            "durable scientific jobs are executing inside the API process; use PCR_JOB_EXECUTION_MODE=external with pcr-runner in production"
        );
        Some(tokio::spawn(pcr_application::jobs::job_recovery_loop(
            accounts.clone(),
            registry.clone(),
            std::time::Duration::from_secs(5),
        )))
    } else {
        tracing::info!("durable scientific jobs delegated to external pcr-runner");
        None
    };
    let warm_registry = registry.clone();
    tokio::spawn(async move {
        let started = std::time::Instant::now();
        let gate = pcr_server::gate::Gate::shared();
        match gate
            .run(move || Ok(pcr_server::routes::catalogue(&warm_registry)))
            .await
        {
            Ok(catalogue) => {
                let count = catalogue
                    .get("polymerases")
                    .and_then(|value| value.as_array())
                    .map_or(0, Vec::len);
                tracing::info!(
                    count,
                    took_ms = started.elapsed().as_millis(),
                    "reaction catalogue ready"
                );
            }
            Err(error) => {
                tracing::warn!(%error, "reaction catalogue warm-up did not complete");
            }
        }
    });

    let router = app(&config, accounts)?;

    let listener = tokio::net::TcpListener::bind(&config.bind).await?;
    tracing::info!(
        address = %listener.local_addr()?,
        worker_ceiling = pcr_server::gate::Gate::shared().permits(),
        trusted_proxies = std::env::var("PCR_TRUSTED_PROXIES").is_ok_and(|v| !v.is_empty()),
        "PCRStudio API listening"
    );

    // `ConnectInfo` is what lets the rate limiter fall back to the peer address
    // when no forwarded header is present.
    let serve_result = axum::serve(
        listener,
        router.into_make_service_with_connect_info::<SocketAddr>(),
    )
    .with_graceful_shutdown(shutdown_signal())
    .await;

    if let Some(job_loop) = embedded_job_loop {
        tracing::info!("API shutdown cancelling embedded scientific workers");
        pcr_application::jobs::signal_all_local_cancellations();
        let remaining =
            pcr_application::jobs::drain_local_jobs(std::time::Duration::from_secs(30)).await;
        if remaining != 0 {
            tracing::warn!(
                remaining,
                "embedded scientific worker drain deadline reached"
            );
        }
        job_loop.abort();
        let _ = job_loop.await;
    }

    serve_result?;
    Ok(())
}

/// The jobs that run on a clock rather than on a request.
///
/// Both are about not keeping data longer than it is wanted. Expired sessions
/// are already refused, so purging them only stops a table growing without
/// bound. Deleted projects are the sharper one: "delete" has to eventually mean
/// deleted, and until this runs a deletion is only a hidden row.
///
/// A failure is logged and the loop continues. The alternative — ending the
/// task — would leave a server that looks healthy and quietly stops honouring
/// deletions, which is the worst of the available outcomes.
async fn housekeeping(accounts: Accounts) {
    let projects = pcr_projects::Projects::new(accounts.pool());
    let foundation = pcr_storage::FoundationStorage::new(accounts.pool());
    let mut ticker = tokio::time::interval(std::time::Duration::from_secs(3600));

    loop {
        ticker.tick().await;

        match accounts.purge_expired_sessions().await {
            Ok(0) => {}
            Ok(count) => tracing::info!(count, "purged expired sessions"),
            Err(error) => tracing::warn!(%error, "could not purge expired sessions"),
        }

        match accounts.purge_rate_limit_buckets().await {
            Ok(0) => {}
            Ok(count) => tracing::info!(count, "purged idle rate-limit buckets"),
            Err(error) => tracing::warn!(%error, "could not purge idle rate-limit buckets"),
        }

        match projects.purge_deleted().await {
            Ok(0) => {}
            Ok(count) => tracing::info!(count, "purged projects past the undo window"),
            Err(error) => tracing::warn!(%error, "could not purge deleted projects"),
        }

        match foundation.purge_terminal_run_jobs().await {
            Ok(0) => {}
            Ok(count) => tracing::info!(count, "purged expired durable job envelopes"),
            Err(error) => tracing::warn!(%error, "could not purge expired durable jobs"),
        }

        match foundation.purge_unreferenced_sequence_assets().await {
            Ok(0) => {}
            Ok(count) => tracing::info!(count, "purged unreferenced sequence assets"),
            Err(error) => tracing::warn!(%error, "could not purge unreferenced sequence assets"),
        }

        match foundation.purge_stale_runners().await {
            Ok(0) => {}
            Ok(count) => tracing::info!(count, "purged stale scientific runner registrations"),
            Err(error) => tracing::warn!(%error, "could not purge stale runner registrations"),
        }
    }
}

/// Stop on Ctrl-C, and on the SIGTERM a container runtime sends, so in-flight
/// requests finish instead of being cut off.
async fn shutdown_signal() {
    let ctrl_c = async {
        match signal::ctrl_c().await {
            Ok(()) => true,
            Err(error) => {
                tracing::error!(%error, "could not install the Ctrl-C handler");
                std::future::pending::<()>().await;
                false
            }
        }
    };

    #[cfg(unix)]
    let terminate = async {
        match signal::unix::signal(signal::unix::SignalKind::terminate()) {
            Ok(mut stream) => {
                stream.recv().await;
                true
            }
            Err(error) => {
                tracing::error!(%error, "could not install the SIGTERM handler");
                std::future::pending::<()>().await;
                false
            }
        }
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<bool>();

    tokio::select! {
        is_ctrl_c = ctrl_c => if is_ctrl_c { tracing::info!("received Ctrl-C, shutting down"); },
        is_terminate = terminate => if is_terminate { tracing::info!("received SIGTERM, shutting down"); },
    }
}
