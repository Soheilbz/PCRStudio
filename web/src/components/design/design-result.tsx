"use client";

/**
 * What a run produced, and everything it checked to say so.
 *
 * The order is deliberate. What we understood about the sequence comes first,
 * because that is the last chance to notice the wrong thing was pasted. Then
 * the pairs. Then what was not checked, stated rather than omitted — a missing
 * section reads as "nothing to report", and here that would usually be the
 * opposite of the truth.
 */

import { Check, ChevronDown, Copy, Layers, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { copyText } from "@/lib/clipboard";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { count } from "@/lib/numbers";
import { cn } from "@/lib/utils";
import { Nested } from "@/components/heading-level";
import { OrderActions } from "./order-actions";
import { SequenceMap } from "./sequence-map";
import { GelSimulator } from "./gel-simulator";
import { PrimerMatrix } from "./primer-matrix";
import { WorkflowEvidenceCard } from "./workflow-evidence";
import {
  FlankingNumericRecipeCard,
  FlankingProtocol,
  ValidationPlan,
} from "./protocol-result-cards";
import {
  DigitalContext,
  ModifiedOligosContext,
  SpeciesPanelSnapshot,
} from "./result-context-cards";
import type { DesignResult, PrimerPair, Stage } from "@/lib/api/types";

export function DesignResultView({ result }: { result: DesignResult }) {
  const [selectedPairIndex, setSelectedPairIndex] = useState(0);
  const [showOtherPairCards, setShowOtherPairCards] = useState(false);
  const selectedPair = result.pairs[selectedPairIndex] ?? result.pairs[0];

  // Keep the gel synchronized with the pair the scientist is inspecting.
  // Earlier builds always drew off-targets for rank 1 even after the matrix
  // selection changed, which made the visual explanation contradict the card.
  const gelProducts = result.pairs.slice(0, 3).map((pair, idx) => ({
    label: `Pair ${idx + 1}${idx === selectedPairIndex ? " (selected)" : ""}`,
    size: pair.product_size,
    intensity: idx === selectedPairIndex ? 2 : 1,
    isOffTarget: false,
  }));

  // Predicted off-target bands belong to the currently inspected pair.
  if (selectedPair?.off_targets?.checked && selectedPair.off_targets.products) {
    for (const off of selectedPair.off_targets.products) {
      if (off.size && off.size > 0) {
        gelProducts.push({
          label: `Off-target (${off.contig})`,
          size: off.size,
          intensity: 0.8,
          isOffTarget: true,
        });
      }
    }
  }

  return (
    <div className="space-y-5">
      <WhatWeUnderstood result={result} />

      <Funnel stages={result.stages} />

      {result.cloning ? <CloningTails cloning={result.cloning} /> : null}

      {result.backbone ? <BackboneScreen screen={result.backbone} /> : null}

      {result.colony_context ? <ColonyContext context={result.colony_context} /> : null}
      {result.species_panel_snapshot ? (
        <SpeciesPanelSnapshot snapshot={result.species_panel_snapshot} />
      ) : null}
      {result.rpa_screening_cohort ? (
        <RpaScreeningCohort cohort={result.rpa_screening_cohort} />
      ) : null}
      {result.rpa_multiplex_panel ? <RpaMultiplexPanel panel={result.rpa_multiplex_panel} /> : null}
      {result.cloning_coding_context ? (
        <CloningCodingContext context={result.cloning_coding_context} />
      ) : null}
      {result.restriction_workflow ? (
        <RestrictionWorkflow workflow={result.restriction_workflow} />
      ) : null}
      {result.digital_context ? <DigitalContext context={result.digital_context} /> : null}
      {result.modified_oligos ? <ModifiedOligosContext context={result.modified_oligos} /> : null}

      {result.pairs.length === 0 ? (
        <NothingFound result={result} />
      ) : (
        <>
          {/* Comparative Matrix across all candidate pairs */}
          {result.pairs.length > 1 ? (
            <PrimerMatrix
              pairs={result.pairs}
              selectedRank={selectedPairIndex + 1}
              tmPairMaxDifference={
                typeof result.constraints.tm_pair_max_difference === "number"
                  ? result.constraints.tm_pair_max_difference
                  : undefined
              }
              crossDimerThreshold={
                typeof result.interactions?.threshold === "number"
                  ? result.interactions.threshold
                  : undefined
              }
              onSelectPair={(rank) => {
                setSelectedPairIndex(rank - 1);
                const elem = document.getElementById("selected-pair-card");
                if (elem) elem.scrollIntoView({ behavior: "auto", block: "start" });
              }}
            />
          ) : null}

          {/* Virtual Agarose Gel Simulator */}
          <GelSimulator products={gelProducts} />

          <section className="space-y-2.5" aria-labelledby="candidate-detail-heading">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <div>
                <h2 id="candidate-detail-heading" className="text-sm font-medium">
                  {selectedPairIndex === 0
                    ? "Recommended pair"
                    : `Inspecting pair ${selectedPairIndex + 1}`}
                </h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Candidates are ranked deterministically under the active assay profile; rank 1 is
                  a recommendation, not a universal biological guarantee.
                </p>
              </div>
              <span className="text-xs text-muted-foreground">
                {result.pairs.length} candidate pair{result.pairs.length === 1 ? "" : "s"}
              </span>
            </div>
            <SelectionVerdict considered={result.considered} />

            {selectedPair ? (
              <Nested>
                <div id="selected-pair-card" className="scroll-mt-24">
                  <PairCard
                    pair={selectedPair}
                    rank={selectedPairIndex + 1}
                    templateLength={result.target.length}
                    templateName={result.target.name}
                    cloning={result.cloning}
                  />
                </div>
              </Nested>
            ) : null}

            {result.pairs.length > 1 ? (
              <div className="rounded-xl border border-border/60 bg-surface-wash/20 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-xs font-medium">Other candidate details</p>
                    <p className="text-xs text-muted-foreground">
                      The comparison matrix stays visible above; expand full cards only when you
                      need expert-level inspection.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-expanded={showOtherPairCards}
                    onClick={() => setShowOtherPairCards((value) => !value)}
                  >
                    {showOtherPairCards
                      ? "Hide details"
                      : `Show ${result.pairs.length - 1} other card${result.pairs.length === 2 ? "" : "s"}`}
                  </Button>
                </div>
                {showOtherPairCards ? (
                  <Nested>
                    <div className="mt-3 space-y-3">
                      {result.pairs.map((pair, index) =>
                        index === selectedPairIndex ? null : (
                          <PairCard
                            key={pair.left.sequence + pair.right.sequence}
                            pair={pair}
                            rank={index + 1}
                            templateLength={result.target.length}
                            templateName={result.target.name}
                            cloning={result.cloning}
                          />
                        ),
                      )}
                    </div>
                  </Nested>
                ) : null}
              </div>
            ) : null}
          </section>

          <OrderSheet result={result} />
          <TheWholeOrder result={result} />
        </>
      )}

      <TheAssay result={result} />
      <Alert className="border-border/70 bg-muted/20 text-xs">
        <TriangleAlert aria-hidden="true" />
        <AlertTitle>Bench-program authority</AlertTitle>
        <AlertDescription>
          Pair-level generic cycling is intentionally absent. A named chemistry/protocol card, when
          selected, is the bench starting-point authority; otherwise PCRStudio leaves cycling and
          bench annealing unresolved rather than manufacturing a universal programme from the primer
          pair.
        </AlertDescription>
      </Alert>
      {result.protocol ? <FlankingProtocol result={result} /> : null}
      {result.flanking_numeric_recipe ? <FlankingNumericRecipeCard result={result} /> : null}
      {result.validation ? <ValidationPlan plan={result.validation} /> : null}
      <WorkflowEvidenceCard evidence={result.workflow_evidence} />
      <WhatWasChecked result={result} />
      <Provenance result={result} />
    </div>
  );
}

function WhatWeUnderstood({ result }: { result: DesignResult }) {
  const { target } = result;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">What arrived</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-4">
          <Fact label="Name" value={target.name} />
          <Fact label="Length" value={`${count(target.length)} bp`} />
          <Fact label="GC" value={`${target.gc_percent}%`} />
          <Fact
            label="Ambiguity"
            value={target.ambiguous_count === 0 ? "none" : `${target.ambiguous_count} code(s)`}
          />
        </dl>

        {target.notes.length > 0 ? (
          <ul className="space-y-1">
            {target.notes.map((note) => (
              <li
                key={note.kind}
                className="flex gap-2 text-xs leading-relaxed text-muted-foreground"
              >
                <span className="mt-[3px] size-1 shrink-0 rounded-full bg-current text-brand" />
                {note.message}
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

/**
 * Where every candidate went.
 */
function Funnel({ stages }: { stages: Stage[] }) {
  const [open, setOpen] = useState(false);
  if (stages.length === 0) return null;

  const widest = Math.max(...stages.map((stage) => stage.went_in ?? 0), 1);

  return (
    <Card>
      <CardHeader>
        <button
          type="button"
          onClick={() => setOpen((previous) => !previous)}
          className="flex w-full items-center gap-2 rounded-lg text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          aria-expanded={open}
        >
          <ChevronDown
            className={cn("size-4 transition-transform", open ? "" : "-rotate-90")}
            aria-hidden="true"
          />
          <CardTitle className="text-[13px] font-medium">Where every candidate went</CardTitle>
          <span className="ml-auto text-xs text-muted-foreground">{stages.length} steps</span>
        </button>
      </CardHeader>

      <CardContent className="space-y-3">
        {stages.map((stage) => {
          const isScorer = stage.kind === "scorer";
          return (
            <div key={stage.key} className="space-y-1.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                <span className="text-sm font-medium">{stage.title}</span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {!stage.ran
                    ? "skipped"
                    : isScorer
                      ? `${stage.went_in ?? 0} scored`
                      : `${stage.went_in ?? 0} in → ${stage.came_out ?? 0} kept`}
                </span>
              </div>

              {stage.ran ? (
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      isScorer
                        ? "bg-muted-foreground/40"
                        : (stage.came_out ?? 0) === 0
                          ? "bg-destructive"
                          : "bg-primary",
                    )}
                    style={{
                      width: `${Math.max(
                        2,
                        ((isScorer ? (stage.went_in ?? 0) : (stage.came_out ?? 0)) / widest) * 100,
                      )}%`,
                    }}
                  />
                </div>
              ) : null}

              <p className="text-xs leading-relaxed text-muted-foreground">{stage.detail}</p>

              {open && stage.ran && stage.rejections.length > 0 ? (
                <ul className="space-y-0.5 pt-1 pl-3 text-xs text-muted-foreground">
                  {stage.rejections.map((r) => (
                    <li key={r.reason} className="flex justify-between gap-3 tabular-nums">
                      <span>{r.reason}</span>
                      <span>{r.count}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}

        {!open ? (
          <p className="text-xs text-muted-foreground">Open this for the reasons each step gave.</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function NothingFound({ result }: { result: DesignResult }) {
  return (
    <Card className="border-warning/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[13px] font-medium text-warning">
          <TriangleAlert className="size-4" />
          No pair satisfied all of that
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm leading-relaxed">{result.why_nothing}</p>
        <div className="space-y-1.5">
          {result.considered
            .filter((stage) => stage.sentence)
            .map((stage) => (
              <p key={stage.stage} className="text-xs leading-relaxed text-muted-foreground">
                {stage.sentence}
              </p>
            ))}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Why these pairs and not the others.
 *
 * The search counts every candidate it looked at before settling on the ones
 * below; the funnel it kept is in `considered`. The reasons live with the run
 * rather than with any single pair — nothing per-pair survives the search — so
 * this is said once, above the list, and quietly. The three most common
 * reasons are chips whose tooltips carry the worker's own advice, because
 * "no product size fit · 214" is only useful if the next question ("so what
 * would fit?") is one hover away.
 *
 * Rendered as nothing at all when there is no funnel to show: an explanation
 * block explaining an empty set is decoration.
 */
export function SelectionVerdict({ considered }: { considered: DesignResult["considered"] }) {
  const widest = considered[0];
  if (!widest || widest.considered === 0) return null;

  const rejections = considered
    .flatMap((stage) => stage.rejections)
    .filter((rejection) => rejection.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 3);

  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
      <span>
        Top-ranked after evaluating {count(widest.considered)} candidates under this profile
      </span>
      {rejections.map((rejection, index) => (
        <span
          key={`${rejection.reason}-${index}`}
          title={rejection.advice || undefined}
          className="rounded-full border px-2.5 py-0.5"
        >
          {rejection.reason} · {count(rejection.count)}
        </span>
      ))}
    </div>
  );
}

function PairCard({
  pair,
  rank,
  templateLength,
  templateName,
  cloning,
}: {
  pair: PrimerPair;
  rank: number;
  templateLength: number;
  templateName?: string;
  cloning?: DesignResult["cloning"];
}) {
  const serious = pair.off_targets.serious ?? 0;
  const fullOligoInteraction = pair.tailed?.interaction;
  const [showMap, setShowMap] = useState(true);

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
                ? ", bench Ta not inferred"
                : `, thermodynamic reference ${pair.annealing_temperature} °C`}
              {pair.crosses_the_join ? ", across the join" : ""}
            </span>
          </CardTitle>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground tabular-nums">
              score {pair.score.toFixed(2)}
            </span>
            <button
              type="button"
              onClick={() => setShowMap((prev) => !prev)}
              className="inline-flex min-h-6 items-center gap-1 rounded border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-surface-warm/45 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <Layers className="size-3" />
              {showMap ? "Hide map" : "Show map"}
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Interactive Sequence & Primer Map for this pair */}
        {showMap ? (
          <SequenceMap templateLength={templateLength} templateName={templateName} pair={pair} />
        ) : null}

        <div className="grid gap-2.5 md:grid-cols-2">
          <OligoRow
            label="Forward"
            oligo={pair.left}
            at={`${pair.left_at.start + 1}–${pair.left_at.start + pair.left_at.length}`}
            accessibility={pair.accessibility?.left ?? null}
            tail={cloning?.applied ? cloning.forward?.site : undefined}
          />
          <OligoRow
            label="Reverse"
            oligo={pair.right}
            at={`${pair.right_at.start - pair.right_at.length + 2}–${pair.right_at.start + 1}`}
            accessibility={pair.accessibility?.right ?? null}
            tail={cloning?.applied ? cloning.reverse?.site : undefined}
          />
        </div>

        <dl className="grid gap-x-6 gap-y-1.5 text-xs sm:grid-cols-3">
          <Fact label="Tm difference" value={`${pair.tm_difference} °C`} small />
          <Fact label="Pair dimer ΔG" value={`${pair.cross_dimer_dg} kcal/mol`} small />
          <Fact
            label="Off-targets"
            value={
              pair.off_targets.checked
                ? `${pair.off_targets.product_count ?? 0} predicted${serious ? `, ${serious} firm` : ""}`
                : "not checked"
            }
            small
          />
        </dl>
        {pair.off_targets.terminal_mismatch_scan ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Species-specific review includes potential sites with a terminal 3′ mismatch. This is a
            conservative screening signal, not proof that the polymerase will extend the site.
          </p>
        ) : null}

        {/* Only when it changes what goes in the tube.
            An easy product saying "this product is easy" on every card is a
            line nobody reads, which makes the one that matters invisible. */}
        {pair.quality || pair.uniformity || pair.thermodynamic_temperature_role ? (
          <details>
            <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
              Additional in-silico diagnostics
            </summary>
            <div className="mt-2 space-y-1 text-xs leading-relaxed text-muted-foreground">
              {pair.quality ? (
                <p>
                  <span className="font-medium text-foreground">Heuristic quality summary:</span>{" "}
                  {pair.quality.score}/100. This is reported beside the ranking score and is not a
                  universal validity threshold.
                </p>
              ) : null}
              {pair.uniformity ? (
                <p>
                  <span className="font-medium text-foreground">Amplicon GC uniformity:</span>{" "}
                  {pair.uniformity.min_window_gc}–{pair.uniformity.max_window_gc}% across{" "}
                  {pair.uniformity.window_bp}-bp windows
                  {pair.uniformity.note ? ` — ${pair.uniformity.note}` : "."}
                </p>
              ) : null}
              {pair.thermodynamic_temperature_role ? (
                <p>
                  <span className="font-medium text-foreground">
                    Thermodynamic temperature role:
                  </span>{" "}
                  {pair.thermodynamic_temperature_role}
                  {pair.cross_dimer_temperature_c != null
                    ? `; cross-dimer model ${pair.cross_dimer_temperature_c} °C`
                    : ""}
                  {pair.accessibility_temperature_c != null
                    ? `; accessibility model ${pair.accessibility_temperature_c} °C`
                    : ""}
                  .
                </p>
              ) : null}
            </div>
          </details>
        ) : null}

        {pair.amplicon_profile && pair.amplicon_profile.difficulty !== "easy" ? (
          <p className="rounded border border-warning/30 bg-warning/5 p-2 text-xs leading-relaxed text-muted-foreground">
            <span className="font-medium text-warning">
              {pair.amplicon_profile.difficulty_scope ===
              "composition-only-not-rpa-performance-threshold"
                ? "High-GC composition needs RPA-specific review"
                : pair.amplicon_profile.difficulty === "very hard"
                  ? "High-GC product needs difficult-template review"
                  : "High-GC product flagged for bench review"}
            </span>
            {" — "}
            {pair.amplicon_profile.note}
          </p>
        ) : null}

        {cloning?.applied && fullOligoInteraction ? (
          <p className="rounded border border-border/70 bg-surface-wash/35 p-2 text-xs leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">Full ordered-oligo check</span>
            {" — "}
            {fullOligoInteraction.worsened_by <= 0.5
              ? `Adding the restriction tails did not materially strengthen the predicted cross-oligo interaction (${fullOligoInteraction.with_tails.dg} kcal/mol).`
              : `The predicted interaction changes from ${fullOligoInteraction.without_tails.dg} to ${fullOligoInteraction.with_tails.dg} kcal/mol after the tails are added. Treat this as an in-silico review flag and confirm the complete oligos experimentally.`}
          </p>
        ) : null}

        {pair.amplicon ? (
          <details>
            <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
              The product ({pair.product_size} bp
              {pair.amplicon_profile ? `, ${pair.amplicon_profile.gc}% GC` : ""})
            </summary>
            <div className="mt-2 flex items-start gap-1.5">
              <p className="max-h-40 flex-1 overflow-y-auto rounded border bg-surface-wash/45 p-2 font-mono text-xs leading-relaxed break-all">
                {pair.amplicon}
              </p>
              <CopyOne text={pair.amplicon} label="Copy the product sequence" />
            </div>
          </details>
        ) : null}

        {pair.off_targets.checked && (pair.off_targets.products?.length ?? 0) > 0 ? (
          <details>
            <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
              Unwanted products ({pair.off_targets.product_count ?? 0})
            </summary>
            <ul className="mt-2 space-y-1">
              {(pair.off_targets.products ?? []).map((product) => (
                <li
                  key={`${product.contig}:${product.start}:${product.size}`}
                  className="flex flex-wrap gap-x-3 text-xs text-muted-foreground"
                >
                  <span className="text-foreground tabular-nums">{product.size} bp</span>
                  <span className="truncate">
                    {product.contig}:{count(product.start)}–{count(product.end)}
                  </span>
                  <span className="tabular-nums">
                    weaker primer binds at {product.worst_dg} kcal/mol
                  </span>
                  {product.forward?.mismatches || product.reverse?.mismatches ? (
                    <span>
                      mismatch topology: F {product.forward?.mismatches ?? 0}
                      {product.forward?.nearest_three_prime_mismatch != null
                        ? ` (nearest ${product.forward.nearest_three_prime_mismatch} nt from 3′${
                            product.forward.mismatch_base_pairs_from_three_prime?.[0]
                              ? `; ${product.forward.mismatch_base_pairs_from_three_prime[0].primer_base}↔${product.forward.mismatch_base_pairs_from_three_prime[0].template_base}`
                              : ""
                          })`
                        : ""}
                      , R {product.reverse?.mismatches ?? 0}
                      {product.reverse?.nearest_three_prime_mismatch != null
                        ? ` (nearest ${product.reverse.nearest_three_prime_mismatch} nt from 3′${
                            product.reverse.mismatch_base_pairs_from_three_prime?.[0]
                              ? `; ${product.reverse.mismatch_base_pairs_from_three_prime[0].primer_base}↔${product.reverse.mismatch_base_pairs_from_three_prime[0].template_base}`
                              : ""
                          })`
                        : ""}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        <details className="group">
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

function OligoRow({
  label,
  oligo,
  at,
  accessibility,
  tail,
}: {
  label: string;
  oligo: PrimerPair["left"];
  /** Where it sits on the template, one-based and inclusive. */
  at: string;
  /** Probability its landing site is unpaired, when that was computed. */
  accessibility: number | null;
  /** If 5' tail or restriction site is prepended */
  tail?: string;
}) {
  return (
    <div className="space-y-1.5 rounded-lg border bg-surface-wash/45 p-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium">{label}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {oligo.length} nt · {oligo.gc_percent}% GC · {oligo.tm} °C
        </span>
      </div>

      <div className="flex items-start gap-1.5">
        <div className="flex-1 font-mono text-xs break-all">
          {tail && oligo.sequence.startsWith(tail) ? (
            <>
              <span
                className="rounded bg-brand/20 px-1 py-0.5 font-semibold text-brand"
                title="5′ Tail / Overhang"
              >
                {tail}
              </span>
              <span>{oligo.sequence.slice(tail.length)}</span>
            </>
          ) : (
            <span>{oligo.sequence}</span>
          )}
        </div>
        <CopyOne text={oligo.sequence} label={`Copy the ${label.toLowerCase()} primer`} />
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        <Term term="Position" value={at} />
        <Term term="3′ end ΔG" value={`${oligo.three_prime_dg} kcal/mol`} />
        <Term
          term="Hairpin"
          value={
            oligo.hairpin.found ? `${oligo.hairpin.dg} kcal/mol, ${oligo.hairpin.tm} °C` : "none"
          }
        />
        <Term
          term="Self-dimer"
          value={
            oligo.self_dimer.found
              ? `${oligo.self_dimer.dg} kcal/mol, ${oligo.self_dimer.tm} °C`
              : "none"
          }
        />
        {accessibility !== null ? (
          <Term term="Site unpaired" value={accessibility.toExponential(1)} />
        ) : null}
      </dl>
    </div>
  );
}

function Term({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex min-w-0 justify-between gap-2">
      <dt>{term}</dt>
      <dd className="text-foreground tabular-nums">{value}</dd>
    </div>
  );
}

/** Copy one thing, and say so for two seconds. */
function CopyOne({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={() => {
        void copyText(text)
          .then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 2000);
          })
          .catch(() => {
            toast.error("Could not reach the clipboard", {
              description:
                "Your browser refused the request. Select the sequence and copy it manually.",
            });
          });
      }}
      className="inline-flex size-6 shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
  );
}

function OrderSheet({ result }: { result: DesignResult }) {
  const historicalSpecificityV4 = Boolean(result.background && "clamp" in result.background);
  if (historicalSpecificityV4) {
    return (
      <section className="rounded-lg border p-3">
        <h2 className="text-sm font-medium">Historical specificity result — do not order</h2>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          This saved run carries the retired specificity-v4 clamp contract. Regenerate under
          mismatch-complete specificity-v5 before using supplier lines.
        </p>
      </section>
    );
  }
  const topAmplicon = result.pairs[0]?.amplicon
    ? { name: result.target.name || "amplicon", sequence: result.pairs[0].amplicon }
    : undefined;

  return (
    <section className="space-y-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium">What to order</h2>
        <OrderActions
          lines={result.order_sheet}
          targetName={result.target.name}
          kind="primers"
          conditions={result.reaction}
          amplicon={topAmplicon}
        />
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-xs">
          <caption className="sr-only">Selected primer sequences and thermodynamics</caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                Name
              </th>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                Sequence (5&prime; → 3&prime;)
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                nt
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Tm
              </th>
            </tr>
          </thead>
          <tbody>
            {result.order_sheet.map((oligo) => (
              <tr key={oligo.name} className="border-t">
                <td className="px-3 py-1.5 font-medium whitespace-nowrap">{oligo.name}</td>
                <td className="px-3 py-1.5 font-mono break-all">{oligo.sequence}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{oligo.length}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{oligo.tm}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TheWholeOrder({ result }: { result: DesignResult }) {
  const interactions = result.interactions;
  if (!interactions) return null;

  const acrossDesigns = interactions.worst.filter((entry) => !entry.same_pair);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          The order as a whole — {interactions.checked} oligos
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm leading-relaxed text-muted-foreground">{interactions.note}</p>

        {interactions.worst.length > 0 ? (
          <ul className="space-y-1">
            {interactions.worst.map((entry) => (
              <li
                key={`${entry.a}:${entry.b}`}
                className="flex flex-wrap gap-x-3 text-xs text-muted-foreground"
              >
                <span className="text-foreground">
                  {entry.a} + {entry.b}
                </span>
                <span className="tabular-nums">
                  {entry.dg} kcal/mol at {entry.tm} °C
                </span>
                <span>{entry.same_pair ? "same pair, expected" : "different designs"}</span>
              </li>
            ))}
          </ul>
        ) : null}

        {acrossDesigns.length > 0 ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            The ones marked as different designs only matter if those two oligos meet — which they
            will not unless you multiplex them or make a mistake at the bench.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Provenance({ result }: { result: DesignResult }) {
  const made = result.provenance;
  if (!made) return null;

  return (
    <p className="text-xs leading-relaxed text-muted-foreground">
      Computed by primer3-py {made.primer3_py} (libprimer3{" "}
      {made.tool_versions?.libprimer3 ?? "not reported"}) under {made.model.name}, worker{" "}
      {made.worker}, on Python {made.python} ({made.platform}). {made.note} Keep this beside the
      primers: a design nobody can reproduce is a design nobody can publish.
    </p>
  );
}

function TheAssay({ result }: { result: DesignResult }) {
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
      <CardContent className="space-y-3">
        {set.length > 0 ? (
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
        ) : null}

        <p className="text-xs leading-relaxed text-muted-foreground">
          {assay.overruled.length === 0
            ? "This assay's own numbers were the ones used."
            : "Struck-through numbers are what the assay asked for; the number beside each is what ran instead. Neither is wrong — the assay describes the reaction, and you can see something it cannot."}
        </p>
      </CardContent>
    </Card>
  );
}

function WhatWasChecked({ result }: { result: DesignResult }) {
  const { reaction, accessibility, background, request: requestAudit, transcript } = result;
  const specificityMethod = background?.method;
  const seedRule = specificityMethod?.seed.match.includes("IUPAC")
    ? "exact on unambiguous sequence; possible on IUPAC ambiguity"
    : "exact";
  const chemistry = reaction.chemistry;
  const chemistrySummary = chemistry
    ? [
        chemistry.strand_displacing ? "strand-displacing" : null,
        chemistry.proofreading ? "proofreading" : null,
        chemistry.five_prime_exonuclease ? "5′ exonuclease" : null,
        chemistry.rpa_compatible ? "RPA-compatible" : null,
        chemistry.thermostable ? "thermostable" : "not thermostable",
      ]
        .filter(Boolean)
        .join(" · ")
    : undefined;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">What was checked</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
          <Fact label="Reaction" value={reaction.polymerase_name} small />
          <Fact
            label={reaction.context_role ? "Screening-model chemistry flags" : "Chemistry"}
            value={chemistrySummary}
            small
          />
          <Fact label="Melting temperature model" value={reaction.model.name} small />
          <Fact
            label="Salt"
            value={`${reaction.mv_conc} mM monovalent, ${reaction.dv_conc} mM divalent`}
            small
          />
          <Fact
            label="dNTP and Tm oligo input"
            value={`${reaction.dntp_conc} mM total dNTP, ${reaction.dna_conc} nM Tm oligo input`}
            small
          />
          {specificityMethod ? (
            <Fact
              label="Specificity scope"
              value={
                background?.template_only ? "Pasted template only" : "Supplied background sequence"
              }
              small
            />
          ) : null}
          {transcript?.junction_spanning_required ? (
            <Fact
              label="Transcript geometry"
              value={`${transcript.exon_junctions.length} junction${transcript.exon_junctions.length === 1 ? "" : "s"} enforced`}
              small
            />
          ) : null}
        </dl>

        {reaction.context_note ? (
          <div className="rounded-md border border-border/70 bg-muted/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            <p>
              Thermodynamic context: {reaction.context_role ?? "calculation context"}.{" "}
              {reaction.context_note}
            </p>
          </div>
        ) : null}

        {specificityMethod ? (
          <div className="rounded-md border border-border/70 bg-muted/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            <p>
              Specificity method:{" "}
              <span className="font-medium text-foreground">{specificityMethod.id}</span>
              {" · "}
              {specificityMethod.seed.strategy === "pigeonhole-k-plus-one-partitions"
                ? "mismatch-complete whole-primer seed partitions"
                : `${specificityMethod.seed.length ?? "legacy"}-base ${seedRule} 3′ seed`}
              , up to {specificityMethod.max_mismatches} mismatches, ΔG cutoff{" "}
              {specificityMethod.binding_score.dg_filter_applied
                ? `${specificityMethod.binding_score.minimum_dg_kcal_mol} kcal/mol filter`
                : "no ΔG site-existence filter"}
              .
            </p>
            <p className="mt-1">
              This is a bounded sequence screen; it does not replace BLAST/Primer-BLAST or establish
              whole-database uniqueness.
            </p>
          </div>
        ) : null}

        {transcript?.junction_spanning_required ? (
          <div className="rounded-md border border-brand/30 bg-brand/5 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            <p>
              Every reported pair crosses at least one supplied transcript boundary (
              {transcript.exon_junctions.join(", ")}).
            </p>
            <p className="mt-1">{transcript.note}</p>
          </div>
        ) : null}

        {requestAudit ? (
          <div className="rounded-md border border-border/70 bg-muted/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            <p>
              Resolved run:{" "}
              {requestAudit.rna.effective
                ? "RNA → reverse transcription → amplification"
                : "DNA amplification"}
              {" · "}
              {requestAudit.circular ? "circular template" : "linear template"}
              {" · "}
              {requestAudit.known_variants} known variant(s), {requestAudit.excluded_regions}{" "}
              excluded region(s).
            </p>
            <p className="mt-1">
              Preset{" "}
              <span className="font-medium text-foreground">
                {requestAudit.polymerase.effective}
              </span>
              , purpose{" "}
              <span className="font-medium text-foreground">{requestAudit.purpose.effective}</span>;
              coordinate frame: {requestAudit.coordinates.system}.
            </p>
          </div>
        ) : null}

        {result.purpose ? (
          <div className="rounded-md border border-border/70 bg-muted/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            <p>
              Search purpose:{" "}
              <span className="font-medium text-foreground">{result.purpose.name}</span> (
              <span className="font-mono">{result.purpose.id}</span>). {result.purpose.summary}
            </p>
            <p className="mt-1">
              Purpose constraints:{" "}
              {Object.keys(result.purpose.constraints).length === 0
                ? "none"
                : Object.entries(result.purpose.constraints)
                    .map(([key, value]) => `${key}=${value}`)
                    .join(" · ")}
              ; ranking weights:{" "}
              {Object.keys(result.purpose.ranking_weights).length === 0
                ? "none"
                : Object.entries(result.purpose.ranking_weights)
                    .map(([key, value]) => `${key}=${value}`)
                    .join(" · ")}
              .
            </p>
            <p className="mt-1">
              Explicit request overrides of purpose constraints:{" "}
              {result.purpose.overridden.length === 0
                ? "none"
                : result.purpose.overridden.join(", ")}
              .
            </p>
          </div>
        ) : null}

        {reaction.model.role === "screening-proxy" ? (
          <Alert className="border-brand/30 bg-brand/5 text-xs">
            <TriangleAlert aria-hidden="true" />
            <AlertTitle>RPA temperature note</AlertTitle>
            <AlertDescription>
              {reaction.model.interpretation ??
                "The reported Tm is a sequence-screening proxy, not a mechanistic RPA binding or yield prediction."}
            </AlertDescription>
          </Alert>
        ) : null}

        <ul className="space-y-1.5 border-t pt-3">
          <Checked
            done={accessibility.checked}
            done_text={`Template folding: ${accessibility.model}. Binding sites that the template keeps closed are ranked below ones it leaves open.`}
            missing_text={accessibility.note}
          />
          {/* Absent on engines that never ask the question; present and
              `checked: false` when this page asked and nobody answered. The
              two have to look different, which is why this reads `checked`
              rather than testing for the block. */}
          {result.variants ? (
            <Checked
              done={result.variants.checked}
              done_text={variantSummaryNote(result.variants)}
              missing_text={variantSummaryNote(result.variants)}
            />
          ) : null}
        </ul>
      </CardContent>
    </Card>
  );
}

function variantSummaryNote(variants: DesignResult["variants"]): string {
  if (!variants) return "";
  if (variants.note) return variants.note;
  const supplied = variants.supplied ?? variants.given ?? 0;
  if (!variants.checked || supplied === 0) {
    return "No known variants were given, so no primer was checked against one.";
  }
  const rejected = variants.rejected ?? 0;
  return `${supplied} known variant${supplied === 1 ? "" : "s"} checked; ${rejected} candidate${rejected === 1 ? "" : "s"} rejected for variant overlap.`;
}

function CloningTails({ cloning }: { cloning: NonNullable<DesignResult["cloning"]> }) {
  const ends = [
    ["Forward end", cloning.forward] as const,
    ["Reverse end", cloning.reverse] as const,
  ].filter(([, end]) => end);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">On the ends of every primer below</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {cloning.applied ? (
          <dl className="grid gap-3 sm:grid-cols-2">
            {ends.map(([label, end]) => (
              <div key={label} className="space-y-0.5">
                <dt className="text-xs text-muted-foreground">
                  {label} — {end!.enzyme}
                </dt>
                <dd className="font-mono text-xs break-all">
                  <span className="text-muted-foreground">{end!.protective}</span>
                  <span className="font-medium">{end!.site}</span>
                </dd>
                {end!.first_observed_activity_flanking_bases != null && (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Close-to-end evidence
                    {end!.end_cleavage_evidence_identity
                      ? ` (${end!.end_cleavage_evidence_identity})`
                      : ""}
                    : first non-zero activity was observed at{" "}
                    {end!.first_observed_activity_flanking_bases} flanking base(s). This is
                    descriptive supplier evidence, not an efficiency recommendation or a universal
                    minimum.
                  </p>
                )}
                {end!.first_observed_activity_flanking_bases != null &&
                  (() => {
                    const used = label.startsWith("Forward")
                      ? cloning.forward_protective_bases
                      : cloning.reverse_protective_bases;
                    return used != null && used < end!.first_observed_activity_flanking_bases ? (
                      <p className="text-xs leading-relaxed text-warning">
                        This design uses {used} flanking base(s), below the first non-zero activity
                        point recorded for the cited supplier/formulation.
                      </p>
                    ) : null;
                  })()}
              </div>
            ))}
          </dl>
        ) : null}
        {cloning.applied && cloning.directional == null ? (
          <div className="space-y-1 text-xs leading-relaxed text-warning">
            <p>
              Directionality is unresolved: insert-end geometry alone does not establish the vector
              sites or their order. Verify the exact vector-end geometry before treating this as
              directional cloning.
            </p>
            {cloning.insert_ends_compatible != null ? (
              <p>
                Insert-end compatibility:{" "}
                {cloning.insert_ends_compatible
                  ? "compatible cohesive/end family — orientation risk remains"
                  : "incompatible end families — vector geometry still required"}
                .
              </p>
            ) : null}
            {cloning.insert_end_compatibility_scope ? (
              <p>
                Compatibility scope: insert-end sequence geometry only. Vector-end compatibility,
                ligation efficiency and whether a hybrid ligation junction is recleavable are not
                modeled.
              </p>
            ) : null}
          </div>
        ) : null}
        {cloning.applied && cloning.digest_validation ? (
          <div className="space-y-1 rounded-md border border-border/70 bg-surface-wash/35 p-2 text-xs leading-relaxed text-muted-foreground">
            <p className="font-medium text-foreground">Digest / ligation evidence boundary</p>
            <p>Methylation: {cloning.digest_validation.methylation_sensitivity_status}.</p>
            <p>Star activity: {cloning.digest_validation.star_activity_status}.</p>
            <p>
              Double-digest compatibility:{" "}
              {cloning.digest_validation.double_digest_compatibility_status}.
            </p>
            <p>
              Heat inactivation / cleanup: {cloning.digest_validation.heat_inactivation_status}.
            </p>
            <p>
              Junction re-cleavage: {cloning.digest_validation.ligation_junction_recleavage_status}.
            </p>
            <p>{cloning.digest_validation.note}</p>
          </div>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">{cloning.note}</p>
      </CardContent>
    </Card>
  );
}

function CloningCodingContext({
  context,
}: {
  context: NonNullable<DesignResult["cloning_coding_context"]>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Restriction-cloning coding / fusion context
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label="Intent" value={context.intent} />
          <Fact
            label="CDS"
            value={
              context.cds_start !== undefined && context.cds_end !== undefined
                ? `${context.cds_start}..${context.cds_end} (${context.cds_length_bp} bp)`
                : "not applicable"
            }
          />
          <Fact label="Stop policy" value={context.stop_codon_policy} />
          <Fact
            label="Junction phase"
            value={
              context.vector_junction_frame === null || context.vector_junction_frame === undefined
                ? "not declared"
                : String(context.vector_junction_frame)
            }
          />
        </dl>
        {context.fusion_tag || context.linker_aa ? (
          <p className="text-muted-foreground">
            Fusion tag: {context.fusion_tag || "—"} · linker AA: {context.linker_aa || "—"}
          </p>
        ) : null}
        <p className="text-muted-foreground">{context.claim_boundary}</p>
      </CardContent>
    </Card>
  );
}

function RpaScreeningCohort({
  cohort,
}: {
  cohort: NonNullable<DesignResult["rpa_screening_cohort"]>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          RPA empirical screening short-list
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <p className="text-muted-foreground">{cohort.claim_boundary}</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {cohort.pairs.map((pair) => (
            <div key={pair.candidate} className="rounded-md border border-border/60 p-2">
              <p className="font-medium">Candidate {pair.primary_rank}</p>
              <p className="text-muted-foreground">
                score {pair.score} · L {pair.left_start} · R {pair.right_start}
                {pair.amplicon_length ? ` · ${pair.amplicon_length} bp` : ""}
              </p>
            </div>
          ))}
        </div>
        <p className="text-muted-foreground">
          Primary ranking is unchanged; shortlist method: {cohort.selection_method}.
        </p>
        <div className="rounded-md border border-border/60 p-2">
          <p className="font-medium">Full empirical RPA assay-development authority</p>
          <p className="text-muted-foreground">
            {cohort.full_empirical_assay_development.forward_candidates_recommended.join("–")}{" "}
            forward ×{" "}
            {cohort.full_empirical_assay_development.reverse_candidates_recommended.join("–")}{" "}
            reverse = {cohort.full_empirical_assay_development.pair_matrix_recommended.join("–")}{" "}
            combinations. Prepared:{" "}
            {cohort.full_empirical_assay_development.prepared_forward_candidates.length} ×{" "}
            {cohort.full_empirical_assay_development.prepared_reverse_candidates.length} ={" "}
            {cohort.full_empirical_assay_development.prepared_matrix_pair_count}; matrix{" "}
            {cohort.full_empirical_assay_development.matrix_ready ? "ready" : "insufficient"}.{" "}
            {cohort.full_empirical_assay_development.note}
          </p>
          <p className="text-muted-foreground">
            Forward candidates:{" "}
            {cohort.full_empirical_assay_development.prepared_forward_candidates
              .map((row) => row.sequence)
              .join(", ") || "none"}
          </p>
          <p className="text-muted-foreground">
            Reverse candidates:{" "}
            {cohort.full_empirical_assay_development.prepared_reverse_candidates
              .map((row) => row.sequence)
              .join(", ") || "none"}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function RpaMultiplexPanel({ panel }: { panel: NonNullable<DesignResult["rpa_multiplex_panel"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          RPA multiplex empirical panel context
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <p className="text-muted-foreground">{panel.selection_authority}</p>
        <p>
          {panel.target_count} targets · panel {panel.panel_sha256.slice(0, 12)}… · peer evidence{" "}
          {panel.peer_empirical_evidence_complete ? "complete" : "incomplete"} · wet-lab qualified
          plex: not asserted
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {panel.panel.map((row) => (
            <div key={row.target} className="rounded-md border border-border/60 p-2">
              <p className="font-medium">{row.target}</p>
              <p className="font-mono text-xs break-all">
                F {row.forward_primer}
                <br />R {row.reverse_primer}
              </p>
              <p className="text-muted-foreground">
                {row.empirical_evidence_ref || "Empirical evidence not supplied"}
              </p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function RestrictionWorkflow({
  workflow,
}: {
  workflow: NonNullable<DesignResult["restriction_workflow"]>;
}) {
  const stages = [workflow.digest, workflow.dephosphorylation, workflow.ligation];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Source-conditioned digest / ligation workflow
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        <p className="text-muted-foreground">
          Bench-planning evidence only; primer-ranking impact: none.
        </p>
        {stages.map((stage) => (
          <div key={stage.id} className="rounded-md border border-border/60 p-3">
            <p className="font-medium">{stage.name}</p>
            <dl className="mt-2 grid gap-x-4 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(stage.values).map(([key, value]) => (
                <Fact key={key} label={key.replaceAll("_", " ")} value={String(value)} />
              ))}
            </dl>
            {stage.unresolved.length ? (
              <ul className="mt-2 list-disc pl-5 text-warning">
                {stage.unresolved.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
        <ul className="list-disc pl-5 text-muted-foreground">
          {workflow.controls.required_measured_controls.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function ColonyContext({ context }: { context: NonNullable<DesignResult["colony_context"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Colony-screen provenance</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs leading-relaxed">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          <Fact label="Host class" value={context.host_class} />
          <Fact label="Preparation" value={context.preparation} />
          <Fact label="Interpretation" value={context.interpretation_status} />
        </dl>
        <p>
          <span className="font-medium text-foreground">Protocol/SOP:</span> {context.protocol_name}
        </p>
        <p>
          <span className="font-medium text-foreground">SOP provenance:</span>{" "}
          {context.protocol_provenance}
        </p>
        <p className="text-muted-foreground">
          PCRStudio inferred neither lysis timing nor colony/sample amount. Cycling authority:{" "}
          {context.cycling_authority}.
        </p>
        <p className="text-muted-foreground">Source recovery: {context.source_recovery_status}.</p>
        <p className="text-muted-foreground">{context.note}</p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          {context.required_observations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function BackboneScreen({ screen }: { screen: NonNullable<DesignResult["backbone"]> }) {
  const note = screen.partner?.note || screen.product?.note || screen.why_nothing;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Vector backbone screen</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {note ? <p className="text-xs leading-relaxed text-muted-foreground">{note}</p> : null}
      </CardContent>
    </Card>
  );
}

function Fact({
  label,
  value,
  small = false,
}: {
  label: string;
  value: string | undefined;
  small?: boolean;
}) {
  return (
    <div className="space-y-0.5">
      <dt className={cn("text-muted-foreground", small ? "text-xs" : "text-xs")}>{label}</dt>
      <dd className={cn("font-medium", small ? "text-xs" : "text-sm tabular-nums")}>
        {value || "—"}
      </dd>
    </div>
  );
}

function Checked({
  done,
  done_text,
  missing_text,
}: {
  done: boolean;
  done_text: string;
  missing_text: string;
}) {
  return (
    <li className="flex gap-2 text-xs leading-relaxed">
      {done ? (
        <Check className="mt-0.5 size-3.5 shrink-0 text-success" />
      ) : (
        <span className="mt-0.5 size-3.5 shrink-0 text-center font-mono text-muted-foreground">
          —
        </span>
      )}
      <span className={done ? "text-foreground" : "text-muted-foreground"}>
        {done ? done_text : missing_text}
      </span>
    </li>
  );
}
