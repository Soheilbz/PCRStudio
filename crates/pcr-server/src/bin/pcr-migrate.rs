//! One-shot database migration command for production Linux deployments.

use pcr_accounts::Accounts;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::registry()
        .with(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "pcr_migrate=info,pcr_storage=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let url = database_url()?;
    let accounts = Accounts::connect(&url).await?;
    tracing::info!("database migrations and relational invariant validation complete");
    // Closing is explicit so the one-shot container leaves no idle connection
    // while Compose unblocks API/runner startup.
    accounts.pool().close().await;
    tracing::info!("PCRStudio database migrations complete");
    Ok(())
}

fn database_url() -> Result<String, Box<dyn std::error::Error>> {
    pcr_storage::database_url_from_environment()?.ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "PCR_DATABASE_URL_FILE (preferred) or PCR_DATABASE_URL is required for pcr-migrate",
        )
        .into()
    })
}
