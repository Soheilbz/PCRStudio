//! The endpoints. Each one is a thin wrapper over the registry.

use axum::extract::{Path, State};
use axum::Json;
use pcr_core::{CoreError, EngineDescription, EngineId, Goal, Modifier, Profile, Registry};
use serde::Serialize;

use crate::error::ApiError;
use crate::ModuleState;

/// Identity of the running build, for the About page and for bug reports.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ServiceInfo {
    /// Product name.
    pub name: &'static str,
    /// Semantic version of this build.
    pub version: &'static str,
}

/// Liveness. Deliberately does no work beyond proving the process answers.
pub async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({ "status": "ok" }))
}

/// What this build is.
pub async fn info() -> Json<ServiceInfo> {
    Json(ServiceInfo {
        name: "PCRStudio",
        version: env!("CARGO_PKG_VERSION"),
    })
}

/// Every assay, ordered by id.
pub async fn list_modules(State(state): State<ModuleState>) -> Json<Vec<Profile>> {
    Json(state.registry.profiles())
}

// Canonical application rules are re-exported here only for existing server
// bench/tests. The implementation authority lives in `pcr-application`.
pub(crate) use pcr_application::{assay_payload, ensure_release_executable, validate_requirements};

/// One assay.
pub async fn get_module(
    State(state): State<ModuleState>,
    Path(id): Path<String>,
) -> Result<Json<Profile>, ApiError> {
    Ok(Json(state.registry.profile(&id)?.clone()))
}

/// The engines this build compiled in, and what each will be combined with.
///
/// Published because the compatibility matrix decides which assays can exist,
/// and a rule that governs the catalogue should be inspectable rather than
/// buried in a source file.
pub async fn list_engines(State(state): State<ModuleState>) -> Json<Vec<EngineDescription>> {
    Json(
        EngineId::all()
            .iter()
            .filter_map(|id| state.registry.engine_description(*id))
            .collect(),
    )
}

/// The goals assays are grouped under, in presentation order.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GoalDescription {
    /// The goal itself.
    pub id: Goal,
    /// Human-readable label.
    pub label: &'static str,
    /// What a design under this goal is checked against.
    pub rule: &'static str,
    /// How many assays sit under it.
    pub count: usize,
}

/// The sidebar's groups, in the order they should appear.
pub async fn list_goals(State(state): State<ModuleState>) -> Json<Vec<GoalDescription>> {
    Json(
        Goal::all()
            .iter()
            .map(|goal| GoalDescription {
                id: *goal,
                label: goal.label(),
                rule: goal.rule(),
                count: state.registry.profiles_for(*goal).len(),
            })
            .collect(),
    )
}

/// One entry of a closed vocabulary, with the wording the interface shows.
///
/// The label belongs to the core because the core is where the vocabulary is
/// defined; restating it in TypeScript would be the same fact written twice.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Term<T> {
    /// The value as it appears on the wire.
    pub id: T,
    /// Human-readable label.
    pub label: &'static str,
}

/// The modifiers an assay can carry, in declaration order.
pub async fn list_modifiers() -> Json<Vec<Term<Modifier>>> {
    Json(
        Modifier::all()
            .iter()
            .map(|modifier| Term {
                id: *modifier,
                label: modifier.label(),
            })
            .collect(),
    )
}

/// One status, with what it claims and what would change it.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct StatusDescription {
    /// The value as it appears on the wire.
    pub id: pcr_core::Status,
    /// The word on the badge.
    pub label: &'static str,
    /// What that word claims, in the words somebody at a bench would use.
    pub means: &'static str,
    /// What it would take to move past it. `None` for the last one.
    pub promotion: Option<&'static str>,
}

/// What each status means, and what promotion from it takes.
///
/// Published for the same reason the compatibility matrix is: a badge reading
/// "Experimental" with nothing behind it is not a claim anybody can act on, and
/// the people this is for are deciding whether to order oligos from it. All
/// twenty-one assays carry that word, so the sentence behind it is the most
/// consequential one in the catalogue.
pub async fn list_statuses() -> Json<Vec<StatusDescription>> {
    Json(
        pcr_core::Status::all()
            .iter()
            .map(|status| StatusDescription {
                id: *status,
                label: status.label(),
                means: status.means(),
                promotion: status.promotion(),
            })
            .collect(),
    )
}

/// How far an isothermal enzyme's hold may sit from the one an assay designs at.
///
/// Ten degrees. Wide enough for a variant of the same enzyme — a warm-start
/// *Bst* or a *Bsm* running at 60 rather than 65 — and narrow enough to keep
/// the two isothermal methods in this catalogue apart, which sit 26 degrees
/// away from each other. Measured against those two rather than chosen: there
/// is nothing between 39 and 65 for it to land wrongly on.
///
/// It is a floor on what can be told apart rather than a claim about any
/// enzyme's tolerance. An enzyme whose own hold is recorded is judged by that.
const HOLD_TOLERANCE: f64 = 10.0;

/// Why one enzyme cannot run one assay, or `None` if it can.
///
/// One function because there are two places that must agree about it: the
/// presets endpoint, which decides what to offer, and the design endpoint,
/// which decides what to accept. They did not agree — the offer was narrowed
/// and the run was not, so LAMP listed only *Bst* and still designed a set
/// with a proofreading polymerase, reporting melting temperatures computed in
/// a buffer that reaction never sees.
///
/// `held_at` is the hold this assay's numbers were computed at, for an
/// isothermal assay, and `None` for one that cycles. See `HOLD_TOLERANCE`.
fn why_not(
    profile: &pcr_core::Profile,
    entry: &serde_json::Value,
    held_at: Option<f64>,
) -> Option<String> {
    for need in profile.enzyme_needs() {
        let (activity, wanted) = need.wants();
        let has = entry
            .pointer(&format!("/does/{activity}"))
            .and_then(serde_json::Value::as_bool);
        // Missing capability metadata is not proof that the enzyme has the
        // activity. Refuse it rather than silently offering an unclassified
        // preset; the preset catalogue is the authority for these flags.
        if has != Some(wanted) {
            return Some(need.why().to_owned());
        }
    }

    // Strand displacement is necessary for an isothermal reaction and not
    // sufficient to tell two of them apart: LAMP holds at 65 and RPA at 39,
    // both displace strands, and neither runs the other's reaction — every
    // melting window in the design is computed at the hold, and twenty-six
    // degrees out is not a tuning problem.
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

/// The hold an assay's own numbers were computed at, if it does not cycle.
fn held_at(presets: &serde_json::Value, named: Option<&str>) -> Option<f64> {
    presets
        .get("polymerases")
        .and_then(serde_json::Value::as_array)?
        .iter()
        .find(|entry| entry.get("id").and_then(serde_json::Value::as_str) == named)?
        .pointer("/cycling/isothermal_c")
        .and_then(serde_json::Value::as_f64)
}

/// The named settings this assay's engine offers, for a form to render.
///
/// Empty rather than missing when the engine has none, so the interface does
/// not have to tell "no presets" apart from "this endpoint failed".
pub async fn get_presets(
    State(state): State<ModuleState>,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, ApiError> {
    let profile = state.registry.profile(&id)?;
    let engine = state.registry.engine_for(&id)?;

    // Asking an engine for its presets spawns the worker, so the ask runs off
    // the async runtime's threads like every other worker call. The narrowing
    // below is pure JSON work and stays on the cheap side of the boundary.
    let engine_presets = {
        let gate = state.gate.clone();
        let profile_id = id.clone();
        gate.run(move || {
            engine.presets().map_err(move |error| {
                tracing::error!(assay = %profile_id, error = %error, "presets failed");
                error
            })
        })
        .await?
        .unwrap_or_else(|| serde_json::json!({}))
    };
    let mut presets = engine_presets;

    /*
     * The engine's answer, narrowed to this assay.
     *
     * This route is addressed by assay and was answering by engine, so all
     * eight modules on flanking-pair received the same eight enzymes and the
     * same fifteen numbers at the same defaults — including the ones whose
     * profile pins an enzyme and rewrites half the numbers. A form built from
     * that shows a person their assay's questions with another assay's
     * answers already in the boxes.
     *
     * Narrowing rather than replacing: the engine still decides what exists,
     * and the assay decides which of it applies and what it starts at. An
     * assay that names no purposes offers all of them, which is what an empty
     * list already means everywhere else in a profile.
     */
    if let Some(object) = presets.as_object_mut() {
        let defaults = &profile.defaults;

        if !defaults.purposes.is_empty() {
            if let Some(offered) = object.get_mut("purposes").and_then(|v| v.as_array_mut()) {
                offered.retain(|entry| {
                    entry
                        .get("id")
                        .and_then(serde_json::Value::as_str)
                        .is_some_and(|id| defaults.purposes.iter().any(|want| want == id))
                });
            }
        }

        /*
         * The same narrowing for the enzymes, and by the same rule.
         *
         * Every module offered every enzyme, so a LAMP design could be run
         * with a proofreading polymerase — which produces nothing at all,
         * because LAMP never heats the template apart and that enzyme cannot
         * open it. Three of these were already refused *after* somebody chose,
         * inside the worker, which is the right check in the wrong place: a
         * choice that cannot work should not be on the list.
         *
         * Derived rather than listed. The assay says what activity it needs
         * and the enzyme says what it does, so a tenth enzyme is offered
         * wherever it fits without twenty-one lists being edited. An assay
         * that says nothing offers everything, which is the honest default —
         * narrowing is a claim about that assay's chemistry, and a claim
         * nobody has researched should not be put in front of a bench.
         */
        // Read before the list is narrowed: the assay's own enzyme is what
        // says which temperature its windows were computed at, and narrowing
        // could remove it from the list this reads it out of.
        let hold = held_at(
            &serde_json::Value::Object(object.clone()),
            defaults.polymerase.as_deref(),
        );
        if let Some(offered) = object.get_mut("polymerases").and_then(|v| v.as_array_mut()) {
            offered.retain(|entry| {
                if why_not(profile, entry, hold).is_some() {
                    return false;
                }
                let Some(id) = entry.get("id").and_then(serde_json::Value::as_str) else {
                    return false;
                };
                // Capability-equivalent is not assay-equivalent. When a
                // profile names its chemistry, the release UI offers only that
                // identity plus explicitly reviewed alternatives. Development
                // callers can still exercise another preset directly, where
                // the Python Scientific-Strict policy remains authoritative.
                match defaults.polymerase.as_deref() {
                    Some(expected) => {
                        id == expected
                            || defaults
                                .allowed_polymerases
                                .iter()
                                .any(|allowed| allowed == id)
                    }
                    None => true,
                }
            });
        }

        // What this assay starts each box at, beside what the engine allows.
        // Sent as its own key rather than written over `fields`, so a form can
        // show both — the assay's figure in the box, and the engine's own as
        // the placeholder behind it.
        object.insert(
            "assay".to_owned(),
            serde_json::json!({
                "id": profile.id,
                "name": profile.name,
                "polymerase": defaults.polymerase,
                "allowedPolymerases": defaults.allowed_polymerases,
                "defaultPurpose": defaults.default_purpose,
                "constraints": defaults.constraints,
                "cycling": defaults.cycling,
                "requires": profile.requires,
                // What was ruled out and why, so a shortened list is a
                // statement rather than an absence. A person who came here
                // knowing which enzyme they use needs to be told it is not
                // offered and told the reason, not left to wonder.
                "enzyme": profile
                    .enzyme
                    .iter()
                    .map(|need| serde_json::json!({ "need": need, "why": need.why() }))
                    .collect::<Vec<_>>(),
            }),
        );
    }

    Ok(Json(presets))
}

/// Every named reaction any assay in this build offers.
///
/// The settings page needs this, and no single module can answer it: presets
/// are a property of an engine, and asking one module's engine would make that
/// module quietly canonical for the whole catalogue. So it is a union, and it
/// stays right the day two engines stop agreeing.
///
/// Computed once. Each engine answers by spawning the worker, and eleven
/// subprocesses is a second of somebody's time to render a dropdown — but the
/// catalogue is compiled into the worker and cannot change while this process
/// runs, so the first caller pays and nobody else does.
pub async fn all_presets(
    State(state): State<ModuleState>,
) -> Result<Json<serde_json::Value>, ApiError> {
    // The first build of the catalogue spawns eleven interpreters and takes
    // seconds. That work belongs on the blocking pool with everything else
    // that forks a worker -- a request arriving before the startup warmer has
    // finished must not park an executor thread against the init latch.
    let registry = state.registry.clone();
    Ok(Json(
        state.gate.run(move || Ok(catalogue(&registry))).await?,
    ))
}

/// The catalogue itself, so it can also be warmed at startup.
///
/// Measured before it was: the first caller waited 7.5 seconds while eleven
/// interpreters started, and every caller after that waited 70 milliseconds.
/// Warming it at boot moves that cost to a moment when nobody is waiting.
#[must_use]
pub fn catalogue(registry: &Registry) -> serde_json::Value {
    static CATALOGUE: std::sync::OnceLock<serde_json::Value> = std::sync::OnceLock::new();

    /*
     * `get_or_init` and nothing before it.
     *
     * The first version checked `get()`, found nothing, computed the catalogue,
     * and only then called `get_or_init` — so a request arriving while the
     * startup warmer was still running did the entire eleven-subprocess build a
     * second time and threw its answer away. Measured: 7.5 seconds lazy, and
     * 14 seconds with a warmer that was supposed to make it faster.
     *
     * `get_or_init` blocks the second caller until the first finishes and then
     * hands over the same value, which is the behaviour the warmer was written
     * to rely on.
     */
    CATALOGUE
        .get_or_init(|| {
            let mut polymerases: Vec<serde_json::Value> = Vec::new();
            let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();

            for profile in registry.profiles() {
                // An engine that cannot answer is skipped rather than failing
                // the request: one broken engine should not empty the list.
                let Ok(engine) = registry.engine_for(&profile.id) else {
                    continue;
                };
                let Ok(Some(presets)) = engine.presets() else {
                    continue;
                };
                let Some(offered) = presets.get("polymerases").and_then(|v| v.as_array()) else {
                    continue;
                };

                for entry in offered {
                    let Some(id) = entry.get("id").and_then(|v| v.as_str()) else {
                        continue;
                    };
                    if seen.insert(id.to_owned()) {
                        polymerases.push(entry.clone());
                    }
                }
            }

            serde_json::json!({ "polymerases": polymerases })
        })
        .clone()
}

/// Run an assay against a request whose shape its engine defines.
///
/// The assay travels with the request. Several assays share one engine, and
/// looking the engine up by assay id and then dropping the id is how Colony
/// PCR came to behave exactly like Standard PCR: the search could not tell
/// which of the two it was running, so it ran the same one twice under two
/// names.
/// Run a design for one assay, whoever is asking and wherever it will be kept.
///
/// The only place an engine is called. Both callers — the public endpoint below
/// and the save-into-a-project handler in `projects.rs` — go through here, and
/// that is the point of it existing rather than each doing the same three steps.
///
/// They did not, and the difference was invisible from either file. Looking an
/// engine up by assay id and then handing it a request with no `assay` in it
/// gives a design with none of that assay's parameters — the same defect the
/// warning below was written about, on the only path a person actually uses.
/// Measured on qPCR-probe against TP53: through this preparation, the qPCR
/// buffer and a 154 bp product; without it, Taq, no assay id, and a 359 bp
/// product that a two-step reaction will not finish.
///
/// # Errors
///
/// [`CoreError::UnknownProfile`] for an assay that is not registered, and
/// whatever the engine says about a request it cannot answer.
pub fn design_for(
    registry: &Registry,
    id: &str,
    request: serde_json::Value,
) -> Result<serde_json::Value, CoreError> {
    pcr_application::design_for(registry, id, request)
}

/// Run a design and hand it straight back, without keeping it.
///
/// The try-before-you-sign-up path. Everything it does happens in
/// [`design_for`], which is also what the save-into-a-project handler calls.
///
/// # Errors
///
/// Whatever [`design_for`] says about an assay or a request it cannot answer.
pub async fn run_design(
    State(state): State<ModuleState>,
    Path(id): Path<String>,
    Json(request): Json<serde_json::Value>,
) -> Result<Json<serde_json::Value>, ApiError> {
    // A design runs for seconds inside a subprocess. The whole of `design_for`
    // runs on the blocking pool under a gate permit: off the async runtime's
    // threads, and one of at most N concurrent searches no matter how many
    // requests are in flight.
    let weight = pcr_contracts::resource_weight_for_module(&id).unwrap_or(1) as usize;
    let inner = state.clone();
    let answer = state
        .gate
        .run_weighted(weight, move || design_for(&inner.registry, &id, request))
        .await?;
    Ok(Json(answer))
}

#[cfg(test)]
mod tests {
    use super::{assay_payload, ensure_release_executable};

    #[test]
    fn worker_assay_payload_carries_modifiers_and_enzyme_contract() {
        let registry = pcr_core::default_registry().expect("the registry builds");
        let profile = registry
            .profile("qpcr-probe")
            .expect("the probe assay exists");
        let payload = assay_payload(profile);

        assert_eq!(payload["id"], "qpcr-probe");
        assert_eq!(
            payload["modifiers"],
            serde_json::json!(["reverse-transcription", "variant-masking"])
        );
        assert!(payload["enzyme"]
            .as_array()
            .is_some_and(|needs| { needs.iter().any(|need| need == "five-prime-exonuclease") }));
    }

    #[test]
    fn worker_assay_payload_carries_profile_requirements() {
        let registry = pcr_core::default_registry().expect("the registry builds");
        let profile = registry
            .profile("species-specific-pcr")
            .expect("the species-specific assay exists");

        assert_eq!(
            assay_payload(profile)["requires"],
            serde_json::json!(["background", "inclusivity"])
        );
    }
    #[test]
    fn public_registry_has_no_release_routable_planned_module() {
        let registry = pcr_core::default_registry().expect("the registry builds");
        for profile in registry.profiles() {
            if profile.status == pcr_core::taxonomy::Status::Planned {
                assert!(
                    ensure_release_executable(&profile).is_err(),
                    "planned profiles must fail closed"
                );
            }
        }
    }

    #[test]
    fn worker_assay_payload_preserves_engine_and_status() {
        let registry = pcr_core::default_registry().expect("the registry builds");
        let profile = registry
            .profile("standard-pcr")
            .expect("standard PCR exists");
        let payload = assay_payload(profile);
        assert_eq!(payload["engine"], "flanking-pair");
        assert_eq!(payload["status"], "experimental");
        assert_eq!(
            payload["profileAuthority"]["source"],
            "pcr-core:profiles.toml"
        );
        assert_eq!(payload["profileAuthority"]["profileId"], "standard-pcr");
        assert_eq!(
            payload["profileAuthority"]["transport"],
            "server-injected-canonical-profile"
        );
    }
}
