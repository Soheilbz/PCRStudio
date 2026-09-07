/**
 * Browser readiness derived from the same canonical module runtime contract
 * that the scientific worker uses.
 *
 * The generated JSON is intentionally local to the Web package. Keeping a
 * generated projection rather than a second hand-maintained list prevents a
 * module from displaying an enabled Run button while the core already knows a
 * required assay fact is missing.
 */
import generated from "./required-context.generated.json";
import type { ValidationIssue } from "@/lib/contracts/validation-issue";
import type { RawDraftValues } from "@/lib/projects/draft";

type Draft = RawDraftValues;
type Rule = { when: Record<string, string>; required_context: string[] };
type Contract = {
  required_context: string[];
  conditional_required_context: Rule[];
  field_owners: Record<string, RequiredContextStep>;
};

const contracts = generated.modules as unknown as Record<string, Contract>;

function camel(value: string): string {
  return value.replace(/_([a-z0-9])/g, (_match, letter: string) => letter.toUpperCase());
}

/** Map worker contract paths onto the flat draft controls that produce them. */
export function draftFieldForContext(path: string): string {
  const [scope, leaf] = path.split(".", 2);
  if (!leaf) return camel(scope!);
  if (scope === "tails") return camel(leaf);
  if (scope === "edit") return `edit${camel(leaf)[0]!.toUpperCase()}${camel(leaf).slice(1)}`;
  return camel(leaf);
}

function matches(draft: Draft, when: Record<string, string>): boolean {
  return Object.entries(when).every(
    ([path, expected]) => (draft[draftFieldForContext(path)] ?? "") === expected,
  );
}

/** Required flat draft fields for the module in its current conditional branch. */
export function requiredDraftFields(moduleId: string, draft: Draft): string[] {
  const contract = contracts[moduleId];
  if (!contract) return [];
  const fields = contract.required_context.map(draftFieldForContext);
  for (const rule of contract.conditional_required_context) {
    if (matches(draft, rule.when)) fields.push(...rule.required_context.map(draftFieldForContext));
  }
  return Array.from(new Set(fields));
}

export type RequiredContextStep =
  | "target"
  | "design"
  | "strategy"
  | "constraints"
  | "vector"
  | "reaction"
  | "specificity"
  | "validation"
  | "construct"
  | "review";

/**
 * Where the current browser actually asks for canonical required context.
 * Ownership is field-level where an assay deliberately splits pre-analytical
 * context from bench chemistry. Unknown fields default to Target because that
 * is where the engine-specific design controls are rendered.
 */
export function requiredDraftFieldsForStep(
  moduleId: string,
  draft: Draft,
  step: RequiredContextStep,
): string[] {
  const all = requiredDraftFields(moduleId, draft);
  const owners = contracts[moduleId]?.field_owners ?? {};
  return all.filter((field) => (owners[field] ?? "target") === step);
}

/** Structured missing-context facts used by both step badges and Run readiness. */
export function requiredContextIssues(moduleId: string, draft: Draft): ValidationIssue[] {
  return requiredDraftFields(moduleId, draft)
    .filter((field) => !(draft[field] ?? "").trim())
    .map((field) => ({
      code: "REQUIRED_CONTEXT_MISSING",
      severity: "error" as const,
      ownerStep: contracts[moduleId]?.field_owners[field] ?? "target",
      fieldPath: field,
      message: `Required assay context is missing: ${field}.`,
      source: "module-contract",
      blocking: true,
    }));
}
