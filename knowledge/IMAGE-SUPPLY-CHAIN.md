# Container image supply-chain policy

Production Dockerfiles and Compose services pin every external base image by an immutable
multi-platform `sha256` manifest/index digest while retaining the human-readable tag. Updates are
reviewed as source changes and must be accompanied by source qualification and a regenerated SBOM.

GitHub Actions are pinned by commit SHA. Rust/npm/Python dependencies are frozen by their native
lockfiles; scientific executables use the canonical `contracts/tools.toml` version/hash policy.
