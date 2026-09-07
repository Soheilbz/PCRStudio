"use client";

/**
 * What a degenerate design produced.
 *
 * A different view from the flanking-pair one, because it is a different
 * answer. There is no single template to report against, no order sheet of two
 * oligos per pair — a degenerate primer is a mixture, and the two things
 * somebody has to know about it are how many molecules it holds and how many
 * of their sequences it actually fits.
 *
 * Coverage is measured rather than assumed: the primer is built to cover every
 * sequence, and then checked against each one. If those two ever disagree, the
 * measured number is the one shown.
 */

import { Layers, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { count, maybeCount } from "@/lib/numbers";
import { degenerateLines } from "@/lib/order-sheet";
import { OrderActions } from "./order-actions";
import { WorkflowEvidenceCard } from "./workflow-evidence";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { DegenerateSite, UniversalPair, UniversalResult } from "@/lib/api/types";

export function UniversalResultView({ result }: { result: UniversalResult }) {
  return (
    <div className="space-y-5">
      <TheAlignment result={result} />
      {result.panel ? <PanelEvidence result={result} /> : null}
      {result.degenerate_thermodynamics ? <ThermodynamicModel result={result} /> : null}
      <WorkflowEvidenceCard
        evidence={result.workflow_evidence}
        title="Universal-primer validation evidence"
      />
      <TheSearch result={result} />

      {result.pairs.length === 0 ? (
        <NothingFound result={result} />
      ) : (
        <>
          <section className="space-y-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-sm font-medium">
                {result.pairs.length} pair{result.pairs.length === 1 ? "" : "s"}
              </h2>
              <span className="text-xs text-muted-foreground">
                Widest supplied-panel coverage first, then the declared deterministic score
              </span>
            </div>
            <div className="space-y-2.5">
              {result.pairs.map((pair, index) => (
                <PairCard
                  key={pair.left.sequence + pair.right.sequence}
                  pair={pair}
                  rank={index + 1}
                />
              ))}
            </div>
          </section>

          <OrderSheet result={result} />
        </>
      )}
    </div>
  );
}

function TheAlignment({ result }: { result: UniversalResult }) {
  const { alignment } = result;
  const conserved = alignment.columns
    ? Math.round((100 * alignment.conserved_columns) / alignment.columns)
    : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">What was designed across</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-4">
          <Fact label="Sequences" value={String(alignment.sequences)} />
          <Fact label="Columns" value={count(alignment.columns)} />
          <Fact
            label="Fully conserved"
            value={`${count(alignment.conserved_columns)} (${conserved}%)`}
          />
          <Fact label="Holding a gap" value={count(alignment.gapped_columns)} />
        </dl>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {alignment.names.join(" · ")}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          No primer is placed across a gapped column: a column where one sequence has nothing is a
          column where a mixture cannot say what it covers.
        </p>
      </CardContent>
    </Card>
  );
}

function PanelEvidence({ result }: { result: UniversalResult }) {
  const panel = result.panel as Record<string, unknown> | undefined;
  if (!panel) return null;
  const qc = (panel.qc ?? {}) as Record<string, unknown>;
  const duplicateGroups = Array.isArray(qc.duplicate_sequence_groups)
    ? qc.duplicate_sequence_groups.length
    : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Panel, sampling frame & formulation contract
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <dl className="grid gap-x-6 gap-y-1.5 sm:grid-cols-4">
          <Fact
            label="Consensus policy"
            value={String(
              panel.policy ?? result.alignment.consensus_policy ?? "strict-all-members",
            )}
            small
          />
          <Fact label="Metadata records" value={String(qc.metadata_records ?? 0)} small />
          <Fact label="Exact duplicate groups" value={String(duplicateGroups)} small />
          <Fact
            label="Population inference"
            value={String(panel.population_inference ?? "not-established")}
            small
          />
        </dl>
        <p className="leading-relaxed text-muted-foreground">
          {String(qc.note ?? "Coverage is descriptive of the supplied panel only.")}
        </p>
        {result.nontarget_panel ? (
          <p className="leading-relaxed text-muted-foreground">
            Non-target panel:{" "}
            {String((result.nontarget_panel as Record<string, unknown>).count ?? 0)} supplied
            records; bounded specificity only.
          </p>
        ) : null}
        {result.alignment_audit ? (
          <p className="leading-relaxed text-muted-foreground">
            Alignment sensitivity validator:{" "}
            {String(
              (result.alignment_audit as Record<string, unknown>).backend ?? "caller-supplied",
            )}{" "}
            — primary ranking not mutated.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ThermodynamicModel({ result }: { result: UniversalResult }) {
  const model = result.degenerate_thermodynamics;
  if (!model) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Degenerate-pool Tm concentration model
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs leading-relaxed text-muted-foreground">{model.note}</p>
        <p className="text-xs text-muted-foreground tabular-nums">
          Effective pool reference: {model.pool_effective_dna_conc_nM} nM. Each primer card reports
          the nominal per-member value actually used for its Primer3 Tm calculation.
        </p>
      </CardContent>
    </Card>
  );
}

/** Where the windows went, and which of the three rules took them. */
function TheSearch({ result }: { result: UniversalResult }) {
  const [open, setOpen] = useState(false);
  const { windows, pair_counts, capped } = result;

  return (
    <Card>
      <CardHeader>
        <button
          type="button"
          onClick={() => setOpen((previous) => !previous)}
          aria-expanded={open}
          className="w-full text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <CardTitle className="text-[13px] font-medium">
            {count(windows.considered)} windows considered, {count(windows.accepted)} usable
          </CardTitle>
        </button>
      </CardHeader>
      <CardContent className="space-y-2">
        <ul className="space-y-1">
          {windows.rejections.map((entry) => (
            <li key={entry.reason} className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
              <span className="tabular-nums">
                {count(entry.count)} ({entry.share}%)
              </span>
              <span className="text-foreground">{entry.reason}</span>
              {open && entry.advice ? <span>— {entry.advice}</span> : null}
            </li>
          ))}
        </ul>

        {open ? (
          <div className="space-y-2 text-xs leading-relaxed text-muted-foreground">
            <p>
              {maybeCount(pair_counts.wrong_size, "0")} pairings were outside the selected
              product-size envelope and went no further; {maybeCount(pair_counts.considered, "0")}{" "}
              fell inside the range. Of those,{" "}
              {maybeCount(pair_counts.above_tm_pair_reference, "0")} exceeded the profile&apos;s
              pair-Tm reference but were retained for ranking rather than rejected.{" "}
              {pair_counts.measured ?? 0} were then measured properly and{" "}
              {pair_counts.collapsed ?? 0} were another pair shifted along.
              {!capped.search_complete ? ` ${capped.note}` : ""}
            </p>
            {windows.by_orientation ? (
              <p>
                Orientation ledger: forward {windows.by_orientation.forward.accepted}/
                {windows.by_orientation.forward.considered} accepted; reverse{" "}
                {windows.by_orientation.reverse.accepted}/
                {windows.by_orientation.reverse.considered} accepted.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Open this for what each refusal means.</p>
        )}
      </CardContent>
    </Card>
  );
}

function NothingFound({ result }: { result: UniversalResult }) {
  const worst = result.windows.rejections[0];
  return (
    <Card className="border-warning/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[13px] font-medium text-warning">
          <TriangleAlert className="size-4" />
          No pair fits all of these sequences under those rules
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed">
          {worst
            ? `Of ${count(result.windows.considered)} windows, ${count(worst.count)} failed on ${worst.reason}${worst.advice ? ` — ${worst.advice}` : ""}.`
            : "Nothing was even considered, which usually means the alignment is shorter than the product asked for."}
        </p>
      </CardContent>
    </Card>
  );
}

function PairCard({ pair, rank }: { pair: UniversalPair; rank: number }) {
  const complete = pair.covers === pair.of;

  return (
    <Card className="gap-3">
      <CardHeader>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <CardTitle className="text-sm font-medium">
            Pair {rank}
            <span className="ml-2 text-xs font-normal text-muted-foreground tabular-nums">
              {" — "}
              {pair.product_size} bp
              {pair.annealing_temperature == null
                ? ", bench Ta unresolved"
                : `, historical saved Ta ${pair.annealing_temperature} °C — not current authority`}
            </span>
          </CardTitle>
          <span className={cn("text-xs tabular-nums", complete ? "text-success" : "text-warning")}>
            covers {pair.covers}/{pair.of}
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="grid gap-2.5 md:grid-cols-2">
          <SiteRow label="Forward" site={pair.left} />
          <SiteRow label="Reverse" site={pair.right} />
        </div>

        <dl className="grid gap-x-6 gap-y-1.5 text-xs sm:grid-cols-3">
          <Fact label="Molecules in the tube" value={`${count(pair.degeneracy)}-fold`} small />
          <Fact label="Pair dimer ΔG" value={`${pair.cross_dimer_dg} kcal/mol`} small />
          <Fact label="Score" value={pair.score.toFixed(2)} small />
        </dl>

        {pair.coverage_evidence ||
        pair.formulation ||
        pair.nontarget_evidence ||
        pair.alignment_sensitivity ? (
          <details className="rounded-lg border border-border/60 bg-surface-wash/20 px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium">
              Coverage, formulation & sensitivity evidence
            </summary>
            <div className="mt-2 space-y-1.5 text-xs leading-relaxed text-muted-foreground">
              {pair.coverage_evidence ? (
                <p>
                  Weighted supplied-panel coverage:{" "}
                  {String(
                    (pair.coverage_evidence as Record<string, unknown>).weighted_coverage ??
                      "unresolved",
                  )}
                  ; population inference remains not established.
                </p>
              ) : null}
              {pair.formulation ? (
                <p>
                  Formulation:{" "}
                  {String((pair.formulation as Record<string, unknown>).mode ?? "unresolved")} —
                  equal concrete-member abundance is not assumed.
                </p>
              ) : null}
              {pair.nontarget_evidence ? (
                <p>
                  Finite non-target exact-compatible products:{" "}
                  {String(
                    (pair.nontarget_evidence as Record<string, unknown>)
                      .records_with_exact_compatible_product ?? 0,
                  )}{" "}
                  record(s).
                </p>
              ) : null}
              {pair.alignment_sensitivity ? (
                <p>
                  Alternative-alignment status:{" "}
                  {String(
                    (pair.alignment_sensitivity as Record<string, unknown>).status ?? "unresolved",
                  )}
                  .
                </p>
              ) : null}
              {pair.split_pool_alternative ? (
                <SplitPoolSummary value={pair.split_pool_alternative as Record<string, unknown>} />
              ) : null}
              {pair.amplicon_informativeness ? (
                <InformativenessSummary
                  value={pair.amplicon_informativeness as Record<string, unknown>}
                />
              ) : null}
            </div>
          </details>
        ) : null}

        <details>
          <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
            Why this score
          </summary>
          <ul className="mt-2 space-y-1.5">
            {pair.score_components.map((part) => (
              <li key={part.name} className="text-xs leading-relaxed">
                <span className="font-medium tabular-nums">
                  {part.value >= 0 ? "+" : ""}
                  {part.value.toFixed(2)}
                </span>{" "}
                <span className="text-muted-foreground">
                  {part.name} — {part.detail}
                </span>
              </li>
            ))}
          </ul>
        </details>
      </CardContent>
    </Card>
  );
}

function SplitPoolSummary({ value }: { value: Record<string, unknown> }) {
  const primers = Array.isArray(value.selected_members)
    ? value.selected_members.length
    : value.pool_size;
  const coverage = value.coverage ?? value.covered_records;
  return (
    <p>
      Defined split-pool alternative: {String(primers ?? "unresolved")} concrete member(s) in the
      deterministic greedy diagnostic; supplied-panel coverage {String(coverage ?? "unresolved")}.
      This is not claimed to be a globally minimal set.
    </p>
  );
}

function InformativenessSummary({ value }: { value: Record<string, unknown> }) {
  return (
    <p>
      Amplicon informativeness: {String(value.variable_columns ?? 0)} variable aligned column(s),{" "}
      {String(value.unique_ungapped_amplicons ?? "unresolved")} unique supplied-panel amplicon
      sequence(s), mean Shannon entropy{" "}
      {String(value.mean_shannon_entropy ?? value.mean_entropy_bits ?? "unresolved")}. This is
      descriptive, not a taxonomic-identification guarantee.
    </p>
  );
}

function SiteRow({ label, site }: { label: string; site: DegenerateSite }) {
  const mixed = site.degeneracy > 1;
  return (
    <div className="space-y-1.5 rounded-lg border bg-surface-wash/45 p-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium">
          {label}
          {mixed ? (
            <span className="ml-1.5 inline-flex items-center gap-1 text-xs font-normal text-muted-foreground">
              <Layers className="size-3" aria-hidden="true" />
              {site.degeneracy}-fold
            </span>
          ) : null}
        </span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {site.length} nt · {site.gc_min}–{site.gc_max}% GC
        </span>
      </div>

      <p className="font-mono text-xs break-all">{site.sequence}</p>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        <Small term="Columns" value={`${site.start}–${site.end}`} />
        <Small
          term="Melts at"
          value={site.tm_spread > 0 ? `${site.tm_min}–${site.tm_max} °C` : `${site.tm_min} °C`}
        />
        <Small term="Fits" value={`${site.covers} sequences`} />
        <Small term="Tm member model" value={`${site.tm_member_dna_conc_nM} nM`} />
        <Small term="Hairpin ΔG" value={`${site.hairpin_dg} kcal/mol`} />
      </dl>
    </div>
  );
}

function OrderSheet({ result }: { result: UniversalResult }) {
  const rows = result.pairs.flatMap((pair, index) => [
    { name: `universal_${index + 1}F`, site: pair.left },
    { name: `universal_${index + 1}R`, site: pair.right },
  ]);

  /*
   * The worker now emits a generic auditable order ledger, but this view deliberately
   * rebuilds supplier lines from the degenerate sites because a degenerate pool has a
   * Tm range rather than one physically meaningful scalar Tm. The raw ledger is retained
   * in the parsed result for provenance; it is not the display authority here.
   *
   * These lines are built carefully, because a degenerate
   * primer is not one molecule.
   *
   * It ships as a pool of up to `degeneracy` distinct sequences, and those
   * sequences melt at different temperatures. The single `tm` column every
   * other engine fills would have to be given some representative value, and
   * every candidate for it — the mean, the minimum, the temperature of the
   * consensus base at each position — is the melting temperature of something
   * that is not in the tube. So the range goes out instead, and the count of
   * distinct sequences with it: that is what a supplier synthesises and what
   * an annealing temperature has to accommodate.
   */
  const lines = degenerateLines(rows);

  return (
    <section className="space-y-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium">What to order</h2>
        <OrderActions lines={lines} kind="universal-primers" conditions={result.reaction} />
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-xs">
          <caption className="sr-only">Universal primer sequences and fold measurements</caption>
          <thead className="bg-surface-warm/42 text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                Name
              </th>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                Sequence (5′ → 3′)
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                nt
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Fold
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name} className="border-t">
                <td className="px-3 py-1.5 font-medium whitespace-nowrap">{row.name}</td>
                <td className="px-3 py-1.5 font-mono break-all">{row.site.sequence}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{row.site.length}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{row.site.degeneracy}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        Order these as written: the IUPAC codes specify mixed-base positions rather than
        placeholders. Standard synthesis may dispense nominally equal base ratios at a mixed
        position, but coupling bias can change the delivered composition. The Tm member
        concentrations above are therefore a declared screening model, not an assay of the
        synthesized pool.
      </p>
    </section>
  );
}

function Fact({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <div className="min-w-0 space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("break-words", small ? "text-xs" : "text-sm")}>{value}</dd>
    </div>
  );
}

function Small({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex min-w-0 justify-between gap-2">
      <dt>{term}</dt>
      <dd className="text-foreground tabular-nums">{value}</dd>
    </div>
  );
}
