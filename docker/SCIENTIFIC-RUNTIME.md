# Docker scientific-runtime boundary

Linux x86_64 is the only supported CURRENT runtime platform. The base `compose.yaml` packages the Rust API, Python worker environment, database and Web application. External scientific tools and approved specificity data are treated as independently fingerprinted deployment assets rather than being silently downloaded by an application request.

The contract is fail-closed:

- `PCRSTUDIO_SCIENTIFIC_POLICY=strict` and `PCRSTUDIO_TOOLCHAIN_MODE=strict` remain the release defaults.
- Final API and runner images use the digest-pinned official BusyBox glibc
  runtime foundation. Python, glibc, CA certificates, and the approved native
  tool bundle cross the stage boundary from pinned build stages; Debian's
  package-manager database and compiler toolchain do not. This keeps the
  production attack surface reproducible without suppressing vulnerability
  findings.
- `/health` proves process liveness only.
- `/ready` proves application/database/worker readiness.
- `/ready/scientific` is the authority for scientific-toolchain and approved-database readiness; HTTP 503 means the deployment is not scientifically ready.
- Missing or hash-mismatched external tools produce refusal, never an internal approximation.
- A scientific container/deployment profile must pin the same tool versions, executable hashes, scientific-Python freeze and database manifest used during Linux qualification.

For a VM deployment, provision the Linux toolchain on the target host with `python scripts/provision-tools.py`, configure the approved specificity snapshot, and qualify that exact host. Do not copy opaque binaries into an image or volume without binding their SHA-256 to qualification evidence.
