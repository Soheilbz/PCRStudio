import type { RunResult } from "@/lib/api/types";

/**
 * A saved result as clean markdown, for pasting into a notebook or an issue.
 *
 * Deliberately a summary rather than the whole view: what runs, which oligos
 * to order, how much they amplify and how warm — the things that get retyped
 * by hand when there is no button. Everything else (the funnel, the maps, the
 * scores) is on the run itself, and a report that carried all of it would be
 * nobody's summary.
 *
 * Engines whose shapes carry measured pairs are written out pair by pair; the
 * rest fall through to their order sheet, which every engine produces and
 * which carries name, sequence, GC and Tm for each line. An engine with
 * neither gets its reason for coming back empty, quoted — never silence.
 */

export interface ReportInput {
  /** The run's label, or whatever the caller calls it when none was given. */
  label: string;
  /** ISO, as stored. Only the day is quoted in the report. */
  createdAt: string;
  /** The assay's own name, when it has one. */
  moduleName: string | null;
  result: RunResult;
}

/** One oligo as the report quotes it. The figures are preformatted strings,
 * because some engines measure a range where others measure one number. */
interface ReportedOligo {
  role: string;
  sequence: string;
  tm: string;
  gc: string;
}

/** One design as the report quotes it. */
interface ReportedDesign {
  heading: string;
  oligos: ReportedOligo[];
  productSize: number | null;
}

type JunctionProtocolForReport = {
  selection: string;
  reaction_volume_uL: number;
  source_identity?: string;
  source_revision?: string;
  source_revision_date_precision?: string | null;
  fragment_count: number;
  total_fragment_input_pmol_min: number;
  total_fragment_input_pmol_max: number;
  incubation: { temperature_c: number; minutes: number; branch: string };
  insert_molar_excess: string;
  unpurified_pcr_fraction_max: number;
  note: string;
};

type DiscriminatingProtocolForReport = {
  selection: string;
  plate_format: string;
  reaction_volume_uL: number;
  dna_final_ng_per_uL: number;
  source_identity?: string;
  source_revision?: string;
  chemistry_identity?: string;
  instrument_model?: string;
  rox_policy?: string;
  dna_volume_uL?: number;
  master_mix_volume_uL?: number;
  assay_mix_volume_uL?: number;
  touchdown: { cycles: number; anneal_extend_start_c: number; anneal_extend_final_c: number };
  amplification: { cycles: number; anneal_extend_c: number };
  readout: { channels: string[]; ntc_minimum: number };
  note: string;
};

type PairProbeProtocolForReport = {
  selection: string;
  probe_chemistry: string;
  application_scope?: string;
  source_identity?: string;
  source_revision?: string;
  source_revision_date?: string;
  source_revision_date_precision?: string;
  source_documents?: Array<{
    identity: string;
    publication?: string;
    revision?: string;
    revision_date?: string;
    supports: string[];
  }>;
  primer_final_concentration_nM: number;
  probe_final_concentration_nM: number;
  amplicon_bp: { min: number; max: number };
  primer_tm_c: { min: number; max: number };
  probe_tm_c: { min: number; max: number };
  probe_length_nt: { min: number; max: number };
  primer_constraints?: Record<string, unknown>;
  probe_constraints?: Record<string, unknown>;
  reporter_options: string[];
  quencher: string;
  note: string;
};

function objectRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

export function reportMarkdown(input: ReportInput): string {
  const designs = extract(input.result);
  const lines: string[] = [];

  lines.push(`# ${input.label || "A primer design"}`);
  const subtitle = [input.moduleName ?? null, dayOf(input.createdAt)].filter(Boolean).join(" · ");
  if (subtitle) lines.push("", subtitle);

  if ("assay" in input.result && input.result.assay?.profile_authority) {
    const authority = input.result.assay.profile_authority;
    lines.push(
      "",
      "## Profile authority",
      "",
      `- Profile: ${authority.profileId}`,
      `- Source: ${authority.source}`,
      `- Transport: ${authority.transport}`,
    );
  }

  if (input.result.engine === "flanking-pair") {
    if (input.result.purpose) {
      const purpose = input.result.purpose;
      const purposeConstraints = Object.entries(purpose.constraints);
      const rankingWeights = Object.entries(purpose.ranking_weights);
      lines.push(
        "",
        "## Search purpose",
        "",
        `- ${purpose.name} (${purpose.id})`,
        `- ${purpose.summary}`,
        `- Purpose constraints: ${purposeConstraints.length === 0 ? "none" : purposeConstraints.map(([key, value]) => `${key}=${value}`).join(" · ")}`,
        `- Ranking weights: ${rankingWeights.length === 0 ? "none" : rankingWeights.map(([key, value]) => `${key}=${value}`).join(" · ")}`,
        `- Explicit request overrides of purpose constraints: ${purpose.overridden.length === 0 ? "none" : purpose.overridden.join(", ")}`,
      );
    }

    const screeningReaction = input.result.reaction;
    if (screeningReaction.context_note) {
      lines.push(
        "",
        "## Thermodynamic screening context",
        "",
        `- Role: ${screeningReaction.context_role ?? "calculation context"}`,
        `- Model: ${screeningReaction.model.name}`,
        `- Inputs: ${screeningReaction.mv_conc} mM monovalent · ${screeningReaction.dv_conc} mM divalent · ${screeningReaction.dntp_conc} mM total dNTP · ${screeningReaction.dna_conc} nM Tm oligo`,
        `- ${screeningReaction.context_note}`,
      );
    }

    if (input.result.background) {
      const background = input.result.background;
      lines.push(
        "",
        "## Specificity/background scope",
        "",
        `- Checked: ${background.checked ? "yes" : "no"}`,
        `- Scope: ${background.template_only ? "template only" : `${background.contigs} record(s), ${background.bases} bases`}`,
        ...(background.panel_sha256
          ? [`- Exclusivity panel SHA-256: ${background.panel_sha256}`]
          : []),
        ...(background.panel_provenance
          ? [`- Exclusivity panel provenance: ${background.panel_provenance}`]
          : []),
        ...(background.panel_selection_rationale
          ? [`- Panel-selection rationale: ${background.panel_selection_rationale}`]
          : []),
        ...(background.taxonomy_resolution_status
          ? [`- Taxonomy resolution: ${background.taxonomy_resolution_status}`]
          : []),
        ...(background.biological_traceability_status
          ? [`- Biological traceability: ${background.biological_traceability_status}`]
          : []),
        ...(background.diversity_coverage_status
          ? [`- Diversity coverage: ${background.diversity_coverage_status}`]
          : []),
        ...(background.population_frequency_status
          ? [`- Population-frequency coverage: ${background.population_frequency_status}`]
          : []),
        ...(background.surveillance_status
          ? [`- Surveillance: ${background.surveillance_status}`]
          : []),
        ...(background.sequence_topology_assumption
          ? [`- Sequence topology assumption: ${background.sequence_topology_assumption}`]
          : []),
        ...(background.topology_note ? [`- Topology note: ${background.topology_note}`] : []),
        ...(background.note ? [`- ${background.note}`] : []),
      );
    }

    if (input.result.inclusivity) {
      const inclusivity = input.result.inclusivity;
      lines.push(
        "",
        "## Target inclusivity scope",
        "",
        `- Records: ${inclusivity.contigs}; bases: ${inclusivity.bases}`,
        `- Candidate pairs checked/rejected: ${inclusivity.pairs_checked}/${inclusivity.pairs_rejected}`,
        ...(inclusivity.panel_sha256
          ? [`- Inclusivity panel SHA-256: ${inclusivity.panel_sha256}`]
          : []),
        ...(inclusivity.panel_provenance
          ? [`- Inclusivity panel provenance: ${inclusivity.panel_provenance}`]
          : []),
        ...(inclusivity.panel_selection_rationale
          ? [`- Panel-selection rationale: ${inclusivity.panel_selection_rationale}`]
          : []),
        ...(inclusivity.taxonomy_resolution_status
          ? [`- Taxonomy resolution: ${inclusivity.taxonomy_resolution_status}`]
          : []),
        ...(inclusivity.biological_traceability_status
          ? [`- Biological traceability: ${inclusivity.biological_traceability_status}`]
          : []),
        ...(inclusivity.diversity_coverage_status
          ? [`- Diversity coverage: ${inclusivity.diversity_coverage_status}`]
          : []),
        ...(inclusivity.population_frequency_status
          ? [`- Population-frequency coverage: ${inclusivity.population_frequency_status}`]
          : []),
        ...(inclusivity.surveillance_status
          ? [`- Surveillance: ${inclusivity.surveillance_status}`]
          : []),
        ...(inclusivity.sequence_topology_assumption
          ? [`- Sequence topology assumption: ${inclusivity.sequence_topology_assumption}`]
          : []),
        ...(inclusivity.topology_note ? [`- Topology note: ${inclusivity.topology_note}`] : []),
        `- ${inclusivity.note}`,
      );
    }

    if (input.result.reverse_transcription) {
      const rt = input.result.reverse_transcription;
      const placement =
        rt.before === "concurrent-with-rpa"
          ? "concurrent with RPA amplification"
          : rt.before
            ? `before ${rt.before.replaceAll("-", " ")}`
            : "not resolved by the generic RNA modifier";
      lines.push(
        "",
        "## Reverse-transcription handoff",
        "",
        `- One-step status: ${rt.one_step == null ? "not inferred" : rt.one_step ? "one-step" : "two-step"}`,
        `- Placement: ${placement}`,
        ...(rt.hold
          ? [`- Named hold: ${rt.hold.celsius} °C for ${Math.round(rt.hold.seconds / 60)} min`]
          : []),
        ...(rt.authority_status ? [`- Authority: ${rt.authority_status}`] : []),
        `- ${rt.note}`,
      );
    }

    if (input.result.colony_context) {
      const colony = input.result.colony_context;
      lines.push(
        "",
        "## Colony-screen provenance",
        "",
        `- Host class: ${colony.host_class}`,
        `- Preparation: ${colony.preparation}`,
        `- Protocol/SOP: ${colony.protocol_name}`,
        `- SOP provenance: ${colony.protocol_provenance}`,
        `- Interpretation: ${colony.interpretation_status}`,
        `- Lysis timing inferred by PCRStudio: ${colony.lysis_timing_inferred ? "yes" : "no"}`,
        `- Colony/sample amount inferred by PCRStudio: ${colony.sample_amount_inferred ? "yes" : "no"}`,
        `- Cycling authority: ${colony.cycling_authority}`,
        `- Source recovery: ${colony.source_recovery_status}`,
        ...colony.required_observations.map((item) => `- Required observation: ${item}`),
        `- ${colony.note}`,
      );
    }

    if (input.result.digital_context) {
      const digital = input.result.digital_context;
      lines.push(
        "",
        "## Digital-PCR run handoff",
        "",
        `- Platform: ${digital.platform_name}`,
        ...(digital.instrument_model ? [`- Instrument model: ${digital.instrument_model}`] : []),
        `- Partition format: ${digital.partition_format}`,
        `- Fragmentation: ${digital.fragmentation_state}`,
        `- Threshold status: ${digital.threshold_status}`,
        `- Quantification status: ${digital.quantification_status}`,
        `- Partition-volume authority: ${digital.partition_volume_authority_status}`,
        `- Analysis software/version: ${digital.analysis_software_version_status}`,
        `- Volume correction / VPF: ${digital.volume_precision_factor_status}`,
        ...(digital.current_platform_authority_reference
          ? [
              `- Current platform reference (not a substitute for run metadata): ${digital.current_platform_authority_reference.software_suite_reference}; ${digital.current_platform_authority_reference.volume_precision_factor_reference}`,
              `- Reference policy: ${digital.current_platform_authority_reference.authority_use}; ${digital.current_platform_authority_reference.inference_policy}`,
            ]
          : []),
        ...digital.required_run_evidence.map((item) => `- Required run evidence: ${item}`),
        `- ${digital.note}`,
      );
    }

    const diagnosticPairs = input.result.pairs
      .map((pair, index) => ({ pair, index }))
      .filter(({ pair }) => pair.quality || pair.uniformity || pair.thermodynamic_temperature_role);
    if (diagnosticPairs.length > 0) {
      lines.push("", "## Pair diagnostic context", "");
      for (const { pair, index } of diagnosticPairs) {
        const pieces = [`Pair ${index + 1}`];
        if (pair.quality) pieces.push(`heuristic quality ${pair.quality.score}/100`);
        if (pair.uniformity) {
          pieces.push(
            `GC uniformity ${pair.uniformity.min_window_gc}–${pair.uniformity.max_window_gc}% over ${pair.uniformity.window_bp}-bp windows`,
          );
        }
        if (pair.cross_dimer_temperature_c != null) {
          pieces.push(`cross-dimer model ${pair.cross_dimer_temperature_c} °C`);
        }
        lines.push(`- ${pieces.join(" · ")}`);
        if (pair.thermodynamic_temperature_role) {
          lines.push(`  - Temperature role: ${pair.thermodynamic_temperature_role}`);
        }
        if (pair.uniformity?.note) lines.push(`  - ${pair.uniformity.note}`);
      }
      lines.push(
        "- Quality is a reported heuristic beside the ranking score, not a universal validity threshold.",
      );
    }

    if (input.result.cloning?.applied) {
      const cloning = input.result.cloning;
      lines.push(
        "",
        "## Restriction-cloning boundary",
        "",
        `- Tail protocol: ${cloning.tail_protocol ?? "not recorded"}`,
        `- Strategy: ${cloning.strategy ?? "not recorded"}`,
        `- Directionality: ${cloning.directional == null ? "unresolved" : cloning.directional ? "directional" : "non-directional"}`,
        ...(cloning.insert_ends_compatible != null
          ? [
              `- Insert-end compatibility: ${cloning.insert_ends_compatible ? "compatible" : "incompatible"}; this is not a vector-directionality claim.`,
            ]
          : []),
        ...(cloning.insert_end_compatibility_scope
          ? [
              `- Compatibility scope: insert-end sequence geometry only; vector-end compatibility, ligation efficiency and hybrid-junction recleavage are not modeled.`,
            ]
          : []),
        ...(cloning.directionality_evidence
          ? [`- Directionality evidence boundary: ${cloning.directionality_evidence}.`]
          : []),
        ...(cloning.digest_validation
          ? [
              `- Methylation sensitivity: ${cloning.digest_validation.methylation_sensitivity_status}.`,
              `- Star-activity status: ${cloning.digest_validation.star_activity_status}.`,
              `- Double-digest compatibility: ${cloning.digest_validation.double_digest_compatibility_status}.`,
              `- Heat inactivation / cleanup: ${cloning.digest_validation.heat_inactivation_status}.`,
              `- Ligation-junction re-cleavage: ${cloning.digest_validation.ligation_junction_recleavage_status}.`,
              `- Enzyme-formulation scope: ${cloning.digest_validation.enzyme_formulation_scope}.`,
              ...cloning.digest_validation.required_records.map(
                (item) => `- Required digest record: ${item}`,
              ),
              `- Digest evidence boundary: ${cloning.digest_validation.note}`,
            ]
          : []),
        `- Protective-sequence authority: ${cloning.protective_sequence_authority ?? "not recorded"}`,
        ...(cloning.forward?.first_observed_activity_flanking_bases != null
          ? [
              `- Forward close-to-end evidence: ${cloning.forward.end_cleavage_evidence_identity ?? "supplier/formulation identity not recorded"}; first non-zero activity at ${cloning.forward.first_observed_activity_flanking_bases} flanking base(s), descriptive only.`,
            ]
          : []),
        ...(cloning.reverse?.first_observed_activity_flanking_bases != null
          ? [
              `- Reverse close-to-end evidence: ${cloning.reverse.end_cleavage_evidence_identity ?? "supplier/formulation identity not recorded"}; first non-zero activity at ${cloning.reverse.first_observed_activity_flanking_bases} flanking base(s), descriptive only.`,
            ]
          : []),
        ...cloning.bench_controls.map((item) => `- Bench control: ${item}`),
        ...(cloning.insert_boundary_contract
          ? [
              `- Insert boundary: ${cloning.insert_boundary_contract.mode}; product ${cloning.insert_boundary_contract.product_size_bp} bp; terminal primers required = ${cloning.insert_boundary_contract.terminal_primers_required ? "yes" : "no"}`,
              `- ${cloning.insert_boundary_contract.note}`,
            ]
          : []),
        `- ${cloning.note}`,
      );
    }
  }

  if (designs.length > 0) {
    lines.push("", "## Designs");
    for (const design of designs) {
      lines.push(...designSection(design));
    }
  }

  if (input.result.engine === "tiling-scheme") {
    const namedTiles = input.result.tiles.filter((tile) => tile.name);
    lines.push(
      "",
      "## Tiling scheme identity",
      "",
      `- Backend: ${String(input.result.primary_backend?.id ?? "historical/unknown")}${input.result.primary_backend?.configured_version ? ` ${String(input.result.primary_backend.configured_version)}` : ""}`,
      `- Lifecycle operation: ${input.result.lifecycle?.operation ?? "not recorded in historical result"}`,
      `- Scheme format: ${input.result.scheme_format}`,
      `- Reference: ${input.result.reference_id} · coordinates ${input.result.coordinate_system}`,
      `- Amplicon identities retained: ${namedTiles.length}/${input.result.tiles.length}`,
      ...(namedTiles.length > 0
        ? [
            `- Amplicons: ${namedTiles.map((tile) => `${tile.name} (pool ${tile.pool + 1})`).join(", ")}`,
          ]
        : ["- This saved result predates stable PrimalScheme3 amplicon-name retention."]),
    );
  }

  if (input.result.engine === "junction-primers") {
    const boundedFoldDiagnostics = input.result.junctions.filter(
      (junction) => junction.search?.fold_diagnostic_complete === false,
    );
    if (boundedFoldDiagnostics.length > 0) {
      lines.push("", "## Assembly fold-diagnostic boundary", "");
      for (const junction of boundedFoldDiagnostics) {
        lines.push(
          `- Junction ${junction.index}: ${junction.search?.fold_claim ?? "optional fold diagnostic incomplete"}`,
          "- The bounded fold diagnostic is review evidence only and did not become a hidden validity/ranking gate.",
        );
      }
    }
  }

  if (input.result.engine === "single-primer") {
    const adapterDiagnostics = input.result.primers
      .map((primer, index) => ({ primer, index }))
      .filter(({ primer }) => primer.adapter_dimer);
    if (adapterDiagnostics.length > 0) {
      lines.push("", "## RACE partner-interaction diagnostics", "");
      for (const { primer, index } of adapterDiagnostics) {
        const diagnostic = primer.adapter_dimer!;
        lines.push(
          `- Primer ${index + 1} vs ${diagnostic.partner}: ΔG ${diagnostic.dg} kcal/mol · Tm ${diagnostic.tm} °C · watch line ${diagnostic.watch_threshold_dg} kcal/mol · flagged=${diagnostic.flagged ? "yes" : "no"}`,
          `- Decision role: ${diagnostic.decision_role}; ${diagnostic.temperature_role}`,
          `- ${diagnostic.note}`,
        );
      }
    }
  }

  if (input.result.engine === "nested") {
    const notes = input.result.nests
      .map((nest, index) => ({ note: nest.tm_note, index }))
      .filter((entry): entry is { note: string; index: number } => Boolean(entry.note));
    if (notes.length > 0) {
      lines.push("", "## Nested-round Tm relationship", "");
      for (const entry of notes) {
        lines.push(`- Design ${entry.index + 1}: ${entry.note}`);
      }
    }
  }

  if (input.result.engine === "loop-set" && input.result.readout) {
    const readout = input.result.readout;
    lines.push(
      "",
      "## LAMP readout / detection boundary",
      "",
      `- Selection: ${readout.selection}`,
      `- Sequence-selection impact: ${readout.sequence_decision_impact}`,
      `- ${readout.note}`,
    );
  }

  if (input.result.engine === "loop-set") {
    const reaction = input.result.reaction;
    const model = input.result.parameter_set.thermodynamic_model;
    const diagnosticTemperature = reaction.diagnostic_structure_temperature_c;
    const historicalTemperature = reaction.screening_temperature_c ?? reaction.hold;
    lines.push(
      "",
      "## LAMP design-model boundary",
      "",
      `- Role/Tm design authority: ${model?.id ?? "not recorded in historical result"}`,
      ...(model
        ? [
            `- Tm reference: ${model.tm_reference}`,
            `- End-stability reference: ${model.end_stability_reference}`,
            `- Model role: ${model.role}`,
          ]
        : []),
      `- Structure-diagnostic temperature: ${diagnosticTemperature == null ? "not recorded in historical result" : `${diagnosticTemperature} °C`}`,
      ...(reaction.context_role ? [`- Diagnostic context role: ${reaction.context_role}`] : []),
      ...(reaction.context_note ? [`- ${reaction.context_note}`] : []),
      ...(diagnosticTemperature == null && historicalTemperature != null
        ? [
            `- Historical saved temperature field: ${historicalTemperature} °C; its older semantics are not silently reclassified as current design, diagnostic, or bench authority.`,
          ]
        : []),
    );
  }

  const protocol = selectedProtocolLines(input.result);
  if (protocol.length > 0) lines.push("", "## Selected protocol", "", ...protocol);

  if (input.result.engine === "outward-pair") {
    const contract = input.result.experiment_contract;
    lines.push(
      "",
      "## Preparation / claim boundary",
      "",
      `- Branch: ${contract.branch}`,
      `- Digest ends: ${contract.left_end_phosphate} / ${contract.right_end_phosphate}`,
      `- Circularization: ${contract.circularization_provenance}`,
      `- Linear control: ${contract.linear_control_provenance}`,
      `- Methylation branch: ${contract.methylation_branch}`,
      `- Result status: **${contract.result_status}**`,
      `- ${contract.status_semantics}`,
    );
  }

  // A sequence-only design must carry its experimental boundary into the
  // portable report. Keeping this outside the design loop makes it a property
  // of the run, not something a reader can mistake for a measured pair.
  if ("validation" in input.result && input.result.validation) {
    lines.push("", "## Required validation", "", "Status: in-silico only.");
    for (const requirement of input.result.validation.required) {
      lines.push(`- ${requirement}`);
    }
  }

  const orderability = effectiveOrderability(input.result);
  if (orderability && !orderability.orderable) {
    lines.push(
      "",
      "## Orderability",
      "",
      `Status: **${orderability.status}**`,
      `- ${orderability.note}`,
    );
  }

  // Every engine but consensus-pair produces one, so it is both the fallback
  // and the takeaway: the exact strings to send to an oligo house.
  const sheet = "order_sheet" in input.result ? input.result.order_sheet : [];
  if (
    (!orderability || orderability.orderable) &&
    !coveredByPairs(input.result) &&
    sheet.length > 0
  ) {
    lines.push("", "## What to order", "", table(sheet));
  }

  if (designs.length === 0 && sheet.length === 0) {
    const why = whyNothing(input.result);
    if (why) lines.push("", `> ${why}`);
    else lines.push("", "This run finished without designs to report.");
  }

  return `${lines.join("\n")}\n`;
}

function protocolSourceLine(
  identity: string | undefined,
  revision: string | undefined,
  date?: string | null,
  precision?: string | null,
): string {
  if (!identity && !revision) return "- Source provenance: not recorded in this historical result";
  if (identity && !revision) return `- Source: ${identity} · revision not published/recorded`;
  if (!identity && revision) return `- Source identity not recorded · revision ${revision}`;
  const dated = date ? ` · ${date}` : "";
  const precisionNote = precision && !date ? ` (${precision}-precision revision date)` : "";
  return `- Source: ${identity} · ${revision}${dated}${precisionNote}`;
}

/** Keep named kit overlays in the portable report beside, not inside, design geometry. */
function selectedProtocolLines(result: RunResult): string[] {
  if (result.engine === "nested" && result.protocol) {
    return [
      `- Carry-over selection: ${result.protocol.selection}`,
      `- Execution status: ${result.protocol.execution_status ?? "legacy-result-without-explicit-status"}`,
      `- ${result.protocol.note}`,
    ];
  }
  if (result.engine === "junction-primers" && result.protocol) {
    const protocol = result.protocol as unknown as JunctionProtocolForReport;
    return [
      `- ${protocol.selection} · ${protocol.reaction_volume_uL} µL`,
      protocolSourceLine(
        protocol.source_identity,
        typeof protocol.source_revision === "string" ? protocol.source_revision : undefined,
        undefined,
        protocol.source_revision_date_precision ?? null,
      ),
      `- ${protocol.fragment_count} fragments: ${protocol.total_fragment_input_pmol_min}–${protocol.total_fragment_input_pmol_max} pmol total`,
      `- Incubate at ${protocol.incubation.temperature_c} °C for ${protocol.incubation.minutes} min (${protocol.incubation.branch})`,
      `- ${protocol.insert_molar_excess}; unpurified PCR volume ≤${protocol.unpurified_pcr_fraction_max * 100}%`,
      `- ${protocol.note}`,
    ];
  }
  if (result.engine === "flanking-pair" && result.protocol) {
    const { protocol } = result;
    if (protocol.kind === "standard-pcr") {
      const reactionVolume =
        protocol.reaction_volume_uL == null
          ? "see named protocol"
          : typeof protocol.reaction_volume_uL === "number"
            ? `${protocol.reaction_volume_uL} µL`
            : Object.entries(protocol.reaction_volume_uL)
                .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value} µL`)
                .join(" · ");
      const primerValues = Object.values(protocol.primer_final_concentration_uM ?? {});
      const primerRange = primerValues.length
        ? `${Math.min(...primerValues)}${Math.min(...primerValues) === Math.max(...primerValues) ? "" : `–${Math.max(...primerValues)}`} µM documented values`
        : "see named protocol";
      const properties = protocol.polymerase_properties ?? {};
      return [
        `- ${protocol.selection}`,
        protocolSourceLine(
          protocol.source_publication,
          protocol.source_revision,
          protocol.source_revision_date,
          protocol.source_revision_date_precision ?? undefined,
        ),
        `- Reaction/provenance: ${reactionVolume} · primer ${primerRange}${protocol.magnesium_final_mM != null ? ` · Mg²⁺ ${protocol.magnesium_final_mM} mM` : ""}${protocol.dntp_each_mM != null ? ` · dNTP ${protocol.dntp_each_mM} mM each` : ""}.`,
        `- Polymerase behavior: proofreading ${String(properties.proofreading ?? "not recorded")} · hot start ${String(properties.hot_start ?? "not recorded")} · product end ${String(properties.product_end ?? "not recorded")}.`,
        `- Sequence-design impact: ${protocol.sequence_decision_impact}; thermodynamic-model impact: ${protocol.thermodynamic_model_impact}.`,
        `- Screening boundary: ${protocol.screening_context_note}`,
        ...(protocol.carryover_prevention
          ? [
              `- Carry-over/uracil state: dUTP supported=${String(protocol.carryover_prevention.dUTP_supported ?? "not recorded")} · UDG built in=${String(protocol.carryover_prevention.UDG_built_in ?? "not recorded")} · enabled by polymerase selection alone=${String(protocol.carryover_prevention.enabled_by_protocol_selection_alone ?? "not recorded")}.`,
              `- Carry-over/uracil boundary: ${String(protocol.carryover_prevention.note ?? "follow the named protocol and record actual dUTP/UDG state")}.`,
            ]
          : []),
        ...(protocol.downstream_cloning
          ? [
              `- Downstream product-end handoff: ${String(protocol.downstream_cloning.note ?? protocol.downstream_cloning.ta_cloning_direct ?? "verify the actual product-end state and cloning workflow")}.`,
            ]
          : []),
        ...(protocol.difficult_template
          ? [
              "- Difficult-template additives/enhancers remain named-protocol experiments; PCRStudio does not auto-select them from sequence GC alone.",
            ]
          : []),
        `- ${protocol.note}`,
      ];
    }
    if (protocol.kind === "rpa") {
      const mixing = protocol.agitation
        ? ` · agitate after ${protocol.agitation.after_minutes} min (${protocol.agitation.action})`
        : protocol.mixing
          ? ` · optional mixing ${protocol.mixing.optional_rpm} rpm (${protocol.mixing.effect})`
          : "";
      const magnesium =
        protocol.magnesium_acetate_mM !== undefined
          ? ` · ${protocol.magnesium_acetate_mM} mM magnesium acetate`
          : protocol.magnesium_chloride_mM !== undefined
            ? ` · ${protocol.magnesium_chloride_mM} mM MgCl2`
            : "";
      const rt = protocol.reverse_transcription
        ? `- RT-RPA: ${protocol.reverse_transcription.reverse_transcriptase} ${protocol.reverse_transcription.reverse_transcriptase_final_U_per_uL} U/µL · ${protocol.reverse_transcription.rnase_inhibitor} ${protocol.reverse_transcription.rnase_inhibitor_final_U_per_uL} U/µL · ${protocol.reverse_transcription.rnase_h} ${protocol.reverse_transcription.rnase_h_final_U_per_uL} U/µL · one-pot ${protocol.reverse_transcription.temperature_c} °C/${protocol.reverse_transcription.incubation_minutes} min`
        : undefined;
      return [
        `- ${protocol.selection}`,
        protocolSourceLine(
          protocol.source_publication,
          protocol.source_revision,
          protocol.source_revision_date,
          protocol.source_revision_date_precision,
        ),
        `- Starting point: primer preference ${protocol.primer_length_nt.rapid_preferred_min}–${protocol.primer_length_nt.rapid_preferred_max} nt · reviewed upper evidence boundary ${protocol.primer_length_nt.reviewed_upper_nt} nt · amplicon ${protocol.amplicon_bp.preferred_rapid_min}–${protocol.amplicon_bp.preferred_rapid_max} bp · reviewed context up to ${protocol.amplicon_bp.supported_context_max} bp`,
        `- Isothermal hold: ${protocol.temperature_c} °C for ${protocol.incubation_minutes} min${mixing} · ${protocol.primer_final_concentration_nM} nM primer each${magnesium}`,
        `- Primer-length note: ${protocol.primer_length_nt.below_preferred_note}`,
        ...(protocol.production_dna_warning
          ? [
              `- Production-DNA warning: ${protocol.production_dna_warning.contaminant}; supplier boundary: ${protocol.production_dna_warning.supplier_boundary}. PCRStudio does not infer organism identity from the FASTA; action: ${protocol.production_dna_warning.action}.`,
            ]
          : []),
        ...(protocol.contamination_control
          ? [`- Contamination-control handoff: ${protocol.contamination_control.note}`]
          : []),
        ...(rt ? [rt] : []),
        `- Sequence decision impact: ${protocol.sequence_decision_impact ?? "none"}; thermodynamic-model impact: ${protocol.thermodynamic_model_impact ?? "none"}`,
        `- Readout: ${protocol.readout}`,
        ...(protocol.readout_contract
          ? [
              `- Oligo/readout boundary: ${protocol.oligo_contract ?? "plain ACGT primers"}; modified-probe support=${protocol.modified_probe_support ? "yes" : "no"}; ${protocol.readout_contract}.`,
            ]
          : []),
        `- ${protocol.note}`,
      ];
    }
    if (protocol.kind === "digital-pcr") {
      const reactionVolume =
        typeof protocol.reaction_volume_uL === "number"
          ? `${protocol.reaction_volume_uL} µL`
          : Object.entries(protocol.reaction_volume_uL)
              .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value} µL`)
              .join(" · ");
      return [
        `- ${protocol.selection} · ${protocol.supermix}`,
        protocolSourceLine(
          protocol.source_publication,
          protocol.source_revision,
          protocol.source_revision_date,
          protocol.source_revision_date_precision,
        ),
        `- Reaction/partition: ${reactionVolume}${protocol.droplets_target ? ` · approximately ${protocol.droplets_target} target droplets` : protocol.partition_model ? ` · ${protocol.partition_model}` : ""}`,
        ...(protocol.amplicon_bp_preferred
          ? [
              `- Platform design preference: amplicon ${protocol.amplicon_bp_preferred.min}–${protocol.amplicon_bp_preferred.max} bp${protocol.primer_final_concentration_nM ? ` · primer ${Object.values(protocol.primer_final_concentration_nM).join("–")} nM documented range` : protocol.primer_final_concentration_uM != null ? ` · primer ${protocol.primer_final_concentration_uM} µM starting point` : ""}.`,
            ]
          : []),
        ...(protocol.constraints && Object.keys(protocol.constraints).length
          ? [
              `- Named design constraint envelope: ${Object.entries(protocol.constraints)
                .map(([key, value]) => `${key}=${value}`)
                .join(" · ")}.`,
            ]
          : []),
        ...(protocol.reverse_transcription
          ? [
              `- Named RT authority: one-step RT-dPCR · ${protocol.reverse_transcription.temperature_c} °C/${protocol.reverse_transcription.incubation_minutes} min · ${protocol.reverse_transcription.authority_status}.`,
            ]
          : []),
        ...(protocol.sequence_decision_impact
          ? [
              `- Sequence-design impact: ${protocol.sequence_decision_impact}; thermodynamic-model impact: ${protocol.thermodynamic_model_impact ?? "none"}.`,
            ]
          : []),
        `- Cycling handoff: ${protocol.cycling_summary ?? "follow the named platform protocol"}`,
        `- Readout: ${protocol.readout} · ${protocol.quantitation}`,
        `- ${protocol.note}`,
      ];
    }
    if (protocol.kind === "long-range-pcr") {
      const reactionVolume =
        typeof protocol.reaction_volume_uL === "number"
          ? `${protocol.reaction_volume_uL} µL`
          : Object.entries(protocol.reaction_volume_uL)
              .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value} µL`)
              .join(" · ");
      const primerValues = Object.values(protocol.primer_final_concentration_uM);
      const primerRange = primerValues.length
        ? `${Math.min(...primerValues)}${Math.min(...primerValues) === Math.max(...primerValues) ? "" : `–${Math.max(...primerValues)}`} µM documented value${primerValues.length === 1 ? "" : "s"}`
        : "see named protocol";
      const lifecycle =
        protocol.lifecycle.status === "discontinued"
          ? `discontinued${protocol.lifecycle.discontinued_date ? ` ${protocol.lifecycle.discontinued_date}` : ""}; silent substitution is not permitted`
          : "current named manufacturer branch";
      const cyclingModel = objectRecord(protocol.cycling_model);
      const branchSelection = objectRecord(cyclingModel?.branch_selection);
      const cyclingLines = [
        ...(typeof branchSelection?.supplier_rule === "string"
          ? [`- Supplier cycling rule: ${branchSelection.supplier_rule}`]
          : []),
        ...(cyclingModel?.two_step
          ? ["- Published two-step branch: retained as a named supplier cycling branch."]
          : []),
        ...(cyclingModel?.three_step
          ? ["- Published three-step branch: retained as a named supplier cycling branch."]
          : []),
        ...(typeof branchSelection?.selected_branch === "string"
          ? [`- Branch selection status: ${branchSelection.selected_branch}`]
          : []),
      ];
      return [
        `- ${protocol.selection} · kit ${protocol.kit_ids.join(" / ")}`,
        `- Source: ${protocol.source_publication} · ${protocol.source_revision}${protocol.source_revision_date ? ` · ${protocol.source_revision_date}` : ""} (${protocol.manual})`,
        `- Lifecycle: ${lifecycle}`,
        `- Reaction: ${reactionVolume} · primer ${primerRange}${protocol.magnesium_chloride_mM != null ? ` · MgCl₂ ${protocol.magnesium_chloride_mM} mM` : ""}${protocol.dntp_each_mM != null ? ` · dNTP ${protocol.dntp_each_mM} mM each` : ""}`,
        `- Cycling handoff: ${protocol.cycling_summary ?? "follow the named manufacturer protocol"}`,
        ...cyclingLines,
        ...(protocol.screening_thermodynamics
          ? [`- Thermodynamic boundary: ${protocol.screening_thermodynamics}.`]
          : []),
        ...(protocol.sequence_decision_impact
          ? [
              `- Sequence-design impact: ${protocol.sequence_decision_impact === "constraint-envelope" ? "named protocol narrows the reviewed primer constraint envelope; thermodynamic reaction model remains unchanged" : "none"}.`,
            ]
          : []),
        ...(protocol.constraints && Object.keys(protocol.constraints).length
          ? [
              `- Protocol constraint overlay: ${Object.entries(protocol.constraints)
                .map(([key, value]) => `${key}=${value}`)
                .join(" · ")}.`,
            ]
          : []),
        `- ${protocol.note}`,
      ];
    }
    // The only remaining flanking protocol kind is qPCR/SYBR. Keeping this
    // explicit prevents a future protocol shape from being silently rendered
    // as qPCR merely because it shares the flanking-pair engine.
    if (protocol.kind === "qpcr-sybr") {
      const reactionVolume =
        protocol.reaction_volume_uL == null
          ? undefined
          : typeof protocol.reaction_volume_uL === "number"
            ? `${protocol.reaction_volume_uL} µL`
            : Object.entries(protocol.reaction_volume_uL)
                .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value} µL`)
                .join(" · ");
      const primerConcentration = protocol.primer_final_concentration_nM;
      const primerText = primerConcentration
        ? primerConcentration.starting != null
          ? `${primerConcentration.starting} nM each starting point${
              primerConcentration.optimization_min != null &&
              primerConcentration.optimization_max != null
                ? ` · optimization ${primerConcentration.optimization_min}–${primerConcentration.optimization_max} nM each`
                : ""
            }`
          : primerConcentration.optimization_min != null &&
              primerConcentration.optimization_max != null
            ? `${primerConcentration.optimization_min}–${primerConcentration.optimization_max} nM each documented range`
            : undefined
        : undefined;
      const rt = protocol.reverse_transcription
        ? `- Named RT authority: ${protocol.reverse_transcription.reverse_transcriptase} · ${protocol.reverse_transcription.temperature_c} °C/${protocol.reverse_transcription.incubation_minutes} min · ${protocol.reverse_transcription.authority_status}`
        : undefined;
      return [
        `- ${protocol.selection} · ${protocol.master_mix}`,
        protocolSourceLine(
          protocol.source_publication,
          protocol.source_revision,
          protocol.source_revision_date,
          protocol.source_revision_date_precision,
        ),
        `- Preferred design window: amplicon ${protocol.amplicon_bp_preferred.min}–${protocol.amplicon_bp_preferred.max} bp · primer Tm target ${protocol.primer_tm_c.target} °C · ${protocol.cycles.min}–${protocol.cycles.max} cycle context at ${protocol.anneal_extend_c} °C`,
        ...(reactionVolume
          ? [`- Reaction: ${reactionVolume}${primerText ? ` · primer ${primerText}` : ""}`]
          : primerText
            ? [`- Primer: ${primerText}`]
            : []),
        ...(rt ? [rt] : []),
        ...(protocol.genomic_dna_control
          ? [
              `- RNA-specificity controls: no-RT=${protocol.genomic_dna_control.no_rt_control_recommended ? "recommended" : "not specified"} · NTC=${protocol.genomic_dna_control.no_template_control_recommended ? "recommended" : "not specified"} · exon-junction design recommended when annotated/appropriate=${String(protocol.genomic_dna_control.exon_exon_junction_design_recommended_when_annotated_and_appropriate)}.`,
              `- Genomic-DNA boundary: ${protocol.genomic_dna_control.note}`,
            ]
          : []),
        ...(protocol.carryover_prevention?.optional_udg_pretreatment
          ? [
              `- Optional carry-over branch: ${protocol.carryover_prevention.optional_UDG ?? "compatible UDG"} · ${protocol.carryover_prevention.optional_udg_pretreatment.temperature_c} °C/${protocol.carryover_prevention.optional_udg_pretreatment.minutes} min starting pretreatment; UDG built in=${String(protocol.carryover_prevention.UDG_built_in)}.`,
            ]
          : []),
        `- Readout: ${protocol.readout}`,
        `- ${protocol.note}`,
      ];
    }
  }
  if (result.engine === "loop-set" && result.protocol) {
    const { protocol } = result;
    const holdTemperature =
      protocol.hold_temperature_c != null
        ? `${protocol.hold_temperature_c} °C`
        : protocol.hold_temperature_range_c
          ? `${protocol.hold_temperature_range_c[0]}–${protocol.hold_temperature_range_c[1]} °C`
          : "not resolved";
    const holdTime =
      protocol.hold_time_min != null
        ? `${protocol.hold_time_min} min`
        : protocol.hold_time_range_min
          ? `${protocol.hold_time_range_min[0]}–${protocol.hold_time_range_min[1]} min`
          : "not resolved";
    const holdAuthority =
      holdTemperature === "not resolved" && holdTime === "not resolved"
        ? "bench hold not resolved"
        : `hold ${holdTemperature} for ${holdTime}`;
    return [
      `- ${protocol.selection} · kit ${protocol.kit_id}`,
      protocolSourceLine(
        protocol.source_identity,
        protocol.source_revision,
        protocol.source_revision_date,
        protocol.source_revision_date_precision,
      ),
      `- Reaction authority: ${protocol.reaction_volume_uL != null ? `${protocol.reaction_volume_uL} µL` : "volume not resolved"} · ${holdAuthority}`,
      protocol.primer_concentrations_uM
        ? `- Primer concentrations: ${Object.entries(protocol.primer_concentrations_uM)
            .map(([role, concentration]) => `${role} ${concentration} µM`)
            .join(" · ")}`
        : "- Primer concentrations: not asserted by this registry identity; use the cited protocol/formulation authority.",
      ...(protocol.carryover_prevention
        ? [
            `- Carry-over: ${protocol.carryover_prevention.included ? "built in" : "not built in"} · ${protocol.carryover_prevention.chemistry}. ${protocol.carryover_prevention.note}`,
          ]
        : []),
      ...(protocol.readout_compatibility
        ? [
            `- Readout compatibility: ${protocol.readout_compatibility.status} · ${protocol.readout_compatibility.note}`,
          ]
        : []),
      ...(protocol.readout_notes ?? []).map((note) => `- Readout note: ${note}`),
      ...(protocol.sample_compatibility_notes ?? []).map((note) => `- Sample note: ${note}`),
      ...(protocol.controls ?? []).map((note) => `- Control: ${note}`),
      ...(protocol.oligo_manufacturing_guidance
        ? [`- Oligo manufacturing: ${protocol.oligo_manufacturing_guidance}`]
        : []),
      `- Post-reaction handling: ${protocol.post_inactivation}`,
    ];
  }
  if (result.engine === "mutagenic-pair" && result.protocol) {
    const { protocol } = result;
    const pcr = protocol.pcr as Record<string, unknown>;
    const kld = protocol.kld as Record<string, unknown>;
    return [
      `- ${protocol.selection}`,
      protocolSourceLine(
        protocol.source_identity,
        typeof protocol.source_revision === "string" ? protocol.source_revision : undefined,
        undefined,
        typeof protocol.source_revision_date_precision === "string"
          ? protocol.source_revision_date_precision
          : null,
      ),
      `- Topology: ${protocol.topology}`,
      `- Q5 PCR contract: ${String(pcr.reaction_volume_uL ?? "not recorded")} µL · ${String(pcr.cycles ?? "not recorded")} cycles · primer ${String(pcr.primer_final_uM_each ?? "not recorded")} µM each`,
      `- KLD handoff: ${String(kld.room_temperature_minutes ?? "not recorded")} min at room temperature`,
      `- ${protocol.note}`,
    ];
  }
  if (result.engine === "discriminating-pair" && result.protocol) {
    const protocol = result.protocol as unknown as DiscriminatingProtocolForReport;
    return [
      `- ${protocol.selection} · ${protocol.plate_format}-well · ${protocol.reaction_volume_uL} µL · final DNA ${protocol.dna_final_ng_per_uL} ng/µL`,
      protocolSourceLine(protocol.source_identity, protocol.source_revision ?? undefined),
      ...(protocol.chemistry_identity
        ? [`- Chemistry identity: ${protocol.chemistry_identity}`]
        : []),
      `- Instrument: ${protocol.instrument_model ?? "not recorded"} · ROX/reference: ${protocol.rox_policy ?? "not recorded"}`,
      `- Mix: DNA ${protocol.dna_volume_uL ?? "not recorded"} µL · master mix ${protocol.master_mix_volume_uL ?? "not recorded"} µL · assay mix ${protocol.assay_mix_volume_uL ?? "not recorded"} µL`,
      `- ${protocol.touchdown.cycles} touchdown cycles (${protocol.touchdown.anneal_extend_start_c}–${protocol.touchdown.anneal_extend_final_c} °C), then ${protocol.amplification.cycles} cycles at ${protocol.amplification.anneal_extend_c} °C`,
      `- Readout: ${protocol.readout.channels.join(" / ")} · at least ${protocol.readout.ntc_minimum} NTC wells`,
      `- ${protocol.note}`,
    ];
  }
  if (result.engine === "single-primer" && result.protocol) {
    const { protocol } = result;
    const cycle = protocol.cycling;
    return [
      `- ${protocol.selection} · ${protocol.reaction_volumes_uL.join(" / ")} µL · primer ${protocol.primer_input_pmol} pmol`,
      `- Source: ${protocol.source_publication} · revision ${protocol.source_revision} · ${protocol.source_revision_date}`,
      `- Supplier-table boundary: ${protocol.supplier_table_ambiguity}`,
      `- ${cycle.cycles} cycles: ${cycle.initial_denature.temperature_c} °C initial denaturation, then ${cycle.denature.temperature_c} °C / ${cycle.anneal.temperature_c} °C / ${cycle.extend.temperature_c} °C; hold at ${cycle.hold_temperature_c} °C`,
      `- Template guidance: PCR product ${Object.entries(
        protocol.template_input.pcr_product_ng_by_length,
      )
        .map(([size, amount]) => `${size} ${amount} ng`)
        .join(", ")}; dsDNA ${protocol.template_input.double_stranded_dna_ng} ng`,
      `- Cleanup: ${protocol.cleanup_options.join(", ")}`,
      `- ${protocol.note}`,
    ];
  }
  if (result.engine === "single-primer" && result.race_adapter) {
    return [
      ...(result.race_direction ? [`- RACE transcript end: ${result.race_direction}`] : []),
      `- Named RACE partner: ${result.race_adapter.name}`,
      `- Adapter sequence: \`${result.race_adapter.sequence}\``,
      ...(result.race_adapter.protocol_identity
        ? [`- Protocol identity: ${result.race_adapter.protocol_identity}`]
        : []),
      ...(result.race_adapter.source_publication
        ? [`- Source publication: ${result.race_adapter.source_publication}`]
        : []),
      ...(result.race_adapter.source_identity
        ? [`- Source identity: ${result.race_adapter.source_identity}`]
        : []),
      ...(result.race_adapter.source_url
        ? [`- Source URL: ${result.race_adapter.source_url}`]
        : []),
      ...(result.race_adapter.source_reviewed_date
        ? [`- Source reviewed: ${result.race_adapter.source_reviewed_date}`]
        : []),
      ...(result.race_adapter.source_revision
        ? [`- Source revision: ${result.race_adapter.source_revision}`]
        : []),
      ...(result.race_adapter.source_revision_date
        ? [`- Source revision date: ${result.race_adapter.source_revision_date}`]
        : []),
      ...(result.race_context?.caller_sop_revision
        ? [`- Caller-reviewed SOP/manual revision: ${result.race_context.caller_sop_revision}`]
        : []),
      ...(result.race_context?.caller_sop_sha256
        ? [`- Caller-reviewed SOP/manual SHA-256: ${result.race_context.caller_sop_sha256}`]
        : []),
      ...(result.race_context?.polyadenylated !== undefined &&
      result.race_context?.polyadenylated !== null
        ? [`- Poly(A) explicitly confirmed: ${result.race_context.polyadenylated ? "yes" : "no"}`]
        : []),
      "- Adapter interaction was screened in silico; transcript-end identity and product interpretation remain experimental.",
    ];
  }
  if (result.engine === "single-primer" && result.race_direction) {
    return [`- RACE transcript end: ${result.race_direction}`];
  }
  if (result.engine === "pair-and-probe" && result.protocol) {
    const protocol = result.protocol as unknown as PairProbeProtocolForReport;
    return [
      `- ${protocol.selection} · ${protocol.probe_chemistry}`,
      ...(protocol.application_scope ? [`- Application scope: ${protocol.application_scope}`] : []),
      ...(protocol.source_identity
        ? [
            protocolSourceLine(
              protocol.source_identity,
              protocol.source_revision ?? undefined,
              protocol.source_revision_date,
              protocol.source_revision_date_precision ?? null,
            ),
          ]
        : ["- Source: historical saved result did not record protocol provenance"]),
      ...(protocol.source_documents ?? []).map(
        (source) =>
          `- Evidence source: ${source.identity}${source.publication ? ` · ${source.publication}` : ""}${source.revision ? ` · revision ${source.revision}` : ""}${source.revision_date ? ` · ${source.revision_date}` : ""} — ${source.supports.join("; ")}`,
      ),
      `- Primer / probe starting concentrations: ${protocol.primer_final_concentration_nM} / ${protocol.probe_final_concentration_nM} nM`,
      `- Starting windows: amplicon ${protocol.amplicon_bp.min}–${protocol.amplicon_bp.max} bp · primers ${protocol.primer_tm_c.min}–${protocol.primer_tm_c.max} °C · probe ${protocol.probe_tm_c.min}–${protocol.probe_tm_c.max} °C · MGB probe ${protocol.probe_length_nt.min}–${protocol.probe_length_nt.max} nt`,
      ...(protocol.primer_constraints
        ? [
            `- Protocol primer constraint ledger: ${Object.entries(protocol.primer_constraints)
              .map(([key, value]) => `${key}=${value}`)
              .join(" · ")}`,
          ]
        : []),
      ...(protocol.probe_constraints
        ? [
            `- Protocol probe constraint ledger: ${Object.entries(protocol.probe_constraints)
              .map(([key, value]) => `${key}=${value}`)
              .join(" · ")}`,
          ]
        : []),
      `- Reporter options: ${protocol.reporter_options.join(" / ")}; quencher: ${protocol.quencher}`,
      `- ${protocol.note}`,
    ];
  }
  return [];
}

/* ── Extraction, engine by engine ──────────────────────────────────────── */

function extract(result: RunResult): ReportedDesign[] {
  switch (result.engine) {
    case "flanking-pair": {
      const cloning = result.cloning?.applied ? result.cloning : null;
      return result.pairs.map((pair, index) => ({
        heading: `Pair ${index + 1}`,
        oligos: [
          oligo(
            "Forward",
            cloning?.forward
              ? { ...pair.left, sequence: cloning.forward.sequence + pair.left.sequence }
              : pair.left,
          ),
          oligo(
            "Reverse",
            cloning?.reverse
              ? { ...pair.right, sequence: cloning.reverse.sequence + pair.right.sequence }
              : pair.right,
          ),
        ],
        productSize: pair.product_size,
      }));
    }
    case "consensus-pair":
      return result.pairs.map((pair, index) => ({
        heading: `Pair ${index + 1}`,
        oligos: [degenerate("Forward", pair.left), degenerate("Reverse", pair.right)],
        productSize: pair.product_size,
      }));
    case "nested":
      return result.nests.flatMap((nest, index) => [
        round(`Nest ${index + 1}, outer round`, nest.outer),
        round(`Nest ${index + 1}, inner round`, nest.inner),
      ]);
    case "outward-pair":
      return result.pairs.map((pair, index) => ({
        heading: `Pair ${index + 1}`,
        oligos: [oligo("Forward", pair.left), oligo("Reverse", pair.right)],
        productSize: pair.product_size,
      }));
    case "pair-and-probe":
      return result.assays.map((assay, index) => ({
        heading: `Assay ${index + 1}`,
        oligos: [
          oligo("Forward", assay.left),
          oligo("Reverse", assay.right),
          oligo("Probe", assay.probe),
        ],
        productSize: assay.product_size,
      }));
    case "single-primer":
      return result.primers.map((primer, index) => ({
        heading: `Primer ${index + 1} (${primer.direction})`,
        oligos: [oligo("Primer", primer)],
        productSize: null,
      }));
    case "mutagenic-pair":
      return result.pairs.map((pair, index) => ({
        heading: `Pair ${index + 1}`,
        oligos: [oligo("Forward", pair.forward), oligo("Reverse", pair.reverse)],
        productSize: result.edit?.product_length ?? null,
      }));
    default:
      return [];
  }
}

function round(
  heading: string,
  entry: {
    left: { sequence: string; tm: number; gc_percent: number };
    right: { sequence: string; tm: number; gc_percent: number };
    product_size: number;
  },
): ReportedDesign {
  return {
    heading,
    oligos: [oligo("Forward", entry.left), oligo("Reverse", entry.right)],
    productSize: entry.product_size,
  };
}

function oligo(
  role: string,
  o: { sequence: string; tm: number; gc_percent: number },
): ReportedOligo {
  return { role, sequence: o.sequence, tm: `${o.tm} °C`, gc: `${o.gc_percent}%` };
}

/** A degenerate primer is a mixture: its Tm and GC are ranges, honestly. */
function degenerate(
  role: string,
  site: { sequence: string; tm_min: number; tm_max: number; gc_min: number; gc_max: number },
): ReportedOligo {
  return {
    role,
    sequence: site.sequence,
    tm: `${site.tm_min}–${site.tm_max} °C`,
    gc: `${site.gc_min}–${site.gc_max}%`,
  };
}

/* ── Sections ──────────────────────────────────────────────────────────── */

function designSection(design: ReportedDesign): string[] {
  const lines = ["", `### ${design.heading}`];
  for (const o of design.oligos) {
    lines.push(`- **${o.role}** \`${o.sequence}\` — Tm ${o.tm}, GC ${o.gc}`);
  }
  if (design.productSize !== null) {
    lines.push(`- Product size: ${design.productSize} bp`);
  }
  return lines;
}

/* ── Small pieces ──────────────────────────────────────────────────────── */

const dayOf = (iso: string): string => iso.slice(0, 10);

/** Whether extraction already wrote every oligo the order sheet would list. */
function coveredByPairs(result: RunResult): boolean {
  return (
    result.engine === "flanking-pair" ||
    result.engine === "consensus-pair" ||
    result.engine === "nested" ||
    result.engine === "outward-pair" ||
    result.engine === "pair-and-probe" ||
    result.engine === "single-primer" ||
    result.engine === "mutagenic-pair"
  );
}

function effectiveOrderability(
  result: RunResult,
): { orderable: boolean; status: string; note: string } | null {
  if ("orderability" in result && result.orderability) return result.orderability;
  if (result.engine === "pair-and-probe") {
    return {
      orderable: false,
      status: "historical-result-orderability-not-recorded",
      note: "This saved pair-and-probe result predates the current chemistry/orderability contract. Conventional Thermo Fisher/IDT branches are now executable only when the current authority and orderability fields are recorded; this historical result lacks that provenance, so saved supplier lines are evidence only and must not be used for ordering.",
    };
  }
  if (result.engine === "mutagenic-pair") {
    return {
      orderable: false,
      status: "historical-result-orderability-not-recorded",
      note: "This saved mutagenesis result predates the current named Q5/E0554 and orderability contract. Historical oligo lines are evidence only and must not be used for ordering until regenerated under the current worker.",
    };
  }
  if (result.engine === "tiling-scheme") {
    return {
      orderable: false,
      status: "historical-result-orderability-not-recorded",
      note: "This saved tiled-scheme result predates the current PrimalScheme3 orderability contract. Historical supplier lines are evidence only; regenerate with the current canonical backend before ordering.",
    };
  }
  if (result.engine === "junction-primers") {
    return {
      orderable: false,
      status: "historical-result-orderability-not-recorded",
      note: "This saved junction result predates the current named-protocol/orderability contract. Historical supplier lines are evidence only; regenerate under the current supported assembly protocol before ordering.",
    };
  }
  if (result.engine === "discriminating-pair") {
    return {
      orderable: false,
      status: "historical-result-orderability-not-recorded",
      note: "This saved discriminating-assay result predates the current completeness/orderability contract. Historical supplier lines are evidence only; regenerate with the current worker before ordering.",
    };
  }
  if (result.engine === "single-primer") {
    const assayId = result.assay?.id;
    if (assayId === "sequencing-primer" && !result.sequencing_context) {
      return {
        orderable: false,
        status: "historical-result-read-envelope-not-explicit",
        note: "This saved sequencing-primer result predates the current explicit read-envelope/handoff contract. Its supplier line is evidence only; regenerate after explicitly recording the provider read envelope before ordering.",
      };
    }
    if (assayId === "race" && (!result.race_context || !result.race_adapter)) {
      return {
        orderable: false,
        status: "historical-result-race-context-incomplete",
        note: "This saved RACE result predates the current versioned adapter/preparation contract. Its supplier line is evidence only; regenerate under a current named or explicit adapter branch before ordering.",
      };
    }
  }
  if (result.engine === "flanking-pair" && result.background && "clamp" in result.background) {
    return {
      orderable: false,
      status: "historical-result-specificity-v4",
      note: "This saved flanking-pair result carries the retired specificity-v4 clamp contract. Regenerate under mismatch-complete specificity-v5 before using any historical supplier lines.",
    };
  }
  return null;
}

function whyNothing(result: RunResult): string | null {
  const why = (result as { why_nothing?: unknown }).why_nothing;
  return typeof why === "string" && why ? why : null;
}

function table(
  sheet: readonly {
    name: string;
    sequence: string;
    length: number;
    gc_percent?: number;
    tm?: number;
  }[],
): string {
  const head = "| Name | Sequence (5′ → 3′) | nt | GC % | Tm °C |";
  const rule = "| --- | --- | --- | --- | --- |";
  const rows = sheet.map(
    (line) =>
      `| ${line.name} | \`${line.sequence}\` | ${line.length} | ${line.gc_percent ?? "not recorded"} | ${line.tm ?? "not recorded"} |`,
  );
  return [head, rule, ...rows].join("\n");
}
