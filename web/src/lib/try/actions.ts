"use server";

/**
 * One design, run and thrown away.
 *
 * A server action rather than a route handler for the same reason as the rest:
 * the browser never learns the API's address, and Next checks the request
 * origin. Nothing here touches the session, because the whole point is that
 * there does not have to be one.
 */

import { api } from "@/lib/api";
import { describe } from "@/lib/api/error";
import type { RunResult } from "@/lib/api/types";
import type { DesignPayload } from "@/lib/contracts/design-requests";

export interface TryState {
  result?: RunResult;
  error?: string;
  /** Echoed back so a failed attempt does not also lose what was typed. */
  template?: string;
}

export async function tryDesignAction(_previous: TryState, form: FormData): Promise<TryState> {
  const template = String(form.get("template") ?? "").trim();

  if (!template) return { error: "Paste a sequence first." };

  try {
    const request: DesignPayload = {
      template,
      // Two rather than the usual five. This is a demonstration and a wall of
      // results is not a better one; the full number comes with a project.
      howMany: 2,
    };
    const result = await api.runDesign("standard-pcr", request);
    return { result, template };
  } catch (cause) {
    return { error: describe(cause), template };
  }
}
