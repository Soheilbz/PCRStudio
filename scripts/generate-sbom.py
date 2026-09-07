#!/usr/bin/env python3
"""Generate a deterministic CycloneDX 1.6 source SBOM from frozen lockfiles."""
from __future__ import annotations

import argparse
import base64
import json
import re
import tomllib
import uuid
from pathlib import Path

from release_utils import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "release/current/SBOM.cdx.json"
NAMESPACE = uuid.UUID("e9f76a45-9ae9-53ab-ae48-47c66eb8c3d8")


def component(kind: str, name: str, version: str, *, purl: str | None = None,
              hashes: list[dict[str, str]] | None = None, properties: dict[str, str] | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "type": "library" if kind != "application" else "application",
        "bom-ref": f"{kind}:{name}@{version}",
        "name": name,
        "version": version,
        "properties": [{"name": "pcrstudio:ecosystem", "value": kind}],
    }
    if purl:
        row["purl"] = purl
    if hashes:
        row["hashes"] = hashes
    if properties:
        row["properties"] = list(row["properties"]) + [
            {"name": key, "value": value} for key, value in sorted(properties.items())
        ]
    return row


def cargo_components() -> list[dict[str, object]]:
    data = tomllib.loads((ROOT / "Cargo.lock").read_text(encoding="utf-8"))
    rows = []
    for package in data.get("package", []):
        name = str(package["name"]); version = str(package["version"])
        checksum = package.get("checksum")
        hashes = [{"alg": "SHA-256", "content": str(checksum)}] if checksum else None
        source = str(package.get("source") or "workspace")
        purl = f"pkg:cargo/{name}@{version}" if source.startswith("registry+") else None
        rows.append(component("cargo", name, version, purl=purl, hashes=hashes, properties={"source": source}))
    return rows


def python_components() -> list[dict[str, object]]:
    data = tomllib.loads((ROOT / "tools/uv.lock").read_text(encoding="utf-8"))
    rows = []
    for package in data.get("package", []):
        name = str(package["name"]); version = str(package["version"])
        source = package.get("source") or {}
        registry = source.get("registry") if isinstance(source, dict) else None
        hashes: list[dict[str, str]] = []
        sdist = package.get("sdist")
        if isinstance(sdist, dict):
            value = str(sdist.get("hash") or "")
            if value.startswith("sha256:"):
                hashes.append({"alg": "SHA-256", "content": value.split(":", 1)[1]})
        purl = f"pkg:pypi/{name}@{version}" if registry else None
        rows.append(component("pypi", name, version, purl=purl, hashes=hashes or None,
                              properties={"source": str(registry or source)}))
    return rows


def npm_components() -> list[dict[str, object]]:
    # pnpm's package keys are YAML strings but the packages section is regular
    # enough to parse dependency-free. We use the exact lockfile key and its
    # integrity line; the lockfile itself remains the authoritative parser input.
    text = (ROOT / "pnpm-lock.yaml").read_text(encoding="utf-8")
    start = text.find("\npackages:\n")
    if start < 0:
        raise SystemExit("pnpm-lock.yaml has no packages section")
    section = text[start + len("\npackages:\n"):]
    rows: list[dict[str, object]] = []
    pattern = re.compile(r"(?m)^  ('(?:[^']|'')+'|[^\s][^:]*):\n")
    matches = list(pattern.finditer(section))
    for idx, match in enumerate(matches):
        raw_key = match.group(1)
        key = raw_key[1:-1].replace("''", "'") if raw_key.startswith("'") else raw_key
        block = section[match.end(): matches[idx + 1].start() if idx + 1 < len(matches) else len(section)]
        # Peer-qualified snapshots can appear after packages; only accept actual
        # package identities with a terminal @version portion.
        if "@" not in key or key.startswith("/"):
            continue
        if key.startswith("@"):
            pos = key.find("@", 1 + key.find("/"))
        else:
            pos = key.rfind("@")
        if pos <= 0:
            continue
        name, version = key[:pos], key[pos + 1:]
        if not version or "(" in version:
            version = version.split("(", 1)[0]
        integrity_match = re.search(r"integrity:\s*(sha512-[A-Za-z0-9+/=]+)", block)
        hashes = None
        if integrity_match:
            raw = base64.b64decode(integrity_match.group(1).split("-", 1)[1])
            hashes = [{"alg": "SHA-512", "content": raw.hex()}]
        rows.append(component("npm", name, version, purl=f"pkg:npm/{name}@{version}", hashes=hashes))
    # Deduplicate aliases/peer variants by bom-ref/hash identity.
    by_ref = {str(row["bom-ref"]): row for row in rows}
    return list(by_ref.values())


def scientific_tool_components() -> list[dict[str, object]]:
    data = json.loads((ROOT / "knowledge/runtime/tool-contracts.generated.json").read_text(encoding="utf-8"))
    rows = []
    for tool_id, spec in sorted(data["tools"].items()):
        hashes = None
        expected = spec.get("provision_sha256")
        if expected:
            hashes = [{"alg": "SHA-256", "content": str(expected)}]
        rows.append(component(
            "scientific-tool", tool_id, str(spec.get("version") or "internal"), hashes=hashes,
            properties={
                "catalog_disposition": str(spec.get("catalog_disposition") or ""),
                "execution_scope": str(spec.get("execution_scope") or ""),
                "source_ref": str(spec.get("source_ref") or ""),
            },
        ))
    return rows


def build_payload() -> dict[str, object]:
    foundation = json.loads((ROOT / "knowledge/runtime/foundation.generated.json").read_text(encoding="utf-8"))
    lock_hashes = {name: sha256(ROOT / name) for name in ("Cargo.lock", "tools/uv.lock", "pnpm-lock.yaml")}
    seed = "|".join([str(foundation["foundation_release"])] + [f"{k}:{v}" for k, v in sorted(lock_hashes.items())])
    serial = f"urn:uuid:{uuid.uuid5(NAMESPACE, seed)}"
    components = cargo_components() + python_components() + npm_components() + scientific_tool_components()
    components.sort(key=lambda row: (str(row.get("properties")), str(row["name"]), str(row["version"])))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "component": component("application", "PCRStudio", str(foundation["foundation_release"])),
            "properties": [
                {"name": "pcrstudio:source-only", "value": "true"},
                {"name": "pcrstudio:native-linux-qualification", "value": "external-gate"},
            ] + [{"name": f"pcrstudio:lock-sha256:{name}", "value": value} for name, value in sorted(lock_hashes.items())],
        },
        "components": components,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    payload = build_payload()
    if args.check:
        expected = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != expected:
            raise SystemExit(f"SBOM drift: run {Path(__file__).name}")
        print(f"SBOM check PASS: {len(payload['components'])} components")
        return 0
    write_json(args.output, payload)
    print(f"generated {args.output.relative_to(ROOT)} with {len(payload['components'])} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
