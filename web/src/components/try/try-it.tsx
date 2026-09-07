"use client";

import { ArrowRight, Dna, FlaskConical, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useActionState, useEffect, useState } from "react";

import { ResultView } from "@/components/design/result-view";
import { SAMPLE_TEMPLATES } from "@/components/design/sequence-input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { count } from "@/lib/numbers";
import { tryDesignAction, type TryState } from "@/lib/try/actions";

const EMPTY: TryState = {};

export function TryIt() {
  const [state, run, pending] = useActionState(tryDesignAction, EMPTY);
  const [template, setTemplate] = useState(state.template ?? "");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

  const cleanBasesCount = template
    .split("\n")
    .filter((l) => !l.startsWith(">"))
    .join("")
    .replace(/\s/g, "").length;

  return (
    <div className="space-y-6">
      {/* Input Card */}
      <Card className="workbench-card">
        <CardContent className="space-y-4 pt-5">
          {/* Quick Samples Bar */}
          <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-dashed border-primary/20 bg-surface-warm/35 px-3 py-2 text-xs">
            <span className="flex shrink-0 items-center gap-1 font-medium text-muted-foreground">
              <FlaskConical className="size-3 text-primary" />
              <span>1-Click Sample Templates:</span>
            </span>
            <div className="flex flex-wrap gap-1">
              {SAMPLE_TEMPLATES.map((sample) => (
                <button
                  key={sample.id}
                  type="button"
                  onClick={() => setTemplate(sample.sequence)}
                  className="min-h-6 cursor-pointer rounded-lg border border-border/70 bg-surface-wash/35 px-2 py-0.5 text-xs font-medium text-foreground transition-colors hover:border-primary hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  title={`${sample.name}: ${sample.description}`}
                >
                  {sample.name}
                </button>
              ))}
            </div>
          </div>

          <form action={run} className="space-y-3" data-form-ready={mounted ? "true" : undefined}>
            <Textarea
              name="template"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              onInput={(e) => setTemplate(e.currentTarget.value)}
              rows={8}
              required
              aria-label="Sequence to design against"
              placeholder={">my_target\nATGCGTACGATCGATCGTAGCTAGCTAGCATCGATCGATCG…"}
              className="font-mono text-xs leading-relaxed"
            />

            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
              <span className="flex items-center gap-1 font-medium text-foreground tabular-nums">
                <Dna className="size-3 text-primary" />
                <span>
                  {cleanBasesCount > 0 ? `${count(cleanBasesCount)} bases` : "FASTA or bare bases"}
                </span>
              </span>

              <span>Standard PCR · Standard Taq · Top 2 Pairs</span>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button type="submit" disabled={pending || cleanBasesCount === 0} className="gap-1.5">
                {pending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Sparkles className="size-3.5" />
                )}
                <span>{pending ? "Designing Primers…" : "Design Primers"}</span>
              </Button>
              <p className="text-xs text-muted-foreground">
                No account needed.{" "}
                <Link href="/modules" className="underline hover:text-foreground">
                  Browse all design systems
                </Link>{" "}
                for specialized assays.
              </p>
            </div>

            {state.error ? (
              <div
                role="alert"
                className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive"
              >
                {state.error}
              </div>
            ) : null}
          </form>
        </CardContent>
      </Card>

      {/* Results View */}
      {state.result ? (
        <div className="workbench-result space-y-4 rounded-2xl border-t border-primary/20 pt-5">
          <ResultView result={state.result} />

          <div className="workbench-card bg-surface-lilac/25 p-5">
            <p className="text-sm font-medium text-foreground">
              This run was generated in guest scratchpad mode.
            </p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Creating a free account allows saving sequence drafts, storing multiple runs,
              exporting IDT order sheets, and using all the specialized design modules.
            </p>
            <div className="mt-3.5 flex flex-wrap gap-2">
              <Button render={<Link href="/sign-up" />} size="sm">
                Create an account
                <ArrowRight className="size-3.5" />
              </Button>
              <Button render={<Link href="/modules" />} variant="outline" size="sm">
                Browse all design systems
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
