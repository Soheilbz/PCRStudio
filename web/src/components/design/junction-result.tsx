"use client";

/**
 * What an assembly design produced.
 *
 * The thing this view has to make legible is that an ordered oligo here is two
 * different things joined together, and that they are measured on two different
 * scales that must never be added.
 *
 * The annealing portion is the sequence used for PCR thermodynamic screening.
 * The tail is not on that fragment's template at all — it is the join to the
 * fragment next door, judged only with the metric that the selected method actually
 * defines. The whole-oligo Tm describes neither a PCR programme nor an assembly
 * hold. None of these calculated Tm values independently authorises a cycler
 * setting; bench cycling belongs to the selected amplification chemistry/SOP.
 *
 * So every primer is drawn as two coloured halves with two numbers under them,
 * rather than as one sequence with one temperature beside it.
 *
 * The other thing shown plainly is the tube. Two primers carrying the same
 * overlap must not share a reaction — in one tube they amplify each other
 * rather than their templates — so which reaction each oligo belongs to is on
 * its card and on its order line rather than in a footnote.
 */

import { OrderActions } from "./order-actions";
import { WorkflowEvidenceCard } from "./workflow-evidence";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count } from "@/lib/numbers";
import type { JunctionEntry, JunctionResult, TailedPrimer } from "@/lib/api/types";

export function JunctionResultView({ result }: { result: JunctionResult }) {
  return (
    <div className="space-y-5">
      <TheConstruct result={result} />
      {result.search && !result.search.complete ? <SearchBoundary result={result} /> : null}
      {result.protocol ? <AssemblyProtocol result={result} /> : null}
      <AssemblyGraph result={result} />
      <FeatureIntegrity result={result} />
      <WorkflowEvidenceCard
        evidence={result.workflow_evidence}
        title="Assembly validation evidence"
      />

      {result.junctions.map((junction) => (
        <JunctionCard key={junction.index} junction={junction} />
      ))}

      {result.clashes.length > 0 ? <Clashes result={result} /> : null}
      {result.overlap_interactions ? <OverlapInteractions result={result} /> : null}

      {result.primers.length > 0 ? (
        <>
          <Primers result={result} />
          <OrderSheet result={result} />
        </>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">No oligos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs leading-relaxed text-muted-foreground">{result.why_nothing}</p>
          </CardContent>
        </Card>
      )}

      <Provenance result={result} />
    </div>
  );
}

function SearchBoundary({ result }: { result: JunctionResult }) {
  const search = result.search;
  if (!search) return null;
  const truncated = result.junctions.filter((one) => one.search && !one.search.complete);
  const diagnosticTruncated = result.junctions.filter(
    (one) => one.search?.fold_diagnostic_complete === false,
  );
  if (search.complete && truncated.length === 0 && diagnosticTruncated.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Search boundary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs leading-relaxed text-muted-foreground">
          This result is the best design found inside the evaluated search set, not a claim of a
          global optimum. The worker measured at most {search.fold_candidate_cap_per_junction}
          candidate overlap windows per junction and allowed at most {search.backtrack_cap}
          clash-resolution moves.
        </p>
        {truncated.length > 0 ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {truncated.map((junction) => (
              <li key={junction.index}>
                Junction {junction.index}: measured {junction.search!.candidate_windows_measured} of{" "}
                {junction.search!.candidate_windows_generated} generated windows —{" "}
                {junction.search!.claim}.
              </li>
            ))}
          </ul>
        ) : null}
        {diagnosticTruncated.length > 0 ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {diagnosticTruncated.map((junction) => (
              <li key={`fold-${junction.index}`}>
                Junction {junction.index}:{" "}
                {junction.search?.fold_claim ??
                  "the optional fold diagnostic was bounded and incomplete"}
                . This diagnostic did not become a hidden validity/ranking gate.
              </li>
            ))}
          </ul>
        ) : null}
        {search.backtrack_limit_hit ? (
          <p className="text-xs text-muted-foreground">
            The backtracking cap was reached after {search.backtrack_steps_used} moves; unresolved
            clashes must therefore not be interpreted as proof that no valid overlap set exists.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function OverlapInteractions({ result }: { result: JunctionResult }) {
  const evidence = result.overlap_interactions;
  if (!evidence) return null;
  const pairs = evidence.pairs ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Overlap interaction diagnostic</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs leading-relaxed text-muted-foreground">{evidence.note}</p>
        <p className="text-xs text-muted-foreground">
          {evidence.model_temperature_c != null
            ? `Model temperature: ${evidence.model_temperature_c} °C · ${evidence.classification}`
            : `No single assembly-temperature model · ${evidence.classification}`}
        </p>
        {pairs.length > 0 ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {pairs.slice(0, 8).map((pair) => (
              <li key={`${pair.a}-${pair.b}`}>
                Junctions {pair.a} / {pair.b}: strongest modeled heterodimer ΔG {pair.dg} kcal/mol,
                Tm {pair.tm} °C
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">
            No pairwise overlap comparison was needed.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/** The selected NEB overlay, kept separate from the chemistry/overlap profile. */
function AssemblyProtocol({ result }: { result: JunctionResult }) {
  const protocol = result.protocol as Record<string, unknown> | undefined;
  if (!protocol) return null;
  const incubation = asRecord(protocol.incubation);
  const fragmentInput = asRecord(protocol.total_fragment_input_pmol);
  const overlap = asRecord(protocol.overlap_bp);
  const source = String(protocol.source_identity ?? "source identity not recorded");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Selected assembly protocol authority
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs font-medium">
          {String(protocol.selection ?? protocol.id ?? "selected assembly protocol")}
        </p>
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
          <Fact label="Method" value={result.method.name} />
          <Fact
            label="Fragments"
            value={String(
              protocol.fragment_count ??
                result.construct.physical_fragments ??
                result.construct.segments.length,
            )}
          />
          <Fact
            label="Authority status"
            value={String(protocol.execution_status ?? "executable-reviewed-branch")}
          />
          <Fact
            label="Source revision"
            value={String(protocol.source_revision ?? "not published/recorded")}
          />
        </dl>
        {protocol.reaction_volume_uL != null || protocol.total_fragment_input_pmol_min != null ? (
          <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
            <Fact
              label="Reaction"
              value={
                protocol.reaction_volume_uL != null
                  ? `${String(protocol.reaction_volume_uL)} µL`
                  : "protocol-owned"
              }
            />
            <Fact
              label="Fragment input"
              value={
                protocol.total_fragment_input_pmol_min != null
                  ? `${String(protocol.total_fragment_input_pmol_min)}–${String(protocol.total_fragment_input_pmol_max)} pmol`
                  : "not transferred"
              }
            />
            <Fact
              label="Incubation"
              value={
                incubation
                  ? `${String(incubation.temperature_c ?? "?")} °C · ${String(incubation.minutes ?? "?")} min`
                  : "not resolved"
              }
            />
            <Fact
              label="PCR fraction"
              value={
                typeof protocol.unpurified_pcr_fraction_max === "number"
                  ? `≤${protocol.unpurified_pcr_fraction_max * 100}%`
                  : "not resolved"
              }
            />
          </dl>
        ) : null}
        {fragmentInput || overlap ? (
          <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
            <Fact
              label="Overlap authority"
              value={
                overlap
                  ? `${String(overlap.min)}–${String(overlap.max)} bp`
                  : `${result.method.overlap_min}–${result.method.overlap_max} bp`
              }
            />
            <Fact
              label="Total fragment input"
              value={
                fragmentInput
                  ? `${String(fragmentInput.min)}–${String(fragmentInput.max)} pmol`
                  : "source-limited for this branch"
              }
            />
            <Fact
              label="Vector:insert"
              value={String(
                protocol.vector_insert_molar_ratio ??
                  protocol.insert_molar_excess ??
                  "protocol/source dependent",
              )}
            />
          </dl>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">
          Source: {source}
          {protocol.source_reviewed_date
            ? ` · reviewed ${String(protocol.source_reviewed_date)}`
            : ""}
          . Gibson and NEBuilder remain distinct chemistries; numeric values are never inherited
          across them.
        </p>
        {protocol.note ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{String(protocol.note)}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function AssemblyGraph({ result }: { result: JunctionResult }) {
  const graph = result.assembly_graph as Record<string, unknown> | undefined;
  if (!graph) return null;
  const nodes = Array.isArray(graph.nodes) ? (graph.nodes as Array<Record<string, unknown>>) : [];
  const edges = Array.isArray(graph.edges) ? (graph.edges as Array<Record<string, unknown>>) : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Construct graph</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          role="img"
          className="flex flex-wrap items-center gap-1.5"
          aria-label={`${String(graph.topology ?? "assembly")} construct graph`}
        >
          {nodes.map((node, index) => (
            <div key={`${String(node.id)}-${index}`} className="contents">
              {index > 0 ? <span className="text-muted-foreground">→</span> : null}
              <div className="rounded-md border bg-surface-wash/35 px-2.5 py-1.5 text-xs">
                <span className="font-medium">{String(node.id)}</span>
                <span className="ml-1.5 text-xs text-muted-foreground">
                  {String(node.kind)} · {String(node.length)} bp
                </span>
              </div>
            </div>
          ))}
          {graph.topology === "circular" && nodes.length > 1 ? (
            <span className="text-xs text-muted-foreground">↺ closes to first fragment</span>
          ) : null}
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {edges.length} explicit junction edge(s).{" "}
          {String(graph.rotation_invariance ?? "Graph order follows the declared construct.")}
        </p>
      </CardContent>
    </Card>
  );
}

function FeatureIntegrity({ result }: { result: JunctionResult }) {
  const value = result.feature_integrity as Record<string, unknown> | undefined;
  if (!value) return null;
  const warnings = Array.isArray(value.warnings) ? value.warnings : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Declared feature integrity</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          <Fact label="Features supplied" value={String(value.features_supplied ?? 0)} />
          <Fact label="Status" value={String(value.status ?? "reported-not-inferred")} />
          <Fact label="Warnings" value={String(warnings.length)} />
        </dl>
        {warnings.length ? (
          <ul className="list-disc space-y-1 pl-5 text-xs text-warning">
            {warnings.map((warning, index) => (
              <li key={index}>{String(warning)}</li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">
            No inconsistency was found in the user-declared feature coordinates.
          </p>
        )}
        <p className="text-xs leading-relaxed text-muted-foreground">
          {String(
            value.claim_boundary ??
              "Feature annotations are user-supplied evidence; PCRStudio does not infer biology from raw sequence.",
          )}
        </p>
      </CardContent>
    </Card>
  );
}

/** The finished molecule, which is what every other number here is about. */
function TheConstruct({ result }: { result: JunctionResult }) {
  const { construct, method } = result;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">What is being built</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
          <Fact label="Construct" value={`${count(construct.length)} bp`} />
          <Fact label="Shape" value={construct.circular ? "circular" : "linear"} />
          <Fact label="Fragments" value={String(construct.segments.length)} />
          <Fact label="Chemistry" value={method.name} />
        </dl>

        {/* The fragments in order, sized by how much of the construct each is. */}
        <div aria-hidden="true" className="flex h-6 overflow-hidden rounded">
          {construct.segments.map((segment, index) => (
            <div
              key={segment.name}
              className={
                segment.tailable
                  ? index % 2 === 0
                    ? "bg-primary/40"
                    : "bg-primary/25"
                  : "bg-muted-foreground/30"
              }
              style={{
                width: `${(segment.length / Math.max(construct.length, 1)) * 100}%`,
              }}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {construct.segments.map((segment) => (
            <span key={segment.name}>
              {segment.name} · {count(segment.length)} bp ·{" "}
              {segment.tailable ? "amplified" : segment.kind}
            </span>
          ))}
        </div>

        <div className="grid gap-2 md:grid-cols-2">
          {construct.segments.map((segment) => (
            <div
              key={`details-${segment.name}`}
              className="rounded-md border border-border/60 p-2.5 text-xs"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium text-foreground">{segment.name}</span>
                <span className="text-muted-foreground">
                  {segment.production_method ?? segment.kind} · {segment.orientation ?? "forward"}
                </span>
              </div>
              <p className="mt-1 text-muted-foreground">
                {segment.mass_ng != null ? `${segment.mass_ng} ng` : "mass not recorded"}
                {segment.concentration_ng_ul != null
                  ? ` · ${segment.concentration_ng_ul} ng/µL`
                  : ""}
                {segment.volume_ul != null ? ` · ${segment.volume_ul} µL` : ""}
              </p>
              {segment.molarity ? (
                <p className="mt-1 text-muted-foreground">
                  Approximate molarity evidence:{" "}
                  {String(
                    (segment.molarity as Record<string, unknown>).pmol_from_mass ?? "unresolved",
                  )}{" "}
                  pmol. Exact provider MW remains authoritative.
                </p>
              ) : null}
              {segment.restriction ? (
                <p className="mt-1 text-muted-foreground">
                  Restriction-linearized input metadata recorded; digest geometry remains explicit
                  rather than inferred.
                </p>
              ) : null}
            </div>
          ))}
        </div>

        <p className="text-xs leading-relaxed text-muted-foreground">{construct.note}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {method.name} uses a reviewed {method.overlap_min}–{method.overlap_max} bp overlap
          envelope.{" "}
          {method.overlap_tm_min != null && method.overlap_tm_metric
            ? `Its executable overlap-Tm floor is ${method.overlap_tm_min} °C in ${method.overlap_tm_metric}. `
            : "No generic overlap-Tm floor is inferred for this chemistry. "}
          {method.note}
        </p>
      </CardContent>
    </Card>
  );
}

/** One join, with where each half of it came from. */
function JunctionCard({ junction }: { junction: JunctionEntry }) {
  const [upstream, downstream] = junction.between;

  if (!junction.sequence) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">
            {upstream} → {downstream} — no join
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs leading-relaxed text-muted-foreground">{junction.why_nothing}</p>
        </CardContent>
      </Card>
    );
  }

  const fromUpstream = junction.from_upstream ?? 0;
  const interposed = junction.interposed ?? 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-baseline justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          {upstream} → {downstream}
        </CardTitle>
        <span className="text-xs text-muted-foreground tabular-nums">
          {junction.length} bp · {junction.wallace_tm} °C
        </span>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* The overlap, coloured by which fragment each part comes from —
            because that is exactly what decides which primer carries it. */}
        <p className="font-mono text-xs break-all">
          <span className="rounded-l bg-primary/25 px-0.5 py-0.5">
            {junction.sequence.slice(0, fromUpstream)}
          </span>
          {interposed > 0 ? (
            <span className="bg-chart-3/30 px-0.5 py-0.5">
              {junction.sequence.slice(fromUpstream, fromUpstream + interposed)}
            </span>
          ) : null}
          <span className="rounded-r bg-chart-4/25 px-0.5 py-0.5">
            {junction.sequence.slice(fromUpstream + interposed)}
          </span>
        </p>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <Swatch className="bg-primary/25" label={`${fromUpstream} from ${upstream}`} />
          {interposed > 0 ? (
            <Swatch
              className="bg-chart-3/30"
              label={`${interposed} on neither — ${junction.carries.join(", ") || "added"}`}
            />
          ) : null}
          <Swatch
            className="bg-chart-4/25"
            label={`${junction.from_downstream ?? 0} from ${downstream}`}
          />
        </div>

        <p className="text-xs leading-relaxed text-muted-foreground">{junction.note}</p>

        {/*
         * A method-specific structure diagnostic, when an explicit model exists.
         * It is ranking evidence only and never creates an unsourced pass mark.
         *
         * Shown as a bar rather than only as a number because the number is a
         * ranking: where it sits between the best and worst overlap that would
         * also have worked here is the readable part, and a bare percentage
         * invites somebody to invent a pass mark for it.
         */}
        {junction.fold ? <Folding fold={junction.fold} /> : null}

        {junction.alternates && junction.alternates > 1 ? (
          <p className="text-xs text-muted-foreground">
            {junction.alternates - 1} other overlap
            {junction.alternates === 2 ? "" : "s"} would also have worked here; this is the
            shortest.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

/**
 * How much self-structure the selected model predicts for the overlap.
 *
 * There is no pass mark, deliberately: at these lengths ordinary sequence and
 * deliberately structured sequence overlap on every statistic, because a
 * hundred-and-twenty-base sequence at 50 °C genuinely has structure. So this
 * shows where the chosen overlap sits among the ones that would also have
 * worked, and leaves the judgement where it belongs.
 */
function Folding({ fold }: { fold: NonNullable<JunctionEntry["fold"]> }) {
  if (!fold.checked) {
    return <p className="text-xs leading-relaxed text-muted-foreground italic">{fold.note}</p>;
  }

  const against = fold.of_alternates;
  // Where this overlap sits between the least and most folded alternative. A
  // single point on a line of one is meaningless, so the bar only appears when
  // there is a spread to place it in.
  const spread = against ? against.worst - against.best : 0;
  const along = spread > 0 ? ((fold.fraction - against!.best) / spread) * 100 : null;

  return (
    <details>
      <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
        Folds on itself: {(fold.fraction * 100).toFixed(1)}%
        {against ? ` of ${(against.worst * 100).toFixed(1)}% at worst here` : ""}
      </summary>

      {along !== null ? (
        <div className="mt-2 space-y-1">
          <div className="relative h-1.5 rounded bg-muted" aria-hidden="true">
            <div
              className="absolute inset-y-0 w-1 rounded-sm bg-primary"
              style={{ left: `calc(${Math.min(100, Math.max(0, along))}% - 2px)` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
            <span>least folded {(against!.best * 100).toFixed(1)}%</span>
            <span>most {(against!.worst * 100).toFixed(1)}%</span>
          </div>
        </div>
      ) : null}

      {fold.structure ? (
        <p className="mt-2 overflow-x-auto font-mono text-xs whitespace-pre text-muted-foreground">
          {fold.structure}
        </p>
      ) : null}

      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{fold.note}</p>
      {fold.model ? <p className="mt-1 text-xs text-muted-foreground">{fold.model}</p> : null}
    </details>
  );
}

function Clashes({ result }: { result: JunctionResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          These joins are not distinct enough
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {result.clashes.map((clash) => (
          <p
            key={clash.between.join("-")}
            className="rounded-md border border-destructive/40 bg-destructive/5 p-2.5 text-xs leading-relaxed"
          >
            Join{clash.between.length > 1 ? "s" : ""} {clash.between.join(" and ")} — {clash.why}
          </p>
        ))}
      </CardContent>
    </Card>
  );
}

/** Each oligo as its two halves, with the two numbers kept apart. */
function Primers({ result }: { result: JunctionResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          The oligos, and which part of each does what
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {result.primers.map((primer) => (
          <PrimerCard key={primer.name} primer={primer} />
        ))}
        <p className="text-xs leading-relaxed text-muted-foreground">
          One reaction per fragment. The two primers that carry the same join are in different tubes
          by construction — in one tube they would amplify each other rather than their templates.
        </p>
      </CardContent>
    </Card>
  );
}

function PrimerCard({ primer }: { primer: TailedPrimer }) {
  return (
    <div className="rounded-md border p-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="font-mono text-xs font-medium">{primer.name}</span>
        <span className="text-xs text-muted-foreground">
          tube: {primer.fragment} · {primer.length} nt
        </span>
      </div>

      <p className="mt-1 font-mono text-xs break-all">
        {primer.tail ? (
          <span className="rounded-l bg-chart-3/30 px-0.5 py-0.5">{primer.tail.sequence}</span>
        ) : null}
        <span className="rounded-r bg-primary/25 px-0.5 py-0.5">{primer.anneals.sequence}</span>
      </p>

      {/* Two numbers, labelled by which step each belongs to. Adding them
          together, or quoting the whole oligo's, is the mistake this view
          exists to prevent. */}
      <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Annealing-core screening Tm</dt>
          <dd className="font-medium tabular-nums">{primer.anneals.tm} °C</dd>
        </div>
        {primer.tail ? (
          <div>
            <dt className="text-muted-foreground">Join, at assembly</dt>
            <dd className="tabular-nums">{primer.tail.wallace_tm} °C</dd>
          </div>
        ) : null}
        <div>
          <dt className="text-muted-foreground">Whole oligo (not a setting)</dt>
          <dd className="text-muted-foreground tabular-nums">{primer.whole_oligo.tm} °C</dd>
        </div>
      </dl>
    </div>
  );
}

function OrderSheet({ result }: { result: JunctionResult }) {
  const orderability = result.orderability ?? {
    orderable: false,
    status: "historical-result-orderability-not-recorded",
    note: "This saved junction result predates the current named-protocol/orderability contract. Historical oligo lines must not be used for ordering; regenerate under the current supported assembly protocol.",
  };
  if (!orderability.orderable) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">
            Diagnostic design — do not order
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
        <OrderActions
          lines={result.order_sheet}
          kind="junction-primers"
          conditions={result.reaction}
        />
      </CardHeader>
      <CardContent className="space-y-2">
        {result.order_sheet.map((line) => (
          <div key={line.name} className="rounded-md border p-2.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <span className="font-mono text-xs font-medium">{line.name}</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {line.tube ? `tube ${line.tube} · ` : ""}
                {line.length} nt · {line.tm} °C
              </span>
            </div>
            <p className="mt-1 font-mono text-xs break-all">{line.sequence}</p>
            {line.note ? <p className="mt-1 text-xs text-muted-foreground">{line.note}</p> : null}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Swatch({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden="true" className={`size-2 rounded-sm ${className}`} />
      {label}
    </span>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-foreground">{value}</dd>
    </div>
  );
}

function Provenance({ result }: { result: JunctionResult }) {
  const made = result.provenance;
  if (!made) return null;
  return (
    <p className="text-xs leading-relaxed text-muted-foreground">
      Computed by primer3-py {made.primer3_py} (libprimer3{" "}
      {made.tool_versions?.libprimer3 ?? "not reported"}) under {made.model.name}, worker{" "}
      {made.worker}, on Python {made.python} ({made.platform}).{" "}
      {result.method.overlap_tm_min != null && result.method.overlap_tm_metric
        ? `The overlap validity floor is ${result.method.overlap_tm_min} °C in ${result.method.overlap_tm_metric}, exactly the metric carried by the reviewed assembly rule; it is not the PCR annealing-core model.`
        : "Wallace overlap Tm, when displayed, is diagnostic only for this method and is not a fabricated validity floor."}
    </p>
  );
}
