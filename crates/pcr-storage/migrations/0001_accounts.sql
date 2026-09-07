-- Users and their sessions.

CREATE TABLE users (
    id               TEXT PRIMARY KEY,
    -- Kept as typed, for addressing the person.
    email            TEXT NOT NULL,
    -- Lowercased and trimmed. Uniqueness is enforced here, so the same address
    -- in a different case cannot be registered twice.
    email_normalised TEXT NOT NULL UNIQUE,
    display_name     TEXT NOT NULL,
    password_hash    TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The token itself is never stored, only its SHA-256. A dump of this table
-- therefore does not hand anyone a working session.
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Signing out everywhere, and deleting an account, both filter by user.
CREATE INDEX sessions_user_id_idx ON sessions (user_id);
-- The periodic purge filters by expiry.
CREATE INDEX sessions_expires_at_idx ON sessions (expires_at);
