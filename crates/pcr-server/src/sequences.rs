//! Getting a sequence in, when somebody has an accession rather than bases.
//!
//! Two endpoints, neither of which belongs to a particular engine: fetching a
//! record from NCBI, and collapsing an alignment into a consensus.
//!
//! The rate limit lives here rather than in the worker, and that is the whole
//! reason this file exists. NCBI allows three requests a second from an
//! address, ten with an API key, and on a public service that is a *shared*
//! budget — one visitor's impatience is everybody's block. The worker cannot
//! enforce it because every call is a new process with no memory of the last
//! one; this server is long-running, so it can.

use std::collections::HashSet;
use std::sync::Arc;
use std::time::Duration;

use axum::extract::State;
use axum::routing::post;
use axum::{Json, Router};
use pcr_core::{CoreError, Worker};
use pcr_storage::FoundationStorage;
use serde::{Deserialize, Serialize};

use crate::error::ApiError;
use crate::gate::Gate;
use crate::http_routes;

/// The largest FASTA this will hand to the worker.
///
/// The body limit already caps a request at 32 MB, but that is a cap on
/// whatever JSON arrives; an alignment over even two megabases runs for many
/// minutes, which is longer than any caller is served by waiting. Sized for a
/// large gene family with room to spare -- and named so the reason travels
/// with the number.
const MAX_FASTA_CHARS: usize = 4 * 1024 * 1024;

/// The most accessions one lookup may name.
///
/// Keep this equal to the worker's ceiling. Rejecting the request here avoids
/// spending a rate-limit slot and spawning a worker only to have the worker
/// refuse the same input later.
const MAX_ACCESSIONS: usize = 50;

fn accession_tokens(raw: &str) -> Vec<&str> {
    raw.split(|c: char| c.is_whitespace() || c == ',' || c == ';')
        .filter(|entry| !entry.trim().is_empty())
        .map(str::trim)
        .collect()
}

fn validate_accession_request(raw: &str) -> Result<usize, CoreError> {
    let tokens = accession_tokens(raw);
    if tokens.is_empty() {
        return Err(CoreError::InvalidRequest(
            "At least one nucleotide accession is required.".to_owned(),
        ));
    }
    if tokens.len() > MAX_ACCESSIONS {
        return Err(CoreError::InvalidRequest(format!(
            "That is {} accessions in one lookup; the most this will \
             fetch at once is {MAX_ACCESSIONS}. Ask for the rest in a second \
             request.",
            tokens.len()
        )));
    }

    let mut seen = HashSet::with_capacity(tokens.len());
    for token in &tokens {
        if !seen.insert(token.to_ascii_uppercase()) {
            return Err(CoreError::InvalidRequest(format!(
                "The accession `{token}` was supplied more than once. Remove \
                 duplicates before requesting a lookup."
            )));
        }
    }
    Ok(tokens.len())
}

fn refuse_oversize_fasta(field: &str) -> CoreError {
    CoreError::InvalidRequest(format!(
        "That {field} is larger than this endpoint will align or collapse. \
         Split it into smaller families and ask again."
    ))
}

/// The gap NCBI's policy implies between one request and the next.
///
/// Three a second without a key, ten with one. Rounded up rather than down:
/// being blocked costs everybody far more than a hundred milliseconds does.
fn minimum_gap(has_api_key: bool) -> Duration {
    if has_api_key {
        Duration::from_millis(110)
    } else {
        Duration::from_millis(360)
    }
}

/// Maximum time an HTTP request may wait behind already-reserved NCBI calls.
///
/// A bounded shared horizon prevents a burst (or distributed abuse) from
/// reserving minutes of future NCBI capacity. Requests beyond this horizon are
/// refused without extending it and can retry after the caller rate window.
const MAX_NCBI_RESERVATION_WAIT: Duration = Duration::from_secs(5);

const NCBI_EMAIL_REQUIRED_REASON: &str =
    "Looking a sequence up by accession needs a contact address for NCBI. Set PCR_NCBI_EMAIL on the server.";

/// What the sequence endpoints need.
#[derive(Clone)]
pub struct SequenceState {
    worker: Worker,
    /// Shared PostgreSQL-backed reservation authority for NCBI's service quota.
    storage: FoundationStorage,
    /// The address NCBI's policy asks every request to carry.
    email: String,
    /// Optional NCBI key. Presence, not an empty-string sentinel, determines
    /// whether authenticated NCBI quota may be reserved. It crosses only the
    /// dedicated fetch IPC request and is never inherited through the generic
    /// scientific worker environment.
    api_key: Option<String>,
    /// The process's one ceiling on concurrent workers.
    gate: Arc<Gate>,
}

fn fetch_unavailable_reason(email: &str) -> Option<&'static str> {
    email
        .trim()
        .is_empty()
        .then_some(NCBI_EMAIL_REQUIRED_REASON)
}

impl SequenceState {
    fn has_api_key(&self) -> bool {
        self.api_key.is_some()
    }
}

/// Accessions to look up.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FetchRequest {
    /// One accession, or several separated by whitespace, commas or semicolons.
    pub accessions: String,
}

/// Sequences to collapse into one.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConsensusRequest {
    /// The aligned sequences, as FASTA.
    pub fasta: String,
}

/// Sequences to align.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AlignRequest {
    /// The sequences, as FASTA. Any lengths — that is the point.
    pub fasta: String,
}

/// Whether this build can reach NCBI at all, so the interface can say so
/// before somebody types an accession into a box that will refuse it.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FetchAvailability {
    /// True when a contact address is configured.
    pub available: bool,
    /// Why not, when it is not.
    pub reason: &'static str,
}

async fn availability(State(state): State<SequenceState>) -> Json<FetchAvailability> {
    let reason = fetch_unavailable_reason(&state.email);
    Json(FetchAvailability {
        available: reason.is_none(),
        reason: reason.unwrap_or(""),
    })
}

/// Run one worker command under the shared gate, off the async runtime's
/// threads.
async fn ask_worker(
    state: &SequenceState,
    command: &'static str,
    request: serde_json::Value,
) -> Result<serde_json::Value, ApiError> {
    Ok(state
        .gate
        .run({
            let worker = state.worker.clone();
            move || worker.call(command, &request)
        })
        .await?)
}

async fn fetch(
    State(state): State<SequenceState>,
    Json(body): Json<FetchRequest>,
) -> Result<Json<serde_json::Value>, ApiError> {
    validate_accession_request(&body.accessions)?;
    if let Some(reason) = fetch_unavailable_reason(&state.email) {
        return Err(CoreError::InvalidRequest(reason.to_owned()).into());
    }

    // Reserve before the request goes out, not after it comes back. PostgreSQL
    // makes this one service-wide budget across every API replica.
    let wait = state
        .storage
        .reserve_external_service_slot(
            "ncbi-efetch",
            minimum_gap(state.has_api_key()),
            MAX_NCBI_RESERVATION_WAIT,
        )
        .await
        .map_err(|error| {
            tracing::error!(%error, "shared NCBI throttle reservation failed");
            ApiError(CoreError::WorkerBusy(
                "shared NCBI throttle is temporarily unavailable".to_owned(),
            ))
        })?;
    if !wait.is_zero() {
        tokio::time::sleep(wait).await;
    }

    let request = serde_json::json!({
        "accessions": body.accessions,
        "email": state.email,
        "apiKey": state.api_key.as_deref().unwrap_or(""),
    });

    // The worker blocks on a network call, so it does not belong on the async
    // runtime's threads.
    let answer = ask_worker(&state, "fetch", request).await?;
    Ok(Json(answer))
}

async fn consensus(
    State(state): State<SequenceState>,
    Json(body): Json<ConsensusRequest>,
) -> Result<Json<serde_json::Value>, ApiError> {
    if body.fasta.len() > MAX_FASTA_CHARS {
        return Err(refuse_oversize_fasta("alignment").into());
    }
    let request = serde_json::json!({ "fasta": body.fasta });
    let answer = ask_worker(&state, "consensus", request).await?;
    Ok(Json(answer))
}

/// Which aligners the current host can use, so a form knows what to offer before
/// somebody pastes ten sequences and presses a button that cannot work.
async fn aligners(State(state): State<SequenceState>) -> Result<Json<serde_json::Value>, ApiError> {
    let answer = ask_worker(&state, "aligners", serde_json::json!({})).await?;
    Ok(Json(answer))
}

/// Align sequences with whatever standard aligner is installed.
///
/// This can take real time on a large family, so it runs off the async
/// runtime's threads like every other blocking call here.
async fn align(
    State(state): State<SequenceState>,
    Json(body): Json<AlignRequest>,
) -> Result<Json<serde_json::Value>, ApiError> {
    if body.fasta.len() > MAX_FASTA_CHARS {
        return Err(refuse_oversize_fasta("set of sequences").into());
    }
    let request = serde_json::json!({ "fasta": body.fasta });
    let answer = ask_worker(&state, "align", request).await?;
    Ok(Json(answer))
}

/// The sequence endpoints, ready to nest.
pub fn routes(storage: FoundationStorage, email: String, api_key: Option<String>) -> Router {
    let state = SequenceState {
        worker: pcr_application::scientific::worker_from_env(),
        storage,
        email: email.trim().to_owned(),
        api_key: api_key.and_then(|value| {
            let value = value.trim().to_owned();
            (!value.is_empty()).then_some(value)
        }),
        gate: Arc::new(Gate::shared()),
    };

    Router::new()
        .route(http_routes::SEQUENCE_FETCH, post(fetch).get(availability))
        .route(http_routes::SEQUENCE_CONSENSUS, post(consensus))
        .route(http_routes::SEQUENCE_ALIGN, post(align).get(aligners))
        .with_state(state)
}

#[cfg(test)]
mod tests {
    use super::{
        accession_tokens, fetch_unavailable_reason, validate_accession_request, MAX_ACCESSIONS,
        NCBI_EMAIL_REQUIRED_REASON,
    };

    #[test]
    fn accession_tokens_use_the_same_separators_as_the_worker() {
        assert_eq!(
            accession_tokens("NM_000546.6, NC_000913.3;AB123456"),
            vec!["NM_000546.6", "NC_000913.3", "AB123456"]
        );
    }

    #[test]
    fn accession_validation_boundary_matches_the_worker_ceiling() {
        let at_limit = (0..MAX_ACCESSIONS)
            .map(|index| format!("AB{index:06}"))
            .collect::<Vec<_>>()
            .join(" ");
        let over_limit = format!("{at_limit} AB999999");

        assert_eq!(validate_accession_request(&at_limit), Ok(MAX_ACCESSIONS));
        assert!(validate_accession_request(&over_limit).is_err());
    }

    #[test]
    fn ncbi_availability_and_fetch_share_one_contact_policy() {
        assert_eq!(
            fetch_unavailable_reason("  \n\t"),
            Some(NCBI_EMAIL_REQUIRED_REASON)
        );
        assert_eq!(fetch_unavailable_reason("researcher@example.org"), None);
    }

    #[test]
    fn empty_accession_request_is_rejected_before_rate_limiting() {
        assert!(validate_accession_request(" ; , \n\t").is_err());
    }

    #[test]
    fn duplicate_accessions_are_rejected_case_insensitively() {
        let error = validate_accession_request("NM_000546.6 nm_000546.6")
            .expect_err("duplicates must not reach the worker");
        assert!(error.to_string().contains("more than once"));
    }
}
