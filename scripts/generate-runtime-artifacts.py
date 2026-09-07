#!/usr/bin/env python3
"""Regenerate PCRStudio's derived Generation-1 runtime knowledge artifacts.

This script is deliberately dependency-free and imports no PCRStudio runtime
modules.  It parses the canonical TOML/Python/JSON source files as data so it
is safe to run during a dependency-free static source audit.
"""
from __future__ import annotations

import hashlib
import json
import argparse
import importlib
import re
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHECK = False
DRIFT: list[str] = []
PROFILE_SOURCE = Path("crates/pcr-core/profiles.toml")
FOUNDATION_MODULE_SOURCE = Path("knowledge/runtime/module-contracts.generated.json")
LINUX_ACCEPTANCE_SOURCE = Path("knowledge/runtime/linux-acceptance-matrix.json")
PROFILE_OUTPUT = Path("knowledge/runtime/profile-bindings.generated.json")
TRACE_OUTPUT = Path("knowledge/runtime/module-rule-trace.generated.json")
WEB_REQUIRED_CONTEXT_OUTPUT = Path("web/src/lib/projects/required-context.generated.json")
WEB_MODULE_COPY_OUTPUT = Path("web/src/lib/module-copy.generated.json")
WEB_MODULE_DOCUMENTATION_OUTPUT = Path("web/src/lib/module-documentation.generated.json")
BIBLIOGRAPHY_METADATA_SOURCE = Path("contracts/bibliography-metadata.json")
LAMP_NUMERIC_SOURCE = Path("tools/src/pcr_tools/lamp_numeric_recipes.py")
LAMP_NUMERIC_OUTPUT = Path("web/src/lib/lamp-numeric-recipes.generated.json")
FLANKING_NUMERIC_SOURCE = Path("tools/src/pcr_tools/flanking_numeric_recipes.py")
FLANKING_NUMERIC_OUTPUT = Path("web/src/lib/flanking-numeric-recipes.generated.json")
RESTRICTION_WORKFLOW_SOURCE = Path("tools/src/pcr_tools/registries/restriction_workflows.py")
RESTRICTION_WORKFLOW_OUTPUT = Path("web/src/lib/restriction-workflows.generated.json")

ENGINE_TO_COMMAND = {
    "flanking-pair": "run",
    "consensus-pair": "universal",
    "nested": "nested",
    "outward-pair": "inverse",
    "pair-and-probe": "probe",
    "single-primer": "single",
    "mutagenic-pair": "mutagenic",
    "tiling-scheme": "tiling",
    "junction-primers": "junction",
    "discriminating-pair": "discriminate",
    "loop-set": "loop_set",
}

ATLAS_DOCUMENTS = {
    "standard-pcr": "knowledge/atlas/engines/flanking-pair/02-standard-pcr.md",
    "long-range-pcr": "knowledge/atlas/engines/flanking-pair/03-long-range-pcr.md",
    "colony-pcr": "knowledge/atlas/engines/flanking-pair/04-colony-pcr.md",
    "nested-pcr": "knowledge/atlas/engines/nested/02-nested-pcr.md",
    "inverse-pcr": "knowledge/atlas/engines/outward-pair/02-inverse-pcr.md",
    "qpcr-sybr": "knowledge/atlas/engines/flanking-pair/05-qpcr-sybr.md",
    "qpcr-probe": "knowledge/atlas/engines/pair-and-probe/02-qpcr-probe.md",
    "digital-pcr": "knowledge/atlas/engines/flanking-pair/06-digital-pcr.md",
    "arms-pcr": "knowledge/atlas/engines/discriminating-pair/02-arms-pcr.md",
    "tetra-primer-arms": "knowledge/atlas/engines/discriminating-pair/04-tetra-primer-arms.md",
    "kasp": "knowledge/atlas/engines/discriminating-pair/03-kasp.md",
    "species-specific-pcr": "knowledge/atlas/engines/flanking-pair/07-species-specific-pcr.md",
    "lamp": "knowledge/atlas/engines/loop-set/02-lamp.md",
    "rpa": "knowledge/atlas/engines/flanking-pair/08-rpa.md",
    "universal-primers": "knowledge/atlas/engines/consensus-pair/02-universal-primers.md",
    "tiled-scheme": "knowledge/atlas/engines/tiling-scheme/02-tiled-scheme.md",
    "race": "knowledge/atlas/engines/single-primer/02-race.md",
    "sequencing-primer": "knowledge/atlas/engines/single-primer/03-sequencing-primer.md",
    "gibson-assembly": "knowledge/atlas/engines/junction-primers/02-gibson-assembly.md",
    "restriction-cloning": "knowledge/atlas/engines/flanking-pair/09-restriction-cloning.md",
    "site-directed-mutagenesis": "knowledge/atlas/engines/mutagenic-pair/02-site-directed-mutagenesis.md",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    rendered = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if CHECK:
        if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
            DRIFT.append(path.as_posix())
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8", newline="\n")


MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(((?:[^()]|\([^()]*\))*)\)")
EXTERNAL_URL = re.compile(r"https?://[^\s<>\]]+")

# Bibliographic metadata verified against the publisher/index record. Sources
# without a verified record intentionally keep the descriptive label authored
# in the Atlas and use the complete Vancouver web-reference form in the UI.
CITATION_OVERRIDES = {
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC4846334/": "Lorenz TC. Polymerase chain reaction: basic protocol plus troubleshooting and optimization strategies. J Vis Exp. 2012;(63):3998. doi:10.3791/3998.",
    "https://pubmed.ncbi.nlm.nih.gov/15488375/": "Onodera K, Melcher U. Selection for 3′ end triplets for polymerase chain reaction primers. Mol Cell Probes. 2004;18(6):369-372. doi:10.1016/j.mcp.2004.05.007.",
    "https://academic.oup.com/nar/article/40/15/e115/1223759": "Untergasser A, Cutcutache I, Koressaar T, Ye J, Faircloth BC, Remm M, et al. Primer3—new capabilities and interfaces. Nucleic Acids Res. 2012;40(15):e115. doi:10.1093/nar/gks596.",
    "https://pubmed.ncbi.nlm.nih.gov/40272429/": "Bustin SA, Ruijter JM, van den Hoff MJB, Kubista M, Pfaffl MW, Shipley GL, et al. MIQE 2.0: revision of the minimum information for publication of quantitative real-time PCR experiments guidelines. Clin Chem. 2025;71(6):634-651. doi:10.1093/clinchem/hvaf043.",
    "https://pubmed.ncbi.nlm.nih.gov/32746458/": "The dMIQE Group. The Digital MIQE Guidelines update: minimum information for publication of quantitative digital PCR experiments for 2020. Clin Chem. 2020;66(8):1012-1029. doi:10.1093/clinchem/hvaa125.",
}


def clean_external_url(value: str) -> str:
    """Trim prose punctuation without truncating balanced parentheses in DOIs."""
    url = value.rstrip(".,;:")
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]
    return url


def is_public_reference(url: str) -> bool:
    """Exclude PCRStudio's own repository paths from the public bibliography."""
    return "github.com/pcrstudio/pcrstudio/" not in url.lower()


HOST_ORGANIZATIONS = {
    "academic.oup.com": "Oxford University Press",
    "assets.thermofisher.com": "Thermo Fisher Scientific",
    "bio-rad.com": "Bio-Rad Laboratories",
    "cdc.gov": "Centers for Disease Control and Prevention",
    "github.com": "GitHub",
    "iso.org": "International Organization for Standardization",
    "libnano.github.io": "libnano",
    "mafft.cbrc.jp": "MAFFT",
    "mfeprimer.com": "MFEprimer",
    "ncbi.nlm.nih.gov": "National Center for Biotechnology Information",
    "neb.com": "New England Biolabs",
    "pypi.org": "Python Packaging Authority",
    "qiagen.com": "QIAGEN",
    "stillatechnologies.com": "Stilla Technologies",
    "thermofisher.com": "Thermo Fisher Scientific",
    "viennarna.readthedocs.io": "ViennaRNA",
    "who.int": "World Health Organization",
}


def fallback_citation(url: str, label: str) -> str:
    """Give non-indexed web/manual sources an honest corporate-author form."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower().removeprefix("www.")
    organization = next(
        (name for domain, name in HOST_ORGANIZATIONS.items() if host == domain or host.endswith("." + domain)),
        "Web publisher",
    )
    title = label.strip().rstrip(".") or "Web resource"
    if title.lower().startswith(organization.lower()):
        return f"{title}."
    return f"{organization}. {title}."


def citation_record(url: str, label: str, bibliography_metadata: dict[str, Any]) -> dict[str, str]:
    metadata = bibliography_metadata.get(url)
    if metadata:
        return {"citation": str(metadata["citation"]), "kind": str(metadata.get("kind", "web"))}
    if url in CITATION_OVERRIDES:
        return {"citation": CITATION_OVERRIDES[url], "kind": "journal"}
    return {"citation": fallback_citation(url, label), "kind": "web"}


def module_documentation(module_contracts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Project every module's Atlas record into a complete, compact source index.

    Module records link to shared engine/tool records. Follow those local Markdown
    links so the UI's source list includes inherited evidence too, then deduplicate
    URLs while retaining every Atlas document that cited each source.
    """
    metadata_payload = read_json(ROOT / BIBLIOGRAPHY_METADATA_SOURCE)
    bibliography_metadata = metadata_payload.get("entries", {})
    modules: dict[str, Any] = {}
    for module_id, contract in module_contracts.items():
        root_doc = Path(str(contract["atlas_document"]))
        pending = [root_doc]
        visited: set[Path] = set()
        references: dict[str, dict[str, Any]] = {}

        while pending:
            document = pending.pop()
            absolute = ROOT / document
            if document in visited or not absolute.is_file():
                continue
            visited.add(document)
            text = absolute.read_text(encoding="utf-8")

            for label, href in MARKDOWN_LINK.findall(text):
                href = href.strip()
                clean_href = href.split("#", 1)[0].split("?", 1)[0]
                if href.startswith(("http://", "https://")):
                    url = clean_external_url(href)
                    if not is_public_reference(url):
                        continue
                    reference = references.setdefault(
                        url,
                        {
                            **citation_record(url, label, bibliography_metadata),
                            "url": url,
                            "atlas_documents": [],
                        },
                    )
                    if document.as_posix() not in reference["atlas_documents"]:
                        reference["atlas_documents"].append(document.as_posix())
                elif clean_href.endswith(".md"):
                    linked = (absolute.parent / clean_href).resolve()
                    try:
                        linked.relative_to(ROOT.resolve())
                    except ValueError:
                        continue
                    # A module may inherit its engine's 00-engine/01-tools
                    # records. Do not follow those shared records into other
                    # module-specific files in the same Atlas tree: that would
                    # make one module's bibliography contain every sibling's
                    # chemistry instead of the sources it actually inherits.
                    if document == root_doc and linked.name in {"00-engine.md", "01-tools.md"}:
                        pending.append(linked.relative_to(ROOT))

            # Include bare URLs in prose as a safety net. Markdown links remain
            # authoritative for the citation label when the same URL appears twice.
            for url in EXTERNAL_URL.findall(text):
                url = clean_external_url(url)
                if not is_public_reference(url):
                    continue
                reference = references.setdefault(
                    url,
                    {
                        **citation_record(url, url, bibliography_metadata),
                        "url": url,
                        "atlas_documents": [],
                    },
                )
                if document.as_posix() not in reference["atlas_documents"]:
                    reference["atlas_documents"].append(document.as_posix())

        modules[module_id] = {
            # Dict insertion order is the order in which the Atlas records
            # first cite each source, which is the useful default for numbered
            # Vancouver-style references.
            "references": [
                {"citation": item["citation"], "kind": item["kind"], "url": item["url"]}
                for item in references.values()
            ],
        }

    return {
        "schema_version": "1.0.0",
        "generation_policy": "Generated from the module Atlas records, linked shared records and the checked-in bibliography metadata cache by scripts/generate-runtime-artifacts.py; do not hand-edit.",
        "citation_style": "Vancouver article citations when indexed metadata is available; otherwise Vancouver internet citations with organization, title, Internet marker, access date and Available from link.",
        "citation_accessed": "2026 Sep 7",
        "modules": modules,
    }


def runtime_contract() -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    """Load module contracts from the canonical generated foundation projection.

    Legacy code parsed Python literals here. Generation 1 foundation deliberately moved module
    identity, engine binding and context ownership to contracts/modules.toml;
    generate-foundation-contracts.py materializes this projection. Keeping this
    generator on that projection prevents a second hand-maintained truth.
    """
    payload = read_json(ROOT / FOUNDATION_MODULE_SOURCE)
    modules = payload.get("modules")
    if not isinstance(modules, dict):
        raise ValueError("module-contracts.generated.json must contain a modules object")
    normalized = {str(mid): dict(contract) for mid, contract in modules.items()}
    return {mid: str(contract["engine"]) for mid, contract in normalized.items()}, normalized


def profiles() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    raw = tomllib.loads((ROOT / PROFILE_SOURCE).read_text(encoding="utf-8"))
    ordered = raw.get("profile")
    if not isinstance(ordered, list):
        raise ValueError("profiles.toml must contain [[profile]] entries")
    by_id = {str(item["id"]): item for item in ordered}
    if len(by_id) != len(ordered):
        raise ValueError("profiles.toml contains duplicate profile ids")
    return ordered, by_id


def profile_binding(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": profile["name"],
        "engine": profile["engine"],
        "goal": profile["goal"],
        "status": profile["status"],
        "modifiers": profile.get("modifiers", []),
        "enzyme": profile.get("enzyme", []),
        "requires": profile.get("requires", []),
        "defaults": profile.get("defaults", {}),
    }


def main() -> None:
    global CHECK
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if generated runtime artifacts drift from canonical sources.")
    args = parser.parse_args()
    CHECK = args.check
    ordered_profiles, by_id = profiles()
    module_to_engine, module_contracts = runtime_contract()
    acceptance = read_json(ROOT / LINUX_ACCEPTANCE_SOURCE)
    acceptance_modules = acceptance.get("modules", {})

    module_ids = list(module_to_engine)
    if len(module_ids) != 21 or len(set(module_to_engine.values())) != 11:
        raise ValueError("Generation-1 contract must remain exactly 21 modules -> 11 engines")
    if set(module_ids) != set(by_id):
        raise ValueError("profiles.toml module ids do not match MODULE_TO_ENGINE")
    if set(module_ids) != set(module_contracts):
        raise ValueError("MODULE_CONTRACTS module ids do not match MODULE_TO_ENGINE")
    if set(module_ids) != set(acceptance_modules):
        raise ValueError("Linux acceptance matrix module ids do not match MODULE_TO_ENGINE")

    for module_id, engine in module_to_engine.items():
        if by_id[module_id].get("engine") != engine:
            raise ValueError(f"{module_id}: profile engine disagrees with MODULE_TO_ENGINE")
        if str(module_contracts[module_id].get("command")) != ENGINE_TO_COMMAND.get(engine):
            raise ValueError(f"{module_id}: canonical command disagrees with engine command contract")

    profile_payload = {
        "schema_version": "1.1.0",
        "source": PROFILE_SOURCE.as_posix(),
        "source_sha256": sha256(ROOT / PROFILE_SOURCE),
        "semantics": {
            "purpose": "Exact active module/profile bindings used by Generation-1 runtime.",
            "numeric_policy": "Only values bound in the active profile are runtime defaults. Numeric Evidence in the Atlas remains source-/study-/vendor-scoped unless a named overlay or explicit implementation rule activates it.",
            "override_policy": "Hard engine/assay/chemistry invariants cannot be broken; bounded/recommended values may be user-overridden only where the runtime contract allows it and provenance records the resolution.",
            "generation_policy": "Generated from crates/pcr-core/profiles.toml by scripts/generate-runtime-artifacts.py; do not hand-edit.",
        },
        "profiles": {item["id"]: profile_binding(item) for item in ordered_profiles},
    }
    write_json(ROOT / PROFILE_OUTPUT, profile_payload)

    trace_modules: dict[str, Any] = {}
    for module_id in module_ids:
        engine = module_to_engine[module_id]
        contract = module_contracts[module_id]
        atlas_doc = Path(str(contract["atlas_document"]))
        atlas_abs = ROOT / atlas_doc
        if not atlas_abs.is_file():
            raise FileNotFoundError(f"{module_id}: missing Atlas document {atlas_doc}")
        module_runtime_contract = {
            "gates": list(contract.get("gates", ())),
            "fallback": contract.get("fallback"),
            "required_context": list(contract.get("required_context", ())),
            "wire_required_context": list(contract.get("wire_required_context", ())),
            "wire_required_any_of": [list(group) for group in contract.get("wire_required_any_of", ())],
            "engine": engine,
            "command": str(contract["command"]),
        }
        conditional = contract.get("conditional_required_context", ())
        if conditional:
            module_runtime_contract["conditional_required_context"] = [
                {"when": dict(rule.get("when", {})), "required_context": list(rule.get("required_context", ()))}
                for rule in conditional
            ]
        wire_conditional = contract.get("wire_conditional_required_context", ())
        if wire_conditional:
            module_runtime_contract["wire_conditional_required_context"] = [
                {"when": dict(rule.get("when", {})), "required_context": list(rule.get("required_context", ()))}
                for rule in wire_conditional
            ]
        trace_modules[module_id] = {
            "engine": engine,
            "atlas_document": atlas_doc.as_posix(),
            "atlas_sha256": sha256(atlas_abs),
            "profile_source": PROFILE_SOURCE.as_posix(),
            "profile_sha256": profile_payload["source_sha256"],
            "active_profile": by_id[module_id],
            "runtime_contract": module_runtime_contract,
            "linux_acceptance": acceptance_modules[module_id],
            "coverage_state": "implemented-or-explicitly-bounded",
            "wet_lab_claim": "not-implied-by-computational-design",
        }

    trace_payload = {
        "schema_version": "1.1.0",
        "purpose": "Machine-readable trace from each public module to its Atlas evidence, active executable profile, runtime gates/fallback, worker command and Linux acceptance contract.",
        "scientific_numeric_policy": "Atlas evidence does not become an executable default merely by existing. The active profile is the executable numeric authority; hard/bounded/recommended override semantics are enforced separately.",
        "generation_policy": "Generated from canonical source by scripts/generate-runtime-artifacts.py; do not hand-edit.",
        "modules": trace_modules,
    }
    write_json(ROOT / TRACE_OUTPUT, trace_payload)

    web_required_context = {
        "schema_version": "2.1.0",
        "generation_policy": "Generated from contracts/modules.toml; do not hand-edit.",
        "modules": {
            module_id: {
                "required_context": list(module_contracts[module_id].get("required_context", ())),
                "conditional_required_context": [
                    {
                        "when": dict(rule.get("when", {})),
                        "required_context": list(rule.get("required_context", ())),
                    }
                    for rule in module_contracts[module_id].get("conditional_required_context", ())
                ],
                "wire_required_context": list(module_contracts[module_id].get("wire_required_context", ())),
                "wire_conditional_required_context": [
                    {
                        "when": dict(rule.get("when", {})),
                        "required_context": list(rule.get("required_context", ())),
                    }
                    for rule in module_contracts[module_id].get("wire_conditional_required_context", ())
                ],
                "wire_required_any_of": [list(group) for group in module_contracts[module_id].get("wire_required_any_of", ())],
                "field_owners": dict(module_contracts[module_id].get("field_owners", {})),
            }
            for module_id in module_ids
        },
    }
    write_json(ROOT / WEB_REQUIRED_CONTEXT_OUTPUT, web_required_context)

    # The browser receives the same canonical user-facing module copy as the
    # Rust registry. This keeps a running frontend useful during a backend
    # rebuild and prevents a stale API process from putting old descriptions
    # back into an otherwise current interface.
    missing_checks = [item["id"] for item in ordered_profiles if not item.get("checks")]
    if missing_checks:
        raise ValueError(
            "Every module profile must define page-specific design checks; missing: "
            + ", ".join(missing_checks)
        )

    web_module_copy = {
        "schema_version": "1.0.0",
        "source": PROFILE_SOURCE.as_posix(),
        "source_sha256": profile_payload["source_sha256"],
        "generation_policy": "Generated from crates/pcr-core/profiles.toml by scripts/generate-runtime-artifacts.py; do not hand-edit.",
        "modules": {
            item["id"]: {
                "name": item["name"],
                "summary": item["summary"],
                "guidance": item["guidance"],
                "checks": item["checks"],
            }
            for item in ordered_profiles
        },
    }
    write_json(ROOT / WEB_MODULE_COPY_OUTPUT, web_module_copy)

    # Keep the module guide's bibliography on the same generated path as the
    # module contract. This scans the module Atlas record plus any linked local
    # engine/tool records, so inherited scientific sources are not silently lost.
    documentation = module_documentation(module_contracts)
    documentation["source_sha256"] = {
        module_id: sha256(ROOT / str(contract["atlas_document"]))
        for module_id, contract in module_contracts.items()
    }
    write_json(ROOT / WEB_MODULE_DOCUMENTATION_OUTPUT, documentation)

    # The LAMP numeric source is intentionally standard-library-only and has no
    # PCRStudio runtime imports, so executing it here is safe in source-only
    # release environments. The browser receives the same canonical numeric
    # facts as the Python worker rather than a hand-copied table.
    tools_src = ROOT / "tools/src"
    tools_src_text = str(tools_src)
    if tools_src_text not in sys.path:
        sys.path.insert(0, tools_src_text)
    numeric_module = importlib.import_module("pcr_tools.lamp_numeric_recipes")
    numeric_catalogue = numeric_module.generated_catalogue()
    numeric_catalogue["source"] = LAMP_NUMERIC_SOURCE.as_posix()
    numeric_catalogue["source_sha256"] = sha256(ROOT / LAMP_NUMERIC_SOURCE)
    numeric_catalogue["generation_policy"] = "Generated from tools/src/pcr_tools/lamp_numeric_recipes.py; do not hand-edit."
    write_json(ROOT / LAMP_NUMERIC_OUTPUT, numeric_catalogue)

    flanking_module = importlib.import_module("pcr_tools.flanking_numeric_recipes")
    flanking_catalogue = flanking_module.generated_catalogue()
    flanking_catalogue["source"] = FLANKING_NUMERIC_SOURCE.as_posix()
    flanking_catalogue["source_sha256"] = sha256(ROOT / FLANKING_NUMERIC_SOURCE)
    flanking_catalogue["generation_policy"] = "Generated from tools/src/pcr_tools/flanking_numeric_recipes.py; do not hand-edit."
    write_json(ROOT / FLANKING_NUMERIC_OUTPUT, flanking_catalogue)

    restriction_module = importlib.import_module("pcr_tools.registries.restriction_workflows")
    restriction_catalogue = restriction_module.generated_catalogue()
    restriction_catalogue["source"] = RESTRICTION_WORKFLOW_SOURCE.as_posix()
    restriction_catalogue["source_sha256"] = sha256(ROOT / RESTRICTION_WORKFLOW_SOURCE)
    restriction_catalogue["generation_policy"] = "Generated from tools/src/pcr_tools/registries/restriction_workflows.py; do not hand-edit."
    write_json(ROOT / RESTRICTION_WORKFLOW_OUTPUT, restriction_catalogue)

    if CHECK and DRIFT:
        print("RUNTIME_GENERATED_DRIFT")
        for rel in DRIFT:
            print(rel)
        raise SystemExit(1)
    mode = "CHECK-PASS" if CHECK else "GENERATED"
    print(
        f"RUNTIME_ARTIFACTS={mode} {PROFILE_OUTPUT}, {TRACE_OUTPUT}, {WEB_REQUIRED_CONTEXT_OUTPUT}, {WEB_MODULE_COPY_OUTPUT}, {WEB_MODULE_DOCUMENTATION_OUTPUT}, {LAMP_NUMERIC_OUTPUT} and {FLANKING_NUMERIC_OUTPUT} "
        f"modules={len(module_ids)}"
    )


if __name__ == "__main__":
    main()
