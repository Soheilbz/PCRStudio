//! Compatibility re-export for the application-layer scientific admission gate.
//!
//! The implementation lives in `pcr-application` so both the HTTP server and
//! the dedicated Linux runner share one concurrency/cancellation policy.

pub use pcr_application::gate::*;
