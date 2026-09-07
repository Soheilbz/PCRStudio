# ADR 0008 — Layered modular monolith and architecture drift guards

**Status:** accepted for Generation 1 architecture

PCRStudio remains a layered modular monolith. The scientific engines are deliberately
not split into network microservices: they share versioned contracts, provenance,
coordinate semantics and a single release lifecycle. The system is modular by domain,
not by deployment boundary.

## Dependency direction

- `contracts/` is canonical authority; generated projections are read-only outputs.
- Python owns scientific candidate generation and assay-specific evaluation.
- Rust owns typed transport/domain validation, worker orchestration and HTTP composition.
- Web owns browser orchestration, presentation and explicit evidence capture.
- Persistence stores immutable historical requests/results with versioned read migrations.
- Cross-domain security primitives live in `pcr-security`; domain crates do not depend
  sideways on another domain merely to reuse a primitive.

## Stable cross-layer contracts

All internal coordinates are zero-based half-open intervals. Oligos are stored 5'→3'.
Workflow evidence has one canonical result shape: `{ recorded, decision_impact: "none",
observed, note }`. Historical `{ fields }` evidence is accepted only through a read
migration and is never rewritten in storage.

HTTP failures preserve the server error envelope (`code`, `kind`, `detail`, `fieldPath`,
`stage`, `retryable`, `requestId`) through the Web transport. Generated contract files
must be regenerated from canonical authority and must not be hand-edited.

## Why not refactor every large file now?

File size alone is not architectural fragmentation. Some large files are orchestration
hubs that intentionally keep a single state machine visible. Generation 1 therefore uses
review thresholds and dependency/duplication guards rather than performing broad
behavior-changing splits without native Linux qualification.

## Enforcement

`contracts/architecture.toml` is the machine-readable policy. `scripts/audit/architecture.py`
checks dependency direction, shared evidence/error contracts, persistence versioning,
workspace lint/lock policy, UI layering and hotspot thresholds. Linux qualification
runs the normal compiler/test suites with `cargo --locked` after generated artifacts
have converged.
