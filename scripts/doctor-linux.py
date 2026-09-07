#!/usr/bin/env python3
"""Read-only PCRStudio Linux production host diagnostic.

This command never installs packages, writes secrets, builds images, starts
containers or changes firewall/systemd state. It reports whether the current
host is suitable for the production bootstrap and identifies remediations
before deployment begins.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import socket
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024 ** 3


def load_bootstrap():
    path = ROOT / "scripts" / "bootstrap-linux.py"
    spec = importlib.util.spec_from_file_location("pcrstudio_bootstrap_doctor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(name: str, status: str, detail: str, *, remediation: str | None = None) -> dict[str, str]:
    item = {"name": name, "status": status, "detail": detail}
    if remediation:
        item["remediation"] = remediation
    return item


def mode_string(path: Path) -> str:
    return oct(stat.S_IMODE(path.stat().st_mode))


def listeners() -> set[int]:
    ss = shutil.which("ss")
    if not ss:
        return set()
    cp = subprocess.run([ss, "-ltnH"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    ports: set[int] = set()
    if cp.returncode:
        return ports
    for line in cp.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        local = fields[3]
        try:
            ports.add(int(local.rsplit(":", 1)[1]))
        except (ValueError, IndexError):
            continue
    return ports


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only PCRStudio Linux host doctor")
    ap.add_argument("--reference-fasta", type=Path, help="reference FASTA planned for specificity indexing")
    ap.add_argument("--domain", help="public hostname planned for Caddy/TLS")
    ap.add_argument("--private", action="store_true", help="private/loopback deployment; ports 80/443 and public DNS are not required")
    ap.add_argument("--allow-docker-install", action="store_true", help="report a missing Docker engine as remediable rather than a blocking error")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = ap.parse_args()

    b = load_bootstrap()
    results: list[dict[str, str]] = []

    machine = platform.machine().lower()
    linux_ok = sys.platform.startswith("linux") and machine in {"x86_64", "amd64"}
    results.append(check(
        "platform",
        "PASS" if linux_ok else "FAIL",
        f"{platform.system()} {platform.release()} {machine}",
        remediation="Use a Linux x86_64 VM; pinned native scientific artifacts are qualified for that target." if not linux_ok else None,
    ))

    py_ok = sys.version_info >= (3, 11)
    results.append(check(
        "host_python",
        "PASS" if py_ok else "FAIL",
        platform.python_version(),
        remediation="Install Python 3.11+ for bootstrap/qualification scripts." if not py_ok else None,
    ))

    total = b.host_memory_bytes()
    try:
        profile, _ = b.resource_profile_for_memory(total)
        results.append(check("memory", "PASS", f"{total / GIB:.2f} GiB total; automatic profile={profile}"))
    except SystemExit as exc:
        results.append(check("memory", "FAIL", str(exc), remediation="Use a VM with at least 4 GiB RAM; 8+ GiB is recommended."))

    cpus = max(1, os.cpu_count() or 1)
    results.append(check(
        "cpu",
        "PASS" if cpus >= 2 else "WARN",
        f"{cpus} logical CPU(s)",
        remediation="Two or more vCPUs are recommended for concurrent scientific work." if cpus < 2 else None,
    ))

    root_free = shutil.disk_usage(ROOT).free
    reference_bytes = 0
    if args.reference_fasta:
        fasta = args.reference_fasta.expanduser().resolve()
        if not fasta.is_file() or fasta.stat().st_size <= 0:
            results.append(check("reference_fasta", "FAIL", f"missing/empty: {fasta}", remediation="Provide a readable non-empty approved FASTA."))
        else:
            reference_bytes = fasta.stat().st_size
            results.append(check("reference_fasta", "PASS", f"{fasta} ({reference_bytes} bytes)"))
    baseline_disk = 16 * GIB + reference_bytes * 6
    results.append(check(
        "repository_disk",
        "PASS" if root_free >= baseline_disk else "FAIL",
        f"{root_free / GIB:.1f} GiB free; conservative pre-bootstrap target {baseline_disk / GIB:.1f} GiB",
        remediation="Increase the filesystem or move Docker/scientific data to storage with more free space." if root_free < baseline_disk else None,
    ))

    prefix = b.existing_docker_prefix()
    if prefix is None:
        status = "WARN" if args.allow_docker_install else "FAIL"
        results.append(check(
            "docker",
            status,
            "Docker Engine with Compose >=2.24.4 is not currently usable",
            remediation="Run ./bootstrap.sh (automatic supported-host setup) or install Docker Engine + Compose v2 from Docker's official repository.",
        ))
    else:
        ver = subprocess.run([*prefix, "compose", "version", "--short"], stdout=subprocess.PIPE, text=True, check=False).stdout.strip()
        root = b.nearest_existing_parent(b.docker_root_dir(prefix))
        free = shutil.disk_usage(root).free
        results.append(check("docker", "PASS", f"usable via {' '.join(prefix)}; Compose {ver}"))
        results.append(check(
            "docker_disk",
            "PASS" if free >= 10 * GIB else "FAIL",
            f"Docker root {root}; {free / GIB:.1f} GiB free",
            remediation="Keep at least 10 GiB free in Docker storage for a clean production image build." if free < 10 * GIB else None,
        ))

    manifest_check = subprocess.run(
        [sys.executable, "scripts/generate-release-manifests.py", "--baseline-manifest", "release/baseline/R15-FILE-MANIFEST.json", "--check"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    results.append(check(
        "source_manifest",
        "PASS" if manifest_check.returncode == 0 else "FAIL",
        "release/FILE-MANIFEST.json matches source bytes" if manifest_check.returncode == 0 else manifest_check.stdout.strip()[-1200:],
        remediation="Regenerate and requalify release metadata before deployment." if manifest_check.returncode else None,
    ))

    env_path = ROOT / ".env"
    if env_path.exists():
        env_mode = stat.S_IMODE(env_path.stat().st_mode)
        results.append(check(
            "env_permissions",
            "PASS" if env_mode & 0o077 == 0 else "FAIL",
            f"{env_path} mode {oct(env_mode)}",
            remediation="chmod 600 .env" if env_mode & 0o077 else None,
        ))
    else:
        results.append(check("env_permissions", "PASS", ".env not created yet; bootstrap will create it mode 0600"))

    secret_dir = ROOT / ".local" / "secrets"
    if secret_dir.exists():
        bad = []
        for p in secret_dir.iterdir():
            if p.is_file() and stat.S_IMODE(p.stat().st_mode) & 0o077:
                bad.append(f"{p.name}:{mode_string(p)}")
        results.append(check(
            "secret_permissions",
            "PASS" if not bad else "FAIL",
            "all existing secret files are owner-only" if not bad else ", ".join(bad),
            remediation="Restrict secret files to mode 0600." if bad else None,
        ))
    else:
        results.append(check("secret_permissions", "PASS", "secret directory not created yet"))

    systemd = Path("/run/systemd/system").exists() and shutil.which("systemctl") is not None
    results.append(check(
        "systemd",
        "PASS" if systemd else "WARN",
        "active" if systemd else "not active; Docker restart policies still work but scheduled backup timers will not be installed",
        remediation="Use a systemd-based VM or schedule backup/prune/restore-drill with the host's scheduler." if not systemd else None,
    ))

    if not args.private:
        active_ports = listeners()
        if active_ports:
            collisions = sorted({80, 443} & active_ports)
            results.append(check(
                "edge_ports",
                "WARN" if collisions else "PASS",
                f"listening collision(s): {collisions}" if collisions else "TCP 80/443 appear unused",
                remediation="Stop/reconfigure the existing edge proxy or intentionally integrate PCRStudio behind it." if collisions else None,
            ))
        else:
            results.append(check("edge_ports", "WARN", "could not reliably enumerate TCP listeners (ss unavailable or returned no data)"))

        if args.domain:
            try:
                infos = socket.getaddrinfo(args.domain, 443, type=socket.SOCK_STREAM)
                ips = sorted({entry[4][0] for entry in infos})
                results.append(check("public_dns", "PASS", f"{args.domain} resolves to {', '.join(ips)}"))
            except OSError as exc:
                results.append(check(
                    "public_dns", "WARN", f"{args.domain} did not resolve from this host: {exc}",
                    remediation="Create/verify the DNS A/AAAA records before expecting Caddy to obtain a public certificate.",
                ))

    status = "FAIL" if any(x["status"] == "FAIL" for x in results) else ("WARN" if any(x["status"] == "WARN" for x in results) else "PASS")
    payload = {
        "schema_version": "1.0.0",
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"PCRStudio Linux doctor: {status}")
        for item in results:
            print(f"[{item['status']:<4}] {item['name']}: {item['detail']}")
            if item.get("remediation"):
                print(f"       remediation: {item['remediation']}")
        print("No host state was modified.")
    return 2 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
