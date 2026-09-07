import { GitCompareArrows } from "lucide-react";

import { CopyButton } from "@/components/copy-button";
import { LocalTime } from "@/components/local-time";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  buildComparisonRows,
  COMPARISON_EPSILON,
  engineLabel,
  firstPair,
  isFlagged,
} from "@/lib/projects/comparison";
import type { Run } from "@/lib/api/types";

import { ClearComparison } from "./clear-comparison";

/**
 * Two runs, side by side.
 *
 * The question a run history exists to ask — what was different about the
 * attempt that worked? — could until now only be answered by opening runs one
 * at a time and holding the numbers in your head. This renders both runs'
 * FIRST pairs in one table instead, and shades the figures that differ by half
 * a degree or more.
 *
 * The shading is deliberately the only decoration: similarities stay quiet, so
 * what is shaded is what the comparison found. Everything is rendered on the
 * server from ids in the address bar, which makes any comparison a link
 * somebody can paste.
 *
 * Scoped honestly: engines whose saved shapes carry no pair of measured oligos
 * get a row that says so rather than rows of numbers read from the wrong field.
 */
export function RunComparison({
  a,
  b,
  nameA,
  nameB,
}: {
  a: Run;
  b: Run;
  nameA: string;
  nameB: string;
}) {
  const metricsA = firstPair(a.result);
  const metricsB = firstPair(b.result);
  const rows = buildComparisonRows(metricsA, metricsB);

  // Said once and attached to every shaded cell: a highlight nobody can
  // interrogate is a highlight somebody learns to ignore.
  const flaggedTitle = `These two figures differ by ${COMPARISON_EPSILON} or more.`;

  return (
    <Card className="workbench-card">
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1.5">
          <CardTitle className="flex items-center gap-2 font-serif text-lg font-semibold">
            <GitCompareArrows className="size-4" />
            Comparing two runs
          </CardTitle>
          <p className="text-xs leading-relaxed text-muted-foreground">
            The first pair of each run, side by side. Figures that differ by {COMPARISON_EPSILON} or
            more are shaded; everything else agreed within that.
          </p>
        </div>
        <ClearComparison />
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-sm">
            <caption className="sr-only">Side-by-side comparison of two design runs</caption>
            <thead>
              <tr className="border-b">
                <th
                  scope="col"
                  className="px-4 py-2 text-left text-xs font-normal text-muted-foreground"
                >
                  Metric
                </th>
                {[nameA, nameB].map((name, index) => {
                  const run = index === 0 ? a : b;
                  return (
                    <th scope="col" key={run.id} className="px-4 py-2 text-left align-top">
                      <span className="block text-xs font-medium">{name}</span>
                      <Badge variant="secondary" className="mt-1 max-w-full">
                        <span className="truncate">{engineLabel(run.result)}</span>
                      </Badge>
                      <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                        <LocalTime iso={run.createdAt} relative />
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-6 text-center text-xs leading-relaxed text-muted-foreground"
                  >
                    Neither of these runs carries a comparable primer pair — this engine&apos;s
                    results answer a different question, so there are no matching figures to put
                    beside each other.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.label} className="border-b last:border-b-0">
                    <th
                      scope="row"
                      className="px-4 py-2 text-left text-xs font-normal text-muted-foreground"
                    >
                      {row.label}
                    </th>
                    <Cell row={row} side="a" flaggedTitle={flaggedTitle} />
                    <Cell row={row} side="b" flaggedTitle={flaggedTitle} />
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

/** One cell of one metric row, shaded when it differs past the threshold. */
function Cell({
  row,
  side,
  flaggedTitle,
}: {
  row: ReturnType<typeof buildComparisonRows>[number];
  side: "a" | "b";
  flaggedTitle: string;
}) {
  const cell = side === "a" ? row.a : row.b;

  if (cell.text === null) {
    // A dash with its reason, never a bare em dash: "—" beside an empty cell
    // reads as a rendering bug, where "— not part of this engine's results"
    // reads as a fact.
    return (
      <td className="px-4 py-2 text-muted-foreground" title={row.missingBecause ?? undefined}>
        —
      </td>
    );
  }

  const flagged = isFlagged(row, side);
  const truncated =
    !row.monospace && cell.text.length > 80 ? `${cell.text.slice(0, 80)}…` : cell.text;

  return (
    <td
      className={flagged ? "bg-warning/15 px-4 py-2 tabular-nums" : "px-4 py-2 tabular-nums"}
      title={flagged ? flaggedTitle : undefined}
    >
      <span className={row.monospace ? "font-mono text-xs break-all" : ""}>{truncated}</span>
      {row.monospace ? <CopyButton value={cell.text} label={row.label} /> : null}
    </td>
  );
}
