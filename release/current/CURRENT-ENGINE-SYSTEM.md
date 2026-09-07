# CURRENT unified engine system

The canonical engine authority is `contracts/engines.toml`. PCRStudio CURRENT defines exactly 11 engines:

- `consensus-pair`
- `discriminating-pair`
- `flanking-pair`
- `junction-primers`
- `loop-set`
- `mutagenic-pair`
- `nested`
- `outward-pair`
- `pair-and-probe`
- `single-primer`
- `tiling-scheme`

Every engine has exactly one profile under `contracts/engines/profiles/`. The same generic generation path produces authority projections, feature/tool capability matrices, transport parity, differential-corpus projections and Rust/Web/Python registries. Qualification uses `engine-authority-generator-check`, `engine-contract-generator-check`, `engine-web-differential-contract` and the unified `engine_differential_contract`; no active gate is named after an engine count.

Specialized scientific authorities remain specialized by assay/domain where scientifically necessary. Uniform architecture does not mean forcing different assays into one algorithm; it means every engine obeys the same registration, provenance, generation, testing and qualification lifecycle.
