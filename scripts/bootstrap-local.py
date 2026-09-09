#!/usr/bin/env python3
"""One-command, project-local Linux development bootstrap.

This is the host-side companion to the Docker production bootstrap. It keeps
all mutable state under ``.local`` and prepares the exact Python, JavaScript
and scientific toolchain before running the deterministic source gates.
System Docker/Rust installation and production database provisioning remain
explicit host/release gates; this command never silently changes them.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
UV_BOOTSTRAP = LOCAL / "uv-venv"
UV_VERSION = "0.12.10"
RUST_TOOLCHAIN = "1.94.1"


def run(argv: list[str], *, env: dict[str, str] | None = None) -> None:
    print(">", " ".join(str(part) for part in argv), flush=True)
    subprocess.run([str(part) for part in argv], cwd=ROOT, check=True, env=env)


def require_linux() -> None:
    if not sys.platform.startswith("linux"):
        raise SystemExit("PCRStudio local bootstrap supports Linux only.")
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        raise SystemExit(f"Pinned native artifacts require Linux x86_64; detected {machine!r}.")


def ensure_uv() -> Path:
    existing = shutil.which("uv")
    if existing:
        return Path(existing)

    LOCAL.mkdir(parents=True, exist_ok=True)
    uv_python = UV_BOOTSTRAP / "bin" / "python"
    if not uv_python.is_file():
        print(f"Creating project-local uv environment at {UV_BOOTSTRAP}", flush=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(UV_BOOTSTRAP)
    run([
        str(uv_python), "-m", "pip", "install", "--disable-pip-version-check",
        "--no-input", f"uv=={UV_VERSION}",
    ])
    uv = UV_BOOTSTRAP / "bin" / "uv"
    if not uv.is_file():
        raise SystemExit(f"uv installation did not produce {uv}")
    return uv


def ensure_node_runtime(env: dict[str, str]) -> Path:
    """Find Node even when the caller only exposed the bundled pnpm shim."""
    configured = shutil.which("node")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))

    # Codex and other managed runtimes commonly expose pnpm through a shim
    # while keeping its matching Node binary beside the shim's parent. Follow
    # that relationship so bootstrap does not depend on an already activated
    # interactive shell.
    package_manager_path = shutil.which("pnpm")
    if package_manager_path:
        shim = Path(package_manager_path).resolve()
        for ancestor in shim.parents:
            candidates.append(ancestor / "node" / "bin" / "node")

    candidates.extend([
        LOCAL / "node" / "bin" / "node",
        Path("/usr/local/bin/node"),
        Path("/usr/bin/node"),
    ])
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            env["PATH"] = f"{candidate.parent}{os.pathsep}{env.get('PATH', '')}"
            return candidate
    raise SystemExit(
        "Node.js 22+ is required for the Web workspace. The bootstrap could not "
        "find a usable Node runtime; install Node or expose the bundled runtime, "
        "then rerun ./bootstrap.sh --local"
    )


def package_manager() -> list[str]:
    direct = shutil.which("pnpm")
    if direct:
        return [direct]
    corepack = shutil.which("corepack")
    if corepack:
        # package.json pins the exact pnpm version. Corepack may download it,
        # but the prompt must never block an unattended bootstrap.
        return [corepack, "pnpm"]
    raise SystemExit(
        "Node.js 24 with Corepack (or pnpm 11.26.0) is required for the Web workspace; "
        "install Node first, then rerun ./bootstrap.sh --local"
    )


def ensure_rust_components(env: dict[str, str]) -> None:
    """Make the pinned local Rust toolchain complete before qualification."""
    rustup = LOCAL / "cargo" / "bin" / "rustup"
    if not rustup.is_file():
        configured = shutil.which("rustup")
        if configured:
            rustup = Path(configured)
    if not rustup.is_file():
        raise SystemExit(
            "Rust/rustup is required for the API workspace; install rustup or "
            "run the Linux system bootstrap, then rerun ./bootstrap.sh --local"
        )
    rust_env = {
        **env,
        "RUSTUP_HOME": str(LOCAL / "rustup"),
        "CARGO_HOME": str(LOCAL / "cargo"),
        "RUSTUP_TOOLCHAIN": RUST_TOOLCHAIN,
        "PATH": f"{rustup.parent}{os.pathsep}{env.get('PATH', '')}",
    }
    complete_toolchains = [
        path
        for path in (LOCAL / "rustup" / "toolchains").glob(f"{RUST_TOOLCHAIN}-*")
        if all((path / "bin" / binary).is_file() for binary in ("rustc", "rustfmt", "clippy-driver"))
    ]
    if complete_toolchains:
        print(
            f"Reusing pinned Rust {RUST_TOOLCHAIN} with rustfmt and clippy: "
            f"{sorted(complete_toolchains)[0]}",
            flush=True,
        )
        return
    run([str(rustup), "toolchain", "install", RUST_TOOLCHAIN, "--profile", "minimal"], env=rust_env)
    run([str(rustup), "component", "add", "clippy", "rustfmt", "--toolchain", RUST_TOOLCHAIN], env=rust_env)


def install_e2e_browsers(pnpm: list[str], env: dict[str, str]) -> Path:
    """Install the browser engines declared by the Playwright suite.

    Playwright's default cache is user-global, which makes a fresh isolated
    checkout look provisioned until the first E2E run. Keep the browsers with
    the rest of this project's mutable state and let Playwright verify/reuse
    the pinned binaries on subsequent bootstrap runs.
    """
    browser_root = LOCAL / "playwright-browsers"
    browser_root.mkdir(parents=True, exist_ok=True)
    browser_env = {**env, "PLAYWRIGHT_BROWSERS_PATH": str(browser_root)}
    run([
        *pnpm, "--filter", "web", "exec", "playwright", "install",
        "chromium", "firefox", "webkit",
    ], env=browser_env)
    return browser_root


def read_assignment_file(path: Path) -> dict[str, str]:
    """Read the provisioner's one-assignment shell environment safely."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed = shlex.split(value, comments=False, posix=True)
        if len(parsed) != 1 or not key.isidentifier():
            raise SystemExit(f"Invalid toolchain assignment in {path}: {key!r}")
        values[key] = parsed[0]
    return values


def ensure_local_specificity_database(env: dict[str, str]) -> None:
    """Create the deterministic approved-reference DB used by local E2E runs.

    Production deployments must provide their own reviewed reference snapshot.
    Local bootstrap may use the repository's versioned pUC19 corpus, which is
    sufficient to exercise the complete worker/API/database path without
    presenting it as a population-wide production database.
    """
    specificity = LOCAL / "tools" / "specificity.env"
    if specificity.is_file():
        return
    source = ROOT / "tools" / "tests" / "corpus" / "L09137.2.fasta"
    if not source.is_file():
        raise SystemExit(f"Local specificity seed is missing: {source}")
    run([
        sys.executable, "scripts/configure-specificity-database.py", str(source),
        "local-regression", "--scope", "approved-reference",
        "--sequence-release", "pcrstudio-regression-2026",
        "--taxonomy-release", "not-applicable", "--force",
    ], env=env)


def ensure_local_environment() -> None:
    """Create the ignored development environment when a checkout has none."""
    env_file = ROOT / ".env"
    if not env_file.is_file():
        env_file.write_text(
            "# Generated by ./bootstrap.sh --local; local development only.\n"
            "PCR_DATABASE_URL=postgres://pcr:pcr@127.0.0.1:55432/pcrstudio\n"
            "PCR_BIND=127.0.0.1:8080\n",
            encoding="utf-8",
        )
        env_file.chmod(0o600)
        return
    contents = env_file.read_text(encoding="utf-8")
    if not any(line.startswith("PCR_DATABASE_URL=") for line in contents.splitlines()):
        with env_file.open("a", encoding="utf-8") as handle:
            handle.write("\nPCR_DATABASE_URL=postgres://pcr:pcr@127.0.0.1:55432/pcrstudio\n")


def verify_scientific_runtime(env: dict[str, str]) -> None:
    """Fail bootstrap before launch when strict worker readiness is false."""
    toolchain = LOCAL / "tools"
    runtime_env = {
        **env,
        **read_assignment_file(toolchain / "toolchain.env"),
        **read_assignment_file(toolchain / "specificity.env"),
    }
    envelope = {
        "protocolVersion": "2.0.0", "requestSchema": 2, "resultSchema": 4,
        "requestId": "bootstrap-probe", "command": "toolchain", "engine": "utility",
        "module": None, "payload": {},
    }
    worker = ROOT / "tools" / ".venv" / "bin" / "python"
    completed = subprocess.run(
        [str(worker), "-m", "pcr_tools", "toolchain"], cwd=ROOT,
        input=json.dumps(envelope), text=True, capture_output=True, env=runtime_env,
    )
    if completed.returncode != 0:
        raise SystemExit(f"Scientific worker probe failed during bootstrap: {completed.stderr.strip()}")
    try:
        response = json.loads(completed.stdout)
        ready = response["payload"]["toolchain"]["strict_execution"]["ready"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit(f"Scientific worker probe returned an invalid contract: {error}") from error
    if ready is not True:
        raise SystemExit(
            "Scientific worker strict readiness is false after bootstrap. "
            "Inspect the toolchain and approved-reference database contract."
        )


def ensure_local_admin(env: dict[str, str], api_url: str) -> Path:
    """Create or verify the local administrator without putting its secret in logs."""
    credentials = LOCAL / "admin-credentials.json"
    email = env.get("PCR_ADMIN_EMAIL", "admin@pcrstudio.local").strip()
    password = env.get("PCR_ADMIN_PASSWORD", "").strip()
    if credentials.is_file():
        try:
            saved = json.loads(credentials.read_text(encoding="utf-8"))
            if (
                not isinstance(saved, dict)
                or not isinstance(saved.get("email"), str)
                or not isinstance(saved.get("password"), str)
                or not saved["email"]
                or not saved["password"]
            ):
                raise ValueError("expected non-empty email/password")
            email = saved["email"]
            password = saved["password"]
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemExit(f"Invalid local admin credential file {credentials}: {error}") from error
    elif not password:
        password = secrets.token_urlsafe(24)

    admin_env = {
        **env,
        "PCR_API_URL": api_url,
        "PCR_ADMIN_EMAIL": email,
        "PCR_ADMIN_PASSWORD": password,
        "PCR_ADMIN_NAME": env.get("PCR_ADMIN_NAME", "PCRStudio Administrator"),
        "NODE_ENV": "development",
    }
    completed = subprocess.run(
        ["node", "scripts/dev-admin.mjs"], cwd=ROOT, text=True,
        capture_output=True, env=admin_env, check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise SystemExit(f"Local admin provisioning failed: {detail}")
    LOCAL.mkdir(parents=True, exist_ok=True)
    credentials.write_text(json.dumps({"email": email, "password": password}, indent=2) + "\n", encoding="utf-8")
    credentials.chmod(0o600)
    return credentials


def start_services_and_verify(env: dict[str, str]) -> tuple[str, Path]:
    """Start/reuse the local full stack and require real HTTP readiness."""
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js is required to start the full-stack local launcher.")
    runtime = LOCAL / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    log_path = runtime / "bootstrap-launcher.log"
    endpoints_path = runtime / "endpoints.json"

    def http_ok(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError):
            return False

    if endpoints_path.is_file():
        try:
            existing = json.loads(endpoints_path.read_text(encoding="utf-8"))
            existing_api = str(existing["api"]).rstrip("/")
            existing_web = str(existing["web"]).rstrip("/")
            if (
                http_ok(f"{existing_api}/health")
                and http_ok(f"{existing_api}/ready")
                and http_ok(f"{existing_api}/ready/scientific")
                and http_ok(f"{existing_web}/")
            ):
                return existing_web, ensure_local_admin(env, existing_api)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        # The launcher owns this exact generated runtime record. A dead or
        # malformed record must not make bootstrap probe stale ports forever.
        endpoints_path.unlink(missing_ok=True)

    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [node, "scripts/start-app.mjs", "--background"], cwd=ROOT,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            env=env, start_new_session=True,
        )
    deadline = time.monotonic() + 300
    endpoints: dict[str, object] | None = None
    while time.monotonic() < deadline:
        if endpoints_path.is_file():
            try:
                candidate = json.loads(endpoints_path.read_text(encoding="utf-8"))
                if isinstance(candidate, dict) and isinstance(candidate.get("api"), str) and isinstance(candidate.get("web"), str):
                    endpoints = candidate
                    break
            except (OSError, json.JSONDecodeError):
                pass
        if process.poll() is not None:
            break
        time.sleep(0.5)
    if endpoints is None:
        tail = ""
        if log_path.is_file():
            tail = "\n" + "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-30:])
        raise SystemExit(f"Full-stack launcher did not publish endpoints.{tail}")

    def require_ok(url: str, label: str) -> None:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status != 200:
                    raise SystemExit(f"{label} returned HTTP {response.status}; see {log_path}")
        except (urllib.error.URLError, TimeoutError) as error:
            raise SystemExit(f"{label} is not ready: {error}; see {log_path}") from error

    api_url = str(endpoints["api"]).rstrip("/")
    web_url = str(endpoints["web"]).rstrip("/")
    require_ok(f"{api_url}/health", "API liveness")
    require_ok(f"{api_url}/ready", "API readiness")
    require_ok(f"{api_url}/ready/scientific", "Scientific readiness")
    require_ok(f"{web_url}/", "Web frontend")
    credentials = ensure_local_admin(env, api_url)
    return web_url, credentials


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-tools", action="store_true",
        help="sync Python/Web dependencies and qualify source, but skip native scientific downloads",
    )
    args = parser.parse_args()
    require_linux()
    ensure_local_environment()

    uv = ensure_uv()
    env = os.environ.copy()
    node = ensure_node_runtime(env)
    pnpm = package_manager()
    env["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["UV_CACHE_DIR"] = str(LOCAL / "uv-cache")
    env["PATH"] = f"{uv.parent}:{os.pathsep}{env.get('PATH', '')}"
    env["RUSTUP_HOME"] = str(LOCAL / "rustup")
    env["CARGO_HOME"] = str(LOCAL / "cargo")
    env["RUSTUP_TOOLCHAIN"] = RUST_TOOLCHAIN
    env["PATH"] = f"{LOCAL / 'cargo' / 'bin'}{os.pathsep}{env['PATH']}"
    os.environ.update({
        "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
        "UV_CACHE_DIR": env["UV_CACHE_DIR"],
        "PATH": env["PATH"],
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    print(f"Node runtime: {node}", flush=True)

    ensure_rust_components(env)

    prepare = [
        sys.executable, "scripts/prepare-linux.py", "--sync-dependencies",
        "--pnpm-store-dir", ".local/pnpm-store",
    ]
    if not args.skip_tools:
        prepare.extend(["--provision-tools", "--approve-scientific-freeze"])
    run(prepare, env=env)
    if not args.skip_tools:
        ensure_local_specificity_database(env)
        verify_scientific_runtime(env)
    browsers = install_e2e_browsers(pnpm, env)
    web_url, admin_credentials = start_services_and_verify(env)
    print("\nPCRStudio local bootstrap PASS", flush=True)
    print(f"  uv: {uv}", flush=True)
    print(f"  worker: {ROOT / 'tools/.venv/bin/python'}", flush=True)
    if not args.skip_tools:
        print(f"  scientific tools: {LOCAL / 'tools'}", flush=True)
    print(f"  e2e browsers: {browsers}", flush=True)
    print(f"  full stack: {web_url}", flush=True)
    print(f"  local admin credentials: {admin_credentials} (mode 600; not printed)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
