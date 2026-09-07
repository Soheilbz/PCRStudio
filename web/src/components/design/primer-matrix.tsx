"use client";

import { useMemo, useState } from "react";
import { ArrowUpDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { PrimerPair } from "@/lib/api/types";

export function PrimerMatrix({
  pairs,
  selectedRank,
  onSelectPair,
  tmPairMaxDifference,
  crossDimerThreshold,
}: {
  pairs: PrimerPair[];
  selectedRank: number;
  onSelectPair: (rank: number) => void;
  /** Effective profile/request bound. Undefined means the result supplied no bound. */
  tmPairMaxDifference?: number;
  /** Worker-declared diagnostic/ranking watch line. Undefined means no visual threshold. */
  crossDimerThreshold?: number;
}) {
  const [sortKey, setSortKey] = useState<"rank" | "score" | "size" | "tm_diff" | "cross_dimer">(
    "rank",
  );
  const [sortAsc, setSortAsc] = useState(true);

  const sortedPairs = useMemo(() => {
    return pairs
      .map((pair, index) => ({ pair, rank: index + 1 }))
      .sort((a, b) => {
        let diff = 0;
        if (sortKey === "rank") diff = a.rank - b.rank;
        else if (sortKey === "score") diff = a.pair.score - b.pair.score;
        else if (sortKey === "size") diff = a.pair.product_size - b.pair.product_size;
        else if (sortKey === "tm_diff") diff = a.pair.tm_difference - b.pair.tm_difference;
        else if (sortKey === "cross_dimer") diff = a.pair.cross_dimer_dg - b.pair.cross_dimer_dg;
        return sortAsc ? diff : -diff;
      });
  }, [pairs, sortKey, sortAsc]);

  const handleSort = (key: typeof sortKey) => {
    if (sortKey === key) {
      setSortAsc((prev) => !prev);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  return (
    <Card className="workbench-card gap-3">
      <CardHeader>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <CardTitle className="font-serif text-base font-semibold">
            Candidate Comparison Matrix
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            {pairs.length} candidate pairs evaluated
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-xs">
            <caption className="sr-only">
              Primer candidate comparison and inspection controls
            </caption>
            <thead className="bg-surface-warm/42 text-muted-foreground">
              <tr>
                <th
                  scope="col"
                  aria-sort={sortKey === "rank" ? (sortAsc ? "ascending" : "descending") : "none"}
                  className="px-3 py-2 text-left font-medium"
                >
                  <button
                    type="button"
                    onClick={() => handleSort("rank")}
                    className="inline-flex min-h-6 items-center gap-1 rounded-sm px-1 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    Pair # <ArrowUpDown className="size-3" aria-hidden="true" />
                  </button>
                </th>
                <th
                  scope="col"
                  aria-sort={sortKey === "size" ? (sortAsc ? "ascending" : "descending") : "none"}
                  className="px-3 py-2 text-right font-medium"
                >
                  <button
                    type="button"
                    onClick={() => handleSort("size")}
                    className="inline-flex min-h-6 w-full items-center justify-end gap-1 rounded-sm px-1 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    Amplicon <ArrowUpDown className="size-3" aria-hidden="true" />
                  </button>
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Ta (°C)
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Fwd Tm (°C)
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Rev Tm (°C)
                </th>
                <th
                  scope="col"
                  aria-sort={
                    sortKey === "tm_diff" ? (sortAsc ? "ascending" : "descending") : "none"
                  }
                  className="px-3 py-2 text-right font-medium"
                >
                  <button
                    type="button"
                    onClick={() => handleSort("tm_diff")}
                    className="inline-flex min-h-6 w-full items-center justify-end gap-1 rounded-sm px-1 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    ΔTm (°C) <ArrowUpDown className="size-3" aria-hidden="true" />
                  </button>
                </th>
                <th
                  scope="col"
                  aria-sort={
                    sortKey === "cross_dimer" ? (sortAsc ? "ascending" : "descending") : "none"
                  }
                  className="px-3 py-2 text-right font-medium"
                >
                  <button
                    type="button"
                    onClick={() => handleSort("cross_dimer")}
                    className="inline-flex min-h-6 w-full items-center justify-end gap-1 rounded-sm px-1 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    Dimer ΔG <ArrowUpDown className="size-3" aria-hidden="true" />
                  </button>
                </th>
                <th
                  scope="col"
                  aria-sort={sortKey === "score" ? (sortAsc ? "ascending" : "descending") : "none"}
                  className="px-3 py-2 text-right font-medium"
                >
                  <button
                    type="button"
                    onClick={() => handleSort("score")}
                    className="inline-flex min-h-6 w-full items-center justify-end gap-1 rounded-sm px-1 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    Score <ArrowUpDown className="size-3" aria-hidden="true" />
                  </button>
                </th>
                <th scope="col" className="px-3 py-2 text-center font-medium">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedPairs.map(({ pair, rank }) => {
                const isSelected = rank === selectedRank;
                const tmDiffSafe =
                  typeof tmPairMaxDifference === "number"
                    ? pair.tm_difference <= tmPairMaxDifference
                    : undefined;
                // Never resurrect a hidden -6 kcal/mol UI line when the worker did
                // not declare one. A supplied line is diagnostic/ranking evidence,
                // not a universal biological pass/fail threshold.
                const dimerSafe =
                  typeof crossDimerThreshold === "number"
                    ? pair.cross_dimer_dg >= crossDimerThreshold
                    : undefined;

                return (
                  <tr
                    key={rank}
                    className={cn(
                      "border-t transition-colors hover:bg-surface-warm/35",
                      isSelected && "bg-primary/5 font-medium",
                    )}
                  >
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <span>Pair {rank}</span>
                        {rank === 1 ? (
                          <Badge variant="default" className="h-4 px-1 text-xs">
                            Top-ranked
                          </Badge>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                      {pair.product_size} bp
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                      {pair.annealing_temperature ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                      {pair.left.tm}
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                      {pair.right.tm}
                    </td>
                    <td
                      className={cn(
                        "px-3 py-2 text-right whitespace-nowrap tabular-nums",
                        tmDiffSafe === false && "font-semibold text-warning",
                      )}
                    >
                      {pair.tm_difference.toFixed(1)}
                    </td>
                    <td
                      className={cn(
                        "px-3 py-2 text-right whitespace-nowrap tabular-nums",
                        dimerSafe === false && "font-semibold text-destructive",
                      )}
                    >
                      {pair.cross_dimer_dg.toFixed(1)}
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                      {pair.score.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-center whitespace-nowrap">
                      <Button
                        type="button"
                        variant={isSelected ? "secondary" : "ghost"}
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => onSelectPair(rank)}
                      >
                        {isSelected ? "Inspecting" : "Inspect"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
