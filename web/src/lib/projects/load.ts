import "server-only";

/**
 * Server-side loaders for projects.
 *
 * A signed-out visitor gets empty lists rather than an error: the projects
 * page has something to say to them — sign in, or try a module directly — and
 * throwing would replace that with a stack trace.
 */

import { api, PcrStudioError } from "@/lib/api";
import { describe } from "@/lib/api/error";
import type {
  Preferences,
  Project,
  ProjectLimits,
  Run,
  RunSummary,
  SharedRun,
} from "@/lib/api/types";
import { readSessionToken } from "@/lib/auth/session";

export async function loadProjects(): Promise<{
  projects: Project[];
  signedIn: boolean;
  error: string | null;
}> {
  const token = await readSessionToken();
  if (!token) return { projects: [], signedIn: false, error: null };

  try {
    return { projects: await api.listProjects(token), signedIn: true, error: null };
  } catch (cause) {
    return {
      projects: [],
      signedIn: true,
      error: describe(cause, "Your projects could not be loaded. Try again in a moment."),
    };
  }
}

/**
 * One project with its runs.
 *
 * Four answers rather than three. "Missing" and "belongs to somebody else" are
 * deliberately the same, because distinguishing them would say whether a
 * project exists. But "we do not know who you are" is a different thing
 * entirely and has a different fix, so a visitor gets told to sign in rather
 * than told their project is gone — and "the store did not answer" is different
 * from both, because nothing about the project is known and the fix is to try
 * again rather than to sign in or give up.
 */
export type LoadedProject =
  | { status: "anonymous" }
  | { status: "missing" }
  | { status: "unreachable" }
  | { status: "ok"; project: Project; runs: RunSummary[]; runsError: string | null };

export async function loadProject(id: string): Promise<LoadedProject> {
  const token = await readSessionToken();
  if (!token) return { status: "anonymous" };

  try {
    const project = await api.getProject(token, id);
    let runs: RunSummary[] = [];
    let runsError: string | null = null;
    try {
      runs = await api.listRuns(token, id);
    } catch (cause) {
      runsError = describe(cause, "This project's run history could not be loaded.");
    }
    return { status: "ok", project, runs, runsError };
  } catch (cause) {
    if (cause instanceof PcrStudioError) {
      // Only the API's own `notFound` means the project is not there; a refused
      // connection or a store failure must not be rendered as "No such project".
      return cause.project?.kind === "notFound" ? { status: "missing" } : { status: "unreachable" };
    }
    throw cause;
  }
}

/** One run, whole — or where the lookup actually failed. */
export type LoadedRun =
  { status: "ok"; run: Run } | { status: "missing" } | { status: "unreachable" };

export async function loadRun(projectId: string, runId: string): Promise<LoadedRun> {
  const token = await readSessionToken();
  if (!token) return { status: "missing" };

  try {
    return { status: "ok", run: await api.getRun(token, projectId, runId) };
  } catch (cause) {
    if (cause instanceof PcrStudioError) {
      return cause.project?.kind === "notFound" ? { status: "missing" } : { status: "unreachable" };
    }
    throw cause;
  }
}

/**
 * The ceilings an account works inside, from the store that enforces them.
 *
 * Falls back to figures rather than throwing, because a page that cannot reach
 * the core should still render the project — but the fallback is deliberately
 * generous, so a stale answer never *invents* a warning that the store would
 * not have given.
 */
export async function loadProjectLimits(): Promise<ProjectLimits> {
  try {
    return await api.projectLimits();
  } catch {
    return {
      maxProjectsPerUser: Number.POSITIVE_INFINITY,
      maxRunsPerProject: Number.POSITIVE_INFINITY,
      maxAccountDataBytes: Number.POSITIVE_INFINITY,
      maxNameLength: 120,
      undoWindowDays: 30,
      maxActiveRunJobsPerUser: Number.POSITIVE_INFINITY,
      maxRetainedRunJobsPerUser: Number.POSITIVE_INFINITY,
      maxRunJobRequestBytes: Number.POSITIVE_INFINITY,
      maxRunJobDataBytesPerUser: Number.POSITIVE_INFINITY,
      runJobRetentionDays: Number.POSITIVE_INFINITY,
    };
  }
}

/**
 * What this person has told us about how they work.
 *
 * Empty for a visitor who is not signed in, and empty when the store cannot be
 * asked — in both cases the application does what it would have done without
 * preferences at all, which is the only safe way for a settings lookup to fail.
 */
export async function loadPreferences(): Promise<Preferences> {
  const token = await readSessionToken();
  if (!token) return {};

  try {
    return await api.preferences(token);
  } catch {
    return {};
  }
}

/**
 * One run, from a share link.
 *
 * No session is read, deliberately: the token is the authorisation, and asking
 * who is holding it would be asking a question the feature exists to avoid.
 * A withdrawn link and one that never existed are the same `missing` answer on
 * purpose. Transport/store failure stays separate so an outage is never shown
 * as evidence that the owner revoked the link.
 */
export type LoadedSharedRun =
  { status: "ok"; run: SharedRun } | { status: "missing" } | { status: "unreachable" };

export async function loadSharedRun(token: string): Promise<LoadedSharedRun> {
  try {
    return { status: "ok", run: await api.sharedRun(token) };
  } catch (cause) {
    if (cause instanceof PcrStudioError) {
      return cause.project?.kind === "notFound" ? { status: "missing" } : { status: "unreachable" };
    }
    throw cause;
  }
}
