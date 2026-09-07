# CURRENT cross-layer remediation audit

**Status:** source remediation complete; native qualification pending

**Audit date:** 2026-09-05

**Scope:** full-stack source consistency, release/evidence contracts, UI state, API/wire contracts, and test architecture. No native build/runtime/scientific execution is claimed by this record.

## Closure summary

The deep post-cleanup audit identified 18 source-level findings: one release
blocker, seven high-severity findings, nine medium-severity findings, and one
low-severity maintenance finding. All 18 are closed in the current source tree.
The remediation also exposed a cross-layer architectural defect in the initial
required-context fix: semantic form context was being inferred as HTTP wire
context. That defect is closed by module-contract **2.2.0**, which makes the two
surfaces explicit rather than relying on snake-case/camel-case convention.

## Release and evidence integrity

- The master Linux qualifier and CURRENT finalizer use the same CURRENT source-gate
  identity and the finalizer requires the CURRENT authority, closure,
  differential/property, high-risk, and 21-module functional-acceptance gates.
- The release audit checks the qualifier/finalizer relationship and rejects the
  obsolete release-specific source-qualifier step name.
- CURRENT high-risk scenarios map to scenario-specific test selectors instead of
  re-running a generic suite under multiple scenario labels.
- Module and integration evidence is path-bound inside the project tree and is
  re-hashed by the acceptance validator. Evidence records carry the selector,
  command/log provenance, timestamp, and SHA-256 required by schema 1.3.0.
- The retained unified engine regression harness consumes the same hardened
  evidence model without being promoted to current-release authority.
- Linux CI is explicitly a source preflight, not a substitute for the native
  CURRENT qualification sequence; shared cargo-audit/cargo-deny versions are
  aligned across Linux/Linux workflow definitions.

## Contracts, API, and transport

- `contracts/modules.toml` now separates semantic/draft requirements from
  explicit `wire_required_context`, `wire_conditional_required_context`, and
  `wire_required_any_of` requirements for all 21 modules.
- Rust server request validation and Python worker runtime validation consume
  the generated wire contract. Web readiness consumes the semantic form
  contract. No layer infers one surface from the other by naming convention.
- Nested flanking numeric context and mutagenesis one-of request shapes are
  represented explicitly, eliminating the regression that a generic
  snake-case-to-camel-case validator would have introduced.
- The module contract version is **2.2.0** across canonical foundation,
  architecture, Rust contract identity, generated projections, and the new
  non-destructive storage migration. Existing historical rows are not rewritten.
- Differential-context projections now carry both semantic and wire context,
  and current generated module/foundation/engine/tool projections are
  byte-identical across knowledge, Python, Web, Rust core, and Rust contracts.
- Web transport tests use actual request construction against the canonical
  unified-engine transport contract rather than validating an isolated schema copy.

## UI/UX and project reproducibility

- Fork/Reopen restores the previously omitted qPCR, RACE, Sequencing, Inverse,
  and Tiling scientific settings, including structured multiplex/target data.
- Tiling operation state is seeded consistently rather than being represented
  only as a visual fallback.
- qPCR multiplex input uses a structured editor rather than a raw JSON textarea.
  Reporter/quencher authority key names are aligned with canonical data.
- Multiplex target data is typed and validates target identity plus supported
  chemistry/modification choices. Instrument spectral compatibility and
  peer-assay oligo interactions remain explicitly unresolved/diagnostic when
  the required authority or peer sequences are absent; the UI/result layer no
  longer overclaims those checks.

## Test and maintainability closure

- Current live runtime-contract tests cover qPCR Probe, RACE, Sequencing Primer,
  Inverse PCR, and Tiling result shapes rather than relying only on historical
  fixtures.
- Browser E2E coverage includes the CURRENT engine workspaces; an obsolete pUC19
  display-name assumption in the older critical journey was reconciled.
- High-risk acceptance scenarios are evidence-addressable one by one.
- CURRENT-specific high-change Web controls were extracted from the main engine
  field monolith. Existing large scientific modules are protected by static
  no-growth budgets so future work must extract responsibilities rather than
  silently enlarge the hotspots before a qualified refactor is available.
- ESLint 9 remains under an explicit, expiring maintenance exception because
  the current React/Next peer graph does not support a clean forced ESLint 10
  promotion. The exception is visible to source audit and dependency monitoring
  rather than hidden by a peer-dependency override.

## Static reconciliation result

The final independent source audit after remediation reports:

- 21 canonical public modules and 22 canonical Linux integration scenarios.
- Module contract 2.2.0 and package identity 17.0.0 across Cargo, Python, and Web.
- Zero Python/JSON/TOML parse errors and zero TypeScript/TSX parser errors.
- Zero generated projection drift and zero expert source-fingerprint drift.
- Zero symlink/build/cache/pyc residue, merge markers, trailing whitespace,
  broken local Markdown links, case-insensitive Linux path collisions,
  reserved Win32 names, private-key patterns, or `/mnt/data` leakage.
- All relative source paths are at most 100 characters.

## Boundary

This is a **source-level** closure. It does not claim Cargo build/test/clippy,
Python pytest/runtime, pnpm/Vitest/lint/typecheck/Next build, scientific tool
invocation, running-stack behavior, database qualification, or Linux-native
functional acceptance. Those must be produced on the supported Linux
host and bound to the exact candidate manifest before CURRENT Final promotion.


## Pre-Linux cold double-audit closure

After the original 18-finding remediation, a separate cold audit found 20 additional
operational/source holes before Linux handoff. These are also closed. The closure
includes: explicit fingerprinted `external-managed` Olivar resolution; feature-gated
scientific readiness; master-qualifier import of the provisioned toolchain; approved
specificity/scientific-environment sequencing; native unmocked PrimalScheme3 lifecycle
acceptance; live Web runtime-contract execution; authenticated Chromium full-stack E2E
plus cross-browser/mobile accessibility smoke; dynamic endpoint discovery; 7-Zip-free
Linux provisioning; current timeout documentation; current qPCR/Tiling copy; strict
acceptance evidence provenance; performance/capacity evidence; public evidence summary
attestation; Docker application/control-plane fail-closed semantics; and generated-scheme
license provenance for PrimalScheme outputs.

The strict source audit then reported 46 residual items. They were not bulk-suppressed:
real defects were corrected (including KASP provider/software evidence preservation,
Inverse cohort magic-bound provenance, Junction authority projection structure, UI
accessibility/token issues and the qPCR MGB refusal marker), while obsolete release-specific
wording checks were rewritten to assert the current scientific invariants. Canonical
expert/runtime artifacts were regenerated. The resulting `scripts/audit-source.py`
status is **0 errors / 0 warnings**.
