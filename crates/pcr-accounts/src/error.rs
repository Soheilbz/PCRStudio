//! What can go wrong with an account, in a shape the interface can branch on.

use serde::{Deserialize, Serialize};

/// A failure raised while creating, checking or changing an account.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, thiserror::Error)]
#[serde(tag = "kind", content = "detail", rename_all = "camelCase")]
pub enum AccountError {
    /// The address is already registered.
    #[error("that email address is already registered")]
    EmailTaken,

    /// The address does not look like an address.
    #[error("{0}")]
    InvalidEmail(String),

    /// The password does not meet the policy.
    #[error("{0}")]
    WeakPassword(String),

    /// The display name is empty or too long.
    #[error("{0}")]
    InvalidName(String),

    /// Wrong email, wrong password, or no such account.
    ///
    /// Deliberately one variant: telling the two apart would let anyone check
    /// whether an address has an account here.
    #[error("that email and password do not match an account")]
    InvalidCredentials,

    /// Too many wrong recovery codes against this account, too recently.
    ///
    /// Its own variant rather than folded into `InvalidCredentials`, because
    /// the two need different words: one means "that was wrong", the other
    /// means "stop, and come back later". Telling somebody their correct code
    /// was wrong is how they conclude the account is unrecoverable and give up.
    #[error("too many recovery attempts on this account; try again in an hour")]
    RecoveryLocked,

    /// The session token is unknown, expired, or was revoked.
    #[error("your session has ended; sign in again")]
    SessionEnded,

    /// The account no longer exists.
    #[error("that account no longer exists")]
    NoSuchUser,

    /// Too many password-protected operations from one caller and account.
    #[error("too many attempts in too short a time; try again in a minute")]
    TooManyRequests,

    /// A request that could not be acted on, with what was wrong with it.
    ///
    /// Its own case rather than reusing `InvalidName`, which is about the name
    /// somebody chose to display. A setting whose *value* is too long is not a
    /// name problem, and an error kind that says it is will eventually be read
    /// by something that believes it.
    #[error("{0}")]
    BadRequest(String),

    /// The store itself failed. The detail is for the log, not the visitor.
    #[error("the account store failed: {0}")]
    Store(String),
}

/// Result alias used throughout this crate.
pub type Result<T> = std::result::Result<T, AccountError>;

impl From<sqlx::Error> for AccountError {
    fn from(error: sqlx::Error) -> Self {
        Self::Store(error.to_string())
    }
}
