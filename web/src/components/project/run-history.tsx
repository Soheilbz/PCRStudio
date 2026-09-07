"use client";

/**
 * Every run kept in this project.
 *
 * A design is rarely right the first time, and the useful question a week
 * later is what was different about the attempt that worked. So each run keeps
 * its label, when it ran, and what it produced.
 */

import { History, Trash2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useActionState, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LocalTime } from "@/components/local-time";
import type { Project, RunSummary } from "@/lib/api/types";
import { ShareRun } from "@/components/project/share-run";
import { deleteRunAction, type ProjectState } from "@/lib/projects/actions";
import { runName } from "@/lib/projects/run-name";

function outputLabel(count: number, unit: string): string {
  return `${count} ${unit}${count === 1 ? "" : "s"}`;
}

export function RunHistory({
  project,
  runs,
  showing,
  maxRuns,
}: {
  project: Project;
  runs: RunSummary[];
  /** Which run is rendered above, so the list can say which one that is. */
  showing: string | null;
  /** How many this project keeps before the oldest is dropped. */
  maxRuns: number;
}) {
  /*
   * The ceiling is not a limit that refuses — it is a limit that *deletes*. A
   * project at its cap loses its oldest run the moment the next one is saved,
   * and until now nothing said so anywhere: somebody comparing this month's
   * attempt with the one from March would simply find March gone.
   *
   * Warned from five out, which is far enough ahead to label the ones worth
   * keeping or start a second project, and close enough that it is not a
   * standing notice on every project.
   */
  const remaining = maxRuns - runs.length;
  const nearlyFull = remaining <= 5;

  /*
   * Which runs are being compared lives in the address bar, like the module
   * list's filters: a comparison is a thing people send each other, and state
   * held in the component could not be linked, bookmarked or survive a reload.
   *
   * One parameter carrying both ids rather than two — `?compare=a,b` — because
   * typedRoutes and repeated query keys do not agree, and the joined form
   * reads the same everywhere a URL does. Replaced rather than pushed: picking
   * two runs is one deliberate act, and Back should undo it in one step.
   */
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const comparing = (params.get("compare") ?? "").split(",").filter(Boolean);

  const toggleCompare = (runId: string) => {
    // A third tick replaces the oldest selection rather than refusing: "no"
    // is an answer that makes somebody read the URL to work out why, where
    // dropping the first pick keeps the two they are looking at now.
    const next = comparing.includes(runId)
      ? comparing.filter((id) => id !== runId)
      : [...comparing, runId].slice(-2);
    const searchParams = new URLSearchParams(params.toString());
    if (next.length > 0) searchParams.set("compare", next.join(","));
    else searchParams.delete("compare");
    const search = searchParams.toString();
    router.replace(search ? `${pathname}?${search}` : pathname, { scroll: false });
  };

  return (
    <Card className="workbench-card">
      <CardHeader className="space-y-1.5">
        <CardTitle className="flex items-center gap-2 font-serif text-base font-semibold">
          <History className="size-4" />
          {runs.length} run{runs.length === 1 ? "" : "s"} kept{" "}
          {/* The space is written out because the gap between these two is
              flex, and flex is invisible to a screen reader: without it the
              line is read as "47 runs keptof 50". */}
          <span className="font-normal text-muted-foreground tabular-nums">of {maxRuns}</span>
        </CardTitle>
        {nearlyFull ? (
          <p className="text-xs leading-relaxed text-warning">
            {remaining > 0
              ? `${remaining} more can be saved here. After that, saving a run drops the oldest one — label anything worth keeping, or start a second project.`
              : "This project is full. Saving another run will drop the oldest one."}
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y">
          {runs.map((run) => {
            const open = run.id === showing;
            const name = runName(runs, run);

            return (
              <li
                key={run.id}
                className="flex flex-wrap items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-warm/35"
              >
                {/* A link, not a row that only reads.
                  Every run was listed here and openable from nowhere: five
                  attempts showed that five existed and rendered the last. The
                  earlier ones are usually the interesting ones. */}
                <Link
                  href={`/projects/${project.id}?run=${run.id}`}
                  aria-current={open ? "true" : undefined}
                  className="w-full rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:min-w-0 sm:flex-1"
                >
                  <p className="truncate text-sm font-medium">
                    {name}
                    {open ? (
                      // A real space, not a margin: a screen reader reads the
                      // text, and "first pass" beside "shown above" with only
                      // CSS between them is announced as one word.
                      <span className="ml-2 text-xs font-normal text-muted-foreground">
                        {" — shown above"}
                      </span>
                    ) : null}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {outputLabel(run.resultCount, run.resultUnit)}
                    {run.targetName ? ` from ${run.targetName}` : ""} ·{" "}
                    <LocalTime iso={run.createdAt} relative />
                  </p>
                </Link>
                <div className="flex w-full flex-wrap items-center gap-x-3 gap-y-1.5 sm:w-auto sm:shrink-0">
                  <CompareToggle
                    runId={run.id}
                    name={name}
                    checked={comparing.includes(run.id)}
                    onToggle={toggleCompare}
                  />
                  <ShareRun projectId={project.id} runId={run.id} sharedAlready={run.shared} />
                  <DeleteRun projectId={project.id} runId={run.id} name={name} />
                </div>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}

/**
 * The tick that puts a run into the comparison.
 *
 * A real checkbox, not a styled button pretending to be one: it is the one
 * control on this list whose meaning is "selected or not", and a native input
 * keeps the keyboard, the space bar and the screen-reader announcement of
 * checked state without any of them being re-implemented here.
 */
function CompareToggle({
  runId,
  name,
  checked,
  onToggle,
}: {
  runId: string;
  name: string;
  checked: boolean;
  onToggle: (runId: string) => void;
}) {
  return (
    <label className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
      <input
        type="checkbox"
        checked={checked}
        onChange={() => onToggle(runId)}
        aria-label={checked ? `Remove ${name} from comparison` : `Add ${name} to comparison`}
        className="size-3.5 accent-primary"
      />
      Compare
    </label>
  );
}

/**
 * Deletion, in two presses rather than one.
 *
 * The first press only asks; the second is the deletion. A window.confirm here
 * would block the whole page for a question that usually has the same answer,
 * so the ask lives on the button instead — and gives up after a few seconds,
 * because a confirmation that stays armed until clicked is a second
 * single-click delete that happens to say otherwise.
 */
function DeleteRun({ projectId, runId, name }: { projectId: string; runId: string; name: string }) {
  const [asking, setAsking] = useState(false);
  const [state, submit, pending] = useActionState(deleteRunAction, {} as ProjectState);
  const timer = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const arm = () => {
    setAsking(true);
    timer.current = setTimeout(() => setAsking(false), 4000);
  };

  return (
    <form action={submit}>
      <input type="hidden" name="projectId" value={projectId} />
      <input type="hidden" name="runId" value={runId} />
      <Button
        type={asking ? "submit" : "button"}
        onClick={asking ? undefined : arm}
        disabled={pending}
        variant="ghost"
        size="sm"
        className={
          asking
            ? "text-destructive hover:text-destructive"
            : "text-muted-foreground hover:text-destructive"
        }
        aria-label={asking ? `Confirm deleting ${name}` : `Delete ${name}`}
      >
        {pending ? (
          <span className="text-xs">Deleting…</span>
        ) : asking ? (
          <span className="text-xs">Confirm delete?</span>
        ) : (
          <Trash2 aria-hidden="true" />
        )}
      </Button>
      {state.error ? (
        <p role="alert" className="mt-1 max-w-44 text-right text-xs text-destructive">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}
