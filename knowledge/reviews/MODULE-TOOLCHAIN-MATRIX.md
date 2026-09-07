# PCRStudio Module × Toolchain Matrix

Audit state as of: 2026-09-05

| Engine | Modules | Tool | Role | Version/scope | Strict meaning |
|---|---|---|---|---|---|
| `consensus-pair` | `universal-primers` | `mafft` | **PRIMARY** | 7.526 / local | required decision authority |
| `consensus-pair` | ↳ | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `consensus-pair` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `consensus-pair` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `consensus-pair` | ↳ | `pcrstudio_consensus_resolver` | **PRIMARY** | internal / internal | required decision authority |
| `discriminating-pair` | `arms-pcr`, `kasp`, `tetra-primer-arms` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `discriminating-pair` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `discriminating-pair` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `discriminating-pair` | ↳ | `pcrstudio_allele_wrapper` | **PRIMARY** | internal / internal | required decision authority |
| `flanking-pair` | `colony-pcr`, `digital-pcr`, `long-range-pcr`, `qpcr-sybr`, `restriction-cloning`, `rpa`, `species-specific-pcr`, `standard-pcr` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `flanking-pair` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `flanking-pair` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `flanking-pair` | ↳ | `primerpooler` | **OPTIONAL** | 1.89 / local | advisory only; may not change deterministic selection |
| `flanking-pair` | ↳ | `viennarna` | **OPTIONAL** | 2.7.2 / optional-package | advisory only; may not change deterministic selection |
| `flanking-pair` | ↳ | `primer_blast` | **REFERENCE** | live / remote-reference | reference only; never runtime prerequisite |
| `flanking-pair` | ↳ | `nupack4` | **REFERENCE** | 4.x / manual-reference | reference only; never runtime prerequisite |
| `flanking-pair` | ↳ | `pydna` | **OPTIONAL** | 5.5.16 / local | advisory only; may not change deterministic selection |
| `flanking-pair` | ↳ | `pcrstudio_flanking_wrapper` | **PRIMARY** | internal / internal | required decision authority |
| `junction-primers` | `gibson-assembly` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `junction-primers` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `junction-primers` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `junction-primers` | ↳ | `viennarna` | **OPTIONAL** | 2.7.2 / optional-package | advisory only; may not change deterministic selection |
| `junction-primers` | ↳ | `pydna` | **OPTIONAL** | 5.5.16 / local | advisory only; may not change deterministic selection |
| `junction-primers` | ↳ | `pcrstudio_junction_composer` | **PRIMARY** | internal / internal | required decision authority |
| `loop-set` | `lamp` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `loop-set` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `loop-set` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `loop-set` | ↳ | `mafft` | **CONDITIONAL_PRIMARY** | 7.526 / local | reference only; never runtime prerequisite |
| `loop-set` | ↳ | `viennarna` | **OPTIONAL** | 2.7.2 / optional-package | advisory only; may not change deterministic selection |
| `loop-set` | ↳ | `pcrstudio_lamp_enumerator` | **PRIMARY** | internal / internal | required decision authority |
| `mutagenic-pair` | `site-directed-mutagenesis` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `mutagenic-pair` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `mutagenic-pair` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `mutagenic-pair` | ↳ | `pydna` | **OPTIONAL** | 5.5.16 / local | advisory only; may not change deterministic selection |
| `mutagenic-pair` | ↳ | `pcrstudio_edit_normalizer` | **PRIMARY** | internal / internal | required decision authority |
| `nested` | `nested-pcr` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `nested` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `nested` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `nested` | ↳ | `primerpooler` | **OPTIONAL** | 1.89 / local | advisory only; may not change deterministic selection |
| `nested` | ↳ | `pcrstudio_nested_containment` | **PRIMARY** | internal / internal | required decision authority |
| `outward-pair` | `inverse-pcr` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `outward-pair` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `outward-pair` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `outward-pair` | ↳ | `pydna` | **OPTIONAL** | 5.5.16 / local | advisory only; may not change deterministic selection |
| `outward-pair` | ↳ | `pcrstudio_topology_resolver` | **PRIMARY** | internal / internal | required decision authority |
| `pair-and-probe` | `qpcr-probe` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `pair-and-probe` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `pair-and-probe` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `pair-and-probe` | ↳ | `viennarna` | **OPTIONAL** | 2.7.2 / optional-package | advisory only; may not change deterministic selection |
| `pair-and-probe` | ↳ | `primer_blast` | **REFERENCE** | live / remote-reference | reference only; never runtime prerequisite |
| `pair-and-probe` | ↳ | `pcrstudio_probe_wrapper` | **PRIMARY** | internal / internal | required decision authority |
| `single-primer` | `race`, `sequencing-primer` | `primer3_core` | **PRIMARY** | 2.6.1 / embedded-package | required decision authority |
| `single-primer` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `single-primer` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `single-primer` | ↳ | `pcrstudio_single_primer_wrapper` | **PRIMARY** | internal / internal | required decision authority |
| `tiling-scheme` | `tiled-scheme` | `mafft` | **PRIMARY** | 7.526 / local | required decision authority |
| `tiling-scheme` | ↳ | `primalscheme3` | **PRIMARY** | 3.3.0 / local | required decision authority |
| `tiling-scheme` | ↳ | `olivar` | **PRIMARY** | 1.3.3 / external-managed | required decision authority |
| `tiling-scheme` | ↳ | `primerpooler` | **VALIDATOR** | 1.89 / local | required independent evidence when bound as VALIDATOR |
| `tiling-scheme` | ↳ | `mfeprimer` | **VALIDATOR** | 4.5.1 / local | required independent evidence when bound as VALIDATOR |
| `tiling-scheme` | ↳ | `ncbi_blast_plus` | **VALIDATOR** | 2.17.0 / local | required independent evidence when bound as VALIDATOR |
| `tiling-scheme` | ↳ | `pcrstudio_scheme_wrapper` | **PRIMARY** | internal / internal | required decision authority |
