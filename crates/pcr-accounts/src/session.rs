//! Session tokens: how they are made, and what is kept about them.
//!
//! The primitive is domain-neutral and lives in `pcr-security`; this module
//! preserves the public account-domain names used by existing callers.

pub use pcr_security::{hash_bearer_token as hash, BearerToken as SessionToken};
