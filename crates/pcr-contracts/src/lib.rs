//! Read-only access to Generation 1 foundation generated architecture contracts.
//!
//! Canonical files live under `contracts/*.toml`; this crate embeds generated
//! JSON projections so Rust domain/storage/server code never grows a second
//! hand-maintained module/engine/tool registry.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::sync::OnceLock;

use serde::Deserialize;

include!("../generated/foundation.generated.rs");

#[derive(Debug, Clone, Deserialize)]
struct ModulesDocument {
    modules: std::collections::HashMap<String, ModuleContract>,
}

/// Minimal runtime projection for one public module.
#[derive(Debug, Clone, Deserialize)]
pub struct ModuleContract {
    /// Stable module id.
    pub id: String,
    /// Engine id.
    pub engine: String,
    /// Worker command.
    pub command: String,
    /// Release status.
    pub status: String,
    /// Relative execution weight.
    pub resource_weight: u32,
    /// Required semantic/form context paths used by browser readiness.
    #[serde(default)]
    pub required_context: Vec<String>,
    /// Conditional semantic/form context rules retained for browser readiness.
    #[serde(default)]
    pub conditional_required_context: Vec<serde_json::Value>,
    /// Exact request-payload paths required at the HTTP boundary.
    #[serde(default)]
    pub wire_required_context: Vec<String>,
    /// Conditional request-payload rules. These paths describe the wire shape,
    /// not flat browser controls.
    #[serde(default)]
    pub wire_conditional_required_context: Vec<serde_json::Value>,
    /// At-least-one groups for mutually exclusive wire representations.
    #[serde(default)]
    pub wire_required_any_of: Vec<Vec<String>>,
    /// Canonical field-to-workflow-step ownership.
    #[serde(default)]
    pub field_owners: std::collections::HashMap<String, String>,
}

#[derive(Debug, Clone, Deserialize)]
struct EnginesDocument {
    engines: std::collections::HashMap<String, EngineContract>,
}

/// Minimal runtime projection for one engine.
#[derive(Debug, Clone, Deserialize)]
pub struct EngineContract {
    /// Stable engine id.
    pub id: String,
    /// Worker command.
    pub command: String,
    /// Relative execution weight.
    pub resource_weight: u32,
}

fn modules() -> &'static ModulesDocument {
    static VALUE: OnceLock<ModulesDocument> = OnceLock::new();
    VALUE.get_or_init(|| {
        serde_json::from_str(include_str!("../generated/module-contracts.generated.json"))
            .expect("generated module contract must deserialize")
    })
}

fn engines() -> &'static EnginesDocument {
    static VALUE: OnceLock<EnginesDocument> = OnceLock::new();
    VALUE.get_or_init(|| {
        serde_json::from_str(include_str!("../generated/engine-contracts.generated.json"))
            .expect("generated engine contract must deserialize")
    })
}

#[derive(Debug, Clone, Deserialize)]
struct ToolsDocument {
    tools: std::collections::HashMap<String, serde_json::Value>,
}

fn tools() -> &'static ToolsDocument {
    static VALUE: OnceLock<ToolsDocument> = OnceLock::new();
    VALUE.get_or_init(|| {
        serde_json::from_str(include_str!("../generated/tool-contracts.generated.json"))
            .expect("generated tool contract must deserialize")
    })
}

/// Every declared scientific tool id in deterministic order.
#[must_use]
pub fn tool_ids() -> Vec<&'static str> {
    let mut ids: Vec<_> = tools().tools.keys().map(String::as_str).collect();
    ids.sort_unstable();
    ids
}

/// Generated public tool metadata for operator diagnostics and provenance.
#[must_use]
pub fn tool(tool_id: &str) -> Option<&'static serde_json::Value> {
    tools().tools.get(tool_id)
}

/// Find one canonical public module.
#[must_use]
pub fn module(module_id: &str) -> Option<&'static ModuleContract> {
    modules().modules.get(module_id)
}

/// Return canonical required-context paths that are missing from one public
/// request payload. The module contract remains the single source of truth;
/// callers must not restate the canonical required/conditional field matrix.
#[must_use]
pub fn missing_required_wire_context(
    module_id: &str,
    payload: &serde_json::Map<String, serde_json::Value>,
) -> Vec<String> {
    let Some(contract) = module(module_id) else {
        return Vec::new();
    };

    fn camel(segment: &str) -> String {
        let mut out = String::with_capacity(segment.len());
        let mut upper = false;
        for ch in segment.chars() {
            if ch == '_' {
                upper = true;
            } else if upper {
                out.extend(ch.to_uppercase());
                upper = false;
            } else {
                out.push(ch);
            }
        }
        out
    }

    fn at_path<'a>(
        root: &'a serde_json::Map<String, serde_json::Value>,
        path: &str,
    ) -> Option<&'a serde_json::Value> {
        let mut parts = path.split('.');
        let first = camel(parts.next()?);
        let mut current = root.get(&first)?;
        for part in parts {
            current = current.as_object()?.get(&camel(part))?;
        }
        Some(current)
    }

    fn supplied(value: Option<&serde_json::Value>) -> bool {
        match value {
            None | Some(serde_json::Value::Null) => false,
            Some(serde_json::Value::String(value)) => !value.trim().is_empty(),
            Some(serde_json::Value::Array(values)) => !values.is_empty(),
            Some(serde_json::Value::Object(values)) => !values.is_empty(),
            // `false` can be an explicit and scientifically meaningful answer
            // (for example singleTube/circular), so presence is what matters.
            Some(serde_json::Value::Bool(_)) | Some(serde_json::Value::Number(_)) => true,
        }
    }

    fn rule_matches(
        payload: &serde_json::Map<String, serde_json::Value>,
        when: &serde_json::Map<String, serde_json::Value>,
    ) -> bool {
        when.iter()
            .all(|(path, expected)| at_path(payload, path) == Some(expected))
    }

    let mut missing = Vec::new();
    for path in &contract.wire_required_context {
        if !supplied(at_path(payload, path)) {
            missing.push(path.clone());
        }
    }
    for rule in &contract.wire_conditional_required_context {
        let Some(rule_obj) = rule.as_object() else {
            continue;
        };
        let Some(when) = rule_obj.get("when").and_then(serde_json::Value::as_object) else {
            continue;
        };
        if !rule_matches(payload, when) {
            continue;
        }
        let Some(required) = rule_obj
            .get("required_context")
            .and_then(serde_json::Value::as_array)
        else {
            continue;
        };
        for path in required.iter().filter_map(serde_json::Value::as_str) {
            if !supplied(at_path(payload, path)) && !missing.iter().any(|existing| existing == path)
            {
                missing.push(path.to_owned());
            }
        }
    }
    for group in &contract.wire_required_any_of {
        if !group.iter().any(|path| supplied(at_path(payload, path))) {
            missing.push(format!("one-of({})", group.join(" | ")));
        }
    }
    missing
}

/// Find one canonical engine.
#[must_use]
pub fn engine(engine_id: &str) -> Option<&'static EngineContract> {
    engines().engines.get(engine_id)
}

/// Resolve a module id to its engine id.
#[must_use]
pub fn engine_for_module(module_id: &str) -> Option<&'static str> {
    module(module_id).map(|value| value.engine.as_str())
}

/// Resolve a module id to its configured execution weight.
#[must_use]
pub fn resource_weight_for_module(module_id: &str) -> Option<u32> {
    module(module_id).map(|value| value.resource_weight)
}

/// Resolve a worker command to its engine id.
#[must_use]
pub fn engine_for_command(command: &str) -> Option<&'static str> {
    engines()
        .engines
        .values()
        .find(|value| value.command == command)
        .map(|value| value.id.as_str())
}

/// Every declared module id in deterministic order.
#[must_use]
pub fn module_ids() -> Vec<&'static str> {
    let mut ids: Vec<_> = modules().modules.keys().map(String::as_str).collect();
    ids.sort_unstable();
    ids
}

/// Validation severity shared by UI, API, core and worker.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ValidationSeverity {
    /// Informational evidence.
    Info,
    /// Non-blocking caution.
    Warning,
    /// Invalid or incomplete state.
    Error,
}

/// Page that owns a validation fact.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ValidationStep {
    /// Target/input.
    Target,
    /// Assay design.
    Design,
    /// Assay strategy.
    Strategy,
    /// Numeric/oligo constraints.
    Constraints,
    /// Vector/enzyme context.
    Vector,
    /// Bench reaction context.
    Reaction,
    /// Specificity evidence.
    Specificity,
    /// Validation evidence.
    Validation,
    /// Construct simulation.
    Construct,
    /// Final review.
    Review,
}

/// Machine-readable validation fact.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ValidationIssue {
    /// Stable code; never parse `message` for behavior.
    pub code: String,
    /// Severity.
    pub severity: ValidationSeverity,
    /// Owning workflow step.
    pub owner_step: ValidationStep,
    /// Canonical field path when applicable.
    pub field_path: Option<String>,
    /// Human-readable explanation.
    pub message: String,
    /// Layer/validator that produced the issue.
    pub source: String,
    /// Whether execution is blocked.
    pub blocking: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generated_registry_has_expected_partition() {
        assert_eq!(module_ids().len(), 21);
        assert_eq!(engines().engines.len(), 11);
        assert_eq!(tool_ids().len(), 12);
        for module in modules().modules.values() {
            let engine = engine(&module.engine).expect("module engine exists");
            assert_eq!(module.command, engine.command);
        }
    }

    #[derive(serde::Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct DifferentialCase {
        module: String,
        expected_engine: String,
        expected_command: String,
        resource_weight: u32,
        required_context: Vec<String>,
        conditional_required_context: Vec<serde_json::Value>,
        wire_required_context: Vec<String>,
        wire_conditional_required_context: Vec<serde_json::Value>,
        wire_required_any_of: Vec<Vec<String>>,
        field_owners: std::collections::HashMap<String, String>,
        wrong_engine: String,
    }

    #[derive(serde::Deserialize)]
    struct DifferentialDocument {
        cases: Vec<DifferentialCase>,
    }

    #[test]
    fn differential_corpus_matches_rust_projection() {
        let doc: DifferentialDocument = serde_json::from_str(include_str!(
            "../generated/differential-context.generated.json"
        ))
        .expect("generated differential corpus must deserialize");
        assert_eq!(doc.cases.len(), 21);
        for case in doc.cases {
            let module = module(&case.module).expect("differential module exists");
            assert_eq!(module.engine, case.expected_engine);
            assert_eq!(module.command, case.expected_command);
            assert_eq!(module.resource_weight, case.resource_weight);
            assert_eq!(module.required_context, case.required_context);
            assert_eq!(
                module.conditional_required_context,
                case.conditional_required_context
            );
            assert_eq!(module.wire_required_context, case.wire_required_context);
            assert_eq!(
                module.wire_conditional_required_context,
                case.wire_conditional_required_context
            );
            assert_eq!(module.wire_required_any_of, case.wire_required_any_of);
            assert_eq!(module.field_owners, case.field_owners);
            assert_ne!(module.engine, case.wrong_engine);
        }
    }
    #[test]
    fn required_context_validation_uses_generated_contract_and_preserves_false() {
        let mut qpcr = serde_json::Map::new();
        qpcr.insert(
            "probeProtocol".into(),
            serde_json::json!("thermofisher-taqman-conventional"),
        );
        qpcr.insert(
            "probeChemistry".into(),
            serde_json::json!("conventional-hydrolysis"),
        );
        qpcr.insert("probeReporter".into(), serde_json::json!("FAM"));
        assert_eq!(
            missing_required_wire_context("qpcr-probe", &qpcr),
            vec!["probe_quencher"]
        );
        qpcr.insert("probeQuencher".into(), serde_json::json!("NFQ"));
        assert!(missing_required_wire_context("qpcr-probe", &qpcr).is_empty());

        let mut nested = serde_json::Map::new();
        nested.insert("shares".into(), serde_json::json!(2));
        nested.insert("margin".into(), serde_json::json!(10));
        nested.insert("singleTube".into(), serde_json::json!(false));
        nested.insert("carryoverPrevention".into(), serde_json::json!("none"));
        nested.insert("transferMode".into(), serde_json::json!("direct"));
        assert!(missing_required_wire_context("nested-pcr", &nested).is_empty());
    }

    #[test]
    fn conditional_required_context_is_enforced_from_generated_contract() {
        let mut inverse = serde_json::Map::new();
        inverse.insert(
            "inverseBranch".into(),
            serde_json::json!("supplied-circular-template"),
        );
        inverse.insert(
            "circularizationProvenance".into(),
            serde_json::json!("user-supplied"),
        );
        assert!(missing_required_wire_context("inverse-pcr", &inverse)
            .contains(&"circle_length".to_owned()));
        inverse.insert("circleLength".into(), serde_json::json!(1200));
        assert!(!missing_required_wire_context("inverse-pcr", &inverse)
            .contains(&"circle_length".to_owned()));
    }

    #[test]
    fn wire_context_is_not_inferred_from_flat_browser_fields() {
        let mut standard = serde_json::Map::new();
        standard.insert(
            "flankingNumericContext".into(),
            serde_json::json!({"additive": "high-gc-enhancer"}),
        );
        assert!(missing_required_wire_context("standard-pcr", &standard)
            .contains(&"flanking_numeric_context.gc_enhancer_percent".to_owned()));
        standard.insert(
            "flankingNumericContext".into(),
            serde_json::json!({"additive": "high-gc-enhancer", "gcEnhancerPercent": 10.0}),
        );
        assert!(missing_required_wire_context("standard-pcr", &standard).is_empty());

        let mut mutagenesis = serde_json::Map::new();
        mutagenesis.insert(
            "mutagenesisTopology".into(),
            serde_json::json!("q5-back-to-back"),
        );
        mutagenesis.insert(
            "postAmplificationProtocol".into(),
            serde_json::json!("neb-q5-e0554"),
        );
        assert!(
            missing_required_wire_context("site-directed-mutagenesis", &mutagenesis)
                .iter()
                .any(|item| item.starts_with("one-of("))
        );
        mutagenesis.insert(
            "edit".into(),
            serde_json::json!({"kind": "substitute", "at": 4, "to": "T", "replacing": 1}),
        );
        assert!(
            missing_required_wire_context("site-directed-mutagenesis", &mutagenesis).is_empty()
        );
    }
}
