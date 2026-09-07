# CURRENT toolchain status

PCRStudio uses one Linux-native scientific toolchain policy for all engines. Exact executable versions/artifacts, scientific Python freeze, specificity databases and optional backends must be provisioned and fingerprinted before strict scientific readiness passes.

The toolchain is not grouped by engine-release batches. Tool bindings are owned by `contracts/engines.toml`; per-engine capability projections are generated through the unified engine contract generator. Native execution must still be qualified on the exact Linux CI/target host.
