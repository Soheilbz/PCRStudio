//! The engines that compute, as opposed to the ones that are only named.
//!
//! Every engine in `taxonomy::EngineId` lives here and computes; there is no
//! unbuilt one left. The registry keeps the `UnbuiltEngine` machinery because
//! it is how the next engine arrives: registered first, answering
//! `NotImplemented`, then replaced by the real search without any caller
//! seeing the seam.
//!
//! What the adapters share -- request checks that must mean the same thing on
//! every assay -- lives in [`common`], and every engine calls it rather than
//! keeping its own copy.

pub mod common;
pub mod consensus_pair;
pub mod digital_multiplex;
pub mod discriminating_pair;
pub mod flanking_pair;
pub mod junction_primers;
mod lamp_multiplex;
pub mod loop_set;
pub mod mutagenic_pair;
pub mod nested;
pub mod outward_pair;
pub mod pair_and_probe;
mod rpa_multiplex;
pub mod single_primer;
pub mod tiling_scheme;

pub use consensus_pair::{ConsensusPair, ConsensusPairRequest};
pub use discriminating_pair::{DiscriminatingPair, DiscriminatingPairRequest};
pub use flanking_pair::{FlankingPair, FlankingPairRequest};
pub use junction_primers::{Fragment, JunctionPrimers, JunctionPrimersRequest};
pub use loop_set::{LoopSet, LoopSetRequest};
pub use mutagenic_pair::{Edit, MutagenicPair, MutagenicPairRequest};
pub use nested::{Nested, NestedRequest};
pub use outward_pair::{OutwardPair, OutwardPairRequest};
pub use pair_and_probe::{PairAndProbe, PairAndProbeRequest};
pub use single_primer::{SinglePrimer, SinglePrimerRequest};
pub use tiling_scheme::{TilingScheme, TilingSchemeRequest};
