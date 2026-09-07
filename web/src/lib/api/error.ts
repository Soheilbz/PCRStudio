/** A failure from the core, from an account, from a project store, or from the transport. */
import {
  accountErrorSchema,
  coreErrorSchema,
  projectErrorSchema,
  type AccountError,
  type CoreError,
  type ProjectError,
} from "./types";
import { z } from "zod";

const transientFailureSchema = z.object({
  kind: z.enum(["storeFailure", "serviceUnavailable"]),
  detail: z.string(),
  code: z.string().optional(),
  fieldPath: z.string().nullable().optional(),
  stage: z.string().nullable().optional(),
  retryable: z.boolean().optional(),
  requestId: z.string().nullable().optional(),
});

/** Everything the API can name as a reason for refusing. */
export type ApiFailure = CoreError | AccountError | ProjectError;

export class PcrStudioError extends Error {
  /** The structured cause when the API produced one, otherwise `null`. */
  readonly cause_: ApiFailure | null;

  constructor(message: string, cause_: ApiFailure | null = null, options?: ErrorOptions) {
    super(message, options);
    this.name = "PcrStudioError";
    this.cause_ = cause_;
  }

  /** The machine-readable reason, when there was one. */
  get kind(): ApiFailure["kind"] | null {
    return this.cause_?.kind ?? null;
  }

  /** Stable server code for telemetry/support correlation. */
  get code(): string | null {
    return this.cause_?.code ?? null;
  }

  /** Input field associated with the refusal, when the server knows it. */
  get fieldPath(): string | null {
    return this.cause_?.fieldPath ?? null;
  }

  /** Processing stage that raised the refusal, when known. */
  get stage(): string | null {
    return this.cause_?.stage ?? null;
  }

  /** Whether retrying the same request later is meaningful. */
  get retryable(): boolean {
    return this.cause_?.retryable ?? false;
  }

  /** Correlation id matching the Rust `x-request-id` response header. */
  get requestId(): string | null {
    return this.cause_?.requestId ?? null;
  }

  /** Kept for the module pages, which branch on the core's vocabulary. */
  get core(): CoreError | null {
    const kinds = [
      "unknownProfile",
      "duplicateProfile",
      "unknownEngine",
      "incompatibleModifier",
      "invalidRequest",
      "notImplemented",
      "toolFailed",
      "workerBusy",
      "cancelled",
    ];
    return this.cause_ && kinds.includes(this.cause_.kind) ? (this.cause_ as CoreError) : null;
  }

  /** The project store's own reason, when the refusal was about a project. */
  get project(): ProjectError | null {
    const kinds = [
      "notFound",
      "invalidName",
      "invalidData",
      "tooManyProjects",
      "storageLimit",
      "conflict",
      "notAnExport",
      "store",
    ];
    return this.cause_ && kinds.includes(this.cause_.kind) ? (this.cause_ as ProjectError) : null;
  }

  /** True when this module exists but has no implementation behind it yet. */
  get isNotImplemented(): boolean {
    return this.kind === "notImplemented";
  }
}

/**
 * Turn whatever a transport threw into a `PcrStudioError`.
 *
 * The API answers a failed request with a tagged union, but a proxy, a timeout
 * or a crash can produce a plain string or a network error instead — so both
 * paths have to be handled.
 */
export function toPcrStudioError(cause: unknown): PcrStudioError {
  const core = coreErrorSchema.safeParse(cause);
  if (core.success) {
    return new PcrStudioError(describeCore(core.data), core.data, { cause });
  }

  const account = accountErrorSchema.safeParse(cause);
  if (account.success) {
    return new PcrStudioError(describeAccount(account.data), account.data, { cause });
  }

  const project = projectErrorSchema.safeParse(cause);
  if (project.success) {
    return new PcrStudioError(describeProject(project.data), project.data, { cause });
  }

  // These are transport-level failures, not domain enum members: the Rust
  // handlers redact database details and the limiter reports an unavailable
  // dependency. Normalize both to the existing store vocabulary so forms get
  // a useful message instead of an "unrecognised shape" parsing error.
  const transient = transientFailureSchema.safeParse(cause);
  if (transient.success) {
    const message =
      transient.data.kind === "storeFailure"
        ? transient.data.detail
        : "The service is temporarily unavailable. Try again in a moment.";
    return new PcrStudioError(
      message,
      {
        kind: "store",
        detail: transient.data.detail,
        code: transient.data.code,
        fieldPath: transient.data.fieldPath,
        stage: transient.data.stage,
        retryable: transient.data.retryable,
        requestId: transient.data.requestId,
      },
      { cause },
    );
  }

  if (typeof cause === "string") {
    return new PcrStudioError(cause, null, { cause });
  }
  if (cause instanceof Error) {
    return new PcrStudioError(cause.message, null, { cause });
  }
  return new PcrStudioError("The server failed without saying why.", null, { cause });
}

function describeCore(error: CoreError): string {
  switch (error.kind) {
    case "unknownProfile":
      return `No design module is registered under the id "${error.detail}".`;
    case "duplicateProfile":
      return `Two design modules claim the id "${error.detail}".`;
    // The next two are refused when the registry is built, so reaching a
    // browser means the running build is misconfigured rather than misused.
    case "unknownEngine":
      return `A module names an engine this build does not have: ${error.detail}`;
    case "incompatibleModifier":
      return error.detail;
    case "invalidRequest":
      return error.detail;
    case "notImplemented":
      return `The ${error.detail} engine is registered but not written yet.`;
    // Never the person's fault, so the message must not suggest they change
    // what they asked for.
    case "toolFailed":
      return `The design tool could not complete this run: ${error.detail}`;
    case "workerBusy":
      return "The design service is busy right now. Try again shortly.";
    case "cancelled":
      return "The running design was cancelled.";
  }
}

function describeAccount(error: AccountError): string {
  switch (error.kind) {
    case "emailTaken":
      return "That email address already has an account.";
    case "invalidCredentials":
      // Deliberately does not say which half was wrong.
      return "That email and password do not match an account.";
    case "sessionEnded":
      return "Your session has ended. Sign in again.";
    case "noSuchUser":
      return "That account no longer exists.";
    case "badRequest":
      return error.detail;
    case "store":
      return "The account store is not answering. Try again in a moment.";
    case "recoveryLocked":
      // Different words from a wrong code on purpose. Telling somebody their
      // correct code was wrong is how they conclude the account is gone.
      return (
        "Too many recovery attempts on this account. Wait an hour and try " +
        "again — the code itself is still good."
      );
    case "invalidEmail":
    case "weakPassword":
    case "invalidName":
    case "tooManyAttempts":
    case "tooManyRequests":
      return error.detail;
  }
}

function describeProject(error: ProjectError): string {
  switch (error.kind) {
    case "notFound":
      // One answer for both reasons, here as on the wire: telling the two apart
      // would say whether a project exists.
      return "No such project, or it belongs to a different account.";
    case "invalidName":
    case "invalidData":
    case "tooManyProjects":
    case "storageLimit":
    case "conflict":
    case "notAnExport":
      return error.detail;
    case "store":
      return "The project store is not answering. Try again in a moment.";
  }
}

/**
 * An unknown throw, turned into something a person can read.
 *
 * There were four copies of this, and two of them had already drifted — most
 * said "Something went wrong. Try again." and the loader said "The design core
 * did not answer." That second wording is right where it is: a page that cannot
 * reach the core has a different problem from a form that failed to save, and
 * telling somebody to try again is poor advice when the core is down.
 *
 * So the difference stays and the duplication goes: the fallback is the
 * argument, and the part that never varies — pulling a message out of whatever
 * was thrown — is written once.
 */
export function describe(cause: unknown, fallback = "Something went wrong. Try again."): string {
  return cause instanceof PcrStudioError || cause instanceof Error ? cause.message : fallback;
}
