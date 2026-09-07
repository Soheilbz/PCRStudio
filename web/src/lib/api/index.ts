/**
 * The one place that decides how the interface reaches the core.
 *
 * Everything above this file works against `Transport`, so moving the core
 * somewhere else is a change here and nowhere else.
 */
import { createHttpTransport } from "./http";
import type { Transport } from "./transport";

export const api: Transport = createHttpTransport();

export { PcrStudioError, toPcrStudioError } from "./error";
export type { Transport } from "./transport";
export * from "./types";
