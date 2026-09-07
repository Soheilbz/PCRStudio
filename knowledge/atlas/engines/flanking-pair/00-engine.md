# Flanking Pair Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `flanking-pair` |
| Scope | one target sequence in, one inward-facing primer pair out |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-09-03 |

> This document owns only rules shared by every module that uses the engine. It must not become a profile catalogue. Module-specific chemistry, ranges, cycle programmes, product windows, tails, required panels and validation decisions belong in that module's numbered record.
>
> Citation policy: every externally checkable scientific, tool-semantic or vendor-protocol claim carries an inline external reference. Statements about this repository's document boundaries or implementation status are explicitly marked as internal records and are not presented as scientific evidence.

## 1. Scope and ownership

`flanking-pair` searches for a left/right primer pair around a requested region on one target sequence. This is the ordinary pair-selection problem described by the [Primer3 manual](https://primer3.org/manual.html). Primer3 generates candidates under the resolved module contract; the application then applies the shared specificity, topology, interaction, product and provenance stages.

The engine is a reusable computational core, not a universal PCR protocol. Primer3 itself describes its constraints as user-specifiable criteria rather than as a guarantee of experimental success ([Primer3 manual](https://primer3.org/manual.html)). A module supplies the chemistry, purpose, bounds and required inputs. The result must expose the resolved module values and the limits of what sequence-only computation can establish; assay specificity and performance require an explicitly declared comparison and validation scope ([National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)).

### Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| [`00-engine.md`](00-engine.md) | shared request/output contract, topology, common pipeline, common safety and shared operational invariants | module-specific values, chemistry presets, module matrices or module evidence |
| [`01-tools.md`](01-tools.md) | participating tools, tool roles, upstream field vocabulary and field ownership/disposition | defaults, numeric settings, assay ranges or resolved values |
| [`02-standard-pcr.md`](02-standard-pcr.md) | Standard PCR values, evidence, implementation decision and validation boundary | a second copy of the shared contract |
| [`03-long-range-pcr.md`](03-long-range-pcr.md) | Long-range PCR values, processivity boundary and validation evidence | values for other modules |
| [`04-colony-pcr.md`](04-colony-pcr.md) | Colony PCR screening and crude-template contract | generic endpoint-PCR assumptions as universal rules |
| [`05-qpcr-sybr.md`](05-qpcr-sybr.md) | intercalating-dye qPCR values and measured-readout boundary | probe or instrument claims |
| [`06-digital-pcr.md`](06-digital-pcr.md) | dPCR primer-only values and partition/readout boundary | platform-independent partition defaults |
| [`07-species-specific-pcr.md`](07-species-specific-pcr.md) | inclusivity/exclusivity inputs, gates and claim boundary | universal taxonomic specificity claims |
| [`08-rpa.md`](08-rpa.md) | RPA chemistry, isothermal values and probe boundary | PCR annealing assumptions |
| [`09-restriction-cloning.md`](09-restriction-cloning.md) | cloning purpose, annealing core and typed tail decisions | generic tail defaults for every enzyme |

**Internal document-boundary rule.** The module record is the only place where a module-specific value is resolved. This engine document may link to a module, but it does not repeat that module's parameter table. This separation is an editorial/implementation decision, not a biological claim.

## 2. Authority and conflict resolution

**Internal precedence policy.** Two different conflicts must not be collapsed into one order:

1. For **scientific validity**, the primary study/consensus guideline or official tool/vendor protocol is the evidence authority; the module record then makes the scoped decision and states its limitation. Code is checked against that decision and is never allowed to overrule the source silently ([ISO 20395:2019](https://www.iso.org/standard/67893.html), [National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)).
2. For **actual runtime behaviour**, the selected profile, executable request contract, resolver/worker and emitted provenance describe what the current build really does. **Internal runtime boundary:** a mismatch with the scientific decision is an implementation defect or an explicitly documented open item, not a new scientific rule.
3. For **document ownership**, the tool vocabulary and ownership map in [`01-tools.md`](01-tools.md) and the selected module record determine where a value is maintained; duplicated prose is removed rather than used as a tie-breaker.

**Internal verification rule.** If runtime output disagrees with the cited scientific decision, both facts remain visible: the runtime behaviour is recorded as implemented, while the scientific decision remains the acceptance target until the implementation or the evidence is deliberately revised. A library default is never treated as an intentional scientific choice without an explicit module decision.

## 3. Shared input contract

**Internal contract notice.** The following sequence, coordinate and topology rules are executable contract statements, not literature-derived thresholds. They must not be misread as biological thresholds.

### 3.1 Sequence and panels

- `template` is exactly one DNA/FASTA/GenBank record.
- `background` is a declared exclusion panel when the selected module requires one; an absent panel must be reported as a narrower computational scope.
- `inclusivity` is a typed intended-target panel when the selected module asks for coverage across records.
- Designed primers are unambiguous `ACGT`; templates and backgrounds may use IUPAC ambiguity symbols.
- `U` is normalized to `T` only in a request explicitly routed as RT/cDNA; a contradictory request is refused.
- Punctuation, alignment gaps, raw digits and protein letters are refused rather than silently deleted. Degenerate primer design is not implied by accepting ambiguity in a template.

### 3.2 Coordinates and topology

- Public coordinates are translated to one zero-based internal frame exactly once.
- `target`, `included`, `excluded`, `variants` and junction boundaries are validated before search.
- Circular targets use a checked repeated search head, then fold coordinates and products back onto the real molecule. The repeated head is never reported as biological sequence.
- Exon-junction requirements are typed boundaries and are enforced after a sufficiently wide candidate search; splicing is not inferred from sequence alphabet normalization.

## 4. Shared safety invariants

**Internal runtime guarantee.** The request route and worker reject unknown request fields, non-finite numbers, booleans where integers are required, fractional counts, invalid thermal programmes, oversized targets, duplicate panel identifiers and unbounded backgrounds. These are representation and runtime guarantees, not biological acceptance thresholds.

**Internal resource policy.** The engine also has shared operational ceilings for designed-oligo length, background scan size, specificity controls and optional accessibility runtime. Their names and emitted provenance are part of the implementation contract; the selected module may tighten a design envelope but may not silently widen a resource ceiling.

## 5. Shared execution pipeline

```text
request
  → web/Rust contract and selected profile capabilities
  → sequence intake, masking and topology normalization
  → module purpose, chemistry and reaction resolution
  → Primer3 candidate generation
  → circular de-duplication and candidate diversity
  → optional DNA-accessibility diagnostic/report
  → bounded specificity scan of the declared background
  → module-specific inclusivity, variant or junction gates
  → thermodynamic, interaction and product reports
  → explanatory score, order representation, named protocol/bench handoff when available, validation plan and provenance
```

**Internal pipeline invariant.** The stage order is shared. A post-search signal must not be presented as a Primer3 hard constraint, and an optional-stage failure must remain visible instead of becoming a false clean result.

## 6. Shared thermodynamic and interaction contract

The selected module resolves the reaction model and effective temperature. The engine passes that resolved model to Primer3 and to the post-search interaction reports. Primer3 documents the relevant Tm, salt, concentration and thermodynamic-alignment fields ([Primer3 manual](https://primer3.org/manual.html)); the underlying nearest-neighbour and salt corrections are described by [SantaLucia (1998)](https://doi.org/10.1073/pnas.95.4.1460) and [Owczarzy et al. (2008)](https://doi.org/10.1021/bi702363u). It must distinguish:

- candidate Tm from an annealing-programme guarantee;
- nearest-neighbour duplex estimates from reaction kinetics;
- intended-product evidence from whole-database specificity;
- computational structure warnings from productive amplification;
- an RPA duplex proxy from recombinase loading kinetics.

**Internal provenance invariant.** Primer3, the custom specificity screen and the optional accessibility worker must record their model/method identity and effective temperature whenever a temperature-dependent result is emitted. No generic value is rebuilt in the UI or copy/order path.

## 7. Shared output contract

**Internal output contract.** Every result preserves, as applicable:

- selected module and executable capability contract;
- resolved thermodynamic screening reaction/model, plus a named protocol/cycling or isothermal bench handoff only when the selected module actually supplies one;
- candidate primers, coordinates, Tm, GC and structure reports;
- specificity method, searched scope, thresholds and evaluation context;
- topology, variant, junction and accessibility decisions;
- product composition and pair/oligo interaction reports;
- score components with their engineering/evidence status;
- typed order tails only where the module contract supports them;
- validation plan separating computable fields from run or wet-lab evidence;
- tool versions, method versions and provenance.

**Internal presentation invariant.** The UI, export and order views render these resolved result fields. They do not reconstruct a generic protocol or hide an unchecked optional stage.

### 7.1 Multiplex orchestration boundary

**Internal runtime contract.** The multiplex orchestrator is a higher-level selector around this single-target engine. It may be used only when the canonical module profile explicitly declares the `multiplex` modifier. Direct worker callers are now checked against that same capability gate, so a simplex qPCR/dPCR/RPA profile cannot be routed through the endpoint agarose/capillary/NGS multiplex model merely by bypassing the UI. Within one physical tube the orchestrator also requires the same assay, thermodynamic screening reaction, named protocol/chemistry overlay and reverse-transcription placement/authority; mixed chemistries must be split into separate tubes/requests. This is an execution/provenance invariant, not evidence that the final multiplex has been empirically balanced.

## 8. Shared claim boundary

This engine does not itself perform BLAST, indexed-genome search, gapped alignment, consensus inference, polymerase-processivity modelling, qPCR/dPCR-instrument analysis, RPA recombinase kinetics, melt-curve prediction, taxonomic-completeness proof, digest/ligation validation or universal diagnostic specificity. The [National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/) treats specificity as a comparison and validation problem, while [MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/) and [dMIQE2020](https://pubmed.ncbi.nlm.nih.gov/32746458/) define measured reporting requirements for quantitative assays; such work is therefore module-scoped validation, another engine, an explicit external handoff or wet-lab evidence.

**Claim-boundary interpretation.** An output is therefore a reproducible design and preflight report, not a claim that the assay will amplify, quantify, discriminate or perform in a specimen ([National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)).

## 9. Evidence and maintenance policy

**Internal evidence taxonomy.** Each module-owned parameter record identifies its evidence class:

- primary study or consensus guideline;
- official tool/manual semantics;
- vendor or kit protocol;
- engineering decision;
- validation-only observation;
- not applicable or unsupported because the current input model cannot express it.

**Internal status vocabulary.** `implemented-verified` means implementation, evidence and regression agree. `limited` means the computation is explicit but experimental evidence is missing. `open` means the decision is not yet justified. A change to a profile, tool, chemistry, coordinate contract, primary source or calibration set reopens only the affected module records and dependent tests.

**Internal documentation contract.** The minimum module record contains: scope, module-owned values, evidence, implementation comparison, source-to-parameter map, decision, verification record and explicit limitations. Shared prose is linked, not copied.

**Internal vendor-coverage rule.** Vendor research is maintained as a dated, module-owned registry of named product families, catalogues or manuals and their declared scope. “Complete” means that every vendor overlay accepted into the current product scope has an identified official source and an explicit limitation; it does not claim that an open-ended worldwide catalogue of suppliers, revisions or discontinued products has been exhaustively enumerated. A new product, revision, chemistry, host, instrument or readout reopens only the affected module overlay and must not inherit a value by analogy.

**Source-selection rule.** Use a primary experimental paper for an observed performance claim, a consensus guideline or international standard for reporting/validation requirements, an official tool manual for field semantics, and a vendor/kit manual for kit-specific starting conditions. A review may synthesize evidence, but it must not be used to turn a context-dependent observation into a universal hard threshold when the primary or official source says otherwise ([ISO 20395:2019](https://www.iso.org/standard/67893.html), [MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/), [Primer3 manual](https://primer3.org/manual.html)).

**Conflict-record rule.** When two credible sources disagree, preserve both citations, identify the population/chemistry/platform difference, choose a scoped default only when the evidence supports it, and otherwise mark the parameter as `open` or `validation-only`. Do not average incompatible values or hide the disagreement behind a single “recommended” number ([National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/), [ISO 20395:2019](https://www.iso.org/standard/67893.html)).

## 10. Extended cross-module evidence rules

The engine must keep four different evidence layers separate: tool semantics, sequence-level in-silico evidence, analytical assay performance and specimen-level or biological performance. Primer3 documents what its constraints and thermodynamic fields mean, whereas the National Academies BioWatch assay-development framework, hosted on NCBI Bookshelf, treats specificity and performance as comparison-and-validation questions; a candidate passing the first two layers must not be described as having passed the latter two ([Primer3 manual](https://primer3.org/manual.html), [National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)).

| Evidence layer | What the engine may state | What requires an external or laboratory record |
| --- | --- | --- |
| Tool semantics | the selected tool, field interpretation, model and resolved input values | the tool's documented semantics and versioned release notes ([Primer3 manual](https://primer3.org/manual.html)) |
| Sequence preflight | candidate geometry, computed Tm/GC/structure, supplied-panel hits and explicit topology/variant results | completeness of the background, annotation and biological target diversity ([NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)) |
| Analytical validation | observed specificity, efficiency, precision, linearity, detection/quantification limits and robustness | assay runs, controls, acceptance criteria and uncertainty records ([ISO 20395:2019](https://www.iso.org/standard/67893.html)) |
| Biological/application validation | performance in the intended matrix, population, specimen or workflow | representative samples, pre-analytical records and application-specific validation; ISO 20395 does not itself define application-specific matrix acceptance criteria ([ISO 20395:2019](https://www.iso.org/standard/67893.html)) |

**Internal provenance rule.** A result must preserve the exact sequence identity/accession and version where supplied, input topology, coordinate convention, background/inclusivity scope, chemistry profile, thermodynamic model, tool identity, effective temperature and every override that changed candidate generation or ranking. For Primer3, package version and bundled `libprimer3` engine version are separate identifiers and both must be recorded because the Python binding exposes a bundled engine rather than a separately installed executable ([Primer3 manual](https://primer3.org/manual.html), [primer3-py documentation](https://libnano.github.io/primer3-py/), [National Academies BioWatch assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)). These fields make a design auditable; they do not turn metadata into biological validation.

**External-handoff rule.** If a user asks for a whole-database, indel-aware, taxonomically complete or specimen-level claim, the engine must emit an explicit handoff and retain the narrower in-silico result instead of silently upgrading it. Primer-BLAST's database-search and alignment scope is a different evidence path from a bounded local scan ([NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)).

**Quantification boundary.** qPCR and dPCR modules inherit the same primer-search core but not the same evidence contract: qPCR requires run-level efficiency and calibration/normalization evidence, while dPCR requires partition classification, Poisson/volume assumptions and uncertainty reporting. The international quantification standard covers both technologies and is currently marked for revision, so the application must record the edition used rather than calling it the final or only authority ([ISO 20395:2019](https://www.iso.org/standard/67893.html), [MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/), [dMIQE2020](https://pubmed.ncbi.nlm.nih.gov/32746458/)).

## References for shared semantics

- [Primer3 manual](https://primer3.org/manual.html)
- [SantaLucia 1998](https://doi.org/10.1073/pnas.95.4.1460)
- [Owczarzy 2008](https://doi.org/10.1021/bi702363u)
- [von Ahsen et al.](https://doi.org/10.1093/bib/bbq081)
- [NCBI Primer-BLAST guidance](https://www.ncbi.nlm.nih.gov/guide/howto/design-pcr-primers/)
- [MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/)
- [dMIQE2020](https://pubmed.ncbi.nlm.nih.gov/32746458/)
- [ISO 20395:2019](https://www.iso.org/standard/67893.html)
