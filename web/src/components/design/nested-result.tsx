"use client";

/**
 * What a nested design produced.
 *
 * A different view from the flanking-pair one because it is a different
 * answer: two pairs in a fixed relationship rather than one pair, and the
 * relationship is the thing worth showing. Two primer pairs listed one after
 * another would look like two ordinary designs, and somebody reading it that
 * way would order four oligos without knowing which two go in the first tube.
 *
 * So the geometry is drawn, both rounds are labelled by round, and how far the
 * second round moved in at each end is stated — that number is how you tell a
 * nested design from two pairs that merely overlap.
 */

import { ResultFact as Fact, RuntimeProvenance } from "./result-primitives";
import { ScanFindings } from "@/components/design/scan";
import { OrderActions } from "./order-actions";
import { WorkflowEvidenceCard } from "./workflow-evidence";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count, maybeCount } from "@/lib/numbers";
import type { Nest, NestedResult, NestedRound } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function NestedResultView({ result }: { result: NestedResult }) {
  return (
    <div className="space-y-5">
      <TheTemplate result={result} />
      <ReactionTimeline result={result} />
      <WorkflowEvidenceCard
        evidence={result.workflow_evidence}
        title="Nested-PCR run & contamination evidence"
      />

      {result.nests.length === 0 ? (
        <NothingFound result={result} />
      ) : (
        <>
          <section className="space-y-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-sm font-medium">
                {result.nests.length} nested design
                {result.nests.length === 1 ? "" : "s"}
              </h2>
              <span className="text-xs text-muted-foreground">
                {result.nesting.shares === "nothing"
                  ? "fully nested · two tube"
                  : `semi-nested · two tube — the ${result.nesting.shares} primer is shared`}
              </span>
            </div>
            {result.nesting.note ? (
              <p className="text-xs leading-relaxed text-muted-foreground">{result.nesting.note}</p>
            ) : null}
            {result.protocol ? (
              <div className="rounded-lg border border-border/60 bg-surface-wash/25 px-3 py-2 text-xs">
                <span className="font-medium">Carry-over prevention: </span>
                <span className="text-muted-foreground">
                  {result.protocol.selection === "dutp-ung-strategy-only" ||
                  result.protocol.selection === "dUTP-UNG"
                    ? "dUTP / UNG strategy recorded; no generic bench recipe inferred. "
                    : "Not selected. "}
                  {result.protocol.note}
                </span>
              </div>
            ) : null}
            {result.nests.map((nest, index) => (
              <NestCard key={index} nest={nest} index={index + 1} />
            ))}
          </section>

          <OrderSheet result={result} />
        </>
      )}

      <WhatWasTried result={result} />
      <TheAssay result={result} />
      <RuntimeProvenance provenance={result.provenance} />
    </div>
  );
}

function ReactionTimeline({ result }: { result: NestedResult }) {
  const rounds = result.round_reactions ?? {};
  const r1 = rounds.round1;
  const r2 = rounds.round2;
  const transfer = asRecord(result.transfer);
  if (!r1 && !r2 && !transfer) return null;
  const cleanup = transfer ? asRecord(transfer.cleanup) : null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Two-round reaction timeline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 md:grid-cols-[1fr_auto_1fr_auto_1fr] md:items-stretch">
          <TimelineStep
            title="Round 1"
            subtitle={r1?.polymerase_identity ?? "polymerase not recorded"}
            detail={thermalSummary(r1?.thermal_program)}
          />
          <div className="hidden items-center text-muted-foreground md:flex">→</div>
          <TimelineStep
            title="Transfer / cleanup"
            subtitle={String(transfer?.mode ?? "not recorded")}
            detail={transferSummary(transfer)}
          />
          <div className="hidden items-center text-muted-foreground md:flex">→</div>
          <TimelineStep
            title="Round 2"
            subtitle={r2?.polymerase_identity ?? "polymerase not recorded"}
            detail={thermalSummary(r2?.thermal_program)}
          />
        </div>
        {cleanup ? (
          <div className="rounded-md border border-primary/20 bg-primary/5 p-2.5 text-xs leading-relaxed text-muted-foreground">
            Named cleanup authority:{" "}
            {String(
              cleanup.selection ?? cleanup.id ?? transfer?.cleanup_protocol ?? "selected cleanup",
            )}
            . {cleanupProgram(cleanup)} Numeric values belong only to this named source branch.
          </div>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">
          Round programs and transfer are separate provenance objects. Primer-screening Tm does not
          silently become a cycling program, and selecting cleanup does not prove carry-over
          control.
        </p>
      </CardContent>
    </Card>
  );
}

function TimelineStep({
  title,
  subtitle,
  detail,
}: {
  title: string;
  subtitle: string;
  detail: string;
}) {
  return (
    <div className="rounded-md border p-2.5">
      <p className="text-xs font-medium">{title}</p>
      <p className="mt-1 text-xs text-foreground">{subtitle}</p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{detail}</p>
    </div>
  );
}

function NestedFalseProductGraph({ value }: { value?: Record<string, unknown> }) {
  if (!value) return null;
  const edges = Array.isArray(value.edges) ? (value.edges as Array<Record<string, unknown>>) : [];
  const propagating = Number(value.propagating_outer_products ?? 0);
  return (
    <div className="space-y-2 rounded-md border border-border/60 bg-surface-wash/20 p-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-medium">Causal nested false-product graph</p>
        <span
          className={propagating > 0 ? "text-xs text-warning" : "text-xs text-muted-foreground"}
        >
          {propagating} propagating outer product(s)
        </span>
      </div>
      {value.checked === false ? (
        <p className="text-xs text-muted-foreground">
          No finite background was supplied; causal propagation was not evaluated.
        </p>
      ) : null}
      {edges.slice(0, 8).map((edge, index) => {
        const product = asRecord(edge.outer_product);
        return (
          <div key={index} className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="rounded border px-1.5 py-0.5">
              {String(product?.contig ?? "background")}:{String(product?.start ?? "?")}–
              {String(product?.end ?? "?")}
            </span>
            <span className="text-muted-foreground">→ inner rescan →</span>
            <span
              className={
                edge.risk === "nested-false-product"
                  ? "font-medium text-warning"
                  : "text-muted-foreground"
              }
            >
              {String(edge.inner_product_count ?? 0)} product(s) ·{" "}
              {String(edge.risk ?? "unresolved")}
            </span>
          </div>
        );
      })}
      <p className="text-xs leading-relaxed text-muted-foreground">
        {String(
          value.claim_boundary ??
            "Finite supplied background only; absence is not global specificity.",
        )}
      </p>
    </div>
  );
}

function thermalSummary(program: Array<Record<string, unknown>> | undefined) {
  if (!program?.length)
    return "No explicit thermal stages recorded; use the named round SOP rather than inferring from screening Tm.";
  return `${program.length} recorded thermal stage(s): ${program
    .slice(0, 3)
    .map((stage) => String(stage.name ?? stage.stage ?? stage.temperature_c ?? "stage"))
    .join(" → ")}${program.length > 3 ? " …" : ""}`;
}

function transferSummary(transfer: Record<string, unknown> | null) {
  if (!transfer) return "Transfer provenance not recorded.";
  const bits = [
    transfer.transfer_volume_ul != null ? `${String(transfer.transfer_volume_ul)} µL` : null,
    transfer.dilution_factor != null ? `${String(transfer.dilution_factor)}× dilution` : null,
    transfer.cleanup_protocol ? `cleanup ${String(transfer.cleanup_protocol)}` : null,
  ].filter(Boolean);
  return bits.join(" · ") || "Mode recorded; numeric transfer fields unresolved.";
}

function cleanupProgram(cleanup: Record<string, unknown>) {
  const numeric = asRecord(cleanup.numeric) ?? asRecord(cleanup.program) ?? cleanup;
  const stages = Array.isArray(numeric.stages)
    ? (numeric.stages as Array<Record<string, unknown>>)
    : [];
  if (stages.length)
    return stages
      .map(
        (stage) =>
          `${String(stage.temperature_c ?? "?")} °C / ${String(stage.minutes ?? stage.seconds ?? "?")} ${stage.minutes != null ? "min" : "s"}`,
      )
      .join(" → ");
  const temp = numeric.incubation_temperature_c ?? numeric.temperature_c;
  const mins = numeric.incubation_minutes ?? numeric.minutes;
  return temp != null
    ? `${String(temp)} °C${mins != null ? ` / ${String(mins)} min` : ""}.`
    : "Program is retained in the source authority.";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function TheTemplate({ result }: { result: NestedResult }) {
  const { target } = result;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">What arrived</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
        <Fact label="Name" value={target.name || "unnamed"} />
        <Fact label="Length" value={`${count(target.length)} bp`} />
        <Fact label="GC" value={`${target.gc_percent}%`} />
      </CardContent>
    </Card>
  );
}

/**
 * One nested design.
 *
 * The bar is the point of this component. Reading four positions off a table
 * and holding them in your head is exactly the step where somebody decides two
 * pairs are nested when they are not.
 */
function NestCard({ nest, index }: { nest: Nest; index: number }) {
  const outerStart = nest.outer.left_at.start;
  const outerEnd = nest.outer.right_at.start + nest.outer.right_at.length;
  const span = outerEnd - outerStart || 1;

  const at = (position: number) => ((position - outerStart) / span) * 100;
  const innerStart = at(nest.inner.left_at.start);
  const innerWidth = at(nest.inner.right_at.start + nest.inner.right_at.length) - innerStart;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-[13px] font-medium">
          <span>
            Design {index} — {nest.inner.product_size} bp read from a {nest.outer.product_size} bp
            first round
          </span>
          <span className="text-xs font-normal text-muted-foreground tabular-nums">
            moved in {nest.moved_in.left} / {nest.moved_in.right} bases
          </span>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Round one across the whole width, round two inside it. */}
        <div aria-hidden="true" className="space-y-1">
          <div className="relative h-3 rounded bg-muted">
            <div className="absolute inset-y-0 left-0 w-full rounded bg-primary/20 ring-1 ring-primary/40" />
            <div
              className="absolute inset-y-0 rounded bg-primary/50 ring-1 ring-primary/70"
              style={{ left: `${innerStart}%`, width: `${innerWidth}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
            <span>{count(outerStart)}</span>
            <span>{count(outerEnd)}</span>
          </div>
        </div>
        <p className="sr-only">
          The first round runs from base {outerStart} to {outerEnd}. The second round runs from base{" "}
          {nest.inner.left_at.start} to {nest.inner.right_at.start + nest.inner.right_at.length},
          inside it.
        </p>

        <Round title="First round" round={nest.outer} />
        <Round
          title="Second round"
          round={nest.inner}
          note={
            nest.shares === "nothing"
              ? undefined
              : `Reuses the ${nest.shares} primer from the first round.`
          }
        />
        {nest.tm_note ? (
          <p className="rounded-md border border-border/60 bg-surface-wash/25 px-2.5 py-2 text-xs leading-relaxed text-muted-foreground">
            {nest.tm_note}
          </p>
        ) : null}

        {/*
         * One block per set of oligos that share a tube, because that is the
         * difference the scan is about. A two-tube nest is scanned twice —
         * only the inner pair is present in the second round — and a
         * single-tube one is scanned once with all four, where an outer primer
         * facing an inner one is a real product rather than a false alarm.
         */}
        {Object.entries(nest.off_targets ?? {}).map(([where, off]) => (
          <div key={where} className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">{where}</p>
            <ScanFindings off={off} intended={2} />
          </div>
        ))}
        <NestedFalseProductGraph
          value={nest.nested_false_product_graph as Record<string, unknown> | undefined}
        />
      </CardContent>
    </Card>
  );
}

function Round({ title, round, note }: { title: string; round: NestedRound; note?: string }) {
  return (
    <div className="space-y-1.5 border-t pt-2.5 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h3 className="text-xs font-medium">{title}</h3>
        <span className="text-xs text-muted-foreground tabular-nums">
          {round.product_size} bp · Tm apart by {round.tm_difference} °C
        </span>
      </div>
      {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
      <Oligo role="Forward" oligo={round.left} at={round.left_at} />
      <Oligo role="Reverse" oligo={round.right} at={round.right_at} />
    </div>
  );
}

function Oligo({
  role,
  oligo,
  at,
}: {
  role: string;
  oligo: NestedRound["left"];
  at: { start: number; length: number };
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs">
      <span className="w-14 shrink-0 text-muted-foreground">{role}</span>
      <code className="font-mono">{oligo.sequence}</code>
      <span className="text-muted-foreground tabular-nums">
        {oligo.length} nt · {oligo.gc_percent}% GC · {oligo.tm} °C · at {count(at.start)}
      </span>
    </div>
  );
}

/**
 * The outer pairs that held no inner pair.
 *
 * "No nested design exists" and "each outer pair we tried was eighty bases too
 * short" are different problems with different fixes.
 */
function WhatWasTried({ result }: { result: NestedResult }) {
  if (result.rejected.length === 0 && result.nests.length > 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          {result.outer_considered} first-round pair
          {result.outer_considered === 1 ? "" : "s"} were tried
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm leading-relaxed text-muted-foreground">
          The lowest-penalty first-round pair can still leave no room inside it, so each was tried
          in turn rather than only the first.
        </p>
        {result.rejected.length > 0 ? (
          <ul className="space-y-1.5">
            {result.rejected.map((entry, index) => (
              <li key={index} className="text-xs">
                <span className="text-foreground tabular-nums">
                  {maybeCount(entry.outer_at[0])}–{maybeCount(entry.outer_at[1])} (
                  {entry.outer_product} bp)
                </span>{" "}
                <span className="text-muted-foreground">— {entry.detail}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

function NothingFound({ result }: { result: NestedResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">No nested design</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed text-muted-foreground">{result.why_nothing}</p>
      </CardContent>
    </Card>
  );
}

/** Both rounds, named by round so nobody puts the inner pair in the first tube. */
function OrderSheet({ result }: { result: NestedResult }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          What to order — {result.order_sheet.length} oligos
        </CardTitle>
        <OrderActions
          lines={result.order_sheet}
          kind="nested-primers"
          conditions={result.reaction}
        />
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <caption className="sr-only">Nested PCR primer sequences and thermodynamics</caption>
            <thead>
              <tr className="text-left text-muted-foreground">
                <th scope="col" className="pr-3 pb-1 font-normal">
                  Name
                </th>
                <th scope="col" className="pr-3 pb-1 font-normal">
                  Sequence (5′ → 3′)
                </th>
                <th scope="col" className="pr-3 pb-1 font-normal">
                  nt
                </th>
                <th scope="col" className="pb-1 font-normal">
                  Tm
                </th>
              </tr>
            </thead>
            <tbody>
              {result.order_sheet.map((line) => (
                <tr key={line.name}>
                  <td
                    className={cn(
                      "py-0.5 pr-3 font-mono whitespace-nowrap",
                      line.name.includes("i") ? "" : "text-muted-foreground",
                    )}
                  >
                    {line.name}
                  </td>
                  <td className="py-0.5 pr-3 font-mono">{line.sequence}</td>
                  <td className="py-0.5 pr-3 tabular-nums">{line.length}</td>
                  <td className="py-0.5 tabular-nums">{line.tm}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Names ending <code className="font-mono">o</code> are the first round and{" "}
          <code className="font-mono">i</code> the second. The second round goes in a fresh tube
          with a little of the first reaction as its template — putting both pairs in one tube is
          not a nested PCR.
        </p>
      </CardContent>
    </Card>
  );
}

function TheAssay({ result }: { result: NestedResult }) {
  const assay = result.assay;
  if (!assay?.id) return null;
  const set = Object.entries(assay.defaults);
  if (set.length === 0 && assay.overruled.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          What {assay.name || assay.id} changed
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-1">
          {set.map(([field, value]) => {
            const beaten = assay.overruled.find((entry) => entry.field === field);
            return (
              <li key={field} className="flex flex-wrap items-baseline gap-x-2 text-xs">
                <span className="font-mono text-foreground">{field}</span>
                <span
                  className={cn("tabular-nums", beaten && "text-muted-foreground line-through")}
                >
                  {String(value)}
                </span>
                {beaten ? (
                  <>
                    <span className="text-foreground tabular-nums">{String(beaten.used)}</span>
                    <span className="text-muted-foreground">— {beaten.because}</span>
                  </>
                ) : null}
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
