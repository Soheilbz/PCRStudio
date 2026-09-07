# Native Linux runtime contract

Linux x86_64 is the canonical PCRStudio R17 development, qualification and deployment platform. No Linux, Python, batch launcher or platform-emulation layer is part of the runtime contract.

## Process rules

- Rust uses `tools/.venv/bin/python` before a generic Python interpreter.
- External scientific tools are invoked with argument vectors and `shell=False`; request data never becomes a shell fragment.
- Explicit `PCRSTUDIO_*` executable paths take precedence over native `PATH` discovery.
- Paths use `pathlib.Path`; temporary workspaces use project-local `.local/tmp` or the host `tempfile` implementation.
- Database lists use `os.pathsep` (`:` on Linux).
- The Rust worker clears its child environment and forwards only the reviewed allow-list.
- Installation and index construction are deployment operations. A design request never downloads tools or mutates a reference database.

## Reproducibility modes

`PCRSTUDIO_SCIENTIFIC_POLICY=strict` is the release default and is a ceiling over lower-level tool/validator modes. In strict mode, every required local executable and scientific environment is fingerprinted; production specificity also requires a `production` or `approved-reference` database manifest with content/index hashes.

A newly provisioned host may use a smoke/regression corpus for wiring checks, but that corpus is never promoted to a production specificity claim.

## Supported configuration variables

| Variable | Meaning |
|---|---|
| `PCR_PYTHON` | worker Python interpreter override |
| `PCRSTUDIO_SCIENTIFIC_POLICY` | `strict` or explicit development mode |
| `PCR_WORKER_TIMEOUT_SECONDS` | worker timeout; parent HTTP deadline remains authoritative |
| `PCRSTUDIO_EXTERNAL_VALIDATION` | validator mode; forced to strict under strict scientific policy |
| `PCRSTUDIO_TOOLCHAIN_MODE` | toolchain mode; forced to strict under strict scientific policy |
| `PCRSTUDIO_MFEPRIMER` / `_SHA256` | MFEprimer 4.5.1 Linux executable and exact hash |
| `PCRSTUDIO_MFEPRIMER_DATABASES*` | approved MFEprimer database path, scope, source hash and manifest |
| `PCRSTUDIO_BLASTN` / `_SHA256` | NCBI BLAST+ 2.17.0 Linux `blastn` executable and exact hash |
| `PCRSTUDIO_BLAST_DATABASE*` | approved BLAST database basename, scope, source hash and manifest |
| `PCRSTUDIO_PRIMERPOOLER` / `_SHA256` | PrimerPooler 1.89 Linux executable and exact hash |
| `PCRSTUDIO_PRIMALSCHEME3` / `_SHA256` | PrimalScheme3 3.3.0 Linux entry point and exact hash |
| `PCRSTUDIO_PYDNA_PYTHON` / `_SHA256` | isolated scientific Python for pydna and exact interpreter hash |
| `PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE*` | exact post-provision scientific environment freeze/fingerprint |
| `PCRSTUDIO_MAFFT` / `_SHA256` | MAFFT 7.526 Linux wrapper and exact hash |
| `PCRSTUDIO_OLIVAR` / `_SHA256` | explicitly managed Olivar 1.3.3 Linux executable and exact hash |

## Molecule semantics

Every order-sheet oligo may expose `sequence`, `annealing_sequence`, and `tail_sequence`. Specificity searches use the annealing segment; dimer/hairpin/pooling checks use the complete ordered molecule. This distinction is mandatory for tails, adapters, LAMP composites, Gibson overlaps and other 5′ extensions.
