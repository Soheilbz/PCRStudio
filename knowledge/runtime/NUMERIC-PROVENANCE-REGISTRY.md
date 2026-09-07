# PCRStudio Numeric Provenance Registry

Audit state as of: 2026-09-05

Active numeric profile constraints: **190**. Qualification-envelope bounds: **3**. Named numeric constants: **138**. Inline decision/comparison numeric literals: **204**.

The registry separates hard/assay-envelope values from ranking tuning, diagnostics, search caps and protocol/readout models. Literature/vendor numbers in Atlas documents are not runtime defaults unless a named active profile/overlay explicitly activates them.

## Ranking-only/tuning constants

| Source | Constant | Category | Decision role |
|---|---|---|---|
| `tools/src/pcr_tools/pipeline.py:110` | `OFF_TARGET_SERIOUS` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:111` | `OFF_TARGET_WATCH` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:117` | `PENALTY_CAP` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:123` | `ACCESSIBILITY_WEIGHT` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:124` | `ACCESSIBILITY_CAP` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:146` | `CROSS_DIMER_WEIGHT` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:147` | `CROSS_DIMER_CAP` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:428` | `PURPOSE_WEIGHTS` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:462` | `THREE_PRIME_TRIPLET_FREQUENCIES` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:533` | `THREE_PRIME_TRIPLET_CAP` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:570` | `ISOTHERMAL_PRIMER3_WEIGHTS` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:916` | `QUALITY_WEIGHTS` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/pipeline.py:928` | `END_STABILITY_SCALE` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/lamp_geometry.py:163` | `EVIDENCE_2026_F2_B2_PREFERRED` | ranking-tuning | may rank/report only; not a hard validity gate |
| `tools/src/pcr_tools/lamp_geometry.py:164` | `EVIDENCE_2026_OUTER_GAP_PREFERRED` | ranking-tuning | may rank/report only; not a hard validity gate |

## Inline decision-literal inventory

Every numeric literal that still appears directly inside a core decision comparison is inventoried in the JSON registry with file, line, function and category. Non-trivial scientific/tool bounds should be promoted to named constants when practical; structural 0/1/cardinality and percentage-domain literals remain visible here rather than being treated as hidden evidence.

## Profile policy summary

| Module | Numeric constraints | Locked | Bounded | Recommended |
|---|---:|---:|---:|---:|
| `arms-pcr` | 14 | 0 | 0 | 14 |
| `colony-pcr` | 0 | 0 | 0 | 0 |
| `digital-pcr` | 14 | 0 | 0 | 14 |
| `gibson-assembly` | 14 | 0 | 0 | 14 |
| `inverse-pcr` | 0 | 0 | 0 | 0 |
| `kasp` | 14 | 0 | 1 | 13 |
| `lamp` | 0 | 0 | 0 | 0 |
| `long-range-pcr` | 13 | 0 | 6 | 7 |
| `nested-pcr` | 0 | 0 | 0 | 0 |
| `qpcr-probe` | 14 | 0 | 0 | 14 |
| `qpcr-sybr` | 14 | 0 | 0 | 14 |
| `race` | 11 | 0 | 0 | 11 |
| `restriction-cloning` | 0 | 0 | 0 | 0 |
| `rpa` | 14 | 4 | 0 | 10 |
| `sequencing-primer` | 11 | 0 | 0 | 11 |
| `site-directed-mutagenesis` | 11 | 11 | 0 | 0 |
| `species-specific-pcr` | 1 | 0 | 0 | 1 |
| `standard-pcr` | 1 | 0 | 0 | 1 |
| `tetra-primer-arms` | 14 | 0 | 0 | 14 |
| `tiled-scheme` | 14 | 0 | 0 | 14 |
| `universal-primers` | 16 | 0 | 0 | 16 |
