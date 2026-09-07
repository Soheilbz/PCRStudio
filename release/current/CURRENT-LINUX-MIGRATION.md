# PCRStudio CURRENT — Linux-native migration closure

**Canonical platform:** Linux x86_64
**Release state:** Linux-native source-qualified candidate; full host qualification remains an explicit dependency-backed gate.

## Migration closure

CURRENT no longer uses PowerShell/CMD batch launchers, Windows executable paths, WSL bridges, or platform-emulation wrappers in the active runtime/release pipeline. Linux x86_64 is the canonical development, CI, qualification and deployment platform.

Key changes:

- pnpm optional/native dependency materialization targets the current Linux x86_64 host.
- POSIX process groups are created explicitly for API/Web children and terminated as process groups, preventing orphaned children during launcher shutdown.
- shell launch, user creation, backup/restore and signing scripts carry executable Linux permissions.
- scientific provisioning is Python/Linux-native and verifies published/downloaded artifacts before installation whenever an upstream digest is available.
- MFEprimer 4.5.1 and NCBI BLAST+ 2.17.0 use pinned Linux x86_64 artifacts; PrimerPooler 1.89 is built from pinned source; MAFFT 7.526 uses the upstream Linux portable bundle; PrimalScheme3 3.3.0 and pydna 5.5.16 use exact wheels and published hashes.
- Olivar 1.3.3 is bound only through an explicitly reviewed Linux installation/environment.
- production specificity databases are created atomically from an explicitly supplied reviewed FASTA, with normalized FASTA hash and every generated index artifact fingerprinted.
- scientific Python freeze approval is Linux qualification evidence rather than platform-specific legacy evidence.
- acceptance results and qualification evidence are bound to the current release identity and `FILE-MANIFEST` hash.
- active source hygiene rejects legacy `.ps1`, `.bat` and `.cmd` files, CRLF text and case-only path collisions.

## Scientific supply-chain boundary

The official MAFFT 7.526 Linux portable distribution does not publish a digest alongside the portable archive on the upstream download page used by this release. The provisioner therefore retrieves that archive over HTTPS, safely extracts it, records the downloaded archive SHA-256 as deployment evidence, and computes a deterministic tree digest over the complete extracted portable bundle (paths, executable modes, wrappers, and companion binaries). Strict runtime verifies that bundle identity and executes a real alignment smoke test. This is an explicit trust boundary, not a fabricated upstream authenticity checksum. All other provisioned artifacts with an authoritative/published digest are verified before use.

## Qualification boundary

Source qualification is deliberately not promoted into a native-execution claim. Run the full Linux gate on the target host after dependency synchronization, scientific-tool provisioning and production reference-database configuration:

```bash
python3 scripts/run-linux-qualification.py --full --require-functional-acceptance
```

The target host is not qualified if any required native build, scientific tool, database, functional evidence or live-stack gate fails.
