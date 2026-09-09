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
| Git provenance | The candidate is a clean local commit on `release-candidate-20260909`; the branch is now published to GitHub and remote `main` remains unchanged. | Resolved at the repository boundary. No history rewrite or force-push was used. |
| GitHub Actions runtime | The remote CI run at the baseline commit emitted a Node 20 deprecation warning for the pinned checkout action. | Resolved in the candidate by moving all actions to current immutable Node 24-compatible SHAs and adding bounded job timeouts. |
| Dependency review | No dependency-review workflow existed. | Resolved by adding `.github/workflows/dependency-review.yml`, failing on high severity changes with a pinned action. |
| Code scanning coverage | CodeQL covered Rust only even though the repository ships Rust, Python and TypeScript; the hosted Rust initializer also rejected the obsolete `manual` build mode. | Resolved by covering Rust, Python and JavaScript/TypeScript with the supported `none` build mode; Rust compilation and tests remain separate CI gates. |
| Image SBOM portability | CI invoked `docker sbom`, a non-core Docker plugin unavailable on the audit host. | Resolved by using pinned Anchore SBOM action/Syft and retaining all image SBOMs as a 14-day CI artifact. |
| Image vulnerability gate | Hosted image qualification failed the API image scan on 22 HIGH Go standard-library findings in the pinned MFEprimer 4.5.1 binary (`CVE-2026-25679`, `CVE-2026-27137`, `CVE-2026-27145`, `CVE-2026-32280`, `CVE-2026-32281`, `CVE-2026-32283`, `CVE-2026-33810`, `CVE-2026-33811`, `CVE-2026-33814`, `CVE-2026-33818`, `CVE-2026-39820`, `CVE-2026-39821`, `CVE-2026-39822`, `CVE-2026-39836`, `CVE-2026-42499`, `CVE-2026-42504`, `CVE-2026-46600`, `CVE-2026-56853`, `CVE-2026-56858`, `CVE-2026-56859`, `CVE-2026-56860`, and `CVE-2026-56862`). | **Open external dependency gate.** The latest hosted run is `34360729083`. The upstream distribution repository has no newer release or source tree for a repository-owned rebuild at audit time. Findings are not suppressed; the candidate is not GitHub-release-ready until an upstream-fixed artifact is adopted and requalified, or a security owner documents an explicit, time-bounded VEX decision with compensating controls. |
| Deployment topology | Deployment prose previously said the runner had outbound egress while Compose correctly keeps it on the internal data network only. | Resolved by making the deployment authority match Compose: API owns explicit external-reference egress; runner has no outbound network. |
| GitHub repository metadata | Public repository metadata was initially empty. | Resolved through the authenticated GitHub CLI: description and focused topics are now set for PCRStudio. |
| GitHub security settings | Ruleset and security controls were verified through the authenticated owner session. | Resolved: active `Protect main` ruleset blocks deletion/force-push, requires pull requests, one approval, Code Owner review, conversation resolution, up-to-date required checks, and the two available CI checks; dependency graph, Dependabot alerts/security updates, secret scanning/push protection and private vulnerability reporting are enabled. |
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

The latest hosted run for candidate commit `c956e42` passed source/Rust/Python/
Web checks, CodeQL, dependency review and Linux source qualification. Linux
image qualification completed all exact image builds and failed only at the
Trivy security scan on the 22 HIGH Go standard-library findings in
`/opt/pcrstudio/tools/mfeprimer/mfeprimer`. The candidate is open as PR #19. The
run does not indicate a Docker Hub, authentication, or mutable package-resolution
failure; exact pinned image pulls/builds completed successfully.

## Authenticated GitHub state and remaining owner actions

The authenticated owner session was used to inspect and update repository
settings. SSH remains the Git transport; it does not grant access to Actions
settings, environments, or secret values.

1. Keep `main` as the default branch. The active `Protect main` ruleset now
   enforces the safe subset available in the repository: pull requests, one
   approval, Code Owner review, stale-review dismissal, latest-push approval,
   conversation resolution, two required CI checks, branch freshness, and no
   force-push or deletion. CodeQL/dependency-review results are not required
   until those checks have a stable result on the protected branch.
2. Dependency graph, Dependabot alerts/security updates, secret scanning and
   push protection are enabled. No repository or environment secrets exist.
3. Configure a `staging` environment only after the target server exists;
   environment secrets must be scoped to that environment and never repository
   plaintext.

## Release boundary

The repository-owned source, artifact, container, deployment and documentation
checks must remain green. The MFEprimer finding is deliberately carried as an
open gate rather than hidden by an ignore file or severity downgrade. The next
safe action is to obtain an upstream-fixed MFEprimer build or an authorized
security disposition, then rebuild and rerun the full image, runtime and
staging-shaped qualification against the exact resulting artifact.
