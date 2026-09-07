# Mutagenic Pair Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `mutagenic-pair` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| reference/edit sequence comparator | constructs and verifies the intended edit | does not prove polymerase fidelity or clone identity ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/)) |
| mutagenic primer evaluator | checks overlap, mismatch and whole-product geometry | method performance depends on template and polymerase ([Qi et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7351327/)) |
| high-fidelity polymerase protocol | supplies reaction and extension context | values belong to the selected product manual ([NEB Q5 protocol](https://www.neb.com/en/protocols/pcr-using-q5-hot-start-high-fidelity-dna-polymerase-m0493)) |
| parental-template removal/clone verification | supports post-PCR selection and confirmation | must be recorded as experimental workflow ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/)) |
| NEBaseChanger | designs Q5 back-to-back mutagenic primers and returns a Q5-specific annealing temperature/troubleshooting context | values and edit-size rules remain Q5/E0554-scoped in `02-site-directed-mutagenesis.md`; the tool does not validate the recovered clone ([NEB Q5 primer-design FAQ](https://www.neb.com/en-us/faqs/how-do-i-design-primers-to-use-with-the-q5-site-directed-mutagenesis-kit)) |

| NEBaseChanger → NEBuilder HiFi multi-site branch ([NEBaseChanger](https://nebasechanger.neb.com/), [NEB tutorial](https://www.neb.com/en-gb/tools-and-resources/video-library/nebasechanger-primer-design-tool-tutorial)) | designs primers for multiple site-directed changes using NEBuilder HiFi assembly rather than the Q5 single-site back-to-back branch | this is an overlap-assembly mutagenesis topology and must route to a distinct chemistry/protocol identity; it is not interchangeable with Q5/E0554 or QuikChange Multi |

```text
reference_sequence  edited_sequence  edit_type  edit_position  allele_change
primer_overlap  plasmid_topology  polymerase_identity  parental_template_treatment
transformation  clone_sequence_status
```

## Field families and result provenance

The edit definition, template topology, primer architecture and polymerase identity form one protocol record. A sequence-level edit check cannot certify polymerase fidelity, parental-template removal or the genotype of a recovered clone ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/)).

Protocol-specific reaction values are resolved by the selected polymerase or kit overlay and must not be copied from a different mutagenesis workflow ([NEB Q5 protocol](https://www.neb.com/en/protocols/pcr-using-q5-hot-start-high-fidelity-dna-polymerase-m0493)).

## Generation-1 production toolchain

| Tool/method | Role | Engine use | Production decision |
| --- | --- | --- | --- |
| Primer3 (shared pin) | `PRIMARY` | annealing/core candidate features for the declared edit topology | local subprocess; PCRStudio owns edit normalization and mutation placement |
| PCRStudio edit/topology normalizer | `PRIMARY` | normalize substitution/insertion/deletion, circular plasmid coordinates, overlap/back-to-back geometry and edited construct | deterministic sequence transformation with before/after construct hashes |
| MFEprimer/BLAST+ | `VALIDATOR` | background/off-target checks when relevant | exact databases/settings captured |
| NEBaseChanger | `REFERENCE` | Q5-specific single-site/back-to-back and NEBuilder multi-site design comparison | web-only vendor reference; Q5 values stay source-scoped in the module |
| pydna (shared pin) | `OPTIONAL` | current PCRStudio adapter: independent selected-primer PCR-product simulation | validation aid, not primary candidate generator ([pydna](https://pypi.org/project/pydna/5.5.16/)) |

### Edit-preservation contract

The adapter must round-trip `reference_sequence → normalized_edit → edited_sequence` before candidate design and verify that reconstructed primer-incorporated product contains exactly the requested edit. Candidate ranking cannot compensate for a failed edit reconstruction. Multi-site assembly-like designs route to the junction/assembly topology instead of silently using the Q5 single-site branch.

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
plasmid/construct + requested edit
        -> edit normalization and edited-construct construction
        -> topology branch selection
        -> mutagenic/non-mutagenic annealing-core placement
        -> Primer3 core feature evaluation
        -> full primer construction
        -> exact edited-product reconstruction
        -> background/off-target checks when relevant
        -> pydna independent PCR-product simulation when enabled
        -> chemistry-specific reference overlay (e.g. Q5/NEBaseChanger)
```

### Engine-owned canonical inputs

```text
construct_id  source_construct_sequence  circularity
edit_id  edit_type  source_edit_repr  normalized_edit
reference_segment  replacement_or_insert_sequence  deletion_interval
edited_construct_hash  topology_branch
mutagenic_primer_side  annealing_core_policy  mutation_segment_policy
primer_pair_relationship  overlap_or_back_to_back_policy
polymerase_profile  kit_profile  KLD_or_template_removal_branch
background_database
```

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Required captured semantics | Normalized result |
| --- | --- | --- | --- |
| `normalize_edit` | PCRStudio | substitution/insertion/deletion source representation, normalized position/sequence, circular wrap handling | immutable edit record + before/after construct hashes |
| `enumerate_mutagenic_pair` | PCRStudio + Primer3 | annealing core vs edited/non-annealing segment, direction, pair topology, core size/Tm/GC/structure constraints | role-labelled full primers with exact mutation segment annotation |
| `verify_edit_product` | PCRStudio | predicted PCR product/circularized construct and authorized edit | sequence diff against requested edited construct; no extra changes allowed |
| `validate_background` | MFEprimer/BLAST+ | annealing cores/full primers as appropriate and declared background | binding/off-target evidence |
| `simulate_selected_primer_product` | pydna | supplied template and selected primers | optional independent PCR-product evidence; complete edited-construct reconstruction is not claimed |
| `vendor_reference` | NEBaseChanger/Q5 | edit topology and chemistry-specific design/annealing guidance | reference record; web service never owns internal candidate output |

NEB explicitly recommends back-to-back primer design with NEBaseChanger for the Q5 Site-Directed Mutagenesis workflow and treats substitutions/insertions/deletions as kit-specific design cases. Those rules remain a Q5 profile, not a universal mutagenesis engine default ([NEB Q5 primer-design FAQ](https://www.neb.com/en-us/faqs/how-do-i-design-primers-to-use-with-the-q5-site-directed-mutagenesis-kit)).

### Normalized output

```text
MutagenicPairResult {
  edit_id
  normalized_edit
  source_construct_hash
  expected_edited_construct_hash
  topology_branch
  primers[] { annealing_core, mutation_or_tail_segment, full_oligo, binding_interval }
  predicted_product_or_construct_hash
  exact_edit_diff_check
  background_specificity
  structure_interactions
  chemistry_reference
  warnings[]
  tool_runs[]
}
```

### Engine-specific failures and controlled recovery

- `EDIT_REFERENCE_MISMATCH`: requested edit does not match the supplied source construct; refuse.
- `EDIT_NORMALIZATION_AMBIGUOUS`: equivalent representations cannot be resolved without changing intended sequence; refuse or require explicit representation.
- `EDIT_NOT_PRESERVED`: predicted construct differs from the requested edited construct outside the authorized edit; hard reject.
- `TOPOLOGY_BRANCH_UNSUPPORTED`: edit is forced into a mutagenesis topology not supported by the selected module/chemistry; do not emulate it with generic pair design.
- `CORE_PASS_FULL_PRIMER_FAIL`: mutation/tail segment causes unacceptable full-primer structure; redesign while preserving edit semantics.

### Regression fixture matrix

Fixtures cover single-base substitution, multi-base substitution, insertion, deletion, circular-origin edit, one-mutagenic-primer and two-mutagenic-primer cases, Q5 back-to-back geometry, long/non-annealing edit segment, duplicated plasmid region, and a deliberate failure containing an extra unintended base. Assert exact before/after hashes, edit diff, segment annotation and topology.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
