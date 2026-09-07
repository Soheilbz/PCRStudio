"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MultiplexResult, RunResult } from "@/lib/api/types";

function human(value: string | undefined): string {
  return (value || "not recorded").replaceAll("-", " ");
}

/**
 * Generation-1 execution evidence shared by all eleven engine result views.
 *
 * The first row answers the three questions a scientist needs immediately.
 * Tool-by-tool provenance, warnings and selection authority are progressively
 * disclosed so a routine user is not forced through deployment diagnostics,
 * while an expert can still audit exactly what happened.
 */
export function ToolchainStatus({ result }: { result: RunResult | MultiplexResult }) {
  const validation = result.toolchain_validation;
  const contract = result.runtime_contract;
  const verification = result.verification;
  const wetLabPlan = result.validation;
  const scientificIntegrity = result.scientific_integrity;
  if (!validation && !contract && !verification && !wetLabPlan && !scientificIntegrity) return null;

  const checks = validation?.checks ?? [];
  const checked = checks.filter((item) => item.status === "evidence-collected");
  const uninterpreted = checked.filter((item) => item.interpretation_complete !== true);
  const limited = checks.filter((item) => item.status === "evidence-collected-limited");
  const pending = checks.filter((item) =>
    ["unchecked", "error", "validator-error", "verification-incomplete"].includes(item.status),
  );
  const warnings = validation?.warnings ?? [];
  const moduleContract = "module_contract" in result ? result.module_contract : undefined;
  const resolution = contract?.resolved_parameters;

  const countPolicies = (
    value: unknown,
    counts = { locked: 0, bounded: 0, recommended: 0 },
  ): typeof counts => {
    if (!value || typeof value !== "object") return counts;
    for (const item of Object.values(value as Record<string, unknown>)) {
      if (
        item &&
        typeof item === "object" &&
        "override_policy" in (item as Record<string, unknown>)
      ) {
        const policy = String((item as Record<string, unknown>).override_policy ?? "");
        if (policy.includes("locked")) counts.locked += 1;
        else if (policy.includes("bounded")) counts.bounded += 1;
        else counts.recommended += 1;
      } else countPolicies(item, counts);
    }
    return counts;
  };
  const policyCounts = countPolicies(resolution);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <CardTitle className="text-[13px] font-medium">Toolchain verification</CardTitle>
          {validation ? (
            <span className="text-xs text-muted-foreground capitalize">
              {human(validation.status)}
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-xs leading-relaxed">
        <div className="grid gap-2 sm:grid-cols-3">
          <Fact
            label="Design"
            value={verification?.computational_design_complete ? "complete" : "incomplete"}
          />
          <Fact label="Independent evidence" value={human(validation?.status)} />
          <Fact
            label="Wet-lab"
            value={verification?.wet_lab_validated ? "validated" : "not claimed"}
          />
        </div>

        {checked.length > 0 ? (
          <p className="text-muted-foreground">
            Evidence collected with{" "}
            {checked.map((item) => `${item.tool_id} ${item.configured_version}`).join(", ")}.
          </p>
        ) : null}
        {validation?.status === "evidence-collected-uninterpreted" || uninterpreted.length > 0 ? (
          <div className="rounded-lg border border-warning/35 bg-warning/5 px-3 py-2 text-warning">
            <p className="font-medium">Evidence collected, interpretation incomplete</p>
            <p className="mt-1 text-xs leading-relaxed">
              {uninterpreted.length > 0
                ? `${uninterpreted.map((item) => item.tool_id).join(", ")} returned reproducible evidence, but the adapter cannot yet distinguish intended from unintended hits under a target-aware identity contract.`
                : "Required external evidence was collected, but it is not target-aware enough to support an external pass/fail claim."}{" "}
              This run is not labelled externally verified.
            </p>
          </div>
        ) : null}
        {limited.length > 0 ? (
          <div className="rounded-lg border border-warning/35 bg-warning/5 px-3 py-2 text-warning">
            <p className="font-medium">Limited database evidence</p>
            <p className="mt-1 text-xs leading-relaxed">
              {limited
                .map((item) => {
                  const scope = String(item.evidence?.database_scope ?? "non-production");
                  return `${item.tool_id} (${scope})`;
                })
                .join(", ")}
              . These checks prove tool wiring or bounded reference evidence; they are not presented
              as production organism-level specificity.
            </p>
          </div>
        ) : null}
        {pending.length > 0 ? (
          <p className="text-warning">
            Pending: {pending.map((item) => item.tool_id).join(", ")}. The result remains a
            computational design, but those independent checks are not complete.
          </p>
        ) : null}

        <p className="rounded-lg border border-border/60 bg-surface-wash/25 px-3 py-2 text-xs text-muted-foreground">
          Independent database hits are evidence, not an automatic off-target verdict. A validator
          affects selection only when the target/background identity makes that interpretation
          explicit and reproducible.
        </p>

        {wetLabPlan ? (
          <div className="rounded-lg border border-border/60 bg-background/60 px-3 py-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium">Required wet-lab evidence</p>
              <span className="text-xs text-muted-foreground">
                {wetLabPlan.required.length} required item(s)
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Computational ranking stops here. These observations must be collected before the
              assay is described as experimentally validated.
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {wetLabPlan.items
                .filter((item) => item.required)
                .map((item) => (
                  <li key={item.key}>
                    <span className="font-medium text-foreground">{item.label}:</span> {item.why}
                  </li>
                ))}
            </ul>
            {wetLabPlan.not_computed.length ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Not inferred: {wetLabPlan.not_computed.join("; ")}.
              </p>
            ) : null}
          </div>
        ) : null}

        {scientificIntegrity ? (
          <p className="rounded-lg border border-primary/20 bg-primary/[0.025] px-3 py-2 text-xs text-muted-foreground">
            Scientific policy {scientificIntegrity.policy_version}:{" "}
            <span className="font-medium text-foreground">{human(scientificIntegrity.mode)}</span>
            {scientificIntegrity.fail_closed ? " · fail-closed" : " · development mode"}. No
            scientific prerequisite is silently replaced to obtain a result.
          </p>
        ) : null}

        {checks.length > 0 ||
        warnings.length > 0 ||
        validation?.selection_policy ||
        contract ||
        moduleContract ? (
          <details className="rounded-lg border border-border/60 bg-background/60">
            <summary className="min-h-8 cursor-pointer px-3 py-2 text-xs font-medium focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
              Technical evidence and provenance
            </summary>
            <div className="space-y-3 border-t border-border/60 px-3 py-3">
              {checks.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Independent validators
                  </h4>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {checks.map((item) => (
                      <div
                        key={`${item.tool_id}-${item.purpose}`}
                        className="rounded-md border border-border/60 bg-surface-wash/20 px-2.5 py-2"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <span className="font-medium">
                            {item.tool_id} {item.configured_version}
                          </span>
                          <span className="text-xs text-muted-foreground capitalize">
                            {human(item.status)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">{item.purpose}</p>
                        {item.evidence?.database_scope ? (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Database scope: {human(String(item.evidence.database_scope))}
                            {item.evidence.database_id
                              ? ` · ${String(item.evidence.database_id)}`
                              : ""}
                          </p>
                        ) : null}
                        {item.decision_impact ? (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Selection impact: {human(item.decision_impact)}
                          </p>
                        ) : null}
                        {item.evidence?.pool_proposal &&
                        typeof item.evidence.pool_proposal === "object" ? (
                          <p className="mt-1 rounded border border-border/50 bg-background/50 px-2 py-1 text-xs text-muted-foreground">
                            Upstream pool proposal:{" "}
                            {human(
                              String(
                                (item.evidence.pool_proposal as Record<string, unknown>).status ??
                                  "recorded",
                              ),
                            )}
                            {(item.evidence.pool_proposal as Record<string, unknown>).pool_count !=
                            null
                              ? ` · ${String((item.evidence.pool_proposal as Record<string, unknown>).pool_count)} pool(s)`
                              : ""}
                            . Proposal is evidence-only until explicitly accepted into the panel
                            formulation.
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {warnings.length > 0 ? (
                <div>
                  <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Warnings
                  </h4>
                  <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                    {warnings.map((warning, index) => (
                      <li key={`${warning}-${index}`}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {validation?.selection_policy ? (
                <div>
                  <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Selection authority
                  </h4>
                  <dl className="mt-1 grid gap-1.5 text-xs sm:grid-cols-[9rem_1fr]">
                    {Object.entries(validation.selection_policy).map(([key, value]) => (
                      <div key={key} className="contents">
                        <dt className="font-medium text-foreground">{human(key)}</dt>
                        <dd className="text-muted-foreground">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ) : null}

              {moduleContract ? (
                <div>
                  <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Assay obligations
                  </h4>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {moduleContract.gates.length} explicit gate
                    {moduleContract.gates.length === 1 ? "" : "s"}; fallback:{" "}
                    {human(moduleContract.fallback)}.
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {moduleContract.gates.map((gate) => (
                      <span
                        key={gate}
                        className="rounded-full border border-border/60 bg-surface-wash/20 px-2 py-0.5 text-xs text-muted-foreground"
                      >
                        {human(gate)}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              {resolution &&
              (policyCounts.locked || policyCounts.bounded || policyCounts.recommended) ? (
                <div>
                  <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Parameter authority
                  </h4>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {policyCounts.locked} locked · {policyCounts.bounded} bounded ·{" "}
                    {policyCounts.recommended} recommended/tunable resolved field(s). Recommended
                    values are starting settings, not validity gates; bounded/locked fields still
                    require a reviewed profile to widen or replace them.
                  </p>
                </div>
              ) : null}

              {contract ? (
                <p className="text-xs text-muted-foreground">
                  Contract {contract.contract_version} · {contract.coordinate_contract.notation}{" "}
                  coordinates · engine {contract.engine_id} · parameter map{" "}
                  {contract.parameter_map_version}
                </p>
              ) : null}
            </div>
          </details>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border/60 bg-surface-wash/30 px-2.5 py-2">
      <div className="text-xs tracking-wide text-muted-foreground uppercase">{label}</div>
      <div className="mt-0.5 font-medium capitalize">{value}</div>
    </div>
  );
}
