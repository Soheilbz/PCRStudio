# Discriminating Pair Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `discriminating-pair` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| Primer3 / `primer3-py` | candidate oligo and product search under a supplied allele contract | does not prove allele discrimination ([Primer3 manual](https://primer3.org/manual.html)) |
| PCRStudio generalized allele-aware generator (ARMSprimer3 reference) | masks interfering neighbouring variants, enumerates deliberate mismatch templates and tests both left/right allele-specific orientations before Primer3 candidate selection | ARMSprimer3 is a computational precedent; its defaults and validation results are implementation/study-specific, not universal ARMS rules ([Guo et al., 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12104711/)) |
| BatchPrimer3 / tetra-primer generator | enumerates both theoretical tetra-primer orientation sets and position-restricted allele-specific candidates | the program implements published Tetra-ARMS heuristics; software output still requires interaction, band-resolution and wet-lab validation ([You et al., BatchPrimer3](https://pmc.ncbi.nlm.nih.gov/articles/PMC2438325/)) |
| allele-aware mismatch evaluator | compares intended and competing allele terminal geometry | mismatch effects remain chemistry- and context-dependent ([Kwok et al.](https://pubmed.ncbi.nlm.nih.gov/2179874/)) |
| multiplex/set scorer | reviews competing products and interaction risk | does not establish fluorescence-cluster separation or gel-resolvable bands; those are assay/readout validation questions ([LGC KASP cluster-plot guide](https://biosearchassets.biosearchtech.com/assetsv6/Analysis-of-KASP-genotyping-data-using-cluster-plots.pdf), [Medrano & de Oliveira](https://pubmed.ncbi.nlm.nih.gov/24519268/)) |
| external genotyping/readout analysis | evaluates fluorescence, melt, gel or sequencing calls | external evidence must retain platform and control provenance ([Cuppen](https://pubmed.ncbi.nlm.nih.gov/21357174/)) |
| LGC KASP assay-design / troubleshooting overlay | records chemistry-version, high-GC, homology, instrument and cluster-analysis context for an LGC KASP branch | vendor troubleshooting values stay in `03-kasp.md`; the tool layer does not convert them into universal allele-specific rules ([LGC KASP troubleshooting guide](https://biosearchassets.biosearchtech.com/assetsv6/KASP-troubleshooting-guide.pdf)) |

```text
variant_position  reference_allele  alternate_allele  allele_orientation
terminal_mismatch  deliberate_mismatch  product_size  channel_or_band
call_rule  control_panel  genotype_confirmation
```

The vocabulary is descriptive; a module must declare which fields are active and how their evidence is bounded ([Primer3 manual](https://primer3.org/manual.html)).

## Field families and result provenance

Variant coordinates, strand orientation, mismatch identity/position, product readout and control panel are separate evidence families. A terminal mismatch can change allele preference, but its effect depends on mismatch identity, position, neighbouring sequence and polymerase; no generic mismatch field is a validated genotype call ([Kwok et al.](https://pubmed.ncbi.nlm.nih.gov/2179874/), [Newton et al.](https://pubmed.ncbi.nlm.nih.gov/2785681/)).

The exported record must preserve the intended alleles, competing-template checks and the declared call rule. Reference, alternate, heterozygous and no-template controls remain part of assay validation rather than a Primer3 output field ([Newton et al.](https://pubmed.ncbi.nlm.nih.gov/2785681/), [Ye et al.](https://pubmed.ncbi.nlm.nih.gov/11522844/), [LGC KASP cluster-plot guide](https://biosearchassets.biosearchtech.com/assetsv6/Analysis-of-KASP-genotyping-data-using-cluster-plots.pdf)).

## Generation-1 production toolchain

This engine inherits the shared execution/adapter contract from [`../../knowledge/design-intelligence.md`](../../knowledge/design-intelligence.md#generation-1-toolchain-maturity-contract). Generation 1 keeps allele discrimination transparent: a Primer3 search is combined with PCRStudio-owned allele/mismatch geometry rather than delegated to an opaque genotyping model.

| Tool/method | Role | Engine use | Production decision |
| --- | --- | --- | --- |
| Primer3 (shared pin) | `PRIMARY` | constrained candidate generation for common and allele-specific annealing segments | local subprocess; complete parameter provenance; does not itself prove allele discrimination ([Primer3 manual](https://primer3.org/manual.html)) |
| PCRStudio allele-aware wrapper | `PRIMARY` | variant normalization, intended/competing-template construction, 3′ placement, deliberate-mismatch templates and orientation enumeration | deterministic internal logic whose hard/soft rules come from the owning ARMS/KASP/Tetra-ARMS module |
| MFEprimer (shared pin) + BLAST+ (shared pin) | `VALIDATOR` | target/off-target products and locus specificity | frozen background database; exact version/schema/settings captured ([MFEprimer](https://www.mfeprimer.com/updates/), [BLAST+](https://www.ncbi.nlm.nih.gov/books/NBK131777/)) |
| EasyKASP 2025 | `REFERENCE` | KASP-specific candidate ranges, direction heuristic and Tm formula extracted from 500 successful primers | Excel/VBA/GPL tool is not a backend dependency; its values are source-scoped in `03-kasp.md` ([EasyKASP](https://pmc.ncbi.nlm.nih.gov/articles/PMC12717768/)) |
| PolyMarker | `OPTIONAL` | polyploid/homoeolog-specific KASP design | only for declared polyploid context; requires its own external dependencies and current reference genomes |
| ARMSprimer3 | `BENCHMARK` | published allele-aware generation precedent | legacy human/UCSC/database assumptions prevent it from being a general production dependency; PCRStudio reimplements only source-supported logic against current data |
| BatchPrimer3 / Tetra-ARMS tools | `BENCHMARK` | compare orientation and tetra-primer geometry | no silent import of historical defaults or product-ranking heuristics |

### Polymerase-aware mismatch contract

Mismatch identity/position is stored independently from polymerase/chemistry. The validator may compute thermodynamic destabilization, but amplification discrimination is not derived from ΔTm/ΔG alone. When a module uses an empirical mismatch rule, the rule must identify polymerase family/proofreading status and evidence scope; otherwise the worker returns the generic sequence-level warning instead of inventing a universal mismatch penalty ([Huang et al., 2024](https://www.mdpi.com/2073-4425/15/2/215)).

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
variant + reference intake
        -> variant normalization / allele-template construction
        -> assay branch (ARMS | KASP | Tetra-ARMS)
        -> orientation and intentional-mismatch enumeration
        -> Primer3 annealing-core candidate evaluation
        -> assay-specific hard geometry/mismatch filters
        -> MFEprimer + BLAST+ locus/background validation
        -> allele-separation evidence aggregation
        -> deterministic ranking
```

Variant representation is normalized before primer design. Left-normalization/representation changes must preserve the intended alternate construct and a round-trip link to the user's source variant.

### Engine-owned canonical inputs

```text
variant_id  source_variant_repr  reference_id  reference_allele  alternate_allele
normalized_start0  normalized_ref  normalized_alt  variant_class
intended_allele  competing_alleles[]  assay_branch
allele_specific_side  deliberate_mismatch_policy  mismatch_position_policy
common_primer_policy  tetra_outer_policy  product_separation_policy
tail_identity_or_reporter_identity  polyploid_context  homoeolog_background
assay_profile_id  chemistry_profile_id  background_database
```

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Required captured semantics | Normalized result |
| --- | --- | --- | --- |
| `normalize_variant` | PCRStudio | source coordinate/alleles, normalized coordinate/alleles, reference build and alternate-construct hash | one immutable variant-normalization record |
| `enumerate_allele_specific_candidates` | PCRStudio + Primer3 | intended/competing template, allele-specific 3′ placement, deliberate mismatch identity/position, Primer3 region/size/Tm/GC constraints | role-labelled annealing cores with mismatch provenance |
| `evaluate_discrimination` | PCRStudio thermo/mismatch layer | mismatch identity, position from extendable 3′ end, nearest-neighbour context, polymerase family/proofreading state and reaction profile | source/model-labelled intended-vs-competing discrimination features |
| `validate_locus` | MFEprimer/BLAST+ | both allelic/common primers, possible primer combinations, frozen locus/background DB | intended products, competing-allele products and off-target evidence kept distinct |
| `polyploid_specialization` | PolyMarker when enabled | genome/reference assemblies, target chromosome/homoeolog context, tool/version | optional homoeolog-specific candidate evidence |
| `reference_profile` | EasyKASP / ARMSprimer3 / Tetra-ARMS tools | exact source/tool profile and any imported heuristic | reference/benchmark record only |

### Assay-branch ownership

`ARMS`, `KASP` and `Tetra-ARMS` are separate subcontracts. A mismatch rule, tail sequence, fluorescence convention, product-size separation rule or empirical Tm range from one branch cannot leak into another through a shared field name. EasyKASP numeric evidence remains a named KASP empirical profile, including its source-code-resolved Tm formula semantics; it is not a generic Primer3 or ARMS default.

### Normalized output

```text
DiscriminatingPairResult {
  assay_branch
  normalized_variant
  intended_template_hash
  competing_template_hashes[]
  primers[] { role, annealing_core, full_oligo, binding_interval, intentional_mismatches[] }
  intended_product_geometry
  competing_product_geometry[]
  discrimination_evidence { model_id, intended_features, competing_features }
  locus_specificity
  assay_specific_call_geometry
  score_components
  warnings[]
  tool_runs[]
}
```

A predicted allele-specific primer is not labelled experimentally discriminating unless wet-lab call separation is provided by the validation layer.

### Engine-specific failures and controlled recovery

- `VARIANT_REFERENCE_MISMATCH`: normalized REF does not match the supplied reference; refuse design.
- `ALLELE_SPECIFIC_3P_PLACEMENT_IMPOSSIBLE`: the assay branch cannot place the discriminating base under its hard topology; do not silently move it.
- `MISMATCH_MODEL_OUT_OF_SCOPE`: polymerase/context required to interpret an intentional mismatch is absent; retain model-agnostic features or refuse a hard discrimination claim.
- `NO_COMMON_PRIMER_OR_TETRA_GEOMETRY`: allele-specific cores exist but the complete assay topology does not; return no set rather than isolated primers.
- `HOMOELOG_CONTEXT_MISSING`: a polyploid-specific request lacks the needed reference/homoeolog evidence; PolyMarker-style specialization cannot be claimed.

### Regression fixture matrix

Fixtures cover SNP, short insertion and deletion normalization; forward and reverse allele-specific orientation; same variant represented in equivalent VCF forms; a deliberate mismatch at multiple positions; intended/competing allele inversion; KASP common-primer choice; tetra four-primer geometry/band ordering; polyploid near-homoeologs; and a locus with a deceptive off-target. Assert normalized construct hashes, primer roles, mismatch coordinates, product identities and validator evidence.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
