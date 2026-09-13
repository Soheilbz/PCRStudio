#!/usr/bin/env python3
"""Classify a pull request into stable, testable PCRStudio CI scopes.

Unknown paths deliberately select every broad gate. Narrow exceptions are
limited to documentation, current release evidence, release-bundle tooling,
and dependency-maintenance policy files with direct, always-run coverage.
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
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/dependency-review.yml",
    ".github/workflows/production-deploy.yml",
    "release/release.toml",
    "scripts/classify-ci-scope.py",
    "scripts/check-linux-bootstrap.py",
    "scripts/pull-release.py",
    "scripts/provision-tools.py",
    "scripts/release_bundle.py",
}
TARGETED_MAINTENANCE_POLICY_FILES = {
    ".github/dependabot.yml",
    "contracts/capability-maturity.json",
    "contracts/maintenance-exceptions.json",
    "scripts/audit/release.py",
}
TARGETED_RELEASE_EVIDENCE_FILES = {
    "release/INDEX.md",
    "release/RELEASE-NOTES.md",
    "release/FILE-MANIFEST.json",
    "release/PATCH-MANIFEST.json",
    "release/RUNTIME-CONTRACT-MANIFEST.json",
    "release/SHA256SUMS.txt",
    "release/current/ENGINEERING-CLOSURE-REPORT.md",
    "release/current/CURRENT-FOUNDATION-CLOSURE.md",
    "release/current/CURRENT-STATIC-CONSISTENCY-AUDIT.json",
    "release/current/CURRENT-STATIC-CONSISTENCY-AUDIT.md",
    "release/current/SBOM.cdx.json",
    "release/current/SOURCE-ATTESTATION.intoto.json",
}
TARGETED_STORAGE_FILES = {
    ".env.example",
    ".env.vm.example",
    "contracts/operations.toml",
    "knowledge/runtime/operations.generated.json",
    "scripts/audit/operations.py",
    "scripts/backup-db.sh",
    "scripts/backup-restore-drill.sh",
    "scripts/bootstrap-linux.py",
    "scripts/ci-qualification-gate.py",
    "scripts/generate-operations-policy.py",
    "scripts/prune-backups.sh",
    "scripts/storage-guard.py",
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
        if path in TARGETED_RELEASE_EVIDENCE_FILES:
            # Narrative/evidence-only updates do not alter product execution.
            # The fast contract job still verifies static source and the exact
            # generated release manifests, attestation, and checksums.
            contracts = True
            continue
        if path in TARGETED_STORAGE_FILES:
            # Dedicated-host storage changes have direct source regression
            # coverage in check-linux-bootstrap.py and the operations audit.
            # Keep the Docker/runtime-wide matrix for execution/topology changes.
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


def full_scope() -> dict[str, bool]:
    return {
        "full": True,
        "web": True,
        "contracts": False,
        "docs": False,
        "action_pins": False,
    }


def classify_event_paths(
    event: str,
    paths: list[str] | None,
    *,
    action_pins_only: bool = False,
) -> dict[str, bool]:
    """Use the tested path scope for PRs and pushes; fail closed otherwise."""
    if event not in {"pull_request", "push"} or paths is None:
        return full_scope()
    return classify_paths(paths, action_pins_only=action_pins_only)


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

    if args.event == "pull_request":
        if not args.base or not args.head:
            parser.error("pull_request scope requires --base and --head SHAs")
        paths = changed_paths(args.base, args.head)
        action_pins_only = action_pin_only_change(args.base, args.head)
        scope = classify_event_paths(args.event, paths, action_pins_only=action_pins_only)
    elif args.event == "push":
        if not args.base or args.base == "0" * 40 or not args.head:
            scope = full_scope()
        else:
            paths = changed_paths(args.base, args.head)
            action_pins_only = action_pin_only_change(args.base, args.head)
            scope = classify_event_paths(args.event, paths, action_pins_only=action_pins_only)
    else:
        scope = full_scope()

    for name, enabled in scope.items():
        print(f"{name}={str(enabled).lower()}")
        if args.output:
            with open(args.output, "a", encoding="utf-8") as output:
                output.write(f"{name}={str(enabled).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
