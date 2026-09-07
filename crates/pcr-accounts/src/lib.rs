//! Accounts for PCRStudio: who someone is, and whether they are still signed in.
//!
//! Backed by PostgreSQL. The row counts here are small, but the write path has
//! to stay open to more than one server process, and that is the thing a
//! single-file database cannot give back once it is needed.
//!
//! Nothing in this crate knows about HTTP; `pcr-server` puts it on the network.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod error;
pub mod password;
pub mod recovery;
pub mod session;

use std::time::Duration as StdDuration;

use chrono::Duration;
use serde::{Deserialize, Serialize};
use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};

// Re-exported rather than merely used, so callers can name the timestamps this
// crate hands them without taking their own dependency on the same version of
// chrono -- and without the two drifting apart the day one of them upgrades.
pub use chrono::{DateTime, Utc};
pub use error::{AccountError, Result};
pub use recovery::RecoveryCode;
pub use session::SessionToken;

/// Server-side lifetime of a browser-session sign-in.
///
/// The browser cookie still disappears when the browser session ends, but the
/// bearer token itself also has a short absolute lifetime so copying a session
/// cookie does not turn an unchecked "remember me" choice into a 30-day token.
pub const BROWSER_SESSION_DURATION_HOURS: i64 = 24;

/// Server-side lifetime of an explicitly remembered session.
pub const REMEMBERED_SESSION_DURATION_DAYS: i64 = 30;

/// Session lifetime chosen by the authentication boundary.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionLifetime {
    /// Ordinary browser session; short absolute server lifetime.
    Browser,
    /// Explicit "remember me" session.
    Remembered,
}

impl SessionLifetime {
    /// Exact absolute lifetime persisted in PostgreSQL.
    #[must_use]
    pub const fn seconds(self) -> i64 {
        match self {
            Self::Browser => BROWSER_SESSION_DURATION_HOURS * 60 * 60,
            Self::Remembered => REMEMBERED_SESSION_DURATION_DAYS * 24 * 60 * 60,
        }
    }

    fn duration(self) -> Duration {
        Duration::seconds(self.seconds())
    }
}

/// Default maximum connections held by one API instance.
///
/// This is intentionally a per-instance budget rather than one connection
/// per concurrent user. Five thousand researchers mostly wait on short
/// queries; allowing every request to open a PostgreSQL connection would move
/// the bottleneck into the database and make a traffic spike self-amplifying.
pub const DEFAULT_DB_MAX_CONNECTIONS: u32 = 32;

/// Hard ceiling for one API instance's database pool.
pub const MAX_DB_CONNECTIONS: u32 = 128;

fn parse_pool_setting(
    name: &str,
    raw: Option<&str>,
    default: u32,
    minimum: u32,
    maximum: u32,
) -> Result<u32> {
    let Some(raw) = raw else {
        return Ok(default);
    };
    let value = raw.parse::<u32>().map_err(|_| {
        AccountError::Store(format!(
            "{name} must be an integer from {minimum} to {maximum}; got {raw:?}"
        ))
    })?;
    if !(minimum..=maximum).contains(&value) {
        return Err(AccountError::Store(format!(
            "{name} must be an integer from {minimum} to {maximum}; got {raw:?}"
        )));
    }
    Ok(value)
}

fn pool_setting(name: &str, default: u32, minimum: u32, maximum: u32) -> Result<u32> {
    match std::env::var(name) {
        Ok(raw) => parse_pool_setting(name, Some(&raw), default, minimum, maximum),
        Err(std::env::VarError::NotPresent) => {
            parse_pool_setting(name, None, default, minimum, maximum)
        }
        Err(std::env::VarError::NotUnicode(_)) => Err(AccountError::Store(format!(
            "{name} must be valid Unicode containing an integer from {minimum} to {maximum}"
        ))),
    }
}

/// A person, as the rest of the program sees them. No password material.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct User {
    /// Stable identifier.
    pub id: String,
    /// The address as they typed it.
    pub email: String,
    /// What to call them in the interface.
    pub display_name: String,
    /// When the account was created.
    pub created_at: DateTime<Utc>,
    /// Authorization role. New accounts are always ordinary users.
    pub role: String,
}

/// The store. Cheap to clone: it is a handle onto a connection pool.
#[derive(Clone)]
pub struct Accounts {
    pool: PgPool,
}

impl std::fmt::Debug for Accounts {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Accounts").finish_non_exhaustive()
    }
}

impl Accounts {
    /// Connect to the database and apply any outstanding migrations.
    ///
    /// # Errors
    ///
    /// Returns [`AccountError::Store`] if a database-pool override is malformed
    /// or out of range, if the database cannot be reached, or if migrations do
    /// not apply.
    pub async fn connect(url: &str) -> Result<Self> {
        Self::connect_inner(url, true).await
    }

    /// Connect to an already-migrated database without taking migration
    /// ownership. Production API/runner processes use this after the dedicated
    /// one-shot migration service has completed successfully.
    ///
    /// # Errors
    ///
    /// Returns [`AccountError::Store`] if database-pool configuration is
    /// malformed or the database cannot be reached.
    pub async fn connect_without_migrations(url: &str) -> Result<Self> {
        Self::connect_inner(url, false).await
    }

    async fn connect_inner(url: &str, run_migrations: bool) -> Result<Self> {
        let max_connections = pool_setting(
            "PCR_DB_MAX_CONNECTIONS",
            DEFAULT_DB_MAX_CONNECTIONS,
            4,
            MAX_DB_CONNECTIONS,
        )?;
        let min_connections = pool_setting("PCR_DB_MIN_CONNECTIONS", 2, 0, max_connections)?;
        let acquire_timeout = pool_setting("PCR_DB_ACQUIRE_TIMEOUT_SECONDS", 5, 1, 60)?;
        let pool = PgPoolOptions::new()
            // Sized for short session/project queries rather than for long
            // transactions. The deployment can budget this per replica, but
            // the hard ceiling prevents an accidental env value from turning
            // five thousand callers into five thousand database connections.
            .max_connections(max_connections)
            .min_connections(min_connections)
            .acquire_timeout(StdDuration::from_secs(u64::from(acquire_timeout)))
            .idle_timeout(StdDuration::from_secs(600))
            .connect(url)
            .await?;

        if run_migrations {
            pcr_storage::migrate(&pool)
                .await
                .map_err(|error| AccountError::Store(error.to_string()))?;
        }

        Ok(Self { pool })
    }

    /// The connection pool, for stores that share this database.
    ///
    /// One database means one pool: opening a second would double the
    /// connection count for no benefit, and Postgres counts connections, not
    /// What this person has told us about how they work.
    ///
    /// An empty object when they have said nothing, which is most accounts —
    /// so the caller reads a shape rather than an option, and a preference that
    /// is absent simply falls through to whatever the application would have
    /// done anyway.
    ///
    /// # Errors
    ///
    /// [`AccountError::NoSuchUser`] if there is no such account.
    pub async fn preferences(&self, user_id: &str) -> Result<serde_json::Value> {
        sqlx::query_scalar::<_, serde_json::Value>("SELECT preferences FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(&self.pool)
            .await
            .map_err(AccountError::from)?
            .ok_or(AccountError::NoSuchUser)
    }

    /// Replace the whole preferences object.
    ///
    /// Whole rather than merged, deliberately: a merge has no way to express
    /// "unset this", and a settings screen that can turn something on but never
    /// off is a settings screen people stop trusting.
    ///
    /// # Errors
    ///
    /// [`AccountError::NoSuchUser`] if there is no such account.
    pub async fn set_preferences(
        &self,
        user_id: &str,
        preferences: &serde_json::Value,
    ) -> Result<serde_json::Value> {
        let affected = sqlx::query("UPDATE users SET preferences = $1 WHERE id = $2")
            .bind(preferences)
            .bind(user_id)
            .execute(&self.pool)
            .await
            .map_err(AccountError::from)?
            .rows_affected();

        if affected == 0 {
            return Err(AccountError::NoSuchUser);
        }
        Ok(preferences.clone())
    }

    /// Whether the database will actually answer.
    ///
    /// A readiness probe needs more than a parsed connection string: a pool
    /// holds no connection until one is asked for, so a server pointed at a
    /// database that is down starts cleanly and fails every request. `SELECT 1`
    /// costs nothing and proves a live connection can be had.
    ///
    /// Here rather than in the server because this crate owns the pool. Asking
    /// the server to reach through `pool()` and run its own query would make
    /// `sqlx` a dependency of a crate that otherwise has no business knowing
    /// which database this is.
    ///
    /// # Errors
    ///
    /// [`AccountError::Store`] with what the database said.
    pub async fn reachable(&self) -> Result<()> {
        sqlx::query("SELECT 1")
            .execute(&self.pool)
            .await
            .map(|_| ())
            .map_err(AccountError::from)
    }

    /// crates.
    #[must_use]
    pub fn pool(&self) -> sqlx::PgPool {
        self.pool.clone()
    }

    /// Current PostgreSQL pool size and idle-connection count for low-cardinality
    /// operator telemetry. No database names, users, queries, or request data are
    /// exposed.
    #[must_use]
    pub fn pool_utilization(&self) -> (u32, usize) {
        (self.pool.size(), self.pool.num_idle())
    }

    /// Atomically consume one attempt in a shared rate-limit bucket.
    ///
    /// The bucket lives in PostgreSQL so API replicas cannot each grant a
    /// caller a separate budget. The operation is one upsert and is safe when
    /// several replicas update the same caller concurrently.
    ///
    /// # Errors
    ///
    /// Returns [`AccountError::Store`] when the shared limiter cannot be
    /// reached.
    pub async fn allow_rate_limit(
        &self,
        namespace: &str,
        key: &str,
        max: i32,
        window_seconds: i64,
    ) -> Result<bool> {
        sqlx::query_scalar::<_, bool>(
            "INSERT INTO rate_limit_buckets
                (namespace, bucket_key, window_started_at, hits, updated_at)
             VALUES ($1, $2, now(), 1, now())
             ON CONFLICT (namespace, bucket_key) DO UPDATE
             SET window_started_at = CASE
                     WHEN EXTRACT(EPOCH FROM now() - rate_limit_buckets.window_started_at) >= $4
                     THEN now() ELSE rate_limit_buckets.window_started_at END,
                 hits = CASE
                     WHEN EXTRACT(EPOCH FROM now() - rate_limit_buckets.window_started_at) >= $4
                     THEN 1 ELSE rate_limit_buckets.hits + 1 END,
                 updated_at = now()
             RETURNING hits <= $3",
        )
        .bind(namespace)
        .bind(key)
        .bind(max)
        .bind(window_seconds as f64)
        .fetch_one(&self.pool)
        .await
        .map_err(|error| AccountError::Store(format!("rate limiter failed: {error}")))
    }

    /// Remove shared rate-limit buckets that have been idle for an hour.
    ///
    /// # Errors
    ///
    /// Returns [`AccountError::Store`] when the cleanup query fails.
    pub async fn purge_rate_limit_buckets(&self) -> Result<u64> {
        let result = sqlx::query(
            "DELETE FROM rate_limit_buckets WHERE updated_at < now() - INTERVAL '1 hour'",
        )
        .execute(&self.pool)
        .await
        .map_err(|error| AccountError::Store(format!("rate-limit cleanup failed: {error}")))?;
        Ok(result.rows_affected())
    }

    /// Create an account and return it.
    ///
    /// # Errors
    ///
    /// [`AccountError::InvalidEmail`], [`AccountError::InvalidName`] and
    /// [`AccountError::WeakPassword`] for input that does not pass;
    /// [`AccountError::EmailTaken`] if the address is already registered.
    pub async fn register(
        &self,
        email: &str,
        display_name: &str,
        password: &str,
    ) -> Result<(User, RecoveryCode)> {
        self.register_inner(email, display_name, password, None)
            .await
    }

    /// Create an account and its first session atomically.
    ///
    /// This is the HTTP registration primitive. The recovery code exists in
    /// plaintext only in the returned value, so committing the account before
    /// the session row would create a half-success if session storage failed:
    /// the browser would receive an error while the account (and the only copy
    /// of its recovery code) had already changed. Both rows therefore commit
    /// together or neither does.
    pub async fn register_and_start_session(
        &self,
        email: &str,
        display_name: &str,
        password: &str,
    ) -> Result<(User, RecoveryCode, SessionToken)> {
        let token = SessionToken::generate();
        let (user, recovery) = self
            .register_inner(email, display_name, password, Some(&token))
            .await?;
        Ok((user, recovery, token))
    }

    async fn register_inner(
        &self,
        email: &str,
        display_name: &str,
        password: &str,
        session: Option<&SessionToken>,
    ) -> Result<(User, RecoveryCode)> {
        let email = normalise_email_input(email)?;
        let display_name = clean_display_name(display_name)?;
        password::check_policy(password, &email)?;

        let now = Utc::now();
        let user = User {
            id: uuid::Uuid::new_v4().to_string(),
            email: email.clone(),
            display_name,
            created_at: now,
            role: "user".to_owned(),
        };
        let hash = password::hash_async(password.to_owned()).await?;

        let code = RecoveryCode::generate();
        let recovery_hash = password::hash_async(recovery::normalise(&code.plain)).await?;
        let mut transaction = self.pool.begin().await?;
        let result = sqlx::query(
            "INSERT INTO users (id, email, email_normalised, display_name, password_hash, role,
                                recovery_hash, recovery_issued_at, created_at, updated_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8, $8)",
        )
        .bind(&user.id)
        .bind(&user.email)
        .bind(email.to_lowercase())
        .bind(&user.display_name)
        .bind(&hash)
        .bind(&user.role)
        .bind(&recovery_hash)
        .bind(now)
        .execute(&mut *transaction)
        .await;

        match result {
            Ok(_) => {}
            Err(sqlx::Error::Database(error)) if error.is_unique_violation() => {
                transaction.rollback().await?;
                return Err(AccountError::EmailTaken);
            }
            Err(error) => {
                transaction.rollback().await?;
                return Err(error.into());
            }
        }

        if let Some(session) = session {
            let expires = now + SessionLifetime::Remembered.duration();
            sqlx::query(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
                 VALUES ($1, $2, $3, $4)",
            )
            .bind(&session.hashed)
            .bind(&user.id)
            .bind(now)
            .bind(expires)
            .execute(&mut *transaction)
            .await?;
        }

        transaction.commit().await?;
        Ok((user, code))
    }

    /// Whether this account has a recovery code, and when it was issued.
    ///
    /// Accounts made before recovery existed have none. They are offered one
    /// rather than being locked out of the feature or made to take it.
    ///
    /// # Errors
    ///
    /// [`AccountError::NoSuchUser`] if the account is gone.
    pub async fn recovery_status(&self, user_id: &str) -> Result<Option<DateTime<Utc>>> {
        let row = sqlx::query("SELECT recovery_hash, recovery_issued_at FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or(AccountError::NoSuchUser)?;

        let hash: Option<String> = row.try_get("recovery_hash")?;
        if hash.is_none() {
            return Ok(None);
        }
        Ok(row.try_get("recovery_issued_at")?)
    }

    /// Replace this account's recovery code, proving the password first.
    ///
    /// Returns the new code, which is the only time it exists in plain text.
    /// The old one stops working the moment this returns.
    ///
    /// # Errors
    ///
    /// [`AccountError::InvalidCredentials`] if the password is wrong.
    pub async fn reissue_recovery_code(
        &self,
        user_id: &str,
        password: &str,
    ) -> Result<RecoveryCode> {
        let row = sqlx::query("SELECT password_hash, recovery_hash FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or(AccountError::NoSuchUser)?;

        let stored: String = row.try_get("password_hash")?;
        let previous_recovery: Option<String> = row.try_get("recovery_hash")?;
        if !password::verify_async(password.to_owned(), stored.clone()).await {
            return Err(AccountError::InvalidCredentials);
        }

        let code = RecoveryCode::generate();
        let hash = password::hash_async(recovery::normalise(&code.plain)).await?;
        let now = Utc::now();

        let affected = sqlx::query(
            "UPDATE users
                SET recovery_hash = $1,
                    recovery_issued_at = $2,
                    recovery_attempts = 0,
                    recovery_attempted_at = NULL,
                    updated_at = $2
              WHERE id = $3
                AND password_hash = $4
                AND recovery_hash IS NOT DISTINCT FROM $5",
        )
        .bind(&hash)
        .bind(now)
        .bind(user_id)
        .bind(&stored)
        .bind(previous_recovery.as_deref())
        .execute(&self.pool)
        .await?
        .rows_affected();

        if affected == 0 {
            return Err(AccountError::InvalidCredentials);
        }
        Ok(code)
    }

    /// Set a new password from a recovery code, and end every session.
    ///
    /// Returns a fresh recovery code: the one just used is spent, and leaving
    /// the account without one would mean the next forgotten password is the
    /// last one.
    ///
    /// Every session is ended rather than kept. Somebody using this either
    /// forgot their password or is recovering from someone else having it, and
    /// in the second case the sessions are the attacker's.
    ///
    /// # Errors
    ///
    /// [`AccountError::InvalidCredentials`] for a wrong address or a wrong
    /// code, told apart nowhere; [`AccountError::RecoveryLocked`] once an
    /// account has absorbed too many wrong attempts.
    pub async fn recover(
        &self,
        email: &str,
        code: &str,
        new_password: &str,
    ) -> Result<(User, RecoveryCode)> {
        self.recover_inner(email, code, new_password, None).await
    }

    /// Recover an account and create its replacement session atomically.
    ///
    /// Recovery spends the old code, rotates the password, revokes every old
    /// session and returns a new recovery code. Because the replacement code
    /// exists only in plaintext in this return value, the new session is part
    /// of the same database transaction: a session-store failure cannot commit
    /// a credential rotation that the HTTP caller is told failed.
    pub async fn recover_and_start_session(
        &self,
        email: &str,
        code: &str,
        new_password: &str,
    ) -> Result<(User, RecoveryCode, SessionToken)> {
        let token = SessionToken::generate();
        let (user, recovery) = self
            .recover_inner(email, code, new_password, Some(&token))
            .await?;
        Ok((user, recovery, token))
    }

    async fn recover_inner(
        &self,
        email: &str,
        code: &str,
        new_password: &str,
        session: Option<&SessionToken>,
    ) -> Result<(User, RecoveryCode)> {
        // Reject an impossible code before touching either PostgreSQL or Argon2.
        // This reveals nothing about the account: every email address gets the
        // same answer for an input that cannot have been generated by PCRStudio.
        if !recovery::looks_like_a_code(code) {
            return Err(AccountError::InvalidCredentials);
        }

        let normalised = email.trim().to_lowercase();

        let row = sqlx::query(
            "SELECT id, email, display_name, created_at, role, recovery_hash,
                    recovery_attempts, recovery_attempted_at
               FROM users
              WHERE email_normalised = $1",
        )
        .bind(&normalised)
        .fetch_optional(&self.pool)
        .await?;

        // An unknown address and a wrong code answer alike. Telling them apart
        // would make this endpoint a way to ask whether somebody has an account
        // here, which is exactly what sign-in already refuses to answer. Spend
        // the same Argon2 work on the unknown path so the answer is not exposed
        // through response timing either.
        let Some(row) = row else {
            let _ = password::verify_async(recovery::normalise(code), DUMMY_HASH.to_owned()).await;
            return Err(AccountError::InvalidCredentials);
        };

        let user_id: String = row.try_get("id")?;
        let stored: Option<String> = row.try_get("recovery_hash")?;
        let attempts: i32 = row.try_get("recovery_attempts")?;
        let attempted_at: Option<DateTime<Utc>> = row.try_get("recovery_attempted_at")?;

        // The shutter, and whether it has lifted.
        let locked_until = attempted_at.map(|at| at + Duration::minutes(recovery::LOCKOUT_MINUTES));
        let still_locked = locked_until.is_some_and(|until| until > Utc::now());

        if attempts >= recovery::MAX_ATTEMPTS && still_locked {
            // A locked account must not verify its real recovery hash, but it
            // still does equivalent work so lock state cannot become another
            // account-enumeration signal.
            let _ = password::verify_async(recovery::normalise(code), DUMMY_HASH.to_owned()).await;
            return Err(AccountError::RecoveryLocked);
        }

        let Some(stored) = stored else {
            // No code was ever issued for this account. Same answer as a wrong
            // one: the alternative announces which accounts predate the feature.
            let _ = password::verify_async(recovery::normalise(code), DUMMY_HASH.to_owned()).await;
            return Err(AccountError::InvalidCredentials);
        };

        if !password::verify_async(recovery::normalise(code), stored.clone()).await {
            /*
             * One statement counts the attempt, where a read, an add and a
             * write apart would let two simultaneous attempts both read the
             * same number and lose one — exactly the undercount a lockout
             * must not have. Whether the previous window has expired is
             * judged inside the same statement, against the row as it stands
             * now rather than as the last reader saw it.
             */
            let counted = sqlx::query_as::<_, (i32, Option<DateTime<Utc>>)>(
                "UPDATE users
                    SET recovery_attempts = CASE
                          WHEN recovery_attempted_at IS NOT NULL
                           AND recovery_attempted_at > $2 - make_interval(mins => $3::int)
                          THEN recovery_attempts + 1
                          ELSE 1 END,
                        recovery_attempted_at = $2
                  WHERE id = $1 AND recovery_hash = $4
                  RETURNING recovery_attempts, recovery_attempted_at",
            )
            .bind(&user_id)
            .bind(Utc::now())
            .bind(recovery::LOCKOUT_MINUTES)
            .bind(&stored)
            .fetch_optional(&self.pool)
            .await?;

            // A concurrent reissue/recovery can rotate the code after the
            // verification above. An attempt against the old hash must not
            // spend the budget of the newly issued code.
            let Some((counted, counted_at)) = counted else {
                return Err(AccountError::InvalidCredentials);
            };

            // This attempt may be the one that spent the budget. The shutter
            // closes here rather than making the account ask once more.
            let shut_until = counted_at.map(|at| at + Duration::minutes(recovery::LOCKOUT_MINUTES));
            if counted >= recovery::MAX_ATTEMPTS
                && shut_until.is_some_and(|until| until > Utc::now())
            {
                return Err(AccountError::RecoveryLocked);
            }

            return Err(AccountError::InvalidCredentials);
        }

        let user = User {
            id: user_id.clone(),
            email: row.try_get("email")?,
            display_name: row.try_get("display_name")?,
            created_at: row.try_get("created_at")?,
            role: row.try_get("role")?,
        };

        password::check_policy(new_password, &user.email)?;
        let password_hash = password::hash_async(new_password.to_owned()).await?;

        let next = RecoveryCode::generate();
        let recovery_hash = password::hash_async(recovery::normalise(&next.plain)).await?;
        let now = Utc::now();
        // One transaction: a password changed without the sessions being cleared
        // would leave whoever prompted this recovery still signed in.
        let mut transaction = self.pool.begin().await?;

        let affected = sqlx::query(
            "UPDATE users
                SET password_hash = $1,
                    recovery_hash = $2,
                    recovery_issued_at = $3,
                    recovery_attempts = 0,
                    recovery_attempted_at = NULL,
                    updated_at = $3
              WHERE id = $4 AND recovery_hash = $5",
        )
        .bind(&password_hash)
        .bind(&recovery_hash)
        .bind(now)
        .bind(&user_id)
        .bind(&stored)
        .execute(&mut *transaction)
        .await?
        .rows_affected();

        if affected == 0 {
            transaction.rollback().await?;
            return Err(AccountError::InvalidCredentials);
        }

        sqlx::query("DELETE FROM sessions WHERE user_id = $1")
            .bind(&user_id)
            .execute(&mut *transaction)
            .await?;

        if let Some(session) = session {
            let expires = now + SessionLifetime::Remembered.duration();
            sqlx::query(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
                 VALUES ($1, $2, $3, $4)",
            )
            .bind(&session.hashed)
            .bind(&user_id)
            .bind(now)
            .bind(expires)
            .execute(&mut *transaction)
            .await?;
        }

        transaction.commit().await?;
        Ok((user, next))
    }

    /// Check an email and password.
    ///
    /// # Errors
    ///
    /// [`AccountError::InvalidCredentials`] whether the address is unknown or
    /// the password is wrong, so neither can be probed.
    pub async fn authenticate(&self, email: &str, password: &str) -> Result<User> {
        let normalised = email.trim().to_lowercase();

        let row = sqlx::query(
            "SELECT id, email, display_name, password_hash, created_at, role
             FROM users WHERE email_normalised = $1",
        )
        .bind(&normalised)
        .fetch_optional(&self.pool)
        .await?;

        let Some(row) = row else {
            // Hash anyway. Returning here without doing the work would make an
            // unknown address measurably faster to reject than a wrong
            // password, which is enough to enumerate who has an account.
            let _ = password::verify_async(password.to_owned(), DUMMY_HASH.to_owned()).await;
            return Err(AccountError::InvalidCredentials);
        };

        let stored: String = row.try_get("password_hash")?;
        if !password::verify_async(password.to_owned(), stored.clone()).await {
            return Err(AccountError::InvalidCredentials);
        }

        let user = User {
            id: row.try_get("id")?,
            email: row.try_get("email")?,
            display_name: row.try_get("display_name")?,
            created_at: row.try_get("created_at")?,
            role: row.try_get("role")?,
        };

        // A successful login is the only safe time to upgrade a password hash:
        // the plaintext is already present, and the compare-and-swap keeps a
        // concurrent password change from being overwritten. Rehash failure is
        // a storage failure rather than a reason to accept an obsolete policy.
        if password::needs_rehash(&stored) {
            let upgraded = password::hash_async(password.to_owned()).await?;
            sqlx::query(
                "UPDATE users SET password_hash = $1, updated_at = $2
                 WHERE id = $3 AND password_hash = $4",
            )
            .bind(upgraded)
            .bind(Utc::now())
            .bind(&user.id)
            .bind(&stored)
            .execute(&self.pool)
            .await?;
        }

        Ok(user)
    }

    /// Start a session and return the token to hand to the browser.
    ///
    /// # Errors
    ///
    /// [`AccountError::Store`] if the session cannot be written.
    pub async fn start_session(&self, user_id: &str) -> Result<SessionToken> {
        self.start_session_with_lifetime(user_id, SessionLifetime::Remembered)
            .await
    }

    /// Start a session with an explicit server-side absolute lifetime.
    ///
    /// # Errors
    /// [`AccountError::Store`] if the session cannot be written.
    pub async fn start_session_with_lifetime(
        &self,
        user_id: &str,
        lifetime: SessionLifetime,
    ) -> Result<SessionToken> {
        let token = SessionToken::generate();
        let now = Utc::now();
        let expires = now + lifetime.duration();

        sqlx::query(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
             VALUES ($1, $2, $3, $4)",
        )
        .bind(&token.hashed)
        .bind(user_id)
        .bind(now)
        .bind(expires)
        .execute(&self.pool)
        .await?;

        Ok(token)
    }

    /// Who a session token belongs to.
    ///
    /// This runs on every request that needs to know who is asking, so it is
    /// one primary-key lookup joined to one primary key and nothing else.
    ///
    /// # Errors
    ///
    /// [`AccountError::SessionEnded`] if the token is unknown, expired or
    /// revoked.
    pub async fn user_for_session(&self, token: &str) -> Result<User> {
        let hashed = session::hash(token);

        let row = sqlx::query(
            "SELECT u.id, u.email, u.display_name, u.created_at, u.role
             FROM sessions s JOIN users u ON u.id = s.user_id
             WHERE s.token_hash = $1 AND s.expires_at > $2",
        )
        .bind(&hashed)
        .bind(Utc::now())
        .fetch_optional(&self.pool)
        .await?;

        let Some(row) = row else {
            return Err(AccountError::SessionEnded);
        };

        Ok(User {
            id: row.try_get("id")?,
            email: row.try_get("email")?,
            display_name: row.try_get("display_name")?,
            created_at: row.try_get("created_at")?,
            role: row.try_get("role")?,
        })
    }

    /// End one session. Signing out of an unknown session is not an error.
    ///
    /// # Errors
    ///
    /// [`AccountError::Store`] if the delete fails.
    pub async fn end_session(&self, token: &str) -> Result<()> {
        sqlx::query("DELETE FROM sessions WHERE token_hash = $1")
            .bind(session::hash(token))
            .execute(&self.pool)
            .await?;
        Ok(())
    }

    /// End every session a user has, and report how many that was.
    ///
    /// # Errors
    ///
    /// [`AccountError::Store`] if the delete fails.
    pub async fn end_all_sessions(&self, user_id: &str) -> Result<u64> {
        let result = sqlx::query("DELETE FROM sessions WHERE user_id = $1")
            .bind(user_id)
            .execute(&self.pool)
            .await?;
        Ok(result.rows_affected())
    }

    /// Change what someone is called.
    ///
    /// # Errors
    ///
    /// [`AccountError::InvalidName`] for an empty or overlong name;
    /// [`AccountError::NoSuchUser`] if the account is gone.
    pub async fn rename(&self, user_id: &str, display_name: &str) -> Result<User> {
        let display_name = clean_display_name(display_name)?;

        let row = sqlx::query(
            "UPDATE users SET display_name = $1, updated_at = $2 WHERE id = $3
             RETURNING id, email, display_name, created_at, role",
        )
        .bind(&display_name)
        .bind(Utc::now())
        .bind(user_id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or(AccountError::NoSuchUser)?;

        Ok(User {
            id: row.try_get("id")?,
            email: row.try_get("email")?,
            display_name: row.try_get("display_name")?,
            created_at: row.try_get("created_at")?,
            role: row.try_get("role")?,
        })
    }

    /// Change the sign-in email after proving the current password.
    ///
    /// The address is both identity and login key in this application, so a
    /// session alone is not enough authority to change it. The update is
    /// compare-and-swap against the password hash that was verified; if a
    /// concurrent password rotation wins first, this request is refused rather
    /// than committing under stale credentials. Other sessions are ended so an
    /// account-identifier change also closes browsers the caller may no longer
    /// control.
    ///
    /// # Errors
    ///
    /// [`AccountError::InvalidCredentials`] if the password is wrong or changed
    /// concurrently; [`AccountError::InvalidEmail`] if the address is malformed;
    /// [`AccountError::EmailTaken`] if another account already owns it.
    pub async fn change_email(
        &self,
        user_id: &str,
        current_password: &str,
        next_email: &str,
        keep_session: Option<&str>,
    ) -> Result<User> {
        let next_email = normalise_email_input(next_email)?;
        let row = sqlx::query(
            "SELECT email, password_hash, display_name, created_at, role FROM users WHERE id = $1",
        )
        .bind(user_id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or(AccountError::NoSuchUser)?;

        let current_email: String = row.try_get("email")?;
        let stored: String = row.try_get("password_hash")?;
        if !password::verify_async(current_password.to_owned(), stored.clone()).await {
            return Err(AccountError::InvalidCredentials);
        }
        // Changing an identifier must not retroactively impose today's full
        // password-length policy on a legacy account. Preserve the one invariant
        // that depends on the identifier itself: a password must not equal the
        // newly selected sign-in email.
        if current_password.eq_ignore_ascii_case(&next_email) {
            return Err(AccountError::WeakPassword(
                "the password must not be your email address".into(),
            ));
        }

        if current_email.eq_ignore_ascii_case(&next_email) {
            return Ok(User {
                id: user_id.to_owned(),
                email: current_email,
                display_name: row.try_get("display_name")?,
                created_at: row.try_get("created_at")?,
                role: row.try_get("role")?,
            });
        }

        let mut transaction = self.pool.begin().await?;
        let result = sqlx::query(
            "UPDATE users
             SET email = $1, email_normalised = $2, updated_at = $3
             WHERE id = $4 AND password_hash = $5
             RETURNING id, email, display_name, created_at, role",
        )
        .bind(&next_email)
        .bind(next_email.to_lowercase())
        .bind(Utc::now())
        .bind(user_id)
        .bind(&stored)
        .fetch_optional(&mut *transaction)
        .await;

        let row = match result {
            Ok(Some(row)) => row,
            Ok(None) => {
                transaction.rollback().await?;
                return Err(AccountError::InvalidCredentials);
            }
            Err(sqlx::Error::Database(error)) if error.is_unique_violation() => {
                transaction.rollback().await?;
                return Err(AccountError::EmailTaken);
            }
            Err(error) => {
                transaction.rollback().await?;
                return Err(error.into());
            }
        };

        match keep_session {
            Some(token) => {
                sqlx::query("DELETE FROM sessions WHERE user_id = $1 AND token_hash <> $2")
                    .bind(user_id)
                    .bind(session::hash(token))
                    .execute(&mut *transaction)
                    .await?;
            }
            None => {
                sqlx::query("DELETE FROM sessions WHERE user_id = $1")
                    .bind(user_id)
                    .execute(&mut *transaction)
                    .await?;
            }
        }

        let user = User {
            id: row.try_get("id")?,
            email: row.try_get("email")?,
            display_name: row.try_get("display_name")?,
            created_at: row.try_get("created_at")?,
            role: row.try_get("role")?,
        };
        transaction.commit().await?;
        Ok(user)
    }

    /// Replace a password, having checked the current one.
    ///
    /// Every other session is ended: changing a password is what someone does
    /// when they think a session somewhere is not theirs.
    ///
    /// # Errors
    ///
    /// [`AccountError::InvalidCredentials`] if the current password is wrong;
    /// [`AccountError::WeakPassword`] if the new one fails the policy.
    pub async fn change_password(
        &self,
        user_id: &str,
        current: &str,
        next: &str,
        keep_session: Option<&str>,
    ) -> Result<()> {
        let row = sqlx::query("SELECT email, password_hash FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or(AccountError::NoSuchUser)?;

        let email: String = row.try_get("email")?;
        let stored: String = row.try_get("password_hash")?;
        if !password::verify_async(current.to_owned(), stored.clone()).await {
            return Err(AccountError::InvalidCredentials);
        }
        password::check_policy(next, &email)?;

        let hash = password::hash_async(next.to_owned()).await?;
        let mut transaction = self.pool.begin().await?;

        let affected = sqlx::query(
            "UPDATE users SET password_hash = $1, updated_at = $2
              WHERE id = $3 AND password_hash = $4",
        )
        .bind(&hash)
        .bind(Utc::now())
        .bind(user_id)
        .bind(&stored)
        .execute(&mut *transaction)
        .await?
        .rows_affected();

        if affected == 0 {
            transaction.rollback().await?;
            return Err(AccountError::InvalidCredentials);
        }

        match keep_session {
            Some(token) => {
                sqlx::query("DELETE FROM sessions WHERE user_id = $1 AND token_hash <> $2")
                    .bind(user_id)
                    .bind(session::hash(token))
                    .execute(&mut *transaction)
                    .await?;
            }
            None => {
                sqlx::query("DELETE FROM sessions WHERE user_id = $1")
                    .bind(user_id)
                    .execute(&mut *transaction)
                    .await?;
            }
        }

        transaction.commit().await?;
        Ok(())
    }

    /// Delete an account and everything hanging off it.
    ///
    /// # Errors
    ///
    /// [`AccountError::InvalidCredentials`] if the password does not match;
    /// [`AccountError::NoSuchUser`] if it is already gone.
    pub async fn delete(&self, user_id: &str, password: &str) -> Result<()> {
        let row = sqlx::query("SELECT password_hash FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or(AccountError::NoSuchUser)?;

        let stored: String = row.try_get("password_hash")?;
        if !password::verify_async(password.to_owned(), stored.clone()).await {
            return Err(AccountError::InvalidCredentials);
        }

        // Sessions go with it, by the foreign key. Tie the delete to the exact
        // credential we verified so a concurrent password change invalidates
        // this stale destructive request.
        let affected = sqlx::query("DELETE FROM users WHERE id = $1 AND password_hash = $2")
            .bind(user_id)
            .bind(&stored)
            .execute(&self.pool)
            .await?
            .rows_affected();
        if affected == 0 {
            return Err(AccountError::InvalidCredentials);
        }
        Ok(())
    }

    /// One user by id.
    ///
    /// # Errors
    ///
    /// [`AccountError::NoSuchUser`] if there is no such account.
    pub async fn user(&self, user_id: &str) -> Result<User> {
        let row = sqlx::query(
            "SELECT id, email, display_name, created_at, role FROM users WHERE id = $1",
        )
        .bind(user_id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or(AccountError::NoSuchUser)?;

        Ok(User {
            id: row.try_get("id")?,
            email: row.try_get("email")?,
            display_name: row.try_get("display_name")?,
            created_at: row.try_get("created_at")?,
            role: row.try_get("role")?,
        })
    }

    /// Delete sessions that have already expired, and report how many.
    ///
    /// Expired sessions are refused on sight, so this is housekeeping to keep
    /// the table from growing without bound rather than a security measure.
    ///
    /// # Errors
    ///
    /// [`AccountError::Store`] if the delete fails.
    pub async fn purge_expired_sessions(&self) -> Result<u64> {
        let result = sqlx::query("DELETE FROM sessions WHERE expires_at <= $1")
            .bind(Utc::now())
            .execute(&self.pool)
            .await?;
        Ok(result.rows_affected())
    }
}

/// A real Argon2 hash of a value nobody knows, used to spend the same time on
/// an unknown address as on a wrong password.
const DUMMY_HASH: &str = "$argon2id$v=19$m=19456,t=2,p=1$c29tZXNhbHRzb21lc2FsdA$Xb0kZQKPQZ2Y3jWvI0m1x0Yy4CqB2C4z7bYh1sWjS9k";

fn normalise_email_input(email: &str) -> Result<String> {
    let email = email.trim();
    // Deliberately shallow. The only real test that a mailbox exists is sending
    // to it; anything stricter here only rejects valid, unusual addresses.
    let looks_like_an_address = email.len() >= 3
        && email.len() <= 254
        && !email.contains(char::is_whitespace)
        && email.matches('@').count() == 1
        && email.split('@').all(|part| !part.is_empty())
        && email
            .split('@')
            .nth(1)
            .is_some_and(|host| host.contains('.'));

    if !looks_like_an_address {
        return Err(AccountError::InvalidEmail(
            "that does not look like an email address".into(),
        ));
    }
    Ok(email.to_owned())
}

fn clean_display_name(name: &str) -> Result<String> {
    let name = name.trim();
    if name.is_empty() {
        return Err(AccountError::InvalidName("a name is required".into()));
    }
    if name.chars().count() > 80 {
        return Err(AccountError::InvalidName(
            "the name must be at most 80 characters".into(),
        ));
    }
    Ok(name.to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Everything that does not touch the database, so these run anywhere.
    mod rules {
        use super::*;

        #[test]
        fn an_address_needs_one_at_sign_and_a_dotted_host() {
            for good in ["a@b.co", "ada.lovelace+lab@example.co.uk"] {
                assert!(normalise_email_input(good).is_ok(), "`{good}` should pass");
            }
            for bad in [
                "",
                "ada",
                "ada@",
                "@example.org",
                "a b@example.org",
                "ada@example",
                "a@b@c.d",
            ] {
                assert!(
                    normalise_email_input(bad).is_err(),
                    "`{bad}` should be refused"
                );
            }
        }

        #[test]
        fn the_typed_address_survives_trimming_but_keeps_its_case() {
            assert_eq!(
                normalise_email_input("  Ada@Example.org ").expect("valid"),
                "Ada@Example.org"
            );
        }

        #[test]
        fn a_name_is_trimmed_and_bounded() {
            assert_eq!(clean_display_name("  Ada  ").expect("valid"), "Ada");
            assert!(clean_display_name("   ").is_err());
            assert!(clean_display_name(&"x".repeat(81)).is_err());
            assert!(clean_display_name(&"x".repeat(80)).is_ok());
        }

        #[test]
        fn the_password_policy_is_length_and_nothing_else() {
            assert!(password::check_policy("short", "a@b.co").is_err());
            assert!(password::check_policy("          ", "a@b.co").is_err());
            assert!(password::check_policy("a@b.co", "a@b.co").is_err());
            // No uppercase, no digit, no symbol, and correctly accepted.
            assert!(password::check_policy("correct horse battery", "a@b.co").is_ok());
        }

        #[test]
        fn a_hash_verifies_against_its_own_password_and_no_other() {
            let hash = password::hash("correct horse battery").expect("hashes");
            assert!(password::verify("correct horse battery", &hash));
            assert!(!password::verify("correct horse batteru", &hash));
            // A corrupted row is a mismatch, not a crash.
            assert!(!password::verify("correct horse battery", "not a hash"));
        }

        #[test]
        fn two_hashes_of_one_password_differ_because_the_salt_does() {
            let first = password::hash("correct horse battery").expect("hashes");
            let second = password::hash("correct horse battery").expect("hashes");
            assert_ne!(first, second);
            assert!(password::verify("correct horse battery", &first));
            assert!(password::verify("correct horse battery", &second));
        }

        #[test]
        fn the_dummy_hash_is_a_real_hash_that_matches_nothing() {
            // If this stopped parsing, the timing defence in `authenticate`
            // would silently become a fast path.
            assert!(!password::verify("anything at all", DUMMY_HASH));
            assert!(argon2::password_hash::PasswordHash::new(DUMMY_HASH).is_ok());
        }

        #[test]
        fn a_session_token_is_random_and_stored_only_as_its_hash() {
            let first = SessionToken::generate();
            let second = SessionToken::generate();
            assert_ne!(first.plain, second.plain);
            assert_eq!(first.plain.len(), 64);
            assert_ne!(first.plain, first.hashed);
            assert_eq!(first.hashed, session::hash(&first.plain));
        }

        #[test]
        fn errors_serialise_with_a_kind_the_interface_can_branch_on() {
            let json = serde_json::to_value(AccountError::EmailTaken).expect("serialisable");
            assert_eq!(json, serde_json::json!({ "kind": "emailTaken" }));
        }
    }
}
#[cfg(test)]
mod pool_setting_tests {
    use super::parse_pool_setting;

    #[test]
    fn explicit_pool_settings_fail_instead_of_clamping_or_falling_back() {
        assert_eq!(
            parse_pool_setting("PCR_DB_MAX_CONNECTIONS", None, 32, 4, 128)
                .expect("an absent setting uses the documented default"),
            32
        );
        assert_eq!(
            parse_pool_setting("PCR_DB_MAX_CONNECTIONS", Some("64"), 32, 4, 128)
                .expect("an in-range override is accepted"),
            64
        );
        assert!(
            parse_pool_setting("PCR_DB_MAX_CONNECTIONS", Some("not-a-number"), 32, 4, 128).is_err()
        );
        assert!(parse_pool_setting("PCR_DB_MAX_CONNECTIONS", Some("3"), 32, 4, 128).is_err());
        assert!(parse_pool_setting("PCR_DB_MIN_CONNECTIONS", Some("9"), 2, 0, 8).is_err());
    }
}
