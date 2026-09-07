//! The contract a search implements, and what it will accept alongside itself.

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, Result};
use crate::taxonomy::{EngineId, Modifier};

/// One search.
///
/// Requests and answers are untyped JSON on purpose: each engine owns its own
/// input and output shape, and the layers above only ferry them. An engine
/// that wants type safety deserialises the request into its own struct.
pub trait Engine: Send + Sync + 'static {
    /// Which search this is.
    fn id(&self) -> EngineId;

    /// Whether this engine computes, as opposed to being named for later.
    ///
    /// The interface needs to know before it offers somebody a form: a page
    /// that takes a sequence and then answers "not implemented" wastes the one
    /// thing a person brought with them.
    fn implemented(&self) -> bool {
        true
    }

    /// Modifiers this engine can be combined with.
    ///
    /// Declared rather than assumed, and checked when profiles are registered,
    /// so an impossible combination fails at startup instead of surprising
    /// somebody mid-run. A tiling scheme assigns its own pools, for instance,
    /// so multiplexing it is not a thing that can be asked for.
    fn accepts(&self) -> &'static [Modifier];

    /// The named settings this engine offers a form, if it has any.
    ///
    /// Published rather than restated in the interface: a reaction preset is
    /// defined in one place, and a form that hard-codes the list is a form
    /// that goes stale the first time one is added.
    ///
    /// # Errors
    ///
    /// Whatever the engine's own failure modes are.
    fn presets(&self) -> Result<Option<serde_json::Value>> {
        Ok(None)
    }

    /// Check a request without running it. Accepts by default.
    ///
    /// # Errors
    ///
    /// [`CoreError::InvalidRequest`] when the request is malformed.
    fn validate(&self, _request: &serde_json::Value) -> Result<()> {
        Ok(())
    }

    /// Run the search.
    ///
    /// # Errors
    ///
    /// Whatever this engine's failure modes are, most often
    /// [`CoreError::InvalidRequest`] or [`CoreError::NotImplemented`].
    fn design(&self, request: serde_json::Value) -> Result<serde_json::Value>;
}

/// What an engine is, for the interface to display without knowing what it does.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EngineDescription {
    /// Which search.
    pub id: EngineId,
    /// Human-readable name.
    pub name: &'static str,
    /// What it starts from.
    pub input: &'static str,
    /// What it can be combined with.
    pub accepts: Vec<Modifier>,
    /// Whether asking it to design something will produce a result.
    pub implemented: bool,
}

/// An engine that is named but not written.
///
/// Every assay needs an engine to point at, and most engines will be named
/// long before they compute anything. This one refuses rather than returning
/// an empty answer, so nothing downstream can mistake silence for a result.
#[derive(Debug, Clone)]
pub struct UnbuiltEngine {
    id: EngineId,
    accepts: &'static [Modifier],
}

impl UnbuiltEngine {
    /// Name an engine, and declare what it will accept once it exists.
    #[must_use]
    pub const fn new(id: EngineId, accepts: &'static [Modifier]) -> Self {
        Self { id, accepts }
    }
}

impl Engine for UnbuiltEngine {
    fn id(&self) -> EngineId {
        self.id
    }

    fn implemented(&self) -> bool {
        false
    }

    fn accepts(&self) -> &'static [Modifier] {
        self.accepts
    }

    fn design(&self, _request: serde_json::Value) -> Result<serde_json::Value> {
        Err(CoreError::NotImplemented(self.id.label().to_owned()))
    }
}

/// The compatibility matrix, as this build declares it -- by building it.
///
/// One row per engine, **read from the engines themselves**: each real engine
/// declares its own `ACCEPTS` const next to its request type, and this
/// function constructs the real engine and asks it what it accepts. There was
/// a second, hand-written table here once, and by the time anyone compared the
/// two it disagreed with six of the eleven engines -- an assay could pass
/// startup against rules its own engine contradicted, because the placeholder
/// rows were always overwritten by the real ones before anything ran.
///
/// Changing an engine's row means changing that engine's `ACCEPTS`; there is
/// no second place to remember, and nothing left for two copies to disagree
/// about.
#[must_use]
pub fn default_engines() -> Vec<std::sync::Arc<dyn Engine>> {
    default_engines_with_worker(crate::Worker::unbound())
}

/// Build every shipped engine against one explicit scientific execution port.
///
/// The injected handle is cloned into each engine, so catalogue/domain metadata
/// remains independent of the concrete process or remote transport used by a
/// production application.
#[must_use]
pub fn default_engines_with_worker(worker: crate::Worker) -> Vec<std::sync::Arc<dyn Engine>> {
    use std::sync::Arc;

    use crate::engines::{
        ConsensusPair, DiscriminatingPair, FlankingPair, JunctionPrimers, LoopSet, MutagenicPair,
        Nested, OutwardPair, PairAndProbe, SinglePrimer, TilingScheme,
    };

    vec![
        Arc::new(FlankingPair::with_worker(worker.clone())),
        Arc::new(PairAndProbe::with_worker(worker.clone())),
        Arc::new(Nested::with_worker(worker.clone())),
        Arc::new(LoopSet::with_worker(worker.clone())),
        Arc::new(DiscriminatingPair::with_worker(worker.clone())),
        Arc::new(SinglePrimer::with_worker(worker.clone())),
        Arc::new(OutwardPair::with_worker(worker.clone())),
        Arc::new(ConsensusPair::with_worker(worker.clone())),
        Arc::new(TilingScheme::with_worker(worker.clone())),
        Arc::new(JunctionPrimers::with_worker(worker.clone())),
        Arc::new(MutagenicPair::with_worker(worker)),
    ]
}
