//! Specialized LAMP multiplex planning/evidence boundary.
//!
//! Modified-primer/probe multiplex LAMP topologies are not a generic extension
//! of standard LAMP set design. PCRStudio records the reviewed method identity,
//! selected peer-set hash and optical/evidence context without manufacturing a
//! modified oligo or target-specific signal model.
use crate::error::{CoreError, Result};
use serde::{Deserialize, Serialize};

pub const LAMP_MULTIPLEX_SOFTWARE_MAX_TARGETS: usize = 4;
const METHODS: &[&str] = &[
    "darq",
    "quasr",
    "flos",
    "assimilation-probe",
    "other-reviewed",
];

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LampMultiplexTarget {
    pub target: String,
    pub method: String,
    pub reporter: String,
    pub channel: String,
    pub modified_oligo_role: String,
    pub set_sha256: String,
    pub authority_id: String,
    pub empirical_evidence_ref: String,
}

pub fn validate(plan: Option<&[LampMultiplexTarget]>, topology: &str) -> Result<()> {
    if topology != "multiplex-modified-primer-probe" {
        if plan.is_some() {
            return Err(CoreError::InvalidRequest("lampMultiplexPlan is accepted only with lampDetectionTopology=`multiplex-modified-primer-probe`.".to_owned()));
        }
        return Ok(());
    }
    let plan=plan.ok_or_else(||CoreError::InvalidRequest("multiplex-modified-primer-probe requires a complete lampMultiplexPlan; PCRStudio does not infer a multiplex topology from standard LAMP primers.".to_owned()))?;
    if plan.is_empty() || plan.len() >= LAMP_MULTIPLEX_SOFTWARE_MAX_TARGETS {
        return Err(CoreError::InvalidRequest("lampMultiplexPlan must contain 1–3 peer targets (4 total including the current target); this is a software planning bound, not wet-lab qualification.".to_owned()));
    }
    let mut ids = std::collections::BTreeSet::new();
    let mut channels = std::collections::BTreeSet::new();
    let mut reporters = std::collections::BTreeSet::new();
    for row in plan {
        if row.target.trim().is_empty() || !ids.insert(row.target.trim().to_owned()) {
            return Err(CoreError::InvalidRequest(
                "lampMultiplexPlan target identities must be non-empty and unique.".to_owned(),
            ));
        }
        if !METHODS.contains(&row.method.as_str()) {
            return Err(CoreError::InvalidRequest("lampMultiplexPlan method must be darq, quasr, flos, assimilation-probe or other-reviewed.".to_owned()));
        }
        if row.reporter.trim().is_empty()
            || !reporters.insert(row.reporter.trim().to_owned())
            || row.channel.trim().is_empty()
            || !channels.insert(row.channel.trim().to_owned())
        {
            return Err(CoreError::InvalidRequest(
                "LAMP multiplex peers require unique explicit reporter and channel identities."
                    .to_owned(),
            ));
        }
        if row.modified_oligo_role.trim().is_empty()
            || row.authority_id.trim().is_empty()
            || row.empirical_evidence_ref.trim().is_empty()
        {
            return Err(CoreError::InvalidRequest("LAMP multiplex peers require modifiedOligoRole, authorityId and empiricalEvidenceRef.".to_owned()));
        }
        let sha = row.set_sha256.trim();
        if sha.len() != 64 || !sha.chars().all(|c| c.is_ascii_hexdigit()) {
            return Err(CoreError::InvalidRequest(
                "lampMultiplexPlan setSha256 must be a 64-character SHA-256 hex digest.".to_owned(),
            ));
        }
    }
    Ok(())
}
