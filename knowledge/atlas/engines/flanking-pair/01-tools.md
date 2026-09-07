# Flanking Pair Engine — tool and field vocabulary

| Field | Value |
| --- | --- |
| Engine | `flanking-pair` |
| Purpose | define which tools participate and which upstream field names are owned, forwarded, rejected or delegated |
| Last reviewed | 2026-09-03 |

> **Internal vocabulary record.** This document is a vocabulary and ownership map and inherits the canonical [generation-1 runtime contract](../../contracts/runtime-contract.schema.json) and [toolchain manifest](../../contracts/toolchain-manifest.json), and [engine tool bindings](../../contracts/engine-tool-contracts.json). It does not assign PCRStudio assay defaults; versioned upstream tool-native defaults may be recorded as source semantics, while resolved assay values belong to the relevant module record or a genuinely shared engine contract.

## 1. Participating tools and methods

| Tool or method | Role in this engine | Ownership boundary |
| --- | --- | --- |
| Primer3 / `primer3-py` ([manual](https://primer3.org/manual.html)) | candidate pair placement, hard constraints, Tm and oligo structure calculations | establishes candidates under a supplied model; does not establish yield, database specificity or wet-lab success |
| Primer3 `ThermoAnalysis` ([thermodynamic fields](https://primer3.org/manual.html)) | post-search hairpin, homo/heterodimer and duplex reports | establishes a nearest-neighbour proxy; does not establish productive extension or reaction kinetics |
| bounded specificity scanner ([scope rationale](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)) | supplied-background and intended-product preflight | scans the declared scope; does not establish whole-database, taxonomic or gapped-alignment specificity |
| ViennaRNA worker ([API](https://viennarna.readthedocs.io/en/latest/api_python.html)) | optional local DNA accessibility report | estimates a configured local folding proxy; does not model buffer chemistry, chromatin, supercoiling or kinetics |
| FASTA/GenBank intake and bounded NCBI fetch | sequence parsing, identity, masking and provenance | establishes deterministic record handling; does not infer annotation or splicing correctness |
| multiplex set scorer | set-level interaction and readout-separation review | supports bounded compatibility review; does not establish complete multiplex kinetics or instrument physics |
| NEBridge Golden Gate Assembly Tool ([official tool](https://goldengate.neb.com/)) | external Type IIS assembly planning, fragment/junction ordering and assembly workflow support | external handoff only; the current engine does not call the web application or treat its output as an internal run |
| NEBridge Ligase Fidelity Viewer / GetSet / SplitSet ([DAD study](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0238592)) | external overhang-set fidelity review, high-fidelity set search and sequence breakpoint selection | external handoff only; any returned fidelity is conditional on the selected ligase, Type IIS enzyme and cycling profile and is not a universal property of the overhang string |

| QIAcuity Software Suite / VPF registry ([QIAGEN current resource page](https://www.qiagen.com/cm/products/instruments-and-automation/pcr-instruments/qiacuity-digital-pcr-system)) | versioned dPCR software, API, VPF, archive/automation and audit-trail provenance | software/version metadata affect analysis and traceability; they do not alter primer thermodynamics or prove an assay |
| Roche Digital LightCycler platform registry ([Roche system page](https://diagnostics.roche.com/us/en/products/systems/digital-lightcycler-system-sys-362.html)) | fixed-partition dPCR platform/plate/channel vocabulary | plate volume, partition count and channel count are platform/consumable properties, not primer-design defaults |
| Stilla Nio / Ruby Chip registry ([Stilla Nio](https://www.stillatechnologies.com/), [Ruby Chip](https://www.stillatechnologies.com/multiplex-pcr/digital-pcr-reagents/)) | current Crystal Digital PCR instrument/chip/channel vocabulary | droplet count, chamber pooling, multiplex/color-combination and throughput are platform-specific and require run provenance |
| QuantStudio Absolute Q platform registry ([Thermo Fisher current system page](https://www.thermofisher.com/us/en/home/life-science/pcr/real-time-pcr/real-time-pcr-instruments/quantstudio-systems/models/quantstudio-absolute-q.html)) | MAP16 chamber/channel/software provenance | official Thermo pages contain a four-analytical-channel versus five-physical-channel wording conflict; do not collapse it into a universal multiplex rule |
| Q5-XT Hot Start High-Fidelity 2X Master Mix ([NEB M2499](https://www.neb.com/en-us/products/m2499-q5-xt-hot-start-high-fidelity-2x-master-mix)) | executable named Long-range PCR chemistry overlay | current R5/R6 runtime branch; product capability, primer concentration and extension values remain M2499-specific bench authority and do not replace the engine's internal search envelope |
| KOD Long long-range registry + KOD One Standard-PCR registry ([KOD One](https://www.toyobo-global.com/products/lifescience/products/pcr_020/index.html), [KOD Long](https://www.toyobo-global.com/products/lifescience/products/pcr_022/index.html)) | KOD Long KML-101 is a runtime-selectable source-conditioned long-range branch; KOD One is runtime-selectable in Standard PCR, while its long-target demonstrations remain evidence rather than a separate long-range protocol | KOD Long target length drives only its documented 5 s/kb (<10 kb) versus 10 s/kb (>=10 kb) extension rule; KOD One and KOD Long retain separate product-specific runtime/evidence semantics |
| Platinum SuperFi II registry ([Thermo Fisher PCR enzyme comparison](https://www.thermofisher.com/ar/en/home/life-science/pcr/pcr-enzymes-master-mixes.html)) | executable named Standard-PCR and Long-range chemistry overlay where selected | runtime-selectable in its reviewed branches; vendor reach, primer concentration and optimization claims remain chemistry-specific and are not universal primer or product-size limits |
| Primer PICKR ([Nature Communications 2026](https://www.nature.com/articles/s41467-026-73648-2)) | literature-mined empirical RT-qPCR primer evidence and pair ranking handoff | citation frequency and PICKR score are study/tool evidence, not PCRStudio acceptance rules; inaccessible supplementary material remains a corpus boundary |
| PrimerAST ([Scientific Reports 2026](https://www.nature.com/articles/s41598-026-38238-8)) | ML-based primer-quality assessment precedent using multivariate sequence/structure features | model scores are conditional on a modest training set with synthetic negatives and must not become universal wet-lab success probabilities |
| NEBridge Ligase Master Mix / Type IIS family registry ([NEB M1100 protocol](https://www.neb.com/en-us/protocols/protocol-for-nebridge-ligase-master-mix-neb-m1100)) | enzyme-specific Golden Gate cycling, ligase and Type IIS routing | BbsI-HF, BsaI-HFv2, BsmBI-v2, Esp3I, PaqCI, SapI and BspQI branches retain enzyme-specific temperature, units and activator requirements |

**Internal multiplex-search boundary.** The set scorer optimizes one selected pair per target *within each already formed tube* using a deterministic greedy start plus bounded local improving swaps. If `per_tube` causes multiple tubes, target-to-tube assignment is a deterministic fewest-candidates-first chunking heuristic; the engine does **not** enumerate or globally optimize every possible tube partition. Result provenance therefore exposes this partition strategy separately from within-tube pair-set optimization and never claims a global multiplex optimum. Target-specific design constraints remain attached to each target whenever their resolved envelopes differ.

**Internal tool-boundary record.** The engine does not call `pyfamsa`, consensus, remote Primer-BLAST, MAFFT, MUSCLE, NEBridge Golden Gate or NEBridge ligase-fidelity web tools. Local BLAST+ is an executable validator. pydna/Bio.Restriction is an **OPTIONAL independent validator only for the restriction-cloning construct-simulation branch**; its availability never changes primary pair selection. External names may appear in explicit handoffs, but mere presence in the environment is not evidence that a run used them.

## 2. Primer3 global field vocabulary

The primary adapter's ordinary-pair field vocabulary is defined by Primer3's [sequence/global input documentation](https://primer3.org/manual.html):

```text
PRIMER_ANNEALING_TEMP
PRIMER_DMSO_CONC                    PRIMER_DMSO_FACTOR
PRIMER_DNA_CONC                     PRIMER_DNTP_CONC
PRIMER_EXPLAIN_FLAG                 PRIMER_FIRST_BASE_INDEX
PRIMER_FORMAMIDE_CONC               PRIMER_GC_CLAMP
PRIMER_INSIDE_PENALTY               PRIMER_LIBERAL_BASE
PRIMER_LIB_AMBIGUITY_CODES_CONSENSUS PRIMER_LOWERCASE_MASKING
PRIMER_MASK_3P_DIRECTION             PRIMER_MASK_5P_DIRECTION
PRIMER_MASK_FAILURE_RATE             PRIMER_MASK_KMERLIST_PATH
PRIMER_MASK_KMERLIST_PREFIX          PRIMER_MASK_TEMPLATE
PRIMER_MAX_BOUND                     PRIMER_MAX_END_GC
PRIMER_MAX_END_STABILITY             PRIMER_MAX_GC
PRIMER_MAX_HAIRPIN_TH                PRIMER_MAX_LIBRARY_MISPRIMING
PRIMER_MAX_NS_ACCEPTED               PRIMER_MAX_POLY_X
PRIMER_MAX_SELF_ANY                  PRIMER_MAX_SELF_ANY_TH
PRIMER_MAX_SELF_END                  PRIMER_MAX_SELF_END_TH
PRIMER_MAX_SIZE                      PRIMER_MAX_TEMPLATE_MISPRIMING
PRIMER_MAX_TEMPLATE_MISPRIMING_TH    PRIMER_MAX_TM
PRIMER_MIN_3_PRIME_OVERLAP_OF_JUNCTION
PRIMER_MIN_5_PRIME_OVERLAP_OF_JUNCTION
PRIMER_MIN_BOUND                     PRIMER_MIN_END_QUALITY
PRIMER_MIN_GC                        PRIMER_MIN_LEFT_THREE_PRIME_DISTANCE
PRIMER_MIN_QUALITY                   PRIMER_MIN_RIGHT_THREE_PRIME_DISTANCE
PRIMER_MIN_SIZE                      PRIMER_MIN_THREE_PRIME_DISTANCE
PRIMER_MIN_TM                        PRIMER_MISPRIMING_LIBRARY
PRIMER_MUST_MATCH_FIVE_PRIME         PRIMER_MUST_MATCH_THREE_PRIME
PRIMER_NUM_RETURN                    PRIMER_OPT_BOUND
PRIMER_OPT_GC_PERCENT                PRIMER_OPT_SIZE
PRIMER_OPT_TM                        PRIMER_OUTSIDE_PENALTY
PRIMER_PAIR_MAX_COMPL_ANY            PRIMER_PAIR_MAX_COMPL_ANY_TH
PRIMER_PAIR_MAX_COMPL_END            PRIMER_PAIR_MAX_COMPL_END_TH
PRIMER_PAIR_MAX_DIFF_TM              PRIMER_PAIR_MAX_LIBRARY_MISPRIMING
PRIMER_PAIR_MAX_TEMPLATE_MISPRIMING  PRIMER_PAIR_MAX_TEMPLATE_MISPRIMING_TH
PRIMER_PAIR_WT_COMPL_ANY             PRIMER_PAIR_WT_COMPL_ANY_TH
PRIMER_PAIR_WT_COMPL_END             PRIMER_PAIR_WT_COMPL_END_TH
PRIMER_PAIR_WT_DIFF_TM               PRIMER_PAIR_WT_IO_PENALTY
PRIMER_PAIR_WT_LIBRARY_MISPRIMING    PRIMER_PAIR_WT_PR_PENALTY
PRIMER_PAIR_WT_PRODUCT_SIZE_GT       PRIMER_PAIR_WT_PRODUCT_SIZE_LT
PRIMER_PAIR_WT_PRODUCT_TM_GT         PRIMER_PAIR_WT_PRODUCT_TM_LT
PRIMER_PAIR_WT_TEMPLATE_MISPRIMING   PRIMER_PAIR_WT_TEMPLATE_MISPRIMING_TH
PRIMER_PICK_ANYWAY                   PRIMER_PICK_INTERNAL_OLIGO
PRIMER_PICK_LEFT_PRIMER              PRIMER_PICK_RIGHT_PRIMER
PRIMER_PRODUCT_MAX_TM                PRIMER_PRODUCT_MIN_TM
PRIMER_PRODUCT_OPT_SIZE              PRIMER_PRODUCT_OPT_TM
PRIMER_PRODUCT_SIZE_RANGE             PRIMER_QUALITY_RANGE_MAX
PRIMER_QUALITY_RANGE_MIN             PRIMER_SALT_CORRECTIONS
PRIMER_SALT_DIVALENT                 PRIMER_SALT_MONOVALENT
PRIMER_SECONDARY_STRUCTURE_ALIGNMENT  PRIMER_SEQUENCING_ACCURACY
PRIMER_SEQUENCING_INTERVAL            PRIMER_SEQUENCING_LEAD
PRIMER_SEQUENCING_SPACING             PRIMER_TASK
PRIMER_THERMODYNAMIC_OLIGO_ALIGNMENT  PRIMER_THERMODYNAMIC_PARAMETERS_PATH
PRIMER_THERMODYNAMIC_TEMPLATE_ALIGNMENT PRIMER_TM_FORMULA
PRIMER_WT_BOUND_GT                   PRIMER_WT_BOUND_LT
PRIMER_WT_END_QUAL                   PRIMER_WT_END_STABILITY
PRIMER_WT_GC_PERCENT_GT              PRIMER_WT_GC_PERCENT_LT
PRIMER_WT_HAIRPIN_TH                 PRIMER_WT_LIBRARY_MISPRIMING
PRIMER_WT_MASK_FAILURE_RATE          PRIMER_WT_NUM_NS
PRIMER_WT_POS_PENALTY                PRIMER_WT_SELF_ANY
PRIMER_WT_SELF_ANY_TH                PRIMER_WT_SELF_END
PRIMER_WT_SELF_END_TH                PRIMER_WT_SEQ_QUAL
PRIMER_WT_SIZE_GT                    PRIMER_WT_SIZE_LT
PRIMER_WT_TEMPLATE_MISPRIMING        PRIMER_WT_TEMPLATE_MISPRIMING_TH
PRIMER_WT_TM_GT                      PRIMER_WT_TM_LT
PRIMER_INTERNAL_DMSO_CONC            PRIMER_INTERNAL_DMSO_FACTOR
PRIMER_INTERNAL_DNA_CONC             PRIMER_INTERNAL_DNTP_CONC
PRIMER_INTERNAL_FORMAMIDE_CONC       PRIMER_INTERNAL_MAX_BOUND
PRIMER_INTERNAL_MAX_GC               PRIMER_INTERNAL_MAX_HAIRPIN_TH
PRIMER_INTERNAL_MAX_LIBRARY_MISHYB   PRIMER_INTERNAL_MAX_NS_ACCEPTED
PRIMER_INTERNAL_MAX_POLY_X           PRIMER_INTERNAL_MAX_SELF_ANY
PRIMER_INTERNAL_MAX_SELF_ANY_TH      PRIMER_INTERNAL_MAX_SELF_END
PRIMER_INTERNAL_MAX_SELF_END_TH      PRIMER_INTERNAL_MAX_SIZE
PRIMER_INTERNAL_MAX_TM               PRIMER_INTERNAL_MIN_3_PRIME_OVERLAP_OF_JUNCTION
PRIMER_INTERNAL_MIN_5_PRIME_OVERLAP_OF_JUNCTION
PRIMER_INTERNAL_MIN_BOUND             PRIMER_INTERNAL_MIN_GC
PRIMER_INTERNAL_MIN_QUALITY           PRIMER_INTERNAL_MIN_SIZE
PRIMER_INTERNAL_MIN_THREE_PRIME_DISTANCE PRIMER_INTERNAL_MIN_TM
PRIMER_INTERNAL_MISHYB_LIBRARY        PRIMER_INTERNAL_MUST_MATCH_FIVE_PRIME
PRIMER_INTERNAL_MUST_MATCH_THREE_PRIME PRIMER_INTERNAL_OPT_BOUND
PRIMER_INTERNAL_OPT_GC_PERCENT        PRIMER_INTERNAL_OPT_SIZE
PRIMER_INTERNAL_OPT_TM                PRIMER_INTERNAL_SALT_DIVALENT
PRIMER_INTERNAL_SALT_MONOVALENT       PRIMER_INTERNAL_WT_BOUND_GT
PRIMER_INTERNAL_WT_BOUND_LT           PRIMER_INTERNAL_WT_END_QUAL
PRIMER_INTERNAL_WT_GC_PERCENT_GT      PRIMER_INTERNAL_WT_GC_PERCENT_LT
PRIMER_INTERNAL_WT_HAIRPIN_TH         PRIMER_INTERNAL_WT_LIBRARY_MISHYB
PRIMER_INTERNAL_WT_NUM_NS             PRIMER_INTERNAL_WT_SELF_ANY
PRIMER_INTERNAL_WT_SELF_ANY_TH        PRIMER_INTERNAL_WT_SELF_END
PRIMER_INTERNAL_WT_SELF_END_TH        PRIMER_INTERNAL_WT_SEQ_QUAL
PRIMER_INTERNAL_WT_SIZE_GT            PRIMER_INTERNAL_WT_SIZE_LT
PRIMER_INTERNAL_WT_TM_GT              PRIMER_INTERNAL_WT_TM_LT
```

The inventory above is the complete documented global input vocabulary for the current Primer3 IO specification, including internal-oligo and conditional families; aliases, deprecated task names and indexed output fields are handled separately in the sections below ([Primer3 manual](https://primer3.org/manual.html)). It lists names only: it deliberately does not assign a value or claim that the current engine supports every field.

**Internal field-activation rule.** Conditional vocabulary includes `PRIMER_MAX_END_STABILITY`, `PRIMER_PRODUCT_OPT_SIZE`, the verified Tm/pair-difference/product-size weight families, and the explicit low-level thermodynamic controls. Whether a field is active and what it means is resolved by the module record and executable adapter; this document does not assign a value.

## 3. Primer3 sequence-field vocabulary

The adapter vocabulary includes the Primer3 [sequence fields](https://primer3.org/manual.html):

```text
SEQUENCE_ID
SEQUENCE_TEMPLATE
SEQUENCE_TARGET
SEQUENCE_INCLUDED_REGION
SEQUENCE_EXCLUDED_REGION
SEQUENCE_INTERNAL_EXCLUDED_REGION
SEQUENCE_PRIMER
SEQUENCE_PRIMER_REVCOMP
SEQUENCE_INTERNAL_OLIGO
SEQUENCE_PRIMER_PAIR_OK_REGION_LIST
SEQUENCE_OVERHANG_LEFT
SEQUENCE_OVERHANG_RIGHT
SEQUENCE_OVERLAP_JUNCTION_LIST
SEQUENCE_INTERNAL_OVERLAP_JUNCTION_LIST
SEQUENCE_QUALITY
SEQUENCE_START_CODON_POSITION
SEQUENCE_START_CODON_SEQUENCE
SEQUENCE_FORCE_LEFT_START
SEQUENCE_FORCE_LEFT_END
SEQUENCE_FORCE_RIGHT_START
SEQUENCE_FORCE_RIGHT_END
```

The engine owns typed coordinates and typed tail/junction semantics. Raw upstream grammars are not accepted when they would create a second coordinate or chemistry contract. Primer3 documents internal oligos, target/included/excluded regions and overhang-related fields in its [input specification](https://primer3.org/manual.html); in this application, internal-oligo fields belong to the probe-capable engine, quality fields require a typed quality-vector contract, and sequencing and variant-specific matching fields require their own assay contract.

## 3.1 Primer3 program and output vocabulary

Primer3 also defines program-level fields `P3_FILE_ID`, `P3_FILE_TYPE`, `P3_FILE_FLAG` and `P3_COMMENT`, plus command-line controls such as `--default_version`, `--io_version`, `--strict_tags`, `--p3_settings_file`, `--echo_settings_file`, `--output` and `--error`. These control file/stream behaviour and provenance rather than primer biology ([Primer3 manual](https://primer3.org/manual.html)).

Primer-level output is indexed and follows the documented family form `PRIMER_{LEFT,RIGHT,INTERNAL,PAIR}_<j>_<tag_name>`; the engine must preserve the output family, explanation/error channels, selected sequences, coordinates, Tm/GC/quality fields, structure fields, product fields, mispriming fields and library identifiers when they are emitted, without treating an absent optional output as a successful calculation ([Primer3 manual](https://primer3.org/manual.html)). The exact output set is version- and task-dependent, so the adapter records the raw versioned output vocabulary rather than hard-coding an invented universal list.

The fixed and indexed output vocabulary documented by Primer3 includes `P3_SETTINGS_FILE_USED`, `P3_SETTINGS_FILE_END`, `PRIMER_ERROR`, `PRIMER_WARNING`, the returned-count fields, the `*_PROBLEMS` and `*_EXPLAIN` channels, indexed coordinates and sequences, `PRODUCT_SIZE`, `PENALTY`, `TM`, `BOUND`, `GC_PERCENT`, `SELF_ANY`, `SELF_ANY_TH`, `SELF_END`, `SELF_END_TH`, `HAIRPIN_TH`, the corresponding optional `*_STUCT` structure strings, pair `COMPL_ANY`/`COMPL_END` families, `END_STABILITY`, template/library mispriming families, `MIN_SEQ_QUALITY`, position penalties, product-Tm diagnostics and `PRIMER_STOP_CODON_POSITION` ([Primer3 manual](https://primer3.org/manual.html)). Optional fields are conditional on task, input tags, thermodynamic mode and whether a structure or quality calculation was available.

**Input-record multiplicity rule.** Primer3 permits interval-list tags to repeat as defined by the input grammar, but other tags are intended to occur once; repeated non-interval tags are not systematically rejected and the later value can silently overwrite the earlier one ([Primer3 manual](https://primer3.org/manual.html)). The typed application boundary does not expose raw BoulderIO duplicate-tag semantics; if a raw BoulderIO adapter is introduced, it must reject duplicate logical fields before worker execution and record the effective value rather than relying on permissive overwrite semantics.

## 3.2 Version-sensitive and non-portable capabilities

The following items are compatibility findings, not new module defaults. They prevent the adapter from silently treating a documented name as universally active across the Primer3 executable, the `primer3-py` binding and the selected task ([Primer3 manual](https://primer3.org/manual.html); [primer3-py API](https://libnano.github.io/primer3-py/api/bindings.html)).

| Capability or field | Evidence-backed finding | Engine disposition |
| --- | --- | --- |
| package version versus library version | `primer3-py` exposes a package version and wraps a bundled `libprimer3` implementation; the two identifiers are not interchangeable ([primer3-py documentation](https://libnano.github.io/primer3-py/); [primer3-py API](https://libnano.github.io/primer3-py/api/thermoanalysis.html)). | Record both identifiers in provenance and use the library version when interpreting engine behaviour; a package-only version string is insufficient for reproducibility. |
| released versus development Primer3 semantics | As reviewed on `2026-08-30`, Primer3 upstream still labels `2.6.1` (released `2022-01-26`) as the latest formal release, and the current `primer3-py` documentation states that its primer-design library is a derivative of Primer3 `2.6.1`. The upstream `main` release notes also contain an unreleased `2.7.0` draft (`2025-XX-XX`) with a corrected Owczarzy salt calculation, SantaLucia & Hicks (2004) thermodynamic parameters and other Tm/structure-affecting changes ([Primer3 releases](https://github.com/primer3-org/primer3/releases), [primer3-py quickstart](https://libnano.github.io/primer3-py/quickstart.html), [Primer3 development release notes](https://github.com/primer3-org/primer3/blob/main/src/release_notes.txt)). | Pin the exact released/bundled library and thermodynamic model in every run. Do not import or cite unreleased `2.7.0` behavior as the production contract until a tagged release is deliberately adopted and regression-tested against existing Tm, structure and selection outputs. |
| `PRIMER_MAX_SIZE` | The executable, binding and compiled library may impose different ceilings, and the ceiling is not evidence that the largest accepted oligo is biologically appropriate ([Primer3 manual](https://primer3.org/manual.html); [primer3-py API](https://libnano.github.io/primer3-py/api/bindings.html)). | Preserve the runtime-reported limit in the compatibility layer, record the exact library identity with each run, and keep module-specific size policy separate from the engine ceiling. |
| unknown input tags and `--strict_tags` | Primer3 documents a permissive parser mode and a strict-tag command-line control; an unrecognised field can therefore be ignored rather than becoming an error unless strict handling is requested ([Primer3 manual](https://primer3.org/manual.html)). | Validate the public schema before calling the binding; reject unknown or unsupported fields explicitly and never report an ignored field as applied. |
| `PRIMER_PAIR_MAX_HAIRPIN_TH` | The manual identifies the pair hairpin control as removed or ignored, while individual-primer hairpin controls remain documented ([Primer3 manual](https://primer3.org/manual.html)). | Do not expose this field as an active pair constraint; retain individual hairpin evidence where the selected tool path emits it. |
| masking controls and platform support | Primer3’s masking-library/path family is conditional, and the manual records platform-specific limitations for the masker ([Primer3 manual](https://primer3.org/manual.html)). | Treat masking as an explicit, versioned intake capability; require a declared masker and provenance instead of assuming that a field name means masking occurred. |
| thermodynamic parameter files | Thermodynamic oligo alignment requires the corresponding parameter directory; the documented default search locations differ by operating system ([Primer3 manual](https://primer3.org/manual.html)). | Resolve and record the parameter directory before a thermodynamic run; fail closed when the required files are unavailable. |
| thermodynamic alignment length | Primer3 and `primer3-py` document different limits for whole-sequence alignment, hairpin, homodimer, heterodimer and end-stability call paths ([Primer3 manual](https://primer3.org/manual.html); [primer3-py API](https://libnano.github.io/primer3-py/api/bindings.html)). These are different boundaries for different call paths. | Enforce the selected call path’s documented length limit before dimer, hairpin or end-stability analysis and route longer inputs to an explicitly bounded fallback or a manual review. |
| `PRIMER_TASK` aliases | The manual distinguishes canonical tasks from deprecated aliases, including the former detection-primer alias ([Primer3 manual](https://primer3.org/manual.html)). | Normalize aliases at input, store the canonical task in the run record, and preserve the original user input only as provenance. |
| BoulderIO versus Python representations | Primer3-py mirrors Primer3’s field names but represents some ranges and index lists as Python lists/tuples rather than BoulderIO strings ([primer3-py quickstart](https://libnano.github.io/primer3-py/quickstart.html)). | Keep a typed adapter boundary; do not serialize Python-native range structures as if they were raw BoulderIO values. |
| output errors, warnings and explanations | Primer3 separates user-correctable `PRIMER_ERROR`, non-fatal `PRIMER_WARNING`, returned-count fields and explanatory channels; the absence of a primer pair must not erase these reasons ([Primer3 manual](https://primer3.org/manual.html)). | Preserve error/warning/explanation fields in the result contract and distinguish “no pair under this contract” from an internal worker failure. |

**Compatibility rule.** A field is not considered implemented merely because it appears in this vocabulary. It is implemented only when the current adapter accepts it, the selected runtime reports it as active, the module contract assigns its meaning, and the run record preserves the effective value or an explicit rejection reason ([Primer3 manual](https://primer3.org/manual.html); [primer3-py quickstart](https://libnano.github.io/primer3-py/quickstart.html)).

## 4. Field-family ownership and disposition

| Field family | Disposition | Owning boundary |
| --- | --- | --- |
| thermal additives and bound-fraction controls | not active without a typed chemistry model | selected module and reaction contract |
| thermodynamic parameter-file paths | pinned tool capability only | runtime/toolchain configuration |
| quality and binding fields | not active without quality/binding input | sequence-intake contract |
| coordinate-base controls | not a public free field | shared engine coordinate contract |
| ambiguity and consensus controls | not a Primer3 default | sequence intake and specificity method |
| masking-library/path controls | not active without a versioned masker | sequence-intake tool contract |
| library/template mispriming fields | not the specificity implementation | bounded scanner or external handoff |
| raw must-match terminal fields | not a global default | variant/discrimination module contract |
| product-Tm and positional objective fields | not inferred globally | explicit product-ranking contract |
| hidden GC objectives | not active as an implicit global preference | module-owned evidence |
| junction-overlap controls | not raw ordinary-pair input | typed junction contract |
| sequencing objectives | delegated | sequencing engine |
| broad legacy structure switches | not active when typed thermodynamic controls exist | tool adapter |
| removed or ignored upstream fields | rejected or ignored explicitly | adapter regression |
| unverified weight channels | not active until behaviour is tested | ranking contract |
| internal-oligo controls | delegated | pair-and-probe engine |

## 5. Custom specificity field vocabulary

**Internal scanner vocabulary.** The bounded scanner records the following named controls and provenance fields:

```text
seed_length
max_mismatches
binding_cutoff
serious_off_target_fraction
watch_fraction
product_ceiling
background_ceiling
alignment_gaps
indexed_search
whole_database
evaluation_temperature
intended_product_exclusion
```

These names describe the method interface. Module records decide which controls are required, optional, or validation-only and record their resolved values. The method remains limited to the supplied sequence scope and does not become BLAST or Primer-BLAST by naming those handoffs; the distinction follows the [NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/).

## 6. Accessibility field vocabulary

The optional ViennaRNA worker exposes model/provenance fields for parameter-set identity, dangle handling, GU-pair handling, lonely-pair handling, special-loop handling, salt model, topology, local window, maximum span, temperature, requested windows and checked/unchecked status ([ViennaRNA Python/API documentation](https://viennarna.readthedocs.io/en/latest/api_python.html)). It is a local comparative proxy; a missing, timed-out, malformed or partial result must stay visible and must not improve a candidate by pretending the sequence is open. The latter is an application safety decision, not a claim that ViennaRNA models reaction accessibility in full.

## 7. Non-tool engine field vocabulary

**Internal project vocabulary.** The following are project controls rather than upstream tools:

```text
candidate_shortlist
score_components
product_gc_window
product_gc_watch_lines
three_prime_stability_scale
circular_search_head
accessibility_timeout
resource_ceilings
```

**Internal ownership rule.** Their resolved values are owned by the shared engine contract only when they are genuinely common; an assay-specific override belongs in that module's record and executable profile.

## 8. Vendor, kit and platform field vocabulary

**Internal vocabulary only.** Commercial-product identity and protocol context are represented by named fields; this document deliberately assigns no values. The selected module owns the resolved value and cites the corresponding current manual or primary source.

```text
vendor_name
product_name
catalog_number
document_title
document_revision
document_date
chemistry_family
polymerase_family
enzyme_identity
master_mix_identity
template_class
host_or_matrix
readout_format
instrument_platform
consumable_format
reaction_volume
input_volume
partition_or_chamber_format
partition_volume
partition_count
primer_concentration
probe_concentration
buffer_identity
salt_or_ion_condition
dntp_condition
temperature_program
acquisition_program
digest_or_fragmentation_plan
overhang_or_end_chemistry
ligase_identity
ligase_fidelity_dataset
overhang_set
overhang_length
overhang_orientation
fragment_order
fragment_count
fragment_molarity
part_purity
internal_type_iis_sites
assembly_protocol
fidelity_metric
efficiency_metric
mismatch_matrix
vendor_claim_scope
validation_status
```

**Internal ownership rule.** A vendor field is metadata until a module record resolves it from a named product/document. It must never become a hidden shared default, and a value from one vendor, template class, readout or instrument must not be copied to another without a cited compatibility decision ([Primer3 manual](https://primer3.org/manual.html), [National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/), [ISO 20395:2019](https://www.iso.org/standard/67893.html)).

## 9. Source policy

**Evidence policy.** Official tool manuals define field semantics. Peer-reviewed studies and consensus documents support biological claims. Vendor manuals support kit-specific starting conditions. Engineering decisions are labelled and are never presented as universal biology. Module-specific sources are cited in the module file, not copied into this vocabulary map ([Primer3 manual](https://primer3.org/manual.html), [NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)).

Shared references:

- [Primer3 manual](https://primer3.org/manual.html)
- [SantaLucia 1998](https://doi.org/10.1073/pnas.95.4.1460)
- [Owczarzy 2008](https://doi.org/10.1021/bi702363u)
- [ViennaRNA Python/API documentation](https://viennarna.readthedocs.io/en/latest/api_python.html)
- [NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)

## 10. Extended tool-evidence rules

Primer3 output is a constrained candidate search, not a biological ranking oracle. The adapter must retain the task, sequence fields, hard constraints, thermodynamic inputs, product-size ranges, pair-difference limit, number of returned candidates and explanation/status fields so that a later reviewer can distinguish “no candidate under this contract” from “no biologically valid primer exists” ([Primer3 manual](https://primer3.org/manual.html)).

The same field name must not be reused with a different meaning across modules. In particular, Tm, salt, divalent-ion, dNTP and oligo-concentration inputs belong to the selected reaction model; a library default or a value copied from a different chemistry is not a module decision ([Primer3 manual](https://primer3.org/manual.html), [SantaLucia 1998](https://doi.org/10.1073/pnas.95.4.1460), [Owczarzy 2008](https://doi.org/10.1021/bi702363u)).

ViennaRNA is retained only as a comparative local-fold proxy. Its output must include parameter-set identity, temperature, window and checked/unchecked status, and it must never be phrased as a direct model of DNA accessibility in chromatin, buffer or polymerase kinetics without a separate calibration study ([ViennaRNA Python/API documentation](https://viennarna.readthedocs.io/en/latest/api_python.html)).

**Internal adapter rule.** A tool result is invalid when the tool failed, timed out, returned a partial field set or used an unrecorded override. The adapter must surface that state; it may not convert an absent calculation into a favourable score or a clean specificity label ([Primer3 manual](https://primer3.org/manual.html)).

## 11. Design-versus-check semantics

Primer3's candidate-generation task and its existing-primer checking task are different operations. A design request may search for new left/right candidates under the resolved constraints, while a check request evaluates supplied primer sequences against the supplied template; the engine must retain which operation produced the result and must not describe a checked pair as a newly optimized pair ([Primer3 manual](https://primer3.org/manual.html)).

| Tool output | Required interpretation | Prohibited interpretation |
| --- | --- | --- |
| candidate list and penalty | ordered candidates under the submitted constraints and objective | “best biological primer” without assay validation ([Primer3 manual](https://primer3.org/manual.html)) |
| explanation/status fields | why candidates were rejected or which constraint failed | silent fallback to a different range or chemistry ([Primer3 manual](https://primer3.org/manual.html)) |
| thermodynamic report | model-dependent hairpin, homo/heterodimer or duplex estimate | proof of productive extension, yield or reaction specificity ([Primer3 manual](https://primer3.org/manual.html)) |
| supplied-primer check | preflight of an existing pair on the declared template/coordinates | evidence that the pair works in an untested sample or background ([National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)) |

**Internal vocabulary rule.** Every exported tool result should carry operation type (`design` or `check`), tool/model identity, input scope, resolved constraints, warnings and incompleteness state. This is an auditability requirement, not a new biological threshold ([Primer3 manual](https://primer3.org/manual.html)).

## 12. Generation-1 production toolchain

This engine inherits the shared role/adapter/version contract from [`../../../TOOLCHAIN-POLICY.md`](../../../TOOLCHAIN-POLICY.md#generation-1-toolchain-maturity-contract). The detailed Primer3 vocabulary above remains canonical; this section resolves execution roles and carries no defaults, ranges, thresholds, concentrations ([Primer3 manual](https://primer3.org/manual.html)).

| Tool | Role | Engine use | Required execution/provenance |
| --- | --- | --- | --- |
| Primer3 `primer3_core` `2.6.1` | `PRIMARY` | pair/internal-oligo generation and Primer3-native thermodynamic features | subprocess boundary; explicit Boulder-IO; binary hash; all emitted `PRIMER_*`/`SEQUENCE_*` parameters retained ([Primer3 manual](https://primer3.org/manual.html), [releases](https://github.com/primer3-org/primer3/releases)) |
| MFEprimer `4.5.1` | `VALIDATOR` | local specificity, amplicon, dimer/hairpin checks where supported | database/index hash, index `k`, CLI mode, output-schema version; fail closed on unknown TSV layout ([updates](https://www.mfeprimer.com/updates/)) |
| BLAST+ `2.17.0` | `VALIDATOR` | independent local search for off-target evidence and sequences not expressible through an MFEprimer index | exact task/options, masking/scoring and database snapshot ([NCBI release notes](https://www.ncbi.nlm.nih.gov/books/NBK131777/)) |
| PrimerPooler `1.89` | `OPTIONAL` | only when a request contains multiple products/pairs whose already-selected set needs an independent cross-interaction audit | explicit `--dg` ionic/temperature inputs or score mode, pool constraints, genome/amplicon overlap settings and randomization policy; never inherit tool defaults as assay defaults ([PrimerPooler](https://github.com/ssb22/PrimerPooler)) |
| ViennaRNA `2.7.2` | `OPTIONAL` | independent DNA structure/accessibility feature when explicitly enabled | explicit DNA parameter set, salt/temperature and sequence material; output stays separate from Primer3 thermodynamic penalties ([ViennaRNA parameters](https://viennarna.readthedocs.io/en/latest/eval/energy_parameters.html)) |
| pydna `5.5.16` | `OPTIONAL` | restriction-cloning only: independent tailed-PCR → restriction-digest → ligation/circular-construct simulation through the scientific-Python boundary | exact insert/vector hashes, selected enzyme identities, pydna/Biopython environment fingerprint, serialized construct candidates and ambiguity state; advisory only and never a primary pair-selection gate |
| Primer-BLAST | `REFERENCE` | manual/remote independent confirmation | remote execution must record organism/database/date and is never required for local pipeline completion ([Primer-BLAST](https://www.ncbi.nlm.nih.gov/tools/primer-blast/)) |
| NUPACK 4.x | `REFERENCE` | model comparison only | not a default production dependency under the current non-commercial/web-use license boundary ([NUPACK license](https://docs.nupack.org/)) |

### Specificity orchestration

Normal production order is `Primer3 candidate generation → local MFEprimer validation → BLAST+ expansion/fallback when the MFEprimer database/model cannot answer the declared background question`. Raw hit identity and reconstructed off-target product evidence remain distinct from a binary pass/fail. A remote Primer-BLAST result can corroborate but cannot replace frozen local-database provenance ([NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)).

### Salt/thermodynamic adapter rule

The adapter must send explicit ionic/concentration fields whenever the owning assay/profile resolves them and must record the correction/model used by Primer3. PCRStudio stores raw Na⁺/K⁺/NH₄⁺/Mg²⁺/dNTP/DMSO/oligo-concentration inputs separately from any derived equivalent-salt quantity; the named PCR-condition conversion in the shared design-intelligence layer is an optional parameter-set branch, not a replacement for Primer3's own selected salt model ([Primer3 manual](https://primer3.org/manual.html)).

## Production-grade adapter contract

This section is normative for the engine adapter. It complements the shared runtime schema rather than replacing it. A production run is valid only when the engine-specific operation, the exact tool artifact, resolved parameters, input/output schema versions, coordinate conversion and validation state are all recoverable from provenance ([Primer3 manual](https://primer3.org/manual.html)).

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

## 13. Production-parity completion contract

The preceding sections contain the most extensive upstream Primer3 vocabulary in the Atlas. To keep this file at the same **execution-contract** maturity as every other engine, the following requirements are normative and use the same shared runtime schema.

### Execution graph

```text
sequence intake / topology / assay profile
        -> normalization + masking/target-window resolution
        -> Primer3 candidate generation
        -> full candidate normalization
        -> MFEprimer local specificity
        -> BLAST+ expansion/fallback where required
        -> optional ViennaRNA / PrimerPooler independent evidence
        -> assay-specific hard filters
        -> deterministic ranking + controlled relaxation
```

### Normalized flanking-pair output

```text
FlankingPairResult {
  pair_id
  left_primer  right_primer
  source_binding_intervals[]
  expected_product { region, length, sequence_hash }
  primer3_features_and_raw_penalty
  thermodynamic_features
  local_specificity
  expanded_background_evidence
  assay_specific_checks[]
  score_components
  relaxation_history[]
  warnings[]
  tool_runs[]
}
```

### Error and refusal additions

In addition to the shared error vocabulary, `PRODUCT_RECONSTRUCTION_FAILED`, `TARGET_WINDOW_INVALID`, `TOPOLOGY_UNSUPPORTED`, `ASSAY_PROFILE_REQUIRED` and `RELAXATION_EXHAUSTED` are explicit terminal states. A product size or specificity claim is never synthesized when the product sequence cannot be reconstructed from the normalized coordinates.

### Deterministic ranking contract

All candidate pairs are retained with their raw Primer3 order/penalty. PCRStudio hard filters operate before soft ranking. Soft ranking uses named, versioned score components; ties use a stable deterministic key based on normalized coordinates/sequences rather than arrival order. Controlled relaxation records the exact constraint changed, prior/new value, source layer and candidate-set delta.

### Regression fixture matrix

Maintain fixtures for: ordinary linear target; left/right exclusion boundaries; reverse-strand target annotation; circular-origin representation when supported by the owning module; GC-extreme and repeat/low-complexity templates; no-candidate hard-failure; specificity database update; MFEprimer parser-version change; Primer3 version gate; product reconstruction; multiplex PrimerPooler optional path; and chemistry/salt profile change. Assertions cover candidate count/order, coordinates, product hash, Tm/structure fields, specificity evidence, warning state and relaxation provenance.

### Completeness gate

This `01-tools.md` is considered complete only when all production/validator tools have: exact version/artifact policy; invocation and parameter map; input/output normalization; coordinate conversion; chemistry/model identity; parser schema; error/timeout behavior; database manifest where applicable; determinism/cache policy; license/deployment boundary; fallback semantics; and regression fixtures. Module files may own assay-specific numeric values, but no runtime behavior may remain implicit merely because it is a tool default.
