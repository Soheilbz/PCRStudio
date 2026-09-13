# Changelog

This file summarizes the current public-source milestone. Detailed scientific and
qualification evidence is maintained under `release/current/`.

## v1.0.5 — superseded before deployment — 2026-09-13

- Its source changes normalized permissions across pinned native-tool trees, but the final runtime smoke exposed a missing launcher interpreter before the deployment bundle was published. Use v1.0.6 for a deployable release; no production rollout occurred from v1.0.5.

## v1.0.6 — 2026-09-13

- Fix production startup in the restricted runtime without changing pinned product images or user data.
- Publish production releases only after image startup qualification passes, so an incomplete build cannot become the public Latest release.
- Refresh the host storage guard before deployment image operations, so old reserve policies cannot stop services on the dedicated VM.

## v1.0.4 — 2026-09-13

- Fixed bundled runtime-tool permissions so the unprivileged service account can read and execute them.
- Kept pinned base-image identities, scientific behavior, and user data formats unchanged.

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
