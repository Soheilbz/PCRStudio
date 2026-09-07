# Nested PCR Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `nested` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| Primer3 / `primer3-py` | searches outer and inner pairs under separate contracts | does not establish nesting workflow success ([Primer3 manual](https://primer3.org/manual.html)) |
| containment evaluator | verifies inner product lies within the outer product | geometry alone does not prove second-round specificity ([Snounou et al.](https://pubmed.ncbi.nlm.nih.gov/8264734/)) |
| cross-round interaction evaluator | checks outer/inner oligo compatibility across the two executable rounds | does not model carryover or transfer contamination; one-tube four-oligo evaluation is reference-only in Generation-1 ([Longo et al.](https://doi.org/10.1016/0378-1119(90)90145-h)) |
| specificity/validation handoff | records background, controls and round workflow | laboratory performance remains external ([NCBI assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)) |
| successive-amplification contamination-control record | records workflow direction, opened-tube transfer, NTC placement and separated pre/post-amplification handling | laboratory contamination control is not inferable from nested-primer containment and remains an explicit workflow handoff ([CDC Good Laboratory Practices](https://www.cdc.gov/mmwr/preview/mmwrhtml/rr5806a1.htm)) |

```text
outer_pair  inner_pair  nesting_margin  round_mode  transfer_volume
round_temperature  cross_round_interaction  background_scope
carryover_control  confirmation_method
```

## Field families and result provenance

The outer and inner pairs are two linked records, not four interchangeable primers. The containment relation and explicit two-tube round provenance must be retained together so that a second-round result is not misreported as a single-round specificity claim ([Snounou et al.](https://pubmed.ncbi.nlm.nih.gov/8264734/)).

Transfer volume, carry-over control, reaction identity and confirmation method are workflow provenance. They are not inferred from primer geometry. Generation-1 executes the two-tube workflow only; one-tube literature branches carry different contamination and interaction risks and require a separate future protocol contract ([QIAGEN CLC Nested PCR manual](https://resources.qiagenbioinformatics.com/manuals/clcgenomicsworkbench/current/index.php?manual=Nested_PCR.html), [NCBI assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)).

## Generation-1 production toolchain

| Tool/method | Role | Engine use | Production decision |
| --- | --- | --- | --- |
| Primer3 (shared pin) | `PRIMARY` | outer-round and inner-round pair generation under separate profiles | two explicit calls/profiles; no silent inheritance of inner/outer constraints |
| PCRStudio containment validator | `PRIMARY` | enforce inner-product containment/orientation and coordinate mapping from outer product to original template | deterministic topology gate before ranking |
| MFEprimer (shared pin) + BLAST+ (shared pin) | `VALIDATOR` | outer, inner and cross-round specificity evidence | each round is checked with its declared template/background context |
| PrimerPooler (shared minimum/pin) | `OPTIONAL` | cross-round/cross-assay interaction review when many nested assays share a run | explicit set-level use only; not needed for one isolated nested assay |

### Two-round execution contract

The outer and inner pair are separate candidate objects linked by `outer_product_id`. Failure to generate an inner pair must not cause unreported relaxation of the outer pair. Cross-round primer interactions and contaminating first-round product are separate evidence families from genomic specificity.

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
template/background intake
        -> outer Primer3 call under outer_profile
        -> outer product reconstruction/validation
        -> inner search space derived from outer product
        -> inner Primer3 call under inner_profile
        -> containment + nesting-margin validation
        -> per-round MFEprimer/BLAST+ specificity
        -> cross-round interaction review
        -> optional multi-assay PrimerPooler review
        -> deterministic pair-of-pairs ranking
```

### Engine-owned canonical inputs

```text
template_id  background_database
outer_profile_id  inner_profile_id
outer_product_range  inner_product_range  nesting_margin_policy
round_mode  one_tube_or_two_tube  cross_round_interaction_policy
round1_chemistry_profile  round2_chemistry_profile
transfer_workflow  carryover_control  contamination_control
confirmation_method
```

Outer and inner profiles are fully resolved independently. The inner profile does not inherit a missing value from the outer profile unless a shared profile explicitly supplies that value and provenance records the inheritance.

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Required captured semantics | Normalized result |
| --- | --- | --- | --- |
| `design_outer` | Primer3 | original template, outer target/regions and complete outer profile | outer candidate pairs + products |
| `derive_inner_template` | PCRStudio | selected outer product sequence/coordinates and source mapping | inner search template linked to `outer_product_id` |
| `design_inner` | Primer3 | inner template/region and complete inner profile | inner pair mapped both to outer-product and original-template coordinates |
| `validate_containment` | PCRStudio | inner/outer product intervals, minimum margins and orientation | explicit containment/margin checks |
| `validate_specificity` | MFEprimer/BLAST+ | round-specific primers, template/background and product ranges | separate outer, inner and cross-combination evidence |
| `validate_interactions` | PrimerPooler when set-level review is enabled | four primers and any neighboring assays; explicit ΔG/score chemistry | optional interaction/pooling evidence |

### Normalized output

```text
NestedPCRResult {
  nested_assay_id
  outer_pair { pair, product_interval, product_sequence_hash, specificity }
  inner_pair { pair, product_interval_on_outer, product_interval_on_source, specificity }
  containment_check
  nesting_margins
  cross_round_interactions
  round_workflow_provenance
  contamination_control_handoff
  score_components
  warnings[]
  tool_runs[]
}
```

Genomic/locus specificity, containment and laboratory carryover risk are distinct evidence families and must not be collapsed into one “specific” flag.

### Engine-specific failures and controlled recovery

- `NO_OUTER_PAIR`: no valid first-round pair; inner design is not attempted.
- `OUTER_PRODUCT_UNRESOLVED`: product sequence cannot be reconstructed unambiguously; inner design is blocked.
- `NO_INNER_PAIR`: outer result remains auditable but the nested assay is unsuccessful; outer constraints are not silently relaxed.
- `INNER_NOT_CONTAINED`: coordinate mapping or required nesting margin fails; hard reject.
- `CROSS_ROUND_PRODUCT_RISK`: unintended combinations among outer/inner primers create a prohibited product; reject or explicitly rerank according to module policy.
- `CONTAMINATION_WORKFLOW_UNSPECIFIED`: sequence design may be returned, but any claim of a validated successive-amplification workflow is blocked.

### Regression fixture matrix

Fixtures include clean two-round nesting, inner primer at a margin boundary, inner pair outside outer product, reverse-strand coordinate mapping, separate outer/inner chemistry profiles, explicit refusal of one-tube execution, two-tube workflow metadata, duplicated background target and a case where only the inner pair fails. Assert independent profile resolution and source-coordinate round-trip.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
