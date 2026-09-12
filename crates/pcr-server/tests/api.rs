//! Drives the router directly rather than over a socket, so the tests assert
//! on routing and status mapping without needing a free port.

use axum::body::{Body, Bytes};
use axum::http::{Request, StatusCode};
use axum::routing::post;
use http_body_util::BodyExt;
use pcr_server::module_routes;
use pcr_server::rate_limit::DESIGNS_PER_WINDOW;
use serde_json::{json, Value};
use tower::ServiceExt;

async fn call(method: &str, uri: &str, body: Option<Value>) -> (StatusCode, Value) {
    // Only the module half of the API, so these need no database.
    let router = axum::Router::new().nest("/api", module_routes().expect("the registry builds"));
    let request = Request::builder().method(method).uri(uri);
    let request = match body {
        Some(payload) => request
            .header("content-type", "application/json")
            .body(Body::from(payload.to_string()))
            .expect("request builds"),
        None => request.body(Body::empty()).expect("request builds"),
    };

    let response = router.oneshot(request).await.expect("the router answers");
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

#[tokio::test]
async fn info_reports_the_running_build() {
    let (status, body) = call("GET", "/api/info", None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["name"], "PCRStudio");
    assert!(body["version"].is_string());
}

#[tokio::test]
async fn modules_come_back_sorted_so_the_sidebar_is_stable() {
    let (status, body) = call("GET", "/api/modules", None).await;
    assert_eq!(status, StatusCode::OK);

    let ids: Vec<&str> = body
        .as_array()
        .expect("an array of manifests")
        .iter()
        .map(|module| module["id"].as_str().expect("every module has an id"))
        .collect();
    assert!(!ids.is_empty(), "the catalogue should not be empty");

    let mut sorted = ids.clone();
    sorted.sort_unstable();
    assert_eq!(ids, sorted);
}

#[tokio::test]
async fn one_module_carries_the_fields_the_interface_parses() {
    let (status, body) = call("GET", "/api/modules/standard-pcr", None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["id"], "standard-pcr");
    assert_eq!(body["goal"], "amplify");
    assert_eq!(body["engine"], "flanking-pair");
    // One of the three, rather than whichever one it happens to be today. This
    // test is about the manifest carrying what the interface parses; pinning
    // the value here would make every honest status change look like a
    // regression in the wrong file.
    assert!(
        ["planned", "experimental", "stable"].contains(&body["status"].as_str().expect("a status")),
        "unrecognised status: {}",
        body["status"]
    );
    assert!(body["summary"].as_str().is_some_and(|s| !s.is_empty()));
    assert!(body["guidance"].as_str().is_some_and(|g| g.len() > 80));
    assert!(body["modifiers"].is_array(), "modifiers is always present");
}

#[tokio::test]
async fn colony_pcr_manifest_carries_its_screening_default_purpose() {
    let (status, body) = call("GET", "/api/modules/colony-pcr", None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["defaults"]["defaultPurpose"], "screen");
}

#[tokio::test]
async fn an_unknown_module_is_a_404_carrying_the_id_that_was_asked_for() {
    let (status, body) = call("GET", "/api/modules/does-not-exist", None).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["kind"], "unknownProfile");
    assert!(body["detail"]
        .as_str()
        .is_some_and(|detail| detail.contains("does-not-exist")));
}

#[tokio::test]
async fn no_module_answers_not_implemented_any_more() {
    // This test used to check that LAMP came back 501, because the loop-set
    // engine was named and not written. Every one of the eleven engines now
    // computes, so what is worth pinning is the other half of the same
    // contract: nothing in the catalogue is a placeholder.
    //
    // The 501 path itself is still tested, in pcr-core, against the placeholder
    // type rather than against whichever engine happens to be unwritten.
    let (_, modules) = call("GET", "/api/modules", None).await;

    for module in modules.as_array().expect("an array") {
        let id = module["id"].as_str().expect("an id");
        let (status, body) = call(
            "POST",
            &format!("/api/modules/{id}/design"),
            Some(json!({})),
        )
        .await;
        assert_ne!(
            status,
            StatusCode::NOT_IMPLEMENTED,
            "{id} has no engine behind it: {body}"
        );
    }
}

#[tokio::test]
async fn a_written_engine_refuses_a_bad_request_rather_than_a_missing_one() {
    // Standard PCR reaches the flanking-pair engine, so an empty body is a 400
    // about the request instead of a 501 about the engine. That difference is
    // how a caller can tell an assay that can run from one that cannot.
    let (status, body) = call("POST", "/api/modules/standard-pcr/design", Some(json!({}))).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["kind"], "invalidRequest");
}

#[tokio::test]
async fn every_assay_that_claims_to_run_is_reachable_over_http() {
    // The check that catches an engine written, tested, and never registered.
    //
    // That has happened here: two engines once passed their own suites while
    // every request for them came back 501, because an edit to the registry
    // silently did not apply. A unit test on the engine cannot see it — only a
    // request through the same door a caller uses can.
    //
    // An empty body is deliberate. What is asserted is which *kind* of refusal
    // comes back: 400 means the request reached an engine and was found
    // wanting, 501 means there was no engine to reach.
    for assay in [
        "qpcr-probe",
        "sequencing-primer",
        "race",
        "site-directed-mutagenesis",
        "tiled-scheme",
        "gibson-assembly",
        "arms-pcr",
        "tetra-primer-arms",
        "kasp",
        "lamp",
    ] {
        let (status, body) = call(
            "POST",
            &format!("/api/modules/{assay}/design"),
            Some(json!({})),
        )
        .await;
        assert_eq!(
            status,
            StatusCode::BAD_REQUEST,
            "{assay} says it runs but answered {status}: {body}"
        );
        assert_eq!(body["kind"], "invalidRequest", "{assay}");
    }
}

#[tokio::test]
async fn no_assay_that_says_it_runs_answers_not_implemented() {
    // The same claim as above, made of the whole catalogue rather than of a
    // list somebody has to remember to extend. A status is the one field
    // people use to decide whether to trust an answer before reading it.
    let (_, modules) = call("GET", "/api/modules", None).await;

    for module in modules.as_array().expect("an array") {
        if module["status"] == "planned" {
            continue;
        }
        let id = module["id"].as_str().expect("an id");
        let (status, _) = call(
            "POST",
            &format!("/api/modules/{id}/design"),
            Some(json!({})),
        )
        .await;
        assert_ne!(
            status,
            StatusCode::NOT_IMPLEMENTED,
            "{id} is published as {} and has no engine behind it",
            module["status"]
        );
    }
}

#[tokio::test]
async fn a_design_request_carrying_a_typo_names_the_field() {
    // A misspelt parameter that is silently ignored produces a run whose
    // settings are not the settings that were asked for.
    let (status, body) = call(
        "POST",
        "/api/modules/standard-pcr/design",
        Some(json!({ "template": "ACGTACGTACGTACGTACGT", "polymerse": "taq-standard" })),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert!(body["detail"]
        .as_str()
        .is_some_and(|detail| detail.contains("polymerse")));
}

#[tokio::test]
async fn designing_with_an_unknown_module_fails_before_the_request_is_read() {
    let (status, body) = call("POST", "/api/modules/nope/design", Some(json!({}))).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["kind"], "unknownProfile");
}

#[tokio::test]
async fn every_goal_is_published_with_a_label_and_a_count() {
    let (status, body) = call("GET", "/api/goals", None).await;
    assert_eq!(status, StatusCode::OK);

    let goals = body.as_array().expect("an array of goals");
    assert_eq!(goals.len(), 7, "the goal vocabulary is closed");

    let total: u64 = goals
        .iter()
        .map(|goal| {
            assert!(goal["label"].as_str().is_some_and(|l| !l.is_empty()));
            // The rule is what tells somebody why an assay is in this group
            // and not the next one. A goal without one is a bare heading.
            assert!(goal["rule"].as_str().is_some_and(|r| r.len() > 30));
            let count = goal["count"].as_u64().expect("a count");
            assert!(count > 0, "{} has no assays under it", goal["id"]);
            count
        })
        .sum();

    // Every assay sits under exactly one goal, so the counts partition the
    // catalogue rather than merely covering it.
    let (_, modules) = call("GET", "/api/modules", None).await;
    assert_eq!(total as usize, modules.as_array().expect("an array").len());
}

#[tokio::test]
async fn the_compatibility_matrix_is_published_rather_than_buried() {
    let (status, body) = call("GET", "/api/engines", None).await;
    assert_eq!(status, StatusCode::OK);

    let engines = body.as_array().expect("an array of engines");
    assert_eq!(engines.len(), 11, "the engine vocabulary is closed");

    let tiling = engines
        .iter()
        .find(|engine| engine["id"] == "tiling-scheme")
        .expect("the tiling engine is published");
    let accepts: Vec<&str> = tiling["accepts"]
        .as_array()
        .expect("an array")
        .iter()
        .map(|m| m.as_str().expect("a modifier"))
        .collect();
    // A tiling scheme assigns its own pools; the refusal is the point of
    // publishing the matrix at all.
    assert!(!accepts.contains(&"multiplex"));
    assert!(tiling["input"].as_str().is_some_and(|i| !i.is_empty()));

    // Which engines compute is published too, so the interface can decide
    // whether to offer a form or an explanation without guessing.
    //
    // Asserted as a property of every engine rather than by naming one that
    // happens to be unwritten today: this test used to pin `tiling-scheme` to
    // false, and went red the day it was built — which is a test failing on
    // work being finished rather than on anything breaking.
    for engine in engines {
        assert!(
            engine["implemented"].is_boolean(),
            "{} does not say whether it computes",
            engine["id"]
        );
    }
    let flanking = engines
        .iter()
        .find(|engine| engine["id"] == "flanking-pair")
        .expect("the flanking-pair engine is published");
    assert_eq!(flanking["implemented"], true);
}

#[tokio::test]
async fn every_assay_names_an_engine_the_engines_endpoint_lists() {
    let (_, engines) = call("GET", "/api/engines", None).await;
    let known: Vec<&str> = engines
        .as_array()
        .expect("an array")
        .iter()
        .map(|engine| engine["id"].as_str().expect("an id"))
        .collect();

    let (_, modules) = call("GET", "/api/modules", None).await;
    for module in modules.as_array().expect("an array") {
        let engine = module["engine"].as_str().expect("every assay names one");
        assert!(
            known.contains(&engine),
            "{engine} is not a published engine"
        );
    }
}

#[tokio::test]
async fn the_modifier_vocabulary_is_published_with_its_wording() {
    let (status, body) = call("GET", "/api/modifiers", None).await;
    assert_eq!(status, StatusCode::OK);

    let modifiers = body.as_array().expect("an array of modifiers");
    assert_eq!(modifiers.len(), 5, "the modifier vocabulary is closed");
    for modifier in modifiers {
        assert!(modifier["id"].as_str().is_some_and(|id| !id.is_empty()));
        assert!(modifier["label"].as_str().is_some_and(|l| !l.is_empty()));
    }

    // Nothing an assay declares may fall outside this list.
    let known: Vec<&str> = modifiers
        .iter()
        .map(|m| m["id"].as_str().expect("an id"))
        .collect();
    let (_, modules) = call("GET", "/api/modules", None).await;
    for module in modules.as_array().expect("an array") {
        for modifier in module["modifiers"].as_array().expect("an array") {
            let id = modifier.as_str().expect("a modifier id");
            assert!(known.contains(&id), "{id} is not a published modifier");
        }
    }
}

#[tokio::test]
async fn a_caller_cannot_claim_to_be_a_different_assay() {
    // The assay is set from the address the request was sent to. A body that
    // also carries one is working from a misunderstanding, and overwriting it
    // quietly would hide that rather than settle it.
    let (status, body) = call(
        "POST",
        "/api/modules/standard-pcr/design",
        Some(json!({
            "template": "ACGTACGTACGTACGTACGT",
            "assay": { "id": "colony-pcr" },
        })),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert!(body["detail"]
        .as_str()
        .is_some_and(|detail| detail.contains("address")));
}

#[tokio::test]
async fn an_assay_that_cannot_share_a_tube_is_refused_by_name() {
    // Nested PCR multiplexed is four pairs whose second round would amplify
    // across each other's first products. The catalogue already says which
    // assays can be combined, so the answer comes from there rather than from
    // a list kept beside it.
    let (status, body) = call(
        "POST",
        "/api/modules/nested-pcr/multiplex",
        Some(json!({ "readout": "agarose", "targets": [] })),
    )
    .await;

    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert!(body["detail"]
        .as_str()
        .is_some_and(|detail| detail.contains("nested-pcr")));
}

#[tokio::test]
async fn multiplexing_checks_each_target_for_the_assay_requirements() {
    let (status, body) = call(
        "POST",
        "/api/modules/species-specific-pcr/multiplex",
        Some(json!({
            "readout": "agarose",
            "targets": [
                { "name": "without-background", "template": "ACGT" },
                {
                    "name": "with-background",
                    "template": "TGCA",
                    "background": ">excluded\nACGT"
                }
            ]
        })),
    )
    .await;

    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert!(body["detail"]
        .as_str()
        .is_some_and(|detail| detail.contains("needs a background")));
}

#[tokio::test]
async fn multiplexing_an_unknown_module_is_a_missing_module_not_a_bad_request() {
    let (status, body) = call(
        "POST",
        "/api/modules/nope/multiplex",
        Some(json!({ "readout": "agarose", "targets": [] })),
    )
    .await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["kind"], "unknownProfile");
}

#[tokio::test]
async fn ranking_enzymes_needs_something_to_rank_them_against() {
    // An enzyme table in the abstract is a catalogue, not an answer: which one
    // to use depends entirely on the sequence in hand.
    let (status, body) = call(
        "POST",
        "/api/enzymes",
        Some(json!({ "template": "", "purpose": "inverse-flank" })),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert!(body["detail"]
        .as_str()
        .is_some_and(|detail| detail.contains("restriction sites")));
}

/* ── The layers in front of every route ──────────────────────────────────── */

/// One router, reused across the calls in a test.
///
/// The helper at the top of this file builds a fresh router per call, which is
/// right for routing assertions and wrong for anything with state: a rate
/// limiter rebuilt on every request has no memory, and a test using it would
/// pass whether the limiter worked or not.
fn shared() -> axum::Router {
    pcr_server::harden(
        axum::Router::new().nest("/api", module_routes().expect("the registry builds")),
    )
}

async fn call_on(
    router: &axum::Router,
    method: &str,
    uri: &str,
    body: Option<Value>,
) -> StatusCode {
    let request = Request::builder().method(method).uri(uri);
    let request = match body {
        Some(payload) => request
            .header("content-type", "application/json")
            .body(Body::from(payload.to_string()))
            .expect("request builds"),
        None => request.body(Body::empty()).expect("request builds"),
    };
    router
        .clone()
        .oneshot(request)
        .await
        .expect("the router answers")
        .status()
}

#[tokio::test]
async fn designing_too_often_is_refused_and_says_why() {
    // The endpoint that forks a Python worker takes no account, deliberately —
    // somebody should be able to try the tool before signing up. That makes a
    // ceiling the only thing between one script and every core on the machine,
    // and it is the cheapest way to take this service down.
    //
    // An invalid body is used on purpose: what is under test is the meter in
    // front of the handler rather than the handler, and a valid one would run a
    // real search thirty times over.
    let router = shared();
    let mut refused_at = None;

    for attempt in 0..(DESIGNS_PER_WINDOW + 5) {
        let status = call_on(
            &router,
            "POST",
            "/api/modules/standard-pcr/design",
            Some(json!({ "template": "" })),
        )
        .await;

        if status == StatusCode::TOO_MANY_REQUESTS {
            refused_at = Some(attempt);
            break;
        }
        assert_eq!(status, StatusCode::BAD_REQUEST, "attempt {attempt}");
    }

    let attempt = refused_at.expect("the meter never refused anything");
    assert!(
        attempt >= DESIGNS_PER_WINDOW,
        "refused after {attempt}, before the limit of {DESIGNS_PER_WINDOW}"
    );
}

#[tokio::test]
async fn the_refusal_says_what_the_limit_is_and_why_there_is_one() {
    let router = shared();
    for _ in 0..DESIGNS_PER_WINDOW {
        let _ = call_on(
            &router,
            "POST",
            "/api/modules/standard-pcr/design",
            Some(json!({ "template": "" })),
        )
        .await;
    }

    let response = router
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/modules/standard-pcr/design")
                .header("content-type", "application/json")
                .body(Body::from(json!({ "template": "" }).to_string()))
                .expect("a request"),
        )
        .await
        .expect("a response");

    assert_eq!(response.status(), StatusCode::TOO_MANY_REQUESTS);
    let bytes = response
        .into_body()
        .collect()
        .await
        .expect("a body")
        .to_bytes();
    let body: Value = serde_json::from_slice(&bytes).expect("json");

    assert_eq!(body["kind"], "tooManyRequests");
    let detail = body["detail"].as_str().expect("a detail");
    assert!(detail.contains(&DESIGNS_PER_WINDOW.to_string()), "{detail}");
    // Says why the limit exists, not only that it was hit.
    assert!(detail.contains("real search"), "{detail}");
}

#[tokio::test]
async fn reading_the_catalogue_is_not_metered() {
    // Answered from memory, the same for everybody, and asked for on every page
    // load. Metering it alongside the searches would throttle the sidebar.
    let router = shared();
    for attempt in 0..(DESIGNS_PER_WINDOW + 20) {
        let status = call_on(&router, "GET", "/api/modules", None).await;
        assert_eq!(status, StatusCode::OK, "attempt {attempt}");
    }
}

#[tokio::test]
async fn every_response_carries_the_headers_that_stop_it_being_read_as_a_document() {
    // Much of what these endpoints return is sequence somebody else pasted in.
    // A browser that decides a body labelled JSON is really HTML turns that
    // into a script that runs.
    let response = shared()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/api/modules")
                .body(Body::empty())
                .expect("a request"),
        )
        .await
        .expect("a response");

    let headers = response.headers();
    assert_eq!(headers["x-content-type-options"], "nosniff");
    assert_eq!(headers["referrer-policy"], "no-referrer");
    assert_eq!(headers["cross-origin-resource-policy"], "same-origin");
    // And an id, so a report of "it failed at 14:03" can be matched to a log
    // line rather than guessed at.
    assert!(headers.contains_key("x-request-id"), "no request id");
}

#[tokio::test]
async fn a_caller_supplied_request_id_is_kept_rather_than_replaced() {
    // A proxy or a client that already has a correlation id keeps it, so one
    // id spans the whole hop rather than changing at this boundary.
    let response = shared()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/api/modules")
                .header("x-request-id", "from-the-caller")
                .body(Body::empty())
                .expect("a request"),
        )
        .await
        .expect("a response");

    assert_eq!(response.headers()["x-request-id"], "from-the-caller");
}

#[tokio::test]
async fn a_body_larger_than_the_limit_is_refused_before_a_handler_sees_it() {
    // Do not accidentally rely on the design engine's own sequence validation
    // or on a Content-Length header. A streamed import may not carry that
    // header, so consume bytes in a trivial route behind the exact global
    // hardening layers used by the production router.
    let router = pcr_server::harden(axum::Router::new().route(
        "/consume",
        post(|_body: Bytes| async { StatusCode::NO_CONTENT }),
    ));
    let response = router
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/consume")
                .body(Body::from(vec![
                    b'x';
                    pcr_contracts::MAX_HTTP_BODY_BYTES + 1
                ]))
                .expect("request builds"),
        )
        .await
        .expect("the router answers");

    assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
}

#[tokio::test]
async fn the_catalogue_says_it_may_be_cached() {
    // Compiled into the binary, identical for every caller, and asked for on
    // every page load. Answering it afresh each time is work nobody needed.
    let response = shared()
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/api/modules")
                .body(Body::empty())
                .expect("a request"),
        )
        .await
        .expect("a response");

    let cache = response.headers()["cache-control"]
        .to_str()
        .expect("a header");
    assert!(cache.contains("public"), "{cache}");
    assert!(cache.contains("max-age="), "{cache}");
}

#[tokio::test]
async fn a_design_is_not_cached_even_though_it_sits_beside_the_catalogue() {
    // Two routes under the same prefix with opposite needs. A design is about
    // one person's sequence and must not be handed to the next caller who asks
    // the same question — and the header is set per group rather than per
    // route, which is exactly the arrangement that gets this wrong.
    let response = shared()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/modules/standard-pcr/design")
                .header("content-type", "application/json")
                .body(Body::from(json!({ "template": "" }).to_string()))
                .expect("a request"),
        )
        .await
        .expect("a response");

    let cache = response
        .headers()
        .get("cache-control")
        .map(|value| value.to_str().unwrap_or_default().to_owned())
        .unwrap_or_default();

    assert!(
        !cache.contains("public"),
        "a design answered with a public cache header: {cache}"
    );
}

/* ── One design path ─────────────────────────────────────────────────────── */

/// The preparation that must happen before any engine runs, on every path.
///
/// There were two paths. The public endpoint injected the assay profile and
/// validated; the save-into-a-project handler called the engine directly and did
/// neither. Nothing in either file showed the difference, and the consequence
/// only appeared in the results: measured on qPCR-probe against TP53, the
/// public path gave the qPCR buffer and a 154 bp product while the saved path
/// gave Taq, no assay id, and 359 bp — outside the window that assay exists
/// for, on the only kind of run anybody keeps.
///
/// These tests hold the *contract of the shared function* rather than compare
/// two handlers, because comparing handlers is what stopped being true.
#[test]
fn a_prepared_request_carries_the_assay_it_was_addressed_to() {
    let registry = pcr_core::default_registry().expect("the registry builds");

    // The engine is not reached: an empty template is refused first. What is
    // under test is what the request looked like by the time it got there.
    let error = pcr_server::routes::design_for(&registry, "qpcr-probe", json!({ "template": "" }))
        .expect_err("an empty template is not designable");

    // It reached an engine at all, rather than falling over on a missing assay.
    assert!(
        matches!(error, pcr_core::CoreError::InvalidRequest(_)),
        "{error:?}"
    );
}

#[test]
fn a_caller_cannot_supply_its_own_assay_on_any_path() {
    // Set from the address, never from the body. A caller who sends one is
    // working from a misunderstanding, and quietly replacing it would hide it.
    let registry = pcr_core::default_registry().expect("the registry builds");
    let error = pcr_server::routes::design_for(
        &registry,
        "standard-pcr",
        json!({ "template": "ACGTACGTACGTACGT", "assay": { "id": "something-else" } }),
    )
    .expect_err("an assay in the body");

    assert!(error.to_string().contains("address"), "{error}");
}

#[test]
fn an_unknown_assay_is_refused_before_anything_runs() {
    let registry = pcr_core::default_registry().expect("the registry builds");
    let error = pcr_server::routes::design_for(&registry, "not-an-assay", json!({}))
        .expect_err("no such assay");
    assert!(error.to_string().contains("not-an-assay"), "{error}");
}

#[test]
fn the_saving_handler_and_the_public_endpoint_call_the_same_function() {
    // The drift test, made structural because the behavioural version needs a
    // database and a Python worker to run.
    //
    // Two handlers doing the same three steps is two handlers that will
    // eventually do two different things, and this pair already did. What is
    // asserted is that neither reaches an engine on its own any more.
    let projects = include_str!("../src/projects.rs");
    let application = include_str!("../../pcr-application/src/design.rs");

    assert!(
        projects.contains("routes::design_for"),
        "projects.rs no longer goes through the shared preparation"
    );
    assert!(
        !projects.contains("engine.design("),
        "projects.rs calls an engine directly again, which is how the assay got dropped"
    );
    // The application layer owns the single engine invocation; the server
    // route is only a transport adapter.
    assert_eq!(
        application.matches("engine.design(").count(),
        1,
        "the application layer must own exactly one engine call"
    );
}

/* ── What an assay cannot be run without ───────────────────────────────── */

#[test]
fn an_assay_defined_by_a_background_will_not_run_without_one() {
    /*
     * Species-specific PCR is defined by what it must *not* amplify. Before
     * this it would happily design without any background and report that the
     * specificity check had not run -- honest, and still the wrong outcome:
     * the primers that come back are specific to nothing in particular, under
     * a name that says otherwise.
     */
    let registry = pcr_core::default_registry().expect("the registry builds");

    let error = pcr_server::routes::design_for(
        &registry,
        "species-specific-pcr",
        json!({ "template": "ACGTACGTACGTACGTACGTACGTACGTACGT" }),
    )
    .expect_err("this assay is not itself without a background");

    let said = error.to_string();
    assert!(said.contains("Species-specific PCR"), "{said}");
    assert!(
        said.contains("must not amplify"),
        "the message should say why this assay in particular needs one: {said}"
    );
}

#[test]
fn an_empty_background_does_not_count_as_one() {
    // A field present and empty is the shape a form sends when nobody filled
    // it in, and it must not satisfy a requirement.
    let registry = pcr_core::default_registry().expect("the registry builds");

    for empty in [json!(""), json!(null)] {
        let error = pcr_server::routes::design_for(
            &registry,
            "species-specific-pcr",
            json!({ "template": "ACGTACGTACGTACGTACGTACGTACGTACGT", "background": empty }),
        )
        .expect_err("an empty background is not a background");

        assert!(
            error.to_string().contains("Species-specific PCR"),
            "{error}"
        );
    }
}

#[test]
fn assays_that_do_not_require_a_background_still_run_without_one() {
    /*
     * The requirement belongs to one assay, not to the engine it shares with
     * seven others. Standard PCR checked against its template alone is the
     * ordinary case and must stay that way.
     */
    let registry = pcr_core::default_registry().expect("the registry builds");

    let error =
        pcr_server::routes::design_for(&registry, "standard-pcr", json!({ "template": "" }))
            .expect_err("an empty template is still refused");

    assert!(
        !error.to_string().contains("must not amplify"),
        "standard PCR should not be asked for a background: {error}"
    );
}

#[test]
fn a_shared_engine_cannot_receive_a_modifier_its_assay_did_not_declare() {
    let registry = pcr_core::default_registry().expect("the registry builds");

    let error = pcr_server::routes::design_for(
        &registry,
        "rpa",
        json!({
            "template": "ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT",
            "tails": { "forward_enzyme": "HindIII", "reverse_enzyme": "PstI" }
        }),
    )
    .expect_err("RPA does not declare restriction tails");

    assert!(error.to_string().contains("restriction tails"), "{error}");
}

#[test]
fn a_flanking_assay_requires_rpa_protocol_before_execution() {
    let registry = pcr_core::default_registry().expect("the registry builds");
    let error = pcr_server::routes::design_for(
        &registry,
        "rpa",
        json!({
            "template": "ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT",
            "polymerase": "bst"
        }),
    )
    .expect_err("RPA must carry its named protocol before execution");

    let said = error.to_string();
    assert!(said.contains("rpa_protocol"), "{said}");
}

#[test]
fn camel_case_reverse_transcription_is_checked_at_the_assay_boundary() {
    let registry = pcr_core::default_registry().expect("the registry builds");

    let error = pcr_server::routes::design_for(
        &registry,
        "restriction-cloning",
        json!({
            "template": "ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT",
            "fromRna": true
        }),
    )
    .expect_err("restriction cloning does not declare reverse transcription");

    assert!(
        error.to_string().contains("reverse transcription"),
        "{error}"
    );
}

#[test]
fn a_false_boolean_modifier_is_not_treated_as_requested() {
    let registry = pcr_core::default_registry().expect("the registry builds");

    let error = pcr_server::routes::design_for(
        &registry,
        "restriction-cloning",
        json!({
            "template": "ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT",
            "fromRna": false
        }),
    )
    .expect_err("the small fixture cannot meet the cloning product range");

    assert!(
        !error.to_string().contains("reverse transcription"),
        "false must not trigger the modifier guard: {error}"
    );
}

#[test]
fn a_vector_primer_is_restricted_to_colony_pcr_even_though_the_engine_accepts_it() {
    let registry = pcr_core::default_registry().expect("the registry builds");

    let error = pcr_server::routes::design_for(
        &registry,
        "standard-pcr",
        json!({
            "template": "ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT",
            "vectorPrimer": { "sequence": "GTAAAACGACGGCCAGT" }
        }),
    )
    .expect_err("vector primers are a Colony PCR control");

    assert!(error.to_string().contains("vector primer"), "{error}");
}

#[test]
fn every_declared_requirement_names_a_field_and_a_reason() {
    /*
     * A requirement whose message is empty would refuse a request and say
     * nothing useful about it, which is worse than not having the requirement.
     * Checked across the registry rather than for the one assay that has one
     * today, so the second one to declare one inherits the check.
     */
    let registry = pcr_core::default_registry().expect("the registry builds");

    for profile in registry.profiles() {
        for requirement in &profile.requires {
            assert!(
                !requirement.field().is_empty(),
                "{} has a nameless requirement",
                profile.id
            );
            assert!(
                requirement.why().len() > 40,
                "{} declares a requirement with no explanation worth reading",
                profile.id
            );
        }
    }
}
