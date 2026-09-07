//! Primers that carry the joins, for assembling fragments without ligation.
//!
//! Gibson assembly and its relatives do not cut and paste. Each fragment is
//! made with ends that already match its neighbour, an exonuclease chews those
//! ends back, and the matching single strands find each other. The primers put
//! those ends there: each carries a tail that is not on its own template at
//! all, but on the fragment next door.
//!
//! Three things about the request are unlike every other engine here.
//!
//! There is no template. What this takes is a plan — an ordered list of
//! fragments — and the sequence everything is a statement about is the
//! construct those fragments would make. An overlap spans a join, so it cannot
//! be reasoned about from either fragment alone.
//!
//! The joining chemistry is required and cannot be guessed. Each supported
//! chemistry keeps its own reviewed overlap envelope and protocol identity. In
//! In the current contract, Gibson is executable only through the named NEB E5510 branch while the
//! distinct NEBuilder HiFi branch is executable through explicit E2621, E5520
//! or E2623 protocol identities. The historical generic Gibson recipe remains
//! reference evidence, never a policy fallback, and method-specific numbers do
//! not cross-inherit between Gibson and NEBuilder.
//!
//! And each fragment says whether it is being amplified, which decides the
//! geometry rather than describing it. A fragment that arrives already cut has
//! no primer, so it cannot carry a tail — and the whole overlap has to come
//! from its neighbour. Two such fragments meeting cannot be joined at all.
//!
//! Nothing scientific happens in this file. It checks the request and hands it
//! to the worker.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::common::check_template;
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

include!("assembly_authority.generated.rs");

/// Modifiers this engine will be combined with.
///
/// None of them, and that is the finding rather than an omission. Tails are not
/// a modifier here — they are the entire mechanism, and every primer this
/// engine designs already carries one chosen to join two named fragments.
/// Offering the modifier as well would let somebody ask for a second tail with
/// nothing to say about what it should be.
const ACCEPTS: &[Modifier] = &[];

/// The most fragments one assembly may join.
///
/// The vendors' own figures stop well below this; past a handful the yield
/// falls off and the usual advice is to assemble in two stages.
const MOST_FRAGMENTS: usize = 12;

/// The longest construct this will take in one request.
const MAX_CONSTRUCT_BASES: usize = 1_000_000;

/// The largest template one amplified fragment may name.
///
/// The construct itself is limited by [`MAX_CONSTRUCT_BASES`] once the pieces
/// are summed; this is the ceiling for the sequence a fragment is pulled
/// *from*, which arrived unchecked however large it was.
const MAX_TEMPLATE_BASES: usize = 1_000_000;

/// What kinds of fragment a plan can hold.
const KINDS: &[&str] = &[
    "amplified",
    "fixed",
    "literal",
    "pcr-amplified",
    "restriction-digest",
    "synthetic-dsdna",
    "ssdna-oligo",
    "annealed-oligos",
    "existing-linear",
];

/// One piece of the intended construct.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Fragment {
    /// What to call it. Junctions are reported by the fragments either side.
    #[serde(default)]
    pub name: Option<String>,
    /// `amplified`, `fixed`, or `literal`.
    #[serde(default)]
    pub kind: Option<String>,
    /// What this contributes to the finished construct.
    pub sequence: String,
    /// For an amplified fragment, the template it comes from when that is
    /// larger than the piece being used.
    #[serde(default)]
    pub template: Option<String>,
    /// Sequence is always expressed in final-construct orientation; this field records source orientation provenance.
    #[serde(default)]
    pub orientation: Option<String>,
    #[serde(default)]
    /// Fragment concentration in nanograms per microlitre.
    pub concentration_ng_ul: Option<f64>,
    #[serde(default)]
    /// Fragment mass in nanograms.
    pub mass_ng: Option<f64>,
    #[serde(default)]
    /// Fragment input volume in microlitres.
    pub volume_ul: Option<f64>,
    #[serde(default)]
    /// Restriction-enzyme metadata.
    pub restriction: Option<serde_json::Value>,
    #[serde(default)]
    /// Construct feature annotations.
    pub features: Option<Vec<serde_json::Value>>,
    #[serde(default)]
    /// Fragment provenance metadata.
    pub provenance: Option<serde_json::Value>,
}

/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct JunctionPrimersRequest {
    /// The fragments to join, in the order they go in.
    pub segments: Vec<Fragment>,
    /// Whether the finished construct closes into a circle.
    ///
    /// Required. Circular and linear plans have different junction graphs;
    /// omission cannot be treated as a scientific default.
    #[serde(default)]
    pub circular: Option<bool>,
    /// Which joining chemistry. Required — see the module note.
    pub method: String,
    /// Optional named vendor protocol overlay; absence is intentional.
    #[serde(default)]
    pub assembly_protocol: Option<String>,
    /// What to call the design.
    #[serde(default)]
    pub name: Option<String>,
    /// Which assay this is, and the numbers that assay differs by.
    #[serde(default)]
    pub assay: Option<serde_json::Value>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// What the annealing portion of each primer has to satisfy.
    ///
    /// The tail is not held to these: it is judged at the assembly temperature
    /// in the assembly's own units, and mixing the two is how an oligo gets a
    /// block set by a temperature describing neither step.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// Empirical assembly/QC observations; decision impact on sequence ranking is none.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
}

/// An assembly design, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct JunctionPrimers {
    worker: Worker,
}

impl JunctionPrimers {
    /// An engine that will call whatever `PCR_PYTHON` names.
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

impl Engine for JunctionPrimers {
    fn id(&self) -> EngineId {
        EngineId::JunctionPrimers
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
        self.worker.call("junction", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<JunctionPrimersRequest> {
    let parsed: JunctionPrimersRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

impl JunctionPrimersRequest {
    /// Whether this request could describe an assembly at all.
    fn check(&self) -> Result<()> {
        if self.segments.len() < 2 {
            return Err(CoreError::InvalidRequest(
                "An assembly joins at least two fragments. One fragment is not an \
                 assembly, it is a PCR."
                    .to_owned(),
            ));
        }
        if self.segments.len() > MOST_FRAGMENTS {
            return Err(CoreError::InvalidRequest(format!(
                "This plan joins {} fragments; the most this designs at once is \
                 {MOST_FRAGMENTS}. Past a handful the yield falls off and the usual \
                 answer is to assemble in two stages.",
                self.segments.len()
            )));
        }
        if self.method.trim().is_empty() {
            return Err(CoreError::InvalidRequest(
                "This needs to know which assembly chemistry you are using, and there \
                 is nothing to default it to: the overlap length is a property of the \
                 enzyme rather than of your DNA."
                    .to_owned(),
            ));
        }
        let assay_id = self
            .assay
            .as_ref()
            .and_then(|assay| assay.get("id"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default();
        if assay_id == "gibson-assembly" && !matches!(self.method.as_str(), "gibson" | "nebuilder")
        {
            return Err(CoreError::InvalidRequest(format!(
                "gibson-assembly supports reviewed `gibson` and distinct `nebuilder` branches; `{}` is not executable in this module.",
                self.method
            )));
        }
        if let Some(protocol) = &self.assembly_protocol {
            if !ASSEMBLY_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "protocol {protocol} is not an assembly protocol this knows. It knows: {}.",
                    ASSEMBLY_PROTOCOLS.join(", ")
                )));
            }
            if protocol == "neb-e5510" && self.method != "gibson" {
                return Err(CoreError::InvalidRequest(
                    "the NEB E5510 overlay belongs to the `gibson` chemistry".to_owned(),
                ));
            }
            if matches!(
                protocol.as_str(),
                "neb-nebuilder-e2621" | "neb-nebuilder-e5520" | "neb-nebuilder-e2623"
            ) && self.method != "nebuilder"
            {
                return Err(CoreError::InvalidRequest(
                    "NEBuilder E2621/E5520/E2623 overlays require `method=nebuilder`".to_owned(),
                ));
            }
        }
        if self.method == "iva" {
            return Err(CoreError::InvalidRequest(
                "Generation-1 IVA is recognised but not executable until its published \
                 overlap-Tm optimisation model is reproduced and calibrated; no generic \
                 Wallace/PCR-Tm substitute is allowed in any policy mode."
                    .to_owned(),
            ));
        }
        if self.method == "gibson" && self.assembly_protocol.as_deref() != Some("neb-e5510") {
            return Err(CoreError::InvalidRequest(
                "Generation-1 Gibson requires the reviewed `neb-e5510` protocol; \
                 the legacy generic/original Gibson recipe is not an executable branch in any policy mode."
                    .to_owned(),
            ));
        }
        if self.method == "nebuilder"
            && !matches!(
                self.assembly_protocol.as_deref(),
                Some("neb-nebuilder-e2621" | "neb-nebuilder-e5520" | "neb-nebuilder-e2623")
            )
        {
            return Err(CoreError::InvalidRequest("Generation-1 NEBuilder requires an explicit reviewed E2621/E5520/E2623 protocol identity.".to_owned()));
        }

        if self.circular.is_none() {
            return Err(CoreError::InvalidRequest(
                "Assembly topology requires explicit `circular=true|false`; circularity changes the junction graph and is not inferred.".to_owned(),
            ));
        }

        let mut total = 0usize;
        let mut amplified = 0usize;
        for (index, fragment) in self.segments.iter().enumerate() {
            // The same shared sequence check every engine applies: present,
            // plausible, and within a ceiling. Without it a paste error in one
            // fragment cost a process spawn to be told about.
            let bases =
                check_template(&fragment.sequence, MAX_CONSTRUCT_BASES).map_err(|error| {
                    CoreError::InvalidRequest(format!("Fragment {}: {error}", index + 1))
                })?;
            total += bases;
            let kind = fragment.kind.as_deref().filter(|value| !value.trim().is_empty()).ok_or_else(|| {
                CoreError::InvalidRequest(format!(
                    "Fragment {} needs explicit `kind`: amplified, fixed, or literal. PCRStudio does not infer PCR amplification from omission.",
                    index + 1
                ))
            })?;
            if !KINDS.contains(&kind) {
                return Err(CoreError::InvalidRequest(format!(
                    "Fragment {} is a `{kind}`, which is not a kind of fragment this \
                     assembles. It takes: {}.",
                    index + 1,
                    KINDS.join(", ")
                )));
            }
            // The template an amplified fragment is pulled from was never
            // bounded: the construct limit summed the fragments, and this
            // rode alongside them however large it was.
            if let Some(template) = &fragment.template {
                check_template(template, MAX_TEMPLATE_BASES).map_err(|error| {
                    CoreError::InvalidRequest(format!(
                        "Fragment {} names a template of its own: {error}",
                        index + 1
                    ))
                })?;
            }
            if matches!(kind, "amplified" | "pcr-amplified") {
                amplified += 1;
            }
            if kind == "restriction-digest" && fragment.restriction.is_none() {
                return Err(CoreError::InvalidRequest(format!(
                    "Fragment {} is restriction-digest and requires typed `restriction` metadata.",
                    index + 1
                )));
            }
            if !matches!(
                fragment.orientation.as_deref().unwrap_or("final-construct"),
                "final-construct" | "forward" | "reverse"
            ) {
                return Err(CoreError::InvalidRequest(format!("Fragment {} orientation must be final-construct, forward or reverse; sequence itself remains in final-construct orientation.", index + 1)));
            }
        }

        if amplified == 0 {
            return Err(CoreError::InvalidRequest(
                "An assembly needs at least one fragment made by PCR; fixed/literal fragments alone have no primers to design.".to_owned(),
            ));
        }
        if total > MAX_CONSTRUCT_BASES {
            return Err(CoreError::InvalidRequest(format!(
                "The finished construct would be {total} bases. This engine takes up \
                 to {MAX_CONSTRUCT_BASES}."
            )));
        }
        Ok(())
    }

    /// This request in the worker's own vocabulary.
    fn to_worker(&self) -> serde_json::Value {
        let segments: Vec<serde_json::Value> = self
            .segments
            .iter()
            .enumerate()
            .map(|(index, fragment)| {
                let mut entry = serde_json::Map::new();
                entry.insert(
                    "name".into(),
                    fragment
                        .name
                        .clone()
                        .unwrap_or_else(|| format!("fragment {}", index + 1))
                        .into(),
                );
                entry.insert(
                    "kind".into(),
                    fragment
                        .kind
                        .clone()
                        .expect("validated fragment kind")
                        .into(),
                );
                entry.insert("sequence".into(), fragment.sequence.clone().into());
                if let Some(template) = fragment.template.clone() {
                    entry.insert("template".into(), template.into());
                }
                if let Some(v) = fragment.orientation.clone() {
                    entry.insert("orientation".into(), v.into());
                }
                if let Some(v) = fragment.concentration_ng_ul {
                    entry.insert("concentration_ng_ul".into(), v.into());
                }
                if let Some(v) = fragment.mass_ng {
                    entry.insert("mass_ng".into(), v.into());
                }
                if let Some(v) = fragment.volume_ul {
                    entry.insert("volume_ul".into(), v.into());
                }
                if let Some(v) = fragment.restriction.clone() {
                    entry.insert("restriction".into(), v);
                }
                if let Some(v) = fragment.features.clone() {
                    entry.insert("features".into(), v.into());
                }
                if let Some(v) = fragment.provenance.clone() {
                    entry.insert("provenance".into(), v);
                }
                serde_json::Value::Object(entry)
            })
            .collect();

        let mut payload = serde_json::Map::new();
        payload.insert("segments".into(), segments.into());
        payload.insert("method".into(), self.method.clone().into());
        payload.insert(
            "circular".into(),
            self.circular.expect("validated assembly topology").into(),
        );

        let mut put = |key: &str, value: Option<serde_json::Value>| {
            if let Some(value) = value {
                payload.insert(key.to_owned(), value);
            }
        };
        put("name", self.name.clone().map(Into::into));
        put(
            "assembly_protocol",
            self.assembly_protocol.clone().map(Into::into),
        );
        put("assay", self.assay.clone());
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("workflow_evidence", self.workflow_evidence.clone());

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(value: serde_json::Value) -> Result<JunctionPrimersRequest> {
        parse(&value)
    }

    fn two() -> serde_json::Value {
        json!({
            "segments": [
                { "name": "vector", "kind": "amplified", "sequence": "ACGTACGTACGTACGT" },
                { "name": "insert", "kind": "amplified", "sequence": "TTTTGGGGCCCCAAAA" },
            ],
            "method": "nebuilder",
            "assemblyProtocol": "neb-nebuilder-e2621",
            "circular": true,
        })
    }

    #[test]
    fn an_assembly_of_one_fragment_is_a_pcr() {
        let error = request(json!({
            "segments": [{ "sequence": "ACGTACGTACGT" }],
            "method": "nebuilder",
        }))
        .expect_err("one fragment");
        assert!(error.to_string().contains("is a PCR"), "{error}");
    }

    #[test]
    fn a_plan_without_a_chemistry_is_refused_rather_than_defaulted() {
        // The chemistry is assay identity, not a numeric preference; there is
        // no scientifically neutral overlap profile to fall back on.
        let error = request(json!({
            "segments": [
                { "sequence": "ACGTACGTACGTACGT" },
                { "sequence": "TTTTGGGGCCCCAAAA" },
            ],
        }))
        .expect_err("no method");
        assert!(error.to_string().contains("method"), "{error}");
    }

    #[test]
    fn a_plan_with_nothing_amplified_has_no_primers_to_design() {
        let error = request(json!({
            "segments": [
                { "kind": "fixed", "sequence": "ACGTACGTACGTACGT" },
                { "kind": "fixed", "sequence": "TTTTGGGGCCCCAAAA" },
            ],
            "method": "nebuilder",
            "assemblyProtocol": "neb-nebuilder-e2621",
            "circular": false,
        }))
        .expect_err("nothing to amplify");
        assert!(error.to_string().contains("made by PCR"), "{error}");
    }

    #[test]
    fn a_kind_this_does_not_assemble_lists_the_ones_it_does() {
        let error = request(json!({
            "segments": [
                { "kind": "ligated", "sequence": "ACGTACGTACGTACGT" },
                { "sequence": "TTTTGGGGCCCCAAAA" },
            ],
            "method": "nebuilder",
            "assemblyProtocol": "neb-nebuilder-e2621",
            "circular": false,
        }))
        .expect_err("not a kind");
        let message = error.to_string();
        for kind in KINDS {
            assert!(message.contains(kind), "{kind} not offered: {message}");
        }
    }

    #[test]
    fn a_plan_carries_explicit_circularity_to_the_worker() {
        // Circularity is explicit because the last fragment either meets the
        // first or ends at a real linear boundary.
        let parsed = request(two()).expect("a well-formed plan");
        assert_eq!(parsed.to_worker()["circular"], true);
    }

    #[test]
    fn every_fragment_reaches_the_worker_named_and_kinded() {
        // The worker reports junctions by the fragments either side of them,
        // so an unnamed fragment would produce a junction nobody can place.
        let parsed = request(json!({
            "segments": [
                { "kind": "amplified", "sequence": "ACGTACGTACGTACGT" },
                { "kind": "amplified", "sequence": "TTTTGGGGCCCCAAAA" },
            ],
            "method": "gibson",
            "assemblyProtocol": "neb-e5510",
            "circular": true,
        }))
        .expect("a well-formed plan");

        let payload = parsed.to_worker();
        let segments = payload["segments"].as_array().expect("an array");
        assert_eq!(segments[0]["name"], "fragment 1");
        assert_eq!(segments[0]["kind"], "amplified");
        assert_eq!(payload["method"], "gibson");
    }

    #[test]
    fn an_unknown_assembly_protocol_is_refused() {
        let mut body = two();
        body["assemblyProtocol"] = json!("guess");
        let error = request(body).expect_err("unknown assembly protocol");
        assert!(error.to_string().contains("assembly protocol"), "{error}");
    }

    #[test]
    fn the_neb_overlay_requires_gibson_chemistry() {
        let mut body = two();
        body["method"] = json!("nebuilder");
        body["assemblyProtocol"] = json!("neb-e5510");
        let error = request(body).expect_err("mismatched kit overlay");
        assert!(error.to_string().contains("`gibson` chemistry"), "{error}");
    }

    #[test]
    fn a_named_assembly_protocol_reaches_the_worker() {
        let mut body = two();
        body["method"] = json!("gibson");
        body["assemblyProtocol"] = json!("neb-e5510");
        let parsed = request(body).expect("named assembly protocol");
        assert_eq!(parsed.to_worker()["assembly_protocol"], "neb-e5510");
    }

    #[test]
    fn an_amplified_fragments_own_template_is_no_longer_unbounded() {
        // The construct limit summed the fragments; the sequence a fragment is
        // pulled from arrived unchecked however large it was.
        let error = request(json!({
            "segments": [
                {
                    "kind": "amplified",
                    "sequence": "ACGTACGTACGTACGT",
                    "template": "A".repeat(MAX_TEMPLATE_BASES + 1),
                },
                { "kind": "amplified", "sequence": "TTTTGGGGCCCCAAAA" },
            ],
            "method": "nebuilder",
            "assemblyProtocol": "neb-nebuilder-e2621",
            "circular": false,
        }))
        .expect_err("an oversized source template");
        assert!(error.to_string().contains("Fragment 1"), "{error}");
    }

    #[test]
    fn a_paste_error_in_a_fragment_is_caught_before_a_process_starts() {
        let error = request(json!({
            "segments": [
                { "sequence": "soheil@example.com" },
                { "sequence": "TTTTGGGGCCCCAAAA" },
            ],
            "method": "nebuilder",
            "assemblyProtocol": "neb-nebuilder-e2621",
            "circular": false,
        }))
        .expect_err("not a sequence");
        assert!(error.to_string().contains("Fragment 1"), "{error}");
    }

    #[test]
    fn an_assembly_is_not_offered_the_tails_modifier() {
        // Tails are not a modifier here, they are the mechanism: every primer
        // already carries one chosen to join two named fragments.
        assert!(!ACCEPTS.contains(&Modifier::Tails));
        assert!(ACCEPTS.is_empty());
    }
}
