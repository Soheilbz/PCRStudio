# Development guide

PCRStudio CURRENT uses Linux x86_64 as the canonical development, CI and production platform. Machine-specific workstation state is not part of the public source contract.

## Generated and local state

Keep mutable state inside ignored project-local paths: `.local/logs/`, `.local/backups/`, `.local/tmp/`, `target/`, `node_modules/`, `tools/.venv/`, `web/.next/`, `test-results/`, and `playwright-report/`. Do not commit credentials, databases, caches, local environments or build output.

## Bootstrap

The single-command local bootstrap is:

```bash
./bootstrap.sh --local
```

It keeps the uv environment, pnpm store, Python environments, scientific tools
and the Chromium/Firefox/WebKit E2E browsers under `.local`/`tools/.venv`, then
runs the generated-contract and source qualification gates. It also starts the
local PostgreSQL/API/Next stack, waits for `/health`, `/ready` and
`/ready/scientific`, and creates `.local/admin-credentials.json` with mode 600.
The selected endpoints are recorded in `.local/runtime/endpoints.json`; repeat
runs reuse a healthy stack.

The individual commands below remain useful for debugging or CI reproduction:

```bash
corepack enable
pnpm install --frozen-lockfile
uv sync --project tools --frozen --extra dev --extra folding
python scripts/provision-tools.py
```

The provisioner is Linux-only and installs/fingerprints the scientific toolchain under `.local/tools/`. A smoke/regression tool install does not imply production specificity readiness.

With the API running, create a local administrator with `pnpm admin`. The
helper registers through the normal auth boundary and promotes only that exact
email in the local PostgreSQL database. It refuses production and asks for the
password with terminal echo disabled; do not put the password in shell history
or commit it to `.env`.

## Development database

```bash
docker compose -f docker/compose.devdb.yaml up -d --wait db
docker compose -f docker/compose.devdb.yaml down
```

The development database binds to loopback only. Back up project data before destructive database work.

## Launching the stack

```bash
./run.sh
# optional manual/restart command after bootstrap
pnpm launch
```

The launcher owns dedicated POSIX process groups for API/Web children, so SIGINT/SIGTERM tears down the complete process tree without killing unrelated listeners. The API exposes `/health`, `/ready`, and `/ready/scientific` for liveness, application readiness and strict scientific readiness.

## Verification

```bash
pnpm typecheck
pnpm lint
pnpm format:check
pnpm test
cargo fmt --all -- --check
pnpm rust:lint
pnpm rust:test
tools/.venv/bin/python -m pytest tools/tests -q -n auto --dist loadgroup
python scripts/run-linux-qualification.py --full
```

`python scripts/run-linux-qualification.py` without `--full` performs the non-mutating source/static gate. It must never be reported as native build/runtime qualification.

## Specificity database

After tool provisioning, create an atomic production or approved-reference MFEprimer/BLAST snapshot:

```bash
python scripts/configure-specificity-database.py reference.fasta my-reference \
  --scope approved-reference --sequence-release <release> --taxonomy-release <release>
```

The database builder validates FASTA structure, rejects duplicate record identifiers, builds both indexes in a staging directory, fingerprints every index artifact, and swaps the completed snapshot atomically.

## Scientific changes

Scientific behavior is contract-driven. Update canonical contracts first, regenerate projections, inspect the diff and preserve typed refusal boundaries when exact authority is unavailable. Architecture decisions are documented under `docs/adr/`.
