# Current release evidence

This directory contains only the current release's evidence and operating
contracts. The single candidate-wide record is
[`ENGINEERING-CLOSURE-REPORT.md`](ENGINEERING-CLOSURE-REPORT.md); it is the
`current_report` named by `release/release.toml`.

## Current authorities

- [`CURRENT-ENGINE-SYSTEM.md`](CURRENT-ENGINE-SYSTEM.md) — unified engine architecture.
- [`CURRENT-LINUX-MIGRATION.md`](CURRENT-LINUX-MIGRATION.md) — Linux migration and release-boundary record.
- [`CURRENT-LINUX-QUALIFICATION.md`](CURRENT-LINUX-QUALIFICATION.md) — supported native qualification gate.
- [`CURRENT-FOUNDATION-CLOSURE.md`](CURRENT-FOUNDATION-CLOSURE.md) — machine-backed foundation maturity matrix.
- [`CURRENT-METHOD-FIDELITY-CLOSURE.md`](CURRENT-METHOD-FIDELITY-CLOSURE.md) — named-method fidelity boundary.
- [`CURRENT-MULTIPLEX-CLOSURE.md`](CURRENT-MULTIPLEX-CLOSURE.md) — modality-specific multiplex boundary.
- [`CURRENT-STATIC-CONSISTENCY-AUDIT.md`](CURRENT-STATIC-CONSISTENCY-AUDIT.md) and its JSON projection — generated source-consistency evidence.
- [`SOURCE-QUALIFICATION.md`](SOURCE-QUALIFICATION.md) and `SOURCE-QUALIFICATION.json` — environment-independent source gate.
- [`SUPPLY-CHAIN.md`](SUPPLY-CHAIN.md) — dependency, image, and provenance boundary.
- [`PERFORMANCE-STATUS.md`](PERFORMANCE-STATUS.md) — performance evidence boundary.
- [`SECURITY-EXCEPTIONS.md`](SECURITY-EXCEPTIONS.md) — explicit, time-bounded security exceptions.

Generated JSON, SBOM, attestation, and manifest files are produced by the
release scripts and must not be hand-edited. Superseded audits, debugging
reports, and intermediate closure snapshots are removed from this directory;
durable release history remains in Git history or the immutable baseline.
