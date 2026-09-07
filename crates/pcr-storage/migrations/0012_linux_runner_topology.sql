-- Linux production topology: durable runner presence is database-observable so
-- API readiness cannot report healthy while every scientific executor is down.
CREATE TABLE IF NOT EXISTS runner_instances (
    id TEXT PRIMARY KEY,
    release_version TEXT NOT NULL,
    build_identity TEXT NOT NULL CHECK (build_identity ~ '^[0-9a-f]{64}$'),
    worker_capacity INTEGER NOT NULL CHECK (worker_capacity BETWEEN 1 AND 16),
    scientific_freeze_sha256 TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        scientific_freeze_sha256 IS NULL
        OR scientific_freeze_sha256 ~ '^[0-9a-f]{64}$'
    )
);

CREATE INDEX IF NOT EXISTS runner_instances_heartbeat_idx
    ON runner_instances (heartbeat_at DESC);
