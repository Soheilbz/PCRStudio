//! Machine-readable HTTP error contract for PCRStudio.
//!
//! Every error response has stable `code`/`kind` fields, an optional field and
//! execution stage, retryability, and the request id already propagated in the
//! response headers.  Internal diagnostics are logged and redacted from 5xx
//! response detail.

use axum::http::{Request, StatusCode};
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use axum::Json;
use pcr_core::CoreError;
use serde::Serialize;
use tracing::Instrument;

tokio::task_local! {
    static REQUEST_ID: Option<String>;
}

/// Stable machine-readable API error body.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ErrorBody {
    /// Stable code suitable for UI branching and telemetry aggregation.
    pub code: &'static str,
    /// Compatibility vocabulary for existing clients.
    pub kind: &'static str,
    /// Human-readable explanation safe to display.
    pub detail: String,
    /// Input field that owns the issue, when known.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub field_path: Option<String>,
    /// Processing stage that raised the issue, when known.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stage: Option<&'static str>,
    /// Whether a caller may reasonably retry the same request later.
    pub retryable: bool,
    /// Correlation id matching the `x-request-id` response header.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
}

/// Capture the request id minted by the outer request-id layer for the whole
/// handler task, allowing error responders deep in crates to include it without
/// passing transport metadata through scientific APIs.
pub async fn request_context(request: Request<axum::body::Body>, next: Next) -> Response {
    let request_id = request
        .headers()
        .get("x-request-id")
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned);
    let span = tracing::info_span!(
        "http_request",
        request_id = request_id.as_deref().unwrap_or("unknown")
    );
    REQUEST_ID
        .scope(request_id, next.run(request).instrument(span))
        .await
}

/// Build the common error body from any transport vocabulary.
#[must_use]
pub fn body(
    code: &'static str,
    kind: &'static str,
    detail: impl Into<String>,
    field_path: Option<String>,
    stage: Option<&'static str>,
    retryable: bool,
) -> ErrorBody {
    ErrorBody {
        code,
        kind,
        detail: detail.into(),
        field_path,
        stage,
        retryable,
        request_id: REQUEST_ID.try_with(Clone::clone).ok().flatten(),
    }
}

/// A `CoreError` on its way out over HTTP.
#[derive(Debug)]
pub struct ApiError(pub CoreError);

impl From<CoreError> for ApiError {
    fn from(error: CoreError) -> Self {
        Self(error)
    }
}

impl ApiError {
    pub(crate) fn contract(&self) -> (StatusCode, &'static str, &'static str, &'static str, bool) {
        match self.0 {
            CoreError::UnknownProfile(_) => (
                StatusCode::NOT_FOUND,
                "PROFILE_NOT_FOUND",
                "unknownProfile",
                "validation",
                false,
            ),
            CoreError::InvalidRequest(_) => (
                StatusCode::BAD_REQUEST,
                "INVALID_REQUEST",
                "invalidRequest",
                "validation",
                false,
            ),
            CoreError::NotImplemented(_) => (
                StatusCode::NOT_IMPLEMENTED,
                "CAPABILITY_NOT_IMPLEMENTED",
                "notImplemented",
                "dispatch",
                false,
            ),
            CoreError::DuplicateProfile(_) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "DUPLICATE_PROFILE",
                "duplicateProfile",
                "registry",
                false,
            ),
            CoreError::UnknownEngine(_) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "UNKNOWN_ENGINE",
                "unknownEngine",
                "registry",
                false,
            ),
            CoreError::IncompatibleModifier(_) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "INCOMPATIBLE_MODIFIER",
                "incompatibleModifier",
                "registry",
                false,
            ),
            CoreError::ToolFailed(_) => (
                StatusCode::BAD_GATEWAY,
                "SCIENTIFIC_TOOL_FAILED",
                "toolFailed",
                "execution",
                true,
            ),
            CoreError::WorkerBusy(_) => (
                StatusCode::SERVICE_UNAVAILABLE,
                "WORKER_CAPACITY_EXHAUSTED",
                "workerBusy",
                "queue",
                true,
            ),
            CoreError::Cancelled => (
                StatusCode::CONFLICT,
                "REQUEST_CANCELLED",
                "cancelled",
                "execution",
                false,
            ),
        }
    }

    pub(crate) fn safe_detail(&self, status: StatusCode) -> String {
        if status.is_server_error() {
            match self.0 {
                CoreError::WorkerBusy(_) => {
                    "the design service is at capacity; try again shortly".to_owned()
                }
                _ => "this build could not complete the request; try again in a moment".to_owned(),
            }
        } else {
            match &self.0 {
                CoreError::Cancelled => "the running design was cancelled".to_owned(),
                other => other.to_string(),
            }
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, code, kind, stage, retryable) = self.contract();
        if status.is_server_error() {
            if matches!(&self.0, CoreError::WorkerBusy(_)) {
                tracing::warn!(error = %self.0, code, "design request refused");
            } else {
                tracing::error!(error = %self.0, code, "request failed");
            }
        }
        let detail = self.safe_detail(status);
        let mut response = (
            status,
            Json(body(code, kind, detail, None, Some(stage), retryable)),
        )
            .into_response();
        if retryable && matches!(status, StatusCode::SERVICE_UNAVAILABLE) {
            response.headers_mut().insert(
                axum::http::header::RETRY_AFTER,
                axum::http::HeaderValue::from_static("5"),
            );
        }
        response
    }
}
