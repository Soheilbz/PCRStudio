# PCRStudio generation-1 implementation knowledge

This folder carries the reviewed scientific/toolchain authority beside the code that implements it. Runtime code does **not** parse Markdown; the
machine-readable contract lives in `runtime/` and the Python/Rust/API adapters.

Authority order:

1. `atlas/engines/**/00-engine.md` and module documents: assay/topology science.
2. `atlas/engines/**/01-tools.md`: tool semantics, versions, roles and limits.
3. `atlas/contracts/*.json`: canonical machine-readable toolchain contract.
4. `runtime/module-contracts.json`: implementation mapping for the 21 product modules.
5. `runtime/ux-contract.json`: canonical interaction/result language and accessibility obligations for the design workbench.
6. `reviews/FULL-SYSTEM-AUDIT.md` and `reviews/UX-EXPERT-REVIEW.md`: current static implementation/UX review record.
7. Source code: must implement the contracts above; it must not silently redefine them.

Generation-1 philosophy: mature tools + deterministic orchestration + independent validation +
explicit fallback/provenance. Experimental learned scoring is not a production dependency.
