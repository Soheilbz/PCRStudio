# PCRStudio Method Fidelity audit

**Status:** **PASS**

Canonical registry: `contracts/method-fidelity.json`
Canonical SHA-256: `faf15cc9095e72142a981408b6132d96c40d21cd1bad264e68456c62f82d5384`
Methods: **31** · Public modules: **21**

## Fidelity grades

| Grade | Count | Meaning |
| --- | ---: | --- |
| `F0-upstream-exact` | 9 | The pinned official/upstream executable or library is invoked directly. |
| `F1-exact-public-port` | 2 | A fully specified exact algorithm/component is implemented without hidden heuristics; for named external methods this requires a complete public authority/differential port, while PCRStudio-owned exact algorithms must expose their objective, bounds and refusal conditions. |
| `F2-manual-rule-faithful` | 5 | All public rules used by the named protocol/method branch are implemented, without claiming proprietary software equivalence. |
| `F3-compatible-approximate` | 8 | Internal compatible/inspired/heuristic logic. It must not be presented as the named external method and cannot drive Scientific-Strict primary decisions unless the decision impact is explicitly non-primary. |
| `F4-external-authority-only` | 7 | Critical internals are proprietary/incomplete or an exact external authority is required; PCRStudio must not invent them. |

## Scientific-Strict policy

Named methods may drive primary Scientific-Strict decisions only when the declared fidelity authority permits it. Internal compatible/heuristic logic is never silently relabelled as an upstream method; proprietary or incompletely published methods remain external-authority/refusal boundaries.

Primary methods explicitly blocked from Scientific-Strict until a higher-fidelity authority path exists:

- `arms-pcr-generalized-policy` — PCRStudio generalized ARMS candidate policy — F3-compatible-approximate
- `armsprimer3` — ARMSprimer3 — F4-external-authority-only
- `kasp-compatible-policy` — PCRStudio open KASP-compatible candidate policy — F3-compatible-approximate
- `kraken` — LGC Kraken KASP assay-design platform — F4-external-authority-only
- `nebasechanger-web` — NEBaseChanger web-tool design implementation — F4-external-authority-only
- `pcrstudio-multiplex-local-optimizer` — PCRStudio deterministic multiplex local optimiser — F3-compatible-approximate
- `primerexplorer-v5-search` — PrimerExplorer V5 proprietary search/ranking implementation — F4-external-authority-only
- `quikchange-primer-design-web` — Agilent QuikChange Primer Design Program — F4-external-authority-only
- `saddle-optimizer` — SADDLE simulated-annealing optimiser — F4-external-authority-only

## Method registry

| Method | Grade | Decision impact | Strict | Claim boundary |
| --- | --- | --- | --- | --- |
| `ambiguous-specificity-surrogate` | `F3-compatible-approximate` | `unresolved-evidence-only` | yes | Possible-base compatible matching is conservative evidence with mismatch bounds; it may not produce a definitive clean specificity claim. |
| `arms-pcr-generalized-policy` | `F3-compatible-approximate` | `primary-ranking` | no | This generalized ARMS branch is not ARMSprimer3 and is not a universal polymerase mismatch law; use only outside Scientific-Strict until an exact named authority path is selected. |
| `armsprimer3` | `F4-external-authority-only` | `primary-design` | no | ARMSprimer3 is a distinct open-source upstream implementation. PCRStudio must not label its generalized internal ARMS policy ARMSprimer3; exact use requires a managed upstream adapter and qualification. |
| `blast-plus` | `F0-upstream-exact` | `independent-validation` | yes | PCRStudio invokes the pinned NCBI BLAST+ executable for indexed validation rather than cloning BLAST. |
| `kasp-compatible-policy` | `F3-compatible-approximate` | `primary-ranking` | no | This policy models open KASP chemistry/geometry only and is explicitly not LGC Kraken-equivalent. |
| `kraken` | `F4-external-authority-only` | `primary-design` | no | Kraken internals are proprietary; PCRStudio does not reverse-engineer or claim equivalence. |
| `lamp-linear-specificity-proxy` | `F3-compatible-approximate` | `diagnostic-only` | yes | A linear PCR-style screen is retained only as diagnostic evidence and never ranks/eliminates LAMP sets. LAMP-native six-region topology owns direct candidate-ranking impact. |
| `mafft` | `F0-upstream-exact` | `alignment` | yes | PCRStudio invokes MAFFT for managed alignment workflows; it does not label an internal alignment heuristic as MAFFT. |
| `mfeprimer` | `F0-upstream-exact` | `independent-validation` | yes | PCRStudio invokes the managed MFEprimer executable when that validation path is selected. |
| `mgb-tm` | `F4-external-authority-only` | `probe-thermodynamics` | yes | PCRStudio exports/imports hash-bound candidate results and does not invent an MGB Tm formula. |
| `nebasechanger-web` | `F4-external-authority-only` | `primary-design` | no | PCRStudio must not claim NEBaseChanger-equivalent primer design without official vendor output/authority. |
| `olivar` | `F0-upstream-exact` | `primary-tiling-design` | yes | The Olivar backend invokes upstream Olivar and retains its backend-specific risk evidence. |
| `pcrstudio-multiplex-exact-search` | `F1-exact-public-port` | `primary-ranking` | yes | PCRStudio exact lexicographic branch-and-bound over the evaluated candidate pools. It is not SADDLE and claims no optimum outside the supplied candidate pools. |
| `pcrstudio-multiplex-local-optimizer` | `F3-compatible-approximate` | `primary-ranking` | no | PCRStudio deterministic greedy/local-swap optimiser using SADDLE Badness; it is not SADDLE simulated annealing and cannot be presented as such. |
| `pcrstudio-nebuilder-multisite-route` | `F3-compatible-approximate` | `routing-only` | yes | Deterministic construct/fragment routing informed by the NEBaseChanger multi-site workflow; Junction Primers owns actual overlap/primer design. It is not NEBaseChanger primer design. |
| `primalscheme3` | `F0-upstream-exact` | `primary-tiling-design` | yes | The PrimalScheme3 backend runs the upstream command; PCRStudio does not substitute its fallback while claiming PrimalScheme3. |
| `primer3` | `F0-upstream-exact` | `primary-design` | yes | PCRStudio invokes the pinned upstream Primer3/libprimer3 implementation; it does not reimplement Primer3 ranking. |
| `primerexplorer-v5-public-rules` | `F2-manual-rule-faithful` | `lamp-geometry-and-eligibility` | yes | PCRStudio implements reviewed public PrimerExplorer V5 geometry/thermodynamic rules and reference outputs; it does not claim to reproduce proprietary PrimerExplorer search/ranking internals. |
| `primerexplorer-v5-search` | `F4-external-authority-only` | `primary-ranking` | no | No internal equivalence claim is allowed without an official executable/service or complete public algorithm authority. |
| `primerpooler` | `F0-upstream-exact` | `multiplex-validation-or-pooling` | yes | PCRStudio invokes PrimerPooler as an independent managed tool when configured; internal PCRStudio multiplex optimisation is separately identified. |
| `pydna` | `F0-upstream-exact` | `construct-or-topology-validation` | yes | PCRStudio hands supported construct/topology work to the pinned pydna library. |
| `q5-manual` | `F2-manual-rule-faithful` | `primary-design` | yes | PCRStudio implements reviewed Q5 public primer/topology rules and explicitly refuses proprietary/unsupported branches rather than impersonating NEBaseChanger. |
| `qpcr-unbound-probe-heuristic` | `F3-compatible-approximate` | `research-only` | no | Low-level research helper only; routed qPCR Probe requires named executable chemistry and does not use this heuristic as an orderable scientific result. |
| `quikchange-lightning-manual` | `F2-manual-rule-faithful` | `primary-design` | yes | PCRStudio applies published manual geometry/Tm/GC/end/structure-review rules but does not claim equivalence to Agilent QuikChange Primer Design software or its Energy Cost optimiser. |
| `quikchange-primer-design-web` | `F4-external-authority-only` | `primary-ranking` | no | PCRStudio does not reproduce proprietary web-tool ranking/Energy Cost internals. Exact web-tool equivalence requires the vendor authority. |
| `rpa-full-empirical-development` | `F2-manual-rule-faithful` | `empirical-selection` | yes | PCRStudio orchestrates the source-backed empirical 8-10 forward by 8-10 reverse candidate matrix; assay selection remains evidence-driven rather than sequence-predicted. |
| `rpa-quick-primer3-screen` | `F3-compatible-approximate` | `screening-plan-only` | yes | The in-silico shortlist is not a mechanistic RPA predictor and cannot validate an assay or replace empirical pair-matrix screening. |
| `saddle-badness` | `F1-exact-public-port` | `multiplex-objective` | yes | PCRStudio implements only the published SADDLE Badness interaction objective. This does not make the PCRStudio optimiser the SADDLE simulated-annealing optimiser. |
| `saddle-optimizer` | `F4-external-authority-only` | `primary-ranking` | no | Exact SADDLE optimiser execution requires the official algorithm/code authority. PCRStudio must not guess unpublished cooling/stopping details or claim an internal replacement is SADDLE. |
| `tetra-arms-ye-2001` | `F2-manual-rule-faithful` | `primary-design` | yes | The named tetra-primer branch enforces the published -2 deliberate mismatch, mismatch-strength pairing, >=26-nt inner-primer rule, opposite inner-primer geometry and three-product layout; bench optimisation remains empirical. |
| `viennarna` | `F0-upstream-exact` | `secondary-accessibility-evidence` | yes | PCRStudio invokes ViennaRNA for the optional accessibility calculation and records model parameters. |

## Module roles

- **arms-pcr** — active: `primer3`, `arms-pcr-generalized-policy`; references: `armsprimer3`
- **colony-pcr** — active: `primer3`; diagnostic: `ambiguous-specificity-surrogate`; validators: `blast-plus`, `mfeprimer`
- **digital-pcr** — active: `primer3`; validators: `blast-plus`, `mfeprimer`
- **gibson-assembly** — active: `primer3`; validators: `pydna`
- **inverse-pcr** — active: `primer3`; conditional: `pydna`; validators: `blast-plus`
- **kasp** — active: `primer3`, `kasp-compatible-policy`; references: `kraken`
- **lamp** — active: `primerexplorer-v5-public-rules`; conditional: `viennarna`; diagnostic: `lamp-linear-specificity-proxy`; references: `primerexplorer-v5-search`; validators: `blast-plus`
- **long-range-pcr** — active: `primer3`; diagnostic: `ambiguous-specificity-surrogate`; validators: `blast-plus`, `mfeprimer`
- **nested-pcr** — active: `primer3`; validators: `blast-plus`, `mfeprimer`
- **qpcr-probe** — active: `primer3`; conditional: `mgb-tm`; references: `qpcr-unbound-probe-heuristic`; validators: `blast-plus`, `mfeprimer`
- **qpcr-sybr** — active: `primer3`; validators: `blast-plus`, `mfeprimer`
- **race** — active: `primer3`; validators: `blast-plus`
- **restriction-cloning** — active: `primer3`
- **rpa** — active: `primer3`; diagnostic: `rpa-quick-primer3-screen`; required_followup: `rpa-full-empirical-development`
- **sequencing-primer** — active: `primer3`; validators: `blast-plus`
- **site-directed-mutagenesis** — active: `primer3`; conditional: `q5-manual`, `quikchange-lightning-manual`, `pcrstudio-nebuilder-multisite-route`; references: `quikchange-primer-design-web`, `nebasechanger-web`
- **species-specific-pcr** — active: `primer3`; diagnostic: `ambiguous-specificity-surrogate`; validators: `blast-plus`, `mfeprimer`
- **standard-pcr** — active: `primer3`; diagnostic: `ambiguous-specificity-surrogate`; validators: `blast-plus`, `mfeprimer`
- **tetra-primer-arms** — active: `primer3`, `tetra-arms-ye-2001`
- **tiled-scheme** — conditional: `primalscheme3`, `olivar`; validators: `primerpooler`, `mfeprimer`, `blast-plus`
- **universal-primers** — active: `primer3`

This is a source-fidelity audit, not native/runtime or wet-lab qualification. F0 means the upstream tool/library is the selected implementation path; it does not mean the tool has already passed the target Linux qualification for this release candidate.
