# Loop Set Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `loop-set` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-09-03 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| role-aware sequence search | enumerates candidates for each primer role | does not establish complete isothermal kinetics ([Notomi et al.](https://doi.org/10.1093/nar/28.12.e63)) |
| thermodynamic structure evaluator | reports hairpin and interaction proxies | does not prove productive LAMP amplification ([Primer3 manual](https://primer3.org/manual.html)) |
| set geometry validator | checks ordered regions and role relationships | geometry is necessary but not sufficient for assay performance ([Nagamine et al.](https://doi.org/10.1006/meth.2002.1264)) |
| readout/validation handoff | records turbidity, fluorescence, colour or lateral-flow context | readout performance is external evidence ([Soroka et al.](https://doi.org/10.3390/cells10081931)) |
| NEB LAMP Primer Design Tool / current technical-note registry | supplies role-aware LAMP geometry, source-scoped length/distance/Tm/end-stability rules, primer-mix/purification guidance and a versioned handoff to Bst-XT workflows | all values remain NEB-tool/technical-note scoped and still require target-specific specificity plus wet-lab validation ([NEB LAMP Primer Design Technical Note](https://media.neb.com/m/cc0bbc21ec612a7/original/LAMP_TechNote_0425.pdf), [NEB application-note index](https://www.neb.com/en-gb/application-notes)) |
| NEB Bst-XT WarmStart M9204 protocol registry | supplies a current standalone Bst-XT reaction identity and optimization branch | M9204 values remain module-scoped and are not interchangeable with kit/master-mix records ([NEB M9204 protocol](https://www.neb.com/en/protocols/loop-mediated-isothermal-amplification-lamp-protocol-using-bst-xt-warmstart-neb-m9204)) |
| NEB Bst-XT WarmStart glycerol-free M9205 protocol registry | supplies the current lyo-compatible standalone Bst-XT/RTx-glycerol-free reaction identity and optimization branch | M9205 is a distinct formulation/protocol identity; its lyo-compatible buffer does not imply that any arbitrary assembled assay is validated as lyophilized ([NEB M9205 protocol](https://www.neb.com/en/protocols/2025/03/18/loop-mediated-isothermal-amplification-lamp-protocol-using-bst-xt-warmstart-dna-polymerase-glycerol-free)) |
| NEB Bst-XT WarmStart Multi-Purpose LAMP/RT-LAMP 2X Master Mix with UDG, M1712 ([product](https://www.neb.com/en/products/m1712-bst-xt-warmstart-multi-purpose-lamp-rt-lamp-2x-master-mix-with-udg), [protocol](https://www.neb.com/en/protocols/bst-xt-warmstart-multi-purpose-lamp-rt-lamp-2x-master-mix-with-udg-protocol-neb-m1712)) | current Bst-XT + WarmStart RTx + dUTP/UDG LAMP/RT-LAMP chemistry branch | M1712 formulation and detection/carryover values are product-specific and do not replace M9204 or E1700 records |
| patent/adjacent-chemistry registry ([RNase-H2-cleavable LAMP primers](https://patents.google.com/patent/WO2017136387A1/en), [LAMP cycling-probe detection](https://patents.google.com/patent/WO2021091487A1/en)) | tracks blocked/cleavable primer and probe architectures that can change LAMP signal/specificity topology | patent disclosure is prior-art/architecture evidence only; no patent claim is promoted to a validated PCRStudio default without independent implementation and validation |

```text
role_id  role_orientation  binding_region  set_order  loop_relation
set_size  target_window  reaction_identity  readout_format  validation_status
```

## Field families and result provenance

The set record must preserve role identity and order before any thermodynamic score is interpreted: inner, outer and loop primers participate in a defined LAMP geometry, so an ordinary pair score cannot stand in for set validity ([Notomi et al.](https://doi.org/10.1093/nar/28.12.e63), [Nagamine et al.](https://doi.org/10.1006/meth.2002.1264)).

Reaction identity, readout format and validation status are separate fields. The presence of a plausible primer set does not establish isothermal detection performance or a positive call rule ([Soroka, Wasowicz and Rymaszewska](https://doi.org/10.3390/cells10081931)).

## Generation-1 production toolchain

No mature local open tool currently covers every LAMP role, loop-primer option, specificity check and current chemistry branch well enough to be the sole generation-1 authority. PCRStudio therefore uses transparent role-aware enumeration/geometry plus established thermodynamic/specificity tools, while browser/legacy LAMP designers remain references/benchmarks.

| Tool/method | Role | Engine use | Production decision |
| --- | --- | --- | --- |
| PCRStudio role-aware enumerator | `PRIMARY` | enumerate F3/B3, F2/B2, F1c/B1c and optional loop-role candidates under module geometry | deterministic windows/ordering; no hidden kinetic model |
| Primer3 (shared pin) thermodynamic routines / local oligo evaluator | `PRIMARY` | length/Tm/GC and supported structure features for concrete oligos | exact parameter/salt/concentration profile captured; role geometry remains owned by `02-lamp.md` |
| MFEprimer (shared pin) | `VALIDATOR` | independent ordered-oligo QC plus specificity evidence | validation evidence; absence of a hit is not promoted to a wet-lab specificity guarantee |
| BLAST+ (shared pin) | `VALIDATOR` | genome-scale short-region search; FIP/BIP are split into F1c/F2 and B1c/B2, synthetic linker excluded, then full-length region hits are reassembled into six-region LAMP-compatible loci on both whole-locus orientations | indexed search is practical but not claimed mismatch-complete; compatible loci are evidence until intended-target/background identity is resolved |
| MAFFT (shared pin) | `CONDITIONAL_PRIMARY` | when an inclusivity panel is supplied, align that homologous target panel and map primer-region variation back to reference coordinates | required for panel-inclusivity claims; absent when no panel is supplied, in which case PCRStudio makes no population/strain-coverage claim |
| NEB LAMP Primer Design Tool / PrimerExplorer V5 | `REFERENCE` | compare role geometry and vendor/reference candidate sets | web-only/manual workflows are not required backend dependencies |
| LAMPrimers iQ 2024 | `BENCHMARK` | local algorithm precedent for scanning/filtering and LAMP-set QC | upstream is MIT-licensed but currently Windows-only and loads a bundled `LAMP.dll` from a Python 3.10/Qt application; useful as a Windows-side benchmark, not a transparent production backend. The publication reports long-sequence support and homo/heterodimer rejection, but it does not cover every loop/specificity capability needed by PCRStudio; OCR-suspect equations are never imported without source verification ([LAMPrimers iQ paper](https://pubmed.ncbi.nlm.nih.gov/37924966/), [upstream repository](https://github.com/Restily/LAMPrimers-iQ)) |
| GLAPD | `BENCHMARK` | whole-genome target-commonality/background-specificity precedent and legacy set-generation comparison | GPL-2.0 upstream targets Linux and requires Perl/GCC plus Bowtie for common/specific modes. Its target/background logic is scientifically useful evidence, but adopting it as a mandatory backend would add Linux-centric deployment/licensing/dependency constraints to the Linux-first GEN1 toolchain ([GLAPD repository](https://github.com/jiqingxiaoxi/GLAPD), [GLAPD paper](https://doi.org/10.3389/fmicb.2019.02860)) |
| LAVA and similar historical tools | `BENCHMARK` | compare legacy set-generation heuristics | legacy dependencies/defaults are not production requirements |

### LAMP protocol-overlay adapter boundary

The R15 runtime protocol catalogue contains **72 distinct source-backed product/protocol identities** (excluding `not-selected`), partitioned as **35 DNA-only / 4 RNA-only / 33 DNA+RNA**. The exact ID set is canonical in `contracts/chemistry/lamp-protocols.json` and generated into Python, Rust and Web projections; the runtime registry is no longer an independently maintained truth. It covers complete master mixes/kits, assembled-enzyme authorities, liquid/dried/lyophilized/air-dryable formulations, direct-matrix branches and DNA/RT-LAMP substrate authorities from NEB, Thermo Fisher/Invitrogen, OptiGene, Meridian Bioscience, Eiken, Nippon Gene, Takara, Jena Bioscience, NZYtech, Yeasen, Vazyme and Agdia. R9 also resolves source-backed numeric overlays conditioned by readout chemistry, substrate, carry-over, formulation/reconstitution, sample context, additives, primer kinetics and instrument profile. These identities are **diagnostic/bench-context adapters only**: changing `lamp_protocol`, specimen, formulation, readout, confirmation or source-bounded bench settings must not silently alter target-derived sequence ranking. Native runtime execution remains a Linux-host qualification responsibility.

| Evidence branch | Adapter disposition | Reason |
| --- | --- | --- |
| current named NEB/Eiken/Thermo/Nippon/Takara identities | `RUNTIME OVERLAY` | source-bounded reaction/substrate/readout authority; this includes `neb-l4401`, `eiken-lmp247`, `thermo-a5180x`, `nippon-ne6041` and Takara `takara-rr385`. Pyrophosphatase/turbidity and M1712/HNB incompatibilities are fail-closed |
| Thermo Fisher SuperScript IV RT-LAMP Master Mix A51801/A51802/A51803 | `RUNTIME OVERLAY` | official Quick Reference fixes a `25 µL` six-primer recipe at `1.6/0.2/0.4 µM`, `65 °C`, and a `15–30 min` endpoint window; an official application note confirms the same mix for genomic DNA, while current product performance claims are kept as time-to-signal context rather than silently replacing the procedural run window |
| Nippon Gene 2x LAMP Master Mix NE6041/NE6043 | `RUNTIME OVERLAY` | current product/manual provide a coherent DNA-LAMP identity: `25 µL`, `1.6/0.2/0.8 µM`, `60–68 °C / 30 min`, built-in dsDNA fluorescent dye and thermostable pyrophosphatase; turbidity is explicitly outside the reviewed readout branch |
| OptiGene ISO-004/ISO-001 families, RT, Lyse & LAMP, dried and lyophilized branches | `RUNTIME SCENARIO OVERLAY` | distinct product/formulation/substrate identities are selectable and fail closed on substrate/formulation/direct-KOH contradictions. Public optimization ranges remain evidence unless an exact reviewed override envelope is represented ([OptiGene reaction guide](https://www.optigene.co.uk/isothermal-reaction-guide/)) |
| OptiGene ISO-001Tin / HD-LAMP | `SEPARATE TOPOLOGY WATCHLIST` | optional `95 °C / 5 min` preheat creates a preheat→isothermal topology that must not be represented as a normal single LAMP hold ([OptiGene ISO-001TIN](https://www.optigene.co.uk/iso-001tin/)) |
| Thermo A56656 Lyo-ready Bst + separate Dry-Ready evidence | `RUNTIME ASSEMBLED-ENZYME / EVIDENCE BOUNDARY` | `thermo-a56656` is executable as a DNA-only assembled-enzyme authority; product-specific Dry-Ready RT-LAMP formulation/thermal records remain separate evidence and are not collapsed into A56656 or A5180x ([Thermo Lyo-ready Bst guide](https://documents.thermofisher.com/TFS-Assets/LSG/manuals/MAN0029128-lyo-ready-Bst-DNA-polymerase_UG.pdf), [Dry-Ready RT-LAMP kit](https://www.thermofisher.com/order/catalog/product/A40006907)) |
| Meridian general/direct-matrix/liquid/lyophilized/air-dryable identities | `RUNTIME SCENARIO OVERLAY` | exact reviewed product identities are represented separately; direct specimen authority is matrix-specific. `meridian-mdx126` uniquely carries reviewed blood/plasma/serum + liquid/air-dryable authority and does not generalize inhibitor tolerance to other mixes |
| DARQ/QUASR/lateral-flow/multiplex LAMP | `FUTURE MODIFIED-OLIGO LAYER` | sequence-specific multiplex readouts require modified primers/probes and their own orderability/validation semantics ([multiplex LAMP review](https://pubmed.ncbi.nlm.nih.gov/38928080/)) |
| DPO outer primers (`F3/B3`) | `EXPERIMENTAL MODIFIED-PRIMER WATCHLIST` | one 2023 LAMP study found DPO replacement of ordinary outer primers preserved overall performance and improved temperature robustness in the tested assay, but DPO has a segmented/poly-dI molecular architecture. It therefore needs a future typed modified-primer/manufacturing/thermodynamic contract rather than being emitted as an ordinary F3/B3 sequence ([Talanta 2023](https://pubmed.ncbi.nlm.nih.gov/37167680/)) |
| NEB assembled-enzyme Bst authorities (`M0275`, `M0537`, `M0538`, `M0374`, Bst-family + RTx) | `RUNTIME ASSEMBLED-ENZYME` | represented as assembled-enzyme identities rather than pretending they are complete master mixes. Their protocol-specific optimization evidence is preserved without making enzyme families interchangeable ([M0538](https://www.neb.com/en/protocols/typical-lamp-protocol-m0538), [M0374](https://www.neb.com/en-us/protocols/typical-lamp-protocol-m0374), [M0275](https://www.neb.com/en-us/protocols/typical-lamp-protocol-m0275)) |
| Tte UvrD Helicase (`M1202`) | `EXPERIMENTAL CHEMISTRY ADJUNCT` | NEB documents UvrD as an assay-dependent method for suppressing non-template amplification, including `10 ng/25 µL` with E1700 and enzyme-specific titration ranges. It changes reaction chemistry rather than genomic primer geometry, so Gen-1 does not convert it into a primer-ranking bonus or automatic specificity rescue ([NEB UvrD FAQ](https://www.neb.com/faqs/how-do-i-use-tte-uvrd-helicase-for-reducing-non-template-amplification-in-lamp-reactions), [M1202 protocol](https://www.neb.com/en-us/protocols/protocol-for-lamp-reactions-with-tte-uvrd-helicase-m1202)) |
| Inner-primer Blockers / IIP-SCAN | `EXPERIMENTAL MODIFIED-OLIGO WATCHLIST` | a 2026 study identified initiator inner primers in non-template amplification and reported F1c/B1c-targeted blocker oligos that extended the NSA-free window. These are extra, empirically selected oligos with their own length/topology and validation requirements, so they belong to a future modified-oligo layer rather than an automatic ordinary-primer feature ([Mo et al. 2026](https://pubmed.ncbi.nlm.nih.gov/41526128/)) |
| high-temperature ssBP-LAMP | `EXPERIMENTAL CHEMISTRY / FORMULATION WATCHLIST` | a 2026 peer-reviewed study found that `69 °C` alone still produced NSA in `11/21` tested primer sets, whereas a thermolabile T7 ssDNA-binding protein combined with a thermostable high-temperature Bst formulation suppressed NSA across the evaluated panel. This is a reaction-formulation strategy (polymerase + temperature + ssBP + validation), not a genomic primer-ranking rule and not an automatic rescue for a weak set ([Simões et al. 2026](https://link.springer.com/article/10.1186/s11658-026-00926-8)) |

Readout compatibility attached to a named overlay is advisory (`reviewed-compatible`, `review-required`, or `not-assessed`), never a sequence-selection gate. Likewise, named kit concentrations are used for ordered-oligo **diagnostic context** only; PrimerExplorer geometry/Tm eligibility remains owned by the versioned LAMP design model.

### Set generation and ranking boundary

The candidate unit is a **role-labelled set**, not a bag of individually high-scoring primers. Hard ordering/spacing constraints are applied before set scoring. Pairwise hairpin/self-dimer/cross-dimer and directed 3′-extendability features are retained as continuous set-level risk evidence and ranking terms; the current generation does **not** use an invented universal dimer/interaction cutoff as a wet-lab rejection oracle. If no complete set exists, the engine returns an explainable refusal rather than silently widening the selected geometry profile. Computational shortlist/cap state is preserved in search provenance.

### LAMP-specific query semantics

For genomic validation, the ordered FIP/BIP molecules are **not** queried as if their full sequence were contiguous in the template. PCRStudio emits six target-derived region queries (`F3`, `F2`, `F1c`, `B1c`, `B2`, `B3`). `FIP => F1c + [optional synthetic linker] + F2` and `BIP => B1c + [optional synthetic linker] + B2`; the linker participates in oligo-structure calculations and order sheets but is excluded from genomic alignment. BLAST hit coordinates and strands are interpreted at the locus level, including reverse-complement whole-locus orientation, before six-region compatibility is reported. This follows the set-level specificity principle used by GLAPD rather than treating independent primer hit counts as a LAMP verdict ([GLAPD](https://doi.org/10.3389/fmicb.2019.02860)).

Target inclusivity is a separate question from background specificity. When a homologous target FASTA panel is supplied, MAFFT is the **conditional primary** alignment authority and reports role- and position-aware conservation; no panel means no population-coverage claim and no MAFFT requirement.

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
| ViennaRNA | `2.7.2` when used | optional post-selection RT-LAMP RNA accessibility worker | package hash, Turner-2004 RNA parameter identity, selected hold/diagnostic temperature, requested role windows and checked/unchecked result; `decision_impact=none` ([ViennaRNA releases](https://github.com/ViennaRNA/ViennaRNA/releases)) |

Remote/browser/vendor tools remain `REFERENCE` unless an explicit supported API and deployment contract is later approved. They must never be scraped or called silently as a production dependency.

### Shared coordinate, sequence and chemistry semantics

- Internal coordinates are **0-based, half-open** `[start0,end0)`; strand is explicit and intervals always increase on the reference.
- Oligos are stored **5′→3′ in synthesized/read orientation**. Reverse-strand binding coordinates are not represented by reversed interval endpoints.
- Coordinate semantics can represent segmented/circular records elsewhere in PCRStudio, but classic Gen-1 Loop Set is explicitly **linear-target only**; circular origin-spanning LAMP fails closed until its six-region geometry is independently implemented and qualified.
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
target/template intake
        -> LAMP role-window construction
        -> F3/B3/F2/B2/F1c/B1c candidate enumeration
        -> composite FIP/BIP construction
        -> optional LF/LB design after core-set selection
        -> role/order/spacing hard validation
        -> oligo thermodynamics + pairwise interaction graph
        -> MFEprimer/BLAST+ binding/background evidence
        -> complete-set filtering/ranking
        -> vendor/reference comparison when requested
```

### Engine-owned canonical inputs

```text
template_id  target_window  topology
role_windows { F3, F2, F1c, B1c, B2, B3, LF, LB }
role_order_policy  spacing_policy  loop_primer_policy
composite_primer_policy  target_strand_mapping
oligo_size_tm_gc_profile  structure_profile
set_interaction_profile  assay_chemistry_profile
background_database  readout_format
```

FIP and BIP are composite oligos whose segment identities and orientations are preserved explicitly; an inner primer must not be treated as a single contiguous binding interval. The candidate unit is the complete role-labelled set.

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Required captured semantics | Normalized result |
| --- | --- | --- | --- |
| `enumerate_role_sites` | PCRStudio | role-specific windows, strand/orientation, spacing/order and exclusion regions | role-labelled annealing segments with source coordinates |
| `evaluate_segments` | Primer3 thermo/local evaluator | concrete segment/full-oligo sequence plus explicit chemistry/model | segment and full-composite thermodynamic features kept distinct |
| `compose_inner_primers` | PCRStudio | F1c+F2 and B1c+B2 segment order, optional linker if ever supported | composite FIP/BIP with segment map and multiple binding intervals |
| `design_loop_primers` | PCRStudio | selected core set, loop regions and role geometry | optional LF/LB linked to a specific core-set id |
| `validate_background` | MFEprimer/BLAST+ | every binding segment/oligo role, declared background DB | role-level hit evidence; ordinary PCR products are not equated with productive LAMP kinetics |
| `reference_compare` | NEB LAMP tool / PrimerExplorer V5 | target and fixed-primer constraints if manually supplied | reference-only candidate-set comparison |
| `benchmark` | LAMPrimers iQ / LAVA / GLAPD | exact version/source and native heuristics | benchmark-only evidence |

### Normalized output

```text
LampSetResult {
  set_id
  role_oligos {
    F3, B3,
    FIP { full_sequence, segments:[F1c,F2], binding_regions[] },
    BIP { full_sequence, segments:[B1c,B2], binding_regions[] },
    LF?, LB?
  }
  role_order_and_spacing_checks
  thermodynamic_features_by_oligo_and_segment
  interaction_graph[]
  background_binding_evidence
  set_score_components
  chemistry_profile_id
  warnings[]
  tool_runs[]
}
```

No set-level score may hide the single interaction edge or geometry rule that caused a rejection.

### Engine-specific failures and controlled recovery

- `INCOMPLETE_CORE_LAMP_SET`: fewer than the required core roles can be satisfied; isolated good primers are not returned as a successful set.
- `ROLE_ORDER_OR_SPACING_VIOLATION`: role coordinates are individually valid but the LAMP topology is invalid; hard reject.
- `COMPOSITE_ORIENTATION_ERROR`: FIP/BIP segment orientation or concatenation cannot round-trip to the template; hard reject.
- `LOOP_PRIMER_UNAVAILABLE`: core set may remain valid if the owning module permits a no-loop branch; do not relax the core geometry implicitly.
- `LAMP_KINETICS_UNMODELED`: ordinary thermodynamic/specificity tools cannot establish reaction kinetics; keep this as a claim boundary, not a warning score bonus.

### Regression fixture matrix

Fixtures include canonical six-role and four-primer core designs; unavailable LF/LB; reverse-complement target; circular/ambiguous target rejection if unsupported; FIP/BIP segment-order swap; tight spacing boundary; a severe cross-role dimer; repeated target sequence causing specificity conflict; and manual NEB/PrimerExplorer comparison. Assert role identity, segment coordinates, composite sequences, set completeness and deterministic set ordering.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
