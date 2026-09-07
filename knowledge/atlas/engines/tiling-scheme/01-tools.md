# Tiling Scheme Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `tiling-scheme` |
| Purpose | production-grade tool, adapter, parameter, provenance and failure contract |
| Contract maturity | `generation-1 / production-contract-complete` |
| Last reviewed | 2026-08-30 |

**Internal vocabulary record.** This file defines engine-specific tool/interface semantics and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values remain in the owning module.

| Tool or method | Role | Boundary |
| --- | --- | --- |
| reference/variant intake | defines target sequence, versions and risk positions | database completeness is external ([Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)) |
| tiled-window generator | creates ordered overlapping amplicon regions | nominal tiling does not prove depth ([ARTIC specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)) |
| multiplex interaction scorer | reviews primer dimers and pool compatibility | cannot fully predict low-input amplification bias ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)) |
| sequencing/coverage analysis | evaluates read mapping, depth and consensus | requires run data and platform-specific provenance ([Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)) |
| PrimalScheme3 (`v3.3.0`) | builds tiled overlapping primer schemes from one or more MSAs with pool assignment, diversity filtering, dimer checking, circular/backtracking and repair options | CLI/web defaults are versioned tool semantics and must not be copied into the PCRStudio internal profile without an explicit decision ([PrimalScheme](https://primalscheme.com/), [PrimalScheme3 GitHub](https://github.com/artic-network/primalscheme3)) |

| varVAMP tiled mode | builds a weighted amplicon graph and selects coverage paths using Dijkstra search, then assigns non-adjacent amplicons to pools and performs bounded heterodimer repair | algorithm semantics are varVAMP-specific; graph/penalty behavior must not be implied by a generic tiled-window generator ([varVAMP](https://www.nature.com/articles/s41467-025-60175-9)) |
| PrimalScheme3 lifecycle commands (`repair-mode`, `scheme-replace`, `interactions`, `visualise-primer-mismatches`, `panel-create`) | maintains, repairs and audits a scheme after initial design | scheme maintenance is a separate lifecycle state from initial `scheme-create`; mutation repair and primer replacement must preserve original scheme/config provenance ([PrimalScheme3 GitHub](https://github.com/artic-network/primalscheme3)) |
| Tiled ClickSeq adjacent topology | single-template-specific-primer tiled RT/sequencing architecture using stochastic azido termination and click-ligated downstream adaptor | not a pair-based tiled-PCR topology; retain as an adjacent/unsupported architecture rather than forcing it into `left_primer/right_primer` fields ([WO2021257963A1](https://patents.google.com/patent/WO2021257963A1/en), [US12359266B2](https://patents.google.com/patent/US12359266B2/en)) |

```text
amplicon_id  amplicon_order  primer_pool  left_primer  right_primer
overlap_interval  uncovered_interval  variant_risk  scheme_version
read_platform  depth_metric  consensus_status
```

## Field families and scheme provenance

The scheme record must preserve ordered amplicons, pool membership, overlap and target coordinates together. A flat primer list cannot represent the downstream scheme contract or distinguish nominal interval coverage from run depth ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf)).

Variant risk, read platform, depth metric and consensus status belong to the sequencing validation handoff. They cannot be inferred from the nominal tiling geometry because primer dropout and pool-specific amplification bias remain possible ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/), [Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)).

## Generation-1 production toolchain

| Tool | Role | Engine use | Required execution/provenance |
| --- | --- | --- | --- |
| MAFFT (shared pin) | `PRIMARY` | MSA for variant-aware scheme generation | local CLI; exact strategy/options/input hash; production minimum `>=7.487` ([MAFFT](https://mafft.cbrc.jp/alignment/software/)) |
| PrimalScheme3 (shared pin) | `PRIMARY` | scheme creation plus repair/replacement lifecycle | external-process boundary; GPL-3.0-only; Python `>=3.11,<3.14`; capture command/config/MSA/BED and software hash ([PyPI](https://pypi.org/project/primalscheme3/), [CLI](https://github.com/artic-network/primalscheme3)) |
| PrimerPooler (shared exact pin `1.89`) | `VALIDATOR` | independent cross-primer interaction, genomic-overlap and pool reassignment check | capture score-vs-ΔG mode, temperature/ionic inputs, pool size, genome and randomization policy ([PrimerPooler](https://github.com/ssb22/PrimerPooler)) |
| MFEprimer (shared pin) + BLAST+ (shared pin) | `VALIDATOR` | independent specificity/background checks | frozen database/index/version/schema provenance |
| varVAMP / Olivar / primerJinn / ThermoPlex | `BENCHMARK` | compare scheme-design and set-level decisions | tool/study-specific settings remain benchmark metadata |
| PRISM / DIMPLE and other emerging optimizers | `WATCHLIST` | future global-optimization comparison | no generation-1 production dependency unless maturity/deployment/benchmark criteria are later met |

### PrimalScheme3 executable parameter map

For `scheme-create`, PCRStudio records at least `--amplicon-size` (tool default `400`, accepted `100–2000`, with ±10% size interpretation), `--min-overlap` (default `10`), `--n-pools` (default `2`), `--dimer-score` (default `-26.0`), `--min-base-freq` (default `0.0`), `--mapping` (`first|consensus`, default `first`) and circularity. These are **PrimalScheme3 native defaults** until an owning PCRStudio scheme profile explicitly adopts or overrides them ([PrimalScheme3 CLI](https://github.com/artic-network/primalscheme3)).

The lifecycle contract also captures `repair-mode`, `scheme-replace`, `interactions` threshold and mismatch visualization. Scheme maintenance therefore operates on a versioned `scheme_id + MSA/database snapshot` rather than treating the initial BED file as timeless.

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
reference/variant panel
        -> MAFFT MSA
        -> PrimalScheme3 scheme-create/panel-create
        -> normalized BED/scheme representation
        -> independent PrimerPooler interaction/pool audit
        -> MFEprimer + BLAST+ specificity/background audit
        -> coverage/variant-risk analysis
        -> deterministic repair/replacement lifecycle
        -> versioned scheme release
```

### Engine-owned canonical inputs

```text
scheme_id  reference_id  msa_records[]  variant_snapshot
region_bed  existing_scheme_bed  scheme_mode
amplicon_size_policy  overlap_policy  pool_count
interaction_threshold_policy  base_frequency_policy  mapping_policy
circularity  high_gc_branch  specificity_database
repair_policy  replacement_constraints  protected_primers[]
sequencing_platform  coverage_validation_handoff
```

### PrimalScheme3 executable parameter map

The pinned CLI exposes separate lifecycle commands and those commands are never conflated in provenance. For `scheme-create`, capture at least:

```text
--msa
--output
--amplicon-size
--bedfile
--min-overlap
--n-pools
--dimer-score
--min-base-freq
--mapping first|consensus
--circular / --no-circular
--high-gc / --no-high-gc
--use-matchdb / --no-use-matchdb   # where exposed by the selected command
```

The current CLI documents a native default `--amplicon-size 400`, allowed range `100..2000` with ±10% size interpretation, `--min-overlap 10`, `--n-pools 2`, `--dimer-score -26.0`, `--min-base-freq 0.0` and mapping default `first`; all remain **tool-native defaults** until a PCRStudio module/profile explicitly adopts them ([PrimalScheme3 CLI](https://github.com/artic-network/primalscheme3)).

Lifecycle provenance distinguishes `scheme-create`, `panel-create`, `repair-mode`, `scheme-replace`, `interactions` and visualization/audit commands.

### PrimerPooler independent validation map

When PrimerPooler is invoked, record `--dg` parameters (temperature, Mg, monovalent cation and dNTP) or score mode, `--pools`, `--max-count`, `--genome`, `--amp-max`, and randomization/seed policy. Upstream documents the thermodynamic-mode units and pooling controls; PCRStudio must not inherit those defaults as assay chemistry ([PrimerPooler](https://github.com/ssb22/PrimerPooler)).

### Normalized output

```text
TilingSchemeResult {
  scheme_id  scheme_version
  reference_and_msa_hashes
  amplicons[] {
    amplicon_id, order, pool,
    left_primer, right_primer,
    product_region, overlap_regions[], variant_risk
  }
  uncovered_regions[]
  interaction_edges[]
  independent_pooler_result
  specificity_evidence
  repair_history[]
  coverage_validation_handoff
  warnings[]
  tool_runs[]
}
```

The BED file is an interchange artifact, not the complete scheme state. The normalized record retains coordinate-system declaration, source MSA/reference identity, primer sequences, pools and lifecycle history.

### Engine-specific failures and controlled recovery

- `MSA_REFERENCE_MAPPING_FAILED`: scheme coordinates cannot map consistently between MSA and reference; block generation/repair.
- `UNCOVERED_REQUIRED_REGION`: no allowed amplicon covers a required target interval; report the gap explicitly.
- `POOL_INTERACTION_CONFLICT`: a hard interaction/pool constraint cannot be solved without violating protected assignments; no silent reassignment.
- `REPAIR_PROVENANCE_MISSING`: an existing scheme lacks the config/reference/MSA needed for deterministic repair; refuse mutation of the scheme.
- `SCHEME_VERSION_DRIFT`: a tool/database update changes primer coordinates, pool assignment or candidate ordering; regression gate requires explicit review before promotion.

### Regression fixture matrix

Fixtures cover a short linear genome, circular genome, high-GC region, variant at a primer 3′ end, two- and multi-pool schemes, interaction evidence on an already assigned pool, protected existing BED primer, scheme replacement, repair against a changed MSA, an uncovered interval and a PrimalScheme3/PrimerPooler disagreement. Assert BED round-trip, PRIMARY pool assignment, validator interaction evidence, coverage and repair history; PrimerPooler audit must not silently replace the selected pool assignment.

## Completeness gate

This engine tool contract is complete only when every production/validator path has an explicit operation, input/output normalization, tool/artifact identity, parameter map, coordinate conversion, chemistry/model identity, database provenance where applicable, parser/error behavior, determinism/cache rule, fallback/refusal behavior, license/deployment boundary and regression fixture. Assay-specific numeric values remain owned by the module; the tool file owns the executable semantics.
