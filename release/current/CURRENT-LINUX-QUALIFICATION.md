# CURRENT Linux native qualification

PCRStudio CURRENT is qualified on Linux x86_64. This gate is intentionally separate from source-only qualification because it executes dependency-backed builds, native scientific tools, high-risk integration scenarios and (when requested) live-stack probes.

## Host prerequisites

- Linux x86_64 with a POSIX shell
- Python 3.11+ (the production worker image uses Python 3.12)
- Node.js 24.x and Corepack/pnpm 11.19.0 (matching the production Web image)
- Rust toolchain pinned by the repository
- `uv`, C/C++ build tools and `make`
- PostgreSQL/Docker only when exercising the deployment stack

No PowerShell/CMD batch launcher, Windows executable path, WSL bridge, Wine layer, or other platform emulation is part of this qualification contract.

## Preparation

Before mutating a production host, the read-only doctor can be used independently:

```bash
python3 scripts/doctor-linux.py --domain pcr.example.org --allow-docker-install
```

The one-command production bootstrap performs its own stricter RAM/disk/Docker
preflight before image construction.


```bash
python3 scripts/prepare-linux.py --sync-dependencies --provision-tools
```

The scientific provisioner installs the exact Linux-native artifacts declared by the canonical tool contract and writes provenance under `.local/tools/`. Production specificity remains fail-closed until an approved reference FASTA is indexed explicitly:

```bash
python3 scripts/configure-specificity-database.py \
  /absolute/path/to/reviewed-reference.fasta \
  <reviewed-id> \
  --scope approved-reference
```

Olivar 1.3.3 is intentionally external-managed. Bind an explicitly reviewed Linux installation with:

```bash
python3 scripts/configure-olivar-linux.py --executable /absolute/path/to/olivar
```

## Full native gate

```bash
python3 scripts/run-linux-qualification.py --full \
  --require-functional-acceptance
```

Add `--require-olivar` when Olivar is a release requirement and `--probe-running-stack` when the production stack is already running. The gate is manifest-bound and fails closed on missing tools, dependency/build failures, scientific readiness failure, scenario evidence drift, or source mutation during qualification.
