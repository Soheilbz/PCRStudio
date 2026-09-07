import type { DesignPayload } from "@/lib/contracts/design-requests";

type Value = unknown;
type Settings = Record<string, string>;
type FlankingContext = NonNullable<DesignPayload["flankingNumericContext"]>;

type ScalarKind = "number" | "string" | "boolean";

type FlankingFieldSpec = Readonly<{
  requestKey: keyof FlankingContext;
  draftKey: string;
  kind: ScalarKind;
  modules: readonly string[];
}>;

export const FLANKING_MODULES = [
  "standard-pcr",
  "long-range-pcr",
  "colony-pcr",
  "qpcr-sybr",
  "digital-pcr",
  "rpa",
] as const;

/**
 * Canonical scalar mapping between the flat workspace draft and the nested
 * flankingNumericContext wire object. Primer concentration is handled below
 * because its unit depends on assay/protocol rather than only module id.
 */
export const FLANKING_FIELD_SPECS: readonly FlankingFieldSpec[] = [
  {
    requestKey: "reactionVolumeUl",
    draftKey: "flankingReactionVolumeUl",
    kind: "number",
    modules: FLANKING_MODULES,
  },
  {
    requestKey: "templateInputNg",
    draftKey: "flankingTemplateInputNg",
    kind: "number",
    modules: FLANKING_MODULES,
  },
  {
    requestKey: "templateInputUl",
    draftKey: "flankingTemplateInputUl",
    kind: "number",
    modules: FLANKING_MODULES,
  },
  {
    requestKey: "templateClass",
    draftKey: "flankingTemplateClass",
    kind: "string",
    modules: FLANKING_MODULES,
  },
  {
    requestKey: "templateFractionPercent",
    draftKey: "flankingTemplateFractionPercent",
    kind: "number",
    modules: ["qpcr-sybr"],
  },
  {
    requestKey: "cyclingProfile",
    draftKey: "qpcrCyclingProfile",
    kind: "string",
    modules: ["qpcr-sybr"],
  },
  {
    requestKey: "qpcrInstrumentProfile",
    draftKey: "qpcrInstrumentProfile",
    kind: "string",
    modules: ["qpcr-sybr"],
  },
  {
    requestKey: "additive",
    draftKey: "flankingAdditive",
    kind: "string",
    modules: ["standard-pcr", "qpcr-sybr"],
  },
  {
    requestKey: "gcEnhancerPercent",
    draftKey: "flankingGcEnhancerPercent",
    kind: "number",
    modules: ["standard-pcr"],
  },
  {
    requestKey: "targetLengthKb",
    draftKey: "longRangeTargetLengthKb",
    kind: "number",
    modules: ["long-range-pcr"],
  },
  {
    requestKey: "hmwTemplateVerified",
    draftKey: "longRangeHmwTemplateVerified",
    kind: "boolean",
    modules: ["long-range-pcr"],
  },
  {
    requestKey: "partitionFormatDetail",
    draftKey: "digitalPartitionFormatDetail",
    kind: "string",
    modules: ["digital-pcr"],
  },
  {
    requestKey: "digitalConsumableId",
    draftKey: "digitalConsumableId",
    kind: "string",
    modules: ["digital-pcr"],
  },
  {
    requestKey: "effectivePartitionVolumeNl",
    draftKey: "digitalEffectivePartitionVolumeNl",
    kind: "number",
    modules: ["digital-pcr"],
  },
  {
    requestKey: "fragmentationEnzyme",
    draftKey: "digitalFragmentationEnzyme",
    kind: "string",
    modules: ["digital-pcr"],
  },
  { requestKey: "rpaTemperatureC", draftKey: "rpaTemperatureC", kind: "number", modules: ["rpa"] },
  { requestKey: "rpaTimeMin", draftKey: "rpaTimeMin", kind: "number", modules: ["rpa"] },
  {
    requestKey: "rpaBstUnitsPerUl",
    draftKey: "rpaBstUnitsPerUl",
    kind: "number",
    modules: ["rpa"],
  },
  { requestKey: "rpaMultiplex", draftKey: "rpaMultiplex", kind: "boolean", modules: ["rpa"] },
  {
    requestKey: "initialDenaturationTimeMin",
    draftKey: "colonyInitialDenaturationMin",
    kind: "number",
    modules: ["colony-pcr"],
  },
  {
    requestKey: "colonySampleInputUl",
    draftKey: "colonySampleInputUl",
    kind: "number",
    modules: ["colony-pcr"],
  },
] as const;

export const WINDOW_OBJECT_ROLES = ["outer", "inner", "loop"] as const;
export const WINDOW_OBJECT_FIELDS = ["tm_min", "tm_max", "length_min", "length_max"] as const;
export const WINDOW_SPAN_ROLES = ["f2_b2_span", "loop_span", "outer_gap", "middle_gap"] as const;

function rawField(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function numberField(form: FormData, name: string): number | undefined {
  const raw = rawField(form, name);
  if (!raw) return undefined;
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new Error(`${name} must be a finite number.`);
  return value;
}

function put(out: Settings, key: string, value: Value): void {
  if (value === undefined || value === null || value === "") return;
  out[key] = String(value);
}

function assignContextField(
  context: Record<string, unknown>,
  spec: FlankingFieldSpec,
  form: FormData,
): void {
  if (spec.kind === "number") {
    const value = numberField(form, spec.draftKey);
    if (value !== undefined) context[spec.requestKey] = value;
    return;
  }
  const raw = rawField(form, spec.draftKey);
  if (spec.kind === "boolean") {
    if (raw === "true") context[spec.requestKey] = true;
    else if (raw === "false") context[spec.requestKey] = false;
    return;
  }
  if (raw) context[spec.requestKey] = raw;
}

/** Build the nested scientific context from the flat workspace draft. */
export function flankingNumericContextFromDraft(
  form: FormData,
  moduleId: string,
): DesignPayload["flankingNumericContext"] | undefined {
  if (!FLANKING_MODULES.includes(moduleId as (typeof FLANKING_MODULES)[number])) return undefined;

  const context: Record<string, unknown> = {};
  for (const spec of FLANKING_FIELD_SPECS) {
    if (spec.modules.includes(moduleId)) assignContextField(context, spec, form);
  }

  const digitalProtocol = moduleId === "digital-pcr" ? rawField(form, "digitalProtocol") : "";
  const usesNmPrimer =
    moduleId === "qpcr-sybr" || moduleId === "rpa" || digitalProtocol === "bio-rad-qx200-evagreen";
  const concentrationDraftKey = usesNmPrimer ? "flankingPrimerEachNm" : "flankingPrimerEachUm";
  const concentration = numberField(form, concentrationDraftKey);
  if (concentration !== undefined)
    context[usesNmPrimer ? "primerEachNm" : "primerEachUm"] = concentration;

  if (moduleId === "colony-pcr") {
    const preparation = rawField(form, "colonyPreparation");
    if (preparation) context.preparation = preparation;
  }

  return Object.keys(context).length
    ? (context as NonNullable<DesignPayload["flankingNumericContext"]>)
    : undefined;
}

/** Restore the same context into draft keys; used by project/share forking. */
export function restoreFlankingNumericContext(out: Settings, value: Value): void {
  if (!value || typeof value !== "object" || Array.isArray(value)) return;
  const context = value as Record<string, Value>;
  for (const spec of FLANKING_FIELD_SPECS) put(out, spec.draftKey, context[spec.requestKey]);
  put(out, "flankingPrimerEachUm", context.primerEachUm);
  put(out, "flankingPrimerEachNm", context.primerEachNm);
  if (!out.colonyPreparation) put(out, "colonyPreparation", context.preparation);
}

/** Build the typed LAMP window object from draft fields. */
export function windowsFromDraft(form: FormData): Record<string, unknown> | undefined {
  const built: Record<string, unknown> = {};
  for (const role of WINDOW_OBJECT_ROLES) {
    const window: Record<string, number> = {};
    for (const name of WINDOW_OBJECT_FIELDS) {
      const given = numberField(form, `w_${role}_${name}`);
      if (given !== undefined) window[name] = given;
    }
    if (Object.keys(window).length) built[role] = window;
  }

  for (const span of WINDOW_SPAN_ROLES) {
    const low = numberField(form, `w_${span}_min`);
    const high = numberField(form, `w_${span}_max`);
    if ((low === undefined) !== (high === undefined)) {
      throw new Error(`${span.replace(/_/g, " ")} requires both minimum and maximum values.`);
    }
    if (low !== undefined && high !== undefined) built[span] = [low, high];
  }
  return Object.keys(built).length ? built : undefined;
}

/** Restore LAMP window roles and spans using the same canonical role lists. */
export function restoreWindows(out: Settings, value: Value): void {
  if (!value || typeof value !== "object" || Array.isArray(value)) return;
  const windows = value as Record<string, Value>;

  for (const role of WINDOW_OBJECT_ROLES) {
    const window = windows[role];
    if (!window || typeof window !== "object" || Array.isArray(window)) continue;
    for (const name of WINDOW_OBJECT_FIELDS) {
      put(out, `w_${role}_${name}`, (window as Record<string, Value>)[name]);
    }
  }
  for (const span of WINDOW_SPAN_ROLES) {
    const range = windows[span];
    if (!Array.isArray(range)) continue;
    put(out, `w_${span}_min`, range[0]);
    put(out, `w_${span}_max`, range[1]);
  }
}
