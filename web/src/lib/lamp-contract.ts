/**
 * Browser-side LAMP scenario + conditional numeric contract.
 *
 * Compatibility facts mirror Python/Rust fail-closed contracts. Numeric facts
 * are generated directly from the canonical Python numeric authority. Neither
 * compatibility nor bench chemistry is allowed to silently change sequence
 * ranking.
 */
import numericCatalog from "./lamp-numeric-recipes.generated.json";
import { LAMP_PROTOCOL_METADATA, LAMP_AUTHORITY } from "./lamp-protocol-authority.generated";

type LampProtocolMetadata = {
  supports_dna?: boolean;
  supports_rna?: boolean;
  formats?: readonly string[];
  direct_sample_matrices?: readonly string[];
  forbidden_readouts?: Readonly<Record<string, string>>;
  forbidden_readout_chemistries?: Readonly<Record<string, string>>;
};
const protocolEntries = Object.entries(
  LAMP_PROTOCOL_METADATA as unknown as Record<string, LampProtocolMetadata>,
);
export const LAMP_DNA_ONLY_PROTOCOLS = new Set(
  protocolEntries.filter(([, r]) => r.supports_dna && !r.supports_rna).map(([id]) => id),
);
export const LAMP_RNA_ONLY_PROTOCOLS = new Set(
  protocolEntries.filter(([, r]) => r.supports_rna && !r.supports_dna).map(([id]) => id),
);
export const LAMP_DIRECT_SAMPLE_AUTHORITY: Readonly<Record<string, string>> = Object.fromEntries(
  protocolEntries.flatMap(([id, r]) =>
    (r.direct_sample_matrices ?? []).slice(0, 1).map((matrix) => [id, matrix]),
  ),
);
const LAMP_PROTOCOL_FORMULATIONS: Readonly<Record<string, readonly string[]>> = Object.fromEntries(
  protocolEntries.map(([id, r]) => [id, r.formats ?? ["liquid"]]),
);
export const LAMP_CHEMISTRY_BRANCH: Readonly<Record<string, string>> = LAMP_AUTHORITY.compatibility
  .readout_chemistry_branch as Readonly<Record<string, string>>;
const LAMP_FORBIDDEN_READOUTS: Readonly<Record<string, readonly string[]>> = Object.fromEntries(
  protocolEntries
    .filter(([, r]) => Object.keys(r.forbidden_readouts ?? {}).length)
    .map(([id, r]) => [id, Object.keys(r.forbidden_readouts ?? {})]),
);
const LAMP_FORBIDDEN_READOUT_CHEMISTRIES: Readonly<Record<string, readonly string[]>> =
  Object.fromEntries(
    protocolEntries
      .filter(([, r]) => Object.keys(r.forbidden_readout_chemistries ?? {}).length)
      .map(([id, r]) => [id, Object.keys(r.forbidden_readout_chemistries ?? {})]),
  );

export const LAMP_BENCH_FIELD_MAP = [
  ["lampOptMagnesium", "magnesium_mM", "Mg²⁺ (mM)"],
  ["lampOptDntpEach", "dntp_each_mM", "dNTP each (mM)"],
  ["lampOptBetaine", "betaine_M", "Betaine (M)"],
  ["lampOptPolymeraseUnits", "polymerase_units", "Polymerase units"],
  ["lampOptRtUnits", "rt_units", "RT units"],
  ["lampOptFipBip", "fip_bip_uM", "FIP/BIP (µM)"],
  ["lampOptF3B3", "f3_b3_uM", "F3/B3 (µM)"],
  ["lampOptLoop", "loop_uM", "LF/LB (µM)"],
  ["lampOptTemperature", "hold_temperature_c", "Hold temperature (°C)"],
  ["lampOptTime", "hold_time_min", "Hold time (min)"],
  ["lampOptGuanidine", "guanidine_mM", "Guanidine (mM)"],
  ["lampOptDyeX", "fluorescent_dye_x", "Fluorescent dye (X)"],
] as const;
export type LampBenchWireField = (typeof LAMP_BENCH_FIELD_MAP)[number][0];
export type LampBenchKey = (typeof LAMP_BENCH_FIELD_MAP)[number][1];

type NumericRule = {
  id: string;
  when?: Record<string, unknown>;
  set?: Record<string, number>;
  unset?: string[];
  ranges?: Record<string, [number, number]>;
  authority?: string;
};
const NUMERIC_BASELINES = numericCatalog.effective_baselines as unknown as Record<
  string,
  Record<string, number>
>;
const NUMERIC_RULES = numericCatalog.conditional_rules as unknown as Record<string, NumericRule[]>;
const NUMERIC_ENVELOPES = numericCatalog.optimization_envelopes as unknown as Record<
  string,
  Partial<Record<LampBenchKey, [number, number]>>
>;
const NUMERIC_SAMPLE_LIMITS = numericCatalog.sample_input_limits as unknown as Record<
  string,
  Record<string, number>
>;
const NUMERIC_PROFILES = numericCatalog.primer_kinetics_profiles as unknown as Record<
  string,
  Record<string, number>
>;
const NUMERIC_UNRESOLVED = numericCatalog.unresolved_numeric_dependencies as unknown as Record<
  string,
  { id: string; when?: string; note: string }[]
>;

function namedProtocol(protocol: string) {
  return Boolean(protocol && protocol !== "not-selected");
}
export function lampProtocolSupportsSubstrate(protocol: string, fromRna: boolean) {
  if (!namedProtocol(protocol)) return true;
  return fromRna ? !LAMP_DNA_ONLY_PROTOCOLS.has(protocol) : !LAMP_RNA_ONLY_PROTOCOLS.has(protocol);
}
export function lampProtocolFormulationAllowed(protocol: string, formulation: string) {
  if (!formulation || formulation === "not-specified") return true;
  if (!namedProtocol(protocol)) return false;
  return (LAMP_PROTOCOL_FORMULATIONS[protocol] ?? ["liquid"]).includes(formulation);
}
export function lampProtocolDirectMatrix(protocol: string) {
  return LAMP_DIRECT_SAMPLE_AUTHORITY[protocol];
}
export function lampProtocolForbidsReadout(protocol: string, readout: string) {
  return (LAMP_FORBIDDEN_READOUTS[protocol] ?? []).includes(readout);
}
export function lampProtocolForbidsChemistry(protocol: string, chemistry: string) {
  return (LAMP_FORBIDDEN_READOUT_CHEMISTRIES[protocol] ?? []).includes(chemistry);
}
export function lampReadoutChemistryBranch(chemistry: string) {
  return LAMP_CHEMISTRY_BRANCH[chemistry];
}
export function lampBenchOptimizationRange(
  protocol: string,
  key: LampBenchKey,
): readonly [number, number] | undefined {
  return NUMERIC_ENVELOPES[protocol]?.[key];
}

export interface LampScenarioState {
  protocol: string;
  fromRna: boolean;
  matrix: string;
  preparation: string;
  formulation: string;
  readout: string;
  chemistry: string;
  designIntent?: string;
  inclusivity?: string;
  benchValues?: Partial<Record<LampBenchWireField, string>>;
  carryoverStrategy?: string;
  reconstitutionX?: string;
  specificityAdditive?: string;
  accelerationAdditive?: string;
  primerKineticsProfile?: string;
  preincubationStrategy?: string;
  sampleInputPercent?: string;
  sampleBufferType?: string;
  sampleBufferPh?: string;
  sampleBufferPercent?: string;
  transportMediumPercent?: string;
  bileSaltMgMl?: string;
  caryBlairPercent?: string;
  upstreamGuanidineMm?: string;
  instrumentProfile?: string;
}
export interface LampScenarioIssue {
  field: string;
  message: string;
}
export type LampScenarioIssueOwner = "reaction" | "specificity";
export function lampScenarioIssueOwner(issue: LampScenarioIssue): LampScenarioIssueOwner {
  return issue.field === "inclusivity" ? "specificity" : "reaction";
}

const value = (raw: string | undefined) => {
  if (raw == null || !raw.trim()) return undefined;
  const n = Number(raw);
  return Number.isFinite(n) ? n : NaN;
};

export function lampScenarioIssues(state: LampScenarioState): LampScenarioIssue[] {
  const issues: LampScenarioIssue[] = [];
  const direct =
    state.preparation === "direct-addition" || state.preparation === "koh-lyse-and-lamp";
  const authority = lampProtocolDirectMatrix(state.protocol);
  if (!lampProtocolSupportsSubstrate(state.protocol, state.fromRna))
    issues.push({
      field: "lampProtocol",
      message: state.fromRna
        ? "The selected named chemistry is DNA-only; choose an RT-LAMP-capable protocol for RNA input."
        : "The selected named chemistry is RNA-only; choose a DNA-capable LAMP protocol for DNA input.",
    });
  if (!lampProtocolFormulationAllowed(state.protocol, state.formulation))
    issues.push({
      field: state.protocol ? "lampFormulation" : "lampProtocol",
      message: state.protocol
        ? "The selected formulation is outside the reviewed authority for this named protocol."
        : "An explicit formulation requires a named reviewed LAMP protocol.",
    });
  if (direct) {
    if (!namedProtocol(state.protocol))
      issues.push({
        field: "lampProtocol",
        message: "Direct-sample LAMP requires a named reviewed protocol authority.",
      });
    else if (!authority)
      issues.push({
        field: "lampSamplePreparation",
        message: "The selected named protocol has no reviewed direct-sample authority.",
      });
    else if (["not-specified", "crude-unspecified"].includes(state.matrix))
      issues.push({
        field: "lampSampleMatrix",
        message: "Direct-sample LAMP requires an explicit reviewed specimen matrix.",
      });
    else if (authority !== state.matrix)
      issues.push({
        field: "lampSampleMatrix",
        message: `This direct protocol is reviewed for ${authority}, not ${state.matrix}.`,
      });
    if (state.preparation === "koh-lyse-and-lamp" && state.matrix !== "koh-lysate")
      issues.push({
        field: "lampSampleMatrix",
        message: "KOH Lyse & LAMP requires the KOH-lysate matrix branch.",
      });
  }
  if (lampProtocolForbidsReadout(state.protocol, state.readout))
    issues.push({
      field: "lampReadout",
      message: "The selected exact product formulation excludes this readout branch.",
    });
  if (lampProtocolForbidsChemistry(state.protocol, state.chemistry))
    issues.push({
      field: "lampReadoutChemistry",
      message:
        state.protocol === "neb-m1712"
          ? "HNB is disabled for M1712 because the reviewed authority reports poor contrast."
          : "The selected exact product excludes pyrophosphate-turbidity chemistry.",
    });
  const branch = lampReadoutChemistryBranch(state.chemistry);
  if (
    state.chemistry !== "not-specified" &&
    state.readout !== "not-specified" &&
    branch !== state.readout
  )
    issues.push({
      field: "lampReadoutChemistry",
      message: `The selected exact readout chemistry belongs to ${branch ?? "an unresolved"} branch, not ${state.readout}.`,
    });
  if (state.designIntent === "panel-conservation-aware" && !state.inclusivity?.trim())
    issues.push({
      field: "inclusivity",
      message: "Panel-conservation-aware LAMP requires an explicit inclusivity panel.",
    });
  if (
    state.carryoverStrategy &&
    state.carryoverStrategy !== "protocol-default" &&
    !["neb-m9204", "neb-m9205"].includes(state.protocol)
  )
    issues.push({
      field: "lampCarryoverStrategy",
      message: "The numeric dUTP/UDG overlay is reviewed only for M9204/M9205.",
    });
  if (
    state.reconstitutionX &&
    state.reconstitutionX !== "protocol-default" &&
    state.protocol !== "neb-l4401"
  )
    issues.push({
      field: "lampReconstitutionX",
      message: "Explicit 2X/4X reconstitution authority is reviewed only for L4401.",
    });
  if (
    state.specificityAdditive &&
    state.specificityAdditive !== "none" &&
    state.protocol !== "neb-e1700"
  )
    issues.push({
      field: "lampSpecificityAdditive",
      message: "The Tte UvrD starting amount is scoped to the reviewed E1700 example.",
    });
  if (
    state.accelerationAdditive &&
    state.accelerationAdditive !== "none" &&
    (!["neb-m1800", "neb-m1804"].includes(state.protocol) || state.readout !== "colorimetric")
  )
    issues.push({
      field: "lampAccelerationAdditive",
      message:
        "40 mM guanidine acceleration is reviewed only for NEB M1800/M1804 pH-colorimetric LAMP.",
    });
  if (
    state.primerKineticsProfile &&
    state.primerKineticsProfile !== "protocol-default" &&
    !["optigene-iso001", "optigene-iso001-rt", "optigene-iso004", "optigene-iso004-rt"].includes(
      state.protocol,
    )
  )
    issues.push({
      field: "lampPrimerKineticsProfile",
      message:
        "This primer concentration profile is reviewed only for OptiGene ISO-001/ISO-004 liquid branches.",
    });
  if (
    state.preincubationStrategy &&
    state.preincubationStrategy !== "protocol-default" &&
    state.protocol !== "takara-rr385"
  )
    issues.push({
      field: "lampPreincubationStrategy",
      message: "The 25°C/10 min pre-incubation branch is specific to Takara RR385.",
    });
  if (
    state.chemistry === "eiken-fd-lmp221" &&
    !["eiken-lmp204", "eiken-lmp207", "eiken-lmp244"].includes(state.protocol)
  )
    issues.push({
      field: "lampReadoutChemistry",
      message: "Eiken LMP221 reagent is source-backed only for the reviewed Eiken kit branches.",
    });
  if (
    state.chemistry === "eiken-fd-lmp221" &&
    ["te", "chelating-other"].includes(state.sampleBufferType ?? "")
  )
    issues.push({
      field: "lampSampleBufferType",
      message:
        "Eiken LMP221 is incompatible with TE/chelating buffer context because Mn chelation can release calcein.",
    });
  if (state.instrumentProfile?.startsWith("vazyme-") && state.protocol !== "vazyme-rp711")
    issues.push({
      field: "lampInstrumentProfile",
      message: "Vazyme instrument-conditioned dye values require RP711.",
    });
  if (state.instrumentProfile === "agdia-amplifire" && state.protocol !== "agdia-lmx54700")
    issues.push({
      field: "lampInstrumentProfile",
      message: "The AmpliFire numeric run profile is source-backed here only for Agdia LMX 54700.",
    });
  const numericContext = [
    state.sampleBufferPh,
    state.sampleBufferPercent,
    state.upstreamGuanidineMm,
  ].some((x) => x != null && x.trim());
  if (
    numericContext &&
    (!["neb-m1800", "neb-m1804"].includes(state.protocol) || state.readout !== "colorimetric")
  )
    issues.push({
      field: "lampSampleBufferType",
      message:
        "Sample pH/buffer fraction and upstream guanidine numeric authority is scoped to NEB pH-colorimetric LAMP.",
    });
  const samplePct = value(state.sampleInputPercent);
  const limit = NUMERIC_SAMPLE_LIMITS[state.protocol]?.[state.matrix];
  if (samplePct !== undefined) {
    if (!Number.isFinite(samplePct) || limit === undefined || samplePct < 0 || samplePct > limit)
      issues.push({
        field: "lampSampleInputPercent",
        message:
          limit === undefined
            ? "No reviewed exact-product sample-input percentage is published for this protocol/matrix."
            : `Sample input must remain within 0–${limit}% final for this exact product/matrix.`,
      });
  }
  const transport = value(state.transportMediumPercent);
  if (
    transport !== undefined &&
    (!["meridian-mdx134", "meridian-mdx135"].includes(state.protocol) ||
      !Number.isFinite(transport) ||
      transport < 0 ||
      transport > 50)
  )
    issues.push({
      field: "lampTransportMediumPercent",
      message: "Transport-medium percentage is reviewed only up to 50% for MDX134/MDX135.",
    });
  const bile = value(state.bileSaltMgMl);
  if (
    bile !== undefined &&
    (state.protocol !== "meridian-mdx144" || !Number.isFinite(bile) || bile < 0 || bile > 2)
  )
    issues.push({
      field: "lampBileSaltMgMl",
      message: "Bile-salt numeric authority is reviewed only for MDX144 up to 2 mg/mL.",
    });
  const cary = value(state.caryBlairPercent);
  if (
    cary !== undefined &&
    (state.protocol !== "meridian-mdx144" || !Number.isFinite(cary) || cary < 0 || cary > 40)
  )
    issues.push({
      field: "lampCaryBlairPercent",
      message: "Cary-Blair numeric authority is reviewed only for MDX144 up to 40%.",
    });
  for (const [wire, key] of LAMP_BENCH_FIELD_MAP) {
    const raw = state.benchValues?.[wire]?.trim();
    if (!raw) continue;
    const range = lampBenchOptimizationRange(state.protocol, key);
    if (!range) {
      issues.push({
        field: wire,
        message: state.protocol
          ? "This named protocol does not publish a reviewed optimization envelope for this parameter."
          : "Bench optimization requires a named reviewed protocol authority.",
      });
      continue;
    }
    const n = Number(raw);
    if (!Number.isFinite(n) || n < range[0] || n > range[1])
      issues.push({
        field: wire,
        message: `Value must remain within the reviewed ${range[0]}–${range[1]} envelope for this protocol.`,
      });
  }
  return issues;
}

export interface LampThermalStage {
  id: string;
  temperature_c?: number;
  time_min?: number;
  authority: string;
  required_by_selection: boolean;
}
export interface LampNumericPreview {
  values: Record<string, number>;
  origins: Record<string, string>;
  ranges: Record<string, [number, number]>;
  appliedOverlays: string[];
  unresolved: { id: string; note: string }[];
  thermalStages?: LampThermalStage[];
  thermalStageModel?: "ordered-source-backed-only";
  sequenceDecisionImpact?: "none";
}

export interface LampNumericChange {
  key: string;
  previous?: number;
  next?: number;
  origin?: string;
}

/**
 * Explain numeric recipe movement without introducing a second resolver.
 *
 * The UI uses this after a user changes product/readout/instrument/context.
 * Only resolved numeric values are compared; the current resolver remains the
 * single authority for both the number and its provenance.
 */
export function diffLampNumericPreview(
  previous: LampNumericPreview | null | undefined,
  current: LampNumericPreview,
): LampNumericChange[] {
  if (!previous) return [];
  const keys = new Set([...Object.keys(previous.values), ...Object.keys(current.values)]);
  return [...keys]
    .sort((a, b) => a.localeCompare(b))
    .flatMap((key) => {
      const before = previous.values[key];
      const after = current.values[key];
      if (before === after) return [];
      return [{ key, previous: before, next: after, origin: current.origins[key] }];
    });
}
export function resolveLampNumericPreview(state: LampScenarioState): LampNumericPreview {
  const values = { ...(NUMERIC_BASELINES[state.protocol] ?? {}) };
  const origins: Record<string, string> = {};
  Object.keys(values).forEach((k) => (origins[k] = "product-baseline"));
  const ranges = { ...(NUMERIC_ENVELOPES[state.protocol] ?? {}) } as Record<
    string,
    [number, number]
  >;
  const applied: string[] = [];
  const scenario: Record<string, unknown> = {
    readout: state.readout,
    chemistry: state.chemistry,
    from_rna: state.fromRna,
    matrix: state.matrix,
    preparation: state.preparation,
    formulation: state.formulation,
    carryover_strategy: state.carryoverStrategy ?? "protocol-default",
    reconstitution_x: state.reconstitutionX ?? "protocol-default",
    specificity_additive: state.specificityAdditive ?? "none",
    acceleration_additive: state.accelerationAdditive ?? "none",
    primer_kinetics_profile: state.primerKineticsProfile ?? "protocol-default",
    preincubation_strategy: state.preincubationStrategy ?? "protocol-default",
    instrument_profile: state.instrumentProfile ?? "not-specified",
  };
  for (const rule of NUMERIC_RULES[state.protocol] ?? []) {
    if (Object.entries(rule.when ?? {}).every(([k, v]) => scenario[k] === v)) {
      for (const k of rule.unset ?? []) {
        delete values[k];
        delete origins[k];
      }
      for (const [k, v] of Object.entries(rule.set ?? {})) {
        values[k] = v;
        origins[k] = `automatic:${rule.id}`;
      }
      for (const [k, v] of Object.entries(rule.ranges ?? {})) ranges[k] = v;
      applied.push(rule.id);
    }
  }
  const profile = state.primerKineticsProfile ?? "protocol-default";
  if (NUMERIC_PROFILES[profile])
    for (const [k, v] of Object.entries(NUMERIC_PROFILES[profile])) {
      values[k] = v;
      origins[k] = `automatic:${profile}`;
    }
  for (const [wire, key] of LAMP_BENCH_FIELD_MAP) {
    const raw = state.benchValues?.[wire]?.trim();
    if (!raw) continue;
    const n = Number(raw);
    const r = ranges[key];
    if (Number.isFinite(n) && r && n >= r[0] && n <= r[1]) {
      values[key] = n;
      origins[key] = "user-override-within-source-bound";
    }
  }
  if (values.fluorescent_dye_x !== undefined && values.fluorescent_dye_stock_x !== undefined) {
    const rxn = values.reaction_volume_uL ?? 25;
    values.fluorescent_dye_uL_per_25uL =
      (rxn * values.fluorescent_dye_x) / values.fluorescent_dye_stock_x;
    origins.fluorescent_dye_uL_per_25uL = "derived-stoichiometry";
  }
  const unresolved = (NUMERIC_UNRESOLVED[state.protocol] ?? [])
    .filter(
      (x) =>
        x.when !== "turbidity-or-gel" || ["turbidity", "other-validated"].includes(state.readout),
    )
    .map(({ id, note }) => ({ id, note }));
  const thermalStages: LampThermalStage[] = [];
  if (state.preincubationStrategy === "takara-ung-25c-10min")
    thermalStages.push({
      id: "carryover-preincubation",
      temperature_c: 25,
      time_min: 10,
      authority: "Takara RR385 reviewed pre-incubation branch",
      required_by_selection: true,
    });
  if (values.hold_temperature_c !== undefined || values.hold_time_min !== undefined)
    thermalStages.push({
      id: "isothermal-amplification",
      temperature_c: values.hold_temperature_c,
      time_min: values.hold_time_min,
      authority: origins.hold_temperature_c ?? origins.hold_time_min ?? "product-baseline",
      required_by_selection: true,
    });
  return {
    values,
    origins,
    ranges,
    appliedOverlays: applied,
    unresolved,
    thermalStages,
    thermalStageModel: "ordered-source-backed-only",
    sequenceDecisionImpact: "none",
  };
}
