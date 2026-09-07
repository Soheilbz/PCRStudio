-- Production integrity: durable-job ownership/correlation and cross-replica
-- external-service scheduling. Staged NOT VALID constraints keep upgrades
-- diagnosable while enforcing the invariants for all new writes immediately.

CREATE TABLE external_service_slots (
    namespace TEXT PRIMARY KEY,
    next_allowed_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(namespace) BETWEEN 1 AND 64)
);

ALTER TABLE run_jobs
    ADD CONSTRAINT run_jobs_project_required
    CHECK (project_id IS NOT NULL) NOT VALID;
ALTER TABLE run_jobs
    ADD CONSTRAINT run_jobs_project_owner_fk
    FOREIGN KEY (project_id, user_id) REFERENCES projects_all (id, user_id)
    ON DELETE CASCADE NOT VALID;
ALTER TABLE run_jobs
    ADD CONSTRAINT run_jobs_run_project_fk
    FOREIGN KEY (run_id, project_id) REFERENCES runs (id, project_id)
    ON DELETE SET NULL (run_id) NOT VALID;
