#!/usr/bin/env python3
"""Create sidecar in-toto attestation for a built deterministic ZIP.

For qualified Final releases, ``--qualification-result`` binds the archive to
its Linux/native qualification evidence and the exact FILE-MANIFEST hash that
qualification verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tomllib

from release_utils import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--qualification-result", type=Path)
    ap.add_argument("--acceptance-results", type=Path)
    ap.add_argument("--public-evidence-summary", type=Path)
    args = ap.parse_args()
    archive = args.archive.resolve()
    if not archive.is_file():
        raise SystemExit(f"missing archive: {archive}")
    out = args.output.resolve() if args.output else archive.with_suffix(archive.suffix + ".intoto.json")

    foundation = json.loads((ROOT / "knowledge/runtime/foundation.generated.json").read_text(encoding="utf-8"))
    file_manifest_path = ROOT / "release/FILE-MANIFEST.json"
    file_manifest = json.loads(file_manifest_path.read_text(encoding="utf-8"))
    release_identity = tomllib.loads((ROOT / "release/release.toml").read_text(encoding="utf-8"))
    current_manifest_sha = sha256(file_manifest_path)

    native_evidence = {
        "status": "not-bound",
        "qualificationResult": None,
        "qualificationResultSha256": None,
        "qualifiedFileManifestSha256": None,
    }
    acceptance_evidence = {"status": "not-bound", "results": None, "resultsSha256": None}
    if args.qualification_result is not None:
        result_path = args.qualification_result.resolve()
        if not result_path.is_file():
            raise SystemExit(f"missing qualification result: {result_path}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        source_identity = result.get("source_identity") or {}
        if result.get("overall") != "pass":
            raise SystemExit("qualification result is not PASS")
        if source_identity.get("file_manifest_verified") is not True:
            raise SystemExit("qualification result did not verify its FILE-MANIFEST")
        if str(source_identity.get("file_manifest_sha256") or "").lower() != current_manifest_sha:
            raise SystemExit("qualification result is not bound to the current FILE-MANIFEST")
        if source_identity.get("release_class") != file_manifest.get("release_class"):
            raise SystemExit("qualification release class does not match current release class")
        native_evidence = {
            "status": "pass-bound",
            "qualificationResult": result_path.name,
            "qualificationResultSha256": sha256(result_path),
            "qualifiedFileManifestSha256": current_manifest_sha,
        }

    if args.acceptance_results is not None:
        acceptance_path = args.acceptance_results.resolve()
        if not acceptance_path.is_file():
            raise SystemExit(f"missing acceptance results: {acceptance_path}")
        acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
        modules = acceptance.get("modules") or {}
        scenarios = acceptance.get("integration_scenarios") or {}
        if acceptance.get("release_id") != release_identity.get("release_id"):
            raise SystemExit("acceptance results release_id does not match current release identity")
        if acceptance.get("release_class") != file_manifest.get("release_class"):
            raise SystemExit("acceptance results release_class does not match current release class")
        if acceptance.get("source_manifest") != "release/FILE-MANIFEST.json":
            raise SystemExit("acceptance results source_manifest is not canonical")
        if str(acceptance.get("source_sha256") or "").lower() != current_manifest_sha:
            raise SystemExit("acceptance results are not bound to the current FILE-MANIFEST")
        if not modules or any((row or {}).get("status") != "pass" for row in modules.values()):
            raise SystemExit("acceptance results do not show PASS for every module")
        if not scenarios or any((row or {}).get("status") != "pass" for row in scenarios.values()):
            raise SystemExit("acceptance results do not show PASS for every integration scenario")

        # Bind the attestation to the evidence artifacts themselves, not only to
        # the JSON index that names them. Finalization therefore fails if a log
        # is deleted, replaced or edited after acceptance was recorded.
        evidence_files: list[dict[str, str]] = []
        for group_name, rows in (("module", modules), ("scenario", scenarios)):
            for row_id, row in sorted(rows.items()):
                evidence = (row or {}).get("evidence") or {}
                rel = str(evidence.get("path") or "")
                expected = str(evidence.get("sha256") or "").lower()
                command = str(evidence.get("command") or "").strip()
                selector = str(evidence.get("test_selector") or "").strip()
                exit_code = evidence.get("exit_code")
                if not rel or len(expected) != 64:
                    raise SystemExit(f"{group_name} {row_id} lacks evidence path/SHA-256")
                if not command or not selector or exit_code != 0:
                    raise SystemExit(f"{group_name} {row_id} lacks command/test selector/exit_code=0 provenance")
                evidence_path = Path(rel)
                if not evidence_path.is_absolute():
                    evidence_path = ROOT / evidence_path
                evidence_path = evidence_path.resolve()
                try:
                    evidence_path.relative_to(ROOT.resolve())
                except ValueError as exc:
                    raise SystemExit(f"{group_name} {row_id} evidence escapes the project tree") from exc
                if not evidence_path.is_file():
                    raise SystemExit(f"{group_name} {row_id} evidence file is missing: {rel}")
                actual = sha256(evidence_path)
                if actual != expected:
                    raise SystemExit(f"{group_name} {row_id} evidence SHA-256 mismatch")
                evidence_files.append({"kind": group_name, "id": row_id, "path": rel.replace("\\", "/"), "sha256": actual, "command": command, "test_selector": selector, "exit_code": 0})
        evidence_set_sha = hashlib.sha256(
            json.dumps(evidence_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        acceptance_evidence = {
            "status": "pass-bound",
            "results": acceptance_path.name,
            "resultsSha256": sha256(acceptance_path),
            "releaseId": acceptance.get("release_id"),
            "releaseClass": acceptance.get("release_class"),
            "qualifiedFileManifestSha256": current_manifest_sha,
            "evidenceFiles": evidence_files,
            "evidenceSetSha256": evidence_set_sha,
        }

    public_summary = None
    if args.public_evidence_summary is not None:
        summary_path = args.public_evidence_summary.resolve()
        if not summary_path.is_file():
            raise SystemExit(f"missing public evidence summary: {summary_path}")
        public_summary = {"name": summary_path.name, "sha256": sha256(summary_path)}

    payload = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": archive.name, "digest": {"sha256": sha256(archive)}}],
        "predicateType": "https://pcrstudio.local/attestation/deterministic-source-archive/v2",
        "predicate": {
            "releaseClass": file_manifest.get("release_class"),
            "foundationRelease": foundation["foundation_release"],
            "builder": "scripts/build-deterministic-zip.py",
            "verification": "scripts/verify-release.py --archive",
            "nativeQualification": native_evidence,
            "functionalAcceptance": acceptance_evidence,
            "publicEvidenceSummary": public_summary,
            "signatureStatus": "unsigned-public-source",
            "signatureInstruction": "Use scripts/sign-release.sh or scripts/sign-release.sh with the operator/CI signing identity.",
        },
    }
    write_json(out, payload)
    print(f"generated {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
