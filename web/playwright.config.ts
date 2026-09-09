import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectBrowsers = resolve(projectRoot, ".local", "playwright-browsers");
if (!process.env.PLAYWRIGHT_BROWSERS_PATH && existsSync(projectBrowsers)) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = projectBrowsers;
}

/**
 * End-to-end tests for the browser surface only.
 *
 * The suite is written to pass with the Rust core down: every page in the app
 * degrades to an empty or error state rather than crashing, and that is part
 * of the contract these tests pin down. Flows that genuinely need the core are
 * gated behind PCR_E2E_WITH_API.
 */
const externalBaseURL = process.env.PCR_E2E_BASE_URL?.trim();
const baseURL = externalBaseURL || "http://localhost:3100";
const configuredSiteURL = process.env.NEXT_PUBLIC_SITE_URL?.trim();

/**
 * A built server's public origin is part of its runtime contract. When E2E
 * points at an already-built server, reject a target that could make browser
 * mutations look like product failures because Next's origin guard is doing
 * its job. The comparison is intentionally opt-in: a development server with
 * no explicit public-origin configuration keeps its normal localhost default.
 */
if (externalBaseURL && configuredSiteURL) {
  let targetOrigin;
  let configuredOrigin;
  try {
    targetOrigin = new URL(baseURL).origin;
    configuredOrigin = new URL(configuredSiteURL).origin;
  } catch {
    throw new Error("PCR_E2E_BASE_URL and NEXT_PUBLIC_SITE_URL must both be valid absolute URLs");
  }
  if (targetOrigin !== configuredOrigin) {
    throw new Error(
      `E2E origin mismatch: target ${targetOrigin} does not match built public origin ${configuredOrigin}`,
    );
  }
}

export default defineConfig({
  testDir: "./e2e",
  // Next's development server may compile a route on first navigation. Keep
  // that cold-start cost out of the product assertions while retaining a
  // finite bound for genuinely hung pages.
  // A cold Next route can compile on first navigation. The page assertions
  // already wait for their semantic target, so keep the timeout large enough
  // for that one-time compile rather than classifying a healthy route as flaky.
  timeout: 60_000,
  fullyParallel: true,
  // The full-stack cases share one API process. Its abuse limiter is
  // intentionally process-local, so running the account journeys in parallel
  // makes the test outcome depend on scheduling rather than product behavior.
  // Browser-only coverage remains fully parallel; the real-core run is
  // deliberately serial and still fast enough for CI.
  workers: process.env.PCR_E2E_WITH_API ? 1 : undefined,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["html"], ["list"]] : [["list"]],
  use: {
    // A dedicated port rather than the usual 3000: a developer host may keep other
    // dev servers there, and reusing whatever answers would test the wrong
    // app. `localhost` rather than 127.0.0.1 because the dev server blocks
    // static chunks from origins outside its allowlist, which would leave the
    // client half of every page unhydrated.
    baseURL,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    { name: "mobile-chrome", use: { ...devices["Pixel 7"] } },
    { name: "mobile-safari", use: { ...devices["iPhone 15"] } },
  ],
  webServer: externalBaseURL
    ? undefined
    : {
        // Local development boots a dev server; release qualification points
        // Playwright at the already-running qualified stack instead.
        command:
          process.env.PCR_E2E_WEB_COMMAND ?? "node node_modules/next/dist/bin/next dev --port 3100",
        url: "http://localhost:3100",
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
