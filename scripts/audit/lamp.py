"""Lamp static-audit checks."""
from __future__ import annotations

from .common import *  # noqa: F403

def audit_lamp_web_contract() -> None:
    """Keep current LAMP worker evidence visible in the typed Web contract.

    The worker may legitimately add historical/diagnostic fields, but current
    ranking and specificity evidence must not be silently stripped by a Zod
    object or accidentally declared on another engine.
    """
    types = (ROOT / "web/src/lib/api/types.ts").read_text(encoding="utf-8")
    request = (ROOT / "web/src/lib/projects/request.ts").read_text(encoding="utf-8")
    view = (ROOT / "web/src/components/design/loop-set-result.tsx").read_text(encoding="utf-8")

    loop_start = types.find("export const loopSetEntrySchema = z.object({")
    loop_end = types.find("export type LoopSetEntry", loop_start)
    outward_start = types.find("export const outwardPairSchema = z.object({")
    outward_end = types.find("export type OutwardPair", outward_start)
    if min(loop_start, loop_end, outward_start, outward_end) < 0:
        error("LAMP/outward Web schema anchors disappeared")
        return
    loop = types[loop_start:loop_end]
    outward = types[outward_start:outward_end]
    for field in (
        "lamp_background_topology", "target_inclusivity", "evidence_rank",
        "sequence_interaction_risk", "terminal_gc",
    ):
        if field not in loop:
            error(f"lamp: current worker evidence field {field!r} is missing from loopSetEntrySchema")
    for field in ("lamp_background_topology", "target_inclusivity"):
        if field in outward:
            error(f"outward-pair: LAMP-only field {field!r} polluted outwardPairSchema")
    for field in ("evidence_rank", "sequence_interaction_risk", "terminal_gc"):
        if f"entry.{field}" not in view:
            error(f"lamp: typed evidence field {field!r} is retained but not surfaced in the result view")

    # Direct property use in the LAMP result view must remain representable by
    # the closed Zod object; otherwise parsing can strip evidence before render.
    loop_keys = set(re.findall(r"(?m)^\s{2}([A-Za-z_][A-Za-z0-9_]*):", loop))
    entry_refs = set(re.findall(r"\bentry\.([A-Za-z_][A-Za-z0-9_]*)", view))
    for field in sorted(entry_refs - loop_keys):
        error(f"lamp: result view reads entry.{field} but loopSetEntrySchema does not declare it")

    result_start = types.find("export const loopSetResultSchema = z.object({")
    result_end = types.find("export type LoopSetResult", result_start)
    if result_start < 0 or result_end < 0:
        error("lamp: loopSetResultSchema anchor disappeared")
    else:
        result_block = types[result_start:result_end]
        result_keys = set(re.findall(r"(?m)^\s{2}([A-Za-z_][A-Za-z0-9_]*):", result_block))
        # Shared object spreads are part of this schema too. The textual audit
        # must model them or a newly rendered shared field becomes a false
        # "missing schema" error even though Zod receives it at runtime.
        if "...carriesScan" in result_block:
            result_keys.add("background")
        if "...carriesRt" in result_block:
            result_keys.add("rt")
        result_refs = set(re.findall(r"\bresult\.([A-Za-z_][A-Za-z0-9_]*)", view))
        for field in sorted(result_refs - result_keys):
            error(f"lamp: result view reads result.{field} but loopSetResultSchema does not declare it")
    for field in ("lampGeometryProfile", "lampInnerLinker", "inclusivity", "background"):
        if field not in request:
            error(f"lamp: request builder no longer carries {field}")

    wiring = (ROOT / "web/src/lib/projects/wiring.test.ts").read_text(encoding="utf-8")
    reachable = (ROOT / "web/src/lib/projects/reachable.test.ts").read_text(encoding="utf-8")
    rust = (ROOT / "crates/pcr-core/src/engines/loop_set.rs").read_text(encoding="utf-8")
    schema_tests = (ROOT / "web/src/lib/api/result-schemas.test.ts").read_text(encoding="utf-8")
    for field in ("lampProtocol", "lampReadout", "lampGeometryProfile", "lampInnerLinker", "inclusivity"):
        if field not in wiring:
            error(f"lamp: Web wiring regression no longer covers {field}")
    for field in ("lampGeometryProfile", "lampInnerLinker"):
        if field not in reachable:
            error(f"lamp: Web reachability regression no longer covers {field}")
    for marker in (
        "advanced_lamp_fields_reach_the_worker_without_cross_engine_aliases",
        "unknown_lamp_geometry_and_linker_are_refused_before_worker_execution",
    ):
        if marker not in rust:
            error(f"lamp: Rust request regression lost marker {marker}")
    for marker in (
        "retains LAMP ranking and interaction evidence instead of stripping worker diagnostics",
        "keeps LAMP-only topology evidence out of the outward-pair schema",
    ):
        if marker not in schema_tests:
            error(f"lamp: Web result-schema regression lost marker {marker}")
    if "  outwardPairSchema," not in schema_tests:
        error("lamp: outward-pair isolation regression exists without importing outwardPairSchema")

    loop_source = (ROOT / "tools/src/pcr_tools/loop_set.py").read_text(encoding="utf-8") + "\n" + (ROOT / "tools/src/pcr_tools/lamp_geometry.py").read_text(encoding="utf-8")
    for marker in (
        '"id": "primerexplorer-v5-reference-output-compatible-sl98-tm-end-dg"',
        '"sodium_mM": 50.0',
        '"magnesium_mM": 4.0',
        '"oligo_concentration_uM": 0.1',
        '"role": "LAMP design eligibility/ranking only; not the selected kit master-mix model"',
    ):
        if marker not in loop_source:
            error(f"lamp: PrimerExplorer thermodynamic-model provenance drifted: {marker}")
    lamp_tests = (ROOT / "tools/tests/test_loop_set.py").read_text(encoding="utf-8")
    for marker in (
        "test_repeated_bounded_search_is_deterministic_for_identical_input",
        "test_evidence_geometry_does_not_replace_primerexplorer_thermodynamic_metric",
    ):
        if marker not in lamp_tests:
            error(f"lamp: reproducibility/model-boundary regression lost marker {marker}")

def audit_lamp_protocol_contract() -> None:
    """Audit the canonical LAMP authority and every generated projection."""
    authority_path = ROOT / "contracts/chemistry/lamp-protocols.json"
    try:
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error(f"lamp: canonical authority is unreadable: {exc}")
        return
    protocols = authority.get("protocols") or {}
    groups = authority.get("groups") or {}
    protocol_ids = list(groups.get("protocols") or [])
    named = [pid for pid in protocol_ids if pid != "not-selected"]
    if set(named) != set(protocols) or len(named) != len(set(named)):
        error("lamp: canonical protocol group must contain every named protocol exactly once")
    if len(named) != 72:
        error(f"lamp: reviewed catalogue must contain 72 named protocol identities, found {len(named)}")
    for pid, record in protocols.items():
        for field in ("selection", "vendor", "source_identity", "source_url", "source_reviewed_date", "supports_dna", "supports_rna", "lifecycle"):
            if field not in record or record[field] in (None, ""):
                error(f"lamp: canonical protocol {pid} lacks {field}")
        lifecycle = record.get("lifecycle")
        if not isinstance(lifecycle, dict) or not lifecycle.get("status"):
            error(f"lamp: protocol {pid} lifecycle must be a structured status object")
        if record.get("sequence_decision_impact") != "none":
            error(f"lamp: bench protocol {pid} must not silently affect sequence ranking")

    expected_json = json.dumps(authority, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    for rel in (
        "tools/src/pcr_tools/data/lamp-protocol-authority.generated.json",
        "web/src/lib/lamp-protocol-authority.generated.json",
        "knowledge/runtime/lamp-protocol-authority.generated.json",
    ):
        path = ROOT / rel
        if not path.is_file() or path.read_text(encoding="utf-8") != expected_json:
            error(f"lamp: generated authority projection drifted: {rel}")

    registry = (ROOT / "tools/src/pcr_tools/registries/lamp.py").read_text(encoding="utf-8")
    for marker in ("lamp-protocol-authority.generated.json", "LAMP_PROTOCOL_REGISTRY", "LAMP_AUTOMATIC_JUDGMENT", "LAMP_SCREENING_COHORT"):
        if marker not in registry:
            error(f"lamp: Python generated-authority loader lost {marker!r}")
    if "_scenario_protocol_record(" in registry or '"neb-e1700": {' in registry:
        error("lamp: a second hand-written protocol catalogue reappeared in Python")

    rust = (ROOT / "crates/pcr-core/src/engines/loop_set.rs").read_text(encoding="utf-8")
    rust_generated = (ROOT / "crates/pcr-core/src/engines/lamp_protocol_ids.generated.rs").read_text(encoding="utf-8")
    if 'include!("lamp_protocol_ids.generated.rs")' not in rust:
        error("lamp: Rust preflight no longer consumes generated authority")
    rust_protocols = re.search(r"const LAMP_PROTOCOLS: &\[&str\] = &\[(.*?)\];", rust_generated, re.S)
    if set(re.findall(r'"([^"]+)"', rust_protocols.group(1) if rust_protocols else "")) != set(protocol_ids):
        error("lamp: generated Rust protocol IDs drifted from canonical authority")

    ts = (ROOT / "web/src/lib/lamp-protocol-authority.generated.ts").read_text(encoding="utf-8")
    fields = (ROOT / "web/src/components/design/engine-fields/lamp-fields.tsx").read_text(encoding="utf-8")
    request_types = (ROOT / "web/src/lib/contracts/design-requests.ts").read_text(encoding="utf-8")
    if "LAMP_PROTOCOL_METADATA" not in fields or "LAMP_PROTOCOLS" not in fields or "LAMP_PROTOCOL_VENDOR_GROUPS" in fields:
        error("lamp: product picker must be generated-authority driven, not a stale hand-written catalogue")
    for type_name in ("LampProtocolId", "LampDesignIntent", "LampDesignStage", "LampMutationAnchor"):
        if type_name not in ts or type_name not in request_types:
            error(f"lamp: generated TypeScript authority lost {type_name}")

    auto = authority.get("automatic_judgment") or {}
    if auto.get("gc_rich_min_percent_inclusive") != 60:
        error("lamp: PrimerExplorer V5 GC-rich automatic judgment must be inclusive at >=60%")
    if auto.get("at_rich_max_percent_inclusive") != 45:
        error("lamp: PrimerExplorer V5 AT-rich automatic judgment must be inclusive at <=45%")
    if auto.get("normal_rule") != "greater than 45% and less than 60%":
        error("lamp: PrimerExplorer V5 Normal automatic judgment must be strictly between 45% and 60%")
    if auto.get("source_url") != "https://primerexplorer.jp/e/v5_manual/02.html":
        error("lamp: PrimerExplorer V5 automatic-judgment source identity drifted")
    algorithm = "\n".join((
        (ROOT / "tools/src/pcr_tools/loop_set.py").read_text(encoding="utf-8"),
        (ROOT / "tools/src/pcr_tools/lamp_geometry.py").read_text(encoding="utf-8"),
        (ROOT / "tools/src/pcr_tools/lamp_profiles.py").read_text(encoding="utf-8"),
    ))
    for marker in ("gc_max <= AT_RICH_AT_OR_BELOW", "gc_min >= GC_RICH_AT_OR_ABOVE", "_matches_fixed_primers", "_matches_mutation_anchor", '"screening_cohort"'):
        if marker not in algorithm:
            error(f"lamp: advanced design contract lost marker {marker!r}")
    if "circular target topology" not in algorithm or '<option value="true">Circular' in fields:
        error("lamp: Gen-1 circular LAMP must remain explicitly linear-only/fail-closed until origin-aware six-region design is versioned")

    numeric = (ROOT / "tools/src/pcr_tools/lamp_numeric_recipes.py").read_text(encoding="utf-8")
    for pid in ("hyasen-hyb413", "hyasen-hyb414", "hyasen-hyb315"):
        if f'"{pid}"' not in numeric:
            error(f"lamp: reviewed Hyasen numeric authority missing {pid}")
    if '"vazyme-rp712"' not in numeric or "exact-recipe" not in numeric:
        error("lamp: Vazyme RP712 exact numeric recipe must remain explicit unresolved/source-limited authority")
    if "thermal_stage_model" not in numeric:
        error("lamp: ordered source-backed thermal-stage model disappeared")

    result = (ROOT / "web/src/components/design/loop-set-result.tsx").read_text(encoding="utf-8")
    for marker in ("source_url", "source_revision", "source_reviewed_date", "lifecycle", "numeric_authority_status"):
        if marker not in result:
            error(f"lamp: result provenance no longer surfaces {marker}")
    for pid in ("vazyme-rp712", "hyasen-hyb413", "hyasen-hyb414", "hyasen-hyb315"):
        if pid not in authority_path.read_text(encoding="utf-8"):
            error(f"lamp: reviewed catalogue identity disappeared: {pid}")

    modified_schema = ROOT / "contracts/oligos/modified-oligo.schema.json"
    modified_python = (ROOT / "tools/src/pcr_tools/modified_oligos.py").read_text(encoding="utf-8")
    if not modified_schema.is_file() or "decision_impact" not in modified_python or "modified_oligos" not in algorithm or "modified_oligos" not in rust:
        error("lamp: shared modified-oligo manufacturing schema is incomplete across contract/Python/Rust")
    if "multiplex-modified-primer-probe" not in algorithm or "lamp_multiplex_plan" not in algorithm or "lamp_multiplex_plan" not in rust:
        error("lamp: specialized multiplex modified-primer/probe planning boundary is missing")
    if "automatic_modified_oligo_design':False" not in (ROOT / "tools/src/pcr_tools/lamp_multiplex.py").read_text(encoding="utf-8").replace(" ", ""):
        error("lamp: multiplex planning must not manufacture modified LAMP oligos")
    if "other modified-probe/lateral-flow" not in algorithm or "other modified-probe/lateral-flow" not in rust:
        error("lamp: non-multiplex modified-probe/lateral-flow execution must remain fail-closed")

    tests = (ROOT / "tools/tests/test_loop_set.py").read_text(encoding="utf-8")
    for marker in (
        "test_repeated_bounded_search_is_deterministic_for_identical_input",
        "test_meridian_mdx126_preserves_air_dryable_direct_blood_authority",
    ):
        if marker not in tests:
            error(f"lamp: existing regression lost marker {marker!r}")

def audit_lamp_evidence_ledger() -> None:
    """Make the LAMP release ledger executable evidence rather than prose.

    Implemented rules must point at an existing source symbol and at regression
    tests that are present in the LAMP-focused suite. Watchlist items are
    intentionally allowed to have neither implementation nor tests.
    """
    ledger_path = ROOT / "release/LAMP-EVIDENCE-LEDGER.json"
    if not ledger_path.is_file():
        error("missing LAMP evidence ledger")
        return
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entries = ledger.get("entries", [])
    ids = [str(item.get("id", "")) for item in entries]
    if len(ids) != len(set(ids)):
        error("LAMP evidence ledger contains duplicate evidence ids")
    if not entries:
        error("LAMP evidence ledger is empty")
        return

    test_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "tools/tests").glob("test_*.py")
    )
    for item in entries:
        evidence_id = str(item.get("id", "<missing-id>"))
        sources = item.get("sources", [])
        if not sources:
            error(f"{evidence_id}: evidence ledger entry has no source")
        for source in sources:
            url = str(source.get("url", ""))
            if not url.startswith(("https://", "http://")):
                error(f"{evidence_id}: source is missing an absolute URL")
            if not source.get("title") or not source.get("year"):
                error(f"{evidence_id}: source title/year is incomplete")

        status = str(item.get("status", ""))
        implementation = list(item.get("implementation", []))
        tests = list(item.get("tests", []))
        if status == "implemented" and (not implementation or not tests):
            error(f"{evidence_id}: implemented evidence must name source symbols and regression tests")
        for ref in implementation:
            if "::" not in ref:
                error(f"{evidence_id}: malformed implementation reference {ref!r}")
                continue
            rel, symbol = ref.split("::", 1)
            source_path = ROOT / rel
            if not source_path.is_file():
                error(f"{evidence_id}: implementation file does not exist: {rel}")
                continue
            source_text = source_path.read_text(encoding="utf-8")
            # References may be functions, constants, methods, or indexed contract
            # expressions; requiring the declared symbol text catches stale ledger
            # pointers without overfitting to one language parser.
            symbol_anchor = symbol.split("[", 1)[0].split(".", 1)[0]
            if symbol_anchor not in source_text:
                error(f"{evidence_id}: implementation symbol is stale: {ref}")
        for test_name in tests:
            if f"def {test_name}(" not in test_text:
                error(f"{evidence_id}: regression test reference is stale: {test_name}")
        if not item.get("decision_role") or not item.get("claim_boundary"):
            error(f"{evidence_id}: decision role/claim boundary is incomplete")

