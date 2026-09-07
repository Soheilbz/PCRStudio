#!/usr/bin/env python3
"""Native Linux acceptance for the four PrimalScheme3 lifecycle operations.

Unlike unit tests, this script does not monkeypatch external execution. It is
called only by the Linux native release qualification after the pinned toolchain has
been imported and identity-checked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pcr_tools import primalscheme_adapter

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tools" / "tests" / "corpus" / "NC_012920.1.fasta"


def common() -> dict:
    return {
        "template": REFERENCE.read_text(encoding="utf-8"),
        "name": "NC_012920.1",
        "assay": {"id": "tiled-scheme"},
        "tilingBackend": "primalscheme3",
        "tilingAlignmentMode": "prealigned",
        "tilingMinBaseFrequency": 0.0,
        "tilingBacktrack": False,
        "tilingHighGc": False,
    }


def create_scheme() -> dict:
    return primalscheme_adapter.run(
        {**common(), "tilingOperation": "scheme-create", "overlap": 75, "pools": 2}
    )


def require_baseline_artifacts(result: dict) -> tuple[str, str, str]:
    artifacts = result.get("scheme_artifacts") or {}
    bed = ((artifacts.get("primer_bed") or {}).get("content") or "").strip()
    config = ((artifacts.get("config_json") or {}).get("content") or "").strip()
    tiles = result.get("tiles") or []
    if not bed or not config or not tiles:
        raise RuntimeError("native scheme-create did not return BED/config/tiles required for lifecycle acceptance")
    name = str(tiles[0].get("name") or "").strip()
    if not name:
        raise RuntimeError("native scheme-create returned no primer-pair stem for replacement acceptance")
    return bed + "\n", config + "\n", name


def run(operation: str) -> dict:
    if operation == "scheme-create":
        return create_scheme()
    if operation == "panel-create":
        return primalscheme_adapter.run(
            {
                **common(),
                "tilingOperation": "panel-create",
                "panelMode": "region-only",
                "pools": 2,
                "regionBed": "NC_012920.1\t1000\t5000\n",
            }
        )
    baseline = create_scheme()
    bed, config, primer_name = require_baseline_artifacts(baseline)
    if operation == "repair-mode":
        return primalscheme_adapter.run(
            {
                **common(),
                "tilingOperation": "repair-mode",
                "existingBed": bed,
                "schemeConfig": config,
            }
        )
    if operation == "scheme-replace":
        return primalscheme_adapter.run(
            {
                **common(),
                "tilingOperation": "scheme-replace",
                "existingBed": bed,
                "schemeConfig": config,
                "primerName": primer_name,
            }
        )
    raise ValueError(operation)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True, choices=["scheme-create", "panel-create", "repair-mode", "scheme-replace"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.operation)
    backend = result.get("primary_backend") or {}
    if backend.get("id") != "primalscheme3" or backend.get("configured_version") != "3.3.0":
        raise RuntimeError("native lifecycle acceptance did not use pinned PrimalScheme3 3.3.0")
    runs = (result.get("lifecycle") or {}).get("tool_runs") or []
    if not any(run.get("tool_id") == "primalscheme3" and run.get("exit_status") == 0 for run in runs):
        raise RuntimeError("native lifecycle acceptance lacks a successful PrimalScheme3 tool-run record")
    payload = {
        "schema_version": "1.0.0",
        "operation": args.operation,
        "backend": backend,
        "tool_runs": runs,
        "tiles": len(result.get("tiles") or []),
        "orderable": bool((result.get("orderability") or {}).get("orderable")),
        "artifact_sha256": {k: v.get("sha256") for k, v in (result.get("scheme_artifacts") or {}).items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Native PrimalScheme lifecycle PASS: {args.operation} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
