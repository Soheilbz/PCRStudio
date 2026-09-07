//! Inputs for idempotent durable-job creation.

/// Immutable inputs for creating one durable execution job.
pub struct CreateRunJobInput<'a> {
    /// Authenticated owner identifier.
    pub user_id: &'a str,
    /// Destination project identifier.
    pub project_id: &'a str,
    /// Canonical module identifier.
    pub module_id: &'a str,
    /// Canonical engine identifier.
    pub engine_id: &'a str,
    /// Fingerprint of the canonical request and contract identity.
    pub request_fingerprint: &'a str,
    /// Optional caller-provided idempotency key.
    pub idempotency_key: Option<&'a str>,
    /// User-visible job label.
    pub label: &'a str,
    /// Immutable scientific request payload.
    pub request: &'a serde_json::Value,
}

impl<'a> CreateRunJobInput<'a> {
    /// Borrow the fields in the order consumed by the transactional writer.
    pub(crate) fn parts(
        self,
    ) -> (
        &'a str,
        &'a str,
        &'a str,
        &'a str,
        &'a str,
        Option<&'a str>,
        &'a str,
        &'a serde_json::Value,
    ) {
        (
            self.user_id,
            self.project_id,
            self.module_id,
            self.engine_id,
            self.request_fingerprint,
            self.idempotency_key,
            self.label,
            self.request,
        )
    }
}
