#!/usr/bin/env python3
"""Fail a CI aggregate unless all gates required by the classified scope pass."""
from __future__ import annotations

import argparse


def validate_results(
    *,
    full: str,
    web: str,
    changes: str,
    fast: str,
    source: str,
    image: str,
    browser: str,
) -> list[str]:
    """Return actionable gate failures; out-of-scope jobs must stay skipped."""
    failures: list[str] = []
    if full not in {"true", "false"} or web not in {"true", "false"}:
        return ["scope outputs must be exactly 'true' or 'false'"]
    if web == "true" and full != "true":
        failures.append("invalid scope: Web qualification cannot be enabled without full qualification")
    if changes != "success":
        failures.append(f"scope classification did not succeed (result={changes})")
    if fast != "success":
        failures.append(f"fast feedback did not succeed (result={fast})")

    for name, result in (("source", source), ("Linux image", image)):
        expected = "success" if full == "true" else "skipped"
        if result != expected:
            failures.append(f"{name} gate result was {result}; expected {expected} for full={full}")

    expected_browser = "success" if web == "true" else "skipped"
    if browser != expected_browser:
        failures.append(
            f"Web browser gate result was {browser}; expected {expected_browser} for web={web}"
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("full", "web", "changes", "fast", "source", "image", "browser"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    failures = validate_results(
        full=args.full,
        web=args.web,
        changes=args.changes,
        fast=args.fast,
        source=args.source,
        image=args.image,
        browser=args.browser,
    )
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(f"PCRStudio CI qualification gate: PASS (full={args.full}, web={args.web})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
