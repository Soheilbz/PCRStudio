import type { NextConfig } from "next";

import { MAX_ACTION_BYTES } from "./src/lib/limits";
import { publicOriginRequiresSecureTransport } from "./src/lib/http/public-origin";

/**
 * The security headers that are the same on every response.
 *
 * The one that is not — Content-Security-Policy, which needs a fresh nonce each
 * time — is set in `src/proxy.ts`. These are here because a constant in
 * the config is cheaper than a constant recomputed per request, and because a
 * header nobody has to think about is a header that does not get forgotten.
 *
 * Each of these closes something specific rather than being on because a
 * checklist said so:
 */
const PUBLIC_ORIGIN_IS_HTTPS = publicOriginRequiresSecureTransport(
  process.env.NEXT_PUBLIC_SITE_URL,
  process.env.NODE_ENV,
);

const SECURITY_HEADERS = [
  ...(PUBLIC_ORIGIN_IS_HTTPS
    ? [
        {
          /*
           * HSTS is meaningful only on the TLS deployment. PCRStudio keeps a
           * loopback-only HTTP bootstrap for SSH/VPN or managed TLS tunnels;
           * it is never a supported cleartext public deployment. Caddy adds
           * the same header at the HTTPS edge, and this copy protects direct
           * Next responses as well.
           */
          key: "Strict-Transport-Security",
          value: "max-age=31536000",
        },
      ]
    : []),
  {
    /*
     * Stops the browser guessing that a file we served as JSON is really HTML
     * and running it. A sequence somebody pastes is user content, and user
     * content that gets sniffed into a document is an XSS hole.
     */
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    /*
     * The old clickjacking defence. `frame-ancestors` in the CSP supersedes it
     * everywhere modern, and this stays for the browsers that only understand
     * this one.
     */
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    /*
     * A project id in a URL is not secret, but it is somebody's work. This
     * sends the full path only within this site, and bare origin off it — so a
     * link somebody follows outward does not carry which project they had open.
     */
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    /*
     * Nothing here needs a camera, a microphone, a location or a payment
     * handler, so nothing here — or anything that ends up embedded in it — may
     * ask for one.
     */
    key: "Permissions-Policy",
    value: [
      "accelerometer=()",
      "camera=()",
      "geolocation=()",
      "gyroscope=()",
      "magnetometer=()",
      "microphone=()",
      "payment=()",
      "usb=()",
      "interest-cohort=()",
    ].join(", "),
  },
  {
    /*
     * Keeps this origin out of any browsing-context group it did not choose to
     * join, which is what closes the cross-origin side channels that made
     * Spectre-class attacks reachable from a page.
     */
    key: "Cross-Origin-Opener-Policy",
    value: "same-origin",
  },
  {
    /* Nothing here is meant to be embedded by another site. */
    key: "Cross-Origin-Resource-Policy",
    value: "same-origin",
  },
];

const nextConfig: NextConfig = {
  // Emits a self-contained server bundle so the Docker image does not need to
  // carry node_modules.
  output: "standalone",
  // The all-in-one launcher gives each concurrently running local listener its
  // own Turbopack state. Two checkouts/processes must never mutate one cache.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  // Links are checked against the routes that actually exist, at build time.
  typedRoutes: true,
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    // Use Next's compiler API for type checking; the CLI path in Next
    // 16.3.3 cannot parse the pinned TypeScript 5.9 --showConfig payload.
    useTypeScriptCli: false,
    serverActions: {
      /*
       * Next defaults this to 1 MB, and everything here goes through a server
       * action. The upload box accepts 8 MB and the API allows 24, so the
       * unconfigured middle was the real ceiling — and it failed with a bare
       * 500 that lost whatever had been pasted. Imported rather than written
       * again so the three cannot disagree a second time.
       */
      bodySizeLimit: MAX_ACTION_BYTES,
    },
  },

  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
};

export default nextConfig;
