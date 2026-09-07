#!/usr/bin/env python3
"""Create deterministic in-toto source attestation for the current source release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from release_utils import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "release/current/SOURCE-ATTESTATION.intoto.json"
SUBJECTS = (
    "release/FILE-MANIFEST.json",
    "release/PATCH-MANIFEST.json",
    "release/RUNTIME-CONTRACT-MANIFEST.json",
    "release/current/SBOM.cdx.json",
    "knowledge/runtime/foundation.generated.json",
    "knowledge/runtime/module-contracts.generated.json",
    "knowledge/runtime/engine-contracts.generated.json",
    "knowledge/runtime/tool-contracts.generated.json",
    "docs/openapi.generated.json",
)


def payload() -> dict[str, object]:
    foundation = json.loads((ROOT / "knowledge/runtime/foundation.generated.json").read_text(encoding="utf-8"))
    file_manifest = json.loads((ROOT / "release/FILE-MANIFEST.json").read_text(encoding="utf-8"))
    subjects = []
    for rel in SUBJECTS:
        path = ROOT / rel
        if not path.is_file():
            raise SystemExit(f"attestation subject missing: {rel}")
        subjects.append({"name": rel, "digest": {"sha256": sha256(path)}})
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://pcrstudio.local/attestation/source-qualification/v1",
        "predicate": {
            "releaseClass": file_manifest.get("release_class"),
            "foundationRelease": foundation["foundation_release"],
            "moduleContractVersion": foundation["module_contract_version"],
            "ipcProtocolVersion": foundation["ipc_protocol_version"],
            "apiVersion": foundation["api_version"],
            "qualificationScope": "source-integrity-and-environment-independent-gates",
            "nativeLinuxQualification": {
                "status": "delegated-external-gate",
                "claim": "not asserted by this source attestation",
                "entrypoint": "scripts/run-linux-qualification.py",
            },
            "reproducibility": {
                "manifest": "release/FILE-MANIFEST.json",
                "sbom": "release/current/SBOM.cdx.json",
                "deterministicArchiveBuilder": "scripts/build-deterministic-zip.py",
            },
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    data = payload()
    expected = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != expected:
            raise SystemExit("source attestation drift")
        print("source attestation check PASS")
        return 0
    write_json(args.output, data)
    print(f"generated {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
