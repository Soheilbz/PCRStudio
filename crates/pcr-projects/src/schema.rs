//! Persistence schema versions and non-destructive read migrations.
//!
//! Stored project drafts and run documents are immutable historical evidence.
//! PCRStudio therefore never rewrites a saved request/result merely because the
//! current application learned a newer shape. A caller may request a migrated
//! *view* for current code while the raw document and its original version stay
//! available for reproducibility and export.

use serde_json::Value;

/// Current draft schema written by the active Foundation contract.
pub const CURRENT_DRAFT_SCHEMA_VERSION: i32 = pcr_contracts::DRAFT_SCHEMA_VERSION;
/// Current design-request schema written by the active Foundation contract.
pub const CURRENT_REQUEST_SCHEMA_VERSION: i32 = pcr_contracts::REQUEST_SCHEMA_VERSION;
/// Current result schema written by the active Foundation contract.
pub const CURRENT_RESULT_SCHEMA_VERSION: i32 = pcr_contracts::RESULT_SCHEMA_VERSION;
/// Current cross-layer module contract identity.
pub const CURRENT_MODULE_CONTRACT_VERSION: &str = pcr_contracts::MODULE_CONTRACT_VERSION;

/// Persistence migration error.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum SchemaMigrationError {
    /// A stored version is newer than this build understands.
    #[error("stored {kind} schema version {found} is newer than supported version {supported}")]
    FutureVersion {
        /// Document class.
        kind: &'static str,
        /// Stored version.
        found: i32,
        /// Highest supported version.
        supported: i32,
    },
    /// A migration step for an older version is unavailable.
    #[error("no {kind} view migration exists from schema version {from}")]
    UnsupportedLegacy {
        /// Document class.
        kind: &'static str,
        /// Stored version.
        from: i32,
    },
}

fn check_version(kind: &'static str, from: i32, current: i32) -> Result<(), SchemaMigrationError> {
    if from > current {
        return Err(SchemaMigrationError::FutureVersion {
            kind,
            found: from,
            supported: current,
        });
    }
    if from < 1 {
        return Err(SchemaMigrationError::UnsupportedLegacy { kind, from });
    }
    Ok(())
}

/// Return a current draft view without mutating the stored draft.
pub fn migrate_draft_view(raw: &Value, from: i32) -> Result<Value, SchemaMigrationError> {
    check_version("draft", from, CURRENT_DRAFT_SCHEMA_VERSION)?;
    let mut view = raw.clone();
    let mut version = from;
    while version < CURRENT_DRAFT_SCHEMA_VERSION {
        view = match version {
            // legacy drafts were already flat browser values. CURRENT adds an explicit
            // version column and typed browser wrapper, not a semantic rewrite.
            1 => view,
            other => {
                return Err(SchemaMigrationError::UnsupportedLegacy {
                    kind: "draft",
                    from: other,
                })
            }
        };
        version += 1;
    }
    Ok(view)
}

/// Return a current request view without mutating the stored request.
pub fn migrate_request_view(raw: &Value, from: i32) -> Result<Value, SchemaMigrationError> {
    check_version("request", from, CURRENT_REQUEST_SCHEMA_VERSION)?;
    let mut view = raw.clone();
    let mut version = from;
    while version < CURRENT_REQUEST_SCHEMA_VERSION {
        view = match version {
            // V2 introduces the transport envelope at the IPC boundary. Saved
            // run payloads intentionally remain the scientific request body.
            1 => view,
            other => {
                return Err(SchemaMigrationError::UnsupportedLegacy {
                    kind: "request",
                    from: other,
                })
            }
        };
        version += 1;
    }
    Ok(view)
}

/// Return a current result view without mutating the stored result.
pub fn migrate_result_view(raw: &Value, from: i32) -> Result<Value, SchemaMigrationError> {
    check_version("result", from, CURRENT_RESULT_SCHEMA_VERSION)?;
    let mut view = raw.clone();
    let mut version = from;
    while version < CURRENT_RESULT_SCHEMA_VERSION {
        view = match version {
            // CURRENT adds structured execution/toolchain metadata. A historical
            // result without those facts must not have them fabricated.
            1 | 2 => view,
            // Current schema canonicalises workflow evidence as `observed`. Legacy records stored the
            // same flat scalar evidence under `fields`; migrate only the view.
            // The raw result and its original schema version remain unchanged.
            3 => migrate_workflow_evidence_v4(view),
            other => {
                return Err(SchemaMigrationError::UnsupportedLegacy {
                    kind: "result",
                    from: other,
                })
            }
        };
        version += 1;
    }
    Ok(view)
}

fn migrate_workflow_evidence_v4(mut view: Value) -> Value {
    let Some(root) = view.as_object_mut() else {
        return view;
    };
    let Some(evidence) = root
        .get_mut("workflow_evidence")
        .and_then(Value::as_object_mut)
    else {
        return view;
    };
    if !evidence.contains_key("observed") {
        if let Some(fields) = evidence.remove("fields") {
            evidence.insert("observed".to_owned(), fields);
        }
    }
    view
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn r15_evidence_is_migrated_in_the_view_only() {
        let raw = json!({
            "engine": "flanking-pair",
            "workflow_evidence": {
                "recorded": true,
                "decision_impact": "none",
                "fields": {"qpcrInstrument": "example"},
                "note": "historical"
            }
        });
        let view = migrate_result_view(&raw, 3).expect("v3 result should have a v4 view");
        assert_eq!(
            view["workflow_evidence"]["observed"]["qpcrInstrument"],
            "example"
        );
        assert!(view["workflow_evidence"].get("fields").is_none());
        assert_eq!(
            raw["workflow_evidence"]["fields"]["qpcrInstrument"],
            "example"
        );
    }

    #[test]
    fn current_evidence_is_not_rewritten() {
        let raw = json!({"workflow_evidence": {"decision_impact": "none", "observed": {"x": 1}}});
        assert_eq!(
            migrate_result_view(&raw, CURRENT_RESULT_SCHEMA_VERSION).unwrap(),
            raw
        );
    }
}
