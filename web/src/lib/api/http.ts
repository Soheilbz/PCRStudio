/**
 * The transport: HTTP to the Rust API.
 *
 * Marked server-only. Every call happens during rendering or inside a server
 * action, so the API's address never reaches the browser and the API never has
 * to be exposed to the public internet — only Next has to reach it.
 */
import "server-only";

import { headers } from "next/headers";
import { z } from "zod";

import { PcrStudioError, toPcrStudioError } from "./error";
import { HTTP_ROUTES, httpRoute, type HttpRouteId } from "./routes.generated";
import type { Transport } from "./transport";
import {
  alignedSchema,
  alignersSchema,
  appInfoSchema,
  consensusSchema,
  fetchAnswerSchema,
  fetchAvailabilitySchema,
  endedSchema,
  engineDescriptionSchema,
  goalDescriptionSchema,
  modifierTermSchema,
  statusTermSchema,
  moduleManifestSchema,
  presetsSchema,
  catalogueSchema,
  preferencesSchema,
  shareLinkSchema,
  sharedRunSchema,
  projectLimitsSchema,
  projectSchema,
  runAnswerSchema,
  checkedPairSchema,
  enzymeRankingSchema,
  multiplexResultSchema,
  runResultSchema,
  vectorPrimersSchema,
  runSchema,
  runJobSchema,
  runSummarySchema,
  recoveryCodeSchema,
  recoveryStatusSchema,
  sessionSchema,
  userSchema,
} from "./types";

/** Where the design core listens. Set in the environment for deployment. */
const API_URL = (process.env.PCR_API_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");

/** How long a rendered page may reuse a fetched answer, in seconds. */
const REVALIDATE_SECONDS = 300;

// Keep the client-side deadline just beyond the API's five-minute request
// timeout. Without an explicit signal, a dead or half-open API connection can
// pin a Next render or server action indefinitely.
const API_TIMEOUT_MS = 310_000;

interface CallOptions {
  method?: string;
  params?: Record<string, string>;
  body?: unknown;
  token?: string;
  /** Additional internal API headers, such as Idempotency-Key. */
  headers?: Record<string, string>;
  /** Seconds the answer may be reused. Omit for answers that must be fresh. */
  revalidate?: number;
}

/**
 * The address of whoever asked us, so the core's rate limiter can count people
 * rather than count this process.
 *
 * The API keys its limits on the peer address, and from there every request
 * this module makes looks identical — one caller, the web tier — unless the
 * original address rides along in `X-Forwarded-For`. Without it, ten login
 * attempts in five minutes are shared by the whole site, and one bad actor
 * locks everybody out.
 *
 * Only uncached calls carry it: a cached answer is not about one person, and a
 * per-caller header would splinter Next's shared cache into one entry per
 * visitor. Cached calls also happen to be exactly the ones no limiter cares
 * who asked for.
 *
 * The value is trusted as Caddy handed it to us (Caddy discards what an
 * untrusted client sent and writes the real address itself), which makes the
 * edge part of this contract: anything exposed to the internet ahead of this
 * process must sanitise that header the same way, or a script can hand itself
 * a fresh bucket per request.
 */
async function callerAddress(): Promise<string | undefined> {
  try {
    return (await headers()).get("x-forwarded-for")?.trim() || undefined;
  } catch {
    // No request scope (a build-time render, say). Nothing to forward; the
    // core falls back to counting the web tier as one caller, as before.
    return undefined;
  }
}

async function request<T>(
  routeId: HttpRouteId,
  schema: z.ZodType<T>,
  options: CallOptions = {},
): Promise<T> {
  const path = httpRoute(routeId, options.params);
  const contractMethod = HTTP_ROUTES[routeId].method;
  if (options.method !== undefined && options.method !== contractMethod) {
    throw new PcrStudioError(
      `HTTP contract drift for ${routeId}: client requested ${options.method}, canonical method is ${contractMethod}.`,
      null,
    );
  }
  const url = `${API_URL}${path}`;
  const outgoing: Record<string, string> = { accept: "application/json" };
  if (options.body !== undefined) outgoing["content-type"] = "application/json";
  if (options.token) outgoing.authorization = `Bearer ${options.token}`;
  Object.assign(outgoing, options.headers ?? {});
  if (options.revalidate === undefined) {
    const forwarded = await callerAddress();
    if (forwarded) outgoing["x-forwarded-for"] = forwarded;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: contractMethod,
      headers: outgoing,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
      ...(options.revalidate === undefined
        ? { cache: "no-store" as const }
        : { next: { revalidate: options.revalidate } }),
    });
  } catch (cause) {
    // Never put the internal API URL or operator instructions on the browser
    // error path. In Compose that address names private service topology. The
    // cause remains attached for server-side logging/telemetry.
    throw new PcrStudioError(
      "The design service is temporarily unavailable. Try again shortly.",
      null,
      { cause },
    );
  }

  // 204 and friends carry nothing to parse.
  const text = await response.text();
  const body: unknown = text.length > 0 ? safeJson(text) : null;

  if (!response.ok) {
    throw toPcrStudioError(body ?? `The server answered ${response.status} for ${path}.`);
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    // Rust and TypeScript have drifted. Name the endpoint so the fix does not
    // start with a hunt.
    throw new PcrStudioError(
      `${path} returned a shape the interface does not recognise: ${parsed.error.message}`,
      null,
      { cause: parsed.error },
    );
  }
  return parsed.data;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function createHttpTransport(): Transport {
  return {
    appInfo: () => request("info", appInfoSchema, { revalidate: REVALIDATE_SECONDS }),

    listModules: () =>
      request("modules", z.array(moduleManifestSchema), { revalidate: REVALIDATE_SECONDS }),

    getModule: (id) =>
      request("module", moduleManifestSchema, {
        params: { id },
        revalidate: REVALIDATE_SECONDS,
      }),

    listGoals: () =>
      request("goals", z.array(goalDescriptionSchema), { revalidate: REVALIDATE_SECONDS }),

    listEngines: () =>
      request("engines", z.array(engineDescriptionSchema), {
        revalidate: REVALIDATE_SECONDS,
      }),

    listModifiers: () =>
      request("modifiers", z.array(modifierTermSchema), { revalidate: REVALIDATE_SECONDS }),

    listStatuses: () =>
      request("statuses", z.array(statusTermSchema), { revalidate: REVALIDATE_SECONDS }),

    getPresets: (id) =>
      request("module_presets", presetsSchema, {
        params: { id },
        revalidate: REVALIDATE_SECONDS,
      }),

    canFetch: () =>
      request("sequence_fetch_availability", fetchAvailabilitySchema, {
        revalidate: REVALIDATE_SECONDS,
      }),

    // Not cached: a lookup is cheap to repeat and a stale sequence would be
    // the worst possible thing to hand somebody.
    fetchSequences: (accessions) =>
      request("sequence_fetch", fetchAnswerSchema, {
        method: "POST",
        body: { accessions },
      }),

    canAlign: () =>
      request("sequence_aligners", alignersSchema, { revalidate: REVALIDATE_SECONDS }),

    alignSequences: (fasta) =>
      request("sequence_align", alignedSchema, { method: "POST", body: { fasta } }),

    consensus: (fasta) =>
      request("sequence_consensus", consensusSchema, {
        method: "POST",
        body: { fasta },
      }),

    // Never cached: a design is a computation over what was just typed, and a
    // reused answer would silently belong to a different request.
    runDesign: (id, body) =>
      request("module_design", runResultSchema, {
        params: { id },
        method: "POST",
        body,
      }),

    rankEnzymes: (template, background, purpose) =>
      request("enzymes", enzymeRankingSchema, {
        method: "POST",
        body: { template, background, purpose },
      }),

    placeVectorPrimers: (vector, vectorName) =>
      request("vector_primers", vectorPrimersSchema, {
        method: "POST",
        body: { vector, vectorName },
      }),

    checkPrimers: (body) => request("check_primers", checkedPairSchema, { method: "POST", body }),

    runMultiplex: (id, body) =>
      request("module_multiplex", multiplexResultSchema, {
        params: { id },
        method: "POST",
        body,
      }),

    // Nothing below may be cached: each one is about a particular person, and
    // several of them change what the answer to the next call should be.
    register: (email, displayName, password) =>
      request("auth_register", sessionSchema, {
        method: "POST",
        body: { email, displayName, password },
      }),

    login: (email, password, remember) =>
      request("auth_login", sessionSchema, {
        method: "POST",
        body: { email, password, remember },
      }),

    recover: (email, recoveryCode, newPassword) =>
      request("auth_recover", sessionSchema, {
        method: "POST",
        body: { email, recoveryCode, newPassword },
      }),

    recoveryStatus: (token) => request("auth_recovery_get", recoveryStatusSchema, { token }),

    reissueRecoveryCode: (token, password) =>
      request("auth_recovery_post", recoveryCodeSchema, {
        method: "POST",
        token,
        body: { password },
      }),

    logout: (token) =>
      request("auth_logout", z.unknown(), { method: "POST", token }).then(() => undefined),

    currentUser: (token) => request("auth_me", userSchema, { token }),

    rename: (token, displayName) =>
      request("auth_profile", userSchema, {
        method: "PATCH",
        token,
        body: { displayName },
      }),

    changeEmail: (token, currentPassword, newEmail) =>
      request("auth_email", userSchema, {
        method: "PATCH",
        token,
        body: { currentPassword, newEmail },
      }),

    changePassword: (token, currentPassword, newPassword) =>
      request("auth_password", z.unknown(), {
        method: "POST",
        token,
        body: { currentPassword, newPassword },
      }).then(() => undefined),

    // Nothing below may be cached either: a project changes as somebody works
    // in it, and a stale draft is worse than a slow one.
    listProjects: (token) => request("projects_list", z.array(projectSchema), { token }),

    createProject: (token, name, moduleId, initial) =>
      request("projects_create", projectSchema, {
        method: "POST",
        token,
        body: { name, moduleId, ...(initial ?? {}) },
      }),

    getProject: (token, id) => request("project_get", projectSchema, { params: { id }, token }),

    updateProject: (token, id, change) =>
      request("project_patch", projectSchema, {
        params: { id },
        method: "PATCH",
        token,
        body: change,
      }),

    deleteProject: (token, id) =>
      request("project_delete", z.unknown(), {
        params: { id },
        method: "DELETE",
        token,
      }).then(() => undefined),

    shareRun: (token, projectId, runId) =>
      request("run_share_post", shareLinkSchema, {
        params: { id: projectId, run: runId },
        method: "POST",
        token,
      }).then((answer) => answer.token),

    unshareRun: (token, projectId, runId) =>
      request("run_share_delete", z.unknown(), {
        params: { id: projectId, run: runId },
        method: "DELETE",
        token,
      }).then(() => undefined),

    sharedRun: (shareToken) =>
      request("shared_run", sharedRunSchema, { params: { token: shareToken } }),

    catalogue: () => request("presets", catalogueSchema, {}),

    preferences: (token) => request("auth_preferences_get", preferencesSchema, { token }),

    setPreferences: (token, preferences) =>
      request("auth_preferences_put", preferencesSchema, {
        method: "PUT",
        token,
        body: preferences,
      }),

    projectLimits: () => request("project_limits", projectLimitsSchema, {}),

    restoreProject: (token, id) =>
      request("project_restore", projectSchema, {
        params: { id },
        method: "POST",
        token,
      }),

    listRuns: (token, projectId) =>
      request("runs_list", z.array(runSummarySchema), {
        params: { id: projectId },
        token,
      }),

    getRun: (token, projectId, runId) =>
      request("run_get", runSchema, { params: { id: projectId, run: runId }, token }),

    deleteRun: (token, projectId, runId) =>
      request("run_delete", z.unknown(), {
        params: { id: projectId, run: runId },
        method: "DELETE",
        token,
      }).then(() => undefined),

    runInProject: (token, projectId, label, body) =>
      request("project_design", runAnswerSchema, {
        params: { id: projectId },
        method: "POST",
        token,
        body: { label, request: body },
      }),

    startRunJob: (token, projectId, label, body, idempotencyKey) =>
      request("jobs_create", runJobSchema, {
        params: { id: projectId },
        method: "POST",
        token,
        headers: { "idempotency-key": idempotencyKey },
        body: { label, request: body },
      }),

    getRunJob: (token, projectId, jobId) =>
      request("job_get", runJobSchema, { params: { id: projectId, job: jobId }, token }),

    cancelRunJob: (token, projectId, jobId) =>
      request("job_cancel", runJobSchema, {
        params: { id: projectId, job: jobId },
        method: "DELETE",
        token,
      }),

    endAllSessions: (token) =>
      request("auth_sessions_delete", endedSchema, { method: "DELETE", token }).then(
        (result) => result.ended,
      ),

    deleteAccount: (token, password) =>
      request("auth_account_delete", z.unknown(), {
        method: "DELETE",
        token,
        body: { password },
      }).then(() => undefined),
  };
}
