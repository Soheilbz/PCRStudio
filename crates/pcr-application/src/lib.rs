//! Application orchestration shared by PCRStudio transports and workers.
//!
//! The crate deliberately has no HTTP dependency. It owns the use-case layer:
//! canonical design preparation, weighted scientific admission control, and the
//! durable PostgreSQL job executor. `pcr-server` therefore remains a
//! transport/authentication boundary, while `pcr-runner` executes the exact
//! same scientific contract without depending on Axum.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod design;
pub mod gate;
pub mod jobs;
pub mod scientific;

pub use design::{
    assay_payload, design_for, ensure_release_executable, enzyme_incompatibility, preset_hold,
    validate_requirements,
};
pub use gate::Gate;
