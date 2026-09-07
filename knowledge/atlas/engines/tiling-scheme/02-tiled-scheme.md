# Tiled scheme — tiling-scheme engine record

| Field | Value |
| --- | --- |
| Profile ID | `tiled-scheme` |
| Runtime profile status | experimental |
| Goal | `sequence` |
| Modifiers | none |
| Purpose modes | `sequencing` is the default; the profile exposes `general` and `sequencing` |
| Evidence status | bounded nominal-coverage scheme; depth and variant recovery remain experimental |
| Last reviewed | 2026-08-30 |

## Scope

A tiled scheme divides a long target into ordered, usually overlapping amplicons. Multiplex implementations may partition primers into separate pools to reduce cross-primer interactions, but the number of pools and the overlap are scheme-specific. The output is a versioned scheme, not just a flat primer list: the ARTIC interchange unit couples `primer.bed` to the matching `reference.fasta`, with primer coordinates, strand, sequence, amplicon name and pool recorded; overlap and wet-lab validation are additional metadata, not required BED columns ([ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)).

The module owns target class, amplicon window, overlap policy, pool assignment, variant masking and sequencing handoff. Nominal coverage must be separated from uniform depth and variant sensitivity because primer interactions, dropouts and circulating variation can create coverage bias ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/), [Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)).

## Atlas overlay

| Dimension | Module decision | Evidence and boundary |
| --- | --- | --- |
| Scheme order | immutable amplicon numbering; records may be sorted/validated by amplicon number | The ARTIC name contains a positive, incrementing amplicon number; the BED format itself does not make overlap a field ([ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)) |
| Amplicon overlap | explicit per adjacent pair; no universal number | Overlap and amplicon architecture are scheme-specific ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)) |
| Pool assignment | explicit; one pool ID may be shared by many primers and alternate pools are a workflow choice | ARTIC requires a positive integer pool field; the V4 release documents odd/even pools and primer-interaction mitigation ([ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [ARTIC V4 scheme release](https://community.artic.network/t/sars-cov-2-version-4-scheme-release/312/1)) |
| Variant masking | report primer-binding variants and risk intervals | Variant-aware redesign is required to reduce dropout risk ([Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)) |
| Readout | sequencing platform and library handoff are typed fields | Scheme specifications define a handoff format, not uniform run performance ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)) |
| Claim boundary | `limited` until run depth, dropout and consensus accuracy are measured | In-silico nominal coverage cannot prove uniform recovery ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)) |

## Parameter audit

| Parameter | Decision | Source-to-parameter record |
| --- | --- | --- |
| `target_interval` | required | The scheme is defined against a declared target ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)) |
| `amplicon_order` | required and gap-checked | Ordered scheme records are required for downstream primer handling ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)) |
| `amplicon_interval` | required per amplicon | Coordinates define coverage and overlap ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)) |
| `overlap_length` | module/profile-resolved; no global value | Tiling schemes use architecture-specific overlaps ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)) |
| `pool_id` | required positive integer; shared by all primers in the same PCR pool | The format requires a positive integer pool field; uniqueness applies to primer names, not pool IDs ([ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)) |
| `primer_binding_variants` | calculated against a declared variant set | Variant-aware schemes track binding-site risk ([Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)) |
| `tails` | optional workflow metadata; not an ARTIC BED requirement | The format permits arbitrary primer attributes, while library tails belong to the selected library protocol ([ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)) |
| `coverage_report` | report nominal bases and uncovered/risk intervals separately | Coverage bias and dropout are experimentally observed risks ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)) |
| `reference_id` / `coordinate_system` | emitted as scheme metadata; PCRStudio's internal format is `pcrstudio-tiling-v1` with `0-based, half-open` primer intervals | ARTIC requires `chrom` to match an ID in the accompanying FASTA and defines primer start/end as zero-based, half-open; `pcrstudio-tiling-v1` is internal, not an ARTIC identifier ([ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)) |

## Runtime profile binding

| Profile field | Current binding |
| --- | --- |
| `polymerase` | `proofreading` |
| `constraints` | `product_min`, `product_max`, `tm_min`, `tm_opt`, `tm_max`, `tm_pair_max_difference`, `length_min`, `length_opt`, `length_max`, `gc_min`, `gc_max`, `gc_clamp`, `max_end_gc`, `max_poly_x` |
| `purposes` | `general`, `sequencing` |
| scheme metadata | `reference_id`, `coordinate_system`, `scheme_format`; each tile also exposes BED-like left/right primer intervals |

The profile binding is an internal execution surface; coverage and variant-recovery claims remain conditional on the cited tiling evidence ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)).

## Numeric baseline disposition

| Profile field | Current software baseline | Evidence status |
| --- | --- | --- |
| `product_min` / `product_max` | `300–500 bp` | internal nominal amplicon envelope for the current scheme profile; it is not a universal sequencing-scheme size rule (see `tiling_profile_software_baseline` in the Numeric evidence register) |
| `tm_min` / `tm_opt` / `tm_max` | `59 / 61 / 64 °C` | internal pooled-primer starting envelope; pool balance and platform must be validated (see `tiling_profile_software_baseline`) |
| `tm_pair_max_difference` | `2 °C` | internal coupled-pair baseline for a pool, not a coverage or dropout guarantee (see `tiling_profile_software_baseline`) |
| `length_min` / `length_opt` / `length_max` | `20 / 24 / 30 nt` | internal candidate baseline; binding-site variants and pool interactions remain separate checks (see `tiling_profile_software_baseline`) |
| `gc_min` / `gc_max` | `30–65%` | internal search envelope for scheme coverage, not a universal platform recipe (see `tiling_profile_software_baseline`) |
| `gc_clamp` / `max_end_gc` / `max_poly_x` | `1 / 3 / 5` | internal candidate filters; dropout and depth require run evidence (see `tiling_profile_software_baseline`) |
| `pools` | explicit integer `>=1` for PrimalScheme3 create operations; PCRStudio applies no additional biological upper bound | This mirrors the pinned PrimalScheme3 `--n-pools` CLI contract. Pool count is scheme/tool configuration, not a universal PCR validity constant ([PrimalScheme3 GitHub](https://github.com/artic-network/primalscheme3)) |
| `overlap` / `slide` | `overlap=0` is refused; an explicit `slide=0` means no recovery search, while omission uses the profile starting value | A zero overlap is not a tiled overlap, and any start-sliding tolerance changes the declared scheme coordinates; both choices must remain explicit in the scheme record ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)) |

No universal overlap length, pool count, depth threshold or variant-frequency cutoff is embedded here. The profile values are nominal design baselines and must remain versioned with the scheme and sequencing protocol ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)).

## Interchange and coverage rules

The ARTIC primer-scheme specification makes the reference sequence and primer table a coupled reproducibility unit. A scheme record must retain reference identity, zero-based half-open primer coordinates, primer name/class, pool, strand, 5′→3′ sequence and any declared attributes; a primer table without the matching reference cannot be treated as a complete scheme. The specification is deliberately minimal: scheme-level metadata, overlap, chemistry, run platform and evidence state remain outside the interchange format ([ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)).

The specification also distinguishes the formal interchange format from biological validation. PCRStudio now preserves a scheme-format label, reference identifier and machine-readable primer intervals, but it does not accept or invent `draft`, `tested` or `validated` evidence states; nominal coverage therefore remains nominal and is never promoted to measured depth or consensus accuracy ([ARTIC primer scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)).

Primer-site sequence is potentially masked in the read data, so overlapping neighbouring amplicons are not merely redundancy: they provide independent evidence for regions occupied by primer sites. The workflow must trim primer sequences with the scheme metadata, retain the overlap map and flag gaps created when a read is too short to span the relevant assignment/overlap boundary ([ARTIC beginner's guide](https://community.artic.network/t/a-beginners-guide-to-artic/531), [ARTIC amplicon pipeline guidance](https://artic-tools.readthedocs.io/en/latest/primerscheme/)).

For degraded or low-quality input, shorter amplicons can improve recoverability, but changing the target length changes the number of amplicons, pool balance and scheme version. The length choice must therefore be an explicit design parameter tied to sample quality and sequencing platform, not an automatic “more sensitive” switch ([ARTIC beginner's guide](https://community.artic.network/t/a-beginners-guide-to-artic/531)).

## Chemistry and protocol branches

The following branches must not be merged into the generic design baseline. The published ARTIC V4 implementation uses Q5 Hot Start High-Fidelity 2X Master Mix in a multiplex cDNA reaction and is not the same recipe as NEB's routine single-pair Q5 protocol. NEB's manufacturer protocol specifies `1X` master mix, `0.5 µM` each primer, `25–35` cycles, `50–72 °C` annealing, `72 °C` extension at `20–30 s/kb`, and warns that Q5 does not incorporate dUTP; these are vendor starting conditions, not ARTIC multiplex conditions ([NEB Q5 Hot Start High-Fidelity 2X Master Mix protocol](https://www.neb.com/en-us/protocols/protocol-for-q5-hot-start-high-fidelity-2x-master-mix-m0494)).

The ARTIC V4 branch instead uses a low multiplex-primer concentration and a two-stage cycling programme reported for the specific cDNA/Q5 workflow below. An RNA input branch also needs a reverse-transcription record: the ARTIC Ebola SOP uses SuperScript IV with random hexamers and an RT-specific programme before Q5 amplification. That RT chemistry is not implied by the tiled-scheme engine and must not be substituted into a DNA workflow ([ARTIC Ebola sequencing SOP](https://artic.network/viruses/ebov/ebov-seq-sop.html)).

## Numeric protocol overlay: ARTIC-style two-pool scheme

The ARTIC SARS-CoV-2 scheme is retained as a named sequencing overlay rather than as a universal tiling recipe. The V4 release describes a continuous tiling path with amplicons no longer than approximately `400 bp` and uses `2` alternating primer pools to address primer interactions. Individual oligos can be resuspended at `100 µM`, pooled by odd/even amplicon assignment, and diluted `1:10` to a `10 µM` working pool. One published V4 implementation used `2` reactions per sample, with each `12.5 µL` reaction containing `3 µL` water, `6.3 µL` Q5 Hot Start High-Fidelity `2X` Master Mix, `1.9 µL` primer pool and `1.3 µL` cDNA; the final concentration was `0.015 µM` per primer ([ARTIC FAQ](https://community.artic.network/t/frequently-asked-questions-about-artic-protocol/34), [ARTIC V4 optimisation study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891481/)).

The same V4 implementation recorded a `98 °C/30 s` initial cycle, followed by `25` cycles of `98 °C/30 s` and `65 °C/5 min`, then `15` cycles of `62.5 °C/5 min` and `98 °C/15 s`, with a final `62.5 °C/5 min` step and a `4 °C` hold. Because that cycling programme is tied to the cited cDNA/Q5/ARTIC workflow, the module must preserve it as protocol metadata and must not apply it to arbitrary genomic tiling, another polymerase or another amplicon architecture ([ARTIC V4 optimisation study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891481/)).

Primer weighting is also a first-class numeric field. The current ARTIC scheme specification permits a positive floating-point `primerWeight`; the effective concentration is `primerWeight × typical PCR concentration`. A value of `1.0` therefore means the unweighted pool concentration, while values such as `2.0` represent deliberate enrichment of a weak amplicon and must be retained with the scheme version and validation evidence ([ARTIC primer-scheme specification v3](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [ARTIC V4.1 update](https://community.artic.network/t/sars-cov-2-v4-1-update-for-omicron-variant/342)).

## Current PrimalScheme3 design branch

PrimalScheme3 is now a distinct, current design implementation that should be represented explicitly rather than treating all ARTIC-style scheme generation as one historical tool. The current public web application identifies itself as `PrimalScheme v3.3.0`, accepts up to `10` FASTA inputs with a maximum of `10 MB` each, and uses an existing alignment directly or MAFFT for unaligned input. The web UI may guide users toward multiple pools, but the pinned PrimalScheme3 CLI accepts `--n-pools >=1`; PCRStudio follows the CLI for executable strict validation rather than turning a web-form convention into a biological rule ([PrimalScheme web application](https://primalscheme.com/)).

The current `primalscheme3` CLI/PyPI `3.3.0` `scheme-create` contract gives a default amplicon size of `400` with allowed target size `100–2000` and a min/max window of `±10%`, minimum overlap default `10`, pool count default `2` (`≥1` in the CLI), dimer-score threshold default `−26.0`, minimum base-frequency default `0.0`, and default mapping mode `first`; circular mode, backtracking and high-GC handling are opt-in, while a mispriming match database is enabled by default. These are software defaults and search semantics of PrimalScheme3, not PCRStudio defaults and not wet-lab acceptance criteria ([PrimalScheme3 GitHub](https://github.com/artic-network/primalscheme3), [primalscheme3 3.3.0 on PyPI](https://pypi.org/project/primalscheme3/3.3.0/)).

This tool branch complements, rather than replaces, the ARTIC `primer.bed`/`reference.fasta` interchange contract. In particular, scheme algorithm/version, input alignment provenance, circular topology, base-frequency filtering, pool count and dimer threshold must be exported with a generated scheme so that a later redesign is reproducible ([ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [PrimalScheme3 GitHub](https://github.com/artic-network/primalscheme3)).

## Deep-search enrichment — tiling algorithm and scheme lifecycle

The previous record included varVAMP as a degenerate-primer precedent but did not capture its tiled-scheme optimization contract. In tiled mode, varVAMP constructs a weighted directed graph in which candidate amplicons are vertices and compatible overlaps are edges; edge weights incorporate off-target status and amplicon penalty. It searches the graph with Dijkstra's shortest-path algorithm for high-coverage/low-penalty paths, assigns non-adjacent amplicons into `2` pools, then checks within-pool heterodimers and performs only `1` primer-swapping repair round. Remaining interactions can be reported as unsolved. These details are algorithm semantics, not generic tiling laws, and belong to the versioned varVAMP tool record ([varVAMP](https://www.nature.com/articles/s41467-025-60175-9)).

PrimalScheme3 must also be modeled as a **scheme lifecycle**, not only initial design. Current CLI commands include `repair-mode` for adding primers to accommodate new mutations, `scheme-replace` for replacing a primer pair in an existing BED scheme, `interactions`, `visualise-primer-mismatches`, and `panel-create`. The original MSA, BED/config, command/version and repair/replacement event therefore belong in provenance whenever a maintained scheme differs from its original design ([PrimalScheme3 GitHub](https://github.com/artic-network/primalscheme3)).

Tiled ClickSeq is retained as an adjacent topology rather than forced into this pair-based engine. The patent family describes a tiled sequencing method using one template-specific RT primer per amplicon, stochastic `3′`-azido termination and click-ligation of a downstream adaptor, so a second template-specific primer is not required. The patent describes one primer pool even with `>300` template-specific primers and claimed amplicon lengths of `100–10,000 nt`. These are patent/architecture records, not PCRStudio pair-scheme defaults ([WO2021257963A1](https://patents.google.com/patent/WO2021257963A1/en), [US12359266B2](https://patents.google.com/patent/US12359266B2/en)).

### Deep-search numeric evidence addendum

| Parameter ID | Exact value or rule | Scope / condition | Operational role | Evidence boundary |
| --- | --- | --- | --- | --- |
| `varvamp_tiled_graph_contract` | weighted directed amplicon graph; Dijkstra shortest path; `2` non-adjacent amplicon pools; `1` heterodimer primer-swapping repair round | varVAMP tiled sequencing mode | `tool-specific algorithm provenance`; retain penalty/off-target/mismatch settings | Not a universal two-pool or one-repair rule for all tiling algorithms. Source: [varVAMP](https://www.nature.com/articles/s41467-025-60175-9) |
| `primalscheme3_lifecycle_commands` | `repair-mode`, `scheme-replace`, `interactions`, `visualise-primer-mismatches`, `panel-create` in addition to `scheme-create`; current documented default interaction threshold includes `-26.0` in relevant commands | PrimalScheme3 current CLI | `scheme maintenance/repair provenance` | CLI defaults are versioned tool semantics; no command outcome proves wet-lab rescue of dropout. Source: [PrimalScheme3](https://github.com/artic-network/primalscheme3) |
| `tiled_clickseq_adjacent_topology` | single template-specific primer per amplicon; patent examples describe `>300` tiled primers in one RT pool and claim amplicon lengths `100–10,000 nt` | Tiled ClickSeq patent family | `adjacent/unsupported single-primer tiling topology` | Patent claims/examples are not pair-based PCR defaults and require a different request/result schema. Sources: [WO2021257963A1](https://patents.google.com/patent/WO2021257963A1/en), [US12359266B2](https://patents.google.com/patent/US12359266B2/en) |
| `dimple_extreme_multiplex_preprint_2026` | preprint reports generation of `>10,000` primers; one demonstration used `204` primers for `2,302` KMT2A fusion subtypes in one tube | DIMPLE 2026 bioRxiv preprint / massively multiplex qPCR | `watchlist scalability evidence`; retain algorithm/preprint version and assay context | Not peer reviewed at the 2026-08-30 cut-off; values are not PCRStudio multiplex/tiling defaults or validated universal capacity. Source: [DIMPLE preprint](https://doi.org/10.64898/2026.04.17.719221) |

## Heavy-pass enrichment — global multiplex optimization

Tiled design is a special case of a broader set-level optimization problem. Current peer-reviewed tools now provide complementary formulations that PCRStudio should preserve as algorithm provenance rather than merge into one synthetic score. `ThermoPlex` (2025) screens target-specific multiplex candidates using target/non-target alignments and thermodynamic simulation of competing reactions, whereas `PRISM` (2026) formulates primer-set selection as constrained submodular maximization balancing genome coverage and primer-dimer `Badness`. These methods complement the existing SADDLE/Olivar/PrimalScheme3/varVAMP records and demonstrate that **candidate generation, set selection, interaction scoring and pool assignment are separable stages** ([ThermoPlex](https://academic.oup.com/biomethods/article/10/1/bpaf074/8283541), [PRISM](https://academic.oup.com/bioinformatics/article/42/7/btag478/8722296)).

`DIMPLE` (2026) is retained only as a preprint watchlist branch for extreme-scale multiplex qPCR. The preprint reports generation of `>10,000` primers and a demonstration using `204` primers to address `2,302` KMT2A fusion subtypes in one tube. Because this evidence was not peer reviewed at the cut-off, these figures are neither tiling defaults nor validation claims for PCRStudio ([DIMPLE preprint](https://doi.org/10.64898/2026.04.17.719221)).

For future global optimization, a tiled result should be able to retain `candidate_generator`, `set_optimizer`, objective vector, hard constraints, interaction metric/version, random seed where applicable, pool assignment and unresolved interactions. A tool that optimizes one objective must not be treated as having validated another objective such as empirical amplification balance or sequencing depth ([ARTIC network design guidance](https://artic.network/ncov-2019/ncov2019-bioinformatics-sop.html)).

## Numeric evidence register

The following records preserve scheme baselines, coordinate semantics and ARTIC protocol values separately. They are not a universal tiling recipe and do not turn nominal coverage into measured depth or variant recovery ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [ARTIC V4 optimisation study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891481/)).

| Parameter ID | Exact value or rule | Scope / condition | Operational role | Evidence boundary |
| --- | --- | --- | --- | --- |
| `tiling_profile_software_baseline` | Current profile baseline: product `300–500 bp`, primer Tm `59/61/64 °C`, pair ΔTm `2 °C`, primer length `20/24/30 nt`, GC `30–65%`, filters `gc_clamp=1`, `max_end_gc=3`, `max_poly_x=5`, and pool gate `2–6` with `2` as the omitted-field default. | Internal `tiled-scheme` search contract. | `software starting envelope`; preserve as implementation metadata. | No external source in this record establishes these exact values; they are implementation constants and must not be presented as vendor or literature recommendations. |
| `tiling_coordinate_contract` | PCRStudio emits `0-based, half-open` intervals and the current format identifier is `pcrstudio-tiling-v1`; each tile carries a reference-linked left/right primer interval ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)). | Machine-readable scheme interchange. | `hard serialization rule`; retain reference identity and coordinate system. | Coordinates without the matching reference sequence or scheme version are incomplete and must not be treated as reproducible. |
| `artic_amplicon_and_pool_example` | ARTIC V4: amplicon length not longer than approximately `400 bp`; `2` pools; individual oligos at `100 µM`, odd/even pooling, then `1:10` dilution to `10 µM` ([ARTIC V4 scheme release](https://community.artic.network/t/sars-cov-2-version-4-scheme-release/312/1), [ARTIC Ebola sequencing SOP](https://artic.network/viruses/ebov/ebov-seq-sop.html)). | Named ARTIC-style sequencing overlay; the SOP is an independent ARTIC example for stock preparation. | `scheme/preparation example`; preserve pool topology and dilution. | These values belong to named ARTIC workflows and cannot overwrite another organism, target length or library protocol. |
| `artic_v4_reaction_setup` | A published ARTIC V4 implementation uses `2` reactions per sample; each `12.5 µL` reaction contains `3 µL` water, `6.3 µL` Q5 Hot Start High-Fidelity `2X` Master Mix, `1.9 µL` primer pool and `1.3 µL` cDNA, with `0.015 µM` final concentration per primer ([ARTIC V4 optimisation study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891481/)). | Specific cDNA/Q5/ARTIC V4 implementation; the listed components sum to `12.5 µL`. | `vendor/protocol overlay`; retain reaction volume, components and final concentration. | This recipe cannot be applied to genomic DNA, another polymerase or a different pool architecture without validation. |
| `artic_v4_cycling` | The same implementation records `98 °C/30 s` initially, `25` cycles of `98 °C/30 s` plus `65 °C/5 min`, then `15` cycles of `62.5 °C/5 min` plus `98 °C/15 s`, a final `62.5 °C/5 min` and `4 °C` hold ([ARTIC V4 optimisation study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891481/)). | Named ARTIC V4 cDNA/Q5 workflow. | `protocol cycling record`; preserve stage order and all cycle counts. | These cycling values are not a general rule for tiled PCR or for every ARTIC revision. |
| `artic_primer_weight` | ARTIC scheme metadata permits a positive floating-point `primerWeight`; effective concentration is `primerWeight × typical PCR concentration`, so `1.0` means unweighted and `2.0` means two-fold enrichment relative to that typical concentration ([ARTIC primer-scheme specification v3](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [ARTIC V4.1 update](https://community.artic.network/t/sars-cov-2-v4-1-update-for-omicron-variant/342)). | Per-primer scheme balancing and weak-amplicon recovery. | `quantitative scheme metadata`; retain weight, formula, reason and validation result. | Weighting changes pool composition; it is not evidence that the weak amplicon will recover or that all other amplicons remain balanced. |
| `tiling_overlap_and_slide` | The current software refuses `overlap=0`; explicit `slide=0` means no recovery search, while omission uses the profile starting value ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)). | Internal geometry and recovery-search controls. | `explicit geometry policy`; store the chosen values with scheme coordinates. | No universal overlap length or sliding tolerance is supported; changing either changes the scheme identity. |
| `neb_q5_routine_branch` | `1X` master mix; `0.5 µM` each primer in a `25 µL` reaction; `25–35` cycles; annealing `50–72 °C`; extension `72 °C` for `20–30 s/kb`; Q5 does not incorporate dUTP ([NEB Q5 Hot Start High-Fidelity 2X Master Mix protocol](https://www.neb.com/en-us/protocols/protocol-for-q5-hot-start-high-fidelity-2x-master-mix-m0494)). | NEB routine single-pair Q5 Hot Start High-Fidelity 2X Master Mix branch. | `vendor chemistry overlay`; use NEB Tm calculation and record template type. | Not interchangeable with the ARTIC multiplex cDNA recipe; dUTP/uracil-containing inputs require a different enzyme choice. |
| `artic_ebola_rt_branch` | RT setup uses `1 µL` 50 µM random hexamers, `1 µL` 10 mM dNTP mix and `11 µL` RNA; then `42 °C/90 min` and `70 °C/10 min` with SuperScript IV ([ARTIC Ebola sequencing SOP](https://artic.network/viruses/ebov/ebov-seq-sop.html)). | RNA-to-cDNA ARTIC branch before tiled Q5 PCR. | `reverse-transcription metadata`; keep separate from amplicon PCR chemistry. | This is an Ebola SOP branch, not a universal RT recipe or a DNA-template rule. |
| `primalscheme_web_v3_3_0_inputs` | PrimalScheme `v3.3.0`; up to `10` FASTA files; maximum `10 MB` each; minimum `2` pools for overlapping schemes; unaligned input is aligned with MAFFT | Current PrimalScheme web application | `tool input/provenance contract`; record input files and alignment path | Web input limits and minimum pool UI are tool constraints, not universal multiplex-PCR rules. Source: [PrimalScheme web application](https://primalscheme.com/) |
| `primalscheme3_scheme_create_defaults` | amplicon target `400 bp`; allowed `100–2000 bp`; size window `±10%`; minimum overlap `10 bp`; pools default `2` (`≥1` CLI); dimer score `−26.0`; min base frequency `0.0`; mapping default `first` | primalscheme3 `3.3.0` `scheme-create` CLI | `tool-specific defaults`; preserve version and user overrides separately from PCRStudio profile | These values are algorithm defaults, not validated universal tiled-PCR optima. Source: [primalscheme3 3.3.0 on PyPI](https://pypi.org/project/primalscheme3/3.3.0/), [PrimalScheme3 GitHub](https://github.com/artic-network/primalscheme3) |
| `primalscheme3_boolean_branches` | circular default `off`; backtrack default `off`; high-GC default `off`; mispriming match database default `on` | primalscheme3 `3.3.0` search topology/options | `tool-specific categorical defaults`; export selected states with scheme provenance | Changing these options changes candidate generation/topology and therefore scheme identity. Source: [primalscheme3 3.3.0 on PyPI](https://pypi.org/project/primalscheme3/3.3.0/) |

The register keeps the current `300–500 bp` software envelope distinct from the ARTIC approximately `400 bp` example, and keeps the `2–6` pool software gate distinct from the named ARTIC `2`-pool protocol. These are different evidence layers, not values to average ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [ARTIC FAQ](https://community.artic.network/t/frequently-asked-questions-about-artic-protocol/34)).

## Source-to-parameter map

| Source | Parameters or claims supported |
| --- | --- |
| [ARTIC primer-scheme specification v3.0.0-alpha](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf) | `primer.bed`/`reference.fasta` coupling; zero-based half-open coordinates; name, pool, strand, 5′→3′ sequence, arbitrary attributes; `primerWeight`; format limits |
| [Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/) | primer interaction and coverage-bias risks |
| [Olivar, variant-aware tiling](https://pubmed.ncbi.nlm.nih.gov/39060254/) | primer-binding variants and redesign rationale |
| [ARTIC V4 scheme release](https://community.artic.network/t/sars-cov-2-version-4-scheme-release/312/1) | approximately `400 bp` maximum path length, `2` odd/even pools, `100 µM` individual stocks, variant-driven redesign and interaction testing |
| [ARTIC beginner's guide](https://community.artic.network/t/a-beginners-guide-to-artic/531) | pool separation, primer trimming, overlap interpretation and degraded-sample length choice |
| [ARTIC FAQ](https://community.artic.network/t/frequently-asked-questions-about-artic-protocol/34) | named ARTIC FAQ context only; it is not used as the sole authority for the corrected numeric register |
| [ARTIC V4 optimisation study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891481/) | named `12.5 µL` two-reaction protocol, `0.015 µM` primer concentration and the complete temperature/time/cycle record |
| [NEB Q5 Hot Start High-Fidelity 2X Master Mix protocol](https://www.neb.com/en-us/protocols/protocol-for-q5-hot-start-high-fidelity-2x-master-mix-m0494) | routine Q5 branch: `1X`, `0.5 µM` each primer, `25–35` cycles, `50–72 °C` annealing, `72 °C` extension, and dUTP incompatibility |
| [ARTIC Ebola sequencing SOP](https://artic.network/viruses/ebov/ebov-seq-sop.html) | SuperScript IV RT branch; `400 nt` overlapping-amplicon example; `100 µM` stock, `1:10` dilution to `10 µM`; Q5 and Nanopore library handoff |
| [PrimalScheme web application](https://primalscheme.com/) | current `v3.3.0` web input limits, alignment handling and two-pool requirement for overlapping schemes |
| [PrimalScheme3 GitHub](https://github.com/artic-network/primalscheme3) / [PyPI 3.3.0](https://pypi.org/project/primalscheme3/3.3.0/) | current scheme-create defaults/ranges for amplicon size, overlap, pool count, dimer threshold, base-frequency filter, mapping, circular/backtrack/high-GC/matchdb branches |

## Evidence

The cited specification and primary studies support ordered overlapping amplicons, pool metadata, reference-linked intervals and variant-aware coverage review, but they do not support one universal amplicon length, overlap, pool count or depth guarantee. These remain scheme and platform inputs ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)).

## Verification record

**Implementation:** validate ordered intervals, overlap/gap accounting, pool identity and primer interactions; emit reference-linked, zero-based half-open primer intervals with a PCRStudio format/version label; support PrimalScheme3 circular `scheme-create`, capture optional native visualisation artifacts, import observed amplicon-depth TSV as evidence, generate a non-causal dropout→repair handoff, and report old→new BED scheme diff plus a non-auto-publishing semantic-version recommendation, while retaining variant-binding warnings and the nominal-versus-measured claim boundary ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)).

**Test:** cover uncovered target ends, duplicate amplicon IDs, pool collisions, reverse-strand intervals, primer-binding variants and scheme-version changes ([Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)).

**Limitation:** this profile is `limited`; run-level depth, dropout, consensus accuracy and variant sensitivity require sequencing validation ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)).
