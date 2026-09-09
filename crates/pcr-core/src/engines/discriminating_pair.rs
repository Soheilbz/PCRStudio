//! A pair that amplifies one allele and not the other.
//!
//! Allele-specific PCR puts the variant base at a primer's 3' end. On the
//! allele it was designed for the primer matches and extends; on the other it
//! ends in a mismatch and the polymerase extends far more slowly. The read-out
//! is whether a band appeared.
//!
//! Three things about the request are unlike every other engine here.
//!
//! It takes a variant rather than a region. Where to amplify is a consequence
//! of where the variant is, not something anybody chooses, and there is nothing
//! to default the position to — the whole design is anchored on one base.
//!
//! It takes both alleles, and both are required. A genotype is read by
//! comparing two reactions; one on its own cannot tell a homozygote from a tube
//! that failed.
//!
//! And the enzyme is part of the design rather than a preference. A
//! proofreading polymerase can alter or remove the terminal mismatch the assay
//! relies on, collapsing the intended discrimination and risking an apparent
//! heterozygote. The worker refuses that combination by name unless a separate
//! validated chemistry contract is introduced.
//!
//! Nothing scientific happens in this file. It checks the request and hands it
//! to the worker.

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::common::{check_excluded, check_positions, check_template, excluded_to_worker};
use crate::engine::Engine;
use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};
use crate::worker::Worker;

include!("discriminating_authority.generated.rs");

/// Modifiers this engine will be combined with.
///
/// Tails, because KASP's allele-specific primers carry fixed ones that a
/// fluorescent cassette reads.
///
/// Multiplex is an engine capability because the ARMS profile can activate it.
/// It is **not** an implicit property of every discriminating assay: the KASP
/// profile does not carry the modifier and the canonical LGC KASP branch is
/// singleplex. Tetra-ARMS uses four primers for one locus, which is also not a
/// claim of multi-locus multiplex chemistry.
///
/// Variant masking matters more here than almost anywhere else in this
/// project. It masks *other* known variants, not the one being typed: a second
/// polymorphism sitting under an allele-specific primer changes how well that
/// primer binds on some people's DNA and not others', which is a genotyping
/// assay that quietly gives the wrong answer for a subset of samples rather
/// than failing.
const ACCEPTS: &[Modifier] = &[
    Modifier::Multiplex,
    Modifier::Tails,
    Modifier::VariantMasking,
];

/// The longest template this will take in one request.
const MAX_TEMPLATE_BASES: usize = 1_000_000;

/// The layouts this designs.
const GEOMETRIES: &[&str] = &["arms-two-tube", "tetra", "kasp"];

/// Named KASP wet-lab overlays.  Absence is intentional: a geometry does not
/// identify a master-mix revision, instrument or cycling branch by itself.
const KASP_PROTOCOLS: &[&str] = DISCRIMINATING_KASP_PROTOCOLS;
const KASP_ASSAY_MODES: &[&str] = &["biallelic-genotype", "plus-minus-presence-absence"];
const KASP_PLATE_FORMATS: &[&str] = &["96", "384"];
const KASP_ROX_POLICIES: &[&str] = &["none", "low", "standard", "high", "unresolved"];

/// What a caller has to send.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DiscriminatingPairRequest {
    /// The template, in any shape the worker resolves.
    pub template: String,
    /// Whether lowercase letters in the submitted template are intentional
    /// soft masking. None means the caller did not resolve the ambiguity; the
    /// Scientific-Strict worker refuses lowercase input in that case instead of
    /// guessing from how much of the sequence happens to be lowercase.
    #[serde(default)]
    pub lowercase_masking: Option<bool>,
    /// Where the variant is, zero-based. Required — see the module note.
    #[serde(default)]
    pub at: Option<usize>,
    /// What the variant reads on each of the two versions being told apart.
    #[serde(default)]
    pub alleles: Option<Vec<String>>,
    /// Rich normalized variant input: SNV/MNV/indel/complex/presence-absence.
    #[serde(default)]
    pub variant: Option<serde_json::Value>,
    /// Caller-supplied finite VCF used only to mask nearby polymorphisms.
    #[serde(default)]
    pub nearby_variants_vcf: Option<String>,
    /// Polymerase-scoped discrimination evidence identity.
    #[serde(default)]
    pub mismatch_evidence_profile: Option<String>,
    /// Tetra electrophoresis context; resolution remains caller-declared.
    #[serde(default)]
    pub tetra_readout: Option<String>,
    #[serde(default)]
    /// Declared tetra gel percentage used for run planning.
    pub tetra_gel_percent: Option<f64>,
    #[serde(default)]
    /// Declared electrophoresis ladder identity.
    pub tetra_ladder: Option<String>,
    #[serde(default)]
    /// Declared tetra electrophoresis run context.
    pub tetra_run_context: Option<String>,
    /// How the allele-specific primers are laid out.
    ///
    /// The choice that matters is whether they share a strand: one that faces
    /// them apart can give both alleles a blocking mismatch on a transversion,
    /// and one that does not can only ever give it to one of them.
    #[serde(default)]
    pub geometry: Option<String>,
    /// Optional named KASP protocol overlay.  Only meaningful for `kasp`; it
    /// is still validated here so an unknown protocol can never reach a worker
    /// through a typo or a stale client.
    #[serde(default)]
    pub kasp_protocol: Option<String>,
    /// KASP interpretation branch. Required for KASP so genotype semantics are never inferred.
    #[serde(default)]
    pub kasp_assay_mode: Option<String>,
    /// Plate branch for the named LGC protocol overlay.
    #[serde(default)]
    pub kasp_plate_format: Option<String>,
    /// Instrument context retained for endpoint interpretation/provenance.
    #[serde(default)]
    pub kasp_instrument_model: Option<String>,
    /// ROX/reference-dye branch. `unresolved` is explicit; absence is not.
    #[serde(default)]
    pub kasp_rox_policy: Option<String>,
    /// Minimum pairwise product-size gap the intended electrophoresis workflow can resolve.
    /// Required for tetra-primer ARMS; never inferred from a generic gel assumption.
    #[serde(default)]
    pub tetra_min_band_separation_bp: Option<usize>,
    /// Bench/run observations travel with the saved run but never alter
    /// candidate ranking in the design worker.
    #[serde(default)]
    pub workflow_evidence: Option<serde_json::Value>,
    /// What to call the design.
    #[serde(default)]
    pub name: Option<String>,
    /// Which assay this is, and the numbers that assay differs by.
    #[serde(default)]
    pub assay: Option<serde_json::Value>,
    /// Which named reaction the numbers are computed for.
    #[serde(default)]
    pub polymerase: Option<String>,
    /// What the product is for, which sets the sizes and the tolerances.
    #[serde(default)]
    pub purpose: Option<String>,
    /// Individual salt or oligo concentrations, overriding the preset.
    #[serde(default)]
    pub conditions: Option<serde_json::Value>,
    /// What a primer has to satisfy.
    ///
    /// A GC clamp among these applies to the common primer only. An
    /// allele-specific primer's 3' end is the variant, and the variant is
    /// wherever it happens to be.
    #[serde(default)]
    pub constraints: Option<serde_json::Value>,
    /// Sequence these oligos must not also find.
    ///
    /// The page asked for it and the engine had nowhere to put it, so a pasted
    /// genome was dropped on the way in and the result said nothing about it —
    /// which reads exactly like a design that came back clean.
    #[serde(default)]
    pub background: Option<String>,
    /// Stretches the common primer may not overlap.
    ///
    /// The common primer only. Where the allele-specific primers sit is not a
    /// choice — their 3' end is the variant, which is wherever it is — so an
    /// exclusion covering it would be a request this assay cannot honour.
    #[serde(default)]
    pub excluded: Option<Vec<(usize, usize)>>,
}

/// A genotyping design, run by the Python worker.
#[derive(Debug, Clone, Default)]
pub struct DiscriminatingPair {
    worker: Worker,
}

impl DiscriminatingPair {
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

impl Engine for DiscriminatingPair {
    fn id(&self) -> EngineId {
        EngineId::DiscriminatingPair
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
        self.worker.call("discriminate", &parsed.to_worker())
    }
}

/// Read the wire request, or say which part of it is wrong.
fn parse(request: &serde_json::Value) -> Result<DiscriminatingPairRequest> {
    let parsed: DiscriminatingPairRequest = serde_json::from_value(request.clone())
        .map_err(|error| CoreError::InvalidRequest(error.to_string()))?;
    parsed.check()?;
    Ok(parsed)
}

impl DiscriminatingPairRequest {
    /// Whether this request could describe a genotyping assay at all.
    ///
    /// Every shared rule comes from [`super::common`], so it means the same
    /// thing here as on every other engine that carries the field.
    fn check(&self) -> Result<()> {
        let template_bases = check_template(&self.template, MAX_TEMPLATE_BASES)?;
        // Historical single-base fields remain supported, but a rich `variant`
        // object owns SNV/MNV/indel/presence-absence semantics.
        if self.variant.is_none() {
            let at = self.at.ok_or_else(|| {
                CoreError::InvalidRequest(
                    "variant position `at` is required when rich `variant` is absent".to_owned(),
                )
            })?;
            check_positions(&[at], template_bases, "variant")?;
            let alleles = self.alleles.as_ref().ok_or_else(|| {
                CoreError::InvalidRequest(
                    "exactly two alleles are required when rich `variant` is absent".to_owned(),
                )
            })?;
            if alleles.len() != 2 {
                return Err(CoreError::InvalidRequest(format!(
                    "This needs exactly two alleles and {} were given.",
                    alleles.len()
                )));
            }
            for allele in alleles {
                let base = allele.trim().to_uppercase();
                if base.len() != 1 || !matches!(base.as_str(), "A" | "C" | "G" | "T") {
                    return Err(CoreError::InvalidRequest(format!("`{allele}` is not a single A/C/G/T allele; use the rich `variant` object for MNV/indel/complex variants.")));
                }
            }
            if alleles[0].trim().eq_ignore_ascii_case(alleles[1].trim()) {
                return Err(CoreError::InvalidRequest(
                    "Both alleles are the same. There is nothing to tell apart.".to_owned(),
                ));
            }
        } else if let Some(variant) = &self.variant {
            let object = variant
                .as_object()
                .ok_or_else(|| CoreError::InvalidRequest("variant must be an object".to_owned()))?;
            let at = object
                .get("at")
                .and_then(serde_json::Value::as_u64)
                .ok_or_else(|| {
                    CoreError::InvalidRequest("variant.at must be a zero-based integer".to_owned())
                })? as usize;
            if at > template_bases {
                return Err(CoreError::InvalidRequest(
                    "variant.at lies beyond the submitted template".to_owned(),
                ));
            }
            let kind = object
                .get("type")
                .or_else(|| object.get("kind"))
                .and_then(serde_json::Value::as_str)
                .unwrap_or("");
            if ![
                "snv",
                "mnv",
                "insertion",
                "deletion",
                "complex-replacement",
                "presence-absence",
            ]
            .contains(&kind)
            {
                return Err(CoreError::InvalidRequest("variant.type must be snv, mnv, insertion, deletion, complex-replacement or presence-absence".to_owned()));
            }
            let ref_seq = object
                .get("ref")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("")
                .to_ascii_uppercase();
            let alt_seq = object
                .get("alt")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("")
                .to_ascii_uppercase();
            if !ref_seq
                .chars()
                .chain(alt_seq.chars())
                .all(|base| matches!(base, 'A' | 'C' | 'G' | 'T'))
            {
                return Err(CoreError::InvalidRequest(
                    "variant.ref/alt must contain only unambiguous A/C/G/T sequence".to_owned(),
                ));
            }
            let shape_ok = match kind {
                "snv" => ref_seq.len() == 1 && alt_seq.len() == 1 && ref_seq != alt_seq,
                "mnv" => ref_seq.len() > 1 && ref_seq.len() == alt_seq.len() && ref_seq != alt_seq,
                "insertion" => ref_seq.is_empty() && !alt_seq.is_empty(),
                "deletion" => !ref_seq.is_empty() && alt_seq.is_empty(),
                "complex-replacement" => {
                    !ref_seq.is_empty() && !alt_seq.is_empty() && ref_seq != alt_seq
                }
                "presence-absence" => !ref_seq.is_empty() && alt_seq.is_empty(),
                _ => false,
            };
            if !shape_ok {
                return Err(CoreError::InvalidRequest(format!(
                    "variant.ref/alt do not match the canonical `{kind}` shape. Presence-absence uses non-empty REF on the submitted reference and empty ALT; use insertion when the reference is the absence allele."
                )));
            }
        }
        if let Some(profile) = self.mismatch_evidence_profile.as_deref() {
            if profile != DISCRIMINATING_MISMATCH_MODEL_ID {
                return Err(CoreError::InvalidRequest(format!(
                    "`{profile}` is not the reviewed mismatch-evidence profile for this reviewed source snapshot. Expected `{DISCRIMINATING_MISMATCH_MODEL_ID}`."
                )));
            }
        }
        let variant_kind = self
            .variant
            .as_ref()
            .and_then(serde_json::Value::as_object)
            .and_then(|object| object.get("type").or_else(|| object.get("kind")))
            .and_then(serde_json::Value::as_str)
            .unwrap_or("snv");
        if let Some(geometry) = self.geometry.as_deref() {
            if !geometry.is_empty() && !GEOMETRIES.contains(&geometry) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{geometry}` is not a layout this designs. It does: {}.",
                    GEOMETRIES.join(", ")
                )));
            }
        }
        let assay_id = self
            .assay
            .as_ref()
            .and_then(|assay| assay.get("id"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default();
        let expected_geometry = match assay_id {
            "arms-pcr" => Some("arms-two-tube"),
            "tetra-primer-arms" => Some("tetra"),
            "kasp" => Some("kasp"),
            _ => None,
        };
        let geometry = if let Some(expected) = expected_geometry {
            let actual = self.geometry.as_deref().filter(|value| !value.is_empty()).ok_or_else(|| {
                CoreError::InvalidRequest(format!(
                    "`{assay_id}` requires explicit canonical geometry `{expected}`; assay identity is not inferred from omission."
                ))
            })?;
            if actual != expected {
                return Err(CoreError::InvalidRequest(format!(
                    "`{assay_id}` is fixed to geometry `{expected}`, not `{actual}`. Choose the matching module instead of changing assay topology."
                )));
            }
            actual
        } else {
            self.geometry.as_deref().unwrap_or("arms-two-tube")
        };
        if geometry == "tetra" {
            match self.tetra_min_band_separation_bp {
                Some(0) => {
                    return Err(CoreError::InvalidRequest(
                        "tetraMinBandSeparationBp must be a positive integer.".to_owned(),
                    ));
                }
                None => {
                    return Err(CoreError::InvalidRequest(
                        "Tetra-primer ARMS requires `tetraMinBandSeparationBp` from the intended electrophoresis/resolution workflow; PCRStudio does not invent a gel-resolution threshold.".to_owned(),
                    ));
                }
                Some(_) => {}
            }
        } else if self.tetra_min_band_separation_bp.is_some() {
            return Err(CoreError::InvalidRequest(
                "tetraMinBandSeparationBp is only valid with tetra-primer ARMS geometry."
                    .to_owned(),
            ));
        }
        if geometry == "kasp" {
            let mode = self.kasp_assay_mode.as_deref().ok_or_else(||
                CoreError::InvalidRequest("KASP requires an explicit `kaspAssayMode`; genotype-call semantics are not inferred.".to_owned())
            )?;
            if !KASP_ASSAY_MODES.contains(&mode) {
                return Err(CoreError::InvalidRequest(format!(
                    "`{mode}` is not a KASP assay mode. It knows: {}.",
                    KASP_ASSAY_MODES.join(", ")
                )));
            }
            if mode == "biallelic-genotype" && !matches!(variant_kind, "snv" | "mnv") {
                return Err(CoreError::InvalidRequest(format!(
                    "KASP biallelic-genotype is the current single-anchor SNV/MNV branch; `{variant_kind}` requires `plus-minus-presence-absence`."
                )));
            }
            if mode == "plus-minus-presence-absence"
                && !matches!(
                    variant_kind,
                    "insertion" | "deletion" | "complex-replacement" | "presence-absence"
                )
            {
                return Err(CoreError::InvalidRequest(format!(
                    "KASP plus-minus-presence-absence requires insertion, deletion, complex-replacement or presence-absence input, not `{variant_kind}`."
                )));
            }
        } else if self.kasp_assay_mode.is_some()
            || self.kasp_plate_format.is_some()
            || self.kasp_instrument_model.is_some()
            || self.kasp_rox_policy.is_some()
        {
            return Err(CoreError::InvalidRequest(
                "KASP-specific fields require `kasp` geometry.".to_owned(),
            ));
        }
        if let Some(protocol) = &self.kasp_protocol {
            if !KASP_PROTOCOLS.contains(&protocol.as_str()) {
                return Err(CoreError::InvalidRequest(format!(
                    "protocol {protocol} is not a KASP protocol this knows. It knows: {}.",
                    KASP_PROTOCOLS.join(", ")
                )));
            }
            if matches!(protocol.as_str(), "lgc-standard" | "lgc-kasp-tf-v5") && geometry != "kasp"
            {
                return Err(CoreError::InvalidRequest(
                    "the LGC KASP protocol overlay requires `kasp` geometry".to_owned(),
                ));
            }
            if matches!(protocol.as_str(), "lgc-standard" | "lgc-kasp-tf-v5") {
                let plate = self.kasp_plate_format.as_deref().ok_or_else(|| {
                    CoreError::InvalidRequest(
                        "The LGC KASP protocol requires an explicit `kaspPlateFormat` (96 or 384)."
                            .to_owned(),
                    )
                })?;
                if !KASP_PLATE_FORMATS.contains(&plate) {
                    return Err(CoreError::InvalidRequest(format!(
                        "`{plate}` is not a KASP plate format; use 96 or 384."
                    )));
                }
                let rox = self.kasp_rox_policy.as_deref().ok_or_else(|| CoreError::InvalidRequest(
                    "The LGC KASP protocol requires an explicit `kaspRoxPolicy`; use `unresolved` when the instrument branch is not known.".to_owned()
                ))?;
                if !KASP_ROX_POLICIES.contains(&rox) {
                    return Err(CoreError::InvalidRequest(format!(
                        "`{rox}` is not a KASP ROX policy."
                    )));
                }
                if self
                    .kasp_instrument_model
                    .as_deref()
                    .map(str::trim)
                    .unwrap_or("")
                    .is_empty()
                {
                    return Err(CoreError::InvalidRequest(
                        "The LGC KASP protocol requires `kaspInstrumentModel`; use `unresolved` when unknown so provenance remains explicit.".to_owned()
                    ));
                }
                if let Some(constraints) = self.constraints.as_ref().and_then(|v| v.as_object()) {
                    if constraints
                        .get("product_max")
                        .and_then(|v| v.as_f64())
                        .is_some_and(|v| v > 100.0)
                    {
                        return Err(CoreError::InvalidRequest(
                            "The standard LGC KASP branch is capped at approximately 100 bp and cannot use a larger `product_max`.".to_owned()
                        ));
                    }
                }
            }
        }
        if let Some(regions) = &self.excluded {
            check_excluded(regions, template_bases)?;
        }
        Ok(())
    }

    /// This request in the worker's own vocabulary.
    fn to_worker(&self) -> serde_json::Value {
        let mut payload = serde_json::Map::new();
        payload.insert("template".into(), self.template.clone().into());
        if let Some(at) = self.at {
            payload.insert("at".into(), at.into());
        }
        if let Some(alleles) = &self.alleles {
            payload.insert(
                "alleles".into(),
                alleles
                    .iter()
                    .map(|allele| allele.trim().to_uppercase())
                    .collect::<Vec<_>>()
                    .into(),
            );
        }

        let mut put = |key: &str, value: Option<serde_json::Value>| {
            if let Some(value) = value {
                payload.insert(key.to_owned(), value);
            }
        };
        put("geometry", self.geometry.clone().map(Into::into));
        put("variant", self.variant.clone());
        put(
            "nearby_variants_vcf",
            self.nearby_variants_vcf.clone().map(Into::into),
        );
        put(
            "mismatch_evidence_profile",
            self.mismatch_evidence_profile.clone().map(Into::into),
        );
        put("tetra_readout", self.tetra_readout.clone().map(Into::into));
        put("tetra_gel_percent", self.tetra_gel_percent.map(Into::into));
        put("tetra_ladder", self.tetra_ladder.clone().map(Into::into));
        put(
            "tetra_run_context",
            self.tetra_run_context.clone().map(Into::into),
        );
        put("kasp_protocol", self.kasp_protocol.clone().map(Into::into));
        put(
            "kasp_assay_mode",
            self.kasp_assay_mode.clone().map(Into::into),
        );
        put(
            "kasp_plate_format",
            self.kasp_plate_format.clone().map(Into::into),
        );
        put(
            "kasp_instrument_model",
            self.kasp_instrument_model.clone().map(Into::into),
        );
        put(
            "kasp_rox_policy",
            self.kasp_rox_policy.clone().map(Into::into),
        );
        put(
            "tetra_min_band_separation_bp",
            self.tetra_min_band_separation_bp.map(Into::into),
        );
        put("workflow_evidence", self.workflow_evidence.clone());
        put("lowercase_masking", self.lowercase_masking.map(Into::into));
        put("name", self.name.clone().map(Into::into));
        put("assay", self.assay.clone());
        put("polymerase", self.polymerase.clone().map(Into::into));
        put("purpose", self.purpose.clone().map(Into::into));
        put("conditions", self.conditions.clone());
        put("constraints", self.constraints.clone());
        put("background", self.background.clone().map(Into::into));
        put("excluded", excluded_to_worker(self.excluded.as_ref()));

        serde_json::Value::Object(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(value: serde_json::Value) -> Result<DiscriminatingPairRequest> {
        parse(&value)
    }

    fn ok() -> serde_json::Value {
        json!({ "template": "ACGTACGTACGTACGT", "at": 8, "alleles": ["C", "G"] })
    }

    #[test]
    fn a_design_without_a_variant_position_is_refused() {
        // Every other engine defaults a missing region to somewhere sensible.
        // There is nowhere sensible here — the design is anchored on one base.
        let error = request(json!({
            "template": "ACGTACGTACGTACGT",
            "alleles": ["C", "G"],
        }))
        .expect_err("no position");
        assert!(error.to_string().contains("at"), "{error}");
    }

    #[test]
    fn one_allele_is_not_a_variant() {
        let error = request(json!({ "template": "ACGTACGT", "at": 4, "alleles": ["C"] }))
            .expect_err("one allele");
        assert!(error.to_string().contains("exactly two"), "{error}");
    }

    #[test]
    fn two_identical_alleles_are_refused() {
        let error = request(json!({ "template": "ACGTACGT", "at": 4, "alleles": ["C", "c"] }))
            .expect_err("the same twice");
        assert!(
            error.to_string().contains("nothing to tell apart"),
            "{error}"
        );
    }

    #[test]
    fn an_indel_is_named_as_a_different_assay() {
        let error = request(json!({
            "template": "ACGTACGT",
            "at": 4,
            "alleles": ["C", "CG"],
        }))
        .expect_err("not a single base");
        assert!(
            error.to_string().contains("rich `variant` object"),
            "{error}"
        );
    }

    #[test]
    fn a_layout_this_does_not_design_lists_the_ones_it_does() {
        let mut body = ok();
        body["geometry"] = json!("single-tube-nested");
        let error = request(body).expect_err("not a layout");
        let message = error.to_string();
        for geometry in GEOMETRIES {
            assert!(
                message.contains(geometry),
                "{geometry} not offered: {message}"
            );
        }
    }

    #[test]
    fn the_alleles_reach_the_worker_in_upper_case() {
        // The worker compares them against the template base by base, so a
        // lower-case allele would read as a mismatch with itself.
        let mut body = ok();
        body["alleles"] = json!(["c", " g "]);
        let parsed = request(body).expect("a well-formed request");
        assert_eq!(parsed.to_worker()["alleles"], json!(["C", "G"]));
    }

    #[test]
    fn the_variant_position_reaches_the_worker_under_its_own_name() {
        let parsed = request(ok()).expect("a well-formed request");
        assert_eq!(parsed.to_worker()["at"], 8);
        // Never sent as null: the worker has its own default layout.
        assert!(parsed.to_worker().get("geometry").is_none());
    }

    #[test]
    fn an_unknown_kasp_protocol_is_refused() {
        let mut body = ok();
        body["kaspProtocol"] = json!("guess");
        let error = request(body).expect_err("unknown KASP protocol");
        assert!(error.to_string().contains("KASP protocol"), "{error}");
    }

    #[test]
    fn a_named_kasp_protocol_reaches_the_worker() {
        let mut body = ok();
        body["geometry"] = json!("kasp");
        body["kaspProtocol"] = json!("lgc-standard");
        body["kaspAssayMode"] = json!("biallelic-genotype");
        body["kaspPlateFormat"] = json!("96");
        body["kaspInstrumentModel"] = json!("unresolved");
        body["kaspRoxPolicy"] = json!("unresolved");
        let parsed = request(body).expect("named KASP protocol");
        assert_eq!(parsed.to_worker()["kasp_protocol"], "lgc-standard");
    }

    #[test]
    fn a_kasp_protocol_cannot_be_attached_to_a_gel_geometry() {
        let mut body = ok();
        body["kaspProtocol"] = json!("lgc-standard");
        let error = request(body).expect_err("protocol on ARMS");
        assert!(
            error.to_string().contains("requires `kasp` geometry"),
            "{error}"
        );
    }

    #[test]
    fn a_variant_off_the_end_of_the_template_is_refused() {
        // Where the variant is was never range-checked: a typo anchored the
        // whole design off the template and nothing said so.
        let mut body = ok();
        body["at"] = json!(99);
        let error = request(body).expect_err("past the end");
        let message = error.to_string();
        assert!(message.contains("variant"), "{message}");
        assert!(message.contains("past the end"), "{message}");
    }

    #[test]
    fn avoided_regions_are_checked_here_and_travel_as_pairs() {
        let parsed = request(json!({
            "template": "ACGTACGTACGTACGT",
            "at": 8,
            "alleles": ["C", "G"],
            "excluded": [[2, 4]],
        }))
        .expect("a well-formed request");
        assert_eq!(parsed.to_worker()["excluded"], json!([[2, 4]]));

        let error = request(json!({
            "template": "ACGTACGTACGTACGT",
            "at": 8,
            "alleles": ["C", "G"],
            "excluded": [[12, 40]],
        }))
        .expect_err("this protects nothing");
        assert!(error.to_string().contains("past the end"), "{error}");
    }

    #[test]
    fn a_genotyping_assay_is_offered_variant_masking() {
        // It masks other known variants, not the one being typed. A second
        // polymorphism under an allele-specific primer makes the assay give a
        // different answer for different people, which is worse than failing.
        assert!(ACCEPTS.contains(&Modifier::VariantMasking));
    }
}
