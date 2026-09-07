"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { RunJob, RunResult } from "@/lib/api/types";
import { countAssayDesigns } from "@/lib/projects/result-count";
import {
  cancelRunJobAction,
  getRunJobAction,
  startRunJobAction,
  type WorkspaceState,
} from "@/lib/projects/actions";

const EMPTY: WorkspaceState = {};
const TERMINAL_JOB_STATUSES = new Set(["completed", "failed", "cancelled"]);

/** Own the durable-job state machine; the workspace only renders its projection. */
export function useWorkspaceRun({
  projectId,
  latest,
}: {
  projectId: string;
  latest: RunResult | null;
}) {
  const [state, setRunState] = useState<WorkspaceState>(EMPTY);
  const [job, setJob] = useState<RunJob | null>(null);
  const [startingRun, setStartingRun] = useState(false);
  const [cancellingRun, setCancellingRun] = useState(false);
  const activeJob = job !== null && !TERMINAL_JOB_STATUSES.has(job.status);
  const pending = startingRun || activeJob;
  const jobId = job?.id;
  const jobStatus = job?.status;

  const submit = useCallback(async (form: FormData) => {
    setRunState(EMPTY);
    setJob(null);
    setStartingRun(true);
    const answer = await startRunJobAction(form, crypto.randomUUID());
    setStartingRun(false);
    if (answer.error || !answer.job) {
      setRunState({ error: answer.error ?? "The design job could not be started." });
      return;
    }
    setJob(answer.job);
  }, []);

  useEffect(() => {
    if (!jobId || !jobStatus || TERMINAL_JOB_STATUSES.has(jobStatus)) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      const answer = await getRunJobAction(projectId, jobId);
      if (!alive) return;
      if (answer.error || !answer.job) {
        setRunState({ error: answer.error ?? "The design job could not be read." });
        setJob(null);
        return;
      }
      setJob(answer.job);
      if (answer.run && answer.project) {
        setRunState({ run: answer.run, project: answer.project });
        return;
      }
      if (answer.job.status === "failed") {
        const detail =
          typeof answer.job.error?.detail === "string"
            ? answer.job.error.detail
            : "The design job failed before a run was saved.";
        setRunState({ error: detail });
        return;
      }
      if (answer.job.status === "cancelled") {
        setRunState({ error: "The design run was cancelled. No result was saved." });
        return;
      }
      timer = setTimeout(poll, 500);
    };

    timer = setTimeout(poll, 250);
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, jobStatus, projectId]);

  const cancelCurrentRun = useCallback(async () => {
    if (!job || !activeJob || cancellingRun) return;
    setCancellingRun(true);
    const answer = await cancelRunJobAction(projectId, job.id);
    setCancellingRun(false);
    if (answer.error || !answer.job) {
      setRunState({ error: answer.error ?? "Cancellation could not be requested." });
      return;
    }
    setJob(answer.job);
    if (answer.job.status === "cancelled") {
      setRunState({ error: "The design run was cancelled. No result was saved." });
    }
  }, [activeJob, cancellingRun, job, projectId]);

  const result = state.run?.result ?? latest;
  const resultRef = useRef<HTMLDivElement>(null);
  const announcement = useMemo(() => {
    if (!state.run) return "";
    const found = countAssayDesigns(state.run.result);
    if (found === null) return "The design finished. The result is below.";
    if (found === 0) {
      return "The design finished and found nothing. The reason is below the button.";
    }
    return `The design finished with ${found} result${found === 1 ? "" : "s"}, below.`;
  }, [state.run]);

  useEffect(() => {
    if (state.run) resultRef.current?.focus();
  }, [state.run]);

  return {
    state,
    job,
    activeJob,
    startingRun,
    pending,
    cancellingRun,
    submit,
    cancelCurrentRun,
    result,
    resultRef,
    announcement,
  };
}
