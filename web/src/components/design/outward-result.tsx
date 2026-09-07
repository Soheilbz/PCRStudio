"use client";

/**
 * Inverse-PCR result for the Gen-1 restriction-digest/self-ligation branch.
 *
 * The selected restriction enzyme must not cut inside the known anchor.  The
 * complete known anchor remains on one restriction fragment, that fragment is
 * self-ligated, and one outward-facing primer pair amplifies across the
 * flanking-sequence/ligation path.  There is deliberately no synthetic
 * "internal cut" visualization here: internal-cut/one-sided inverse PCR is a
 * different, currently non-executable topology.
 */

import { ResultFact as Fact, RuntimeProvenance } from "./result-primitives";
import { ScanFindings } from "@/components/design/scan";
import { OrderActions } from "./order-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count } from "@/lib/numbers";
import type { OutwardPair, OutwardResult } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { OutwardClosurePanels } from "./engine-closure-panels";

export function OutwardResultView({ result }: { result: OutwardResult }) {
  return (
    <div className="space-y-5">
      <DigestTopology result={result} />
      <ExperimentContract result={result} />
      <OutwardClosurePanels result={result} />

      {result.pairs.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">
              Outward pairs on the intact known anchor
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {result.pairs.map((pair, index) => (
              <PairCard
                key={index}
                pair={pair}
                index={index + 1}
                knownLength={result.digest.known_length}
              />
            ))}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">No outward pair</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs leading-relaxed text-muted-foreground">{result.why_nothing}</p>
          </CardContent>
        </Card>
      )}

      {result.pairs.length > 0 ? <OrderSheet result={result} /> : null}
      <RuntimeProvenance provenance={result.provenance} />
    </div>
  );
}

function DigestTopology({ result }: { result: OutwardResult }) {
  const { digest, circle } = result;
  const unknown = circle.unknown_interval;
  const unknownText =
    unknown.exact !== null
      ? `${count(unknown.exact)} bp exact`
      : unknown.minimum !== null || unknown.maximum !== null
        ? `${unknown.minimum ?? "?"}–${unknown.maximum ?? "?"} bp`
        : "unresolved";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Restriction fragment and self-ligation topology
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
          <Fact label="Known anchor" value={`${count(digest.known_length)} bp`} />
          <Fact label="Named enzyme" value={digest.enzyme ?? "unresolved"} />
          <Fact
            label="Sites inside anchor"
            value={
              digest.known_sites.length === 0 ? "0 (required)" : String(digest.known_sites.length)
            }
          />
          <Fact
            label="Self-ligated fragment"
            value={
              digest.circle_length === null ? "not supplied" : `${count(digest.circle_length)} bp`
            }
          />
          <Fact label="Combined unknown flanks" value={unknownText} />
          <Fact label="Branch" value={digest.branch_identity} />
        </dl>
        <div aria-hidden="true" className="space-y-1">
          <div className="relative h-3 rounded bg-muted">
            <div className="absolute inset-y-0 right-[18%] left-[18%] rounded bg-primary/45" />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>unknown upstream flank</span>
            <span>complete known anchor — no internal enzyme site</span>
            <span>unknown downstream flank</span>
          </div>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">{digest.note}</p>
      </CardContent>
    </Card>
  );
}

function ExperimentContract({ result }: { result: OutwardResult }) {
  const contract = result.experiment_contract;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Preparation and claim boundary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
          <Fact label="Branch" value={contract.branch} />
          <Fact label="Left end" value={contract.left_end_phosphate} />
          <Fact label="Right end" value={contract.right_end_phosphate} />
          <Fact label="Result status" value={contract.result_status} />
          <Fact label="Circularization" value={contract.circularization_provenance} />
          <Fact label="Linear control" value={contract.linear_control_provenance} />
          <Fact label="Methylation" value={contract.methylation_branch} />
        </dl>
        <p className="text-xs leading-relaxed text-muted-foreground">{contract.status_semantics}</p>
      </CardContent>
    </Card>
  );
}

function PairCard({
  pair,
  index,
  knownLength,
}: {
  pair: OutwardPair;
  index: number;
  knownLength: number;
}) {
  const percent = (value: number) => (value / Math.max(knownLength, 1)) * 100;
  return (
    <div className="space-y-2 border-t pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs">
        <span className="font-medium">Pair {index}</span>
        <span className="text-muted-foreground tabular-nums">
          {count(pair.known_span)} bp of known-anchor path
        </span>
      </div>

      <div aria-hidden="true" className="space-y-1">
        <div className="relative h-3 rounded bg-muted">
          <div
            className="absolute inset-y-0 rounded bg-primary/60"
            style={{
              left: `${percent(pair.left_at.start)}%`,
              width: `${(pair.left_at.length / Math.max(knownLength, 1)) * 100}%`,
            }}
          />
          <div
            className="absolute inset-y-0 rounded bg-primary/60"
            style={{
              left: `${percent(pair.right_at.start)}%`,
              width: `${(pair.right_at.length / Math.max(knownLength, 1)) * 100}%`,
            }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>← outward into upstream flank</span>
          <span>outward into downstream flank →</span>
        </div>
      </div>

      <Oligo role="Forward" oligo={pair.left} at={pair.left_at} />
      <Oligo role="Reverse" oligo={pair.right} at={pair.right_at} />
      <ScanFindings off={pair.off_targets} intended={2} />

      <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs">
        <span className="text-muted-foreground">Final inverse-PCR product</span>
        <span className={cn("tabular-nums", pair.product_size === null && "text-muted-foreground")}>
          {pair.product_size === null ? "not known" : `${count(pair.product_size)} bp`}
        </span>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">{pair.product_note}</p>
      <details className="rounded-md border border-border/50 bg-background/35 p-2.5">
        <summary className="min-h-6 cursor-pointer py-1 text-xs font-medium">
          Product path and unknown interval
        </summary>
        <div className="mt-2 space-y-1 text-xs text-muted-foreground">
          <p>
            Unknown interval: {pair.unknown_interval.status}
            {pair.unknown_interval.exact !== null
              ? ` · ${count(pair.unknown_interval.exact)} bp`
              : pair.unknown_interval.minimum !== null || pair.unknown_interval.maximum !== null
                ? ` · ${pair.unknown_interval.minimum ?? "?"}–${pair.unknown_interval.maximum ?? "?"} bp`
                : ""}
          </p>
          <ol className="list-decimal space-y-0.5 pl-4">
            {pair.product_path.map((part, pathIndex) => (
              <li key={pathIndex}>
                <code>{String(part.kind ?? "segment")}</code>
              </li>
            ))}
          </ol>
        </div>
      </details>
    </div>
  );
}

function Oligo({
  role,
  oligo,
  at,
}: {
  role: string;
  oligo: OutwardPair["left"];
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

function OrderSheet({ result }: { result: OutwardResult }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          What to order — {result.order_sheet.length} oligos
        </CardTitle>
        <OrderActions
          lines={result.order_sheet}
          kind="inverse-primers"
          conditions={result.reaction}
        />
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-xs">
          <caption className="sr-only">Outward-facing primer sequences and thermodynamics</caption>
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
                <td className="py-0.5 pr-3 font-mono whitespace-nowrap">{line.name}</td>
                <td className="py-0.5 pr-3 font-mono">{line.sequence}</td>
                <td className="py-0.5 pr-3 tabular-nums">{line.length}</td>
                <td className="py-0.5 tabular-nums">{line.tm}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
