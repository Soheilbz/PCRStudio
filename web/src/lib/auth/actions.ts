"use server";

/**
 * Everything that changes an account.
 *
 * Server actions rather than route handlers: the browser never learns the API's
 * address, Next checks the request origin for us, and the same function can set
 * the session cookie and revalidate the pages that depend on it.
 */

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { describe, PcrStudioError, type ApiFailure } from "@/lib/api/error";
import type { Preferences } from "@/lib/api/types";

import { currentUser } from "./current-user";
import { isSafeDestination } from "./destination";
import {
  clearPendingCodeFlag,
  clearSessionToken,
  readSessionToken,
  writePendingCodeFlag,
  writeSessionToken,
} from "./session";

/** What a form gets back. `message` is shown on success, `error` on failure. */
export interface FormState {
  error?: string;
  /**
   * The API's machine-readable reason for `error`, when there was one.
   *
   * Forms branch on this rather than on words in the message: a banner that
   * fires because a sentence happens to contain "wait" will fire for the
   * wrong sentence eventually.
   */
  errorKind?: ApiFailure["kind"];
  message?: string;
  /**
   * A recovery code, on the two actions that mint one.
   *
   * Returned rather than redirected past, and never written anywhere on the
   * way. It is stored hashed, so this is the only moment it exists in a form
   * anybody can read — putting it in a cookie or a query string to survive a
   * redirect would mean writing the one secret that cannot be reissued into
   * the two places most likely to be logged.
   */
  recoveryCode?: string;
}

/**
 * One failure from an API call, shaped for a form.
 *
 * The only path any catch below should take: it keeps the wording decision in
 * the error describer and the branching decision with the form that knows its
 * own context, and stops both drifting apart copy by copy.
 */
function formError(cause: unknown): FormState {
  const kind = cause instanceof PcrStudioError ? cause.kind : null;
  return { error: describe(cause), ...(kind ? { errorKind: kind } : {}) };
}

function field(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value : "";
}

/**
 * Where to go after signing in.
 *
 * The rule lives in `./destination` so the sign-in and sign-up pages can apply
 * the same one before the value ever reaches a client component.
 */
function safeDestination(raw: string): string {
  return isSafeDestination(raw) ? raw : "/";
}

export async function signUpAction(_previous: FormState, form: FormData): Promise<FormState> {
  let recoveryCode: string | undefined;

  try {
    const session = await api.register(
      field(form, "email"),
      field(form, "displayName"),
      field(form, "password"),
    );
    await writeSessionToken(session.token, session.expiresIn);
    // Minted a code that must reach the screen: flag off the guard that the
    // framework's post-action refresh would otherwise trip (see below).
    await writePendingCodeFlag(session.token);
    recoveryCode = session.recoveryCode;
  } catch (cause) {
    return formError(cause);
  }

  /*
   * Deliberately not a redirect, and deliberately no revalidatePath.
   *
   * Everywhere else, signing up lands you where you were going. Here there is
   * one string that will never be shown again, and redirecting past it means
   * every account is created with a recovery code nobody ever saw — which is
   * the same as having none, discovered a year later by somebody locked out.
   *
   * The session cookie is already set, so nothing is lost by stopping here:
   * they are signed in, and the next click takes them on.
   *
   * The refresh that setting a cookie provokes is survived rather than
   * prevented: the page guard reads PENDING_CODE_COOKIE and lets this one
   * render through, so the form keeps its state and shows the code. Continue
   * clears the flag on the way out.
   */
  return { recoveryCode };
}

/**
 * Whether the signed-in account has a recovery code.
 *
 * Returns null when there is nobody signed in or the store cannot be reached,
 * which the card words differently from "asked, and there is none" — the
 * second is a real gap somebody should close, and the first is not.
 */
export async function recoveryStatus() {
  const token = await readSessionToken();
  if (!token) return null;
  try {
    return await api.recoveryStatus(token);
  } catch {
    // The account page is still useful when this secondary lookup is down,
    // but it must not turn an unknown answer into "a code exists".
    return { unavailable: true as const };
  }
}

/**
 * Save what somebody has told us about how they work.
 *
 * The whole object each time, because a merge cannot express "unset" — and a
 * settings screen that can turn something on and never off is one people stop
 * trusting.
 */
export async function savePreferencesAction(
  preferences: Preferences,
): Promise<{ saved?: Preferences; error?: string }> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  try {
    const saved = await api.setPreferences(token, preferences);
    // The reaction step reads this when a project starts, so the pages that
    // could be showing a stale default are the ones that have to be refreshed.
    revalidatePath("/projects", "layout");
    revalidatePath("/account");
    return { saved };
  } catch (cause) {
    return formError(cause);
  }
}

/** Set a new password from a recovery code, for somebody locked out. */
export async function recoverAction(_previous: FormState, form: FormData): Promise<FormState> {
  let recoveryCode: string | undefined;

  try {
    const session = await api.recover(
      field(form, "email"),
      field(form, "recoveryCode"),
      field(form, "newPassword"),
    );
    // Signed in immediately: somebody who has just proved who they are should
    // not then be asked to prove it again.
    await writeSessionToken(session.token, session.expiresIn);
    // Same handoff as signUpAction: the replacement code must survive the
    // refresh that writing a session cookie just caused.
    await writePendingCodeFlag(session.token);
    recoveryCode = session.recoveryCode;
  } catch (cause) {
    return formError(cause);
  }

  // No revalidatePath here either: as in signUpAction, refreshing /recover
  // would trip its signed-in guard and discard the replacement code below.
  // The used code is spent and this is its replacement — shown for the same
  // reason, and with the same one chance.
  return { recoveryCode };
}

/**
 * Leave the one-time recovery-code screen without racing cookie cleanup against
 * client-side navigation. The clear and redirect are one server action, so the
 * guard exception is retired before the next page is requested.
 */
export async function continueAfterRecoveryCodeAction(destination: string): Promise<void> {
  await clearPendingCodeFlag();
  redirect(safeDestination(destination));
}

/** Replace the recovery code, from the account page. */
export async function reissueRecoveryCodeAction(
  _previous: FormState,
  form: FormData,
): Promise<FormState> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  try {
    const { recoveryCode } = await api.reissueRecoveryCode(token, field(form, "password"));
    revalidatePath("/account");
    return { recoveryCode };
  } catch (cause) {
    return formError(cause);
  }
}

export async function signInAction(_previous: FormState, form: FormData): Promise<FormState> {
  const destination = safeDestination(field(form, "next"));
  // The choice is sent to the API as well as applied to the cookie. An
  // unchecked sign-in therefore gets both a browser-session cookie and a short
  // server-side token; checked gets the longer remembered lifetime.
  const remember = field(form, "remember") === "on";

  try {
    const session = await api.login(field(form, "email"), field(form, "password"), remember);
    await writeSessionToken(session.token, remember ? session.expiresIn : undefined);
  } catch (cause) {
    return formError(cause);
  }

  revalidatePath("/", "layout");
  redirect(destination);
}

export async function signOutAction(): Promise<void> {
  const token = await readSessionToken();
  if (token) {
    // If the API is unreachable the cookie still goes: from the visitor's side
    // signing out must always work.
    await api.logout(token).catch(() => undefined);
  }
  await clearSessionToken();

  revalidatePath("/", "layout");
  // Back to the sign-in page rather than the dashboard. Signing out is not a
  // way of leaving; it is a way of stopping being one person, and the next
  // thing anybody does is either sign in again or hand the machine over.
  redirect("/sign-in?signedOut=1");
}

export async function renameAction(_previous: FormState, form: FormData): Promise<FormState> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  try {
    const user = await api.rename(token, field(form, "displayName"));
    revalidatePath("/", "layout");
    return { message: `You will be shown as ${user.displayName}.` };
  } catch (cause) {
    return formError(cause);
  }
}

export async function changeEmailAction(_previous: FormState, form: FormData): Promise<FormState> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  try {
    const user = await api.changeEmail(
      token,
      field(form, "currentPassword"),
      field(form, "newEmail"),
    );
    revalidatePath("/", "layout");
    revalidatePath("/account");
    return {
      message: `Sign-in email is ${user.email}. When the address changes, other signed-in browsers are signed out.`,
    };
  } catch (cause) {
    return formError(cause);
  }
}

export async function changePasswordAction(
  _previous: FormState,
  form: FormData,
): Promise<FormState> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  const next = field(form, "newPassword");
  if (next !== field(form, "confirmPassword")) {
    return { error: "The two new passwords do not match." };
  }

  try {
    await api.changePassword(token, field(form, "currentPassword"), next);
    return {
      message: "Password changed. Any other browser signed in as you has been signed out.",
    };
  } catch (cause) {
    return formError(cause);
  }
}

export async function endAllSessionsAction(
  _previous: FormState,
  _form: FormData,
): Promise<FormState> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  try {
    // Unlike an ordinary local sign-out, this action makes a security claim
    // about *other* browsers. Never clear the local cookie and imply success
    // unless the API has confirmed that every server-side session is gone.
    await api.endAllSessions(token);
  } catch (cause) {
    return formError(cause);
  }

  await clearSessionToken();
  revalidatePath("/", "layout");
  redirect("/sign-in?signedOut=all");
}

export async function deleteAccountAction(
  _previous: FormState,
  form: FormData,
): Promise<FormState> {
  const token = await readSessionToken();
  if (!token) return { error: "Your session has ended. Sign in again." };

  const user = await currentUser();
  if (!user) return { error: "Your session has ended. Sign in again." };
  if (field(form, "confirm").trim() !== user.email) {
    return { error: "Type your email address exactly to confirm." };
  }

  try {
    await api.deleteAccount(token, field(form, "password"));
  } catch (cause) {
    return formError(cause);
  }

  await clearSessionToken();
  revalidatePath("/", "layout");
  redirect("/");
}
