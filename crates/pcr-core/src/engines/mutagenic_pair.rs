//! Topology-aware site-directed mutagenesis request boundary.
//!
//! Q5 back-to-back, QuikChange complementary, QuikChange Lightning Multi and
//! NEBuilder multi-site are different assay topologies.  This boundary keeps
//! them separate and forwards the reviewed identity to the scientific worker;
//! it never treats one topology as a preset of another.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::common::{check_how_many, check_positions, check_template};
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

include!("mutagenesis_authority.generated.rs");

const ACCEPTS: &[Modifier] = &[Modifier::Tails];
const MAX_TEMPLATE_BASES: usize = 20_000;
const MOST_PAIRS: u8 = 10;
const TEMPLATE_METHYLATION_STATES: &[&str] = &[
    "unknown",
    "dam-methylated",
    "unmethylated",
    "other-reviewed",
];

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
/// One requested sequence edit.
pub struct Edit {
    /// Edit kind, such as substitution, insertion, or deletion.
    pub kind: String,
    /// Zero-based edit coordinate.
    pub at: usize,
    #[serde(default)]
    /// Replacement sequence when the edit supplies one.
    pub to: Option<String>,
    #[serde(default)]
    /// Number of reference bases replaced by the edit.
    pub replacing: Option<usize>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
/// Request boundary for topology-aware mutagenic primer design.
pub struct MutagenicPairRequest {
    /// Template sequence to edit.
    pub template: String,
    #[serde(default)]
    /// Whether lowercase template bases are intentional soft masking.
    pub lowercase_masking: Option<bool>,
    #[serde(default)]
    /// Optional request label.
    pub name: Option<String>,
    #[serde(default)]
    /// Assay metadata.
    pub assay: Option<serde_json::Value>,
    #[serde(default)]
    /// Single edit compatibility field.
    pub edit: Option<Edit>,
    #[serde(default)]
    /// Ordered multi-edit request.
    pub edits: Option<Vec<Edit>>,
    #[serde(default)]
    /// Mutagenesis topology identity.
    pub mutagenesis_topology: Option<String>,
    #[serde(default)]
    /// Amino-acid-level edit metadata.
    pub amino_acid_edit: Option<serde_json::Value>,
    #[serde(default)]
    /// Codon selection policy.
    pub codon_policy: Option<String>,
    #[serde(default)]
    /// Codon-usage metadata.
    pub codon_usage: Option<serde_json::Value>,
    #[serde(default)]
    /// Library design mode.
    pub library_mode: Option<String>,
    #[serde(default)]
    /// Library edit metadata.
    pub library_edit: Option<serde_json::Value>,
    #[serde(default)]
    /// Template methylation status.
    pub template_methylation_status: Option<String>,
    #[serde(default)]
    /// Polymerase identity.
    pub polymerase: Option<String>,
    #[serde(default)]
    /// Design purpose.
    pub purpose: Option<String>,
    #[serde(default)]
    /// Reaction conditions metadata.
    pub conditions: Option<serde_json::Value>,
    #[serde(default)]
    /// Additional design constraints.
    pub constraints: Option<serde_json::Value>,
    #[serde(default)]
    /// Requested number of primer pairs.
    pub how_many: Option<u8>,
    #[serde(default)]
    /// Post-amplification protocol identity.
    pub post_amplification_protocol: Option<String>,
    /// Empirical observations are stored with the run and have no sequence-
    /// ranking decision impact.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
}

/// Engine adapter for topology-aware mutagenic primer design.
#[derive(Debug, Clone, Default)]
pub struct MutagenicPair {
    worker: Worker,
}

impl MutagenicPair {
    /// Construct the unbound engine.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Bind this engine to an explicit scientific execution port.
    #[must_use]
    pub fn with_worker(worker: Worker) -> Self {
        Self { worker }
    }
}

impl Engine for MutagenicPair {
    fn id(&self) -> EngineId {
        EngineId::MutagenicPair
    }

    fn accepts(&self) -> &'static [Modifier] {
        ACCEPTS
    }

    fn presets(&self) -> Result<Option<serde_json::Value>> {
        self.worker.call("presets", &json!({})).map(Some)
    }

    fn validate(&self, request: &serde_json::Value) -> Result<()> {
        parse(request).map(|_| ())
    }

    fn design(&self, request: serde_json::Value) -> Result<serde_json::Value> {
        let parsed = parse(&request)?;
        self.worker.call("mutagenic", &parsed.to_worker())
    }
}

fn parse(request: &serde_json::Value) -> Result<MutagenicPairRequest> {
    let parsed: MutagenicPairRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

fn validate_edit(edit: &Edit, template_bases: usize) -> Result<()> {
    if !MUTAGENESIS_EDIT_KINDS.contains(&edit.kind.as_str()) {
        return Err(CoreError::InvalidRequest(format!(
            "`{}` is not a reviewed edit kind. Choose: {}.",
            edit.kind,
            MUTAGENESIS_EDIT_KINDS.join(", ")
        )));
    }
    if edit.kind == "insert" {
        if edit.at > template_bases {
            return Err(CoreError::InvalidRequest(format!(
                "The insertion boundary is at base {} of a {template_bases}-base sequence, which is outside it.",
                edit.at
            )));
        }
    } else {
        check_positions(&[edit.at], template_bases, "edit")?;
    }
    let putting = edit.to.as_deref().unwrap_or_default();
    let replacing = edit.replacing.unwrap_or_default();
    match edit.kind.as_str() {
        "substitute" if putting.is_empty() => Err(CoreError::InvalidRequest(
            "A substitution needs a non-empty `to` sequence.".to_owned(),
        )),
        "substitute" if putting.len() != replacing => Err(CoreError::InvalidRequest(
            "A substitution must replace the same number of bases; use an insertion/deletion or an explicit multi-edit replacement workflow when lengths differ.".to_owned(),
        )),
        "insert" if putting.is_empty() => Err(CoreError::InvalidRequest(
            "An insertion needs a non-empty `to` sequence.".to_owned(),
        )),
        "insert" if replacing > 0 => Err(CoreError::InvalidRequest(
            "An insertion replaces zero template bases.".to_owned(),
        )),
        "delete" if !putting.is_empty() => Err(CoreError::InvalidRequest(
            "A deletion cannot also supply a replacement sequence.".to_owned(),
        )),
        "delete" if replacing == 0 => Err(CoreError::InvalidRequest(
            "A deletion of zero bases changes nothing.".to_owned(),
        )),
        _ => {
            if edit.kind != "insert" && edit.at.saturating_add(replacing) > template_bases {
                return Err(CoreError::InvalidRequest(
                    "The edit extends past the end of the submitted plasmid.".to_owned(),
                ));
            }
            Ok(())
        }
    }
}

fn expected_protocol(topology: &str) -> Option<&'static str> {
    match topology {
        "q5-back-to-back" => Some("neb-q5-e0554"),
        "quikchange-complementary" => Some("agilent-quikchange-lightning-210518"),
        "quikchange-lightning-multi" => Some("agilent-quikchange-lightning-multi-210513-210516"),
        "nebuilder-multisite" => Some("neb-nebuilder-multisite"),
        _ => None,
    }
}

impl MutagenicPairRequest {
    fn check(&self) -> Result<()> {
        let template_bases = check_template(&self.template, MAX_TEMPLATE_BASES)?;
        if let Some(wanted) = self.how_many {
            check_how_many(wanted, MOST_PAIRS)?;
        }
        if let Some(constraints) = &self.constraints {
            if !constraints
                .as_object()
                .map(|v| v.is_empty())
                .unwrap_or(false)
            {
                return Err(CoreError::InvalidRequest(
                    "Site-directed mutagenesis does not accept generic PCR constraint overrides; topology-specific authorities own primer geometry.".to_owned(),
                ));
            }
        }

        let topology = self
            .mutagenesis_topology
            .as_deref()
            .unwrap_or("q5-back-to-back");
        if !MUTAGENESIS_TOPOLOGY_FAMILIES.contains(&topology) {
            return Err(CoreError::InvalidRequest(format!(
                "`{topology}` is not a reviewed mutagenesis topology. Choose: {}.",
                MUTAGENESIS_TOPOLOGY_FAMILIES.join(", ")
            )));
        }
        if let Some(policy) = &self.codon_policy {
            if !MUTAGENESIS_CODON_POLICIES.contains(&policy.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{policy}` is not a reviewed codon policy. Choose: {}.",
                    MUTAGENESIS_CODON_POLICIES.join(", ")
                )));
            }
        }
        if let Some(state) = &self.template_methylation_status {
            if !TEMPLATE_METHYLATION_STATES.contains(&state.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{state}` is not a supported template methylation state. Choose: {}.",
                    TEMPLATE_METHYLATION_STATES.join(", ")
                )));
            }
        }

        let library_mode = self.library_mode.as_deref().unwrap_or("none");
        if !MUTAGENESIS_LIBRARY_MODES.contains(&library_mode) {
            return Err(CoreError::InvalidRequest(format!(
                "`{library_mode}` is not a reviewed library mode. Choose: {}.",
                MUTAGENESIS_LIBRARY_MODES.join(", ")
            )));
        }
        if library_mode != "none" {
            if self
                .library_edit
                .as_ref()
                .and_then(serde_json::Value::as_object)
                .is_none()
            {
                return Err(CoreError::InvalidRequest(
                    "A degenerate-library request requires `libraryEdit` with an explicit coordinate/codon declaration.".to_owned(),
                ));
            }
            return Ok(());
        }

        if let Some(edit) = &self.edit {
            validate_edit(edit, template_bases)?;
        }
        if let Some(edits) = &self.edits {
            if edits.is_empty() {
                return Err(CoreError::InvalidRequest(
                    "`edits` cannot be an empty array.".to_owned(),
                ));
            }
            for edit in edits {
                validate_edit(edit, template_bases)?;
            }
        }
        let edit_count = usize::from(self.edit.is_some())
            + self.edits.as_ref().map(Vec::len).unwrap_or_default()
            + usize::from(self.amino_acid_edit.is_some());
        if edit_count == 0 {
            return Err(CoreError::InvalidRequest(
                "A mutagenesis request requires `edit`, `edits`, an `aminoAcidEdit`, or an explicit library design.".to_owned(),
            ));
        }
        if self.edit.is_some() && self.edits.is_some() {
            return Err(CoreError::InvalidRequest(
                "Send either `edit` or `edits`, not both; the coordinate truth must be unambiguous.".to_owned(),
            ));
        }
        if topology == "q5-back-to-back" && edit_count != 1 {
            return Err(CoreError::InvalidRequest(
                "Q5 back-to-back is a single-edit PCRStudio topology; route multiple edits to Lightning Multi or NEBuilder multi-site.".to_owned(),
            ));
        }
        if topology == "quikchange-complementary" && edit_count != 1 {
            return Err(CoreError::InvalidRequest(
                "QuikChange complementary topology requires exactly one edit.".to_owned(),
            ));
        }
        if topology == "q5-back-to-back" {
            let q5_edit = self
                .edit
                .as_ref()
                .or_else(|| self.edits.as_ref().and_then(|v| v.first()));
            if let Some(edit) = q5_edit {
                if edit.kind == "insert" && edit.to.as_deref().unwrap_or_default().len() > 100 {
                    return Err(CoreError::InvalidRequest(
                        "The reviewed Q5 branch supports split-tail insertion design through 100 nt; larger insertions route to an assembly topology.".to_owned(),
                    ));
                }
            }
        }

        let protocol = self.post_amplification_protocol.as_deref().ok_or_else(|| {
            CoreError::InvalidRequest(
                "The selected mutagenesis topology requires an explicit named `postAmplificationProtocol`.".to_owned(),
            )
        })?;
        if !MUTAGENESIS_PROTOCOLS.contains(&protocol) {
            return Err(CoreError::InvalidRequest(format!(
                "`{protocol}` is not a reviewed mutagenesis protocol. Choose: {}.",
                MUTAGENESIS_PROTOCOLS.join(", ")
            )));
        }
        if let Some(expected) = expected_protocol(topology) {
            if protocol != expected {
                return Err(CoreError::InvalidRequest(format!(
                    "Topology `{topology}` requires protocol `{expected}`; PCRStudio does not substitute another mutagenesis chemistry."
                )));
            }
        }
        Ok(())
    }

    fn to_worker(&self) -> serde_json::Value {
        let mut payload = serde_json::Map::new();
        payload.insert("template".into(), self.template.clone().into());
        let mut put = |key: &str, value: Option<serde_json::Value>| {
            if let Some(value) = value {
                payload.insert(key.to_owned(), value);
            }
        };
        put("lowercase_masking", self.lowercase_masking.map(Into::into));
        put("name", self.name.clone().map(Into::into));
        put("assay", self.assay.clone());
        put(
            "edit",
            self.edit
                .as_ref()
                .map(|v| serde_json::to_value(v).expect("serializable edit")),
        );
        put(
            "edits",
            self.edits
                .as_ref()
                .map(|v| serde_json::to_value(v).expect("serializable edits")),
        );
        put(
            "mutagenesis_topology",
            Some(
                self.mutagenesis_topology
                    .clone()
                    .unwrap_or_else(|| "q5-back-to-back".to_owned())
                    .into(),
            ),
        );
        put("amino_acid_edit", self.amino_acid_edit.clone());
        put("codon_policy", self.codon_policy.clone().map(Into::into));
        put("codon_usage", self.codon_usage.clone());
        put("library_mode", self.library_mode.clone().map(Into::into));
        put("library_edit", self.library_edit.clone());
        put(
            "template_methylation_status",
            self.template_methylation_status.clone().map(Into::into),
        );
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("how_many", self.how_many.map(Into::into));
        put(
            "post_amplification_protocol",
            self.post_amplification_protocol.clone().map(Into::into),
        );
        put("workflow_evidence", self.workflow_evidence.clone());
        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn q5_large_insertion_up_to_reviewed_boundary_is_accepted() {
        let parsed = parse(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "edit": { "kind": "insert", "at": 10, "to": "GGGAAAT" },
            "mutagenesisTopology": "q5-back-to-back",
            "postAmplificationProtocol": "neb-q5-e0554"
        }))
        .expect("split-tail Q5 insertion is a reviewed branch");
        assert_eq!(parsed.edit.as_ref().expect("edit").at, 10);
    }

    #[test]
    fn topology_and_protocol_cannot_be_cross_wired() {
        let error = parse(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "edit": { "kind": "substitute", "at": 4, "to": "T", "replacing": 1 },
            "mutagenesisTopology": "quikchange-complementary",
            "postAmplificationProtocol": "neb-q5-e0554"
        }))
        .expect_err("different topologies are not presets of each other");
        assert!(error.to_string().contains("requires protocol"));
    }

    #[test]
    fn q5_insertion_above_one_hundred_routes_elsewhere() {
        let error = parse(&json!({
            "template": "ACGTACGTACGTACGTACGT",
            "edit": { "kind": "insert", "at": 10, "to": "A".repeat(101) },
            "mutagenesisTopology": "q5-back-to-back",
            "postAmplificationProtocol": "neb-q5-e0554"
        }))
        .expect_err("the sourced boundary is explicit");
        assert!(error.to_string().contains("100 nt"));
    }
}
