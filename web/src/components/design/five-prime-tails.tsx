"use client";

import type { FivePrimeTail } from "@/lib/api/types";

/**
 * What was put in front of every oligo, and whose temperature is quoted.
 *
 * Stated once for the whole result rather than on each oligo: the tail is the
 * same on all of them — it is a property of what happens after the PCR, not of
 * the search — and repeating it on sixteen tiles would bury the only sentence
 * that matters, which is that the temperatures below are the annealing halves'.
 */
export function FivePrimeTails({
  tails,
}: {
  tails: { forward?: FivePrimeTail; reverse?: FivePrimeTail } | null | undefined;
}) {
  const ends = [tails?.forward, tails?.reverse].filter(Boolean) as NonNullable<FivePrimeTail>[];
  if (ends.length === 0) return null;

  return (
    <section className="rounded-xl border border-dashed border-border/60 bg-surface-wash/30 p-4">
      <h3 className="font-serif text-base font-semibold">In front of every oligo below</h3>
      <dl className="mt-2 grid gap-3 sm:grid-cols-2">
        {ends.map((end) => (
          <div key={end.role} className="min-w-0 space-y-0.5">
            <dt className="text-xs text-muted-foreground">
              {end.role === "forward" ? "Forward" : "Reverse"} · {end.length} bases
            </dt>
            <dd className="font-mono text-xs break-all">{end.tail}</dd>
            <dd className="text-xs text-muted-foreground tabular-nums">
              anneals at {end.annealing_tm} °C · whole molecule {end.whole_tm} °C
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{ends[0]!.note}</p>
    </section>
  );
}
