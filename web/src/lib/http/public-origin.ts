/** Canonical parsing for the one public HTTP(S) origin of this deployment. */
export function parsePublicOrigin(raw: string): URL | null {
  const value = raw.trim();
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    if (url.username || url.password) return null;
    if (url.pathname !== "/" || url.search || url.hash) return null;
    return url;
  } catch {
    return null;
  }
}

/** Resolve a configured deployment origin, throwing on explicit misconfiguration. */
export function requirePublicOrigin(raw: string | undefined, fallback: string): URL {
  const candidate = raw?.trim() || fallback;
  const parsed = parsePublicOrigin(candidate);
  if (!parsed) {
    throw new Error(
      "NEXT_PUBLIC_SITE_URL must be an http(s) origin without credentials, path, query, or fragment",
    );
  }
  return parsed;
}

/** Origin-header serialization is stricter than configuration: no trailing slash. */
export function parseSerializedOrigin(raw: string): URL | null {
  const value = raw.trim();
  const parsed = parsePublicOrigin(value);
  return parsed && value === parsed.origin ? parsed : null;
}

const LOOPBACK_HOSTNAMES = new Set(["localhost", "127.0.0.1", "[::1]"]);

/**
 * Whether deployment security policy must assume HTTPS for the public origin.
 *
 * Production fails closed: an absent/malformed URL or an accidental cleartext
 * public hostname still requires Secure cookies/HSTS rather than silently
 * downgrading credential transport. The only supported production HTTP case is
 * the documented loopback bootstrap used behind SSH/VPN or an outer TLS tunnel.
 */
export function publicOriginRequiresSecureTransport(
  raw: string | undefined,
  nodeEnv: string | undefined,
): boolean {
  const configured = raw?.trim();
  if (!configured) return nodeEnv === "production";

  const origin = parsePublicOrigin(configured);
  if (!origin) return nodeEnv === "production";
  if (origin.protocol === "https:") return true;

  return nodeEnv === "production" && !LOOPBACK_HOSTNAMES.has(origin.hostname);
}
