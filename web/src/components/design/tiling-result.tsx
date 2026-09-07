"use client";

/**
 * What a tiling scheme produced.
 *
 * Two things make this unlike every other result here, and the view is built
 * around both.
 *
 * The answer is not a list of pairs, it is a set of pools. Neighbouring
 * amplicons overlap, so they cannot share a tube — two primers spanning the
 * same stretch would amplify each other's short products in preference to the
 * real ones, and the reaction would fill with the shortest thing it could make.
 * Which tube a pair goes in is therefore not a detail of the order sheet, it is
 * part of the design, and it is shown on the map and on every line.
 *
 * And coverage is the result. Every other engine either found something or did
 * not; this one can succeed almost everywhere and leave a hole, and the hole is
 * the thing worth knowing. A scheme with a gap somebody knows about is usable —
 * they sequence that stretch another way. A scheme that silently skipped a
 * region is not, because nobody finds out until the assembly has a hole in it.
 * So gaps are shown as gaps, in the map and in words, never rounded away into a
 * coverage percentage.
 */

import { RuntimeProvenance } from "./result-primitives";
import { OrderActions } from "./order-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count } from "@/lib/numbers";
import type { TilingResult } from "@/lib/api/types";
import { TilingClosurePanels } from "./engine-closure-panels";

/** One colour per pool, so the map and the sheet agree at a glance. */
const POOL_FILL = [
  "bg-primary/45",
  "bg-chart-3/45",
  "bg-chart-4/45",
  "bg-chart-2/45",
  "bg-chart-5/45",
  "bg-destructive/45",
];
const POOL_DOT = [
  "bg-primary",
  "bg-chart-3",
  "bg-chart-4",
  "bg-chart-2",
  "bg-chart-5",
  "bg-destructive",
];

export function TilingResultView({ result }: { result: TilingResult }) {
  if (result.tiles.length === 0) {
    return (
      <div className="space-y-5">
        <TilingClosurePanels result={result} />
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">No scheme here</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs leading-relaxed text-muted-foreground">{result.why_nothing}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Lifecycle result={result} />
      <TilingClosurePanels result={result} />
      <Coverage result={result} />
      {result.variant_risk ? <VariantRisk result={result} /> : null}
      <Pools result={result} />
      {result.interactions.length > 0 ? <Interactions result={result} /> : null}
      <OrderSheet result={result} />
      <RuntimeProvenance provenance={result.provenance} />
    </div>
  );
}

function Lifecycle({ result }: { result: TilingResult }) {
  if (!result.lifecycle && !result.scheme_artifacts) return null;
  const operation = result.lifecycle?.operation ?? "scheme-create";
  const alignment = result.lifecycle?.alignment ?? {};
  const artifacts = Object.values(result.scheme_artifacts ?? {});
  const primaryBackend = result.primary_backend ?? {};
  const backendId = String(primaryBackend.id ?? "unresolved");
  const backendVersion = String(primaryBackend.configured_version ?? "").trim();
  const backendName =
    backendId === "primalscheme3" ? "PrimalScheme3" : backendId === "olivar" ? "Olivar" : backendId;
  const backendLabel = `${backendName}${backendVersion ? ` ${backendVersion}` : ""}`;
  const comparisonBackend = String(primaryBackend.comparison_backend ?? "").trim();
  const download = (name: string, content: string) => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Scheme lifecycle and interchange</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          <Fact label="Operation" value={operation} />
          <Fact label="Alignment" value={String(alignment.authority ?? "not applicable")} />
          <Fact label="Backend" value={backendLabel} />
          {comparisonBackend ? <Fact label="Comparison" value={comparisonBackend} /> : null}
        </dl>
        {alignment.sha256 ? (
          <p className="text-xs break-all text-muted-foreground">
            MSA SHA-256: <span className="font-mono">{String(alignment.sha256)}</span>
          </p>
        ) : null}
        {result.lifecycle?.interaction_evidence ? (
          <details className="rounded-md border border-border/70 bg-surface-wash/20">
            <summary className="min-h-8 cursor-pointer px-3 py-2 text-xs font-medium focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
              {backendLabel} primary interaction evidence
            </summary>
            <div className="space-y-1 border-t px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              <p>
                Status: {String(result.lifecycle.interaction_evidence.status ?? "not reported")}
                {typeof result.lifecycle.interaction_evidence.threshold === "number"
                  ? ` · threshold ${result.lifecycle.interaction_evidence.threshold}`
                  : ""}
              </p>
              {Array.isArray(result.lifecycle.interaction_evidence.summary_lines) &&
              result.lifecycle.interaction_evidence.summary_lines.length > 0 ? (
                <pre className="max-h-48 overflow-auto rounded bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">
                  {result.lifecycle.interaction_evidence.summary_lines.join("\n")}
                </pre>
              ) : null}
              {result.lifecycle.interaction_evidence.interpretation ? (
                <p>{String(result.lifecycle.interaction_evidence.interpretation)}</p>
              ) : null}
              {result.lifecycle.interaction_evidence.warning ? (
                <p>{String(result.lifecycle.interaction_evidence.warning)}</p>
              ) : null}
            </div>
          </details>
        ) : null}
        {result.output_license ? (
          <div className="rounded-md border border-border/70 bg-surface-wash/30 p-3 text-xs leading-relaxed">
            <p className="font-medium">Generated-scheme license: {result.output_license.spdx}</p>
            <p className="mt-1 text-muted-foreground">
              {result.output_license.applies_to}. Attribution
              {result.output_license.share_alike ? " and share-alike" : ""} are required by the
              upstream output license; input-reference licensing remains separate. The downloadable
              license notice travels with the scheme artifacts.
            </p>
          </div>
        ) : null}
        {artifacts.length > 0 ? (
          <div className="space-y-2">
            <p className="font-medium">Reusable scheme artifacts</p>
            <div className="flex flex-wrap gap-2">
              {artifacts.map((artifact) => (
                <button
                  key={`${artifact.kind}-${artifact.sha256}`}
                  type="button"
                  onClick={() => download(artifact.name, artifact.content)}
                  className="min-h-6 rounded-md border px-2.5 py-1.5 text-xs hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  Download {artifact.kind}
                </button>
              ))}
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Keep the BED and config together. Repair and replacement reuse these exact artifacts;
              PCRStudio hashes imported and exported content so scheme history does not depend on a
              host path or filename.
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** How much is covered, where the amplicons fall, and what was missed. */
function Coverage({ result }: { result: TilingResult }) {
  const { coverage, gaps } = result;
  const referenceBases = coverage.reference_bases ?? coverage.of;
  const place = (base: number) => (base / Math.max(referenceBases, 1)) * 100;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Coverage</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
          <Fact label="Covered" value={`${coverage.percent}%`} />
          <Fact label="Bases" value={`${count(coverage.bases)} of ${count(coverage.of)}`} />
          <Fact label="Amplicons" value={String(result.tiles.length)} />
          <Fact label="Pools" value={String(Object.keys(result.pools).length)} />
        </dl>

        {/* Each amplicon on the sequence, coloured by tube. Alternating rows so
            neighbours that overlap do not draw over one another. */}
        <div aria-hidden="true" className="space-y-1">
          {[0, 1].map((row) => (
            <div key={row} className="relative h-3 rounded bg-muted">
              {result.tiles
                .filter((tile) => tile.index % 2 === row)
                .map((tile) => (
                  <div
                    key={tile.index}
                    className={`absolute inset-y-0 rounded-sm ${
                      POOL_FILL[tile.pool % POOL_FILL.length]
                    }`}
                    style={{
                      left: `${place(tile.start)}%`,
                      // A tile that wraps is drawn only to the end of the bar;
                      // the part past it is drawn again at the left below.
                      width: `${Math.max(place(Math.min(tile.end, referenceBases) - tile.start), 0.4)}%`,
                    }}
                  />
                ))}

              {/* The other half of a wrapping tile, at the beginning, because
                  it is one amplicon covering two ends of one picture. */}
              {result.tiles
                .filter((tile) => tile.index % 2 === row && tile.crosses_the_join)
                .map((tile) => (
                  <div
                    key={`${tile.index}-wrapped`}
                    className={`absolute inset-y-0 rounded-sm ${
                      POOL_FILL[tile.pool % POOL_FILL.length]
                    }`}
                    style={{
                      left: "0%",
                      width: `${Math.max(place(tile.end - referenceBases), 0.4)}%`,
                    }}
                  />
                ))}
              {/* Gaps drawn on both rows, because a hole is not in a pool. */}
              {gaps.map((gap) => (
                <div
                  key={`${row}-${gap.from}`}
                  className="absolute inset-y-0 bg-destructive/60"
                  style={{
                    left: `${place(gap.from)}%`,
                    width: `${Math.max(place(gap.bases), 0.3)}%`,
                  }}
                />
              ))}
            </div>
          ))}
          <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
            <span>1</span>
            <span>{count(referenceBases)}</span>
          </div>
        </div>

        {coverage.scope === "requested-regions" ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            The percentage and covered-base count are computed only across the merged requested BED
            regions. The map still uses the full {count(referenceBases)}-base reference for
            coordinate orientation; bases outside the requested regions are not counted as panel
            failures.
          </p>
        ) : null}

        {gaps.length > 0 ? (
          <div className="space-y-1.5 rounded-md border border-destructive/40 bg-destructive/5 p-2.5">
            <p className="text-xs font-medium">
              {gaps.length} stretch{gaps.length === 1 ? "" : "es"} nothing could be placed over
            </p>
            {gaps.map((gap) => (
              <p key={gap.from} className="text-xs leading-relaxed text-muted-foreground">
                <span className="tabular-nums">
                  {count(gap.from)}–{count(gap.to)} ({gap.bases} bases)
                </span>{" "}
                — {gap.why}
              </p>
            ))}
          </div>
        ) : null}

        {result.how_it_was_laid_out.map((line) => (
          <p key={line} className="text-xs leading-relaxed text-muted-foreground">
            {line}
          </p>
        ))}
      </CardContent>
    </Card>
  );
}

/** Which amplicons share a tube, and why they have to be split at all. */
function VariantRisk({ result }: { result: TilingResult }) {
  const evidence = result.variant_risk;
  if (!evidence) return null;
  const affected = evidence.primers.filter(
    (primer) => primer.exact_match_sequences < primer.alignment_depth,
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Observed MSA primer-site conservation
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-4">
          <Fact label="Alignment depth" value={String(evidence.alignment_depth)} />
          <Fact
            label="Primers with non-exact observations"
            value={String(evidence.primers_with_any_non_exact_observation ?? affected.length)}
          />
          <Fact
            label="Primers with definite mismatch/gap"
            value={String(evidence.primers_with_definite_mismatch_or_gap ?? 0)}
          />
          <Fact
            label="Largest definite nonmatch fraction"
            value={`${((evidence.max_definite_nonmatch_fraction ?? 0) * 100).toFixed(1)}%`}
          />
        </dl>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {evidence.interpretation ??
            evidence.semantics ??
            "Alignment conservation evidence only; not a wet-lab dropout guarantee."}
        </p>
        {affected.length > 0 ? (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[720px] text-left text-xs">
              <caption className="sr-only">Tiling primer alignment impact summary</caption>
              <thead className="bg-muted/50">
                <tr>
                  <th scope="col" className="px-2 py-1.5 font-medium">
                    Primer
                  </th>
                  <th scope="col" className="px-2 py-1.5 font-medium">
                    Exact
                  </th>
                  <th scope="col" className="px-2 py-1.5 font-medium">
                    Ambiguity-compatible
                  </th>
                  <th scope="col" className="px-2 py-1.5 font-medium">
                    Definite mismatch/gap
                  </th>
                  <th scope="col" className="px-2 py-1.5 font-medium">
                    3′ terminal non-exact
                  </th>
                </tr>
              </thead>
              <tbody>
                {affected.map((primer) => (
                  <tr key={`${primer.name}-${primer.start}-${primer.end}`} className="border-t">
                    <td className="px-2 py-1.5 font-mono">{primer.name}</td>
                    <td className="px-2 py-1.5">
                      {primer.exact_match_sequences}/{primer.alignment_depth}
                    </td>
                    <td className="px-2 py-1.5">{primer.ambiguity_compatible_sequences}</td>
                    <td className="px-2 py-1.5">{primer.definite_nonmatch_sequences}</td>
                    <td className="px-2 py-1.5">{primer.terminal_5nt_non_exact_sequences}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="rounded-md border bg-surface-wash/20 px-3 py-2 text-xs text-muted-foreground">
            Every imported primer site is exact in every sequence represented by this design MSA.
            This does not establish amplification performance outside that MSA.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Pools({ result }: { result: TilingResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Which tube each one goes in</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(result.pools).map(([pool, indices]) => (
            <div key={pool} className="rounded-md border p-2.5">
              <div className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className={`size-2 rounded-full ${POOL_DOT[Number(pool) % POOL_DOT.length]}`}
                />
                <span className="text-xs font-medium">Pool {Number(pool) + 1}</span>
                <span className="text-xs text-muted-foreground">
                  {indices.length} amplicon{indices.length === 1 ? "" : "s"}
                </span>
              </div>
              <p className="mt-1 font-mono text-xs break-all text-muted-foreground">
                {indices
                  .map(
                    (index) =>
                      result.tiles.find((tile) => tile.index === index)?.name ?? String(index),
                  )
                  .join(", ")}
              </p>
            </div>
          ))}
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">{result.note}</p>
      </CardContent>
    </Card>
  );
}

/** What the oligos in each tube do to each other. */
function Interactions({ result }: { result: TilingResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Inside each tube</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {result.interactions.map((pool) => (
          <div key={pool.pool} className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className={`size-2 rounded-full ${POOL_DOT[pool.pool % POOL_DOT.length]}`}
              />
              <span className="text-xs font-medium">Pool {pool.pool + 1}</span>
              <span className="text-xs text-muted-foreground">{pool.oligos} oligos</span>
            </div>
            <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
              {pool.worst.map((one) => (
                <div
                  key={`${one.a}-${one.b}`}
                  className="flex items-baseline justify-between gap-2 rounded border px-2 py-1 text-xs"
                >
                  <span className="font-mono">
                    {one.a} × {one.b}
                  </span>
                  <span className="text-muted-foreground tabular-nums">{one.badness}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
        {/* The same measure the multiplex engine uses, so two parts of this
            project do not disagree about what a bad interaction is. */}
        <p className="text-xs leading-relaxed text-muted-foreground">
          Scored the way the multiplex engine scores a set: higher is worse, and what matters is how
          the worst pairs here compare with the rest rather than any absolute figure.
        </p>
      </CardContent>
    </Card>
  );
}

function OrderSheet({ result }: { result: TilingResult }) {
  const orderability = result.orderability ?? {
    orderable: false,
    status: "historical-result-orderability-not-recorded",
    note: "This saved tiled-scheme result predates the current PrimalScheme3 orderability contract. Its oligo lines are historical evidence only; regenerate the scheme with the current canonical backend before ordering.",
  };
  if (!orderability.orderable) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">
            Diagnostic scheme — do not order yet
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs font-medium">{orderability.status}</p>
          <p className="text-xs leading-relaxed text-muted-foreground">{orderability.note}</p>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          What to order — {result.order_sheet.length} oligos
        </CardTitle>
        <OrderActions lines={result.order_sheet} kind="tiles" conditions={result.reaction} />
      </CardHeader>
      <CardContent className="space-y-2">
        {result.order_sheet.map((line) => (
          <div key={line.name} className="rounded-md border p-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <span className="flex items-baseline gap-2 font-mono text-xs font-medium">
                <span
                  aria-hidden="true"
                  className={`size-2 shrink-0 self-center rounded-full ${
                    POOL_DOT[(line.pool ?? 0) % POOL_DOT.length]
                  }`}
                />
                {line.name}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                pool {(line.pool ?? 0) + 1} · {line.length} nt · {line.tm} °C
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
