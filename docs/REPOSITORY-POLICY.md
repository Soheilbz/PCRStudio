# PCRStudio repository policy

This is the current-state policy for the public source tree. The repository
should describe the current product and its supported workflows, not accumulate
internal checkpoints or workstation state.

## Canonical boundaries

- Product implementation lives in `crates/`, `tools/`, `web/`, and `contracts/`.
- Operational entrypoints and release generators live in `scripts/` and the
  small, documented root launchers.
- Maintainer guidance lives in `README.md`, `CONTRIBUTING.md`, `SECURITY.md`,
  `docs/`, `knowledge/`, and the active `release/` authorities.
- Current release evidence lives in `release/current/`; its map is
  `release/current/README.md`, and its candidate-wide report is the
  `current_report` named by `release/release.toml`.
- Generated projections, manifests, SBOMs, attestations, and runtime data are
  retained only where a build, runtime, test, or release verifier consumes
  them. Their canonical sources must be updated first; generated files are not
  hand-edited.
- Local environments, credentials, caches, build output, test output, and
  generated agent guidance belong under ignored paths such as `.local/`,
  `node_modules/`, `target/`, `tools/.venv/`, `web/.next/`, and test-output
  directories.

## Documentation and history

One document owns each active concern. Indexes route maintainers to that owner;
they do not copy its claims. ADRs, migrations, changelogs, legal/security
records, compatibility rationale, and release provenance are durable records.
Debugging reports, intermediate closure snapshots, superseded checklists, and
duplicate “current/latest/final” summaries are removed once their useful facts
are incorporated into the current authority. They remain recoverable through
Git history or the immutable release baseline when provenance requires it; they
are not copied into the active documentation tree.

## Residue and deletion rule

Before removing or moving a file, search code, CI, scripts, manifests, build
configuration, deployment files, and documentation for its path and basename.
Keep a file only when that search finds a live dependency or a documented
current purpose. After a structural change, repair indexes and generated
metadata, then run source qualification, release verification, link/path checks,
and the relevant product tests.

Agent, cloud-assistant, IDE, vendor-specific, and unrelated workstation files
are not product documentation. Generated local guidance is ignored; an
unreferenced installer or tool note is removed rather than promoted into the
supported developer workflow.
