import type { ModuleId } from "@/lib/contracts/module-bindings.generated";

/** Raw HTML controls are strings by definition. */
export type RawDraftValues = Record<string, string>;

/** Normalized draft identity carried into readiness/request/persistence code. */
export interface ModuleDraft<M extends ModuleId = ModuleId> {
  schemaVersion: 2;
  moduleId: M;
  values: RawDraftValues;
}

export function normalizeDraft<M extends ModuleId>(
  moduleId: M,
  values: Record<string, unknown>,
): ModuleDraft<M> {
  const normalized: RawDraftValues = {};
  for (const [key, value] of Object.entries(values)) {
    if (typeof value === "string") normalized[key] = value;
  }
  return { schemaVersion: 2, moduleId, values: normalized };
}
