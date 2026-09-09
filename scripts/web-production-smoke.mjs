#!/usr/bin/env node
/**
 * Verify the public Next.js production surface and its response budget.
 *
 * This HTTP-level gate proves that the built server serves every public route
 * without depending on the scientific engine/API. The API has its own
 * readiness contract and image qualification gate.
 */

const argument = (name) => {
  const prefix = name + "=";
  const value = process.argv.slice(2).find((item) => item.startsWith(prefix));
  return value ? value.slice(prefix.length) : undefined;
};

const base = (
  argument("--url") ??
  process.env.PCR_E2E_BASE_URL ??
  "http://localhost:3100"
).replace(/\/$/, "");
const budgetMs = Number(
  argument("--budget-ms") ?? process.env.PCR_WEB_ROUTE_BUDGET_MS ?? 1500,
);
if (!Number.isFinite(budgetMs) || budgetMs <= 0) {
  throw new Error("Invalid route budget: " + budgetMs);
}

const routes = [
  "/",
  "/sign-in",
  "/sign-up",
  "/recover",
  "/about",
  "/docs",
  "/privacy",
  "/terms",
  "/contact",
  "/try",
  "/robots.txt",
  "/sitemap.xml",
];
const pageRoutes = new Set(
  routes.filter((route) => !route.endsWith(".txt") && !route.endsWith(".xml")),
);
const results = [];

for (const route of routes) {
  const started = performance.now();
  const response = await fetch(base + route, { redirect: "manual" });
  const elapsed = Math.round(performance.now() - started);
  const body = await response.text();
  const allowedStatuses = route === "/" ? [200, 307, 308] : [200];
  if (!allowedStatuses.includes(response.status)) {
    throw new Error(
      route +
        ": expected HTTP " +
        allowedStatuses.join(" or ") +
        ", got " +
        response.status,
    );
  }
  if (response.status !== 200) {
    results.push({
      route,
      status: response.status,
      elapsed,
      bytes: Buffer.byteLength(body),
      contentType: response.headers.get("content-type") ?? "",
    });
    continue;
  }
  const expectedType = pageRoutes.has(route)
    ? "text/html"
    : route.endsWith(".xml")
      ? "application/xml"
      : "text/plain";
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().includes(expectedType)) {
    throw new Error(
      route + ": expected " + expectedType + ", got " + contentType,
    );
  }
  if (body.length === 0) throw new Error(route + ": empty response body");
  if (elapsed > budgetMs) {
    throw new Error(
      route +
        ": " +
        elapsed +
        "ms exceeds " +
        budgetMs +
        "ms production route budget",
    );
  }
  results.push({
    route,
    status: response.status,
    elapsed,
    bytes: Buffer.byteLength(body),
    contentType,
  });
}

const securityResponse = await fetch(base + "/sign-in");
const requiredHeaders = [
  "content-security-policy",
  "x-content-type-options",
  "x-frame-options",
  "referrer-policy",
  "permissions-policy",
  "cross-origin-opener-policy",
  "cross-origin-resource-policy",
];
for (const header of requiredHeaders) {
  if (!securityResponse.headers.get(header)) {
    throw new Error("/sign-in: missing security header " + header);
  }
}

console.log(
  "Web production smoke PASS: " +
    results.length +
    " routes, budget " +
    budgetMs +
    "ms",
);
for (const result of results) {
  console.log(
    result.route +
      "\t" +
      result.status +
      "\t" +
      result.elapsed +
      "ms\t" +
      result.bytes +
      " bytes\t" +
      result.contentType,
  );
}
