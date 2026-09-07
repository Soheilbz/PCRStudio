#[cfg(test)]
use super::*;

#[test]
fn a_name_is_trimmed_rather_than_refused_for_its_spaces() {
    assert_eq!(check_name("  TP53 exon 7  ").expect("valid"), "TP53 exon 7");
}

#[test]
fn an_empty_name_is_refused_with_a_sentence() {
    let error = check_name("   ").expect_err("no name");
    assert!(matches!(error, ProjectError::InvalidName(_)));
    assert!(error.to_string().contains("needs a name"));
}

#[test]
fn a_name_too_long_to_show_says_the_limit() {
    let error = check_name(&"x".repeat(MAX_NAME + 1)).expect_err("too long");
    assert!(error.to_string().contains(&MAX_NAME.to_string()));
}

#[test]
fn control_characters_are_refused_because_they_break_a_breadcrumb() {
    assert!(check_name("first\nsecond").is_err());
}

#[test]
fn errors_serialise_with_a_kind_the_interface_can_branch_on() {
    let json = serde_json::to_value(ProjectError::NotFound).expect("serialisable");
    assert_eq!(json, serde_json::json!({ "kind": "notFound" }));
}

#[test]
fn ordinary_project_writes_enforce_storage_limits() {
    let settings = serde_json::json!({ "draft": "x".repeat(MAX_SETTINGS_BYTES) });
    assert!(matches!(
        check_project_data(Some(&"x".repeat(MAX_NOTES_BYTES + 1)), Some(&settings)),
        Err(ProjectError::InvalidData(_))
    ));
    assert!(matches!(
        check_project_data(None, Some(&serde_json::json!([]))),
        Err(ProjectError::InvalidData(_))
    ));
}

#[test]
fn ordinary_run_writes_enforce_shape_and_size_limits() {
    assert!(matches!(
        check_run_data("", &serde_json::json!([]), &serde_json::json!({})),
        Err(ProjectError::InvalidData(_))
    ));
    let oversized = serde_json::json!({ "result": "x".repeat(MAX_RUN_DOCUMENT_BYTES) });
    assert!(matches!(
        check_run_data("", &serde_json::json!({}), &oversized),
        Err(ProjectError::InvalidData(_))
    ));
}
