# Consensus Pair Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `consensus-pair` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

## Alignment and conservation methods

| Tool or method | Role in this engine | Interface vocabulary | Boundary |
| --- | --- | --- | --- |
| MAFFT | multiple-sequence alignment for a declared nucleotide family | `alignment_tool`, `alignment_version`, `alignment_strategy`, `alignment_parameters`, `gap_policy`, `direction_handling`, `alignment_records` | The current upstream release is `7.526`; the MAFFT project warns that versions `7.463–7.486` had a serious FFT-NS-i/`--auto` memory bug. Strategy and version therefore belong in provenance, and an MSA is not itself proof of homology or universal amplifiability ([MAFFT current software page](https://mafft.ddbj.nig.ac.jp/alignment/software/), [Katoh & Standley, 2013](https://academic.oup.com/mbe/article/30/4/772/1073398)). |
| MUSCLE5 | alternative MSA and alignment-uncertainty/ensemble path | `alignment_tool`, `alignment_version`, `alignment_strategy`, `alignment_parameters`, `alignment_ensemble`, `alignment_replicates`, `alignment_dispersion` | MUSCLE5 is a major rewrite of the 2004 MUSCLE algorithm; upstream releases list version `5.3` as current at review time, and the method can generate alternative alignment ensembles; downstream primer sites that change across plausible replicates should be reported as alignment-sensitive rather than treated as fixed biology ([MUSCLE5 paper](https://pubmed.ncbi.nlm.nih.gov/36379955/), [MUSCLE5 documentation](https://www.drive5.com/muscle5/manual/getting_started.html), [MUSCLE releases](https://github.com/rcedgar/muscle/releases)). |
| Clustal Omega | alternative profile/HMM-based alignment path when the selected workflow supports it | `alignment_tool`, `alignment_version`, `alignment_strategy`, `alignment_parameters`, `profile_mode`, `guide_tree_policy` | The original 2011 paper describes a protein-focused release; current `1.2.4` software supports DNA/RNA since version `1.1.0`. Use current software documentation for nucleotide behavior and retain the exact version; Clustal Omega is no longer under active algorithmic development ([Clustal Omega README](https://github.com/GSLBiotech/clustal-omega/blob/master/README), [Clustal Omega releases](https://github.com/GSLBiotech/clustal-omega/releases), [EMBL Clustal history](https://www.embl.org/news/embletc/issue-100/the-story-of-clustal-democratising-sequence-alignments/)). |
| SINA / SILVA alignment | reference-alignment branch for ribosomal RNA workflows | `alignment_tool`, `alignment_version`, `silva_release`, `reference_alignment`, `alignment_quality_fields` | SINA/SILVA is rRNA-specific and tied to a release-specific curated reference alignment; it must not be presented as a generic whole-genome aligner. Current SILVA release scope is asymmetric across SSU and LSU (`SSU 144`, `LSU 138.2` at review time), so the exact dataset/release must be recorded ([SILVA release 144](https://www.arb-silva.de/documentation/release-144), [SILVA release 138.2](https://www.arb-silva.de/documentation/release-1382/)). |
| multiple-sequence alignment | establishes the declared family coordinate system and conservation evidence | `alignment_records`, `alignment_accessions`, `alignment_version`, `conservation_policy`, `excluded_records`, `alignment_uncertainty` | Biological homology and alignment quality require curation; column identity alone cannot establish family membership, and unstable columns should not be used as if they were certain primer sites ([FAS-DPD](https://pmc.ncbi.nlm.nih.gov/articles/PMC3600133/), [MUSCLE5](https://pubmed.ncbi.nlm.nih.gov/36379955/)). |

## Degenerate-primer and consensus methods

| Tool or method | Role in this engine | Interface vocabulary | Boundary |
| --- | --- | --- | --- |
| HYDEN | maximum-coverage degenerate-primer search over a supplied sequence set | `primer_length`, `max_degeneracy`, `coverage_objective`, `mismatch_policy`, `search_window`, `optimization_policy` | HYDEN's published problem is coverage-oriented and heuristic; its output still requires thermodynamic, pair and specificity evaluation in the selected assay context ([Linhart & Shamir, 2007](https://pubmed.ncbi.nlm.nih.gov/17951798/)). |
| DegePrime | degenerate-primer design for broad-taxonomic-range microbial PCR | `alignment_records`, `window_policy`, `max_degeneracy`, `coverage_fraction`, `taxonomic_strata`, `primer_pair` | DegePrime optimizes maximum coverage at a declared degeneracy budget and reports taxonomic-group coverage; its historical benchmark values are algorithm/data-set observations, not universal primer rules ([DegePrime](https://pmc.ncbi.nlm.nih.gov/articles/PMC4135748/)). |
| DeGenPrime | thermodynamic/conservation-aware MSA degenerate-primer design precedent | `degeneracy_filter`, `deletion_filter`, `tm_range`, `gc_range`, `structure_limits`, `conserved_region_policy` | DeGenPrime 2024 contributes explicit tool-specific ambiguity/deletion filters and thermodynamic scoring. Those numeric filters must remain attributed to DeGenPrime rather than silently becoming this engine's biological defaults ([DeGenPrime](https://pmc.ncbi.nlm.nih.gov/articles/PMC11001487/)). |
| ConsensusPrime | alignment cleaning plus conserved-region/Primer3 pipeline precedent | `duplicate_policy`, `partial_sequence_policy`, `outlier_policy`, `consensus_region_policy`, `primer3_profile` | ConsensusPrime supports the need to remove or explicitly handle duplicate, partial and discordant records before primer design; its 2024 MRSA qPCR validation is one scoped experimental case, not a general performance guarantee ([ConsensusPrime pipeline](https://www.mdpi.com/2673-7426/2/4/41), [ConsensusPrime MRSA validation](https://www.mdpi.com/2673-7426/4/2/68)). |
| varVAMP | modern MSA-based degenerate-primer precedent for variable viral genomes | `consensus_threshold`, `max_ambiguous_positions`, `gap_masking`, `mismatch_position_penalty`, `blast_background` | varVAMP 2025 separates majority and degenerate consensus sequences, masks alignment gaps, penalizes permutation count and 3′ mismatches, and supports BLAST review. Its defaults and mode-specific thresholds remain tool-specific precedents, not universal rules for this engine ([varVAMP](https://pmc.ncbi.nlm.nih.gov/articles/PMC12126543/)). |
| PrimerProspector | de novo primer design and taxonomic-coverage analysis for barcoded/broad-range PCR | `target_region`, `primer_length`, `degeneracy`, `reference_taxonomy`, `coverage_by_taxon`, `amplicon_readout` | PrimerProspector makes taxonomic coverage and reference-set construction explicit and can evaluate existing or de novo primers; its coverage is conditional on the reference database and filtering policy ([PrimerProspector](https://pmc.ncbi.nlm.nih.gov/articles/PMC3072552/)). |
| DECIPHER `DesignPrimers` | target-group primer design in the presence of declared non-target groups | `target_group`, `nontarget_groups`, `alignment`, `extension_bias`, `specificity_objective` | DECIPHER is a useful precedent for designing against nearly identical non-target ensembles and for treating primer-extension bias as part of specificity; its group-specific objective is distinct from unconstrained family universality ([DECIPHER Design Primers](https://decipher.codes/DesignPrimers.html)). |
| ecoPrimers / ecoPCR | taxonomically constrained broad-range primer/marker search with explicit example and counterexample sets | `target_taxon`, `counterexample_taxon`, `reference_database`, `mismatch_policy`, `amplicon_range`, `taxonomic_resolution` | ecoPrimers demonstrates that broad coverage and taxonomic discrimination are joint database-dependent objectives; its historical database examples and mismatch settings are not current PCRStudio defaults ([ecoPrimers](https://academic.oup.com/nar/article/39/21/e145/1105558)). |
| PrimerDesign-M | MSA-informed primer design for genetically variable targets, single or walking/multi-fragment modes | `alignment`, `region_of_interest`, `gap_strip_policy`, `fragment_mode`, `primer_constraints`, `adaptor`, `barcode` | PrimerDesign-M is a relevant variable-genome precedent that jointly optimizes diversity-aware primer placement and experimental constraints; walking/multi-fragment modes belong conceptually to tiling rather than this single consensus-pair output ([PrimerDesign-M](https://pmc.ncbi.nlm.nih.gov/articles/PMC4410655/), [LANL PrimerDesign-M](https://www.hiv.lanl.gov/content/sequence/PRIMER_DESIGN/primer_design.html)). |
| CODEHOP | hybrid consensus-degenerate primer design from conserved protein motifs | `protein_alignment`, `consensus_clamp`, `degenerate_core`, `codon_policy`, `coverage_policy` | CODEHOP's 3′ degenerate core plus 5′ consensus clamp is a distinct protein/back-translation contract and must not be silently flattened into the current nucleotide-alignment consensus-pair workflow ([Rose et al., 2003](https://pubmed.ncbi.nlm.nih.gov/12824413/), [Rose et al., 1998](https://pubmed.ncbi.nlm.nih.gov/9512532/)). |
| consensus/degenerate-base resolver | converts accepted column variation into an IUPAC ambiguity representation | `consensus_policy`, `ambiguity_codes`, `degeneracy_count`, `ambiguity_order`, `represented_records` | Degeneracy represents a physical mixture of sequence species and can reduce effective member concentration and specificity; exact formulation and synthesis semantics must remain explicit ([IDT mixed bases](https://www.idtdna.com/pages/products/custom-dna-rna/mixed-bases), [QIAGEN degenerate-primer guidance](https://www.qiagen.com/us/knowledge-and-support/knowledge-hub/bench-guide/pcr/introduction/guidelines-for-degenerate-primer-design-and-use)). |

## Oligo and specificity validation methods

| Tool or method | Role in this engine | Interface vocabulary | Boundary |
| --- | --- | --- | --- |
| Primer3 / `primer3-py` | evaluates concrete oligo size, Tm, self-complementarity, pair compatibility and supplied product constraints after a consensus window/member set is defined | `primer3_profile`, `primer3_version`, `thermodynamic_parameter_set`, `dna_conc_assumption`, `salt_model`, `length_range`, `tm_range`, `gc_range`, `structure_limits`, `pair_constraints` | Stable upstream Primer3 release is `2.6.1`; the main branch contains an unreleased `2.7.0` development record with changes to Owczarzy salt correction and SantaLucia/Hicks thermodynamic parameters. Exact version/model settings therefore belong in provenance. Primer3 does not establish family coverage or validate an input alignment ([Primer3 releases](https://github.com/primer3-org/primer3/releases), [Primer3 development release notes](https://github.com/primer3-org/primer3/blob/main/src/release_notes.txt), [Primer3 manual](https://primer3.org/manual.html)). |
| concrete-member thermodynamic evaluator | evaluates each declared oligo member rather than one ambiguous-string surrogate | `member_sequences`, `member_count`, `member_concentration_policy`, `thermodynamic_member_ceiling`, `interaction_evaluation_ceiling` | Nearest-neighbour Tm depends on concrete sequence, salt and oligo concentration. Exhaustive self/cross interaction counts grow combinatorially with degeneracy; bounded evaluation must be disclosed rather than labelled exhaustive ([Primer3 manual](https://primer3.org/manual.html), [IDT mixed bases](https://www.idtdna.com/pages/products/custom-dna-rna/mixed-bases)). |
| NCBI Primer-BLAST | optional external specificity handoff against a selected database and organism/background | `background_database`, `organism_scope`, `specificity_search`, `off_target_policy`, `database_version` | Primer-BLAST is a database-dependent pair-aware specificity check, not a substitute for alignment curation or an experimental validation panel ([Primer-BLAST paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3412702/), [NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)). |
| AmpliconHunter v2 | large-scale in-silico PCR against genomic databases with degenerate-primer, mismatch, Tm and taxonomy-aware output | `background_database`, `database_version`, `degenerate_primers`, `mismatch_tolerance`, `taxonomic_profile`, `amplicon_length_distribution`, `amplicon_gc_distribution` | The current webserver advertises evaluation against databases containing up to `2.4 million` genomes. This is tool/webserver capability, not a guarantee of database completeness or wet-lab coverage ([AmpliconHunter v2](https://ah2.engr.uconn.edu/about)). |

| bounded specificity scanner | checks supplied background records and intended targets inside the application | `background_records`, `target_records`, `match_policy`, `off_target_policy`, `validation_panel` | An in-app scan is not a whole-database or gapped-alignment proof; its database, algorithm, member-expansion boundary and search parameters must be retained. Tool records define semantics and numeric defaults remain module-owned ([NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)). |

## Physical oligo formulation vocabulary

| Formulation | Interface vocabulary | Boundary |
| --- | --- | --- |
| IUPAC mixed-base synthesis | `oligo_formulation=mixed-base`, `vendor`, `mix_ratio_mode`, `purification`, `lot` | Standard mixed bases target equal dispensed ratios but coupling-rate differences can shift actual composition; custom unequal mixtures are separate order specifications ([IDT mixed bases](https://www.idtdna.com/pages/products/custom-dna-rna/mixed-bases)). |
| explicit member pool | `oligo_formulation=explicit-members`, `member_sequences`, `member_concentrations`, `pooling_method` | Exact sequence membership is known, but equal pooling must be specified rather than assumed. Total pool concentration and per-member concentration are different quantities. |
| grouped submixes | `oligo_formulation=submixes`, `submix_members`, `submix_concentrations` | Splitting sequence diversity into several less-degenerate oligos or submixes is a distinct physical strategy and must not be represented as one IUPAC string. |
| inosine-containing primer | `oligo_formulation=inosine`, `inosine_positions`, `vendor_chemistry` | Inosine is a non-IUPAC chemistry branch with distinct base-pairing and specificity behavior; it is not equivalent to `N` ([inosine study](https://pmc.ncbi.nlm.nih.gov/articles/PMC1636166/)). |

## Field families

```text
alignment_records       alignment_accessions     alignment_version
alignment_tool          alignment_strategy       alignment_parameters
gap_policy              direction_handling       conservation_policy
excluded_records        alignment_uncertainty    alignment_ensemble
alignment_replicates    alignment_dispersion     protein_alignment
consensus_policy        consensus_threshold      ambiguity_codes
ambiguity_order         represented_records      coverage_fraction
coverage_stratification conserved_window         primer_length
max_degeneracy          mismatch_policy          search_window
optimization_policy     primer_pair              primer3_profile
primer3_version         thermodynamic_parameter_set  dna_conc_assumption
salt_model              length_range             tm_range
gc_range                structure_limits         pair_constraints
member_sequences        member_count             member_concentration_policy
thermodynamic_member_ceiling interaction_evaluation_ceiling
oligo_formulation       mix_ratio_mode           member_concentrations
pooling_method          background_records       background_database
organism_scope          specificity_search       off_target_policy
database_version        validation_panel         coverage_objective
codon_policy            consensus_clamp          degenerate_core
target_group             nontarget_groups         reference_taxonomy
target_taxon             counterexample_taxon     taxonomic_resolution
amplicon_utility          readable_span             informative_resolution
region_of_interest       gap_strip_policy          fragment_mode
```

The names describe the engine interface; module records resolve values, evidence and applicability. A field name alone is not evidence that the corresponding calculation occurred, and a software version name alone does not establish that its documented behavior was used in a particular run ([Primer3 manual](https://primer3.org/manual.html)).

## Generation-1 production toolchain

This engine inherits the shared tool roles, adapter schema and regression policy from [`../../../TOOLCHAIN-POLICY.md`](../../../TOOLCHAIN-POLICY.md#generation-1-toolchain-maturity-contract).

| Tool | Role | Engine use | Required execution/provenance |
| --- | --- | --- | --- |
| MAFFT (shared pin) | `PRIMARY` | target-panel alignment before conservation/degeneracy analysis | local CLI; production minimum `>=7.487`; capture exact strategy/options, input order and aligned-output hash because conservation depends on alignment state ([MAFFT](https://mafft.cbrc.jp/alignment/software/)) |
| Primer3 (shared pin) | `PRIMARY` | concrete/core oligo candidate generation under resolved consensus windows | run only on a declared sequence representation; ambiguity strings are not allowed to acquire fictitious single-molecule Tm values ([Primer3 manual](https://primer3.org/manual.html)) |
| MFEprimer (shared pin) | `VALIDATOR` | local binding/product specificity against frozen background databases | capture index/database hash, k-mer setting and output schema ([MFEprimer updates](https://www.mfeprimer.com/updates/)) |
| BLAST+ (shared pin) | `VALIDATOR` | large/background searches and independent hit evidence | exact task/options and database build/checksum ([NCBI BLAST+](https://www.ncbi.nlm.nih.gov/books/NBK131777/)) |
| AmpliconHunter2 | `OPTIONAL` | very large genome/taxonomic scans for degenerate primers | retain tool/version/database and mismatch settings; current 2026 implementation is useful but newer than the core stack, so it cannot be the sole specificity authority ([AmpliconHunter2](https://ah2.engr.uconn.edu/about)) |
| DegePrime / DeGenPrime / DECIPHER / ecoPCR / PrimerProspector | `BENCHMARK` | compare degenerate-primer/conservation strategies | tool-specific thresholds and heuristics remain source-scoped; they do not become shared defaults |

### Alignment and database contract

The adapter must preserve sequence identifiers through alignment and produce a stable coordinate map back to every source sequence. Dataset release, taxonomy release, filtering/deduplication rules and content checksum are mandatory. SILVA SSU/LSU or other resources may release asynchronously; each resource is versioned independently rather than recorded as one generic “database version.”

### Degenerate-member execution contract

Any reported thermodynamic or interaction metric that depends on molecular sequence is evaluated on explicit concrete members or a declared bounded approximation. Candidate coverage, member concentration and computational expansion ceiling are separate fields. If expansion exceeds the configured ceiling, the worker returns a typed approximation/unresolved state; it does not silently treat an IUPAC string as one oligo.

## Production-grade adapter contract

This section is normative for the engine adapter. It complements the shared runtime schema rather than replacing it. A production run is valid only when the engine-specific operation, the exact tool artifact, resolved parameters, input/output schema versions, coordinate conversion and validation state are all recoverable from provenance.

### Shared executable pins used by this engine

When a row below is applicable, the engine inherits the exact artifact policy from [`../../contracts/toolchain-manifest.json`](../../contracts/toolchain-manifest.json). The release string is an identity constraint, **not** a substitute for the installed artifact SHA-256.

| Tool | Generation-1 pin / service state | Invocation boundary | Required provenance |
| --- | --- | --- | --- |
| Primer3 `primer3_core` | `2.6.1` | local subprocess using explicit Boulder-IO | binary/source artifact hash, full submitted tags, task, explanation/error fields, parser/schema version ([Primer3 manual](https://primer3.org/manual.html), [upstream repository](https://github.com/primer3-org/primer3)) |
| MFEprimer | `4.5.1` | local CLI; `mfeprimer`, `spec`, `dimer`, `hairpin` as applicable | executable hash, subcommand, index/database hash, index `k`, output schema/parser version; unknown layouts fail closed ([MFEprimer updates](https://www.mfeprimer.com/updates/), [CLI documentation](https://www.mfeprimer.com/mfeprimer-3.1/)) |
| NCBI BLAST+ | `2.17.0` | local CLI | executable hash, program/task, scoring/masking/search options, database release/build/hash, output format and parser version ([NCBI BLAST+ manual](https://www.ncbi.nlm.nih.gov/books/NBK279690/)) |
| PrimerPooler | `1.89` when used | local CLI | executable hash, score vs `--dg` mode, temperature/ions/dNTP, pool constraints, genome/amplicon options and randomization policy ([PrimerPooler](https://github.com/ssb22/PrimerPooler)) |
| MAFFT | `7.526` when used | local CLI | executable/package hash, strategy/options, threads, sequence order, input and aligned-output hashes; releases `7.463–7.486` are outside the supported production range ([MAFFT](https://mafft.cbrc.jp/alignment/software/)) |
| PrimalScheme3 | `3.3.0` when used | local CLI | package/artifact hash, command, config, MSA/BED hashes and all non-default options ([PrimalScheme3](https://github.com/artic-network/primalscheme3), [PyPI](https://pypi.org/project/primalscheme3/)) |
| pydna | `5.5.16` when used | local Python validation boundary | installed wheel/sdist hash, Python/environment lock, input construct hashes and serialized validation result ([PyPI](https://pypi.org/project/pydna/5.5.16/)) |
| ViennaRNA | `2.7.2` when used | local comparative structure worker | package hash, DNA parameter-set identity, temperature/ionic inputs, command/API path and output model identity ([ViennaRNA releases](https://github.com/ViennaRNA/ViennaRNA/releases)) |

Remote/browser/vendor tools remain `REFERENCE` unless an explicit supported API and deployment contract is later approved. They must never be scraped or called silently as a production dependency.

### Shared coordinate, sequence and chemistry semantics

- Internal coordinates are **0-based, half-open** `[start0,end0)`; strand is explicit and intervals always increase on the reference.
- Oligos are stored **5′→3′ in synthesized/read orientation**. Reverse-strand binding coordinates are not represented by reversed interval endpoints.
- Circular origin-spanning targets use ordered segment arrays; `end0 < start0` is forbidden internally.
- Raw source-tool coordinates are retained beside normalized coordinates so an adapter conversion can be round-tripped and regression-tested.
- Annealing/binding sequence, non-annealing 5′ tail/overlap, dye/quencher/modification and composite oligo sequence are separate fields. Thermodynamics must state which sequence material was evaluated.
- Na⁺/K⁺/NH₄⁺/Mg²⁺/dNTP/DMSO/formamide and oligo concentration are stored as separate raw quantities with units. Any derived equivalent-salt value records its named model and must not overwrite the raw chemistry.
- A tool-native default is never silently promoted to a PCRStudio assay default. Every resolved value follows the shared precedence/`override_policy` contract.

### Primer3 adapter field families

Any Primer3 call from this engine uses only tags supported by the pinned release and records the complete submitted Boulder-IO record. The relevant ordinary field families are:

```text
SEQUENCE_ID  SEQUENCE_TEMPLATE  SEQUENCE_INCLUDED_REGION
SEQUENCE_TARGET  SEQUENCE_EXCLUDED_REGION
SEQUENCE_PRIMER  SEQUENCE_PRIMER_REVCOMP
PRIMER_TASK
PRIMER_PICK_LEFT_PRIMER  PRIMER_PICK_RIGHT_PRIMER  PRIMER_PICK_INTERNAL_OLIGO
PRIMER_MIN_SIZE  PRIMER_OPT_SIZE  PRIMER_MAX_SIZE
PRIMER_MIN_TM  PRIMER_OPT_TM  PRIMER_MAX_TM
PRIMER_MIN_GC  PRIMER_OPT_GC_PERCENT  PRIMER_MAX_GC
PRIMER_PRODUCT_SIZE_RANGE  PRIMER_PRODUCT_OPT_SIZE
PRIMER_PAIR_MAX_DIFF_TM  PRIMER_NUM_RETURN
PRIMER_SALT_MONOVALENT  PRIMER_SALT_DIVALENT  PRIMER_DNTP_CONC  PRIMER_DNA_CONC
PRIMER_DMSO_CONC  PRIMER_DMSO_FACTOR  PRIMER_FORMAMIDE_CONC
PRIMER_MAX_SELF_ANY_TH  PRIMER_MAX_SELF_END_TH  PRIMER_MAX_HAIRPIN_TH
PRIMER_PAIR_MAX_COMPL_ANY_TH  PRIMER_PAIR_MAX_COMPL_END_TH
PRIMER_EXPLAIN_FLAG
```

An engine may use only a subset, but omission from the adapter map is explicit. Upstream development-only tags must not be sent to stable `2.6.1`.

### Specificity adapter semantics

`MFEprimer` and `BLAST+` answer related but non-identical questions. PCRStudio therefore normalizes raw binding-hit evidence separately from reconstructed amplifiable-product evidence. The database manifest is mandatory and includes release/build, sequence/taxonomy identity where applicable, filtering/deduplication and SHA-256. A validator timeout, parser mismatch, missing database or incomplete scan is `unchecked/error`, never `pass`.

For MFEprimer `4.5.1`, omission of query `-k` may use the value stored in the index header; if `-k` is supplied it must match the index. The adapter records the effective value and fails closed on mismatch or an unrecognized output schema ([MFEprimer updates](https://www.mfeprimer.com/updates/)).

For BLAST+, at minimum the exact program/task, database, word-size/scoring/masking policy, target cap, threads and `outfmt` are retained. A truncated result set caused by a target cap cannot be reported as exhaustive specificity evidence.

### Error, fallback and refusal semantics

Every engine distinguishes these states:

| State | Meaning | Required behavior |
| --- | --- | --- |
| `NO_CANDIDATE_UNDER_CONTRACT` | the primary generator returned no candidate under resolved constraints | report the failed constraints/explain fields; relax only through the owning module's named relaxation step |
| `TOOL_EXECUTION_FAILED` | non-zero exit, crash, missing artifact or invalid environment | do not score absent results; use a declared fallback only if the fallback answers the same question |
| `PARSER_SCHEMA_MISMATCH` | output does not match the pinned parser/schema contract | fail closed; preserve raw stdout/stderr digests |
| `DATABASE_PROVENANCE_MISSING` | specificity/background database cannot be identified and hashed | specificity validation is `unchecked`; production acceptance requiring it is blocked |
| `COORDINATE_ROUNDTRIP_FAILED` | normalized coordinates cannot reconstruct the source-tool location | reject the affected result; never repair silently |
| `UNRESOLVED_HARD_ASSUMPTION` | topology/chemistry/assay identity required for a hard rule is unknown | return a refusal or request-level error rather than inventing a value |
| `OPTIONAL_VALIDATOR_UNAVAILABLE` | an optional independent check could not run | retain a warning and `unchecked` evidence; do not convert it to a favourable feature |

### Determinism, caching and concurrency

- Cache keys include engine/module profile version, normalized input hash, exact tool artifact identity, complete resolved parameter map, database/index hashes and adapter/parser schema versions.
- Input order is canonicalized only when order has no scientific meaning; otherwise the original order is part of the cache key and provenance.
- Thread count is recorded for tools whose output or ordering can depend on concurrency. Stable result ordering is normalized with deterministic tie-breaking after preserving raw order.
- Randomized tools must receive an explicit seed when reproducibility is supported. If no seedable deterministic mode exists, the run is labelled non-deterministic and cannot silently replace a deterministic production result.
- Cache reuse is prohibited across a changed database, tool artifact, parser schema, coordinate contract or chemistry/profile version even when user-visible inputs are unchanged.

### License, privacy and deployment gate

Production execution is local-first. Primer3 is GPL-2.0-or-later upstream; PCRStudio's subprocess boundary is intentionally recorded rather than implying source/library incorporation. PrimerPooler is Apache-2.0 in current upstream releases. Other executables/packages retain their upstream license metadata in the build manifest. Legal/deployment review is a release gate, not a biological claim ([Primer3 repository](https://github.com/primer3-org/primer3), [PrimerPooler repository](https://github.com/ssb22/PrimerPooler)).

A remote validator is opt-in and records that sequence data leaves the local environment, destination/service identity, date and submitted scope. Private or proprietary sequences must not be transmitted by an implicit fallback.

### Engine execution graph

```text
sequence-panel intake + record filtering
        -> MAFFT alignment
        -> alignment QC / conservation / ambiguity resolver
        -> concrete or degenerate candidate-window enumeration
        -> Primer3 evaluation of concrete annealing members/cores
        -> MFEprimer specificity
        -> BLAST+ expansion when required
        -> member-wise/set-wise coverage + interaction aggregation
        -> deterministic filtering/ranking
```

The MSA is a versioned intermediate artifact. Candidate coordinates are stored both in alignment-column space and mapped source-record/reference space; neither coordinate system may be inferred from the other after gap stripping without an explicit mapping table.

### Engine-owned canonical inputs

```text
panel_id  sequence_records[]  reference_record_id  molecule_type
alignment_strategy  alignment_options  direction_policy
gap_policy  duplicate_policy  partial_record_policy  outlier_policy
conservation_policy  min_base_frequency  ambiguity_policy
max_degeneracy  expansion_cap  member_concentration_semantics
target_taxa/groups  nontarget_taxa/groups  background_database
candidate_windows  assay_profile_id  chemistry_profile_id
```

`max_degeneracy`, conservation thresholds and taxonomic objectives are module/profile choices. Values from DegePrime, DeGenPrime, varVAMP, DECIPHER, ecoPrimers or other literature tools remain source-scoped evidence unless explicitly adopted by the module.

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Parameters or fields that must be captured | Normalized result |
| --- | --- | --- | --- |
| `align_panel` | MAFFT | exact strategy (`--auto` or explicit algorithm flags), `--thread`, orientation handling if used, sequence order, any add/keep-length mode | aligned FASTA hash, record map, column count, gap/ambiguity summaries, tool run |
| `resolve_conservation` | PCRStudio | per-column base counts/frequencies, gap fraction, accepted ambiguity, represented/excluded records, degeneracy product | conserved windows with coverage vectors and rejection reasons |
| `evaluate_oligo_members` | Primer3/thermo | concrete member sequence, full chemistry/model profile, size/Tm/GC/structure fields | per-member thermo features; **never** a fictitious single Tm for an unresolved ambiguity string |
| `validate_background` | MFEprimer/BLAST+ | expanded member policy, mismatch/product search settings, database manifest | member-level hits/products plus aggregate target/non-target coverage |
| `compare_benchmark` | DegePrime/DeGenPrime/DECIPHER/etc. | tool/version/input dataset and native thresholds | benchmark-only candidate/coverage record, excluded from production ranking unless explicitly imported |

### Degenerate oligo physical-mixture contract

A degenerate IUPAC sequence is an encoding of a set/mixture. The normalized record therefore retains `iupac_sequence`, `degeneracy_count`, deterministic expanded members or an expansion digest when capped, synthesis formulation if known, effective/member concentration interpretation and per-member validation status. Any approximation caused by an expansion cap is surfaced as a warning and cannot be represented as exhaustive coverage.

### Normalized output

```text
ConsensusPairResult {
  pair_id
  left_oligo { iupac_sequence, members_or_digest, degeneracy_count, binding_columns, source_intervals[] }
  right_oligo { iupac_sequence, members_or_digest, degeneracy_count, binding_columns, source_intervals[] }
  represented_records[]
  excluded_records[]
  target_coverage_by_record
  target_coverage_by_taxon_or_group
  nontarget_evidence
  alignment_sensitivity
  thermodynamic_member_summary
  specificity_member_summary
  product_geometry_summary
  score_components
  warnings[]
  tool_runs[]
}
```

Coverage is reported against the exact panel/database snapshot; it is not described as universal coverage of a taxon or gene family.

### Engine-specific failures and controlled recovery

- `ALIGNMENT_UNSTABLE_AT_BINDING_SITE`: candidate columns change materially under the declared alignment-QC/alternate-alignment check; reject or mark alignment-sensitive according to module policy.
- `NO_CONSERVED_WINDOW`: no window satisfies the declared conservation/gap/degeneracy constraints; relaxation changes one named constraint at a time.
- `DEGENERACY_EXPANSION_LIMIT`: exhaustive physical-member evaluation would exceed the cap; return bounded/approximate evidence, never pretend the unexpanded members were checked.
- `TARGET_NONTARGET_CONFLICT`: the same candidate needed for target coverage also supports a forbidden non-target product; no ranking weight may override a hard specificity rule.
- `PANEL_PROVENANCE_INCOMPLETE`: accession/version or inclusion/exclusion provenance is missing; broad-range coverage claims are blocked.

### Regression fixture matrix

At minimum maintain fixtures for: identical sequences; one SNP near a 3′ end; dispersed low-frequency variants; an internal alignment gap; reverse-orientation input; duplicate/partial records; high degeneracy; a target/non-target near-neighbour; a database update changing taxonomic coverage; MAFFT update with unchanged biological input; and an expansion-cap boundary. Assertions cover alignment hash/column map, degeneracy, candidate count/order, member expansion, coverage vector, specificity status and deterministic tie-break.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
