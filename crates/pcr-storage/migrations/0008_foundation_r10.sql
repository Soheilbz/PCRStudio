-- Foundation R10: explicit schema/version identity, immutable derived run
-- summaries, execution jobs, sequence assets, attachments and qualification
-- evidence. Historical request/result JSON is never rewritten.

DROP VIEW projects;

ALTER TABLE projects_all ADD COLUMN draft_schema_version INTEGER;
UPDATE projects_all SET draft_schema_version = 1 WHERE draft_schema_version IS NULL;
ALTER TABLE projects_all ALTER COLUMN draft_schema_version SET DEFAULT 2;
ALTER TABLE projects_all ALTER COLUMN draft_schema_version SET NOT NULL;

ALTER TABLE projects_all ADD COLUMN module_contract_version TEXT;
UPDATE projects_all SET module_contract_version = 'R9' WHERE module_contract_version IS NULL;
ALTER TABLE projects_all ALTER COLUMN module_contract_version SET DEFAULT '2.0.0';
ALTER TABLE projects_all ALTER COLUMN module_contract_version SET NOT NULL;

CREATE VIEW projects AS
SELECT id, user_id, name, notes, module_id, settings, draft_schema_version,
       module_contract_version, created_at, updated_at
FROM projects_all
WHERE deleted_at IS NULL;

ALTER TABLE runs ADD COLUMN request_schema_version INTEGER;
UPDATE runs SET request_schema_version = 1 WHERE request_schema_version IS NULL;
ALTER TABLE runs ALTER COLUMN request_schema_version SET DEFAULT 2;
ALTER TABLE runs ALTER COLUMN request_schema_version SET NOT NULL;

ALTER TABLE runs ADD COLUMN result_schema_version INTEGER;
UPDATE runs SET result_schema_version = 2 WHERE result_schema_version IS NULL;
ALTER TABLE runs ALTER COLUMN result_schema_version SET DEFAULT 3;
ALTER TABLE runs ALTER COLUMN result_schema_version SET NOT NULL;

ALTER TABLE runs ADD COLUMN module_contract_version TEXT;
UPDATE runs SET module_contract_version = 'R9' WHERE module_contract_version IS NULL;
ALTER TABLE runs ALTER COLUMN module_contract_version SET DEFAULT '2.0.0';
ALTER TABLE runs ALTER COLUMN module_contract_version SET NOT NULL;

ALTER TABLE runs ADD COLUMN toolchain_fingerprint TEXT;
ALTER TABLE runs ADD COLUMN run_fingerprint TEXT;
ALTER TABLE runs ADD COLUMN engine_id TEXT;
ALTER TABLE runs ADD COLUMN module_id TEXT;
ALTER TABLE runs ADD COLUMN result_count BIGINT;
ALTER TABLE runs ADD COLUMN result_unit TEXT;
ALTER TABLE runs ADD COLUMN target_name TEXT;

UPDATE runs r
SET module_id = p.module_id
FROM projects_all p
WHERE p.id = r.project_id AND r.module_id IS NULL;

UPDATE runs
SET result_count = CASE
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'sets') = 'array' THEN jsonb_array_length(result -> 'sets')
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'pairs') = 'array' THEN jsonb_array_length(result -> 'pairs')
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'assays') = 'array' THEN jsonb_array_length(result -> 'assays')
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'tiles') = 'array' THEN jsonb_array_length(result -> 'tiles')
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'primers') = 'array' THEN jsonb_array_length(result -> 'primers')
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'junctions') = 'array' THEN jsonb_array_length(result -> 'junctions')
      ELSE 0 END
WHERE result_count IS NULL;

UPDATE runs
SET result_unit = CASE
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'sets') = 'array' THEN 'set'
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'pairs') = 'array' THEN 'pair'
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'assays') = 'array' THEN 'assay'
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'tiles') = 'array' THEN 'tile'
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'primers') = 'array' THEN 'primer'
      WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'junctions') = 'array' THEN 'junction'
      ELSE 'result' END
WHERE result_unit IS NULL;

UPDATE runs
SET target_name = COALESCE(
  CASE WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result -> 'target') = 'object'
       THEN result -> 'target' ->> 'name' END,
  ''
)
WHERE target_name IS NULL;

ALTER TABLE runs ALTER COLUMN result_count SET DEFAULT 0;
ALTER TABLE runs ALTER COLUMN result_count SET NOT NULL;
ALTER TABLE runs ALTER COLUMN result_unit SET DEFAULT 'result';
ALTER TABLE runs ALTER COLUMN result_unit SET NOT NULL;
ALTER TABLE runs ALTER COLUMN target_name SET DEFAULT '';
ALTER TABLE runs ALTER COLUMN target_name SET NOT NULL;

CREATE INDEX runs_fingerprint_idx ON runs (run_fingerprint) WHERE run_fingerprint IS NOT NULL;
CREATE INDEX runs_module_engine_idx ON runs (module_id, engine_id, created_at DESC);

CREATE TABLE run_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    project_id TEXT REFERENCES projects_all (id) ON DELETE CASCADE,
    module_id TEXT NOT NULL,
    engine_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    idempotency_key TEXT,
    label TEXT NOT NULL DEFAULT '',
    request JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_id TEXT REFERENCES runs (id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','cancel_requested','cancelled','completed','failed')),
    stage TEXT NOT NULL DEFAULT 'queued',
    progress JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX run_jobs_user_status_idx ON run_jobs (user_id, status, updated_at DESC);
CREATE INDEX run_jobs_fingerprint_idx ON run_jobs (request_fingerprint, created_at DESC);
CREATE UNIQUE INDEX run_jobs_idempotency_idx
    ON run_jobs (user_id, project_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE sequence_assets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL,
    length BIGINT NOT NULL CHECK (length >= 0),
    alphabet TEXT NOT NULL DEFAULT 'dna',
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, sha256)
);
CREATE INDEX sequence_assets_user_created_idx ON sequence_assets (user_id, created_at DESC);

CREATE TABLE attachments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    project_id TEXT REFERENCES projects_all (id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs (id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    byte_length BIGINT NOT NULL CHECK (byte_length >= 0),
    storage_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, sha256, storage_key)
);
CREATE INDEX attachments_run_idx ON attachments (run_id, created_at DESC);

CREATE TABLE assay_qualifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects_all (id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    evidence_schema_version INTEGER NOT NULL DEFAULT 1,
    sop_id TEXT,
    instrument_identity TEXT,
    kit_lot TEXT,
    operator_ref TEXT,
    experiment_date DATE,
    matrix TEXT,
    lod_summary JSONB,
    reproducibility_summary JSONB,
    acceptance_criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, id)
);
CREATE INDEX assay_qualifications_run_idx ON assay_qualifications (run_id, created_at DESC);
