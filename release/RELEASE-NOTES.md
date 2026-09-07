# CURRENT public source — release notes

## Linux architecture and operations hardening

The current candidate is now Linux x86_64-native at the release/runtime boundary. Production durable jobs execute in a dedicated PostgreSQL-backed `pcr-runner`, deployment migrations are owned by a one-shot `pcr-migrate`, and the Rust HTTP API remains the enqueue/control plane. Scientific subprocesses are isolated into POSIX process groups so timeout/cancellation/shutdown reap native descendants rather than leaving BLAST/MAFFT-style orphans.

Production Compose now carries immutable scientific code/tooling in the API/runner image, mounts only fingerprinted specificity data read-only, uses file-backed database secrets, validates the Next Server Actions build key, applies segmented networks and per-role resource/PID ceilings, and records source/scientific build identities in readiness evidence. The bootstrap adds RAM-aware profiles, disk and subnet preflight, pre-deploy backups, strict scientific readiness, immutable environment-drift approval, and optional systemd backup/restore-drill timers. A read-only Linux doctor can audit a VM before bootstrap mutates it.

Source/static qualification was re-run after the migration and remains green. Native Docker/Rust/Web/scientific execution is deliberately left to the explicit Linux CI/target-host gates rather than being inferred from source inspection. See `release/current/CURRENT-LINUX-ENGINEERING-CLOSURE.md`.
## Current static full-stack remediation

The current source hardens the qualification-candidate tree without promoting any scientific module or claiming runtime evidence. Durable jobs now use database-backed executor leases, heartbeat/recovery and atomic run/job completion; job creation is rate-limited and bounded by active, retained, payload, account-byte and retention limits. Backup format v2 preserves project/run provenance instead of relabelling restored history, while legacy v1 remains accepted with unknown project draft provenance represented explicitly rather than guessed.

Worker stdout/stderr retention is bounded and timeout cleanup kills/reaps children before joining pipe helpers. Durable-job diagnostics are redacted through the public error taxonomy. Attachment/qualification ownership correlation is enforced in code and strengthened by composite database constraints. The no-domain VM bootstrap is loopback-only; direct public service requires HTTPS. The mobile sheet close control, auth text alignment, API project-limit contract parity and workflow permissions are also corrected.

The current remediation changes were prepared and reconciled by static source inspection only. They do not claim Rust/TypeScript/Python compilation, migrations, Docker/runtime behavior, native-tool availability, Linux acceptance or wet-lab qualification; those remain required before Final promotion.

A subsequent method-fidelity closure adds a canonical named-method registry and CI/source gate. SADDLE Badness is separated from the unavailable exact SADDLE simulated-annealing optimiser; Universal Primer surrogate pre-ranking and LAMP linear proxy ranking are removed from primary decisions; Tetra-ARMS uses the reviewed Ye/Collins-Day public-rule branch; RPA exposes a source-backed 8–10 forward × 8–10 reverse empirical screening matrix rather than treating Primer3 scores as RPA validation; QuikChange rules are manual-faithful without claiming Agilent web-tool equivalence; and ARMSprimer3, Kraken, PrimerExplorer proprietary search and NEBaseChanger web-tool design remain distinct external/reference authorities where exact execution is not integrated. Per-run method fidelity is fingerprint-bound and exposed in Web provenance.

CURRENT completes the source/full-stack closure of Inverse PCR, hydrolysis-probe
qPCR, RACE/Sequencing Primer, and Tiling Scheme on the Generation-1 baseline.

Key changes include qPCR Probe status/projection reconciliation; source-backed
separation of vendor rules from PCRStudio search defaults; conventional Thermo
Fisher/IDT probe execution plus hash-bound MGB external-authority export/import; current
FirstChoice exact-partner and content-addressed SMARTer/custom RACE authority support;
correction of a RACE adapter dispatch defect; inverse-PCR circular/pydna/Sanger evidence;
PrimalScheme3 circular create/native visual/depth-dropout repair/version-diff transport; and
unified-engine Rust/Python/Web differential/property contracts plus Linux high-risk acceptance coverage.

A subsequent cross-layer audit closed 18 additional source findings spanning
release finalization, acceptance evidence, Fork/Reopen state, qPCR multiplex
claims, live/E2E coverage, transport parity, package identity, and canonical
API requirements. Module-contract 2.2.0 now explicitly separates semantic
form context from HTTP wire context so Web readiness, Rust API validation,
and Python worker validation share authority without inferring payload paths
from UI field names.

A final pre-Linux cold audit identified and closed 20 further operational gaps in
scientific tool resolution/readiness, native qualification evidence, E2E/deployment
boundaries, UI semantics and release provenance. A strict follow-up reconciliation
reduced 46 residual audit findings to zero without weakening scientific refusal
boundaries.

The public-source cleanup removes superseded checkpoint/history reports and
obsolete release-control scripts, keeps only the baseline artifact required
by CURRENT qualification, and replaces machine/agent-specific notes with public
development, contribution, and security documentation.

CURRENT does not claim native Linux PASS or wet-lab validation until those gates
are executed and recorded against the exact release identity.
