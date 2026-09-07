#!/usr/bin/env node
/**
 * PCRStudio All-In-One Launcher
 *
 * Starts the development services and opens the app in your default browser.
 *
 * Ordering matters: the database must be healthy before the API starts
 * against it (migrations run at boot), and the web server must be listening
 * before a browser is pointed at it. Both are waited on rather than timed,
 * because a fixed sleep is right exactly once per machine.
 */

import { execFileSync, spawn } from "node:child_process";
import { createConnection, createServer } from "node:net";
import { dirname, resolve } from "node:path";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const WEB_PORT_PREFERENCE = Number(process.env.WEB_PORT ?? 3000);
const API_PORT_PREFERENCE = Number(process.env.API_PORT ?? 8080);
const DB_PORT_PREFERENCE = Number(process.env.PCR_DATABASE_PORT ?? 55432);
const BACKGROUND = process.argv.includes("--background");
let dbPort = 0;
let webPort = 0;
let apiPort = 0;
let apiProcess = null;
let webProcess = null;
let shuttingDown = false;

console.log("\n=======================================================");
console.log("             PCRStudio Full-Stack Launcher             ");
console.log("=======================================================\n");

/**
 * Kill a child *and everything it spawned*.
 *
 * Each child is started in its own POSIX process group. Sending a signal to
 * the negative pid terminates the launcher child and every subprocess it owns.
 * Existing listeners are never killed.
 */
function killTree(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch (cause) {
    // ESRCH means the process group is already gone; other errors deserve a log.
    if (cause?.code !== "ESRCH") {
      console.warn(
        ` ! Could not terminate process group ${child.pid}: ${cause.message}`,
      );
    }
  }
}

/** Resolve true when something is listening on `port`. */
function portOpen(port) {
  return new Promise((resolveOpen) => {
    const socket = createConnection({ port, host: "127.0.0.1" });
    const done = (result) => {
      socket.destroy();
      resolveOpen(result);
    };
    socket.once("connect", () => done(true));
    socket.once("error", () => done(false));
  });
}

/**
 * Reserve a loopback port briefly and return the port the child should use.
 * The preferred port is kept when it is free; port 0 asks the OS for an
 * ephemeral one when another application already owns the preference.
 *
 * There is necessarily a tiny hand-off between this reservation and the child
 * binding. Keeping the probe and both children on loopback makes that race
 * harmless in normal development, while avoiding the much worse old behaviour
 * of silently attaching to an unrelated service.
 */
function findAvailablePort(preferred) {
  const candidate =
    Number.isInteger(preferred) && preferred > 0 ? preferred : 0;
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    const finish = (error) => {
      server.removeAllListeners();
      if (error) reject(error);
      else resolvePort(server.address().port);
      server.close();
    };
    server.once("error", (error) => {
      if (candidate !== 0 && error.code === "EADDRINUSE") {
        server.close(() => {
          const fallback = createServer();
          fallback.once("error", reject);
          fallback.listen(0, "127.0.0.1", () => {
            const port = fallback.address().port;
            fallback.close(() => resolvePort(port));
          });
        });
        return;
      }
      finish(error);
    });
    server.listen(candidate, "127.0.0.1", () => finish());
  });
}

async function waitUntil(portOpen_, port, label, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await portOpen_(port)) return true;
    await new Promise((wake) => setTimeout(wake, 500));
  }
  console.log(
    ` ! ${label} did not start listening on ${port} within ${timeoutMs / 1000}s.`,
  );
  return false;
}

async function waitForHttp(url, label, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(5_000) });
      // A 503 is the truthful answer while a service is starting, not a
      // readiness success. Keep polling until the endpoint returns 2xx.
      if (response.ok) return true;
    } catch {
      // The service may still be compiling or applying migrations.
    }
    await new Promise((wake) => setTimeout(wake, 500));
  }
  console.log(` ! ${label} did not answer HTTP within ${timeoutMs / 1000}s.`);
  return false;
}

async function reuseExistingStack() {
  const path = resolve(root, ".local", "runtime", "endpoints.json");
  if (!existsSync(path)) return false;
  try {
    const endpoints = JSON.parse(readFileSync(path, "utf8"));
    const api = new URL(endpoints.api);
    const web = new URL(endpoints.web);
    const apiPort = Number(api.port);
    const webPort = Number(web.port);
    if (
      !apiPort ||
      !webPort ||
      !(await portOpen(apiPort)) ||
      !(await portOpen(webPort))
    ) {
      return false;
    }
    if (
      !(await waitForHttp(
        `${api.origin}/health`,
        "existing API liveness",
        5_000,
      ))
    )
      return false;
    if (
      !(await waitForHttp(
        `${api.origin}/ready`,
        "existing API readiness",
        5_000,
      ))
    )
      return false;
    if (
      !(await waitForHttp(
        `${api.origin}/ready/scientific`,
        "existing scientific readiness",
        5_000,
      ))
    )
      return false;
    if (!(await waitForHttp(`${web.origin}/`, "existing web frontend", 5_000)))
      return false;
    console.log(
      `       Reusing the healthy PCRStudio stack at ${endpoints.web}.`,
    );
    return true;
  } catch {
    return false;
  }
}

function detachForBackground(child) {
  if (BACKGROUND) child.unref();
}

async function main() {
  if (BACKGROUND && (await reuseExistingStack())) return;
  // Verify/rebuild the project-local native toolchain before any request can
  // reach the API.  The provisioner is idempotent: healthy artifacts are
  // hash-checked and reused; missing/corrupt artifacts are re-fetched only
  // from their pinned official sources.
  console.log(" [0/3] Verifying PCRStudio scientific toolchain...");
  try {
    execFileSync(
      process.env.PYTHON ?? "python3",
      [resolve(root, "scripts", "provision-tools.py")],
      { cwd: root, stdio: "inherit", timeout: 900_000 },
    );
  } catch {
    console.error(
      "       Toolchain provisioning failed; refusing to start a design-capable API.",
    );
    shutdown(1);
    return;
  }
  // [1/3] Database. A failure to reach Docker at all is fine — a developer may
  // run Postgres locally — but a broken compose file must not hide behind that.
  console.log(" [1/3] Checking PostgreSQL container via Docker...");
  try {
    execFileSync("docker", ["--version"], { stdio: "pipe", encoding: "utf8" });
    let ownDatabase = false;
    let existingDatabasePort = null;
    try {
      ownDatabase = Boolean(
        execFileSync(
          "docker",
          [
            "compose",
            "-f",
            "docker/compose.devdb.yaml",
            "ps",
            "-q",
            "--status",
            "running",
            "db",
          ],
          { cwd: root, stdio: "pipe", encoding: "utf8" },
        ).trim(),
      );
      if (ownDatabase) {
        const published = execFileSync(
          "docker",
          ["compose", "-f", "docker/compose.devdb.yaml", "port", "db", "5432"],
          { cwd: root, stdio: "pipe", encoding: "utf8" },
        ).trim();
        const match = /:(\d+)\s*$/.exec(published);
        if (match) existingDatabasePort = Number(match[1]);
      }
    } catch {
      // Compose may be installed while its daemon is unavailable.
    }
    if (
      ownDatabase &&
      existingDatabasePort &&
      (await portOpen(existingDatabasePort))
    ) {
      dbPort = existingDatabasePort;
      console.log(
        `       PCRStudio database already listening on ${dbPort}; reusing it.`,
      );
    } else {
      dbPort = await findAvailablePort(DB_PORT_PREFERENCE);
      if (dbPort !== DB_PORT_PREFERENCE) {
        console.log(
          `       Port ${DB_PORT_PREFERENCE} is occupied; database will use ${dbPort}.`,
        );
      }
      try {
        // --wait blocks until the healthcheck passes, not merely until the
        // container exists. The selected port is loopback-only.
        execFileSync(
          "docker",
          [
            "compose",
            "-f",
            "docker/compose.devdb.yaml",
            "up",
            "-d",
            "--wait",
            "db",
          ],
          {
            cwd: root,
            stdio: "pipe",
            timeout: 120_000,
            env: { ...process.env, PCR_DATABASE_PORT: String(dbPort) },
          },
        );
        console.log(`       Database service is healthy on ${dbPort}.`);
      } catch (cause) {
        const output = String(cause.stderr ?? cause.message ?? "");
        console.log("       docker compose up db FAILED:");
        console.log("       " + output.trim().split(/\r?\n/).join("\n       "));
        if (!(await portOpen(dbPort))) {
          console.error(
            "       PostgreSQL is not available. Start Docker/PostgreSQL or configure a healthy local database, then retry.",
          );
          shutdown(1);
          return;
        }
        console.log(
          `       A local PostgreSQL service is healthy on ${dbPort}; reusing it.`,
        );
      }
    }
  } catch {
    dbPort = DB_PORT_PREFERENCE;
    if (await portOpen(dbPort)) {
      console.log(
        `       Docker unavailable; using local database on ${dbPort}.`,
      );
    } else {
      console.error(
        "       Docker is unavailable and no local PostgreSQL service is listening on " +
          `${dbPort}. Start PostgreSQL or Docker, then retry.`,
      );
      shutdown(1);
      return;
    }
  }

  // [2/3] API server. Choose a free loopback port so another application never
  // causes this launcher to attach to the wrong API.
  console.log(" [2/3] Starting Backend API Server (pcr-server)...");
  apiPort = await findAvailablePort(API_PORT_PREFERENCE);
  console.log(`       API will use http://127.0.0.1:${apiPort}.`);
  apiProcess = spawn(process.execPath, ["scripts/dev-api.mjs"], {
    cwd: root,
    stdio: "inherit",
    env: {
      ...process.env,
      PCR_BIND: `127.0.0.1:${apiPort}`,
      PCR_DATABASE_PORT: String(dbPort),
    },
    detached: true,
  });
  detachForBackground(apiProcess);
  watchChild(apiProcess, "API launcher");
  if (!(await waitUntil(portOpen, apiPort, "Backend API", 180_000))) {
    shutdown(1);
    return;
  }
  if (
    !(await waitForHttp(
      `http://127.0.0.1:${apiPort}/ready`,
      "Backend API readiness",
      180_000,
    ))
  ) {
    shutdown(1);
    return;
  }

  // [3/3] Web frontend. Invoke Next directly so launching the app can never
  // trigger package-manager reconciliation or an interactive reinstall.
  console.log(" [3/3] Starting Web Frontend (Next.js)...");
  const nextCli = resolve(
    root,
    "web",
    "node_modules",
    "next",
    "dist",
    "bin",
    "next",
  );
  webPort = await findAvailablePort(WEB_PORT_PREFERENCE);
  // Next's dev lock is runtime state, not source. If a previous launcher was
  // interrupted after its process died, remove only that exact launcher-owned
  // dist directory. A different listener may still be using the ordinary
  // `.next` directory, so sharing it would let Turbopack corrupt both caches.
  const nextDistDir = `.next/pcrstudio-dev-${webPort}`;
  const nextDistPath = resolve(root, "web", nextDistDir);
  if (existsSync(nextDistPath) && !(await portOpen(webPort))) {
    rmSync(nextDistPath, { recursive: true, force: true });
    console.log("       Removed the stale PCRStudio Next.js runtime cache.");
  }
  if (!existsSync(nextCli)) {
    console.error(
      "\n Could not find web dependencies. Run `pnpm install` once, then launch again.\n",
    );
    shutdown(1);
  } else {
    console.log(`       Web frontend will use http://localhost:${webPort}.`);
    webProcess = spawn(process.execPath, [nextCli, "dev", "--turbopack"], {
      cwd: resolve(root, "web"),
      stdio: "inherit",
      env: {
        ...process.env,
        HOSTNAME: "127.0.0.1",
        PORT: String(webPort),
        NEXT_DIST_DIR: nextDistDir,
        PCR_API_URL: `http://127.0.0.1:${apiPort}`,
      },
      detached: true,
    });
    detachForBackground(webProcess);
    watchChild(webProcess, "Next.js");
  }

  // Publish the exact loopback endpoints selected by this launcher. Release
  // qualification reads this file instead of assuming ports 8080/3000 when
  // either preference was already occupied by an unrelated process. Do not
  // publish a record until the Web server is answering: bootstrap treats the
  // file as an atomic signal that the whole stack is ready to inspect.
  if (
    !(await waitForHttp(
      `http://localhost:${webPort}/`,
      "Web frontend",
      180_000,
    ))
  ) {
    shutdown(1);
    return;
  }
  const runtimeDir = resolve(root, ".local", "runtime");
  mkdirSync(runtimeDir, { recursive: true });
  writeFileSync(
    resolve(runtimeDir, "endpoints.json"),
    JSON.stringify(
      {
        schema_version: "1.0.0",
        api: `http://127.0.0.1:${apiPort}`,
        web: `http://localhost:${webPort}`,
        database_port: dbPort,
        api_pid: apiProcess?.pid ?? null,
        web_pid: webProcess?.pid ?? null,
        generated_at: new Date().toISOString(),
      },
      null,
      2,
    ) + "\n",
    "utf8",
  );

  // Open the browser only after the endpoint record has been published.
  if (!BACKGROUND) {
    await openBrowserWhenReady();
  }
}

/*
 * The database block used to be in the top-level body. Keeping it inside the
 * async startup sequence lets port reuse happen before either child is born,
 * which is what makes a second launch harmless.
 */
/* istanbul ignore next -- startup is exercised by the launcher smoke test. */
void main().catch((cause) => {
  console.error(`\n PCRStudio launcher failed: ${cause.message}`);
  shutdown(1);
});

// Open the browser only once the web server is actually answering, so nobody
// meets ERR_CONNECTION_REFUSED on a slow first compile.
async function openBrowserWhenReady() {
  const url = `http://localhost:${webPort}`;
  if (await waitUntil(portOpen, webPort, "Web frontend", 180_000)) {
    const opener = process.env.BROWSER?.trim() || "xdg-open";
    try {
      console.log(`\n Opening PCRStudio in your browser: ${url}\n`);
      const openerProcess = spawn(opener, [url], {
        stdio: "ignore",
        detached: true,
      });
      openerProcess.unref();
    } catch {
      console.log(`\n Please open ${url} in your browser.\n`);
    }
  }
}

function watchChild(child, label) {
  child.on("error", (cause) => {
    console.error(`\n Could not start ${label} (${cause.message}).`);
    shutdown(1);
  });
  child.on("exit", (code, signal) => {
    if (!shuttingDown) {
      console.error(`\n ${label} stopped unexpectedly.`);
      shutdown(signal ? 1 : (code ?? 1));
    }
  });
}

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log("\n Shutting down PCRStudio services...");
  // `main` assigns only children created by this invocation. A reused service
  // is intentionally left alive for the developer who started it.
  killTree(apiProcess);
  killTree(webProcess);
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
