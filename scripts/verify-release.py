#!/usr/bin/env python3
"""Independent verifier for PCRStudio source releases."""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT / "scripts"))
from release_utils import MANIFEST_EXCLUDED, SKIP_PARTS, sha256, source_files  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def verify_tree(root: Path) -> dict[str, int]:
    errors: list[str] = []
    manifest_path = root / "release/FILE-MANIFEST.json"
    sums_path = root / "release/SHA256SUMS.txt"
    sbom_path = root / "release/current/SBOM.cdx.json"
    attest_path = root / "release/current/SOURCE-ATTESTATION.intoto.json"
    for path in (manifest_path, sums_path, sbom_path, attest_path):
        if not path.is_file():
            errors.append(f"missing verification artifact: {path.relative_to(root)}")
    if errors:
        raise SystemExit("\n".join(errors))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("files") or []
    expected = {str(row["path"]): row for row in rows}
    actual = source_files(root, excluded=MANIFEST_EXCLUDED)
    if set(expected) != set(actual):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        errors.append(f"manifest file-set mismatch missing={missing[:10]} extra={extra[:10]}")
    mismatches = 0
    for rel, row in expected.items():
        path = root / rel
        if not path.is_file():
            mismatches += 1; continue
        if path.stat().st_size != int(row["bytes"]) or sha256(path) != row["sha256"]:
            mismatches += 1
    if mismatches:
        errors.append(f"FILE-MANIFEST mismatches={mismatches}")

    sum_count = 0; sum_mismatch = 0
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, sep, rel = line.partition("  ")
        sum_count += 1
        path = root / rel
        if not sep or not HEX64.match(digest) or not path.is_file() or sha256(path) != digest:
            sum_mismatch += 1
    if sum_mismatch:
        errors.append(f"SHA256SUMS mismatches={sum_mismatch}")

    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.6" or not sbom.get("components"):
        errors.append("SBOM is not a non-empty CycloneDX 1.6 document")

    att = json.loads(attest_path.read_text(encoding="utf-8"))
    if att.get("_type") != "https://in-toto.io/Statement/v1":
        errors.append("source attestation type mismatch")
    for subject in att.get("subject") or []:
        rel = subject.get("name")
        digest = ((subject.get("digest") or {}).get("sha256"))
        path = root / str(rel)
        if not path.is_file() or sha256(path) != digest:
            errors.append(f"attestation subject mismatch: {rel}")

    eligible = source_files(root)
    lower: dict[str, str] = {}
    collisions = []
    for rel in eligible:
        folded = rel.casefold()
        if folded in lower and lower[folded] != rel:
            collisions.append((lower[folded], rel))
        lower[folded] = rel
    symlinks = [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_symlink()
        and not any(part in SKIP_PARTS for part in p.relative_to(root).parts)
    ]
    if collisions:
        errors.append(f"case collisions={collisions[:10]}")
    if symlinks:
        errors.append(f"symlinks present={symlinks[:10]}")
    if errors:
        raise SystemExit("\n".join(errors))
    return {
        "manifest_files": len(expected),
        "manifest_mismatches": 0,
        "sha256sum_files": sum_count,
        "sha256sum_mismatches": 0,
        "sbom_components": len(sbom["components"]),
        "symlinks": 0,
        "case_collisions": 0,
    }


def safe_archive_members(zf: zipfile.ZipFile) -> tuple[str, list[zipfile.ZipInfo]]:
    infos = zf.infolist()
    if not infos:
        raise SystemExit("empty archive")
    roots = set()
    names = set()
    folded = set()
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
            raise SystemExit(f"unsafe or unrooted archive path: {info.filename}")
        roots.add(path.parts[0])
        if info.filename in names or info.filename.casefold() in folded:
            raise SystemExit(f"duplicate/case-colliding ZIP member: {info.filename}")
        names.add(info.filename); folded.add(info.filename.casefold())
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise SystemExit(f"symlink ZIP member forbidden: {info.filename}")
    if len(roots) != 1:
        raise SystemExit(f"archive must have exactly one root directory, got {sorted(roots)}")
    return next(iter(roots)), infos


def verify_archive(archive: Path) -> dict[str, object]:
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad:
            raise SystemExit(f"ZIP CRC failure: {bad}")
        root_name, infos = safe_archive_members(zf)
        shebang_members = 0
        missing_exec: list[str] = []
        for info in infos:
            if info.is_dir():
                continue
            with zf.open(info) as handle:
                prefix = handle.read(2)
            if prefix == b"#!":
                shebang_members += 1
                mode = (info.external_attr >> 16) & 0xFFFF
                if not (mode & stat.S_IXUSR):
                    missing_exec.append(info.filename)
        if missing_exec:
            raise SystemExit(
                "ZIP shebang member(s) missing owner executable bit: "
                + ", ".join(missing_exec[:20])
            )
        scratch = SCRIPT_ROOT / ".local" / "tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="release-verify-", dir=scratch) as tmp:
                zf.extractall(tmp)
                extracted = Path(tmp) / root_name
                tree = verify_tree(extracted)
                expected_members = {f"{root_name}/{rel}" for rel in source_files(extracted)}
                actual_members = {info.filename for info in infos if not info.is_dir()}
                if expected_members != actual_members:
                    raise SystemExit("ZIP member set does not match extracted qualified source tree")
        finally:
            for parent in (scratch, scratch.parent):
                try:
                    parent.rmdir()
                except OSError:
                    pass
    return {
        "archive_sha256": sha256(archive),
        "archive_entries": len(infos),
        "crc": "PASS",
        "shebang_members": shebang_members,
        "shebang_members_missing_executable_bit": 0,
        **tree,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--root", type=Path)
    group.add_argument("--archive", type=Path)
    args = ap.parse_args()
    result = verify_tree(args.root.resolve()) if args.root else verify_archive(args.archive.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
