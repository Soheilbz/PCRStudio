"use client";

/**
 * What a hydrolysis-probe design produced.
 *
 * This view exists to put one number in front of somebody: how far the probe
 * melts above its own primers.
 *
 * It is the whole mechanism. The probe is destroyed rather than extended, so it
 * has to be already bound when the polymerase arrives — which means it melts
 * several degrees above the primers rather than alongside them, the opposite of
 * every other relationship this project manages. A probe that melts with its
 * primers gives a reaction that amplifies perfectly and reports nothing, and on
 * a plate that reads as absent template rather than as a bad design.
 *
 * So the separation is the headline of each card rather than a column in a
 * table, and the temperatures are shown as a scale you can see the gap on.
 *
 * The other thing said out loud is which reaction the numbers were computed in.
 * Primer3 keeps the internal oligo's buffer separate from the primers', and
 * leaving it at its defaults puts the two temperatures nearly nine degrees
 * apart on the same oligo — so anybody comparing these figures against another
 * tool's needs to know both were measured in the same tube.
 */

import { ScanFindings } from "@/components/design/scan";
import { OrderActions } from "./order-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProbeAssay, ProbeResult } from "@/lib/api/types";
import { ProbeClosurePanels } from "./engine-closure-panels";

export function ProbeResultView({ result }: { result: ProbeResult }) {
  if (result.assays.length === 0) {
    return (
      <div className="space-y-5">
        {result.protocol ? <ProbeProtocol result={result} /> : null}
        <ProbeClosurePanels result={result} />
        <IndependentStructure result={result} />
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">No assay here</CardTitle>
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
      <TheWindows result={result} />
      {result.protocol ? <ProbeProtocol result={result} /> : null}
      <ProbeClosurePanels result={result} />
      <IndependentStructure result={result} />
      {result.assays.map((assay, index) => (
        <AssayCard key={assay.probe.sequence} assay={assay} index={index + 1} />
      ))}
      <OrderabilityNotice result={result} />
      <OrderSheet result={result} />
      <Provenance result={result} />
    </div>
  );
}

function IndependentStructure({ result }: { result: ProbeResult }) {
  const evidence = result.independent_probe_structure;
  if (!evidence) return null;
  const folds = Object.entries(evidence.folds);
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-[13px] font-medium">
          Independent probe-structure evidence
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs leading-relaxed">
        <p className="text-muted-foreground">
          {evidence.checked
            ? `${evidence.model ?? "Independent structure model"} evaluated each full probe${evidence.celsius != null ? ` at ${evidence.celsius} °C` : ""}.`
            : "The optional independent structure validator did not run for this design."}{" "}
          This evidence is advisory and does not silently replace Primer3 as the candidate
          authority.
        </p>
        {folds.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <caption className="sr-only">Probe folding results</caption>
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th scope="col" className="pr-3 font-normal">
                    Probe
                  </th>
                  <th scope="col" className="pr-3 font-normal">
                    ΔG
                  </th>
                  <th scope="col" className="font-normal">
                    Structure
                  </th>
                </tr>
              </thead>
              <tbody>
                {folds.map(([name, fold]) => (
                  <tr key={name}>
                    <td className="py-0.5 pr-3 font-medium">{name}</td>
                    <td className="py-0.5 pr-3 tabular-nums">
                      {fold.dg == null ? "—" : `${fold.dg} kcal/mol`}
                    </td>
                    <td className="py-0.5 font-mono text-muted-foreground">
                      {fold.structure ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {evidence.note ? <p className="text-xs text-muted-foreground">{evidence.note}</p> : null}
      </CardContent>
    </Card>
  );
}

function ProbeProtocol({ result }: { result: ProbeResult }) {
  type Protocol = {
    selection: string;
    application_scope?: string;
    probe_chemistry?: string;
    primer_final_concentration_nM?: number;
    probe_final_concentration_nM?: number;
    probe_length_nt?: { min: number; max: number };
    reporter_options?: string[];
    quencher?: string;
    amplicon_bp?: { min: number; max: number };
    source_identity?: string;
    source_revision?: string;
    source_documents?: Array<{
      identity: string;
      publication?: string;
      revision?: string;
      revision_date?: string;
      supports: string[];
    }>;
    note?: string;
  };
  const protocol = result.protocol as Protocol | undefined;
  if (!protocol) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Selected probe chemistry</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs leading-relaxed">
        <p className="font-medium text-foreground">{protocol.selection}</p>
        {protocol.application_scope ? (
          <p className="text-xs text-muted-foreground">
            Scope: {String(protocol.application_scope)}
          </p>
        ) : null}
        {protocol.source_identity ? (
          <p className="text-xs text-muted-foreground">
            Source authority: {protocol.source_identity}
            {protocol.source_revision
              ? ` · ${protocol.source_revision}`
              : " · exact source revision not recorded"}
          </p>
        ) : null}
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          <Fact label="Chemistry" value={protocol.probe_chemistry ?? "unresolved"} />
          <Fact
            label="Primer / probe input"
            value={`${protocol.primer_final_concentration_nM ?? "?"} / ${protocol.probe_final_concentration_nM ?? "?"} nM`}
          />
          <Fact
            label="Probe length"
            value={
              protocol.probe_length_nt
                ? `${protocol.probe_length_nt.min}–${protocol.probe_length_nt.max} nt`
                : "unresolved"
            }
          />
          <Fact
            label="Reporter options"
            value={protocol.reporter_options?.join(" / ") ?? "unresolved"}
          />
          <Fact label="Quencher" value={protocol.quencher ?? "unresolved"} />
          <Fact
            label="Amplicon starting window"
            value={
              protocol.amplicon_bp
                ? `${protocol.amplicon_bp.min}–${protocol.amplicon_bp.max} bp`
                : "unresolved"
            }
          />
        </dl>
        {protocol.source_documents?.length ? (
          <div className="space-y-1 text-xs text-muted-foreground">
            {protocol.source_documents.map((source) => (
              <p key={`${source.identity}-${source.publication ?? "unversioned"}`}>
                {source.identity}
                {source.publication ? ` · ${source.publication}` : ""}
                {source.revision ? ` · revision ${source.revision}` : ""}
                {source.revision_date ? ` · ${source.revision_date}` : ""}:{" "}
                {source.supports.join("; ")}
              </p>
            ))}
          </div>
        ) : null}
        <p className="text-xs text-muted-foreground">{protocol.note}</p>
      </CardContent>
    </Card>
  );
}

/**
 * The two windows, side by side, because they are not one window rescaled.
 *
 * Showing them together is the point: the probe's floor sits above the primers'
 * ceiling, and seeing that is what makes the rest of the result legible.
 */
function TheWindows({ result }: { result: ProbeResult }) {
  const primers = result.constraints.primers;
  const probe = result.constraints.probe;
  const from = (window: Record<string, number | string | null | undefined>) => {
    const minimum = window.tm_min ?? "—";
    const maximum = window.tm_max ?? "—";
    return `${minimum}–${maximum} °C`;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          What the two oligo kinds were held to
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
          <Fact label="Primers" value={from(primers)} />
          <Fact label="Probe" value={from(probe)} />
          <Fact
            label="Probe window came from"
            value={String(probe.from ?? "historical / source not recorded")}
          />
        </dl>
        {probe.note ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{String(probe.note)}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** One pair with its probe, led by the separation between them. */
function AssayCard({ assay, index }: { assay: ProbeAssay; index: number }) {
  const coolest = Math.min(assay.left.tm, assay.right.tm);
  const warmest = Math.max(assay.left.tm, assay.right.tm);

  return (
    <Card>
      <CardHeader className="flex flex-row items-baseline justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          Assay {index} — {assay.product_size} bp
        </CardTitle>
        <span className="text-xs text-muted-foreground">
          probe{" "}
          <span className="font-medium text-foreground tabular-nums">
            +{assay.probe.above_primers} °C
          </span>{" "}
          above the warmer primer
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* The gap, drawn. Two bands on one axis so the separation is a
            distance you can see rather than a subtraction you have to do. */}
        <Scale coolest={coolest} warmest={warmest} probe={assay.probe.tm} />

        <div className="space-y-2">
          <Oligo role="Forward" sequence={assay.left.sequence} tm={assay.left.tm} />
          <Oligo role="Reverse" sequence={assay.right.sequence} tm={assay.right.tm} />
          <Oligo
            role="Probe"
            sequence={assay.probe.sequence}
            tm={assay.probe.tm}
            note={`5′ ${assay.probe.first_base} · ${assay.probe.after_left} bp after the forward primer`}
            highlight
          />
        </div>

        <p className="text-xs leading-relaxed text-muted-foreground">{assay.probe.note}</p>

        {/*
         * Where else these oligos sit. Rendered from the same component every
         * other engine uses, so the same finding is not described two ways.
         * `intended` is how many sites this design is *meant* to have on its
         * own template, so anything past that is a second place.
         */}
        <ScanFindings off={assay.off_targets} intended={3} />
      </CardContent>
    </Card>
  );
}

/**
 * Where the three oligos melt, on one axis.
 *
 * Deliberately not a chart library: what has to be legible is one gap, and a
 * bar with two marks on it says that more directly than axes and gridlines
 * would.
 */
function Scale({ coolest, warmest, probe }: { coolest: number; warmest: number; probe: number }) {
  const low = Math.floor(coolest - 4);
  const high = Math.ceil(probe + 4);
  const place = (value: number) => ((value - low) / Math.max(high - low, 1)) * 100;

  return (
    <div aria-hidden="true" className="space-y-1.5">
      <div className="relative h-7 rounded bg-muted">
        <div
          className="absolute inset-y-0 rounded-l bg-primary/25"
          style={{ left: `${place(coolest)}%`, width: `${place(warmest) - place(coolest)}%` }}
        />
        <div className="absolute inset-y-0 w-0.5 bg-primary" style={{ left: `${place(probe)}%` }} />
        <div
          className="absolute inset-y-0 border-l border-dashed border-primary/40"
          style={{ left: `${place(warmest)}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
        <span>{low} °C</span>
        <span>
          primers {coolest}–{warmest} · probe {probe}
        </span>
        <span>{high} °C</span>
      </div>
    </div>
  );
}

/**
 * One oligo, wrapping rather than scrolling.
 *
 * A sequence is the thing people copy, so it is shown whole on any width; a
 * card that scrolls sideways hides the end of the very thing it is displaying.
 */
function Oligo({
  role,
  sequence,
  tm,
  note,
  highlight,
}: {
  role: string;
  sequence: string;
  tm: number;
  note?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={
        highlight
          ? "rounded-md border border-primary/30 bg-primary/5 p-2.5"
          : "rounded-md border p-2.5"
      }
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs font-medium">{role}</span>
        <span className="text-xs text-muted-foreground tabular-nums">{tm} °C</span>
      </div>
      <p className="mt-1 font-mono text-xs break-all">{sequence}</p>
      {note ? <p className="mt-1 text-xs text-muted-foreground">{note}</p> : null}
    </div>
  );
}

function effectiveOrderability(result: ProbeResult) {
  return (
    result.orderability ?? {
      orderable: false as const,
      status: "historical-result-orderability-not-recorded",
      note: "This saved pair-and-probe result predates the current chemistry/orderability contract. Conventional Thermo Fisher/IDT branches are now executable only with current authority and orderability provenance; this historical result lacks that record, so supplier lines remain saved evidence only and must not be used to order oligos.",
    }
  );
}

function OrderabilityNotice({ result }: { result: ProbeResult }) {
  const orderability = effectiveOrderability(result);
  if (orderability.orderable) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Diagnostic design — do not order</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-xs leading-relaxed">
        <p className="font-medium">{orderability.status}</p>
        <p className="text-muted-foreground">{orderability.note}</p>
      </CardContent>
    </Card>
  );
}

function OrderSheet({ result }: { result: ProbeResult }) {
  if (!effectiveOrderability(result).orderable || result.order_sheet.length === 0) return null;
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          What to order — {result.order_sheet.length} oligos
        </CardTitle>
        <OrderActions lines={result.order_sheet} kind="probe-assay" conditions={result.reaction} />
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
            {/* A probe ordered as a plain oligo is a plain oligo, and it will
                report nothing. The one line on the sheet that is not sequence. */}
            {line.note ? (
              <p className="mt-1 text-xs font-medium text-primary">{line.note}</p>
            ) : null}
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

function Provenance({ result }: { result: ProbeResult }) {
  const made = result.provenance;
  if (!made) return null;
  return (
    <p className="text-xs leading-relaxed text-muted-foreground">
      Computed by primer3-py {made.primer3_py} (libprimer3{" "}
      {made.tool_versions?.libprimer3 ?? "not reported"}) under {made.model.name}, worker{" "}
      {made.worker}, on Python {made.python} ({made.platform}). The probe was measured in the same
      reaction as the primers, so the two temperatures can be compared with each other. {made.note}
    </p>
  );
}
