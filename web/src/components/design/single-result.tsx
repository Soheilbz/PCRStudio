"use client";

/**
 * What a single-primer design produced.
 *
 * There is no partner here, so every column the other views lead with is gone:
 * no product size, no matched temperatures, no cross-dimer. What replaces them
 * is placement, and placement is the whole design.
 *
 * A Sanger trace does not start where the primer ends. The first few dozen
 * bases come back as a smear and the read fades after several hundred, so the
 * primer has a window it must put its target inside — far enough ahead to clear
 * the smear, close enough to still be legible on arrival. A primer that is
 * beautiful by every thermodynamic measure and sitting three hundred bases from
 * its target is a wasted reaction, and no melting temperature fixes it.
 *
 * So this view draws the read: where the primer sits, where the unreadable part
 * ends, where the target falls, and how much legible trace is left after it.
 * The two numbers somebody actually decides on — how far the target is, and
 * what is left over — are the ones in front.
 */

import { RuntimeProvenance } from "./result-primitives";
import { ScanFindings } from "@/components/design/scan";
import { OrderActions } from "./order-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count } from "@/lib/numbers";
import type { SinglePrimerCandidate, SingleResult } from "@/lib/api/types";
import { SingleClosurePanels } from "./engine-closure-panels";

export function SingleResultView({ result }: { result: SingleResult }) {
  if (result.primers.length === 0) {
    return (
      <div className="space-y-5">
        <SingleClosurePanels result={result} />
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">No primer here</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs leading-relaxed text-muted-foreground">
            <p>{result.why_nothing}</p>
            {result.considered ? <p className="font-mono">{result.considered}</p> : null}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {result.race_placement ? <RacePlacement placement={result.race_placement} /> : null}
      {result.read ? <TheRead read={result.read} firstPrimer={result.primers[0]} /> : null}
      {result.sequencing_context ? <SequencingContext context={result.sequencing_context} /> : null}
      {result.protocol ? <SequencingProtocol protocol={result.protocol} /> : null}
      {result.race_adapter ? <RaceAdapter adapter={result.race_adapter} /> : null}
      {result.race_context ? <RaceContext context={result.race_context} /> : null}
      <SingleClosurePanels result={result} />
      {result.primers.map((primer, index) => (
        <PrimerCard
          key={primer.sequence}
          primer={primer}
          index={index + 1}
          readLength={result.read?.read_length}
        />
      ))}
      <OrderSheet result={result} />
      <RuntimeProvenance provenance={result.provenance} />
    </div>
  );
}

function SequencingContext({
  context,
}: {
  context: NonNullable<SingleResult["sequencing_context"]>;
}) {
  const instrument =
    context.instrument === "other" && context.instrument_name
      ? context.instrument_name
      : context.instrument;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Sequencing run handoff</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs leading-relaxed">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          <Fact label="Instrument" value={instrument} />
          <Fact label="Trace" value={context.trace_status} />
          <Fact label="Quality" value={context.quality_status} />
        </dl>
        {context.facility_sop ? (
          <p>
            <span className="font-medium text-foreground">Facility/SOP:</span>{" "}
            {context.facility_sop}
          </p>
        ) : null}
        <p className="text-muted-foreground">{context.note}</p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          {context.required_run_evidence.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function SequencingProtocol({ protocol }: { protocol: NonNullable<SingleResult["protocol"]> }) {
  const cycle = protocol.cycling;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Selected sequencing protocol</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs leading-relaxed">
        <p className="font-medium text-foreground">{protocol.selection}</p>
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          <Fact label="Reaction volumes" value={`${protocol.reaction_volumes_uL.join(" / ")} µL`} />
          <Fact label="Primer input" value={`${protocol.primer_input_pmol} pmol`} />
          <Fact label="Cycling" value={`${cycle.cycles} cycles · 96 / 50 / 60 °C`} />
        </dl>
        <p className="text-muted-foreground">
          Cleanup: {protocol.cleanup_options.join(", ")}. {protocol.note}
        </p>
      </CardContent>
    </Card>
  );
}

function RaceContext({ context }: { context: NonNullable<SingleResult["race_context"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          RACE provenance and claim boundary
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs leading-relaxed">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          <Fact label="Substrate" value={context.substrate} />
          <Fact label="Round" value={context.round} />
          <Fact label="End status" value={context.end_status} />
          {context.polyadenylated !== undefined && context.polyadenylated !== null ? (
            <Fact label="Poly(A) confirmed" value={context.polyadenylated ? "yes" : "no"} />
          ) : null}
        </dl>
        <p>
          <span className="font-medium text-foreground">Preparation:</span> {context.preparation}
        </p>
        {context.caller_sop_revision ? (
          <p>
            <span className="font-medium text-foreground">Caller-reviewed SOP/manual:</span>{" "}
            {context.caller_sop_revision}
          </p>
        ) : null}
        {context.caller_sop_sha256 ? (
          <p className="font-mono text-xs break-all text-muted-foreground">
            SHA-256 {context.caller_sop_sha256}
          </p>
        ) : null}
        <p className="text-muted-foreground">{context.note}</p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          {context.validation_required.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function RaceAdapter({ adapter }: { adapter: NonNullable<SingleResult["race_adapter"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Selected RACE partner</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs leading-relaxed">
        <p className="font-medium text-foreground">{adapter.name}</p>
        <p className="font-mono break-all text-muted-foreground">{adapter.sequence}</p>
        <p className="text-muted-foreground">
          The interaction screen is limited to this named kit-provided partner. Adapter
          compatibility, transcript-end identity and product interpretation still require the
          selected RACE protocol and experimental controls.
        </p>
      </CardContent>
    </Card>
  );
}

function RacePlacement({ placement }: { placement: NonNullable<SingleResult["race_placement"]> }) {
  const [start, span] = placement.search_region;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">RACE GSP placement</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
          <Fact label="Transcript end" value={placement.race_direction} />
          <Fact label="Primer direction" value={placement.direction} />
          <Fact label="Known-sequence search region" value={`${start} + ${span} bases`} />
        </dl>
        <p className="text-xs leading-relaxed text-muted-foreground">{placement.note}</p>
      </CardContent>
    </Card>
  );
}

/** The Sanger provider-defined window every candidate had to sit in. */
function TheRead({
  read,
  firstPrimer,
}: {
  read: NonNullable<SingleResult["read"]>;
  firstPrimer?: SinglePrimerCandidate;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Sequencing placement envelope</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
          <Fact label="Reading" value={read.direction} />
          <Fact label="Unreadable start" value={`${read.dead_zone} bases`} />
          <Fact label="Usable read length" value={`${read.read_length} bases`} />
          <Fact label="Allowed distance" value={`${read.nearest}–${read.furthest} bases`} />
        </dl>
        <p className="text-xs leading-relaxed text-muted-foreground">{read.note}</p>
        {firstPrimer?.window?.widened ? (
          <p className="rounded-xl border border-warning/40 bg-warning/5 p-2.5 text-xs leading-relaxed">
            Nothing acceptable sat at the ideal distance, so the search widened its band{" "}
            {firstPrimer.window.widened} time
            {firstPrimer.window.widened === 1 ? "" : "s"}.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** One primer, led by what its read would actually cover. */
function PrimerCard({
  primer,
  index,
  readLength,
}: {
  primer: SinglePrimerCandidate;
  index: number;
  readLength?: number;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-baseline justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          Primer {index} — base {count(primer.at)}
        </CardTitle>
        <span className="text-xs text-muted-foreground">
          {primer.reaches !== undefined ? (
            <>
              target starts{" "}
              <span className="font-medium text-foreground tabular-nums">{primer.reaches}</span>{" "}
              bases in{primer.wrapped_to_reach ? ", round the join" : ""}
            </>
          ) : (
            <>GSP points {primer.direction} toward the selected transcript end</>
          )}
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
        {readLength !== undefined &&
        primer.window &&
        primer.reaches !== undefined &&
        primer.spare !== undefined ? (
          <ReadPicture primer={primer} readLength={readLength} />
        ) : null}

        <div className="rounded-md border p-2.5">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-xs font-medium">{primer.direction}</span>
            <span className="text-xs text-muted-foreground tabular-nums">
              {primer.tm} °C · {primer.length} nt · {primer.gc_percent}% GC
            </span>
          </div>
          <p className="mt-1 font-mono text-xs break-all">{primer.sequence}</p>
        </div>

        {primer.reaches !== undefined && primer.spare !== undefined ? (
          <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
            <Fact label="Target starts after" value={`${primer.reaches} bases`} />
            <Fact label="Usable trace left over" value={`${primer.spare} bases`} />
          </dl>
        ) : null}

        <p className="text-xs leading-relaxed text-muted-foreground">{primer.note}</p>

        {primer.adapter_dimer ? (
          <div className="rounded-md border p-2.5 text-xs leading-relaxed">
            <p className="font-medium">RACE GSP / selected-partner interaction diagnostic</p>
            <p className="mt-1 text-muted-foreground">
              {primer.adapter_dimer.partner}: ΔG {primer.adapter_dimer.dg} kcal/mol · Tm{" "}
              {primer.adapter_dimer.tm} °C · internal watch line{" "}
              {primer.adapter_dimer.watch_threshold_dg} kcal/mol ·
              {primer.adapter_dimer.flagged ? " flagged for review" : " not flagged"}.
            </p>
            <p className="mt-1 text-muted-foreground">
              Decision role: {primer.adapter_dimer.decision_role}.{" "}
              {primer.adapter_dimer.temperature_role}. {primer.adapter_dimer.note}
            </p>
          </div>
        ) : null}

        {/*
         * Where else these oligos sit. Rendered from the same component every
         * other engine uses, so the same finding is not described two ways.
         * `intended` is how many sites this design is *meant* to have on its
         * own template, so anything past that is a second place.
         */}
        <ScanFindings off={primer.off_targets} intended={1} />
      </CardContent>
    </Card>
  );
}

/**
 * The read, drawn from the primer's 3' end.
 *
 * Three regions on one bar: the part that comes back unreadable, the part
 * before the target, and the target itself. Seeing that the target clears the
 * smear is the check somebody would otherwise do by subtracting two numbers.
 */
function ReadPicture({
  primer,
  readLength,
}: {
  primer: SinglePrimerCandidate;
  readLength: number;
}) {
  if (!primer.window || primer.reaches === undefined || primer.spare === undefined) return null;
  const width = (bases: number) => `${(bases / Math.max(readLength, 1)) * 100}%`;
  const targetLength = Math.max(readLength - primer.reaches - primer.spare, 0);

  return (
    <div aria-hidden="true" className="space-y-1.5">
      <div className="relative flex h-7 overflow-hidden rounded bg-muted">
        <div
          className="h-full bg-destructive/25"
          style={{ width: width(primer.window.nearest) }}
          title="unreadable"
        />
        <div
          className="h-full"
          style={{ width: width(Math.max(primer.reaches - primer.window.nearest, 0)) }}
        />
        <div className="h-full bg-primary/40" style={{ width: width(targetLength) }} />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
        <span>3′ end</span>
        <span>
          smear {primer.window.nearest} · target at {primer.reaches} · {primer.spare} to spare
        </span>
        <span>{readLength}</span>
      </div>
    </div>
  );
}

function OrderSheet({ result }: { result: SingleResult }) {
  const assayId = result.assay?.id;
  const historicalReason =
    assayId === "sequencing-primer" && !result.sequencing_context
      ? "This saved sequencing-primer result predates the current explicit read-envelope/handoff contract. Regenerate after recording the provider read envelope before ordering."
      : assayId === "race" && (!result.race_context || !result.race_adapter)
        ? "This saved RACE result predates the current versioned adapter/preparation contract. Regenerate under a current adapter branch before ordering."
        : null;
  if (historicalReason) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">
            Historical design — do not order
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs leading-relaxed text-muted-foreground">{historicalReason}</p>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          What to order — {result.order_sheet.length} oligo
          {result.order_sheet.length === 1 ? "" : "s"}
        </CardTitle>
        <OrderActions
          lines={result.order_sheet}
          kind="single-primer"
          conditions={result.reaction}
        />
      </CardHeader>
      <CardContent className="space-y-2">
        {result.order_sheet.map((line) => (
          <div key={line.name} className="rounded-md border p-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-mono text-xs font-medium">{line.name}</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {line.length} nt · {line.tm} °C
              </span>
            </div>
            <p className="mt-1 font-mono text-xs break-all">{line.sequence}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-foreground">{value}</dd>
    </div>
  );
}
