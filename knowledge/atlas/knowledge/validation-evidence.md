# Cross-engine validation and evidence

This document owns validation, metrology, uncertainty, failure-evidence and reproducibility concepts shared across PCRStudio assay families. It does **not** replace assay-specific Numeric Evidence registers and it does not manufacture universal acceptance thresholds from unrelated standards, vendors or studies.

- **Evidence cut-off:** 2026-08-30
- **Normative state:** ISO 20395:2019 remains the published standard; ISO/CD 20395.2 Edition 2 is under development at Committee Draft stage 30.20 and is watchlist/non-normative evidence as of the cut-off.
- **Reporting state:** MIQE 2.0 (2025) is the current major qPCR reporting revision; dMIQE 2020 remains the principal published digital-PCR reporting update used in this atlas.

## Claim levels and validation maturity

PCRStudio separates evidence into levels that cannot be silently collapsed:

1. **Sequence/design evidence** — computable sequence/topology/algorithmic properties.
2. **Reaction evidence** — amplification or failure with declared reagents and conditions.
3. **Analytical-method evidence** — specificity/sensitivity, LoB/LoD/LoQ, precision, trueness, linearity/measuring interval and robustness under a validation plan.
4. **Platform evidence** — instrument/software/partition/optical behavior and analysis settings.
5. **Matrix/application evidence** — intended specimen, extraction/process and use-case performance.
6. **Transfer/reproducibility evidence** — performance across runs, operators, lots, instruments or laboratories as appropriate.

Passing a lower level never proves the higher one. In particular, a sequence-only prediction cannot establish analytical LoD, matrix robustness or clinical/specimen validity.

## Pass 5 — validation and metrology framework

### ISO 20395

ISO 20395:2019 covers requirements for evaluating nucleic-acid quantification methods including qPCR and dPCR. The current ISO page for Edition 2 (`ISO/CD 20395.2`) lists validation topics including precision, linearity, LoQ, LoD, trueness and robustness, plus metrological traceability and measurement uncertainty, while explicitly excluding application-specific sampling/sample-processing requirements and specific matrix acceptance criteria. Its lifecycle is unusually important for a current atlas: the CD consultation closed in April 2026, the draft was referred back to the Working Group on **2026-08-06**, re-registered as a Committee Draft the same day, and a new CD consultation was initiated on **2026-08-07**. As of 2026-08-30 the revision is therefore **under development, stage 30.20**, not a published normative replacement ([ISO 20395:2019](https://www.iso.org/standard/67893.html), [ISO/CD 20395.2](https://www.iso.org/standard/91706.html)).

This standard boundary is important: analytical validation and specimen-processing validation are related but not interchangeable.

### MIQE 2.0 for qPCR

MIQE 2.0 was published in Clinical Chemistry in 2025. It strengthens expectations around transparent sample handling, assay design, controls, raw-data/analysis reporting, efficiency, normalization, detection limits and reproducibility. PCRStudio uses MIQE as a **reporting/quality framework**, not as a source for universal Cq cutoffs or one fixed acceptance criterion across assays ([MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/)).

For qPCR, preserve at least the analysis method used to derive Cq/quantification, baseline/threshold handling, efficiency estimation method, calibration/reference material identity where applicable, replicate structure and excluded-data rationale. A reported Cq without analysis provenance is not fully reproducible.

### dMIQE 2020 for dPCR

dMIQE 2020 emphasizes reporting the partitioning method, measured/analyzed partition number, partition volume, software/thresholding/classification, rain handling, assay validation and statistical method. It also notes that nominal manufacturer partition volumes can have uncertainty and that partition-volume variation can bias concentration estimates. PCRStudio therefore treats `partition_volume`, its source/uncertainty, accepted partitions, classification method and software version as first-class platform evidence ([dMIQE 2020](https://academic.oup.com/clinchem/article/66/8/1012/5880117)).

### Validation vocabulary

Where applicable, validation records may include:

| Term | Atlas treatment |
| --- | --- |
| Limit of blank (LoB) | Method- and decision-rule-specific; retain estimation method and confidence framework |
| Limit of detection (LoD) | Retain definition, replicate design, detection criterion, target material and matrix |
| Limit of quantification (LoQ) | Retain precision/bias criterion and calculation method; do not assume LoQ = LoD |
| Precision | Separate repeatability/intermediate precision/reproducibility where the source does |
| Trueness/bias | Requires appropriate reference/control material and declared assigned value/traceability |
| Linearity/measuring interval | Retain concentration range, model and residual/acceptance method |
| Robustness | Retain deliberately varied factors and predefined outcome criteria |
| Analytical specificity | Retain inclusivity/exclusivity/near-neighbour or variant panels and empirical/computational distinction |
| Measurement uncertainty | Retain model, variance components and confidence/coverage convention |
| Metrological traceability | Retain calibrator/reference-material chain when applicable |
| Commutability | Only claim when the reference/control material is shown suitable for the intended measurement context |

No number in this table is a universal acceptance threshold.

## Standardized validation workflows and uncertainty methods

PCR-ValiPal (Analytica Chimica Acta, 2026) is a current workflow/tool precedent that standardizes dPCR validation calculations including LoB, LoD, LoQ, precision, trueness and linearity and demonstrates cross-platform use. It is **not itself an international standard**; its value to PCRStudio is as a reproducible validation-workflow implementation mapped to established validation concepts ([PCR-ValiPal](https://pubmed.ncbi.nlm.nih.gov/41730601/)).

A 2025 iScience study proposed `NonPVar` and `BinomVar` for flexible dPCR uncertainty estimation and showed through simulation/empirical analysis that methods relying on simple binomial assumptions can misestimate standard errors when additional variability is present. PCRStudio should therefore record the uncertainty model rather than assuming one variance formula is universally adequate ([iScience 2025](https://www.sciencedirect.com/science/article/pii/S2589004225000318)).

The assay-specific implementation consequences of these findings are recorded in [`../engines/flanking-pair/06-digital-pcr.md`](../engines/flanking-pair/06-digital-pcr.md).

## Matrix and preanalytical validation boundary

Environmental, clinical, food, wastewater and other complex specimens can introduce extraction losses and inhibitors that are not represented by clean analytical standards. EMMI explicitly emphasizes inhibition and matrix-aware quality reporting for environmental qPCR/dPCR. Therefore:

- analytical validation on purified material does not automatically validate extraction/recovery;
- matrix-matched or process controls may be needed for the intended application;
- inhibition must be measured or otherwise justified, not inferred from a good primer sequence;
- sample processing, preservation and extraction provenance must accompany application-level claims.

Source: [EMMI guidelines](https://pubs.acs.org/doi/10.1021/acs.est.1c01767).

## Inclusivity, exclusivity and evolutionary coverage

Analytical specificity may require both computational and empirical evidence. Sequence searches identify predicted cross-reactivity/mismatch risks; empirical panels measure actual amplification under the named chemistry and matrix. The species-specific module owns FDA-style FP/FN and inclusivity/exclusivity evidence; population/pangenome and drift concepts are shared in [`design-intelligence.md`](design-intelligence.md).

For evolving targets, a validated assay can become less inclusive after deployment. The 2026 SARS-CoV-2 drift study provides an example in which primer/probe target mutations differed by geography, variant and time; surveillance recommendations from that study remain study-specific rather than universal validation law ([J Med Virol 2026](https://pubmed.ncbi.nlm.nih.gov/42312714/)).

## Reference-material context and commutability

Reference material is not automatically commutable merely because it contains the same amplicon sequence. A 2026 Scientific Reports study showed that qPCR quantitation could change when sample and standard-curve material differed in the **neighbouring GC-rich sequence context** surrounding the target; physical separation/fragmentation altered recovery in the tested system. PCRStudio therefore treats `reference_material_context` as part of quantitative validation: record material type, topology/fragmentation or restriction state, relevant flanking context when known, extraction/processing, and the evidence that calibration material behaves comparably to the intended sample. This is a context/commutability issue, not a sequence-only primer-design rule ([Scientific Reports 2026](https://www.nature.com/articles/s41598-026-55452-6)).

## Transcript and exon-junction specificity is a separate validation branch

A 2026 Scientific Reports ddPCR study focused specifically on exon–exon junctions and rare splice-variant transcripts using hydrolysis-probe and EvaGreen assays. Its core lesson is that highly similar junctions and rare transcript abundance create specificity/validation problems that are not equivalent to genomic-template specificity. For transcript/junction assays, retain transcript/isoform accession and version, exact junction coordinates, closely related exon-junction backgrounds, reverse-transcription strategy, no-RT controls where genomic carryover is plausible, and empirical discrimination in the intended biological material. This paper is an assay-development precedent, not a universal numerical threshold ([Scientific Reports 2026](https://www.nature.com/articles/s41598-026-67542-6)).

## Failure and negative-evidence registry

Negative evidence is first-class evidence. A useful failure record should state:

- design/oligo/reagent/platform identity and version;
- target/background or specimen matrix;
- expected behavior;
- observed failure mode;
- raw or summary metric supporting failure;
- whether the failure was sequence-predictable, chemistry-dependent, platform-dependent, matrix-dependent or unresolved;
- corrective action attempted;
- outcome after correction;
- source/date and evidence class.

Recommended controlled failure vocabulary includes:

`no_amplification`, `low_efficiency`, `late_or_unstable_quantification`, `nonspecific_product`, `primer_dimer`, `probe_or_target_dropout`, `cross_reactivity`, `false_positive`, `false_negative`, `rain_or_cluster_ambiguity`, `matrix_inhibition`, `carryover_contamination`, `pool_imbalance`, `sequencing_dropout`, `construct_verification_failure`, and `unresolved`.

Do not convert one failed experiment into a universal prohibition. Conversely, never erase historical failure because a newer chemistry succeeds under different conditions; preserve both records and the condition separating them.

## Robustness and design-of-experiments

Robustness studies deliberately vary factors likely to matter to the assay, for example annealing temperature, primer/probe concentration, Mg2+, enzyme/master-mix concentration, template amount, reaction volume, cycle number, extraction input, instrument or operator. PCRStudio does not prescribe one universal DoE design; it requires the validation owner to retain:

- factors and ranges tested;
- planned design (one-factor, factorial, response-surface or other);
- predefined response metrics and acceptance logic;
- interaction terms when the design supports them;
- failed corners of the design space rather than only the selected optimum.

This negative information is particularly valuable for future model training because it defines the boundary around a successful protocol.

## Reproducibility and transferability

A reproducibility/transfer record should distinguish variability attributable to:

- run/date;
- operator;
- reagent lot;
- instrument/unit/software;
- laboratory/site;
- extraction batch;
- reference/control material lot;
- threshold/analysis method.

Replication at the reaction level alone estimates only part of the total measurement process. Where the intended claim is specimen-level, replicating extraction/RT/preanalytical steps provides a more complete view of random and systematic variation, consistent with dMIQE/MIQE reporting principles.

## Conflict handling

The atlas uses a conflict-preserving rule across all engines:

- retain materially different authoritative values;
- state the product, version, workflow, matrix or statistical method separating them;
- never average conflicts into a synthetic threshold;
- if context is insufficient to choose, retain both and mark the decision validation-only;
- a superseded software/manual value may remain historically valid for data generated under that version.

## Canonical ownership map

| Validation domain | Detailed owner |
| --- | --- |
| qPCR analytical/reporting guidance | [`../engines/flanking-pair/05-qpcr-sybr.md`](../engines/flanking-pair/05-qpcr-sybr.md) and [`../engines/pair-and-probe/02-qpcr-probe.md`](../engines/pair-and-probe/02-qpcr-probe.md) |
| dPCR platform/quantification/uncertainty validation | [`../engines/flanking-pair/06-digital-pcr.md`](../engines/flanking-pair/06-digital-pcr.md) |
| Species-specific inclusivity/exclusivity and FP/FN evidence | [`../engines/flanking-pair/07-species-specific-pcr.md`](../engines/flanking-pair/07-species-specific-pcr.md) |
| Universal-primer coverage versus empirical amplification bias | [`../engines/consensus-pair/02-universal-primers.md`](../engines/consensus-pair/02-universal-primers.md) |
| Probe-target drift and multiplex readout | [`../engines/pair-and-probe/02-qpcr-probe.md`](../engines/pair-and-probe/02-qpcr-probe.md) |
| Clone/construct verification boundaries | [`../engines/mutagenic-pair/02-site-directed-mutagenesis.md`](../engines/mutagenic-pair/02-site-directed-mutagenesis.md), [`../engines/junction-primers/02-gibson-assembly.md`](../engines/junction-primers/02-gibson-assembly.md), and [`../engines/flanking-pair/09-restriction-cloning.md`](../engines/flanking-pair/09-restriction-cloning.md) |
| Sequencing trace/read-quality boundary | [`../engines/single-primer/03-sequencing-primer.md`](../engines/single-primer/03-sequencing-primer.md) |

## Validation handoff contract

For any assay result that is not fully validated, the output should state what is still required rather than inferring success. A minimal handoff may identify missing items such as matrix panel, reference material, dilution series, replicate structure, instrument/analysis version, inhibition assessment, LoD/LoQ study, robustness study or independent laboratory replication.

The correct terminal state is often **`limited / requires empirical validation`**, not an invented universal threshold.
