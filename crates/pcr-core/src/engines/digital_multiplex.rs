//! Digital-PCR multiplex planning boundary.
//!
//! This deliberately does not turn the dye/EvaGreen flanking designer into a
//! probe-dPCR designer. It validates the panel architecture and preserves the
//! run/evidence contract. Thresholds, rain gates, cluster geometry and absolute
//! concentration remain measured-run evidence.

use crate::error::{CoreError, Result};
use serde::{Deserialize, Serialize};

include!("digital_multiplex_authority.generated.rs");

/// One target row in a digital multiplex panel.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DigitalMultiplexTarget {
    /// Stable target identity used to match panel rows.
    pub target: String,
    #[serde(default)]
    /// Optional reporter dye or channel label.
    pub reporter: Option<String>,
    #[serde(default)]
    /// Optional instrument detection channel.
    pub channel: Option<String>,
    #[serde(default)]
    /// Optional amplitude class used by the platform authority.
    pub amplitude_class: Option<String>,
    #[serde(default)]
    /// Planned primer concentration in nanomolar.
    pub primer_each_nm: Option<f64>,
    #[serde(default)]
    /// Planned probe concentration in nanomolar.
    pub probe_nm: Option<f64>,
}

/// Validate a digital multiplex panel against the reviewed platform boundary.
pub fn validate(
    mode: Option<&str>,
    panel: Option<&[DigitalMultiplexTarget]>,
    platform_id: &str,
    instrument_model: Option<&str>,
    protocol_id: Option<&str>,
) -> Result<()> {
    let mode = mode.unwrap_or("none");
    if !["none", "channel", "amplitude", "hybrid", "probe-mix"].contains(&mode) {
        return Err(CoreError::InvalidRequest(
            "digitalMultiplexMode must be one of: none, channel, amplitude, hybrid, probe-mix."
                .to_owned(),
        ));
    }
    let panel = panel.unwrap_or(&[]);
    if mode == "none" {
        if !panel.is_empty() {
            return Err(CoreError::InvalidRequest(
                "digitalMultiplexPanel requires a non-none digitalMultiplexMode.".to_owned(),
            ));
        }
        return Ok(());
    }
    if panel.len() < 2 || panel.len() > 12 {
        return Err(CoreError::InvalidRequest(
            "digitalMultiplexPanel must contain 2–12 targets; 12 is a software/planning bound, not a wet-lab validation claim."
                .to_owned(),
        ));
    }
    if protocol_id.is_some_and(|value| value != "not-selected") {
        return Err(CoreError::InvalidRequest(
            "digital multiplex probe/amplitude planning cannot inherit a named dye/EvaGreen chemistry. Leave digitalProtocol=not-selected and bind the exact probe multiplex chemistry in the Pair+Probe/vendor run authority."
                .to_owned(),
        ));
    }

    let mut target_ids = std::collections::BTreeSet::new();
    let mut channels = std::collections::BTreeSet::new();
    for row in panel {
        let target = row.target.trim();
        if target.is_empty() || !target_ids.insert(target.to_owned()) {
            return Err(CoreError::InvalidRequest(
                "digitalMultiplexPanel target identities must be non-empty and unique.".to_owned(),
            ));
        }
        for (label, value) in [
            ("primerEachNm", row.primer_each_nm),
            ("probeNm", row.probe_nm),
        ] {
            if value.is_some_and(|number| !number.is_finite() || number <= 0.0) {
                return Err(CoreError::InvalidRequest(format!(
                    "digital multiplex {label} must be a positive finite measured/planned concentration."
                )));
            }
        }
        let channel = row.channel.as_deref().unwrap_or("").trim();
        if mode == "channel" {
            if channel.is_empty()
                || row
                    .reporter
                    .as_deref()
                    .is_none_or(|value| value.trim().is_empty())
            {
                return Err(CoreError::InvalidRequest(
                    "channel dPCR multiplex requires reporter and channel for every target."
                        .to_owned(),
                ));
            }
            if !channels.insert(channel.to_owned()) {
                return Err(CoreError::InvalidRequest(
                    "channel dPCR multiplex requires unique explicit channels; use amplitude/hybrid mode when targets intentionally share a channel."
                        .to_owned(),
                ));
            }
        }
        if matches!(mode, "amplitude" | "hybrid")
            && row
                .amplitude_class
                .as_deref()
                .is_none_or(|value| value.trim().is_empty())
        {
            return Err(CoreError::InvalidRequest(
                "amplitude/hybrid dPCR multiplex requires an amplitudeClass for every target."
                    .to_owned(),
            ));
        }
    }
    let authority_key = if platform_id == "qiagen-qiacuity" {
        instrument_model.ok_or_else(|| CoreError::InvalidRequest(
            "digitalInstrumentModel is required for QIAcuity multiplex planning because model optical capacity differs.".to_owned(),
        ))?
    } else {
        platform_id
    };
    if let Some(authority) = digital_multiplex_platform_authority(authority_key) {
        if !authority.modes.contains(&mode) {
            return Err(CoreError::InvalidRequest(format!(
                "{} source-backed multiplex authority does not support mode {mode}; allowed modes: {}.",
                authority.family,
                authority.modes.join(", ")
            )));
        }
        if mode == "channel" && panel.len() > authority.detection_channels {
            return Err(CoreError::InvalidRequest(format!(
                "{} channel-per-target planning is source-backed only up to {} targets.",
                authority.family, authority.detection_channels
            )));
        }
        if panel.len() > authority.multiplex_target_bound {
            return Err(CoreError::InvalidRequest(format!(
                "{} multiplex planning is source-backed only up to {} targets; this is not a wet-lab qualification claim.",
                authority.family, authority.multiplex_target_bound
            )));
        }
    } else if platform_id == "qiagen-qiacuity" {
        return Err(CoreError::InvalidRequest(
            "unsupported QIAcuity multiplex instrument model".to_owned(),
        ));
    }
    Ok(())
}
