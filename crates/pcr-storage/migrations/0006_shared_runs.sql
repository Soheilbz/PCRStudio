-- A link that shows one run to somebody without an account.
--
-- This is the only route in the application that serves somebody's data to a
-- caller who has proved nothing, so the shape is deliberate.
--
-- Opt-in per run, never per project and never by default. Sharing a project
-- would mean sharing every future run in it too, including ones not yet made.
--
-- Only the hash is stored, exactly as with a session token: the link exists in
-- plain text once, on its way to the person who asked for it. A database dump
-- yields no working links.
--
-- Revocable, and revoking is a delete rather than a flag — a revoked link that
-- still has a row is a link somebody has to reason about later.
ALTER TABLE runs ADD COLUMN share_hash TEXT UNIQUE;
ALTER TABLE runs ADD COLUMN shared_at TIMESTAMPTZ;

-- The lookup is by hash and nothing else, so it is the only index worth having.
CREATE INDEX runs_share_hash_idx ON runs (share_hash) WHERE share_hash IS NOT NULL;
