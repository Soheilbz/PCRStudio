# PCRStudio CURRENT Linux acceptance runbook

This runbook is the native host counterpart to source qualification. Linux x86_64 is the canonical host for development, qualification and deployment.

## 1. Isolated preparation

Keep generated state under ignored repository-local paths (`.local/`, `tools/.venv/`, `node_modules/`, `target/`). Do not mutate global package state as part of routine qualification.

```bash
python3 scripts/prepare-linux.py --sync-dependencies --provision-tools
python3 scripts/new-linux-acceptance-results.py --force
```

## 2. Production specificity database

The bundled regression corpus is not production specificity evidence. Build an explicitly reviewed reference snapshot:

```bash
python3 scripts/configure-specificity-database.py \
  --database-id <reviewed-id> \
  --fasta /absolute/path/to/reference.fasta \
  --scope approved-reference
```

The operation is staged and atomically promoted. The normalized FASTA and every generated MFEprimer/BLAST index artifact are fingerprinted.

## 3. Optional Olivar binding

Olivar is external-managed and never guessed from an arbitrary environment:

```bash
python3 scripts/configure-olivar-linux.py --executable /absolute/path/to/olivar
```

## 4. Full native qualification

```bash
python3 scripts/run-linux-qualification.py --full --require-functional-acceptance
```

Use `--require-olivar` when that backend is a release requirement. Add `--probe-running-stack` only after the production stack is running.

The full gate executes dependency-backed Python/Rust/Web tests and builds, canonical high-risk scenario acceptance, LAMP qualification, exact scientific-tool readiness and manifest-bound functional evidence. A partial subset is not a native qualification PASS.

## 5. Evidence boundary

Acceptance rows are bound to the exact `release/FILE-MANIFEST.json` hash and canonical release identity. Candidate evidence cannot be transplanted to a changed source tree. Failures must be fixed in source/configuration; canonical matrices must never be edited to make a failure disappear.
