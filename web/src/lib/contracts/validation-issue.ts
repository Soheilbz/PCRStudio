import { z } from "zod";

export const validationIssueSchema = z.object({
  code: z.string().min(1),
  severity: z.enum(["info", "warning", "error"]),
  ownerStep: z.enum([
    "target",
    "design",
    "strategy",
    "constraints",
    "vector",
    "reaction",
    "specificity",
    "validation",
    "construct",
    "review",
  ]),
  fieldPath: z.string().nullable(),
  message: z.string().min(1),
  source: z.string().min(1),
  blocking: z.boolean(),
});

export type ValidationIssue = z.infer<typeof validationIssueSchema>;

export function hasBlockingIssue(
  issues: readonly ValidationIssue[],
  ownerStep?: ValidationIssue["ownerStep"],
): boolean {
  return issues.some((issue) => issue.blocking && (!ownerStep || issue.ownerStep === ownerStep));
}
