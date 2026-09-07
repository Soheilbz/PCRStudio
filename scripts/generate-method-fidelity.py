#!/usr/bin/env python3
"""Generate runtime and review artifacts from the canonical method-fidelity registry."""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "contracts/method-fidelity.json"
OUT = ROOT / "tools/src/pcr_tools/data/method-fidelity.generated.json"
REPORT_JSON = ROOT / "knowledge/reviews/METHOD-FIDELITY-AUDIT.json"
REPORT_MD = ROOT / "knowledge/reviews/METHOD-FIDELITY-AUDIT.md"


def _canonical() -> tuple[dict, str]:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    digest = hashlib.sha256(SRC.read_bytes()).hexdigest()
    return data, digest


def render_runtime(data: dict, digest: str) -> str:
    projected = dict(data)
    projected["_projection"] = {
        "canonical_source": "contracts/method-fidelity.json",
        "canonical_sha256": digest,
        "generated_by": "scripts/generate-method-fidelity.py",
    }
    return json.dumps(projected, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def report_payload(data: dict, digest: str) -> dict:
    methods = data.get("methods", {})
    roles = data.get("module_method_roles", {})
    grades = Counter(str(row.get("grade") or "") for row in methods.values() if isinstance(row, dict))
    blocked_primary = sorted(
        method_id
        for method_id, row in methods.items()
        if isinstance(row, dict)
        and row.get("scientific_strict_eligible") is False
        and str(row.get("decision_impact") or "").startswith("primary")
    )
    return {
        "status": "PASS",
        "registry_id": data.get("registry_id"),
        "schema_version": data.get("schema_version"),
        "reviewed_date": data.get("reviewed_date"),
        "canonical_source": "contracts/method-fidelity.json",
        "canonical_sha256": digest,
        "method_count": len(methods),
        "module_count": len(roles),
        "grade_counts": dict(sorted(grades.items())),
        "scientific_strict_blocked_primary_methods": blocked_primary,
        "policy": data.get("policy", {}),
        "module_method_roles": roles,
        "methods": methods,
        "generated_by": "scripts/generate-method-fidelity.py",
    }


def render_report_json(data: dict, digest: str) -> str:
    return json.dumps(report_payload(data, digest), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_report_md(data: dict, digest: str) -> str:
    payload = report_payload(data, digest)
    lines = [
        "# PCRStudio Method Fidelity audit",
        "",
        "**Status:** **PASS**",
        "",
        f"Canonical registry: `contracts/method-fidelity.json`",
        f"Canonical SHA-256: `{digest}`",
        f"Methods: **{payload['method_count']}** · Public modules: **{payload['module_count']}**",
        "",
        "## Fidelity grades",
        "",
        "| Grade | Count | Meaning |",
        "| --- | ---: | --- |",
    ]
    definitions = data.get("grade_definitions", {})
    for grade, count in payload["grade_counts"].items():
        lines.append(f"| `{grade}` | {count} | {definitions.get(grade, '')} |")
    lines += [
        "",
        "## Scientific-Strict policy",
        "",
        "Named methods may drive primary Scientific-Strict decisions only when the declared fidelity authority permits it. "
        "Internal compatible/heuristic logic is never silently relabelled as an upstream method; proprietary or incompletely published methods remain external-authority/refusal boundaries.",
        "",
        "Primary methods explicitly blocked from Scientific-Strict until a higher-fidelity authority path exists:",
        "",
    ]
    for method_id in payload["scientific_strict_blocked_primary_methods"]:
        row = data["methods"][method_id]
        lines.append(f"- `{method_id}` — {row.get('display_name')} — {row.get('grade')}")
    lines += ["", "## Method registry", "", "| Method | Grade | Decision impact | Strict | Claim boundary |", "| --- | --- | --- | --- | --- |"]
    for method_id, row in sorted(data.get("methods", {}).items()):
        boundary = str(row.get("claim_boundary") or "").replace("|", "\\|")
        lines.append(
            f"| `{method_id}` | `{row.get('grade')}` | `{row.get('decision_impact')}` | "
            f"{'yes' if row.get('scientific_strict_eligible') else 'no'} | {boundary} |"
        )
    lines += ["", "## Module roles", ""]
    for module_id, role_map in sorted(data.get("module_method_roles", {}).items()):
        bits = []
        for role, methods in role_map.items():
            bits.append(f"{role}: {', '.join(f'`{m}`' for m in methods)}")
        lines.append(f"- **{module_id}** — " + "; ".join(bits))
    lines += [
        "",
        "This is a source-fidelity audit, not native/runtime or wet-lab qualification. F0 means the upstream tool/library is the selected implementation path; it does not mean the tool has already passed the target Linux qualification for this release candidate.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    data, digest = _canonical()
    outputs = {
        OUT: render_runtime(data, digest),
        REPORT_JSON: render_report_json(data, digest),
        REPORT_MD: render_report_md(data, digest),
    }
    if args.check:
        stale = [path for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
        if stale:
            for path in stale:
                print(f"method-fidelity artifact is stale: {path.relative_to(ROOT)}")
            return 1
        print("method-fidelity artifacts: PASS")
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
