# Junction Primers Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `junction-primers` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| fragment/FASTA intake | validates fragment identity, sequence, orientation, declared topology and source-template provenance | cannot certify physical fragment integrity or experimental purity |
| overlap/junction evaluator | checks exact homology, orientation, intended junction sequence, duplicate/repetitive terminal sequence and graph compatibility | sequence complementarity is not assembly yield or clone validation ([Gibson et al.](https://pubmed.ncbi.nlm.nih.gov/19363495/)) |
| Primer3 / `primer3-py` | optional search/evaluation of the template-annealing segment of primers used to generate an individual fragment | does not model the complete assembly reaction; 5′ assembly tails and assembly chemistry require separate accounting ([Primer3 manual](https://primer3.org/manual.html)) |
| NEBuilder Assembly Tool | independent vendor precedent for multi-fragment planning, Gibson-vs-NEBuilder chemistry selection, polymerase-aware primer design, linear/circular constructs, fragment reordering, restriction-digested inputs, optional spacer/site regeneration and oligo export | tool behavior is external evidence and is not proof that PCRStudio implements every feature ([NEBuilder Assembly Tool 2.0](https://www.neb.com/en/tools-and-resources/video-library/nebuilder-assembly-tool-20-whats-new)) |
| external assembly planner | supports reaction-specific multi-fragment planning, molarity calculations and construct visualization | output remains conditional on the selected chemistry and protocol ([Gibson et al.](https://pubmed.ncbi.nlm.nih.gov/19363495/)) |

```text
fragment_id  fragment_order  orientation  construct_topology  junction_id
fragment_generation_method  source_template_id  source_coordinates
overlap_sequence  overlap_length  overlap_distribution  junction_tm
fragment_count  insert_count  total_part_count  molarity  purity
assembly_chemistry  chemistry_capability_flags  reaction_identity
restriction_end_geometry  spacer_sequence  site_regeneration_policy
validation_status  evidence_status  tool_version  thermodynamic_model
```

## Field families and result provenance

The engine keeps fragment identity, ordered junction geometry, construct topology, fragment-generation method and reaction identity separate: an overlap sequence is not a replacement for fragment order, and an in-silico junction check is not an assembled-clone result ([Gibson et al.](https://pubmed.ncbi.nlm.nih.gov/19363495/)).

`insert_count` and `total_part_count` are distinct fields. Vendor documents may describe “five inserts plus a vector” while product pages summarize the same scope as “up to six fragments”; the engine must preserve the vendor's terminology and normalize it only through explicitly typed fields, never by silently changing the count convention ([GeneArt Gibson Assembly HiFi User Guide, revision D](https://documents.thermofisher.com/TFS-Assets/LSG/manuals/MAN0019062_GeneArtGibsonHiFi_UG.pdf), [GeneArt HiFi product page](https://www.thermofisher.com/order/catalog/product/A46628)).

`chemistry_capability_flags` must be chemistry-scoped. In particular, NEBuilder HiFi has end-mismatch-removal capabilities that NEB explicitly distinguishes from Gibson Assembly; a junction that depends on a NEBuilder-specific mismatch-removal behavior must not be relabeled as a generic Gibson-compatible junction ([NEBuilder HiFi mismatch-removal guidance](https://www.neb.com/en-us/tools-and-resources/video-library/nebuilder-hifi-dna-assembly-removal-of-3-end-mismatches), [NEB chemistry comparison FAQ](https://www.neb.com/en-us/faqs/i-am-not-sure-whether-to-choose-nebuilder-hifi-dna-assembly-or-neb-gibson-assembly)).

The exported record must retain the selected assembly chemistry, fragment set, orientation, intended construct topology, junction sequence, source-template provenance, primer-design engine/version and validation status. Primer3's latest tagged release remains `2.6.1`, while its upstream release notes contain an unreleased `2.7.0` section with thermodynamic changes; therefore an exact engine/version/thermodynamic-settings record is required whenever Primer3 contributes a design decision rather than treating development-branch behavior as a production default ([Primer3 releases](https://github.com/primer3-org/primer3/releases), [Primer3 development release notes](https://github.com/primer3-org/primer3/blob/main/src/release_notes.txt)).

NEBuilder Assembly Tool 2.0 is useful as a feature-completeness precedent because it can treat vectors as fragments, choose Gibson or NEBuilder chemistry and the PCR polymerase, represent linear or circular assemblies, reorder fragments, add custom spacers, plan restriction-digested inputs and regenerate restriction sites, distribute overlaps between adjacent primers, split long sequences into overlapping fragments, display junction details and export required oligos. These capabilities are documented comparison targets only; each requires its own PCRStudio implementation and test before it can be claimed as supported ([NEBuilder Assembly Tool 2.0](https://www.neb.com/en/tools-and-resources/video-library/nebuilder-assembly-tool-20-whats-new), [NEBuilder restriction-digest workflow](https://www.neb.com/en/tools-and-resources/video-library/nebuilder-assembly-tool-20-restriction-enzyme-digest)).

## Generation-1 production toolchain

This engine inherits the shared adapter contract from [`../../knowledge/design-intelligence.md`](../../knowledge/design-intelligence.md#generation-1-toolchain-maturity-contract).

| Tool/method | Role | Engine use | Production decision |
| --- | --- | --- | --- |
| Primer3 (shared pin) | `PRIMARY` | annealing-core candidate generation after junction/overlap geometry is resolved | local subprocess; PCRStudio owns full-oligo assembly and distinguishes annealing core from 5′ overlap/tail |
| PCRStudio junction composer | `PRIMARY` | end geometry, overlap construction, insert/vector orientation, restriction-derived ends and construct sequence | deterministic sequence transformation; final full oligo is rechecked after tail/overlap addition |
| MFEprimer/BLAST+ | `VALIDATOR` | template/off-target checks when genomic or complex backgrounds are part of the request | local frozen databases with exact versions/settings |
| pydna (shared pin) | `OPTIONAL` | current PCRStudio adapter: independent PCR-product simulation of amplified fragments; the pydna library itself has broader assembly capabilities that are not claimed by this adapter | local Python validator; never owns the design rule or replaces sequence-level construct verification ([pydna](https://pypi.org/project/pydna/5.5.16/)) |
| NEBuilder / GeneArt browser tools | `REFERENCE` | vendor-specific overlap/chemistry comparison | web tools are not automatic production dependencies; vendor values remain in the Gibson module |

### Full-oligo validation rule

Candidate selection may optimize an annealing core, but every generated oligo must be re-evaluated after the application-specific 5′ sequence is attached. The exported object retains `annealing_core`, `application_tail_or_overlap`, and `full_ordered_oligo` separately so downstream thermodynamic checks and ordering cannot accidentally use different molecules.

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
fragment/vector intake + desired final construct
        -> topology/orientation/restriction-end normalization
        -> junction and overlap resolver
        -> Primer3 annealing-core search on each source fragment
        -> full-oligo composition (5′ overlap/tail + annealing core)
        -> full-oligo structure/interaction checks
        -> MFEprimer/BLAST+ when genomic/complex backgrounds apply
        -> pydna independent PCR-product simulation of amplified fragments when enabled
        -> exact final-construct reconstruction and verification
```

### Engine-owned canonical inputs

```text
construct_id  desired_construct_sequence_or_parts[]  circularity
fragment_id  fragment_sequence  fragment_orientation  source_interval
junction_id  upstream_fragment  downstream_fragment
overlap_policy  overlap_sequence  overlap_tm_model
annealing_core_policy  restriction_digest  end_chemistry
reading_frame_requirement  protected_features[]
assembly_chemistry  polymerase_profile  background_database
```

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Required captured semantics | Normalized result |
| --- | --- | --- | --- |
| `resolve_construct` | PCRStudio junction composer | ordered parts, orientation, circular/linear state, digest cut/end semantics, desired junction sequence | canonical final-construct sequence/hash and source-to-construct map |
| `design_annealing_core` | Primer3 | source fragment sequence, included/excluded region, direction, core size/Tm/GC/structure profile | annealing core only; no 5′ assembly overlap hidden inside Primer3 coordinate semantics |
| `compose_full_oligo` | PCRStudio | overlap/tail sequence and provenance + annealing core | full synthesized oligo with segment annotation |
| `validate_full_oligo` | Primer3 thermo/local evaluator | full oligo and explicit chemistry/model | full-oligo structure/interaction evidence separate from core evidence |
| `validate_background` | MFEprimer/BLAST+ | annealing cores against relevant genomic/vector/background sequences | off-target binding/products; synthetic 5′ overlap is not treated as genomic annealing sequence |
| `simulate_amplified_fragment_pcr_products` | pydna | exact amplified-fragment templates and selected primers | optional independent PCR-product evidence; full assembly/construct reconstruction is not claimed by the current adapter |
| `vendor_compare` | NEBuilder Assembly Tool | final construct/fragments/polymerase branch | manual/reference comparison only; remote output does not own production design |

NEB's assembly guidance describes overlap design as chemistry-specific and recommends using the NEBuilder Assembly Tool for its own assembly branches; such values stay module/vendor-scoped rather than becoming universal overlap rules ([NEB primer design tools](https://www.neb.com/en-us/neb-primer-design-tools/neb-primer-design-tools)).

### Normalized output

```text
JunctionPrimerResult {
  construct_id
  desired_construct_hash
  junctions[] {
    junction_id, source_fragments[], overlap_sequence,
    primers[] { annealing_core, nonannealing_5p_segment, full_oligo, source_binding_interval }
  }
  reconstructed_construct_hash
  feature_preservation_checks[]
  background_specificity
  full_oligo_interactions
  simulation_evidence
  warnings[]
  tool_runs[]
}
```

The run passes the topology gate only if the reconstructed construct is sequence-identical to the requested construct modulo explicitly authorized end-repair or feature edits.

### Engine-specific failures and controlled recovery

- `CONSTRUCT_TOPOLOGY_AMBIGUOUS`: fragment order/orientation or circularity is unresolved; refuse rather than guess.
- `JUNCTION_SEQUENCE_MISMATCH`: composed overlap does not reconstruct the desired junction exactly; reject.
- `ANNEALING_CORE_VALID_FULL_OLIGO_INVALID`: added tail/overlap creates an unacceptable full-oligo structure/interaction; redesign without discarding the reason.
- `RESTRICTION_END_MODEL_INCOMPLETE`: digest-derived ends cannot be reconstructed from enzyme/cut provenance; vendor-specific assembly assumptions are blocked.
- `FEATURE_OR_FRAME_VIOLATION`: final construct changes a protected feature/reading frame outside the authorized edit; hard reject.

### Regression fixture matrix

Fixtures cover two-fragment and multi-fragment circular assemblies; all-PCR fragments; restriction-digested vector ends; reverse-oriented input fragment; overlap split across two primers; protected reading frame; a 5′ tail that creates a severe dimer; circular-origin junction; and pydna/manual reference disagreement. Assertions include exact construct hash, segment annotations, coordinate maps and full-oligo versus core validation separation.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
