#!/usr/bin/env python3
"""Classify a pull request into stable, testable PCRStudio CI scopes.

Unknown paths deliberately select every broad gate. Narrow exceptions are
limited to documentation, release-bundle tooling, and dependency-maintenance
policy files with direct, always-run contract coverage.
"""
from __future__ import annotations

import argparse
from collections import Counter
import os
import re
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
ACTION_USE_LINE = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)\s*$")
ACTION_SHA = re.compile(r"^[0-9a-f]{40}$")


def is_action_pin_only_diff_text(diff: str) -> bool:
    """Accept only paired GitHub Action SHA changes, with no workflow edits."""
    removed: list[tuple[str, str]] = []
    added: list[tuple[str, str]] = []
    for line in diff.splitlines():
        if line.startswith(("+++", "---")) or not line.startswith(("+", "-")):
            continue
        match = ACTION_USE_LINE.fullmatch(line[1:])
        if match is None:
            return False
        reference = match.group(1)
        action, separator, revision = reference.rpartition("@")
        if not separator or not action or not ACTION_SHA.fullmatch(revision):
            return False
        (added if line.startswith("+") else removed).append((action, revision))

    if not removed or len(removed) != len(added):
        return False
    # A change may update a SHA, but it may not add/remove/swap the action or
    # modify permissions, triggers, inputs, job conditions, or any other YAML.
    return (
        Counter(action for action, _ in removed) == Counter(action for action, _ in added)
        and Counter(removed) != Counter(added)
    )


def action_pin_only_change(base: str, head: str) -> bool:
    result = subprocess.run(
        [
            "git", "diff", "--unified=0", f"{base}...{head}",
            "--", ".github/workflows/",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return is_action_pin_only_diff_text(result.stdout)


def classify_paths(paths: list[str], *, action_pins_only: bool = False) -> dict[str, bool]:
    """Return broad and lightweight qualification scopes for a PR."""
    full = False
    web = False
    contracts = False
    documentation = False
    action_pins = False
    if not paths:
        # An empty diff is unexpected; fail closed instead of silently skipping
        # qualification when the event payload or checkout history is wrong.
        return {
            "full": True,
            "web": True,
            "contracts": False,
            "docs": False,
            "action_pins": False,
        }
    for raw_path in paths:
        path = PurePosixPath(raw_path).as_posix()
        if path in DOCS_ONLY_ROOT_FILES or path.startswith(("docs/", "history/", "archive/")):
            documentation = True
            continue
        if action_pins_only and path.startswith(".github/workflows/"):
            action_pins = True
            continue
        if path in TARGETED_RELEASE_FILES:
            contracts = True
            continue
        if path in TARGETED_MAINTENANCE_POLICY_FILES:
            contracts = True
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
            # behavior. Only the explicitly tested release helpers above
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
            documentation = True
            continue
        # A new or unclassified path gets the complete gates until someone
        # deliberately adds and tests a narrower rule above.
        full = True
        web = True
    return {
        "full": full,
        "web": web,
        "contracts": contracts and not full,
        "docs": documentation and not contracts and not full,
        "action_pins": action_pins and not full,
    }


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
        scope = {
            "full": True,
            "web": True,
            "contracts": False,
            "docs": False,
            "action_pins": False,
        }
    else:
        if not args.base or not args.head:
            parser.error("pull_request scope requires --base and --head SHAs")
        paths = changed_paths(args.base, args.head)
        action_pins_only = action_pin_only_change(args.base, args.head)
        scope = classify_paths(paths, action_pins_only=action_pins_only)

    for name, enabled in scope.items():
        print(f"{name}={str(enabled).lower()}")
        if args.output:
            with open(args.output, "a", encoding="utf-8") as output:
                output.write(f"{name}={str(enabled).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
