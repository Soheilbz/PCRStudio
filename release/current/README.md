# CURRENT candidate evidence

This directory contains the active release candidate's evidence and operating
contracts. The latest candidate-wide record is
[`ENGINEERING-CLOSURE-REPORT.md`](ENGINEERING-CLOSURE-REPORT.md); it is the
`current_report` named by `release/release.toml`.

The independent GitHub/release/deployment audit is
[`UNKNOWN-UNKNOWNS-AUDIT.md`](UNKNOWN-UNKNOWNS-AUDIT.md); its open findings are
release gates, not historical notes.

## Authorities

- [`CURRENT-ENGINE-SYSTEM.md`](CURRENT-ENGINE-SYSTEM.md) — unified engine architecture.
- [`CURRENT-LINUX-MIGRATION.md`](CURRENT-LINUX-MIGRATION.md) — Linux migration and release-boundary record.
- [`CURRENT-LINUX-QUALIFICATION.md`](CURRENT-LINUX-QUALIFICATION.md) — supported native qualification gate.
- [`CURRENT-STATIC-CONSISTENCY-AUDIT.md`](CURRENT-STATIC-CONSISTENCY-AUDIT.md) and its JSON projection — generated source-consistency evidence.
- [`SOURCE-QUALIFICATION.md`](SOURCE-QUALIFICATION.md) and `SOURCE-QUALIFICATION.json` — environment-independent source gate.
- [`SUPPLY-CHAIN.md`](SUPPLY-CHAIN.md) — dependency, image, and provenance boundary.
- [`PERFORMANCE-STATUS.md`](PERFORMANCE-STATUS.md) — performance evidence status.

The remaining `CURRENT-*` audit and closure records are scoped evidence for
their named concern; they do not redefine the authorities above. Generated
JSON, SBOM, attestation, and manifest files are produced by the release
scripts and must not be hand-edited. Historical release reports belong in Git
history or the immutable baseline, not in this active directory.
