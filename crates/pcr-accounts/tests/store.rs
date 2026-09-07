//! What the account store does against a real database.
//!
//! These need PostgreSQL. Start one with `docker compose up -d db` and set
//! `PCR_TEST_DATABASE_URL`; without it every test here reports that it did
//! nothing rather than passing quietly.
//!
//! Each test gets its own schema, so they can run in parallel and none of them
//! sees another's rows.

use pcr_accounts::{AccountError, Accounts, RecoveryCode, User};
use sqlx::PgPool;

/// Open a store in a schema of its own, or `None` when no database is configured.
async fn store() -> Option<Accounts> {
    let Ok(base) = std::env::var("PCR_TEST_DATABASE_URL") else {
        if std::env::var("CI").is_ok_and(|value| value.eq_ignore_ascii_case("true")) {
            panic!("PCR_TEST_DATABASE_URL is required in CI; refusing a green database-test skip");
        }
        eprintln!(
            "SKIPPED: set PCR_TEST_DATABASE_URL to run the account store tests \
             (docker compose up -d db)"
        );
        return None;
    };

    let schema = format!("t{}", uuid::Uuid::new_v4().simple());

    let admin = PgPool::connect(&base)
        .await
        .expect("PCR_TEST_DATABASE_URL should point at a reachable database");
    sqlx::query(sqlx::AssertSqlSafe(format!(r#"CREATE SCHEMA "{schema}""#)))
        .execute(&admin)
        .await
        .expect("the test schema should be creatable");
    admin.close().await;

    let separator = if base.contains('?') { '&' } else { '?' };
    let url = format!("{base}{separator}options=-c%20search_path%3D{schema}");

    Some(
        Accounts::connect(&url)
            .await
            .expect("the store should open and migrate"),
    )
}

/// Skips the body when no database is configured.
macro_rules! with_store {
    ($name:ident) => {
        let Some($name) = store().await else { return };
    };
}

async fn a_user(accounts: &Accounts) -> User {
    // Registering also mints a recovery code, which most of these tests do not
    // care about. The ones that do use  below.
    a_user_with_code(accounts).await.0
}

async fn a_user_with_code(accounts: &Accounts) -> (User, RecoveryCode) {
    accounts
        .register(
            "Ada@Example.org",
            "  Ada Lovelace  ",
            "correct horse battery",
        )
        .await
        .expect("registration succeeds")
}

#[tokio::test]
async fn registering_trims_the_name_and_keeps_the_typed_email() {
    with_store!(accounts);
    let user = a_user(&accounts).await;
    assert_eq!(user.display_name, "Ada Lovelace");
    assert_eq!(user.email, "Ada@Example.org");
}

#[tokio::test]
async fn the_same_address_in_another_case_is_still_taken() {
    with_store!(accounts);
    a_user(&accounts).await;
    let again = accounts
        .register("ADA@example.ORG", "Someone Else", "another long password")
        .await;
    assert_eq!(again.unwrap_err(), AccountError::EmailTaken);
}

#[tokio::test]
async fn signing_in_is_case_insensitive_on_the_address() {
    with_store!(accounts);
    let user = a_user(&accounts).await;
    let signed_in = accounts
        .authenticate("  ADA@EXAMPLE.ORG  ", "correct horse battery")
        .await
        .expect("the address matches regardless of case");
    assert_eq!(signed_in.id, user.id);
}

#[tokio::test]
async fn an_unknown_address_and_a_wrong_password_fail_identically() {
    with_store!(accounts);
    a_user(&accounts).await;

    let unknown = accounts
        .authenticate("nobody@example.org", "correct horse battery")
        .await;
    let wrong = accounts
        .authenticate("ada@example.org", "not the password")
        .await;

    assert_eq!(unknown.unwrap_err(), AccountError::InvalidCredentials);
    assert_eq!(wrong.unwrap_err(), AccountError::InvalidCredentials);
}

#[tokio::test]
async fn a_session_identifies_its_user_until_it_is_ended() {
    with_store!(accounts);
    let user = a_user(&accounts).await;

    let token = accounts
        .start_session(&user.id)
        .await
        .expect("session starts");
    let found = accounts
        .user_for_session(&token.plain)
        .await
        .expect("the token resolves");
    assert_eq!(found.id, user.id);

    accounts.end_session(&token.plain).await.expect("sign out");
    assert_eq!(
        accounts.user_for_session(&token.plain).await.unwrap_err(),
        AccountError::SessionEnded
    );
}

#[tokio::test]
async fn an_invented_token_resolves_to_nobody() {
    with_store!(accounts);
    a_user(&accounts).await;
    assert_eq!(
        accounts
            .user_for_session("not a real token")
            .await
            .unwrap_err(),
        AccountError::SessionEnded
    );
}

#[tokio::test]
async fn changing_the_password_keeps_this_session_and_ends_the_others() {
    with_store!(accounts);
    let user = a_user(&accounts).await;
    let here = accounts
        .start_session(&user.id)
        .await
        .expect("session starts");
    let elsewhere = accounts
        .start_session(&user.id)
        .await
        .expect("session starts");

    accounts
        .change_password(
            &user.id,
            "correct horse battery",
            "a different long one",
            Some(&here.plain),
        )
        .await
        .expect("the current password matches");

    assert!(accounts.user_for_session(&here.plain).await.is_ok());
    assert_eq!(
        accounts
            .user_for_session(&elsewhere.plain)
            .await
            .unwrap_err(),
        AccountError::SessionEnded
    );
    assert!(accounts
        .authenticate("ada@example.org", "a different long one")
        .await
        .is_ok());
}

#[tokio::test]
async fn the_wrong_current_password_changes_nothing() {
    with_store!(accounts);
    let user = a_user(&accounts).await;

    let error = accounts
        .change_password(&user.id, "wrong", "a different long one", None)
        .await
        .unwrap_err();
    assert_eq!(error, AccountError::InvalidCredentials);
    assert!(accounts
        .authenticate("ada@example.org", "correct horse battery")
        .await
        .is_ok());
}

#[tokio::test]
async fn renaming_shows_up_and_an_empty_name_is_refused() {
    with_store!(accounts);
    let user = a_user(&accounts).await;

    let renamed = accounts.rename(&user.id, " Ada L. ").await.expect("rename");
    assert_eq!(renamed.display_name, "Ada L.");

    let error = accounts.rename(&user.id, "   ").await.unwrap_err();
    assert!(matches!(error, AccountError::InvalidName(_)));
}

#[tokio::test]
async fn deleting_an_account_takes_its_sessions_with_it() {
    with_store!(accounts);
    let user = a_user(&accounts).await;
    let token = accounts
        .start_session(&user.id)
        .await
        .expect("session starts");

    assert_eq!(
        accounts.delete(&user.id, "wrong").await.unwrap_err(),
        AccountError::InvalidCredentials
    );

    accounts
        .delete(&user.id, "correct horse battery")
        .await
        .expect("the password matches");

    assert_eq!(
        accounts.user_for_session(&token.plain).await.unwrap_err(),
        AccountError::SessionEnded
    );
    assert_eq!(
        accounts.user(&user.id).await.unwrap_err(),
        AccountError::NoSuchUser
    );
}

#[tokio::test]
async fn signing_out_everywhere_reports_how_many_were_ended() {
    with_store!(accounts);
    let user = a_user(&accounts).await;
    accounts.start_session(&user.id).await.expect("one");
    accounts.start_session(&user.id).await.expect("two");

    assert_eq!(accounts.end_all_sessions(&user.id).await.expect("ended"), 2);
    assert_eq!(
        accounts
            .end_all_sessions(&user.id)
            .await
            .expect("none left"),
        0
    );
}

#[tokio::test]
async fn the_purge_leaves_live_sessions_alone() {
    with_store!(accounts);
    let user = a_user(&accounts).await;
    let token = accounts
        .start_session(&user.id)
        .await
        .expect("session starts");

    assert_eq!(
        accounts
            .purge_expired_sessions()
            .await
            .expect("the purge runs"),
        0
    );
    assert!(accounts.user_for_session(&token.plain).await.is_ok());
}

#[tokio::test]
async fn a_rate_limit_bucket_is_shared_and_atomic() {
    with_store!(accounts);
    let key = format!("test-{}", uuid::Uuid::new_v4());

    assert!(accounts
        .allow_rate_limit("test", &key, 2, 60)
        .await
        .expect("first shared hit succeeds"));
    assert!(accounts
        .allow_rate_limit("test", &key, 2, 60)
        .await
        .expect("second shared hit succeeds"));
    assert!(!accounts
        .allow_rate_limit("test", &key, 2, 60)
        .await
        .expect("third shared hit is denied"));
}

/* â”€â”€ Getting back in after a forgotten password â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

#[tokio::test]
async fn registering_issues_a_recovery_code() {
    // Issued here rather than offered later, because later never comes: nobody
    // visits a settings page to prepare for losing a password, and the moment
    // they need one is the moment they can no longer get one.
    with_store!(accounts);
    let (_, code) = a_user_with_code(&accounts).await;
    assert!(pcr_accounts::recovery::looks_like_a_code(&code.plain));
}

#[tokio::test]
async fn a_recovery_code_sets_a_new_password_and_hands_back_a_fresh_one() {
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;

    let (recovered, next) = accounts
        .recover(&user.email, &code.plain, "a brand new passphrase")
        .await
        .expect("the code should work");

    assert_eq!(recovered.id, user.id);
    // The used code is spent, so leaving the account without one would make the
    // next forgotten password the last one.
    assert_ne!(next.plain, code.plain);

    accounts
        .authenticate(&user.email, "a brand new passphrase")
        .await
        .expect("the new password should work");
}

#[tokio::test]
async fn a_code_cannot_be_used_twice() {
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;

    accounts
        .recover(&user.email, &code.plain, "a brand new passphrase")
        .await
        .expect("the first use should work");

    let error = accounts
        .recover(&user.email, &code.plain, "another passphrase entirely")
        .await
        .expect_err("the second use should not");
    assert!(matches!(error, AccountError::InvalidCredentials));
}

#[tokio::test]
async fn recovering_ends_every_session() {
    // Somebody doing this either forgot their password or is recovering from
    // someone else having it. In the second case the open sessions are the
    // attacker's, and leaving them running would make the recovery pointless.
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;

    let session = accounts
        .start_session(&user.id)
        .await
        .expect("a session starts");
    accounts
        .user_for_session(&session.plain)
        .await
        .expect("and works");

    accounts
        .recover(&user.email, &code.plain, "a brand new passphrase")
        .await
        .expect("recovery works");

    let error = accounts
        .user_for_session(&session.plain)
        .await
        .expect_err("the old session should be gone");
    assert!(matches!(error, AccountError::SessionEnded));
}

#[tokio::test]
async fn the_same_code_typed_carelessly_still_works() {
    // This is the one screen somebody reaches while already locked out. It is
    // the worst possible place to reject the right answer over punctuation.
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;

    let careless = code.plain.to_lowercase().replace('-', " ");
    accounts
        .recover(&user.email, &careless, "a brand new passphrase")
        .await
        .expect("lower case with spaces is the same code");
}

#[tokio::test]
async fn an_unknown_address_and_a_wrong_code_answer_alike() {
    // Telling them apart would make this a way to ask whether somebody has an
    // account here, which is exactly what signing in already refuses to answer.
    with_store!(accounts);
    let (user, _) = a_user_with_code(&accounts).await;
    let wrong = "AAAAA-AAAAA-AAAAA-AAAAA-AAAAA";

    let wrong_code = accounts
        .recover(&user.email, wrong, "a new passphrase")
        .await
        .expect_err("a wrong code");
    let unknown = accounts
        .recover("nobody@example.org", wrong, "a new passphrase")
        .await
        .expect_err("an unknown address");

    assert!(matches!(wrong_code, AccountError::InvalidCredentials));
    assert!(matches!(unknown, AccountError::InvalidCredentials));
}

#[tokio::test]
async fn too_many_wrong_codes_shuts_recovery_for_that_account() {
    // Counted against the account rather than the caller. A per-caller ceiling
    // is the right shape for password guessing, but the only realistic attack
    // on a 125-bit code is many attempts against one account â€” and those spread
    // across addresses trivially.
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;
    let wrong = "AAAAA-AAAAA-AAAAA-AAAAA-AAAAA";

    for _ in 0..pcr_accounts::recovery::MAX_ATTEMPTS {
        let _ = accounts
            .recover(&user.email, wrong, "a new passphrase")
            .await;
    }

    // Even the correct code is refused now, and refused differently: "stop and
    // come back later" rather than "that was wrong". Telling somebody their
    // right code was wrong is how they conclude the account is unrecoverable.
    let error = accounts
        .recover(&user.email, &code.plain, "a new passphrase")
        .await
        .expect_err("recovery should be shut");
    assert!(matches!(error, AccountError::RecoveryLocked), "{error:?}");
}

#[tokio::test]
async fn the_lock_trips_exactly_at_the_documented_threshold() {
    /*
     * The counter is incremented atomically in the database, and the attempt
     * that reaches the ceiling sees that itself. So the count of wrong codes
     * that shuts recovery is exactly `MAX_ATTEMPTS`: one short, and a wrong
     * code is still only a wrong code; on the last one, the answer changes.
     */
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;
    let wrong = "AAAAA-AAAAA-AAAAA-AAAAA-AAAAA";

    for remaining in (1..=pcr_accounts::recovery::MAX_ATTEMPTS).rev() {
        let error = accounts
            .recover(&user.email, wrong, "a new passphrase")
            .await
            .expect_err("a wrong code");
        match error {
            AccountError::InvalidCredentials => {
                assert!(
                    remaining > 1,
                    "attempt {remaining} before the lock should not shut it"
                )
            }
            AccountError::RecoveryLocked => {
                assert_eq!(remaining, 1, "the lock should trip on the last attempt")
            }
            other => panic!("unexpected answer: {other:?}"),
        }
    }

    // And it stays shut: even the correct code is refused while the shutter
    // is down.
    let error = accounts
        .recover(&user.email, &code.plain, "a new passphrase")
        .await
        .expect_err("recovery should be shut now");
    assert!(matches!(error, AccountError::RecoveryLocked), "{error:?}");
}

#[tokio::test]
async fn a_successful_recovery_clears_the_attempt_count() {
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;
    let wrong = "AAAAA-AAAAA-AAAAA-AAAAA-AAAAA";

    // Some wrong attempts, but not enough to shut it.
    for _ in 0..3 {
        let _ = accounts
            .recover(&user.email, wrong, "a new passphrase")
            .await;
    }

    let (_, next) = accounts
        .recover(&user.email, &code.plain, "a brand new passphrase")
        .await
        .expect("the right code still works");

    // And the count is back to zero, so the earlier failures do not carry over
    // into the next time this is needed.
    for _ in 0..3 {
        let _ = accounts
            .recover(&user.email, wrong, "another passphrase")
            .await;
    }
    accounts
        .recover(&user.email, &next.plain, "a third passphrase")
        .await
        .expect("the new code works, so the counter reset");
}

#[tokio::test]
async fn a_recovery_code_will_not_sign_anybody_in() {
    // It is not a second password. It does one thing, once.
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;

    let error = accounts
        .authenticate(&user.email, &code.plain)
        .await
        .expect_err("a recovery code is not a password");
    assert!(matches!(error, AccountError::InvalidCredentials));
}

#[tokio::test]
async fn the_code_can_be_replaced_by_somebody_who_knows_the_password() {
    with_store!(accounts);
    let (user, first) = a_user_with_code(&accounts).await;

    let second = accounts
        .reissue_recovery_code(&user.id, "correct horse battery")
        .await
        .expect("the password proves who is asking");
    assert_ne!(second.plain, first.plain);

    // And the old one stops working the moment the new one exists.
    let error = accounts
        .recover(&user.email, &first.plain, "a new passphrase")
        .await
        .expect_err("the replaced code should be dead");
    assert!(matches!(error, AccountError::InvalidCredentials));
}

#[tokio::test]
async fn replacing_the_code_needs_the_password() {
    with_store!(accounts);
    let (user, _) = a_user_with_code(&accounts).await;

    let error = accounts
        .reissue_recovery_code(&user.id, "not the password")
        .await
        .expect_err("a wrong password should not mint a code");
    assert!(matches!(error, AccountError::InvalidCredentials));
}

#[tokio::test]
async fn the_account_can_say_whether_it_has_a_code_and_when() {
    with_store!(accounts);
    let (user, _) = a_user_with_code(&accounts).await;

    let issued = accounts
        .recovery_status(&user.id)
        .await
        .expect("the status is readable");
    assert!(issued.is_some(), "a new account should have a code");
}

/* â”€â”€ What somebody has told us about how they work â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

/// One registered account, by its id.
async fn someone(accounts: &Accounts, email: &str) -> String {
    accounts
        .register(email, "Ada Lovelace", "a long enough password")
        .await
        .expect("the account registers")
        .0
        .id
}

#[tokio::test]
async fn preferences_start_empty_and_survive_being_set() {
    with_store!(accounts);
    let user = someone(&accounts, "settings@example.org").await;

    // Empty rather than absent, so a caller reads a shape rather than an
    // option â€” a preference nobody has set falls through to whatever the
    // application would have done anyway.
    assert_eq!(
        accounts.preferences(&user).await.expect("readable"),
        serde_json::json!({})
    );

    let wanted = serde_json::json!({ "preferredPolymerase": "proofreading" });
    accounts
        .set_preferences(&user, &wanted)
        .await
        .expect("saves");
    assert_eq!(accounts.preferences(&user).await.expect("readable"), wanted);
}

#[tokio::test]
async fn setting_preferences_replaces_rather_than_merges() {
    /*
     * A merge cannot express "unset", and a settings screen that can turn
     * something on but never off is one people stop trusting. So the whole
     * object is written each time, and this is the test that keeps it that way.
     */
    with_store!(accounts);
    let user = someone(&accounts, "unset@example.org").await;

    accounts
        .set_preferences(&user, &serde_json::json!({ "preferredPolymerase": "rpa" }))
        .await
        .expect("saves");
    accounts
        .set_preferences(&user, &serde_json::json!({}))
        .await
        .expect("clears");

    assert_eq!(
        accounts.preferences(&user).await.expect("readable"),
        serde_json::json!({})
    );
}

#[tokio::test]
async fn preferences_belong_to_one_account() {
    with_store!(accounts);
    let mine = someone(&accounts, "mine-prefs@example.org").await;
    let theirs = someone(&accounts, "theirs-prefs@example.org").await;

    accounts
        .set_preferences(
            &mine,
            &serde_json::json!({ "preferredPolymerase": "proofreading" }),
        )
        .await
        .expect("saves");

    assert_eq!(
        accounts.preferences(&theirs).await.expect("readable"),
        serde_json::json!({}),
        "one account's settings are not another's"
    );
}

#[tokio::test]
async fn registration_can_commit_the_first_session_with_the_account() {
    with_store!(accounts);
    let (user, recovery, token) = accounts
        .register_and_start_session(
            "atomic-register@example.org",
            "Atomic Register",
            "correct horse battery",
        )
        .await
        .expect("registration and its first session commit together");

    assert!(pcr_accounts::recovery::looks_like_a_code(&recovery.plain));
    assert_eq!(
        accounts
            .user_for_session(&token.plain)
            .await
            .expect("the returned session is already durable")
            .id,
        user.id
    );
}

#[tokio::test]
async fn recovery_can_commit_credential_rotation_and_the_new_session_together() {
    with_store!(accounts);
    let (user, code) = accounts
        .register(
            "atomic-recovery@example.org",
            "Atomic Recovery",
            "correct horse battery",
        )
        .await
        .expect("registration succeeds");
    let old = accounts
        .start_session(&user.id)
        .await
        .expect("old session starts");

    let (recovered, next, replacement) = accounts
        .recover_and_start_session(&user.email, &code.plain, "a brand new passphrase")
        .await
        .expect("recovery and replacement session commit together");

    assert_eq!(recovered.id, user.id);
    assert_ne!(next.plain, code.plain);
    assert_eq!(
        accounts.user_for_session(&old.plain).await.unwrap_err(),
        AccountError::SessionEnded,
        "recovery revokes the old session"
    );
    assert_eq!(
        accounts
            .user_for_session(&replacement.plain)
            .await
            .expect("replacement session is live")
            .id,
        user.id
    );
}

#[tokio::test]
async fn concurrent_password_changes_cannot_both_commit_from_one_old_password() {
    with_store!(accounts);
    let user = a_user(&accounts).await;

    let left = accounts.clone();
    let right = accounts.clone();
    let user_left = user.id.clone();
    let user_right = user.id.clone();
    let (a, b) = tokio::join!(
        left.change_password(
            &user_left,
            "correct horse battery",
            "first concurrent replacement",
            None,
        ),
        right.change_password(
            &user_right,
            "correct horse battery",
            "second concurrent replacement",
            None,
        )
    );

    assert_eq!(usize::from(a.is_ok()) + usize::from(b.is_ok()), 1);
    let loser = match a {
        Err(error) => error,
        Ok(_) => b.expect_err("the other concurrent password change must lose"),
    };
    assert_eq!(loser, AccountError::InvalidCredentials);
}

#[tokio::test]
async fn one_recovery_code_cannot_win_two_concurrent_rotations() {
    with_store!(accounts);
    let (user, code) = a_user_with_code(&accounts).await;

    let left = accounts.clone();
    let right = accounts.clone();
    let email_left = user.email.clone();
    let email_right = user.email.clone();
    let code_left = code.plain.clone();
    let code_right = code.plain.clone();
    let (a, b) = tokio::join!(
        left.recover(&email_left, &code_left, "first concurrent recovery"),
        right.recover(&email_right, &code_right, "second concurrent recovery")
    );

    assert_eq!(usize::from(a.is_ok()) + usize::from(b.is_ok()), 1);
    let loser = match a {
        Err(error) => error,
        Ok(_) => b.expect_err("the other concurrent recovery must lose"),
    };
    assert_eq!(loser, AccountError::InvalidCredentials);
}

#[tokio::test]
async fn changing_email_requires_the_password_and_ends_other_sessions() {
    with_store!(accounts);
    let (user, _) = accounts
        .register("old@example.org", "Email Owner", "a-long-enough-password")
        .await
        .expect("registration succeeds");
    let here = accounts
        .start_session(&user.id)
        .await
        .expect("current session");
    let elsewhere = accounts
        .start_session(&user.id)
        .await
        .expect("other session");

    let changed = accounts
        .change_email(
            &user.id,
            "a-long-enough-password",
            " New@Example.org ",
            Some(&here.plain),
        )
        .await
        .expect("email changes");
    assert_eq!(changed.email, "New@Example.org");
    assert!(accounts.user_for_session(&here.plain).await.is_ok());
    assert_eq!(
        accounts
            .user_for_session(&elsewhere.plain)
            .await
            .unwrap_err(),
        AccountError::SessionEnded
    );
    assert!(accounts
        .authenticate("new@example.org", "a-long-enough-password")
        .await
        .is_ok());
    assert!(accounts
        .authenticate("old@example.org", "a-long-enough-password")
        .await
        .is_err());
}
