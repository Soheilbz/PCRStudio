//! Hashing, verifying, and the one rule about what a password may be.

use argon2::password_hash::{PasswordHash, PasswordHasher, SaltString};
use argon2::{Algorithm, Argon2, Params, PasswordVerifier, Version};
use rand::{rng, Rng};

use crate::error::{AccountError, Result};

/// Shorter than this and an offline attacker does not need Argon2 to be slow.
pub const MIN_PASSWORD_LENGTH: usize = 10;

/// Long inputs cost CPU to hash and buy no security; this is well past any
/// passphrase a person will type.
pub const MAX_PASSWORD_LENGTH: usize = 256;

/// Maximum UTF-8 byte length accepted for a password that is only being
/// verified. This is deliberately much wider than the current creation policy
/// so a legacy passphrase is not invalidated, while a multi-megabyte request
/// can never be handed to Argon2.
pub const MAX_VERIFICATION_PASSWORD_BYTES: usize = 16 * 1024;

/// Check a candidate password against the policy.
///
/// Length only, deliberately. Composition rules push people towards
/// `Password1!` and away from passphrases, which is the opposite of the goal.
///
/// # Errors
///
/// Returns [`AccountError::WeakPassword`] describing what to fix.
pub fn check_policy(password: &str, email: &str) -> Result<()> {
    let length = password.chars().count();
    if length < MIN_PASSWORD_LENGTH {
        return Err(AccountError::WeakPassword(format!(
            "the password must be at least {MIN_PASSWORD_LENGTH} characters"
        )));
    }
    if length > MAX_PASSWORD_LENGTH {
        return Err(AccountError::WeakPassword(format!(
            "the password must be at most {MAX_PASSWORD_LENGTH} characters"
        )));
    }
    if password.trim().is_empty() {
        return Err(AccountError::WeakPassword(
            "the password must not be only spaces".into(),
        ));
    }
    if password.eq_ignore_ascii_case(email) {
        return Err(AccountError::WeakPassword(
            "the password must not be your email address".into(),
        ));
    }
    Ok(())
}

/// Versioned password-hashing policy.  Keep these explicit so a dependency
/// default change cannot silently alter account cost or PHC identity.
pub const ARGON2_POLICY_VERSION: &str = "argon2id-v1";
/// Argon2id memory cost in kibibytes.
pub const ARGON2_MEMORY_KIB: u32 = 19_456;
/// Argon2id time cost.
pub const ARGON2_TIME_COST: u32 = 2;
/// Argon2id lane count.
pub const ARGON2_PARALLELISM: u32 = 1;

fn argon2_policy() -> Result<Argon2<'static>> {
    let params = Params::new(
        ARGON2_MEMORY_KIB,
        ARGON2_TIME_COST,
        ARGON2_PARALLELISM,
        None,
    )
    .map_err(|error| AccountError::Store(format!("invalid Argon2 policy: {error}")))?;
    Ok(Argon2::new(Algorithm::Argon2id, Version::V0x13, params))
}

/// Whether a stored PHC hash predates the current explicit password policy.
///
/// This is deliberately format-level rather than a second password verifier:
/// the argon2 crate remains authoritative for verification; this parser only
/// decides whether a successful login should opportunistically rehash.
#[must_use]
pub fn needs_rehash(stored: &str) -> bool {
    let mut parts = stored.split('$');
    if parts.next() != Some("") || parts.next() != Some("argon2id") || parts.next() != Some("v=19")
    {
        return true;
    }
    let Some(parameters) = parts.next() else {
        return true;
    };
    let mut memory = None;
    let mut time = None;
    let mut parallelism = None;
    for parameter in parameters.split(',') {
        let Some((key, raw)) = parameter.split_once('=') else {
            return true;
        };
        let Ok(value) = raw.parse::<u32>() else {
            return true;
        };
        match key {
            "m" => memory = Some(value),
            "t" => time = Some(value),
            "p" => parallelism = Some(value),
            _ => {}
        }
    }
    memory != Some(ARGON2_MEMORY_KIB)
        || time != Some(ARGON2_TIME_COST)
        || parallelism != Some(ARGON2_PARALLELISM)
}

/// The salt length `SaltString::generate` used: PHC's recommended 16 bytes.
const SALT_BYTES: usize = 16;

/// Hash a password for storage.
///
/// # Errors
///
/// Returns [`AccountError::Store`] if hashing fails, which would mean the
/// process is out of memory rather than anything the caller did.
pub fn hash(password: &str) -> Result<String> {
    // The salt comes from the OS-seeded CSPRNG here rather than through
    // password-hash's own `generate`, which needs the `getrandom` feature of
    // its bundled rand_core — a second copy of that crate for one call.
    let mut bytes = [0u8; SALT_BYTES];
    rng().fill_bytes(&mut bytes);
    let salt = SaltString::encode_b64(&bytes)
        .map_err(|error| AccountError::Store(format!("could not encode the salt: {error}")))?;
    argon2_policy()?
        .hash_password(password.as_bytes(), &salt)
        .map(|hash| hash.to_string())
        .map_err(|error| AccountError::Store(format!("could not hash the password: {error}")))
}

/// Hash without occupying an async runtime worker thread.
pub async fn hash_async(password: String) -> Result<String> {
    tokio::task::spawn_blocking(move || hash(&password))
        .await
        .map_err(|error| AccountError::Store(format!("password worker failed: {error}")))?
}

/// Whether a password matches a stored hash.
///
/// A malformed stored hash counts as "does not match" rather than as an error,
/// so a corrupted row cannot be used to tell one account from another.
#[must_use]
pub fn verify(password: &str, stored: &str) -> bool {
    if password.len() > MAX_VERIFICATION_PASSWORD_BYTES {
        return false;
    }

    let Ok(parsed) = PasswordHash::new(stored) else {
        return false;
    };
    let Ok(verifier) = argon2_policy() else {
        return false;
    };
    verifier
        .verify_password(password.as_bytes(), &parsed)
        .is_ok()
}

/// Verify without occupying an async runtime worker thread.
pub async fn verify_async(password: String, stored: String) -> bool {
    tokio::task::spawn_blocking(move || verify(&password, &stored))
        .await
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verification_rejects_unbounded_input_before_argon2() {
        let oversized = "x".repeat(MAX_VERIFICATION_PASSWORD_BYTES + 1);
        assert!(!verify(&oversized, "not-even-a-hash"));
    }

    #[test]
    fn current_hashes_are_marked_current_and_older_costs_need_rehash() {
        let current = hash("correct horse battery staple").expect("hash");
        assert!(!needs_rehash(&current));
        assert!(needs_rehash(
            "$argon2id$v=19$m=8192,t=1,p=1$c29tZXNhbHQ$YWJj"
        ));
        assert!(needs_rehash(
            "$argon2i$v=19$m=19456,t=2,p=1$c29tZXNhbHQ$YWJj"
        ));
        assert!(needs_rehash("not-a-phc-hash"));
        assert_eq!(ARGON2_POLICY_VERSION, "argon2id-v1");
    }
}
