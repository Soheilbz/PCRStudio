#!/usr/bin/env node
/**
 * Create — or verify — the local development account.
 *
 *   node scripts/dev-user.mjs
 *
 * The API must be running (start-app.mjs or dev-api.mjs). On first run the
 * account is created and the one-time recovery code is printed; every run
 * after that signs in to confirm the credentials still work. Credentials are
 * supplied through the environment so this helper cannot accidentally ship a
 * usable account password in source control.
 *
 *   PCR_DEV_EMAIL=dev@pcrstudio.local PCR_DEV_PASSWORD='<local secret>'
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const API = process.env.PCR_API_URL ?? "http://127.0.0.1:8080";
const EMAIL = process.env.PCR_DEV_EMAIL ?? "dev@pcrstudio.local";
const PASSWORD = process.env.PCR_DEV_PASSWORD;
const NAME = process.env.PCR_DEV_NAME ?? "Bench Developer";

if (process.env.NODE_ENV === "production") {
  console.error("Refusing to create a development account in production.");
  process.exit(1);
}

if (!PASSWORD) {
  console.error(
    "Set PCR_DEV_PASSWORD for this local-only helper; it is deliberately not stored in the repository.",
  );
  process.exit(1);
}

/** The PCR_DATABASE_URL from `.env`, for the "is the API even up" message. */
function apiHint() {
  const env = join(root, ".env");
  if (
    existsSync(env) &&
    readFileSync(env, "utf8").includes("PCR_DATABASE_URL")
  ) {
    return "start the stack first:  node scripts/start-app.mjs";
  }
  return "start the API first (see docs/DEVELOPMENT.md, Launching the stack)";
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

const register = await call("/api/auth/register", {
  email: EMAIL,
  displayName: NAME,
  password: PASSWORD,
});

if (register.ok) {
  console.log(`created  ${EMAIL}`);
  if (register.payload.recoveryCode) {
    console.log(
      `recovery code (shown once, also stored nowhere): ${register.payload.recoveryCode}`,
    );
  }
  process.exit(0);
}

if (
  register.status === 409 ||
  /exist|taken/i.test(register.payload.error ?? "")
) {
  const login = await call("/api/auth/login", {
    email: EMAIL,
    password: PASSWORD,
  });
  if (login.ok) {
    console.log(`verified  ${EMAIL}  (account already existed)`);
    process.exit(0);
  }
  console.error(
    "account exists but the password does not match — a previous dev database?",
  );
  console.error(
    `delete the row or pick the password the database was created with.`,
  );
  process.exit(1);
}

console.error(`could not create the dev user (${register.status}):`);
console.error(register.payload.error ?? JSON.stringify(register.payload));
console.error(apiHint());
process.exit(1);
