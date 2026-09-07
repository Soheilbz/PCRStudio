//! Lightweight unit-bearing reaction quantities.

use serde::{Deserialize, Serialize};

/// Supported reaction units at contract boundaries.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Unit {
    /// Millimolar.
    MilliMolar,
    /// Micromolar.
    MicroMolar,
    /// Microliter.
    Microliter,
    /// Enzyme units.
    Units,
    /// Degrees Celsius.
    Celsius,
    /// Minutes.
    Minutes,
    /// Fold concentration.
    Fold,
    /// Percent.
    Percent,
}

/// Numeric value with explicit unit identity.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Quantity {
    /// Numeric magnitude.
    pub value: f64,
    /// Unit identity.
    pub unit: Unit,
}

impl Quantity {
    /// Construct one quantity.
    #[must_use]
    pub const fn new(value: f64, unit: Unit) -> Self {
        Self { value, unit }
    }
}

/// C1V1=C2V2 for fold-concentration reagents.
pub fn dilution_volume(
    reaction_volume: Quantity,
    final_concentration: Quantity,
    stock_concentration: Quantity,
) -> Option<Quantity> {
    if reaction_volume.unit != Unit::Microliter
        || final_concentration.unit != Unit::Fold
        || stock_concentration.unit != Unit::Fold
        || stock_concentration.value <= 0.0
    {
        return None;
    }
    Some(Quantity::new(
        reaction_volume.value * final_concentration.value / stock_concentration.value,
        Unit::Microliter,
    ))
}
