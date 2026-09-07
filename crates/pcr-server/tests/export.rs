//! What a person gets when they ask for their data back.
//!
//! Needs PostgreSQL: start one with `docker compose up -d db` and set
//! `PCR_TEST_DATABASE_URL`. Without it each test says it was skipped rather
//! than passing quietly.

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use http_body_util::BodyExt;
use pcr_accounts::Accounts;
use pcr_core::Registry;
use serde_json::{json, Value};
use tower::ServiceExt;

async fn app() -> Option<Router> {
    let Ok(base) = std::env::var("PCR_TEST_DATABASE_URL") else {
        if std::env::var("CI").is_ok_and(|value| value.eq_ignore_ascii_case("true")) {
            panic!("PCR_TEST_DATABASE_URL is required in CI; refusing a green database-test skip");
        }
        eprintln!("SKIPPED: set PCR_TEST_DATABASE_URL to run the export tests");
        return None;
    };

    let schema = format!("t{}", uuid::Uuid::new_v4().simple());
    let admin = sqlx::PgPool::connect(&base)
        .await
        .expect("PCR_TEST_DATABASE_URL should point at a reachable database");
    sqlx::query(sqlx::AssertSqlSafe(format!(r#"CREATE SCHEMA "{schema}""#)))
        .execute(&admin)
        .await
        .expect("the test schema should be creatable");
    admin.close().await;

    let separator = if base.contains('?') { '&' } else { '?' };
    let url = format!("{base}{separator}options=-c%20search_path%3D{schema}");
    let accounts = Accounts::connect(&url).await.expect("the store opens");
    let registry = Registry::new();

    Some(
        Router::new()
            .nest("/api/auth", pcr_server::auth::routes(accounts.clone()))
            .nest(
                "/api/projects",
                pcr_server::projects::routes(accounts, registry),
            ),
    )
}

macro_rules! with_app {
    ($name:ident) => {
        let Some($name) = app().await else { return };
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
        .expect("router answers");
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

/// An account with one project that has been set up but never run.
async fn account_with_a_draft(router: &Router) -> String {
    let (status, registered) = send(
        router,
        "POST",
        "/api/auth/register",
        None,
        Some(json!({
            "email": format!("ada-{}@example.org", uuid::Uuid::new_v4().simple()),
            "displayName": "Ada Lovelace",
            "password": "correct horse battery"
        })),
    )
    .await;
    assert_eq!(
        status,
        StatusCode::OK,
        "registration should succeed before the project fixture is built: {registered}"
    );
    let token = registered["token"].as_str().expect("a token").to_owned();

    let (status, project) = send(
        router,
        "POST",
        "/api/projects",
        Some(&token),
        Some(json!({ "name": "TP53 exon 7", "moduleId": "standard-pcr" })),
    )
    .await;
    assert_eq!(
        status,
        StatusCode::CREATED,
        "the project should be created: {project}"
    );

    let id = project["id"].as_str().expect("an id");
    let (status, _) = send(
        router,
        "PATCH",
        &format!("/api/projects/{id}"),
        Some(&token),
        Some(json!({
            "notes": "Ordered from the second supplier this time.",
            "settings": { "template": ">TP53\nACGTACGTACGTACGT", "polymerase": "taq-standard" }
        })),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "the draft should save");

    token
}

#[tokio::test]
async fn an_export_carries_the_draft_and_the_notes() {
    /*
     * The failure this exists for: the export listed a project's id, name,
     * module and dates, and stopped. `settings` is where the draft lives â€” the
     * sequence somebody pasted, the constraints they set â€” and `notes` is what
     * they wrote beside it. Neither was included, under a note claiming the
     * document held everything.
     *
     * A project that has been set up but not yet run is the case that exposes
     * it: with no runs to carry the request, the export held nothing of the
     * work at all.
     */
    with_app!(router);
    let token = account_with_a_draft(&router).await;

    let (status, export) = send(&router, "GET", "/api/projects/export", Some(&token), None).await;
    assert_eq!(status, StatusCode::OK);

    let project = &export["projects"][0];
    assert_eq!(project["name"], "TP53 exon 7");
    assert_eq!(
        project["notes"], "Ordered from the second supplier this time.",
        "what somebody wrote beside a project is theirs to take away"
    );
    assert_eq!(
        project["settings"]["template"], ">TP53\nACGTACGTACGTACGT",
        "the pasted sequence is the single most important thing in an export"
    );
    assert_eq!(project["settings"]["polymerase"], "taq-standard");
}

#[tokio::test]
async fn an_export_omits_no_field_the_api_reports() {
    /*
     * Asserted as a set difference rather than field by field, because the
     * defect was not that two particular fields were forgotten â€” it was that
     * the export was written by hand from a struct and had no way to notice
     * when the two drifted apart. A field added to a project next year should
     * fail here rather than be quietly dropped from everybody's data.
     *
     * `runCount` is excluded deliberately: it is derived from the runs the
     * document already carries in full, so exporting it would be duplicating
     * a number, not preserving one.
     */
    with_app!(router);
    let token = account_with_a_draft(&router).await;

    let (_, listed) = send(&router, "GET", "/api/projects", Some(&token), None).await;
    let (_, export) = send(&router, "GET", "/api/projects/export", Some(&token), None).await;

    let reported: Vec<String> = listed[0]
        .as_object()
        .expect("a project object")
        .keys()
        .filter(|key| *key != "runCount")
        .cloned()
        .collect();

    let exported = export["projects"][0]
        .as_object()
        .expect("an exported project");

    // The API answers in camelCase and the export writes snake_case, so the
    // comparison is on the name with the case flattened out of it.
    let flattened: Vec<String> = exported
        .keys()
        .map(|key| key.replace('_', "").to_lowercase())
        .collect();

    for field in &reported {
        let wanted = field.replace('_', "").to_lowercase();
        assert!(
            flattened.contains(&wanted),
            "the export drops `{field}`, which the API reports; \
             it carries {flattened:?}"
        );
    }
}

#[tokio::test]
async fn an_export_can_be_imported_back() {
    /*
     * The property worth having is not "import works" â€” it is that the two
     * halves fit each other. The document here is the one `export_everything`
     * actually wrote, not a hand-built object shaped like what the importer
     * happens to accept, so a field added to one side and forgotten on the
     * other fails here.
     */
    with_app!(router);
    let mine = account_with_a_draft(&router).await;
    let (_, document) = send(&router, "GET", "/api/projects/export", Some(&mine), None).await;

    // Somebody else's account: a fresh instance, a new sign-up, a colleague.
    let theirs = account_with_a_draft(&router).await;
    let (status, summary) = send(
        &router,
        "POST",
        "/api/projects/import",
        Some(&theirs),
        Some(document.clone()),
    )
    .await;

    assert_eq!(status, StatusCode::OK);
    assert_eq!(summary["projects"], 1);
    assert_eq!(summary["alreadyHere"], 0);

    let (_, listed) = send(&router, "GET", "/api/projects", Some(&theirs), None).await;
    let restored = listed
        .as_array()
        .expect("a list")
        .iter()
        .find(|one| one["name"] == "TP53 exon 7")
        .expect("the imported project");

    // The draft is the point. A restore that brings back a name and a date has
    // restored the label on the box.
    assert_eq!(
        restored["notes"],
        "Ordered from the second supplier this time."
    );
    assert_eq!(restored["settings"]["template"], ">TP53\nACGTACGTACGTACGT");
}

#[tokio::test]
async fn importing_the_same_export_twice_changes_nothing() {
    /*
     * This is what makes the button safe to press when unsure â€” which is the
     * state anybody restoring a backup is in. Without it, the natural response
     * to "did that work?" is to click again, and the natural result is two of
     * everything.
     */
    with_app!(router);
    let token = account_with_a_draft(&router).await;
    let (_, document) = send(&router, "GET", "/api/projects/export", Some(&token), None).await;

    let (_, first) = send(
        &router,
        "POST",
        "/api/projects/import",
        Some(&token),
        Some(document.clone()),
    )
    .await;
    let (_, again) = send(
        &router,
        "POST",
        "/api/projects/import",
        Some(&token),
        Some(document),
    )
    .await;

    // The first import is already a no-op here: these projects are this
    // account's own, under the ids they still hold.
    assert_eq!(first["projects"], 0);
    assert_eq!(first["alreadyHere"], 1);
    assert_eq!(again["projects"], 0);
    assert_eq!(again["alreadyHere"], 1);

    let (_, listed) = send(&router, "GET", "/api/projects", Some(&token), None).await;
    assert_eq!(listed.as_array().expect("a list").len(), 1);
}

#[tokio::test]
async fn a_file_that_is_not_an_export_is_refused_with_what_to_do() {
    with_app!(router);
    let token = account_with_a_draft(&router).await;

    for wrong in [
        serde_json::json!({}),
        serde_json::json!({ "format": "something.else.v1", "projects": [] }),
        serde_json::json!({ "projects": [{ "id": "x" }] }),
    ] {
        let (status, body) = send(
            &router,
            "POST",
            "/api/projects/import",
            Some(&token),
            Some(wrong),
        )
        .await;

        assert_eq!(status, StatusCode::BAD_REQUEST);
        // Its own kind, not `invalidName`: the fix is a different file, not a
        // different name, and an interface can only say so if the error does.
        assert_eq!(body["kind"], "notAnExport");
        assert!(
            body["detail"].as_str().is_some_and(
                |text| text.contains("account page") || text.contains("could not be read")
            ),
            "the message should say what to do: {body}"
        );
    }
}

#[tokio::test]
async fn importing_a_backup_brings_back_what_was_deleted() {
    /*
     * The case this was got wrong on the first attempt, and the reason it is
     * worth its own test: a deleted project still holds its id, so an import
     * that only asks "do I already have this id" reports "already here" about
     * something its owner cannot see.
     *
     * That is the worst available answer to the exact person most likely to be
     * importing a backup â€” somebody who deleted it by mistake. Importing a
     * backup of a deleted project plainly means bring it back, so it does.
     */
    with_app!(router);
    let token = account_with_a_draft(&router).await;
    let (_, document) = send(&router, "GET", "/api/projects/export", Some(&token), None).await;

    let id = document["projects"][0]["id"]
        .as_str()
        .expect("an id")
        .to_owned();
    let (status, _) = send(
        &router,
        "DELETE",
        &format!("/api/projects/{id}"),
        Some(&token),
        None,
    )
    .await;
    assert_eq!(status, StatusCode::NO_CONTENT);

    let (_, listed) = send(&router, "GET", "/api/projects", Some(&token), None).await;
    assert!(
        listed.as_array().expect("a list").is_empty(),
        "deleted, so not listed"
    );

    let (status, summary) = send(
        &router,
        "POST",
        "/api/projects/import",
        Some(&token),
        Some(document),
    )
    .await;

    assert_eq!(status, StatusCode::OK);
    assert_eq!(
        summary["restored"], 1,
        "the deleted project should come back"
    );
    assert_eq!(
        summary["alreadyHere"], 0,
        "it was not here â€” that was the bug"
    );
    assert_eq!(summary["projects"], 0, "brought back, not duplicated");

    let (_, listed) = send(&router, "GET", "/api/projects", Some(&token), None).await;
    let back = &listed.as_array().expect("a list")[0];
    assert_eq!(back["id"], id, "the same project, under the same id");
    assert_eq!(back["notes"], "Ordered from the second supplier this time.");
}

/* â”€â”€ Whether this instance should be sent traffic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

/// A router carrying only the probes, so readiness can be tested without the
/// rest of the API â€” which is the point of the endpoint.
async fn probes_with_worker(
    worker: pcr_core::Worker,
) -> Option<(Router, pcr_server::readiness::Readiness)> {
    let Ok(base) = std::env::var("PCR_TEST_DATABASE_URL") else {
        if std::env::var("CI").is_ok_and(|value| value.eq_ignore_ascii_case("true")) {
            panic!("PCR_TEST_DATABASE_URL is required in CI; refusing a green database-test skip");
        }
        eprintln!("SKIPPED: set PCR_TEST_DATABASE_URL to run the readiness tests");
        return None;
    };

    let schema = format!("t{}", uuid::Uuid::new_v4().simple());
    let admin = sqlx::PgPool::connect(&base)
        .await
        .expect("a reachable database");
    sqlx::query(sqlx::AssertSqlSafe(format!(r#"CREATE SCHEMA "{schema}""#)))
        .execute(&admin)
        .await
        .expect("the test schema is creatable");
    admin.close().await;

    let separator = if base.contains('?') { '&' } else { '?' };
    let url = format!("{base}{separator}options=-c%20search_path%3D{schema}");
    let accounts = Accounts::connect(&url).await.expect("the store opens");
    let readiness = pcr_server::readiness::Readiness::with_worker(accounts, worker);

    Some((
        Router::new()
            .route("/ready", axum::routing::get(pcr_server::readiness::ready))
            .with_state(readiness.clone()),
        readiness,
    ))
}

#[tokio::test]
async fn readiness_says_which_dependency_is_missing() {
    /*
     * The failure this endpoint exists for: a container whose worker is absent
     * or misconfigured answers `/health` with `ok` and then fails every design.
     * Compose reads "healthy" as "ready for what depends on this", so the web
     * container would start against exactly that instance.
     *
     * The interpreter is pointed at nothing here, which is the same shape as an
     * image built without the worker stage.
     */
    let Some((router, _)) = probes_with_worker(pcr_application::scientific::worker_with_python(
        "/definitely/not/a/python",
    ))
    .await
    else {
        return;
    };

    let (status, body) = send(&router, "GET", "/ready", None, None).await;

    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert_eq!(body["ready"], false);
    assert_eq!(
        body["database"]["ok"], true,
        "the database is fine; only the worker is not"
    );
    assert_eq!(body["designWorker"]["ok"], false);

    // Public readiness is safe for an orchestrator to expose. The detailed
    // subprocess failure belongs in server logs, not in an unauthenticated
    // response where it could reveal executable paths or host details.
    assert!(body["designWorker"].get("why").is_none());
    assert!(body["database"].get("why").is_none());
}

/* â”€â”€ A link that shows one run to somebody with no account â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

#[tokio::test]
async fn a_share_link_shows_one_run_and_nothing_around_it() {
    /*
     * This is the only route in the application that answers without a session,
     * so what it does *not* return matters as much as what it does. Somebody
     * handed a link to one result has been given one result â€” not the project
     * it sits in, not the runs beside it, and not who made it.
     */
    with_app!(router);
    let token = account_with_a_draft(&router).await;

    let (_, listed) = send(&router, "GET", "/api/projects", Some(&token), None).await;
    let project = listed[0]["id"].as_str().expect("a project").to_owned();

    // A run to share. Saved through the API so the shape is the real one.
    let (status, saved) = send(
        &router,
        "POST",
        &format!("/api/projects/{project}/design"),
        Some(&token),
        Some(json!({
            "label": "first go",
            "request": { "template": ">x\nACGT", "polymerase": "taq-standard" }
        })),
    )
    .await;

    // A design needs the worker. Where it is not installed this test has
    // nothing to share, and says so rather than passing quietly.
    if status != StatusCode::OK {
        if std::env::var("PCR_PYTHON").is_ok_and(|value| !value.trim().is_empty()) {
            panic!("the configured design worker must save a run, got {status}: {saved}");
        }
        eprintln!("SKIPPED: no configured design worker could save a run ({status}): {saved}");
        return;
    }

    let run = saved["run"]["id"].as_str().expect("a run id").to_owned();
    let (status, minted) = send(
        &router,
        "POST",
        &format!("/api/projects/{project}/runs/{run}/share"),
        Some(&token),
        None,
    )
    .await;
    assert_eq!(status, StatusCode::OK);

    let link = minted["token"].as_str().expect("a link token");
    assert_eq!(link.len(), 64, "32 bytes of randomness, hex encoded");

    // Anonymous: no session header at all.
    let (status, shared) = send(&router, "GET", &format!("/api/shared/{link}"), None, None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(shared["id"], run);

    /*
     * `projectId` is in this list for a reason that is not obvious. It is a
     * random UUID and useless by itself â€” every route taking one checks
     * ownership first. What it does is correlate: somebody sent two links from
     * the same project could see that they are siblings, which is a fact about
     * the sender's filing rather than about either result.
     */
    for leaked in ["email", "userId", "user_id", "displayName", "projectId"] {
        assert!(
            !shared.to_string().contains(leaked),
            "a share response must not carry `{leaked}`"
        );
    }
}

#[tokio::test]
async fn a_token_that_matches_nothing_is_a_plain_404() {
    /*
     * The same answer for "never existed" and "withdrawn", so the endpoint
     * cannot be used to tell one from the other â€” which is what would make it a
     * way to test tokens.
     */
    with_app!(router);

    for guess in ["a".repeat(64), "not-a-token".to_owned(), String::new()] {
        let (status, _) = send(&router, "GET", &format!("/api/shared/{guess}"), None, None).await;
        assert_eq!(
            status,
            StatusCode::NOT_FOUND,
            "an unknown token should be a 404, got {status} for `{guess}`"
        );
    }
}

/// A saved run in a fresh account, or `None` where the worker is not installed.
async fn a_saved_run(router: &Router) -> Option<(String, String, String)> {
    let token = account_with_a_draft(router).await;
    let (_, listed) = send(router, "GET", "/api/projects", Some(&token), None).await;
    let project = listed[0]["id"].as_str().expect("a project").to_owned();

    let (status, saved) = send(
        router,
        "POST",
        &format!("/api/projects/{project}/design"),
        Some(&token),
        Some(json!({
            "label": "first go",
            "request": { "template": ">x\nACGT", "polymerase": "taq-standard" }
        })),
    )
    .await;

    if status != StatusCode::OK {
        if std::env::var("PCR_PYTHON").is_ok_and(|value| !value.trim().is_empty()) {
            panic!("the configured design worker must save a run, got {status}: {saved}");
        }
        eprintln!("SKIPPED: no configured design worker could save a run ({status}): {saved}");
        return None;
    }

    let run = saved["run"]["id"].as_str().expect("a run id").to_owned();
    Some((token, project, run))
}

#[tokio::test]
async fn withdrawing_a_link_takes_effect_at_once() {
    with_app!(router);
    let Some((token, project, run)) = a_saved_run(&router).await else {
        return;
    };

    let (_, minted) = send(
        &router,
        "POST",
        &format!("/api/projects/{project}/runs/{run}/share"),
        Some(&token),
        None,
    )
    .await;
    let link = minted["token"].as_str().expect("a link").to_owned();

    let (before, _) = send(&router, "GET", &format!("/api/shared/{link}"), None, None).await;
    assert_eq!(before, StatusCode::OK);

    let (status, _) = send(
        &router,
        "DELETE",
        &format!("/api/projects/{project}/runs/{run}/share"),
        Some(&token),
        None,
    )
    .await;
    assert_eq!(status, StatusCode::NO_CONTENT);

    // Immediately, not eventually. A link somebody withdraws because it reached
    // the wrong person has to stop working before they finish worrying.
    let (after, _) = send(&router, "GET", &format!("/api/shared/{link}"), None, None).await;
    assert_eq!(after, StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn re_sharing_invalidates_the_previous_link() {
    /*
     * There is no separate "rotate" button, because the one somebody reaches
     * for after sending a link to the wrong person is the one they already
     * know. So sharing again has to mean the old link stops working.
     */
    with_app!(router);
    let Some((token, project, run)) = a_saved_run(&router).await else {
        return;
    };

    let mint = || async {
        let (_, minted) = send(
            &router,
            "POST",
            &format!("/api/projects/{project}/runs/{run}/share"),
            Some(&token),
            None,
        )
        .await;
        minted["token"].as_str().expect("a link").to_owned()
    };

    let first = mint().await;
    let second = mint().await;
    assert_ne!(first, second, "each share mints a fresh token");

    let (old, _) = send(&router, "GET", &format!("/api/shared/{first}"), None, None).await;
    let (new, _) = send(&router, "GET", &format!("/api/shared/{second}"), None, None).await;

    assert_eq!(
        old,
        StatusCode::NOT_FOUND,
        "the previous link should be dead"
    );
    assert_eq!(new, StatusCode::OK);
}

#[tokio::test]
async fn deleting_the_project_withdraws_every_link_into_it() {
    /*
     * Claimed in the store's own documentation, so it is checked here rather
     * than trusted. Somebody who deletes a project has withdrawn it from
     * everybody, and would be right to be alarmed to find a link they sent last
     * month still serving it.
     */
    with_app!(router);
    let Some((token, project, run)) = a_saved_run(&router).await else {
        return;
    };

    let (_, minted) = send(
        &router,
        "POST",
        &format!("/api/projects/{project}/runs/{run}/share"),
        Some(&token),
        None,
    )
    .await;
    let link = minted["token"].as_str().expect("a link").to_owned();

    send(
        &router,
        "DELETE",
        &format!("/api/projects/{project}"),
        Some(&token),
        None,
    )
    .await;

    let (status, _) = send(&router, "GET", &format!("/api/shared/{link}"), None, None).await;
    assert_eq!(
        status,
        StatusCode::NOT_FOUND,
        "a deleted project's links must stop serving it"
    );
}

#[tokio::test]
async fn a_run_is_not_somebody_elses_to_share() {
    with_app!(router);
    let Some((_, project, run)) = a_saved_run(&router).await else {
        return;
    };
    let stranger = account_with_a_draft(&router).await;

    let (status, _) = send(
        &router,
        "POST",
        &format!("/api/projects/{project}/runs/{run}/share"),
        Some(&stranger),
        None,
    )
    .await;

    assert_eq!(status, StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn a_nested_run_route_must_match_its_project() {
    with_app!(router);
    let Some((token, project, run)) = a_saved_run(&router).await else {
        return;
    };

    let (status, second) = send(
        &router,
        "POST",
        "/api/projects",
        Some(&token),
        Some(json!({ "name": "second project", "moduleId": "standard-pcr" })),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    let other_project = second["id"].as_str().expect("a second project");

    // The run belongs to this account, but not to the project in the URL.
    for (method, suffix) in [("GET", ""), ("POST", "/share"), ("DELETE", "")] {
        let (status, _) = send(
            &router,
            method,
            &format!("/api/projects/{other_project}/runs/{run}{suffix}"),
            Some(&token),
            None,
        )
        .await;
        assert_eq!(
            status,
            StatusCode::NOT_FOUND,
            "{method} must reject a run nested under the wrong project"
        );
    }

    // The correct path still works, proving the guard is about nesting rather
    // than making the run unavailable altogether.
    let (status, _) = send(
        &router,
        "GET",
        &format!("/api/projects/{project}/runs/{run}"),
        Some(&token),
        None,
    )
    .await;
    assert_eq!(status, StatusCode::OK);
}
