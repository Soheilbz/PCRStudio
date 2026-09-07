import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DesignResult, LoopSetResult } from "@/lib/api/types";

function Fact({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value || "—"}</dd>
    </div>
  );
}

export function DigitalContext({
  context,
}: {
  context: NonNullable<DesignResult["digital_context"]>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">Digital-PCR run handoff</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs leading-relaxed">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          <Fact label="Platform" value={context.platform_name} />
          {context.instrument_model ? (
            <Fact label="Instrument model" value={context.instrument_model} />
          ) : null}
          <Fact label="Route" value={context.platform_route ?? undefined} />
          <Fact label="Protocol" value={context.protocol_id ?? undefined} />
          <Fact label="Consumable" value={context.consumable_id ?? undefined} />
          <Fact label="Partition" value={context.partition_format} />
          <Fact label="Fragmentation" value={context.fragmentation_state} />
          <Fact label="Threshold" value={context.threshold_status} />
          <Fact label="Quantification" value={context.quantification_status} />
          <Fact
            label="Partition-volume authority"
            value={context.partition_volume_authority_status}
          />
          <Fact label="Analysis software" value={context.analysis_software_version_status} />
          <Fact label="Volume correction / VPF" value={context.volume_precision_factor_status} />
          {context.current_platform_authority_reference ? (
            <Fact
              label="Current QIAcuity reference"
              value={`${context.current_platform_authority_reference.software_suite_reference}; ${context.current_platform_authority_reference.volume_precision_factor_reference}`}
            />
          ) : null}
        </dl>
        {context.current_platform_authority_reference ? (
          <p className="rounded-md border border-border/60 bg-surface-wash/35 p-2 text-muted-foreground">
            {context.current_platform_authority_reference.authority_use}.{" "}
            {context.current_platform_authority_reference.inference_policy}.
          </p>
        ) : null}
        {context.multiplex ? (
          <div className="space-y-2 rounded-md border border-border/60 bg-surface-wash/35 p-2">
            <p className="font-medium">
              Digital multiplex · {context.multiplex.mode} · {context.multiplex.target_count}{" "}
              targets
            </p>
            <p className="font-mono text-xs break-all text-muted-foreground">
              Panel SHA-256: {context.multiplex.panel_sha256}
            </p>
            <p className="text-muted-foreground">
              Software planning bound: {context.multiplex.software_planning_bound}; wet-lab
              qualified plex: not claimed. {context.multiplex.sequence_design_scope}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <caption className="sr-only">Digital multiplex panel targets</caption>
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th scope="col" className="pr-3 font-normal">
                      Target
                    </th>
                    <th scope="col" className="pr-3 font-normal">
                      Reporter/channel
                    </th>
                    <th scope="col" className="font-normal">
                      Amplitude / concentration
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {context.multiplex.panel.map((row) => (
                    <tr key={row.target} className="border-t border-border/60">
                      <td className="py-1.5 pr-3 font-medium">{row.target}</td>
                      <td className="py-1.5 pr-3">
                        {[row.reporter, row.channel].filter(Boolean).join(" / ") || "unresolved"}
                      </td>
                      <td className="py-1.5">
                        {[
                          row.amplitude_class,
                          row.primer_each_nm != null ? `${row.primer_each_nm} nM primer` : null,
                          row.probe_nm != null ? `${row.probe_nm} nM probe` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "run evidence pending"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-muted-foreground">
              Threshold/rain/cluster inference from sequence: forbidden. Imported run evidence never
              changes sequence ranking.
            </p>
          </div>
        ) : null}
        <p className="text-muted-foreground">{context.note}</p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          {context.required_run_evidence.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export function SpeciesPanelSnapshot({
  snapshot,
}: {
  snapshot: NonNullable<DesignResult["species_panel_snapshot"]>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Species-specific reproducibility snapshot
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label="Target TaxID" value={String(snapshot.target_taxid)} />
          <Fact label="Taxonomy snapshot" value={snapshot.taxonomy_snapshot} />
          <Fact label="Database snapshot" value={snapshot.database_snapshot} />
          <Fact label="Retrieved" value={snapshot.retrieved_date} />
        </dl>
        <p className="font-mono text-xs break-all text-muted-foreground">
          Accession manifest SHA-256: {snapshot.accession_manifest_sha256}
        </p>
        <p className="font-mono text-xs break-all text-muted-foreground">
          Record metadata SHA-256: {snapshot.record_metadata_manifest_sha256}
        </p>
        <p className="text-muted-foreground">
          Topology:{" "}
          {Object.entries(snapshot.record_metadata_summary.topology_counts)
            .map(([k, v]) => `${k}=${v}`)
            .join(" · ")}{" "}
          · Population weights: {snapshot.record_metadata_summary.population_weighting_status}
        </p>
        <p className="text-muted-foreground">
          {snapshot.taxonomy_resolution_status} · {snapshot.panel_completeness_status}
        </p>
        <p className="text-muted-foreground">Surveillance: {snapshot.surveillance_status}</p>
        <p className="text-muted-foreground">
          Revalidation: {snapshot.revalidation_policy.required_action}
        </p>
        <p className="text-muted-foreground">
          Triggers: {snapshot.revalidation_policy.triggers.join(" · ")}
        </p>
      </CardContent>
    </Card>
  );
}

export function ModifiedOligosContext({
  context,
}: {
  context:
    NonNullable<DesignResult["modified_oligos"]> | NonNullable<LoopSetResult["modified_oligos"]>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Modified-oligo manufacturing provenance
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <p className="text-muted-foreground">{context.note}</p>
        <dl className="space-y-1">
          {context.annotations.map((item, index) => (
            <div key={`${item.role}-${index}`} className="rounded-md border border-border/60 p-2">
              <dt className="font-medium">{item.role}</dt>
              <dd className="mt-1 text-muted-foreground">
                {[
                  item.fivePrimeLabel,
                  item.fluorophore,
                  item.quencher,
                  item.affinityLabel,
                  item.lateralFlowLabel,
                  item.threePrimeBlock,
                ]
                  .filter(Boolean)
                  .join(" · ") || "No terminal label/block recorded"}
                {item.internalModifications?.length
                  ? ` · Internal: ${item.internalModifications.map((mod) => `${mod.kind}@${mod.position}${mod.identity ? `:${mod.identity}` : ""}`).join(", ")}`
                  : ""}
                {item.cleavageSite != null ? ` · Cleavage site: ${item.cleavageSite}` : ""}
              </dd>
            </div>
          ))}
        </dl>
        <p className="font-mono text-xs text-muted-foreground">
          Schema: {context.schema} · sequence decision impact: {context.decision_impact}
        </p>
      </CardContent>
    </Card>
  );
}
