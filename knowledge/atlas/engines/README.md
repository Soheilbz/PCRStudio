# Engine atlas

This directory is the canonical documentation tree for the design engines. The eleven engine folders own shared semantics and tool vocabulary; the numbered module records own assay-specific chemistry, values, evidence and validation boundaries. This is an internal documentation rule, not a biological claim.

Software gaps are recorded in each owning module's unresolved-implementation or verification sections and in repository implementation/audit records. This documentation package does not ship a separate `IMPLEMENTATION-GAPS.md`; laboratory validation tasks remain outside the software-gap register by design.

## Deep-search evidence freeze note — 2026-08-30

A long-tail evidence pass covering current vendor software/platform generations, supplementary algorithm details, current 2025–2026 polymerase/chemistry branches, official FAQ exceptions and selected patent/adjacent topologies was incorporated after the previous freeze. The affected modules retain source-specific numeric evidence and conflict/version provenance rather than replacing historical records. See [`../audits/current-state.md`](../audits/current-state.md) for the current release status. Historical deep-enrichment reports are preserved under `../provenance/`; use the module-level sources as the canonical scientific record.

## Canonical map

| Engine folder | Modules | Scientific boundary |
| --- | --- | --- |
| `flanking-pair` | Standard PCR; Long-range PCR; Colony PCR; qPCR—SYBR; Digital PCR; Species-specific PCR; RPA; Restriction cloning | One inward-facing pair on one target; quantitative, isothermal, taxonomic and cloning claims remain module-scoped ([Primer3 manual](https://primer3.org/manual.html), [NCBI assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)) |
| `discriminating-pair` | ARMS PCR; KASP; Tetra-primer ARMS | Allele-specific competition and readout; a terminal mismatch is not a universal block across polymerases and contexts ([Kwok et al.](https://pubmed.ncbi.nlm.nih.gov/2179874/), [Newton et al.](https://pubmed.ncbi.nlm.nih.gov/2259643/)) |
| `consensus-pair` | Universal primers | Alignment-derived coverage is not population-wide universality ([Campos & Quesada](https://pubmed.ncbi.nlm.nih.gov/28540700/), [NCBI assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)) |
| `junction-primers` | Gibson assembly | Overlap-directed construction is distinct from ordinary PCR and still requires construct validation ([Gibson et al.](https://pubmed.ncbi.nlm.nih.gov/19363495/)) |
| `loop-set` | LAMP | Multi-primer isothermal role geometry and readout are distinct from paired thermal-cycling PCR ([Notomi et al.](https://doi.org/10.1093/nar/28.12.e63)) |
| `mutagenic-pair` | Site-directed mutagenesis | Primer incorporation is not proof of recovered-clone genotype or purity ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/)) |
| `nested` | Nested PCR | Inner-round specificity depends on the first-round product and transfer/contamination workflow ([Snounou et al.](https://pubmed.ncbi.nlm.nih.gov/8264734/)) |
| `outward-pair` | Inverse PCR | Outward orientation only becomes meaningful with the declared digest/circularization topology ([Ochman et al.](https://pubmed.ncbi.nlm.nih.gov/7866865/)) |
| `pair-and-probe` | qPCR—hydrolysis probe | Probe/readout and quantitative validation are separate from primer design ([MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/)) |
| `single-primer` | RACE; Sequencing primer | A single primer has a placement/read-direction contract; transcript-end or trace quality requires downstream evidence ([Pinto & Lindblad](https://pubmed.ncbi.nlm.nih.gov/19837043/), [Design strategies for sequencing primers](https://pubmed.ncbi.nlm.nih.gov/10489613/)) |
| `tiling-scheme` | Tiled scheme | Coverage is a scheme-level property and does not prove uniform amplification or sequencing quality ([NCBI assay-development framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)) |

## File ownership

| File | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | shared topology, request/output contract, common safety and claim boundary | module-specific values or vendor recipes |
| `01-tools.md` | tool names/roles, production disposition, version/deployment/parser contracts, tool-native execution parameters and field vocabulary | assay-specific scientific defaults, kit recipes or duplicated numeric evidence owned by a numbered module |
| `02-*.md`, `03-*.md`, … | one module's values, source-to-parameter map, implementation decision, verification record and limitations | copied shared prose or values belonging to another module |

## Generation-1 toolchain rule

Every `01-tools.md` uses the shared role and adapter contract in [`../knowledge/design-intelligence.md`](../knowledge/design-intelligence.md#generation-1-toolchain-maturity-contract) and inherits the normative runtime/tool identity/engine-binding contracts under [`../contracts/`](../contracts/). A tool-native CLI/API default may be documented in `01-tools.md` because it is executable software behavior; an assay-specific scientific/kit value remains in the numbered module. Tool identity/version policy is global, while executable role and operation are resolved per engine in `engine-tool-contracts.json`. Production integrations are local-first where practical, version-pinned and schema-aware. Remote/web-only tools are never silent backend dependencies, and experimental/ML tools remain benchmark/watchlist unless generation-1 maturity criteria are explicitly met.

## Cross-engine ownership

Knowledge that materially applies to more than one engine belongs under [`../knowledge/`](../knowledge/). Those files own shared concepts and claim boundaries only; assay-specific numbers, vendor recipes, versioned platform values and conflicts remain in the numbered module that owns the experimental context. This prevents the same scientific value from becoming independently editable in multiple files.

## Evidence and change rule

| Evidence type | Use |
| --- | --- |
| Primary paper or consensus guideline | observed biological behaviour, assay design or validation requirement |
| Official tool manual | field semantics and algorithm vocabulary ([Primer3 manual](https://primer3.org/manual.html)) |
| Official vendor/kit manual | named chemistry, reaction and cycling overlay; never a universal default |
| Internal implementation/test record | what this build currently enforces; never a substitute for external scientific evidence |
| `open` or `validation-only` | unresolved values, unsupported claims or requirements that need a wet-lab/platform record |

Every resolved scientific or vendor claim in a module record must carry an inline external reference. Every implementation-only statement must be marked as internal, and every unresolved field must say what evidence is still needed. The cited source supports the scoped claim only; it does not turn a passing in-silico result into analytical or specimen-level validation ([ISO 20395:2019](https://www.iso.org/standard/67893.html), [MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/)).

## Software-completeness gate

The acceptance target for PCRStudio is the strongest defensible theoretical and computational result. A module is software-complete when its inputs, sequence transformations, topology and geometry rules, constraints, scoring and refusal paths, provenance, UI/API wiring and result schema agree with one another and are covered by regression tests. Laboratory validation, instrument exports and measured assay performance are separate downstream activities; they must not be used as a reason to leave a software rule unspecified.

When a field is not computable from the declared input, the module must still choose an explicit behavior: require the field, expose it as a user-supplied override, return a typed unresolved state, or state that the claim is outside the engine. “Needs wet-lab validation” is a claim boundary, not by itself a software gap. “The UI drops this field”, “the worker ignores this constraint”, “the output schema loses this result”, and “the algorithm does not implement the documented rule” are software gaps and belong in the module's unresolved implementation list.

**Numeric and categorical extraction rule (internal).** A source-derived value must not be discarded merely because it is vendor-specific, product-specific, platform-specific, contradictory, or not suitable as a shared default. The owning module record must preserve the value exactly with its unit, parameter name, source, document/product revision, assay context, role (`hard gate`, `starting value`, `observed range`, `advisory`, or `validation-only`) and any known alternatives or conflicts. This includes lengths, product-size ranges, temperatures, times, cycle counts, concentrations, enzyme units, template amounts, volumes, copy numbers, thresholds, replicate counts, efficiency and fit criteria, as well as non-numeric settings such as host, readout, buffer, instrument, probe format and topology. The module may decide not to apply a value automatically, but it must retain the value and explain why it is not a shared default. A value that becomes executable belongs in the module record; `01-tools.md` may name the field and its vocabulary but must not become the value catalogue.

**Minimum numeric-record schema (internal).** Every extracted numeric value is recorded with at least: `parameter_id`, exact `value` or range, `unit`, `condition/context`, `scope` (method, kit, product, platform or generic literature), `role`, `source`, source document/product revision or access date, and `implementation_status`. Ratios, formulas, conversions, increments, replicate counts, positive/negative thresholds and examples are separate records even when they occur in the same paragraph. A value such as `0.6 °C` per cycle is not collapsed into a touchdown label; `50–100 ng` is not collapsed into a midpoint; and a formula such as `pmol = (ng × 1000)/(bp × 650 Da)` is retained alongside its worked examples. If a source prints an apparent unit or value ambiguity, the printed form and the ambiguity are both retained with an explicit review state. This schema is an evidence ledger, not permission to turn every extracted value into an automatic software default.

**Direct-reference invariant (internal).** Every atomic numeric-record row must contain its own external source link in the row, even when it also belongs to an aggregate record or inherits the same scope from a parent entry. A parent paragraph or a nearby source list is not a substitute for the row-level reference; internal implementation rows must identify themselves as internal instead of fabricating an external citation.

**Conflict-preservation rule (internal).** When sources publish different values, all materially relevant values remain in the module's evidence and vendor-overlay sections. The record must identify the condition that separates them and state which value, if any, is selected for the current profile; it must not average, silently overwrite, or remove the alternatives. If the context is insufficient to choose, the parameter remains `open` or `validation-only` while the extracted values stay available for a later decision.

**Module-completion gate (internal).** A module is not marked research-complete because its register has grown or because one vendor protocol was found. Before the module can move to implementation review, its owning record must show that the search covered: (a) the shared engine contract and every module-specific input/output field, (b) primary literature and current consensus or standards, (c) relevant official tool, kit, enzyme, reagent and instrument documentation, (d) every numeric value, formula, unit, ratio, threshold, cycle, volume, temperature, time and example that materially affects a decision, (e) named chemistry/platform branches and source conflicts, (f) negative controls, failure modes, specificity/inclusivity boundaries and validation handoffs, and (g) an explicit unresolved list explaining what experiment or external record is still required. This is an editorial readiness gate; it does not claim that an in-silico document has replaced wet-lab validation.

**Supervision and handoff rule (internal).** Parallel research agents may edit only their assigned module record. The supervising pass must review their source links, scope labels, duplicate parameter identifiers, conflict handling, and boundary between module values and shared/tool vocabulary before accepting the work. A report from an agent is progress evidence, not proof of completion; the final state is established only by the repository-wide structural audit and the module-by-module evidence review.

The current tree contains eleven engine folders and twenty-one numbered module records. Cross-engine concepts are routed through [`../knowledge/`](../knowledge/) without duplicating assay-specific values. Historical research/review snapshots are deliberately absent from the current tree and remain recoverable from Git history or prior signed bundles. Once a value becomes executable or scientifically resolved, its canonical decision belongs in the owning engine/module record.
