#!/usr/bin/env node
/**
 * A dependency-free HTTP capacity probe for the API edge.
 *
 * This deliberately measures transport and handler capacity only. It is not
 * a substitute for a production-shaped 30-minute test involving authenticated
 * project traffic and separately sized design-worker jobs.
 *
 * Examples:
 *   node scripts/capacity-smoke.mjs --path=/health
 *   node scripts/capacity-smoke.mjs --path=/api/modules --requests=5000 --concurrency=5000
 */

const args = new Map(
  process.argv.slice(2).map((arg) => {
    const [key, value = "true"] = arg.replace(/^--/, "").split("=", 2);
    return [key, value];
  }),
);

if (args.has("help") || args.has("h")) {
  console.log(
    "Usage: node scripts/capacity-smoke.mjs [--url=URL] [--path=PATH] " +
      "[--requests=N] [--concurrency=N]",
  );
  process.exit(0);
}

const base = args.get("url") ?? "http://127.0.0.1:8080";
const path = args.get("path") ?? "/health";
const requests = positiveInteger(args.get("requests"), 5000, "requests");
const concurrency = Math.min(
  requests,
  positiveInteger(args.get("concurrency"), requests, "concurrency"),
);

const durations = [];
const statuses = new Map();
let next = 0;

const started = performance.now();
await Promise.all(
  Array.from({ length: concurrency }, async () => {
    while (true) {
      const index = next++;
      if (index >= requests) return;
      const requestStarted = performance.now();
      let status = 0;
      try {
        const response = await fetch(new URL(path, base));
        status = response.status;
        await response.arrayBuffer();
      } catch {
        // Keep network failures in the report instead of hiding them in a
        // rejected Promise that makes the whole sample look inconclusive.
      }
      durations[index] = performance.now() - requestStarted;
      statuses.set(status, (statuses.get(status) ?? 0) + 1);
    }
  }),
);

const elapsed = performance.now() - started;
const ordered = durations.toSorted((a, b) => a - b);
const percentile = (fraction) =>
  Math.round(
    ordered[
      Math.min(ordered.length - 1, Math.floor(ordered.length * fraction))
    ],
  );
const statusCounts = Object.fromEntries(
  [...statuses.entries()].sort(([left], [right]) => left - right),
);

console.log(
  JSON.stringify({
    url: new URL(path, base).toString(),
    requests,
    concurrency,
    elapsedMs: Math.round(elapsed),
    requestsPerSecond: Math.round(requests / (elapsed / 1000)),
    statusCounts,
    p50Ms: percentile(0.5),
    p95Ms: percentile(0.95),
    p99Ms: percentile(0.99),
  }),
);

function positiveInteger(value, fallback, name) {
  const number = value === undefined ? fallback : Number(value);
  if (!Number.isSafeInteger(number) || number < 1) {
    throw new Error(`--${name} must be a positive integer`);
  }
  return number;
}
