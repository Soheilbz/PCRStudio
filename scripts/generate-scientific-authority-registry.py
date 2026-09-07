#!/usr/bin/env python3
"""Project canonical scientific authorities into runtime-safe content-addressed records."""
from __future__ import annotations
import argparse, hashlib, json, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts/scientific-authorities.json"
CHEM = ROOT / "contracts/chemistry"
OUTPUTS = [
    ROOT / "tools/src/pcr_tools/data/scientific-authority-registry.generated.json",
    ROOT / "web/src/lib/scientific-authority-registry.generated.json",
    ROOT / "knowledge/runtime/scientific-authority-registry.generated.json",
]

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    revision: object = None
    authority: object = None
    effective: object = None
    if path.suffix == ".json":
        doc = json.loads(raw)
        if isinstance(doc, dict):
            revision = doc.get("schema_version") or doc.get("version") or doc.get("revision")
            authority = doc.get("authority") or doc.get("id") or doc.get("name")
            effective = doc.get("effective_date") or doc.get("reviewed_date") or doc.get("audit_as_of")
    elif path.suffix == ".toml":
        doc = tomllib.loads(raw.decode("utf-8"))
        revision = doc.get("schema_version")
        authority = doc.get("authority")
        effective = doc.get("effective_date")
    return {
        "authority_id": str(authority or path.stem),
        "authority_revision": str(revision or "content-addressed"),
        "effective_date": str(effective) if effective is not None else None,
        "canonical_source": path.relative_to(ROOT).as_posix(),
        "canonical_sha256": hashlib.sha256(raw).hexdigest(),
    }

def render() -> str:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    declared = list(manifest["chemistry_files"])
    actual = sorted(p.name for p in CHEM.iterdir() if p.is_file() and p.suffix in {".json", ".toml"})
    if sorted(declared) != actual:
        raise SystemExit(f"scientific authority manifest chemistry coverage drift: declared={len(declared)} actual={len(actual)} missing={sorted(set(actual)-set(declared))} extra={sorted(set(declared)-set(actual))}")
    records = {name: identity(CHEM / name) for name in declared}
    supplemental: dict[str, list[dict[str, object]]] = {}
    for chemistry_name, paths in manifest.get("supplemental_authorities", {}).items():
        rows=[]
        for rel in paths:
            p=ROOT/rel
            if not p.is_file():
                raise SystemExit(f"missing supplemental scientific authority: {rel}")
            rows.append({"authority_id": p.stem, "authority_revision": "content-addressed", "effective_date": None, "canonical_source": rel, "canonical_sha256": sha(p)})
        supplemental[chemistry_name]=rows
    modules={}
    for module_id, names in manifest["modules"].items():
        rows=[]
        for name in names:
            if name not in records:
                raise SystemExit(f"{module_id}: unknown scientific authority {name}")
            rows.append(records[name])
            rows.extend(supplemental.get(name, []))
        modules[module_id]=rows
    payload={
        "schema_version":"1.0.0",
        "authority":"pcrstudio-scientific-authority-registry",
        "effective_date":manifest["effective_date"],
        "manifest_sha256":sha(MANIFEST),
        "chemistry_file_count":len(records),
        "chemistry_files":records,
        "modules":modules,
        "policy":manifest["policy"],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)+"\n"

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); args=ap.parse_args()
    text=render(); drift=[]
    for path in OUTPUTS:
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text: drift.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8", newline="\n")
    if drift:
        print("SCIENTIFIC_AUTHORITY_REGISTRY=CHECK-DRIFT " + ", ".join(drift)); return 1
    print("SCIENTIFIC_AUTHORITY_REGISTRY=" + ("CHECK-PASS" if args.check else "GENERATED"))
    return 0
if __name__ == "__main__": raise SystemExit(main())
