-- Projects, and the runs kept inside them.
--
-- These tables live in the accounts crate's migration set because a database
-- has one migration history and this is that database. The code that uses them
-- is in `pcr-projects`, which is a separate crate for the ordinary reason:
-- accounts and design work are different domains and should not share a module.

CREATE TABLE projects (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    notes      TEXT NOT NULL DEFAULT '',
    -- Which assay this project designs for. Not a foreign key: the catalogue
    -- lives in the binary, not in the database, and a project must survive an
    -- assay being renamed rather than being deleted with it.
    module_id  TEXT NOT NULL,
    -- What has been filled in so far, step by step. A draft rather than a
    -- submission: somebody who closes the tab between the target and the
    -- constraints should find both still there.
    settings   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The list page orders by when a project was last touched.
CREATE INDEX projects_user_id_idx ON projects (user_id, updated_at DESC);

-- One completed design, kept whole.
--
-- The request and the result are both stored because a result without the
-- request that produced it cannot be reproduced, and reproducing it is the
-- point of keeping it at all.
CREATE TABLE runs (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    label      TEXT NOT NULL DEFAULT '',
    request    JSONB NOT NULL,
    result     JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX runs_project_id_idx ON runs (project_id, created_at DESC);
