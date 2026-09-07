"use client";

/**
 * Topology-aware site-directed mutagenesis result.
 *
 * The current contract deliberately keeps Q5, QuikChange Lightning, Lightning Multi and the
 * NEBuilder multi-site route separate. A formula value published by Agilent is
 * not relabelled as Primer3 Tm, and a route-to-assembly plan is not presented as
 * an already orderable primer design.
 */

import { ResultFact as Fact, RuntimeProvenance } from "./result-primitives";
import { ArrowRight, Route } from "lucide-react";

import { OrderActions } from "./order-actions";
import { WorkflowEvidenceCard } from "./workflow-evidence";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count } from "@/lib/numbers";
import type { OrderLine } from "@/lib/order-sheet";
import type { MutagenicPair, MutagenicResult } from "@/lib/api/types";

export function MutagenicResultView({ result }: { result: MutagenicResult }) {
  const topology = result.mutagenesis_topology ?? "q5-back-to-back";
  return (
    <div className="space-y-5">
      <MutationOverview result={result} />
      <ConstructEvidence result={result} />
      {result.protocol ? <ProtocolAuthority result={result} /> : null}
      <TopologyDesign result={result} />

      {result.pairs.map((pair, index) => (
        <Q5PairCard key={`${pair.forward.sequence}-${index}`} pair={pair} index={index + 1} />
      ))}

      {result.pairs.length === 0 &&
      !result.design &&
      !result.library_design &&
      result.why_nothing ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">No complete {topology} design</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs leading-relaxed text-muted-foreground">{result.why_nothing}</p>
          </CardContent>
        </Card>
      ) : null}

      <OrderabilityBoundary result={result} />
      {result.order_sheet.length > 0 && effectiveOrderability(result).orderable ? (
        <OrderSheet result={result} />
      ) : null}
      <WorkflowEvidenceCard
        evidence={result.workflow_evidence}
        title="Mutagenesis validation evidence"
      />
      <RuntimeProvenance provenance={result.provenance} />
    </div>
  );
}

function effectiveOrderability(result: MutagenicResult) {
  return (
    result.orderability ?? {
      orderable: false,
      status: "historical-result-orderability-not-recorded",
      note: "This saved mutagenesis result predates the topology-specific orderability contract. Regenerate before ordering.",
    }
  );
}

function OrderabilityBoundary({ result }: { result: MutagenicResult }) {
  const value = effectiveOrderability(result);
  if (value.orderable) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Diagnostic / routed design — do not order here
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <p className="text-xs font-medium">{value.status}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">{value.note}</p>
      </CardContent>
    </Card>
  );
}

function MutationOverview({ result }: { result: MutagenicResult }) {
  const edits =
    result.edits ?? (result.edit ? [result.edit as unknown as Record<string, unknown>] : []);
  const amino = asRecord(result.amino_acid_evidence);
  const library = asRecord(result.library_design);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Mutation plan</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
          <Fact label="Topology" value={result.mutagenesis_topology ?? "q5-back-to-back"} />
          <Fact label="Edits" value={String(edits.length || (library ? 1 : 0))} />
          <Fact
            label="Template methylation"
            value={result.template_methylation_status ?? "unknown"}
          />
          <Fact label="Verification state" value="predicted construct" />
        </dl>

        {result.edit ? <SingleEdit edit={result.edit} /> : null}
        {edits.length > 1 ? (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-xs">
              <caption className="sr-only">Declared mutation edits</caption>
              <thead className="bg-surface-wash/40 text-muted-foreground">
                <tr>
                  <th scope="col" className="px-2.5 py-1.5 text-left font-medium">
                    #
                  </th>
                  <th scope="col" className="px-2.5 py-1.5 text-left font-medium">
                    Kind
                  </th>
                  <th scope="col" className="px-2.5 py-1.5 text-left font-medium">
                    Base
                  </th>
                  <th scope="col" className="px-2.5 py-1.5 text-left font-medium">
                    Replacement
                  </th>
                </tr>
              </thead>
              <tbody>
                {edits.map((edit, index) => (
                  <tr key={index} className="border-t">
                    <td className="px-2.5 py-1.5">{index + 1}</td>
                    <td className="px-2.5 py-1.5">{String(edit.kind ?? "edit")}</td>
                    <td className="px-2.5 py-1.5 tabular-nums">{numberLabel(edit.at, true)}</td>
                    <td className="px-2.5 py-1.5 font-mono">{String(edit.to ?? "") || "∅"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {amino ? (
          <div className="rounded-md border border-primary/25 bg-primary/5 p-2.5 text-xs">
            <p className="font-medium">Amino-acid interpretation</p>
            <p className="mt-1 text-muted-foreground">
              {String(amino.from_aa ?? amino.from ?? "?")} →{" "}
              {String(amino.to_aa ?? amino.to ?? "?")} at residue {String(amino.residue ?? "?")} ·
              codon policy {String(amino.codon_policy ?? "recorded in request")}. DNA remains the
              executable edit authority.
            </p>
          </div>
        ) : null}

        {library ? (
          <div className="rounded-md border border-warning/35 bg-warning/5 p-2.5 text-xs">
            <p className="font-medium">Degenerate library declaration</p>
            <p className="mt-1 text-muted-foreground">
              {String(library.mode ?? "custom")} at base {numberLabel(library.at, true)} · IUPAC{" "}
              {String(library.iupac ?? "unresolved")} · theoretical concrete codons{" "}
              {String(library.theoretical_concrete_codons ?? "custom/undetermined")}.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {String(
                library.claim_boundary ??
                  "Theoretical sequence space is not synthesis abundance or clone distribution.",
              )}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function SingleEdit({ edit }: { edit: NonNullable<MutagenicResult["edit"]> }) {
  return (
    <div className="space-y-2 rounded-md border p-2.5">
      <dl className="grid gap-x-6 gap-y-1.5 text-xs sm:grid-cols-3">
        <Fact label="Kind" value={edit.kind} />
        <Fact label="At base" value={count(edit.at)} />
        <Fact
          label="Predicted product"
          value={edit.product_length != null ? `${count(edit.product_length)} bp` : "see construct"}
        />
      </dl>
      {edit.was || edit.becomes ? (
        <div className="grid gap-1.5 text-xs">
          <div className="flex gap-2">
            <span className="w-14 text-xs text-muted-foreground">was</span>
            <code className="break-all">{edit.was || "∅"}</code>
          </div>
          <div className="flex gap-2">
            <ArrowRight className="mt-0.5 size-3 shrink-0 text-muted-foreground" />
            <span className="w-[3.25rem] text-xs text-muted-foreground">becomes</span>
            <code className="break-all text-primary">{edit.becomes || "∅"}</code>
          </div>
        </div>
      ) : null}
      {edit.describes ? (
        <p className="text-xs leading-relaxed text-muted-foreground">{edit.describes}</p>
      ) : null}
    </div>
  );
}

function ConstructEvidence({ result }: { result: MutagenicResult }) {
  const construct = asRecord(result.construct);
  if (!construct) return null;
  const sequence =
    typeof construct.exact_edited_construct === "string" ? construct.exact_edited_construct : "";
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Predicted edited construct</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-4">
          <Fact label="Reference length" value={String(construct.reference_length ?? "?")} />
          <Fact
            label="Edited length"
            value={String(construct.edited_length ?? (sequence.length || "?"))}
          />
          <Fact label="Length delta" value={String(construct.delta_length ?? "?")} />
          <Fact label="Clone verified" value="no — evidence required" />
        </dl>
        {sequence ? (
          <p className="rounded-md border bg-surface-wash/25 p-2 font-mono text-xs break-all">
            {sequence.length > 240
              ? `${sequence.slice(0, 120)} … ${sequence.slice(-120)}`
              : sequence}
          </p>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">
          {String(
            construct.claim_boundary ??
              "This is an exact predicted sequence transformation, not a verified clone sequence.",
          )}
        </p>
      </CardContent>
    </Card>
  );
}

function ProtocolAuthority({ result }: { result: MutagenicResult }) {
  const protocol = result.protocol as Record<string, unknown>;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Topology-specific protocol authority
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs font-medium">{String(protocol.selection ?? "selected protocol")}</p>
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
          <Fact
            label="Topology"
            value={String(protocol.topology ?? result.mutagenesis_topology ?? "not recorded")}
          />
          <Fact label="Source" value={String(protocol.source_identity ?? "not recorded")} />
          <Fact label="Execution" value={String(protocol.execution_status ?? "topology-owned")} />
        </dl>
        {protocol.numeric_authority ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {String(protocol.numeric_authority)}
          </p>
        ) : null}
        {protocol.note ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{String(protocol.note)}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TopologyDesign({ result }: { result: MutagenicResult }) {
  const design = asRecord(result.design);
  if (!design) return null;
  const pairs = Array.isArray(design.pairs) ? (design.pairs as Array<Record<string, unknown>>) : [];
  const primers = Array.isArray(design.primers)
    ? (design.primers as Array<Record<string, unknown>>)
    : [];
  const segments = Array.isArray(design.segments)
    ? (design.segments as Array<Record<string, unknown>>)
    : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          {String(design.topology ?? result.mutagenesis_topology ?? "Topology")} design
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {pairs.length ? (
          <div className="grid gap-2 md:grid-cols-2">
            {pairs.map((pair, index) => (
              <div key={index} className="rounded-md border p-2.5 text-xs">
                <p className="font-medium">Complementary pair {index + 1}</p>
                <p className="mt-1 font-mono break-all">F: {String(pair.forward ?? "")}</p>
                <p className="mt-1 font-mono break-all">R: {String(pair.reverse ?? "")}</p>
                <p className="mt-1 text-muted-foreground">
                  Agilent formula Tm: {String(pair.tm_formula_c ?? "?")} °C ·{" "}
                  {String(pair.length ?? "?")} nt · GC {String(pair.gc_percent ?? "?")}%
                </p>
              </div>
            ))}
          </div>
        ) : null}
        {primers.length ? (
          <div className="grid gap-2 md:grid-cols-2">
            {primers.map((primer, index) => (
              <div key={index} className="rounded-md border p-2.5 text-xs">
                <p className="font-medium">Mutation primer {index + 1}</p>
                <p className="mt-1 font-mono break-all">{String(primer.sequence ?? "")}</p>
                <p className="mt-1 text-muted-foreground">
                  same template strand · formula Tm {String(primer.tm_formula_c ?? "?")} °C · bases{" "}
                  {numberLabel(primer.start, true)}–{numberLabel(primer.end, false)}
                </p>
              </div>
            ))}
          </div>
        ) : null}
        {design.route_to_engine ? (
          <div className="rounded-md border border-primary/25 bg-primary/5 p-2.5 text-xs">
            <div className="flex items-center gap-2 font-medium">
              <Route className="size-4" />
              Route to {String(design.route_to_engine)}
            </div>
            <p className="mt-1 text-muted-foreground">
              Method {String(design.method ?? "not recorded")} · protocol{" "}
              {String(design.protocol ?? "not recorded")} · {segments.length} fragment route(s).
              PCRStudio does not call this an orderable mutagenic-primer result until Junction
              Primers resolves the overlaps.
            </p>
          </div>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">
          {String(
            design.claim_boundary ??
              design.why ??
              "Topology-specific geometry is reported under its own authority; cross-topology numeric inheritance is prohibited.",
          )}
        </p>
      </CardContent>
    </Card>
  );
}

function Q5PairCard({ pair, index }: { pair: MutagenicPair; index: number }) {
  const { melting } = pair;
  return (
    <Card>
      <CardHeader className="flex flex-row items-baseline justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">Q5 pair {index}</CardTitle>
        <span className="text-xs text-muted-foreground">
          Cycling Ta:{" "}
          <span className="font-medium text-foreground">
            resolve with NEBaseChanger / named protocol
          </span>
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-2">
          <Temperature
            label="Primer3 screening against original template"
            value={melting.on_template}
            lead
          />
          <Temperature
            label="Primer3 screening against edited product"
            value={melting.on_product}
          />
        </div>
        <div className="space-y-2">
          <Oligo
            role="Forward"
            sequence={pair.forward.sequence}
            annealingSequence={pair.forward.annealing_sequence}
            tailSequence={pair.forward.tail_sequence}
            tm={pair.forward.tm}
            at={pair.forward.at}
          />
          <Oligo
            role="Reverse"
            sequence={pair.reverse.sequence}
            annealingSequence={pair.reverse.annealing_sequence}
            tailSequence={pair.reverse.tail_sequence}
            tm={pair.reverse.tm}
            at={pair.reverse.at}
          />
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {melting.note} {melting.authority ?? ""}
        </p>
      </CardContent>
    </Card>
  );
}

function Temperature({ label, value, lead }: { label: string; value: number; lead?: boolean }) {
  return (
    <div
      className={
        lead ? "rounded-md border border-primary/30 bg-primary/5 p-2.5" : "rounded-md border p-2.5"
      }
    >
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-lg font-medium tabular-nums">{value} °C</p>
    </div>
  );
}

function Oligo({
  role,
  sequence,
  annealingSequence,
  tailSequence,
  tm,
  at,
}: {
  role: string;
  sequence: string;
  annealingSequence?: string;
  tailSequence: string;
  tm: number;
  at: number;
}) {
  return (
    <div className="rounded-md border p-2.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs font-medium">{role}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          Primer3 {tm} °C · base {count(at)}
        </span>
      </div>
      <p className="mt-1 font-mono text-xs break-all">{sequence}</p>
      {tailSequence ? (
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          5′ tail <span className="font-mono">{tailSequence}</span> + template-facing core{" "}
          <span className="font-mono">{annealingSequence ?? "not recorded"}</span>. The tail is not
          treated as matched template sequence during first-cycle screening.
        </p>
      ) : null}
    </div>
  );
}

function OrderSheet({ result }: { result: MutagenicResult }) {
  const exportLines: OrderLine[] = result.order_sheet
    .filter((line) => typeof line.gc_percent === "number")
    .map((line) => ({
      name: line.name,
      sequence: line.sequence,
      length: line.length,
      gc_percent: line.gc_percent as number,
      ...(typeof line.tm === "number" ? { tm: line.tm } : {}),
      note: [
        line.note,
        typeof line.tm_formula_c === "number"
          ? `Agilent-specific formula Tm ${line.tm_formula_c} °C; not Primer3 Tm.`
          : undefined,
      ]
        .filter(Boolean)
        .join(" "),
    }));
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          What to order — {result.order_sheet.length} oligos
        </CardTitle>
        {exportLines.length === result.order_sheet.length ? (
          <OrderActions lines={exportLines} kind="mutagenic-primers" conditions={result.reaction} />
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        {result.order_sheet.map((line) => (
          <div key={line.name} className="rounded-md border p-2.5">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <span className="font-mono text-xs font-medium">{line.name}</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {line.length} nt{line.gc_percent != null ? ` · ${line.gc_percent}% GC` : ""}
                {line.tm != null ? ` · Primer3 ${line.tm} °C` : ""}
                {line.tm_formula_c != null ? ` · Agilent formula ${line.tm_formula_c} °C` : ""}
              </span>
            </div>
            <p className="mt-1 font-mono text-xs break-all">{line.sequence}</p>
            {line.note ? <p className="mt-1 text-xs text-muted-foreground">{line.note}</p> : null}
          </div>
        ))}
        <p className="pt-1 text-xs leading-relaxed text-muted-foreground">
          Formula-specific thermodynamics remain labelled by their source method. Supplier exports
          never convert them into a generic Primer3 Tm.
        </p>
      </CardContent>
    </Card>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function numberLabel(value: unknown, oneBased: boolean) {
  return typeof value === "number" ? String(value + (oneBased ? 1 : 0)) : "?";
}
