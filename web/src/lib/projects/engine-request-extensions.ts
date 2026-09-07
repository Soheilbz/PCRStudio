import type { DesignPayload, ProbeMultiplexTarget } from "@/lib/contracts/design-requests";

function text(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function optionalNumber(form: FormData, name: string): number | undefined {
  const raw = text(form, name);
  if (!raw) return undefined;
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new Error(`${name} must be a finite number.`);
  return value;
}

function jsonObject(form: FormData, name: string): Record<string, unknown> | undefined {
  const raw = text(form, name);
  if (!raw) return undefined;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error(`${name} must contain valid JSON.`);
  }
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error(`${name} must be a JSON object.`);
  return value as Record<string, unknown>;
}

function integerList(form: FormData, name: string): number[] | undefined {
  const raw = text(form, name);
  if (!raw) return undefined;
  const values = raw
    .split(/[\s,;]+/)
    .filter(Boolean)
    .map(Number);
  if (!values.length || values.some((value) => !Number.isSafeInteger(value) || value < 0)) {
    throw new Error(
      `${name} must contain non-negative integer coordinates separated by commas/spaces.`,
    );
  }
  return [...new Set(values)];
}

function stringList(form: FormData, name: string): string[] | undefined {
  const values = text(form, name)
    .split(/[\n,;]+/)
    .map((value) => value.trim())
    .filter(Boolean);
  return values.length ? [...new Set(values)] : undefined;
}

export function probeMultiplexPanelFrom(form: FormData): ProbeMultiplexTarget[] | undefined {
  const raw = text(form, "probeMultiplexPanel");
  if (!raw) return undefined;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(
      "Multiplex panel data is invalid. Reopen the structured editor and correct the affected target.",
    );
  }
  if (!Array.isArray(parsed)) throw new Error("Multiplex panel data must be a list of targets.");
  return parsed.map((row, index) => {
    if (!row || typeof row !== "object" || Array.isArray(row))
      throw new Error(`Multiplex target ${index + 1} is invalid.`);
    const item = row as Record<string, unknown>;
    const required = (key: "target" | "reporter" | "quencher") => {
      const value = typeof item[key] === "string" ? item[key].trim() : "";
      if (!value) throw new Error(`Multiplex target ${index + 1} requires ${key}.`);
      return value;
    };
    const optional = (key: string) =>
      typeof item[key] === "string" && item[key].trim() ? item[key].trim() : undefined;
    return {
      target: required("target"),
      reporter: required("reporter"),
      quencher: required("quencher"),
      internalQuencher: optional("internalQuencher"),
      channel: optional("channel"),
      forwardPrimer: optional("forwardPrimer"),
      reversePrimer: optional("reversePrimer"),
      probeSequence: optional("probeSequence"),
    };
  });
}

export function outwardClosureFields(form: FormData): Partial<DesignPayload> {
  return {
    inverseReferenceSequence: text(form, "inverseReferenceSequence") || undefined,
    inverseReferenceCircular: text(form, "inverseReferenceCircular") === "true",
    inverseCandidateEnzymes: stringList(form, "inverseCandidateEnzymes"),
  };
}

export function probeClosureFields(form: FormData): Partial<DesignPayload> {
  return {
    probeOpticalAuthorityPayload: jsonObject(form, "probeOpticalAuthorityPayload"),
    probeMgbAuthorityMode:
      (text(form, "probeMgbAuthorityMode") as DesignPayload["probeMgbAuthorityMode"]) || undefined,
    probeMgbAuthorityPayload: jsonObject(form, "probeMgbAuthorityPayload"),
    probeTranscriptJunctions: integerList(form, "probeTranscriptJunctions"),
    probeVariantPositions: integerList(form, "probeVariantPositions"),
    probeMultiplexPanel: probeMultiplexPanelFrom(form),
  };
}

export function singleClosureFields(form: FormData, moduleId: string): Partial<DesignPayload> {
  if (moduleId === "sequencing-primer")
    return {
      sequencingPrimerWalking: text(form, "sequencingPrimerWalking") === "true",
      sequencingWalkingOverlap: optionalNumber(form, "sequencingWalkingOverlap"),
      sequencingTraceAb1Base64: text(form, "sequencingTraceAb1Base64") || undefined,
      sequencingTraceFilename: text(form, "sequencingTraceFilename") || undefined,
    };
  if (moduleId === "race")
    return { racePolyadenylated: text(form, "racePolyadenylated") === "true" };
  return {};
}

export function tilingClosureFields(form: FormData): Partial<DesignPayload> {
  return {
    circular: text(form, "circular") === "true",
    tilingDepthTsv: text(form, "tilingDepthTsv") || undefined,
    tilingDropoutThreshold: optionalNumber(form, "tilingDropoutThreshold"),
  };
}
