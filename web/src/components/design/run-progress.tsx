"use client";

/**
 * Measured execution status for a durable Generation 1 foundation run.
 *
 * Stages come from the Rust job lifecycle; this component never infers a stage
 * from elapsed time and never fabricates a percentage. A clock may still be
 * shown as context, but it cannot change the stage text.
 */

import { Loader2, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { RunJob } from "@/lib/api/types";

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued for worker capacity",
  "waiting-capacity": "Waiting for weighted worker capacity",
  "weighted-dispatch": "Scientific design is running",
  "scientific-design": "Scientific design is running",
  "persisting-result": "Saving the immutable run",
  cancelling: "Stopping the scientific worker",
  cancelled: "Run cancelled",
  completed: "Run completed",
  failed: "Run failed",
};

function stageLabel(job: RunJob | null, starting: boolean): string {
  if (starting) return "Submitting the durable run…";
  if (!job) return "Preparing the run…";
  return STAGE_LABELS[job.stage] ?? job.stage.replaceAll("-", " ");
}

export function RunProgress({
  job,
  starting = false,
  cancelling = false,
  onCancel,
}: {
  job: RunJob | null;
  starting?: boolean;
  cancelling?: boolean;
  onCancel?: () => void | Promise<void>;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const elapsed = useMemo(() => {
    const started = job?.startedAt ?? job?.createdAt;
    if (!started) return 0;
    const timestamp = Date.parse(started);
    return Number.isFinite(timestamp) ? Math.max(0, Math.floor((now - timestamp) / 1000)) : 0;
  }, [job?.createdAt, job?.startedAt, now]);

  return (
    <div
      role="status"
      aria-live="polite"
      className="mt-2 space-y-2 rounded-xl border border-warning/25 bg-warning/5 px-3 py-2.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex min-w-0 items-baseline gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3 shrink-0 animate-spin text-warning" aria-hidden="true" />
          <span className="font-medium text-foreground tabular-nums">{elapsed} s</span>
          <span className="leading-relaxed">{stageLabel(job, starting)}</span>
        </p>
        {onCancel ? (
          <button
            type="button"
            onClick={() => void onCancel()}
            disabled={cancelling}
            className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium text-foreground hover:bg-background disabled:cursor-not-allowed disabled:opacity-50"
          >
            {cancelling ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Square className="size-3" />
            )}
            {cancelling ? "Stopping…" : "Cancel run"}
          </button>
        ) : null}
      </div>
      <p className="text-xs leading-snug text-muted-foreground">
        Stage is reported by the backend job lifecycle. No synthetic percentage is shown. Your draft
        is already saved.
      </p>
    </div>
  );
}
