//! RPA multiplex evidence boundary.
//!
//! RPA final assay selection is empirical. This type records already selected
//! peer assays and their empirical evidence identity; it is not a generic PCR
//! multiplex optimiser and it never promotes a sequence-only shortlist to a
//! validated RPA panel.

use crate::error::{CoreError, Result};
use serde::{Deserialize, Serialize};

pub const RPA_MULTIPLEX_SOFTWARE_MAX_TARGETS: usize = 5;

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RpaMultiplexTarget {
    pub target: String,
    pub forward_primer: String,
    pub reverse_primer: String,
    #[serde(default)]
    pub detection_identity: Option<String>,
    #[serde(default)]
    pub empirical_evidence_ref: Option<String>,
}

fn valid_dna(value: &str) -> bool {
    let value = value.trim();
    !value.is_empty()
        && value.len() <= 200
        && value
            .chars()
            .all(|base| matches!(base.to_ascii_uppercase(), 'A' | 'C' | 'G' | 'T'))
}

pub fn validate(panel: Option<&[RpaMultiplexTarget]>) -> Result<()> {
    let Some(panel) = panel else {
        return Ok(());
    };
    if panel.is_empty() || panel.len() >= RPA_MULTIPLEX_SOFTWARE_MAX_TARGETS {
        return Err(CoreError::InvalidRequest(format!(
            "rpaMultiplexPanel must contain 1–{} peer assays ({} total including the current target); this is a software planning bound, not wet-lab qualification.",
            RPA_MULTIPLEX_SOFTWARE_MAX_TARGETS-1,RPA_MULTIPLEX_SOFTWARE_MAX_TARGETS
        )));
    }
    let mut ids = std::collections::BTreeSet::new();
    for row in panel {
        let target = row.target.trim();
        if target.is_empty() || !ids.insert(target.to_owned()) {
            return Err(CoreError::InvalidRequest(
                "rpaMultiplexPanel target identities must be non-empty and unique.".to_owned(),
            ));
        }
        if !valid_dna(&row.forward_primer) || !valid_dna(&row.reverse_primer) {
            return Err(CoreError::InvalidRequest("rpaMultiplexPanel peer forward/reverse primers must be 1–200 unambiguous DNA bases.".to_owned()));
        }
    }
    Ok(())
}
