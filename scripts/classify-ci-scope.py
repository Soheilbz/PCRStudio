#!/usr/bin/env python3
"""Classify a pull request into stable, testable PCRStudio CI scopes.

Unknown paths deliberately select every broad gate. Narrow exceptions are
limited to documentation, release-bundle tooling, and dependency-maintenance
policy files with direct, always-run contract coverage.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import PurePosixPath


DOCS_ONLY_ROOT_FILES = {
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "README.md",
    "SECURITY.md",
}
TARGETED_RELEASE_FILES = {
    ".github/workflows/production-deploy.yml",
    "scripts/classify-ci-scope.py",
    "scripts/check-linux-bootstrap.py",
    "scripts/pull-release.py",
    "scripts/release_bundle.py",
}
TARGETED_MAINTENANCE_POLICY_FILES = {
    ".github/dependabot.yml",
    "contracts/maintenance-exceptions.json",
    "scripts/audit/release.py",
}
WEB_DEPENDENCY_FILES = {
    ".npmrc",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
}
FULL_PATH_PREFIXES = (
    "crates/",
    "tools/",
    "web/",
    "docker/",
    "contracts/",
    "ops/",
    "knowledge/runtime/",
)
FULL_ROOT_FILES = {
    "Cargo.lock",
    "Cargo.toml",
    "compose.yaml",
    "compose.vm.yaml",
}


def classify_paths(paths: list[str]) -> dict[str, bool]:
    """Return whether a PR requires the broad application and Web gates."""
    full = False
    web = False
    for raw_path in paths:
        path = PurePosixPath(raw_path).as_posix()
        if path in DOCS_ONLY_ROOT_FILES or path.startswith(("docs/", "history/", "archive/")):
            continue
        if path in TARGETED_RELEASE_FILES:
            continue
        if path in TARGETED_MAINTENANCE_POLICY_FILES:
            continue
        if path in WEB_DEPENDENCY_FILES:
            full = True
            web = True
            continue
        if path in FULL_ROOT_FILES or path.startswith(FULL_PATH_PREFIXES):
            full = True
            if path.startswith("web/"):
                web = True
            continue
        if path.startswith("scripts/"):
            # Bootstrap, release, and deployment scripts affect production
            # behavior. Only the three explicitly tested release helpers above
            # can use the narrow contract-only path.
            full = True
            continue
        if path.startswith((".github/", "release/")):
            # Workflow/security policy and release/provenance changes are
            # sensitive and therefore keep the broad application gates.
            full = True
            continue
        if path.startswith(("docs/", "history/", "archive/")):
            continue
        if path.lower().endswith((".md", ".rst", ".txt")):
            # The source qualification still checks generated metadata and
            # references; prose-only changes do not need product builds.
            continue
        # A new or unclassified path gets the complete gates until someone
        # deliberately adds and tests a narrower rule above.
        full = True
        web = True
    return {"full": full, "web": web}


def changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [path for path in result.stdout.splitlines() if path]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--output", default=os.environ.get("GITHUB_OUTPUT", ""))
    args = parser.parse_args()

    if args.event != "pull_request":
        scope = {"full": True, "web": True}
    else:
        if not args.base or not args.head:
            parser.error("pull_request scope requires --base and --head SHAs")
        scope = classify_paths(changed_paths(args.base, args.head))

    for name, enabled in scope.items():
        print(f"{name}={str(enabled).lower()}")
        if args.output:
            with open(args.output, "a", encoding="utf-8") as output:
                output.write(f"{name}={str(enabled).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
