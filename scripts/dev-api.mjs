#!/usr/bin/env node
/**
 * Start the API for development, with the two settings it cannot work without.
 *
 * `cargo run -p pcr-server --bin pcr-server` starts the intended API binary;
 * the package also contains the separate migration binary, so omitting
 * `--bin` makes Cargo refuse to choose one.
 * answers `/health` with `ok`, and fails every design — because `PCR_PYTHON`
 * falls back to whatever `python3` resolves to on the PATH, which is almost
 * never the interpreter that has the worker installed. That failure looks like
 * a bug in the design engine and is not one.
 *
 * So this finds the worker's interpreter rather than hoping, and says which one
 * it is on the way past. Everything it sets can be overridden from the
 * environment, because a deployment knows better than a script does.
 */

import { execFileSync, spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** `.env` if there is one, so this agrees with `docker compose`. */
function fromDotEnv() {
  const path = join(root, ".env");
  if (!existsSync(path)) return {};

  const values = {};
  for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim().replace(/^export\s+/, "");
    if (!line || line.startsWith("#")) continue;
    const match = /^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line);
    // A trailing `# comment` is only a comment when unquoted.
    if (!match) continue;
    let value = match[2];
    const quoted = /^["']/.test(value);
    if (!quoted) value = value.split(/\s+#/)[0];
    values[match[1]] = value.replace(/^["']|["']$/g, "").trim();
  }
  return values;
}

/**
 * The interpreter that has `pcr_tools` in it.
 *
 * The virtual environment the README tells you to make, under whichever of the
 * two names the platform uses. A candidate is usable only when it can import
 * the worker package; a bare Python executable is not enough for this API.
 */
function findWorkerPython() {
  const candidates = [join(root, "tools", ".venv", "bin", "python")];
  for (const candidate of candidates) {
    if (!existsSync(candidate)) continue;
    try {
      execFileSync(candidate, ["-c", "import pcr_tools"], {
        cwd: root,
        stdio: "ignore",
      });
      return candidate;
    } catch {
      // Keep looking; a present but uninitialised venv is not a worker.
    }
  }
  return null;
}

const dotEnv = fromDotEnv();
const toolchainEnv = fromToolchainJson(join(root, ".local", "tools", "toolchain.json"));
const specificityEnv = fromFile(join(root, ".local", "tools", "specificity.env"));
const configuredPython = process.env.PCR_PYTHON?.trim();
const python = configuredPython || findWorkerPython();

if (!python) {
  console.error(
    "! No usable PCRStudio worker was found under tools/.venv.\n" +
      "  Initialise the project environment first:\n" +
      "    uv sync --project tools --frozen --extra dev\n" +
      "  Or set PCR_PYTHON explicitly to an interpreter with pcrstudio-tools installed.\n",
  );
  process.exit(1);
}

// A missing database URL must never be guessed. The local compose database
// intentionally uses pcr:pcr, so report that explicitly when a developer has
// chosen it rather than pretending it is a deployment-safe credential.
const DEFAULT_URL = "postgres://pcr:pcr@localhost:55432/pcrstudio";
let database = process.env.PCR_DATABASE_URL ?? dotEnv.PCR_DATABASE_URL ?? null;

// start-app may move the local compose database when 55432 is occupied. Keep
// an explicitly supplied URL authoritative, while retargeting the documented
// loopback URL to the port selected by the launcher.
const selectedDatabasePort = process.env.PCR_DATABASE_PORT?.trim();
if (
  !process.env.PCR_DATABASE_URL &&
  database &&
  selectedDatabasePort &&
  /^postgres(?:ql)?:\/\/[^@/]+@(?:localhost|127\.0\.0\.1):55432\//.test(
    database,
  )
) {
  database = database.replace(/:55432\//, `:${selectedDatabasePort}/`);
}

if (database === null) {
  console.warn(
    "! No PCR_DATABASE_URL in the environment or .env.\n" +
      "  Refusing to guess a password. Set one:\n" +
      '    echo "PCR_DATABASE_URL=postgres://pcr:<password>@localhost:55432/pcrstudio" >> .env\n',
  );
  process.exit(1);
}
if (`${database}` === DEFAULT_URL) {
  console.warn(
    "! PCR_DATABASE_URL is the well-known development default (pcr:pcr).",
  );
}

console.log(`  worker   ${python}`);
console.log(`  database ${database.replace(/:\/\/[^@]*@/, "://***@")}\n`);

const child = spawn("cargo", ["run", "-p", "pcr-server", "--bin", "pcr-server"], {
  cwd: root,
  stdio: "inherit",
  env: {
    ...toolchainEnv,
    ...specificityEnv,
    ...dotEnv,
    ...process.env,
    PCR_PYTHON: python,
    PCR_DATABASE_URL: database,
  },
  detached: true,
});

function fromToolchainJson(path) {
  if (!existsSync(path)) return {};
  let payload;
  try {
    payload = JSON.parse(readFileSync(path, "utf8"));
  } catch (cause) {
    throw new Error(`Invalid toolchain configuration ${path}: ${cause.message}`);
  }
  if (
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    payload.schema_version !== "1.0.0" ||
    !payload.environment ||
    typeof payload.environment !== "object" ||
    Array.isArray(payload.environment) ||
    Object.keys(payload).sort().join(",") !== "environment,schema_version"
  ) {
    throw new Error(`Invalid toolchain configuration schema in ${path}`);
  }
  const values = Object.create(null);
  for (const [key, value] of Object.entries(payload.environment)) {
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) || typeof value !== "string") {
      throw new Error(`Invalid toolchain environment entry ${JSON.stringify(key)} in ${path}`);
    }
    if (/[\0\r\n]/.test(value)) {
      throw new Error(`Toolchain environment value ${key} contains a line/control delimiter`);
    }
    values[key] = value;
  }
  return values;
}

function fromFile(path) {
  if (!existsSync(path)) return {};
  return Object.fromEntries(
    readFileSync(path, "utf8")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => line.split(/=(.*)/s, 2))
      .filter(([key, value]) => /^[A-Za-z_][A-Za-z0-9_]*$/.test(key) && value !== undefined)
      .map(([key, value]) => [key, value.replace(/^['"]|['"]$/g, "")]),
  );
}

child.on("error", (cause) => {
  console.error(
    `\n Could not run cargo (${cause.message}). Is the Rust toolchain installed?\n` +
      "   https://rustup.rs\n",
  );
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 0)));
for (const stop of ["SIGINT", "SIGTERM"]) {
  process.on(stop, () => {
    try {
      process.kill(-child.pid, stop);
    } catch (cause) {
      if (cause?.code !== "ESRCH") {
        console.warn(`Could not signal API process group ${child.pid}: ${cause.message}`);
      }
    }
  });
}
