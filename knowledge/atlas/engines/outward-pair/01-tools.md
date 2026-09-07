# Outward Pair Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `outward-pair` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| circular-template/topology validator | verifies the substrate model and cut location | a FASTA string alone does not prove circular DNA ([Green & Sambrook](https://pubmed.ncbi.nlm.nih.gov/30710023/)) |
| outward primer search | places primers in the required orientation | does not establish digest or ligation success ([Huang](https://pubmed.ncbi.nlm.nih.gov/7866865/)) |
| restriction-site evaluator | checks declared sites and product junctions | enzyme activity is protocol- and substrate-dependent ([NEB recognition sequences](https://www.neb.com/en-us/tools-and-resources/selection-charts/alphabetized-list-of-recognition-specificities)) |
| Primer3 / `primer3-py` | calculates oligo candidates and structures | does not model circularization ([Primer3 manual](https://primer3.org/manual.html)) |
| Sanger flank-confirmation handoff | confirms the unknown sequence adjacent to the known insertion/transposon after topology-aware inverse PCR | sequencing confirms recovered flank identity; it does not retroactively prove digestion or self-ligation efficiency ([Figueroa-Bossi et al., 2024](https://pubmed.ncbi.nlm.nih.gov/37188521/)) |

```text
template_topology  cut_position  enzyme_identity  circularization_method
left_outward  right_outward  product_span  junction_sequence
digest_status  ligation_status  validation_status
```

## Field families and topology boundary

Template topology, cut map, circularization method, primer orientation and unknown interval are separate inputs. A FASTA string does not establish that a substrate is circular or that a restriction/circularization workflow produced the declared junction ([Green & Sambrook](https://pubmed.ncbi.nlm.nih.gov/30710023/)).

Digest, ligation and product validation are workflow-result fields rather than Primer3 outputs. The module resolves the enzyme and topology-specific values; the tool vocabulary deliberately supplies no universal enzyme or protocol choice ([Ochman et al.](https://pubmed.ncbi.nlm.nih.gov/7866865/), [NEB recognition sequences](https://www.neb.com/en-us/tools-and-resources/selection-charts/alphabetized-list-of-recognition-specificities)).

## Generation-1 production toolchain

| Tool/method | Role | Engine use | Production decision |
| --- | --- | --- | --- |
| Primer3 (shared pin) | `PRIMARY` | outward-facing annealing-core search after the template has been transformed into the declared circular/digest representation | local subprocess; transformed-template coordinates are mapped back to source coordinates |
| PCRStudio topology/digest resolver | `PRIMARY` | restriction cut map, fragment selection, circularization/junction construction and outward orientation | deterministic sequence transformation; topology is an input contract, not inferred from primer direction alone |
| MFEprimer/BLAST+ | `VALIDATOR` | specificity against original/background sequence where applicable | exact databases/settings captured |
| pydna (shared pin) | `OPTIONAL` | current PCRStudio adapter: independent PCR-product simulation only when the complete supplied circular template is known | validator only; topology rule remains PCRStudio-owned ([pydna](https://pypi.org/project/pydna/5.5.16/)) |

### Coordinate contract

Every result retains both `source_coordinate` and `transformed_template_coordinate`, plus strand/orientation and circular-wrap metadata. Any restriction-site or ligation transformation is hashed so an outward primer cannot be reproduced against a different implicit circular product.

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
circular/source molecule + inverse-PCR goal
        -> topology declaration
        -> optional restriction digest / fragment selection
        -> linearized or circular search representation
        -> outward-facing target-window construction
        -> Primer3 annealing-core search
        -> source-coordinate and junction round-trip
        -> expected inverse product reconstruction
        -> MFEprimer/BLAST+ specificity
        -> optional pydna PCR-product simulation for a complete supplied circular template
```

### Engine-owned canonical inputs

```text
source_molecule_id  source_sequence  source_length  circularity
target_or_unknown_flank_interval  outward_goal
digest_enzyme  cut_sites[]  selected_fragment  end_chemistry
linearization_origin  synthetic_junction  search_representation_hash
left_outward_window  right_outward_window
assay_profile_id  chemistry_profile_id  background_database
```

Topology is never inferred from primer orientation alone. A circular target and a restriction-ligated inverse-PCR template are different states with different reconstructability and provenance.

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Required captured semantics | Normalized result |
| --- | --- | --- | --- |
| `resolve_topology` | PCRStudio | circularity, digest sites, fragment selection, end chemistry, ligation/junction assumptions | deterministic transformed-template representation + map to source |
| `design_outward_pair` | Primer3 | transformed template, included/target regions and explicit left/right search policy | outward-facing annealing cores with transformed/source coordinates |
| `reconstruct_product` | PCRStudio | primer extension directions across transformed topology | expected product segments ordered in product sequence |
| `validate_specificity` | MFEprimer/BLAST+ | source/background sequences and relevant primer combinations | locus/off-target evidence |
| `simulate_supplied_circular_template_pcr_product` | pydna | complete supplied circular template and selected primers | optional independent PCR-product evidence; digest/ligation/topology reconstruction is not claimed |

### Normalized output

```text
OutwardPairResult {
  topology_record
  transformed_template_hash
  primers[] { sequence, binding_interval_on_source, binding_interval_on_transformed, extension_direction }
  product_segments_on_source[]
  expected_product_hash
  junction_crossing_state
  specificity
  topology_simulation
  warnings[]
  tool_runs[]
}
```

Origin-spanning intervals remain segmented coordinate regions; no internal record uses a negative length or `end < start` to encode wraparound.

### Engine-specific failures and controlled recovery

- `TOPOLOGY_REQUIRED`: circularity/digest/ligation state needed for the requested inverse-PCR branch is absent; refuse.
- `DIGEST_FRAGMENT_AMBIGUOUS`: multiple fragments satisfy an underspecified selection; do not guess.
- `OUTWARD_ORIENTATION_INVALID`: chosen primers face inward in the declared topology; hard reject.
- `JUNCTION_ROUNDTRIP_FAILED`: transformed-template binding cannot map exactly to the original molecule/ligation junction; hard reject.
- `EXPECTED_PRODUCT_UNRECONSTRUCTABLE`: primer extension paths do not produce a unique product under the topology model; no product-size claim is emitted.

### Regression fixture matrix

Fixtures cover a simple circular plasmid, origin-spanning target, single-enzyme digest, multiple digest fragments, ligated inverse-PCR template, inward-facing negative control, restriction site inside a primer candidate, duplicated sequence causing ambiguous product and pydna topology comparison. Assert segmented coordinates, source/transformed mapping and exact product reconstruction.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
