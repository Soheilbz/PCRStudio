-- Large sequence/FASTA documents are content-addressed once and referenced by
-- project drafts, durable jobs and immutable runs. The public/application
-- boundaries hydrate these references; JSONB therefore stays small without
-- changing the external request/project/run shapes.

ALTER TABLE sequence_assets
    ADD CONSTRAINT sequence_assets_id_user_unique UNIQUE (id, user_id),
    ADD CONSTRAINT sequence_assets_sha256_shape CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT sequence_assets_length_matches_content CHECK (length = char_length(content)),
    ADD CONSTRAINT sequence_assets_alphabet_shape CHECK (alphabet IN ('dna','rna','nucleotide-fasta'));

CREATE TABLE project_sequence_asset_refs (
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    field_path TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, field_path),
    FOREIGN KEY (project_id, user_id) REFERENCES projects_all (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id, user_id) REFERENCES sequence_assets (id, user_id) ON DELETE CASCADE,
    CHECK (length(field_path) BETWEEN 1 AND 2048)
);
CREATE INDEX project_sequence_asset_refs_asset_idx ON project_sequence_asset_refs (asset_id, user_id);

CREATE TABLE run_sequence_asset_refs (
    run_id TEXT NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    document_kind TEXT NOT NULL CHECK (document_kind IN ('request','result')),
    field_path TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, document_kind, field_path),
    FOREIGN KEY (project_id, user_id) REFERENCES projects_all (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, project_id) REFERENCES runs (id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id, user_id) REFERENCES sequence_assets (id, user_id) ON DELETE CASCADE,
    CHECK (length(field_path) BETWEEN 1 AND 2048)
);
CREATE INDEX run_sequence_asset_refs_asset_idx ON run_sequence_asset_refs (asset_id, user_id);

ALTER TABLE run_jobs ADD CONSTRAINT run_jobs_id_user_unique UNIQUE (id, user_id);
CREATE TABLE run_job_sequence_asset_refs (
    job_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    field_path TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, field_path),
    FOREIGN KEY (job_id, user_id) REFERENCES run_jobs (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id, user_id) REFERENCES sequence_assets (id, user_id) ON DELETE CASCADE,
    CHECK (length(field_path) BETWEEN 1 AND 2048)
);
CREATE INDEX run_job_sequence_asset_refs_asset_idx ON run_job_sequence_asset_refs (asset_id, user_id);
