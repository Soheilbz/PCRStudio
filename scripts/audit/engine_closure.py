"""Current engine contract integrity checks.

The canonical engine registry is contracts/engines.toml. These dependency-free
checks protect generated projections and deep scientific boundaries without
grouping engines by historical release counts.
"""
from __future__ import annotations

from .common import *  # noqa: F403


_ALLOWED_CAPABILITY_STATUS = {
    "executable",
    "executable-if-installed",
    "diagnostic-only",
    "evidence-only",
    "route-only",
    "reference-only",
    "fail-closed",
    "historical",
}

_AUTHORITY_FILES = {
    "consensus": "contracts/chemistry/consensus-profiles.json",
    "discriminating": "contracts/chemistry/discriminating-protocols.json",
    "assembly": "contracts/chemistry/assembly-protocols.json",
    "mutagenesis": "contracts/chemistry/mutagenesis-protocols.json",
    "nested": "contracts/chemistry/nested-protocols.json",
}

_AUTHORITY_PROJECTIONS = {
    name: (
        f"tools/src/pcr_tools/data/{name}-authority.generated.json",
        f"web/src/lib/{name}-authority.generated.json",
        f"knowledge/runtime/{name}-authority.generated.json",
    )
    for name in _AUTHORITY_FILES
}

_CORPORA = {
    "consensus-pair": "consensus-differential-corpus.json",
    "discriminating-pair": "discriminating-differential-corpus.json",
    "junction-primers": "junction-differential-corpus.json",
    "mutagenic-pair": "mutagenesis-differential-corpus.json",
    "nested": "nested-differential-corpus.json",
}

_PARITY_REL = "knowledge/runtime/engine-transport-parity.generated.json"


def _json(relative: str) -> dict:
    path = ROOT / relative  # noqa: F405
    if not path.is_file():
        error(f"missing current engine artifact: {relative}")  # noqa: F405
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))  # noqa: F405
    except Exception as exc:
        error(f"invalid JSON in {relative}: {exc}")  # noqa: F405
        return {}
    if not isinstance(payload, dict):
        error(f"current engine artifact must be an object: {relative}")  # noqa: F405
        return {}
    return payload


def _authority_ids(payload: dict) -> set[str]:
    records = payload.get("records", {})
    if isinstance(records, dict):
        return {str(key) for key, value in records.items() if isinstance(key, str) and isinstance(value, dict)}
    if isinstance(records, list):
        return {
            str(row.get("id"))
            for row in records
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        }
    return set()


def audit_engine_contract_integrity() -> None:
    """Enforce the current registry/projection/claim boundaries."""

    authorities: dict[str, dict] = {}
    all_authority_ids: set[str] = set()
    for name, canonical_rel in _AUTHORITY_FILES.items():
        canonical = _json(canonical_rel)
        authorities[name] = canonical
        ids = _authority_ids(canonical)
        if not ids:
            error(f"{canonical_rel} has no authority records")  # noqa: F405
        records = canonical.get("records", {})
        if not isinstance(records, (dict, list)) or len(ids) != len(records):
            error(f"{canonical_rel} has duplicate/missing record IDs")  # noqa: F405
        all_authority_ids.update(ids)
        for projection_rel in _AUTHORITY_PROJECTIONS[name]:
            projection = _json(projection_rel)
            if projection and projection != canonical:
                error(
                    f"current {name} authority projection drift: {projection_rel} "
                    f"!= {canonical_rel}"
                )  # noqa: F405

    assembly = authorities.get("assembly", {})
    assembly_ids = _authority_ids(assembly)
    expected_assembly_record_ids = {
        "neb-e5510",
        "neb-nebuilder-e2621",
        "neb-nebuilder-e5520",
        "neb-nebuilder-e2623",
    }
    expected_assembly_vocabulary = {"not-selected", *expected_assembly_record_ids}
    if not expected_assembly_record_ids.issubset(assembly_ids):
        error(
            "current assembly authority lacks explicit Gibson/NEBuilder protocol IDs: "
            f"{sorted(expected_assembly_record_ids - assembly_ids)}"
        )  # noqa: F405
    assembly_groups = assembly.get("groups", {})
    vocabulary = set(assembly_groups.get("protocols", [])) if isinstance(assembly_groups, dict) else set()
    if vocabulary != expected_assembly_vocabulary:
        error(
            "current assembly protocol vocabulary must keep E5510 and three "
            f"NEBuilder catalog IDs explicit: {sorted(vocabulary)}"
        )  # noqa: F405

    discriminating = authorities.get("discriminating", {})
    discriminating_groups = discriminating.get("groups", {})
    geometries = set(discriminating_groups.get("geometries", [])) if isinstance(discriminating_groups, dict) else set()
    if "arms-two-tube" not in geometries:
        error("current discriminating geometry must expose canonical arms-two-tube")  # noqa: F405
    if "two-tube" in geometries:
        error("obsolete generic two-tube geometry remains in current discriminating vocabulary")  # noqa: F405

    discriminating_records = discriminating.get("records", {})
    lgc_standard = discriminating_records.get("lgc-standard") if isinstance(discriminating_records, dict) else None
    lifecycle = lgc_standard.get("lifecycle", {}) if isinstance(lgc_standard, dict) else {}
    if (
        not isinstance(lgc_standard, dict)
        or not isinstance(lifecycle, dict)
        or lgc_standard.get("execution_status") != "historical"
        or not str(lifecycle.get("status", "")).startswith("historical")
    ):
        error("current lgc-standard must exist only as historical KASP compatibility authority")  # noqa: F405

    capabilities_rel = "knowledge/runtime/engine-capability-matrix.generated.json"
    capabilities = _json(capabilities_rel)
    projected_capabilities = (
        "tools/src/pcr_tools/data/engine-capability-matrix.generated.json",
        "web/src/lib/engine-capability-matrix.generated.json",
    )
    for projection_rel in projected_capabilities:
        projection = _json(projection_rel)
        if projection and projection != capabilities:
            error(
                f"current capability projection drift: {projection_rel} != {capabilities_rel}"
            )  # noqa: F405

    engines = capabilities.get("engines", {})
    registry_rows = tomllib.loads((ROOT / "contracts/engines.toml").read_text(encoding="utf-8"))["engine"]  # noqa: F405
    expected_engines = {str(row["id"]) for row in registry_rows}
    if set(engines) != expected_engines or len(expected_engines) != 11:
        error(
            "current engine capability matrix/registry set drift: "
            f"{sorted(set(engines) ^ expected_engines)} count={len(expected_engines)}"
        )  # noqa: F405
    for engine_id, engine_row in engines.items() if isinstance(engines, dict) else ():
        if engine_id not in _CORPORA:
            continue
        rows = engine_row.get("feature_capabilities", {}) if isinstance(engine_row, dict) else {}
        for capability_id, row in rows.items() if isinstance(rows, dict) else ():
            status = row.get("status") if isinstance(row, dict) else None
            if status not in _ALLOWED_CAPABILITY_STATUS:
                error(
                    f"{engine_id}/{capability_id}: unknown capability status {status!r}"
                )  # noqa: F405
            authority = row.get("authority") if isinstance(row, dict) else None
            if authority and authority not in all_authority_ids:
                error(
                    f"{engine_id}/{capability_id}: unresolved authority reference {authority!r}"
                )  # noqa: F405

    kasp_caps = engines.get("discriminating-pair", {}).get("feature_capabilities", {}) if isinstance(engines, dict) else {}
    if kasp_caps.get("kasp-plus-minus", {}).get("status") != "executable":
        error("current KASP plus/minus capability must be executable under its typed contract")  # noqa: F405
    if kasp_caps.get("kasp-threshold-auto-calling", {}).get("status") != "fail-closed":
        error("current KASP endpoint auto-calling must remain fail-closed")  # noqa: F405

    variant_source = (ROOT / "tools/src/pcr_tools/variants.py").read_text(encoding="utf-8")  # noqa: F405
    for token in (
        "presence-absence uses the submitted reference as the present allele",
        "Use insertion when the submitted reference is the absence allele",
    ):
        if token not in variant_source:
            error(f"current variant normalization lost canonical presence/absence boundary {token!r}")  # noqa: F405

    nested_caps = engines.get("nested", {}).get("feature_capabilities", {}) if isinstance(engines, dict) else {}
    if nested_caps.get("generic-one-tube-nested", {}).get("status") != "fail-closed":
        error("current generic one-tube Nested must remain fail-closed")  # noqa: F405

    for engine_id, corpus_file in _CORPORA.items():
        canonical_rel = f"contracts/chemistry/{corpus_file}"
        canonical = _json(canonical_rel)
        if canonical.get("engine") != engine_id:
            error(
                f"{canonical_rel}: engine must be {engine_id!r}, got {canonical.get('engine')!r}"
            )  # noqa: F405
        cases = canonical.get("cases", [])
        case_ids = [row.get("id") for row in cases if isinstance(row, dict)] if isinstance(cases, list) else []
        if not case_ids or len(case_ids) != len(set(case_ids)):
            error(f"{canonical_rel}: differential case IDs are missing or duplicated")  # noqa: F405
        metamorphic = canonical.get("metamorphic", [])
        if not isinstance(metamorphic, list) or not metamorphic:
            error(f"{canonical_rel}: metamorphic corpus is empty")  # noqa: F405
        stem = corpus_file.removesuffix(".json")
        for projection_rel in (
            f"knowledge/runtime/{stem}.generated.json",
            f"tools/src/pcr_tools/data/{stem}.generated.json",
            f"web/src/lib/{stem}.generated.json",
        ):
            projection = _json(projection_rel)
            if projection and projection != canonical:
                error(
                    f"current differential corpus projection drift: {projection_rel} != {canonical_rel}"
                )  # noqa: F405

    modules_text = (ROOT / "contracts/modules.toml").read_text(encoding="utf-8")  # noqa: F405
    required_module_tokens = (
        "consensusPolicy",
        "formulationMode",
        "panelMetadata",
        "variantType",
        "kaspAssayMode",
        "assemblyMethod",
        "assemblyProtocol",
        "mutagenesisTopology",
        "editInputMode",
        "editsJson",
        "aaCdsStart",
        "aaResidue",
        "aaTo",
        "codonPolicy",
        "codonUsage",
        "libraryMode",
        "libraryAt",
        "libraryCodon",
        "transferMode",
        "cleanupProtocol",
        "round1ThermalProgram",
        "round2ThermalProgram",
    )
    for token in required_module_tokens:
        if token not in modules_text:
            error(f"current modules.toml does not own required engine field {token!r}")  # noqa: F405
    for stale in ("multiEdits", "aminoAcidResidue", "userSelectedCodon"):
        if stale in modules_text:
            error(f"current modules.toml retains obsolete mutagenesis field {stale!r}")  # noqa: F405
    for branch_value in ('"edit_input_mode" = "dna"', '"edit_input_mode" = "multi"', '"edit_input_mode" = "amino-acid"', '"edit_input_mode" = "library"'):
        if branch_value not in modules_text:
            error(f"current mutagenesis required-context contract is missing branch {branch_value}")  # noqa: F405

    integration = _json("knowledge/runtime/linux-integration-scenarios.json")
    integration_ids = {
        str(row.get("id"))
        for row in integration.get("scenarios", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    for scenario_id in (
        "consensus-panel-formulation-boundary",
        "kasp-plus-minus-endpoint-boundary",
        "junction-gibson-nebuilder-separation",
        "mutagenic-topology-input-separation",
        "nested-two-round-transfer-causality",
    ):
        if scenario_id not in integration_ids:
            error(f"current Linux integration matrix is missing engine scenario {scenario_id!r}")  # noqa: F405

    acceptance_matrix = _json("knowledge/runtime/linux-acceptance-matrix.json")
    acceptance_template = _json("knowledge/runtime/linux-acceptance-results.template.json")
    expected_modules = set((acceptance_matrix.get("modules") or {}).keys())
    template_modules = set((acceptance_template.get("modules") or {}).keys())
    if expected_modules != template_modules:
        error(
            "current Linux acceptance-results template module set drift: "
            f"missing={sorted(expected_modules - template_modules)} "
            f"extra={sorted(template_modules - expected_modules)}"
        )  # noqa: F405
    template_scenarios = set((acceptance_template.get("integration_scenarios") or {}).keys())
    if integration_ids != template_scenarios:
        error(
            "current Linux acceptance-results template integration-scenario set drift: "
            f"missing={sorted(integration_ids - template_scenarios)} "
            f"extra={sorted(template_scenarios - integration_ids)}"
        )  # noqa: F405

    evidence_text = (ROOT / "tools/src/pcr_tools/workflow_evidence.py").read_text(encoding="utf-8")  # noqa: F405
    for token in ('"decision_impact": "none"', "MAX_WORKFLOW_EVIDENCE_FIELDS", "MAX_WORKFLOW_EVIDENCE_TEXT_CHARS"):
        if token not in evidence_text:
            error(f"current workflow evidence boundary is missing {token!r}")  # noqa: F405

    endpoint_text = (ROOT / "web/src/lib/kasp-endpoint.ts").read_text(encoding="utf-8")  # noqa: F405
    for token in ("FAM", "HEX", "provider", "software"):
        if token not in endpoint_text:
            error(f"current KASP endpoint evidence parser is missing {token!r}")  # noqa: F405
    for forbidden in ("autoCall", "autocall", "auto_call", "universalThreshold"):
        if forbidden in endpoint_text:
            error(f"current KASP endpoint parser regained hidden calling logic: {forbidden!r}")  # noqa: F405

    active_source = {
        "junction.py": (ROOT / "tools/src/pcr_tools/junction.py").read_text(encoding="utf-8"),  # noqa: F405
        "discriminate.py": (ROOT / "tools/src/pcr_tools/discriminate.py").read_text(encoding="utf-8"),  # noqa: F405
        "mutagenic.py": (ROOT / "tools/src/pcr_tools/mutagenic.py").read_text(encoding="utf-8"),  # noqa: F405
        "nested.py": (ROOT / "tools/src/pcr_tools/nested.py").read_text(encoding="utf-8"),  # noqa: F405
    }
    if "neb-nebuilder-hifi-current" in active_source["junction.py"]:
        error("Junction runtime references obsolete non-canonical NEBuilder authority ID")  # noqa: F405
    for token in ("neb-nebuilder-e2621", "neb-nebuilder-e5520", "neb-nebuilder-e2623"):
        if token not in active_source["junction.py"]:
            error(f"Junction runtime is missing explicit NEBuilder protocol {token}")  # noqa: F405
    if "arms-two-tube" not in active_source["discriminate.py"]:
        error("Discriminating runtime lost canonical arms-two-tube geometry")  # noqa: F405
    if "100" not in active_source["mutagenic.py"] and "Q5_MAX_SPLIT_INSERTION" not in active_source["mutagenic.py"]:
        error("Mutagenic runtime lost source-backed Q5 split-insertion boundary")  # noqa: F405
    for token in ("msz-exonuclease-i", "thermolabile-exonuclease-i", "nested_false_product_graph"):
        if token not in active_source["nested.py"]:
            error(f"Nested runtime lost current transfer/specificity contract {token!r}")  # noqa: F405

    boundaries = (ROOT / "knowledge/runtime/GEN1-INTENTIONAL-BOUNDARIES.md").read_text(encoding="utf-8")  # noqa: F405
    if "Plus/minus presence-absence mode is a typed refusal" in boundaries:
        error("intentional-boundaries document regressed to pre-current KASP plus/minus refusal")  # noqa: F405
    for token in (
        "junction-aware `plus-minus`",
        "User weights are not population prevalence",
        "Gibson E5510 and NEBuilder HiFi are separate",
        "QuikChange Lightning single-site",
        "Generic one-tube Nested remains fail-closed",
    ):
        if token not in boundaries:
            error(f"current intentional-boundaries document is missing {token!r}")  # noqa: F405

    parity = _json(_PARITY_REL)
    for projection_rel in (
        "tools/src/pcr_tools/data/engine-transport-parity.generated.json",
        "web/src/lib/engine-transport-parity.generated.json",
    ):
        projection = _json(projection_rel)
        if projection and projection != parity:
            error(f"current transport parity projection drift: {projection_rel} != {_PARITY_REL}")  # noqa: F405
    parity_engines = parity.get("engines", {})
    if set(parity_engines) != expected_engines:
        error(
            "current engine transport parity/registry set drift: "
            f"{sorted(set(parity_engines) ^ expected_engines)}"
        )  # noqa: F405
    rust_sources = {
        "consensus-pair": (ROOT / "crates/pcr-core/src/engines/consensus_pair.rs").read_text(encoding="utf-8"),
        "discriminating-pair": (ROOT / "crates/pcr-core/src/engines/discriminating_pair.rs").read_text(encoding="utf-8"),
        "junction-primers": (ROOT / "crates/pcr-core/src/engines/junction_primers.rs").read_text(encoding="utf-8"),
        "mutagenic-pair": (ROOT / "crates/pcr-core/src/engines/mutagenic_pair.rs").read_text(encoding="utf-8"),
        "nested": (ROOT / "crates/pcr-core/src/engines/nested.rs").read_text(encoding="utf-8"),
    }
    python_sources = {
        "consensus-pair": (ROOT / "tools/src/pcr_tools/__main__.py").read_text(encoding="utf-8") + (ROOT / "tools/src/pcr_tools/universal.py").read_text(encoding="utf-8"),
        "discriminating-pair": (ROOT / "tools/src/pcr_tools/discriminate.py").read_text(encoding="utf-8"),
        "junction-primers": (ROOT / "tools/src/pcr_tools/junction.py").read_text(encoding="utf-8"),
        "mutagenic-pair": (ROOT / "tools/src/pcr_tools/mutagenic.py").read_text(encoding="utf-8"),
        "nested": (ROOT / "tools/src/pcr_tools/nested.py").read_text(encoding="utf-8"),
    }
    web_contract = (ROOT / "web/src/lib/contracts/design-requests.ts").read_text(encoding="utf-8")  # noqa: F405
    web_request = (ROOT / "web/src/lib/projects/request.ts").read_text(encoding="utf-8")  # noqa: F405
    for engine_id, engine_row in parity_engines.items() if isinstance(parity_engines, dict) else ():
        if engine_id not in rust_sources or engine_id not in python_sources:
            continue
        rows = engine_row.get("fields", []) if isinstance(engine_row, dict) else []
        if not isinstance(rows, list) or not rows:
            error(f"{_PARITY_REL}: {engine_id} has no field rows")  # noqa: F405
            continue
        seen_web: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                error(f"{_PARITY_REL}: {engine_id} contains a non-object field row")  # noqa: F405
                continue
            web = str(row.get("web", ""))
            rust = str(row.get("rust", ""))
            python_key = str(row.get("python", ""))
            if not web or not rust or not python_key:
                error(f"{_PARITY_REL}: {engine_id} field row lacks web/rust/python name")  # noqa: F405
                continue
            if web in seen_web:
                error(f"{_PARITY_REL}: {engine_id} duplicates public field {web!r}")  # noqa: F405
            seen_web.add(web)
            if web not in web_contract and web not in web_request:
                error(f"current transport parity public field missing from Web source: {engine_id}/{web}")  # noqa: F405
            if rust not in rust_sources.get(engine_id, ""):
                error(f"current transport parity Rust field missing: {engine_id}/{rust}")  # noqa: F405
            if python_key not in python_sources.get(engine_id, ""):
                error(f"current transport parity Python key missing: {engine_id}/{python_key}")  # noqa: F405

    # current KASP/mismatch authority must be scientifically scoped, not a hidden
    # universal discrimination rule. The selected profile identity is carried
    # end-to-end and the two KASP geometries own disjoint variant classes.
    discriminating = authorities.get("discriminating", {})
    mismatch_model = discriminating.get("mismatch_model", {}) if isinstance(discriminating, dict) else {}
    canonical_mismatch_id = str(mismatch_model.get("model_id") or "") if isinstance(mismatch_model, dict) else ""
    if canonical_mismatch_id != "pcrstudio-gen1-taq-terminal-mismatch-evidence-2026":
        error("current discriminating mismatch evidence model ID drifted from the reviewed canonical snapshot")  # noqa: F405
    if "non-proofreading" not in str(mismatch_model.get("polymerase_scope") or ""):
        error("current mismatch evidence model lost its Taq-like non-proofreading polymerase scope")  # noqa: F405
    if "never a universal" not in str(mismatch_model.get("claim_boundary") or ""):
        error("current mismatch evidence model lost its non-universal claim boundary")  # noqa: F405

    discriminating_caps = capabilities.get("engines", {}).get("discriminating-pair", {}).get("feature_capabilities", {}) if isinstance(capabilities, dict) else {}
    biallelic = discriminating_caps.get("kasp-biallelic-genotype", {}) if isinstance(discriminating_caps, dict) else {}
    plus_minus = discriminating_caps.get("kasp-plus-minus", {}) if isinstance(discriminating_caps, dict) else {}
    hidden_call = discriminating_caps.get("kasp-threshold-auto-calling", {}) if isinstance(discriminating_caps, dict) else {}
    if biallelic.get("status") != "executable" or set(biallelic.get("scope", [])) != {"snv", "mnv"}:
        error("current KASP biallelic capability must be executable only for SNV/MNV")  # noqa: F405
    if plus_minus.get("status") != "executable" or set(plus_minus.get("scope", [])) != {"insertion", "deletion", "complex-replacement", "presence-absence"}:
        error("current KASP plus/minus capability scope drifted from indel/complex/presence-absence")  # noqa: F405
    if hidden_call.get("status") != "fail-closed":
        error("current KASP universal threshold/hidden auto-calling must remain fail-closed")  # noqa: F405

    discrim_corpus = _json("contracts/chemistry/discriminating-differential-corpus.json")
    discrim_case_ids = {
        str(row.get("id"))
        for row in discrim_corpus.get("cases", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    for required_case in ("kasp-biallelic-indel-refusal", "kasp-plus-minus-presence-absence"):
        if required_case not in discrim_case_ids:
            error(f"current discriminating corpus lost required KASP boundary fixture {required_case!r}")  # noqa: F405

    ui_fields = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in ("web/src/components/design/engine-fields.tsx", "web/src/components/design/engine-fields/advanced-fields.tsx"))  # noqa: F405
    ui_fields_normalized = " ".join(ui_fields.split())
    for token in (
        'value="biallelic-genotype" disabled={variantType !== "snv" && variantType !== "mnv"}',
        'value="plus-minus-presence-absence" disabled={variantType === "snv" || variantType === "mnv"}',
        'pcrstudio-gen1-taq-terminal-mismatch-evidence-2026',
    ):
        if token not in ui_fields_normalized:
            error(f"current KASP UI lost required mode/evidence boundary token {token!r}")  # noqa: F405

    # Mutagenic completion must be input-mode aware. DNA-edit fields cannot be
    # globally required for multi-edit, amino-acid or library workflows.
    for token in (
        'required_context = ["mutagenesis_topology", "post_amplification_protocol", "edit_input_mode"]',
        '"edit_input_mode" = "dna"',
        '"edit_input_mode" = "multi"',
        '"edit_input_mode" = "amino-acid"',
        '"edit_input_mode" = "library"',
    ):
        if token not in modules_text:
            error(f"current Mutagenic input-mode completion contract is missing {token!r}")  # noqa: F405
