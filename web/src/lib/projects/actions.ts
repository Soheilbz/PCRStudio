"use server";

/**
 * Everything that touches a project.
 *
 * Server actions rather than route handlers, for the same reasons the account
 * actions are: the browser never learns the API's address, Next checks the
 * request origin, and the session token stays in an HttpOnly cookie that no
 * script can read.
 *
 * Every function here starts by reading that cookie. Without it there is no
 * project to act on, so the failure is a sentence about signing in rather than
 * a 401 somebody has to interpret.
 */

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api, PcrStudioError } from "@/lib/api";
import { describe } from "@/lib/api/error";
import type {
  CheckedPair,
  EnzymeChoice,
  MultiplexResult,
  Project,
  Run,
  RunJob,
  VectorPrimer,
} from "@/lib/api/types";
import type { MultiplexRequest } from "@/lib/api/transport";
import { readSessionToken } from "@/lib/auth/session";
import { collectTargets } from "./multiplex-targets";
import { forkSettingsFromRequest } from "./fork-settings";
import { requestFor } from "./request";
import { designRequestFor, type DesignRequest } from "@/lib/contracts/design-requests";
import type { ModuleId } from "@/lib/contracts/module-bindings.generated";

/** What a project form gets back. */
export interface ProjectState {
  error?: string;
  message?: string;
  project?: Project;
}

/** What the workspace gets back after a run. */
export interface WorkspaceState {
  error?: string;
  run?: Run;
  project?: Project;
}

const NOT_SIGNED_IN = "Sign in to keep projects. Your work is saved to your account.";

function field(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function optionalNumber(form: FormData, name: string): number | undefined {
  const raw = field(form, name);
  if (!raw) return undefined;
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new Error(`${name} must be a finite number.`);
  }
  return value;
}

export async function createProjectAction(
  _previous: ProjectState,
  form: FormData,
): Promise<ProjectState> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };

  const name = field(form, "name");
  const moduleId = field(form, "moduleId") || "standard-pcr";
  if (!name) return { error: "Give the project a name." };

  let project: Project;
  try {
    project = await api.createProject(token, name, moduleId);
  } catch (cause) {
    return { error: describe(cause) };
  }

  revalidatePath(`/modules/${moduleId}`);
  redirect(`/projects/${project.id}`);
}

export async function duplicateProjectAction(
  _previous: ProjectState,
  form: FormData,
): Promise<ProjectState> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };

  const projectId = field(form, "projectId");
  let newProject: Project;
  try {
    const original = await api.getProject(token, projectId);
    newProject = await api.createProject(token, `Copy of ${original.name}`, original.moduleId, {
      notes: original.notes,
      settings: original.settings,
    });
  } catch (cause) {
    return { error: describe(cause) };
  }

  revalidatePath("/projects");
  redirect(`/projects/${newProject.id}`);
}

export async function forkSharedRunAction(
  tokenString: string,
  moduleId?: string,
): Promise<{ projectId?: string; error?: string }> {
  const sessionToken = await readSessionToken();
  if (!sessionToken) {
    return { error: NOT_SIGNED_IN };
  }

  try {
    const shared = await api.sharedRun(tokenString);
    /*
     * The result names the engine that produced it, and several assays share
     * an engine, so the module to fork under is looked up rather than assumed:
     * a Gibson design forked onto standard PCR would refuse its own segments.
     * Not `module`: that identifier is the CommonJS module object, and Next
     * refuses to compile a binding that shadows it.
     */
    const resultObj = shared.result as Record<string, unknown>;
    const resultAssay =
      resultObj?.assay && typeof resultObj.assay === "object"
        ? (resultObj.assay as { id?: string }).id
        : undefined;
    const modules = await api.listModules();
    const currentIds = new Set(modules.map((entry) => entry.id));
    const chosenModule =
      (moduleId && currentIds.has(moduleId) ? moduleId : undefined) ||
      (resultAssay && currentIds.has(resultAssay) ? resultAssay : undefined) ||
      modules.find((entry) => entry.engine === shared.result.engine)?.id ||
      "standard-pcr";
    const targetObj = resultObj?.target as { name?: string } | undefined;
    const targetName = targetObj?.name;
    const name = shared.label ? `Fork: ${shared.label}` : `Forked: ${targetName || "Run"}`;

    const draftSettings = forkSettingsFromRequest(shared.request, targetName);
    const project = await api.createProject(sessionToken, name, chosenModule, {
      notes: `Imported from a shared link (${shared.result.engine})`,
      settings: draftSettings,
    });

    revalidatePath("/projects");
    return { projectId: project.id };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

export async function renameProjectAction(
  _previous: ProjectState,
  form: FormData,
): Promise<ProjectState> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };

  const id = field(form, "projectId");
  try {
    const project = await api.updateProject(token, id, {
      name: field(form, "name"),
      notes: field(form, "notes"),
    });
    revalidatePath(`/projects/${id}`);
    return { project, message: "Saved." };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

export async function deleteProjectAction(
  _previous: ProjectState,
  form: FormData,
): Promise<ProjectState> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };

  const id = field(form, "projectId");
  const moduleId = field(form, "moduleId") || "standard-pcr";
  try {
    await api.deleteProject(token, id);
  } catch (cause) {
    // Deletion is idempotent only when the API confirms the project is already
    // absent. A store outage must remain visible; redirecting then would offer
    // an undo for a project that was never deleted.
    if (!(cause instanceof PcrStudioError && cause.project?.kind === "notFound")) {
      return { error: describe(cause) };
    }
  }
  revalidatePath(`/modules/${moduleId}`);
  revalidatePath("/projects");
  redirect(`/projects?undone=${encodeURIComponent(id)}`);
}

export async function restoreProjectAction(
  _previous: ProjectState,
  form: FormData,
): Promise<ProjectState> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };

  const id = field(form, "projectId");
  try {
    await api.restoreProject(token, id);
  } catch (cause) {
    // A restore that fails is a sentence on the list page rather than an
    // error screen: the window may simply have passed, and either way the
    // rest of the list is still usable.
    return { error: describe(cause) };
  }

  revalidatePath("/projects");
  redirect(`/projects/${id}`);
}

export async function saveDraftAction(
  projectId: string,
  settings: Record<string, unknown>,
  expectedUpdatedAt: string,
): Promise<{
  saved: boolean;
  updatedAt?: string;
  settings?: Record<string, unknown>;
  conflict?: boolean;
  conflictFields?: string[];
  remoteUpdatedAt?: string;
  remoteSettings?: Record<string, unknown>;
  failure?: { kind: string; detail: string };
}> {
  const token = await readSessionToken();
  if (!token) {
    return { saved: false, failure: { kind: "notSignedIn", detail: NOT_SIGNED_IN } };
  }

  try {
    const project = await api.updateProject(token, projectId, { settings, expectedUpdatedAt });
    return { saved: true, updatedAt: project.updatedAt, settings: project.settings };
  } catch (cause) {
    if (!(cause instanceof PcrStudioError && cause.project?.kind === "conflict")) {
      return {
        saved: false,
        failure: {
          kind: cause instanceof PcrStudioError ? (cause.project?.kind ?? "api") : "unexpected",
          detail: describe(cause),
        },
      };
    }

    // Do not send the previous full draft through the Server Action merely to
    // perform a three-way merge. A legal 8 MiB sequence can make two copies of
    // the draft exceed the Server Action transport ceiling. Return the current
    // authoritative server snapshot and let the browser merge against the base
    // it already owns; the retry still uses optimistic concurrency.
    try {
      const remote = await api.getProject(token, projectId);
      return {
        saved: false,
        conflict: true,
        remoteUpdatedAt: remote.updatedAt,
        remoteSettings: remote.settings,
      };
    } catch (remoteCause) {
      return {
        saved: false,
        failure: {
          kind:
            remoteCause instanceof PcrStudioError
              ? (remoteCause.project?.kind ?? "api")
              : "unexpected",
          detail: describe(remoteCause),
        },
      };
    }
  }
}

export async function deleteRunAction(
  _previous: ProjectState,
  form: FormData,
): Promise<ProjectState> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };

  const projectId = field(form, "projectId");
  try {
    await api.deleteRun(token, projectId, field(form, "runId"));
  } catch (cause) {
    // Keep the idempotent case harmless, but do not hide a database or
    // transport failure behind a list refresh that suggests deletion worked.
    if (!(cause instanceof PcrStudioError && cause.project?.kind === "notFound")) {
      return { error: describe(cause) };
    }
  }
  revalidatePath(`/projects/${projectId}`);
  return {};
}

/* ── What is already on the bench ─────────────────────────────────────── */

export async function rankEnzymesAction(
  template: string,
  purpose: "inverse-flank" | "absent" | "open-once",
): Promise<{ enzymes: EnzymeChoice[]; error?: string }> {
  if (!template.trim()) {
    return { enzymes: [], error: "Paste a sequence first." };
  }
  try {
    const answer = await api.rankEnzymes(template, undefined, purpose);
    return { enzymes: answer.enzymes };
  } catch (cause) {
    return { enzymes: [], error: describe(cause) };
  }
}

export async function placeVectorPrimersAction(vector: string): Promise<{
  primers: VectorPrimer[];
  checkedAgainst: string;
  note: string;
  error?: string;
}> {
  if (!vector.trim()) {
    return {
      primers: [],
      checkedAgainst: "",
      note: "",
      error:
        "Paste the vector sequence first — a primer's position in the published plasmid is not a fact about yours.",
    };
  }
  try {
    const answer = await api.placeVectorPrimers(vector);
    return {
      primers: answer.primers,
      checkedAgainst: answer.checked_against,
      note: answer.note,
    };
  } catch (cause) {
    return { primers: [], checkedAgainst: "", note: "", error: describe(cause) };
  }
}

/* ── Several targets in one tube ──────────────────────────────────────── */

export interface MultiplexState {
  result?: MultiplexResult;
  error?: string;
}

export async function runMultiplexAction(
  moduleId: string,
  form: FormData,
): Promise<MultiplexState> {
  const readoutValue = field(form, "readout");
  const readoutProfileValue = field(form, "readoutProfile");
  let candidatesPerTarget: number | undefined;
  let perTube: number | undefined;
  let rounds: number | undefined;
  let optimizerMode: MultiplexRequest["optimizerMode"];
  let fromRna: boolean;
  let targets: ReturnType<typeof collectTargets>;
  try {
    candidatesPerTarget = optionalNumber(form, "candidatesPerTarget");
    perTube = optionalNumber(form, "perTube");
    rounds = optionalNumber(form, "rounds");
    const optimizerRaw = field(form, "optimizerMode");
    optimizerMode =
      optimizerRaw === "exact" || optimizerRaw === "local" || optimizerRaw === "auto"
        ? optimizerRaw
        : undefined;
    const fromRnaRaw = field(form, "fromRna");
    if (fromRnaRaw && fromRnaRaw !== "true") {
      throw new Error("fromRna must be `true` when supplied by the multiplex form.");
    }
    fromRna = fromRnaRaw === "true";
    targets = collectTargets(form);
  } catch (cause) {
    return { error: describe(cause) };
  }

  const readout = ["agarose", "capillary", "ngs"].includes(readoutValue)
    ? (readoutValue as "agarose" | "capillary" | "ngs")
    : null;
  if (!readout) {
    return { error: "Choose how the products will be read before designing the set." };
  }
  const readoutProfile = [
    "qiagen-multiplex-agarose-guideline",
    "qiagen-qiaxcel-high-resolution",
    "qiagen-qiaxcel-screening",
  ].includes(readoutProfileValue)
    ? (readoutProfileValue as
        | "qiagen-multiplex-agarose-guideline"
        | "qiagen-qiaxcel-high-resolution"
        | "qiagen-qiaxcel-screening")
    : undefined;
  if (readout === "agarose" && readoutProfile !== "qiagen-multiplex-agarose-guideline") {
    return {
      error:
        "Choose the named agarose supplier-reference profile; generic gel resolution is not a single number.",
    };
  }
  if (readout === "capillary" && !readoutProfile) {
    return {
      error:
        "Choose the capillary cartridge/reference profile; generic capillary resolution is not a single number.",
    };
  }
  if (targets.length < 2) {
    return { error: "Add at least two targets with sequences to design a multiplex set." };
  }

  try {
    const result = await api.runMultiplex(moduleId, {
      readout,
      readoutProfile,
      fromRna,
      standardPcrProtocol:
        moduleId === "standard-pcr"
          ? (field(form, "standardPcrProtocol") as MultiplexRequest["standardPcrProtocol"]) ||
            undefined
          : undefined,
      colonyHostClass:
        (field(form, "colonyHostClass") as MultiplexRequest["colonyHostClass"]) || undefined,
      colonyPreparation:
        (field(form, "colonyPreparation") as MultiplexRequest["colonyPreparation"]) || undefined,
      colonyProtocolId:
        (field(form, "colonyProtocolId") as MultiplexRequest["colonyProtocolId"]) || undefined,
      colonyProtocolName: field(form, "colonyProtocolName") || undefined,
      colonyProtocolProvenance: field(form, "colonyProtocolProvenance") || undefined,
      targets,
      candidatesPerTarget,
      perTube,
      rounds,
      optimizerMode,
    });
    return { result };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

/* ── Check existing primers ───────────────────────────────────────────── */

export async function checkPrimersAction(request: {
  moduleId?: string;
  template: string;
  lowercaseMasking?: boolean;
  left: string;
  right: string;
  background?: string;
  maxMismatches?: number;
}): Promise<{ result?: CheckedPair; error?: string }> {
  if (!request.template.trim()) {
    return {
      error:
        "A pair can only be checked against the template it was made for — a primer against the wrong one measures exactly as well until the reaction fails.",
    };
  }
  if (!request.left.trim() || !request.right.trim()) {
    return { error: "Both primers, please. One on its own has no product and no pair." };
  }

  try {
    return {
      result: await api.checkPrimers({
        moduleId: request.moduleId,
        template: request.template,
        lowercaseMasking: request.lowercaseMasking,
        left: request.left.trim(),
        right: request.right.trim(),
        background: request.background?.trim() || undefined,
        maxMismatches: request.maxMismatches,
      }),
    };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

export async function shareRunAction(
  projectId: string,
  runId: string,
): Promise<{ link?: string; error?: string }> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  try {
    return { link: await api.shareRun(token, projectId, runId) };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

export async function unshareRunAction(
  projectId: string,
  runId: string,
): Promise<{ error?: string }> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  try {
    await api.unshareRun(token, projectId, runId);
    return {};
  } catch (cause) {
    return { error: describe(cause) };
  }
}

function designFromWorkspaceForm(form: FormData): {
  projectId: string;
  label: string;
  request: DesignRequest;
} {
  const projectId = field(form, "projectId");
  const engine = field(form, "engine");
  const template = field(form, "template");
  if (!template && engine !== "junction-primers") {
    throw new Error("Paste a sequence to design against.");
  }
  const payload = requestFor(engine, template, form);
  const moduleId = field(form, "moduleId") as ModuleId;
  return {
    projectId,
    label: field(form, "label"),
    request: designRequestFor(moduleId, engine, payload) as DesignRequest,
  };
}

export async function runInProjectAction(
  _previous: WorkspaceState,
  form: FormData,
): Promise<WorkspaceState> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };
  try {
    const built = designFromWorkspaceForm(form);
    const answer = await api.runInProject(
      token,
      built.projectId,
      built.label,
      built.request.payload,
    );
    revalidatePath(`/projects/${built.projectId}`);
    return { run: answer.run, project: answer.project };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

/** Start a durable Generation 1 foundation run without exposing the API/session token to the browser. */
export async function startRunJobAction(
  form: FormData,
  idempotencyKey: string,
): Promise<{ job?: RunJob; error?: string }> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };
  if (!idempotencyKey || idempotencyKey.length > 128) {
    return { error: "The run identity is invalid. Try submitting the design again." };
  }
  try {
    const built = designFromWorkspaceForm(form);
    return {
      job: await api.startRunJob(
        token,
        built.projectId,
        built.label,
        built.request.payload,
        idempotencyKey,
      ),
    };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

/** Poll one durable run and materialize its immutable saved result once complete. */
export async function getRunJobAction(
  projectId: string,
  jobId: string,
): Promise<{ job?: RunJob; run?: Run; project?: Project; error?: string }> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };
  try {
    const job = await api.getRunJob(token, projectId, jobId);
    if (job.status === "completed" && job.runId) {
      const [run, project] = await Promise.all([
        api.getRun(token, projectId, job.runId),
        api.getProject(token, projectId),
      ]);
      revalidatePath(`/projects/${projectId}`);
      return { job, run, project };
    }
    return { job };
  } catch (cause) {
    return { error: describe(cause) };
  }
}

/** Request cancellation; the Rust worker boundary kills/reaps an active child. */
export async function cancelRunJobAction(
  projectId: string,
  jobId: string,
): Promise<{ job?: RunJob; error?: string }> {
  const token = await readSessionToken();
  if (!token) return { error: NOT_SIGNED_IN };
  try {
    return { job: await api.cancelRunJob(token, projectId, jobId) };
  } catch (cause) {
    return { error: describe(cause) };
  }
}
