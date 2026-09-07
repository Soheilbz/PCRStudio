//! What this build offers, and the checks that decide whether it may start.
//!
//! The registry holds two things: the engines that were compiled in, and the
//! assay profiles that were declared. Its real job is the join between them —
//! every profile has to name an engine that exists and may only ask for
//! modifiers that engine accepts. Both are settled here, at startup, so an
//! impossible assay stops the process instead of failing under somebody.

use std::collections::BTreeMap;
use std::sync::Arc;

use crate::engine::{Engine, EngineDescription};
use crate::error::{CoreError, Result};
use crate::profile::Profile;
use crate::taxonomy::{EngineId, Goal};

/// Every engine and assay this build ships.
///
/// `BTreeMap` rather than `HashMap` so listings come out in a stable order and
/// the sidebar does not reshuffle between launches.
#[derive(Clone, Default)]
pub struct Registry {
    engines: BTreeMap<EngineId, Arc<dyn Engine>>,
    profiles: BTreeMap<String, Profile>,
}

impl Registry {
    /// An empty registry.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Compile in one engine.
    ///
    /// # Errors
    ///
    /// [`CoreError::DuplicateProfile`] is not used here; a second engine for
    /// the same id simply replaces the first, which is what a test double
    /// needs to be able to do.
    pub fn add_engine(&mut self, engine: Arc<dyn Engine>) {
        self.engines.insert(engine.id(), engine);
    }

    /// Declare one assay, checking it against the engines already present.
    ///
    /// # Errors
    ///
    /// [`CoreError::InvalidRequest`] for an id that would not survive a URL;
    /// [`CoreError::DuplicateProfile`] if the id is taken;
    /// [`CoreError::UnknownEngine`] if it names an engine this build lacks;
    /// [`CoreError::IncompatibleModifier`] if it asks for something the engine
    /// does not accept.
    pub fn add_profile(&mut self, profile: Profile) -> Result<()> {
        profile.check_id()?;
        profile.check_defaults()?;

        if self.profiles.contains_key(&profile.id) {
            return Err(CoreError::DuplicateProfile(profile.id));
        }

        let Some(engine) = self.engines.get(&profile.engine) else {
            return Err(CoreError::UnknownEngine(format!(
                "the assay `{}` names the `{}` engine, which this build does not have",
                profile.id,
                profile.engine.label()
            )));
        };

        let accepted = engine.accepts();
        for modifier in &profile.modifiers {
            if !accepted.contains(modifier) {
                return Err(CoreError::IncompatibleModifier(format!(
                    "the assay `{}` asks for `{}`, which the `{}` engine does not accept",
                    profile.id,
                    modifier.label(),
                    profile.engine.label()
                )));
            }
        }

        self.profiles.insert(profile.id.clone(), profile);
        Ok(())
    }

    /// One assay by id.
    ///
    /// # Errors
    ///
    /// [`CoreError::UnknownProfile`] if nothing is registered under `id`.
    pub fn profile(&self, id: &str) -> Result<&Profile> {
        self.profiles
            .get(id)
            .ok_or_else(|| CoreError::UnknownProfile(id.to_owned()))
    }

    /// The engine one assay runs on.
    ///
    /// # Errors
    ///
    /// [`CoreError::UnknownProfile`] if there is no such assay. The engine
    /// itself cannot be missing: no profile is registered without one.
    pub fn engine_for(&self, profile_id: &str) -> Result<Arc<dyn Engine>> {
        let profile = self.profile(profile_id)?;
        self.engines
            .get(&profile.engine)
            .cloned()
            .ok_or_else(|| CoreError::UnknownEngine(profile.engine.label().to_owned()))
    }

    /// One engine by its id, whether or not any assay uses it yet.
    ///
    /// `engine_for` answers "what runs this assay"; this answers "does the
    /// search exist at all" -- which is what a test that walks the vocabulary
    /// needs, and what would have caught the engines that were once written,
    /// tested, and never registered.
    #[must_use]
    pub fn engine_by_id(&self, id: EngineId) -> Option<Arc<dyn Engine>> {
        self.engines.get(&id).cloned()
    }

    /// Every assay, ordered by id.
    #[must_use]
    pub fn profiles(&self) -> Vec<Profile> {
        self.profiles.values().cloned().collect()
    }

    /// Every assay under one goal, ordered by id.
    #[must_use]
    pub fn profiles_for(&self, goal: Goal) -> Vec<Profile> {
        self.profiles
            .values()
            .filter(|profile| profile.goal == goal)
            .cloned()
            .collect()
    }

    /// How many assays are registered.
    #[must_use]
    pub fn len(&self) -> usize {
        self.profiles.len()
    }

    /// Whether no assay is registered.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.profiles.is_empty()
    }

    /// What one engine is, or `None` if this build does not have it.
    #[must_use]
    pub fn engine_description(&self, id: EngineId) -> Option<EngineDescription> {
        self.engines.get(&id).map(|engine| EngineDescription {
            id: engine.id(),
            name: id.label(),
            input: id.input(),
            accepts: engine.accepts().to_vec(),
            implemented: engine.implemented(),
        })
    }

    /// How many engines were compiled in.
    #[must_use]
    pub fn engine_count(&self) -> usize {
        self.engines.len()
    }
}

impl std::fmt::Debug for Registry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Registry")
            .field("engines", &self.engines.keys().collect::<Vec<_>>())
            .field("assays", &self.profiles.keys().collect::<Vec<_>>())
            .finish()
    }
}
