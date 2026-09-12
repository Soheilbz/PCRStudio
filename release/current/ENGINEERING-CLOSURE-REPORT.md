# PCRStudio Engineering Closure Report

Date: 2026-09-12
Status: **OPEN. The 2026-09-09 non-biological verification remains historical evidence, but the current GitHub candidate has failing CI and an incomplete required-check ruleset. Local fixes are verified; hosted requalification and branch-rule correction remain pending.**

This is the canonical current engineering-closure report. It preserves the
verified 2026-09-09 baseline below and records the newer candidate state
separately; historical evidence is not presented as proof that the current
candidate or a live deployment is green.

## Current GitHub and local state (2026-09-12)

- The canonical repository is `Soheilbz/PCRStudio`; default branch is `main`.
  At the last remote read before this correction, PR
  [#39](https://github.com/Soheilbz/PCRStudio/pull/39) was open from
  `codex/final-readiness-20260912` at `fbb8559af7f892a7f2dc79a656708e216833abcd`
  against `599c736f63bb964fe2834d25785f7d69c154bdef`.
- Its latest observed CI run, [34720256104](https://github.com/Soheilbz/PCRStudio/actions/runs/34720256104),
  failed. The source job completed all 1,167 Python tests and the audits, then
  stopped at Rust formatting. The final qualification job also failed because
  it ran the repository script without first checking out the source.
- Root causes were corrected locally: the Rust test now matches Rust 1.94.1
  formatting; the aggregate job has a read-only checkout with persisted
  credentials disabled; and a dependency-free regression check protects that
  checkout-before-script invariant. Local evidence: all 41
  `pcr-server` API integration tests passed, targeted Clippy passed, Rust
  formatting passed, and `scripts/check-linux-bootstrap.py` passed.
- The full locked Python suite passed locally under four `pytest-xdist`
  workers: 1,167 passed in 610.09 seconds. The prior hosted serial run took
  1,489.54 seconds for the same suite; these are different machines, so the
  timing comparison is indicative, not a controlled benchmark. CI now uses a
  bounded four-worker `loadscope` run; hosted timing and result are pending.
  The local profile disabled pytest's cache provider, which produced expected
  unknown-`cache_dir` warnings; CI keeps the cache provider enabled and sets
  `PYTHONDONTWRITEBYTECODE=1`. Local bytecode created by the profile was removed.
- All four `astral-sh/setup-uv` uses in CI and production qualification now set
  `prune-cache: true`. The pinned action supports this input; upstream documents
  that it removes prebuilt wheels before persisting the GitHub Actions cache,
  while retaining wheels built from source. A source-contract assertion keeps
  future setup-uv uses from silently reverting to unpruned cache saves. This
  controls reusable CI cache size; it is separate from host-local Cargo output
  and application/server storage. The cache-size effect is not separately
  quantified.
- The active `Protect main` ruleset currently requires only
  `Fast feedback and targeted contracts` and `Web production and browser
  qualification`; it does not require `Required PCRStudio qualification`.
  This is the last authenticated API observation; the ruleset could not be
  re-read during this pass. Per the contributor policy, its change must follow
  a successful hosted run of the corrected aggregate gate. No merge, release,
  or deployment has been performed; `main` remains untouched.
- At that public read, PR #39 was open at `fbb8559`; its latest then-observed
  CI run was failing (29m58s), with source qualification and the aggregate
  gate failed. The accepted MFEprimer findings remain visible as
  notices under the documented exception; they were not suppressed. That
  failed run predates the local corrections above and cannot qualify them.
- An initial GitHub read attempt timed out, but follow-up isolation succeeded:
  DNS resolves both GitHub hosts, direct unauthenticated HTTPS returned HTTP
  200 for `github.com` and `api.github.com`, `git ls-remote` returned the
  expected branch SHA, and authenticated PR/ruleset reads succeeded. No
  persistent auth, DNS, proxy, or transport fault remains evidenced; the first
  timeout was transient.
- Generated release manifests and the source attestation have now been
  refreshed after the report/workflow changes. Local release verification
  passes with 1,058 manifest files, 914 SBOM components, 28 checksum entries,
  zero mismatches, zero case collisions, and zero symlinks. Hosted review is
  still pending because these local changes have not been pushed.

## Initial baseline (verified 2026-09-09)

- The candidate is committed on branch `release-candidate-20260909` and
  published to the canonical GitHub repository. Remote `main` remains
  protected and unchanged until the normal pull-request merge process.
- Canonical design modules: 21. Generated contract/runtime artifacts also
  contain 21 module identities.
- Existing source audit: 0 errors, 0 warnings.
- Secret scan: PASS for the current source tree; high-confidence credential
  formats were not found.
- Public-source archive: built and independently verified from the candidate;
  1,055 archive entries, with local caches, dependencies, build output and test
  output excluded. All 80 shebang-bearing archive members retain executable
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
| E-012 | Hosted image qualification reports HIGH Go standard-library findings in the pinned MFEprimer 4.5.1 binary | P1 external security | ACCEPTED-TEMPORARILY | `SEC-EXC-2026-09-MFEPRIMER-451` records the exact executable hash, target path, package/version, severity and CVE allowlist with review-by `2026-10-09`; Trivy findings remain visible and any mismatch fails closed |
| E-013 | Rust formatting failure in the current PR's HTTP body-limit regression test | P2 CI correctness | FIXED | Rust 1.94.1 formatting check passes locally; all 41 `pcr-server` API tests pass. The corrected hosted CI run is pending |
| E-014 | Aggregate qualification job invoked a repository script without checkout | P1 CI enforcement | FIXED | Added least-privilege checkout (`contents: read`, `persist-credentials: false`) and a fast regression assertion. Local aggregate-gate and bootstrap checks pass; hosted requalification is pending |
| E-015 | Full Python suite ran serially for 1,489.54 seconds in hosted CI | P2 feedback latency | FIXED | CI now uses the already-locked `pytest-xdist` with four workers and module-scope scheduling; the same 1,167 tests passed locally in 610.09 seconds. Hosted timing is pending |
| E-016 | `Protect main` does not require the aggregate qualification check | P1 branch protection | OPEN | GitHub's active ruleset currently requires only fast feedback and Web qualification. Require the aggregate after GitHub observes its corrected successful run; no settings change has yet been made |
| E-017 | GitHub Actions persisted the full uv cache without pruning | P2 CI storage hygiene | FIXED | All four pinned setup-uv uses now prune before saving, guarded by `check-linux-bootstrap.py`; the cache-size effect has not been separately measured |
| E-018 | Transient GitHub HTTPS timeout during initial remote verification | P2 external connectivity | RESOLVED | Follow-up direct HTTPS requests returned HTTP 200, `git ls-remote` returned the exact remote branch SHA, and authenticated PR/ruleset reads succeeded; no continuing network or credential issue was observed |

At the 2026-09-09 checkpoint, no unresolved repository-owned defect remained
in the exercised non-biological scope. That statement does not cover the
current PR #39 findings above. The production-shaped control-plane and edge
Compose drill passed with exact PostgreSQL, API, migrator, Web, and Caddy
artifacts. The scientific runner was intentionally not accepted because
native biological/toolchain acceptance is outside the current user scope; its
strict preflight remains fail-closed. E-012 remains a visible, time-bounded
security condition rather than being treated as remediated. The final GitHub
release is created only after the exact release archive and current generated
evidence are rebuilt and verified from the release commit.

## Prior release baseline and historical qualification (2026-09-09)

The following sections preserve the evidence from the earlier candidate. They
are not evidence that the current PR's hosted checks or production deployment
have completed.


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

## Current-state repository policy

The active tree keeps one canonical report for the release-wide state and one
authority for each scoped concern. The obsolete engine-maturity snapshot and
the independent unknown-unknowns checkpoint were removed after their durable
facts were reconciled here. Migrations, ADRs, security records, generated
provenance and the immutable `release/baseline` remain. The diagnostic `/try`
source patch was removed after the verified root cause was found; no
unnecessary product source change remains.

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

Release verification passed with 1,051 manifest files, 914 SBOM components, 28
checksum entries, zero manifest/checksum mismatches, zero case collisions, and
zero symlinks. The public-source archive verifier and extracted-archive audit
also passed. Pinned container and GitHub Actions references were reported by
the verifier. The exact `pnpm audit --prod --audit-level=high` now completes
with no known vulnerabilities after the Next.js 16.3.4 update. The exact
Node/pnpm/uv/Rust baseline is installed and the non-biological qualification
gates pass on it.

The runs `34399728139`, `34399728117`, `34399728175`, and `34399728242` and
PR #19 are historical evidence from the 2026-09-09 candidate, not the current
GitHub state. Current PR #39 and its failing run are recorded at the top of
this report. The pinned MFEprimer 4.5.1 findings, including
`CVE-2026-33818`, remain visible under the exact time-bounded exception. No
image identity, digest, TLS, provenance, or scan policy was weakened.

The same hosted run still contains a PostgreSQL `no usable system locales`
warning from the pinned Alpine image's missing `locale` utility. The image
starts with the requested `C` locale and reaches readiness; removing this
upstream informational message would require replacing or rebuilding the
pinned PostgreSQL image, so it is retained as a documented external warning
and is not hidden by log filtering. Other remaining text warnings are likewise
limited to Trivy's vendor-severity notice, Debian package post-install
manpage notices, and an upstream `genome.c` compiler warning; none is a
PCRStudio-owned defect or is suppressed by CI.

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
  rooted at that canonical commit; the candidate is now represented by the clean
  published review branch `release-candidate-20260909`.

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
  tree; its archive check reported 80 shebang members and zero missing
  executable bits.

## Assumption register

| Assumption | Status and evidence |
| --- | --- |
| The public archive contains only intended source/evidence | VERIFIED: 1,055-entry archive; extracted audit and release verification passed; ignored caches/dependencies/build output absent |
| The exact pinned Docker image can be pulled by a release host | VERIFIED: OCI preflight resolved all Docker Hub endpoints and pulled all five exact digest-pinned external references; Compose database/bootstrap and backup/restore passed |
| The official npm advisory service is reachable for the final audit | VERIFIED: exact `pnpm audit --prod --audit-level=high` returned no known vulnerabilities after the Next.js/Sharp remediation |
| Strict scientific execution artifacts and approved reference data are present | VERIFIED: strict toolchain verifier PASS; all required artifacts/indexes and the approved scientific-Python freeze hash-match; `/ready/scientific` HTTP 200 |
| The current directory proves canonical Git lineage | VERIFIED: this checkout has real Git metadata and tracks `origin/codex/final-readiness-20260912`; current PR #39 is open against `main`. This does not imply that PR is merged or that `main` contains the candidate |
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
| `python3 scripts/verify-release.py --root ...` | PASS: 1,051 manifest files; 914 SBOM components; 28 checksum entries |
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
| Public-source archive build and extracted-archive verification | PASS: 1,055 entries; 80 shebang members with zero missing executable bits; fresh archive qualification, audit and release verification PASS on the exact project-local baseline |
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

The repository/live boundary is explicit: prior evidence covers static, Web,
API-contract, local database, browser, and release-artifact paths, but no live
deployment, production domain, production secrets, or production database was
touched. The current review branch is published, but the local corrections in
this report are not yet on GitHub; the latest hosted run is not green. Remote
`main` remains unchanged. The pinned MFEprimer findings remain a visible
external security exception that must be re-reviewed by `2026-10-09`.

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

## Current closure statement

**Engineering closure is not achieved.** The current candidate still needs the
local fixes to be reviewed by a successful hosted PR #39 run and the `main`
ruleset to require the successful aggregate gate. Local release manifests are
current and verified. Live deployment remains a later, separate phase.
Native biological acceptance remains outside the current scope; the scientific
runner remains fail-closed rather than waived.
