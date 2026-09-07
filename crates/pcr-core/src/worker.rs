//! Domain port for scientific execution.
//!
//! The domain core owns only this call contract. Process spawning, Python
//! selection, pipe draining, cancellation and IPC transport belong to the
//! application/infrastructure layer and are injected through [`ScientificWorker`].

use std::{fmt, sync::Arc};

use crate::error::{CoreError, Result};

/// Port implemented by a scientific execution adapter outside the domain core.
pub trait ScientificWorker: Send + Sync + 'static {
    /// Execute one versioned scientific command.
    ///
    /// # Errors
    /// Returns a domain error translated by the infrastructure adapter.
    fn call(&self, command: &str, request: &serde_json::Value) -> Result<serde_json::Value>;
}

/// Cloneable domain handle to a scientific execution port.
#[derive(Clone)]
pub struct Worker(Arc<dyn ScientificWorker>);

impl fmt::Debug for Worker {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.debug_struct("Worker").finish_non_exhaustive()
    }
}

impl Default for Worker {
    fn default() -> Self {
        Self::unbound()
    }
}

impl Worker {
    /// Bind the domain to an application/infrastructure execution adapter.
    #[must_use]
    pub fn from_port(port: impl ScientificWorker) -> Self {
        Self(Arc::new(port))
    }

    /// Build a metadata-only worker. Any attempted scientific call fails closed.
    ///
    /// This is intentionally the default used by catalogue-only domain tests;
    /// production transports must inject an execution adapter explicitly.
    #[must_use]
    pub fn unbound() -> Self {
        Self::from_port(UnboundScientificWorker)
    }

    /// Execute one versioned worker command through the injected port.
    ///
    /// # Errors
    /// Propagates the adapter's domain error.
    pub fn call(&self, command: &str, request: &serde_json::Value) -> Result<serde_json::Value> {
        self.0.call(command, request)
    }
}

#[derive(Debug)]
struct UnboundScientificWorker;

impl ScientificWorker for UnboundScientificWorker {
    fn call(&self, _command: &str, _request: &serde_json::Value) -> Result<serde_json::Value> {
        Err(CoreError::ToolFailed(
            "scientific execution adapter is not bound to this domain registry".to_owned(),
        ))
    }
}
