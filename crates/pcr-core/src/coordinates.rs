//! Typed zero-based half-open coordinates.
//!
//! Scientific engines may still deserialize legacy integers at their boundary,
//! but interval arithmetic should use these types so a base index, a boundary,
//! and a circular position are not interchangeable integers.

use serde::{Deserialize, Serialize};

/// Zero-based base index.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct BaseIndex(pub usize);

/// Boundary between bases in `[start,end)` coordinates.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Boundary(pub usize);

/// Valid half-open interval.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct HalfOpenInterval {
    /// Inclusive start boundary.
    pub start: Boundary,
    /// Exclusive end boundary.
    pub end: Boundary,
}

impl HalfOpenInterval {
    /// Construct an interval, rejecting a reversed pair.
    pub fn new(start: Boundary, end: Boundary) -> Option<Self> {
        (start <= end).then_some(Self { start, end })
    }

    /// Number of bases covered.
    #[must_use]
    pub fn len(self) -> usize {
        self.end.0 - self.start.0
    }

    /// Whether the interval is empty.
    #[must_use]
    pub fn is_empty(self) -> bool {
        self.start == self.end
    }
}

/// Reference strand; coordinates still increase on the reference.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Strand {
    /// Reference/forward strand.
    Plus,
    /// Reverse-complement strand.
    Minus,
}

/// Position normalized modulo a circular reference length.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct CircularPosition {
    /// Normalized zero-based position.
    pub value: usize,
    /// Circular reference length.
    pub reference_length: usize,
}

impl CircularPosition {
    /// Normalize a raw position on a non-empty circular reference.
    pub fn new(value: usize, reference_length: usize) -> Option<Self> {
        (reference_length > 0).then_some(Self {
            value: value % reference_length,
            reference_length,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interval_has_half_open_length() {
        assert_eq!(
            HalfOpenInterval::new(Boundary(3), Boundary(8))
                .unwrap()
                .len(),
            5
        );
        assert!(HalfOpenInterval::new(Boundary(8), Boundary(3)).is_none());
    }

    #[test]
    fn circular_position_normalizes() {
        assert_eq!(CircularPosition::new(12, 10).unwrap().value, 2);
    }
}
