# CURRENT Linux engineering closure

**Canonical target:** Linux x86_64
**Architecture:** layered modular monolith with an external PostgreSQL-backed scientific runner
**Source disposition:** Linux-migrated and source-qualified; production/native execution remains an explicit evidence gate on a host that has Docker/network access.

## Closed migration work

- Removed active PowerShell/CMD/batch launchers and Windows executable-path assumptions from the runtime/release path.
- Canonicalized LF/UTF-8 source hygiene, executable script modes, case-sensitive path behavior and POSIX process handling.
- Made `pnpm` native dependency materialization Linux/current-x64 aware while retaining legitimate cross-platform lockfile metadata.
- Replaced host-dependent scientific execution with a self-contained Linux API/runner image containing the Python worker and native scientific tools.
- Kept large specificity data deployment-owned, content-addressed and read-only at runtime.
- Added Linux-native provisioning, database indexing, scientific environment fingerprints, immutable scientific-identity approval and whole-MAFFT-bundle integrity binding.
- Split durable scientific execution from HTTP: `pcr-server` enqueues, `pcr-runner` claims/executes, and `pcr-migrate` exclusively owns deployment migrations.
- Added build-identity and scientific-freeze binding to runner registration/readiness so mismatched images cannot appear healthy.
- Added POSIX process-group cancellation/reaping for scientific subprocess trees and bounded runner/API shutdown drain semantics.
- Split control-plane readiness (`/ready`) from strict scientific readiness (`/ready/scientific`).
- Moved production database credentials to file-backed Compose secrets and moved the Next Server Actions encryption key to validated build-time injection.
- Hardened production Compose with non-root/read-only application containers, dropped capabilities, `no-new-privileges`, PID/memory limits, segmented networks, log rotation and dedicated runner scratch.
- Added RAM-aware resource profiles, Docker-network collision handling, stable Compose project identity and fail-closed disk-capacity preflight.
- Added one-command Debian/Ubuntu bootstrap using Docker's official repository only when a sufficient Engine/Compose installation is not already usable.
- Added a read-only `doctor-linux.py` for host diagnostics before any mutation.
- Hardened backup/restore with owner-only dumps, SHA-256 sidecars, pre-deploy/pre-restore snapshots, maintenance-mode restore, migration/invariant validation, retention and optional systemd automation.
- Added CI release topology coverage for `db -> migrate -> runner -> api -> web -> caddy` with strict scientific readiness.
- Added architecture guards/ADR so the application/runner boundary, bootstrap hardening and Linux-only release assumptions cannot silently drift.

## Qualification evidence executed in the migration environment

The environment-independent gates were executed after the refactor:

- Python source AST parsing: PASS
- Bash syntax validation for all active shell scripts: PASS
- Node syntax validation for repository JavaScript/MJS scripts: PASS
- Linux bootstrap/provision regression checks: PASS
- canonical static audit: **0 errors / 0 warnings**
- source qualification, including generated-contract checks, executable Web numeric contracts, Rust source-boundary/differential checks and focused Python regression tests: PASS
- source hygiene: zero symlinks, zero case-only collisions and zero cache/build residue

## Native evidence boundary

This source snapshot does **not** fabricate evidence unavailable in the review sandbox. The sandbox does not provide a Docker daemon or the pinned Rust toolchain, and its shell cannot resolve external package registries. Therefore the following are mandatory external gates rather than claimed local PASS results:

- `cargo test --locked --workspace`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- Node 24 / pnpm 11.19 dependency-backed Web type/lint/test/build
- production Docker image builds
- image-level download/hash/build/version/smoke of the native scientific tools
- Compose production-topology startup/migrations
- strict `/ready/scientific == ready:true`
- full 21-module functional acceptance against the exact source identity

Those gates are implemented in CI/bootstrap/`scripts/run-linux-qualification.py`; a failure blocks the native release claim.

## Production entrypoints

Read-only host diagnosis:

```bash
python3 scripts/doctor-linux.py --domain pcr.example.org --allow-docker-install
```

One-command production bootstrap:

```bash
./bootstrap.sh \
  --domain pcr.example.org \
  --reference-fasta /absolute/path/to/approved-reference.fasta \
  --database-id approved-reference-2026-09
```

Dependency-backed developer/native qualification:

```bash
python3 scripts/prepare-linux.py --sync-dependencies --provision-tools
python3 scripts/run-linux-qualification.py --full --require-functional-acceptance
```

The deployment is not considered scientifically ready until the bootstrap/release gate records a matching source build identity, scientific freeze, MAFFT bundle identity, approved specificity database and fresh compatible runner heartbeat.
