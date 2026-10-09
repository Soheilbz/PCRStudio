# Foundation acceptance evidence

Recorded 2026-10-09. This is acceptance of the first local foundation, not the entire non-scientific platform or a cloud-capacity/compliance certification.

## Current-source result

`./bootstrap` rebuilt the current API, static edge and tools, applied the migration history without pending changes and reached readiness through Caddy. The sole `./bootstrap check deep` completed with actual exit code 0 and all 31 checks passing. The report was independently parsed against the check entry point: unique matching names, every exit code zero and finite nonnegative elapsed time.

| Evidence | Result |
| --- | --- |
| PostgreSQL, Valkey, domain and executor-contract suite | 60 tests passed |
| Frontend unit regressions | 15 tests passed |
| Real Chromium/Caddy/Mailpit journeys | 3 passed |
| Operations unit checks | 13 passed |
| CSP generator checks | 8 passed |
| Backend types, lint, formatting and static security | Passed |
| Dependency checks | No known vulnerabilities reported; 70 locked Python packages and 317 artifacts independently matched primary PyPI hashes |
| OpenAPI/generated TypeScript, migrations and frozen locks | Passed |
| Frontend type, lint, format, build and dependency audit | Passed |
| Live isolation, SQL/query-log privacy and routed readiness | Passed |

The actual tools/runtime use Python 3.13.16 and cryptography 50.0.2. The vulnerable cryptography 49 release was upgraded, not excepted from scanning. Local service ports are loopback-only; API/edge are non-root with read-only filesystems, dropped capabilities and no-new-privileges. PostgreSQL runtime identity has neither DDL nor administrator authority.

The browser journeys cover verified email login, private project edits and two-tab version conflicts; actual MFA owner login, organization invitation, denied/ungranted access, grant removal, orphan recovery, revocation and rejoining; password reset and session invalidation. Ten rendered screenshots were reviewed across desktop, 320px mobile and both themes, including Account and dialogs. Tested surfaces had no Axe findings or horizontal clipping. Automated accessibility results do not certify full WCAG conformance.

Actual stop/bootstrap lifecycle comparison preserved configuration, secret bytes and complete core user/email/workspace/member/project/grant records. Only booleans and counts are retained in its public diagnostic artifact; no secret digest or scientific content was exported.

Local detailed evidence is deliberately ignored by Git: `.local/artifacts/gate.json`, `hardening-gate.log`, `final-gate-summary.json`, `runtime-inspection.jsonl`, `persistence-check.json`, `clean-bootstrap-proof.json` and `visual/`. An additional genuinely empty PostgreSQL volume proved first initialization, retained non-root supplemental groups, all three database identities and all 34 migrations; the temporary namespace was completely removed and existing secret bytes remained unchanged.

The same gate also passed on a fresh GitHub-hosted runner for validation-branch commit `5a92815eb2047be94bb405a62d1823ca74dff5f3`: [Foundation quality](https://github.com/Soheilbz/PCRStudio/actions/runs/37949388098), [Python/JavaScript CodeQL](https://github.com/Soheilbz/PCRStudio/actions/runs/37949388069) and [Dependency review](https://github.com/Soheilbz/PCRStudio/actions/runs/37949388085) all completed successfully. Workflow success does not establish that asynchronous CodeQL alert processing has completed; scanner alerts are separately reviewed. The remaining intentional group-read finding has the bounded false-positive assessment in [ADR 0005](../adr/0005-publication-and-scanner-hardening.md). The final published main commit and its checks must be separately confirmed.

## Independent review and fixed regressions

Independent read-only review confirmed the authorization and transaction boundaries, and found issues that were corrected and regression-tested:

- Existing password-only sessions cannot acquire privileged access merely because MFA was enrolled or a role promoted. Sensitive identity-provider recovery/credential endpoints also require recent factor proof.
- Account enrollment and confirmation remain reachable without fetching a forbidden workspace. A partially completed enrollment refreshes the profile even on a later error.
- Invitation email validation matches the PostgreSQL field boundary. SQL failures and Gunicorn request timeouts do not spill user/query payloads into operational logs.
- A real React Router root-matching defect required an explicit index route. Temporary read failures preserve drafts; parsed access denials settle before cache clearing, avoiding a repeat/loading loop.
- Native TOTP replay protection remains active. Synthetic browser helpers record the consumed enrollment code and wait for a genuinely fresh interval for subsequent authentication.

The original archive is unchanged; the new source contains no `_bmad` folder or methodology runtime. Remaining slices are private scientific files, durable execution, billing and production operations. The 100k-DAU workload, real VPS, off-host backup/restore and external providers remain separate release gates.
