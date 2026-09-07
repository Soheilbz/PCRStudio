#!/usr/bin/env python3
"""Generate the current Linux source-consistency evidence.

This report is deliberately source-only.  It records deterministic structural
facts from the release tree and points at the explicit native Linux gate for
claims that require Cargo, pnpm, Docker, or scientific executables.
"""
from __future__ import annotations

import argparse
import json
import stat
import tomllib
from collections import Counter
from pathlib import Path

from release_utils import SKIP_PARTS, load_release_identity, source_files, write_json

ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = ROOT / "release/current/CURRENT-STATIC-CONSISTENCY-AUDIT.json"
MD_OUT = ROOT / "release/current/CURRENT-STATIC-CONSISTENCY-AUDIT.md"
FORBIDDEN_PLATFORM_SUFFIXES = {".ps1", ".bat", ".cmd"}
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".next", "node_modules", "target"}


def inventory() -> dict[str, object]:
    files = source_files(ROOT)
    counts: Counter[str] = Counter()
    forbidden: list[str] = []
    executable_shebang_missing: list[str] = []
    crlf: list[str] = []

    for rel, path in files.items():
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_PLATFORM_SUFFIXES:
            forbidden.append(rel)
        if suffix == ".py": counts["python"] += 1
        elif suffix == ".json": counts["json"] += 1
        elif suffix == ".toml": counts["toml"] += 1
        elif suffix in {".ts", ".tsx"}: counts["typescript_tsx"] += 1
        elif suffix in {".yml", ".yaml"}: counts["yaml"] += 1
        elif suffix == ".md": counts["markdown"] += 1
        elif suffix == ".rs": counts["rust"] += 1
        elif suffix == ".sh": counts["shell"] += 1

        raw = path.read_bytes()
        if b"\0" not in raw and b"\r\n" in raw:
            crlf.append(rel)
        if raw.startswith(b"#!") and not (path.stat().st_mode & stat.S_IXUSR):
            executable_shebang_missing.append(rel)

    symlinks: list[str] = []
    collisions: list[tuple[str, str]] = []
    folded: dict[str, str] = {}
    caches: list[str] = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        rel_s = rel.as_posix()
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        if path.is_symlink():
            symlinks.append(rel_s)
        if any(part in CACHE_PARTS for part in rel.parts):
            caches.append(rel_s)
            continue
        key = rel_s.casefold()
        if key in folded and folded[key] != rel_s:
            collisions.append((folded[key], rel_s))
        folded[key] = rel_s

    modules = tomllib.loads((ROOT / "contracts/modules.toml").read_text(encoding="utf-8"))
    engines = tomllib.loads((ROOT / "contracts/engines.toml").read_text(encoding="utf-8"))
    module_rows = modules.get("module", [])
    engine_rows = engines.get("engine", [])

    source_qualification_status = "NOT_RECORDED"
    qualification_path = ROOT / "release/current/SOURCE-QUALIFICATION.json"
    if qualification_path.is_file():
        try:
            source_qualification_status = str(json.loads(qualification_path.read_text(encoding="utf-8")).get("status", "UNKNOWN"))
        except Exception:
            source_qualification_status = "INVALID"

    identity = load_release_identity(ROOT)
    violations = forbidden + symlinks + [f"case:{a}|{b}" for a, b in collisions] + caches + crlf + executable_shebang_missing
    return {
        "schema_version": "2.0.0",
        "release_id": identity["release_id"],
        "release_class": identity["release_class"],
        "archive_prefix": identity["archive_prefix"],
        "platform_authority": "linux-x86_64",
        "status": "PASS" if not violations else "FAIL",
        "scope": "deterministic current-tree source/static consistency; native execution remains delegated to scripts/run-linux-qualification.py",
        "counts": {"files": len(files), **dict(sorted(counts.items()))},
        "public_inventory": {
            "engines": len(engine_rows),
            "modules": len(module_rows),
            "experimental_modules": sum(1 for row in module_rows if str(row.get("status", "")).lower() == "experimental"),
            "stable_modules": sum(1 for row in module_rows if str(row.get("status", "")).lower() == "stable"),
        },
        "linux_hygiene": {
            "active_powershell_cmd_batch_files": forbidden,
            "symlinks": symlinks,
            "case_collisions": collisions,
            "cache_build_residue": caches,
            "crlf_text_files": crlf,
            "shebang_scripts_missing_executable_bit": executable_shebang_missing,
        },
        "architecture": {
            "application_layer": (ROOT / "crates/pcr-application/Cargo.toml").is_file(),
            "external_runner": (ROOT / "crates/pcr-runner/Cargo.toml").is_file(),
            "migration_binary": (ROOT / "crates/pcr-server/src/bin/pcr-migrate.rs").is_file(),
            "linux_doctor": (ROOT / "scripts/doctor-linux.py").is_file(),
            "one_command_bootstrap": (ROOT / "bootstrap.sh").is_file(),
            "runner_adr": (ROOT / "docs/adr/0009-external-scientific-runner-and-linux-release-boundary.md").is_file(),
        },
        "source_qualification": {
            "status": source_qualification_status,
            "entrypoint": "scripts/qualify-source.py",
        },
        "native_external_gate": {
            "status": "NOT_ASSERTED_BY_THIS_REPORT",
            "entrypoint": "scripts/run-linux-qualification.py --full --require-functional-acceptance",
            "requires": ["Rust/Cargo", "Node/pnpm dependencies", "Docker Compose", "scientific native artifacts", "approved specificity reference database"],
        },
    }


def render_md(data: dict[str, object]) -> str:
    counts = data["counts"]
    inv = data["public_inventory"]
    hygiene = data["linux_hygiene"]
    arch = data["architecture"]
    yes = lambda value: "PASS" if value else "FAIL"
    return f"""# CURRENT static consistency audit

**Status:** **{data['status']}**
**Platform authority:** Linux x86_64
**Scope:** deterministic current-tree source/static consistency. Native dependency-backed and container/scientific execution is an explicit separate gate.

## Current Linux snapshot

- Source files represented: **{counts['files']}**
- Python: **{counts.get('python', 0)}**
- Rust: **{counts.get('rust', 0)}**
- TypeScript/TSX: **{counts.get('typescript_tsx', 0)}**
- JSON: **{counts.get('json', 0)}**
- TOML: **{counts.get('toml', 0)}**
- YAML: **{counts.get('yaml', 0)}**
- Shell: **{counts.get('shell', 0)}**
- Public engines/modules: **{inv['engines']} / {inv['modules']}**
- Experimental/stable modules: **{inv['experimental_modules']} / {inv['stable_modules']}**
- Active PowerShell/CMD/BAT files: **{len(hygiene['active_powershell_cmd_batch_files'])}**
- Symlinks: **{len(hygiene['symlinks'])}**
- Case-only collisions: **{len(hygiene['case_collisions'])}**
- Cache/build residue: **{len(hygiene['cache_build_residue'])}**
- CRLF text files: **{len(hygiene['crlf_text_files'])}**
- Shebang scripts missing executable bit: **{len(hygiene['shebang_scripts_missing_executable_bit'])}**

## Architecture-hardening markers

- Transport-neutral application layer: **{yes(arch['application_layer'])}**
- External PostgreSQL-backed scientific runner: **{yes(arch['external_runner'])}**
- One-shot migration binary: **{yes(arch['migration_binary'])}**
- Read-only Linux doctor: **{yes(arch['linux_doctor'])}**
- One-command Linux bootstrap: **{yes(arch['one_command_bootstrap'])}**
- Runner/Linux release-boundary ADR: **{yes(arch['runner_adr'])}**

## Qualification boundary

`scripts/qualify-source.py` is the source qualification authority and currently records **{data['source_qualification']['status']}** in `release/current/SOURCE-QUALIFICATION.json`. The source/static report does not convert unexecuted native work into a PASS. Rust/Cargo builds, dependency-backed Web tests/builds, production Docker topology, migrations, native scientific binaries and approved specificity-database execution belong to:

```bash
python3 scripts/run-linux-qualification.py --full --require-functional-acceptance
```

The public modules remain computationally experimental until the explicit native and scientific qualification/promotion gates pass.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = inventory()
    rendered_json = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    rendered_md = render_md(data)
    if args.check:
        expected = {JSON_OUT: rendered_json, MD_OUT: rendered_md}
        drift = [str(path.relative_to(ROOT)) for path, content in expected.items() if not path.is_file() or path.read_text(encoding="utf-8") != content]
        if drift:
            raise SystemExit("current static consistency audit drift: " + ", ".join(drift))
        print("current static consistency audit check PASS")
        return 0
    JSON_OUT.write_text(rendered_json, encoding="utf-8", newline="\n")
    MD_OUT.write_text(rendered_md, encoding="utf-8", newline="\n")
    print(f"generated {JSON_OUT.relative_to(ROOT)} and {MD_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
