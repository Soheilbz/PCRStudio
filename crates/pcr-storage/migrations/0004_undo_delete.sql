-- Deleting a project stops meaning the data is gone.
--
-- Before this, "Delete, with its runs" was a `DELETE`: one mis-aimed click and
-- a sequence, a draft and every saved run were unrecoverable. A second click to
-- confirm is not much protection when the second click is where the mistake
-- happens.
--
-- The shape here is deliberate. The obvious soft delete — add a column, then
-- add `AND deleted_at IS NULL` to every query — puts the correctness of the
-- feature in ten places and keeps it there: the eleventh query, written next
-- year by somebody who has never heard of the column, silently lists deleted
-- projects back to their owner.
--
-- So the table moves out of the way and a view takes its name. Every existing
-- query goes on saying `projects` and is now correct by construction, and a
-- query written later is correct without its author knowing why. The view is a
-- simple filter over one table, which Postgres makes automatically updatable,
-- so inserts and updates continue to work through it unchanged.
--
-- Only the two statements that must see deleted rows — deleting, and undoing —
-- name `projects_all`, and they are the two places where the distinction is
-- the entire point.

ALTER TABLE projects ADD COLUMN deleted_at TIMESTAMPTZ;

ALTER TABLE projects RENAME TO projects_all;
ALTER INDEX projects_user_id_idx RENAME TO projects_all_user_id_idx;

-- Runs keep pointing at `projects_all`, so a project's runs survive its
-- deletion and come back with it. That is what makes the undo whole rather
-- than a project shell with nothing in it.

CREATE VIEW projects AS
SELECT id, user_id, name, notes, module_id, settings, created_at, updated_at
FROM projects_all
WHERE deleted_at IS NULL;

-- Finding what is waiting to be purged, without scanning the live rows.
CREATE INDEX projects_all_deleted_at_idx
    ON projects_all (deleted_at)
    WHERE deleted_at IS NOT NULL;
