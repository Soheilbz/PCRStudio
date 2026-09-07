"use client";

/**
 * What a set of pairs meant to share one tube looks like.
 *
 * The thing that makes this different from several designs shown together is
 * that no pair here was chosen on its own merits. Each was chosen for how the
 * whole tube behaves, and a pair that would rank first alone can be left out
 * because it fights something else in the set. So the reasoning is shown: how
 * the set was arrived at, what interacts with what, and which products a
 * reader could not tell apart.
 *
 * Nothing here passes or fails. There is no published line between an
 * acceptable multiplex and an unacceptable one, so the badness is a number to
 * compare sets by and the judgement stays with the person reading it.
 */

import { OrderActions } from "./order-actions";
import { ToolchainStatus } from "./toolchain-status";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count } from "@/lib/numbers";
import type { MultiplexResult, Tube } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function MultiplexResultView({ result }: { result: MultiplexResult }) {
  return (
    <div className="space-y-5">
      <TheRequest result={result} />
      <ToolchainStatus result={result} />
      {result.tubes.map((tube) => (
        <TubeCard
          key={tube.tube}
          tube={tube}
          orderLines={result.order_sheet.filter((line) => line.pool === tube.tube - 1)}
          only={result.tubes.length === 1}
          crowdedAbove={result.crowded_above}
        />
      ))}
      {result.panel_cross_product_specificity.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">
              Cross-target product specificity
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            {result.panel_cross_product_specificity.map((row, index) => (
              <p key={index} className="text-xs leading-relaxed text-muted-foreground">
                {String(row.tube_id ?? `tube-${String(row.tube ?? index + 1)}`)} · scope{" "}
                {String(row.scope ?? "unresolved")} · unintended products{" "}
                {String(row.unintended_product_count ?? "unresolved")}. Every selected extending
                primer is scanned with every other selected primer, so Fᵢ×Rⱼ products are visible;
                per-target database specificity remains separate.
              </p>
            ))}
          </CardContent>
        </Card>
      ) : null}
      <p className="text-xs leading-relaxed text-muted-foreground">{result.note}</p>
    </div>
  );
}

function TheRequest({ result }: { result: MultiplexResult }) {
  const readable: Record<string, string> = {
    agarose: "a gel",
    capillary: "a capillary instrument",
    ngs: "sequencing",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          {result.targets.length} targets, read on {readable[result.readout] ?? result.readout}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <ul className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
          {result.targets.map((target) => (
            <li key={target.name} className="flex justify-between gap-3">
              <span className="text-foreground">{target.name}</span>
              <span className="text-muted-foreground tabular-nums">
                {target.candidates} candidate{target.candidates === 1 ? "" : "s"}
              </span>
            </li>
          ))}
        </ul>
        <p className="text-xs leading-relaxed text-muted-foreground">
          A target with few candidates constrains the set far more than one with many, so those are
          placed first — placing them last means placing them into whatever is left.
        </p>
        {result.readout_profile ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Readout reference: {result.readout_profile}. Size-spacing is a supplier-reference risk
            screen, not an observed-resolution guarantee.
          </p>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">
          Panel identity: {result.panel_identity.panel_sha256.slice(0, 12)}… · formulation{" "}
          {result.panel_identity.formulation_sha256.slice(0, 12)}…. Sequence/tube identity and
          empirical concentration/evidence formulation are hashed separately so bench balancing
          never masquerades as a sequence-design change.
        </p>
        {result.targets.some(
          (target) => target.primer_concentration_nm != null || target.empirical_evidence_ref,
        ) ? (
          <div className="space-y-1 rounded-lg border border-border/60 bg-surface-wash/30 p-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Empirical formulation metadata</p>
            {result.targets.map((target) =>
              target.primer_concentration_nm != null || target.empirical_evidence_ref ? (
                <p key={`${target.name}-formulation`}>
                  <span className="font-medium text-foreground">{target.name}:</span>
                  {target.primer_concentration_nm != null
                    ? ` ${target.primer_concentration_nm} nM primer`
                    : " concentration not recorded"}
                  {target.empirical_evidence_ref
                    ? ` · evidence ${target.empirical_evidence_ref}`
                    : " · no empirical balancing reference"}
                </p>
              ) : null,
            )}
            <p>
              These fields document planned/measured formulation only and have no sequence-ranking
              impact.
            </p>
          </div>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">
          Constraint provenance:{" "}
          {result.constraint_scope === "shared"
            ? "all targets resolved to the same design-constraint envelope"
            : "target-specific constraint envelopes were preserved per target; no single shared constraint block is claimed"}
          .
        </p>
        {result.constraint_scope === "per-target" ? (
          <div className="space-y-1 rounded-lg border border-border/60 bg-surface-wash/30 p-3 text-xs leading-relaxed text-muted-foreground">
            <p className="font-medium text-foreground">Per-target design constraints</p>
            {result.targets.map((target) => (
              <p key={`${target.name}-constraints`}>
                <span className="font-medium text-foreground">{target.name}:</span>{" "}
                {Object.entries(target.constraints)
                  .map(([key, value]) => `${key}=${String(value)}`)
                  .join(" · ") || "no target-specific numeric overrides"}
              </p>
            ))}
          </div>
        ) : null}
        {result.selection_method ? (
          <>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Selection: {result.selection_method.optimizer}; objective{" "}
              {result.selection_method.objective}.{" "}
              {result.selection_method.candidate_pool_optimum_claimed
                ? "Exact optimum within the evaluated candidate pools; no claim is made outside those pools."
                : "Approximate/local evaluated-search result only; no candidate-pool or global optimum is claimed."}
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Tube assignment: {result.selection_method.tube_assignment.strategy};{" "}
              {result.selection_method.tube_assignment.note}{" "}
              {result.selection_method.tube_assignment.global_partition_optimized
                ? "The tube partition was globally optimized."
                : "No global tube-partition optimum is claimed."}
            </p>
          </>
        ) : null}
        {result.assay?.profile_authority ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Canonical profile authority: {result.assay.profile_authority.profileId} ·{" "}
            {result.assay.profile_authority.source} · {result.assay.profile_authority.transport}.
          </p>
        ) : null}
        {result.protocol ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Shared named protocol: {result.protocol.selection}. Every target in this multiplex was
            required to resolve to this same chemistry overlay.
          </p>
        ) : null}
        {result.reverse_transcription ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Shared RT authority: {result.reverse_transcription.authority_status ?? "unresolved"}
            {result.reverse_transcription.before === "concurrent-with-rpa"
              ? " · concurrent with RPA"
              : result.reverse_transcription.before
                ? ` · before ${result.reverse_transcription.before.replaceAll("-", " ")}`
                : " · placement unresolved"}
            .
          </p>
        ) : null}
        {result.colony_context ? (
          <div className="rounded-lg border border-border/60 bg-surface-wash/30 p-3 text-xs leading-relaxed text-muted-foreground">
            <p className="font-medium text-foreground">Shared colony-PCR provenance</p>
            <p>
              Host: {result.colony_context.host_class} · preparation:{" "}
              {result.colony_context.preparation}
            </p>
            <p>Named SOP: {result.colony_context.protocol_name}</p>
            <p>SOP provenance: {result.colony_context.protocol_provenance}</p>
            <p>{result.colony_context.note}</p>
          </div>
        ) : null}
        {result.targets.some((target) => target.background || target.inclusivity) ? (
          <div className="space-y-2 rounded-lg border border-border/60 bg-surface-wash/30 p-3">
            <p className="text-xs font-medium text-foreground">Assay-specific target evidence</p>
            {result.targets.map((target) =>
              target.background || target.inclusivity ? (
                <div
                  key={`${target.name}-evidence`}
                  className="text-xs leading-relaxed text-muted-foreground"
                >
                  <p className="font-medium text-foreground">{target.name}</p>
                  {target.inclusivity ? (
                    <>
                      <p>
                        Inclusivity: {target.inclusivity.contigs} target record(s),{" "}
                        {target.inclusivity.bases.toLocaleString()} bases,{" "}
                        {target.inclusivity.pairs_rejected}/{target.inclusivity.pairs_checked}{" "}
                        candidate pair(s) rejected. {target.inclusivity.note}
                      </p>
                      {target.inclusivity.panel_provenance ? (
                        <p>Inclusivity panel provenance: {target.inclusivity.panel_provenance}</p>
                      ) : null}
                      {target.inclusivity.panel_selection_rationale ? (
                        <p>
                          Panel-selection rationale: {target.inclusivity.panel_selection_rationale}
                        </p>
                      ) : null}
                    </>
                  ) : null}
                  {target.background ? (
                    <>
                      <p>
                        Exclusion background:{" "}
                        {target.background.checked ? "checked" : "not checked"} across{" "}
                        {target.background.contigs} contig(s) /{" "}
                        {target.background.bases.toLocaleString()} bases. {target.background.note}
                      </p>
                      {target.background.panel_provenance ? (
                        <p>Exclusion-panel provenance: {target.background.panel_provenance}</p>
                      ) : null}
                    </>
                  ) : null}
                </div>
              ) : null,
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TubeCard({
  tube,
  orderLines,
  only,
  crowdedAbove,
}: {
  tube: Tube;
  orderLines: MultiplexResult["order_sheet"];
  only: boolean;
  crowdedAbove: number;
}) {
  const clashes = tube.separation.unresolvable;
  const acrossTargets = tube.worst_interactions.filter(
    (entry) => entry.a.slice(0, -2) !== entry.b.slice(0, -2),
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-[13px] font-medium">
          <span>
            {only ? "One tube" : `Tube ${tube.tube_id ?? tube.tube}`} — {tube.pairs.length} pair
            {tube.pairs.length === 1 ? "" : "s"}
          </span>
          <span className="text-xs font-normal text-muted-foreground tabular-nums">
            badness {count(tube.badness)}
          </span>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        {tube.crowded ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            More than {crowdedAbove} pairs in one reaction. Published panels go much further, but
            they are optimised at the bench rather than designed and used.
          </p>
        ) : null}

        <BandPicture tube={tube} />

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <caption className="sr-only">
              Multiplex target primer sequences and product sizes
            </caption>
            <thead>
              <tr className="text-left text-muted-foreground">
                <th scope="col" className="pr-3 pb-1 font-normal">
                  Target
                </th>
                <th scope="col" className="pr-3 pb-1 font-normal">
                  Forward
                </th>
                <th scope="col" className="pr-3 pb-1 font-normal">
                  Reverse
                </th>
                <th scope="col" className="pb-1 font-normal">
                  Product
                </th>
              </tr>
            </thead>
            <tbody>
              {tube.pairs.map((pair) => (
                <tr key={pair.target}>
                  <td className="py-0.5 pr-3 whitespace-nowrap">{pair.target}</td>
                  <td className="py-0.5 pr-3 font-mono">{pair.left}</td>
                  <td className="py-0.5 pr-3 font-mono">{pair.right}</td>
                  <td className="py-0.5 tabular-nums">{pair.product_size} bp</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <Separation tube={tube} clashes={clashes} />

        {acrossTargets.length > 0 ? (
          <details>
            <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
              What interacts with what
            </summary>
            <ul className="mt-2 space-y-1">
              {acrossTargets.slice(0, 6).map((entry) => (
                <li
                  key={`${entry.a}:${entry.b}`}
                  className="flex flex-wrap gap-x-3 text-xs text-muted-foreground"
                >
                  <span className="text-foreground">
                    {entry.a} + {entry.b}
                  </span>
                  <span className="tabular-nums">{count(entry.badness)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              Two oligos that pair at their 3′ ends cost far more here than the same duplex sitting
              in the middle of both, because extension starts at the 3′ end — that is the one that
              makes a primer dimer rather than noise.
            </p>
          </details>
        ) : null}

        <details>
          <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
            How this set was arrived at
          </summary>
          <ol className="mt-2 space-y-1">
            {tube.how_it_was_chosen.map((step, index) => (
              <li key={index} className="text-xs leading-relaxed text-muted-foreground">
                {step}
              </li>
            ))}
          </ol>
        </details>

        <OrderSheet tube={tube} lines={orderLines} />
      </CardContent>
    </Card>
  );
}

/**
 * The products laid out by size, which is what a gel shows.
 *
 * Products below the selected reference spacing are highlighted together as a
 * readout-resolution risk. This is not a prediction of the observed gel/trace:
 * actual resolution depends on the named cartridge or the gel/run conditions.
 */
function BandPicture({ tube }: { tube: Tube }) {
  const sizes = tube.pairs.map((pair) => pair.product_size);
  if (sizes.length === 0) return null;

  const largest = Math.max(...sizes, 1);
  const clashing = new Set(tube.separation.unresolvable.flatMap((clash) => [clash.a, clash.b]));

  return (
    <div className="space-y-1">
      <div className="relative h-9 rounded bg-muted" aria-hidden="true">
        {tube.pairs.map((pair) => (
          <div
            key={pair.target}
            className={cn(
              "absolute inset-y-1 w-0.5 rounded",
              clashing.has(pair.target) ? "bg-destructive" : "bg-primary",
            )}
            style={{ left: `${(pair.product_size / largest) * 96 + 2}%` }}
            title={`${pair.target}, ${pair.product_size} bp`}
          />
        ))}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
        <span>shorter</span>
        <span>{largest} bp</span>
      </div>
      <p className="sr-only">
        Products at{" "}
        {tube.pairs.map((pair) => `${pair.target} ${pair.product_size} bases`).join(", ")}.
      </p>
    </div>
  );
}

function Separation({
  tube,
  clashes,
}: {
  tube: Tube;
  clashes: Tube["separation"]["unresolvable"];
}) {
  return (
    <div className="space-y-1.5 border-t pt-2.5">
      <p className="text-xs leading-relaxed text-muted-foreground">{tube.separation.note}</p>
      {clashes.length > 0 ? (
        <ul className="space-y-1">
          {clashes.map((clash) => (
            <li key={`${clash.a}:${clash.b}`} className="text-xs">
              <span className="text-foreground">
                {clash.a} and {clash.b}
              </span>{" "}
              <span className="text-muted-foreground tabular-nums">
                — {clash.sizes[0]} and {clash.sizes[1]} bp, {clash.apart} apart; reference spacing{" "}
                {clash.needed} bp
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function OrderSheet({ tube, lines }: { tube: Tube; lines: MultiplexResult["order_sheet"] }) {
  return (
    <div className="flex items-center justify-between gap-3 border-t pt-2.5">
      <p className="text-xs leading-relaxed text-muted-foreground">
        {lines.length} oligos. This export uses the canonical worker order sheet for Tube{" "}
        {tube.tube}; PCRStudio does not infer primer concentrations or a balancing recipe from plex
        count. Use the selected multiplex chemistry/SOP and empirical panel optimisation for
        concentration and rebalance decisions.
      </p>
      <OrderActions lines={lines} kind={`multiplex-tube-${tube.tube}`} />
    </div>
  );
}
