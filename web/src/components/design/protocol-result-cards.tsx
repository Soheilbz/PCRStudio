"use client";

import { TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { flankingNumericLabel } from "@/lib/flanking-contract";
import type { DesignResult } from "@/lib/api/types";

export function FlankingNumericRecipeCard({ result }: { result: DesignResult }) {
  const recipe = result.flanking_numeric_recipe;
  if (!recipe) return null;
  return (
    <Card className="border-border/70">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Resolved numeric recipe · source-conditioned</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Exact-product bench planning. Numeric origins are preserved per value and this block has
          sequence-decision impact: none.
        </p>
        <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(recipe.values)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3 border-b border-border/40 py-1">
                <dt className="text-muted-foreground">{flankingNumericLabel(key)}</dt>
                <dd className="text-right font-medium">
                  {Number.isInteger(value) ? value : Number(value.toFixed(4))}
                  <span className="block text-xs font-normal text-muted-foreground">
                    {recipe.origins[key]}
                  </span>
                </dd>
              </div>
            ))}
        </dl>
        {recipe.unresolved_numeric_dependencies.length ? (
          <Alert className="border-warning/35 bg-warning/5 text-xs">
            <TriangleAlert aria-hidden="true" />
            <AlertTitle>Unresolved numeric dependencies</AlertTitle>
            <AlertDescription>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {recipe.unresolved_numeric_dependencies.map((item) => (
                  <li key={item.id}>{item.note}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function FlankingProtocol({ result }: { result: DesignResult }) {
  const protocol = result.protocol;
  if (!protocol) return null;

  const reactionVolume = (value: number | Record<string, number> | undefined) => {
    if (value == null) return "See named protocol";
    if (typeof value === "number") return `${value} µL`;
    return Object.entries(value)
      .map(([key, amount]) => `${key.replaceAll("_", " ")}: ${amount} µL`)
      .join(" · ");
  };

  if (protocol.kind === "standard-pcr") {
    const primerValues = Object.values(protocol.primer_final_concentration_uM ?? {});
    const primerRange = primerValues.length
      ? `${Math.min(...primerValues)}${Math.min(...primerValues) === Math.max(...primerValues) ? "" : `–${Math.max(...primerValues)}`} µM documented values`
      : "See named protocol";
    const properties = protocol.polymerase_properties ?? {};
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">Selected Standard-PCR chemistry</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed">
          <p className="font-medium text-foreground">{protocol.selection}</p>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Reaction / primer</dt>
              <dd>
                {reactionVolume(protocol.reaction_volume_uL)} · {primerRange}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Polymerase behavior</dt>
              <dd>
                proofreading {String(properties.proofreading ?? "not recorded")} · hot start{" "}
                {String(properties.hot_start ?? "not recorded")} · product end{" "}
                {String(properties.product_end ?? "not recorded")}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Design impact</dt>
              <dd>none · screening thermodynamics unchanged</dd>
            </div>
          </dl>
          {protocol.carryover_prevention ? (
            <div className="rounded-md border border-border/70 bg-surface-wash/35 p-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Carry-over / uracil branch</p>
              <p className="mt-1">
                dUTP support:{" "}
                {String(protocol.carryover_prevention.dUTP_supported ?? "not recorded")} · UDG built
                in: {String(protocol.carryover_prevention.UDG_built_in ?? "not recorded")} · enabled
                by polymerase selection alone:{" "}
                {String(
                  protocol.carryover_prevention.enabled_by_protocol_selection_alone ??
                    "not recorded",
                )}
                .
              </p>
              <p className="mt-1">
                {String(
                  protocol.carryover_prevention.note ??
                    "Follow the named protocol and record the actual dUTP/UDG state.",
                )}
              </p>
            </div>
          ) : null}
          {protocol.downstream_cloning ? (
            <div className="rounded-md border border-border/70 bg-surface-wash/35 p-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Downstream product-end handoff</p>
              <p className="mt-1">
                {String(
                  protocol.downstream_cloning.note ??
                    protocol.downstream_cloning.ta_cloning_direct ??
                    "Verify the actual product-end state and cloning workflow.",
                )}
              </p>
            </div>
          ) : null}
          {protocol.difficult_template ? (
            <p className="text-xs text-muted-foreground">
              Difficult-template guidance is protocol-specific; PCRStudio does not auto-select GC
              enhancer/DMSO/betaine from sequence GC alone.
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">{protocol.screening_context_note}</p>
          <p className="text-xs text-muted-foreground">{protocol.note}</p>
        </CardContent>
      </Card>
    );
  }

  if (protocol.kind === "rpa") {
    const mixing = protocol.agitation
      ? `agitate after ${protocol.agitation.after_minutes} min (${protocol.agitation.action})`
      : protocol.mixing
        ? `optional mixing ${protocol.mixing.optional_rpm} rpm (${protocol.mixing.effect})`
        : "follow the named mixing instruction";
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">Selected RPA chemistry</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed">
          <p className="font-medium text-foreground">{protocol.selection}</p>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Primer starting range</dt>
              <dd>
                rapid preference {protocol.primer_length_nt.rapid_preferred_min}–
                {protocol.primer_length_nt.rapid_preferred_max} nt; reviewed upper evidence boundary{" "}
                {protocol.primer_length_nt.reviewed_upper_nt} nt
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Isothermal hold</dt>
              <dd>
                {protocol.temperature_c} °C for {protocol.incubation_minutes} min · {mixing}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Primer concentration</dt>
              <dd>{protocol.primer_final_concentration_nM} nM each</dd>
            </div>
          </dl>
          {protocol.source_publication && protocol.source_revision ? (
            <p className="text-xs text-muted-foreground">
              Source: {protocol.source_publication} · {protocol.source_revision}
              {protocol.source_revision_date ? ` · ${protocol.source_revision_date}` : ""}
            </p>
          ) : null}
          {protocol.production_dna_warning ? (
            <div className="rounded-md border border-border/70 bg-surface-wash/35 p-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Production-DNA limitation</p>
              <p className="mt-1">
                {protocol.production_dna_warning.contaminant}. Supplier boundary:{" "}
                {protocol.production_dna_warning.supplier_boundary}. PCRStudio does not infer
                organism identity from the FASTA; {protocol.production_dna_warning.action}.
              </p>
            </div>
          ) : null}
          {protocol.contamination_control ? (
            <div className="rounded-md border border-border/70 bg-surface-wash/35 p-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Contamination-control handoff</p>
              <p className="mt-1">{protocol.contamination_control.note}</p>
            </div>
          ) : null}
          {protocol.readout_contract ? (
            <div className="rounded-md border border-border/70 bg-surface-wash/35 p-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Plain-primer/readout boundary</p>
              <p className="mt-1">
                This branch emits two ordinary ACGT primers. Modified Exo/Nfo/Fpg-style probes,
                labels, quenchers, affinity tags and 3′ blocks are not represented or inferred;
                detection modality remains a separate assay decision.
              </p>
            </div>
          ) : null}
          <p className="text-xs text-muted-foreground">{protocol.note}</p>
        </CardContent>
      </Card>
    );
  }

  if (protocol.kind === "long-range-pcr") {
    const primerValues = Object.values(protocol.primer_final_concentration_uM);
    const primerMin = primerValues.length ? Math.min(...primerValues) : null;
    const primerMax = primerValues.length ? Math.max(...primerValues) : null;
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">
            Selected long-range PCR authority
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed">
          <p className="font-medium text-foreground">{protocol.selection}</p>
          <p className="rounded-md border border-border/70 bg-surface-wash/35 p-2 text-xs text-muted-foreground">
            {protocol.lifecycle.status === "discontinued"
              ? `Historical/discontinued chemistry${protocol.lifecycle.discontinued_date ? `: ${protocol.lifecycle.discontinued_date}` : ""}. PCRStudio does not silently substitute a current chemistry.`
              : "Current named manufacturer branch. Screening Tm is not promoted to a vendor bench annealing-temperature decision."}
          </p>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Reaction volume</dt>
              <dd>{reactionVolume(protocol.reaction_volume_uL)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Primer concentration</dt>
              <dd>
                {primerMin == null
                  ? "See protocol"
                  : primerMin === primerMax
                    ? `${primerMin} µM each`
                    : `${primerMin}–${primerMax} µM documented values`}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Source</dt>
              <dd>
                {protocol.source_publication} · {protocol.source_revision}
                {protocol.source_revision_date ? ` · ${protocol.source_revision_date}` : ""}
              </dd>
            </div>
          </dl>
          {protocol.cycling_summary ? (
            <p className="text-xs text-muted-foreground">
              Cycling handoff: {protocol.cycling_summary}
            </p>
          ) : null}
          {protocol.constraints && Object.keys(protocol.constraints).length ? (
            <p className="text-xs text-muted-foreground">
              Protocol constraint overlay:{" "}
              {Object.entries(protocol.constraints)
                .map(([key, value]) => `${key.replaceAll("_", " ")}=${value}`)
                .join(" · ")}
              .
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">{protocol.note}</p>
        </CardContent>
      </Card>
    );
  }

  if (protocol.kind === "digital-pcr") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">Selected digital PCR chemistry</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed">
          <p className="font-medium text-foreground">{protocol.selection}</p>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Reaction / partition</dt>
              <dd>
                {reactionVolume(protocol.reaction_volume_uL)}
                {protocol.droplets_target
                  ? ` · ~${protocol.droplets_target.toLocaleString()} target droplets`
                  : protocol.partition_model
                    ? ` · ${protocol.partition_model}`
                    : ""}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Amplification handoff</dt>
              <dd>{protocol.cycling_summary ?? "Follow the named platform protocol"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Readout</dt>
              <dd>{protocol.readout}</dd>
            </div>
          </dl>
          <p className="text-xs text-muted-foreground">{protocol.note}</p>
        </CardContent>
      </Card>
    );
  }

  if (protocol.kind === "qpcr-sybr") {
    const primerConcentration = protocol.primer_final_concentration_nM;
    const primerRange = primerConcentration
      ? primerConcentration.starting != null
        ? `${primerConcentration.starting} nM starting${
            primerConcentration.optimization_min != null &&
            primerConcentration.optimization_max != null
              ? ` · optimize ${primerConcentration.optimization_min}–${primerConcentration.optimization_max} nM`
              : ""
          }`
        : primerConcentration.optimization_min != null &&
            primerConcentration.optimization_max != null
          ? `${primerConcentration.optimization_min}–${primerConcentration.optimization_max} nM documented range`
          : "See named protocol"
      : "See named protocol";
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">Selected dye-qPCR chemistry</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed">
          <p className="font-medium text-foreground">{protocol.selection}</p>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-4">
            <div>
              <dt className="text-muted-foreground">Amplicon starting window</dt>
              <dd>
                {protocol.amplicon_bp_preferred.min}–{protocol.amplicon_bp_preferred.max} bp
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Reaction / primer</dt>
              <dd>
                {reactionVolume(protocol.reaction_volume_uL)} · {primerRange} each
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Primer Tm target</dt>
              <dd>{protocol.primer_tm_c.target} °C</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Readout</dt>
              <dd>{protocol.readout}</dd>
            </div>
          </dl>
          {protocol.reverse_transcription ? (
            <p className="text-xs text-muted-foreground">
              Named RT: {protocol.reverse_transcription.temperature_c} °C/
              {protocol.reverse_transcription.incubation_minutes} min ·{" "}
              {protocol.reverse_transcription.authority_status}.
            </p>
          ) : null}
          {protocol.genomic_dna_control ? (
            <p className="text-xs text-muted-foreground">
              RNA-specificity controls: no-RT=
              {protocol.genomic_dna_control.no_rt_control_recommended
                ? "recommended"
                : "not specified"}{" "}
              · NTC=
              {protocol.genomic_dna_control.no_template_control_recommended
                ? "recommended"
                : "not specified"}{" "}
              · exon-junction design is recommended when annotated and appropriate, not a universal
              hard requirement.
            </p>
          ) : null}
          {protocol.carryover_prevention?.optional_udg_pretreatment ? (
            <p className="text-xs text-muted-foreground">
              Optional carry-over branch:{" "}
              {protocol.carryover_prevention.optional_UDG ?? "compatible UDG"} ·{" "}
              {protocol.carryover_prevention.optional_udg_pretreatment.temperature_c} °C/
              {protocol.carryover_prevention.optional_udg_pretreatment.minutes} min starting
              pretreatment; UDG is not built in.
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">{protocol.note}</p>
        </CardContent>
      </Card>
    );
  }

  return null;
}

export function ValidationPlan({ plan }: { plan: NonNullable<DesignResult["validation"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[13px] font-medium">
          <TriangleAlert className="size-4 text-warning" aria-hidden="true" />
          Before this becomes a bench result
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2.5">
        <p className="text-xs leading-relaxed text-muted-foreground">
          This run is <span className="font-medium text-foreground">{plan.status}</span>. The checks
          below require the actual reaction and are not measured by the design engine.
        </p>
        <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-muted-foreground">
          {plan.required.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        {plan.items.length > 0 ? (
          <details className="rounded-lg border border-border/60 bg-surface-wash/25">
            <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-foreground">
              Evidence details ({plan.items.length})
            </summary>
            <div className="space-y-1 border-t border-border/60 p-2">
              {plan.items.map((item) => (
                <details key={item.key} className="rounded-md px-2 py-1.5 hover:bg-surface-wash/50">
                  <summary className="flex min-h-6 cursor-pointer list-none items-center justify-between gap-3 py-1 text-xs">
                    <span className="font-medium text-foreground">{item.label}</span>
                    <span className="shrink-0 text-xs tracking-wide text-muted-foreground uppercase">
                      {item.phase}
                    </span>
                  </summary>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {item.why} Source: {item.source}.{item.unit ? ` Unit: ${item.unit}.` : ""}
                    {item.computable
                      ? " A related computational check is present in this run."
                      : " This run does not measure it."}
                  </p>
                </details>
              ))}
            </div>
          </details>
        ) : null}
        {plan.not_computed.length > 0 ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Not computed by this engine: {plan.not_computed.join("; ")}.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
