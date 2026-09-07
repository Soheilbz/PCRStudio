//! Domain-neutral security primitives shared by PCRStudio application crates.

#![forbid(unsafe_code)]
#![warn(missing_docs)]
//!
//! This crate deliberately knows nothing about accounts, projects, HTTP or the
//! database.  It exists so those domains can share one bearer-token convention
//! without depending sideways on each other's implementation.

use rand::{rng, Rng};
use sha2::{Digest, Sha256};

/// 32 bytes of OS randomness, hex encoded.
pub const TOKEN_BYTES: usize = 32;
/// A canonical token contains two lowercase hex characters per byte.
pub const TOKEN_HEX_CHARS: usize = TOKEN_BYTES * 2;

/// A freshly minted opaque bearer credential.
#[derive(Clone)]
pub struct BearerToken {
    /// Give this to the client exactly once.
    pub plain: String,
    /// Store this instead of the plain token.
    pub hashed: String,
}

impl std::fmt::Debug for BearerToken {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("BearerToken")
            .field("plain", &"[REDACTED]")
            .field("hashed", &"[REDACTED]")
            .finish()
    }
}

impl BearerToken {
    /// Mint a new token using the operating-system randomness source.
    #[must_use]
    pub fn generate() -> Self {
        let mut bytes = [0u8; TOKEN_BYTES];
        rng().fill_bytes(&mut bytes);
        let plain = hex::encode(bytes);
        let hashed = hash_bearer_token(&plain);
        Self { plain, hashed }
    }
}

/// SHA-256 representation used for uniformly random bearer credentials.
///
/// A slow password hash is intentionally not used: the input has 256 bits of
/// uniform entropy and has no human dictionary to defend against.
#[must_use]
pub fn hash_bearer_token(token: &str) -> String {
    hex::encode(Sha256::digest(token.as_bytes()))
}

/// Cheap shape validation before a token is considered as an authorization key.
#[must_use]
pub fn looks_like_bearer_token(token: &str) -> bool {
    token.len() == TOKEN_HEX_CHARS
        && token
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

/// Failure while resolving a text secret from direct/file deployment sources.
#[derive(Debug, thiserror::Error)]
pub enum SecretSourceError {
    /// A configured environment value cannot be represented as UTF-8.
    #[error("{0} contains a non-Unicode value that PCRStudio cannot interpret")]
    NonUnicodeEnvironment(&'static str),
    /// Both direct and file-backed forms were configured simultaneously.
    #[error("{direct} and {file} cannot both be set; use exactly one secret source")]
    ConflictingSources {
        /// Direct environment variable.
        direct: &'static str,
        /// File-path environment variable.
        file: &'static str,
    },
    /// The configured file-backed secret could not be read.
    #[error("{source_name} points to an unreadable secret file {path:?}: {detail}")]
    FileUnreadable {
        /// File-path environment variable that selected the file.
        source_name: &'static str,
        /// Configured secret-file path.
        path: String,
        /// Underlying I/O diagnostic for operator logs/CLI surfaces.
        detail: String,
    },
}

fn unicode_environment(
    name: &'static str,
) -> std::result::Result<Option<String>, SecretSourceError> {
    match std::env::var(name) {
        Ok(value) => Ok(Some(value)),
        Err(std::env::VarError::NotPresent) => Ok(None),
        Err(std::env::VarError::NotUnicode(_)) => {
            Err(SecretSourceError::NonUnicodeEnvironment(name))
        }
    }
}

/// Resolve one opaque text secret from mutually-exclusive direct/file env sources.
///
/// Secret content is not normalized: direct environment values are returned
/// byte-for-byte, and file-backed values preserve every character except one
/// conventional terminal line ending (`\n` or `\r\n`). This keeps a generic
/// security primitive from silently changing a legitimate credential while
/// still supporting the newline commonly added by text secret files.
///
/// Empty direct values and empty files (after removing one terminal line
/// ending) are treated as absent. This is the canonical optional-secret
/// convention used by Compose, where an empty mounted file disables an optional
/// capability. Requiredness and content-specific rules such as "no whitespace"
/// belong to the consumer (for example the database or NCBI validators), not
/// this resolver.
///
/// # Errors
/// Returns [`SecretSourceError`] for non-Unicode configuration, conflicting
/// sources, or unreadable files.
pub fn secret_from_environment(
    direct_name: &'static str,
    file_name: &'static str,
) -> std::result::Result<Option<String>, SecretSourceError> {
    resolve_secret_sources(
        direct_name,
        file_name,
        unicode_environment(direct_name)?,
        unicode_environment(file_name)?,
    )
}

fn strip_one_terminal_line_ending(mut value: String) -> String {
    if value.ends_with('\n') {
        value.pop();
        if value.ends_with('\r') {
            value.pop();
        }
    }
    value
}

fn resolve_secret_sources(
    direct_name: &'static str,
    file_name: &'static str,
    direct: Option<String>,
    file: Option<String>,
) -> std::result::Result<Option<String>, SecretSourceError> {
    let direct = direct.filter(|value| !value.is_empty());
    let file = file.filter(|value| !value.is_empty());

    if direct.is_some() && file.is_some() {
        return Err(SecretSourceError::ConflictingSources {
            direct: direct_name,
            file: file_name,
        });
    }
    if let Some(value) = direct {
        return Ok(Some(value));
    }
    let Some(path) = file else {
        return Ok(None);
    };

    let value =
        std::fs::read_to_string(&path).map_err(|error| SecretSourceError::FileUnreadable {
            source_name: file_name,
            path: path.clone(),
            detail: error.to_string(),
        })?;
    let value = strip_one_terminal_line_ending(value);
    Ok((!value.is_empty()).then_some(value))
}

/// Compare two secret byte strings without data-dependent early exit when their
/// lengths match. Length itself is not treated as secret; callers should use a
/// fixed-shape credential when that matters.
#[must_use]
pub fn constant_time_equal(expected: &[u8], given: &[u8]) -> bool {
    if expected.len() != given.len() {
        return false;
    }
    expected
        .iter()
        .zip(given)
        .fold(0_u8, |diff, (&left, &right)| diff | (left ^ right))
        == 0
}

/// Return a canonical lowercase SHA-256 hex identity after trimming surrounding
/// environment whitespace. Uppercase/mixed-case input is deliberately rejected
/// instead of normalized so release/scientific identities have one byte-level
/// representation across API, runner and readiness paths.
#[must_use]
pub fn canonical_sha256(value: &str) -> Option<&str> {
    let value = value.trim();
    (value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)))
    .then_some(value)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generated_bearer_tokens_have_one_canonical_shape() {
        let token = BearerToken::generate();
        assert_eq!(token.plain.len(), TOKEN_HEX_CHARS);
        assert!(looks_like_bearer_token(&token.plain));
        assert_eq!(token.hashed, hash_bearer_token(&token.plain));
        assert_ne!(token.plain, token.hashed);
    }

    #[test]
    fn bearer_token_debug_never_exposes_credentials() {
        let token = BearerToken::generate();
        let debug = format!("{token:?}");
        assert!(debug.contains("[REDACTED]"));
        assert!(!debug.contains(&token.plain));
        assert!(!debug.contains(&token.hashed));
    }

    #[test]
    fn malformed_path_segments_are_not_authorization_candidates() {
        assert!(!looks_like_bearer_token("short"));
        assert!(!looks_like_bearer_token(&"z".repeat(TOKEN_HEX_CHARS)));
        assert!(!looks_like_bearer_token(&"A".repeat(TOKEN_HEX_CHARS)));
    }

    #[test]
    fn secret_sources_have_one_canonical_direct_and_file_policy() {
        let path = std::env::temp_dir().join(format!(
            "pcrstudio-secret-source-{}-{}.txt",
            std::process::id(),
            rand::random::<u64>()
        ));
        std::fs::write(&path, "  file-secret  \r\n").expect("temporary secret is writable");
        let path_text = path.to_string_lossy().into_owned();

        assert_eq!(
            resolve_secret_sources(
                "PCR_TEST_SECRET",
                "PCR_TEST_SECRET_FILE",
                Some("  direct-secret  ".to_owned()),
                None,
            )
            .expect("direct secret resolves")
            .as_deref(),
            Some("  direct-secret  ")
        );
        assert_eq!(
            resolve_secret_sources(
                "PCR_TEST_SECRET",
                "PCR_TEST_SECRET_FILE",
                None,
                Some(path_text.clone()),
            )
            .expect("file-backed secret resolves")
            .as_deref(),
            Some("  file-secret  ")
        );

        let conflict = resolve_secret_sources(
            "PCR_TEST_SECRET",
            "PCR_TEST_SECRET_FILE",
            Some("one".to_owned()),
            Some(path_text.clone()),
        )
        .expect_err("two active secret sources fail closed");
        assert!(matches!(
            conflict,
            SecretSourceError::ConflictingSources { .. }
        ));

        std::fs::write(&path, " \t\r\n").expect("temporary secret is writable");
        assert_eq!(
            resolve_secret_sources(
                "PCR_TEST_SECRET",
                "PCR_TEST_SECRET_FILE",
                None,
                Some(path_text.clone()),
            )
            .expect("generic secret resolver preserves content whitespace")
            .as_deref(),
            Some(" \t")
        );

        std::fs::write(&path, "\r\n").expect("temporary secret is writable");
        assert_eq!(
            resolve_secret_sources(
                "PCR_TEST_SECRET",
                "PCR_TEST_SECRET_FILE",
                None,
                Some(path_text),
            )
            .expect("empty optional secret file disables the capability"),
            None
        );

        let _ = std::fs::remove_file(path);
    }

    #[test]
    fn only_empty_secret_environment_values_are_absent() {
        assert_eq!(
            resolve_secret_sources(
                "PCR_TEST_SECRET",
                "PCR_TEST_SECRET_FILE",
                Some(String::new()),
                Some(String::new()),
            )
            .expect("empty sources are absent"),
            None
        );
        assert!(matches!(
            resolve_secret_sources(
                "PCR_TEST_SECRET",
                "PCR_TEST_SECRET_FILE",
                Some(" ".to_owned()),
                Some("\t".to_owned()),
            ),
            Err(SecretSourceError::ConflictingSources { .. })
        ));
    }

    #[test]
    fn secret_comparison_is_exact() {
        assert!(constant_time_equal(
            b"abcdefghijklmnopqrstuvwx",
            b"abcdefghijklmnopqrstuvwx"
        ));
        assert!(!constant_time_equal(
            b"abcdefghijklmnopqrstuvwx",
            b"abcdefghijklmnopqrstuvwy"
        ));
        assert!(!constant_time_equal(b"short", b"shorter"));
    }

    #[test]
    fn release_sha256_identity_has_one_canonical_representation() {
        let digest = "a".repeat(64);
        assert_eq!(canonical_sha256(&digest), Some(digest.as_str()));
        assert_eq!(
            canonical_sha256(&format!("  {digest}\n")),
            Some(digest.as_str())
        );
        assert!(canonical_sha256(&"A".repeat(64)).is_none());
        assert!(canonical_sha256(&"g".repeat(64)).is_none());
        assert!(canonical_sha256("short").is_none());
    }
}
