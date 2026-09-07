#!/usr/bin/env python3
"""Generate deterministic PCRStudio public-source manifests.

This generator consumes canonical/generated contracts only. It deliberately
never imports PCRStudio runtime modules or native scientific dependencies.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from release_utils import MANIFEST_EXCLUDED, PATCH_EXCLUDED, json_bytes, load_release_identity, sha256, source_files, write_json

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
IDENTITY = load_release_identity(ROOT)
RELEASE_CLASS = IDENTITY["release_class"]
BASELINE_KIND = IDENTITY["baseline_kind"]


def load(rel: str) -> dict[str, object]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def runtime_manifest_payload() -> dict[str, object]:
    foundation = load("knowledge/runtime/foundation.generated.json")
    modules = load("knowledge/runtime/module-contracts.generated.json")
    engines = load("knowledge/runtime/engine-contracts.generated.json")
    tools = load("knowledge/runtime/tool-contracts.generated.json")
    http = load("contracts/http-api.generated.json")
    module_rows = modules["modules"]
    engine_rows = engines["engines"]
    tool_rows = tools["tools"]
    return {
        "schema_version": "2.0.0",
        "release_class": RELEASE_CLASS,
        "foundation_release": foundation["foundation_release"],
        "module_contract_version": foundation["module_contract_version"],
        "ipc_protocol_version": foundation["ipc_protocol_version"],
        "request_schema_version": foundation["request_schema_version"],
        "result_schema_version": foundation["result_schema_version"],
        "draft_schema_version": foundation["draft_schema_version"],
        "api_version": foundation["api_version"],
        "counts": {
            "modules": len(module_rows),
            "engines": len(engine_rows),
            "tools": len(tool_rows),
            "http_operations": len(http["endpoints"]),
        },
        "canonical_sources": foundation["canonical_sources"],
        "source_fingerprints": {
            rel: sha256(ROOT / rel)
            for rel in (
                "contracts/http-api.toml",
                "contracts/http-api.generated.json",
                "crates/pcr-core/profiles.toml",
                "knowledge/runtime/linux-acceptance-matrix.json",
                "knowledge/runtime/module-contracts.generated.json",
                "knowledge/runtime/engine-contracts.generated.json",
                "knowledge/runtime/tool-contracts.generated.json",
                "docs/openapi.generated.json",
            )
        },
        "modules": module_rows,
        "engines": engine_rows,
        "tools": tool_rows,
        "qualification_boundary": {
            "source_integrity": IDENTITY["source_qualification_label"],
            "native_linux": "external-gate-delegated-to-operator",
            "native_entrypoint": "scripts/run-linux-qualification.py",
        },
    }


def write_runtime_manifest() -> None:
    write_json(RELEASE / "RUNTIME-CONTRACT-MANIFEST.json", runtime_manifest_payload())


def baseline_manifest_records(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("files")
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"baseline manifest has no file rows: {path}")
    records: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise SystemExit(f"invalid baseline manifest row in {path}")
        rel = str(row["path"])
        if rel in PATCH_EXCLUDED:
            continue
        digest = row.get("sha256")
        size = row.get("bytes")
        if not isinstance(digest, str) or len(digest) != 64 or not isinstance(size, int):
            raise SystemExit(f"invalid baseline manifest hash/size for {rel}")
        records[rel] = {"sha256": digest, "bytes": size}
    return records


def patch_manifest_payload(*, baseline: Path | None = None, baseline_manifest: Path | None = None) -> dict[str, object]:
    if (baseline is None) == (baseline_manifest is None):
        raise SystemExit("provide exactly one baseline source: tree or file manifest")
    if baseline is not None:
        before_files = source_files(baseline, excluded=PATCH_EXCLUDED)
        before = {
            key: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for key, path in before_files.items()
        }
        baseline_name = baseline.name
        baseline_authority = "extracted-source-tree"
    else:
        assert baseline_manifest is not None
        before = baseline_manifest_records(baseline_manifest)
        baseline_name = baseline_manifest.name
        baseline_authority = "immutable-file-manifest"

    after_files = source_files(ROOT, excluded=PATCH_EXCLUDED)
    after = {
        key: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for key, path in after_files.items()
    }
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(key for key in set(before) & set(after) if before[key]["sha256"] != after[key]["sha256"])
    return {
        "schema_version": "2.1.0",
        "baseline": baseline_name,
        "baseline_kind": BASELINE_KIND,
        "baseline_authority": baseline_authority,
        "release_class": RELEASE_CLASS,
        "excluded_generated_release_artifacts": sorted(PATCH_EXCLUDED),
        "summary": {"added": len(added), "modified": len(modified), "removed": len(removed)},
        "added": [
            {"path": key, "bytes": after[key]["bytes"], "sha256": after[key]["sha256"]}
            for key in added
        ],
        "modified": [
            {
                "path": key,
                "before_sha256": before[key]["sha256"],
                "after_sha256": after[key]["sha256"],
                "before_bytes": before[key]["bytes"],
                "after_bytes": after[key]["bytes"],
            }
            for key in modified
        ],
        "removed": [
            {"path": key, "before_sha256": before[key]["sha256"], "before_bytes": before[key]["bytes"]}
            for key in removed
        ],
    }


def write_patch_manifest(*, baseline: Path | None = None, baseline_manifest: Path | None = None) -> None:
    write_json(
        RELEASE / "PATCH-MANIFEST.json",
        patch_manifest_payload(baseline=baseline, baseline_manifest=baseline_manifest),
    )


def file_manifest_payload() -> dict[str, object]:
    files = source_files(ROOT, excluded=MANIFEST_EXCLUDED)
    return {
        "schema_version": "2.0.0",
        "release_class": RELEASE_CLASS,
        "excluded_generated_verification_artifacts": sorted(MANIFEST_EXCLUDED),
        "file_count": len(files),
        "files": [
            {"path": key, "bytes": files[key].stat().st_size, "sha256": sha256(files[key])}
            for key in sorted(files)
        ],
    }


def write_file_manifest() -> None:
    write_json(RELEASE / "FILE-MANIFEST.json", file_manifest_payload())


def sha256sums_text() -> str:
    # Hash every current release authority plus top-level machine manifests.
    names = [
        "release/FILE-MANIFEST.json",
        "release/PATCH-MANIFEST.json",
        "release/RUNTIME-CONTRACT-MANIFEST.json",
    ]
    current = RELEASE / "current"
    if current.is_dir():
        names.extend(
            path.relative_to(ROOT).as_posix()
            for path in sorted(current.rglob("*"))
            if path.is_file() and path.name != "SHA256SUMS.txt"
        )
    for rel in (
        "docs/openapi.generated.json",
        "contracts/http-api.generated.json",
        "knowledge/runtime/foundation.generated.json",
        "knowledge/runtime/module-contracts.generated.json",
        "knowledge/runtime/engine-contracts.generated.json",
        "knowledge/runtime/tool-contracts.generated.json",
        "knowledge/runtime/linux-acceptance-matrix.json",
        "scripts/run-linux-qualification.py",
    ):
        if rel not in names:
            names.append(rel)
    lines = []
    for rel in sorted(set(names)):
        path = ROOT / rel
        if not path.is_file():
            raise SystemExit(f"missing release artifact for SHA256SUMS: {rel}")
        lines.append(f"{sha256(path)}  {rel}")
    return "\n".join(lines) + "\n"


def write_sha256sums() -> None:
    (RELEASE / "SHA256SUMS.txt").write_text(sha256sums_text(), encoding="utf-8")


def check_outputs(*, baseline: Path | None = None, baseline_manifest: Path | None = None) -> None:
    expected = {
        RELEASE / "RUNTIME-CONTRACT-MANIFEST.json": json_bytes(runtime_manifest_payload()),
        RELEASE / "PATCH-MANIFEST.json": json_bytes(
            patch_manifest_payload(baseline=baseline, baseline_manifest=baseline_manifest)
        ),
        RELEASE / "FILE-MANIFEST.json": json_bytes(file_manifest_payload()),
        RELEASE / "SHA256SUMS.txt": sha256sums_text().encode("utf-8"),
    }
    changed = [
        path.relative_to(ROOT).as_posix()
        for path, content in expected.items()
        if not path.is_file() or path.read_bytes() != content
    ]
    if changed:
        raise SystemExit("release manifest drift: " + ", ".join(changed))
    print("release manifest check PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--baseline", type=Path, help="Extracted immutable baseline source tree")
    group.add_argument(
        "--baseline-manifest",
        type=Path,
        help="Immutable FILE-MANIFEST.json from the baseline release (path/hash/size authority)",
    )
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    baseline = args.baseline.resolve() if args.baseline else None
    baseline_manifest = args.baseline_manifest.resolve() if args.baseline_manifest else None
    if baseline is not None and not baseline.is_dir():
        raise SystemExit(f"baseline is not a directory: {baseline}")
    if baseline_manifest is not None and not baseline_manifest.is_file():
        raise SystemExit(f"baseline manifest is not a file: {baseline_manifest}")
    if args.check:
        check_outputs(baseline=baseline, baseline_manifest=baseline_manifest)
        return 0
    write_runtime_manifest()
    write_patch_manifest(baseline=baseline, baseline_manifest=baseline_manifest)
    write_file_manifest()
    write_sha256sums()
    print("generated current runtime/patch/file manifests and SHA256SUMS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
