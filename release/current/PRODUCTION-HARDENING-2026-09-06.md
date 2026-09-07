# PCRStudio production hardening — 2026-09-06

This source tree was hardened from the public CURRENT source baseline with a
root-cause-first policy: shared invariants were moved to shared authorities
instead of being patched independently at each call site.

## Security and configuration boundaries

- Trusted reverse-proxy parsing is fail-closed. Over-wide CIDRs, trust-all
  ranges and non-canonical network addresses are rejected at startup. Linux
  bootstrap validates Compose trust-zone networks as canonical RFC1918 IPv4
  CIDRs before image build.
- The Next.js Server Actions encryption key no longer travels through Docker
  build arguments or the persisted `.env`. Bootstrap owns a stable file-backed
  key and Docker BuildKit exposes it only to the Web build step.
- Optional operator and NCBI API credentials are file-backed deployment secrets.
  The NCBI key crosses only the dedicated sequence-fetch IPC request and is not
  inherited by generic scientific/native worker environments.
- Public-origin parsing is centralized. Deployment URLs must be HTTP(S) origins
  without credentials/path/query/fragment, Origin headers must use serialized
  origin form, and explicitly malformed/foreign browser mutation origins are
  rejected before reaching framework mutation machinery.
- CSP keeps inline scripts nonce-bound, permits external application chunks only
  from self, and disables script event-handler attributes. No production
  `unsafe-inline` script fallback is introduced.
- Release/scientific SHA-256 identities consumed by Rust share one canonical
  lowercase validation primitive instead of silently normalizing divergent
  representations.

## Process and scientific-runtime boundaries

- Native scientific processes and the accessibility helper use one bounded,
  shell-free subprocess primitive. stdout/stderr are drained concurrently,
  hard byte ceilings are enforced while the child is running, process groups
  are terminated on timeout/overflow, and partial scientific output is never
  silently parsed as a complete result.
- Rust worker stdout/stderr overflow is a protocol failure, not a diagnostic
  truncation followed by continued parsing. Final worker JSON discovery uses a
  linear reverse balanced-object scan rather than repeated suffix parsing.
- A success-shaped JSON payload cannot override a non-zero worker exit status.

## Durable execution and external-service coordination

- PostgreSQL is the cross-replica authority for NCBI request-slot reservation.
  Reservations have a bounded wait horizon so bursts cannot reserve minutes of
  future upstream capacity.
- Durable runner dispatch uses PostgreSQL as the queue authority and only pulls
  work that fits currently available weighted capacity; runners do not mirror a
  large shared backlog into duplicate process-local queues.
- The production runner no longer has the API-only egress network capability.
- Durable `run_jobs` ownership/project/run correlation is additionally enforced
  at the database layer with staged constraints plus post-migration invariant
  validation.

## Refactor closure and control-plane hardening

- Durable execution now has separate persistence/execution, control-plane and
  public HTTP representations. Polling and cancellation no longer hydrate or
  serialize the multi-MiB immutable scientific request, owner identifier or
  idempotency key. `RunJob.project_id` is non-null from PostgreSQL through Rust
  and Web contracts, matching the database invariant instead of carrying an
  impossible optional state.
- Queue hydration is bounded by currently available weighted runner capacity,
  and stale-job recovery mutates/counts rows without returning full request
  payloads. This prevents backlog size from becoming an avoidable database/RAM
  amplification path.
- Secret-bearing values are not raw `Debug` surfaces: bearer/session/recovery
  credentials, authentication DTOs and server configuration use redacted or
  absent debug representations. Deployment secret resolution has one shared
  direct/file authority, with domain-specific normalization at consumers.
- Canonical migration ownership lives in `pcr-storage::migrate`: migrations,
  historical ownership audit, staged constraint validation and the final
  catalog check for any remaining unvalidated FK/CHECK constraints are one
  boundary used by production, development and tests.
- Process supervision treats output overflow, timeout, cancellation and wait
  failures through one cleanup/reap lifecycle. The exact byte limit is accepted;
  the first byte beyond the limit terminates the process tree and fails closed.
- Linux toolchain configuration is emitted as structured JSON and JavaScript
  development tooling consumes that authority directly instead of re-parsing a
  shell-quoted environment file. Scientific smoke probes use the same bounded
  subprocess primitive as the runtime.
- Source-derived release generators are registered once and consumed by both
  preparation and qualification. SBOM generation precedes static-consistency
  rendering so dependency changes cannot manufacture a stale audit during the
  release preparation itself.

## Backup, restore and deployment integrity

- Backup verification hashes the exact operator-selected dump and compares that
  digest with its one-record sidecar; a sidecar naming another dump cannot make
  the selected restore artifact pass verification.
- Restore validates the archive before downtime, then quiesces application
  writers before taking the emergency rollback snapshot. A failed snapshot
  aborts before destructive restore and leaves application tiers stopped.
- Pre-deploy rollback backup is likewise taken after quiescing application
  writers, preventing writes from landing between the rollback point and schema
  migration.
- Restore drill rejects restored schemas containing unvalidated public
  constraints in addition to checking migrations/tables.
- Caddy is read-only, drops capabilities except `NET_BIND_SERVICE`, uses
  `no-new-privileges`, bounded PIDs and a small tmpfs.

## Qualification scope

The source/static and dependency-light gates included in this repository are
regenerated and checked as part of packaging. This environment does not provide
the complete Rust, pnpm, Docker and native scientific toolchain, so this report
does **not** claim native Linux production qualification.

Before a public server rollout, run the canonical full Linux gate on the target
Linux development/qualification host:

```bash
python3 scripts/run-linux-qualification.py --full --require-functional-acceptance
```

Do not promote the image if that gate, the production Compose health checks or
scientific functional acceptance fail.
