# Contributing to PCRStudio

PCRStudio combines application code with scientific design contracts. Changes
must preserve both software correctness and scientific provenance.

## Before opening a pull request

1. Keep the change focused and explain the user-visible/scientific effect.
2. Update canonical contracts before generated projections.
3. Add or update regression tests for changed behavior.
4. Preserve typed refusals where a chemistry, topology, tool, or evidence model
   is not supported exactly.
5. Do not commit secrets, local databases, virtual environments, caches, build
   output, or `.local/` contents.
6. Run the checks documented in `docs/DEVELOPMENT.md` on a supported host.

## Pull-request qualification

CI classifies changed paths before installing toolchains. Documentation-only
changes run the secret scan and static repository audit. SHA-pin-only workflow
updates run the static action-pin audit; GitHub's dedicated CodeQL and
dependency-review workflows still run on their own triggers. A small set of
release/maintenance helpers with direct regression coverage runs those
contracts without compiling unrelated product components. Product and
dependency changes, CI/security/deployment changes outside the explicitly
tested narrow allowlist, and unclassified changes retain the full qualification
path; unknown paths fail closed. Web browser qualification runs only when the
Web surface changes, and broad source/image checks start only after fast
feedback succeeds. The path rules and their regression tests live in
`scripts/classify-ci-scope.py` and `scripts/check-linux-bootstrap.py`.
The final aggregate is named `Required PCRStudio qualification`. Before relying
on conditional jobs for merge protection, the `main` ruleset must require this
aggregate; update/verify that rule only after GitHub has observed a successful
run of the candidate workflow.

## Scientific contributions

For a new or changed protocol/tool authority, include the exact upstream source,
version/revision, applicable numeric envelope, and claim boundary. Vendor
instructions, PCRStudio search preferences, measured run evidence, and design
ranking logic must remain distinguishable.

Generated files are projections. A pull request should change their canonical
source and regenerate them rather than editing projections to satisfy a check.

## Code style

- Rust: `cargo fmt` and Clippy with warnings denied.
- TypeScript/React: repository ESLint, TypeScript, and Prettier rules.
- Python: repository Ruff configuration and tests.
- Keep public APIs and wire formats backward-compatible unless the change is
  explicitly versioned.

## Reporting problems

For security issues, follow `SECURITY.md` instead of opening a public issue with
sensitive details.
