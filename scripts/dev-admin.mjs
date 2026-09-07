#!/usr/bin/env node
/**
 * Create or verify a local administrator account.
 *
 * The account is registered through the normal auth boundary first. Promotion
 * is then performed through psql using the local development database URL;
 * there is intentionally no public "make me admin" HTTP endpoint.
 *
 *   PCR_ADMIN_EMAIL=admin@pcrstudio.local node scripts/dev-admin.mjs
 *
 * When PCR_ADMIN_PASSWORD is not supplied, the helper asks on a terminal with
 * echo disabled. It is intentionally not part of bootstrap-generated files.
 */

import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { createInterface } from "node:readline";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const API = process.env.PCR_API_URL ?? "http://127.0.0.1:8080";
const EMAIL = process.env.PCR_ADMIN_EMAIL ?? "admin@pcrstudio.local";
const PASSWORD = process.env.PCR_ADMIN_PASSWORD;
const NAME = process.env.PCR_ADMIN_NAME ?? "PCRStudio Administrator";

if (process.env.NODE_ENV === "production") {
  console.error("Refusing to create a development administrator in production.");
  process.exit(1);
}
if (!/^[^\s'\\]+@[^\s'\\]+$/.test(EMAIL)) {
  throw new Error("PCR_ADMIN_EMAIL must be a simple email address");
}
async function adminPassword() {
  if (PASSWORD) return PASSWORD;
  if (!process.stdin.isTTY) throw new Error("Set PCR_ADMIN_PASSWORD or run this helper from a terminal");
  const hidden = spawnSync("stty", ["-echo"], { stdio: [process.stdin, process.stderr, process.stderr] });
  const readline = createInterface({ input: process.stdin, output: process.stderr, terminal: true });
  let value;
  try {
    value = await new Promise((resolve) => readline.question("Local admin password: ", resolve));
  } finally {
    readline.close();
    if (hidden.status === 0) spawnSync("stty", ["echo"], { stdio: [process.stdin, process.stderr, process.stderr] });
    process.stderr.write("\n");
  }
  return value;
}

function databaseUrl() {
  const path = join(root, ".env");
  if (!existsSync(path)) throw new Error(".env is missing; run ./bootstrap.sh --local first");
  const match = readFileSync(path, "utf8").match(/^PCR_DATABASE_URL=(.*)$/m);
  if (!match?.[1]) throw new Error("PCR_DATABASE_URL is missing from .env");
  return match[1].trim();
}

async function call(path, body) {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  });
  const payload = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, payload };
}

const adminPasswordValue = await adminPassword();
const registration = await call("/api/auth/register", {
  email: EMAIL,
  displayName: NAME,
  password: adminPasswordValue,
});
if (!registration.ok && registration.status !== 409) {
  console.error(`could not create the admin account (${registration.status})`);
  console.error(registration.payload.error ?? JSON.stringify(registration.payload));
  process.exit(1);
}

if (registration.status === 409) {
  const login = await call("/api/auth/login", { email: EMAIL, password: adminPasswordValue, remember: true });
  if (!login.ok) {
    console.error("the admin email exists but the supplied password does not match");
    process.exit(1);
  }
}

const database = new URL(databaseUrl());
const safeEmail = EMAIL.replaceAll("'", "''");
const result = spawnSync(
  "psql",
  ["--host", database.hostname, "--port", database.port || "5432", "--username", decodeURIComponent(database.username), "--dbname", database.pathname.slice(1), "-v", "ON_ERROR_STOP=1", "-At", "-c", `UPDATE users SET role = 'admin', updated_at = now() WHERE email_normalised = lower(trim('${safeEmail}')) RETURNING email`],
  {
    cwd: root,
    env: { ...process.env, PGPASSWORD: decodeURIComponent(database.password), PGOPTIONS: "-c statement_timeout=5000", PGAPPNAME: "pcrstudio-dev-admin" },
    input: undefined,
    encoding: "utf8",
  },
);

if (result.status !== 0) {
  console.error("database promotion failed; the account was not confirmed as admin");
  if (result.stderr) console.error(result.stderr.trim());
  process.exit(1);
}

const verification = spawnSync(
  "psql",
  ["--host", database.hostname, "--port", database.port || "5432", "--username", decodeURIComponent(database.username), "--dbname", database.pathname.slice(1), "-At", "-c", `SELECT role FROM users WHERE email_normalised = lower(trim('${safeEmail}'))`],
  { cwd: root, env: { ...process.env, PGPASSWORD: decodeURIComponent(database.password), PGOPTIONS: "-c statement_timeout=5000", PGAPPNAME: "pcrstudio-dev-admin-verify" }, encoding: "utf8" },
);
if (verification.status !== 0 || verification.stdout.trim() !== "admin") {
  console.error("database promotion did not result in an admin role");
  if (verification.stderr) console.error(verification.stderr.trim());
  process.exit(1);
}

console.log(`admin verified  ${EMAIL}`);
