# ADR-0005 — Architecture contracts are generated from canonical TOML
Status: Accepted (Generation 1 foundation)

`contracts/modules.toml`, `engines.toml`, `tools.toml` and `foundation.toml`
are architecture/runtime authorities. Rust/Python/Web projections are
generated. Scientific profile defaults remain separate scientific authorities;
canonicalization must not create one giant mixed-purpose manifest.
