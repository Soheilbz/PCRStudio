#!/usr/bin/env python3
"""Generate PCRStudio Gen-1 expert-audit artifacts without importing/running workers.

This is a source-only projection. It reads canonical profiles/contracts and test/UI
sources, then emits machine-readable and human-readable release evidence.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_AS_OF = "2026-09-05"
REV = ROOT / "knowledge/reviews"
RUN = ROOT / "knowledge/runtime"

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true", help="Fail if any generated expert artifact would change.")
args = parser.parse_args()
CHECK = bool(args.check)
if not CHECK:
    REV.mkdir(parents=True, exist_ok=True)
    RUN.mkdir(parents=True, exist_ok=True)

DRIFT: list[str] = []

def emit_text(path: Path, text: str) -> None:
    if CHECK:
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != text:
            DRIFT.append(path.relative_to(ROOT).as_posix())
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    emit_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


profiles = tomllib.loads((ROOT / "crates/pcr-core/profiles.toml").read_text(encoding="utf-8"))["profile"]
profile_by_id = {str(p["id"]): p for p in profiles}
contracts = load_json("knowledge/runtime/module-contracts.json")["modules"]
engine_contracts = load_json("knowledge/atlas/contracts/engine-tool-contracts.json")["engines"]
engine_by_id = {row["engine_id"]: row for row in engine_contracts}
toolchain = load_json("knowledge/atlas/contracts/toolchain-manifest.json")
tool_by_id = {row["tool_id"]: row for row in toolchain["tools"]}
acceptance = load_json("knowledge/runtime/linux-acceptance-matrix.json")["modules"]
validation_source = (ROOT / "tools/src/pcr_tools/validation_plan.py").read_text(encoding="utf-8")

FINGERPRINT_INPUTS = (
    "contracts/modules.toml",
    "knowledge/runtime/engine-system.generated.json",
    "knowledge/runtime/engine-capability-matrix.generated.json",
    "knowledge/runtime/engine-transport-parity.generated.json",
    "contracts/chemistry/consensus-profiles.json",
    "contracts/chemistry/discriminating-protocols.json",
    "contracts/chemistry/assembly-protocols.json",
    "contracts/chemistry/mutagenesis-protocols.json",
    "contracts/chemistry/nested-protocols.json",
    "contracts/chemistry/consensus-differential-corpus.json",
    "contracts/chemistry/discriminating-differential-corpus.json",
    "contracts/chemistry/junction-differential-corpus.json",
    "contracts/chemistry/mutagenesis-differential-corpus.json",
    "contracts/chemistry/nested-differential-corpus.json",
    "crates/pcr-core/profiles.toml",
    "knowledge/runtime/module-contracts.json",
    "knowledge/atlas/contracts/engine-tool-contracts.json",
    "knowledge/atlas/contracts/toolchain-manifest.json",
    "tools/src/pcr_tools/runtime_contract.py",
    "tools/src/pcr_tools/validation_plan.py",
    "knowledge/runtime/scientific-integrity-policy.json",
    "tools/src/pcr_tools/pipeline.py",
    "tools/src/pcr_tools/flanking_request.py",
    "tools/src/pcr_tools/loop_set.py",
    "tools/src/pcr_tools/lamp_geometry.py",
    "tools/src/pcr_tools/lamp_profiles.py",
    "tools/src/pcr_tools/registries/lamp.py",
    "tools/src/pcr_tools/registries/flanking_protocols.py",
    "tools/src/pcr_tools/lamp_numeric_recipes.py",
    "tools/src/pcr_tools/accessibility.py",
    "tools/src/pcr_tools/restriction.py",
    "tools/src/pcr_tools/pydna_bridge.py",
    "tools/src/pcr_tools/data/restriction_enzyme_registry.json",
    "tools/src/pcr_tools/multiplex.py",
    "tools/src/pcr_tools/discriminate.py",
    "tools/src/pcr_tools/variants.py",
    "tools/src/pcr_tools/kasp_plus_minus.py",
    "tools/src/pcr_tools/workflow_evidence.py",
    "tools/src/pcr_tools/probe.py",
    "tools/src/pcr_tools/loop_set.py",
    "tools/src/pcr_tools/single.py",
    "tools/src/pcr_tools/tiling.py",
    "tools/src/pcr_tools/junction.py",
    "tools/src/pcr_tools/inverse.py",
    "tools/src/pcr_tools/mutagenic.py",
    "tools/src/pcr_tools/nested.py",
    "tools/src/pcr_tools/universal.py",
    "tools/src/pcr_tools/universal_panel.py",
    "tools/src/pcr_tools/specificity.py",
    "tools/src/pcr_tools/design.py",
    "web/src/components/design/page-plan.ts",
    "web/src/components/design/result-overview.tsx",
    "web/src/components/design/toolchain-status.tsx",
    "web/src/components/design/design-result.tsx",
    "web/src/components/design/engine-fields.tsx",
    "web/src/components/design/engine-fields/lamp-fields.tsx",
    "web/src/components/design/workflow-evidence.tsx",
    "web/src/components/project/workspace.tsx",
    "web/src/lib/projects/request.ts",
    "web/src/lib/projects/engine-request-extensions.ts",
    "web/src/lib/projects/required-context.ts",
    "web/src/lib/projects/fork-settings.ts",
    "web/src/lib/kasp-endpoint.ts",
    "web/src/lib/contracts/design-requests.ts",
    "tools/tests/test_engine_contract_regressions.py",
    "tools/tests/test_engine_authority_contract.py",
    "crates/pcr-core/tests/engine_differential_contract.rs",
    "scripts/check-engine-web-contract.js",
    "scripts/generate-engine-authorities.py",
    "scripts/generate-engine-contracts.py",
)
CHEMISTRY_FINGERPRINT_INPUTS = tuple(
    p.relative_to(ROOT).as_posix()
    for p in sorted((ROOT / "contracts/chemistry").iterdir())
    if p.is_file() and p.suffix in {".json", ".toml"}
)
EXTRA_FINGERPRINT_INPUTS = (
    "contracts/scientific-authorities.json",
    "knowledge/sources/flanking-source-snapshots.json",
    "knowledge/runtime/scientific-authority-registry.generated.json",
    "tools/src/pcr_tools/scientific_authority.py",
    "scripts/generate-scientific-authority-registry.py",
    "scripts/generate-flanking-source-snapshots.py",
    "contracts/capability-truth.json",
)
FINGERPRINT_INPUTS = tuple(dict.fromkeys((*FINGERPRINT_INPUTS, *CHEMISTRY_FINGERPRINT_INPUTS, *EXTRA_FINGERPRINT_INPUTS)))
SOURCE_FINGERPRINTS = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in FINGERPRINT_INPUTS}
GENERATOR_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def with_meta(doc: dict[str, Any]) -> dict[str, Any]:
    doc["source_fingerprints"] = SOURCE_FINGERPRINTS
    doc["generator_sha256"] = GENERATOR_SHA256
    return doc

MODULE_REVIEW: dict[str, dict[str, Any]] = {
    "standard-pcr": {"science":"strong-named-registry","boundary":"CURRENT retains 16 named executable Standard-PCR chemistry branches under one generated protocol authority: the CURRENT set plus OneTaq/OneTaq GC/Quick-Load variants, PCRBIO HS Taq Mix, QIAGEN AllTaq, Thermo Platinum II, TOYOBO KOD One and the dedicated NEB M0284 multiplex branch. Bench chemistry remains separate from sequence ranking; M0284 is multiplex-only and all source-conditioned numeric overrides remain fail-closed outside their documented envelope.","upgrades":["Admit further named polymerase/kit overlays only when their current source, chemistry distinctions, numeric contract, full-stack wiring and native qualification are complete."]},
    "long-range-pcr": {"science":"strong-multi-protocol","boundary":"CURRENT retains seven current executable long-range branches: NEB LongAmp, Takara PrimeSTAR GXL, QIAGEN UltraRun, NEB Q5-XT, Promega GoTaq Long, Thermo Platinum SuperFi II long-range and TOYOBO KOD Long; Thermo K018x remains historical-only. GoTaq Long has a source-conditioned numeric contract including template-class reach, and long-target HMW integrity remains explicit evidence rather than an inferred guarantee.","upgrades":["Admit another long-range chemistry only through an independently sourced product contract; do not generalize plasmid/simple-template reach to genomic DNA or reconstruct proprietary buffer thermodynamics."]},
    "colony-pcr": {"science":"strong-context-handoff","boundary":"CURRENT uses a generated colony authority for host class, preparation and named SOP identity. Five named source-backed SOP/product branches are selectable alongside a provenance-required custom SOP, including the NEB M0689 supplemental colony-PCR protocol using OneTaq Hot Start Quick-Load. Colony sample input is first-class; unsupported host/preparation combinations fail closed in Python/Rust instead of inheriting bacterial lysis assumptions. Screening geometry remains distinct from empirical colony, gel, miniprep and Sanger evidence.","upgrades":["Add a non-bacterial named SOP only when host-specific preparation authority is explicit; do not collapse yeast, fungi or microalgae into a bacterial direct-transfer recipe."]},
    "nested-pcr": {"science":"strong-two-round-workflow-current","boundary":"CURRENT models Round 1 and Round 2 as independent reactions with typed direct/diluted/purified/custom transfer, source-backed NEB Msz or Thermolabile Exonuclease I cleanup, causal outer-off-target to inner-product re-screening, and contamination/run evidence with decision_impact=none. Fully nested and both semi-nested two-tube topologies execute; generic one-tube nested PCR and anonymous dUTP/UNG numeric recipes remain fail-closed.","upgrades":["Add a named one-tube branch only as a new mechanism-specific protocol contract; do not generalize an assay-specific paper into a universal switch."]},
    "inverse-pcr": {"science":"strong-topology-closed","boundary":"CURRENT validates full-reference outward topology for linear and circular templates, including origin-spanning reconstruction and multi-enzyme cohorts. Restriction/self-ligation preparation remains separately provenance-bound; pydna topology evidence and Sanger handoff are first-class evidence and never replace digest/circularisation provenance.","upgrades":["Perform Linux/native pydna differential qualification and bench digest/circularisation/Sanger qualification before Stable promotion."]},
    "qpcr-sybr": {"science":"strong-miqe-protocol-boundary","boundary":"CURRENT retains 13 named dye-qPCR/one-step RT-qPCR chemistry branches, including Thermo PowerTrack, QIAGEN QuantiNova, Bio-Rad SsoAdvanced, three distinct Solis HOT FIREPol EvaGreen formulations and the source-limited Vazyme Q713 branch. qPCR instrument/ROX profile is generated from the canonical authority and source-conditioned chemistry/instrument incompatibilities fail closed. The current Vazyme Q713 product authority is pinned to the reviewed Flyer Q713 V25.1 identity and public 20-uL/SYBR Green I/dUTP-UDG/ROX claims; exact reagent stoichiometry remains unresolved until the transferable current IFU is content-addressed. CSV/TSV/TXT plus RDML/RDES-style evidence import is non-inferential. Standard-curve, efficiency, controls, melt and run evidence remain measured MIQE-oriented evidence with decision_impact=none on primer ranking.","upgrades":["Qualify the exact current Q713 IFU/reagent table when locally content-addressed authority is available.","Add instrument/version-specific raw-curve adapters only through validated parsers; never infer absent Cq, calibration, threshold, ROX or sample-processing evidence."]},
    "qpcr-probe": {"science":"strong-hydrolysis-mgb-external-authority","boundary":"CURRENT executes reviewed conventional Thermo Fisher/IDT hydrolysis chemistry directly and treats MGB/NFQ as an external-authority-required workflow. PCRStudio exports a content-bound candidate set, imports MGB-aware Tm only for the same candidate-set SHA-256 and never substitutes ordinary-DNA Tm. Optical authority, transcript-junction, probe-specific variants, combined specificity and multiplex interaction evidence are explicit; observed evidence never silently mutates sequence ranking.","upgrades":["Qualify additional instrument/version-specific optical profiles and raw instrument evidence parsers with pinned sources."]},
    "digital-pcr": {"science":"strong-dmiqe-platform-boundary","boundary":"CURRENT keeps chemistry and platform routing explicit. Bio-Rad QX200 ddPCR EvaGreen chemistry is source-backed for QX200, QX600 and QX ONE; QX Continuum is routed to Pair+Probe rather than assigned an unverified dye chemistry. QX700/Nio/naica and QIAcuity retain separate source-backed branches and platform×consumable compatibility. QIAcuity result provenance exposes the current Software Suite 3.5 / VPF Version 13 reference while requiring the exact software/VPF actually used by the measured run. CSV/TSV plus RDML/RDES run evidence import remains non-inferential: threshold, rain, partition volume and concentration never come from primer design.","upgrades":["Qualify vendor-native run/export parsers on Linux with versioned real evidence corpora; current generic evidence import must remain non-inferential.","Keep probe/channel/cluster-aware digital-PCR multiplex in Pair+Probe rather than approximating it with dye-only Flanking semantics."]},
    "arms-pcr": {"science":"strong-evidence-scoped","boundary":"CURRENT normalizes SNV/MNV identity with reference provenance, masks caller-supplied nearby variants, and scopes terminal/secondary mismatch ranking to a versioned Taq-like non-proofreading evidence model. ARMS remains SNV-anchor based; indels are not coerced to synthetic SNVs and empirical paired-allele discrimination remains required.","upgrades":["Add a proofreading-compatible allele-specific chemistry only as a separately validated protocol/evidence topology."]},
    "tetra-primer-arms": {"science":"strong-readout-aware","boundary":"CURRENT preserves four-primer SNV geometry, explicit outer-control/allele products, caller-declared agarose/PAGE/capillary readout context and band-separation review. It does not invent a universal gel-resolution threshold or universal inner:outer concentration ratio; empirical genotype discrimination remains wet-lab evidence.","upgrades":["Admit additional readout-specific quantitative resolution models only when the electrophoresis authority and assay context are explicit."]},
    "kasp": {"science":"strong-endpoint-plus-minus","boundary":"CURRENT supports KASP-compatible biallelic genotype design and a distinct junction-aware plus/minus branch for suitable insertion/deletion/complex/presence-absence variants. Current KASP-TF V5 and historical CURRENT compatibility identities are separated. CSV/TSV FAM×HEX evidence import preserves provider/software calls and controls but does not invent genotype thresholds or claim proprietary Kraken equivalence.","upgrades":["Add instrument-export-specific endpoint adapters only when parser/version semantics are validated; do not promote generic cluster auto-calling without a source-backed model."]},
    "species-specific-pcr": {"science":"strong-fail-closed-panel-exclusivity","boundary":"CURRENT requires separate inclusivity/exclusivity panels and canonical per-record accession.version, role and topology metadata. Linear, circular and fragment records are scanned with topology-aware semantics, including across-origin circular products. Canonical snapshot hashing, duplicate/version checks, surveillance diff, mismatch base identity and optional population-group/weight evidence are implemented; weights never relax the strict sequence gate. A finite submitted panel is explicitly not whole-RefSeq/Primer-BLAST/MFEprimer proof and external database claims require a separately fingerprinted validator/database release.","upgrades":["Add automated accession/taxonomy fetching and suppression/replacement checks only with pinned database/taxonomy authority.","Add population/pangenome completeness claims only when the sampling frame and allele-frequency source are explicit; user-declared weights remain evidence, not proof."]},
    "lamp": {"science":"strong-lamp-canonical-closure","boundary":"CURRENT keeps classic six-region LAMP linear-target topology with one canonical authority generated into Python/Rust/Web/runtime projections. PrimerExplorer V5 automatic semantics are AT-rich <=45%, Normal >45% and <60%, and GC-rich >=60%. Fixed-primer anchoring, mutation-position anchoring, integrated/core-first/add-loops stages and a deterministic 2-4-set empirical screening cohort are first-class without inventing wet-lab mismatch rules. Bench chemistry uses ordered source-backed thermal stages and a shared Python/Rust/Web differential corpus. Vazyme RP712 is pinned to the current V25.1 manual landing-page identity and product claims, but its exact vendor reagent table remains numeric-unresolved until the manual bytes are locally content-addressed; Hyasen HYB413/HYB414/HYB315 retain source-backed admitted recipes. Exact-product contradiction guards remain explicit for Takara RR385, Meridian MDX126 and Nippon NE6041/NE6043. Optional ViennaRNA Turner-2004 RNA accessibility remains post-selection. Modified reporter, multiplex reporter, lateral-flow and circular classic-LAMP topology remain fail-closed until independently executable; chemistry/bench/evidence stays decision_impact=none.","upgrades":["Content-address the current RP712 V25.1 manual bytes before promoting an exact vendor reagent table.","Admit future chemistry only with exact source-bounded compatibility/numeric authority and catalogue-snapshot provenance.","Keep modified reporter and circular classic-LAMP topology non-executable until topology-specific algorithm and native qualification exist."]},
    "rpa": {"science":"strong-named-plain-primer-branches","boundary":"CURRENT retains four executable plain-ACGT RPA branches: TwistAmp Basic, TwistAmp Liquid Basic, Thermo Fisher Lyo-ready RPA/RT-RPA and G-Biosciences RPA 786-2155. Thermo supports its source-backed 20–50 µL scaling envelope, and a deterministic diversity-aware shortlist preserves multiple empirical screening candidates without changing the primary in-silico ranking. Exo/Nfo/Fpg/SIBA remain typed non-executable boundaries until modified-probe/nuclease topology is represented.","upgrades":["Support Exo/Nfo/Fpg only after fluorophore/quencher/THF-or-dSpacer/cleavage/3-prime-block semantics are first-class and independently tested."]},
    "universal-primers": {"science":"strong-panel-formulation","boundary":"CURRENT makes alignment authority, panel QC, strict/threshold/majority/weighted/stratified consensus policy, exact degenerate-member enumeration, observed weighted/stratified coverage, finite target-vs-nontarget evidence and physical oligo formulation first-class. MUSCLE is an alignment-sensitivity validator, split-pool and amplicon informativeness are diagnostic, and user weights never become population prevalence.","upgrades":["Add external population/pangenome completeness only with a declared sampling frame and pinned source; retain panel coverage as descriptive evidence otherwise."]},
    "tiled-scheme": {"science":"strong-lifecycle-closed","boundary":"CURRENT keeps PrimalScheme3 as the primary create/panel/repair/replace backend and adds circular scheme-create, native visualisation evidence, depth/dropout review, repair handoff and version/scheme diff. Lifecycle controls remain operation-specific and no primary-backend substitution is release-grade.","upgrades":["CURRENT closure already includes circular scheme-create, native visualisation evidence, depth/dropout review and version/scheme diff; perform Linux/native PrimalScheme3/Olivar qualification with exact version/hash/database evidence before Stable promotion."]},
    "race": {"science":"strong-boundary-aware","boundary":"CURRENT separates biological direction, substrate, cDNA preparation, primary/nested round, exact PCR partner, nested GSP plan and poly(A) semantics. GeneRacer and FirstChoice exact partners are versioned; SMARTer current catalog identities 634858/634859 remain caller-partner-bound and require SOP/manual revision plus SHA-256. Candidate transcript ends remain unvalidated until sequence evidence confirms them.","upgrades":["Qualify current SMARTer manual/partner identities only when redistributable or locally content-addressed authority is available; never infer proprietary universal-primer sequence from obsolete documentation."]},
    "sequencing-primer": {"science":"strong-run-handoff","boundary":"CURRENT separates direction/dead-zone/read-length placement from instrument/facility SOP and cycle-sequencing reaction handoff. Exact universal-primer reuse requires unique binding, bidirectional planning and primer walking are first-class, and bounded AB1/ABIF chromatogram import is an evidence-only review layer that never reorders primer candidates. Provider/instrument read-window assumptions remain explicitly source- and run-bound.","upgrades":["Qualify a real multi-provider/multi-instrument AB1 corpus on Linux and pin provider SOP/read-window source snapshots; do not infer trace quality from design-time geometry."]},
    "gibson-assembly": {"science":"strong-method-separated-assembly","boundary":"CURRENT treats Gibson E5510 and NEBuilder HiFi E2621/E5520/E2623 as distinct source-backed method/protocol authorities. Ordered typed fragments, construct graph reconstruction, restriction-generated material, short oligo material, approximate molarity provenance and feature/frame diagnostics are first-class; method-specific overlap/reaction numbers never cross-inherit.","upgrades":["Add another assembly chemistry only with an independent capability/protocol contract; Golden Gate remains a separate Type IIS topology."]},
    "restriction-cloning": {"science":"strong-directionality-construct-simulation","boundary":"CURRENT preserves exact insert/circular donor reconstruction, frame/fusion intent and source-fact-driven digest/ligation calculators across 26 curated enzyme geometries. Current supplier buffer/temperature/heat-inactivation evidence is version-specific; SacI-HF close-to-end evidence is now pinned, while HaeIII/MspI/TaqI/HinfI near-end minima remain explicitly unresolved because no enzyme-specific row was present in the reviewed current table. Methylation evidence is enzyme/context-specific and star activity remains fail-closed rather than inferred. Golden Gate stays a separate Type IIS topology.","upgrades":["Resolve the four remaining near-end minima only when an enzyme-specific current supplier table row is published; expand exact-enzyme evidence without cross-inheriting conditions."]},
    "site-directed-mutagenesis": {"science":"strong-topology-separated","boundary":"CURRENT separates Q5 back-to-back, QuikChange Lightning complementary, Lightning Multi same-strand and NEBuilder multi-site routing topologies. Q5 split-tail insertion is source-bounded through 100 nt, multi-edit and amino-acid inputs reconstruct the exact edited construct, library modes report theoretical sequence space only, and clone evidence remains separate from primer ranking.","upgrades":["Add further named mutagenesis families only as topology-specific authorities; never reuse Q5 or Agilent Tm rules across methods."]},
}

assert set(MODULE_REVIEW) == set(profile_by_id) == set(contracts), "module expert dictionary must cover exactly 21 modules"

# Test-source and UI-source evidence (source-only; does not claim execution).
test_paths: list[Path] = []
for root_rel in ("tools/tests", "crates", "web/src"):
    root = ROOT / root_rel
    for p in root.rglob("*"):
        if any(part in {"__pycache__", ".pytest_cache", ".local", "node_modules", "target"} for part in p.relative_to(ROOT).parts):
            continue
        if p.is_file() and p.suffix != ".pyc" and ("test" in p.name.lower() or "spec" in p.name.lower()):
            test_paths.append(p)
ui_paths = [
    p for p in (ROOT / "web/src").rglob("*")
    if p.is_file()
    and p.suffix in {".ts", ".tsx"}
    and not any(part in {"node_modules", ".local"} for part in p.relative_to(ROOT).parts)
]

def files_containing(paths: list[Path], needle: str) -> list[str]:
    hits=[]
    for p in paths:
        try: text=p.read_text(encoding="utf-8", errors="ignore")
        except OSError: continue
        if needle in text:
            hits.append(p.relative_to(ROOT).as_posix())
    return sorted(hits)

# External adapter/source evidence by tool id.
TOOL_RUNTIME_EVIDENCE = {
    "primer3_core": ["tools/src/pcr_tools/design.py", "tools/src/pcr_tools/thermo.py"],
    "primer3_py": ["tools/pyproject.toml", "tools/src/pcr_tools/design.py"],
    "mfeprimer": ["tools/src/pcr_tools/external_validation.py"],
    "ncbi_blast_plus": ["tools/src/pcr_tools/external_validation.py"],
    "mafft": ["tools/src/pcr_tools/align.py", "tools/src/pcr_tools/primalscheme_adapter.py"],
    "primerpooler": ["tools/src/pcr_tools/external_validation.py"],
    "primalscheme3": ["tools/src/pcr_tools/primalscheme_adapter.py"],
    "viennarna": ["tools/src/pcr_tools/accessibility.py", "tools/src/pcr_tools/probe.py", "tools/src/pcr_tools/junction.py"],
    "pydna": ["tools/src/pcr_tools/pydna_bridge.py", "tools/src/pcr_tools/external_validation.py"],
    "primer_blast": ["knowledge/atlas/contracts/toolchain-manifest.json"],
    "nupack4": ["knowledge/atlas/contracts/toolchain-manifest.json"],
}

modules_out: dict[str, Any] = {}
for mid in sorted(profile_by_id):
    p = profile_by_id[mid]
    c = contracts[mid]
    engine = str(p["engine"])
    bindings = engine_by_id[engine]["bindings"]
    tests = files_containing(test_paths, mid)
    # This Vitest suite iterates `plannedModules()` and therefore exercises the
    # page-plan invariants for every module even when a literal module id does
    # not appear in the test source (ARMS was the motivating example).
    generic_ui_test = "web/src/components/design/page-plan.test.ts"
    if (ROOT / generic_ui_test).is_file():
        tests = sorted(set(tests + [generic_ui_test]))
    test_layers = sorted({
        "python-worker" if path.startswith("tools/tests/") else
        "rust-contract" if path.startswith("crates/") else
        "web-ui" if path.startswith("web/src/") else "other"
        for path in tests
    })
    ui = files_containing(ui_paths, mid)
    modules_out[mid] = {
        "name": p["name"],
        "engine": engine,
        "profile_status": p["status"],
        "science_assessment": MODULE_REVIEW[mid]["science"],
        "strict_gates": c.get("gates", []),
        "required_context": c.get("required_context", []),
        "conditional_required_context": c.get("conditional_required_context", []),
        "wire_required_context": c.get("wire_required_context", []),
        "wire_conditional_required_context": c.get("wire_conditional_required_context", []),
        "wire_required_any_of": c.get("wire_required_any_of", []),
        "fallback_policy": c.get("fallback"),
        "tool_bindings": bindings,
        "validation_plan_declared": f'"{mid}"' in validation_source,
        "test_source_count": len(tests),
        "test_layers": test_layers,
        "test_sources": tests,
        "ui_source_count": len(ui),
        "ui_sources": ui,
        "claim_boundary": MODULE_REVIEW[mid]["boundary"],
        "upgrade_opportunities": MODULE_REVIEW[mid]["upgrades"],
        "linux_runtime_qualification": "required-before-Linux-validated-release",
    }

expert = with_meta({
    "schema_version": "1.0.0",
    "audit_as_of": AUDIT_AS_OF,
    "scope": "source-only multidisciplinary audit; native Linux scientific runtime/build is an independent qualification gate",
    "release_rule": "no-result/refusal is acceptable; changing the scientific question to obtain a result is not",
    "module_count": len(modules_out),
    "engine_count": len({v["engine"] for v in modules_out.values()}),
    "modules": modules_out,
})
dump(REV / "EXPERT-MODULE-AUDIT.json", expert)

lines=["# PCRStudio Expert Module Audit", "", f"Audit state as of: {AUDIT_AS_OF}", "", "**Scope:** source-only multidisciplinary assay-science, bioinformatics, toolchain, full-stack and UI/UX audit. This document does not claim Linux runtime qualification.", "", "| Module | Engine | Science | Tests (source) | Required context | Claim boundary / next highest-value upgrade |", "|---|---|---:|---:|---|---|"]
for mid,row in modules_out.items():
    req=", ".join(row["required_context"]) or "—"
    if row.get("conditional_required_context"):
        conditional = "; ".join(
            f"if {','.join(f'{k}={v}' for k,v in rule['when'].items())}: {','.join(rule['required_context'])}"
            for rule in row["conditional_required_context"]
        )
        req = f"{req}; {conditional}"
    upgrade=row["upgrade_opportunities"][0] if row["upgrade_opportunities"] else "—"
    lines.append(f"| `{mid}` | `{row['engine']}` | {row['science_assessment']} | {row['test_source_count']} | {req} | {row['claim_boundary']} **Upgrade:** {upgrade} |")
lines += ["", "## Release interpretation", "", "All 21 modules have canonical profiles, runtime contracts, a page plan, source-level test evidence and a wet-lab validation boundary. `experimental` profile status is retained until Linux qualification; the audit does not convert source completeness into empirical assay validation."]
emit_text(REV / "EXPERT-MODULE-AUDIT.md", "\n".join(lines)+"\n")

# Toolchain matrix by engine/module.
engine_modules: dict[str,list[str]]={}
for mid,p in profile_by_id.items(): engine_modules.setdefault(str(p["engine"]),[]).append(mid)
engines_out={}
for eid in sorted(engine_by_id):
    bindings=[]
    for b in engine_by_id[eid]["bindings"]:
        tid=b["tool_id"]
        catalog=tool_by_id.get(tid)
        binding=dict(b)
        binding["catalog"] = {
            "display_name": catalog.get("display_name") if catalog else tid,
            "version": (catalog.get("version_policy") or {}).get("version") if catalog else "internal",
            "execution_scope": catalog.get("execution_scope") if catalog else "internal",
            "catalog_disposition": catalog.get("catalog_disposition") if catalog else "PRIMARY",
        }
        binding["runtime_evidence"] = TOOL_RUNTIME_EVIDENCE.get(tid, ["internal:pcrstudio-build"])
        binding["strict_semantics"] = (
            "required decision authority" if b["role"] == "PRIMARY" else
            "required independent evidence when bound as VALIDATOR" if b["role"] == "VALIDATOR" else
            "advisory only; may not change deterministic selection" if b["role"] == "OPTIONAL" else
            "reference only; never runtime prerequisite"
        )
        bindings.append(binding)
    engines_out[eid]={"modules":sorted(engine_modules[eid]),"bindings":bindings}

tool_matrix=with_meta({"schema_version":"1.0.0","audit_as_of":AUDIT_AS_OF,"engine_count":len(engines_out),"module_count":21,"engines":engines_out,"catalog_tools":toolchain["tools"]})
dump(REV / "MODULE-TOOLCHAIN-MATRIX.json", tool_matrix)
lines=["# PCRStudio Module × Toolchain Matrix","",f"Audit state as of: {AUDIT_AS_OF}","","| Engine | Modules | Tool | Role | Version/scope | Strict meaning |","|---|---|---|---|---|---|"]
for eid,row in engines_out.items():
    mods=", ".join(f"`{m}`" for m in row["modules"])
    for i,b in enumerate(row["bindings"]):
        cat=b["catalog"]
        lines.append(f"| `{eid}` | {mods if i==0 else '↳'} | `{b['tool_id']}` | **{b['role']}** | {cat['version']} / {cat['execution_scope']} | {b['strict_semantics']} |")
emit_text(REV / "MODULE-TOOLCHAIN-MATRIX.md", "\n".join(lines)+"\n")

# UI/UX continuity matrix.
ui_common={
    "result_overview":"web/src/components/design/result-overview.tsx",
    "toolchain_evidence":"web/src/components/design/toolchain-status.tsx",
    "validation_plan":"web/src/components/design/design-result.tsx + toolchain-status.tsx",
    "cycling_no_fabrication":"web/src/components/design/design-result.tsx",
    "page_plan":"web/src/components/design/page-plan.ts",
}
ui_modules={}
for mid,row in modules_out.items():
    ui_modules[mid]={
        "page_plan": True,
        "assay_or_engine_specific_sources": row["ui_sources"],
        "common_claim_boundary_components": ui_common,
        "validation_visible": row["validation_plan_declared"],
        "accessibility_requirement": "labelled controls + keyboard-reachable result selection; static guard plus Linux manual/automated acceptance",
        "assessment":"source-complete; Linux/browser acceptance required",
    }
ui_audit=with_meta({"schema_version":"1.0.0","audit_as_of":AUDIT_AS_OF,"module_count":21,"common_contract":ui_common,"modules":ui_modules})
dump(REV / "UI-UX-MODULE-AUDIT.json",ui_audit)
lines=["# PCRStudio UI/UX Module Audit","",f"Audit state as of: {AUDIT_AS_OF}","","The UI contract is deliberately evidence-preserving: recommendation, independent validation and wet-lab status are separate; missing cycling is rendered as unresolved rather than synthesized; rank 1 is not labelled a universal biological optimum.","","| Module | Module-specific UI source hits | Validation plan | Assessment |","|---|---:|---:|---|"]
for mid,row in ui_modules.items(): lines.append(f"| `{mid}` | {len(row['assay_or_engine_specific_sources'])} | {'yes' if row['validation_visible'] else 'NO'} | {row['assessment']} |")
emit_text(REV / "UI-UX-MODULE-AUDIT.md", "\n".join(lines)+"\n")

# Scientific risk register. Source blockers must all be closed before packaging.
risks=[
 {"id":"R-SCI-001","severity":"P0","status":"closed","area":"scientific-policy","risk":"PRIMARY backend/tool substitution can change the scientific algorithm silently.","control":"Scientific strict forbids PRIMARY substitution; Tiled PrimalScheme3 fails closed."},
 {"id":"R-SCI-002","severity":"P0","status":"closed","area":"specificity","risk":"Smoke/test databases could be mistaken for production specificity.","control":"Approved-reference scope + FASTA/index fingerprints + limited-evidence semantics."},
 {"id":"R-SCI-003","severity":"P0","status":"closed","area":"optional-tools","risk":"OPTIONAL evidence could alter deterministic selection.","control":"OPTIONAL/REFERENCE tools are advisory only; ViennaRNA accessibility removed from flanking ranking."},
 {"id":"R-SCI-004","severity":"P0","status":"closed","area":"bench-protocol","risk":"UI/backend could fabricate generic cycling or transfer one vendor recipe to another when kit/platform authority is unresolved.","control":"Missing cycling stays unresolved; Standard/qPCR/long-range/dPCR/RPA named overlays retain assay-specific bench authority while proprietary buffer thermodynamics are not reconstructed."},
 {"id":"R-SCI-005","severity":"P0","status":"closed","area":"species-specific","risk":"A single representative target, missing panel provenance or permissive severity tuning could support an overclaimed species-specific result.","control":"All executable modes require inclusivity + exclusion panels, panel provenance and selection rationale; exact panel contradictions and any complete unintended predicted product fail closed."},
 {"id":"R-SCI-006","severity":"P0","status":"closed","area":"supply-chain","risk":"Scientific Python tool identity could drift despite top-level version pins.","control":"Verified wheel hashes plus Linux-approved resolved freeze fingerprint."},
 {"id":"R-SCI-007","severity":"P1","status":"controlled-boundary","area":"pydna","risk":"pydna capabilities exceed the current adapter implementation.","control":"Current claim limited to independent PCR-product simulation; construct/digest/ligation are backlog only."},
 {"id":"R-SCI-008","severity":"P1","status":"controlled-boundary","area":"multiplex","risk":"Primer-pair multiplex engine cannot model probe channels, dPCR clusters or ARMS allele semantics.","control":"Multiplex advertised only for Standard/Colony/Species-specific until dedicated semantics exist."},
 {"id":"R-SCI-009","severity":"P1","status":"controlled-boundary","area":"RPA/KASP","risk":"Modified-probe RPA formats or KASP plus/minus branches could be approximated with the wrong oligo/topology contract.","control":"Exo/Nfo/Fpg/SIBA remain typed refusals. KASP plus/minus is now a distinct junction-aware CURRENT contract and must never fall back to ordinary diploid-SNV geometry or claim Kraken equivalence."},
 {"id":"R-REL-001","severity":"P0-release-qualification","status":"open-host-gate","area":"Linux-runtime","risk":"Source audit cannot prove executables, builds, UI rendering or 21-module runtime behavior on the supported Linux host.","control":"scripts/run-linux-qualification.py + canonical module acceptance matrix; release remains PUBLIC-SOURCE until passed."},
 {"id":"R-REL-002","severity":"P0-release-qualification","status":"open-host-gate","area":"production-database","risk":"Source bundle cannot prove the user's chosen production reference database scope/indexes exist on Linux.","control":"configure-specificity-database.py + approved-reference manifest/hash verification."},
]
risk_doc=with_meta({"schema_version":"1.0.0","audit_as_of":AUDIT_AS_OF,"source_release_blockers_open":0,"host_qualification_gates_open":2,"risks":risks})
dump(REV / "SCIENTIFIC-RISK-REGISTER.json",risk_doc)
lines=["# PCRStudio Scientific Risk Register","",f"Audit state as of: {AUDIT_AS_OF}","","**Source release blockers open: 0.** Linux runtime/database qualification remains an explicit host gate and is not converted into a source claim.","","| ID | Severity | Status | Area | Risk | Control |","|---|---|---|---|---|---|"]
for r in risks: lines.append(f"| `{r['id']}` | {r['severity']} | {r['status']} | {r['area']} | {r['risk']} | {r['control']} |")
emit_text(REV / "SCIENTIFIC-RISK-REGISTER.md", "\n".join(lines)+"\n")

# Upgrade backlog: deliberately not current capability.
items=[]
priority_map={"qpcr-probe":"P1","digital-pcr":"P1","rpa":"P1","kasp":"P1","gibson-assembly":"P1","restriction-cloning":"P1","tiled-scheme":"P1","long-range-pcr":"P1"}
for mid,row in modules_out.items():
    for idx,upgrade in enumerate(row["upgrade_opportunities"],1):
        items.append({
            "id":f"UP-{mid.upper().replace('-','_')}-{idx:02d}",
            "module":mid,
            "priority":priority_map.get(mid,"P2"),
            "status":"not-current-capability",
            "upgrade":upgrade,
            "admission_rule":"Only promote after source-backed contract, full-stack implementation, regression tests and Linux qualification; never approximate with a weaker existing engine.",
        })
backlog=with_meta({"schema_version":"1.0.0","audit_as_of":AUDIT_AS_OF,"rule":"backlog items are not current capabilities","items":items})
dump(REV / "EXPERT-UPGRADE-BACKLOG.json",backlog)
lines=["# PCRStudio Expert Upgrade Backlog","",f"Audit state as of: {AUDIT_AS_OF}","","These are **not current capabilities**. Admission requires a source-backed/versioned contract, end-to-end implementation, regression tests and Linux qualification. An existing engine may not be used as an approximation when assay semantics differ.","","| Priority | Module | Upgrade |","|---|---|---|"]
for x in sorted(items,key=lambda x:(x['priority'],x['module'],x['id'])): lines.append(f"| {x['priority']} | `{x['module']}` | {x['upgrade']} |")
emit_text(REV / "EXPERT-UPGRADE-BACKLOG.md", "\n".join(lines)+"\n")

# Numeric provenance registry: all active numeric profile constraints, hard qualification
# envelopes, and named numeric constants in decision modules. Protocol dictionaries remain
# source/overlay scoped and are not silently promoted.
profile_numeric=[]
profile_envelopes=[]
for mid,p in sorted(profile_by_id.items()):
    defaults=p.get("defaults",{})
    cp=defaults.get("constraintPolicy",{}) if isinstance(defaults.get("constraintPolicy",{}),dict) else {}
    for name,value in sorted((defaults.get("constraints") or {}).items()):
        if not isinstance(value,(int,float)) or isinstance(value,bool): continue
        policy=str(cp.get(name,"recommended"))
        if policy=="locked": category="hard-assay-invariant"
        elif name.endswith("_opt"): category="source-backed-ranking-starting-point"
        else: category="assay-envelope"
        profile_numeric.append({"module":mid,"field":name,"value":value,"policy":policy,"category":category,"source":"crates/pcr-core/profiles.toml"})
    envelope=defaults.get("constraintEnvelope") or {}
    if not isinstance(envelope,dict):
        raise TypeError(f"profile {mid} constraintEnvelope must be an object")
    for name,bounds in sorted(envelope.items()):
        if not isinstance(bounds,dict):
            raise TypeError(f"profile {mid} constraintEnvelope.{name} must be an object")
        for bound,value in sorted(bounds.items()):
            if bound not in {"min","max"}:
                raise ValueError(f"profile {mid} constraintEnvelope.{name} has unknown bound {bound!r}")
            if isinstance(value,(int,float)) and not isinstance(value,bool):
                profile_envelopes.append({
                    "module":mid,
                    "field":name,
                    "bound":bound,
                    "value":value,
                    "category":"qualification-envelope",
                    "decision_role":"hard branch qualification boundary; not a universal biological law",
                    "source":"crates/pcr-core/profiles.toml",
                })

DECISION_FILES=("pipeline.py","flanking_request.py","registries/flanking_protocols.py","multiplex.py","discriminate.py","probe.py","loop_set.py","lamp_geometry.py","lamp_profiles.py","registries/lamp.py","single.py","tiling.py","junction.py","inverse.py","mutagenic.py","nested.py","universal.py","specificity.py","design.py","tails.py")
RANKING_NAMES={"OFF_TARGET_SERIOUS","OFF_TARGET_WATCH","PENALTY_CAP","ACCESSIBILITY_WEIGHT","ACCESSIBILITY_CAP","CROSS_DIMER_WEIGHT","CROSS_DIMER_CAP","PURPOSE_WEIGHTS","THREE_PRIME_TRIPLET_FREQUENCIES","THREE_PRIME_TRIPLET_CAP","ISOTHERMAL_PRIMER3_WEIGHTS","QUALITY_WEIGHTS","END_STABILITY_SCALE","EVIDENCE_2026_F2_B2_PREFERRED","EVIDENCE_2026_OUTER_GAP_PREFERRED"}
REPORT_NAMES={"ACCESSIBILITY_DETAIL_LOG_ORDERS","UNIFORMITY_WINDOW","UNIFORMITY_LOW_GC","UNIFORMITY_HIGH_GC","CROWDED","FOLD_WORTH_MENTIONING","GAP_WORTH_MENTIONING"}
SEARCH_CAP_PREFIXES=("MOST_","MAX_","CANDIDATES_","SHORTLIST_","JUNCTION_SHORTLIST_","INNER_CANDIDATES","MEASURE_BEST","ROOM","SLIDE")
SEARCH_CAP_NAMES={"RISK_RANK_POOL_LIMIT","OUTER_CANDIDATES_PER_SIDE","OUTER_PAIRS_PER_CORE","CORE_PAIR_OUTER_EXPANSION_LIMIT","LAMP_TOPOLOGY_DIRECT_MAX_BASES","LAMP_GENERIC_DIRECT_MAX_BASES","LAMP_RAW_BACKGROUND_DIRECT_MAX_BASES","LAMP_TOPOLOGY_SITE_LIMIT_PER_ROLE","LAMP_TOPOLOGY_COMBINATION_LIMIT","LAMP_TOPOLOGY_REPORT_LIMIT"}
ASSAY_ENVELOPE_NAMES={"PROTECTIVE_BASES","NEBUILDER_STANDARD_QUANTITY_MAX_FRAGMENTS","UNBOUND_ENGINE_PROBE_TM_OFFSET_C","SECOND_MISMATCH_AT","KASP_CONSTRAINT_DEFAULTS","AT_RICH_BELOW","GC_RICH_ABOVE","AT_RICH_AT_OR_BELOW","GC_RICH_AT_OR_ABOVE","LOOP_SPAN","OUTER_GAP","AMPLICON","WINDOW_BOUNDS","GEOMETRY_BOUNDS","END_STABILITY","LOOP_END_STABILITY","END_BASES","LONGEST_RUN","HOLD","DUPLEX_BELOW_HOLD","ADAPTER_DIMER_WATCH","DEAD_ZONE","READ_LENGTH","ACCURACY","OVERLAP","MAX_POOLS","LONGEST_RUN_AT_AN_END","ASSEMBLY_CROSS_TALK_TM","FLANK","MAX_JUNCTION_OFFSET","INNER_SCREEN_MISMATCHES","STRUCTURE_BELOW_TM_MIN","MAX_PRIMER_LENGTH","DEFAULT_TEMPERATURE_C","MAX_MISMATCHES","EVIDENCE_2026_OUTER_GAP","DIGITAL_MULTIPLEX_SOFTWARE_MAX_TARGETS","QIACUITY_CHANNEL_TARGET_MAX","QPCR_MULTIPLEX_SOFTWARE_MAX_TARGETS","QPCR_MULTIPLEX_MAX_PEERS","QIACUITY_ONE_2PLEX_CHANNEL_MAX","QIACUITY_ONE_2PLEX_MULTIPLEX_MAX"}

def has_numeric(v: Any) -> bool:
    if isinstance(v,(int,float)) and not isinstance(v,bool): return True
    if isinstance(v,(list,tuple,set,frozenset)): return any(has_numeric(x) for x in v)
    if isinstance(v,dict): return any(has_numeric(k) or has_numeric(x) for k,x in v.items())
    return False

source_constants=[]
for filename in DECISION_FILES:
    path=ROOT/"tools/src/pcr_tools"/filename
    if not path.is_file(): continue
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    for node in tree.body:
        name=None; value_node=None
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name): name=node.targets[0].id;value_node=node.value
        elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name): name=node.target.id;value_node=node.value
        if not name or not name.isupper() or value_node is None: continue
        try:value=ast.literal_eval(value_node)
        except Exception: continue
        if not has_numeric(value): continue
        if name in RANKING_NAMES: category="ranking-tuning"; decision="may rank/report only; not a hard validity gate"
        elif name in REPORT_NAMES: category="diagnostic-report-threshold"; decision="reporting/advisory only"
        elif name in ASSAY_ENVELOPE_NAMES: category="assay-envelope-or-source-boundary"; decision="may constrain only where the owning assay contract explicitly declares it"
        elif name in SEARCH_CAP_NAMES or name.startswith(SEARCH_CAP_PREFIXES): category="computational-search-cap"; decision="may limit search work/completeness; cannot turn an invalid candidate valid"
        elif name in {"AGAROSE_SEPARATION","CAPILLARY_SEPARATION","CAPILLARY_HIGH_RESOLUTION","MIN_COMPLEMENTARY","QIAXCEL_REFERENCE_MAX_BP","QIAXCEL_SMALL_BAND_MAX_BP","QIAXCEL_MID_BAND_MAX_BP"}: category="readout-or-algorithm-model"; decision="model-specific; preserve provenance and do not generalize across readouts"
        else: category="implementation-numeric-constant"; decision="reviewed source constant; not automatically a wet-lab universal"
        source_constants.append({"file":f"tools/src/pcr_tools/{filename}","line":node.lineno,"name":name,"value":value,"category":category,"decision_role":decision})

decision_numeric_literals=[]
for filename in DECISION_FILES:
    path=ROOT/"tools/src/pcr_tools"/filename
    if not path.is_file():
        continue
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text, filename=str(path))
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child]=node
    for node in ast.walk(tree):
        if not (isinstance(node,ast.Constant) and isinstance(node.value,(int,float)) and not isinstance(node.value,bool)):
            continue
        parent=parents.get(node)
        ancestor=parent
        decision=False
        for _ in range(6):
            if ancestor is None:
                break
            if isinstance(ancestor,ast.Compare):
                decision=True
            if isinstance(ancestor,ast.If) and any(x is node for x in ast.walk(ancestor.test)):
                decision=True
            if isinstance(ancestor,ast.Assert):
                decision=True
            ancestor=parents.get(ancestor)
        if not decision:
            continue
        func="module"
        ancestor=parent
        while ancestor is not None:
            if isinstance(ancestor,(ast.FunctionDef,ast.AsyncFunctionDef)):
                func=ancestor.name
                break
            ancestor=parents.get(ancestor)
        value=node.value
        if value in (0,1,-1):
            category="mathematical-domain-cardinality-or-explicit-sentinel"
        elif value in (2,3):
            category="structural-cardinality-or-index-boundary"
        elif value == 100:
            category="percentage-domain-boundary"
        elif func in {"protocol", "sequencing_protocol"}:
            category="named-protocol-structure"
        else:
            category="reviewed-inline-decision-boundary"
        decision_numeric_literals.append({
            "file":f"tools/src/pcr_tools/{filename}",
            "line":node.lineno,
            "function":func,
            "value":value,
            "category":category,
            "source_segment":ast.get_source_segment(text,node),
            "decision_role":"hard decisions must remain mathematical/structural or explicitly assay/protocol-scoped; ranking tuning is separately named and may not enter hard refusal",
        })

numeric=with_meta({"schema_version":"1.2.0","audit_as_of":AUDIT_AS_OF,"scope":"all numeric active profile constraints, profile qualification envelopes, named uppercase numeric constants, and inline numeric literals used in decision comparisons in core modules","profile_numeric_constraints":profile_numeric,"profile_qualification_envelopes":profile_envelopes,"source_constants":source_constants,"decision_numeric_literals":decision_numeric_literals,"ranking_tuning_names":sorted(RANKING_NAMES),"rule":"ranking-tuning must not determine hard scientific validity; qualification-envelope numbers may gate only in their declared assay/profile and must be independently inventoried; inline decision literals are inventoried so magic gates cannot remain invisible; protocol-study evidence remains source-scoped unless a named overlay activates it"})
dump(RUN / "numeric-provenance-registry.json",numeric)
lines=["# PCRStudio Numeric Provenance Registry","",f"Audit state as of: {AUDIT_AS_OF}","",f"Active numeric profile constraints: **{len(profile_numeric)}**. Qualification-envelope bounds: **{len(profile_envelopes)}**. Named numeric constants: **{len(source_constants)}**. Inline decision/comparison numeric literals: **{len(decision_numeric_literals)}**.","","The registry separates hard/assay-envelope values from ranking tuning, diagnostics, search caps and protocol/readout models. Literature/vendor numbers in Atlas documents are not runtime defaults unless a named active profile/overlay explicitly activates them.","","## Ranking-only/tuning constants","","| Source | Constant | Category | Decision role |","|---|---|---|---|"]
for row in source_constants:
    if row["category"]=="ranking-tuning": lines.append(f"| `{row['file']}:{row['line']}` | `{row['name']}` | {row['category']} | {row['decision_role']} |")
lines += ["", "## Inline decision-literal inventory", "", "Every numeric literal that still appears directly inside a core decision comparison is inventoried in the JSON registry with file, line, function and category. Non-trivial scientific/tool bounds should be promoted to named constants when practical; structural 0/1/cardinality and percentage-domain literals remain visible here rather than being treated as hidden evidence.", "", "## Profile policy summary", "", "| Module | Numeric constraints | Locked | Bounded | Recommended |", "|---|---:|---:|---:|---:|"]
for mid in sorted(profile_by_id):
    rows=[r for r in profile_numeric if r['module']==mid]
    counts={x:sum(r['policy']==x for r in rows) for x in ('locked','bounded','recommended')}
    lines.append(f"| `{mid}` | {len(rows)} | {counts['locked']} | {counts['bounded']} | {counts['recommended']} |")
emit_text(RUN / "NUMERIC-PROVENANCE-REGISTRY.md", "\n".join(lines)+"\n")

if CHECK and DRIFT:
    print("EXPERT_ARTIFACTS=CHECK-DRIFT " + ", ".join(sorted(DRIFT)))
    raise SystemExit(1)
print(f"EXPERT_ARTIFACTS={'CHECK-PASS' if CHECK else 'GENERATED'} modules={len(modules_out)} engines={len(engines_out)} numeric_profile_rows={len(profile_numeric)} qualification_envelope_rows={len(profile_envelopes)} source_constants={len(source_constants)}")
