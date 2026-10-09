#!/usr/bin/env python3
"""The single deterministic quality entry point. Run via ./bootstrap check deep."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".local/artifacts"


@dataclass(frozen=True)
class Check:
    name: str
    arguments: tuple[str, ...]
    directory: str = ""


def checks() -> list[Check]:
    return [
        Check("bootstrap syntax", ("sh", "-n", "bootstrap")),
        Check("operations tests", ("python", "-m", "unittest", "discover", "-s", "scripts/tests", "-v")),
        Check("static shell CSP", ("node", "--test", "scripts/tests/csp.test.mjs")),
        Check("platform boundary", ("python", "scripts/check_boundaries.py")),
        Check("operations live isolation", ("python", "scripts/verify_operations.py")),
        Check("database error log confidentiality", ("python", "scripts/verify_database_log_privacy.py")),
        Check("backend artifact provenance", ("python", "scripts/check_dependency_provenance.py")),
        Check("backend lock consistency", ("uv", "lock", "--check", "--offline"), "backend"),
        Check("backend lint", ("ruff", "check", "."), "backend"),
        Check("backend formatting", ("ruff", "format", "--check", "."), "backend"),
        Check("operations and contract lint", ("ruff", "check", "ops", "scripts", "contracts", "--config", "backend/pyproject.toml")),
        Check("operations runtime static security", ("bandit", "-q", "-r", "ops", "-c", "backend/pyproject.toml")),
        Check("backend types", ("mypy", "."), "backend"),
        Check("backend static security", ("bandit", "-q", "-r", ".", "-c", "pyproject.toml"), "backend"),
        Check("backend dependency export", ("uv", "export", "--frozen", "--no-hashes", "--no-emit-project", "--output-file", str(ARTIFACTS / "requirements.txt")), "backend"),
        Check("backend dependency security", ("pip-audit", "--disable-pip", "--no-deps", "--requirement", str(ARTIFACTS / "requirements.txt")), "backend"),
        Check("Django system checks", ("python", "manage.py", "check"), "backend"),
        Check("migration consistency", ("python", "manage.py", "makemigrations", "--check", "--dry-run"), "backend"),
        Check("PostgreSQL integration and executor contracts", ("pytest", "tests", str(ROOT / "contracts/tests")), "backend"),
        Check("OpenAPI export and validation", ("python", "manage.py", "spectacular", "--format", "openapi-json", "--file", str(ARTIFACTS / "openapi.json"), "--validate", "--fail-on-warn"), "backend"),
        Check("OpenAPI snapshot", ("python", "scripts/check_generated.py", "backend/openapi.json", str(ARTIFACTS / "openapi.json"))),
        Check("frontend locked install", ("npm", "ci", "--no-fund", "--no-audit"), "frontend"),
        Check("frontend dependency security", ("npm", "audit", "--audit-level=high"), "frontend"),
        Check("generated frontend API", ("npx", "openapi-typescript", str(ARTIFACTS / "openapi.json"), "-o", str(ARTIFACTS / "api.generated.ts")), "frontend"),
        Check("frontend API snapshot", ("python", "scripts/check_generated.py", "frontend/app/lib/api.generated.ts", str(ARTIFACTS / "api.generated.ts"))),
        Check("frontend types", ("npm", "run", "typecheck"), "frontend"),
        Check("frontend lint", ("npm", "run", "lint"), "frontend"),
        Check("frontend formatting", ("npm", "run", "format:check"), "frontend"),
        Check("frontend unit tests", ("npm", "test"), "frontend"),
        Check("frontend static build", ("npm", "run", "build"), "frontend"),
        Check("real browser journeys", ("npm", "run", "test:e2e"), "frontend"),
    ]


def run_gate() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    results = []
    environment = {**os.environ, "CI": "1"}
    for check in checks():
        print(f"\nRunning {check.name}…", flush=True)
        start = time.monotonic()
        try:
            process = subprocess.run(check.arguments, cwd=ROOT / check.directory, env=environment, check=False)
            code = process.returncode
        except OSError as error:
            print(f"Check unavailable: {error}", file=sys.stderr)
            code = 127
        results.append({"name": check.name, "exit_code": code, "seconds": round(time.monotonic() - start, 2)})
    report = {"passed": all(result["exit_code"] == 0 for result in results), "checks": results}
    (ARTIFACTS / "gate.json").write_text(json.dumps(report, indent=2) + "\n")
    failed = [result["name"] for result in results if result["exit_code"] != 0]
    if failed:
        print("\nQuality gate failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    print(f"\nQuality gate passed ({len(results)} checks).")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("deep",), nargs="?", default="deep")
    parser.parse_args()
    sys.exit(run_gate())
