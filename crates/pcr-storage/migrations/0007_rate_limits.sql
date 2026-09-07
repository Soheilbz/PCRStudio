CREATE TABLE rate_limit_buckets (
    namespace TEXT NOT NULL,
    bucket_key TEXT NOT NULL,
    window_started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    hits INTEGER NOT NULL CHECK (hits >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, bucket_key)
);

CREATE INDEX rate_limit_buckets_updated_at_idx ON rate_limit_buckets (updated_at);
