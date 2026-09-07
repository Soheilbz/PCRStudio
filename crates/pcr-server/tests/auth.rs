//! The account endpoints over HTTP.
//!
//! These need PostgreSQL. Start one with `docker compose up -d db` and set
//! `PCR_TEST_DATABASE_URL`; without it each test says it was skipped rather
//! than passing quietly. Every test gets its own schema.

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use http_body_util::BodyExt;
use pcr_accounts::Accounts;
use serde_json::{json, Value};
use tower::ServiceExt;

async fn router() -> Option<Router> {
    let Ok(base) = std::env::var("PCR_TEST_DATABASE_URL") else {
        if std::env::var("CI").is_ok_and(|value| value.eq_ignore_ascii_case("true")) {
            panic!("PCR_TEST_DATABASE_URL is required in CI; refusing a green database-test skip");
        }
        eprintln!(
            "SKIPPED: set PCR_TEST_DATABASE_URL to run the account endpoint tests \
             (docker compose up -d db)"
        );
        return None;
    };

    let schema = format!("t{}", uuid::Uuid::new_v4().simple());
    let admin = sqlx_connect(&base).await;
    sqlx::query(sqlx::AssertSqlSafe(format!(r#"CREATE SCHEMA "{schema}""#)))
        .execute(&admin)
        .await
        .expect("the test schema should be creatable");
    admin.close().await;

    let separator = if base.contains('?') { '&' } else { '?' };
    let url = format!("{base}{separator}options=-c%20search_path%3D{schema}");
    let accounts = Accounts::connect(&url).await.expect("the store opens");

    Some(Router::new().nest("/api/auth", pcr_server::auth::routes(accounts)))
}

async fn sqlx_connect(url: &str) -> sqlx::PgPool {
    sqlx::PgPool::connect(url)
        .await
        .expect("PCR_TEST_DATABASE_URL should point at a reachable database")
}

macro_rules! with_router {
    ($name:ident) => {
        let Some($name) = router().await else { return };
    };
}

async fn send(
    router: &Router,
    method: &str,
    uri: &str,
    token: Option<&str>,
    body: Option<Value>,
) -> (StatusCode, Value) {
    let mut request = Request::builder().method(method).uri(uri);
    if let Some(token) = token {
        request = request.header("authorization", format!("Bearer {token}"));
    }
    let request = match body {
        Some(payload) => request
            .header("content-type", "application/json")
            .body(Body::from(payload.to_string()))
            .expect("request builds"),
        None => request.body(Body::empty()).expect("request builds"),
    };

    let response = router
        .clone()
        .oneshot(request)
        .await
        .expect("the router answers");
    let status = response.status();
    let bytes = response
        .into_body()
        .collect()
        .await
        .expect("body is readable")
        .to_bytes();
    let value = if bytes.is_empty() {
        Value::Null
    } else {
        serde_json::from_slice(&bytes).expect("responses are JSON")
    };
    (status, value)
}

async fn register(router: &Router, email: &str) -> (StatusCode, Value) {
    send(
        router,
        "POST",
        "/api/auth/register",
        None,
        Some(json!({
            "email": email,
            "displayName": "Ada Lovelace",
            "password": "correct horse battery"
        })),
    )
    .await
}

#[tokio::test]
async fn registering_returns_the_user_and_a_session_token() {
    with_router!(router);
    let (status, body) = register(&router, "ada@example.org").await;

    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["user"]["email"], "ada@example.org");
    assert_eq!(body["user"]["displayName"], "Ada Lovelace");
    assert!(body["token"]
        .as_str()
        .is_some_and(|token| token.len() == 64));
    assert!(body["expiresIn"]
        .as_i64()
        .is_some_and(|seconds| seconds > 0));
    // The response must never carry password material.
    assert!(body["user"].get("passwordHash").is_none());
}

#[tokio::test]
async fn a_second_registration_of_one_address_is_a_conflict() {
    with_router!(router);
    register(&router, "ada@example.org").await;
    let (status, body) = register(&router, "ada@example.org").await;

    assert_eq!(status, StatusCode::CONFLICT);
    assert_eq!(body["kind"], "emailTaken");
}

#[tokio::test]
async fn a_password_that_fails_the_policy_is_unprocessable_and_says_why() {
    with_router!(router);
    let (status, body) = send(
        &router,
        "POST",
        "/api/auth/register",
        None,
        Some(json!({ "email": "ada@example.org", "displayName": "Ada", "password": "short" })),
    )
    .await;

    assert_eq!(status, StatusCode::UNPROCESSABLE_ENTITY);
    assert_eq!(body["kind"], "weakPassword");
    assert!(body["detail"]
        .as_str()
        .is_some_and(|text| text.contains("10")));
}

#[tokio::test]
async fn signing_in_with_the_wrong_password_is_unauthorised() {
    with_router!(router);
    register(&router, "ada@example.org").await;

    let (status, body) = send(
        &router,
        "POST",
        "/api/auth/login",
        None,
        Some(json!({ "email": "ada@example.org", "password": "not it" })),
    )
    .await;

    assert_eq!(status, StatusCode::UNAUTHORIZED);
    assert_eq!(body["kind"], "invalidCredentials");
}

#[tokio::test]
async fn who_am_i_needs_a_token_and_then_answers_with_the_user() {
    with_router!(router);
    let (_, registered) = register(&router, "ada@example.org").await;
    let token = registered["token"].as_str().expect("a token").to_owned();

    let (anonymous, _) = send(&router, "GET", "/api/auth/me", None, None).await;
    assert_eq!(anonymous, StatusCode::UNAUTHORIZED);

    let (invalid, _) = send(&router, "GET", "/api/auth/me", Some("nonsense"), None).await;
    assert_eq!(invalid, StatusCode::UNAUTHORIZED);

    let (status, body) = send(&router, "GET", "/api/auth/me", Some(&token), None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["email"], "ada@example.org");
}

#[tokio::test]
async fn signing_out_ends_the_token_it_was_called_with() {
    with_router!(router);
    let (_, registered) = register(&router, "ada@example.org").await;
    let token = registered["token"].as_str().expect("a token").to_owned();

    let (status, _) = send(&router, "POST", "/api/auth/logout", Some(&token), None).await;
    assert_eq!(status, StatusCode::NO_CONTENT);

    let (after, _) = send(&router, "GET", "/api/auth/me", Some(&token), None).await;
    assert_eq!(after, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn renaming_takes_effect_and_an_empty_name_is_refused() {
    with_router!(router);
    let (_, registered) = register(&router, "ada@example.org").await;
    let token = registered["token"].as_str().expect("a token").to_owned();

    let (status, body) = send(
        &router,
        "PATCH",
        "/api/auth/profile",
        Some(&token),
        Some(json!({ "displayName": "  Ada L.  " })),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["displayName"], "Ada L.");

    let (refused, _) = send(
        &router,
        "PATCH",
        "/api/auth/profile",
        Some(&token),
        Some(json!({ "displayName": "   " })),
    )
    .await;
    assert_eq!(refused, StatusCode::UNPROCESSABLE_ENTITY);
}

#[tokio::test]
async fn changing_the_sign_in_email_requires_the_password_and_ends_the_rest() {
    with_router!(router);
    let (_, registered) = register(&router, "ada@example.org").await;
    let here = registered["token"].as_str().expect("a token").to_owned();

    let (_, second) = send(
        &router,
        "POST",
        "/api/auth/login",
        None,
        Some(json!({ "email": "ada@example.org", "password": "correct horse battery" })),
    )
    .await;
    let elsewhere = second["token"].as_str().expect("a token").to_owned();

    let (wrong, _) = send(
        &router,
        "PATCH",
        "/api/auth/email",
        Some(&here),
        Some(json!({ "currentPassword": "wrong", "newEmail": "new@example.org" })),
    )
    .await;
    assert_eq!(wrong, StatusCode::UNAUTHORIZED);

    let (status, body) = send(
        &router,
        "PATCH",
        "/api/auth/email",
        Some(&here),
        Some(json!({
            "currentPassword": "correct horse battery",
            "newEmail": "new@example.org"
        })),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["email"], "new@example.org");

    let (still_here, me) = send(&router, "GET", "/api/auth/me", Some(&here), None).await;
    assert_eq!(still_here, StatusCode::OK);
    assert_eq!(me["email"], "new@example.org");

    let (ended, _) = send(&router, "GET", "/api/auth/me", Some(&elsewhere), None).await;
    assert_eq!(ended, StatusCode::UNAUTHORIZED);

    let (old_login, _) = send(
        &router,
        "POST",
        "/api/auth/login",
        None,
        Some(json!({ "email": "ada@example.org", "password": "correct horse battery" })),
    )
    .await;
    assert_eq!(old_login, StatusCode::UNAUTHORIZED);

    let (new_login, _) = send(
        &router,
        "POST",
        "/api/auth/login",
        None,
        Some(json!({ "email": "new@example.org", "password": "correct horse battery" })),
    )
    .await;
    assert_eq!(new_login, StatusCode::OK);
}

#[tokio::test]
async fn changing_a_password_spares_this_session_and_ends_the_rest() {
    with_router!(router);
    let (_, registered) = register(&router, "ada@example.org").await;
    let here = registered["token"].as_str().expect("a token").to_owned();

    let (_, second) = send(
        &router,
        "POST",
        "/api/auth/login",
        None,
        Some(json!({ "email": "ada@example.org", "password": "correct horse battery" })),
    )
    .await;
    let elsewhere = second["token"].as_str().expect("a token").to_owned();

    let (status, _) = send(
        &router,
        "POST",
        "/api/auth/password",
        Some(&here),
        Some(json!({
            "currentPassword": "correct horse battery",
            "newPassword": "a different long one"
        })),
    )
    .await;
    assert_eq!(status, StatusCode::NO_CONTENT);

    let (still_here, _) = send(&router, "GET", "/api/auth/me", Some(&here), None).await;
    assert_eq!(still_here, StatusCode::OK);

    let (ended, _) = send(&router, "GET", "/api/auth/me", Some(&elsewhere), None).await;
    assert_eq!(ended, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn the_wrong_current_password_does_not_change_it() {
    with_router!(router);
    let (_, registered) = register(&router, "ada@example.org").await;
    let token = registered["token"].as_str().expect("a token").to_owned();

    let (status, _) = send(
        &router,
        "POST",
        "/api/auth/password",
        Some(&token),
        Some(json!({ "currentPassword": "wrong", "newPassword": "a different long one" })),
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);

    let (still_works, _) = send(
        &router,
        "POST",
        "/api/auth/login",
        None,
        Some(json!({ "email": "ada@example.org", "password": "correct horse battery" })),
    )
    .await;
    assert_eq!(still_works, StatusCode::OK);
}

#[tokio::test]
async fn signing_out_everywhere_reports_the_count() {
    with_router!(router);
    let (_, registered) = register(&router, "ada@example.org").await;
    let token = registered["token"].as_str().expect("a token").to_owned();

    let (status, body) = send(&router, "DELETE", "/api/auth/sessions", Some(&token), None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["ended"], 1);

    let (after, _) = send(&router, "GET", "/api/auth/me", Some(&token), None).await;
    assert_eq!(after, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn deleting_an_account_needs_the_password_and_then_ends_everything() {
    with_router!(router);
    let (_, registered) = register(&router, "ada@example.org").await;
    let token = registered["token"].as_str().expect("a token").to_owned();

    let (refused, _) = send(
        &router,
        "DELETE",
        "/api/auth/account",
        Some(&token),
        Some(json!({ "password": "wrong" })),
    )
    .await;
    assert_eq!(refused, StatusCode::UNAUTHORIZED);

    let (status, _) = send(
        &router,
        "DELETE",
        "/api/auth/account",
        Some(&token),
        Some(json!({ "password": "correct horse battery" })),
    )
    .await;
    assert_eq!(status, StatusCode::NO_CONTENT);

    let (after, _) = send(&router, "GET", "/api/auth/me", Some(&token), None).await;
    assert_eq!(after, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn repeated_sign_in_attempts_are_eventually_refused() {
    with_router!(router);
    register(&router, "ada@example.org").await;

    let wrong = json!({ "email": "ada@example.org", "password": "not it" });
    let mut refused_at = None;

    for attempt in 0..20 {
        let request = Request::builder()
            .method("POST")
            .uri("/api/auth/login")
            // A forwarded address, so every attempt lands in one bucket the way
            // it would behind the reverse proxy.
            .header("x-forwarded-for", "203.0.113.7")
            .header("content-type", "application/json")
            .body(Body::from(wrong.to_string()))
            .expect("request builds");

        let status = router
            .clone()
            .oneshot(request)
            .await
            .expect("the router answers")
            .status();

        if status == StatusCode::TOO_MANY_REQUESTS {
            refused_at = Some(attempt);
            break;
        }
        assert_eq!(status, StatusCode::UNAUTHORIZED, "attempt {attempt}");
    }

    assert!(
        refused_at.is_some(),
        "the limiter should have refused an attempt within twenty tries"
    );
}

#[tokio::test]
async fn preferences_are_authenticated_allow_listed_and_persisted() {
    with_router!(router);
    let (_, registered) = register(&router, "prefs@example.org").await;
    let token = registered["token"]
        .as_str()
        .expect("registration token")
        .to_owned();

    let (initial, body) = send(&router, "GET", "/api/auth/preferences", Some(&token), None).await;
    assert_eq!(initial, StatusCode::OK);
    assert_eq!(body, json!({}));

    let (saved, body) = send(
        &router,
        "PUT",
        "/api/auth/preferences",
        Some(&token),
        Some(json!({ "preferredPolymerase": "taq-standard" })),
    )
    .await;
    assert_eq!(saved, StatusCode::OK);
    assert_eq!(body["preferredPolymerase"], "taq-standard");

    let (read_back, body) = send(&router, "GET", "/api/auth/preferences", Some(&token), None).await;
    assert_eq!(read_back, StatusCode::OK);
    assert_eq!(body["preferredPolymerase"], "taq-standard");

    let (unknown, body) = send(
        &router,
        "PUT",
        "/api/auth/preferences",
        Some(&token),
        Some(json!({ "typoSetting": "value" })),
    )
    .await;
    assert_eq!(unknown, StatusCode::UNPROCESSABLE_ENTITY);
    assert_eq!(body["kind"], "badRequest");
}

#[tokio::test]
async fn recovery_status_and_recovery_flow_match_the_http_contract() {
    with_router!(router);
    let (_, registered) = register(&router, "recover@example.org").await;
    let token = registered["token"]
        .as_str()
        .expect("registration token")
        .to_owned();
    let recovery = registered["recoveryCode"]
        .as_str()
        .expect("one-time recovery code")
        .to_owned();

    let (status, body) = send(&router, "GET", "/api/auth/recovery", Some(&token), None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["hasCode"], true);
    assert!(body["issuedAt"].as_str().is_some());

    let (status, recovered) = send(
        &router,
        "POST",
        "/api/auth/recover",
        None,
        Some(json!({
            "email": "recover@example.org",
            "recoveryCode": recovery,
            "newPassword": "new correct horse battery"
        })),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert!(recovered["token"]
        .as_str()
        .is_some_and(|value| value.len() == 64));
    assert!(recovered["recoveryCode"].as_str().is_some());

    let (old_password, _) = send(
        &router,
        "POST",
        "/api/auth/login",
        None,
        Some(json!({ "email": "recover@example.org", "password": "correct horse battery" })),
    )
    .await;
    assert_eq!(old_password, StatusCode::UNAUTHORIZED);

    let (new_password, _) = send(
        &router,
        "POST",
        "/api/auth/login",
        None,
        Some(json!({ "email": "recover@example.org", "password": "new correct horse battery" })),
    )
    .await;
    assert_eq!(new_password, StatusCode::OK);
}
