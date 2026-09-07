//! The account endpoints, and the extractor that says who is asking.

use std::net::SocketAddr;

use axum::extract::{ConnectInfo, DefaultBodyLimit, FromRef, FromRequestParts, State};
use axum::http::request::Parts;
use axum::http::{HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete, get, patch, post};
use axum::{Json, Router};
use pcr_accounts::{AccountError, Accounts, DateTime, User, Utc};
use serde::{Deserialize, Serialize};
use tower_http::limit::RequestBodyLimitLayer;

use crate::http_routes;
use crate::rate_limit::{caller_key_with_trusted, RateLimiter};

/// Everything the account endpoints need.
#[derive(Clone)]
pub struct AuthState {
    /// The user store.
    pub accounts: Accounts,
    /// Ceiling on sign-in and registration attempts.
    pub limiter: RateLimiter,
    /// Ceiling on password checks made by somebody who already has a session:
    /// changing the password, reissuing the recovery code, deleting the
    /// account. Each verifies an Argon2 hash, so without a ceiling a stolen
    /// session can guess at the account password for free -- and each attempt
    /// costs the server real CPU even when it fails.
    pub sensitive: RateLimiter,
}

impl FromRef<AuthState> for Accounts {
    fn from_ref(state: &AuthState) -> Self {
        state.accounts.clone()
    }
}

/// An account failure on its way out over HTTP.
#[derive(Debug)]
pub struct AuthError(pub AccountError);

impl From<AccountError> for AuthError {
    fn from(error: AccountError) -> Self {
        Self(error)
    }
}

/// What a 5xx says instead of the store's own words.
///
/// The detail behind a [`AccountError::Store`] is a database driver's error
/// text: connection strings, table names, whatever the driver felt like
/// quoting. It goes to the log in full and to the browser not at all.
const STORE_FAILURE: &str = "The account store is unavailable. Try again in a moment.";

impl IntoResponse for AuthError {
    fn into_response(self) -> Response {
        let (status, code, kind, field_path, retryable) = match &self.0 {
            AccountError::EmailTaken => (
                StatusCode::CONFLICT,
                "EMAIL_TAKEN",
                "emailTaken",
                Some("email"),
                false,
            ),
            AccountError::InvalidEmail(_) => (
                StatusCode::UNPROCESSABLE_ENTITY,
                "INVALID_EMAIL",
                "invalidEmail",
                Some("email"),
                false,
            ),
            AccountError::WeakPassword(_) => (
                StatusCode::UNPROCESSABLE_ENTITY,
                "WEAK_PASSWORD",
                "weakPassword",
                Some("password"),
                false,
            ),
            AccountError::InvalidName(_) => (
                StatusCode::UNPROCESSABLE_ENTITY,
                "INVALID_DISPLAY_NAME",
                "invalidName",
                Some("name"),
                false,
            ),
            AccountError::BadRequest(_) => (
                StatusCode::UNPROCESSABLE_ENTITY,
                "INVALID_ACCOUNT_REQUEST",
                "badRequest",
                None,
                false,
            ),
            AccountError::InvalidCredentials => (
                StatusCode::UNAUTHORIZED,
                "INVALID_CREDENTIALS",
                "invalidCredentials",
                None,
                false,
            ),
            AccountError::RecoveryLocked => (
                StatusCode::TOO_MANY_REQUESTS,
                "RECOVERY_LOCKED",
                "recoveryLocked",
                None,
                true,
            ),
            AccountError::TooManyRequests => (
                StatusCode::TOO_MANY_REQUESTS,
                "ACCOUNT_RATE_LIMITED",
                "tooManyRequests",
                None,
                true,
            ),
            AccountError::SessionEnded => (
                StatusCode::UNAUTHORIZED,
                "SESSION_ENDED",
                "sessionEnded",
                None,
                false,
            ),
            AccountError::NoSuchUser => (
                StatusCode::NOT_FOUND,
                "USER_NOT_FOUND",
                "noSuchUser",
                None,
                false,
            ),
            AccountError::Store(_) => (
                StatusCode::SERVICE_UNAVAILABLE,
                "ACCOUNT_STORE_UNAVAILABLE",
                "storeFailure",
                None,
                true,
            ),
        };
        if status.is_server_error() {
            tracing::error!(error = %self.0, code, "account request failed");
        }
        let detail = if matches!(&self.0, AccountError::Store(_)) {
            STORE_FAILURE.to_owned()
        } else {
            self.0.to_string()
        };
        let mut response = (
            status,
            Json(crate::error::body(
                code,
                kind,
                detail,
                field_path.map(str::to_owned),
                Some("account"),
                retryable,
            )),
        )
            .into_response();
        if retryable {
            response.headers_mut().insert(
                axum::http::header::RETRY_AFTER,
                axum::http::HeaderValue::from_static("5"),
            );
        }
        response
    }
}

/// The signed-in user, resolved from the bearer token on the request.
///
/// Rejects with 401 when the header is missing or the session has ended, so a
/// handler that takes this parameter cannot accidentally run for a stranger.
pub struct CurrentUser {
    /// Who is asking.
    pub user: User,
    /// The token they presented, for operations that spare their own session.
    pub token: String,
}

/// Any state that can produce the account store can authenticate a request.
///
/// Generic rather than bound to `AuthState` so every router that needs to know
/// who is asking uses the same extractor. A second, hand-written ownership
/// check somewhere else is how one endpoint ends up not doing it.
impl<S> FromRequestParts<S> for CurrentUser
where
    S: Send + Sync,
    Accounts: FromRef<S>,
{
    type Rejection = AuthError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let accounts = Accounts::from_ref(state);
        let token = bearer_token(&parts.headers).ok_or(AccountError::SessionEnded)?;
        let user = accounts.user_for_session(&token).await?;
        Ok(Self { user, token })
    }
}

/// The peer address, when the server was started with connection info.
///
/// `Option<ConnectInfo<_>>` is not an extractor axum accepts, and a bare
/// `ConnectInfo` would fail in tests that drive the router directly. Reading it
/// out of the extensions gives the fallback without either problem.
pub struct PeerAddr(pub Option<SocketAddr>);

impl<S: Send + Sync> FromRequestParts<S> for PeerAddr {
    type Rejection = std::convert::Infallible;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        Ok(Self(
            parts
                .extensions
                .get::<ConnectInfo<SocketAddr>>()
                .map(|ConnectInfo(address)| *address),
        ))
    }
}

fn bearer_token(headers: &HeaderMap) -> Option<String> {
    let value = headers
        .get(axum::http::header::AUTHORIZATION)?
        .to_str()
        .ok()?;
    let token = value.strip_prefix("Bearer ")?.trim();
    (!token.is_empty()).then(|| token.to_owned())
}

/// What a new account is created from.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "the field names are the documentation")]
pub struct RegisterRequest {
    pub email: String,
    pub display_name: String,
    pub password: String,
}

/// What signing in is attempted with.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "the field names are the documentation")]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
    #[serde(default)]
    pub remember: bool,
}

/// A new display name.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "the field names are the documentation")]
pub struct RenameRequest {
    pub display_name: String,
}

/// A new sign-in address, proved with the current password.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "the field names are the documentation")]
pub struct ChangeEmailRequest {
    pub current_password: String,
    pub new_email: String,
}

/// The current password, and what to replace it with.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "the field names are the documentation")]
pub struct ChangePasswordRequest {
    pub current_password: String,
    pub new_password: String,
}

/// Confirmation that the person deleting the account owns it.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "the field names are the documentation")]
pub struct DeleteAccountRequest {
    pub password: String,
}

/// A user plus the session token minted for them.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "each field is documented below")]
pub struct SessionResponse {
    pub user: User,
    /// A recovery code, present only on the two responses that mint one:
    /// registering, and recovering. Absent on an ordinary sign-in, which is
    /// why it is skipped rather than sent as null — a null here would read as
    /// "this account has no code".
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recovery_code: Option<String>,
    /// Hand this back as `Authorization: Bearer`. It is not recoverable later.
    pub token: String,
    /// Seconds until the session expires, so the caller can size its cookie.
    pub expires_in: i64,
}

/// How many sessions an operation ended.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EndedResponse {
    /// Number of sessions that were ended.
    pub ended: u64,
}

const REMEMBERED_SESSION_SECONDS: i64 = pcr_accounts::SessionLifetime::Remembered.seconds();

/// Account requests are tiny JSON documents. Keep their extractor/stream
/// ceiling independent from the application's much larger import allowance so
/// public auth endpoints cannot be used as a 32 MiB buffering surface.
const AUTH_BODY_BYTES: usize = 64 * 1024;

/// What a caller sends to get back into an account they are locked out of.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "the field names are the documentation")]
pub struct RecoverRequest {
    pub email: String,
    pub recovery_code: String,
    pub new_password: String,
}

/// What a caller sends to swap their recovery code for a new one.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(missing_docs, reason = "the field names are the documentation")]
pub struct ReissueRequest {
    pub password: String,
}

/// A recovery code, on its way to the person once.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RecoveryResponse {
    /// Show it, and say that it will not be shown again.
    pub recovery_code: String,
}

/// Whether this account has a recovery code, for the settings page to say so.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RecoveryStatus {
    /// False for accounts made before recovery existed.
    pub has_code: bool,
    /// When the current one was issued.
    pub issued_at: Option<DateTime<Utc>>,
}

/// Attempts allowed per caller per window, for the two endpoints that accept a
/// password from a stranger.
const ATTEMPTS: usize = 10;
const ATTEMPT_WINDOW: std::time::Duration = std::time::Duration::from_secs(300);

/// Attempts allowed per caller-and-account for the endpoints that verify a
/// password behind an existing session.
///
/// Wider than a person needs -- changing a password twice in five minutes is
/// already unusual -- and narrow enough that guessing through one is not a
/// strategy.
const SENSITIVE_ATTEMPTS: usize = 10;
const SENSITIVE_WINDOW: std::time::Duration = std::time::Duration::from_secs(300);

/// Why an endpoint that takes a password from a stranger refused.
#[derive(Debug)]
pub enum SignInError {
    /// The caller has used up its attempts for now.
    TooManyAttempts,
    /// The account store said no.
    Account(AccountError),
}

impl From<AccountError> for SignInError {
    fn from(error: AccountError) -> Self {
        Self::Account(error)
    }
}

impl IntoResponse for SignInError {
    fn into_response(self) -> Response {
        match self {
            Self::TooManyAttempts => (
                StatusCode::TOO_MANY_REQUESTS,
                Json(crate::error::body(
                    "AUTH_RATE_LIMITED",
                    "tooManyAttempts",
                    "Too many attempts. Wait a few minutes and try again.",
                    None,
                    Some("authentication"),
                    true,
                )),
            )
                .into_response(),
            Self::Account(error) => AuthError(error).into_response(),
        }
    }
}

/// Set a new password from a recovery code.
///
/// Metered by the same per-caller limiter as signing in, and by a per-account
/// counter in the store underneath. Both are needed: the first stops one caller
/// hammering, and the second stops the same attempt being spread across a
/// thousand callers, which is the only shape an attack on a 125-bit code can
/// take.
async fn recover(
    State(state): State<AuthState>,
    headers: HeaderMap,
    PeerAddr(peer): PeerAddr,
    Json(body): Json<RecoverRequest>,
) -> Result<Json<SessionResponse>, SignInError> {
    guard(&state, &headers, peer).await?;

    let (user, next, token) = state
        .accounts
        .recover_and_start_session(&body.email, &body.recovery_code, &body.new_password)
        .await?;

    Ok(Json(SessionResponse {
        recovery_code: Some(next.plain),
        user,
        token: token.plain,
        expires_in: REMEMBERED_SESSION_SECONDS,
    }))
}

/// Whether the signed-in account has a recovery code.
async fn recovery_status(
    State(state): State<AuthState>,
    CurrentUser { user, .. }: CurrentUser,
) -> Result<Json<RecoveryStatus>, AuthError> {
    let issued_at = state.accounts.recovery_status(&user.id).await?;
    Ok(Json(RecoveryStatus {
        has_code: issued_at.is_some(),
        issued_at,
    }))
}

/// Replace the recovery code, proving the password first.
///
/// Also how an account made before recovery existed gets its first one.
async fn reissue_recovery_code(
    State(state): State<AuthState>,
    CurrentUser { user, .. }: CurrentUser,
    PeerAddr(peer): PeerAddr,
    headers: HeaderMap,
    Json(body): Json<ReissueRequest>,
) -> Result<Json<RecoveryResponse>, AuthError> {
    guard_sensitive(&state, &headers, peer, &user.id).await?;
    let code = state
        .accounts
        .reissue_recovery_code(&user.id, &body.password)
        .await?;
    Ok(Json(RecoveryResponse {
        recovery_code: code.plain,
    }))
}

async fn guard(
    state: &AuthState,
    headers: &HeaderMap,
    peer: Option<SocketAddr>,
) -> Result<(), SignInError> {
    let allowed = state
        .limiter
        .allow_request(&caller_key_with_trusted(
            headers,
            peer,
            state.limiter.trusted_proxies(),
        ))
        .await
        .map_err(|_| {
            SignInError::Account(AccountError::Store("rate limiter unavailable".to_owned()))
        })?;
    if allowed {
        return Ok(());
    }
    Err(SignInError::TooManyAttempts)
}

/// The same ceiling for operations that verify a password behind a session.
///
/// Keyed by caller *and* account: one person's failed attempts must not lock a
/// different person out of their own settings page, and one account's budget
/// cannot be exhausted by a stranger who shares its NAT.
async fn guard_sensitive(
    state: &AuthState,
    headers: &HeaderMap,
    peer: Option<SocketAddr>,
    user_id: &str,
) -> Result<(), AuthError> {
    let key = format!(
        "{}:{user_id}",
        caller_key_with_trusted(headers, peer, state.sensitive.trusted_proxies())
    );
    let allowed =
        state.sensitive.allow_request(&key).await.map_err(|_| {
            AuthError::from(AccountError::Store("rate limiter unavailable".to_owned()))
        })?;
    if allowed {
        return Ok(());
    }
    Err(AuthError::from(AccountError::TooManyRequests))
}

async fn register(
    State(state): State<AuthState>,
    headers: HeaderMap,
    PeerAddr(peer): PeerAddr,
    Json(body): Json<RegisterRequest>,
) -> Result<Json<SessionResponse>, SignInError> {
    guard(&state, &headers, peer).await?;

    let (user, recovery, token) = state
        .accounts
        .register_and_start_session(&body.email, &body.display_name, &body.password)
        .await?;

    Ok(Json(SessionResponse {
        // The only time this exists in plain text anywhere. It is not stored,
        // it is not recoverable, and it is not sent a second time.
        recovery_code: Some(recovery.plain),
        user,
        token: token.plain,
        expires_in: REMEMBERED_SESSION_SECONDS,
    }))
}

async fn login(
    State(state): State<AuthState>,
    headers: HeaderMap,
    PeerAddr(peer): PeerAddr,
    Json(body): Json<LoginRequest>,
) -> Result<Json<SessionResponse>, SignInError> {
    guard(&state, &headers, peer).await?;

    let user = state
        .accounts
        .authenticate(&body.email, &body.password)
        .await?;
    let lifetime = if body.remember {
        pcr_accounts::SessionLifetime::Remembered
    } else {
        pcr_accounts::SessionLifetime::Browser
    };
    let token = state
        .accounts
        .start_session_with_lifetime(&user.id, lifetime)
        .await?;

    Ok(Json(SessionResponse {
        user,
        recovery_code: None,
        token: token.plain,
        expires_in: lifetime.seconds(),
    }))
}

async fn logout(
    State(state): State<AuthState>,
    current: CurrentUser,
) -> Result<StatusCode, AuthError> {
    state.accounts.end_session(&current.token).await?;
    Ok(StatusCode::NO_CONTENT)
}

async fn me(current: CurrentUser) -> Json<User> {
    Json(current.user)
}

async fn rename(
    State(state): State<AuthState>,
    current: CurrentUser,
    Json(body): Json<RenameRequest>,
) -> Result<Json<User>, AuthError> {
    Ok(Json(
        state
            .accounts
            .rename(&current.user.id, &body.display_name)
            .await?,
    ))
}

/// What somebody has told us about how they work.
async fn preferences(
    State(state): State<AuthState>,
    current: CurrentUser,
) -> Result<Json<serde_json::Value>, AuthError> {
    Ok(Json(state.accounts.preferences(&current.user.id).await?))
}

/// The keys this server understands, and what may be in them.
///
/// An allow-list rather than "store whatever arrives". The column is schemaless
/// so that adding a setting costs no migration; that is not a licence to let a
/// session token write arbitrary JSON into a row that is read back on every
/// page load. Anything unrecognised is refused by name, so a client sending a
/// misspelt key learns that rather than silently saving a setting that never
/// takes effect.
const KNOWN_PREFERENCES: &[&str] = &["preferredPolymerase"];

/// Replace the preferences.
async fn set_preferences(
    State(state): State<AuthState>,
    current: CurrentUser,
    Json(body): Json<serde_json::Value>,
) -> Result<Json<serde_json::Value>, AuthError> {
    let object = body.as_object().ok_or_else(|| {
        AuthError::from(AccountError::BadRequest(
            "Preferences must be an object.".to_owned(),
        ))
    })?;

    for key in object.keys() {
        if !KNOWN_PREFERENCES.contains(&key.as_str()) {
            return Err(AccountError::BadRequest(format!(
                "`{key}` is not a setting this version knows about."
            ))
            .into());
        }
    }

    // Every value is a short string naming something from the catalogue. The
    // bound is not about storage — it is so a preferences column cannot become
    // a place to keep a megabyte.
    for (key, value) in object {
        let bad = match value {
            serde_json::Value::Null => false,
            serde_json::Value::String(text) => text.len() > 64,
            _ => true,
        };
        if bad {
            return Err(AccountError::BadRequest(format!(
                "`{key}` must be a short name, or null to unset it."
            ))
            .into());
        }
    }

    // Nulls are dropped rather than stored, so "unset" leaves no trace to read
    // back and reason about later.
    let kept: serde_json::Map<String, serde_json::Value> = object
        .iter()
        .filter(|(_, value)| !value.is_null())
        .map(|(key, value)| (key.clone(), value.clone()))
        .collect();

    Ok(Json(
        state
            .accounts
            .set_preferences(&current.user.id, &serde_json::Value::Object(kept))
            .await?,
    ))
}

async fn change_email(
    State(state): State<AuthState>,
    CurrentUser { user, token }: CurrentUser,
    PeerAddr(peer): PeerAddr,
    headers: HeaderMap,
    Json(body): Json<ChangeEmailRequest>,
) -> Result<Json<User>, AuthError> {
    guard_sensitive(&state, &headers, peer, &user.id).await?;
    Ok(Json(
        state
            .accounts
            .change_email(
                &user.id,
                &body.current_password,
                &body.new_email,
                Some(&token),
            )
            .await?,
    ))
}

async fn change_password(
    State(state): State<AuthState>,
    CurrentUser { user, token }: CurrentUser,
    PeerAddr(peer): PeerAddr,
    headers: HeaderMap,
    Json(body): Json<ChangePasswordRequest>,
) -> Result<StatusCode, AuthError> {
    guard_sensitive(&state, &headers, peer, &user.id).await?;
    state
        .accounts
        .change_password(
            &user.id,
            &body.current_password,
            &body.new_password,
            // The session doing the changing stays alive; every other one ends.
            Some(&token),
        )
        .await?;
    Ok(StatusCode::NO_CONTENT)
}

async fn sign_out_everywhere(
    State(state): State<AuthState>,
    current: CurrentUser,
) -> Result<Json<EndedResponse>, AuthError> {
    let ended = state.accounts.end_all_sessions(&current.user.id).await?;
    Ok(Json(EndedResponse { ended }))
}

async fn delete_account(
    State(state): State<AuthState>,
    CurrentUser { user, .. }: CurrentUser,
    PeerAddr(peer): PeerAddr,
    headers: HeaderMap,
    Json(body): Json<DeleteAccountRequest>,
) -> Result<StatusCode, AuthError> {
    guard_sensitive(&state, &headers, peer, &user.id).await?;
    state.accounts.delete(&user.id, &body.password).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// The account endpoints, ready to nest.
pub fn routes(accounts: Accounts) -> Router {
    let state = AuthState {
        accounts: accounts.clone(),
        limiter: RateLimiter::with_shared_store(ATTEMPTS, ATTEMPT_WINDOW, accounts.clone(), "auth"),
        sensitive: RateLimiter::with_shared_store(
            SENSITIVE_ATTEMPTS,
            SENSITIVE_WINDOW,
            accounts.clone(),
            "sensitive-auth",
        ),
    };

    Router::new()
        .route(http_routes::AUTH_REGISTER, post(register))
        .route(http_routes::AUTH_LOGIN, post(login))
        .route(http_routes::AUTH_LOGOUT, post(logout))
        .route(http_routes::AUTH_ME, get(me))
        .route(http_routes::AUTH_PROFILE, patch(rename))
        .route(http_routes::AUTH_EMAIL, patch(change_email))
        .route(
            http_routes::AUTH_PREFERENCES_GET,
            get(preferences).put(set_preferences),
        )
        .route(http_routes::AUTH_PASSWORD, post(change_password))
        .route(
            http_routes::AUTH_SESSIONS_DELETE,
            delete(sign_out_everywhere),
        )
        .route(http_routes::AUTH_ACCOUNT_DELETE, delete(delete_account))
        .route(http_routes::AUTH_RECOVER, post(recover))
        .route(http_routes::AUTH_RECOVERY_GET, get(recovery_status))
        .route(http_routes::AUTH_RECOVERY_GET, post(reissue_recovery_code))
        // Two caps for the same reason as the application-wide hardening: one
        // constrains Json extractors and one constrains the incoming stream.
        .layer(DefaultBodyLimit::max(AUTH_BODY_BYTES))
        .layer(RequestBodyLimitLayer::new(AUTH_BODY_BYTES))
        .with_state(state)
}
