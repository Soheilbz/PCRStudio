//! The HTTP surface of PCRStudio.
//!
//! This crate is transport and nothing else. It publishes the design registry
//! from `pcr-core` and the account store from `pcr-accounts`; all the work
//! happens in those.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod auth;
pub mod bench;
mod diagnostics;
pub mod error;
pub mod gate;
#[path = "http_routes.generated.rs"]
mod http_routes;
pub mod projects;
pub mod rate_limit;
pub mod readiness;
pub mod routes;
pub mod sequences;

use std::time::Duration;

use crate::rate_limit::{RateLimiter, DESIGNS_PER_WINDOW, DESIGN_WINDOW, SEQUENCES_PER_WINDOW};
use axum::extract::DefaultBodyLimit;
use axum::http::{header, HeaderName, HeaderValue, Method};
use axum::routing::{get, post};
use axum::Router;
use pcr_accounts::Accounts;
use pcr_core::Registry;
use tower_http::compression::CompressionLayer;
use tower_http::cors::CorsLayer;
use tower_http::limit::RequestBodyLimitLayer;
use tower_http::request_id::{MakeRequestUuid, PropagateRequestIdLayer, SetRequestIdLayer};
use tower_http::set_header::SetResponseHeaderLayer;
use tower_http::timeout::TimeoutLayer;
use tower_http::trace::TraceLayer;

/// The largest request body this will read, before any handler sees it.
///
/// Every engine already refuses a template longer than it can work with, but
/// those checks run *after* the body has been read into memory. This is the one
/// that runs before: without it a single request claiming to be a gigabyte is a
/// gigabyte of this process's memory, and it does not need an account to send
/// one.
///
/// Sized against the largest thing a caller legitimately sends — a tiling
/// scheme over a ten-megabase sequence — with room for it to arrive as JSON.
const MAX_BODY_BYTES: usize = pcr_contracts::MAX_HTTP_BODY_BYTES;

/// How long any one request may take before it is abandoned.
///
/// A design runs a Python worker, and a worker that hangs would otherwise hold
/// a connection open forever. Long enough for the slowest legitimate search —
/// a loop set over a long template runs to several seconds, a specificity scan
/// against a background genome to rather more.
const REQUEST_TIMEOUT: Duration = Duration::from_secs(300);

/// The header a request id travels in, so a log line and a bug report can be
/// joined up afterwards.
const REQUEST_ID_HEADER: HeaderName = HeaderName::from_static("x-request-id");

/// Headers on every API response.
///
/// The JSON API is not a document and nothing should treat it as one. `nosniff`
/// stops a browser deciding that a body we labelled JSON is really HTML — which
/// matters here more than in most APIs, because much of what these endpoints
/// return is sequence somebody else pasted in.
fn api_headers() -> [(HeaderName, HeaderValue); 3] {
    [
        (
            header::X_CONTENT_TYPE_OPTIONS,
            HeaderValue::from_static("nosniff"),
        ),
        (
            header::REFERRER_POLICY,
            HeaderValue::from_static("no-referrer"),
        ),
        (
            // An API response has no business being framed, embedded, or
            // opened as a document.
            HeaderName::from_static("cross-origin-resource-policy"),
            HeaderValue::from_static("same-origin"),
        ),
    ]
}

/// What the module handlers need, cloned per request.
///
/// The registry holds `Arc`s, so cloning it is a refcount bump rather than a
/// copy of the engines.
#[derive(Clone)]
pub struct ModuleState {
    /// Every engine and assay this build ships.
    pub registry: Registry,
    /// The ceiling on concurrent worker work, shared by every endpoint that
    /// reaches a Python subprocess.
    pub gate: std::sync::Arc<gate::Gate>,
}

/// Who owns database schema migration at service startup.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DatabaseMigrationMode {
    /// Development compatibility: this API process applies migrations.
    Startup,
    /// Production: a dedicated one-shot migration process must finish first.
    External,
}

impl DatabaseMigrationMode {
    /// Whether this process owns schema migration.
    #[must_use]
    pub fn runs_at_startup(self) -> bool {
        matches!(self, Self::Startup)
    }
}

/// Where durable scientific jobs are executed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JobExecutionMode {
    /// Local development/test mode: the API process also runs durable jobs.
    Embedded,
    /// Production mode: the API only enqueues; a dedicated `pcr-runner` executes.
    External,
}

impl JobExecutionMode {
    /// Whether this API process may start durable scientific jobs.
    #[must_use]
    pub fn is_embedded(self) -> bool {
        matches!(self, Self::Embedded)
    }
}

/// How the server was configured at startup.
#[derive(Clone)]
pub struct Config {
    /// Address to bind, e.g. `0.0.0.0:8080`.
    pub bind: String,
    /// PostgreSQL connection string for the account store.
    pub database_url: String,
    /// Origins allowed to call this API from a browser.
    ///
    /// Empty means no cross-origin access, which is correct when the frontend
    /// reaches the API server-side and the browser never talks to it directly.
    pub cors_origins: Vec<HeaderValue>,
    /// Durable-job execution topology. Production uses a separate runner.
    pub job_execution_mode: JobExecutionMode,
    /// Database migration topology. Production uses a one-shot migrator.
    pub database_migration_mode: DatabaseMigrationMode,
    /// Optional operator diagnostics bearer, read from direct env only for local
    /// compatibility or from a file-backed production secret.
    pub operator_token: Option<String>,
    /// Contact identity sent with NCBI EFetch requests.
    pub ncbi_email: String,
    /// Optional NCBI API key, preferably file-backed in production.
    pub ncbi_api_key: Option<String>,
}

impl std::fmt::Debug for Config {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Config")
            .field("bind", &self.bind)
            .field("database_url", &"[REDACTED]")
            .field("cors_origins", &self.cors_origins)
            .field("job_execution_mode", &self.job_execution_mode)
            .field("database_migration_mode", &self.database_migration_mode)
            .field(
                "operator_token",
                &self.operator_token.as_ref().map(|_| "[REDACTED]"),
            )
            .field(
                "ncbi_email",
                &if self.ncbi_email.is_empty() {
                    "[NOT SET]"
                } else {
                    "[CONFIGURED]"
                },
            )
            .field(
                "ncbi_api_key",
                &self.ncbi_api_key.as_ref().map(|_| "[REDACTED]"),
            )
            .finish()
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            // A directly-run development server must not become reachable from
            // the LAN by accident. The production image overrides this with
            // 0.0.0.0:8080 because it is isolated on the compose network.
            bind: "127.0.0.1:8080".to_owned(),
            // Match the project-local development compose file. Deployments
            // must provide PCR_DATABASE_URL_FILE (preferred) or PCR_DATABASE_URL explicitly.
            database_url: "postgres://pcr:pcr@localhost:55432/pcrstudio".to_owned(),
            cors_origins: Vec::new(),
            job_execution_mode: JobExecutionMode::Embedded,
            database_migration_mode: DatabaseMigrationMode::Startup,
            operator_token: None,
            ncbi_email: String::new(),
            ncbi_api_key: None,
        }
    }
}

/// Errors raised while reading deployment configuration.
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    /// A non-loopback deployment did not provide its database connection string.
    #[error("PCR_DATABASE_URL_FILE (preferred) or PCR_DATABASE_URL must be set when PCR_BIND is not loopback; refusing to expose the development database credential") ]
    MissingDatabaseUrl,
    /// An origin in the CORS allow-list is not an exact HTTP(S) origin.
    #[error("PCR_CORS_ORIGINS contains an invalid origin {0:?}; use an exact http(s) origin such as https://pcrstudio.example.org") ]
    InvalidCorsOrigin(String),
    /// The worker timeout is outside the API request deadline.
    #[error("PCR_WORKER_TIMEOUT_SECONDS must be an integer from 1 to 299 so the worker stops before the 300-second API request deadline; got {0:?}")]
    InvalidWorkerTimeout(String),
    /// The concurrent worker limit is outside the supported range.
    #[error("PCR_MAX_CONCURRENT_WORKERS must be an integer from 1 to 16; got {0:?}")]
    InvalidWorkerConcurrency(String),
    /// The queued worker limit is outside the supported range.
    #[error("PCR_MAX_QUEUED_WORKERS must be an integer from 0 to 1024; got {0:?}")]
    InvalidWorkerQueue(String),
    /// Durable-job execution mode is not one of the closed supported values.
    #[error("PCR_JOB_EXECUTION_MODE must be `embedded` or `external`; got {0:?}")]
    InvalidJobExecutionMode(String),
    /// Database migration mode is not one of the closed supported values.
    #[error("PCR_DATABASE_MIGRATIONS must be `startup` or `external`; got {0:?}")]
    InvalidDatabaseMigrationMode(String),
    /// A trusted proxy entry is not a valid IP address or CIDR.
    #[error("PCR_TRUSTED_PROXIES contains an invalid IP/CIDR entry {0:?}")]
    InvalidTrustedProxy(String),
    /// A content-addressed production identity is missing in external-runner mode.
    #[error("{0} is required when PCR_JOB_EXECUTION_MODE=external")]
    MissingProductionIdentity(&'static str),
    /// A content-addressed production identity is not a lowercase SHA-256 digest.
    #[error("{0} must be a lowercase 64-character SHA-256 hex digest; got {1:?}")]
    InvalidProductionIdentity(&'static str, String),
    /// An environment variable could not be decoded as Unicode.
    #[error("{0} contains a non-Unicode value that this server cannot interpret")]
    NonUnicodeEnvironment(&'static str),
    /// Direct and file-backed forms of the same deployment secret were both configured.
    #[error("{0} and {1} cannot both be set; use exactly one secret source")]
    ConflictingSecretSources(&'static str, &'static str),
    /// A configured file-backed secret cannot be read by this process.
    #[error("{0} points to an unreadable secret file {1:?}")]
    SecretFileUnreadable(&'static str, String),
    /// Operator diagnostics bearer is present but not a visible-ASCII header token.
    #[error("PCR_OPERATOR_TOKEN must contain 24..=512 visible ASCII characters with no whitespace when configured")]
    InvalidOperatorToken,
    /// NCBI API key is not a visible-ASCII header token or is implausibly large.
    #[error("PCR_NCBI_API_KEY must contain 1..=512 visible ASCII characters with no whitespace when configured")]
    InvalidNcbiApiKey,
}

impl Config {
    /// Read and validate deployment configuration from the environment.
    ///
    /// The development database credential is intentionally available only
    /// while the server remains loopback-only. Binding a process to a public or
    /// container interface without an explicit database secret source is a deployment
    /// error, not a reason to reuse a known development password. CORS entries
    /// are exact origins, not arbitrary header strings.
    pub fn from_env() -> Result<Self, ConfigError> {
        let defaults = Self::default();
        let bind = env_utf8("PCR_BIND")?.unwrap_or(defaults.bind);
        let database_url =
            match pcr_storage::database_url_from_environment().map_err(map_secret_source_error)? {
                Some(value) => value,
                None if bind_is_loopback(&bind) => defaults.database_url,
                None => return Err(ConfigError::MissingDatabaseUrl),
            };
        let cors_origins = env_utf8("PCR_CORS_ORIGINS")?
            .unwrap_or_default()
            .split(',')
            .map(str::trim)
            .filter(|origin| !origin.is_empty())
            .map(validate_cors_origin)
            .collect::<Result<Vec<_>, _>>()?;
        let job_execution_mode = match env_utf8("PCR_JOB_EXECUTION_MODE")?
            .unwrap_or_else(|| "embedded".to_owned())
            .trim()
        {
            "embedded" => JobExecutionMode::Embedded,
            "external" => JobExecutionMode::External,
            other => return Err(ConfigError::InvalidJobExecutionMode(other.to_owned())),
        };
        let database_migration_mode = match env_utf8("PCR_DATABASE_MIGRATIONS")?
            .unwrap_or_else(|| "startup".to_owned())
            .trim()
        {
            "startup" => DatabaseMigrationMode::Startup,
            "external" => DatabaseMigrationMode::External,
            other => return Err(ConfigError::InvalidDatabaseMigrationMode(other.to_owned())),
        };

        let build_identity = validate_sha256_env("PCRSTUDIO_BUILD_ID")?;
        let scientific_freeze =
            validate_sha256_env("PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256")?;
        if matches!(job_execution_mode, JobExecutionMode::External) {
            if build_identity.is_none() {
                return Err(ConfigError::MissingProductionIdentity("PCRSTUDIO_BUILD_ID"));
            }
            if scientific_freeze.is_none() {
                return Err(ConfigError::MissingProductionIdentity(
                    "PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256",
                ));
            }
        }

        if let Some(raw) = env_utf8("PCR_WORKER_TIMEOUT_SECONDS")? {
            validate_worker_timeout(&raw)?;
        }
        if let Some(raw) = env_utf8("PCR_MAX_CONCURRENT_WORKERS")? {
            validate_worker_count(&raw, false)?;
        }
        if let Some(raw) = env_utf8("PCR_MAX_QUEUED_WORKERS")? {
            validate_worker_count(&raw, true)?;
        }
        if let Some(raw) = env_utf8("PCR_TRUSTED_PROXIES")? {
            validate_trusted_proxies(&raw)?;
        }
        // Worker paths are represented as Strings internally. A non-Unicode
        // explicit path must not quietly fall back to a different interpreter.
        let _ = env_utf8("PCR_PYTHON")?;

        let operator_token =
            optional_env_or_file_utf8("PCR_OPERATOR_TOKEN", "PCR_OPERATOR_TOKEN_FILE")?;
        if let Some(value) = operator_token.as_deref() {
            validate_operator_token(value)?;
        }
        let ncbi_email = env_utf8("PCR_NCBI_EMAIL")?
            .unwrap_or_default()
            .trim()
            .to_owned();
        let ncbi_api_key = optional_env_or_file_utf8("PCR_NCBI_API_KEY", "PCR_NCBI_API_KEY_FILE")?;
        if let Some(value) = ncbi_api_key.as_deref() {
            validate_ncbi_api_key(value)?;
        }

        Ok(Self {
            bind,
            database_url,
            cors_origins,
            job_execution_mode,
            database_migration_mode,
            operator_token,
            ncbi_email,
            ncbi_api_key,
        })
    }
}

fn env_utf8(name: &'static str) -> Result<Option<String>, ConfigError> {
    match std::env::var(name) {
        Ok(value) => Ok(Some(value)),
        Err(std::env::VarError::NotPresent) => Ok(None),
        Err(std::env::VarError::NotUnicode(_)) => Err(ConfigError::NonUnicodeEnvironment(name)),
    }
}

fn validate_sha256_env(name: &'static str) -> Result<Option<String>, ConfigError> {
    let Some(raw) = env_utf8(name)? else {
        return Ok(None);
    };
    if raw.trim().is_empty() {
        return Ok(None);
    }
    let Some(value) = pcr_security::canonical_sha256(&raw) else {
        return Err(ConfigError::InvalidProductionIdentity(name, raw));
    };
    Ok(Some(value.to_owned()))
}

fn map_secret_source_error(error: pcr_security::SecretSourceError) -> ConfigError {
    match error {
        pcr_security::SecretSourceError::NonUnicodeEnvironment(name) => {
            ConfigError::NonUnicodeEnvironment(name)
        }
        pcr_security::SecretSourceError::ConflictingSources { direct, file } => {
            ConfigError::ConflictingSecretSources(direct, file)
        }
        pcr_security::SecretSourceError::FileUnreadable {
            source_name, path, ..
        } => ConfigError::SecretFileUnreadable(source_name, path),
    }
}

fn optional_env_or_file_utf8(
    name: &'static str,
    file_name: &'static str,
) -> Result<Option<String>, ConfigError> {
    pcr_security::secret_from_environment(name, file_name).map_err(map_secret_source_error)
}

fn is_visible_ascii_credential(value: &str) -> bool {
    value.bytes().all(|byte| byte.is_ascii_graphic())
}

fn validate_operator_token(value: &str) -> Result<(), ConfigError> {
    let valid = (24..=512).contains(&value.len()) && is_visible_ascii_credential(value);
    if valid {
        Ok(())
    } else {
        Err(ConfigError::InvalidOperatorToken)
    }
}

fn validate_ncbi_api_key(value: &str) -> Result<(), ConfigError> {
    let valid = !value.is_empty() && value.len() <= 512 && is_visible_ascii_credential(value);
    if valid {
        Ok(())
    } else {
        Err(ConfigError::InvalidNcbiApiKey)
    }
}

fn validate_worker_timeout(raw: &str) -> Result<(), ConfigError> {
    let value = raw.trim();
    if value.is_empty() {
        return Err(ConfigError::InvalidWorkerTimeout(raw.to_owned()));
    }
    let seconds = value
        .parse::<u64>()
        .map_err(|_| ConfigError::InvalidWorkerTimeout(raw.to_owned()))?;
    if seconds == 0 || seconds >= REQUEST_TIMEOUT.as_secs() {
        return Err(ConfigError::InvalidWorkerTimeout(raw.to_owned()));
    }
    Ok(())
}

fn validate_worker_count(raw: &str, queue: bool) -> Result<(), ConfigError> {
    let value = raw.trim();
    let parsed = value.parse::<usize>().map_err(|_| {
        if queue {
            ConfigError::InvalidWorkerQueue(raw.to_owned())
        } else {
            ConfigError::InvalidWorkerConcurrency(raw.to_owned())
        }
    })?;
    let valid = if queue {
        parsed <= 1024
    } else {
        (1..=16).contains(&parsed)
    };
    if valid {
        Ok(())
    } else if queue {
        Err(ConfigError::InvalidWorkerQueue(raw.to_owned()))
    } else {
        Err(ConfigError::InvalidWorkerConcurrency(raw.to_owned()))
    }
}

fn validate_trusted_proxies(raw: &str) -> Result<(), ConfigError> {
    for entry in raw
        .split(',')
        .map(str::trim)
        .filter(|entry| !entry.is_empty())
    {
        if rate_limit::TrustedProxy::parse(entry).is_none() {
            return Err(ConfigError::InvalidTrustedProxy(entry.to_owned()));
        }
    }
    Ok(())
}

fn bind_is_loopback(bind: &str) -> bool {
    bind.parse::<std::net::SocketAddr>()
        .map(|address| address.ip().is_loopback())
        .unwrap_or(false)
}

fn validate_cors_origin(origin: &str) -> Result<HeaderValue, ConfigError> {
    let uri = origin
        .parse::<axum::http::Uri>()
        .map_err(|_| ConfigError::InvalidCorsOrigin(origin.to_owned()))?;
    let valid_scheme = matches!(uri.scheme_str(), Some("http" | "https"));
    let authority = uri
        .authority()
        .map(|value| value.as_str())
        .unwrap_or_default();
    let has_authority = !authority.is_empty();
    // URI userinfo has no meaning in an Origin header and makes deployment
    // configuration ambiguous. Reject it rather than normalising it away.
    let no_userinfo = !authority.contains('@');
    let clean_path = uri.path().is_empty() || uri.path() == "/";
    let normalized = origin.trim_end_matches('/');
    let header_safe = HeaderValue::from_str(normalized).is_ok();
    if !valid_scheme
        || !has_authority
        || !no_userinfo
        || !clean_path
        || uri.query().is_some()
        || !header_safe
    {
        return Err(ConfigError::InvalidCorsOrigin(origin.to_owned()));
    }
    HeaderValue::from_str(normalized).map_err(|_| ConfigError::InvalidCorsOrigin(origin.to_owned()))
}

/// The design-module endpoints, ready to nest.
///
/// Separate from the account endpoints so it can be built, and tested, without
/// a database.
///
/// # Errors
///
/// Propagates a registry failure, which would mean two modules claim one id.
pub fn module_routes() -> Result<Router, pcr_core::CoreError> {
    module_routes_with_limiter(RateLimiter::from_env(DESIGNS_PER_WINDOW, DESIGN_WINDOW))
}

/// Build module routes with a database-backed limiter for scaled API replicas.
///
/// The no-argument [`module_routes`] remains intentionally local for callers
/// that only need a registry router in tests or tools without a database.
pub fn module_routes_with_accounts(accounts: Accounts) -> Result<Router, pcr_core::CoreError> {
    module_routes_with_limiter(RateLimiter::with_shared_store(
        DESIGNS_PER_WINDOW,
        DESIGN_WINDOW,
        accounts,
        "design",
    ))
}

fn module_routes_with_limiter(limiter: RateLimiter) -> Result<Router, pcr_core::CoreError> {
    let registry = pcr_application::scientific::registry_from_env()?;
    let state = ModuleState {
        registry: registry.clone(),
        gate: std::sync::Arc::new(gate::Gate::shared()),
    };

    // Two groups, split by what they cost.
    //
    // Reading the catalogue is a lookup: it answers from memory, it is the same
    // answer for everybody, and it is safe to hammer. Designing forks a Python
    // worker and runs a real search. Metering them together would either
    // throttle the sidebar or leave the searches open, so they are separated
    // here and the meter is applied to the second group only.
    let cheap = Router::new()
        .route(http_routes::INFO, get(routes::info))
        .route(http_routes::GOALS, get(routes::list_goals))
        .route(http_routes::ENGINES, get(routes::list_engines))
        .route(http_routes::MODIFIERS, get(routes::list_modifiers))
        .route(http_routes::STATUSES, get(routes::list_statuses))
        .route(http_routes::MODULES, get(routes::list_modules))
        .route(http_routes::MODULE, get(routes::get_module))
        .route(http_routes::MODULE_PRESETS, get(routes::get_presets))
        .route(http_routes::PRESETS, get(routes::all_presets))
        .with_state(state.clone())
        // The catalogue is compiled into the binary: it is identical for every
        // caller and changes only when a new build is deployed. Every page load
        // asks for it, so saying so is the difference between answering it once
        // a minute and answering it for everybody, every time.
        //
        // `public` because there is nothing personal in it. The short window
        // plus `stale-while-revalidate` is what makes a deploy take effect
        // promptly without a cache in front needing to be purged by hand.
        .layer(SetResponseHeaderLayer::overriding(
            header::CACHE_CONTROL,
            HeaderValue::from_static("public, max-age=60, stale-while-revalidate=600"),
        ));

    let expensive = bench::routes(registry)
        .merge(
            Router::new()
                .route(http_routes::MODULE_DESIGN, post(routes::run_design))
                .with_state(state),
        )
        .layer(axum::middleware::from_fn_with_state(
            limiter,
            rate_limit::meter,
        ));

    Ok(cheap.merge(expensive))
}

/// Everything that goes on top of the routes, whatever the routes are.
///
/// Separated from [`app`] so it can be tested. `app` needs a database, which
/// means the tests that drive the router directly cannot build it — and a
/// security header nobody can write a test for is a security header that stops
/// being there without anybody noticing.
///
/// The order matters and reads outermost-last: a request id is minted before
/// anything can log, and it is still attached on the way back out.
pub fn harden(router: Router) -> Router {
    let mut router = router;
    for (name, value) in api_headers() {
        router = router.layer(SetResponseHeaderLayer::if_not_present(name, value));
    }

    router
        .layer(CompressionLayer::new())
        // Two limits rather than one. Axum's own applies to extractors and
        // tower-http's applies to the stream, so a body that never finishes
        // arriving is stopped by the second rather than the first.
        .layer(DefaultBodyLimit::max(MAX_BODY_BYTES))
        .layer(RequestBodyLimitLayer::new(MAX_BODY_BYTES))
        // 504 rather than the default: a request abandoned because the worker
        // behind it took too long is a gateway timing out, and a caller can act
        // on that differently from a request they got wrong.
        .layer(TimeoutLayer::with_status_code(
            axum::http::StatusCode::GATEWAY_TIMEOUT,
            REQUEST_TIMEOUT,
        ))
        .layer(PropagateRequestIdLayer::new(REQUEST_ID_HEADER))
        .layer(TraceLayer::new_for_http())
        .layer(axum::middleware::from_fn(diagnostics::observe_http))
        // SetRequestId is outermost and therefore runs first. The context
        // middleware just inside it can safely read the minted id.
        .layer(axum::middleware::from_fn(error::request_context))
        .layer(SetRequestIdLayer::new(REQUEST_ID_HEADER, MakeRequestUuid))
}

/// Build the whole application without binding a socket, so tests can drive it
/// directly instead of over a real port.
///
/// # Errors
///
/// Propagates a registry failure, which would mean two modules claim one id.
pub fn app(config: &Config, accounts: Accounts) -> Result<Router, pcr_core::CoreError> {
    let registry = pcr_application::scientific::registry_from_env()?;
    // Everything below is about one person, or changes as they work. A cache
    // in front of this — a CDN, a proxy, a browser — holding any of it would
    // eventually hand one person another person's projects, and the default
    // when no header says otherwise is that a cache may guess.
    let personal = Router::new()
        .nest("/auth", auth::routes(accounts.clone()))
        .nest(
            "/projects",
            projects::routes_with_execution(
                accounts.clone(),
                registry.clone(),
                config.job_execution_mode.is_embedded(),
            ),
        )
        .layer(SetResponseHeaderLayer::overriding(
            header::CACHE_CONTROL,
            HeaderValue::from_static("no-store, private"),
        ));

    // Outside `personal`, and deliberately so: everything in there is stamped
    // `no-store, private` because it belongs to whoever is signed in, and this
    // route has nobody signed in. It sets its own cache header for the same
    // reason — the data is still one person's even though the caller is not.
    let shared = projects::shared_routes(accounts.clone(), registry.clone());

    // The sequence endpoints fork a worker each, exactly as a design does, and
    // one of them reaches out to NCBI into the bargain. They are metered under
    // their own ceiling rather than the design one so that fetching a record
    // does not spend a design slot -- but they are metered, because an
    // anonymous alignment over a large family is real work on the host.
    let api = module_routes_with_accounts(accounts.clone())?
        .merge(personal)
        .merge(shared)
        .merge(
            Router::new()
                .nest(
                    "/sequences",
                    sequences::routes(
                        pcr_storage::FoundationStorage::new(accounts.pool()),
                        config.ncbi_email.clone(),
                        config.ncbi_api_key.clone(),
                    ),
                )
                .layer(axum::middleware::from_fn_with_state(
                    RateLimiter::with_shared_store(
                        SEQUENCES_PER_WINDOW,
                        DESIGN_WINDOW,
                        accounts.clone(),
                        "sequence",
                    ),
                    rate_limit::meter,
                )),
        );

    // Liveness and readiness are separate endpoints on purpose, and both sit
    // outside `/api`: they are about this process, not about the service it
    // offers, and an orchestrator should not have to know the API's shape to
    // ask whether the container is working.
    let probes = Router::new()
        .route(http_routes::HEALTH, get(routes::health))
        .route(http_routes::READY, get(readiness::ready))
        .route(
            http_routes::SCIENTIFIC_READY,
            get(readiness::scientific_ready),
        )
        .with_state(readiness::Readiness::with_runner_requirement(
            accounts.clone(),
            !config.job_execution_mode.is_embedded(),
        ));

    let operator = Router::new()
        .route(
            http_routes::OPERATOR_DIAGNOSTICS,
            get(diagnostics::diagnostics),
        )
        .route(http_routes::OPERATOR_METRICS, get(diagnostics::metrics))
        .with_state(diagnostics::DiagnosticsState::new(
            gate::Gate::shared(),
            accounts.clone(),
            config.operator_token.clone(),
        ));
    let probes = probes.merge(operator);

    // `/api/v1` is the stable external boundary. `/api` remains as a
    // compatibility alias for legacy clients while the Web tier migrates. Both
    // routers are the same value, so versioning cannot accidentally fork
    // authorization, rate limiting, or scientific behavior.
    let mut router = harden(probes.nest("/api", api.clone()).nest("/api/v1", api));

    if !config.cors_origins.is_empty() {
        // Origins were structurally validated at startup. Reaching this point
        // with an invalid HeaderValue would therefore be an internal invariant
        // violation, so fail construction rather than silently broadening or
        // shrinking the configured policy.
        router = router.layer(
            CorsLayer::new()
                .allow_origin(config.cors_origins.clone())
                .allow_methods([
                    Method::GET,
                    Method::POST,
                    Method::PUT,
                    Method::PATCH,
                    Method::DELETE,
                ])
                .allow_headers([
                    header::ACCEPT,
                    header::AUTHORIZATION,
                    header::CONTENT_TYPE,
                    axum::http::HeaderName::from_static("idempotency-key"),
                    REQUEST_ID_HEADER,
                ])
                // Credentials are not part of this API's contract: sessions
                // travel as bearer tokens, never as cookies, so no cross-origin
                // caller ever has anything to send along "with credentials".
                // Leaving the flag off keeps the origin policy as narrow as it
                // reads.
                .max_age(Duration::from_secs(3600)),
        );
    }

    Ok(router)
}

#[cfg(test)]
mod config_tests {
    use super::{
        bind_is_loopback, validate_cors_origin, validate_ncbi_api_key, validate_operator_token,
        validate_trusted_proxies, validate_worker_count, validate_worker_timeout, Config,
    };

    #[test]
    fn loopback_detection_rejects_public_and_malformed_binds() {
        assert!(bind_is_loopback("127.0.0.1:8080"));
        assert!(bind_is_loopback("[::1]:8080"));
        assert!(!bind_is_loopback("0.0.0.0:8080"));
        assert!(!bind_is_loopback("192.0.2.10:8080"));
        assert!(!bind_is_loopback("not-a-socket"));
    }

    #[test]
    fn worker_timeout_must_finish_before_the_request_deadline() {
        for valid in ["1", "120", "299", " 120 "] {
            assert!(validate_worker_timeout(valid).is_ok(), "rejected {valid:?}");
        }
        for invalid in ["", "0", "300", "420", "-1", "not-a-number"] {
            assert!(
                validate_worker_timeout(invalid).is_err(),
                "accepted {invalid:?}"
            );
        }
    }

    #[test]
    fn worker_capacity_overrides_are_not_silently_clamped() {
        for valid in ["1", "8", "16"] {
            assert!(
                validate_worker_count(valid, false).is_ok(),
                "rejected {valid:?}"
            );
        }
        for invalid in ["", "0", "17", "-1", "lots"] {
            assert!(
                validate_worker_count(invalid, false).is_err(),
                "accepted {invalid:?}"
            );
        }
        for valid in ["0", "256", "1024"] {
            assert!(
                validate_worker_count(valid, true).is_ok(),
                "rejected {valid:?}"
            );
        }
        for invalid in ["", "1025", "-1", "lots"] {
            assert!(
                validate_worker_count(invalid, true).is_err(),
                "accepted {invalid:?}"
            );
        }
    }

    #[test]
    fn trusted_proxy_overrides_are_all_or_nothing() {
        assert!(validate_trusted_proxies("").is_ok());
        assert!(validate_trusted_proxies("127.0.0.1,172.29.0.0/24,::1/128").is_ok());
        assert!(validate_trusted_proxies("172.29.0.0/99").is_err());
        assert!(validate_trusted_proxies("not-an-ip").is_err());
    }

    #[test]
    fn config_debug_redacts_deployment_credentials() {
        let config = Config {
            database_url: "postgres://user:super-secret@db/pcrstudio".to_owned(),
            operator_token: Some("operator-secret-token-value".to_owned()),
            ncbi_api_key: Some("ncbi-secret-value".to_owned()),
            ncbi_email: "operator@example.invalid".to_owned(),
            ..Config::default()
        };
        let rendered = format!("{config:?}");
        assert!(!rendered.contains("super-secret"));
        assert!(!rendered.contains("operator-secret-token-value"));
        assert!(!rendered.contains("ncbi-secret-value"));
        assert!(!rendered.contains("operator@example.invalid"));
        assert!(rendered.contains("[REDACTED]"));
        assert!(rendered.contains("[CONFIGURED]"));
    }

    #[test]
    fn operator_token_has_one_header_safe_shape() {
        assert!(validate_operator_token(&"a".repeat(24)).is_ok());
        for invalid in [
            "short",
            "abcdefghijklmnopqrstuvw ",
            "abcdefghijklmnopqrstuvw\n",
            "éééééééééééééééééééééééé",
        ] {
            assert!(
                validate_operator_token(invalid).is_err(),
                "accepted {invalid:?}"
            );
        }
        assert!(validate_operator_token(&"x".repeat(513)).is_err());
    }

    #[test]
    fn ncbi_api_key_cannot_claim_authenticated_quota_with_whitespace() {
        assert!(validate_ncbi_api_key("abc123_-XYZ").is_ok());
        for invalid in ["", "abc def", "abc\ndef", "abc\tdef", "é"] {
            assert!(
                validate_ncbi_api_key(invalid).is_err(),
                "accepted {invalid:?}"
            );
        }
        assert!(validate_ncbi_api_key(&"x".repeat(513)).is_err());
    }

    #[test]
    fn cors_origin_validation_is_exact() {
        assert_eq!(
            validate_cors_origin("https://pcrstudio.example.org/").unwrap(),
            "https://pcrstudio.example.org"
        );
        assert_eq!(
            validate_cors_origin("http://127.0.0.1:3000").unwrap(),
            "http://127.0.0.1:3000"
        );
        for invalid in [
            "ftp://pcrstudio.example.org",
            "https://pcrstudio.example.org/path",
            "https://pcrstudio.example.org?x=1",
            "https://user@pcrstudio.example.org",
            "pcrstudio.example.org",
            "",
        ] {
            assert!(
                validate_cors_origin(invalid).is_err(),
                "accepted {invalid:?}"
            );
        }
    }
}
