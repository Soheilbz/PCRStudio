"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type WorkflowEvidence =
  | {
      recorded?: boolean;
      decision_impact: "none";
      observed?: Record<string, unknown>;
      /** Historical result shape. Read-only compatibility; new results use observed. */
      fields?: Record<string, unknown>;
      note?: string;
    }
  | null
  | undefined;

function label(key: string): string {
  return key
    .replace(/^qpcr/i, "qPCR ")
    .replace(/^dpcr/i, "dPCR ")
    .replace(/^rpa/i, "RPA ")
    .replace(/^lamp/i, "LAMP ")
    .replace(/^colony/i, "Colony ")
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\bR2\b/g, "R²")
    .replace(/\bBp\b/g, "bp")
    .replace(/\bUl\b/g, "µL")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim();
}

function valueOf(value: unknown): string {
  if (value === null) return "unresolved";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

/** Experimental/workflow evidence retained with a run but excluded from sequence ranking. */
export function WorkflowEvidenceCard({
  evidence,
  title = "Workflow evidence",
}: {
  evidence?: WorkflowEvidence;
  title?: string;
}) {
  if (!evidence) return null;
  const observed = evidence.observed ?? evidence.fields ?? {};
  const entries = Object.entries(observed).filter(([, value]) => value !== "" && value != null);
  if (evidence.recorded === false || entries.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-md border border-primary/25 bg-primary/5 px-2.5 py-2 text-xs leading-relaxed text-muted-foreground">
          Evidence boundary:{" "}
          <span className="font-medium text-foreground">decision impact = none</span>. Measured
          bench/run observations do not retroactively change primer ranking or predicted
          specificity.
        </div>
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
          {entries.map(([key, value]) => (
            <div key={key} className="min-w-0">
              <dt className="text-xs text-muted-foreground">{label(key)}</dt>
              <dd className="break-words text-foreground tabular-nums">{valueOf(value)}</dd>
            </div>
          ))}
        </dl>
        {evidence.note ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{evidence.note}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
