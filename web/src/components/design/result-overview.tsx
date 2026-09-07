"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RunResult } from "@/lib/api/types";

function words(value: string | undefined): string {
  if (!value) return "not recorded";
  return value.replaceAll("-", " ");
}

/**
 * The compact orientation layer above every engine-specific result.
 *
 * A laboratory result page can be technically complete and still fail the
 * person reading it if the recommendation, evidence state and claim boundary
 * are separated by several screens of detail. This block makes those three
 * decisions visible before the user starts inspecting individual oligos.
 */
export function ResultOverview({ result }: { result: RunResult }) {
  const verification = result.verification;
  const validation = result.toolchain_validation;
  const contract = result.runtime_contract;
  const moduleId = contract?.module_id || "saved run";
  const engineId = contract?.engine_id || result.engine;
  const designComplete = verification?.computational_design_complete ?? true;

  return (
    <Card className="border-primary/20 bg-primary/[0.025]">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="font-serif text-base font-semibold">
              {designComplete ? "Recommended computational design" : "Design incomplete"}
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              {moduleId} · {engineId}
            </p>
          </div>
          <nav aria-label="Result sections" className="flex flex-wrap gap-1.5 text-xs">
            <a
              className="min-h-6 rounded-md border px-2.5 py-1 hover:bg-surface-wash focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              href="#result-verification"
            >
              Verification
            </a>
            <a
              className="min-h-6 rounded-md border px-2.5 py-1 hover:bg-surface-wash focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              href="#result-design"
            >
              Design details
            </a>
          </nav>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-3">
          <SummaryFact
            label="Computational design"
            value={designComplete ? "complete" : "incomplete"}
          />
          <SummaryFact label="Independent evidence" value={words(validation?.status)} />
          <SummaryFact
            label="Wet-lab evidence"
            value={verification?.wet_lab_validated ? "recorded" : "not claimed"}
          />
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          “Recommended” means top-ranked by the deterministic rules and constraints of this assay
          profile. It is not a universal guarantee of amplification. Independent database/tool
          evidence and wet-lab validation remain separate claims and are shown explicitly below.
        </p>
      </CardContent>
    </Card>
  );
}

function SummaryFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/70 px-3 py-2">
      <div className="text-xs tracking-wide text-muted-foreground uppercase">{label}</div>
      <div className="mt-0.5 text-xs font-medium capitalize">{value}</div>
    </div>
  );
}
