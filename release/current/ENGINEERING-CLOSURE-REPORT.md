# PCRStudio Engineering Closure Report

Date: 2026-09-09
Status: **Non-biological engineering gates verified locally; Docker/OCI dependency access is stabilized and the production-shaped control-plane/edge drill passed. Native biological acceptance is outside the current scope.**

This report records the repository-wide verification pass performed against the
current source tree. It is intentionally explicit about external gates that
could not be completed, so a green local check is not mistaken for a green
production release.

## Initial baseline

- Repository root: `/home/soheil/Desktop/PCRStudio`.
- The working directory began at the canonical remote's baseline; the candidate
  is now committed on local branch `release-candidate-20260909`. The declared
  canonical remote is
  `https://github.com/Soheilbz/PCRStudio`; publication was attempted but the
  host has neither an HTTPS credential helper nor the private key for the
  account's registered SSH key.
- Canonical design modules: 21. Generated contract/runtime artifacts also
  contain 21 module identities.
- Existing source audit: 0 errors, 0 warnings.
- Secret scan: PASS for the current source tree; high-confidence credential
  formats were not found.
- Public-source archive: built and independently verified from the candidate;
  1,046 archive entries, with local caches, dependencies, build output and test
  output excluded. All 76 shebang-bearing archive members retain executable
  bits. The extracted archive also passed source audit and release verification.
- A fresh archive extraction installed the frozen JavaScript workspace and the
  `tools` development environment from local caches, then passed
  `scripts/qualify-source.py --no-write`. The exact project-local baseline is
  now installed and available: Node 24.20.0, pnpm 11.26.0, uv 0.12.10 and
  Rust 1.94.1.
- Against that same clean extraction, `pnpm --filter web check` passed typecheck,
  lint, formatting and Vitest: 49 test files passed with one skipped, and 619
  tests passed with seven skipped.

## Issue ledger summary

| ID | Finding | Severity | Status | Resolution/evidence |
| --- | --- | --- | --- | --- |
| E-001 | Host Rust 1.93.1 lacks the workspace-required Rust toolchain | P1 environment | VERIFIED | The project-local 1.94.x toolchain boundary was exercised; the current exact 1.94.1 pin is tracked separately in E-008 |
| E-002 | Docker Hub denied the exact pinned PostgreSQL manifest | P1 external | VERIFIED | Standard bearer-token access now returns HTTP 200 for the exact digest; the exact image pulled through the new OCI preflight, the production-shaped private Compose database reached healthy, and a custom-format backup/restore drill passed |
| E-003 | Production dependency advisory finding in Sharp through Next.js | P1 security | VERIFIED | Exact npm advisory access succeeded; the Sharp/libheif finding was remediated by updating Next.js 16.3.3 → 16.3.4, refreshing the lockfile, and obtaining `No known vulnerabilities found` from `pnpm audit --prod --audit-level=high` |
| E-004 | Browser/build origin mismatch could be mistaken for a `/try` product failure | P2 verification setup | VERIFIED | Smoke now defaults to `http://localhost:3100`; E2E rejects an explicit `PCR_E2E_BASE_URL`/`NEXT_PUBLIC_SITE_URL` mismatch before tests run; matching-origin E2E and `/try` pass |
| E-005 | Release metadata drifted during diagnosis | P2 release hygiene | VERIFIED | The diagnostic `/try` patch was removed; manifests, attestation, checksums, archive, and static-consistency artifacts were regenerated and verify clean |
| E-006 | This host lacks the strict native scientific artifacts/databases | P1 external | VERIFIED | Provisioned MAFFT, MFEprimer, BLAST+, PrimalScheme3 and PrimerPooler plus approved-reference indexes now hash-match; the strict verifier passes, `/ready/scientific` is HTTP 200, and the five-browser critical journey passes |
| E-007 | Authenticated unknown-module route streamed HTTP 200 instead of 404 | P2 product correctness | VERIFIED | The authenticated app layout now rejects unknown module IDs before streamed shell content; the five-browser regression and 21-module matrix pass |
| E-008 | Exact final patch-level toolchain cannot be installed on this host | P2 environment | VERIFIED | Project-local Node 24.20.0, pnpm 11.26.0, uv 0.12.10 and Rust 1.94.1 are installed; frozen installs and the non-biological exact qualification gates pass |
| E-009 | Docker BuildKit could not reach the npm registry while building the pinned Web image | P1 external | VERIFIED | The Web builder now inherits its already-materialized pinned pnpm 11.26.0 bundle from the dependency layer, eliminating the second hidden npm-registry fetch; the exact pinned Node image build, Next.js 16.3.4 build, file-backed Server Actions key, and read-only non-root HTTP smoke all passed |
| E-010 | Docker could not resolve the exact Rust base layer required by the production API/runner image | P1 external | VERIFIED | Persistent NetworkManager DNS repair restored canonical Docker Hub answers; the exact Rust digest pull passed, and clean API, runner, and migrator builds passed with the pinned identities |
| E-011 | Caddy healthcheck selected unavailable IPv6 loopback for `localhost` | P2 repository | VERIFIED | The edge probe now targets `127.0.0.1:2019` explicitly; the private loopback production-shaped Compose stack reached healthy and served an edge GET |

No unresolved repository defect remains in the exercised non-biological scope.
The production-shaped control-plane and edge Compose drill passed with exact
PostgreSQL, API, migrator, Web, and Caddy artifacts. The scientific runner
was intentionally not accepted because native biological/toolchain acceptance
is outside the current user scope; its strict preflight remains fail-closed.

## Architecture

The repository remains a layered modular monolith: Next.js web boundary, Rust
workspace/core and server/API crates, Python scientific/tooling layer,
PostgreSQL persistence, and generated contract/release artifacts. Browser code
does not receive the API address; the guest `/try` flow uses a server action and
the same canonical API contract as authenticated workspaces.

The repository-driven capability inventory found 35 web route/page/handler
files, 10 Rust crates, 49 Rust route registrations, 82 Python test files, 15
ordered PostgreSQL migrations, six Compose services (`db`, `migrate`, `api`,
`runner`, `web`, `caddy`), 58 canonical HTTP endpoints, 11 engines, 12 tooling
contracts, and 21 module registry entries. The inventory also confirmed import/
export handlers, shared-run links, account recovery, rate limiting, runner
leases, sequence assets, attachments, assay qualifications, operator metrics,
health/readiness routes, and release-generation tooling as in-scope capabilities.

## Removed or retained historical/legacy material

No broad deletion was performed. Historical release material remains under
`release/baseline`; generated current artifacts remain authoritative for the
candidate. The diagnostic `/try` source patch was removed after the verified
root cause was found; no unnecessary product source change remains.

## Modernization

- Web stack verified on Next 16.3.4 with the repository's breaking-change
  guidance read before editing.
- The obsolete `experimental.useTypeScriptCli: false` workaround was removed
  after the Next 16.3.4 upgrade; the documented project-local TypeScript CLI
  default now runs successfully in the production build.
- The final source pins the authoritative patch-level baseline: Node 24.20.0,
  pnpm 11.26.0, uv 0.12.10 and Rust 1.94.1. All non-biological exact
  qualification gates were re-run on that baseline, including frozen installs,
  Rust checks, the Python environment sync, the web suite, production build,
  and npm advisory audit.
- Standalone Next output was exercised through `web/scripts/start-standalone.mjs`.
- Release manifests, static consistency artifacts, and deterministic source
  attestation were regenerated for the final source state.

The dependency/toolchain audit date is 2026-09-08. Node 24.20.0 is the
current Node 24 LTS release listed by the [official Node release
schedule](https://nodejs.org/en/about/previous-releases); uv 0.12.10 is the
current upstream release listed by [Astral's uv release
history](https://github.com/astral-sh/uv/releases); pnpm 11.26.0 is the current
pnpm 11 release listed by the [official pnpm release
history](https://github.com/pnpm/pnpm/releases); and Rust 1.94.1 is the patch
release documented by the [Rust release notes](https://doc.rust-lang.org/releases.html).
Python 3.14 remains the CI major/minor baseline; the upstream documentation
lists 3.14.7 as the current maintenance release. The exact updated binaries
are installed under the project-local `.local` toolchain root and were
exercised for the non-biological gates recorded below.

## Database and migrations

The local PostgreSQL 18 cluster on `127.0.0.1:55432` accepted the configured
test connection. DB-backed Rust tests passed with that database. The exact
pinned Docker PostgreSQL image now pulls through the standard bearer-token
flow. Its Compose dev database reached healthy, and an exact-image custom-
format backup/restore probe passed; no digest was loosened and no substitute
image was used. Independently, a host-native PostgreSQL 18 custom-format
dump/restore into an isolated temporary PostgreSQL 18 instance passed: 15
migrations, 16 public tables, and zero unvalidated public constraints. This
proves database backup bytes can restore locally. The new OCI preflight also
resolved all three Docker Hub endpoints and pulled the exact five digest-pinned
external references used by the production build/runtime path.

## Security

Source audit, secret scan, static qualification, security-header smoke checks,
and browser-origin behavior passed. The origin guard correctly rejected the
deliberately mismatched `127.0.0.1`/`localhost` Server Action request with 403,
then accepted matching-origin requests. Production headers include CSP,
frame/resource isolation, referrer policy, permissions policy, and content
sniffing protection.

## Web and UX

The integrated `pnpm check` pass passed: web checks reported 49 test files
passed, 1 skipped; 619 tests passed, 7 skipped; Python passed 1,167 tests in
  1,353.97 seconds; and Rust clippy plus the complete workspace test/doc-test
suite passed. Production build passed. The rebuilt standalone server passed
the 12-route smoke gate within the 1,500 ms budget; the latest sampled route
was 68 ms. Full browser E2E passed with a matching origin: 170 passed and 30
intentionally skipped across Chromium, Firefox, WebKit, mobile Chrome, and
mobile Safari. The strict-runtime recheck then passed the authenticated
critical journey in all five browser projects, including mobile Safari. The
`/try` matrix passed 10 of 10 in the standalone deployment-shaped run.
API-backed verification also passed the five-browser 21-module workspace
matrix and the five-browser authenticated unknown-module 404 regression. The
strict engine execution suite passed 10 of 10 browser-project cases, covering
the five current engine workspaces through browser → Next → Rust → Python
result rendering, including mobile Safari. The
earlier Mobile Safari timeout was reproduced as a strict-runtime symptom and
closed after the provisioned strict toolchain was loaded; it is not hidden as
a UI success.

The rendered audit covered desktop and 390px mobile views of sign-in, `/try`,
and documentation surfaces. All sampled routes returned expected content,
showed no horizontal overflow, emitted no browser console errors, and had no
broken visible images. Screenshots were inspected for clipping, hierarchy,
control reachability, footer/header behavior, and mobile stacking.

The existing `/try` action was validated to preserve the submitted sequence
and return an honest transport error when the design core is unavailable, once
the browser and build use the same configured public origin.

## Scientific/modules

All 21 canonical module IDs, generated module contracts, engine contracts, and
static scientific consistency gates passed. The independent strict toolchain
verifier passed with hash-matched native artifacts, approved-reference indexes,
and the approved scientific-Python freeze; `/ready/scientific` returned HTTP
200, the authenticated critical journey passed in all five browser projects,
and the strict engine execution suite passed 10 of 10 browser-project cases.
Those historical scientific results are retained as evidence, but no new
native biological acceptance was attempted in the current non-biological pass.

## Runtime and operations

Linux bootstrap source regression passed. The exact pinned PostgreSQL image,
API/runner/migrator builds, and private loopback production-shaped Compose
path were exercised successfully. PostgreSQL reached healthy, migrations
completed, API `/health` and `/ready` passed, Web and Caddy healthchecks
passed, an edge GET passed, backup/restore passed with 15 migrations and 16
tables, and restart/recreation with `--no-build` reused local artifacts. An
independent second disposable private-loopback Compose pass repeated the
database bootstrap, migrations/readiness, backup/restore, edge GET, and
restart/recreation checks successfully.
Native biological acceptance is outside the current scope; the runner's
strict scientific preflight therefore remained fail-closed. The standalone
launch path is verified and is the correct path for this `output: standalone`
configuration.

## Docker/OCI dependency stabilization

The recurring Docker failure was host-side, not an image or digest problem.
The active NetworkManager connection was accepting a DHCP resolver at
`192.168.168.125` that returned broken/noncanonical Docker Hub answers for
`auth.docker.io`; `systemd-resolved` also changed default routes when the
intermittent `tun0` appeared. The host had no usable IPv6 default route, so
Docker's dual-stack attempts added misleading IPv6/network errors. No HTTP,
HTTPS, or daemon proxy was configured, and the public pinned images did not
require credentials.

The active connection was durably changed to use approved public resolvers
`1.1.1.1,8.8.8.8` with auto-DNS disabled and then reapplied. `resolvectl`
returned canonical Docker Hub answers, and the exact pinned Rust pull passed
immediately afterward. The repository now runs an early OCI preflight that
checks IPv4 resolution for `auth.docker.io`, `registry-1.docker.io`, and
`production.cloudfront.docker.com`, reports IPv6 as an address-family
condition, enumerates the five exact digest-pinned external references, and
pulls them through Docker's normal credential helper. Only classified transient
transport failures retry with finite exponential backoff; DNS, auth,
rate-limit, TLS, and digest/pin failures stop without substitution. Each pull
also has a finite 180-second timeout, and the preflight probes the auth token
service, registry bearer boundary, and CloudFront CDN over HTTPS without
printing response bodies or credentials.

The Web Dockerfile also now retains the materialized pinned pnpm bundle between
dependency and builder stages, preventing a second hidden npm-registry fetch
after source changes invalidate the build layer. No mirror, insecure registry,
tag fallback, TLS bypass, or credential was added.

## CI and supply chain

Release verification passed with 1,050 manifest files, 914 SBOM components, 34
checksum entries, zero manifest/checksum mismatches, zero case collisions, and
zero symlinks. The public-source archive verifier and extracted-archive audit
also passed. Pinned container and GitHub Actions references were reported by
the verifier. The exact `pnpm audit --prod --audit-level=high` now completes
with no known vulnerabilities after the Next.js 16.3.4 update. The exact
Node/pnpm/uv/Rust baseline is installed and the non-biological qualification
gates pass on it.

## Architecture fitness functions

Static source audit, generated-contract qualification, canonical static audit,
secret scan, release verification, build/type/lint/format checks, Rust
fmt/clippy/tests, Python tests, web smoke, and browser E2E all passed in the
available environment.

## Performance

The production smoke gate measured all public routes under the configured 1,500
ms budget. The latest rebuilt standalone smoke run reported the slowest sampled
public route at 68 ms; the route set was non-empty and returned expected
content types.

## Change provenance and cleanup

- The verified root cause for the `/try` failure was a build/test origin
  mismatch: `127.0.0.1` was tested against a build configured for `localhost`.
  The 403 was the intended origin policy, not an application error.
- The smoke/E2E origin contract is now structurally protected: the local smoke
  default matches Playwright's `localhost` default, and an explicit external
  E2E target must match the configured public origin.
- The authenticated module route had a real streamed-404 defect. The layout now
  rejects unknown module IDs before shell content can stream, and the focused
  five-browser regression is green.
- A temporary guarded-normalization patch was introduced during diagnosis and
  removed after that hypothesis was disproven; no origin-policy weakening or
  unrelated fallback was kept.
- Release metadata, the current evidence index and the closure report are
  intentional permanent evidence;
  generated caches, browser traces, and temporary diagnostic outputs are not
  part of the release manifest. The final source audit reports zero cache
  residue and zero whitespace errors.
- Six stale local Next/API verification process groups from earlier acceptance
  runs were identified by their ports and launch commands, then stopped before
  the final fresh-archive passes; no application or test server remains
  listening on the verification ports.
- Generated `.next`, Playwright report/result, and pytest cache directories were
  removed from the working tree after verification; they remain excluded from
  the public archive.
- The unrelated root-level MetaTrader/desktop-tool installer and the
  Next-generated `web/AGENTS.md`/`web/CLAUDE.md` guidance files were removed
  after reference checks found no product, build, release, or documentation
  dependency; no active ignore or build rule refers to those paths.
- No orphan, speculative, debug-only, or test-only bypass change was found in
  the final source change set.
- The final dependency pin modernization is traceable to the 2026-09-08
  authoritative upstream audit; the exact non-biological runtime
  requalification is recorded under E-008.
- The temporary `/try` fallback remains absent; `web/src/lib/try/actions.ts`
  retains the original honest error path.
- A disposable clean checkout of the canonical remote at commit
  `51c94f009048ff60fd3c93c17a63caeb9edcd08d` was reconciled against the
  current candidate by content hash. Candidate-only additions are limited to
  current evidence and supporting audit/test helpers; the working directory is
  rooted at that canonical commit and all changes remain uncommitted for human
  review.

## Assurance-gap and fitness-function review

| Invariant | Enforcement | Verification |
| --- | --- | --- |
| Canonical module/engine/API projections do not drift | Generator and differential-contract checks | `qualify-source.py --no-write`, Rust tests: PASS |
| Secrets and local source hygiene stay safe | High-confidence scan and static audit | `scan-secrets.py`, `audit-source.py`: PASS |
| Release bytes match their manifests | Deterministic manifest, checksum, SBOM, and attestation verification | `verify-release.py`: PASS |
| Browser mutations use the configured public origin | Shared origin classifier, proxy guard, smoke default, and E2E preflight | Matching-origin E2E PASS; mismatch independently observed as 403; preflight now fails early |
| Worker and request boundaries fail closed | Rust worker/client tests and API contract tests | Integrated `pnpm check`: PASS |
| Unknown module IDs cannot become successful pages | Closed module binding plus authenticated layout boundary | Five-browser HTTP 404 regression PASS |

These checks are discoverable in the repository and are run by the relevant
Linux qualification/CI workflows; no hidden suppression was introduced.

## Surprise-resistance assurance

- Independent browser evidence caught the origin/configuration mismatch rather
  than allowing a false application failure.
- The deployment-shaped standalone launcher was tested separately from
  `next start`.
- The unavailable-core `/try` path was exercised and remained readable with
  the pasted sequence intact.
- Release artifacts were re-verified against the final source state.
- The host-native PostgreSQL dump/restore path passed in an isolated temporary
  cluster; the exact-image Compose dev database backup/restore probe also
  passed. The non-biological production-shaped control-plane/edge Compose
  drill also passed, including restart/recreation from local artifacts.
- The public-source archive was extracted into a fresh temporary directory and
  passed source audit and release verification independently of the working
  tree; its archive check reported 77 shebang members and zero missing
  executable bits.

## Assumption register

| Assumption | Status and evidence |
| --- | --- |
| The public archive contains only intended source/evidence | VERIFIED: 1,054-entry archive; extracted audit and release verification passed; ignored caches/dependencies/build output absent |
| The exact pinned Docker image can be pulled by a release host | VERIFIED: OCI preflight resolved all Docker Hub endpoints and pulled all five exact digest-pinned external references; Compose database/bootstrap and backup/restore passed |
| The official npm advisory service is reachable for the final audit | VERIFIED: exact `pnpm audit --prod --audit-level=high` returned no known vulnerabilities after the Next.js/Sharp remediation |
| Strict scientific execution artifacts and approved reference data are present | VERIFIED: strict toolchain verifier PASS; all required artifacts/indexes and the approved scientific-Python freeze hash-match; `/ready/scientific` HTTP 200 |
| The current directory proves canonical Git lineage | VERIFIED: local Git HEAD is canonical commit `51c94f009048ff60fd3c93c17a63caeb9edcd08d`; the candidate remains an explicit uncommitted review diff |
| Standalone output is the deployable Web runtime | VERIFIED: deployment-shaped standalone launch, smoke and browser checks passed |
| The final patch-level toolchain can be exercised on this host | VERIFIED for non-biological gates: exact Node, pnpm, uv and Rust are installed and exercised |

## Two-pass fixed-point status

The broad local verification pass completed before the final patch-level
toolchain pin update and passed except for the documented external blockers.
After the pin update, the non-biological exact source, Python, Rust, web,
security, and release gates passed. Two consecutive fresh public-archive
extractions then passed exact dependency installation, source qualification,
and the complete web check. This establishes a non-biological two-pass fixed
point. The full mission-level two-pass requirement remains **UNVERIFIED**
because the biological acceptance suite was not re-run by explicit user scope;
the non-biological production-shaped Compose drill is verified below in two
independent disposable passes. E-009,
E-010, and E-011 are resolved by the exact image/build and lifecycle evidence
recorded below.

## Verification matrix

| Gate | Result |
| --- | --- |
| `python3 scripts/audit-source.py` | PASS |
| `python3 scripts/scan-secrets.py` | PASS |
| `python3 scripts/qualify-source.py --no-write` | PASS |
| `python3 scripts/verify-release.py --root ...` | PASS: 1,050 manifest files; 914 SBOM components; 34 checksum entries |
| `python3 scripts/check-linux-bootstrap.py` | PASS |
| `python3 scripts/doctor-linux.py` | PASS; `.env` hardened to mode `0600` |
| Integrated `pnpm check` with project-local Rust and local PostgreSQL | PASS: web 619 passed/7 skipped; Python 1,167 passed; Rust workspace and doc-tests passed |
| Web production build | PASS |
| Clean public-archive Web check after offline frozen-lockfile install | PASS: typecheck, lint and formatting; 49 test files passed/1 skipped and 619 tests passed/7 skipped |
| Standalone production smoke | PASS |
| Browser E2E, matching public origin | 170 PASS / 30 intentional skips; five-browser matrix |
| API-backed module matrix | 21 modules × 5 browser projects: PASS |
| Strict engine execution suite | 10 PASS: five current engine workspaces through browser → Next → Rust → Python result rendering |
| Authenticated unknown-module HTTP contract | 5 browser projects: PASS after repository fix |
| Rust fmt/clippy/workspace tests | PASS on exact project-local Rust 1.94.1 |
| Python suite | 1,167 PASS |
| Host-native PostgreSQL dump/restore | PASS: isolated PostgreSQL 18 restore; 15 migrations, 16 public tables, 0 unvalidated constraints |
| Public-source archive build and extracted-archive verification | PASS: 1,054 entries; 77 shebang members with zero missing executable bits; fresh offline dependency installation and extracted source qualification, audit and release verification PASS on the exact project-local baseline |
| Supported Compose backup/restore drill | PASS in two independent disposable non-biological production-shaped passes: migrations, custom-format backup/restore (15 migrations, 16 tables), API/Web/Caddy readiness, edge GET, and restart/recreation all passed |
| Docker/OCI dependency preflight | PASS: all three Docker Hub endpoints resolved; exact pinned Caddy, Node, PostgreSQL, Python, and Rust references pulled and matched their requested digests |
| Docker PostgreSQL bootstrap | PASS: exact pinned image pulled and private production-shaped Compose database reached healthy |
| npm production advisory audit | PASS: exact `pnpm audit --prod --audit-level=high` reports no known vulnerabilities after the Next.js 16.3.4 update |
| Strict scientific readiness | PASS: strict verifier passed; required artifacts, approved-reference indexes and scientific-Python freeze hash-match; `/ready/scientific` HTTP 200 |
| Strict-runtime authenticated critical journey | PASS: 5 browser projects |
| Exact final dependency/toolchain requalification | PASS for non-biological gates: exact Node 24.20.0, pnpm 11.26.0, uv 0.12.10 and Rust 1.94.1 |
| Two-pass fresh archive verification | PASS for non-biological gates: two fresh exact archive extractions, frozen installs, source qualification, and web checks; each 619 passed/7 skipped |
| Deployable Web Docker image build and runtime smoke | PASS: exact pinned Web image built successfully; read-only non-root container served `/` with all capabilities dropped |
| Production API/runner image build | PASS: clean exact-pinned API and runner images built after the OCI preflight; migrator build also passed |

## Remaining exceptions

The non-biological production-shaped control-plane and edge Compose bootstrap
and drill passed on this host. Native biological acceptance is intentionally
deferred under the user's current scope; the scientific runner's strict
preflight remains fail-closed rather than being waived. That is a scope
boundary, not a registry or production control-plane blocker.

The repository/live boundary is explicit: the current source candidate has
verified static, web, API-contract, local database, browser, and release-
artifact evidence, but no live deployment, production domain, production
secrets, or production database was touched. The candidate is committed in a
clean local worktree, while the canonical GitHub remote remains unchanged
because HTTPS and SSH publication both lacked usable host credentials.

For E-002, the registry-access removal condition is met: the exact pinned
`postgres:18-alpine@sha256:d3e1620b...` image was pulled and started through
the dev database Compose path, and the exact-image restore probe passed. The
production-shaped control-plane/edge stack drill also passed. E-003 is resolved by the successful exact audit after
the Next.js 16.3.4/Sharp remediation.
E-006 is resolved by the strict verifier, hash-matched artifact evidence,
approved-reference indexes, HTTP readiness, and the five-browser critical
journey recorded above. E-009 is resolved by the exact pinned Web image build
and runtime smoke from the repository-supported Docker path. E-010 is resolved
by persistent host DNS repair, exact digest pulls, and clean API/runner/migrator
builds. E-011 is resolved by the IPv4-specific Caddy health probe. E-008 is
resolved for the non-biological scope by successful installation and
requalification with the pinned Node 24.20.0, pnpm 11.26.0, uv 0.12.10 and
Rust 1.94.1 baseline.

## Production commands

```text
python3 scripts/audit-source.py
python3 scripts/scan-secrets.py
python3 scripts/qualify-source.py --no-write
python3 scripts/verify-release.py --root /home/soheil/Desktop/PCRStudio
pnpm --filter web check
pnpm --filter web build
pnpm --filter web start:standalone
pnpm web:smoke -- --url=http://localhost:3400
```

## Completion statement

PCRStudio is a locally verified release candidate with strong static, web,
Rust, Python, database, browser, Docker/OCI, and release-artifact evidence.
The non-biological production-shaped control-plane/edge Compose drill passed,
including migrations, readiness, backup/restore, restart, and recreation from
cached local artifacts. Native biological acceptance remains intentionally
outside the current scope. Live deployment remains a separate pending phase.
