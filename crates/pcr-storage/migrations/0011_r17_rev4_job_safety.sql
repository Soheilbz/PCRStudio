-- R17 current job-safety migration closes durable-job crash recovery/resource bounds and strengthens
-- relational ownership for Foundation attachment/qualification records.
ALTER TABLE run_jobs ADD COLUMN IF NOT EXISTS executor_id TEXT;
ALTER TABLE run_jobs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS run_jobs_lease_idx
    ON run_jobs (status, lease_expires_at)
    WHERE status IN ('running','cancel_requested');
CREATE INDEX IF NOT EXISTS run_jobs_queued_created_idx
    ON run_jobs (created_at) WHERE status='queued';

-- Earlier durable jobs could persist raw internal error strings. Existing failed
-- rows are operational envelopes (not scientific history), so redact them on
-- upgrade rather than allowing a legacy diagnostic to bypass the current API/UI
-- error boundary. New failures are stored redacted by the server.
UPDATE run_jobs
SET error = jsonb_build_object(
        'code', COALESCE(error ->> 'code', 'LEGACY_JOB_FAILED'),
        'kind', 'legacyFailure',
        'detail', 'This design job failed under an earlier server revision. Retry it to obtain a current diagnostic.',
        'retryable', true
    ),
    updated_at = now()
WHERE status='failed' AND error IS NOT NULL;

-- Composite unique indexes let new foreign keys bind ownership/correlation, not
-- merely existence of each independent id. NOT VALID preserves upgradeability
-- for historical databases while enforcing the invariant on all new writes.
CREATE UNIQUE INDEX IF NOT EXISTS projects_all_id_user_uidx ON projects_all (id, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS runs_id_project_uidx ON runs (id, project_id);

ALTER TABLE attachments
    ADD CONSTRAINT attachments_run_requires_project
    CHECK (run_id IS NULL OR project_id IS NOT NULL) NOT VALID;
ALTER TABLE attachments
    ADD CONSTRAINT attachments_project_owner_fk
    FOREIGN KEY (project_id, user_id) REFERENCES projects_all (id, user_id)
    ON DELETE CASCADE NOT VALID;
ALTER TABLE attachments
    ADD CONSTRAINT attachments_run_project_fk
    FOREIGN KEY (run_id, project_id) REFERENCES runs (id, project_id)
    ON DELETE CASCADE NOT VALID;

ALTER TABLE assay_qualifications
    ADD CONSTRAINT assay_qualifications_project_owner_fk
    FOREIGN KEY (project_id, user_id) REFERENCES projects_all (id, user_id)
    ON DELETE CASCADE NOT VALID;
ALTER TABLE assay_qualifications
    ADD CONSTRAINT assay_qualifications_run_project_fk
    FOREIGN KEY (run_id, project_id) REFERENCES runs (id, project_id)
    ON DELETE CASCADE NOT VALID;
