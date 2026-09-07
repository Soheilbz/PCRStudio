import { publicOriginRequiresSecureTransport } from "@/lib/http/public-origin";

/**
 * Session-cookie transport policy shared by the proxy and server actions.
 *
 * Public production is HTTPS in PCRStudio. The repository retains only a
 * host-loopback HTTP bootstrap for SSH/VPN or TLS-terminating managed tunnels.
 * Browsers reject `Secure`/`__Host-` cookies on a local cleartext origin, so
 * cookie attributes still follow the configured origin rather than NODE_ENV.
 *
 * When the public origin is absent or malformed in a production process we
 * fail closed and require secure cookies. Development keeps the historical
 * localhost behaviour.
 *
 * This exported decision is the single cookie-transport view of the shared
 * public-origin authority.
 */
export const SECURE_SESSION_COOKIES = publicOriginRequiresSecureTransport(
  process.env.NEXT_PUBLIC_SITE_URL,
  process.env.NODE_ENV,
);

/**
 * The session cookie name.
 *
 * `__Host-` is the strongest browser-enforced scope, but it is valid only for
 * Secure cookies. The loopback-only HTTP bootstrap therefore uses the
 * unprefixed host-only name while retaining HttpOnly, SameSite and Path=/.
 */
export const SESSION_COOKIE = SECURE_SESSION_COOKIES ? "__Host-pcr_session" : "pcr_session";

/** Same transport rule for the short-lived recovery-code handoff flag. */
export const PENDING_CODE_COOKIE = SECURE_SESSION_COOKIES
  ? "__Host-pcr_pending_code"
  : "pcr_pending_code";

/** Every historical/current transport name, for destructive cleanup only. */
export const SESSION_COOKIE_NAMES = ["__Host-pcr_session", "pcr_session"] as const;

/** Every historical/current pending-code flag name, for destructive cleanup only. */
export const PENDING_CODE_COOKIE_NAMES = ["__Host-pcr_pending_code", "pcr_pending_code"] as const;
