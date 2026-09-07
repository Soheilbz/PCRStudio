import { cpSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawn } from "node:child_process";

const webRoot = process.cwd();
const standaloneRoot = resolve(webRoot, ".next", "standalone");
const serverRoot = existsSync(resolve(standaloneRoot, "web", "server.js"))
  ? resolve(standaloneRoot, "web")
  : standaloneRoot;
const server = resolve(serverRoot, "server.js");

if (!existsSync(server)) {
  throw new Error("Standalone server not found. Run `pnpm build` first.");
}

// Next's standalone output intentionally omits these two public asset trees.
// Copy them beside the traced server exactly as the production image does.
for (const [source, destination] of [
  [resolve(webRoot, ".next", "static"), resolve(serverRoot, ".next", "static")],
  [resolve(webRoot, "public"), resolve(serverRoot, "public")],
]) {
  if (existsSync(source)) cpSync(source, destination, { recursive: true, force: true });
}

const child = spawn(process.execPath, [server], {
  cwd: serverRoot,
  env: { ...process.env, PORT: process.env.PORT ?? "3000" },
  stdio: "inherit",
});

const stop = (signal) => child.kill(signal);
process.on("SIGINT", () => stop("SIGINT"));
process.on("SIGTERM", () => stop("SIGTERM"));
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
