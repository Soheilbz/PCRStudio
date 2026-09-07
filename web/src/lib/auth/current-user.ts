/**
 * Who is asking, for the current render.
 *
 * Wrapped in `cache` so a layout, a page and a component asking the same
 * question during one render cost one call rather than three.
 */
import "server-only";

import { cache } from "react";
import { redirect } from "next/navigation";

import { api, PcrStudioError } from "@/lib/api";
import type { User } from "@/lib/api/types";

import { readSessionToken } from "./session";

export const currentUser = cache(async (): Promise<User | null> => {
  const token = await readSessionToken();
  if (!token) return null;

  try {
    return await api.currentUser(token);
  } catch (cause) {
    // Only an invalid identity means "signed out". A database/API outage is a
    // service failure, not evidence that the session ended; turning it into
    // null would redirect a signed-in person to the credential form and hide
    // the outage behind a misleading authentication journey.
    if (
      cause instanceof PcrStudioError &&
      ["sessionEnded", "noSuchUser"].includes(cause.kind ?? "")
    ) {
      return null;
    }
    throw cause;
  }
});

/**
 * The gate every product page opens with.
 *
 * Signed in, this is just `currentUser()` with a non-null answer. Not signed
 * in, the render never happens: the visitor is sent to sign in first, and the
 * page they wanted rides along in `?next=` so the journey resumes after the
 * form. The proxy applies a cheaper version of the same rule (cookie present
 * or not) to save the round trip; this one is authoritative, because it asks
 * the API whether the session is real rather than whether a cookie exists.
 */
export async function requireUser(destination: string): Promise<User> {
  const user = await currentUser();
  if (!user) redirect(`/sign-in?next=${encodeURIComponent(destination)}`);
  return user;
}
