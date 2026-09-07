//! Shared scientific-runtime preflight used by HTTP readiness and runners.
//!
//! Keeping this policy in the application layer prevents the API transport and
//! the dedicated runner from independently interpreting the worker's toolchain
//! payload.  A release therefore has one definition of "scientifically ready".

use pcr_core::{CoreError, ScientificWorker, Worker};

/// Infrastructure adapter that binds the domain worker port to the supervised
/// local scientific process client.
#[derive(Debug, Clone)]
pub struct ProcessScientificWorker {
    inner: pcr_worker_client::Worker,
}

impl ProcessScientificWorker {
    /// Snapshot the configured scientific interpreter and timeout policy.
    #[must_use]
    pub fn from_env() -> Self {
        Self {
            inner: pcr_worker_client::Worker::from_env(),
        }
    }

    /// Bind an explicit interpreter, primarily for integration tests.
    #[must_use]
    pub fn with_python(python: impl Into<String>) -> Self {
        Self {
            inner: pcr_worker_client::Worker::new(python),
        }
    }
}

impl ScientificWorker for ProcessScientificWorker {
    fn call(
        &self,
        command: &str,
        request: &serde_json::Value,
    ) -> pcr_core::Result<serde_json::Value> {
        self.inner
            .call(command, request)
            .map_err(translate_worker_error)
    }
}

fn translate_worker_error(error: pcr_worker_client::WorkerClientError) -> CoreError {
    match error {
        pcr_worker_client::WorkerClientError::InvalidRequest(detail) => {
            CoreError::InvalidRequest(detail)
        }
        pcr_worker_client::WorkerClientError::NotImplemented(detail) => {
            CoreError::NotImplemented(detail)
        }
        pcr_worker_client::WorkerClientError::ToolFailed(detail) => CoreError::ToolFailed(detail),
        pcr_worker_client::WorkerClientError::Cancelled => CoreError::Cancelled,
    }
}

/// Domain worker handle backed by the production process adapter.
#[must_use]
pub fn worker_from_env() -> Worker {
    Worker::from_port(ProcessScientificWorker::from_env())
}

/// Domain worker handle backed by one explicit Python interpreter.
#[must_use]
pub fn worker_with_python(python: impl Into<String>) -> Worker {
    Worker::from_port(ProcessScientificWorker::with_python(python))
}

/// Build the shipped registry with its production scientific execution adapter.
///
/// # Errors
/// Propagates catalogue/registry consistency failures.
pub fn registry_from_env() -> pcr_core::Result<pcr_core::Registry> {
    pcr_core::default_registry_with_worker(worker_from_env())
}

/// Prove the Python worker can start, import the scientific package and answer
/// a cheap versioned command.
///
/// # Errors
/// Returns a redacted operational string when the worker cannot answer.
pub fn probe_design_worker(worker: &Worker) -> Result<(), String> {
    worker
        .call("presets", &serde_json::json!({}))
        .map(|_| ())
        .map_err(|error| error.to_string())
}

/// Validate the canonical `toolchain` worker response.
///
/// Required generation-1 tools must be available, match their version
/// contracts and report no warnings; optional/reference-only tools do not make
/// the whole host unavailable. Strict scientific execution must also be ready.
///
/// # Errors
/// Returns a compact operational description of missing/mismatched authority.
pub fn validate_toolchain_payload(value: &serde_json::Value) -> Result<(), String> {
    let tools = value
        .pointer("/toolchain/tools")
        .and_then(serde_json::Value::as_object)
        .ok_or_else(|| "toolchain probe returned no tool status map".to_owned())?;

    let mut missing = Vec::new();
    for (id, status) in tools {
        let readiness_requirement = status
            .get("readiness_requirement")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("optional");
        if readiness_requirement != "required" {
            continue;
        }
        let available = status
            .get("available")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false);
        let version_ok = status
            .get("version_matches_contract")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false);
        let warnings_empty = status
            .get("warnings")
            .and_then(serde_json::Value::as_array)
            .is_some_and(Vec::is_empty);
        if !available || !version_ok || !warnings_empty {
            missing.push(id.as_str());
        }
    }

    let strict_execution_ready = value
        .pointer("/toolchain/strict_execution/ready")
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false);
    if !strict_execution_ready {
        missing.push("strict scientific execution contract");
    }

    if missing.is_empty() {
        Ok(())
    } else {
        Err(format!(
            "generation-1 scientific toolchain is incomplete or mismatched: {}",
            missing.join(", ")
        ))
    }
}

/// Probe and validate the full strict scientific toolchain through the worker.
///
/// # Errors
/// Returns an operational description when the worker command fails or the
/// returned toolchain contract is not ready.
pub fn probe_scientific_toolchain(worker: &Worker) -> Result<(), String> {
    worker
        .call("toolchain", &serde_json::json!({}))
        .map_err(|error| error.to_string())
        .and_then(|value| validate_toolchain_payload(&value))
}

/// Run the two startup checks a dedicated runner must pass before advertising
/// itself in PostgreSQL.
///
/// # Errors
/// Returns the first failed worker/toolchain probe.
pub fn preflight_runner(worker: &Worker) -> Result<(), String> {
    probe_design_worker(worker)?;
    probe_scientific_toolchain(worker)
}

#[cfg(test)]
mod tests {
    use super::validate_toolchain_payload;

    #[test]
    fn optional_missing_tool_does_not_make_global_readiness_fail() {
        let value = serde_json::json!({
            "toolchain": {
                "tools": {
                    "required": {
                        "readiness_requirement": "required",
                        "available": true,
                        "version_matches_contract": true,
                        "warnings": []
                    },
                    "reference": {
                        "readiness_requirement": "optional",
                        "available": false,
                        "version_matches_contract": false,
                        "warnings": ["not installed"]
                    }
                },
                "strict_execution": {"ready": true}
            }
        });
        assert!(validate_toolchain_payload(&value).is_ok());
    }

    #[test]
    fn required_warning_or_non_strict_execution_fails_closed() {
        let value = serde_json::json!({
            "toolchain": {
                "tools": {
                    "blast": {
                        "readiness_requirement": "required",
                        "available": true,
                        "version_matches_contract": true,
                        "warnings": ["database fingerprint mismatch"]
                    }
                },
                "strict_execution": {"ready": false}
            }
        });
        let error = validate_toolchain_payload(&value).expect_err("must fail closed");
        assert!(error.contains("blast"));
        assert!(error.contains("strict scientific execution contract"));
    }
}
