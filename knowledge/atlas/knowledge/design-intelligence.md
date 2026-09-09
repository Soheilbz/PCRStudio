# Cross-engine design intelligence

This document owns **computational design concepts that affect more than one PCRStudio engine**. It intentionally does not own assay-specific reaction recipes, executable profile defaults or vendor-specific numeric limits; those remain with the narrowest engine/module that actually uses them.

- **Evidence cut-off:** 2026-08-30
- **Evidence posture:** peer-reviewed evidence first; standards/current tool documentation second; preprints and patents are explicit watchlist evidence only.
- **Core rule:** a newer algorithm may extend the atlas without becoming a PCRStudio default. Promotion to an executable rule requires a defined scope, reproducible inputs, an evidence boundary and assay-appropriate validation.

## Design claim model

PCRStudio treats primer/probe design as a chain of distinct claims rather than one generic score:

1. **Candidate sequence claim** — length, GC, sequence motifs, topology and other directly computable properties.
2. **Thermodynamic-model claim** — Tm, self-structure and pair/set interaction predictions under a named model, parameter set and reagent assumptions.
3. **Target/background claim** — predicted coverage or specificity against a versioned target and background population.
4. **Set-level claim** — multiplex compatibility, pool membership, interaction graph and coverage trade-offs for the complete oligo set.
5. **Population-time claim** — robustness to geographic, taxonomic or temporal sequence variation.
6. **Empirical claim** — observed amplification, bias, analytical specificity/sensitivity or failure under a declared chemistry/platform and matrix.

A claim at one level must not silently imply the next level.

## Pass 1 — global multiplex and set-level optimization

### Multiplexing is an optimization problem, not a pair-by-pair filter

A primer pair that passes single-assay filters can still fail in a panel because every additional oligo introduces new heterodimer, off-target, target-competition, product-overlap and pool-assignment relationships. PCRStudio therefore treats a multiplex design as a **set object** with at least: candidate provenance, pair membership, panel membership, interaction graph, pool assignment, objective function, algorithm/version and unresolved interactions.

Current literature shows several distinct algorithmic paradigms rather than one universal scoring rule:

| Method | Evidence state | What it contributes to the atlas | Boundary |
| --- | --- | --- | --- |
| SADDLE (2022) | Peer reviewed | Explicit large-set dimer minimization and empirical high-plex demonstrations; historical benchmark for set-level design | Study-specific multiplex systems; not a universal dimer threshold. [Nature Communications](https://www.nature.com/articles/s41467-022-29500-4) |
| Olivar (2024) | Peer reviewed | Variant-aware tiled design integrating sequence variation, non-specificity, GC/complexity risk and set-level optimization | Tiling-focused implementation; reported comparative numbers stay tool/study specific. [Nature Communications](https://www.nature.com/articles/s41467-024-49957-9) |
| ThermoPlex (2025) | Peer reviewed | Target-specific multiplex candidate screening from target/non-target alignments plus simulated multi-reaction thermodynamic equilibrium | Input-alignment and thermodynamic assumptions are part of the result; study parameter values are not PCRStudio defaults. [Biology Methods and Protocols](https://academic.oup.com/biomethods/article/10/1/bpaf074/8283541) |
| PRISM (2026) | Peer reviewed | Formulates multiplex primer selection as constrained submodular maximization balancing genome coverage and primer-dimer `Badness`, with a mathematical approximation framework | The objective and guarantees belong to PRISM's formulation; empirical superiority in the publication does not create universal ranking weights. [Bioinformatics](https://academic.oup.com/bioinformatics/article/42/7/btag478/8722296) |
| DIMPLE (2026) | **Preprint** | A scalability precedent for extreme multiplex qPCR; the preprint reports linear-runtime generation of >10,000 primers and a 204-primer demonstration for 2,302 KMT2A fusion subtypes | Not peer reviewed as of the evidence cut-off; retain as watchlist/tool evidence, never as a production default. [bioRxiv DOI record](https://doi.org/10.64898/2026.04.17.719221) |

The correct cross-engine representation is therefore **multi-objective provenance**, not a single global “multiplex score.” At minimum retain the optimization targets and constraints separately: target coverage, background/off-target risk, interaction/dimer risk, amplicon geometry, pool balancing, assay-specific optical/readout constraints, and any hard exclusions.

### Tiling-specific routing

The detailed tiled-scheme lifecycle, PrimalScheme3 repair behavior, varVAMP graph optimization and assay-specific numeric values remain canonical in [`../engines/tiling-scheme/02-tiled-scheme.md`](../engines/tiling-scheme/02-tiled-scheme.md). The shared layer only establishes that scheme maintenance, repair and set-level optimization are first-class design operations rather than afterthoughts.

## Pass 2 — pangenome, population diversity and evolutionary drift

### Reference coverage must describe a population, not merely a reference sequence

A reference genome is a coordinate system, not proof of population coverage. For population-aware designs, retain:

- exact target population/database and release/date;
- included/excluded genomes, taxa, strains or haplotypes;
- geographical and temporal sampling boundaries when relevant;
- deduplication/quality filters;
- alignment/mapping/mining method and version;
- target-site conservation and mismatch distribution by position/type;
- background/near-neighbour population used for exclusivity;
- date of the last re-scan.

A 2026 Scientific Reports workflow demonstrates why this matters: pangenome analysis was used to identify strain-unique accessory targets for strain-specific qPCR, but an apparently unique candidate could still fail biological uniqueness and require target reselection. The transferable rule is **validate uniqueness against the relevant population/background**; the study's assay efficiencies and amplicon settings remain study-specific ([Scientific Reports 2026](https://www.nature.com/articles/s41598-026-41449-8)).

MicrobiomePrime provides a separate 2026 precedent for source-tracking marker/primer discovery from large community datasets followed by empirical down-selection. Exact corpus and validation counts remain canonical in the species-specific module rather than being duplicated here ([Water Research 2026](https://www.sciencedirect.com/science/article/pii/S0043135425018937), [`species-specific module`](../engines/flanking-pair/07-species-specific-pcr.md)).

### Alignment-free conserved-region discovery can precede local alignment

A 2026 Journal of Clinical Microbiology study adds a distinct broad-range design strategy: rather than applying a global MSA to a highly divergent genus, it used alignment-free k-mer analysis and a compacted de Bruijn graph to identify conserved candidate regions, then applied a **local** MSA only to the selected design window. The exact study values (`k = 19` for its `51`-genome Orthoflavivirus panel, local ~`600 bp` design window, oligo degeneracy cap `≤100` concrete variants and a study-specific last-`5`-base 3′ caution) remain canonical in the universal-primer module. The transferable rule is architectural: **candidate-region discovery and final oligo alignment/thermodynamic evaluation are separable stages**, and every degenerate oligo should be expanded or otherwise evaluated with semantics that represent its concrete members. The study further used modular add-on primer/probe sets when one broad-range set could not cover the full panel, demonstrating that “universal” coverage may be better represented as a typed panel than by forcing excessive degeneracy into one oligo set ([J Clin Microbiol 2026](https://journals.asm.org/doi/10.1128/jcm.00388-26), [`universal-primer module`](../engines/consensus-pair/02-universal-primers.md)).

A separate 2026 Listeria study shows the same population-genomic principle flowing into ordinary endpoint multiplex PCR: k-mer markers discovered from a large public-isolate collection were empirically down-selected in singleplex and multiplex formats. Exact corpus and multiplex results remain canonical in the species-specific module; the shared rule is that **population-scale in-silico uniqueness must still survive oligo design, chemistry and multiplex validation** ([Scientific Reports 2026](https://www.nature.com/articles/s41598-026-65481-w), [`species-specific module`](../engines/flanking-pair/07-species-specific-pcr.md)).

### Designs age

For evolving targets, `design_date`, `reference_dataset_version`, `last_population_scan`, and `drift_review_status` are part of scientific provenance. A 2026 SARS-CoV-2 analysis found substantial geographic, variant and temporal heterogeneity in mutations affecting primer/probe target sites and proposed a surveillance/redesign policy for that study context. The exact study counts and suggested interval/trigger remain canonical in the qPCR-probe module; they are **study-specific surveillance recommendations**, not universal redesign triggers ([J Med Virol 2026](https://pubmed.ncbi.nlm.nih.gov/42312714/), [`qPCR-probe module`](../engines/pair-and-probe/02-qpcr-probe.md)).

A generic drift record should therefore retain the actual mutation-frequency distribution and its sampling context. It must not collapse the result into a universal “pass/fail at X%” rule unless the assay owner has adopted and validated such a criterion.

### Community-specific bias optimization is an emerging branch

KuafuPrimer (bioRxiv, 2026) uses few-shot machine learning to optimize 16S primers for the community being studied rather than assuming one universal pair is unbiased everywhere. It remains non-peer-reviewed at this cut-off, so it is a **research/watchlist precedent for community-specific bias optimization**, not a replacement for established universal-primer rules. Exact study metrics remain in the universal-primer module ([bioRxiv](https://www.biorxiv.org/content/10.64898/2026.03.29.714677v1), [`universal-primer module`](../engines/consensus-pair/02-universal-primers.md)).

## Large-scale in-silico specificity and empirical primer evidence

Specificity tools must preserve the database and search semantics that produced a result. `AmpliconHunter v2`, already detailed in the universal-primer module, demonstrates large-scale degenerate in-silico PCR with explicit mismatch and taxonomic analysis. Its exact advertised database scale remains canonical in that module; the shared rule is that webserver scale is not proof that every PCRStudio run searched a complete biological universe ([AmpliconHunter v2](https://ah2.engr.uconn.edu/about), [`universal-primer module`](../engines/consensus-pair/02-universal-primers.md)).

Literature-mined empirical evidence is a different evidence class. Primer PICKR (Nature Communications, 2026) mines large-scale published oligo evidence and ranks RT-qPCR primer pairs using literature evidence, biophysical properties and pair synergy. Its exact corpus and validation metrics remain canonical in the qPCR-SYBR module. PCRStudio may use such resources as **empirical priors/reuse evidence**, but publication frequency is not equivalent to current specificity or validation in the user's matrix ([Primer PICKR](https://www.nature.com/articles/s41467-026-73648-2), [`qPCR-SYBR module`](../engines/flanking-pair/05-qpcr-sybr.md)).

Machine-learning predictors such as PrimerAST are similarly retained as model-specific evidence. Model features, training corpus, label construction, validation split and software/model version are required provenance; a model probability is not a wet-lab success probability outside its validated domain ([PrimerAST](https://www.nature.com/articles/s41598-026-38238-8)).

### Integrated and reproducible workflow tools — 2026 additions

Two peer-reviewed 2026 tools add useful **workflow-architecture** precedents without creating new universal primer thresholds. PrimerWeaver integrates primer QC, multiplex PCR, overlap PCR, site-directed mutagenesis, restriction cloning, Golden Gate, Gibson and USER workflows in a client-side browser application. Its design architecture explicitly separates optimization of the 3′ annealing core from application-specific 5′ tails/overlaps, then re-evaluates the full-length oligo for secondary structure. In a study-specific multiplex benchmark using `194` non-dubious yeast transcription-factor targets at target Tm `60 °C`, PrimerWeaver partitioned the resulting set into `13` compatible pools while considering primer–primer thermodynamics, amplicon-size resolution and shared off-target amplification. These numbers are a benchmark for the cited implementation, not PCRStudio defaults ([PrimerWeaver, Nucleic Acids Research 2026](https://academic.oup.com/nar/article/54/W1/W137/8687168), [current PrimerWeaver V1.0.3](https://ignea.lab.mcgill.ca/primerweaver/)).

ColabPCR (Computational Biology and Chemistry, 2026) provides a complementary reproducibility precedent: an executable Google Colab/Jupyter workflow that retrieves target genomes from NCBI by assembly accession, extracts loci/coordinates, calls Primer3 for candidate design, uses BLASTn for virtual-PCR/off-target assessment, supports restriction-enzyme analysis and custom 5′ tails, and keeps these steps in one reproducible notebook. PCRStudio treats this as a workflow/provenance benchmark rather than evidence that one notebook's settings are optimal for every assay ([ColabPCR](https://www.sciencedirect.com/science/article/abs/pii/S147692712600160X)).

## Pass 6 — databases, thermodynamic model uncertainty and reproducibility

### Database and search provenance

A specificity/coverage claim is incomplete without its reference data. At minimum retain:

- database/resource name;
- release/version or retrieval date;
- taxonomic/organism filter;
- sequence class used (genome, transcript, amplicon, rRNA, custom panel, etc.);
- search engine and version where available;
- mismatch/gap/word-size or equivalent search settings;
- whether the database was frozen, local or a live service.

NCBI Primer-BLAST combines Primer3 primer generation with sequence-similarity searching and supports organism/database selection; results are therefore conditional on the exact query and database state, not a timeless specificity certificate ([NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)).

For rRNA workflows, database families can have asynchronous releases. The universal-primer module records SSU and LSU provenance independently rather than inventing one global “SILVA version”; exact current release numbers remain with that module ([SILVA current releases](https://www.arb-silva.de/), [`universal-primer module`](../engines/consensus-pair/02-universal-primers.md)).

### Alignment provenance

Alignment uncertainty can alter apparent conservation. The consensus/universal engine therefore owns exact aligner/version/strategy provenance, including current MAFFT release and known affected-version warnings; those version numbers remain canonical there and are not duplicated in this shared layer ([MAFFT](https://mafft.ddbj.nig.ac.jp/alignment/software/), [`universal-primer module`](../engines/consensus-pair/02-universal-primers.md)).

### Thermodynamic predictions are model-dependent

Every predicted Tm, secondary structure or interaction energy is conditional on a model. A reproducible thermodynamic record should retain, where applicable:

- software and exact version;
- nearest-neighbour/free-energy parameter set;
- salt-correction model;
- Na+/K+/NH4+/Mg2+ assumptions;
- oligo and strand concentrations;
- temperature;
- material type (DNA, RNA, mixed material, modified chemistry when supported);
- dangling/coaxial/ensemble assumptions;
- whether ambiguity/degenerate sequences were expanded to concrete molecules.

Primer3 stable/development separation remains canonical in the engine tool records because the development 2.7.0 release notes include changes capable of altering Tm results; an unreleased branch must not silently alter a production contract ([Primer3 releases](https://github.com/primer3-org/primer3/releases), [development release notes](https://github.com/primer3-org/primer3/blob/main/src/release_notes.txt)).

NUPACK 4.1 is an additional cross-engine thermodynamic tool precedent. Its current documentation names `dna04.3` as the DNA default parameter set and supports DNA calculations with explicit Na+/K+/NH4+/Mg2+ conditions. Mixed RNA/DNA calculations use the `rna-dna06` model with a different supported ionic regime: sodium is parameterized, but magnesium is not supported for the mixed-material model. RNA/2′OMe-RNA uses yet another model/condition set. These are scientifically important boundaries: PCRStudio must never transplant an ionic condition or free-energy parameter set from one NUPACK material model into another merely because the software accepts both sequence types. NUPACK outputs remain **model-qualified structure/interaction predictions**, not universal PCR chemistry ([NUPACK 4.1](https://nupack.org/download/docs), [current documentation](https://www.nupack.org/docs/)).

### Current specificity/design tool surveillance

Tool surveillance is separate from scientific-rule promotion. A current tool can add useful capabilities without creating a new universal design rule. As of the evidence cut-off, the MFEprimer 4.x line has reached **v4.5.1 (2026-08-06)**. The current lifecycle matters for reproducibility: v4.5.1 can auto-detect the index `-k` value and now errors on an explicit mismatch rather than silently returning zero sites; it also hardens index publication/verification and fixes a forward-binding coordinate display issue. The immediately preceding v4.5.0 added SNP-QC columns (`fpSNP`, `rpSNP`, `fpSnpDanger`, `rpSnpDanger`) to `*.spec.tsv`, changing the output-column layout, while the 2026-07-24 service update added a human pan-genome primer check across **97 HPRC assemblies**. PCRStudio therefore records exact MFEprimer version, index/database identity and output schema whenever results are imported; server limits, database choices and column layouts remain **tool/version-specific** ([MFEprimer updates](https://www.mfeprimer.com/updates/), [MFEprimer 4](https://www.mfeprimer.com/)).

`openPrimeR` remains a useful established benchmark precedent for multiplex primer-set design by set-cover optimization, but its package/version and external dependencies must be frozen when used in a reproducible comparison; PCRStudio should not describe a historical package version as a current global reference without checking the environment used for the benchmark ([Bioconductor openPrimeR manual](https://bioconductor.org/packages/release/bioc/manuals/openPrimeR/man/openPrimeR.pdf)).

A 2026 bioRxiv preprint, *Scaling Variant-Aware Multiplex Primer Design*, adds a separate watchlist branch: reference-free Gini-impurity site risk, provable/near-linear primer-design-region optimization, and thermodynamic graph selection for multiplex panels. Because it was not peer reviewed at the cut-off, it remains **preprint evidence only** and cannot replace peer-reviewed PRISM/Olivar/ThermoPlex rules ([bioRxiv DOI](https://doi.org/10.64898/2026.02.03.703607)).

## Generation-1 toolchain maturity contract

PCRStudio generation 1 uses **mature, inspectable tools behind explicit adapters** rather than replacing them with opaque or experimental scoring models. Tool discovery is intentionally broader than the production stack: a method can remain scientifically relevant while being unsuitable as a production dependency because of licensing, remote-only execution, unstable output, narrow assay scope or insufficient maintenance.

### Tool-role vocabulary

Every **engine binding** must resolve a tool to exactly one canonical runtime role. Tool identity/version and catalog disposition are global, but the executable role is context-specific: the same tool can be `VALIDATOR` in one engine and `OPTIONAL` in another. Modifiers such as MSA ownership, tiling, remote execution, licensing blocks or optional execution are orthogonal purposes/qualifiers rather than compound role strings. The machine-readable authority is [`contracts/runtime-contract.schema.json`](../contracts/runtime-contract.schema.json), [`contracts/toolchain-manifest.json`](../contracts/toolchain-manifest.json) and [`contracts/engine-tool-contracts.json`](../contracts/engine-tool-contracts.json).

| Role | Execution meaning |
| --- | --- |
| `PRIMARY` | production candidate generation or an owning transformation required by the normal pipeline |
| `VALIDATOR` | independent local check used to reject, annotate or qualify primary output |
| `FALLBACK` | production-capable alternative used only under a declared failure/capability branch |
| `OPTIONAL` | mature enhancement that can be disabled without changing the core assay topology |
| `BENCHMARK` | comparison/regression implementation; not a normal runtime dependency |
| `REFERENCE` | manual, remote service or method used to define/verify semantics rather than to run the production worker |
| `WATCHLIST` | promising, experimental, preprint, licensing-blocked or otherwise non-production technology |
| `REJECT` | reviewed but deliberately excluded from generation-1 execution; the exclusion reason must be retained in provenance |

### Shared production stack and version policy

The role shown in this table is the **usual catalog disposition**, not an immutable engine role; the active engine binding is authoritative at runtime.

| Tool | Usual catalog disposition | Version/deployment contract | Boundary |
| --- | --- | --- | --- |
| Primer3 `primer3_core` | `PRIMARY` for ordinary primer/internal-oligo candidate generation | pin tagged `2.6.1`; local subprocess adapter; capture binary hash and complete Boulder-IO input/output | Primer3 is GPL-2-or-later; its manual explicitly distinguishes calling the executable and interpreting output from source/library linking. The unreleased 2.7.0 branch contains Tm-affecting changes and is regression-only until a tagged release is deliberately adopted ([Primer3 manual](https://primer3.org/manual.html), [releases](https://github.com/primer3-org/primer3/releases), [development release notes](https://github.com/primer3-org/primer3/blob/main/src/release_notes.txt)) |
| `primer3-py` | `OPTIONAL` development/test adapter | current `2.3.1`; Python `>=3.8`; never silently substitute its bundled Primer3 behavior for the pinned production executable | GPLv2 Python/Cython wrapper; import/linking has a different licensing boundary from process execution and therefore requires deliberate product/legal review ([primer3-py 2.3.1](https://pypi.org/project/primer3-py/2.3.1/)) |
| MFEprimer | `VALIDATOR` for local specificity/amplicon/interaction checks | pin `4.5.1`; local CLI; parser is version/schema-aware; index k-mer setting and database hash are part of provenance | v4.5.1 auto-detects index `-k` and rejects mismatches; v4.5.0 changed SNP-QC TSV columns, so output layout must never be parsed without a version contract ([MFEprimer updates](https://www.mfeprimer.com/updates/), [CLI workflow](https://www.mfeprimer.com/mfeprimer-3.1/), [license/use statement](https://mfeprimer.com/license/)) |
| NCBI BLAST+ | `VALIDATOR` | pin `2.17.0`; local database preferred for privacy/reproducibility; capture task, scoring/masking settings, database build and checksum | live NCBI databases are moving targets; a specificity result is valid only with the exact query and database provenance ([BLAST+ 2.17.0 release notes](https://www.ncbi.nlm.nih.gov/books/NBK131777/)) |
| MAFFT | `PRIMARY` MSA for population/universal/tiling workflows | pin `7.526`; production minimum `>=7.487`; local CLI; record exact strategy/options and input-order identifiers | versions `7.463–7.486` had a serious FFT-NS-i/`--auto` bug; use the core/without-extensions build unless extension functionality is explicitly required ([MAFFT](https://mafft.cbrc.jp/alignment/software/), [source distributions](https://mafft.cbrc.jp/alignment/software/source.html)) |
| PrimerPooler | `VALIDATOR` | pin `1.89` and capture `--version`; local CLI; use explicit non-interactive parameters and a declared randomization policy | versions changed important pool-size/default semantics; `--dg` defaults include `45 °C`, `0 mM` Mg, `50 mM` monovalent cation and `0 mM` dNTP, and `--amp-max` defaults to `220`; these are **tool defaults**, not PCRStudio assay defaults. Apache-2.0 from v1.72 ([PrimerPooler](https://github.com/ssb22/PrimerPooler)) |
| PrimalScheme3 | `PRIMARY` for tiled-scheme generation/repair | pin `3.3.0`; Python `>=3.11,<3.14`; invoke as an external process and capture config/BED/MSA plus command line | GPL-3.0-only. `scheme-create` exposes amplicon size, overlap, pool count, dimer threshold, base-frequency, mapping and circularity; lifecycle commands include interaction inspection and repair/replacement ([PyPI](https://pypi.org/project/primalscheme3/), [CLI](https://github.com/artic-network/primalscheme3)) |
| ViennaRNA | `OPTIONAL` structure/accessibility validator | pin `2.7.2` when enabled; select an explicit DNA parameter file rather than relying on RNA defaults | provides Mathews 1999/2004 DNA parameter sets; its structure energies do not share the same semantics as Primer3 Tm/dimer penalties and therefore stay a separate feature family ([ViennaRNA releases](https://github.com/ViennaRNA/ViennaRNA/releases), [energy parameters](https://viennarna.readthedocs.io/en/latest/eval/energy_parameters.html)) |
| NUPACK 4.x | `REFERENCE` | no automatic runtime integration unless an appropriate license is separately obtained | current standard academic license prohibits redistribution and web/GUI use and is non-commercial; commercial use requires separate licensing. Its model-qualified predictions remain scientifically useful reference evidence ([NUPACK license](https://docs.nupack.org/), [licensing overview](https://www.nupack.org/download/overview)) |
| NCBI Primer-BLAST | `REFERENCE` independent remote validation | optional user-invoked comparison only; record organism/database and retrieval time | remote service/database state is not frozen and target sequences leave the local execution boundary ([Primer-BLAST](https://www.ncbi.nlm.nih.gov/tools/primer-blast/)) |
| pydna | `OPTIONAL` current-adapter PCR-product simulation for junction/outward/mutagenic workflows; broader pydna library capabilities remain future adapter work | pin `5.5.16` if enabled; local Python adapter | useful for PCR/assembly simulation but not the owning candidate generator; current PyPI release is 5.5.16 ([pydna 5.5.16](https://pypi.org/project/pydna/5.5.16/)) |

Vendor browser tools, Excel/VBA tools, web-only primer designers and experimental/ML optimizers can define or benchmark a contract but are not silent backend dependencies. Their numerical guidance belongs to the owning assay when source-scoped; their executable role defaults to `REFERENCE`, `BENCHMARK` or `WATCHLIST` unless a stable automatable interface is separately established.

### Canonical role + qualifier model

A runtime record stores **one engine-resolved** `tool_role` from the eight-value enum and zero or more orthogonal qualifiers/purposes. MAFFT is `PRIMARY` in engines that own an MSA step; PrimalScheme3 is `PRIMARY` for tiled-scheme creation/repair; PrimerPooler is `VALIDATOR` in `tiling-scheme` but `OPTIONAL` in `nested` or ordinary flanking contexts; NUPACK remains `REFERENCE` under the current deployment boundary. Historical compound labels are retained only as provenance aliases and must not reach runtime schemas. Engine-scoped bindings are normative in [`engine-tool-contracts.json`](../contracts/engine-tool-contracts.json).

### Coordinate Contract v1

The canonical internal coordinate system is **0-based, half-open**: `[start0, end0)`. `start0` is included and `end0` is excluded. Intervals always increase along the stored reference regardless of strand. Strand is a separate `+`/`-` field; primer/oligo sequence is always stored 5′→3′ in synthesis/read orientation. A single-base locus is stored as its zero-based position. Every adapter must preserve the source tool/database coordinate representation in provenance before conversion.

Circular references never encode origin crossing by making `end0 < start0`. An origin-spanning binding/product region is represented by an ordered list of normalized half-open segments modulo the declared reference length. External formats such as Primer3/Boulder-IO, BLAST, BED, VCF, GenBank and vendor reports are converted at adapter boundaries and round-trip fixtures must cover forward, reverse, boundary and circular-origin cases.

### Artifact identity and installation lock

A semantic version is necessary but insufficient for reproducibility. Every local production dependency must resolve during build/install to an exact source/package/binary/container identity and SHA-256; the resulting digest is written to the deployment lock and run provenance. The canonical manifest pins the accepted release/ref while deliberately leaving the environment-specific artifact digest to the build/install step. A mismatch between the accepted version/ref and the installed artifact is a deployment failure, not a warning. Remote/manual `REFERENCE` services have no production artifact digest and can never satisfy a local production dependency.

### Adapter contract

Every production adapter exports a common execution envelope in addition to tool-specific output:

```text
engine_id  module_id  operation_id  binding_contract_version
tool_id  tool_role  tool_version  executable_or_package_hash
execution_scope  license_class  command_or_api  parameter_map_version
input_schema_version  output_schema_version  database_id  database_hash
started_at  elapsed_ms  exit_status  stdout_digest  stderr_digest
random_seed_or_determinism  warnings  unresolved_assumptions
```

Tool-native coordinates, sequence orientation, missing values and numeric units are normalized **at the adapter boundary**; raw output is retained for regression/debugging. A parser must fail closed on an unknown output schema instead of guessing column meaning. Remote execution is opt-in and must be visible in the result because target sequences can leave the local trust boundary.

### Parameter resolution and override policy

Parameter resolution is **not** a last-writer-wins cascade. Every executable value carries a source layer and `override_policy = forbidden | bounded | allowed`. The canonical resolution order is:

1. **tool hard capability** and syntax/type limits;
2. **assay hard constraint** from the owning module;
3. **locked chemistry/kit/platform constraint**;
4. a validated **explicit user override** when the preceding constraints permit it;
5. selected **chemistry/kit/platform recommendation**;
6. PCRStudio **recommended default**;
7. a **tool-native default** only when PCRStudio deliberately adopts and version-pins it.

A user value cannot break a `forbidden` constraint and must remain inside declared bounds for `bounded`. Tool-native defaults never become PCRStudio scientific defaults merely because a CLI flag was omitted. Every resolved parameter records value, unit, source layer, override policy, bounds/source identifier and any rejection or warning using the canonical `ParameterResolution` schema.

### Core adapter parameter surfaces

The shared stack is intentionally narrow enough that its production-relevant parameter surfaces can be audited explicitly.

**Primer3.** The engine-specific Primer3 tool record owns the detailed Boulder-IO vocabulary. The cross-engine adapter additionally records `PRIMER_TASK`, all explicit `SEQUENCE_*` constraints, primer/internal pick flags, length/Tm/GC/product windows, thermodynamic/salt/formula selections, oligo/divalent/dNTP concentrations, mispriming/template libraries, returned-candidate count, first-base-index semantics and any overhangs. PCRStudio should emit parameters explicitly rather than depend on a changing upstream default when the value affects candidate eligibility or ranking ([Primer3 manual](https://primer3.org/manual.html)).

**MFEprimer 4.5.1.** Production modes are separated by intent (`index`, `spec`, `qc`, `search`, `dimer`, `hairpin`) and are not treated as one opaque “specificity score.” The adapter records primer input, every `-d` database/index, the index k-mer value, Tm/binding thresholds, `--mono`, `--diva`, `--dntp`, `--oligo`, whether `--bind-amp-only`/binding detail was requested, and output/report mode. For large/repeat-rich genomes, the current guide recommends choosing `-k` at index time, using the same k across split indexes, omitting query `-k` so v4.5.1 reads it from the index, and considering `--bind-amp-only`; PBN/MBN, intended product sequence and the 3′ binding alignment remain distinct evidence fields ([MFEprimer large-genome guide](https://www.mfeprimer.com/large-genome/), [updates](https://www.mfeprimer.com/updates/)).

**BLAST+ 2.17.0.** The adapter records `program/task`, `word_size`, reward/penalty or equivalent scoring, gap costs, DUST/masking policy, strand, e-value, HSP/target retention limits, output fields/format and thread count. `max_target_seqs` and database order can affect retained tabular hits, so the production parser must request sufficient hits for the specificity contract rather than accept a small reporting default as evidence of absence. BLAST+ exit codes are typed: `0` success; `1` query/options; `2` database; `3` engine; `4` out-of-memory; `5` network; `6` output-file; `255` unknown, and the adapter maps these to retry/refuse states rather than “no hits” ([BLAST+ options and exit codes](https://www.ncbi.nlm.nih.gov/books/NBK279684/), [release notes](https://www.ncbi.nlm.nih.gov/books/NBK131777/)).

**MAFFT 7.526.** The adapter records input material, exact command/strategy (including whether `--auto` chose the strategy), thread setting, sequence order/IDs and output hash. Production builds use the core/without-extensions distribution unless an extension is explicitly required; the core license permits redistribution under its stated notice/conditions, while bundled extensions require their own notices ([MAFFT source](https://mafft.cbrc.jp/alignment/software/source.html), [core license](https://mafft.cbrc.jp/alignment/software/license.txt)).

**PrimerPooler.** The adapter uses non-interactive CLI mode and records score versus `--dg` mode, ΔG evaluation temperature, Mg²⁺/monovalent/dNTP concentrations, requested/suggested pool count, `--max-count`, genome/variant scanning, `--amp-max`, fixed-pool tags and randomization/`--seedless` state. Current documentation notes that v1.85 changed the default annealing temperature from `37 °C` to `45 °C`, v1.87 changed maximum-pool-size semantics to product counts, v1.88 fixed an exact-fill infinite loop and v1.89 fixed a fixed-pool edge case; PCRStudio therefore pins reviewed generation-1 version `1.89`; any later version requires the tool-upgrade regression gate before adoption ([PrimerPooler](https://github.com/ssb22/PrimerPooler)).

**PrimalScheme3 3.3.0.** The owning tiling tool file records `scheme-create` values and lifecycle commands. The shared adapter also retains Python/package version, input MSA hash, generated `config.json`, BED outputs and exact command so a repair/replacement run can be traced back to the scheme-generation state ([PrimalScheme3 PyPI](https://pypi.org/project/primalscheme3/)).

### Candidate and validator normalization

Candidate generators should normalize to a tool-independent result object containing at least sequence, role/orientation, canonical coordinates, full oligo versus annealing-core sequence, length, Tm/model, GC, product coordinates/size, tool penalty, hard-filter state and source-tool provenance. Validators add independent feature families rather than overwriting the generator's values: specificity hits/products, self/hairpin/heterodimer metrics, population coverage, pool interactions and warnings remain separately attributable.

A generation-1 ranking pipeline should therefore compare normalized features and explicit hard/soft rules rather than compare incomparable raw scores from different tools. “Best candidate” means best under the owning assay's declared ranking contract, not the candidate with the smallest opaque vendor/tool score.

### Historical interaction-scoring precedents

AutoDimer remains useful as a **historical benchmark**, not a production dependency. NIST describes it as an unsupported/legacy primer-dimer and hairpin screening tool for short oligos and multiplex development. Its original alignment-based scoring and explicit attention to 3′ interactions are valuable regression precedents, but PCRStudio generation 1 uses current Primer3/MFEprimer/PrimerPooler features and modern parameter sets instead of adopting AutoDimer's historical score as a universal biochemical threshold ([NIST AutoDimer](https://www-s.nist.gov/dnaAnalysis/)).

### Database, cache and privacy contract

Local, versioned databases are preferred for automated specificity and alignment work. At minimum a database-backed result retains resource name, assembly/taxonomy scope, build/retrieval date, preprocessing command, content checksum and tool-index parameters. Cache keys include the normalized request, tool version, parameter map version and database checksum; a database update intentionally invalidates the corresponding specificity cache.

### Regression gate for tool upgrades

A production tool is upgraded only after a fixture suite compares old and new versions on representative requests for every engine that consumes it. The gate records candidate count/order, normalized sequences/coordinates, Tm/structure metrics, specificity products, warning/refusal changes, parser schema and runtime failures. A version change that alters results is not automatically wrong, but it requires a documented migration decision before the new version becomes canonical.

### Literature-hub extraction status for generation 1

The Primer Design Literature Hub is a **discovery corpus**, not a production dependency. Its current archive was reviewed specifically for mature tool/parameter evidence. Full-text-derived values are promoted only after source-level verification; index-only or OCR-suspect equations remain reference candidates. The generation-1 selection deliberately favors stable local tools and transparent adapters over novel model complexity.

### PCR-condition salt and additive parameter set

A PCRStudio thermodynamic profile must distinguish **measured reagent concentrations** from the effective-ion approximation used by a chosen model. von Ahsen, Wittwer and Schütz evaluated 475 matched/mismatched duplexes under PCR-oriented conditions and proposed a PCR-context equivalent-monovalent approximation:

\[
[Na^+_{eq}]_{mM} = [\text{monovalent cations}]_{mM} + 120\sqrt{[Mg^{2+}]_{mM}-[dNTP]_{mM}}
\]

and an empirical DMSO adjustment of approximately `−0.75 °C` per `1%` DMSO. The same paper reports an entropy salt correction `ΔS([Na+]) = ΔS(1 M) + 0.847 n ln[Na+]`, with `n = oligo_length − 1`, and an alternative empirical Tm equation. These are a **named historical PCR-condition parameter set**, not universal chemistry: PCRStudio must store the raw monovalent/Mg²⁺/dNTP/DMSO inputs and the selected correction model separately, reject/flag mathematically invalid `Mg²⁺−dNTP` use, and never mix this conversion with another tool's native divalent-ion treatment without an explicit adapter rule ([von Ahsen et al., 2001](https://pubmed.ncbi.nlm.nih.gov/11673362/)).

### Mismatch thermodynamic parameter-set registry

Mismatch scoring must identify the parameter set rather than use one generic “mismatch penalty.” A 2024 nearest-neighbour parameterization was fitted to `4096` melting measurements, optimized `252` independent parameters and covers all single/double plus part of triple-mismatch configurations at low sodium. The reported training and validation prediction deviations were approximately `1.1 °C` and `2.7 °C`, respectively. Its ionic/training scope is distinct from high-salt historical sets; using the model outside its validated ionic regime must be labelled extrapolation ([de Oliveira Martins & Weber, 2024](https://pubmed.ncbi.nlm.nih.gov/38157701/)).

Independent PCR experiments further show that a primer-template mismatch cannot be assigned one polymerase-independent amplification penalty. A 2024 study evaluated `111` mismatch combinations with polymerases differing in proofreading activity and found materially different responses, especially for terminal mismatches. Implementation records therefore separate `mismatch_identity`, `position_from_3prime`, `neighbour_context`, `polymerase_identity/family`, `proofreading_status`, ionic/reaction context and the thermodynamic model; thermodynamic destabilization is not automatically an amplification-efficiency prediction ([Huang et al., 2024](https://www.mdpi.com/2073-4425/15/2/215)).

## Formal benchmark framework for PCRStudio

A claim that PCRStudio is “more comprehensive” than another tool should be demonstrated by a reproducible benchmark rather than asserted from file count. The benchmark unit must be a **task class**, because a universal-primer tool, a tiled-panel optimizer and a qPCR assay designer solve different problems.

Recommended benchmark dimensions are:

| Dimension | What must be compared |
| --- | --- |
| Assay/topology scope | Supported request types, oligo roles, circular/linear/degenerate/multiplex topologies |
| Candidate-generation coverage | Ability to generate feasible candidates under matched input constraints |
| Target coverage | Versioned target-panel coverage and mismatch-position behavior |
| Background specificity | Same frozen background database and same search semantics where technically possible |
| Thermodynamic transparency | Model/version/salt/concentration provenance and reproducibility |
| Set-level behavior | Cross-dimer/off-target handling, pooling, repair and global optimization |
| Population/drift awareness | Dataset/version capture, variant masking, redesign/repair support |
| Evidence depth | Literature/vendor/standard provenance, conflict retention, unresolved-boundary handling |
| Failure behavior | Whether impossible/ambiguous cases are rejected, degraded, or silently forced |
| Reproducibility | Versioned software, parameters, random seeds, database snapshot and machine-readable output |
| Computational performance | Runtime/memory only under matched datasets/hardware; never compare unqualified headline timings |
| Empirical validation | Wet-lab evidence must be separated from purely in-silico benchmark metrics |

No single composite score is required. A multidimensional benchmark prevents a tool that excels at one narrow task from being mislabeled “best” overall.

## Canonical ownership map

| Shared topic | Canonical detailed owner |
| --- | --- |
| Pair thermodynamics, generic pair vocabulary and tool semantics | relevant engine `01-tools.md` |
| Universal/degenerate coverage, concrete-member expansion, alignment provenance and AmpliconHunter | [`../engines/consensus-pair/02-universal-primers.md`](../engines/consensus-pair/02-universal-primers.md) |
| Allele discrimination and mismatch-dependent genotyping | [`../engines/discriminating-pair/`](../engines/discriminating-pair/) |
| Species/strain-specific inclusivity/exclusivity | [`../engines/flanking-pair/07-species-specific-pcr.md`](../engines/flanking-pair/07-species-specific-pcr.md) |
| Tiled-panel optimization, pooling and repair lifecycle | [`../engines/tiling-scheme/02-tiled-scheme.md`](../engines/tiling-scheme/02-tiled-scheme.md) |
| Digital-PCR multiplex/platform constraints | [`../engines/flanking-pair/06-digital-pcr.md`](../engines/flanking-pair/06-digital-pcr.md) |
| Hydrolysis-probe multiplex/readout constraints and drift-sensitive probe design | [`../engines/pair-and-probe/02-qpcr-probe.md`](../engines/pair-and-probe/02-qpcr-probe.md) |
| Literature-mined qPCR primer evidence and ML primer scoring | [`../engines/flanking-pair/05-qpcr-sybr.md`](../engines/flanking-pair/05-qpcr-sybr.md) |

## Required cross-engine provenance fields

When a design-intelligence feature is used, retain the narrowest applicable subset of:

- `target_dataset`, `target_dataset_version`, `retrieved_at`;
- `background_dataset`, `background_dataset_version`;
- `geography`, `time_window`, `taxonomic_population_boundary`;
- `alignment_tool`, `alignment_version`, `alignment_parameters`;
- `search_tool`, `search_version`, `search_parameters`;
- `thermodynamic_tool`, `thermodynamic_version`, `parameter_set`, `ionic_conditions`, `strand_concentrations`;
- `optimization_algorithm`, `optimization_objectives`, `hard_constraints`, `random_seed`;
- `panel_members`, `interaction_graph`, `pool_assignment`;
- `design_date`, `last_drift_scan`, `drift_dataset`;
- `evidence_class` (`peer_reviewed`, `standard`, `vendor_current`, `preprint`, `patent`, `internal`);
- `unresolved_assumptions` and `required_empirical_validation`.

## Promotion rule

A cross-engine research finding may change an assay module only when it has an assay-specific consequence. Shared principles remain here; exact assay values, named chemistry/platform limits, runtime defaults and validation records remain in the owning module. This prevents the atlas from gaining knowledge by duplicating it.
