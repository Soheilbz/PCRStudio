//! Canonical application-layer design preparation.
//!
//! Every scientific execution path must pass through [`design_for`].  The
//! caller supplies only a module id and request payload; the application layer
//! injects the canonical assay profile and execution contract before the
//! engine validates or executes anything.

use pcr_core::{CoreError, Modifier, Profile, Registry, Status};

/// How far an isothermal enzyme's hold may sit from the assay's canonical hold.
const HOLD_TOLERANCE: f64 = 10.0;

/// Serialize the executable portion of one canonical assay profile.
#[must_use]
pub fn assay_payload(profile: &Profile) -> serde_json::Value {
    serde_json::json!({
        "id": profile.id,
        "name": profile.name,
        "engine": profile.engine,
        "status": profile.status,
        "profileAuthority": {
            "source": "pcr-core:profiles.toml",
            "profileId": profile.id,
            "transport": "server-injected-canonical-profile",
        },
        "defaults": profile.defaults,
        "modifiers": profile.modifiers,
        "requires": profile.requires,
        "enzyme": profile
            .enzyme_needs()
            .iter()
            .map(|need| serde_json::json!(need))
            .collect::<Vec<_>>(),
    })
}

/// Refuse catalogue-only profiles before any engine or worker is invoked.
pub fn ensure_release_executable(profile: &Profile) -> Result<(), CoreError> {
    if profile.status == Status::Planned {
        return Err(CoreError::InvalidRequest(format!(
            "{} is Planned and has no release-executable Generation-1 branch. Its catalogue entry is reference metadata only.",
            profile.name
        )));
    }
    Ok(())
}

/// Enforce all canonical assay requirements against the wire request.
pub fn validate_requirements(
    profile: &Profile,
    object: &serde_json::Map<String, serde_json::Value>,
) -> Result<(), CoreError> {
    for requirement in &profile.requires {
        let field = requirement.field();
        let given = object
            .get(field)
            .and_then(serde_json::Value::as_str)
            .is_some_and(|value| !value.trim().is_empty());
        if !given {
            return Err(CoreError::InvalidRequest(format!(
                "{} needs a {field}. {}",
                profile.name,
                requirement.why()
            )));
        }
    }

    let missing = pcr_contracts::missing_required_wire_context(&profile.id, object);
    if !missing.is_empty() {
        return Err(CoreError::InvalidRequest(format!(
            "{} is missing required module context: {}. These fields come from the canonical generated module contract.",
            profile.name,
            missing.join(", ")
        )));
    }
    Ok(())
}

/// Explain why a named enzyme is incompatible with an assay.
#[must_use]
pub fn enzyme_incompatibility(
    profile: &Profile,
    entry: &serde_json::Value,
    held_at: Option<f64>,
) -> Option<String> {
    for need in profile.enzyme_needs() {
        let (activity, wanted) = need.wants();
        let has = entry
            .pointer(&format!("/does/{activity}"))
            .and_then(serde_json::Value::as_bool);
        if has != Some(wanted) {
            return Some(need.why().to_owned());
        }
    }

    let wanted = held_at?;
    let hold = entry
        .pointer("/cycling/isothermal_c")
        .and_then(serde_json::Value::as_f64)?;
    if (hold - wanted).abs() <= HOLD_TOLERANCE {
        return None;
    }
    Some(format!(
        "This reaction is held at {wanted:.0} °C and that enzyme works at {hold:.0}. \
         Every melting temperature in this design was computed at {wanted:.0}, so it \
         is not a matter of adjusting the hold."
    ))
}

/// Return the canonical isothermal hold for a named preset, if any.
#[must_use]
pub fn preset_hold(presets: &serde_json::Value, named: Option<&str>) -> Option<f64> {
    presets
        .get("polymerases")
        .and_then(serde_json::Value::as_array)?
        .iter()
        .find(|entry| entry.get("id").and_then(serde_json::Value::as_str) == named)?
        .pointer("/cycling/isothermal_c")
        .and_then(serde_json::Value::as_f64)
}

/// Run one canonical assay design independent of transport or persistence.
///
/// # Errors
///
/// Returns the registry/validation/scientific error raised by the selected
/// module or engine.  Caller-owned assay/execution metadata is rejected or
/// overwritten only where the application contract explicitly owns it.
pub fn design_for(
    registry: &Registry,
    id: &str,
    mut request: serde_json::Value,
) -> Result<serde_json::Value, CoreError> {
    let profile = registry.profile(id)?.clone();
    ensure_release_executable(&profile)?;
    let engine = registry.engine_for(id)?;

    let Some(object) = request.as_object_mut() else {
        return Err(CoreError::InvalidRequest("a request is an object".into()));
    };
    if object.contains_key("assay") {
        return Err(CoreError::InvalidRequest(
            "`assay` is set from the address this request was sent to, not from the body.".into(),
        ));
    }
    if object.contains_key("executionContext") {
        return Err(CoreError::InvalidRequest(
            "`executionContext` is application-owned and must not be supplied by the caller."
                .into(),
        ));
    }

    let supports = |modifier: Modifier| profile.modifiers.contains(&modifier);
    let supplied = |field: &str| {
        object.get(field).is_some_and(|value| match value {
            serde_json::Value::Null => false,
            serde_json::Value::Bool(value) => *value,
            serde_json::Value::Array(values) => !values.is_empty(),
            serde_json::Value::Object(values) => !values.is_empty(),
            serde_json::Value::String(value) => !value.trim().is_empty(),
            serde_json::Value::Number(_) => true,
        })
    };
    for (field, modifier, label) in [
        ("tails", Modifier::Tails, "restriction tails"),
        (
            "fromRna",
            Modifier::ReverseTranscription,
            "reverse transcription",
        ),
        ("variants", Modifier::VariantMasking, "variant masking"),
    ] {
        if supplied(field) && !supports(modifier) {
            return Err(CoreError::InvalidRequest(format!(
                "{} does not support {label}; remove `{field}` from the request.",
                profile.name
            )));
        }
    }
    if supplied("vectorPrimer") && profile.id != "colony-pcr" {
        return Err(CoreError::InvalidRequest(format!(
            "{} does not support a vector primer; this control is only valid for Colony PCR.",
            profile.name
        )));
    }

    validate_requirements(&profile, object)?;

    if let Some(named) = object.get("polymerase").and_then(serde_json::Value::as_str) {
        let catalogue = engine.presets()?.unwrap_or_else(|| serde_json::json!({}));
        let hold = preset_hold(&catalogue, profile.defaults.polymerase.as_deref());
        let entry = catalogue
            .get("polymerases")
            .and_then(serde_json::Value::as_array)
            .and_then(|all| {
                all.iter()
                    .find(|one| one.get("id").and_then(serde_json::Value::as_str) == Some(named))
            });
        if let Some(entry) = entry {
            if let Some(why) = enzyme_incompatibility(&profile, entry, hold) {
                let name = entry
                    .get("name")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or(named);
                return Err(CoreError::InvalidRequest(format!(
                    "{name} cannot run {}. {why}",
                    profile.name,
                )));
            }
        }
    }

    object.insert("assay".to_owned(), assay_payload(&profile));
    engine.validate(&request)?;
    engine.design(request)
}
