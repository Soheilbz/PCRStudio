/**
 * Browser-side source-conditioned Flanking chemistry contract.
 *
 * Numeric authority is generated from the Python catalogue. This module only
 * resolves bench/reaction planning values; none of them may silently change
 * Primer3 candidate ranking.
 */
import numericCatalog from "./flanking-numeric-recipes.generated.json";

import protocolAuthority from "./flanking-protocol-authority.generated.json";

export type FlankingModuleId =
  "standard-pcr" | "long-range-pcr" | "colony-pcr" | "qpcr-sybr" | "digital-pcr" | "rpa";

export interface FlankingProtocolMetadata {
  module: string;
  label: string;
  vendor: string;
  status: string;
  source: string;
  source_url?: string;
  source_revision?: string;
  source_reviewed_date?: string;
  source_snapshot_status?: string;
  source_availability_scope?: string;
  source_kind?: string;
}

type NumericRule = {
  id: string;
  when?: Record<string, unknown>;
  set?: Record<string, number>;
  authority?: string;
};

const BASELINES = numericCatalog.baselines as unknown as Record<string, Record<string, number>>;
const RULES = numericCatalog.conditional_rules as unknown as Record<string, NumericRule[]>;
const RANGES = numericCatalog.optimization_envelopes as unknown as Record<
  string,
  Record<string, [number, number]>
>;
const UNRESOLVED = numericCatalog.unresolved_numeric_dependencies as Record<
  string,
  { id: string; note: string }[]
>;
const METADATA = numericCatalog.protocol_metadata as Record<string, FlankingProtocolMetadata>;
const REACTION_VOLUMES = numericCatalog.reaction_volume_options as Record<string, number[]>;
const DIGITAL_CONSUMABLE_PLATFORMS = protocolAuthority.compatibility
  .digital_consumable_platforms as Record<string, readonly string[]>;
const DIGITAL_PROTOCOL_PLATFORMS = protocolAuthority.compatibility
  .digital_protocol_platforms as Record<string, readonly string[]>;
const DIGITAL_PLATFORM_ROUTES = protocolAuthority.routing.digital_platforms as Record<
  string,
  string
>;

export const FLANKING_PROTOCOL_METADATA = METADATA;

export function flankingProtocolOptions(
  moduleId: string,
): Array<[string, FlankingProtocolMetadata]> {
  return Object.entries(METADATA)
    .filter(([, meta]) => meta.module === moduleId)
    .sort((a, b) => a[1].vendor.localeCompare(b[1].vendor) || a[1].label.localeCompare(b[1].label));
}

export interface FlankingNumericState {
  moduleId: FlankingModuleId;
  protocol: string;
  reactionVolumeUl?: string;
  primerEachUm?: string;
  primerEachNm?: string;
  gcEnhancerPercent?: string;
  additive?: string;
  cyclingProfile?: string;
  templateFractionPercent?: string;
  targetLengthKb?: string;
  partitionFormatDetail?: string;
  preparation?: string;
  initialDenaturationTimeMin?: string;
  rpaTemperatureC?: string;
  rpaTimeMin?: string;
  rpaBstUnitsPerUl?: string;
  rpaMultiplex?: boolean;
  templateInputNg?: string;
  templateInputUl?: string;
  templateClass?: string;
  hmwTemplateVerified?: boolean;
  qpcrInstrumentProfile?: string;
  digitalPlatformId?: string;
  digitalConsumableId?: string;
  effectivePartitionVolumeNl?: string;
  fragmentationEnzyme?: string;
  colonySampleInputUl?: string;
  fromRna?: boolean;
}

export interface FlankingNumericIssue {
  field: string;
  message: string;
}

export interface FlankingNumericPreview {
  protocol: string;
  module: string;
  values: Record<string, number>;
  origins: Record<string, string>;
  ranges: Record<string, [number, number]>;
  appliedOverlays: string[];
  unresolved: Array<{ id: string; note: string }>;
  issues: FlankingNumericIssue[];
  sequenceDecisionImpact: "none";
}

export interface FlankingNumericChange {
  key: string;
  kind: "added" | "removed" | "changed";
  before?: number;
  after?: number;
  reason?: string;
}

function numberValue(raw?: string): number | undefined {
  if (raw == null || !raw.trim()) return undefined;
  const value = Number(raw);
  return Number.isFinite(value) ? value : NaN;
}

function matches(rule: NumericRule, scenario: Record<string, unknown>): boolean {
  return Object.entries(rule.when ?? {}).every(([key, expected]) => scenario[key] === expected);
}

function setOverride(
  values: Record<string, number>,
  origins: Record<string, string>,
  ranges: Record<string, [number, number]>,
  key: string,
  raw: string | undefined,
  field: string,
  issues: FlankingNumericIssue[],
): void {
  const value = numberValue(raw);
  if (value === undefined) return;
  const range = ranges[key];
  if (!Number.isFinite(value) || !range || value! < range[0] || value! > range[1]) {
    issues.push({
      field,
      message: range
        ? `Value must remain within the source-backed ${range[0]}–${range[1]} range.`
        : "This exact product does not publish a reviewed editable range for this parameter.",
    });
    return;
  }
  values[key] = value!;
  origins[key] = "user-override-within-source-bound";
}

export function resolveFlankingNumericPreview(state: FlankingNumericState): FlankingNumericPreview {
  const protocol = state.protocol || "not-selected";
  const values = { ...(BASELINES[protocol] ?? {}) };
  const origins: Record<string, string> = Object.fromEntries(
    Object.keys(values).map((key) => [key, "product-baseline"]),
  );
  const ranges = structuredClone(RANGES[protocol] ?? {}) as Record<string, [number, number]>;
  const issues: FlankingNumericIssue[] = [];
  const meta = METADATA[protocol];
  if (protocol !== "not-selected" && (!meta || meta.module !== state.moduleId)) {
    issues.push({
      field: "protocol",
      message: `This chemistry belongs to ${meta?.module ?? "an unknown module"}, not ${state.moduleId}.`,
    });
  }
  if (
    state.additive === "high-gc-enhancer" &&
    !["neb-onetaq-hot-start-gc-m0485", "neb-onetaq-hot-start-quickload-gc-m0489"].includes(protocol)
  ) {
    issues.push({
      field: "flankingAdditive",
      message:
        "NEB High GC Enhancer is only source-backed for the reviewed OneTaq GC formulations.",
    });
  }
  if (state.additive === "yellow-sample-buffer" && protocol !== "thermo-powertrack-sybr-a46xxx") {
    issues.push({
      field: "flankingAdditive",
      message: "Yellow Sample Buffer is only source-backed in this catalogue for PowerTrack SYBR.",
    });
  }
  const scenario: Record<string, unknown> = {
    additive: state.additive,
    cycling_profile: state.cyclingProfile,
    preparation: state.preparation,
    partition_format_detail: state.partitionFormatDetail,
    initial_denaturation_time_min: numberValue(state.initialDenaturationTimeMin),
    multiplex: state.rpaMultiplex,
    from_rna: state.fromRna,
    qpcr_instrument_profile: state.qpcrInstrumentProfile,
    template_class: state.templateClass,
    hmw_template_verified: state.hmwTemplateVerified,
    digital_platform_id: state.digitalPlatformId,
    digital_consumable_id: state.digitalConsumableId,
    effective_partition_volume_nl: numberValue(state.effectivePartitionVolumeNl),
    fragmentation_enzyme: state.fragmentationEnzyme,
    colony_sample_input_ul: numberValue(state.colonySampleInputUl),
  };

  const targetLength = numberValue(state.targetLengthKb);
  if (
    protocol === "toyobo-kod-long-kml101" &&
    targetLength !== undefined &&
    Number.isFinite(targetLength)
  ) {
    scenario.target_length_class = targetLength! < 10 ? "under-10kb" : "10kb-or-more";
  }

  const appliedOverlays: string[] = [];
  for (const rule of RULES[protocol] ?? []) {
    if (!matches(rule, scenario)) continue;
    for (const [key, value] of Object.entries(rule.set ?? {})) {
      values[key] = value;
      origins[key] = `automatic:${rule.id}`;
    }
    appliedOverlays.push(rule.id);
  }

  setOverride(
    values,
    origins,
    ranges,
    "primer_each_uM",
    state.primerEachUm,
    "flankingPrimerEachUm",
    issues,
  );
  setOverride(
    values,
    origins,
    ranges,
    "primer_each_nM",
    state.primerEachNm,
    "flankingPrimerEachNm",
    issues,
  );
  setOverride(
    values,
    origins,
    ranges,
    "high_gc_enhancer_percent",
    state.gcEnhancerPercent,
    "flankingGcEnhancerPercent",
    issues,
  );
  if (protocol === "thermo-lyo-ready-rpa" || protocol === "gbiosciences-rpa-786-2155") {
    setOverride(
      values,
      origins,
      ranges,
      "hold_temperature_c",
      state.rpaTemperatureC,
      "rpaTemperatureC",
      issues,
    );
    setOverride(values, origins, ranges, "hold_time_min", state.rpaTimeMin, "rpaTimeMin", issues);
    if (protocol === "thermo-lyo-ready-rpa")
      setOverride(
        values,
        origins,
        ranges,
        "bst_polymerase_U_per_uL",
        state.rpaBstUnitsPerUl,
        "rpaBstUnitsPerUl",
        issues,
      );
  }
  if (protocol === "neb-onetaq-hotstart-m0488-colony") {
    setOverride(
      values,
      origins,
      ranges,
      "initial_denaturation_time_min",
      state.initialDenaturationTimeMin,
      "colonyInitialDenaturationMin",
      issues,
    );
  }

  const requestedVolume = numberValue(state.reactionVolumeUl);
  if (requestedVolume !== undefined) {
    const allowed = REACTION_VOLUMES[protocol] ?? [];
    if (!Number.isFinite(requestedVolume) || !allowed.includes(requestedVolume!)) {
      issues.push({
        field: "flankingReactionVolumeUl",
        message: allowed.length
          ? `Use one of the reviewed exact-product formats: ${allowed.join(", ")} µL.`
          : "No transferable reaction-volume choice is published for this exact product.",
      });
    } else {
      values.reaction_volume_uL = requestedVolume!;
      origins.reaction_volume_uL = "user-override-within-source-bound";
    }
  }

  if (values.reaction_volume_uL && values.master_mix_stock_x && values.master_mix_x_final != null) {
    values.master_mix_uL =
      (values.reaction_volume_uL * values.master_mix_x_final) / values.master_mix_stock_x;
    origins.master_mix_uL = "derived-stoichiometry";
  }
  if (
    values.reaction_volume_uL &&
    values.yellow_sample_buffer_stock_x &&
    values.yellow_sample_buffer_x_final != null
  ) {
    values.yellow_sample_buffer_uL =
      (values.reaction_volume_uL * values.yellow_sample_buffer_x_final) /
      values.yellow_sample_buffer_stock_x;
    origins.yellow_sample_buffer_uL = "derived-stoichiometry";
  }

  if (state.moduleId === "digital-pcr" && state.digitalConsumableId && state.digitalPlatformId) {
    const allowed =
      (DIGITAL_CONSUMABLE_PLATFORMS as Record<string, readonly string[]>)[
        state.digitalConsumableId
      ] ?? [];
    if (!allowed.includes(state.digitalPlatformId)) {
      issues.push({
        field: "digitalConsumableId",
        message: `The selected consumable is not source-backed for ${state.digitalPlatformId}.`,
      });
    }
  }

  if (
    state.moduleId === "digital-pcr" &&
    protocol &&
    protocol !== "not-selected" &&
    state.digitalPlatformId
  ) {
    const allowedPlatforms = DIGITAL_PROTOCOL_PLATFORMS[protocol];
    if (allowedPlatforms && !allowedPlatforms.includes(state.digitalPlatformId)) {
      issues.push({
        field: "digitalPlatformId",
        message: `The selected chemistry is not source-backed for ${state.digitalPlatformId}.`,
      });
    }
  }

  if (
    state.moduleId === "digital-pcr" &&
    state.digitalPlatformId &&
    DIGITAL_PLATFORM_ROUTES[state.digitalPlatformId] === "pair-probe"
  ) {
    issues.push({
      field: "digitalPlatformId",
      message:
        "This platform is recognized, but its current validated chemistry is probe-oriented; route this assay to Pair+Probe.",
    });
  }

  const qpcrProfile = state.qpcrInstrumentProfile ?? "";
  if (protocol === "qiagen-quantinova-sybr-208052") {
    if (qpcrProfile === "high-rox") {
      values.rox_working_dilution_x = 20;
      origins.rox_working_dilution_x = "automatic:quantinova-high-rox-instrument-profile";
    } else if (qpcrProfile === "low-rox") {
      values.rox_working_dilution_x = 200;
      origins.rox_working_dilution_x = "automatic:quantinova-low-rox-instrument-profile";
    } else if (qpcrProfile && !["no-rox", "capillary", "unresolved"].includes(qpcrProfile))
      issues.push({
        field: "qpcrInstrumentProfile",
        message: "QuantiNova requires a high-ROX, low-ROX, no-ROX or capillary profile.",
      });
  }
  if (
    protocol === "solis-hot-firepol-evagreen-rox" &&
    qpcrProfile &&
    !["high-rox", "low-rox", "rox-compatible"].includes(qpcrProfile)
  )
    issues.push({
      field: "qpcrInstrumentProfile",
      message: "The selected Solis ROX formulation requires a ROX-compatible instrument profile.",
    });
  if (protocol === "solis-hot-firepol-evagreen-norox" && qpcrProfile && qpcrProfile !== "no-rox")
    issues.push({
      field: "qpcrInstrumentProfile",
      message: "The selected Solis no-ROX formulation requires the no-ROX profile.",
    });
  if (
    protocol === "solis-hot-firepol-evagreen-capillary" &&
    qpcrProfile &&
    qpcrProfile !== "capillary"
  )
    issues.push({
      field: "qpcrInstrumentProfile",
      message: "The selected Solis capillary formulation requires the capillary profile.",
    });

  if (protocol === "thermo-powertrack-sybr-a46xxx") {
    ranges.template_fraction_percent = [10, 20];
    const fraction = numberValue(state.templateFractionPercent);
    if (fraction !== undefined) {
      if (!Number.isFinite(fraction) || fraction! < 10 || fraction! > 20) {
        issues.push({
          field: "flankingTemplateFractionPercent",
          message: "PowerTrack template fraction must remain within 10–20% of the reaction.",
        });
      } else {
        values.template_fraction_percent = fraction!;
        origins.template_fraction_percent = "user-override-within-source-bound";
      }
    }
  }

  if (protocol === "toyobo-kod-long-kml101" && targetLength !== undefined) {
    if (!Number.isFinite(targetLength) || targetLength! <= 0 || targetLength! > 50) {
      issues.push({
        field: "longRangeTargetLengthKb",
        message: "KOD Long target length must be >0 and ≤50 kb in this reviewed branch.",
      });
    } else {
      const perKb = targetLength! < 10 ? 5 : 10;
      values.target_length_kb = targetLength!;
      values.extension_seconds_per_kb = perKb;
      values.extension_time_sec = targetLength! * perKb;
      origins.target_length_kb = "user-reviewed-context";
      origins.extension_seconds_per_kb = "automatic:kod-long-length-regime";
      origins.extension_time_sec = "derived-stoichiometry";
    }
  }

  if (protocol === "promega-gotaq-long-m4021" && targetLength !== undefined) {
    const ceiling = ["plasmid", "lambda", "lower-complexity"].includes(state.templateClass ?? "")
      ? 40
      : 30;
    if (!Number.isFinite(targetLength) || targetLength! < 5 || targetLength! > ceiling) {
      issues.push({
        field: "longRangeTargetLengthKb",
        message: `GoTaq Long target length must remain within 5–${ceiling} kb for the selected template class.`,
      });
    } else {
      values.target_length_kb = targetLength!;
      values.extension_minutes_per_kb = 1;
      values.extension_time_min = targetLength!;
      origins.target_length_kb = "user-reviewed-context";
      origins.extension_time_min = "derived-stoichiometry";
    }
  }

  const unresolved = [...(UNRESOLVED[protocol] ?? [])];
  if (
    [
      "qiagen-quantinova-sybr-208052",
      "solis-hot-firepol-evagreen-rox",
      "solis-hot-firepol-evagreen-norox",
      "solis-hot-firepol-evagreen-capillary",
    ].includes(protocol) &&
    !qpcrProfile
  )
    unresolved.push({
      id: "qpcr-instrument-profile",
      note: "Choose the instrument/reference-dye profile to validate ROX/no-ROX/capillary compatibility.",
    });
  if (protocol === "promega-gotaq-long-m4021" && targetLength === undefined)
    unresolved.push({
      id: "gotaq-long-target-length",
      note: "Record target length to resolve the source-backed ~1 min/kb extension time.",
    });
  if (protocol === "promega-gotaq-long-m4021" && !state.templateClass)
    unresolved.push({
      id: "gotaq-long-template-class",
      note: "Record genomic/HMW genomic versus plasmid/lambda/lower-complexity template class because the documented reach differs.",
    });
  if (
    protocol === "neb-onetaq-hotstart-m0488-colony" &&
    numberValue(state.initialDenaturationTimeMin) === undefined
  ) {
    unresolved.push({
      id: "m0488-colony-lysis-time",
      note: "Choose a source-backed 2–5 minute initial denaturation/lysis time for M0488 colony PCR.",
    });
  }
  if (
    protocol === "thermo-powertrack-sybr-a46xxx" &&
    !["fast", "standard"].includes(state.cyclingProfile ?? "")
  ) {
    unresolved.push({
      id: "powertrack-cycling-profile",
      note: "Choose the source-backed fast or standard cycling branch; PCRStudio does not invent one.",
    });
  }
  if (protocol === "toyobo-kod-long-kml101" && targetLength === undefined) {
    unresolved.push({
      id: "kod-long-target-length",
      note: "Target length is required to resolve the source-backed 5 s/kb versus 10 s/kb extension branch.",
    });
  }
  if (
    ["qiagen-qiacuity-eg", "qiagen-qiacuity-onestep-advanced-eg"].includes(protocol) &&
    !["8.5k", "26k"].includes(state.partitionFormatDetail ?? "")
  ) {
    unresolved.push({
      id: "qiacuity-nanoplate-format",
      note: "Choose 8.5k or 26k Nanoplate format before PCRStudio resolves reaction volume.",
    });
  }

  return {
    protocol,
    module: state.moduleId,
    values,
    origins,
    ranges,
    appliedOverlays,
    unresolved,
    issues,
    sequenceDecisionImpact: "none",
  };
}

export function diffFlankingNumericPreview(
  previous: FlankingNumericPreview | undefined,
  current: FlankingNumericPreview,
): FlankingNumericChange[] {
  if (!previous) return [];
  const keys = new Set([...Object.keys(previous.values), ...Object.keys(current.values)]);
  const changes: FlankingNumericChange[] = [];
  for (const key of [...keys].sort()) {
    const before = previous.values[key];
    const after = current.values[key];
    if (before === after) continue;
    changes.push({
      key,
      kind: before === undefined ? "added" : after === undefined ? "removed" : "changed",
      before,
      after,
      reason: after === undefined ? undefined : current.origins[key],
    });
  }
  return changes;
}

export function flankingNumericLabel(key: string): string {
  const labels: Record<string, string> = {
    reaction_volume_uL: "Reaction volume (µL)",
    master_mix_uL: "Master mix (µL)",
    master_mix_x_final: "Master mix final (X)",
    primer_each_uM: "Each primer (µM)",
    primer_each_nM: "Each primer (nM)",
    magnesium_mM: "Mg²⁺ (mM)",
    dntp_each_mM: "Each dNTP (mM)",
    dntp_total_mM: "Total dNTP (mM)",
    polymerase_units: "Polymerase (U/reaction)",
    cycles: "Cycles",
    high_gc_enhancer_percent: "High-GC enhancer (%)",
    yellow_sample_buffer_uL: "Yellow Sample Buffer (µL)",
    template_fraction_percent: "Template fraction (%)",
    extension_seconds_per_kb: "Extension (s/kb)",
    extension_time_sec: "Extension time (s)",
    hold_temperature_c: "Hold temperature (°C)",
    hold_time_min: "Hold time (min)",
    initial_denaturation_temperature_c: "Initial denaturation (°C)",
    initial_denaturation_time_min: "Initial denaturation (min)",
    liquid_culture_input_uL: "Overnight culture input (µL)",
    uvsx_mg_per_mL: "UvsX (mg/mL)",
    uvsy_mg_per_mL: "UvsY (mg/mL)",
    gene32_mg_per_mL: "Gene32 / SSB (mg/mL)",
    bst_polymerase_U_per_uL: "Bst polymerase (U/µL)",
    reverse_transcriptase_U_per_uL: "Reverse transcriptase (U/µL)",
    rnase_inhibitor_U_per_uL: "RNase inhibitor (U/µL)",
    rnase_h_U_per_uL: "RNase H (U/µL)",
  };
  return labels[key] ?? key.replaceAll("_", " ");
}
