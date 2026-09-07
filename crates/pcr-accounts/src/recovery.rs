//! The way back in after a forgotten password, without an email server.
//!
//! This application asks for no verification email, on purpose: an address, a
//! password, and the work is yours. That choice has a consequence which is easy
//! to miss until somebody hits it — with no address to send to, a forgotten
//! password is an account nobody can ever open again, and every project inside
//! it is gone with it.
//!
//! A recovery code closes that without bringing email back. It is generated at
//! sign-up, shown exactly once, and stored the way a password is. Presenting it
//! proves the same thing a reset link would prove — that you are the person who
//! made this account — and it does so with no mail server to run, no queue to
//! drain, no deliverability to fight, and nobody in the middle who gets to read
//! the address.
//!
//! What it is not: a second password. It cannot sign you in, it cannot be used
//! twice, and using it ends every session the account has. It does one thing,
//! once, and then it is replaced.

use rand::{rng, RngExt};

/// How many groups the code is printed in.
const GROUPS: usize = 5;

/// How many characters in each group.
const PER_GROUP: usize = 5;

/// The alphabet a code is drawn from.
///
/// Crockford's base32: the digits and letters minus `I`, `L`, `O` and `U`.
/// The first three are dropped because they are unreadable next to `1` and `0`
/// in most typefaces, and this is a string people copy off a screen and type
/// back in months later, quite possibly having written it on paper. `U` is
/// dropped so the generator cannot produce a word somebody would be
/// embarrassed to read out to support.
const ALPHABET: &[u8] = b"0123456789ABCDEFGHJKMNPQRSTVWXYZ";

/// How much randomness a code carries, for the doc-comment above to be true.
///
/// Twenty-five characters from a 32-letter alphabet is 125 bits. That is past
/// the point where guessing is a strategy even without the attempt limit — the
/// limit exists to stop the *attempts* being a load, not because the code needs
/// it.
pub const ENTROPY_BITS: usize = GROUPS * PER_GROUP * 5;

/// How many wrong codes an account tolerates before recovery is shut for a while.
///
/// Counted against the account rather than the caller. A per-caller ceiling is
/// the right shape for password guessing — one password guessed from a thousand
/// addresses is still one password — but the only realistic attack on a
/// 125-bit code is many attempts against a single account, and those spread
/// across addresses trivially. This is the counter that spreading does not
/// defeat.
pub const MAX_ATTEMPTS: i32 = 10;

/// How long the shutter stays down.
///
/// It expires rather than latching. A permanent lockout would turn a nuisance
/// into a way of denying an account to the person who actually owns it.
pub const LOCKOUT_MINUTES: i64 = 60;

/// A freshly generated code.
///
/// The plain text exists exactly once, on its way to the person. Only the hash
/// is written down.
#[derive(Clone)]
pub struct RecoveryCode {
    /// Give this to the person and never store it.
    pub plain: String,
}

impl std::fmt::Debug for RecoveryCode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("RecoveryCode")
            .field("plain", &"[REDACTED]")
            .finish()
    }
}

impl RecoveryCode {
    /// Draw a new code from the operating system randomness source.
    #[must_use]
    pub fn generate() -> Self {
        let mut generator = rng();
        let mut groups = Vec::with_capacity(GROUPS);

        for _ in 0..GROUPS {
            let group: String = (0..PER_GROUP)
                .map(|_| ALPHABET[generator.random_range(0..ALPHABET.len())] as char)
                .collect();
            groups.push(group);
        }

        Self {
            plain: groups.join("-"),
        }
    }
}

/// Put a typed code into the one shape it is compared in.
///
/// People retype these from paper. They will use spaces instead of hyphens,
/// lower case, or neither — and every one of those is the same code. Comparing
/// the typed form directly would reject the right code for the wrong reason,
/// which on the one screen somebody reaches while already locked out is the
/// worst possible place to be pedantic.
#[must_use]
pub fn normalise(typed: &str) -> String {
    typed
        .chars()
        .filter(|character| character.is_ascii_alphanumeric())
        .map(|character| character.to_ascii_uppercase())
        .collect()
}

/// Whether a typed code could be a code at all, before any database work.
///
/// Cheap rejection of an empty box or a pasted paragraph. It is deliberately
/// not a check that the code is *correct* — that comparison happens against the
/// stored hash, in constant time, and this one must not become a way to learn
/// anything about the real code.
#[must_use]
pub fn looks_like_a_code(typed: &str) -> bool {
    let cleaned = normalise(typed);
    cleaned.len() == GROUPS * PER_GROUP && cleaned.bytes().all(|byte| ALPHABET.contains(&byte))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_code_is_five_groups_of_five() {
        let code = RecoveryCode::generate().plain;
        let groups: Vec<&str> = code.split('-').collect();
        assert_eq!(groups.len(), GROUPS);
        assert!(groups.iter().all(|group| group.len() == PER_GROUP));
    }

    #[test]
    fn two_codes_are_not_the_same_code() {
        let one = RecoveryCode::generate().plain;
        let other = RecoveryCode::generate().plain;
        assert_ne!(one, other);
    }

    #[test]
    fn debug_output_never_exposes_the_recovery_code() {
        let code = RecoveryCode::generate();
        let debug = format!("{code:?}");
        assert!(debug.contains("[REDACTED]"));
        assert!(!debug.contains(&code.plain));
    }

    #[test]
    fn the_alphabet_leaves_out_the_letters_people_misread() {
        // A code is copied off a screen and typed back months later, quite
        // possibly from paper. `I` beside `1` and `O` beside `0` is where that
        // goes wrong.
        for confusing in b"ILOU" {
            assert!(!ALPHABET.contains(confusing));
        }
    }

    #[test]
    fn a_code_carries_enough_randomness_that_guessing_is_not_a_strategy() {
        assert_eq!(ENTROPY_BITS, 125);
    }

    #[test]
    fn the_same_code_typed_carelessly_is_still_the_same_code() {
        // The one screen somebody reaches while already locked out is the worst
        // place to reject the right answer over punctuation.
        let code = RecoveryCode::generate().plain;
        let careless = code.to_lowercase().replace('-', " ");
        assert_eq!(normalise(&code), normalise(&careless));
        assert_eq!(normalise(&code), normalise(&code.replace('-', "")));
    }

    #[test]
    fn a_generated_code_looks_like_a_code() {
        assert!(looks_like_a_code(&RecoveryCode::generate().plain));
    }

    #[test]
    fn an_empty_box_or_a_pasted_paragraph_does_not() {
        assert!(!looks_like_a_code(""));
        assert!(!looks_like_a_code("not a recovery code at all"));
        // Right length, wrong alphabet.
        assert!(!looks_like_a_code("IIIII-IIIII-IIIII-IIIII-IIIII"));
    }
}
