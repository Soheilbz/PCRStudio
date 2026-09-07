//! Inputs for atomically persisting a completed durable job.

/// Inputs for atomically persisting one completed durable-job result.
pub struct SaveRunForJobInput<'a> {
    /// Authenticated owner identifier.
    pub user_id: &'a str,
    /// Destination project identifier.
    pub project_id: &'a str,
    /// Durable job identifier.
    pub job_id: &'a str,
    /// Executor lease identity.
    pub executor_id: &'a str,
    /// User-visible run label.
    pub label: &'a str,
    /// Immutable scientific request payload.
    pub request: &'a serde_json::Value,
    /// Completed scientific result payload.
    pub result: &'a serde_json::Value,
    /// Measured progress snapshot at completion.
    pub progress: &'a serde_json::Value,
}

impl<'a> SaveRunForJobInput<'a> {
    /// Borrow the fields in the order consumed by the transactional writer.
    pub(crate) fn parts(
        self,
    ) -> (
        &'a str,
        &'a str,
        &'a str,
        &'a str,
        &'a str,
        &'a serde_json::Value,
        &'a serde_json::Value,
        &'a serde_json::Value,
    ) {
        (
            self.user_id,
            self.project_id,
            self.job_id,
            self.executor_id,
            self.label,
            self.request,
            self.result,
            self.progress,
        )
    }
}
