"use client";

/**
 * The region a product has to contain, chosen by dragging or by typing.
 *
 * Two numbers in two boxes are exact and tell you nothing. Where is base 1,412
 * in a sequence of 2,512? Is the exon you want near the middle or right at the
 * end where no primer can flank it? A bar answers both at a glance, and it is
 * the same two numbers underneath — so the boxes stay, and dragging and typing
 * agree because they write to the same place.
 *
 * The bar also draws where a primer cannot go: a product needs room for a
 * primer at each end, so a region pinned against either edge of the template
 * has no design. That is a thing to see rather than to be told after a run
 * comes back empty.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { count } from "@/lib/numbers";
import { cn } from "@/lib/utils";

/** Roughly how much room a primer needs at each end of the template. */
const PRIMER_ROOM = 25;

/** One stretch no primer may overlap, as the form holds it. */
export interface Avoided {
  from: string;
  to: string;
}

/** Read the avoided regions out of the string a draft carries them in. */
export function parseAvoided(packed: string): Avoided[] {
  return packed
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [from, to] = entry.split("-");
      return { from: (from ?? "").trim(), to: (to ?? "").trim() };
    });
}

/**
 * And write them back, in the same shape.
 */
export function packAvoided(regions: Avoided[]): string {
  return regions.map((region) => `${region.from}-${region.to}`).join(",");
}

export function RegionPicker({
  length,
  start,
  span,
  avoided,
  onChange,
  onAvoidedChange,
  mode = "product",
}: {
  /** How long the template is. Zero means nothing has been pasted yet. */
  length: number;
  /** First base of the region, one-based, or empty for none. */
  start: string;
  /** How many bases from there, or empty for none. */
  span: string;
  /** Stretches no primer may overlap, packed as `from-to,from-to`. */
  avoided: string;
  onChange: (next: { start: string; span: string }) => void;
  onAvoidedChange: (next: string) => void;
  mode?: "product" | "sequencing-target" | "race-gsp";
}) {
  const avoid = parseAvoided(avoided);
  const track = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<"start" | "end" | "whole" | null>(null);

  const from = Number(start) || 0;
  const width = Number(span) || 0;
  const to = from && width ? from + width - 1 : 0;
  const chosen = from > 0 && width > 0;

  const percent = useCallback(
    (base: number) => (length > 0 ? Math.min(100, Math.max(0, (100 * base) / length)) : 0),
    [length],
  );

  const baseAt = useCallback(
    (clientX: number) => {
      const box = track.current?.getBoundingClientRect();
      if (!box || length === 0) return 1;
      const share = Math.min(1, Math.max(0, (clientX - box.left) / box.width));
      return Math.max(1, Math.min(length, Math.round(share * length)));
    },
    [length],
  );

  // Dragging is tracked on the window so the pointer can leave the bar without
  // the region sticking to wherever it was when it left.
  useEffect(() => {
    if (!dragging) return;

    const move = (event: PointerEvent) => {
      const base = baseAt(event.clientX);
      if (dragging === "start") {
        const end = to || base;
        const first = Math.min(base, end);
        onChange({ start: String(first), span: String(Math.max(1, end - first + 1)) });
      } else if (dragging === "end") {
        const first = from || base;
        const last = Math.max(base, first);
        onChange({ start: String(first), span: String(Math.max(1, last - first + 1)) });
      } else {
        const half = Math.round(width / 2);
        const first = Math.max(1, Math.min(length - width + 1, base - half));
        onChange({ start: String(first), span: String(width) });
      }
    };
    const stop = () => setDragging(null);

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
  }, [dragging, baseAt, from, to, width, length, onChange]);

  const clear = () => onChange({ start: "", span: "" });

  const beginAt = (event: React.PointerEvent) => {
    if (length === 0) return;
    const base = baseAt(event.clientX);
    if (!chosen) {
      const width = Math.max(20, Math.round(length / 10));
      const first = Math.max(1, Math.min(length - width + 1, base - Math.round(width / 2)));
      onChange({ start: String(first), span: String(width) });
    }
    setDragging("whole");
  };

  const tooTight =
    mode === "product" &&
    chosen &&
    (from <= PRIMER_ROOM || to >= length - PRIMER_ROOM + 1) &&
    length > 0;
  const heading =
    mode === "race-gsp"
      ? "Where may the RACE gene-specific primer bind?"
      : mode === "sequencing-target"
        ? "Which sequence must this capillary read cover?"
        : "Must the product contain a particular region?";
  const aria =
    mode === "race-gsp"
      ? "Known-sequence RACE GSP search region"
      : mode === "sequencing-target"
        ? "Sequencing target region"
        : "Region the product must contain";

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-sm font-medium">{heading}</h3>
        <span className="text-xs text-muted-foreground tabular-nums">
          {length > 0 ? `${count(length)} bases` : "paste a sequence first"}
        </span>
      </div>

      <div
        ref={track}
        onPointerDown={beginAt}
        className={cn(
          "relative h-9 w-full touch-none rounded-xl border border-border/60 bg-surface-wash/40 select-none",
          length === 0 ? "cursor-not-allowed opacity-60" : "cursor-crosshair",
        )}
        role="group"
        aria-label={aria}
      >
        {length > 0 && mode === "product" ? (
          <>
            <div
              className="absolute inset-y-0 left-0 rounded-l-md bg-destructive/10"
              style={{ width: `${percent(PRIMER_ROOM)}%` }}
              aria-hidden="true"
            />
            <div
              className="absolute inset-y-0 right-0 rounded-r-md bg-destructive/10"
              style={{ width: `${percent(PRIMER_ROOM)}%` }}
              aria-hidden="true"
            />
          </>
        ) : null}

        {avoid.map((region, index) => {
          const from = Number(region.from) || 0;
          const to = Number(region.to) || 0;
          if (!from || to < from) return null;
          return (
            <div
              key={`${region.from}-${region.to}-${index}`}
              className="absolute inset-y-1 rounded bg-destructive/25 ring-1 ring-destructive/40"
              style={{ left: `${percent(from - 1)}%`, width: `${percent(to - from + 1)}%` }}
              aria-hidden="true"
            />
          );
        })}

        {chosen ? (
          <div
            className="absolute inset-y-1 rounded bg-primary/25 ring-1 ring-primary/50"
            style={{ left: `${percent(from - 1)}%`, width: `${percent(width)}%` }}
          >
            <Handle
              side="left"
              value={from}
              min={1}
              max={to}
              onGrab={() => setDragging("start")}
              onStep={(delta) => {
                const nextFrom = Math.max(1, Math.min(to, from + delta));
                onChange({ start: String(nextFrom), span: String(to - nextFrom + 1) });
              }}
              label="Move start of region"
            />
            <Handle
              side="right"
              value={to}
              min={from}
              max={length}
              onGrab={() => setDragging("end")}
              onStep={(delta) => {
                const nextTo = Math.max(from, Math.min(length, to + delta));
                onChange({ start: String(from), span: String(nextTo - from + 1) });
              }}
              label="Move end of region"
            />
          </div>
        ) : (
          <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
            {length > 0 ? "Drag here to mark a region, or type below" : "No sequence yet"}
          </p>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <div className="space-y-1.5">
          <Label htmlFor="targetStart" className="text-xs font-medium">
            From base
          </Label>
          <Input
            id="targetStart"
            type="number"
            min={1}
            max={length || undefined}
            value={start}
            onChange={(event) => onChange({ start: event.target.value, span })}
            placeholder="anywhere"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="targetLength" className="text-xs font-medium">
            For how many bases
          </Label>
          <Input
            id="targetLength"
            type="number"
            min={1}
            max={length || undefined}
            value={span}
            onChange={(event) => onChange({ start, span: event.target.value })}
            placeholder="—"
          />
        </div>
        {chosen ? (
          <button
            type="button"
            onClick={clear}
            className="h-9 rounded-lg px-2 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            Clear
          </button>
        ) : null}
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        {chosen
          ? mode === "race-gsp"
            ? `Bases ${count(from)} to ${count(to)} are the known-sequence window in which the RACE GSP may be selected.`
            : mode === "sequencing-target"
              ? `Bases ${count(from)} to ${count(to)} are the sequence the capillary read must cover.`
              : `Bases ${count(from)} to ${count(to)} will fall inside every product.`
          : mode === "race-gsp"
            ? "Required for RACE: select the known-sequence region where a gene-specific primer is allowed to bind."
            : mode === "sequencing-target"
              ? "Required for sequencing-primer: select the region the capillary read must cover."
              : "Optional. A variant, an exon — something the product has to contain. Both boxes or neither: half of a region would be silently ignored."}
      </p>

      <div className="border-t border-border/60 pt-3">
        <AvoidedRegions value={avoided} onChange={onAvoidedChange} length={length} />
      </div>

      {tooTight ? (
        <p role="status" className="text-xs leading-relaxed text-warning">
          This region reaches within {PRIMER_ROOM} bases of the end of the template, and a primer
          has to fit outside it. Either the region needs to move in, or the template needs more
          sequence around it.
        </p>
      ) : null}
    </div>
  );
}

function Handle({
  side,
  onGrab,
  onStep,
  value,
  min,
  max,
  label,
}: {
  side: "left" | "right";
  onGrab: () => void;
  onStep?: (delta: number) => void;
  value?: number;
  min?: number;
  max?: number;
  label: string;
}) {
  return (
    <button
      type="button"
      role="slider"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      onKeyDown={(event) => {
        if (!onStep) return;
        const step = event.shiftKey ? 10 : 1;
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          onStep(-step);
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          onStep(step);
        }
      }}
      onPointerDown={(event) => {
        event.stopPropagation();
        onGrab();
      }}
      className={cn(
        "absolute inset-y-0 w-3 cursor-ew-resize rounded bg-primary/80 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        "after:absolute after:-inset-2 after:content-['']", // Expanded touch target
        side === "left" ? "-left-1.5" : "-right-1.5",
      )}
    />
  );
}

/**
 * Stretches no primer may sit on.
 */
export function AvoidedRegions({
  value,
  onChange,
  length,
}: {
  /** Packed as `from-to,from-to`, which is the only state these rows have. */
  value: string;
  onChange: (next: string) => void;
  /** How long the sequence is, for the upper bound on each box. */
  length: number;
}) {
  const avoid = parseAvoided(value);
  const setAvoid = (next: Avoided[]) => onChange(packAvoided(next));

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium">Anywhere a primer must not go?</h3>
        <button
          type="button"
          onClick={() => setAvoid([...avoid, { from: "", to: "" }])}
          disabled={length === 0}
          className="min-h-6 rounded-lg px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"
        >
          + Add a region
        </button>
      </div>

      {avoid.length === 0 ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          Optional. A repeat, a stretch of poor sequence, somewhere you already know primes badly.
          Marked in red on the bar above.
        </p>
      ) : (
        <ul className="space-y-2">
          {avoid.map((region, index) => (
            <li key={index} className="flex flex-wrap items-center gap-2">
              <Input
                type="number"
                min={1}
                max={length || undefined}
                value={region.from}
                onChange={(event) =>
                  setAvoid(
                    avoid.map((entry, at) =>
                      at === index ? { ...entry, from: event.target.value } : entry,
                    ),
                  )
                }
                placeholder="from"
                className="w-28"
                aria-label={`Region ${index + 1}, first base`}
              />
              <span className="text-xs text-muted-foreground">to</span>
              <Input
                type="number"
                min={1}
                max={length || undefined}
                value={region.to}
                onChange={(event) =>
                  setAvoid(
                    avoid.map((entry, at) =>
                      at === index ? { ...entry, to: event.target.value } : entry,
                    ),
                  )
                }
                placeholder="to"
                className="w-28"
                aria-label={`Region ${index + 1}, last base`}
              />
              <button
                type="button"
                onClick={() => setAvoid(avoid.filter((_, at) => at !== index))}
                className="rounded-lg px-2 py-1 text-xs text-muted-foreground hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                aria-label={`Remove region ${index + 1}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
