"""Dependency-light current engine authority/capability/differential contract tests.

These tests intentionally avoid importing the scientific engines. Native Primer3,
ViennaRNA, Rust and browser execution are separate Linux qualification gates.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_engine_authority_json_projections_are_exact_canonical_copies():
    specs = {
        "consensus": "contracts/chemistry/consensus-profiles.json",
        "discriminating": "contracts/chemistry/discriminating-protocols.json",
        "assembly": "contracts/chemistry/assembly-protocols.json",
        "mutagenesis": "contracts/chemistry/mutagenesis-protocols.json",
        "nested": "contracts/chemistry/nested-protocols.json",
    }
    for name, canonical_rel in specs.items():
        canonical = load(canonical_rel)
        for projection in (
            f"tools/src/pcr_tools/data/{name}-authority.generated.json",
            f"web/src/lib/{name}-authority.generated.json",
            f"knowledge/runtime/{name}-authority.generated.json",
        ):
            assert load(projection) == canonical, projection


def test_capability_matrix_statuses_and_authority_references_are_closed():
    matrix = load("knowledge/runtime/engine-capability-matrix.generated.json")
    statuses = set(matrix["status_vocabulary"])
    authority_files = {
        "consensus-pair": "contracts/chemistry/consensus-profiles.json",
        "discriminating-pair": "contracts/chemistry/discriminating-protocols.json",
        "junction-primers": "contracts/chemistry/assembly-protocols.json",
        "mutagenic-pair": "contracts/chemistry/mutagenesis-protocols.json",
        "nested": "contracts/chemistry/nested-protocols.json",
    }
    for engine, rel in authority_files.items():
        records = load(rel)["records"]
        for capability, spec in matrix["engines"][engine]["feature_capabilities"].items():
            assert spec["status"] in statuses, (engine, capability, spec["status"])
            if "authority" in spec:
                assert spec["authority"] in records, (engine, capability, spec["authority"])


def test_differential_corpora_have_unique_cases_and_metamorphic_contracts():
    expected = {
        "consensus": "consensus-pair",
        "discriminating": "discriminating-pair",
        "junction": "junction-primers",
        "mutagenesis": "mutagenic-pair",
        "nested": "nested",
    }
    for name, engine in expected.items():
        corpus = load(f"contracts/chemistry/{name}-differential-corpus.json")
        assert corpus["engine"] == engine
        ids = [row["id"] for row in corpus["cases"]]
        assert len(ids) == len(set(ids)) and ids
        assert corpus["metamorphic"]
        for projection in (
            f"tools/src/pcr_tools/data/{name}-differential-corpus.generated.json",
            f"web/src/lib/{name}-differential-corpus.generated.json",
            f"knowledge/runtime/{name}-differential-corpus.generated.json",
        ):
            assert load(projection) == corpus, projection


def test_workflow_evidence_is_flat_bounded_and_never_changes_design_ranking():
    path = ROOT / "tools/src/pcr_tools/workflow_evidence.py"
    spec = importlib.util.spec_from_file_location("workflow_evidence_standalone", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.evidence_block({"ntc": "clear", "replicates": 3, "verified": True})
    assert result["decision_impact"] == "none"
    assert result["observed"]["replicates"] == 3
    with pytest.raises(module.WorkflowEvidenceError):
        module.evidence_block({"nested": {"not": "flat"}})


def test_source_vocabularies_match_corrected_canonical_ids_without_importing_engines():
    junction = (ROOT / "tools/src/pcr_tools/junction.py").read_text(encoding="utf-8")
    rust_junction = (ROOT / "crates/pcr-core/src/engines/junction_primers.rs").read_text(encoding="utf-8")
    assembly = load("contracts/chemistry/assembly-protocols.json")
    protocols = set(assembly["groups"]["protocols"])
    for protocol in protocols - {"not-selected"}:
        assert protocol in junction
        assert protocol in rust_junction
    assert "neb-nebuilder-hifi-current" not in junction
    assert "existing-linear-fragment" not in assembly["groups"]["fragment_kinds"]

    discriminating = load("contracts/chemistry/discriminating-protocols.json")
    py = (ROOT / "tools/src/pcr_tools/discriminate.py").read_text(encoding="utf-8")
    rust = (ROOT / "crates/pcr-core/src/engines/discriminating_pair.rs").read_text(encoding="utf-8")
    assert "arms-two-tube" in discriminating["groups"]["geometries"]
    assert '"two-tube"' not in json.dumps(discriminating["groups"]["geometries"])
    assert "arms-two-tube" in py and "arms-two-tube" in rust


def test_modules_toml_owns_engine_fields_instead_of_leaving_ui_only_state():
    modules = (ROOT / "contracts/modules.toml").read_text(encoding="utf-8")
    required_tokens = [
        "consensusPolicy", "panelMetadata", "formulationMode", "alternativeAlignment",
        "variantType", "nearbyVariantsVcf", "kaspProtocol", "kaspEndpointDataReference",
        "assemblyMethod", "assemblySequenceVerification",
        "mutagenesisTopology", "editInputMode", "editsJson", "aaCdsStart", "aaResidue",
        "aaTo", "codonPolicy", "codonUsage", "libraryMode", "libraryAt", "libraryCodon",
        "transferMode", "cleanupProtocol", "round1ThermalProgram", "round2ThermalProgram",
        "nestedRound1Ntc", "nestedRound2Ntc",
    ]
    missing = [token for token in required_tokens if token not in modules]
    assert not missing, f"current engine field ownership missing: {missing}"


def test_no_legacy_plus_minus_refusal_survives_in_current_expert_source():
    source = (ROOT / "scripts/generate-expert-audit-artifacts.py").read_text(encoding="utf-8")
    kasp_row = next(line for line in source.splitlines() if line.lstrip().startswith('"kasp":'))
    assert "strong-endpoint-plus-minus" in kasp_row
    assert "distinct junction-aware plus/minus branch" in kasp_row
    assert not re.search(r"plus/minus[^.\n]{0,180}(typed refus|typed-refus|refus)", kasp_row, flags=re.I), (
        "expert audit generator still describes implemented KASP plus/minus as refused"
    )

def test_discriminating_mismatch_identity_and_kasp_mode_boundaries_are_canonical():
    authority = load("contracts/chemistry/discriminating-protocols.json")
    model_id = authority["mismatch_model"]["model_id"]
    assert model_id == "pcrstudio-gen1-taq-terminal-mismatch-evidence-2026"
    rust = (ROOT / "crates/pcr-core/src/engines/discriminating_authority.generated.rs").read_text(encoding="utf-8")
    web = (ROOT / "web/src/lib/engine-authorities.generated.ts").read_text(encoding="utf-8")
    assert f'DISCRIMINATING_MISMATCH_MODEL_ID: &str = "{model_id}"' in rust
    assert f'DISCRIMINATING_MISMATCH_MODEL_ID = "{model_id}"' in web

    matrix = load("knowledge/runtime/engine-capability-matrix.generated.json")
    caps = matrix["engines"]["discriminating-pair"]["feature_capabilities"]
    assert set(caps["kasp-biallelic-genotype"]["scope"]) == {"snv", "mnv"}
    assert set(caps["kasp-plus-minus"]["scope"]) == {
        "insertion", "deletion", "complex-replacement", "presence-absence"
    }

    corpus = load("contracts/chemistry/discriminating-differential-corpus.json")
    cases = {row["id"]: row for row in corpus["cases"]}
    assert cases["kasp-biallelic-indel-refusal"]["expected"]["status"] == "refused"
    pa = cases["kasp-plus-minus-presence-absence"]
    assert pa["request"]["kasp_assay_mode"] == "plus-minus-presence-absence"
    assert pa["request"]["variant"] == {"type": "presence-absence", "at": 10, "ref": "ACGT", "alt": ""}
    assert pa["expected"]["variant_shape"] == "reference-present/alternate-absent"

