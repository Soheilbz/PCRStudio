# PCRStudio documentation current state

- **Cut-off:** 2026-08-30
- **Architecture:** single-source-of-truth atlas
- **Scientific engine source:** deep-enriched + six-pass heavy-audited + independent adversarial re-audited 11-engine / 21-module tree

This file is the only active documentation-audit summary. Historical snapshots are intentionally absent from the current tree; Git history and prior signed source bundles preserve them without adding a second specification surface.

## Current canonical surface

| Area | Canonical owner | Current state |
| --- | --- | --- |
| Assay-specific scientific values and evidence | `../engines/<engine>/<numbered-module>.md` | Canonical |
| Engine-shared topology/contract | `../engines/<engine>/00-engine.md` | Canonical |
| Engine-shared tool vocabulary | `../engines/<engine>/01-tools.md` | Canonical |
| Cross-engine design concepts | `../knowledge/design-intelligence.md` | Canonical shared layer |
| Cross-engine laboratory effects | `../knowledge/laboratory-effects.md` | Canonical shared layer |
| Cross-engine validation/failure concepts | `../knowledge/validation-evidence.md` | Canonical shared layer |
| Deployment guidance | `../operations/deployment.md` | Canonical operational layer |
| Historical research/review inputs | Git history / prior signed source bundles | Not part of the current active audit surface |

## Scientific engine state

The active engine tree contains:

- **11 engine directories**;
- **21 numbered assay modules**;
- **44 Markdown files** under `docs/engines/`, including the engine atlas README;
- **914 structured numeric-evidence rows** under headings containing `numeric evidence`, using the current reproducible heading-scoped parser;
- **0 duplicate Numeric Evidence IDs** under that parser;
- the same parser finds **886** rows in the pre-heavy-pass canonical package, so the heavy research, independent re-audit and toolchain-maturity promotion add **28** structured numeric-evidence records cumulatively; the toolchain pass itself adds **12** EasyKASP IDs without removing any prior ID;
- earlier lower/higher figures came from parsers with different section boundaries and are superseded by this heading-scoped count;
- all detected engine/module `Last reviewed` fields set to **2026-08-30**.

The deep-evidence enrichment performed before this documentation refactor is retained in the module records themselves. Historical audit reports are not carried forward as active files; the module-level source links and evidence registers remain the scientific source of truth.

## Six-pass heavy research enrichment

Six consecutive cross-engine research passes were completed against an evidence cut-off of **2026-08-30** without creating additional active knowledge files:

| Pass | Scope | Canonical promotion | State |
| --- | --- | --- | --- |
| 1 | Multiplex optimization, primer-interaction networks and tiling intelligence | `../knowledge/design-intelligence.md`; material assay-specific additions in `tiling-scheme` | Completed |
| 2 | Pangenome/population-aware design, evolutionary drift and large-scale specificity | `../knowledge/design-intelligence.md`; material additions in universal, species-specific and qPCR-probe modules | Completed |
| 3 | Oligo manufacturing, purification, modification, storage and physical QC | `../knowledge/laboratory-effects.md` | Completed |
| 4 | Matrix inhibition, additives, difficult templates and polymerase robustness | `../knowledge/laboratory-effects.md` | Completed |
| 5 | Analytical validation, metrology, failure evidence and reproducibility | `../knowledge/validation-evidence.md`; material dPCR validation additions | Completed |
| 6 | Literature/database provenance, thermodynamic-model uncertainty and benchmark framework | `../knowledge/design-intelligence.md` | Completed |

Evidence classes remain explicit: peer-reviewed literature and published standards are separated from current vendor documentation, preprints, patents/watchlist evidence and internal PCRStudio contracts. Study- or tool-specific thresholds remain source-scoped and are not promoted to universal defaults.

The heavy passes changed scientific content only where the new evidence materially altered an owning contract. This selective-promotion policy avoids copying cross-engine concepts into every assay module. The formal benchmark section defines the comparison framework required before making a defensible claim that PCRStudio is globally the most comprehensive atlas; it does **not** itself claim benchmark superiority.

## Final long-tail verification after the six passes

A final verification pass was performed after the six main research passes to target sources that commonly escape ordinary literature review. Material additions were promoted only to the three shared knowledge owners unless an assay-specific contract changed. The verification covered:

- current NUPACK 4.1 material/parameter/salt boundaries, including the distinction between single-material DNA and mixed RNA/DNA ionic support;
- current MFEprimer 4.x tool surveillance, including the 2026 HPRC pan-genome primer-check branch and versioned SNP-QC output;
- an independent 2026 oligonucleotide-synthesis mechanism paper on guanine O6/thymine O4 phosphitylation and substitution-error pathways;
- current LGC/Biosearch purification/QC rules and IDT storage/stability guidance, retained strictly as supplier-scoped evidence;
- the distinction between enzymatic PCR inhibition and optical/readout interference in qPCR/dPCR;
- the exact ISO/CD 20395.2 lifecycle as of the evidence cut-off, including the 2026-08-06 return to Working Group and 2026-08-07 re-initiation of CD consultation.

No new universal assay threshold was created from these sources. Preprints remain explicitly watchlist evidence, vendor/service claims remain product-scoped, and thermodynamic outputs remain qualified by model/version/material/ionic assumptions.

## Independent adversarial re-audit — 2026-08-30

A further independent re-audit was completed after the heavy six-pass release. This pass targeted sources most likely to escape ordinary review: very recent August 2026 peer-reviewed papers, current tool point releases, integrated-workflow software, vendor technical notes/supplementary numerical details and internal consistency after repeated enrichment.

Material promotions from this pass:

- **MFEprimer v4.5.1** lifecycle and the v4.5.0 SNP-output schema break, tightening tool/database/parser provenance;
- **PrimerWeaver** and **ColabPCR** as 2026 integrated/reproducible workflow-tool precedents;
- an **alignment-free k-mer → compacted de Bruijn graph → local MSA** broad-range RT-qPCR design branch;
- a population-genomic **Listeria** marker workflow validated through singleplex and high-multiplex endpoint PCR;
- a current NEB LAMP technical-note branch covering primer-region geometry, spacing, Tm ionic assumptions, end stability, primer concentrations/purification and non-default long-amplicon optimization;
- a newly published 2026 **neighbouring GC-rich template-context effect** affecting qPCR and nanoplate dPCR quantification, including the requirement to retain fragmentation/digestion and calibration-material context;
- a 2026 **rare splice-variant/exon-junction ddPCR** design/validation branch.

The pass also corrected a documentation-formatting issue in `engines/loop-set/01-tools.md`: two tool rows that had become detached from the surrounding Markdown table during prior enrichment are now restored inside the canonical tool table. This was a presentation/structure defect, not a scientific-data loss.

No new study/vendor threshold was promoted to a universal PCRStudio default. The new August 2026 numerical findings remain explicitly study-, tool-, platform- or vendor-scoped.

### Independent re-audit release gate

| Check | Result |
| --- | ---: |
| New structured Numeric Evidence IDs | **9** |
| Structured Numeric Evidence rows | **902** |
| Prior Numeric Evidence IDs removed | **0** |
| Prior numeric tokens removed from changed engine files | **0** |
| Engine Markdown files changed | **6** |
| Unique external URLs in active Markdown | **719** |
| Broken local Markdown links | **0** |
| Malformed Markdown tables | **0** |
| Hard-wrapped prose candidates | **0** |
| Duplicate Numeric Evidence IDs | **0** |
| Duplicate substantial shared paragraphs | **0** |
| Trailing whitespace / accidental tabs | **0 / 0** |

## Generation-1 toolchain maturity audit — 2026-08-30

A dedicated toolchain audit was completed after the scientific/adversarial evidence passes and before the planned implementation-contract audit. Its purpose was not to add novel algorithms; it converted the existing tool landscape and Primer Design Literature Hub into an explicit generation-1 production/tool contract.

The audit:

- reviewed the current Literature Hub as a discovery corpus and source of implementation-critical mature-tool evidence;
- standardized `PRIMARY / VALIDATOR / FALLBACK / OPTIONAL / BENCHMARK / REFERENCE / WATCHLIST / REJECT` dispositions;
- established local-first execution, version pinning, parser-schema, database/checksum, privacy, licensing and regression requirements;
- designated a conservative shared stack centered on Primer3, MFEprimer, BLAST+, MAFFT, PrimerPooler and PrimalScheme3, with optional validators kept separate from the core;
- explicitly excluded NUPACK from the default production dependency set under its current licensing boundary;
- expanded all eleven `01-tools.md` files from simple registries into engine-specific execution/toolchain contracts without duplicating assay-specific numeric evidence;
- promoted source-verified PCR-condition salt/DMSO semantics, a modern mismatch parameter-set registry and polymerase-aware mismatch boundaries to the shared design-intelligence layer;
- promoted the source-verified EasyKASP 2025 empirical KASP profile to the owning KASP module while retaining it as an empirical/LGC-master-mix-specific profile rather than a universal default.

The resulting documentation is **toolchain-mature for implementation-contract review**, not yet a claim that runtime adapters/tests are implemented. The next gate remains the module-by-module implementation-contract audit: normalization, hard/soft constraints, candidate generation/filtering, scoring/ranking, fallback/refusal, coordinate/numeric semantics, output schema and regression fixtures.

### Toolchain-maturity release gate

| Check | Result |
| --- | ---: |
| Current Literature Hub operational resources triaged | **201 / 201** |
| Legacy/stale Hub resources dispositioned | **42 / 42** |
| Engine `01-tools.md` execution contracts | **11 / 11** |
| New structured Numeric Evidence IDs in this pass | **12** |
| Structured Numeric Evidence rows | **914** |
| Prior Numeric Evidence IDs removed | **0** |
| Prior numeric tokens removed from engine files | **0** |
| Unique external URLs in active Markdown | **747** |
| Broken local Markdown links | **0** |
| Malformed Markdown tables | **0** |
| Hard-wrapped prose candidates | **0** |
| Duplicate Numeric Evidence IDs | **0** |
| Duplicate substantial shared paragraphs | **0** |
| Trailing whitespace / accidental tabs | **0 / 0** |

## Historical-state policy

Superseded audit narratives, raw research dumps, pre-refactor Markdown archives, snapshot manifests and historical source copies are **not** carried in the current tree. Git history and prior signed source bundles are the recovery surface. Current executable/scientific claims must be promoted into their canonical owner before a historical file can be removed; a historical file itself is never runtime authority.

## Documentation QA gate

The refactored active tree must pass all of the following before release:

- local Markdown links resolve;
- Markdown table rows have consistent column counts;
- no accidental hard-wrapped prose;
- no unfinished-work markers such as the standard development placeholders;
- no trailing whitespace or accidental tabs;
- no duplicate IDs within the canonical Numeric Evidence registers;
- package ZIP passes integrity testing after creation.

Release-gate results for the active documentation tree and release archive:

| Check | Result |
| --- | ---: |
| Broken local Markdown links | **0** |
| Malformed Markdown tables | **0** |
| Hard-wrapped prose candidates | **0** |
| Unfinished-work markers | **0** |
| Accidental tabs | **0** |
| Trailing whitespace | **0** |
| Duplicate Numeric Evidence IDs | **0** |
| Prior Numeric Evidence IDs removed by toolchain release | **0** |
| Prior numeric tokens removed from changed scientific files | **0** |
| New structured Numeric Evidence rows in toolchain pass | **12** |
| Structured Numeric Evidence rows in current toolchain-mature tree | **914** |
| Unique external URLs in active Markdown | **747** |
| Engine `01-tools.md` execution contracts matured | **11 / 11** |
| Research-consolidation mismatches | **0** |
| Duplicate substantial paragraphs across active non-engine Markdown | **0** |
| Provenance archive integrity | **PASS** |
| Final package ZIP integrity | **PASS** (`unzip -t`) |


## Canonical tool-file parity + contract-normalization release — 2026-08-30

The toolchain-mature atlas received a final implementation-boundary normalization pass before the module-level implementation-contract audit. This pass did **not** promote new scientific thresholds or add novel design algorithms. It closed machine-readability and adapter-boundary ambiguities found during independent audit.

Changes in this pass:

- compound/hybrid tool-role labels were normalized to exactly one canonical role plus orthogonal qualifiers; legacy labels remain preserved in provenance;
- `Coordinate Contract v1` establishes 0-based half-open internal intervals, explicit strand, 5′→3′ oligo storage, source-coordinate retention and circular-origin segment handling;
- parameter resolution now carries `forbidden | bounded | allowed` override policy instead of relying on an ambiguous last-writer-wins precedence;
- PrimerPooler is pinned to reviewed generation-1 version `1.89` rather than an open-ended `>=1.89` runtime condition;
- release/ref identity is separated from environment-specific artifact identity, and every local production installation must record an exact SHA-256;
- [`contracts/runtime-contract.schema.json`](../contracts/runtime-contract.schema.json), [`contracts/toolchain-manifest.json`](../contracts/toolchain-manifest.json), [`contracts/engine-tool-contracts.json`](../contracts/engine-tool-contracts.json) and its schema are now normative implementation artifacts;
- all eleven engine `01-tools.md` files explicitly inherit the shared machine-readable contracts, contain production-grade execution/parameter/output/error/determinism/deployment/regression sections, and clarify the distinction between source-recorded tool-native defaults and PCRStudio assay defaults;
- runtime role resolution is now engine-scoped rather than incorrectly assuming one immutable global role per tool.

This closes the shared tool-file parity and pre-implementation structural findings. The next audit may focus on the 21 module implementation contracts rather than revisiting tool-file depth, engine-scoped roles, coordinates, override semantics or artifact identity.

### Contract-normalization release gate

| Check | Result |
| --- | ---: |
| Active Markdown | **51** |
| Engine Markdown | **44** |
| Engine `01-tools.md` inheriting canonical contracts | **11 / 11** |
| Machine-readable contract JSON files | **4** |
| Canonical tool-role enum values | **8** |
| Active compound/hybrid role labels | **0** |
| Literature-Hub operational resources normalized | **201 / 201** |
| Shared manifest tool records | **11** |
| JSON / JSON-Schema validation | **PASS** |
| Broken local Markdown links | **0** |
| Malformed Markdown tables | **0** |
| Unfinished-work markers | **0** |
| Trailing whitespace / accidental tabs | **0 / 0** |
| Unique external URLs in active Markdown | **747** |
| Assay-module scientific files changed in this normalization pass | **0** |
| Existing structured Numeric Evidence corpus | **unchanged (914 rows)** |

## Runtime-audit boundary

The historical controls/design-page audits were source-code/UI snapshots. They are not treated as perpetual current truth inside this documentation-only package. If the application source changes, runtime wiring, UI control coverage and source-level regression tests must be rerun against that repository revision. Scientific documentation completeness and runtime implementation completeness are related but distinct gates.

## Operational review boundary

Time-sensitive provider claims were reviewed during this refactor. The deployment runbook no longer treats one Oracle A1 quota as a permanent PCRStudio entitlement because current official Oracle pages expose different free-allocation descriptions depending on context. Cloudflare Quick Tunnels remain explicitly scoped to development/testing, with stable tunnels treated separately.

## Release decision

This architecture is intended to keep the scientific atlas rich while preventing document proliferation:

- science stays with the narrowest scientific owner;
- shared concepts are centralized without copying module numbers;
- audit state is one file;
- deployment is one file;
- historical research is one consolidated JSON plus one immutable Markdown archive.

A future topic should create a new file only if it has an independent canonical ownership boundary that cannot be represented without making an existing owner ambiguous.
