# CURRENT source qualification

`scripts/qualify-source.py` is the environment-independent CURRENT source gate used by CI and Linux preparation. It verifies canonical/generated contracts, the unified 11-engine registry and profiles, method-fidelity and multiplex authorities, focused scientific regressions, architecture/application/UI/security guards, syntax parsing, hygiene and supply-chain pinning.

The current source qualification passes with these engine gates:

- `engine-authority-generator-check`
- `engine-contract-generator-check`
- `engine-web-differential-contract`
- unified focused Python engine-contract regressions

This is a source-only qualification. Native Cargo/pnpm compilation, Docker/runtime behavior, migrations, scientific executables, target-host evidence and wet-lab validation remain explicit Linux qualification gates. Run `scripts/prepare-linux.py` for preparation and `scripts/run-linux-qualification.py --full` on the qualified Linux host.
