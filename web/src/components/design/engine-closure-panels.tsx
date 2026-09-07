"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OutwardResult, ProbeResult, SingleResult, TilingResult } from "@/lib/api/types";

function copyJson(value: unknown) {
  if (typeof navigator === "undefined" || !navigator.clipboard) return;
  void navigator.clipboard.writeText(JSON.stringify(value, null, 2));
}

function downloadText(name: string, content: string, type = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function Fact({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="mt-0.5 font-medium break-words text-foreground">{value}</dd>
    </div>
  );
}

export function OutwardClosurePanels({ result }: { result: OutwardResult }) {
  const topology = result.topology_validation;
  const cohort = result.enzymes;
  if (!topology && !result.sequencing_handoff && cohort.length === 0) return null;
  return (
    <div className="space-y-4">
      {topology ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">
              Full-reference topology validation
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <dl className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <Fact label="Status" value={topology.status} />
              {topology.fragment_length != null ? (
                <Fact label="Restriction fragment" value={`${topology.fragment_length} bp`} />
              ) : null}
              {topology.upstream_flank_length != null ? (
                <Fact label="Upstream flank" value={`${topology.upstream_flank_length} bp`} />
              ) : null}
              {topology.downstream_flank_length != null ? (
                <Fact label="Downstream flank" value={`${topology.downstream_flank_length} bp`} />
              ) : null}
              {topology.origin_spanning != null ? (
                <Fact label="Origin spanning" value={topology.origin_spanning ? "yes" : "no"} />
              ) : null}
            </dl>
            {topology.reason ? <p className="text-muted-foreground">{topology.reason}</p> : null}
            {topology.source_segments?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <caption className="sr-only">Full-reference source segments</caption>
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th scope="col" className="py-1 pr-3 font-normal">
                        Segment
                      </th>
                      <th scope="col" className="py-1 pr-3 font-normal">
                        Source start
                      </th>
                      <th scope="col" className="py-1 pr-3 font-normal">
                        Source end
                      </th>
                      <th scope="col" className="py-1 font-normal">
                        Length
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {topology.source_segments.map((segment, index) => (
                      <tr
                        key={`${segment.source_start}-${segment.source_end}`}
                        className="border-t border-border/60"
                      >
                        <td className="py-1.5 pr-3">{index + 1}</td>
                        <td className="py-1.5 pr-3 tabular-nums">{segment.source_start}</td>
                        <td className="py-1.5 pr-3 tabular-nums">{segment.source_end}</td>
                        <td className="py-1.5 tabular-nums">{segment.length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {topology.ligation_junction ? (
              <p className="text-xs text-muted-foreground">
                Ligation junction: source cuts {topology.ligation_junction.left_source_cut} →{" "}
                {topology.ligation_junction.right_source_cut}; circle coordinate{" "}
                {topology.ligation_junction.circle_coordinate}. Coordinates are preserved separately
                from transformed-circle geometry.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
      {cohort.length > 1 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">Explicit enzyme cohort</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <caption className="sr-only">Inverse PCR enzyme feasibility cohort</caption>
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th scope="col" className="py-1 pr-3 font-normal">
                      Enzyme
                    </th>
                    <th scope="col" className="py-1 pr-3 font-normal">
                      Usable
                    </th>
                    <th scope="col" className="py-1 font-normal">
                      Reason / fragment
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {cohort.map((row) => (
                    <tr key={row.enzyme} className="border-t border-border/60">
                      <td className="py-1.5 pr-3 font-medium">{row.enzyme}</td>
                      <td className="py-1.5 pr-3">{row.usable ? "yes" : "no"}</td>
                      <td className="py-1.5 text-muted-foreground">
                        {row.why ||
                          (row.expected_fragment
                            ? `expected fragment ${row.expected_fragment.median} bp median`
                            : "exact full-reference feasibility recorded")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Caller order is preserved. PCRStudio does not blend buffer, methylation, star-activity
              or bench constraints into a synthetic enzyme score.
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

export function ProbeClosurePanels({ result }: { result: ProbeResult }) {
  const mgb = result.mgb_authority;
  const optical = result.optical_authority;
  const interactions = result.multiplex_interactions;
  const combined = result.assays
    .map((assay, index) => ({
      index: index + 1,
      value: (assay.specificity_layers as Record<string, unknown> | undefined)?.combined_signal as
        Record<string, unknown> | undefined,
    }))
    .filter((row) => row.value);
  if (!mgb && !optical && !interactions && combined.length === 0) return null;
  return (
    <div className="space-y-4">
      {mgb ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">MGB external Tm authority</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            {mgb.exchange ? (
              <>
                <dl className="grid gap-3 sm:grid-cols-3">
                  <Fact label="Step" value="candidate export" />
                  <Fact label="Authority" value={mgb.exchange.authority_id} />
                  <Fact label="Candidates" value={mgb.exchange.candidates.length} />
                </dl>
                <p className="font-mono text-xs break-all text-muted-foreground">
                  candidate-set SHA-256: {mgb.exchange.candidate_set_sha256}
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => copyJson(mgb.exchange)}
                    className="min-h-8 rounded-md border px-3 py-1.5 text-xs hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    Copy candidate exchange JSON
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      downloadText(
                        "pcrstudio-mgb-candidates.json",
                        JSON.stringify(mgb.exchange, null, 2),
                        "application/json",
                      )
                    }
                    className="min-h-8 rounded-md border px-3 py-1.5 text-xs hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    Download candidate exchange
                  </button>
                </div>
              </>
            ) : (
              <Fact label="Status" value={mgb.status ?? "unresolved"} />
            )}
            {mgb.resolution ? (
              <>
                <dl className="grid gap-3 sm:grid-cols-4">
                  <Fact label="Resolution" value={mgb.resolution.status} />
                  <Fact label="Tool" value={`${mgb.resolution.tool} ${mgb.resolution.version}`} />
                  <Fact label="Calculated" value={mgb.resolution.calculated_at} />
                  <Fact label="Target Tm" value={`${mgb.resolution.target_tm_c} °C`} />
                </dl>
                <p className="text-xs text-muted-foreground">
                  Imported Tm values are accepted only when authority ID and candidate-set hash
                  match this exact export. PCRStudio never calculates ordinary-DNA Tm and labels it
                  MGB-aware.
                </p>
              </>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
      {optical ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">Optical authority</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <dl className="grid gap-3 sm:grid-cols-4">
              <Fact label="Status" value={optical.status} />
              {optical.instrument ? <Fact label="Instrument" value={optical.instrument} /> : null}
              {optical.version ? <Fact label="Profile version" value={optical.version} /> : null}
              <Fact label="Checks" value={optical.validations.length} />
            </dl>
            <p className="text-xs text-muted-foreground">{optical.note}</p>
          </CardContent>
        </Card>
      ) : null}
      {interactions ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">Multiplex oligo interactions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <Fact label="Status" value={interactions.status} />
            {interactions.pairs.length ? (
              <div className="max-h-56 overflow-auto">
                <table className="w-full text-xs">
                  <caption className="sr-only">Multiplex heterodimer interactions</caption>
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th scope="col" className="py-1 pr-3 font-normal">
                        Oligo A
                      </th>
                      <th scope="col" className="py-1 pr-3 font-normal">
                        Oligo B
                      </th>
                      <th scope="col" className="py-1 font-normal">
                        ΔG / status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {interactions.pairs.slice(0, 50).map((pair, index) => (
                      <tr key={index} className="border-t border-border/60">
                        <td className="py-1.5 pr-3">{String(pair.a ?? "")}</td>
                        <td className="py-1.5 pr-3">{String(pair.b ?? "")}</td>
                        <td className="py-1.5 tabular-nums">
                          {typeof pair.heterodimer_dg_kcal_mol === "number"
                            ? `${pair.heterodimer_dg_kcal_mol} kcal/mol`
                            : String(pair.status ?? "")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <p className="text-xs text-muted-foreground">
              No universal rejection threshold is invented; this remains interaction evidence for
              multiplex review.
            </p>
          </CardContent>
        </Card>
      ) : null}
      {combined.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">
              Combined amplicon + probe specificity
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            {combined.map(({ index, value }) => (
              <div key={index} className="rounded-md border border-border/60 p-2">
                <span className="font-medium">Assay {index}</span>
                <span className="ml-2 text-muted-foreground">
                  {String(value?.status ?? "unresolved")} · compatible off-target products{" "}
                  {String(value?.compatible_product_count ?? "unresolved")}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

export function SingleClosurePanels({ result }: { result: SingleResult }) {
  const trace = result.trace_review;
  const walk = result.primer_walking;
  const nested = result.nested_gsp_plan;
  const universal = result.universal_primer_scan as
    { checked?: boolean; hits?: Array<Record<string, unknown>>; note?: string } | null | undefined;
  if (!trace && !walk && !nested && !universal?.hits?.length) return null;
  return (
    <div className="space-y-4">
      {walk ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">Primer-walking coverage plan</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <dl className="grid gap-3 sm:grid-cols-4">
              <Fact label="Usable read" value={`${walk.usable_read_length} bp`} />
              <Fact label="Overlap" value={`${walk.overlap} bp`} />
              <Fact label="Step" value={`${walk.step} bp`} />
              <Fact label="Windows" value={walk.windows.length} />
            </dl>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <caption className="sr-only">Primer walking windows</caption>
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th scope="col" className="py-1 pr-3 font-normal">
                      Walk
                    </th>
                    <th scope="col" className="py-1 pr-3 font-normal">
                      Target interval
                    </th>
                    <th scope="col" className="py-1 font-normal">
                      Overlap
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {walk.windows.map((window) => (
                    <tr key={window.walk_index} className="border-t border-border/60">
                      <td className="py-1.5 pr-3">{window.walk_index}</td>
                      <td className="py-1.5 pr-3 font-mono">
                        {window.target_start}–{window.target_end}
                      </td>
                      <td className="py-1.5">{window.overlap} bp</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted-foreground">{walk.note}</p>
          </CardContent>
        </Card>
      ) : null}
      {trace ? <TraceCard trace={trace} /> : null}
      {nested ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">
              Primary + nested RACE GSP plan
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <dl className="grid gap-3 sm:grid-cols-3">
              <Fact label="Status" value={nested.status} />
              <Fact label="Direction" value={nested.direction} />
              <Fact label="Claim" value="candidate geometry only" />
            </dl>
            <div className="grid gap-2 sm:grid-cols-2">
              <PrimerRecord label="Primary GSP" value={nested.primary} />
              <PrimerRecord label="Nested GSP" value={nested.nested} />
            </div>
            <p className="text-xs text-muted-foreground">{nested.note}</p>
          </CardContent>
        </Card>
      ) : null}
      {universal?.hits?.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">
              Reusable universal-primer matches
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            {universal.hits.map((hit, index) => (
              <div key={index} className="rounded-md border border-border/60 p-2 font-mono text-xs">
                {String(hit.id ?? hit.name ?? `hit-${index + 1}`)} · {String(hit.sequence ?? "")} ·{" "}
                {String(hit.orientation ?? hit.direction ?? "")}
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              Only exact uniquely mapped authority-library matches are shown as reuse options; they
              do not silently replace the ranked designed primer.
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function PrimerRecord({ label, value }: { label: string; value: Record<string, unknown> }) {
  return (
    <div className="rounded-md border border-border/60 p-2">
      <p className="font-medium">{label}</p>
      <p className="mt-1 font-mono text-xs break-all text-muted-foreground">
        {String(value.sequence ?? "sequence unavailable")}
      </p>
      {value.at != null ? (
        <p className="mt-1 text-xs text-muted-foreground">Template start {String(value.at)}</p>
      ) : null}
    </div>
  );
}

function TraceCard({ trace }: { trace: NonNullable<SingleResult["trace_review"]> }) {
  const width = 900,
    height = 180;
  const traceArrays = Object.entries(trace.traces).filter(([, values]) => values.length > 1);
  const globalMax = Math.max(1, ...traceArrays.flatMap(([, values]) => values));
  const points = (values: number[]) =>
    values
      .filter((_, index) => index % Math.max(1, Math.floor(values.length / 1200)) === 0)
      .map(
        (value, index, sampled) =>
          `${(index / Math.max(1, sampled.length - 1)) * width},${height - (value / globalMax) * (height - 8)}`,
      )
      .join(" ");
  const classes: Record<string, string> = {
    A: "text-chart-2",
    C: "text-chart-3",
    G: "text-chart-4",
    T: "text-chart-5",
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">AB1 trace review</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        <dl className="grid gap-3 sm:grid-cols-5">
          <Fact label="Bases" value={trace.base_count} />
          <Fact label="Mean Phred" value={trace.mean_phred ?? "unavailable"} />
          <Fact
            label="Longest Q20+"
            value={trace.q20_interval ? `${trace.q20_interval.length} bases` : "none"}
          />
          <Fact label="Mixed peaks" value={trace.mixed_peaks.length} />
          <Fact label="File" value={trace.filename ?? `${trace.file_bytes} bytes`} />
        </dl>
        {traceArrays.length ? (
          <div className="overflow-x-auto rounded-md border border-border/60 bg-background">
            <svg
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label="Sanger chromatogram trace evidence"
              className="w-full min-w-[720px]"
            >
              <title>Sanger chromatogram trace evidence</title>
              {traceArrays.map(([channel, values]) => (
                <g key={channel} className={classes[channel] ?? "text-foreground"}>
                  <polyline
                    points={points(values)}
                    vectorEffect="non-scaling-stroke"
                    className="fill-none stroke-current"
                    strokeWidth="1.25"
                  />
                </g>
              ))}
            </svg>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>A</span>
          <span>C</span>
          <span>G</span>
          <span>T</span>
          <span>· trace order {trace.trace_order}</span>
        </div>
        {trace.mixed_peaks.length ? (
          <details className="rounded-md border border-border/60 p-2">
            <summary className="cursor-pointer text-xs font-medium">Mixed-peak calls</summary>
            <div className="mt-2 max-h-44 overflow-auto font-mono text-xs">
              {trace.mixed_peaks.slice(0, 100).map((peak) => (
                <p key={`${peak.base_index}-${peak.secondary_channel}`}>
                  base {peak.base_index + 1}: {peak.basecall} · secondary {peak.secondary_channel}{" "}
                  ratio {peak.secondary_ratio}
                </p>
              ))}
            </div>
          </details>
        ) : null}
        <p className="text-xs text-muted-foreground">{trace.note}</p>
      </CardContent>
    </Card>
  );
}

export function TilingClosurePanels({ result }: { result: TilingResult }) {
  const tools = result.managed_tools;
  const visuals = result.native_visualisations;
  const depth = result.observed_depth_evidence;
  const handoff = result.dropout_repair_handoff;
  const diff = result.scheme_version_diff;
  const transition = result.version_transition;
  if (!tools && !visuals && !depth && !handoff && !diff && !transition) return null;
  return (
    <div className="space-y-4">
      {tools ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">Managed native tools</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <caption className="sr-only">Managed tiling tool status</caption>
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th scope="col" className="py-1 pr-3 font-normal">
                      Tool
                    </th>
                    <th scope="col" className="py-1 pr-3 font-normal">
                      Status
                    </th>
                    <th scope="col" className="py-1 font-normal">
                      Version / identity
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(tools).map(([name, raw]) => {
                    const row = raw as Record<string, unknown>;
                    return (
                      <tr key={name} className="border-t border-border/60">
                        <td className="py-1.5 pr-3 font-mono">{name}</td>
                        <td className="py-1.5 pr-3">
                          {String(row.status ?? row.availability ?? "unresolved")}
                        </td>
                        <td className="py-1.5 text-muted-foreground">
                          {String(
                            row.version ??
                              row.configured_version ??
                              row.executable ??
                              row.detail ??
                              "",
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : null}
      {visuals ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">
              Native PrimalScheme visual evidence
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <dl className="grid gap-3 sm:grid-cols-3">
              <Fact label="Status" value={visuals.status} />
              <Fact label="Artifacts" value={visuals.artifacts.length} />
              <Fact label="Warnings" value={visuals.warnings.length} />
            </dl>
            {visuals.artifacts.length ? (
              <div className="flex flex-wrap gap-2">
                {visuals.artifacts.map((artifact) => (
                  <button
                    key={artifact.sha256}
                    type="button"
                    onClick={() =>
                      downloadText(
                        artifact.name,
                        artifact.content,
                        artifact.kind.includes("html")
                          ? "text/html;charset=utf-8"
                          : "text/plain;charset=utf-8",
                      )
                    }
                    className="min-h-8 rounded-md border px-3 py-1.5 text-xs hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    Download {artifact.kind}
                  </button>
                ))}
              </div>
            ) : null}
            {visuals.warnings.length ? (
              <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                {visuals.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
            <p className="text-xs text-muted-foreground">{visuals.note}</p>
          </CardContent>
        </Card>
      ) : null}
      {depth ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">
              Observed amplicon depth / dropout
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <dl className="grid gap-3 sm:grid-cols-5">
              <Fact label="Amplicons" value={depth.summary.amplicons} />
              <Fact label="Mean depth" value={Math.round(depth.summary.mean_depth * 100) / 100} />
              <Fact label="Minimum" value={depth.summary.minimum_depth} />
              <Fact label="Threshold" value={depth.dropout_threshold} />
              <Fact label="Dropouts" value={depth.summary.dropout_count} />
            </dl>
            <div className="max-h-64 overflow-auto">
              <table className="w-full text-xs">
                <caption className="sr-only">Observed tiling amplicon depth</caption>
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th scope="col" className="py-1 pr-3 font-normal">
                      Amplicon
                    </th>
                    <th scope="col" className="py-1 pr-3 font-normal">
                      Depth
                    </th>
                    <th scope="col" className="py-1 font-normal">
                      Review
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {depth.rows.map((row) => (
                    <tr key={row.amplicon} className="border-t border-border/60">
                      <td className="py-1.5 pr-3 font-mono">{row.amplicon}</td>
                      <td className="py-1.5 pr-3 tabular-nums">{row.depth}</td>
                      <td className="py-1.5">
                        {row.dropout ? "below threshold" : "within imported threshold"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted-foreground">{depth.note}</p>
          </CardContent>
        </Card>
      ) : null}
      {handoff ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">Dropout → repair handoff</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <dl className="grid gap-3 sm:grid-cols-3">
              <Fact label="Status" value={handoff.status} />
              <Fact label="Recommended operation" value={handoff.recommended_operation} />
              <Fact label="Amplicons" value={handoff.dropout_amplicons.length} />
            </dl>
            <p className="font-mono text-xs">{handoff.dropout_amplicons.join(", ")}</p>
            <p className="text-xs text-muted-foreground">{handoff.note}</p>
          </CardContent>
        </Card>
      ) : null}
      {diff || transition ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">Scheme version diff</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            {diff ? (
              <dl className="grid gap-3 sm:grid-cols-4">
                <Fact label="Added" value={diff.added.length} />
                <Fact label="Removed" value={diff.removed.length} />
                <Fact label="Changed" value={diff.changed.length} />
                <Fact label="Unchanged" value={diff.unchanged_count} />
              </dl>
            ) : null}
            {diff ? (
              <div className="grid gap-2 sm:grid-cols-3">
                <DiffList label="Added" values={diff.added} />
                <DiffList label="Removed" values={diff.removed} />
                <DiffList label="Changed" values={diff.changed} />
              </div>
            ) : null}
            {transition ? (
              <div className="rounded-md border border-border/60 p-2">
                <span className="font-medium">Version recommendation:</span> {transition.current} →{" "}
                {transition.recommended} · {transition.reason}
                <p className="mt-1 text-xs text-muted-foreground">{transition.note}</p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function DiffList({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="rounded-md border border-border/60 p-2">
      <p className="font-medium">{label}</p>
      <p className="mt-1 font-mono text-xs break-words text-muted-foreground">
        {values.length ? values.join(", ") : "none"}
      </p>
    </div>
  );
}
