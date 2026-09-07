"use client";

/**
 * What a loop-mediated design produced.
 *
 * A LAMP set is a shape before it is a list of oligos, so the shape is what this
 * view leads with: six required regions plus any selected LF/LB loop-primer
 * sites in fixed template order, drawn to scale, with the two composite primers
 * shown as the pairs of regions they are actually made of.
 *
 * Two numbers here would mislead if they were shown the way every other engine
 * shows them.
 *
 * FIP and BIP whole-oligo melting values describe a molecule that does not
 * exist on the original template because half of each composite oligo is a
 * 5′ tail. The template-binding half is therefore the sequence used for
 * screening. The current worker reports a separate ordered-oligo structure
 * diagnostic temperature; it is not presented as a bench hold unless a named
 * LAMP kit/protocol independently supplies that hold.
 *
 * And the parameter set is stated rather than assumed. Leaving it unselected
 * uses PrimerExplorer V5 Automatic Judgment from whole-target GC; an explicit
 * Normal/AT-rich/GC-rich choice is reported as an override.
 */

import { RuntimeProvenance } from "./result-primitives";
import { ScanFindings } from "@/components/design/scan";
import { OrderActions } from "./order-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count } from "@/lib/numbers";
import type { LoopSetEntry, LoopSetResult } from "@/lib/api/types";
import { WorkflowEvidenceCard } from "./workflow-evidence";
import { ModifiedOligosContext } from "./result-context-cards";

/** A colour per region class, so the map and the oligos agree at a glance. */
const REGION_FILL: Record<string, string> = {
  F3: "bg-muted-foreground/40",
  F2: "bg-primary/45",
  LF: "bg-chart-3/45",
  F1: "bg-chart-4/45",
  B1c: "bg-chart-4/45",
  LB: "bg-chart-3/45",
  B2c: "bg-primary/45",
  B3c: "bg-muted-foreground/40",
};

export function LoopSetResultView({ result }: { result: LoopSetResult }) {
  if (result.sets.length === 0) {
    return (
      <div className="space-y-5">
        <TheParameterSet result={result} />
        <ReadoutBoundary result={result} />
        <LampScenario result={result} />
        <SearchBoundary result={result} />
        {result.protocol ? <KitProtocol result={result} /> : null}
        {result.modified_oligos ? <ModifiedOligosContext context={result.modified_oligos} /> : null}
        <WorkflowEvidenceCard evidence={result.workflow_evidence} />
        <Card>
          <CardHeader>
            <CardTitle className="text-[13px] font-medium">No set here</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs leading-relaxed text-muted-foreground">{result.why_nothing}</p>
            {/* Six roles have to be filled and then fitted together, so
                "nothing" can mean six different things. */}
            <dl className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
              {Object.entries(result.considered).map(([stage, howMany]) => (
                <div key={stage}>
                  <dt className="text-muted-foreground">{stage.replace(/_/g, " ")}</dt>
                  <dd className="tabular-nums">{count(howMany)}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
        <RuntimeProvenance provenance={result.provenance} />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <TheParameterSet result={result} />
      <ReadoutBoundary result={result} />
      <LampScenario result={result} />
      <SearchBoundary result={result} />
      {result.protocol ? <KitProtocol result={result} /> : null}
      {result.sets.map((entry, index) => (
        <SetCard
          key={entry.at}
          entry={entry}
          index={index + 1}
          diagnosticTemperature={result.reaction.diagnostic_structure_temperature_c}
          templateOnlySpecificity={result.background?.template_only ?? false}
        />
      ))}
      <OrderSheet result={result} />
      {result.modified_oligos ? <ModifiedOligosContext context={result.modified_oligos} /> : null}
      <WorkflowEvidenceCard evidence={result.workflow_evidence} />
      <RuntimeProvenance provenance={result.provenance} />
    </div>
  );
}

function ReadoutBoundary({ result }: { result: LoopSetResult }) {
  const readout = result.readout;
  if (!readout) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Readout / detection boundary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-xs">
        <p className="font-medium">{readout.selection}</p>
        <p className="leading-relaxed text-muted-foreground">{readout.note}</p>
        <p className="text-xs text-muted-foreground">
          Sequence-selection impact: {readout.sequence_decision_impact}. Empirical positivity
          thresholds and instrument/channel validation remain external evidence.
        </p>
      </CardContent>
    </Card>
  );
}

function LampScenario({ result }: { result: LoopSetResult }) {
  const scenario = result.lamp_scenario;
  if (!scenario) return null;
  const optimization = Object.entries(scenario.bench_optimization?.values ?? {});
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">LAMP assay scenario</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-xs leading-relaxed text-muted-foreground">
        <p>
          <span className="font-medium text-foreground">Specimen:</span> {scenario.sample.matrix} ·{" "}
          {scenario.sample.preparation}
          {scenario.sample.direct ? " · direct" : ""}
        </p>
        <p>
          <span className="font-medium text-foreground">Formulation:</span>{" "}
          {scenario.formulation.selection}
        </p>
        <p>
          <span className="font-medium text-foreground">Readout chemistry:</span>{" "}
          {scenario.readout_chemistry.selected} · {scenario.readout_chemistry.branch}
        </p>
        <p>
          <span className="font-medium text-foreground">Confirmation:</span>{" "}
          {scenario.confirmation.selection}
        </p>
        <p>
          <span className="font-medium text-foreground">Topology / intent / loop policy:</span>{" "}
          {scenario.detection_topology.selection} · {scenario.design_intent.selection} ·{" "}
          {scenario.loop_policy.selection}
        </p>
        {scenario.detection_topology.multiplex_plan ? (
          <div className="rounded-md border border-border/60 p-2">
            <p className="font-medium text-foreground">Multiplex LAMP external/empirical plan</p>
            <p>
              {scenario.detection_topology.multiplex_plan.target_count} targets · panel{" "}
              {scenario.detection_topology.multiplex_plan.panel_sha256.slice(0, 12)}… · automatic
              modified-oligo design: no · wet-lab qualified plex: not asserted
            </p>
            <ul className="mt-1 list-disc pl-4">
              {scenario.detection_topology.multiplex_plan.panel.map((row) => (
                <li key={row.target}>
                  {row.target}: {row.method} · {row.reporter}/{row.channel} · evidence{" "}
                  {row.empirical_evidence_ref}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {optimization.length ? (
          <p>
            <span className="font-medium text-foreground">Bench overrides:</span>{" "}
            {optimization.map(([k, v]) => `${k}=${v}`).join(" · ")} · sequence impact: none
          </p>
        ) : null}
        <p className="text-xs">
          Sample, formulation, chemistry and validation provenance do not silently change sequence
          ranking. Only an explicit conservation-aware design intent can make the supplied target
          panel participate in candidate selection.
        </p>
      </CardContent>
    </Card>
  );
}

function KitProtocol({ result }: { result: LoopSetResult }) {
  const { protocol } = result;
  if (!protocol) return null;
  const holdTemperature =
    protocol.hold_temperature_c != null
      ? `${protocol.hold_temperature_c} °C`
      : protocol.hold_temperature_range_c
        ? `${protocol.hold_temperature_range_c[0]}–${protocol.hold_temperature_range_c[1]} °C`
        : "temperature not resolved";
  const holdTime =
    protocol.hold_time_min != null
      ? `${protocol.hold_time_min} min`
      : protocol.hold_time_range_min
        ? `${protocol.hold_time_range_min[0]}–${protocol.hold_time_range_min[1]} min`
        : "time not resolved";
  const concentrations = protocol.primer_concentrations_uM;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">LAMP protocol overlay</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs font-medium">
          {protocol.selection}
          {protocol.reaction_volume_uL != null ? ` · ${protocol.reaction_volume_uL} µL` : ""} ·{" "}
          {holdTemperature} / {holdTime}
        </p>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {protocol.vendor ? <span>Vendor: {protocol.vendor}</span> : null}
          <span>Catalogue: {protocol.kit_id}</span>
          {protocol.source_revision ? (
            <span>Source revision: {protocol.source_revision}</span>
          ) : null}
          {protocol.source_reviewed_date ? (
            <span>Reviewed: {protocol.source_reviewed_date}</span>
          ) : null}
          {protocol.lifecycle ? <span>Lifecycle: {protocol.lifecycle}</span> : null}
          {protocol.source_url ? (
            <a
              className="underline underline-offset-2 hover:text-foreground"
              href={protocol.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Official source
            </a>
          ) : null}
        </div>
        {protocol.source_identity ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Authority: {protocol.source_identity}
          </p>
        ) : null}
        {protocol.numeric_authority_status ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Numeric authority: {protocol.numeric_authority_status}
          </p>
        ) : null}
        {concentrations ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            FIP/BIP {concentrations.FIP} µM · F3/B3 {concentrations.F3} µM · Loop F/B{" "}
            {concentrations.LoopF} µM. {protocol.post_inactivation ?? ""}
          </p>
        ) : (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Primer concentrations are not asserted in this registry entry; follow the cited current
            protocol authority.
          </p>
        )}
        {protocol.carryover_prevention ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Carry-over: {protocol.carryover_prevention.included ? "built in" : "not built in"} ·{" "}
            {protocol.carryover_prevention.chemistry}. {protocol.carryover_prevention.note}
          </p>
        ) : null}
        {protocol.readout_compatibility ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Readout review: {protocol.readout_compatibility.status}.{" "}
            {protocol.readout_compatibility.note}
          </p>
        ) : null}
        {protocol.readout_notes?.map((note) => (
          <p key={note} className="text-xs leading-relaxed text-muted-foreground">
            {note}
          </p>
        ))}
        {protocol.sample_compatibility_notes?.map((note) => (
          <p key={note} className="text-xs leading-relaxed text-muted-foreground">
            Sample note: {note}
          </p>
        ))}
        {protocol.oligo_manufacturing_guidance ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Oligo manufacturing: {protocol.oligo_manufacturing_guidance}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function boundedRange(values: (number | null)[], unit: string): string {
  if (values.length !== 2) return "not resolved";
  const [low, high] = values;
  if (low == null && high == null) return "open source envelope";
  if (low == null) return `≤${high} ${unit}`;
  if (high == null) return `≥${low} ${unit}`;
  return `${low}–${high} ${unit}`;
}

/** Which of the three windows was in force, and where that came from. */
function SearchBoundary({ result }: { result: LoopSetResult }) {
  const search = result.search;
  if (!search || search.complete) return null;
  const capped = [
    search.forward_halves_capped ? "forward halves" : null,
    search.backward_halves_capped ? "backward halves" : null,
    search.join_evaluation_capped ? "core-pair evaluation" : null,
    search.core_pair_outer_expansion_capped ? "core-to-outer expansion pool" : null,
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Bounded search</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-xs leading-relaxed text-muted-foreground">
        <p>{search.claim}.</p>
        {search.orientation_note ? <p>{search.orientation_note}</p> : null}
        <p>
          Truncated stage{capped.includes(",") ? "s" : ""}: {capped || "reported search budget"}.
        </p>
        <p>
          {count(search.join_evaluations)} whole-set combinations were evaluated; this is a
          computational limit, not a LAMP validity criterion.
        </p>
        {search.core_pair_evaluations != null ? (
          <p>
            Core-pair work: {count(search.core_pair_evaluations)} evaluated
            {search.feasible_core_partners_after_local_sampling != null
              ? ` of ${count(search.feasible_core_partners_after_local_sampling)} locally retained feasible partners`
              : ""}
            .{" "}
            {search.core_pair_budget_allocation === "round-robin-across-feasible-forward-halves"
              ? "The global budget is allocated round-robin across feasible forward halves so early target coordinates cannot consume it first."
              : ""}
          </p>
        ) : null}
        {search.core_pairs_outer_expanded != null ? (
          <p>
            Outer expansion was attempted for {count(search.core_pairs_outer_expanded)} core pairs
            {search.core_pairs_outer_expansion_limit != null
              ? ` (pool limit ${count(search.core_pairs_outer_expansion_limit)})`
              : ""}
            ; candidates outside this pool were not expanded into F3×B3 combinations.
          </p>
        ) : null}
        {search.backward_partner_sampling_used ||
        search.core_pair_outer_expansion_capped ||
        search.outer_candidate_truncation_used ||
        search.risk_ranking_capped ? (
          <p>
            Additional bounded stages were active:{" "}
            {[
              search.backward_partner_sampling_used ? "backward-partner sampling" : null,
              search.core_pair_outer_expansion_capped ? "core-pair outer-expansion pool" : null,
              search.outer_candidate_truncation_used ? "outer-primer shortlist" : null,
              search.risk_ranking_capped ? "expensive interaction shortlist" : null,
            ]
              .filter(Boolean)
              .join(", ")}
            .
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TheParameterSet({ result }: { result: LoopSetResult }) {
  const chosen = result.parameter_set;
  const diagnosticTemperature = result.reaction.diagnostic_structure_temperature_c;
  const historicalTemperature = result.reaction.screening_temperature_c ?? result.reaction.hold;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          LAMP design model — {chosen.name}
          {chosen.overruled.length > 0 ? (
            <span className="ml-2 font-normal text-warning">· adjusted</span>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
          <Fact
            label="Role/Tm model"
            value={chosen.thermodynamic_model?.id ?? "not recorded in historical result"}
          />
          <Fact
            label="Geometry profile"
            value={chosen.geometry_profile?.name ?? "historical V5-compatible geometry"}
          />
          <Fact
            label="FIP/BIP junction"
            value={chosen.inner_linker?.sequence ?? "no synthetic linker"}
          />
          <Fact
            label="Structure-diagnostic temperature"
            value={
              diagnosticTemperature == null
                ? "not recorded in historical result"
                : `${diagnosticTemperature} °C`
            }
          />
          <Fact label="Outer (F2, F3, B2, B3)" value={boundedRange(chosen.outer.tm, "°C")} />
          <Fact label="Stems (F1c, B1c)" value={boundedRange(chosen.inner.tm, "°C")} />
          <Fact label="Loops (LF, LB)" value={boundedRange(chosen.loop.tm, "°C")} />
          {chosen.terminal_stability ? (
            <>
              <Fact
                label={`Core critical-end ΔG (${chosen.terminal_stability.window_bases} nt)`}
                value={`≤ ${chosen.terminal_stability.regular_critical_max_dg_kcal_mol} kcal/mol`}
              />
              <Fact
                label={`Loop 3′-end ΔG (${chosen.terminal_stability.window_bases} nt)`}
                value={`≤ ${chosen.terminal_stability.loop_3p_max_dg_kcal_mol} kcal/mol`}
              />
            </>
          ) : null}
          {chosen.f2_b2_span.length === 2 ? (
            <Fact
              label="F2–B2 amplified region"
              value={`${chosen.f2_b2_span[0]}–${chosen.f2_b2_span[1]} bases`}
            />
          ) : null}
          {chosen.loop_span.length === 2 ? (
            <Fact label="Loop span" value={`${chosen.loop_span[0]}–${chosen.loop_span[1]} bases`} />
          ) : null}
          {chosen.outer_gap.length === 2 ? (
            <Fact
              label="F2–F3 / B2–B3 gap"
              value={`${chosen.outer_gap[0]}–${chosen.outer_gap[1]} bases`}
            />
          ) : null}
          {chosen.middle_gap.length === 2 ? (
            <Fact
              label="F1c–B1c gap"
              value={`${chosen.middle_gap[0]}–${chosen.middle_gap[1]} bases`}
            />
          ) : null}
        </dl>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Chosen from {chosen.chosen_from}. {chosen.why}
        </p>
        {chosen.geometry_profile ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {chosen.geometry_profile.claim}
          </p>
        ) : null}
        {chosen.inner_linker ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Junction: {chosen.inner_linker.claim}
          </p>
        ) : null}
        {result.reaction.context_note ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {result.reaction.context_note}
          </p>
        ) : result.reaction.note ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Historical reaction note: {result.reaction.note}
          </p>
        ) : null}
        {diagnosticTemperature == null && historicalTemperature != null ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Historical saved temperature field: {historicalTemperature} °C. Its original semantic
            role predates the current split between PrimerExplorer design authority, structure
            diagnostics, and named-kit bench hold, so PCRStudio does not silently reinterpret it as
            any of those.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** One set: the map first, then its four core oligos plus optional LF/LB. */
function SetCard({
  entry,
  index,
  diagnosticTemperature,
  templateOnlySpecificity,
}: {
  entry: LoopSetEntry;
  index: number;
  diagnosticTemperature?: number;
  templateOnlySpecificity: boolean;
}) {
  const evidencePenalties = entry.evidence_rank
    ? [
        entry.evidence_rank.preferred_f2_b2_span !== null
          ? `F2–B2 ${entry.evidence_rank.preferred_f2_b2_distance_penalty}`
          : null,
        entry.evidence_rank.preferred_outer_gap !== null
          ? `outer gap ${entry.evidence_rank.preferred_outer_gap_penalty}`
          : null,
        entry.evidence_rank.preferred_loop_tm !== null
          ? `loop Tm ${entry.evidence_rank.preferred_loop_tm_penalty}`
          : null,
      ].filter((value): value is string => value !== null)
    : [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-baseline justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          Set {index} — {entry.size} bp
        </CardTitle>
        <span className="text-xs text-muted-foreground">
          {entry.loop_primers}/2 loop primers · {entry.spread} °C spread
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* The six required regions plus any selected LF/LB sites, to scale.
            Their order along the template is the design; a set whose regions were
            out of order would not be one. */}
        <div aria-hidden="true" className="space-y-1.5">
          <div className="relative h-6 rounded bg-muted">
            {entry.regions.map((region) => (
              <div
                key={region.name}
                className={`absolute inset-y-0 rounded-sm ${
                  REGION_FILL[region.name] ?? "bg-primary/30"
                }`}
                style={{
                  left: `${((region.at - entry.at) / Math.max(entry.size, 1)) * 100}%`,
                  width: `${(region.length / Math.max(entry.size, 1)) * 100}%`,
                }}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {entry.regions.map((region) => (
              <span key={region.name} className="flex items-center gap-1">
                <span
                  className={`size-2 rounded-sm ${REGION_FILL[region.name] ?? "bg-primary/30"}`}
                />
                {region.name}
              </span>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          {entry.oligos.map((oligo) => (
            <div
              key={oligo.name}
              className={
                oligo.composite
                  ? "rounded-md border border-primary/30 bg-primary/5 p-2.5"
                  : "rounded-md border p-2.5"
              }
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <span className="text-xs font-medium">
                  {oligo.name}
                  <span className="ml-2 font-normal text-muted-foreground">
                    {oligo.built_from.join(" + ")}
                  </span>
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {oligo.length} nt
                  {oligo.anneals ? ` · binds at ${oligo.anneals.tm} °C` : ` · ${oligo.tm} °C`}
                </span>
              </div>

              <p className="mt-1 font-mono text-xs break-all">
                {oligo.anneals ? (
                  <>
                    <span className="rounded-l bg-chart-3/30 px-0.5 py-0.5">
                      {oligo.sequence.slice(
                        0,
                        oligo.sequence.length - oligo.anneals.sequence.length,
                      )}
                    </span>
                    <span className="rounded-r bg-primary/25 px-0.5 py-0.5">
                      {oligo.anneals.sequence}
                    </span>
                  </>
                ) : (
                  oligo.sequence
                )}
              </p>

              {/* Said only for the composites, because only there does the
                  whole-molecule figure describe something that does not exist
                  yet — near 80 °C against a hold near 65. */}
              {oligo.anneals ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  Whole oligo {oligo.tm} °C, which is not a cycler setting.
                  {diagnosticTemperature == null
                    ? " Current structure-diagnostic temperature was not recorded in this historical result."
                    : ` Ordered-oligo structure diagnostics use ${diagnosticTemperature} °C; this is not a bench hold.`}{" "}
                  {oligo.anneals.note}
                </p>
              ) : null}

              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{oligo.note}</p>
            </div>
          ))}
        </div>

        <p className="text-xs leading-relaxed text-muted-foreground">{entry.note}</p>

        {/*
         * Where else these oligos sit. Rendered from the same component every
         * other engine uses, so the same finding is not described two ways.
         * `intended` is how many sites this design is *meant* to have on its
         * own template, so anything past that is a second place.
         */}
        {entry.off_targets.checked ? (
          <ScanFindings
            off={entry.off_targets}
            intended={templateOnlySpecificity ? 4 + (entry.loop_primers ?? 0) : 0}
          />
        ) : entry.off_targets.note ? (
          <p className="rounded-md border border-dashed p-2.5 text-xs leading-relaxed text-muted-foreground">
            Generic direct specificity: {entry.off_targets.classification ?? "not checked"}.{" "}
            {entry.off_targets.note}
          </p>
        ) : null}

        {entry.lamp_background_topology ? (
          <div className="rounded-md border p-2.5">
            <p className="text-xs font-medium">Six-region LAMP background topology</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {entry.lamp_background_topology.classification} · risk class{" "}
              {entry.lamp_background_topology.risk_class}.
              {String((entry.lamp_background_topology as { claim?: unknown }).claim ?? "")
                ? ` ${String((entry.lamp_background_topology as { claim?: unknown }).claim)}`
                : ""}
            </p>
          </div>
        ) : null}

        {entry.rna_target_accessibility ? (
          <div className="rounded-md border p-2.5">
            <p className="text-xs font-medium">RT-LAMP RNA accessibility · optional diagnostic</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {entry.rna_target_accessibility.checked
                ? `${entry.rna_target_accessibility.parameter_authority ?? entry.rna_target_accessibility.model ?? "ViennaRNA RNA model"}${entry.rna_target_accessibility.celsius != null ? ` at ${entry.rna_target_accessibility.celsius} °C` : ""}.`
                : "RNA accessibility was not computed in this environment."}{" "}
              {entry.rna_target_accessibility.note} Sequence-decision impact:{" "}
              {entry.rna_target_accessibility.decision_impact}.
            </p>
            {entry.rna_target_accessibility.openings &&
            Object.keys(entry.rna_target_accessibility.openings).length ? (
              <div className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                {Object.entries(entry.rna_target_accessibility.openings).map(([name, opening]) => (
                  <p key={name}>
                    {name}: P(all {opening.length} nt unpaired) = {opening.unpaired.toPrecision(3)}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {entry.evidence_rank ? (
          <div className="rounded-md border p-2.5">
            <p className="text-xs font-medium">Evidence-weighted ranking diagnostics</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Profile {entry.evidence_rank.geometry_profile}. Active soft penalties:{" "}
              {evidencePenalties.length ? evidencePenalties.join(", ") : "none"}. These values rank
              source-valid sets; a source reference whose thermodynamic model is not aligned stays
              inactive rather than being projected onto a different Tm scale.
            </p>
          </div>
        ) : null}

        {entry.sequence_interaction_risk ? (
          <div className="rounded-md border p-2.5">
            <p className="text-xs font-medium">3′-extendability risk diagnostic</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Maximum exact complementary run: {entry.sequence_interaction_risk.all_max_bases}{" "}
              bases; {entry.sequence_interaction_risk.all_review_events} review event(s) at or above{" "}
              {entry.sequence_interaction_risk.review_at_or_above_bases} bases.{" "}
              {entry.sequence_interaction_risk.note}
            </p>
          </div>
        ) : null}

        {entry.terminal_gc ? (
          <div className="rounded-md border p-2.5">
            <p className="text-xs font-medium">Terminal-GC evidence</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {Object.entries(entry.terminal_gc)
                .map(
                  ([name, value]) =>
                    `${name}: ${value.gc_in_last_6}/6 GC, 3′ run ${value.three_prime_gc_run}${value.review ? " (review)" : ""}`,
                )
                .join(" · ")}
            </p>
          </div>
        ) : null}

        {entry.interactions ? (
          <div className="rounded-md border p-2.5">
            <p className="text-xs font-medium">Ordered-oligo interaction diagnostic</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {entry.interactions.note}
            </p>
            {entry.interactions.worst.length > 0 ? (
              <div className="mt-2 space-y-1 text-xs text-muted-foreground tabular-nums">
                {entry.interactions.worst.slice(0, 4).map((one) => (
                  <p key={`${one.a}-${one.b}`}>
                    {one.a} ↔ {one.b}: ΔG {one.dg} kcal/mol · Tm {one.tm} °C
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function OrderSheet({ result }: { result: LoopSetResult }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          What to order — {result.order_sheet.length} oligos
        </CardTitle>
        <OrderActions lines={result.order_sheet} kind="lamp-set" conditions={result.reaction} />
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
            {line.note ? <p className="mt-1 text-xs text-muted-foreground">{line.note}</p> : null}
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
