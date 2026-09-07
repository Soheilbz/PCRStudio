-- Account roles are deliberately small and closed: every account is a user
-- unless an operator explicitly promotes it to admin.

ALTER TABLE users
    ADD COLUMN role TEXT NOT NULL DEFAULT 'user';

ALTER TABLE users
    ADD CONSTRAINT users_role_check CHECK (role IN ('user', 'admin'));

CREATE INDEX users_admin_role_idx ON users (role) WHERE role = 'admin';
