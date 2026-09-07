/**
 * The session cookie: the one piece of state the browser is trusted with.
 *
 * It holds an opaque token, never a user id or anything derived from one. The
 * server looks it up on every request, which is what makes signing out
 * everywhere take effect immediately rather than at the next expiry.
 */
import "server-only";

import { createHash, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

import {
  PENDING_CODE_COOKIE,
  PENDING_CODE_COOKIE_NAMES,
  SECURE_SESSION_COOKIES,
  SESSION_COOKIE,
  SESSION_COOKIE_NAMES,
} from "./session-cookie";

export { SESSION_COOKIE };

export async function readSessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

export async function writeSessionToken(token: string, maxAgeSeconds?: number): Promise<void> {
  const store = await cookies();
  for (const name of SESSION_COOKIE_NAMES) {
    if (name !== SESSION_COOKIE) store.delete(name);
  }
  store.set(SESSION_COOKIE, token, {
    httpOnly: true,
    // Script on the page cannot read it, so an injected script cannot steal it.
    sameSite: "lax",
    // Lax rather than strict so following a link from an email still arrives
    // signed in; the actions themselves are origin-checked by Next.
    secure: SECURE_SESSION_COOKIES,
    path: "/",
    // With a max age the cookie survives restarts for the session's length;
    // without one it is a browser-session cookie, gone when the browser
    // closes — which is what "Remember me" left unchecked means. The token
    // itself lives exactly as long as the API says either way; this only
    // decides whether the browser keeps holding it.
    ...(maxAgeSeconds === undefined ? {} : { maxAge: maxAgeSeconds }),
  });
}

export async function clearSessionToken(): Promise<void> {
  const store = await cookies();
  for (const name of SESSION_COOKIE_NAMES) store.delete(name);
}

/**
 * A five-minute flag meaning "a recovery code was just minted and is on
 * screen".
 *
 * Setting the session cookie inside a server action makes the framework answer
 * with a fresh render of the current route — and both pages that mint codes
 * bounce signed-in visitors, which would throw away the action's return value
 * before it is ever displayed. The flag lets that one refreshed render through
 * (the client component keeps its state across a refresh; only a redirect
 * discards it), and `clearPendingCodeFlag` removes it the moment Continue is
 * clicked. Worst case if that never happens: it expires, unread by anything.
 *
 * The value is not a constant but a digest of the session token it belongs
 * to, and `pendingCodeFlagIsValid` recomputes rather than trusts: a cookie
 * hand-typed in a browser's devtools then names nothing, so the guard keeps
 * bouncing whoever set it. The flag is still only ever a UX exception —
 * passing it shows a form whose submission answers for itself — but an
 * exception that cannot be forged casually is worth the one hash call.
 */
function pendingCodeFlagValue(token: string): string {
  return createHash("sha256").update(token).digest("hex").slice(0, 32);
}

export async function writePendingCodeFlag(token: string): Promise<void> {
  const store = await cookies();
  for (const name of PENDING_CODE_COOKIE_NAMES) {
    if (name !== PENDING_CODE_COOKIE) store.delete(name);
  }
  store.set(PENDING_CODE_COOKIE, pendingCodeFlagValue(token), {
    httpOnly: true,
    sameSite: "lax",
    secure: SECURE_SESSION_COOKIES,
    path: "/",
    maxAge: 300,
  });
}

export async function pendingCodeFlagIsValid(): Promise<boolean> {
  const token = await readSessionToken();
  if (!token) return false;

  const store = await cookies();
  const presented = store.get(PENDING_CODE_COOKIE)?.value;
  if (!presented) return false;

  // Digest comparison, constant-time on principle even though the upside of
  // guessing this value is one render of a page that checks the answer again.
  const expected = Buffer.from(pendingCodeFlagValue(token), "hex");
  const actual = Buffer.from(presented, "hex");
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}

export async function clearPendingCodeFlag(): Promise<void> {
  const store = await cookies();
  for (const name of PENDING_CODE_COOKIE_NAMES) store.delete(name);
}
