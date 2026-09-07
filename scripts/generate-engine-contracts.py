#!/usr/bin/env python3
"""Generate the unified engine capability, transport and differential projections.

The canonical engine registry is ``contracts/engines.toml``.  Every engine must
have exactly one profile in ``contracts/engines/profiles``.  Profiles contain
engine-specific authority/differential references and optional feature claims;
tool capabilities are derived uniformly from the engine's declared bindings.
"""
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "contracts/engines/profiles"
STATUS = ROOT / "contracts/engines/status-vocabulary.json"

ROLE_STATUS = {
    "PRIMARY": "executable",
    "CONDITIONAL_PRIMARY": "executable-if-installed",
    "VALIDATOR": "executable-if-installed",
    "OPTIONAL": "executable-if-installed",
    "REFERENCE": "reference-only",
}
ALLOWED_TRANSPORT_MODES = {"explicit-field-parity", "canonical-http-contract"}
ALLOWED_OWNERS = {
    "target", "design", "strategy", "constraints", "vector", "reaction",
    "specificity", "validation", "construct", "review",
}


def jtext(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry() -> list[dict[str, Any]]:
    payload = tomllib.loads((ROOT / "contracts/engines.toml").read_text(encoding="utf-8"))
    rows = payload.get("engine")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("contracts/engines.toml: engine registry missing")
    ids = [row.get("id") for row in rows]
    if any(not isinstance(engine_id, str) or not engine_id for engine_id in ids):
        raise SystemExit("contracts/engines.toml: invalid engine id")
    if len(ids) != len(set(ids)):
        raise SystemExit("contracts/engines.toml: duplicate engine id")
    return rows


def validate_profile(profile: dict[str, Any], engine: dict[str, Any], statuses: set[str]) -> None:
    engine_id = engine["id"]
    if profile.get("schema_version") != "1.0.0":
        raise SystemExit(f"{engine_id}: unexpected profile schema")
    if profile.get("engine_id") != engine_id:
        raise SystemExit(f"{engine_id}: profile engine_id mismatch")
    domains = profile.get("authority_domains")
    if not isinstance(domains, list) or not domains:
        raise SystemExit(f"{engine_id}: authority_domains must be non-empty")
    domain_ids: list[str] = []
    for domain in domains:
        if not isinstance(domain, dict):
            raise SystemExit(f"{engine_id}: malformed authority domain")
        domain_id = domain.get("id")
        source = domain.get("source")
        if not isinstance(domain_id, str) or not domain_id or not isinstance(source, str) or not source:
            raise SystemExit(f"{engine_id}: authority domain requires id/source")
        if domain_id in domain_ids:
            raise SystemExit(f"{engine_id}: duplicate authority domain {domain_id}")
        domain_ids.append(domain_id)
        if not (ROOT / source).is_file():
            raise SystemExit(f"{engine_id}: authority source missing: {source}")
    corpora = profile.get("differential_corpora")
    if not isinstance(corpora, list) or not corpora:
        raise SystemExit(f"{engine_id}: differential_corpora must be non-empty")
    for rel in corpora:
        if not isinstance(rel, str) or not (ROOT / rel).is_file():
            raise SystemExit(f"{engine_id}: differential corpus missing: {rel!r}")
        corpus = load_json(ROOT / rel)
        if not isinstance(corpus.get("cases"), list) or not corpus["cases"]:
            raise SystemExit(f"{engine_id}: differential corpus has no cases: {rel}")
        if "metamorphic" in corpus and (not isinstance(corpus.get("metamorphic"), list) or not corpus["metamorphic"]):
            raise SystemExit(f"{engine_id}: malformed/empty metamorphic contract: {rel}")
        declared = corpus.get("engine")
        if declared is not None and declared != engine_id:
            raise SystemExit(f"{engine_id}: corpus engine mismatch in {rel}: {declared}")
        ids = [case.get("id") for case in corpus["cases"] if isinstance(case, dict)]
        if len(ids) != len(corpus["cases"]) or any(not isinstance(case_id, str) or not case_id for case_id in ids):
            raise SystemExit(f"{engine_id}: invalid differential case id in {rel}")
        if len(ids) != len(set(ids)):
            raise SystemExit(f"{engine_id}: duplicate differential case id in {rel}")
    features = profile.get("feature_capabilities")
    if not isinstance(features, dict):
        raise SystemExit(f"{engine_id}: feature_capabilities must be an object")
    for capability, spec in features.items():
        if not isinstance(capability, str) or not capability or not isinstance(spec, dict):
            raise SystemExit(f"{engine_id}: malformed feature capability")
        status = spec.get("status")
        if status not in statuses:
            raise SystemExit(f"{engine_id}/{capability}: unknown status {status!r}")
    transport = profile.get("transport")
    if not isinstance(transport, dict) or transport.get("mode") not in ALLOWED_TRANSPORT_MODES:
        raise SystemExit(f"{engine_id}: invalid transport mode")
    fields = transport.get("fields")
    if not isinstance(fields, list):
        raise SystemExit(f"{engine_id}: transport fields must be a list")
    names: list[str] = []
    for field in fields:
        if not isinstance(field, dict) or not all(isinstance(field.get(key), str) and field[key] for key in ("web", "rust", "python", "owner")):
            raise SystemExit(f"{engine_id}: malformed transport parity field")
        if field["owner"] not in ALLOWED_OWNERS:
            raise SystemExit(f"{engine_id}/{field['web']}: unknown transport owner {field['owner']!r}")
        names.append(field["web"])
    if len(names) != len(set(names)):
        raise SystemExit(f"{engine_id}: duplicate web transport field")
    if transport["mode"] == "canonical-http-contract":
        authority = transport.get("authority")
        if not isinstance(authority, str) or not (ROOT / authority).is_file():
            raise SystemExit(f"{engine_id}: canonical HTTP authority missing")


def tool_capabilities(engine: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for binding in engine.get("binding", []):
        tool_id = binding.get("tool_id")
        role = binding.get("role")
        if not isinstance(tool_id, str) or role not in ROLE_STATUS:
            raise SystemExit(f"{engine['id']}: invalid tool binding")
        for operation in binding.get("operations", []):
            if not isinstance(operation, str) or not operation:
                raise SystemExit(f"{engine['id']}: invalid operation for {tool_id}")
            capability_id = f"{tool_id}:{operation}"
            if capability_id in result:
                raise SystemExit(f"{engine['id']}: duplicate tool capability {capability_id}")
            result[capability_id] = {
                "status": ROLE_STATUS[role],
                "tool_id": tool_id,
                "role": role,
                "purposes": list(binding.get("purposes", [])),
                "artifact_identity": binding.get("artifact_identity"),
            }
    return result


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    engines = load_registry()
    status_payload = load_json(STATUS)
    if status_payload.get("schema_version") != "1.0.0":
        raise SystemExit("status vocabulary: unexpected schema")
    vocabulary = status_payload.get("status_vocabulary")
    if not isinstance(vocabulary, dict) or not vocabulary:
        raise SystemExit("status vocabulary missing")
    statuses = set(vocabulary)
    profile_paths = {path.stem: path for path in PROFILES.glob("*.json")}
    engine_ids = [engine["id"] for engine in engines]
    if set(profile_paths) != set(engine_ids):
        missing = sorted(set(engine_ids) - set(profile_paths))
        extra = sorted(set(profile_paths) - set(engine_ids))
        raise SystemExit(f"engine profile set drift: missing={missing} extra={extra}")

    profiles: dict[str, dict[str, Any]] = {}
    capability_engines: dict[str, Any] = {}
    transport_engines: dict[str, Any] = {}
    for engine in engines:
        engine_id = engine["id"]
        profile = load_json(profile_paths[engine_id])
        validate_profile(profile, engine, statuses)
        profiles[engine_id] = profile
        capability_engines[engine_id] = {
            "feature_capabilities": profile["feature_capabilities"],
            "tool_capabilities": tool_capabilities(engine),
        }
        transport_engines[engine_id] = profile["transport"]

    capability = {
        "schema_version": "1.0.0",
        "authority_id": "pcrstudio-current-engine-capability-matrix",
        "engine_count": len(engines),
        "engine_registry": "contracts/engines.toml",
        "profile_directory": "contracts/engines/profiles",
        "status_vocabulary": vocabulary,
        "engines": capability_engines,
    }
    transport = {
        "schema_version": "1.0.0",
        "authority_id": "pcrstudio-current-engine-transport-parity",
        "engine_count": len(engines),
        "engine_registry": "contracts/engines.toml",
        "engines": transport_engines,
    }
    registry = {
        "schema_version": "1.0.0",
        "authority_id": "pcrstudio-current-engine-system",
        "engine_count": len(engines),
        "engines": {
            engine["id"]: {
                "command": engine["command"],
                "resource_weight": engine["resource_weight"],
                "profile": f"contracts/engines/profiles/{engine['id']}.json",
                "authority_domains": profiles[engine["id"]]["authority_domains"],
                "differential_corpora": profiles[engine["id"]]["differential_corpora"],
            }
            for engine in engines
        },
    }
    return capability, transport, registry, profiles


def rust_projection(capability: dict[str, Any]) -> str:
    rows: list[tuple[str, str, str, str]] = []
    for engine_id, row in capability["engines"].items():
        for capability_id, spec in row["feature_capabilities"].items():
            rows.append((engine_id, "feature", capability_id, spec["status"]))
        for capability_id, spec in row["tool_capabilities"].items():
            rows.append((engine_id, "tool", capability_id, spec["status"]))
    lines = [
        "// @generated by scripts/generate-engine-contracts.py; do not edit.",
        f"pub const ENGINE_CAPABILITY_AUTHORITY_ID: &str = {json.dumps(capability['authority_id'])};",
        f"pub const ENGINE_COUNT: usize = {capability['engine_count']};",
        "pub const ENGINE_CAPABILITIES: &[(&str, &str, &str, &str)] = &[",
    ]
    lines.extend(
        f"    ({json.dumps(engine)}, {json.dumps(kind)}, {json.dumps(capability_id)}, {json.dumps(status)}),"
        for engine, kind, capability_id, status in rows
    )
    lines.append("];\n")
    return "\n".join(lines)


def ts_projection() -> str:
    return (
        "// @generated by scripts/generate-engine-contracts.py; do not edit.\n"
        'import capabilityMatrix from "./engine-capability-matrix.generated.json";\n'
        'import transportParity from "./engine-transport-parity.generated.json";\n\n'
        "export const ENGINE_CAPABILITY_MATRIX = capabilityMatrix;\n"
        "export const ENGINE_TRANSPORT_PARITY = transportParity;\n"
        "export const ENGINE_CAPABILITY_AUTHORITY_ID = capabilityMatrix.authority_id;\n"
        "export const ENGINE_COUNT = capabilityMatrix.engine_count;\n"
        "export type EngineCapabilityStatus = keyof typeof capabilityMatrix.status_vocabulary;\n"
    )


def graph(registry: dict[str, Any], profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    outputs = [
        "knowledge/runtime/engine-capability-matrix.generated.json",
        "tools/src/pcr_tools/data/engine-capability-matrix.generated.json",
        "web/src/lib/engine-capability-matrix.generated.json",
        "knowledge/runtime/engine-transport-parity.generated.json",
        "tools/src/pcr_tools/data/engine-transport-parity.generated.json",
        "web/src/lib/engine-transport-parity.generated.json",
        "knowledge/runtime/engine-system.generated.json",
        "tools/src/pcr_tools/data/engine-system.generated.json",
        "web/src/lib/engine-system.generated.json",
        "web/src/lib/engine-capabilities.generated.ts",
        "crates/pcr-core/src/engines/engine_capabilities.generated.rs",
    ]
    corpora: set[str] = set()
    for profile in profiles.values():
        corpora.update(profile["differential_corpora"])
    for rel in sorted(corpora):
        name = Path(rel).name.replace(".json", "")
        outputs.extend([
            f"knowledge/runtime/{name}.generated.json",
            f"tools/src/pcr_tools/data/{name}.generated.json",
            f"web/src/lib/{name}.generated.json",
        ])
    sources = [
        "contracts/engines.toml",
        "contracts/engines/status-vocabulary.json",
        *sorted(f"contracts/engines/profiles/{engine_id}.json" for engine_id in profiles),
        *sorted(corpora),
    ]
    return {
        "schema_version": "1.0.0",
        "authority_id": registry["authority_id"],
        "generator": "scripts/generate-engine-contracts.py",
        "engine_count": registry["engine_count"],
        "sources": sources,
        "all_generated_outputs": sorted(outputs),
    }


def emit(path: Path, text: str, *, check: bool, drift: list[str]) -> None:
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            drift.append(path.relative_to(ROOT).as_posix())
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift: list[str] = []
    capability, transport, registry, profiles = build()

    for payload, rels in (
        (capability, (
            "knowledge/runtime/engine-capability-matrix.generated.json",
            "tools/src/pcr_tools/data/engine-capability-matrix.generated.json",
            "web/src/lib/engine-capability-matrix.generated.json",
        )),
        (transport, (
            "knowledge/runtime/engine-transport-parity.generated.json",
            "tools/src/pcr_tools/data/engine-transport-parity.generated.json",
            "web/src/lib/engine-transport-parity.generated.json",
        )),
        (registry, (
            "knowledge/runtime/engine-system.generated.json",
            "tools/src/pcr_tools/data/engine-system.generated.json",
            "web/src/lib/engine-system.generated.json",
        )),
    ):
        rendered = jtext(payload)
        for rel in rels:
            emit(ROOT / rel, rendered, check=args.check, drift=drift)

    corpora: set[str] = set()
    for profile in profiles.values():
        corpora.update(profile["differential_corpora"])
    for rel in sorted(corpora):
        payload = load_json(ROOT / rel)
        rendered = jtext(payload)
        name = Path(rel).name.replace(".json", "")
        for out in (
            f"knowledge/runtime/{name}.generated.json",
            f"tools/src/pcr_tools/data/{name}.generated.json",
            f"web/src/lib/{name}.generated.json",
        ):
            emit(ROOT / out, rendered, check=args.check, drift=drift)

    emit(ROOT / "crates/pcr-core/src/engines/engine_capabilities.generated.rs", rust_projection(capability), check=args.check, drift=drift)
    emit(ROOT / "web/src/lib/engine-capabilities.generated.ts", ts_projection(), check=args.check, drift=drift)
    emit(ROOT / "contracts/engine-generated-graph.json", jtext(graph(registry, profiles)), check=args.check, drift=drift)

    if drift:
        raise SystemExit("ENGINE_CONTRACTS=CHECK-DRIFT " + ",".join(sorted(set(drift))))
    print(f"ENGINE_CONTRACTS={'CHECK-PASS' if args.check else 'GENERATED'} engines={registry['engine_count']}")


if __name__ == "__main__":
    main()
