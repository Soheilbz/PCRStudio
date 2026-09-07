# Single Primer Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `single-primer` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| Primer3 / `primer3-py` | searches a direction-specific oligo | does not establish transcript end or sequencing quality ([Primer3 manual](https://primer3.org/manual.html)) |
| transcript/adaptor boundary evaluator | checks known sequence, adaptor and end orientation | end completeness remains experimental ([Matz et al.](https://pubmed.ncbi.nlm.nih.gov/31043556/)) |
| sequence-read planning | records read direction, useful region and confirmation method | read quality depends on instrument and template ([Primer3 manual](https://primer3.org/manual.html)) |
| NEB Template Switching M0466 / FirstChoice RLM-RACE / BigDye v3.1 protocol registry | preserves RACE chemistry topology and Sanger kit-document revision as explicit protocol identities | protocol values live in the owning RACE or sequencing-primer module and cannot cross branches ([NEB M0466 5′ RACE](https://www.neb.com/en-sg/protocols/5-race-protocol-using-the-template-switching-rt-enzyme-mix), [FirstChoice RLM-RACE](https://documents.thermofisher.com/TFS-Assets/LSG/manuals/MAN1001624-FirstChoiceRLMRACE-UG.pdf), [BigDye v3.1 Rev. B](https://documents.thermofisher.com/TFS-Assets/LSG/manuals/MAN1000355-BDTv3-1CycleSeqKit-UG.pdf)) |

```text
primer_direction  known_boundary  unknown_end  adaptor_sequence
tail_sequence  read_direction  read_length  quality_boundary
template_type  confirmation_method
```

## Field families and result provenance

Primer direction, known internal sequence, adaptor/template-switch identity, substrate and confirmation method must be retained as one RACE workflow record. The direction-specific primer does not by itself establish transcript-end completeness ([Edwards et al.](https://pubmed.ncbi.nlm.nih.gov/11071950/), [Pinto & Lindblad](https://pubmed.ncbi.nlm.nih.gov/19837043/)).

Read length and quality boundary describe the sequencing or readout handoff; they are not hidden primer-search values. End claims require appropriate controls and independent confirmation because artefacts and incomplete substrates can change the observed end ([Pinto & Lindblad](https://pubmed.ncbi.nlm.nih.gov/19837043/)).

## Generation-1 production toolchain

| Tool/method | Role | Engine use | Production decision |
| --- | --- | --- | --- |
| Primer3 (shared pin) | `PRIMARY` | sequencing-primer placement and RACE gene-specific annealing-core candidate generation where ordinary oligo selection applies | local subprocess; exact task/region/coordinate semantics captured |
| PCRStudio RACE/read-direction wrapper | `PRIMARY` | adaptor/known-sequence boundary, GSP orientation, readable-span and sequencing-direction logic | deterministic module logic; vendor RACE chemistry stays in the assay record |
| MFEprimer/BLAST+ | `VALIDATOR` | uniqueness/background binding checks | frozen background database and exact settings |
| RACE kit tools/manuals and BigDye guidance | `REFERENCE` | chemistry/readout overlays | vendor protocols do not become backend candidate generators |

### Single-primer result contract

The result always separates `binding_site`, `primer_sequence`, `extension_direction`, `expected_read_or_extension_span` and any adaptor/known-sequence dependence. A good single-primer Tm/structure score cannot establish transcript-end recovery or Sanger trace quality; those remain validation/readout boundaries.

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
branch selection (RACE | sequencing-primer)
        -> known/unknown boundary or read-direction normalization
        -> direction-specific search window
        -> Primer3 single-oligo candidate evaluation
        -> MFEprimer/BLAST+ uniqueness/background validation
        -> branch-specific adaptor/read-span checks
        -> deterministic ranking
        -> empirical end/readout validation handoff
```

### Engine-owned canonical inputs

```text
branch  template_id  template_type  known_sequence_interval
unknown_end  adaptor_or_TSO_identity  adaptor_sequence
primer_direction  extension_direction  search_window
read_direction  desired_read_span  quality_boundary_policy
RACE_protocol_identity  RT_primer_identity  nested_GSP_policy
sequencing_chemistry  instrument_platform
assay_profile_id  chemistry_profile_id  background_database
```

RACE and Sanger sequencing share single-oligo placement machinery but do **not** share endpoint/read-quality claims or vendor protocol values.

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Required captured semantics | Normalized result |
| --- | --- | --- | --- |
| `design_single_oligo` | Primer3 | direction-specific allowed region, pick-left/pick-right state, size/Tm/GC/structure and chemistry | one or more single annealing candidates with explicit extension direction |
| `validate_uniqueness` | MFEprimer/BLAST+ | single-primer binding sites and, where applicable, partner/adaptor context | binding evidence; single-primer uniqueness is not confused with pair-product specificity |
| `resolve_race_boundary` | PCRStudio | 5′/3′ RACE topology, known gene sequence, adaptor/TSO/RT-primer identity and GSP direction | RACE primer linked to protocol/end topology |
| `plan_sanger_read` | PCRStudio | primer binding site, extension direction, desired region and platform/chemistry metadata | predicted read orientation/span handoff, not a promised quality length |
| `vendor_reference` | NEB M0466 / FirstChoice RLM-RACE / BigDye v3.1 | exact manual/product revision and branch-specific values | reference overlay only |

NEB's current template-switching 5′ RACE protocol, for example, distinguishes TSO-specific and gene-specific primers and states protocol-specific preferences for the gene-specific primer; such values stay attached to the `M0466` protocol identity rather than becoming generic single-primer defaults ([NEB M0466 protocol](https://www.neb.com/en/protocols/5-race-protocol-using-the-template-switching-rt-enzyme-mix)).

### Normalized output

```text
SinglePrimerResult {
  branch
  primer { sequence, binding_interval, extension_direction }
  known_unknown_boundary
  adaptor_or_protocol_dependency
  binding_uniqueness
  expected_extension_or_read_span
  sequencing_or_end_confirmation_handoff
  score_components
  warnings[]
  tool_runs[]
}
```

### Engine-specific failures and controlled recovery

- `DIRECTION_OR_BOUNDARY_AMBIGUOUS`: required extension direction or known/unknown end topology is not resolvable; refuse.
- `NO_SINGLE_PRIMER_UNDER_CONTRACT`: report search-window and Primer3 rejection evidence; relax only via branch module policy.
- `RACE_PROTOCOL_MISMATCH`: adaptor/TSO/RT-primer assumptions are mixed across incompatible protocol branches; hard block until explicitly resolved.
- `SINGLE_BINDING_NONUNIQUE`: multiple high-risk binding sites exist in the declared background; do not treat absence of a second PCR primer as absence of specificity risk.
- `READ_QUALITY_UNVERIFIED`: predicted orientation/span exists but empirical read quality is absent; this is a handoff state, not design failure.

### Regression fixture matrix

Fixtures cover 5′ RACE, 3′ RACE, template-switching adaptor, gene-specific RT primer + nested GSP relationship, reverse-oriented gene target, upstream/downstream Sanger primer, repeated-template uniqueness failure, desired-read-region boundary and protocol identity mismatch. Assert direction, boundary, adaptor dependence and branch separation.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
