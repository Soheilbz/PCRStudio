import { parsePublicOrigin, parseSerializedOrigin } from "@/lib/http/public-origin";

/**
 * Classify the browser Origin header against the public application origin.
 *
 * This is the single authority used by strict Route Handlers and by the early
 * proxy mutation guard. Keeping parsing/comparison here prevents subtly
 * different CSRF rules from emerging at different web boundaries.
 */
export type BrowserOriginState = "missing" | "expected" | "invalid" | "foreign";

export function classifyBrowserOrigin(
  originHeader: string | null,
  requestUrl: string,
  configuredSiteUrl: string | undefined = process.env.NEXT_PUBLIC_SITE_URL,
): BrowserOriginState {
  if (!originHeader) return "missing";

  const supplied = parseSerializedOrigin(originHeader);
  if (!supplied) return "invalid";

  const configured = configuredSiteUrl?.trim();
  let expected: URL;
  if (configured) {
    const parsed = parsePublicOrigin(configured);
    if (!parsed) return "invalid";
    expected = parsed;
  } else {
    try {
      expected = new URL(requestUrl);
    } catch {
      return "invalid";
    }
    if (expected.protocol !== "http:" && expected.protocol !== "https:") return "invalid";
    if (expected.username || expected.password || expected.origin === "null") return "invalid";
  }

  return supplied.origin === expected.origin ? "expected" : "foreign";
}

/** Strict browser-origin predicate for state-changing Route Handlers. */
export function hasExpectedBrowserOrigin(
  originHeader: string | null,
  requestUrl: string,
  configuredSiteUrl: string | undefined = process.env.NEXT_PUBLIC_SITE_URL,
): boolean {
  return classifyBrowserOrigin(originHeader, requestUrl, configuredSiteUrl) === "expected";
}

const BROWSER_MUTATION_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Reject an explicitly supplied bad browser Origin before it reaches Next's
 * Server Action machinery. Missing Origin is intentionally not rejected here:
 * Route Handlers may apply the strict predicate above, while framework/server
 * initiated requests retain their own semantics.
 */
export function shouldRejectBrowserMutationOrigin(
  method: string,
  originHeader: string | null,
  requestUrl: string,
  configuredSiteUrl: string | undefined = process.env.NEXT_PUBLIC_SITE_URL,
): boolean {
  if (!BROWSER_MUTATION_METHODS.has(method.toUpperCase())) return false;
  const state = classifyBrowserOrigin(originHeader, requestUrl, configuredSiteUrl);
  return state !== "missing" && state !== "expected";
}
