# Pair and Probe Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `pair-and-probe` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| Primer3 / `primer3-py` | primer and internal-oligo candidate search | does not prove fluorescent readout or efficiency ([Primer3 manual](https://primer3.org/manual.html)) |
| nearest-neighbour thermoanalysis | estimates primer/probe structures and interactions | model-dependent and not a kinetic assay ([primer3-py thermoanalysis](https://libnano.github.io/primer3-py/api/thermoanalysis.html)) |
| specificity/background evaluator | checks the declared target and background | not a genome-wide specificity guarantee ([NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)) |
| instrument/readout validation | evaluates channels, fluorescence curves and controls | platform and chemistry-specific ([MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/)) |
| TaqMan multiplex concentration optimizer / ISO validation registry | records primer-limited abundance balancing, probe/channel chemistry and the standard/draft validation-reference lifecycle | concentration matrices are vendor-specific and ISO drafts are revision-watch only; neither silently changes module defaults ([TaqMan multiplex guide](https://documents.thermofisher.com/TFS-Assets/LSG/manuals/taqman_optimization_man.pdf), [ISO/CD 20395.2](https://www.iso.org/standard/91706.html)) |

```text
primer_pair  probe_sequence  probe_orientation  fluorophore  quencher
internal_modification  probe_position  pair_probe_interaction
readout_channel  instrument_platform  cq_method  efficiency  lod_loq
```

## Field families and chemistry boundary

Primer, probe, reporter/quencher, channel and quantitative-result fields must remain distinct. A candidate pair plus an internal oligo is not a validated quantitative assay until efficiency, controls, calibration/quantification and platform provenance are recorded ([MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/)).

The active module contract is hydrolysis-probe qPCR. Scorpion, molecular-beacon and other fluorogenic formats require their own topology and signal fields; a fluorescent label alone does not make them interchangeable with a hydrolysis probe ([Applied Biosystems reagent guide](https://tools.thermofisher.com/content/sfs/manuals/cms_046739.pdf), [Scorpion mechanism study](https://pmc.ncbi.nlm.nih.gov/articles/PMC110766/)).

## Generation-1 production toolchain

| Tool/method | Role | Engine use | Production decision |
| --- | --- | --- | --- |
| Primer3 (shared pin) | `PRIMARY` | paired primers plus internal-oligo candidate generation | local subprocess; capture all internal-oligo parameters/output and full Primer3 provenance |
| MFEprimer (shared pin) + BLAST+ (shared pin) | `VALIDATOR` | primer/probe locus specificity and alternative product evidence | local databases; probe-hit evidence kept separate from primer-pair product evidence |
| ViennaRNA (shared pin) | `OPTIONAL` | independent structure/accessibility annotation for difficult candidates | explicit DNA parameter set; not a replacement for Primer3 internal-oligo penalties |
| Primer-BLAST / vendor probe-design tools | `REFERENCE` | independent/manual comparison | remote/vendor tools never silently determine production output |

### Probe-specific adapter fields

The normalized candidate keeps primer pair and probe as distinct oligo objects with `probe_orientation`, genomic position, distance/overlap geometry, full modification/dye/quencher identity, channel compatibility and 5′-base constraints. Primer–probe and probe–probe interactions are independent validation edges. Instrument/channel choice can veto a chemically incompatible result but cannot retroactively alter sequence-specificity evidence.


### Primer3 internal-oligo compatibility

The production adapter activates Primer3 internal-oligo selection explicitly and preserves the internal-oligo field family separately from left/right primers: pick flag, min/opt/max size, min/opt/max Tm, GC limits, self/hairpin limits, salt/divalent/dNTP/DNA concentration fields, mishybridization library fields and internal-oligo weight terms are all versioned inputs/outputs rather than generic probe defaults ([Primer3 manual](https://primer3.org/manual.html)).

The current stable Primer3 release does **not** expose the development-branch `PRIMER_INTERNAL_NO_5_PRIME_G`/reverse-complement preference behavior described for the unreleased 2.7.0 notes. Generation 1 therefore applies any 5′-G probe filter in PCRStudio's assay-specific post-filter and records it as an internal/module rule; the adapter must not send an unreleased tag to stable 2.6.1 or assume the development branch's changed probe selection ([Primer3 development release notes](https://github.com/primer3-org/primer3/blob/main/src/release_notes.txt), [released versions](https://github.com/primer3-org/primer3/releases)).

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
template/target + probe chemistry
        -> Primer3 pair + internal-oligo generation
        -> primer/probe geometry validation
        -> primer, probe and cross-oligo thermo/structure checks
        -> MFEprimer + BLAST+ target/background evidence
        -> dye/quencher/channel/platform compatibility gate
        -> deterministic triplet filtering/ranking
        -> quantitative-assay validation handoff
```

### Engine-owned canonical inputs

```text
template_id  target_interval  amplicon_profile
probe_chemistry  probe_orientation_policy  internal_target_region
probe_size_tm_gc_profile  primer_profile
probe_5p_base_policy  probe_modifications[]  reporter  quencher
instrument_platform  channel  multiplex_context
master_mix_or_chemistry_profile  background_database
quantification_or_detection_mode
```

### Primer3 internal-oligo field map

The adapter records the internal-oligo family separately from left/right-primer fields. Relevant stable `2.6.1` inputs include:

```text
PRIMER_PICK_INTERNAL_OLIGO
PRIMER_INTERNAL_MIN_SIZE  PRIMER_INTERNAL_OPT_SIZE  PRIMER_INTERNAL_MAX_SIZE
PRIMER_INTERNAL_MIN_TM  PRIMER_INTERNAL_OPT_TM  PRIMER_INTERNAL_MAX_TM
PRIMER_INTERNAL_MIN_GC  PRIMER_INTERNAL_OPT_GC_PERCENT  PRIMER_INTERNAL_MAX_GC
PRIMER_INTERNAL_MAX_SELF_ANY  PRIMER_INTERNAL_MAX_SELF_END
PRIMER_INTERNAL_MAX_SELF_ANY_TH  PRIMER_INTERNAL_MAX_SELF_END_TH
PRIMER_INTERNAL_MAX_HAIRPIN_TH
PRIMER_INTERNAL_SALT_MONOVALENT  PRIMER_INTERNAL_SALT_DIVALENT
PRIMER_INTERNAL_DNTP_CONC  PRIMER_INTERNAL_DNA_CONC
SEQUENCE_INTERNAL_EXCLUDED_REGION
```

Any 5′-G or other assay-specific probe rule absent from the stable upstream release is applied as an explicit PCRStudio post-filter, never by sending an unreleased tag.

### Tool-specific parameter and adapter map

| Operation | Tool/interface | Required captured semantics | Normalized result |
| --- | --- | --- | --- |
| `design_triplet` | Primer3 | complete left/right/internal inputs, chemistry and objective weights | candidate primer-pair + internal oligo with raw Primer3 penalties/explain fields |
| `validate_geometry` | PCRStudio | probe interval relative to amplicon/primers, orientation, overlap/distance rules | explicit hard/soft geometry checks |
| `validate_specificity` | MFEprimer/BLAST+ | primer-pair products plus independent probe-hit mapping | product specificity and probe locus evidence kept separate |
| `validate_structure` | Primer3 thermo; ViennaRNA optional | probe/full oligos and declared model/chemistry | model-labelled hairpin/dimer/accessibility features |
| `validate_optics` | PCRStudio vendor/platform registry | reporter/quencher/modifications, instrument channels and multiplex combinations | compatibility gate only; no sequence score alteration |

### Normalized output

```text
PairProbeResult {
  assay_id
  primer_pair
  probe { sequence, orientation, binding_interval, modifications[], reporter, quencher }
  amplicon_geometry
  probe_geometry
  primer_probe_interactions[]
  product_specificity
  probe_binding_specificity
  instrument_channel_compatibility
  quantitative_validation_status
  score_components
  warnings[]
  tool_runs[]
}
```

Efficiency, Cq/Ct behavior, LOD/LOQ and calibration performance are downstream empirical evidence and are never synthesized from design scores.

### Engine-specific failures and controlled recovery

- `NO_INTERNAL_OLIGO`: a primer pair exists but no probe satisfies the probe contract; the pair alone is not a successful pair-and-probe result.
- `PROBE_OUTSIDE_PRODUCT`: normalized probe binding site is not fully inside the intended amplicon; hard reject.
- `PROBE_OFFTARGET_CONFLICT`: primer pair is specific but the probe has a prohibited independent binding context; reject or mark according to module hard rule.
- `OPTICAL_CONFIGURATION_INVALID`: sequence triplet is valid but dye/quencher/channel configuration conflicts with the selected platform; do not alter sequence evidence to hide the conflict.
- `QUANTITATIVE_VALIDATION_ABSENT`: design may be exported, but no claim of validated quantitative performance is allowed.

### Regression fixture matrix

Fixtures cover probe on each strand if supported, probe at geometry boundary, 5′-G post-filter branch, primer-specific but probe-nonspecific target, multiplex dye/channel conflict, probe-primer dimer, internal-oligo no-candidate case, and stable-vs-development Primer3 tag guard. Assert separate primer/probe evidence and exact modification/channel metadata.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
