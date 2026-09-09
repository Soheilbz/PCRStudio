#!/usr/bin/env python3
"""Provision PCRStudio's canonical scientific toolchain on Linux x86_64.

The provisioner is intentionally host-local and idempotent.  Downloaded
artifacts are either SHA-256 pinned in ``contracts/tools.toml`` or, for MAFFT's
official portable bundle (whose download page does not publish a digest),
bound to the current Linux qualification by the generated executable/freeze
fingerprints.  Runtime strict mode verifies those fingerprints on every use.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import shutil
import shlex
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from toolchain_config import render_toolchain_config, sha256_file as config_sha256_file  # noqa: E402

LOCAL = Path(os.environ.get("PCRSTUDIO_PROVISION_PREFIX", ROOT / ".local" / "tools")).expanduser().resolve()
DOWNLOADS = LOCAL / "downloads"
SCIENCE_VENV = LOCAL / "science-venv"

ARTIFACTS = {
    "mfeprimer": {
        "version": "4.5.1",
        "url": "https://github.com/quwubin/MFEprimer-3.0/releases/download/v4.5.1/mfeprimer-4.5.1-linux-amd64.gz",
        "archive": "mfeprimer-4.5.1-linux-amd64.gz",
        "sha256": "56abb0789497a6273e0b7d226671d5f1d959d3bceaba5be53f0d2b2edc13c839",
    },
    "blast": {
        "version": "2.17.0",
        "url": "https://ftp.ncbi.nlm.nih.gov/blast/executables/blast%2B/2.17.0/ncbi-blast-2.17.0%2B-x64-linux.tar.gz",
        "archive": "ncbi-blast-2.17.0-x64-linux.tar.gz",
        "sha256": "3888112d8207831aa47371d93583c601f058f88b5db22dc782438b039a3a411b",
    },
    "mafft": {
        "version": "7.526",
        "url": "https://mafft.ddbj.nig.ac.jp/alignment/software/mafft-7.526-linux.tgz",
        "archive": "mafft-7.526-linux.tgz",
        "sha256": "",  # upstream portable-package page publishes no digest
    },
    "primerpooler": {
        "version": "1.89",
        "url": "https://codeload.github.com/ssb22/PrimerPooler/tar.gz/refs/tags/v1.89",
        "archive": "PrimerPooler-v1.89.tar.gz",
        "sha256": "df07e19c8c11a4aa7e7550fca59209615c3a8483b4cba36d320bb06e30eef414",
    },
}
SCIENCE_WHEELS = {
    "primalscheme3": ("3.3.0", "primalscheme3-3.3.0-py3-none-any.whl", "4ac2455c6071ddef40fd5bed881ad9c129f8590b66e7bf6b73462a0ea9aad30e"),
    "pydna": ("5.5.16", "pydna-5.5.16-py3-none-any.whl", "f89c0787da7f405286c5d4fa8a827bbefbb09c7da382860834d7103dddb452aa"),
}


def verify_contract_alignment() -> None:
    """Refuse provisioning when executable metadata drifts from tools.toml.

    Keeping the installer table and the canonical scientific contract separate
    is useful for a small bootstrap script, but it creates a supply-chain footgun
    if one is edited without the other.  Validate both representations before any
    network request so a stale URL/hash cannot silently survive a contract update.
    """
    contract_path = ROOT / "contracts" / "tools.toml"
    if not contract_path.is_file():
        die(f"Canonical tool contract is missing: {contract_path}")
    data = tomllib.loads(contract_path.read_text(encoding="utf-8"))
    tools = {str(item.get("id")): item for item in data.get("tool", [])}
    provision_by_id = {str(item.get("provision_id")): item for item in data.get("tool", []) if item.get("provision_id")}
    for provision_id, expected in ARTIFACTS.items():
        item = provision_by_id.get(provision_id)
        if not item:
            die(f"contracts/tools.toml has no provision_id={provision_id!r}")
        fields = {
            "version": str(item.get("version") or ""),
            "url": str(item.get("provision_url") or ""),
            "archive": str(item.get("provision_archive") or ""),
            "sha256": str(item.get("provision_sha256") or ""),
        }
        if fields != expected:
            die(f"Provision metadata drift for {provision_id}: contract={fields!r} installer={expected!r}")
    for tool_id, (version, filename, digest) in SCIENCE_WHEELS.items():
        item = tools.get(tool_id)
        if not item:
            die(f"contracts/tools.toml has no tool id={tool_id!r}")
        fields = (str(item.get("version") or ""), str(item.get("package_filename") or ""), str(item.get("package_sha256") or ""))
        if fields != (version, filename, digest):
            die(f"Scientific wheel metadata drift for {tool_id}: contract={fields!r} installer={(version, filename, digest)!r}")


def die(message: str) -> "NoReturn":
    raise SystemExit(message)


def run(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    completed = subprocess.run(
        [str(x) for x in args], cwd=cwd or ROOT, check=True,
        text=True, stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    return (completed.stdout or "").strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def executable(path: Path) -> Path:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def tree_sha256(root: Path) -> str:
    """Deterministically bind every entry in an extracted runtime bundle.

    The digest covers relative path, entry kind, executable/permission bits and
    either file content or symlink target. Symlinks are permitted only when
    their resolved target remains inside the bundle, preventing a digest from
    blessing an escape into host state.
    """
    root = root.resolve()
    if not root.is_dir():
        die(f"Bundle root is not a directory: {root}")
    h = hashlib.sha256()
    entries = sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
    for path in entries:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        st = path.lstat()
        mode = stat.S_IMODE(st.st_mode)
        if path.is_symlink():
            target = os.readlink(path)
            resolved = path.resolve()
            if resolved != root and root not in resolved.parents:
                die(f"Bundle symlink escapes root: {path} -> {target}")
            payload = b"L\0" + rel + b"\0" + f"{mode:o}".encode() + b"\0" + target.encode("utf-8")
        elif path.is_dir():
            payload = b"D\0" + rel + b"\0" + f"{mode:o}".encode()
        elif path.is_file():
            payload = b"F\0" + rel + b"\0" + f"{mode:o}".encode() + b"\0" + sha256(path).encode()
        else:
            die(f"Unsupported special file in runtime bundle: {path}")
        h.update(payload + b"\n")
    return h.hexdigest()


def download(url: str, target: Path, expected: str = "") -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and (not expected or sha256(target) == expected):
        return target
    target.unlink(missing_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "PCRStudio-CURRENT-Linux-Provisioner/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, tmp.open("wb") as out:
        shutil.copyfileobj(response, out)
    actual = sha256(tmp)
    if expected and actual != expected:
        tmp.unlink(missing_ok=True)
        die(f"SHA-256 mismatch for {target.name}: expected {expected}, got {actual}")
    tmp.replace(target)
    print(f"Downloaded {target.name} sha256={actual}")
    return target


def get_verified_pypi_wheel(package: str, version: str, filename: str, expected: str) -> Path:
    """Get-VerifiedPyPiWheel: resolve the exact published wheel and verify it."""
    metadata_url = f"https://pypi.org/pypi/{package}/{version}/json"
    with urllib.request.urlopen(metadata_url, timeout=60) as response:
        metadata = json.load(response)
    published = None
    for item in metadata.get("urls", []):
        if item.get("filename") == filename:
            published = item
            break
    if not published:
        die(f"PyPI did not publish required wheel {filename}")
    published_hash = str((published.get("digests") or {}).get("sha256") or "").lower()
    if published_hash != expected.lower():
        die(f"Published scientific wheel hash drifted for {filename}: {published_hash}")
    path = download(str(published["url"]), DOWNLOADS / filename, expected)
    print(f"Downloaded scientific wheel {filename}")
    return path


def require_linux() -> None:
    if not sys.platform.startswith("linux"):
        die("PCRStudio CURRENT provisioning is Linux-only.")
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        die(f"CURRENT pinned native artifacts require Linux x86_64; detected {machine!r}.")


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        die(f"Required command not found on PATH: {name}")
    return path


def provision_python() -> tuple[Path, Path, Path]:
    uv = Path(require_command("uv"))
    worker_override = os.environ.get("PCRSTUDIO_PROVISION_WORKER_PYTHON", "").strip()
    if worker_override:
        worker_python = Path(worker_override).expanduser().resolve()
        if not worker_python.is_file():
            die(f"PCRSTUDIO_PROVISION_WORKER_PYTHON is not a file: {worker_python}")
    else:
        # Keep worker dependencies exactly reproducible under the checked-in uv.lock.
        # Keep the development extra present while provisioning so a failed
        # network download cannot leave the worker unable to run qualification.
        # The extra is small and the local bootstrap restores it explicitly
        # after provisioning as well.
        run(
            str(uv), "sync", "--project", str(ROOT / "tools"), "--frozen",
            "--extra", "dev", "--extra", "folding",
        )
        worker_python = ROOT / "tools" / ".venv" / "bin" / "python"
        if not worker_python.is_file():
            die("uv sync completed without tools/.venv/bin/python")

    if not (SCIENCE_VENV / "bin" / "python").is_file():
        run(str(uv), "venv", "--python", str(worker_python), str(SCIENCE_VENV))
    science_python = SCIENCE_VENV / "bin" / "python"
    wheels = [get_verified_pypi_wheel(name, *spec) for name, spec in SCIENCE_WHEELS.items()]
    run(str(uv), "pip", "install", "--python", str(science_python), *map(str, wheels))
    freeze_lines = sorted(
        line.strip() for line in run(str(uv), "pip", "freeze", "--python", str(science_python), capture=True).splitlines()
        if line.strip()
    )
    freeze_path = LOCAL / "python-scientific-freeze.txt"
    freeze_path.write_text("\n".join(freeze_lines) + "\n", encoding="utf-8")
    return worker_python, science_python, freeze_path


def safe_extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    base = destination.resolve()
    with tarfile.open(archive, "r:*") as tf:
        for member in tf.getmembers():
            target = (destination / member.name).resolve()
            if target != base and base not in target.parents:
                die(f"Unsafe archive member rejected: {member.name}")
        tf.extractall(destination, filter="data")


def provision_native() -> dict[str, Path]:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    # MFEprimer
    item = ARTIFACTS["mfeprimer"]
    gz = download(item["url"], DOWNLOADS / item["archive"], item["sha256"])
    mfe_dir = LOCAL / "mfeprimer"; mfe_dir.mkdir(parents=True, exist_ok=True)
    mfe = mfe_dir / "mfeprimer"
    with gzip.open(gz, "rb") as src, mfe.open("wb") as dst: shutil.copyfileobj(src, dst)
    executable(mfe)

    # BLAST+
    item = ARTIFACTS["blast"]
    archive = download(item["url"], DOWNLOADS / item["archive"], item["sha256"])
    blast_root = LOCAL / "blast"
    if blast_root.exists(): shutil.rmtree(blast_root)
    safe_extract_tar(archive, blast_root)
    candidates = list(blast_root.rglob("blastn"))
    if len(candidates) != 1: die(f"Expected one blastn executable, found {len(candidates)}")
    blastn = executable(candidates[0])
    makeblastdb = blastn.parent / "makeblastdb"
    if not makeblastdb.is_file(): die("makeblastdb is unavailable beside blastn")
    executable(makeblastdb)

    # MAFFT official Linux portable package. Upstream provides no published
    # package digest. Record the actually downloaded archive digest and bind the
    # entire extracted portable bundle deterministically at runtime.
    item = ARTIFACTS["mafft"]
    archive = download(item["url"], DOWNLOADS / item["archive"], item["sha256"])
    mafft_root = LOCAL / "mafft"
    if mafft_root.exists(): shutil.rmtree(mafft_root)
    safe_extract_tar(archive, mafft_root)
    upstream = next(iter(mafft_root.rglob("mafft.bat")), None)
    if upstream is None: die("MAFFT portable archive does not contain mafft.bat")
    executable(upstream)
    mafft_bundle = upstream.parent
    mafft_archive_sha256 = sha256(archive)
    mafft_bundle_sha256 = tree_sha256(mafft_bundle)
    mafft = mafft_root / "mafft"
    mafft.write_text('#!/bin/sh\nset -eu\nHERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$HERE/mafft-linux64/mafft.bat" "$@"\n', encoding="utf-8")
    executable(mafft)

    # PrimerPooler: build audited v1.89 source on the target Linux host.
    item = ARTIFACTS["primerpooler"]
    archive = download(item["url"], DOWNLOADS / item["archive"], item["sha256"])
    require_command("make"); require_command("cc")
    build_root = LOCAL / "primerpooler-build"
    if build_root.exists(): shutil.rmtree(build_root)
    safe_extract_tar(archive, build_root)
    makefiles = list(build_root.rglob("Makefile"))
    pool_make = next((p for p in makefiles if p.parent.name == "pooler"), makefiles[0] if makefiles else None)
    if pool_make is None: die("PrimerPooler source archive has no Makefile")
    run("make", cwd=pool_make.parent)
    built = next((p for p in (pool_make.parent / name for name in ("pooler", "pooler64")) if p.is_file()), None)
    if built is None: die("PrimerPooler build did not produce pooler/pooler64")
    pool_dir = LOCAL / "primerpooler"; pool_dir.mkdir(parents=True, exist_ok=True)
    pooler = pool_dir / "pooler"
    shutil.copy2(built, pooler); executable(pooler)

    return {
        "mfeprimer": mfe,
        "blastn": blastn,
        "mafft": mafft,
        "mafft_bundle": mafft_bundle,
        "mafft_archive": archive,
        "primerpooler": pooler,
    }


def shell_env_assignment(name: str, value: str) -> str:
    """Serialize one trusted environment value for the POSIX entrypoint.

    ``toolchain.env`` is sourced by ``/bin/sh`` at container startup, so raw
    paths must never become shell syntax. Keep the file one-assignment-per-line
    and quote every value with the standard shell quoting algorithm.
    """
    if not name or not all(ch.isalnum() or ch == "_" for ch in name) or name[0].isdigit():
        die(f"Unsafe toolchain environment key: {name!r}")
    if any(ch in value for ch in ("\0", "\r", "\n")):
        die(f"Toolchain environment value for {name} contains a line/control delimiter")
    return f"{name}={shlex.quote(value)}"


def read_optional_tool_config(path: Path) -> dict[str, str]:
    """Read and verify the managed Olivar binding as structured data."""
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        die(f"Olivar configuration is unreadable/invalid JSON: {error}")
    required = {"schema_version", "tool_id", "version", "executable", "sha256"}
    if not isinstance(payload, dict) or set(payload) != required:
        die(f"Olivar configuration has an invalid field set: {sorted(payload) if isinstance(payload, dict) else type(payload).__name__}")
    if payload["schema_version"] != "1.0.0" or payload["tool_id"] != "olivar" or payload["version"] != "1.3.3":
        die("Olivar configuration identity/version contract is invalid")
    executable = Path(str(payload["executable"]))
    digest = str(payload["sha256"])
    if not executable.is_absolute() or not executable.is_file():
        die(f"Managed Olivar executable is missing/not absolute: {executable}")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        die("Managed Olivar SHA-256 is not canonical lowercase hex")
    actual = sha256(executable)
    if actual != digest:
        die(f"Managed Olivar executable changed after binding: expected {digest}, observed {actual}")
    return {
        "PCRSTUDIO_OLIVAR": str(executable),
        "PCRSTUDIO_OLIVAR_SHA256": digest,
    }


def write_env(native: dict[str, Path], science_python: Path, freeze: Path) -> None:
    primalscheme = SCIENCE_VENV / "bin" / "primalscheme3"
    if not primalscheme.is_file():
        die("PrimalScheme3 console script is missing after installation")
    approved_path = LOCAL / "approved-scientific-python-freeze.sha256"
    approved = approved_path.read_text(encoding="utf-8").strip() if approved_path.is_file() else ""
    values = {
        "PCRSTUDIO_TOOL_PREFIX": str(LOCAL),
        "PCRSTUDIO_SCIENTIFIC_POLICY": "strict",
        "PCRSTUDIO_TOOLCHAIN_MODE": "strict",
        "PCRSTUDIO_EXTERNAL_VALIDATION": "strict",
        "PCRSTUDIO_MFEPRIMER": str(native["mfeprimer"]),
        "PCRSTUDIO_MFEPRIMER_SHA256": sha256(native["mfeprimer"]),
        "PCRSTUDIO_BLASTN": str(native["blastn"]),
        "PCRSTUDIO_BLASTN_SHA256": sha256(native["blastn"]),
        "PCRSTUDIO_MAFFT": str(native["mafft"]),
        "PCRSTUDIO_MAFFT_SHA256": sha256(native["mafft"]),
        "PCRSTUDIO_MAFFT_ARCHIVE_SHA256": sha256(native["mafft_archive"]),
        "PCRSTUDIO_MAFFT_BUNDLE_ROOT": str(native["mafft_bundle"]),
        "PCRSTUDIO_MAFFT_BUNDLE_SHA256": tree_sha256(native["mafft_bundle"]),
        "PCRSTUDIO_PRIMERPOOLER": str(native["primerpooler"]),
        "PCRSTUDIO_PRIMERPOOLER_SHA256": sha256(native["primerpooler"]),
        "PCRSTUDIO_PRIMALSCHEME3": str(primalscheme),
        "PCRSTUDIO_PRIMALSCHEME3_SHA256": sha256(primalscheme),
        "PCRSTUDIO_PYDNA_PYTHON": str(science_python),
        "PCRSTUDIO_PYDNA_PYTHON_SHA256": sha256(science_python),
        "PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE": str(freeze),
        "PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE_SHA256": sha256(freeze),
    }
    if approved:
        values["PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256"] = approved
    values.update(read_optional_tool_config(LOCAL / "olivar.json"))
    config_path = LOCAL / "toolchain.json"
    config_tmp = config_path.with_suffix(".json.tmp")
    config_tmp.write_text(render_toolchain_config(values), encoding="utf-8")
    config_tmp.replace(config_path)
    config_digest = config_sha256_file(config_path)

    env_values = dict(values)
    env_values["PCRSTUDIO_TOOLCHAIN_CONFIG_SHA256"] = config_digest
    rows = [shell_env_assignment(key, value) for key, value in env_values.items()]
    env_path = LOCAL / "toolchain.env"
    env_tmp = env_path.with_suffix(".env.tmp")
    env_tmp.write_text("\n".join(rows) + "\n", encoding="utf-8")
    env_tmp.replace(env_path)


def approve_freeze(freeze: Path) -> None:
    digest = sha256(freeze)
    (LOCAL / "approved-scientific-python-freeze.sha256").write_text(digest + "\n", encoding="utf-8")
    print(f"Approved Linux scientific Python freeze: {digest}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve-scientific-freeze", action="store_true", help="bind the current freeze only after qualification has passed; do not use during an ordinary image build")
    args = parser.parse_args()
    require_linux(); verify_contract_alignment(); LOCAL.mkdir(parents=True, exist_ok=True)
    worker_python, science_python, freeze = provision_python()
    native = provision_native()
    if args.approve_scientific_freeze: approve_freeze(freeze)
    write_env(native, science_python, freeze)
    print(f"PCRStudio Linux toolchain provisioned. Worker Python: {worker_python}")
    print("Production specificity remains fail-closed until configure-specificity-database.py writes an approved database contract.")

if __name__ == "__main__":
    main()
