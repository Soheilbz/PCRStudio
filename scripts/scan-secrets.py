#!/usr/bin/env python3
"""High-confidence source secret scan used before release and in CI.

This deliberately avoids entropy heuristics: scientific fixtures contain many long
random-looking sequences and checksums. It catches credential formats that should
never be committed and private-key material, while test-only database passwords
remain ordinary fixture text rather than false positives.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{30,}\b"),
    "gitlab-token": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
SKIP_PREFIXES = (".git/", ".local/", "node_modules/", "web/.next/", "target/", "tools/.venv/")


def candidates() -> list[Path]:
    try:
        raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        names = [part.decode("utf-8") for part in raw.split(b"\0") if part]
        return [ROOT / name for name in names]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return [path for path in ROOT.rglob("*") if path.is_file()]


def main() -> int:
    findings: list[str] = []
    checked = 0
    for path in candidates():
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(SKIP_PREFIXES) or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        checked += 1
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{rel}:{line}: {label}")
    if findings:
        print(f"Secret scan: FAIL ({len(findings)} high-confidence finding(s))")
        for row in findings:
            print(row)
        return 1
    print(f"Secret scan: PASS ({checked} text files; high-confidence credential formats only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
