import type { RunSummary } from "@/lib/api/types";

/**
 * What to call a run on screen.
 *
 * Most runs are never labelled — the label is optional and typing one costs
 * more than clicking Run — so almost every run needs a name it was not given.
 * Numbering them by age is that name, and the number counts from the oldest so
 * it does not change under somebody when they save the next one.
 *
 * Here rather than inline because two places needed it and computed it
 * differently: the history list said "Run 1" and the line above the result said
 * "an earlier run", for the same run, on the same screen. Neither was wrong on
 * its own, which is exactly why nobody noticed they disagreed.
 */
export function runName(runs: RunSummary[], run: RunSummary | undefined): string {
  if (!run) return "an earlier run";
  if (run.label) return run.label;

  const index = runs.findIndex((one) => one.id === run.id);
  // Newest first in the list, so the oldest carries the lowest number.
  return index < 0 ? "an earlier run" : `Run ${runs.length - index}`;
}

/** The same, from an id. */
export function runNameById(runs: RunSummary[], id: string | null): string {
  return runName(
    runs,
    runs.find((run) => run.id === id),
  );
}
