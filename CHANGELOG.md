# Changelog

This file summarizes the current public-source milestone. Detailed scientific and
qualification evidence is maintained under `release/current/`.

## R17 — current public source — 2026-09-05

- Closed the Generation-1 source/full-stack backlog for Inverse PCR,
  hydrolysis-probe qPCR, RACE/Sequencing Primer, and Tiling Scheme.
- Reconciled qPCR Probe status and chemistry-specific authority across contracts,
  Rust, Python, Web, Atlas, and acceptance layers.
- Kept MGB/NFQ exact-Tm ranking fail-closed pending an executable MGB-aware
  thermodynamic authority.
- Added current FirstChoice RLM-RACE exact-partner support while retaining
  SMARTer as source-limited until equivalent current authority is canonicalized.
- Corrected RACE adapter dispatch and cross-kit non-leakage behavior.
- Preserved provider-scoped sequencing design/submission/evidence boundaries.
- Preserved explicit Inverse-PCR topology and unknown-flank semantics.
- Kept PrimalScheme3 and Olivar as independent tiling backends with actual
  backend provenance and explicit coordinate/export boundaries.
- Added unified-engine differential/property coverage and Linux high-risk
  qualification scenarios.
- Closed the post-cleanup cross-layer audit findings across release finalization,
  evidence integrity, Fork/Reopen state, qPCR multiplex claims, live/E2E tests,
  transport parity, package identity, and canonical API validation.
- Upgraded the canonical module contract to 2.2.0 with explicit semantic/form
  versus HTTP-wire required context consumed independently by Web, Rust, and Python.
- Cleaned the repository for public distribution: removed superseded release
  reports and obsolete R16 release-control scripts, isolated the immutable
  baseline under `release/baseline/`, and replaced machine/agent-specific
  instructions with public development/contribution/security documentation.

R17 remains computationally `experimental` until the native qualification and
wet-lab evidence gates described in `release/STATUS.md` are satisfied.
