"""Foundation static-audit checks."""
from __future__ import annotations

from .common import *  # noqa: F403

def audit_generated_runtime_artifacts() -> None:
    """Derived JSON must be a faithful, current projection of canonical source."""
    modules, contracts, _bindings = parse_runtime_contract()
    profiles = profile_map()
    profile_path = ROOT / "crates/pcr-core/profiles.toml"
    expected_profile_source = "crates/pcr-core/profiles.toml"
    expected_profile_sha = sha256(profile_path)

    bindings_path = ROOT / "knowledge/runtime/profile-bindings.generated.json"
    trace_path = ROOT / "knowledge/runtime/module-rule-trace.generated.json"
    web_required_path = ROOT / "web/src/lib/projects/required-context.generated.json"
    acceptance_path = ROOT / "knowledge/runtime/linux-acceptance-matrix.json"
    if not bindings_path.is_file() or not trace_path.is_file() or not web_required_path.is_file():
        error("generated runtime artifacts are missing")
        return

    generated = json.loads(bindings_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    web_required = json.loads(web_required_path.read_text(encoding="utf-8"))
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8")).get("modules", {})

    if generated.get("source") != expected_profile_source:
        error(f"profile-bindings source path is stale: {generated.get('source')!r}")
    if generated.get("source_sha256") != expected_profile_sha:
        error("profile-bindings source_sha256 does not match current profiles.toml")
    if set(generated.get("profiles", {})) != set(modules):
        error("profile-bindings module ids do not match runtime contract")
    if set(web_required.get("modules", {})) != set(modules):
        error("Web required-context module ids do not match runtime contract")

    for module_id, engine in modules.items():
        profile = profiles[module_id]
        expected_binding = {
            "name": profile["name"],
            "engine": profile["engine"],
            "goal": profile["goal"],
            "status": profile["status"],
            "modifiers": profile.get("modifiers", []),
            "enzyme": profile.get("enzyme", []),
            "requires": profile.get("requires", []),
            "defaults": profile.get("defaults", {}),
        }
        if generated.get("profiles", {}).get(module_id) != expected_binding:
            error(f"{module_id}: generated profile binding drifted from profiles.toml")

        module_generated = json.loads(
            (ROOT / "knowledge/runtime/module-contracts.generated.json").read_text(encoding="utf-8")
        )["modules"][module_id]
        expected_web_required = {
            "required_context": list(contracts[module_id].get("required_context", ())),
            "conditional_required_context": [
                {
                    "when": dict(rule.get("when", {})),
                    "required_context": list(rule.get("required_context", ())),
                }
                for rule in contracts[module_id].get("conditional_required_context", ())
            ],
            "wire_required_context": list(contracts[module_id].get("wire_required_context", ())),
            "wire_conditional_required_context": [
                {
                    "when": dict(rule.get("when", {})),
                    "required_context": list(rule.get("required_context", ())),
                }
                for rule in contracts[module_id].get("wire_conditional_required_context", ())
            ],
            "wire_required_any_of": [list(group) for group in contracts[module_id].get("wire_required_any_of", ())],
            "field_owners": dict(module_generated.get("field_owners", {})),
        }
        if web_required.get("modules", {}).get(module_id) != expected_web_required:
            error(f"{module_id}: generated Web required-context drifted from runtime contract")

        row = trace.get("modules", {}).get(module_id)
        if not isinstance(row, dict):
            error(f"{module_id}: missing module-rule-trace row")
            continue
        if row.get("profile_source") != expected_profile_source:
            error(f"{module_id}: module trace profile_source is stale")
        if row.get("profile_sha256") != expected_profile_sha:
            error(f"{module_id}: module trace profile_sha256 is stale")
        if row.get("active_profile") != profile:
            error(f"{module_id}: module trace active_profile drifted from profiles.toml")
        if row.get("linux_acceptance") != acceptance.get(module_id):
            error(f"{module_id}: module trace Linux acceptance drifted from canonical matrix")

        rc = contracts[module_id]
        acceptance_row = acceptance.get(module_id, {})
        if acceptance_row.get("engine") != engine:
            error(f"{module_id}: Linux acceptance engine drifted from runtime mapping")
        if acceptance_row.get("active_gates") != list(rc.get("gates", ())):
            error(f"{module_id}: Linux acceptance gates drifted from runtime contract")
        if acceptance_row.get("fallback_policy") != rc.get("fallback"):
            error(f"{module_id}: Linux acceptance fallback drifted from runtime contract")
        def camel_path(path: str) -> str:
            out = []
            for segment in str(path).split("."):
                parts = segment.split("_")
                out.append(parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:]))
            return ".".join(out)

        required_ui_context = set(acceptance_row.get("required_user_context", []))
        for required in rc.get("required_context", ()):
            camel = camel_path(str(required))
            if camel not in required_ui_context:
                error(f"{module_id}: Linux acceptance omits required context {camel!r}")

        expected_conditional_ui = [
            {
                "when": {camel_path(path): value for path, value in rule.get("when", {}).items()},
                "required_user_context": [camel_path(path) for path in rule.get("required_context", ())],
            }
            for rule in rc.get("conditional_required_context", ())
        ]
        if acceptance_row.get("conditional_required_user_context", []) != expected_conditional_ui:
            error(f"{module_id}: Linux acceptance conditional required context drifted from runtime contract")

        expected_runtime = {
            "gates": list(rc.get("gates", ())),
            "fallback": rc.get("fallback"),
            "required_context": list(rc.get("required_context", ())),
            "wire_required_context": list(rc.get("wire_required_context", ())),
            "wire_required_any_of": [list(group) for group in rc.get("wire_required_any_of", ())],
            "engine": engine,
            "command": {
                "flanking-pair": "run", "consensus-pair": "universal", "nested": "nested",
                "outward-pair": "inverse", "pair-and-probe": "probe", "single-primer": "single",
                "mutagenic-pair": "mutagenic", "tiling-scheme": "tiling",
                "junction-primers": "junction", "discriminating-pair": "discriminate",
                "loop-set": "loop_set",
            }[engine],
        }
        conditional = rc.get("conditional_required_context", ())
        if conditional:
            expected_runtime["conditional_required_context"] = [
                {"when": dict(rule.get("when", {})), "required_context": list(rule.get("required_context", ()))}
                for rule in conditional
            ]
        wire_conditional = rc.get("wire_conditional_required_context", ())
        if wire_conditional:
            expected_runtime["wire_conditional_required_context"] = [
                {"when": dict(rule.get("when", {})), "required_context": list(rule.get("required_context", ()))}
                for rule in wire_conditional
            ]
        if row.get("runtime_contract") != expected_runtime:
            error(f"{module_id}: module trace runtime contract drifted from Python contract")

        atlas_rel = row.get("atlas_document")
        atlas = ROOT / str(atlas_rel)
        if not atlas.is_file():
            error(f"{module_id}: module trace Atlas document does not exist: {atlas_rel}")
        elif row.get("atlas_sha256") != sha256(atlas):
            error(f"{module_id}: module trace Atlas SHA-256 is stale")

    if set(trace.get("modules", {})) != set(modules):
        error("module-rule-trace module ids do not match runtime contract")

    # Old hand-edited path is a reliable signature of a stale pre-generator artifact.
    for rel in (
        "knowledge/runtime/profile-bindings.generated.json",
        "knowledge/runtime/module-rule-trace.generated.json",
        "knowledge/reviews/MODULE-IMPLEMENTATION-COVERAGE.md",
    ):
        path = ROOT / rel
        if path.is_file() and "rust-core/profiles.toml" in path.read_text(encoding="utf-8"):
            error(f"stale historical profile path remains in {rel}")

def audit_current_surface_hygiene() -> None:
    """Keep the active tree current-only; Git history is the archive."""
    forbidden_exact = {
        "COLD-AUDIT-SNAPSHOT-STATUS-2026-08-31.md",
        "SNAPSHOT-FILE-MANIFEST.json",
        "SNAPSHOT-SHA256SUMS.txt",
        "knowledge/reviews/HISTORICAL-WORKING-SNAPSHOT-STATUS-2026-08-31.md",
        "knowledge/atlas/provenance/research-history-2026-08.json",
        "knowledge/atlas/provenance/pre-refactor-markdown-history-2026-08-30.zip",
    }
    for rel in sorted(forbidden_exact):
        if (ROOT / rel).exists():
            error(f"obsolete/historical artifact remains in current tree: {rel}")

    dated_current_patterns = (
        "knowledge/reviews/EXPERT-MODULE-AUDIT-20",
        "knowledge/reviews/MODULE-TOOLCHAIN-MATRIX-20",
        "knowledge/reviews/UI-UX-MODULE-AUDIT-20",
        "knowledge/reviews/SCIENTIFIC-RISK-REGISTER-20",
        "knowledge/reviews/EXPERT-UPGRADE-BACKLOG-20",
        "knowledge/runtime/numeric-provenance-registry-20",
        "knowledge/runtime/NUMERIC-PROVENANCE-REGISTRY-20",
    )
    if (ROOT / "web/src/lib/api/__fixtures__/qpcr-probe.json").exists():
        error("successful historical qPCR-probe fixture escaped migration quarantine into current runtime fixtures")
    historical_probe = ROOT / "web/src/lib/api/__fixtures__/historical/qpcr-probe__unbound-pre-chemistry.json"
    if not historical_probe.is_file():
        error("missing quarantined saved-result fixture for pre-chemistry qPCR-probe migration compatibility")

    if (ROOT / "web/src/lib/api/__fixtures__/lamp.json").exists():
        error("historical pre-contract LAMP fixture escaped migration quarantine into current runtime fixtures")
    historical_lamp = ROOT / "web/src/lib/api/__fixtures__/historical/lamp__pre-diagnostic-temperature-contract.json"
    if not historical_lamp.is_file():
        error("missing quarantined saved-result fixture for historical LAMP migration compatibility")

    for path in ROOT.rglob("*"):
        if not path.is_file() or is_generated(path):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(rel.startswith(prefix) for prefix in dated_current_patterns):
            error(f"dated duplicate of a stable current artifact remains: {rel}")

def audit_uncompiled_duplicate_sources() -> None:
    """Refuse Rust source lookalikes that Cargo does not compile."""
    crate = ROOT / "crates/pcr-server"
    for name in ("bench.rs", "lib.rs", "routes.rs", "sequences.rs"):
        shadow = crate / name
        if shadow.is_file():
            error(
                f"uncompiled duplicate Rust source remains outside pcr-server/src: {shadow.relative_to(ROOT)}"
            )

def audit_regression_guards() -> None:
    """Make high-risk cross-layer fixes hard to accidentally unwind."""
    routes_text = (ROOT / "crates/pcr-server/src/routes.rs").read_text(encoding="utf-8")
    orchestrator_text = (ROOT / "tools/src/pcr_tools/orchestrator.py").read_text(encoding="utf-8")
    multiplex_worker_text = (ROOT / "tools/src/pcr_tools/multiplex.py").read_text(encoding="utf-8")
    multiplex_ui_text = (ROOT / "web/src/components/design/multiplex-form.tsx").read_text(encoding="utf-8")
    multiplex_server_text = (ROOT / "crates/pcr-server/src/bench.rs").read_text(encoding="utf-8")
    for needle, text, label in (
        ("server-injected-canonical-profile", routes_text, "server assay payload"),
        ("require_profile_authority=True", orchestrator_text, "orchestrator"),
        ("require_profile_authority=True", multiplex_worker_text, "multiplex target worker"),
        ("colonyProtocolName", multiplex_ui_text, "multiplex Colony UI"),
        ("take_colony_multiplex_context", multiplex_server_text, "multiplex Colony server"),
    ):
        if needle not in text:
            error(f"high-risk regression guard missing from {label}: {needle!r}")
    required_tests = {
        "tools/tests/test_primalscheme_adapter.py": (
            "scheme-create", "panel-create", "repair-mode", "scheme-replace", "--output"
        ),
        "tools/tests/test_multiplex_orchestration.py": (
            "panel_validation_scope", "final-selected-oligos-grouped-by-tube", "strict"
        ),
        "tools/tests/test_tool_runtime_database_contract.py": (
            "index_artifacts_match", "blast_prefix", "manifest_contract_consistent"
        ),
        "tools/tests/test_optional_validator_semantics.py": (
            "primerpooler", "_required_validators", "tiling-scheme"
        ),
        "tools/tests/test_pipeline.py": (
            "test_digital_pcr_requires_platform_partition_and_fragmentation_context",
            "test_qx200_overlay_refuses_non_droplet_partition",
            "digital_context",
        ),
        "tools/tests/test_single.py": (
            "test_race_requires_substrate_preparation_round_and_explicit_adapter",
            "candidate-transcript-end",
            "sequencing_context",
        ),
        "tools/tests/test_standard_pcr.py": ("COLONY_CONTEXT",),
        "tools/tests/test_rt.py": (
            "test_generic_rt_handoff_is_unresolved_in_every_policy",
            "rt-isothermal-chemistry-unresolved",
            "rt-chemistry-unresolved",
        ),
        "tools/tests/test_probe.py": (
            "test_qpcr_probe_without_named_executable_chemistry_is_refused_in_every_policy",
            "test_taqman_mgb_requires_explicit_external_authority_mode",
            "test_development_mode_cannot_execute_mgb_by_omitting_assay_identity",
        ),
        "tools/tests/test_discriminate.py": (
            "test_kasp_geometry_never_synthesizes_assay_identity",
            "test_tetra_requires_declared_band_resolution_context_in_every_policy",
        ),
        "tools/tests/test_loop_set.py": (
            "test_reviewed_lamp_envelope_cannot_be_widened_by_policy_mode",
            "test_named_e1700_preserves_its_exact_rt_lamp_hold_and_legacy_authority_label",
            "test_named_rt_lamp_protocols_supply_only_their_own_reviewed_hold",
            "test_generic_rt_lamp_handoff_has_no_inferred_temperature_or_duration",
        ),
    }
    for rel, needles in required_tests.items():
        path = ROOT / rel
        if not path.is_file():
            error(f"missing high-risk regression test: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                error(f"{rel} does not cover required regression marker {needle!r}")

    main_text = (ROOT / "tools/src/pcr_tools/__main__.py").read_text(encoding="utf-8")
    multiplex_text = (ROOT / "tools/src/pcr_tools/multiplex.py").read_text(encoding="utf-8")
    if 'answer["toolchain_validation"] = validate_result(' not in main_text or 'command="multiplex"' not in main_text:
        error("multiplex final selected panel is no longer passed through common external validation")
    if '"panel_validation_scope": "final-selected-oligos-grouped-by-tube"' not in multiplex_text:
        error("multiplex result no longer declares final-panel/tube validation scope")

    cross_layer_markers = {
        "crates/pcr-core/src/engines/flanking_pair.rs": (
            "colony_host_class", "colony_protocol_name", "digital_partition_format",
            "digital_fragmentation_state",
        ),
        "crates/pcr-core/src/engines/single_primer.rs": (
            "race_substrate", "race_preparation", "race_round", "sequencing_instrument",
        ),
        "tools/src/pcr_tools/pipeline.py": ("colony_context", "digital_context"),
        "tools/src/pcr_tools/single.py": ("race_context", "sequencing_context"),
        "web/src/lib/api/types.ts": (
            "colony_context", "digital_context", "race_context", "sequencing_context",
            "platform_route", "protocol_id", "consumable_id", "modified_oligos",
        ),
        "web/src/lib/api/scientific-result-schemas.ts": (
            "modifiedOligosProvenanceSchema", "modifiedOligoAnnotationSchema",
        ),
    }
    for rel, needles in cross_layer_markers.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                error(f"{rel} lost required P2 handoff marker {needle!r}")

def audit_fork_roundtrip_surface() -> None:
    """Every explicit browser input that reaches a saved run must be recoverable on fork."""
    request = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in ("web/src/lib/projects/request.ts", "web/src/lib/projects/engine-request-extensions.ts", "web/src/lib/projects/draft-codec.ts"))
    fork = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in ("web/src/lib/projects/fork-settings.ts", "web/src/lib/projects/draft-codec.ts"))
    # Capture both textual and numeric browser reads. Earlier this guard only
    # saw `field(form, ...)`, which let numeric settings silently disappear on
    # fork even though the request builder accepted them.
    form_fields = set(
        re.findall(r'(?:field|optionalNumber)\(form,\s*"([^"]+)"\)', request)
    )
    # `moduleId` selects the request branch; it is project identity rather than
    # a scientific setting stored inside the request payload.
    form_fields.discard("moduleId")
    mentioned = set(re.findall(r'"([A-Za-z][A-Za-z0-9_]*)"', fork))
    missing = sorted(form_fields - mentioned)
    if missing:
        error(f"fork-settings cannot restore request-producing draft fields: {missing}")
    for marker in (
        '"lampReadout"', '"lowercaseMasking"', '"exonJunctions"', '"alignmentMode"',
        '"tilingOperation"', '"tilingAlignmentMode"', '"tailProtocol"',
        '"maxMismatches"', '"tetraMinBandSeparationBp"',
    ):
        if marker not in fork:
            error(f"fork reproducibility regression lost marker {marker}")

def audit_required_context_surface() -> None:
    """Canonical semantic form facts must be visible, submitted and restorable.

    CURRENT separates semantic/form context from wire context. Field
    ownership names the actual browser draft key, so this audit must resolve a
    semantic path through that canonical map rather than guessing that every
    context key is a direct camelCase request property.
    """
    generated = json.loads(
        (ROOT / "web/src/lib/projects/required-context.generated.json").read_text(encoding="utf-8")
    )["modules"]
    design_root = ROOT / "web/src/components/design"
    ui_paths = [ROOT / "web/src/components/project/workspace.tsx"] + sorted(
        p for p in design_root.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx"}
    )
    ui = "\n".join(path.read_text(encoding="utf-8") for path in ui_paths)
    request = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in ("web/src/lib/projects/request.ts", "web/src/lib/projects/engine-request-extensions.ts", "web/src/lib/projects/draft-codec.ts"))
    fork = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in ("web/src/lib/projects/fork-settings.ts", "web/src/lib/projects/draft-codec.ts"))

    def camel(value: str) -> str:
        return re.sub(r"_([a-z0-9])", lambda m: m.group(1).upper(), value)

    def semantic_candidate(path: str) -> str:
        parts = str(path).split(".")
        if len(parts) == 1:
            return camel(parts[0])
        return camel(parts[0]) + camel(parts[-1])[:1].upper() + camel(parts[-1])[1:]

    def actual_field(path: str, owners: dict[str, str]) -> str | None:
        direct = semantic_candidate(path)
        if direct in owners:
            return direct
        leaf = camel(str(path).split(".")[-1])
        suffix = leaf[:1].upper() + leaf[1:]
        matches = sorted(key for key in owners if key == leaf or key.endswith(suffix))
        return matches[0] if len(matches) == 1 else None

    seen: set[tuple[str, str]] = set()
    for module_id, contract in generated.items():
        owners = contract.get("field_owners", {})
        paths = list(contract.get("required_context", []))
        for rule in contract.get("conditional_required_context", []):
            paths.extend(rule.get("required_context", []))
        for path in paths:
            field = actual_field(str(path), owners)
            if not field:
                error(f"{module_id}: semantic required context {path!r} has no unambiguous canonical browser field owner")
                continue
            key = (module_id, field)
            if key in seen:
                continue
            seen.add(key)
            if field not in ui:
                error(f"{module_id}: required context {path!r} has no visible/fixed browser field {field!r}")
            if field not in owners:
                error(f"{module_id}: required browser field {field!r} has no canonical step owner")
            submitted = f'"{field}"' in request or f'field(form, "{field}")' in request
            # Some semantic controls intentionally compile to a fixed wire value
            # after the UI has already refused unsupported alternatives.
            if field == "singleTube" and "singleTube: false" in request:
                submitted = True
            if not submitted:
                error(f"{module_id}: required browser field {field!r} is not carried by request.ts")
            if f'"{field}"' not in fork:
                error(f"{module_id}: required browser field {field!r} is not restorable on fork")

    readiness = (ROOT / "web/src/components/project/workspace-readiness.ts").read_text(encoding="utf-8")
    for marker in (
        "requiredDraftFields(moduleId, draft)",
        "const contextReadyFor = (owner: RequiredContextStep)",
        'contextReadyFor("design")',
        'contextReadyFor("strategy")',
        'contextReadyFor("reaction")',
        'contextReadyFor("validation")',
        'contextReadyFor("construct")',
    ):
        if marker not in readiness:
            error(f"catalogue-wide readiness marker missing: {marker!r}")

def audit_python_json_toml() -> None:
    for path in iter_source_files():
        if path.suffix not in {".py", ".json", ".toml"}:
            continue
        if path.suffix == ".py":
            try: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except Exception as exc: error(f"Python syntax: {path.relative_to(ROOT)}: {exc}")
        if path.suffix == ".json":
            try: json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc: error(f"JSON parse: {path.relative_to(ROOT)}: {exc}")
        if path.suffix == ".toml":
            try: tomllib.loads(path.read_text(encoding="utf-8"))
            except Exception as exc: error(f"TOML parse: {path.relative_to(ROOT)}: {exc}")

def audit_module_engine_parity() -> None:
    modules, contracts, bindings = parse_runtime_contract()
    profiles = tomllib.loads((ROOT / "crates/pcr-core/profiles.toml").read_text(encoding="utf-8"))["profile"]
    profile_map = {row["id"]: row for row in profiles}
    canonical = json.loads((ROOT / "knowledge/runtime/module-contracts.json").read_text(encoding="utf-8"))["modules"]
    expected = set(modules)
    if len(expected) != 21: error(f"runtime module count is {len(expected)}, expected 21")
    if len(set(modules.values())) != 11: error(f"runtime engine count is {len(set(modules.values()))}, expected 11")
    if set(profile_map) != expected: error(f"profile/runtime module ids differ: {sorted(set(profile_map)^expected)}")
    if set(canonical) != expected: error(f"canonical/runtime module ids differ: {sorted(set(canonical)^expected)}")

    for module_id in sorted(expected):
        if profile_map[module_id].get("engine") != modules[module_id]:
            error(f"{module_id}: profiles.toml engine != runtime mapping")
        rc = contracts[module_id]; cc = canonical[module_id]
        for key in ("gates", "fallback"):
            left = list(rc[key]) if key == "gates" else rc[key]
            if left != cc[key]: error(f"{module_id}: Python {key} drifted from canonical module contract")
        if list(rc.get("required_context", ())) != list(cc.get("required_context", [])):
            error(f"{module_id}: required_context drifted from canonical module contract")
        py_conditional = [
            {"when": dict(rule.get("when", {})), "required_context": list(rule.get("required_context", ()))}
            for rule in rc.get("conditional_required_context", ())
        ]
        if py_conditional != list(cc.get("conditional_required_context", [])):
            error(f"{module_id}: conditional_required_context drifted from canonical module contract")
        if list(rc.get("wire_required_context", ())) != list(cc.get("wire_required_context", [])):
            error(f"{module_id}: wire_required_context drifted from canonical module contract")
        py_wire_conditional = [
            {"when": dict(rule.get("when", {})), "required_context": list(rule.get("required_context", ()))}
            for rule in rc.get("wire_conditional_required_context", ())
        ]
        if py_wire_conditional != list(cc.get("wire_conditional_required_context", [])):
            error(f"{module_id}: wire_conditional_required_context drifted from canonical module contract")
        if [list(group) for group in rc.get("wire_required_any_of", ())] != list(cc.get("wire_required_any_of", [])):
            error(f"{module_id}: wire_required_any_of drifted from canonical module contract")

    plan_text = (ROOT / "web/src/components/design/page-plan.ts").read_text(encoding="utf-8")
    page_capabilities = json.loads(
        (ROOT / "web/src/components/design/page-capabilities.generated.json").read_text(encoding="utf-8")
    )["modules"]
    planned = set(page_capabilities)
    if planned != expected: error(f"generated UI page-capability module ids differ: {sorted(planned^expected)}")

    # The RNA/DNA control is derived from the profile modifier, so its visible
    # default has exactly one owner: Workspace seeds it for every module with
    # `reverse-transcription`. Do not duplicate that default in per-assay plans.
    workspace = (ROOT / "web/src/components/project/workspace.tsx").read_text(encoding="utf-8")
    rt_seed = 'modifiers.includes("reverse-transcription") ? { fromRna: "false" } : {}'
    if rt_seed not in workspace:
        error("Workspace lost the modifier-owned fromRna=false provenance seed")
    for module_id, page in page_capabilities.items():
        if "fromRna" in page.get("initial", {}):
            error(f"{module_id}: fromRna default is duplicated in generated page metadata; modifier-owned Workspace seed must be the single source of truth")

    if page_capabilities.get("colony-pcr", {}).get("initial", {}).get("vectorPrimerReadsInto") != "start":
        error("colony-pcr: visible vector-primer orientation default is not seeded into canonical draft provenance")

    atlas_engines = json.loads((ROOT / "knowledge/atlas/contracts/engine-tool-contracts.json").read_text(encoding="utf-8"))["engines"]
    atlas_bindings = {row["engine_id"]: row["bindings"] for row in atlas_engines}
    if set(atlas_bindings) != set(bindings): error(f"Atlas/runtime engine ids differ: {sorted(set(atlas_bindings)^set(bindings))}")
    for engine in sorted(set(bindings) & set(atlas_bindings)):
        if bindings[engine] != atlas_bindings[engine]: error(f"{engine}: runtime tool bindings drifted from Atlas")

    # Human-facing review matrices are release evidence too.  Keep the LAMP row
    # semantically tied to the canonical runtime contract instead of relying on
    # file hashes alone; this catches stale gate/fallback prose after a contract
    # rename.
    lamp = canonical.get("lamp", {})
    lamp_gates = list(lamp.get("gates", ()))
    coverage = (ROOT / "knowledge/reviews/MODULE-IMPLEMENTATION-COVERAGE.md").read_text(encoding="utf-8")
    full_audit = (ROOT / "knowledge/reviews/FULL-SYSTEM-AUDIT.md").read_text(encoding="utf-8")
    coverage_row = next((line for line in coverage.splitlines() if line.startswith("| `lamp` |")), "")
    full_row = next((line for line in full_audit.splitlines() if line.startswith("| `lamp` (LAMP) |")), "")
    for gate in lamp_gates:
        if gate not in coverage_row:
            error(f"lamp: implementation-coverage review omitted canonical gate {gate!r}")
        if gate not in full_row:
            error(f"lamp: full-system review omitted canonical gate {gate!r}")
    if "set_interactions" in coverage_row or "set_interactions" in full_row:
        error("lamp: stale set_interactions wording remains in human review matrices")
    lamp_fallback = str(lamp.get("fallback", ""))
    if lamp_fallback and lamp_fallback not in full_row:
        error("lamp: full-system review fallback drifted from canonical module contract")
