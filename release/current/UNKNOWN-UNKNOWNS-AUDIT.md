# Independent unknown-unknowns audit

**Audit date:** 2026-09-09
**Scope:** current worktree, GitHub repository metadata and public Actions
evidence, dependency/release graph, security boundaries, deployment topology,
generated artifacts and maintainer documentation.

This is an independent readiness audit. Existing source-qualification results
were treated as evidence to inspect, not as proof that the surrounding GitHub
and deployment system was complete.

## Findings and disposition

| Area | Finding | Disposition |
| --- | --- | --- |
| Git provenance | Local `master` started at the same commit as remote `main`; the candidate is now a clean local commit on `release-candidate-20260909`, but publication could not authenticate from this host. | The reviewable branch is ready. No history rewrite or force-push is permitted; push requires the registered SSH private key or an HTTPS credential helper. |
| GitHub Actions runtime | The remote CI run at the baseline commit emitted a Node 20 deprecation warning for the pinned checkout action. | Resolved in the candidate by moving all actions to current immutable Node 24-compatible SHAs and adding bounded job timeouts. |
| Dependency review | No dependency-review workflow existed. | Resolved by adding `.github/workflows/dependency-review.yml`, failing on high severity changes with a pinned action. |
| Code scanning coverage | CodeQL covered Rust only even though the repository ships Rust, Python and TypeScript. | Resolved by adding Python and JavaScript/TypeScript CodeQL matrix entries with `none` build mode and retaining manual Rust build coverage. |
| Image SBOM portability | CI invoked `docker sbom`, a non-core Docker plugin unavailable on the audit host. | Resolved by using pinned Anchore SBOM action/Syft and retaining all image SBOMs as a 14-day CI artifact. |
| Image vulnerability gate | Public baseline CI failed the API image scan on ten HIGH Go standard-library findings in the pinned MFEprimer 4.5.1 binary (CVE-2026-25679, CVE-2026-27137, CVE-2026-27145, CVE-2026-32280, CVE-2026-32281, CVE-2026-32283, CVE-2026-33810, CVE-2026-33811, CVE-2026-33814 and CVE-2026-33818). | **Open external dependency gate.** The upstream distribution repository has no newer release or source tree for a repository-owned rebuild at audit time. Findings are not suppressed; the candidate is not GitHub-release-ready until an upstream-fixed artifact is adopted and requalified, or a security owner documents an explicit, time-bounded VEX decision with compensating controls. |
| Deployment topology | Deployment prose previously said the runner had outbound egress while Compose correctly keeps it on the internal data network only. | Resolved by making the deployment authority match Compose: API owns explicit external-reference egress; runner has no outbound network. |
| GitHub repository metadata | Public repository has no description or topics. | Requires authenticated repository-owner action; exact requested values are listed below. |
| GitHub security settings | Unauthenticated API inspection cannot read branch protection, Dependabot alerts, automated security fixes, secret scanning or push protection. | Requires authenticated owner inspection/action; exact requested values are listed below. |
| Cloud staging | No cloud host, deployment account, DNS zone, TLS endpoint or staging secrets were supplied. | The repository-supported Linux bootstrap and manual-only SSH staging workflow are complete and documented. Cloud execution remains an infrastructure boundary, not a hidden local claim. |

## Evidence inspected

- `git diff`, status, ignored-state policy, release packaging and generated
  manifest/SBOM/attestation/checksum relationships.
- `.github/workflows/*.yml`, Dependabot, CODEOWNERS, GitHub public repository
  metadata, remote branch heads and public Actions job metadata.
- `Cargo.toml`/`Cargo.lock`, root and Web package manifests/lockfile,
  `tools/pyproject.toml`/`tools/uv.lock`, Dockerfiles and Compose overlays.
- `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, deployment/operations guides,
  environment examples and current release evidence.
- authentication, secret-file, network, health/readiness, migration, backup,
  runner, scratch, logging and resource-limit boundaries in source and
  deployment configuration.

The baseline public Actions run showed successful source checks, dependency
contract, readiness contract, Linux source qualification and CodeQL. Its only
failed job was Linux image qualification, where the scan stopped the job before
SBOM generation. The annotations identify the vulnerable component as
`/opt/pcrstudio/tools/mfeprimer`, not the Debian base image or a mutable package
resolution.

## Required authenticated GitHub actions

These are account/repository settings, not source changes. The current host has
no authenticated GitHub administration capability, so they cannot be asserted
or changed here.

1. Set the repository description to: **“Evidence-first primer design and PCR
   workflow engineering platform.”** Add focused topics such as `pcr`,
   `primer-design`, `bioinformatics`, `rust`, `python`, `nextjs`, and
   `scientific-software`.
2. Keep `main` as the default branch. Protect `main` with pull requests,
   required review from `@Soheilbz`, stale-review dismissal, required status
   checks for every applicable CI/Linux/CodeQL/dependency-review job, branch
   up-to-date-before-merge, conversation resolution, and no force-push or
   branch deletion.
3. Enable dependency graph, Dependabot alerts, Dependabot security updates,
   secret scanning, and secret-scanning push protection. Review existing alerts
   before enabling automatic updates on production scientific dependencies.
4. Configure a `staging` environment only after the target server exists;
   environment secrets must be scoped to that environment and never repository
   plaintext.

## Release boundary

The repository-owned source, artifact, container, deployment and documentation
checks must remain green. The MFEprimer finding is deliberately carried as an
open gate rather than hidden by an ignore file or severity downgrade. The next
safe action is to obtain an upstream-fixed MFEprimer build or an authorized
security disposition, then rebuild and rerun the full image, runtime and
staging-shaped qualification against the exact resulting artifact.
