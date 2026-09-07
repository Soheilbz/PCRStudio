//! Errors that cross the boundary out of the core.
//!
//! Every variant is serialisable so the layers above can hand it on unchanged
//! and branch on `kind` without parsing prose.

use serde::{Deserialize, Serialize};

/// A failure raised by the core or by one of its engines.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, thiserror::Error)]
#[serde(tag = "kind", content = "detail", rename_all = "camelCase")]
pub enum CoreError {
    /// No assay is registered under the requested id.
    #[error("no assay is registered under the id `{0}`")]
    UnknownProfile(String),

    /// Two assays claimed the same id; registration is rejected.
    #[error("an assay is already registered under the id `{0}`")]
    DuplicateProfile(String),

    /// An assay names an engine this build does not have.
    #[error("{0}")]
    UnknownEngine(String),

    /// An assay asks for a modifier its engine does not accept.
    ///
    /// Raised while the registry is built, so an impossible combination stops
    /// the process rather than surprising somebody mid-run.
    #[error("{0}")]
    IncompatibleModifier(String),

    /// The request did not satisfy the engine's input contract.
    #[error("invalid request: {0}")]
    InvalidRequest(String),

    /// The engine exists but has no implementation yet.
    #[error("the `{0}` engine is named but not written yet")]
    NotImplemented(String),

    /// An engine's worker could not be started, died, or answered nonsense.
    ///
    /// Distinct from `InvalidRequest` on purpose: this one is never the
    /// caller's fault, so it must not be reported as a bad request and must
    /// not suggest they change what they asked for.
    #[error("the design tool failed: {0}")]
    ToolFailed(String),

    /// The instance is already carrying its bounded worker workload.
    ///
    /// This is distinct from a worker failure: retrying later is the correct
    /// response, and a 503 lets a proxy shed the request instead of holding
    /// thousands of async tasks in an unbounded queue.
    #[error("the design service is busy: {0}")]
    WorkerBusy(String),

    /// The running scientific job was explicitly cancelled by its caller.
    #[error("the design request was cancelled")]
    Cancelled,
}

/// Result alias used throughout the core.
pub type Result<T> = std::result::Result<T, CoreError>;
