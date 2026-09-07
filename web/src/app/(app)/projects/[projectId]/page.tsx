import { ArrowLeft, History, LogIn } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ProjectHeader } from "@/components/project/project-header";
import { RetiredModule } from "@/components/project/retired-module";
import { RunComparison } from "@/components/project/run-comparison";
import { RunHistory } from "@/components/project/run-history";
import { Workspace } from "@/components/project/workspace";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import {
  loadCanAlign,
  loadCanFetch,
  loadModule,
  loadPresets,
  loadVocabulary,
} from "@/lib/api/load";
import {
  loadPreferences,
  loadProject,
  loadProjectLimits,
  loadRun,
  type LoadedRun,
} from "@/lib/projects/load";
import { requireUser } from "@/lib/auth/current-user";
import { parseCompareIds } from "@/lib/projects/comparison";
import { runNameById } from "@/lib/projects/run-name";
import type { Run } from "@/lib/api/types";

interface PageProps {
  params: Promise<{ projectId: string }>;
  /** `?run=` opens one particular run; `?compare=idA,idB` puts two side by side. */
  searchParams: Promise<{ run?: string; compare?: string }>;
}

export const metadata: Metadata = {
  title: "Project",
  // A project is somebody's working notes. It has no business in an index.
  robots: { index: false, follow: false },
};

/**
 * Which run to render: the one asked for, or the most recent.
 *
 * Kept out of the component so the fallback is one place rather than an
 * expression nobody reads. An id that is not in this project's list is not
 * looked up at all — that check is what stops `?run=` being a way to probe
 * whether somebody else's run exists.
 */
async function openRun(
  projectId: string,
  runs: { id: string }[],
  wanted?: string,
): Promise<LoadedRun> {
  const chosen = wanted && runs.some((run) => run.id === wanted) ? wanted : runs[0]?.id;
  // No runs at all is not a failed lookup — there was simply nothing to open.
  return chosen ? loadRun(projectId, chosen) : { status: "missing" };
}

/**
 * Both runs of a comparison, when two can actually be opened.
 *
 * The ids are checked against the project's own list before anything is looked
 * up (see `parseCompareIds`), and a run that has since been deleted is skipped
 * rather than failing the pair. Fewer than two surviving means no comparison —
 * the caller says so and renders the ordinary view instead, because half a
 * comparison is less use than none.
 */
async function openComparison(
  projectId: string,
  compareIds: [string, string] | null,
): Promise<{ a: Run; b: Run } | null> {
  if (!compareIds) return null;
  const [left, right] = await Promise.all([
    loadRun(projectId, compareIds[0]),
    loadRun(projectId, compareIds[1]),
  ]);
  return left.status === "ok" && right.status === "ok" ? { a: left.run, b: right.run } : null;
}

export default async function ProjectPage({ params, searchParams }: PageProps) {
  const { projectId } = await params;
  const { run: wanted, compare } = await searchParams;

  // A project is somebody's working notes; a stranger is redirected before
  // anything about it is fetched.
  await requireUser(`/projects/${projectId}`);

  const loaded = await loadProject(projectId);

  if (loaded.status === "anonymous") {
    return (
      <div className="space-y-6">
        <EmptyState
          icon={LogIn}
          title="Sign in to open this project"
          description="Projects belong to an account, so this page cannot say anything about one until it knows who is asking."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button render={<Link href={`/sign-in?next=/projects/${projectId}`} />} size="sm">
                <LogIn />
                Sign in
              </Button>
              <Button
                render={<Link href={`/sign-up?next=/projects/${projectId}`} />}
                variant="outline"
                size="sm"
              >
                Create an account
              </Button>
            </div>
          }
        />
      </div>
    );
  }

  if (loaded.status === "missing") {
    return (
      <div className="space-y-6">
        <EmptyState
          icon={History}
          title="No such project"
          description="Either it does not exist, or it belongs to a different account. Those are the same answer here on purpose."
          action={
            <Button render={<Link href="/modules" />} variant="outline" size="sm">
              <ArrowLeft />
              All modules
            </Button>
          }
        />
      </div>
    );
  }

  if (loaded.status === "unreachable") {
    return (
      <div className="space-y-6">
        <ErrorState
          error={new Error("The design core did not answer. Try again in a moment.")}
          title="This project could not be loaded"
        />
      </div>
    );
  }

  const { project, runs, runsError } = loaded;
  const [
    { data: assay },
    { data: presets, error: presetsError },
    { engines },
    canFetch,
    canAlign,
    latest,
    limits,
    preferences,
  ] = await Promise.all([
    loadModule(project.moduleId),
    loadPresets(project.moduleId),
    loadVocabulary(),
    loadCanFetch(),
    loadCanAlign(),
    // The one asked for, or the most recent when nothing was.
    //
    // Every run was reachable in the list and openable from nowhere: a project
    // with five attempts showed that five existed and would only ever render
    // the last. The four before it are usually the interesting ones — the
    // question a week later is what was different about the attempt that
    // worked, and that cannot be asked of a run you cannot open.
    //
    // An unknown id falls back rather than 404ing: a stale link is a link
    // somebody kept, and answering it with the project is more use than
    // answering it with nothing.
    openRun(project.id, runs, wanted),
    loadProjectLimits(),
    loadPreferences(),
  ]);

  const run = latest.status === "ok" ? latest.run : null;

  /*
   * A comparison, when `?compare=` named two runs this project still has.
   * Loaded whether or not the module is retired — a comparison is a reading
   * of saved results, and reading does not need the module to still exist.
   */
  const compareIds = parseCompareIds(compare, runs);
  const comparison =
    compareIds.length === 2
      ? await openComparison(project.id, [compareIds[0]!, compareIds[1]!])
      : null;

  /*
   * A module can leave a build — renamed, retired, or simply not compiled into
   * this one. The project it belonged to did not leave with it, so this is not
   * a 404: everything the person saved is still theirs to read and take away.
   */
  if (!assay) {
    return (
      <div className="space-y-6">
        <ProjectHeader project={project} assayName={project.moduleId} />
        {runsError ? (
          <ErrorState error={new Error(runsError)} title="Run history could not be loaded" />
        ) : null}
        {latest.status === "unreachable" ? (
          <ErrorState
            error={new Error("The design core did not answer. Try again in a moment.")}
            title="This run could not be loaded"
          />
        ) : null}
        {comparison ? (
          <RunComparison
            a={comparison.a}
            b={comparison.b}
            nameA={runNameById(runs, comparison.a.id)}
            nameB={runNameById(runs, comparison.b.id)}
          />
        ) : null}
        <RetiredModule project={project} result={run?.result ?? null} />
        {runs.length > 0 ? (
          <RunHistory
            project={project}
            runs={runs}
            showing={run?.id ?? null}
            maxRuns={limits.maxRunsPerProject}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ProjectHeader project={project} assayName={assay.name} />

      {runsError ? (
        <ErrorState error={new Error(runsError)} title="Run history could not be loaded" />
      ) : null}

      {latest.status === "unreachable" ? (
        <ErrorState
          error={new Error("The design core did not answer. Try again in a moment.")}
          title="This run could not be loaded"
        />
      ) : null}

      {/*
       * Two runs side by side replaces the ordinary view rather than sitting
       * beside it: the workspace renders one run, and a page rendering one
       * run *and* two of them answers three questions at once.
       */}
      {comparison ? (
        <RunComparison
          a={comparison.a}
          b={comparison.b}
          nameA={runNameById(runs, comparison.a.id)}
          nameB={runNameById(runs, comparison.b.id)}
        />
      ) : (
        <>
          {/*
           * Somebody pasted a `?compare=` link whose other half is gone —
           * deleted by the cap, most likely, which drops the oldest without
           * asking. The ordinary view still renders; this only explains why
           * it is the ordinary view.
           */}
          {compare && !comparison ? (
            <p className="rounded-xl border border-border/60 bg-surface-wash/45 px-4 py-3 text-xs leading-relaxed text-muted-foreground">
              That comparison could not be opened — one of its runs is gone or was never in this
              project — so the usual single-run view is shown instead.
            </p>
          ) : null}
          {presetsError || !presets ? (
            <ErrorState
              error={new Error(presetsError ?? "The design settings could not be loaded.")}
              title="Design settings could not be loaded"
            />
          ) : (
            <Workspace
              project={project}
              presets={presets}
              runs={runs}
              latest={run?.result ?? null}
              showing={run?.id ?? null}
              engine={assay.engine}
              // A project on a planned module still keeps a draft; what it cannot do
              // is run, and the workspace says so rather than failing at the end.
              runnable={
                assay.status !== "planned" &&
                Boolean(engines.find((entry) => entry.id === assay.engine)?.implemented)
              }
              canFetch={canFetch}
              canAlign={canAlign}
              preferences={preferences}
              assayDefaults={assay.defaults}
              modifiers={assay.modifiers}
              requirements={assay.requires}
            />
          )}
        </>
      )}

      {runs.length > 0 ? (
        <RunHistory
          project={project}
          runs={runs}
          showing={run?.id ?? null}
          maxRuns={limits.maxRunsPerProject}
        />
      ) : null}
    </div>
  );
}
