/**
 * The headers every response carries, and the one that needs a fresh value each time.
 *
 * Named `proxy` because that is what Next 16 calls this hook; it was
 * `middleware` until the convention was renamed, and the old name now builds
 * with a deprecation warning. Worth following promptly rather than at the next
 * major: whatever else this file is, it is the only thing standing between an
 * injected script and a live session, and it should not be the part of the
 * build that is one release away from silently not running.
 *
 * Most security headers are constants and belong in `next.config.ts`, which is
 * where the rest of them are. This file exists for the one that cannot be a
 * constant: a Content-Security-Policy strict enough to be worth having needs a
 * nonce, and a nonce is only a nonce if it is different on every response.
 *
 * What the policy is actually defending against, in the order it matters here:
 *
 * A cross-site scripting hole anywhere in the app — ours or a dependency's —
 * normally means an attacker's script runs with the user's session. `script-src
 * 'nonce-…'` means inline scripts run only when this response vouched for them.
 * External application chunks are restricted to `'self'`; inline event-handler
 * attributes are disabled separately with `script-src-attr 'none'`.
 *
 * `frame-ancestors 'none'` stops the site being put in an invisible iframe over
 * a decoy page, which is how a click on something harmless becomes a click on
 * "delete this account".
 *
 * `form-action 'self'` stops an injected form posting a password somewhere else.
 *
 * `connect-src` is limited to this origin, so a script that did somehow run
 * could not send what it read anywhere useful. The API is deliberately not
 * named: by architecture the browser never talks to it — every call happens on
 * the server — so allowing it would only widen what an injected script may
 * reach.
 *
 * Two deliberate looser edges, both named rather than left to be discovered:
 * `style-src` allows `'unsafe-inline'` because Next injects style attributes
 * that cannot carry a nonce; and in development `script-src` allows `'unsafe-
 * eval'`, which the dev server's hot reloading requires and the production
 * build does not.
 */
import { NextResponse, type NextRequest } from "next/server";

import { SECURE_SESSION_COOKIES, SESSION_COOKIE } from "@/lib/auth/session-cookie";
import { shouldRejectBrowserMutationOrigin } from "@/lib/http/origin";

/**
 * The product surfaces, which no stranger may render.
 *
 * `/` is the dashboard; `/projects`, `/account`, `/organisation` and
 * `/modules` are the workbench around it. Everything else — the auth pages,
 * `/try` (which exists precisely so somebody can use the tool before an
 * account), share links (whose whole point is reaching people without one),
 * and the informational pages — stays open.
 */
const PRODUCT_ROUTE =
  /^\/(?:$|projects(?:\/|$)|account(?:\/|$)|organisation(?:\/|$)|modules(?:\/|$))/;

export default function proxy(request: NextRequest) {
  // Reject explicitly malformed/null/foreign browser mutation origins at the
  // earliest web boundary. An absent Origin is intentionally left alone so
  // framework/server initiated requests retain their own semantics; strict
  // Route Handlers separately require an expected Origin where appropriate.
  if (
    shouldRejectBrowserMutationOrigin(request.method, request.headers.get("origin"), request.url)
  ) {
    return new NextResponse(null, {
      status: 403,
      headers: { "Cache-Control": "no-store" },
    });
  }

  /*
   * The cheap half of the auth gate: a document on a product surface without
   * a session cookie cannot be anybody signed in, so it is answered with a
   * redirect before a single component renders — no flash of the workbench,
   * no catalogue fetches spent on a visitor who will be bounced anyway.
   *
   * Presence is not proof: an expired or forged cookie passes this line and
   * meets the real gate in the page itself, where `requireUser` asks the API.
   * This layer exists for speed and tidiness; that one exists to be right.
   */
  if (PRODUCT_ROUTE.test(request.nextUrl.pathname) && !request.cookies.has(SESSION_COOKIE)) {
    const signIn = request.nextUrl.clone();
    signIn.pathname = "/sign-in";
    signIn.search = "";
    // Preserve the full internal destination, including query state such as
    // comparison filters. Dropping it makes a successful sign-in land on a
    // different page than the one the visitor asked to open.
    signIn.searchParams.set("next", request.nextUrl.pathname + request.nextUrl.search);
    return NextResponse.redirect(signIn);
  }

  const nonce = crypto.randomUUID().replace(/-/g, "");
  const development = process.env.NODE_ENV !== "production";

  const policy = [
    "default-src 'self'",
    // Inline scripts require this response nonce. External Next chunks may load
    // only from this origin; no script-level unsafe-inline escape hatch exists.
    `script-src 'self' 'nonce-${nonce}' ${development ? "'unsafe-eval'" : ""}`.trim(),
    "script-src-attr 'none'",
    // Next writes style attributes it cannot nonce. Narrower than script-src
    // matters far more, and a style injection is not a session theft.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self'${development ? " ws: wss:" : ""}`,
    // Nothing here embeds anything, and nothing should embed this.
    "frame-ancestors 'none'",
    "frame-src 'none'",
    "object-src 'none'",
    // An injected form cannot post the password somewhere else.
    "form-action 'self'",
    "base-uri 'self'",
    // Upgrade mixed-content requests when the public origin is HTTPS. The
    // only supported HTTP bootstrap is host-loopback behind SSH/VPN/tunnelling,
    // not a cleartext public-Internet deployment.
    ...(SECURE_SESSION_COOKIES ? ["upgrade-insecure-requests"] : []),
  ].join("; ");

  // Both are forwarded on the *request*, and that is what makes this work:
  // Next reads the policy back off the incoming headers and stamps the nonce
  // onto every script tag it renders itself. Without the forwarded policy the
  // nonce would be minted, sent, and matched by nothing — which is a strict CSP
  // that blocks the application rather than an attacker.
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("x-pcr-pathname", request.nextUrl.pathname);
  headers.set("x-pcr-destination", request.nextUrl.pathname + request.nextUrl.search);
  headers.set("Content-Security-Policy", policy);

  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

export const config = {
  matcher: [
    /*
     * Everything except the things that are not documents: static assets, the
     * image optimiser, and the favicon. A policy on a JavaScript chunk protects
     * nothing — the header only means anything on the page that loads it — and
     * running this on every asset costs a middleware invocation each time.
     *
     * Document prefetches are intentionally *not* excluded: `(app)/layout`
     * uses the pathname/destination headers stamped above to distinguish public
     * pages from authenticated workbench pages. Skipping the proxy for a
     * prefetch would classify that render using missing context.
     */
    {
      source: "/((?!_next/static|_next/image|favicon.ico|icon.png).*)",
    },
  ],
};
