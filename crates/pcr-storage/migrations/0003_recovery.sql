-- A way back in after a forgotten password, without an email server.
--
-- This application deliberately asks for no verification email: an address and
-- a password, and the work is yours. That choice has a consequence nobody
-- notices until it bites — with no address to send to, a forgotten password is
-- an account that can never be opened again, and every project in it is gone.
--
-- A recovery code closes that without reintroducing email. It is shown once, at
-- sign-up, and stored the same way a password is: Argon2, so a dump of this
-- table hands nobody a way in. Presenting it proves the same thing an email
-- link would — that you are the person who made the account — and it does so
-- without a mail server, a queue, a deliverability problem, or a third party
-- who gets to read the address.
--
-- Nullable, because accounts made before this migration have none. They are
-- offered one the next time they sign in rather than being locked out of the
-- feature or forced through it.

ALTER TABLE users ADD COLUMN recovery_hash TEXT;

-- When the current code was issued, so the interface can say how old it is and
-- an account made before this existed can be told it has none.
ALTER TABLE users ADD COLUMN recovery_issued_at TIMESTAMPTZ;

-- Attempts are counted per account rather than per caller.
--
-- The rate limiter in the server keys on the caller's address, which is the
-- right shape for a password: an attacker guessing one password from many
-- addresses is still guessing one password. A recovery code is different — it
-- is high-entropy, so the only realistic attack is many attempts against one
-- account, and spreading those across addresses defeats a per-caller ceiling
-- entirely. This counter is what a distributed attempt cannot spread.
ALTER TABLE users ADD COLUMN recovery_attempts INTEGER NOT NULL DEFAULT 0;

-- When the counter above was last reset, so the lockout expires rather than
-- being permanent. A permanent one turns a nuisance into a denial of service
-- against the account's real owner.
ALTER TABLE users ADD COLUMN recovery_attempted_at TIMESTAMPTZ;
