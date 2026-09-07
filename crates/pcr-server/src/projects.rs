//! The project endpoints.
//!
//! Every one of these takes [`CurrentUser`], so there is no path through this
//! file that reads or writes a project without knowing whose it is. That is
//! the whole access-control story: no ownership check is written by hand in a
//! handler, because the store refuses to answer without a user id.
//!
//! Running a design and saving it are one call. Two calls would leave a window
//! in which somebody has a result and no record of it, and the record is what
//! a project is for.

use axum::extract::{DefaultBodyLimit, Path, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete, get, post};
use axum::{Json, Router};
use chrono::{DateTime, Utc};
use pcr_accounts::Accounts;
use pcr_core::{CoreError, Registry};
use pcr_projects::{Project, ProjectError, Projects, Run, RunSummary};
use pcr_storage::{FoundationStorage, RunJobState, StorageError};
use serde::{Deserialize, Serialize};

use crate::auth::CurrentUser;
use crate::error::ApiError;
use crate::http_routes;
use crate::rate_limit::{RateLimiter, DESIGNS_PER_WINDOW, DESIGN_WINDOW};

/// What the project handlers need.
#[derive(Clone)]
pub struct ProjectState {
    /// The store.
    pub projects: Projects,
    /// Needed to resolve the bearer token on every request.
    pub accounts: Accounts,
    /// Needed to run a design without a second hop.
    pub registry: Registry,
    /// The process's one ceiling on concurrent workers, so a saved design
    /// waits its turn like a public one instead of forking interpreter N+1.
    pub gate: std::sync::Arc<crate::gate::Gate>,
    /// Durable Foundation execution/assets/qualification storage.
    pub storage: FoundationStorage,
    /// Whether this API process is allowed to dispatch durable scientific jobs.
    /// Production sets this false and runs the dedicated `pcr-runner`.
    pub embedded_jobs: bool,
}

impl axum::extract::FromRef<ProjectState> for Accounts {
    fn from_ref(state: &ProjectState) -> Self {
        state.accounts.clone()
    }
}

/// A project failure on the wire.
///
/// Separate from [`ApiError`] because the vocabularies are separate: a project
/// that is not there is not the same kind of thing as an engine that refused.
pub struct ProjectApiError(ProjectError);

impl From<ProjectError> for ProjectApiError {
    fn from(error: ProjectError) -> Self {
        Self(error)
    }
}

/// What a 5xx says instead of the store's own words.
///
/// A [`ProjectError::Store`] carries a database driver's error text, which is
/// for the log rather than the browser. The kind is new on purpose: it names
/// where the failure sits without pretending to be one of the project
/// vocabulary's client mistakes.
const STORE_FAILURE: &str = "The project store is unavailable. Try again in a moment.";

fn idempotency_key(headers: &HeaderMap) -> Result<Option<String>, ApiError> {
    let Some(value) = headers.get("idempotency-key") else {
        return Ok(None);
    };
    let value = value.to_str().map_err(|_| {
        ApiError(CoreError::InvalidRequest(
            "Idempotency-Key must contain printable UTF-8 text.".to_owned(),
        ))
    })?;
    if value.is_empty() || value.len() > 128 || value.chars().any(char::is_control) {
        return Err(ApiError(CoreError::InvalidRequest(
            "Idempotency-Key must contain 1-128 printable characters.".to_owned(),
        )));
    }
    Ok(Some(value.to_owned()))
}

impl IntoResponse for ProjectApiError {
    fn into_response(self) -> Response {
        let (status, code, kind, field_path, retryable) = match &self.0 {
            ProjectError::NotFound => (
                StatusCode::NOT_FOUND,
                "PROJECT_NOT_FOUND",
                "notFound",
                None,
                false,
            ),
            ProjectError::InvalidName(_) => (
                StatusCode::BAD_REQUEST,
                "INVALID_PROJECT_NAME",
                "invalidName",
                Some("name"),
                false,
            ),
            ProjectError::InvalidData(_) => (
                StatusCode::BAD_REQUEST,
                "INVALID_PROJECT_DATA",
                "invalidData",
                None,
                false,
            ),
            ProjectError::NotAnExport(_) => (
                StatusCode::BAD_REQUEST,
                "INVALID_PROJECT_EXPORT",
                "notAnExport",
                None,
                false,
            ),
            ProjectError::TooManyProjects(_) => (
                StatusCode::CONFLICT,
                "PROJECT_QUOTA_EXCEEDED",
                "tooManyProjects",
                None,
                false,
            ),
            ProjectError::StorageLimit(_) => (
                StatusCode::CONFLICT,
                "ACCOUNT_STORAGE_LIMIT",
                "storageLimit",
                None,
                false,
            ),
            ProjectError::Conflict(_) => (
                StatusCode::CONFLICT,
                "PROJECT_VERSION_CONFLICT",
                "conflict",
                None,
                false,
            ),
            ProjectError::Store(_) => (
                StatusCode::SERVICE_UNAVAILABLE,
                "PROJECT_STORE_UNAVAILABLE",
                "storeFailure",
                None,
                true,
            ),
        };
        if status.is_server_error() {
            tracing::error!(error = %self.0, code, "project request failed");
        }
        let detail = if matches!(&self.0, ProjectError::Store(_)) {
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
                Some("storage"),
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

/// Storage failure on authenticated Foundation endpoints.
struct StorageApiError(StorageError);

impl From<StorageError> for StorageApiError {
    fn from(error: StorageError) -> Self {
        Self(error)
    }
}

impl IntoResponse for StorageApiError {
    fn into_response(self) -> Response {
        let (status, code, kind, detail, retryable) = match self.0 {
            StorageError::NotFound => (
                StatusCode::NOT_FOUND,
                "STORAGE_RECORD_NOT_FOUND",
                "notFound",
                "The requested record was not found.".to_owned(),
                false,
            ),
            StorageError::Invalid(detail) => (
                StatusCode::BAD_REQUEST,
                "INVALID_STORAGE_INPUT",
                "invalidRequest",
                detail,
                false,
            ),
            StorageError::Conflict(detail) => (
                StatusCode::CONFLICT,
                "IDEMPOTENCY_CONFLICT",
                "conflict",
                detail,
                false,
            ),
            StorageError::Quota(detail) => (
                StatusCode::TOO_MANY_REQUESTS,
                "JOB_QUOTA_EXCEEDED",
                "tooManyRequests",
                detail,
                true,
            ),
            StorageError::Migration(detail) | StorageError::Query(detail) => {
                tracing::error!(error = %detail, "foundation storage request failed");
                (
                    StatusCode::SERVICE_UNAVAILABLE,
                    "STORAGE_UNAVAILABLE",
                    "storeFailure",
                    STORE_FAILURE.to_owned(),
                    true,
                )
            }
        };
        let mut response = (
            status,
            Json(crate::error::body(
                code,
                kind,
                detail,
                None,
                Some("storage"),
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

/// The two vocabularies [`run_and_save`] can fail with, kept distinct.
///
/// The handler sits where the project store meets the design engine, and each
/// speaks its own errors: a project that is not yours is not the same kind of
/// thing as an engine that refused. Collapsing both into a bare `Response`
/// lost that distinction on the way past — and handed axum an `Err` variant
/// the size of a whole HTTP response, which clippy rightly refuses.
enum RunFailure {
    Project(ProjectApiError),
    Design(ApiError),
}

impl From<ProjectError> for RunFailure {
    fn from(error: ProjectError) -> Self {
        Self::Project(ProjectApiError(error))
    }
}

impl From<CoreError> for RunFailure {
    fn from(error: CoreError) -> Self {
        Self::Design(ApiError(error))
    }
}

impl IntoResponse for RunFailure {
    fn into_response(self) -> Response {
        match self {
            Self::Project(error) => error.into_response(),
            Self::Design(error) => error.into_response(),
        }
    }
}

/// What starting a project needs.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NewProject {
    /// What to call it.
    pub name: String,
    /// Which assay it designs for.
    pub module_id: String,
    /// Initial notes, for atomic duplicate/fork creation.
    #[serde(default)]
    pub notes: String,
    /// Initial draft, for atomic duplicate/fork creation.
    #[serde(default = "empty_object")]
    pub settings: serde_json::Value,
}

fn empty_object() -> serde_json::Value {
    serde_json::json!({})
}

/// What changing a project accepts. Anything absent is left alone.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectChange {
    /// A new name.
    #[serde(default)]
    pub name: Option<String>,
    /// New notes.
    #[serde(default)]
    pub notes: Option<String>,
    /// The draft: what has been filled in so far.
    #[serde(default)]
    pub settings: Option<serde_json::Value>,
    /// Optimistic concurrency token from the project snapshot being edited.
    #[serde(default)]
    pub expected_updated_at: Option<DateTime<Utc>>,
}

/// What running inside a project needs.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunRequest {
    /// What to call this attempt.
    #[serde(default)]
    pub label: String,
    /// The design request itself, in the engine's own shape.
    pub request: serde_json::Value,
}

/// A run and the project it changed, so the caller needs no second request.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RunAnswer {
    /// The saved run, whole.
    pub run: Run,
    /// The project as it now stands.
    pub project: Project,
}

/// The intentionally narrow public projection of a shared run.
///
/// `project_id` is absent by type rather than removed from a generic JSON value
/// after serialization. That makes the privacy boundary compile-visible and
/// prevents a serialization fallback from ever returning a misleading empty
/// success body.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SharedRunAnswer {
    id: String,
    label: String,
    request: serde_json::Value,
    result: serde_json::Value,
    created_at: DateTime<Utc>,
}

impl From<Run> for SharedRunAnswer {
    fn from(run: Run) -> Self {
        Self {
            id: run.id,
            label: run.label,
            request: run.request,
            result: run.result,
            created_at: run.created_at,
        }
    }
}

/// Public lifecycle projection for a durable execution job.
///
/// The persistence model also carries the immutable scientific request, owner
/// id and idempotency key because executors need them. Status polling does not.
/// Keeping those fields out of the HTTP type avoids repeatedly serializing
/// multi-MiB requests and makes the transport privacy boundary explicit.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RunJobAnswer {
    id: String,
    project_id: String,
    module_id: String,
    engine_id: String,
    request_fingerprint: String,
    label: String,
    run_id: Option<String>,
    status: String,
    stage: String,
    progress: serde_json::Value,
    error: Option<serde_json::Value>,
    created_at: DateTime<Utc>,
    started_at: Option<DateTime<Utc>>,
    finished_at: Option<DateTime<Utc>>,
    updated_at: DateTime<Utc>,
}

impl From<RunJobState> for RunJobAnswer {
    fn from(job: RunJobState) -> Self {
        Self {
            id: job.id,
            project_id: job.project_id,
            module_id: job.module_id,
            engine_id: job.engine_id,
            request_fingerprint: job.request_fingerprint,
            label: job.label,
            run_id: job.run_id,
            status: job.status,
            stage: job.stage,
            progress: job.progress,
            error: job.error,
            created_at: job.created_at,
            started_at: job.started_at,
            finished_at: job.finished_at,
            updated_at: job.updated_at,
        }
    }
}

async fn list(
    State(state): State<ProjectState>,
    user: CurrentUser,
) -> Result<Json<Vec<Project>>, ProjectApiError> {
    Ok(Json(state.projects.list(&user.user.id).await?))
}

async fn create(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Json(body): Json<NewProject>,
) -> Result<(StatusCode, Json<Project>), ProjectApiError> {
    // A newly created project must point at an assay this build actually
    // exposes. Imports are deliberately different: they may carry historical
    // module ids so old evidence remains readable after a catalogue change.
    if state.registry.profile(&body.module_id).is_err() {
        return Err(ProjectApiError(ProjectError::InvalidData(format!(
            "Unknown module id {:?}. Choose an assay from the current catalogue.",
            body.module_id
        ))));
    }
    let project = state
        .projects
        .create_with_data(
            &user.user.id,
            &body.name,
            &body.module_id,
            &body.notes,
            &body.settings,
        )
        .await?;
    Ok((StatusCode::CREATED, Json(project)))
}

async fn get_one(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path(id): Path<String>,
) -> Result<Json<Project>, ProjectApiError> {
    Ok(Json(state.projects.get(&user.user.id, &id).await?))
}

async fn change(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path(id): Path<String>,
    Json(body): Json<ProjectChange>,
) -> Result<Json<Project>, ProjectApiError> {
    Ok(Json(
        state
            .projects
            .update(
                &user.user.id,
                &id,
                body.name.as_deref(),
                body.notes.as_deref(),
                body.settings.as_ref(),
                body.expected_updated_at,
            )
            .await?,
    ))
}

/// Mint a link that shows this run to somebody with no account.
///
/// The plain token is in the response and nowhere else — it is not stored and
/// cannot be read back, so an interface that loses it has to mint another.
async fn share_run(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path((project, run)): Path<(String, String)>,
) -> Result<Json<serde_json::Value>, ProjectApiError> {
    let token = state
        .projects
        .share_run(&user.user.id, &project, &run)
        .await?;
    Ok(Json(serde_json::json!({ "token": token })))
}

/// Withdraw it.
async fn unshare_run(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path((project, run)): Path<(String, String)>,
) -> Result<StatusCode, ProjectApiError> {
    state
        .projects
        .unshare_run(&user.user.id, &project, &run)
        .await?;
    Ok(StatusCode::NO_CONTENT)
}

/// Whether a link exists, without saying what it is.
async fn share_status(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path((project, run)): Path<(String, String)>,
) -> Result<Json<serde_json::Value>, ProjectApiError> {
    let shared = state
        .projects
        .is_shared(&user.user.id, &project, &run)
        .await?;
    Ok(Json(serde_json::json!({ "shared": shared })))
}

/// One run, to whoever holds the link.
///
/// The only route here that takes no session: the token *is* the
/// authorisation. Three things follow from that and each is deliberate.
///
/// It returns the run alone — not who owns it, not the project around it, not
/// the runs beside it. Somebody handed a link to one result has one result.
///
/// It is never cached by anything shared. The response is one person's data
/// even though the caller is anonymous, and a proxy holding it would hand it to
/// the next caller of the same URL — which is only safe until the link is
/// withdrawn.
///
/// A token that matches nothing is a plain 404, the same answer a withdrawn
/// link gets. There is no way to tell "never existed" from "revoked", which is
/// what stops the endpoint being a way to test tokens.
async fn shared_run(
    State(state): State<ProjectState>,
    Path(token): Path<String>,
) -> Result<Response, ProjectApiError> {
    let run = SharedRunAnswer::from(state.projects.run_by_share(&token).await?);

    /*
     * The project id goes no further.
     *
     * It is a random UUID and useless on its own — every route that takes one
     * checks ownership first. What it does do is correlate: somebody sent two
     * links from the same project can see that they are siblings, which is a
     * fact about the sender's filing that they did not share. "One run and
     * nothing around it" has to mean this too. The response type above makes
     * that omission structural rather than relying on post-serialization
     * mutation.
     */
    Ok((
        [(header::CACHE_CONTROL, "no-store, private".to_owned())],
        Json(run),
    )
        .into_response())
}

/// Bring an export back in.
///
/// The document is taken as it was written by `export_everything`, so the two
/// are checked against each other rather than against a hand-written shape:
/// what comes out is what goes in. The format string is checked because a
/// future version could mean something different by the same field names, and
/// guessing at that would be worse than refusing.
async fn import_everything(
    State(state): State<ProjectState>,
    CurrentUser { user, .. }: CurrentUser,
    Json(document): Json<serde_json::Value>,
) -> Result<Json<pcr_projects::Imported>, ProjectApiError> {
    let format = document.get("format").and_then(serde_json::Value::as_str);
    if !matches!(format, Some(EXPORT_FORMAT | LEGACY_EXPORT_FORMAT)) {
        return Err(ProjectApiError(ProjectError::NotAnExport(format!(
            "This does not look like a {EXPORT_FORMAT} or {LEGACY_EXPORT_FORMAT} export. Choose the JSON file downloaded from the account page."
        ))));
    }
    if format == Some(EXPORT_FORMAT) {
        validate_v2_export_provenance(&document)?;
    }

    let projects: Vec<pcr_projects::Incoming> = serde_json::from_value(
        document.get("projects").cloned().unwrap_or_default(),
    )
    .map_err(|error| {
        ProjectApiError(ProjectError::NotAnExport(format!(
            "The export could not be read: {error}"
        )))
    })?;

    Ok(Json(state.projects.import(&user.id, &projects).await?))
}

/// The ceilings this account works inside.
///
/// Reported rather than left for somebody to discover by hitting one. Two of
/// them are not merely limits: passing the run ceiling *destroys* the oldest
/// run, and a person cannot be expected to weigh that against saving a new one
/// if nothing ever tells them the number.
///
/// Served from the constants themselves so the interface cannot quote a
/// different figure from the one the store enforces — which is exactly what
/// would happen the first time either was tuned.
async fn limits() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "maxProjectsPerUser": pcr_projects::MAX_PROJECTS_PER_USER,
        "maxRunsPerProject": pcr_projects::MAX_RUNS_PER_PROJECT,
        "maxAccountDataBytes": pcr_projects::MAX_ACCOUNT_DATA_BYTES,
        "maxNameLength": pcr_projects::MAX_NAME,
        "undoWindowDays": pcr_projects::Projects::UNDO_WINDOW_DAYS,
        "maxActiveRunJobsPerUser": pcr_storage::MAX_ACTIVE_RUN_JOBS_PER_USER,
        "maxRetainedRunJobsPerUser": pcr_storage::MAX_RETAINED_RUN_JOBS_PER_USER,
        "maxRunJobRequestBytes": pcr_storage::MAX_RUN_JOB_REQUEST_BYTES,
        "maxRunJobDataBytesPerUser": pcr_storage::MAX_RUN_JOB_DATA_BYTES_PER_USER,
        "runJobRetentionDays": pcr_storage::RUN_JOB_RETENTION_DAYS,
    }))
}

async fn remove(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path(id): Path<String>,
) -> Result<StatusCode, ProjectApiError> {
    state.projects.delete(&user.user.id, &id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// Bring back a project deleted within the undo window.
async fn restore(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path(id): Path<String>,
) -> Result<Json<Project>, ProjectApiError> {
    Ok(Json(state.projects.restore(&user.user.id, &id).await?))
}

async fn list_runs(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path(id): Path<String>,
) -> Result<Json<Vec<RunSummary>>, ProjectApiError> {
    Ok(Json(state.projects.runs(&user.user.id, &id).await?))
}

async fn get_run(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path((project, run)): Path<(String, String)>,
) -> Result<Json<Run>, ProjectApiError> {
    Ok(Json(
        state
            .projects
            .run_in_project(&user.user.id, &project, &run)
            .await?,
    ))
}

async fn remove_run(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path((project, run)): Path<(String, String)>,
) -> Result<StatusCode, ProjectApiError> {
    state
        .projects
        .delete_run(&user.user.id, &project, &run)
        .await?;
    Ok(StatusCode::NO_CONTENT)
}

fn execution_state(state: &ProjectState) -> pcr_application::jobs::JobExecutionState {
    pcr_application::jobs::JobExecutionState {
        projects: state.projects.clone(),
        storage: state.storage.clone(),
        registry: state.registry.clone(),
        gate: state.gate.clone(),
    }
}

/// Start an idempotent durable project design job.
async fn start_run_job(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path(id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<RunRequest>,
) -> Result<(StatusCode, Json<RunJobAnswer>), Response> {
    let project = state
        .projects
        .get(&user.user.id, &id)
        .await
        .map_err(|error| ProjectApiError(error).into_response())?;
    let engine_id = pcr_contracts::engine_for_module(&project.module_id).ok_or_else(|| {
        ApiError(CoreError::InvalidRequest(format!(
            "module {:?} has no canonical engine binding",
            project.module_id
        )))
        .into_response()
    })?;
    let fingerprint = pcr_projects::request_fingerprint(&project.module_id, &body.request);
    let key = idempotency_key(&headers).map_err(|error| error.into_response())?;
    let created = state
        .storage
        .create_run_job(pcr_storage::CreateRunJobInput {
            user_id: &user.user.id,
            project_id: &id,
            module_id: &project.module_id,
            engine_id,
            request_fingerprint: &fingerprint,
            idempotency_key: key.as_deref(),
            label: &body.label,
            request: &body.request,
        })
        .await
        .map_err(|error| StorageApiError(error).into_response())?;
    let status = if created.created {
        StatusCode::ACCEPTED
    } else {
        StatusCode::OK
    };
    if state.embedded_jobs && (created.created || created.job.status == "queued") {
        // Local development can still execute in-process. Production sets
        // embedded_jobs=false: PostgreSQL remains queued until pcr-runner
        // claims the row under an executor lease.
        pcr_application::jobs::spawn_run_job(
            execution_state(&state),
            user.user.id.clone(),
            created.job.clone(),
        );
    }
    Ok((status, Json(RunJobState::from(created.job).into())))
}

/// Read measured status/progress for one durable job.
async fn get_run_job(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path((project, job)): Path<(String, String)>,
) -> Result<Json<RunJobAnswer>, StorageApiError> {
    let job = state
        .storage
        .run_job_state(&user.user.id, &project, &job)
        .await?;
    Ok(Json(job.into()))
}

/// Request cancellation. Running subprocesses are killed/reaped; queued work
/// terminates before it can acquire worker capacity.
async fn cancel_run_job(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path((project, job)): Path<(String, String)>,
) -> Result<Json<RunJobAnswer>, StorageApiError> {
    let updated = state
        .storage
        .request_run_job_cancel(&user.user.id, &project, &job)
        .await?;
    if matches!(updated.status.as_str(), "cancel_requested" | "cancelled") {
        pcr_application::jobs::signal_local_cancellation(&user.user.id, &job);
    }
    Ok(Json(updated.into()))
}

/// Run a design inside a project and keep the result.
///
/// The project is read first, so an unknown id costs nothing; the engine runs
/// only once the project is known to be this person's.
async fn run_and_save(
    State(state): State<ProjectState>,
    user: CurrentUser,
    Path(id): Path<String>,
    Json(body): Json<RunRequest>,
) -> Result<Json<RunAnswer>, RunFailure> {
    // The project is read first, so an unknown id costs nothing; the engine
    // runs only once the project is known to be this person's.
    let project = state.projects.get(&user.user.id, &id).await?;

    // The same preparation the public endpoint uses, from the same function,
    // under the same gate: off the async threads and inside the worker ceiling.
    //
    // This used to call `engine.design` directly, which skipped both the assay
    // profile and `validate`. Every run anybody had ever saved was therefore
    // designed as generic PCR whatever module it was filed under — and a saved
    // run is the only kind anybody cites.
    let gate = state.gate.clone();
    let registry = state.registry.clone();
    let module_id = project.module_id.clone();
    let request = body.request.clone();
    let weight = pcr_contracts::resource_weight_for_module(&module_id).unwrap_or(1) as usize;
    let result = gate
        .run_weighted(weight, move || {
            crate::routes::design_for(&registry, &module_id, request)
        })
        .await?;

    // The run and the changed project are materialised inside the same
    // transaction as the save. Never read again after that commit: a transient
    // outage there would turn a successful save into an apparent failure and a
    // retry could create a duplicate run.
    let (run, project) = state
        .projects
        .save_run_with_project(&user.user.id, &id, &body.label, &body.request, &result)
        .await?;

    Ok(Json(RunAnswer { run, project }))
}

/// The project endpoints, ready to nest.
/// Everything this account holds, in one document.
///
/// Not a convenience. Somebody who cannot get their own work out of a service
/// is somebody the service has taken hostage, and a tool that asks scientists
/// to keep a year of designs in it owes them the door.
///
/// Deliberately the whole thing rather than a summary: the request that
/// produced each run is included alongside the result, so an export is enough
/// to reproduce a design elsewhere rather than only to read what it said. That
/// is the same argument the provenance block makes at the level of one run,
/// applied to the account.
async fn export_everything(
    State(state): State<ProjectState>,
    CurrentUser { user, .. }: CurrentUser,
) -> Result<Response, ProjectApiError> {
    let projects = state.projects.everything(&user.id).await?;

    let document = serde_json::json!({
        "exported_at": Utc::now(),
        "format": EXPORT_FORMAT,
        "account": {
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at,
        },
        "projects": projects
            .into_iter()
            .map(|(project, runs)| {
                serde_json::json!({
                    "id": project.id,
                    "name": project.name,
                    // Notes and settings were both missing here, and settings
                    // is where the draft lives — the sequence, the constraints,
                    // the reaction. A project that had been set up but not yet
                    // run therefore exported as a name and a date, with the
                    // one thing worth keeping left behind, under a note
                    // claiming this was everything.
                    "notes": project.notes,
                    "settings": project.settings,
                    "module_id": project.module_id,
                    "draft_schema_version": project.draft_schema_version,
                    "module_contract_version": project.module_contract_version,
                    "created_at": project.created_at,
                    "updated_at": project.updated_at,
                    "runs": runs,
                })
            })
            .collect::<Vec<_>>(),
        "note": concat!(
            "Every project on this account with its notes and its draft, and ",
            "every saved run including the request that produced each result. ",
            "Nothing here is a password or a recovery code: both are stored ",
            "hashed and cannot be exported."
        ),
    });

    // Materialise the exact wire representation before returning it. The live
    // account quota reserves framing/provenance headroom, but this final check
    // is the invariant that matters: every server-produced backup must fit the
    // same authenticated transport ceiling that restores it.
    let bytes = serde_json::to_vec(&document).map_err(|error| {
        ProjectApiError(ProjectError::Store(format!(
            "account export could not be serialized: {error}"
        )))
    })?;
    if bytes.len() > MAX_BACKUP_DOCUMENT_BYTES {
        return Err(ProjectApiError(ProjectError::StorageLimit(format!(
            "This account export is {} bytes, above the {}-byte restore ceiling. Remove old saved runs before exporting again.",
            bytes.len(),
            MAX_BACKUP_DOCUMENT_BYTES
        ))));
    }

    // Named with the date so two exports do not overwrite each other in a
    // downloads folder, and marked as an attachment so a browser saves it
    // rather than rendering a megabyte of JSON.
    let filename = format!("pcrstudio-export-{}.json", Utc::now().format("%Y-%m-%d"));

    Ok((
        [
            (
                header::CONTENT_TYPE,
                "application/json; charset=utf-8".to_owned(),
            ),
            (
                header::CONTENT_DISPOSITION,
                format!("attachment; filename=\"{filename}\""),
            ),
            // Somebody's whole account. Never in a shared cache.
            (header::CACHE_CONTROL, "no-store, private".to_owned()),
        ],
        bytes,
    )
        .into_response())
}

/// The shape of an export, so a reader can tell versions apart later.
const LEGACY_EXPORT_FORMAT: &str = "pcrstudio.export.v1";
const EXPORT_FORMAT: &str = "pcrstudio.export.v2";
/// Must stay aligned with the authenticated global body limit and the web
/// import guard. Export serializes first and refuses anything above this size,
/// making server-produced backups round-trip through the restore endpoint.
const MAX_BACKUP_DOCUMENT_BYTES: usize = pcr_contracts::MAX_BACKUP_DOCUMENT_BYTES;
const PROJECT_DESIGN_BODY_BYTES: usize = pcr_storage::MAX_RUN_JOB_REQUEST_BYTES + 512 * 1024;

fn validate_v2_export_provenance(document: &serde_json::Value) -> Result<(), ProjectApiError> {
    let projects = document
        .get("projects")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| {
            ProjectApiError(ProjectError::NotAnExport(
                "A v2 export must contain a projects array.".into(),
            ))
        })?;
    for project in projects {
        let object = project.as_object().ok_or_else(|| {
            ProjectApiError(ProjectError::NotAnExport(
                "Each v2 project must be an object.".into(),
            ))
        })?;
        if object
            .get("draft_schema_version")
            .and_then(serde_json::Value::as_i64)
            .is_none()
            || object
                .get("module_contract_version")
                .and_then(serde_json::Value::as_str)
                .is_none()
        {
            return Err(ProjectApiError(ProjectError::NotAnExport(
                "A v2 project is missing draft/module-contract provenance.".into(),
            )));
        }
    }
    Ok(())
}

/// Compatibility entry point for embedded development execution.
///
/// Production Linux deployments use the separate `pcr-runner` binary and do
/// not start this loop inside the HTTP process.
pub async fn job_recovery_loop(accounts: Accounts, registry: Registry) {
    pcr_application::jobs::job_recovery_loop(accounts, registry, std::time::Duration::from_secs(5))
        .await;
}

/// The one endpoint that answers without a session.
///
/// Its own function so that it is impossible to add a route to it by accident:
/// anything mounted here is public, and that should take a deliberate act.
pub fn shared_routes(accounts: Accounts, registry: Registry) -> Router {
    let pool = accounts.pool();
    let state = ProjectState {
        projects: Projects::new(pool.clone()),
        storage: FoundationStorage::new(pool),
        accounts,
        registry,
        gate: std::sync::Arc::new(crate::gate::Gate::shared()),
        embedded_jobs: false,
    };

    Router::new()
        .route(http_routes::SHARED_RUN, get(shared_run))
        .with_state(state)
}

/// The project endpoints, mounted under `/api/projects`.
pub fn routes(accounts: Accounts, registry: Registry) -> Router {
    routes_with_execution(accounts, registry, true)
}

/// Project routes with an explicit durable-job execution topology.
///
/// Production passes `embedded_jobs=false`, making the API enqueue-only for
/// durable work while `pcr-runner` owns claim/heartbeat/execution.
pub fn routes_with_execution(
    accounts: Accounts,
    registry: Registry,
    embedded_jobs: bool,
) -> Router {
    let pool = accounts.pool();
    let design_limiter = RateLimiter::with_shared_store(
        DESIGNS_PER_WINDOW,
        DESIGN_WINDOW,
        accounts.clone(),
        "design",
    );
    let state = ProjectState {
        projects: Projects::new(pool.clone()),
        storage: FoundationStorage::new(pool),
        accounts,
        registry,
        gate: std::sync::Arc::new(crate::gate::Gate::shared()),
        embedded_jobs,
    };

    let expensive = Router::new()
        .route(http_routes::JOBS_CREATE, post(start_run_job))
        .route(http_routes::PROJECT_DESIGN, post(run_and_save))
        .layer(DefaultBodyLimit::max(PROJECT_DESIGN_BODY_BYTES))
        .layer(axum::middleware::from_fn_with_state(
            design_limiter,
            crate::rate_limit::meter,
        ));

    Router::new()
        .route(http_routes::PROJECTS_LIST, get(list).post(create))
        .route(http_routes::PROJECT_GET, get(get_one).patch(change))
        .route(http_routes::PROJECT_DELETE, delete(remove))
        .route(http_routes::PROJECT_RESTORE, post(restore))
        .route(http_routes::RUNS_LIST, get(list_runs))
        .route(http_routes::RUN_GET, get(get_run).delete(remove_run))
        .route(
            http_routes::RUN_SHARE_GET,
            get(share_status).post(share_run).delete(unshare_run),
        )
        .route(
            http_routes::JOB_GET,
            get(get_run_job).delete(cancel_run_job),
        )
        .merge(expensive)
        // Not nested under a project: it is everything, across all of them.
        .route(http_routes::PROJECTS_EXPORT, get(export_everything))
        .route(http_routes::PROJECTS_IMPORT, post(import_everything))
        .route(http_routes::PROJECT_LIMITS, get(limits))
        .with_state(state)
}
