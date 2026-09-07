//! What the project store does against a real database.
//!
//! These need PostgreSQL. Start one with `docker compose up -d db` and set
//! `PCR_TEST_DATABASE_URL`; without it every test here reports that it did
//! nothing rather than passing quietly.
//!
//! Each test gets its own schema, so they run in parallel and none of them
//! sees another's rows. The accounts crate owns the migrations, so this opens
//! the store through it and then hands the pool over â€” which is exactly what
//! the server does.

use chrono::Utc;
use pcr_accounts::Accounts;
use pcr_contracts::{MODULE_CONTRACT_VERSION, REQUEST_SCHEMA_VERSION, RESULT_SCHEMA_VERSION};
use pcr_projects::{
    Incoming, IncomingRun, Project, ProjectError, Projects, MAX_IMPORT_PROJECTS, MAX_LABEL_BYTES,
    MAX_NOTES_BYTES, MAX_PROJECTS_PER_USER, MAX_RUNS_PER_PROJECT, MAX_RUN_DOCUMENT_BYTES,
    MAX_SETTINGS_BYTES,
};
use serde_json::json;
use sqlx::PgPool;

/// An accounts store and a projects store over one schema of their own.
async fn stores() -> Option<(Accounts, Projects)> {
    let Ok(base) = std::env::var("PCR_TEST_DATABASE_URL") else {
        if std::env::var("CI").is_ok_and(|value| value.eq_ignore_ascii_case("true")) {
            panic!("PCR_TEST_DATABASE_URL is required in CI; refusing a green database-test skip");
        }
        eprintln!(
            "SKIPPED: set PCR_TEST_DATABASE_URL to run the project store tests \
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

    let accounts = Accounts::connect(&url)
        .await
        .expect("the store should open and migrate");
    let projects = Projects::new(accounts.pool());
    Some((accounts, projects))
}

macro_rules! with_stores {
    (|$accounts:ident, $projects:ident| $body:block) => {
        let Some(($accounts, $projects)) = stores().await else {
            return;
        };
        $body
    };
}

/// Somebody to own the projects.
async fn person(accounts: &Accounts, email: &str) -> String {
    accounts
        .register(email, "A Person", "a-long-enough-password")
        .await
        .expect("registration should succeed")
        .0
        .id
}

async fn a_project(projects: &Projects, owner: &str, name: &str) -> Project {
    projects
        .create(owner, name, "standard-pcr")
        .await
        .expect("the project should be created")
}

#[tokio::test]
async fn a_project_comes_back_with_what_it_was_given() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "one@example.org").await;
        let project = a_project(&projects, &owner, "  TP53 exon 7  ").await;

        assert_eq!(project.name, "TP53 exon 7", "the name is trimmed");
        assert_eq!(project.module_id, "standard-pcr");
        assert_eq!(project.notes, "");
        assert_eq!(project.run_count, 0);
        assert_eq!(project.settings, json!({}));
    });
}

#[tokio::test]
async fn somebody_elses_project_is_indistinguishable_from_a_missing_one() {
    with_stores!(|accounts, projects| {
        let mine = person(&accounts, "mine@example.org").await;
        let yours = person(&accounts, "yours@example.org").await;
        let project = a_project(&projects, &mine, "Mine").await;

        // The same error either way, on purpose: telling them apart would say
        // whether a project exists, which is not theirs to know.
        assert_eq!(
            projects.get(&yours, &project.id).await.unwrap_err(),
            ProjectError::NotFound
        );
        assert_eq!(
            projects.get(&yours, "no-such-id").await.unwrap_err(),
            ProjectError::NotFound
        );
    });
}

#[tokio::test]
async fn nobody_can_change_or_delete_a_project_they_do_not_own() {
    with_stores!(|accounts, projects| {
        let mine = person(&accounts, "owner@example.org").await;
        let yours = person(&accounts, "stranger@example.org").await;
        let project = a_project(&projects, &mine, "Mine").await;

        assert!(projects
            .update(&yours, &project.id, Some("Yours now"), None, None, None)
            .await
            .is_err());
        assert!(projects.delete(&yours, &project.id).await.is_err());

        // And it is untouched.
        let after = projects.get(&mine, &project.id).await.expect("still mine");
        assert_eq!(after.name, "Mine");
    });
}

#[tokio::test]
async fn a_draft_survives_being_saved_a_field_at_a_time() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "draft@example.org").await;
        let project = a_project(&projects, &owner, "Draft").await;

        let step_one = json!({ "template": "ACGT", "step": "target" });
        projects
            .update(&owner, &project.id, None, None, Some(&step_one), None)
            .await
            .expect("the draft saves");

        // Changing the notes must not wipe the draft: somebody who fills in a
        // step and then renames the project should not lose the step.
        let after = projects
            .update(&owner, &project.id, None, Some("a note"), None, None)
            .await
            .expect("the note saves");

        assert_eq!(after.settings, step_one);
        assert_eq!(after.notes, "a note");
        assert_eq!(after.name, "Draft");
    });
}

#[tokio::test]
async fn stale_project_snapshots_do_not_overwrite_newer_edits() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "conflict@example.org").await;
        let project = a_project(&projects, &owner, "Concurrent draft").await;

        let first = json!({ "template": "AAAA" });
        let updated = projects
            .update(
                &owner,
                &project.id,
                None,
                None,
                Some(&first),
                Some(project.updated_at),
            )
            .await
            .expect("the first editor saves");

        let stale = json!({ "template": "CCCC" });
        let error = projects
            .update(
                &owner,
                &project.id,
                None,
                None,
                Some(&stale),
                Some(project.updated_at),
            )
            .await
            .expect_err("the stale snapshot is refused");
        assert!(matches!(error, ProjectError::Conflict(_)));

        let after = projects
            .get(&owner, &project.id)
            .await
            .expect("still readable");
        assert_eq!(after.updated_at, updated.updated_at);
        assert_eq!(after.settings, first);
    });
}

#[tokio::test]
async fn a_run_keeps_the_request_beside_the_result() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "runs@example.org").await;
        let project = a_project(&projects, &owner, "With runs").await;

        let request = json!({ "template": "ACGTACGT", "howMany": 3 });
        let result = json!({ "pairs": [1, 2], "target": { "name": "demo" } });
        let run = projects
            .save_run(&owner, &project.id, "first try", &request, &result)
            .await
            .expect("the run saves");

        // A result without the request that produced it cannot be reproduced,
        // and reproducing it is the point of keeping it.
        assert_eq!(run.request, request);
        assert_eq!(run.result, result);
        assert_eq!(run.label, "first try");
    });
}

#[tokio::test]
async fn listing_runs_summarises_them_without_moving_the_results() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "summary@example.org").await;
        let project = a_project(&projects, &owner, "Summaries").await;

        projects
            .save_run(
                &owner,
                &project.id,
                "",
                &json!({}),
                &json!({ "pairs": [1, 2, 3], "target": { "name": "TP53" } }),
            )
            .await
            .expect("saves");

        let summaries = projects.runs(&owner, &project.id).await.expect("lists");
        assert_eq!(summaries.len(), 1);
        assert_eq!(summaries[0].pair_count, 3);
        assert_eq!(summaries[0].target_name, "TP53");
    });
}

#[tokio::test]
async fn listing_survives_a_legacy_result_that_is_not_the_expected_shape() {
    /*
     * The summary is computed by the database from every row in the project,
     * and a result whose `pairs` is not an array used to make the whole
     * listing refuse â€” so one imported oddity turned every later visit to the
     * project into an error, forever. Each extraction now asks what it is
     * holding first, and answers "none" rather than refusing.
     */
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "odd-shapes@example.org").await;
        let project = a_project(&projects, &owner, "Odd shapes").await;

        for result in [
            json!("a bare string"),
            json!([1, 2, 3]),
            json!({ "pairs": "not an array", "target": "no object either" }),
            json!({ "pairs": [1], "target": { "name": "TP53" } }),
        ] {
            sqlx::query(
                "INSERT INTO runs (id, project_id, label, request, result)
                 VALUES ($1, $2, '', $3, $4)",
            )
            .bind(uuid::Uuid::new_v4().to_string())
            .bind(&project.id)
            .bind(json!({}))
            .bind(result)
            .execute(projects.pool())
            .await
            .expect("a legacy run can be present in storage");
        }

        let summaries = projects
            .runs(&owner, &project.id)
            .await
            .expect("lists anyway");
        assert_eq!(summaries.len(), 4);

        // The one well-formed row still reports what it has; the rest count as
        // nothing rather than taking the listing down with them.
        let good = summaries
            .iter()
            .find(|one| one.pair_count == 1)
            .expect("the well-formed row keeps its pair");
        assert_eq!(good.target_name, "TP53");
        assert_eq!(
            summaries.iter().filter(|one| one.pair_count == 0).count(),
            3,
            "the odd rows read as empty"
        );
    });
}

#[tokio::test]
async fn a_run_counts_towards_its_project_and_moves_it_up_the_list() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "order@example.org").await;
        let older = a_project(&projects, &owner, "Older").await;
        let newer = a_project(&projects, &owner, "Newer").await;

        assert_eq!(
            projects.list(&owner).await.expect("lists")[0].id,
            newer.id,
            "the most recently touched comes first"
        );

        projects
            .save_run(&owner, &older.id, "", &json!({}), &json!({ "pairs": [] }))
            .await
            .expect("saves");

        let listed = projects.list(&owner).await.expect("lists");
        assert_eq!(
            listed[0].id, older.id,
            "running in it counts as touching it"
        );
        assert_eq!(listed[0].run_count, 1);
    });
}

#[tokio::test]
async fn a_project_keeps_only_its_most_recent_runs() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "quota@example.org").await;
        let project = a_project(&projects, &owner, "Busy").await;

        for index in 0..(MAX_RUNS_PER_PROJECT + 5) {
            projects
                .save_run(
                    &owner,
                    &project.id,
                    &format!("run {index}"),
                    &json!({}),
                    &json!({ "pairs": [] }),
                )
                .await
                .expect("saves");
        }

        let kept = projects.runs(&owner, &project.id).await.expect("lists");
        assert_eq!(kept.len() as i64, MAX_RUNS_PER_PROJECT);
        // The oldest go first: the one somebody wants back is nearly always
        // the last one they ran.
        assert_eq!(
            kept[0].label,
            format!("run {}", MAX_RUNS_PER_PROJECT + 4),
            "the newest survives"
        );
    });
}

#[tokio::test]
async fn deleting_a_project_takes_its_runs_with_it() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "cascade@example.org").await;
        let project = a_project(&projects, &owner, "Doomed").await;
        let run = projects
            .save_run(&owner, &project.id, "", &json!({}), &json!({}))
            .await
            .expect("saves");

        projects.delete(&owner, &project.id).await.expect("deletes");

        assert_eq!(
            projects.run(&owner, &run.id).await.unwrap_err(),
            ProjectError::NotFound
        );
    });
}

#[tokio::test]
async fn deleting_the_account_takes_the_projects_with_it() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "gone@example.org").await;
        let project = a_project(&projects, &owner, "Also doomed").await;

        accounts
            .delete(&owner, "a-long-enough-password")
            .await
            .expect("the account is deletable");

        assert_eq!(
            projects.get(&owner, &project.id).await.unwrap_err(),
            ProjectError::NotFound
        );
    });
}

/* â”€â”€ Deleting, and changing your mind â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

#[tokio::test]
async fn a_deleted_project_is_gone_from_every_ordinary_view_of_it() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "regret@example.org").await;
        let project = a_project(&projects, &owner, "Deleted by accident").await;

        projects.delete(&owner, &project.id).await.expect("deletes");

        // Not "mostly gone". Somebody who deleted a project must not meet it
        // again in a list, or a count, or by opening the URL they still have.
        assert_eq!(
            projects.get(&owner, &project.id).await.unwrap_err(),
            ProjectError::NotFound
        );
        assert!(projects
            .list(&owner)
            .await
            .expect("lists")
            .iter()
            .all(|one| one.id != project.id));
    });
}

#[tokio::test]
async fn a_deleted_project_comes_back_with_its_runs() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "undo@example.org").await;
        let project = a_project(&projects, &owner, "TP53 exon 7").await;
        projects
            .update(&owner, &project.id, None, Some("ordered twice"), None, None)
            .await
            .expect("the draft saves");
        let run = projects
            .save_run(
                &owner,
                &project.id,
                "first go",
                &json!({"a": 1}),
                &json!({"b": 2}),
            )
            .await
            .expect("saves");

        projects.delete(&owner, &project.id).await.expect("deletes");
        let back = projects
            .restore(&owner, &project.id)
            .await
            .expect("restores");

        // An undo that returns an empty project is not an undo. The runs are
        // what the work was; they survive because they reference the table
        // rather than the view that hides deleted rows.
        assert_eq!(back.name, "TP53 exon 7");
        assert_eq!(back.notes, "ordered twice");
        assert_eq!(back.run_count, 1);
        assert_eq!(
            projects
                .run(&owner, &run.id)
                .await
                .expect("the run is back")
                .id,
            run.id
        );
    });
}

#[tokio::test]
async fn a_deleted_project_is_nobody_elses_to_bring_back() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "mine@example.org").await;
        let stranger = person(&accounts, "theirs@example.org").await;
        let project = a_project(&projects, &owner, "Not yours").await;
        projects.delete(&owner, &project.id).await.expect("deletes");

        assert_eq!(
            projects.restore(&stranger, &project.id).await.unwrap_err(),
            ProjectError::NotFound
        );
        // And it is still the owner's to bring back afterwards.
        assert!(projects.restore(&owner, &project.id).await.is_ok());
    });
}

#[tokio::test]
async fn restoring_something_that_was_never_deleted_says_so() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "fine@example.org").await;
        let project = a_project(&projects, &owner, "Still here").await;

        assert_eq!(
            projects.restore(&owner, &project.id).await.unwrap_err(),
            ProjectError::NotFound
        );
    });
}

#[tokio::test]
async fn a_deleted_project_stops_counting_against_the_ceiling() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "ceiling@example.org").await;
        let project = a_project(&projects, &owner, "Takes a slot").await;

        let before = projects.list(&owner).await.expect("lists").len();
        projects.delete(&owner, &project.id).await.expect("deletes");
        let after = projects.list(&owner).await.expect("lists").len();

        // The ceiling is counted with the same query the list uses, so this is
        // really asking whether the count reads through the view too. A soft
        // delete that leaves rows counting towards a limit is a soft delete
        // that eventually locks somebody out of their own account.
        assert_eq!(after, before - 1);
    });
}

#[tokio::test]
async fn a_purge_takes_only_what_is_past_the_window() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "purge@example.org").await;
        let recent = a_project(&projects, &owner, "Deleted this morning").await;
        let ancient = a_project(&projects, &owner, "Deleted last year").await;

        projects.delete(&owner, &recent.id).await.expect("deletes");
        projects.delete(&owner, &ancient.id).await.expect("deletes");

        // Reach past the API to age one of them, because the alternative is a
        // test that waits thirty days.
        sqlx::query(
            "UPDATE projects_all SET deleted_at = now() - make_interval(days => $1)
              WHERE id = $2",
        )
        .bind(Projects::UNDO_WINDOW_DAYS + 1)
        .bind(&ancient.id)
        .execute(projects.pool())
        .await
        .expect("the deletion date is adjustable");

        assert_eq!(projects.purge_deleted().await.expect("purges"), 1);
        assert!(projects.restore(&owner, &recent.id).await.is_ok());
        assert_eq!(
            projects.restore(&owner, &ancient.id).await.unwrap_err(),
            ProjectError::NotFound
        );
    });
}

/* â”€â”€ What an import will hold â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

/// One incoming project with nothing in it yet.
fn an_incoming(id: &str) -> Incoming {
    let now = Utc::now();
    Incoming {
        id: id.to_owned(),
        name: "Restored".to_owned(),
        notes: String::new(),
        module_id: "standard-pcr".to_owned(),
        settings: json!({}),
        draft_schema_version: Some(pcr_contracts::DRAFT_SCHEMA_VERSION),
        module_contract_version: Some(MODULE_CONTRACT_VERSION.to_owned()),
        created_at: now,
        updated_at: now,
        runs: Vec::new(),
    }
}

/// One current-format historical run belonging to the supplied exported project.
fn an_incoming_run(project_id: &str) -> IncomingRun {
    IncomingRun {
        id: uuid::Uuid::new_v4().to_string(),
        project_id: project_id.to_owned(),
        label: String::new(),
        request: json!({}),
        result: json!({}),
        request_schema_version: REQUEST_SCHEMA_VERSION,
        result_schema_version: RESULT_SCHEMA_VERSION,
        module_contract_version: MODULE_CONTRACT_VERSION.to_owned(),
        toolchain_fingerprint: None,
        run_fingerprint: None,
        engine_id: None,
        module_id: Some("standard-pcr".to_owned()),
        result_count: 0,
        result_unit: "result".to_owned(),
        target_name: String::new(),
        created_at: Utc::now(),
    }
}

#[tokio::test]
async fn an_import_refuses_a_run_whose_halves_are_not_objects() {
    /*
     * The summary query reads `pairs` and `target` out of every stored result,
     * so a result of any other shape is exactly what a listing cannot afford.
     * Refusing it at the door — by name, not by silence — is cheaper than
     * storing it and hardening everything that ever reads back.
     */
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "shapes@example.org").await;

        for (side, value) in [
            ("request", json!([1, 2])),
            ("result", json!("just a string")),
        ] {
            let mut project = an_incoming(&uuid::Uuid::new_v4().to_string());
            project.runs.push(an_incoming_run(&project.id));
            match side {
                "request" => project.runs[0].request = value,
                _ => project.runs[0].result = value,
            }

            let error = projects.import(&owner, &[project]).await.unwrap_err();
            assert!(
                matches!(error, ProjectError::NotAnExport(_)),
                "a non-object {side} should be refused"
            );
            assert!(
                error.to_string().contains(side),
                "the refusal should name the half that was wrong: {error}"
            );
        }
    });
}

#[tokio::test]
async fn an_import_refuses_oversized_documents_naming_the_limit() {
    /*
     * A document past these bounds was not written by this server; it was
     * edited into something else. Storing it anyway would make one row
     * expensive to read back forever, and the summary would move megabytes to
     * show a list. The refusal says the number, because "too big" alone leaves
     * somebody guessing which field and by how much.
     */
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "sizes@example.org").await;
        let id = || uuid::Uuid::new_v4().to_string();

        // Notes over their ceiling.
        let mut big_notes = an_incoming(&id());
        big_notes.notes = "x".repeat(MAX_NOTES_BYTES + 1);

        // A draft over its ceiling.
        let mut big_settings = an_incoming(&id());
        big_settings.settings = json!({ "text": "x".repeat(MAX_SETTINGS_BYTES) });

        // A label over its ceiling, on an otherwise ordinary run.
        let mut big_label = an_incoming(&id());
        let mut oversized_label_run = an_incoming_run(&big_label.id);
        oversized_label_run.label = "x".repeat(MAX_LABEL_BYTES + 1);
        big_label.runs.push(oversized_label_run);

        // One run whose request and result together pass the run ceiling.
        let mut big_run = an_incoming(&id());
        let bulk = "x".repeat(MAX_RUN_DOCUMENT_BYTES - 64);
        let mut oversized_document_run = an_incoming_run(&big_run.id);
        oversized_document_run.request = json!({ "text": bulk });
        oversized_document_run.result = json!({ "more": bulk });
        big_run.runs.push(oversized_document_run);

        for document in [&big_notes, &big_settings, &big_label, &big_run] {
            let error = projects
                .import(&owner, std::slice::from_ref(document))
                .await
                .unwrap_err();
            assert!(
                matches!(error, ProjectError::NotAnExport(_)),
                "an oversized document should be refused"
            );
            assert!(
                error.to_string().contains("bytes"),
                "the refusal should say the limit: {error}"
            );
        }

        // And none of them landed: refusing happens before the first row.
        assert_eq!(
            projects.list(&owner).await.expect("lists").len(),
            0,
            "nothing from a refused import should have been written"
        );
    });
}

#[tokio::test]
async fn deleting_a_project_permanently_revokes_its_old_share_links() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "share-revoke@example.org").await;
        let project = a_project(&projects, &owner, "Shared then deleted").await;
        let run = projects
            .save_run(&owner, &project.id, "one", &json!({}), &json!({}))
            .await
            .expect("run saves");
        let token = projects
            .share_run(&owner, &project.id, &run.id)
            .await
            .expect("share starts");
        assert!(projects.run_by_share(&token).await.is_ok());

        projects.delete(&owner, &project.id).await.expect("deletes");
        projects
            .restore(&owner, &project.id)
            .await
            .expect("restores");

        assert_eq!(
            projects.run_by_share(&token).await.unwrap_err(),
            ProjectError::NotFound,
            "undoing deletion must not resurrect a capability URL already revoked"
        );
        assert!(!projects
            .is_shared(&owner, &project.id, &run.id)
            .await
            .expect("restored run is readable"));
    });
}

#[tokio::test]
async fn restoring_a_deleted_project_cannot_bypass_the_live_project_ceiling() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "restore-quota@example.org").await;
        let deleted = a_project(&projects, &owner, "Deleted slot").await;
        projects.delete(&owner, &deleted.id).await.expect("deletes");

        for index in 0..MAX_PROJECTS_PER_USER {
            projects
                .create(&owner, &format!("Project {index}"), "standard-pcr")
                .await
                .expect("fills the live quota");
        }

        assert!(matches!(
            projects.restore(&owner, &deleted.id).await.unwrap_err(),
            ProjectError::TooManyProjects(_)
        ));
    });
}

#[tokio::test]
async fn import_refuses_more_projects_than_a_server_export_can_contain() {
    with_stores!(|accounts, projects| {
        let owner = person(&accounts, "import-project-count@example.org").await;
        let incoming = (0..=MAX_IMPORT_PROJECTS)
            .map(|_| an_incoming(&uuid::Uuid::new_v4().to_string()))
            .collect::<Vec<_>>();

        assert!(matches!(
            projects.import(&owner, &incoming).await.unwrap_err(),
            ProjectError::NotAnExport(_)
        ));
        assert!(projects.list(&owner).await.expect("lists").is_empty());
    });
}
