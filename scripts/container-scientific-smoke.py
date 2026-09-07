#!/usr/bin/env python3
"""Read-only scientific runtime smoke gate for the API container.

This gate deliberately does not approve the scientific Python freeze and does
not require a production specificity database. It proves that every bundled
runtime component is present, hash-bound and version-compatible, then emits the
resolved freeze digest that deployment qualification may approve separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from pcr_tools.process_boundary import (
    ProcessOutputLimitExceeded,
    ProcessTransportError,
    run_bounded_text,
)

CONTRACT = Path("/opt/pcrstudio/contracts/tools.toml")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tree_sha256(root: Path) -> str:
    root = root.resolve()
    if not root.is_dir():
        return ""
    h = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        st = path.lstat()
        mode = st.st_mode & 0o7777
        if path.is_symlink():
            target = os.readlink(path)
            resolved = path.resolve()
            if resolved != root and root not in resolved.parents:
                return ""
            payload = b"L\0" + rel + b"\0" + f"{mode:o}".encode() + b"\0" + target.encode("utf-8")
        elif path.is_dir():
            payload = b"D\0" + rel + b"\0" + f"{mode:o}".encode()
        elif path.is_file():
            payload = b"F\0" + rel + b"\0" + f"{mode:o}".encode() + b"\0" + sha256(path).encode()
        else:
            return ""
        h.update(payload + b"\n")
    return h.hexdigest()


def command_output(argv: list[str], *, cwd: Path | None = None, timeout: int = 20) -> tuple[int, str]:
    try:
        cp = run_bounded_text(
            argv,
            cwd=cwd,
            timeout=timeout,
            stdout_limit=2 * 1024 * 1024,
            stderr_limit=512 * 1024,
        )
    except (OSError, subprocess.TimeoutExpired, ProcessOutputLimitExceeded, ProcessTransportError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return cp.returncode, "\n".join(x for x in (cp.stdout, cp.stderr) if x).strip()[:2000]


def version_matches(expected: str, observed: str) -> bool:
    return bool(re.search(rf"(?<![0-9.]){re.escape(expected)}(?![0-9.])", observed or ""))


def load_contract() -> dict[str, dict[str, Any]]:
    if not CONTRACT.is_file():
        raise SystemExit(f"missing runtime contract: {CONTRACT}")
    data = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    return {str(row["id"]): row for row in data.get("tool", [])}


def check_local(tool_id: str, row: dict[str, Any], version_args: list[str], errors: list[str], results: dict[str, Any]) -> None:
    env_var = str(row.get("env_var") or "")
    hash_var = str(row.get("hash_env_var") or "")
    path = Path(os.environ.get(env_var, "")).expanduser() if env_var else Path()
    expected_hash = os.environ.get(hash_var, "").strip().lower() if hash_var else ""
    item: dict[str, Any] = {"version": row.get("version"), "env_var": env_var, "hash_env_var": hash_var}
    if not env_var or not path.is_file():
        errors.append(f"{tool_id}: executable/interpreter missing via {env_var}")
        item["status"] = "missing"
        results[tool_id] = item
        return
    actual = sha256(path)
    item["artifact_sha256"] = actual
    item["artifact_hash_matches"] = bool(expected_hash and actual == expected_hash)
    if not item["artifact_hash_matches"]:
        errors.append(f"{tool_id}: artifact hash mismatch or missing expected hash")
    code, out = command_output([str(path), *version_args], cwd=path.parent if tool_id == "mafft" else None)
    item["version_command_exit_code"] = code
    item["observed_version"] = out[:300]
    item["version_matches_contract"] = version_matches(str(row.get("version") or ""), out)
    if code != 0 and not out:
        errors.append(f"{tool_id}: version command failed with exit {code}")
    if not item["version_matches_contract"]:
        errors.append(f"{tool_id}: version mismatch; observed {out[:160]!r}")
    item["status"] = "pass" if not any(e.startswith(tool_id + ":") for e in errors) else "fail"
    results[tool_id] = item


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    rows = load_contract()
    errors: list[str] = []
    results: dict[str, Any] = {}

    versions = {
        "mfeprimer": ["version"],
        "ncbi_blast_plus": ["-version"],
        "mafft": ["--version"],
        "primerpooler": ["--version"],
        "primalscheme3": ["--version"],
        "pydna": ["-c", "import importlib.metadata as m; print(m.version('pydna'))"],
    }
    for tool_id in ("mfeprimer", "ncbi_blast_plus", "mafft", "primerpooler", "primalscheme3", "pydna"):
        check_local(tool_id, rows[tool_id], versions[tool_id], errors, results)

    worker = Path(os.environ.get("PCR_PYTHON", "/opt/worker/bin/python"))
    code, out = command_output([
        str(worker), "-c",
        "import importlib.metadata as m; from primer3.thermoanalysis import get_libprimer3_version; "
        "print('primer3-py='+m.version('primer3-py')); print('libprimer3='+str(get_libprimer3_version())); "
        "print('ViennaRNA='+m.version('ViennaRNA'))",
    ])
    results["worker_python"] = {"exit_code": code, "identity": out[:500]}
    for token in ("primer3-py=2.3.0", "libprimer3=2.6.1", "ViennaRNA=2.7.2"):
        if token not in out:
            errors.append(f"worker_python: missing identity token {token!r}")

    mafft_bundle = Path(os.environ.get("PCRSTUDIO_MAFFT_BUNDLE_ROOT", ""))
    mafft_bundle_declared = os.environ.get("PCRSTUDIO_MAFFT_BUNDLE_SHA256", "").strip().lower()
    mafft_bundle_actual = tree_sha256(mafft_bundle) if mafft_bundle.is_dir() else ""
    results["mafft_bundle"] = {
        "path_present": mafft_bundle.is_dir(),
        "declared_sha256": mafft_bundle_declared or None,
        "actual_sha256": mafft_bundle_actual or None,
        "declared_matches_actual": bool(mafft_bundle_declared and mafft_bundle_declared == mafft_bundle_actual),
        # Upstream does not publish a digest for the 7.526 portable archive.
        # This is evidence of what was fetched, not a claim of upstream authenticity.
        "downloaded_archive_sha256": os.environ.get("PCRSTUDIO_MAFFT_ARCHIVE_SHA256", "").strip().lower() or None,
    }
    if not mafft_bundle_declared or mafft_bundle_declared != mafft_bundle_actual:
        errors.append("mafft: portable bundle tree hash mismatch or missing expected hash")

    # A tiny MAFFT workflow catches wrappers that report a version but cannot
    # find their companion binaries after being copied into the runtime image.
    mafft = Path(os.environ.get("PCRSTUDIO_MAFFT", ""))
    if mafft.is_file():
        with tempfile.TemporaryDirectory(prefix="pcrstudio-mafft-") as tmp:
            fasta = Path(tmp) / "smoke.fasta"
            fasta.write_text(">a\nACGTACGT\n>b\nACGTTCGT\n", encoding="ascii")
            code, out = command_output([str(mafft), str(fasta)], cwd=mafft.parent, timeout=30)
            aligned = code == 0 and ">a" in out and ">b" in out and "ACGT" in out
            results["mafft_alignment"] = {"exit_code": code, "pass": aligned}
            if not aligned:
                errors.append("mafft: tiny alignment workflow failed")

    freeze = Path(os.environ.get("PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE", ""))
    declared = os.environ.get("PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE_SHA256", "").strip().lower()
    freeze_actual = sha256(freeze) if freeze.is_file() else ""
    results["scientific_python_freeze"] = {
        "path_present": freeze.is_file(),
        "declared_sha256": declared or None,
        "actual_sha256": freeze_actual or None,
        "declared_matches_actual": bool(declared and freeze_actual == declared),
    }
    if not freeze.is_file() or not declared or freeze_actual != declared:
        errors.append("scientific_python_freeze: missing or hash mismatch")

    payload = {
        "schema_version": "1.0.0",
        "platform": sys.platform,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "results": results,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if freeze_actual:
        print(f"SCIENTIFIC_FREEZE_SHA256={freeze_actual}")
    if mafft_bundle_actual:
        print(f"MAFFT_BUNDLE_SHA256={mafft_bundle_actual}")
    mafft_archive = os.environ.get("PCRSTUDIO_MAFFT_ARCHIVE_SHA256", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", mafft_archive):
        print(f"MAFFT_ARCHIVE_SHA256={mafft_archive}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
