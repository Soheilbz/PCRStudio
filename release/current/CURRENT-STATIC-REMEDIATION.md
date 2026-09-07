# CURRENT current static remediation

**Release class:** `generation-1-unified-engine-linux-current`
**Source archive identity:** `PCRStudio-CURRENT-PUBLIC-SOURCE`
**Qualification status:** source remediation only; native/functional/bench qualification remains **PENDING**.

## Scope

The current remediation closes the latest static full-stack findings without claiming runtime evidence that has not been produced. No module maturity label is promoted by this source patch; all 21 public modules remain computationally `experimental` until the documented qualification and bench-evidence gates support promotion.

## Closed static findings

1. **Durable execution:** queued jobs are now recoverable across API restart through atomic executor leases, heartbeat renewal, stale-lease recovery and continuous bounded queued-job redispatch. Capacity is acquired before a job is marked running. Run persistence and job completion share one PostgreSQL transaction, and running-state completion/failure/cancellation mutations are executor-scoped so a stale or duplicate replica cannot overwrite a reclaimed job.
2. **Execution resource bounds:** project design/job creation shares the design rate limiter; durable jobs have active-count, retained-count, request-size, auxiliary-payload, per-account byte and terminal-retention limits. The prior 50 ms per-job cancellation polling is removed.
3. **Backup provenance:** export format `pcrstudio.export.v2` carries project schema/contract provenance; imported runs preserve their historical schema versions, contract identity, toolchain/run fingerprints, engine/module identity, summary metadata and timestamps instead of being relabelled as current. Legacy v1 remains accepted without fabricating a current contract identity; because v1 did not record project-level draft schema provenance, restored v1 projects use the explicit sentinel `0` for unknown/unrecorded draft schema rather than being falsely labelled schema 1.
4. **Backup round-trip bound:** account byte accounting includes provenance/framing headroom and export checks the exact serialized document against the 32 MiB restore ceiling.
5. **Worker process memory/deadlock hardening:** stdout/stderr retention is bounded; timeout/wait-error paths kill/reap the child before joining potentially blocked pipe helpers.
6. **Diagnostic redaction:** durable worker/store failures use the public-safe error taxonomy; the Next-to-Rust transport no longer exposes the internal API URL or local development command to users.
7. **Relational ownership:** attachment and qualification writes validate project/run correlation in code and migration `0011_r17_rev4_job_safety.sql` adds composite ownership/correlation constraints for new writes.
8. **Deployment transport:** the no-domain VM override is loopback-only (`127.0.0.1:8080`) for SSH/VPN/TLS-tunnel use. Cleartext public login/session transport is no longer a supported deployment mode.
9. **UI/accessibility:** the mobile sheet close control is no longer hidden, and justified instructional/auth text is returned to natural start alignment.
10. **CI hardening:** workflows declare read-only repository-content permission at the workflow boundary.
11. **Outward-pair closure:** inverse-PCR now has exact full-reference restriction/circularisation topology, origin-spanning coordinate reconstruction, explicit enzyme-cohort feasibility, pydna validation handoff and sequencing confirmation handoff while retaining one-sided/internal-cut as a reference-only boundary.
12. **Pair-and-probe closure:** conventional hydrolysis-probe design is joined by a hash-bound external MGB-aware Tm exchange, explicit optical authority validation, probe-specific transcript/variant geometry, combined amplicon+probe specificity and multiplex interaction evidence without inventing universal spectral or thermodynamic cutoffs.
13. **Single-primer closure:** SMARTer current-assisted RACE, nested GSP planning, exact/unique universal-primer reuse, primer walking and bounded ABI/AB1 trace review are wired across authority, worker, transport and UI layers; post-run evidence remains separate from ranking.
14. **Tiling closure:** managed PrimalScheme/Olivar lifecycle status, circular PrimalScheme `scheme-create`, native diagnostic visualisations, bounded depth/dropout evidence, repair handoff and scheme/version diff are exposed without synthesizing a universal backend score or auto-publishing a repaired scheme.
15. **Scientific run provenance:** selected chemistry/protocol authorities now contribute `authority_id`, reviewed revision and canonical SHA-256 to scientific/run fingerprinting rather than being implicit behind tool/schema versions.
16. **Authority coverage:** all 23 canonical chemistry/corpus inputs are fingerprint-covered, with an audit invariant that prevents a new decision-bearing authority from silently bypassing provenance.
17. **Source lifecycle:** the 61 flanking source records are represented in a content-addressed reviewed claim/document-identity ledger without redistributing third-party manuals or inventing hashes for bytes not actually held.
18. **Capability truth gate:** MGB, inverse-PCR, tiling and Nested semantics are tied to canonical capability truth so review generators, README/release language and implementation cannot independently drift while still passing static audit.
19. **RACE authority closure:** SMARTer/custom execution now requires exact partner context plus caller-reviewed SOP/manual revision and SHA-256; custom pseudo-authority URLs are removed.
20. **Digital-PCR routing closure:** reviewed QX600/QX ONE EvaGreen compatibility is explicit; QX Continuum remains probe-oriented and routes to Pair+Probe rather than receiving invented dye chemistry. Current QIAcuity software/VPF identity is evidence provenance only, never a substitute for measured run metadata.
21. **Species lifecycle closure:** accession.version, offline taxonomy/database snapshot, suppression/replacement status and explicit revalidation triggers are retained with the finite-panel specificity result; silent database/panel updates are not allowed to renew a prior claim.
22. **Restriction evidence closure:** SacI near-end evidence is source-conditioned; the remaining four enzyme minima stay explicitly unresolved instead of inheriting another enzyme's behavior.
23. **No-growth structural closure:** scientific/UI/API additions were extracted into focused modules and integration tests; maintainability ceilings were not enlarged.

## Release-evidence boundary

No current `release/FILE-MANIFEST.json` is shipped by this static-remediation candidate. The immutable historical baseline remains available, while the exact current candidate manifest must be generated and verified by the documented Linux preparation/qualification stage. This source pass intentionally does not fabricate that evidence during a non-executing source pass.

## Deliberately not claimed

This remediation was prepared by static source inspection. It does **not** assert that Rust/TypeScript/Python compilation, unit/integration/E2E tests, migrations, Docker composition, native scientific tools, Linux qualification or wet-lab qualification passed. Those gates must be executed in the target qualification environment before Final promotion.

The no-growth source-governance policy remains active. This pass did not enlarge any hotspot ceiling: new behavior was moved into focused integration tests, authority/lifecycle helpers, dPCR UI components, result-context cards and scientific result-schema modules while preserving the existing scientific control-flow boundary.
