"use client";

import { PackageX } from "lucide-react";

import { ResultView } from "@/components/design/result-view";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Project, RunResult } from "@/lib/api/types";

/**
 * A project whose design system is not in this build.
 *
 * What this replaces is a 404 saying "No such project" — for a project that
 * exists, belongs to the person reading, and holds their sequence, their
 * settings and every run they saved. Telling somebody their work is gone when
 * it is sitting in the database is the worst answer available, and it is the
 * answer they got.
 *
 * The saved runs still render, because a result records the engine that
 * produced it and the views are chosen from that rather than from the module.
 * So everything except starting a *new* run survives the module leaving —
 * including the download, which is what somebody in this situation actually
 * needs.
 */
export function RetiredModule({ project, result }: { project: Project; result: RunResult | null }) {
  return (
    <div className="space-y-5">
      <Card className="workbench-card border-warning/40 bg-warning/5">
        <CardHeader className="flex flex-row items-start gap-3 space-y-0">
          <PackageX className="mt-0.5 size-4 shrink-0 text-warning" />
          <div className="space-y-1.5">
            <CardTitle className="font-serif text-base font-semibold">
              This project&rsquo;s design system is not in this build
            </CardTitle>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Nothing has been lost. The sequence, the settings and every saved run are still here,
              and the runs below can still be read and downloaded. What is missing is{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
                {project.moduleId}
              </code>
              , so no new run can be started against it until that system is installed again.
            </p>
          </div>
        </CardHeader>
        {project.notes ? (
          <CardContent>
            <p className="text-xs text-muted-foreground">Your notes</p>
            <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap">{project.notes}</p>
          </CardContent>
        ) : null}
      </Card>

      {result ? (
        <div className="workbench-result space-y-4 rounded-2xl border-t border-primary/20 pt-5">
          <ResultView result={result} />
        </div>
      ) : null}
    </div>
  );
}
