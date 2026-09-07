"""Structured validation contracts for sequence-only assay designs.

The flanking-pair worker can calculate primer geometry, thermodynamics and a
bounded in-silico specificity result. It cannot observe a fluorescence trace,
partition population, inhibition, processivity or product identity. A plain
list of prose reminders was too easy for a UI or exported report to flatten
into a vague ``validate experimentally`` sentence, so each assay now carries
a small, typed checklist describing the evidence still required.

This module deliberately contains no guessed laboratory values. A field such
as qPCR efficiency or dPCR partition volume is a measurement from the actual
assay/platform, not a design default. ``source`` identifies why the field is
required; it is not evidence that the current run has passed it.
"""

from __future__ import annotations

from typing import Any


def _item(
    key: str,
    label: str,
    *,
    kind: str,
    phase: str,
    source: str,
    why: str,
    unit: str | None = None,
    required: bool = True,
    computable: bool = False,
) -> dict[str, Any]:
    """Create one stable, UI-friendly validation item."""
    return {
        "key": key,
        "label": label,
        "kind": kind,
        "phase": phase,
        "source": source,
        "why": why,
        "unit": unit,
        "required": required,
        "computable": computable,
    }


COMMON: tuple[dict[str, Any], ...] = (
    _item(
        "no_template_control",
        "No-template control",
        kind="control",
        phase="bench-run",
        source="assay validation practice",
        why="Detects contamination or signal produced without the intended template.",
    ),
    _item(
        "positive_control",
        "Positive control",
        kind="control",
        phase="bench-run",
        source="assay validation practice",
        why="Shows that the reaction and readout can detect the intended target.",
    ),
    _item(
        "product_identity",
        "Product identity",
        kind="measurement",
        phase="post-run",
        source="assay validation practice",
        why="A predicted sequence is not evidence that the observed product is the intended one.",
    ),
    _item(
        "background_scope",
        "Exclusion-background scope",
        kind="decision",
        phase="design-review",
        source="PCRStudio method boundary",
        why="Record exactly which supplied background was screened; a finite scan is not a whole-database claim.",
        computable=True,
    ),
)


PLANS: dict[str, dict[str, Any]] = {
    "standard-pcr": {
        "items": [
            *COMMON,
            _item(
                "reaction_chemistry_provenance",
                "Polymerase, buffer and reagent provenance",
                kind="decision",
                phase="pre-run",
                source="PCR supplier protocol / reproducibility practice",
                why="The Primer3 reaction is a declared thermodynamic calculation context, not a reconstruction of every commercial buffer; record the actual polymerase, buffer/master mix, Mg and additive branch used at the bench.",
            ),
            _item(
                "template_quality_quantity",
                "Template identity, quality and input amount",
                kind="measurement",
                phase="pre-run",
                source="routine PCR optimization guidance",
                why="Template damage, contaminants and excessive or insufficient input can change yield and specificity independently of primer geometry.",
            ),
            _item(
                "annealing_optimization",
                "Bench annealing-temperature / cycling confirmation",
                kind="measurement",
                phase="assay-validation",
                source="routine PCR optimization guidance",
                why="PCRStudio reports sequence Tm in a declared calculation context; it does not convert that value into a universally valid bench annealing programme for an unspecified polymerase/buffer.",
            ),
            _item(
                "primer_concentration_optimization",
                "Primer concentration and reaction optimization",
                kind="measurement",
                phase="assay-validation",
                source="routine PCR optimization guidance",
                why="Primer concentration, magnesium and difficult-template additives affect yield and non-specific amplification and must be verified in the selected chemistry.",
                required=False,
            ),
        ],
        "not_computed": [
            "polymerase yield, empirical annealing optimum, template inhibition and matrix tolerance",
            "gel band identity or downstream product identity",
        ],
    },
    "long-range-pcr": {
        "items": [
            *COMMON,
            _item(
                "template_integrity",
                "Template integrity",
                kind="measurement",
                phase="pre-run",
                source="long-range PCR protocol validation",
                why="Long products depend on intact, high-molecular-weight template and cannot be certified from sequence alone.",
            ),
            _item(
                "extension_processivity",
                "Extension/processivity",
                kind="measurement",
                phase="post-run",
                source="long-range PCR protocol validation",
                why="The extension-rate starting model is not a lot-specific processivity measurement.",
            ),
        ],
        "not_computed": ["template integrity, processivity and matrix inhibition"],
    },
    "colony-pcr": {
        "items": [
            *COMMON,
            _item(
                "empty_vector_control",
                "Empty-vector control",
                kind="control",
                phase="bench-run",
                source="colony-PCR screening practice",
                why="Separates vector-only bands from insert-containing colony products.",
            ),
            _item(
                "host_control",
                "Host/no-template control",
                kind="control",
                phase="bench-run",
                source="colony-PCR screening practice",
                why="Checks for host DNA or lysis-related background amplification.",
            ),
            _item(
                "colony_sampling_record",
                "Colony/sample pick and growth-state record",
                kind="measurement",
                phase="pre-run",
                source="host-specific direct/colony PCR practice",
                why="Cell amount, culture state and transfer method change crude-template load and inhibition; PCRStudio records host/preparation/SOP but does not infer an ideal colony size or universal lysis step.",
            ),
            _item(
                "sampling_tool_and_biomass",
                "Sampling tool and qualitative biomass/input descriptor",
                kind="measurement",
                phase="pre-run",
                source="host-specific direct/colony PCR practice",
                why="A loop, tip, toothpick, liquid aliquot or other transfer can deliver materially different biomass. Record the actual sampling tool and a reproducible qualitative/quantitative input descriptor when available; PCRStudio does not convert colony appearance into a universal cell-number optimum.",
            ),
            _item(
                "medium_carryover",
                "Growth-medium / culture carryover record",
                kind="measurement",
                phase="pre-run",
                source="host-specific direct/colony PCR practice",
                why="Agar, broth, salts and other culture components can alter crude-template inhibition. Record the medium and transfer/carryover context rather than assuming that all colony preparations have equivalent inhibitor load.",
                required=False,
            ),
            _item(
                "colony_sop_provenance",
                "Colony-PCR SOP source, version/revision and chemistry identity",
                kind="decision",
                phase="pre-run",
                source="colony-PCR reproducibility practice / supplier protocol versioning",
                why="A protocol name without its source/revision and actual polymerase/master-mix identity is not enough to reproduce the crude-template preparation or cycling branch. PCRStudio therefore keeps the named SOP as provenance and requires the bench record to preserve the exact revision rather than treating free text as universal authority.",
            ),
            _item(
                "retained_clone_source",
                "Retained source colony/culture for recovery",
                kind="decision",
                phase="pre-run",
                source="colony-screening workflow practice",
                why="A screening aliquot or picked colony is not itself a recoverable confirmed clone; retain, patch or re-streak the source material needed for downstream confirmation and record how the screened source can be recovered.",
            ),
            _item(
                "insert_orientation",
                "Insert orientation, when orientation is part of the screening claim",
                kind="measurement",
                phase="post-run",
                source="colony-PCR screening practice",
                why="Orientation can only be inferred when the vector/insert primer geometry makes the alternatives distinguishable. A presence/size screen must not be forced to claim orientation it was not designed to resolve.",
                required=False,
            ),
        ],
        "not_computed": [
            "colony/sample input optimum, lysis quality, host inhibition, empirical cycling suitability and construct identity"
        ],
    },
    "qpcr-sybr": {
        "items": [
            *COMMON,
            _item(
                "raw_fluorescence",
                "Raw fluorescence traces",
                kind="measurement",
                phase="post-run",
                source="MIQE 2.0",
                why="Raw traces permit review of baseline correction and re-analysis of the fluorescence signal.",
            ),
            _item(
                "cq_method",
                "Cq method and threshold",
                kind="measurement",
                phase="post-run",
                source="MIQE 2.0",
                why="Cq depends on the analysis method and threshold, not only on primer sequence.",
            ),
            _item(
                "standard_curve",
                "Calibration/standard curve, when used",
                kind="measurement",
                phase="assay-validation",
                source="MIQE 2.0",
                why="When a calibration curve is used, report its standards, slope, fit and uncertainty. MIQE 2.0 also permits other justified efficiency/quantity methods, so a dilution-series curve is not universal.",
                required=False,
            ),
            _item(
                "efficiency_percent",
                "Amplification efficiency",
                kind="measurement",
                phase="assay-validation",
                source="MIQE 2.0",
                why="Efficiency is an observed assay property and must be reported with the method and uncertainty.",
                unit="%",
            ),
            _item(
                "quantity_model_and_uncertainty",
                "Efficiency-corrected target-quantity model and uncertainty/prediction interval",
                kind="measurement",
                phase="analysis",
                source="MIQE 2.0",
                why="MIQE 2.0 separates the observed fluorescence/Cq from the model used to estimate target quantity. Record the efficiency correction, calibration/model assumptions and uncertainty or prediction interval instead of reporting Cq alone as a quantitative result.",
            ),
            _item(
                "melt_curve",
                "Melt-curve specificity",
                kind="measurement",
                phase="post-run",
                source="MIQE 2.0",
                why="An intercalating dye reports every double-stranded product, so a single expected melt feature must be checked.",
            ),
            _item(
                "quantitative_range",
                "Validated quantitative/linear range",
                kind="measurement",
                phase="assay-validation",
                source="MIQE 2.0",
                why="The usable quantitative range is an observed assay property and must be tied to the selected efficiency/quantity method rather than inferred from primer geometry.",
            ),
            _item(
                "lod_lloq_when_relevant",
                "LOD and LLOQ, when the application requires low-copy detection/quantification",
                kind="measurement",
                phase="assay-validation",
                source="MIQE 2.0",
                why="MIQE 2.0 distinguishes LOD from LLOQ and notes that these limits are not universally required when low target levels are not relevant; when they matter, define the confidence/accuracy/precision criteria empirically.",
                required=False,
            ),
            _item(
                "instrument_and_analysis_software",
                "qPCR instrument, calibration state and analysis software/version",
                kind="measurement",
                phase="post-run",
                source="MIQE 2.0",
                why="Instrument optics, calibration and analysis software are part of the measurement chain and must not be inferred from the selected master mix.",
            ),
            _item(
                "replicate_and_exclusion_policy",
                "Replicate design and predeclared exclusion policy",
                kind="decision",
                phase="assay-validation",
                source="MIQE 2.0",
                why="Repeatability, reproducibility and any excluded reactions depend on the experimental replicate structure and acceptance rules.",
            ),
            _item(
                "rt_minus_control",
                "Minus-RT control for RNA-derived targets, when applicable",
                kind="control",
                phase="bench-run",
                source="MIQE 2.0",
                why="For RNA-derived measurements, a minus-RT control can reveal genomic-DNA carryover; it is not applicable to every DNA qPCR experiment.",
                required=False,
            ),
            _item(
                "rna_quality_and_rt_provenance",
                "RNA quality/input and reverse-transcription provenance, when applicable",
                kind="measurement",
                phase="pre-run",
                source="MIQE 2.0",
                why="For RNA-derived measurements, RNA integrity/quality, input amount and the exact one-step or two-step RT chemistry materially affect the measured quantity. A primer design or named qPCR master mix cannot establish RT yield or RNA quality.",
                required=False,
            ),
            _item(
                "normalization_strategy",
                "Reference-target validation and normalization strategy, when applicable",
                kind="decision",
                phase="analysis",
                source="MIQE 2.0",
                why="Gene-expression normalization requires justified, stable reference targets and an explicit calculation method; this is not a primer-design property.",
                required=False,
            ),
            _item(
                "matrix_and_inhibition",
                "Matrix/inhibition assessment",
                kind="measurement",
                phase="assay-validation",
                source="MIQE 2.0",
                why="Extraction matrix and inhibitors can change efficiency and fluorescence even when the primer pair is sequence-correct.",
            ),
        ],
        "not_computed": [
            "Cq, efficiency, efficiency-corrected target quantity, uncertainty/prediction intervals, baseline, melt-curve peak identity, instrument calibration, RNA/RT quality, matrix inhibition, normalization, quantitative range and application-relevant LOD/LLOQ"
        ],
    },
    "digital-pcr": {
        "items": [
            *COMMON,
            _item(
                "platform_and_partition_format",
                "Platform and partition format",
                kind="measurement",
                phase="post-run",
                source="dMIQE2020",
                why="Partition volume, acceptance rules and fluorescence behaviour are platform-specific.",
            ),
            _item(
                "reaction_and_template_provenance",
                "Reaction composition, template source/input and pre-analytical treatment",
                kind="measurement",
                phase="pre-run",
                source="dMIQE2020",
                why="dPCR interpretation depends on the exact reaction composition, sample/template source and amount, extraction or pre-amplification history, and any digestion/fragmentation. A named platform or primer pair does not reconstruct those inputs.",
            ),
            _item(
                "partition_counts",
                "Total, accepted, positive and negative partitions",
                kind="measurement",
                phase="post-run",
                source="dMIQE2020",
                why="The Poisson calculation depends on the counted partitions used for quantification.",
                unit="partitions",
            ),
            _item(
                "partition_volume",
                "Partition volume, volume authority/calibration and dead volume",
                kind="measurement",
                phase="post-run",
                source="dMIQE2020 / current platform volume-calibration documentation",
                why="Concentration normalization depends on the partition-volume model actually used by the run. Record the platform/plate-specific volume authority or calibration, analysis software/version and any applicable volume-correction factor (for example a QIAcuity VPF); PCRStudio does not hard-code one historical partition volume into primer design.",
                unit="nL",
            ),
            _item(
                "threshold_and_rain_policy",
                "Threshold, cluster and rain policy",
                kind="measurement",
                phase="post-run",
                source="dMIQE2020",
                why="Positive/negative classification and rain assignment can change the reported concentration.",
            ),
            _item(
                "poisson_and_uncertainty",
                "Poisson model and propagated uncertainty",
                kind="measurement",
                phase="analysis",
                source="dMIQE2020",
                why="Occupancy and final uncertainty require the observed partition counts, volume and replicate variation.",
            ),
            _item(
                "concentration_reporting_basis",
                "Concentration/copy-number reporting basis and conversion assumptions",
                kind="decision",
                phase="analysis",
                source="dMIQE2020",
                why="Report whether the result is copies per reaction, accepted partition volume, input volume or another normalized basis, and preserve dilution, recovery and copy-number conversion assumptions. PCRStudio does not infer a biological copy-number claim from Poisson occupancy alone.",
            ),
            _item(
                "raw_partition_data",
                "Raw partition data and software version",
                kind="measurement",
                phase="post-run",
                source="dMIQE2020",
                why="Sharing raw data makes thresholding and downstream analysis reproducible.",
            ),
            _item(
                "analytical_specificity_and_sensitivity",
                "Empirical analytical specificity and sensitivity",
                kind="measurement",
                phase="assay-validation",
                source="dMIQE2020",
                why="dMIQE2020 treats analytical specificity and sensitivity as assay-validation evidence. Finite sequence screening supports design review but cannot establish experimental positive/negative performance in the intended matrix.",
            ),
            _item(
                "validated_dynamic_range",
                "Validated dPCR measurement range",
                kind="measurement",
                phase="assay-validation",
                source="dMIQE2020",
                why="The usable concentration/occupancy range depends on partition number, accepted partitions, platform volume model, matrix and assay performance and is not a primer-geometry output.",
            ),
            _item(
                "lob_lod_loq_when_relevant",
                "LoB/LoD/LoQ for low-level, rare-target or regulated use, when applicable",
                kind="measurement",
                phase="assay-validation",
                source="dMIQE2020",
                why="For trace or rare-target measurements, low-level false-positive behaviour and the intended decision/quantification claim drive empirical LoB/LoD/LoQ. These limits are application- and control-design-dependent and must not be inferred from primer sequence.",
                required=False,
            ),
            _item(
                "template_fragmentation_and_linkage",
                "Template fragmentation/linkage treatment, when applicable",
                kind="measurement",
                phase="pre-run",
                source="dMIQE2020",
                why="Restriction digestion or other fragmentation can alter target accessibility, linkage and copy-number interpretation; record the actual treatment and ensure the target amplicon is not cut.",
                required=False,
            ),
            _item(
                "matrix_and_inhibition",
                "Matrix/inhibition assessment",
                kind="measurement",
                phase="assay-validation",
                source="dMIQE2020",
                why="Inhibitors can reduce positive-partition fluorescence, increase rain and bias classification even when sequence specificity is sound.",
            ),
            _item(
                "replicate_and_exclusion_policy",
                "Replicate design and partition/reaction exclusion policy",
                kind="decision",
                phase="assay-validation",
                source="dMIQE2020",
                why="Precision and uncertainty depend on biological/technical replicates and on transparent rules for rejecting partitions or whole reactions.",
            ),
            _item(
                "full_process_repeatability_reproducibility",
                "Full-process repeatability/reproducibility across pre-analytical and dPCR stages",
                kind="measurement",
                phase="assay-validation",
                source="dMIQE2020",
                why="Replicating only the partitioning/readout step cannot capture random variation introduced by sampling, extraction, reverse transcription when used, dilution, fragmentation, pipetting and between-run handling. Preserve the level at which replicates were started and validate repeatability/reproducibility across the full process appropriate to the intended claim.",
            ),
            _item(
                "rt_minus_control",
                "Minus-RT control for RNA-derived digital PCR, when applicable",
                kind="control",
                phase="assay-validation",
                source="dMIQE2020 / named RT-dPCR protocol",
                why="A one-step RT-dPCR reagent record does not prove that observed positive partitions came from RNA rather than contaminating DNA; use a minus-RT control when that distinction matters.",
                required=False,
            ),
            _item(
                "rna_quality_and_rt_provenance",
                "RNA input/quality and reverse-transcription provenance, when applicable",
                kind="measurement",
                phase="pre-run",
                source="dMIQE2020 / named RT-dPCR protocol",
                why="RNA-derived dPCR adds pre-analytical and reverse-transcription variability that is not represented by the primer pair or final partition counts. Record RNA source/input/quality and the exact one-step or two-step RT chemistry, placement and conditions used.",
                required=False,
            ),
        ],
        "not_computed": [
            "partition occupancy, rain, threshold classification, fragmentation/linkage effects, matrix inhibition, Poisson uncertainty, analytical sensitivity/specificity, validated measurement range and application-dependent LoB/LoD/LoQ"
        ],
    },
    "species-specific-pcr": {
        "items": [
            *COMMON,
            _item(
                "inclusivity_panel",
                "Intended-target inclusivity panel",
                kind="measurement",
                phase="assay-validation",
                source="FDA nucleic-acid assay analytical-reactivity guidance / ISO 22174:2024",
                why="The inclusivity set should represent the genetic diversity relevant to the claim. A supplied FASTA panel and its hash support reproducible screening, but do not prove strain/population representativeness or empirical detection near the claimed limit.",
            ),
            _item(
                "exclusivity_panel",
                "Near-neighbour exclusivity panel",
                kind="measurement",
                phase="assay-validation",
                source="FDA nucleic-acid assay cross-reactivity guidance / ISO 22174:2024",
                why="Exclusivity should challenge taxonomically related, potentially cross-reactive and application-relevant co-occurring organisms. A finite in-silico background is a reproducible screen, not a complete empirical specificity claim.",
            ),
            _item(
                "panel_provenance",
                "Inclusivity/exclusivity panel provenance and rationale",
                kind="decision",
                phase="design-review",
                source="ISO 22174:2024 / FDA nucleic-acid assay validation guidance",
                why="Record accession/version or traceable isolate identity, taxonomy, temporal/geographic/phylogenetic rationale where relevant, panel date and why each intended target or near-neighbour was included. FASTA labels and a content hash do not independently validate biological identity or diversity coverage.",
            ),
            _item(
                "analytical_sensitivity",
                "Analytical sensitivity / LOD in the intended matrix",
                kind="measurement",
                phase="assay-validation",
                source="diagnostic assay validation",
                why="Exact in-silico primer compatibility does not establish the concentration at which the intended organism is reliably detected.",
            ),
            _item(
                "interference_and_matrix",
                "Matrix and microbial-interference challenge",
                kind="measurement",
                phase="assay-validation",
                source="diagnostic assay validation",
                why="Related organisms, abundant background DNA and specimen inhibitors can alter analytical specificity or sensitivity beyond an isolated sequence screen.",
            ),
            _item(
                "sequence_surveillance",
                "Target/near-neighbour sequence surveillance plan",
                kind="decision",
                phase="post-validation",
                source="diagnostic assay lifecycle practice",
                why="A species or strain population can acquire newly represented variation; database release and review date must be maintained for continuing claims.",
                required=False,
            ),
        ],
        "not_computed": [
            "taxonomic completeness, population-frequency coverage, analytical/clinical sensitivity, matrix interference or empirical exclusivity"
        ],
    },
    "rpa": {
        "items": [
            *COMMON,
            _item(
                "rpa_chemistry_format",
                "RPA chemistry and detection format",
                kind="decision",
                phase="assay-design",
                source="Named RPA supplier guidance (TwistDx / Thermo Fisher)",
                why="RPA formulations and detection formats are chemistry-specific; a primer pair alone does not identify the reagent system, RT branch or readout.",
            ),
            _item(
                "rpa_readout_contract",
                "Readout and modified-oligo contract",
                kind="decision",
                phase="assay-design",
                source="TwistAmp assay design guidance / named RPA supplier protocol",
                why="The executable GEN1 flanking-pair RPA branches emit two plain ACGT primers only and do not infer a fluorescence/lateral-flow probe. Exo/Nfo/Fpg-style THF/dSpacer, reporter/quencher, affinity-tag or 3′-block architectures require a separate typed modified-oligo branch.",
            ),
            _item(
                "isothermal_hold",
                "Hold temperature and duration",
                kind="measurement",
                phase="bench-run",
                source="Named RPA supplier protocol",
                why="The returned hold is a reviewed supplier starting point; actual amplification and time-to-signal require the selected chemistry and matrix.",
                unit="°C; seconds",
            ),
            _item(
                "candidate_primer_screen",
                "Candidate-primer screen",
                kind="measurement",
                phase="assay-validation",
                source="RPA supplier primer-design guidance",
                why="RPA activity, amplification speed and primer noise cannot be predicted from sequence alone; screen multiple candidate combinations and retain the observed sensitivity and product/noise ranking.",
                unit="candidate pairs",
            ),
            _item(
                "rpa_reaction_optimization",
                "RPA reaction optimization",
                kind="measurement",
                phase="assay-validation",
                source="Named RPA supplier protocol",
                why="Temperature, magnesium salt, enzyme and primer/probe concentrations affect rate, sensitivity and noise; verify the selected kit-specific operating point instead of treating any one supplier recipe as universal.",
            ),
            _item(
                "rpa_contamination_workflow",
                "RPA pre/post-amplification contamination workflow and NTC review",
                kind="control",
                phase="bench-run",
                source="TwistDx contamination guidance / named RPA supplier protocol",
                why="RPA endpoint products are high-copy amplicons and no-template positives are commonly caused by carry-over or environmental contamination. Separate pre- and post-amplification areas, appropriate NTCs and source-specific handling/cleanup controls must be documented; PCRStudio does not infer a contamination-free workflow from primer sequence.",
            ),
            _item(
                "rt_minus_control",
                "Minus-RT control for RT-RPA, when RNA is the starting material",
                kind="control",
                phase="assay-validation",
                source="RT-RPA validation practice / MAN1000697",
                why="A named one-pot RT-RPA recipe defines reagents, not whether observed signal originated from RNA rather than contaminating DNA; use a minus-RT control when that distinction matters.",
                required=False,
            ),
            _item(
                "rna_input_and_rt_provenance",
                "RNA input/quality and RT-RPA provenance, when applicable",
                kind="measurement",
                phase="pre-run",
                source="Thermo Fisher MAN1000697 Rev B / RT-RPA validation practice",
                why="The named RT-RPA overlay specifies a reagent recipe but cannot establish RNA integrity, extraction quality, RT yield or sample inhibition. Preserve the actual RNA input/preparation and RT-RPA reagent authority used at the bench.",
                required=False,
            ),
            _item(
                "rpa_mismatch_challenge",
                "Chemistry-bound mismatch / near-neighbour challenge",
                kind="measurement",
                phase="assay-validation",
                source="RPA mismatch-characterization literature / named RPA chemistry",
                why="RPA mismatch effects depend on identity, position, local sequence and chemistry. Use the reported in-silico 3′ mismatch topology to choose empirical near-neighbour challenges, but determine discrimination on the selected RPA formulation instead of applying one universal mismatch cutoff or probability model.",
                required=False,
            ),
            _item(
                "non_target_panel",
                "Non-target and matrix panel",
                kind="measurement",
                phase="assay-validation",
                source="RPA assay validation practice",
                why="Low-temperature recombinase reactions need empirical checks for non-target amplification and inhibition.",
            ),
        ],
        "not_computed": [
            "recombinase loading kinetics, candidate-primer activity, probe cleavage/readout, RT yield, time-to-signal, chemistry-specific mismatch discrimination, reaction optimum and matrix tolerance"
        ],
    },
    "nested-pcr": {
        "items": [
            *COMMON,
            _item(
                "round_one_control",
                "Outer-round amplification control",
                kind="control",
                phase="bench-run",
                source="nested PCR validation practice",
                why="The inner reaction cannot rescue an unobserved or contaminated outer round without changing the interpretation of the assay.",
            ),
            _item(
                "round_two_control",
                "Inner-round amplification control",
                kind="control",
                phase="bench-run",
                source="nested PCR validation practice",
                why="The nested product must be attributable to the intended inner pair and transfer scheme, not carry-over or an unrelated outer product.",
            ),
            _item(
                "carryover_control",
                "Carry-over contamination control",
                kind="control",
                phase="bench-run",
                source="nested PCR validation practice",
                why="Opening or transferring the first-round product materially increases contamination risk and cannot be validated in silico.",
            ),
            _item(
                "nested_product_identity",
                "Nested product identity",
                kind="measurement",
                phase="post-run",
                source="nested PCR validation practice",
                why="Containment geometry predicts an inner product but does not prove the observed nested product identity.",
            ),
        ],
        "not_computed": [
            "round-to-round carry-over, empirical enrichment, contamination rate or observed product identity"
        ],
    },
    "inverse-pcr": {
        "items": [
            *COMMON,
            _item(
                "template_topology",
                "Circularized/digested template topology",
                kind="measurement",
                phase="pre-run",
                source="inverse PCR validation practice",
                why="Outward-primer geometry is only meaningful if the physical digest/circularization state matches the selected branch.",
            ),
            _item(
                "junction_identity",
                "Circularization junction identity",
                kind="measurement",
                phase="post-run",
                source="inverse PCR validation practice",
                why="The reconstructed junction is a sequence model, not evidence that the bench preparation created that junction.",
            ),
            _item(
                "linear_template_control",
                "Linear-template control",
                kind="control",
                phase="bench-run",
                source="inverse PCR validation practice",
                why="A control distinguishes the intended circular-template mechanism from amplification that can occur on residual linear material.",
            ),
        ],
        "not_computed": [
            "digest completeness, ligation/circularization efficiency, methylation-dependent cleavage or physical template topology"
        ],
    },
    "qpcr-probe": {
        "items": [
            *COMMON,
            _item(
                "raw_fluorescence",
                "Raw fluorescence traces",
                kind="measurement",
                phase="post-run",
                source="MIQE 2.0",
                why="Raw traces are required to review baseline, Cq determination and fluorescence behavior; sequence design cannot create them.",
            ),
            _item(
                "cq_method",
                "Cq method and threshold",
                kind="measurement",
                phase="analysis",
                source="MIQE 2.0",
                why="Cq is analysis-method dependent and cannot be inferred from the oligo sequences.",
            ),
            _item(
                "standard_curve",
                "Standard curve, efficiency and quantitative range",
                kind="measurement",
                phase="assay-validation",
                source="MIQE 2.0",
                why="Efficiency, linearity, LOD and LLOQ are empirical assay properties that require dilution-series evidence.",
            ),
            _item(
                "probe_channel_configuration",
                "Probe dye/channel and optical configuration",
                kind="decision",
                phase="pre-run",
                source="qPCR platform validation practice",
                why="A geometrically valid probe is not evidence that the reporter/quencher and instrument channel configuration are compatible.",
            ),
            _item(
                "probe_signal_specificity",
                "Probe-signal specificity",
                kind="measurement",
                phase="assay-validation",
                source="MIQE 2.0",
                why="Observed probe signal, non-template behavior and target discrimination must be demonstrated on the selected chemistry/platform.",
            ),
        ],
        "not_computed": [
            "Cq, amplification efficiency, fluorescence amplitude, LOD/LLOQ, optical cross-talk or observed probe cleavage"
        ],
    },
    "arms-pcr": {
        "items": [
            *COMMON,
            _item(
                "known_genotype_controls",
                "Known-genotype allele controls",
                kind="control",
                phase="assay-validation",
                source="allele-specific PCR validation practice",
                why="Allele discrimination is an empirical extension property and must be demonstrated against known genotypes.",
            ),
            _item(
                "heterozygote_control",
                "Heterozygous control, when biologically applicable",
                kind="control",
                phase="assay-validation",
                source="allele-specific PCR validation practice",
                why="A heterozygous sample tests simultaneous allele detection and exposes preferential amplification that sequence scoring cannot certify.",
                required=False,
            ),
            _item(
                "genotype_concordance",
                "Genotype concordance",
                kind="measurement",
                phase="assay-validation",
                source="genotyping validation practice",
                why="Predicted 3′ discrimination does not establish analytical genotype calling accuracy.",
            ),
        ],
        "not_computed": [
            "allelic amplification ratio, false-call rate, genotype concordance or matrix-specific discrimination"
        ],
    },
    "tetra-primer-arms": {
        "items": [
            *COMMON,
            _item(
                "known_genotype_controls",
                "Known-genotype controls",
                kind="control",
                phase="assay-validation",
                source="tetra-ARMS validation practice",
                why="All genotype band patterns must be observed with known controls rather than inferred from product geometry alone.",
            ),
            _item(
                "diagnostic_band_resolution",
                "Diagnostic band resolution",
                kind="measurement",
                phase="post-run",
                source="tetra-ARMS validation practice",
                why="Predicted product-size separation does not guarantee resolvable bands in the actual gel/capillary system.",
            ),
            _item(
                "four_primer_balance",
                "Four-primer reaction balance",
                kind="measurement",
                phase="assay-validation",
                source="tetra-ARMS validation practice",
                why="Competition among four primers is empirical and can change genotype signal balance despite acceptable pairwise thermodynamics.",
            ),
        ],
        "not_computed": [
            "observed genotype pattern, allele balance, gel resolution or genotype concordance"
        ],
    },
    "kasp": {
        "items": [
            _item(
                "no_template_control",
                "No-template control",
                kind="control",
                phase="bench-run",
                source="KASP genotyping validation practice",
                why="Defines the no-template cluster/background for endpoint genotype calling.",
            ),
            _item(
                "known_genotype_controls",
                "Known-genotype controls",
                kind="control",
                phase="assay-validation",
                source="KASP genotyping validation practice",
                why="FAM/HEX cluster identity must be anchored to known genotypes, not inferred from tail assignment alone.",
            ),
            _item(
                "instrument_optics",
                "Instrument dye/ROX configuration",
                kind="decision",
                phase="pre-run",
                source="KASP platform guidance",
                why="Endpoint FRET readout depends on instrument optical settings and reference-dye policy.",
            ),
            _item(
                "cluster_review",
                "Endpoint cluster quality and call review",
                kind="measurement",
                phase="post-run",
                source="KASP genotyping validation practice",
                why="Cluster separation, call rate and ambiguous wells are observed data properties and cannot be predicted from sequence design.",
            ),
            _item(
                "genotype_concordance",
                "Genotype concordance",
                kind="measurement",
                phase="assay-validation",
                source="genotyping validation practice",
                why="Analytical genotype-call accuracy requires comparison with known or orthogonally confirmed samples.",
            ),
        ],
        "not_computed": [
            "endpoint fluorescence clusters, call rate, cluster separation, ROX behavior or genotype concordance"
        ],
    },
    "lamp": {
        "items": [
            _item(
                "no_template_control",
                "No-template control",
                kind="control",
                phase="bench-run",
                source="LAMP validation practice",
                why="LAMP is highly productive and contamination/background signal must be measured in the actual readout.",
            ),
            _item(
                "positive_control",
                "Positive control",
                kind="control",
                phase="bench-run",
                source="LAMP validation practice",
                why="Confirms the selected Bst-family chemistry and readout can detect the intended target.",
            ),
            _item(
                "readout_validation",
                "Readout-specific validation",
                kind="measurement",
                phase="assay-validation",
                source="LAMP assay validation practice",
                why="Fluorescence, colorimetric and turbidity readouts have different decision behavior; the chosen readout must be validated empirically.",
            ),
            _item(
                "product_identity",
                "LAMP product identity/orthogonal confirmation",
                kind="measurement",
                phase="post-run",
                source="LAMP validation practice",
                why="Complex LAMP products and nonspecific amplification cannot be certified from primer geometry alone.",
            ),
            _item(
                "contamination_control",
                "Carry-over/amplicon contamination control",
                kind="control",
                phase="bench-run",
                source="LAMP validation practice",
                why="High product yield makes contamination control a physical workflow requirement, not a sequence-derived property.",
            ),
        ],
        "not_computed": [
            "time-to-positive, color threshold, fluorescence threshold, matrix inhibition, amplification yield or diagnostic sensitivity/specificity"
        ],
    },
    "universal-primers": {
        "items": [
            _item(
                "alignment_provenance",
                "Alignment/accession provenance",
                kind="decision",
                phase="design-review",
                source="PCRStudio universal-primer contract",
                why="Coverage claims are only meaningful for a versioned, curated input panel and alignment authority.",
                computable=True,
            ),
            _item(
                "coverage_strata",
                "Target coverage by relevant strata",
                kind="measurement",
                phase="assay-validation",
                source="universal-primer validation practice",
                why="Overall in-silico coverage can hide lineage/strain/taxon-specific failures and requires empirical inclusivity review.",
            ),
            _item(
                "degenerate_pool_inclusivity",
                "Degenerate-pool empirical inclusivity",
                kind="measurement",
                phase="assay-validation",
                source="universal-primer validation practice",
                why="Concrete-member coverage does not measure synthesis bias or competitive amplification within the physical degenerate pool.",
            ),
            _item(
                "non_target_panel",
                "Non-target/exclusion panel",
                kind="measurement",
                phase="assay-validation",
                source="universal-primer validation practice",
                why="Broad target coverage must be balanced against empirical non-target amplification in the intended application.",
            ),
        ],
        "not_computed": [
            "population prevalence coverage, synthesis bias, competitive member abundance or empirical inclusivity/exclusivity"
        ],
    },
    "tiled-scheme": {
        "items": [
            _item(
                "sequencing_coverage",
                "Observed sequencing coverage by amplicon",
                kind="measurement",
                phase="post-run",
                source="tiled-amplicon sequencing validation practice",
                why="Predicted tiling coverage cannot establish read depth or dropout in the actual library/sequencing workflow.",
            ),
            _item(
                "pool_balance",
                "Pool balance and dropout review",
                kind="measurement",
                phase="assay-validation",
                source="tiled-amplicon sequencing validation practice",
                why="Interaction scores and pool assignment do not measure empirical amplification balance.",
            ),
            _item(
                "negative_controls",
                "Extraction/NTC controls",
                kind="control",
                phase="bench-run",
                source="amplicon sequencing validation practice",
                why="Controls are required to identify contamination and index/read carry-over that are outside sequence design.",
            ),
            _item(
                "variant_refresh",
                "Primer-mismatch/variant refresh review",
                kind="decision",
                phase="design-review",
                source="PrimalScheme lifecycle practice",
                why="A released scheme must be re-evaluated against newer variation; a historical design cannot guarantee current coverage.",
                computable=True,
            ),
        ],
        "not_computed": [
            "read depth, pool balance, dropout rate, library yield, contamination or current epidemiological coverage"
        ],
    },
    "race": {
        "items": [
            _item(
                "rna_integrity",
                "RNA integrity and input quality",
                kind="measurement",
                phase="pre-run",
                source="RACE validation practice",
                why="Transcript-end recovery depends on physical RNA integrity that cannot be inferred from a reference sequence.",
            ),
            _item(
                "rt_adapter_preparation",
                "RT/adapter preparation evidence",
                kind="measurement",
                phase="pre-run",
                source="RACE protocol validation",
                why="The selected 5′/3′ RACE branch assumes a real preparation/adapter state; sequence design cannot prove it.",
            ),
            _item(
                "nested_round_identity",
                "Nested-round product identity, when nested RACE is used",
                kind="measurement",
                phase="post-run",
                source="RACE validation practice",
                why="A nested design predicts primer geometry but cannot prove the observed transcript-end product.",
                required=False,
            ),
            _item(
                "transcript_end_confirmation",
                "Transcript-end orthogonal confirmation",
                kind="measurement",
                phase="post-run",
                source="RACE validation practice",
                why="A candidate end recovered by amplification should be mapped/sequenced; PCRStudio does not infer a true biological transcript end from primer placement.",
            ),
        ],
        "not_computed": [
            "RNA integrity, reverse-transcription yield, cap/poly(A) state, true transcript end or isoform abundance"
        ],
    },
    "sequencing-primer": {
        "items": [
            _item(
                "instrument_chemistry",
                "Sequencing instrument/chemistry",
                kind="decision",
                phase="pre-run",
                source="Sanger sequencing workflow",
                why="Primer placement is separable from the facility/instrument chemistry that determines trace performance.",
            ),
            _item(
                "trace_quality",
                "Observed chromatogram/trace quality",
                kind="measurement",
                phase="post-run",
                source="Sanger sequencing workflow",
                why="Usable read length, mixed signal and basecalling quality are properties of the observed trace, not sequence-design outputs.",
            ),
            _item(
                "read_mapping",
                "Read mapping and expected-direction confirmation",
                kind="measurement",
                phase="post-run",
                source="Sanger sequencing workflow",
                why="The obtained read must map to the intended template in the expected direction before the design is treated as experimentally successful.",
            ),
        ],
        "not_computed": [
            "chromatogram quality, Phred/basecalling quality, usable read length or facility-specific chemistry performance"
        ],
    },
    "gibson-assembly": {
        "items": [
            _item(
                "assembly_negative_control",
                "Assembly negative control",
                kind="control",
                phase="bench-run",
                source="Gibson assembly validation practice",
                why="A negative control distinguishes intended assembly from vector/background recovery.",
            ),
            _item(
                "junction_verification",
                "Assembly-junction sequence verification",
                kind="measurement",
                phase="post-run",
                source="Gibson assembly validation practice",
                why="Overlap geometry predicts a construct but does not prove the physical junction sequence.",
            ),
            _item(
                "construct_identity",
                "Final construct identity",
                kind="measurement",
                phase="post-run",
                source="Gibson assembly validation practice",
                why="Independent PCR-product simulation is not full assembly/construct validation; verify the completed construct experimentally.",
            ),
        ],
        "not_computed": [
            "assembly efficiency, fragment stoichiometry effects, colony recovery or complete construct sequence"
        ],
    },
    "site-directed-mutagenesis": {
        "items": [
            _item(
                "parental_template_control",
                "Parental-template control/removal",
                kind="control",
                phase="bench-run",
                source="site-directed mutagenesis validation practice",
                why="Primer design cannot establish removal of parental template or background carry-over.",
            ),
            _item(
                "clone_screening",
                "Clone screening",
                kind="measurement",
                phase="post-run",
                source="site-directed mutagenesis validation practice",
                why="A predicted edited amplicon is not evidence that a recovered clone carries the intended edit.",
            ),
            _item(
                "edit_sequence_confirmation",
                "Edit and surrounding-sequence confirmation",
                kind="measurement",
                phase="post-run",
                source="site-directed mutagenesis validation practice",
                why="Confirm the intended change and relevant surrounding sequence; PCRStudio does not infer absence of unintended changes from primer design.",
            ),
        ],
        "not_computed": [
            "mutagenesis efficiency, parental-template carry-over, clone frequency or absence of unintended sequence changes"
        ],
    },
    "restriction-cloning": {
        "items": [
            *COMMON,
            _item(
                "vector_compatibility",
                "Vector and enzyme compatibility",
                kind="decision",
                phase="pre-run",
                source="supplier restriction-enzyme protocol",
                why="An enzyme absent from the insert is not automatically compatible with the vector's cloning site or buffer.",
            ),
            _item(
                "end_cleavage",
                "End-cleavage and protective-base validation",
                kind="measurement",
                phase="bench-run",
                source="supplier restriction-enzyme protocol",
                why="Cleavage near a DNA end depends on the selected enzyme and supplier guidance; the default tail is advisory.",
            ),
            _item(
                "methylation_context",
                "Restriction-site methylation context",
                kind="decision",
                phase="pre-run",
                source="supplier methylation-sensitivity record / substrate provenance",
                why="Dam, Dcm or CpG methylation can block or impair cleavage for particular enzyme/site/substrate combinations; the pasted sequence does not encode the physical methylation state.",
            ),
            _item(
                "star_activity_controls",
                "Digest-condition / star-activity controls",
                kind="decision",
                phase="pre-run",
                source="supplier restriction-enzyme protocol",
                why="Buffer, glycerol fraction, enzyme loading, incubation time and other reaction conditions can relax restriction specificity; PCRStudio does not compute a star-activity-free verdict from the recognition site.",
            ),
            _item(
                "double_digest_and_stop",
                "Double-digest compatibility and reaction-stop/cleanup plan",
                kind="decision",
                phase="pre-run",
                source="current supplier restriction-enzyme buffer/activity and heat-inactivation records",
                why="Recognition sequences alone do not establish that the exact purchased enzyme formulations share a suitable buffer/temperature or can be stopped by the same heat treatment; record the current supplier decision or a sequential-digest/cleanup workflow.",
            ),
            _item(
                "junction_sequence",
                "Assembly-junction sequence verification",
                kind="measurement",
                phase="post-run",
                source="cloning validation practice",
                why="A predicted restriction tail does not prove the final insert/vector junction or whether the reconstructed hybrid junction remains cleavable by either enzyme.",
            ),
        ],
        "not_computed": [
            "vendor lot performance, methylation-dependent cleavage, star activity, exact double-digest compatibility, heat inactivation/cleanup suitability, vector compatibility, ligation-junction re-cleavage or final construct sequence"
        ],
    },
}


RNA_REQUIRED_KEYS: dict[str, frozenset[str]] = {
    "qpcr-sybr": frozenset({"rt_minus_control", "rna_quality_and_rt_provenance"}),
    "digital-pcr": frozenset({"rt_minus_control", "rna_quality_and_rt_provenance"}),
    "rpa": frozenset({"rt_minus_control", "rna_input_and_rt_provenance"}),
}


def for_assay(assay_id: str, *, from_rna: bool = False) -> dict[str, Any] | None:
    """Return a fresh JSON-ready validation contract for an assay.

    RNA-derived workflows promote RNA/RT evidence from a conditional reminder
    to a required validation item. This changes only the evidence contract; it
    does not alter primer ranking or invent an RT yield/quality measurement.
    """
    plan = PLANS.get(assay_id)
    if plan is None:
        return None

    items = [dict(item) for item in plan["items"]]
    if from_rna:
        required_keys = RNA_REQUIRED_KEYS.get(assay_id, frozenset())
        for item in items:
            if item["key"] in required_keys:
                item["required"] = True
    return {
        "status": "in-silico-only",
        "scope": "sequence-design-and-preflight",
        "required": [item["label"] for item in items if item["required"]],
        "items": items,
        "not_computed": list(plan["not_computed"]),
    }
