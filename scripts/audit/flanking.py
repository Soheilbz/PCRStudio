"""Flanking static-audit checks."""
from __future__ import annotations

from .common import *  # noqa: F403

def audit_flanking_protocol_contract() -> None:
    """Keep the flanking-pair named-protocol registries synchronized.

    These registries are executable scientific authority: the worker, Rust
    request validator, TypeScript request union and UI must agree on the exact
    protocol identities.  Long-range PCR and RPA intentionally require a named
    executable choice in the UI, so their ``not-selected`` sentinel remains a
    transport/validation value rather than a selectable option.
    """
    authority = json.loads((ROOT / "knowledge/runtime/flanking-protocol-authority.generated.json").read_text(encoding="utf-8"))
    groups = authority.get("groups", {})
    python_protocols: dict[str, tuple[str, ...]] = {
        "STANDARD_PCR_PROTOCOLS": tuple(groups.get("standard_pcr", ())),
        "QPCR_PROTOCOLS": tuple(groups.get("qpcr_sybr", ())),
        "RPA_PROTOCOLS": tuple(groups.get("rpa", ())),
        "LONG_RANGE_PROTOCOLS": tuple(groups.get("long_range", ())),
        "DIGITAL_PROTOCOLS": tuple(groups.get("digital", ())),
    }
    if not all(python_protocols.values()):
        error("flanking protocol authority generated JSON lost one or more executable protocol groups")

    rust = (ROOT / "crates/pcr-core/src/engines/flanking_pair.rs").read_text(encoding="utf-8")
    rust_authority = (ROOT / "crates/pcr-core/src/engines/flanking_protocol_ids.generated.rs").read_text(encoding="utf-8")
    pipeline_path = ROOT / "tools/src/pcr_tools/pipeline.py"
    pipeline_tree = ast.parse(pipeline_path.read_text(encoding="utf-8"), filename=str(pipeline_path))
    protocol_path = ROOT / "tools/src/pcr_tools/registries/flanking_protocols.py"
    protocol_tree = ast.parse(protocol_path.read_text(encoding="utf-8"), filename=str(protocol_path))
    cloning_coding_path = ROOT / "tools/src/pcr_tools/cloning_coding.py"
    cloning_coding_tree = ast.parse(cloning_coding_path.read_text(encoding="utf-8"), filename=str(cloning_coding_path))
    types = (ROOT / "web/src/lib/contracts/design-requests.ts").read_text(encoding="utf-8")
    fields = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in ("web/src/components/design/engine-fields.tsx", "web/src/components/design/engine-fields/digital-pcr-fields.tsx"))
    generated_fields = (ROOT / "web/src/components/design/engine-fields/flanking-fields.tsx").read_text(encoding="utf-8")
    numeric_catalogue = json.loads((ROOT / "web/src/lib/flanking-numeric-recipes.generated.json").read_text(encoding="utf-8"))

    # CURRENT provenance closure: every vendor/literature protocol identity is
    # bound to one reviewed HTTPS locator in the canonical authority. Remote
    # source documents are deliberately not assigned fake hashes when the
    # document itself is not snapshotted into the release.
    provenance = authority.get("provenance", {})
    provenance_groups = (
        "standard_pcr", "qpcr_sybr", "rpa", "long_range", "digital",
        "colony_protocols", "restriction_digest_protocols",
        "restriction_dephosphorylation_protocols", "restriction_ligation_protocols",
    )
    expected_protocol_provenance: set[str] = set()
    for group in provenance_groups:
        expected_protocol_provenance.update(groups.get(group, ()))
    expected_protocol_provenance -= {"not-selected", "custom-sop", "none"}
    expected_provenance = set(expected_protocol_provenance)
    # Routing/compatibility evidence is scientific authority too even when it
    # is not itself a selectable protocol. Every referenced evidence identity
    # must therefore be provenance-bound and claim-snapshotted, but it is not
    # required to appear in the browser's selectable protocol metadata table.
    for evidence_ids in authority.get("routing_evidence", {}).get("digital_platforms", {}).values():
        expected_provenance.update(evidence_ids or ())
    if set(provenance) != expected_provenance:
        error(f"CURRENT Flanking provenance coverage drifted: {sorted(set(provenance) ^ expected_provenance)}")
    for protocol_id, row in provenance.items():
        if not isinstance(row, dict) or not str(row.get("url", "")).startswith("https://"):
            error(f"CURRENT Flanking provenance locator is not canonical HTTPS: {protocol_id}")
            continue
        reviewed = str(row.get("reviewed_date") or "")
        if not reviewed.startswith("2026-09-"):
            error(f"CURRENT Flanking provenance review date is not release-bounded: {protocol_id}")
        if row.get("snapshot_status") != "canonical-claim-snapshot-pinned":
            error(f"CURRENT Flanking provenance claim-snapshot boundary drifted: {protocol_id}")
        if row.get("snapshot_registry") != "knowledge/sources/flanking-source-snapshots.json":
            error(f"CURRENT Flanking provenance snapshot registry drifted: {protocol_id}")
        digest = row.get("claim_snapshot_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
            error(f"CURRENT Flanking provenance claim-snapshot SHA-256 invalid: {protocol_id}")
        if row.get("availability_scope") != "not-asserted":
            error(f"CURRENT Flanking provenance availability boundary drifted: {protocol_id}")
        if "sha256" in row:
            error(f"CURRENT Flanking provenance must not confuse claim digest with third-party document-byte SHA-256: {protocol_id}")
    metadata_rows = numeric_catalogue.get("protocol_metadata", {})
    for protocol_id in expected_protocol_provenance - set(groups.get("restriction_digest_protocols", ())) - set(groups.get("restriction_dephosphorylation_protocols", ())) - set(groups.get("restriction_ligation_protocols", ())):
        meta = metadata_rows.get(protocol_id)
        if not isinstance(meta, dict):
            error(f"CURRENT Flanking browser metadata missing provenance protocol: {protocol_id}")
            continue
        row = provenance[protocol_id]
        if meta.get("source_url") != row.get("url") or meta.get("source_reviewed_date") != row.get("reviewed_date"):
            error(f"CURRENT Flanking browser provenance projection drifted: {protocol_id}")
        if meta.get("source_snapshot_status") != "canonical-claim-snapshot-pinned" or meta.get("source_availability_scope") != "not-asserted":
            error(f"CURRENT Flanking browser claim-snapshot provenance boundary drifted: {protocol_id}")
        digest = meta.get("source_claim_snapshot_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            error(f"CURRENT Flanking browser claim-snapshot digest missing: {protocol_id}")

    # CURRENT dPCR routing closure: platform identity, consumable compatibility,
    # protocol compatibility and Pair+Probe routing must all project from the
    # same canonical authority rather than being re-hardcoded per language.
    routing = authority.get("routing", {}).get("digital_platforms", {})
    expected_platforms = set(groups.get("digital_platform_ids", ()))
    if set(routing) != expected_platforms:
        error(f"CURRENT dPCR routing coverage drifted: {sorted(set(routing) ^ expected_platforms)}")
    if {platform for platform, route in routing.items() if route == "pair-probe"} != {"thermo-absolute-q", "roche-digital-lightcycler", "bio-rad-qx-continuum"}:
        error("CURRENT dPCR Pair+Probe routing boundary drifted")
    compatibility = authority.get("compatibility", {})
    consumable_platforms = compatibility.get("digital_consumable_platforms", {})
    protocol_platforms = compatibility.get("digital_protocol_platforms", {})
    if set(consumable_platforms.get("qx700-rdg16", ())) != {"bio-rad-qx700", "bio-rad-nio", "bio-rad-naica"}:
        error("naica/RDG16 platform compatibility drifted")
    if set(consumable_platforms.get("naica-sapphire-chip", ())) != {"bio-rad-naica"}:
        error("naica Sapphire Chip compatibility drifted")
    if set(protocol_platforms.get("bio-rad-qx700-naica-evagreen", ())) != {"bio-rad-qx700", "bio-rad-nio", "bio-rad-naica"}:
        error("naica EvaGreen protocol/platform compatibility drifted")
    if set(protocol_platforms.get("bio-rad-qx700-evagreen-supermix", ())) != {"bio-rad-qx700"}:
        error("dedicated QX700 EvaGreen Supermix platform boundary drifted")
    if set(protocol_platforms.get("bio-rad-qx200-evagreen", ())) != {"bio-rad-qx200", "bio-rad-qx600", "bio-rad-qx-one"}:
        error("QX200/QX600/QX ONE shared EvaGreen chemistry boundary drifted")
    protocol_source = protocol_path.read_text(encoding="utf-8")
    web_contract = (ROOT / "web/src/lib/flanking-contract.ts").read_text(encoding="utf-8")
    for label, text, markers in (
        ("Python", protocol_source, ("DIGITAL_PLATFORM_ROUTES", "DIGITAL_PROTOCOL_PLATFORMS", "DIGITAL_CONSUMABLE_PLATFORMS")),
        ("Rust", rust, ("DIGITAL_PLATFORM_ROUTES", "DIGITAL_PROTOCOL_PLATFORM_PAIRS", "DIGITAL_CONSUMABLE_PLATFORM_PAIRS")),
        ("Web", web_contract, ("DIGITAL_PLATFORM_ROUTES", "DIGITAL_PROTOCOL_PLATFORMS", "DIGITAL_CONSUMABLE_PLATFORMS")),
    ):
        for marker in markers:
            if marker not in text:
                error(f"CURRENT dPCR {label} authority projection lost marker: {marker}")
    for stale_literal in (
        '["bio-rad-qx600", "bio-rad-qx-one", "bio-rad-qx-continuum"]',
        '{"bio-rad-qx600", "bio-rad-qx-one", "bio-rad-qx-continuum"}',
    ):
        if stale_literal in protocol_source or stale_literal in rust or stale_literal in web_contract:
            error("CURRENT dPCR runtime regained a parallel hard-coded unresolved-platform compatibility list")

    workspace = (ROOT / "web/src/components/project/workspace.tsx").read_text(encoding="utf-8")
    for marker in ("FLANKING_PROTOCOL_METADATA", "const protocolMeta = FLANKING_PROTOCOL_METADATA[value]", "return protocolMeta.label"):
        if marker not in workspace:
            error(f"Workspace human protocol labels lost generated metadata marker: {marker}")

    # Numeric scientific semantics that are easy to accidentally flatten during
    # catalogue growth. PowerTrack Yellow Sample Buffer is optional, while the
    # Thermo Lyo-ready RPA protein/RT composition is an executable numeric
    # authority. Guard both without requiring native Rust/Web dependencies.
    baselines = numeric_catalogue.get("baselines", {})
    rules = numeric_catalogue.get("conditional_rules", {})
    ranges = numeric_catalogue.get("optimization_envelopes", {})
    powertrack = baselines.get("thermo-powertrack-sybr-a46xxx", {})
    if "yellow_sample_buffer_x_final" in powertrack or "yellow_sample_buffer_stock_x" in powertrack:
        error("flanking numeric: PowerTrack optional Yellow Sample Buffer leaked into the product baseline")
    powertrack_rules = {row.get("id"): row for row in rules.get("thermo-powertrack-sybr-a46xxx", []) if isinstance(row, dict)}
    yellow = powertrack_rules.get("powertrack-yellow-sample-buffer")
    if not isinstance(yellow, dict) or yellow.get("when") != {"additive": "yellow-sample-buffer"}:
        error("flanking numeric: PowerTrack optional Yellow Sample Buffer conditional rule drifted")
    else:
        expected_yellow = {"yellow_sample_buffer_x_final": 1.0, "yellow_sample_buffer_stock_x": 40.0}
        if yellow.get("set") != expected_yellow:
            error("flanking numeric: PowerTrack Yellow Sample Buffer 40X->1X arithmetic authority drifted")

    rpa = baselines.get("thermo-lyo-ready-rpa", {})
    expected_rpa = {
        "reaction_volume_uL": 20.0, "primer_each_nM": 300.0, "magnesium_mM": 14.0,
        "dntp_each_mM": 0.2, "uvsx_mg_per_mL": 0.03, "uvsy_mg_per_mL": 0.03,
        "gene32_mg_per_mL": 0.4, "bst_polymerase_U_per_uL": 0.15,
        "hold_temperature_c": 42.0, "hold_time_min": 20.0,
    }
    for key, expected in expected_rpa.items():
        if rpa.get(key) != expected:
            error(f"flanking numeric: Thermo Lyo-ready RPA baseline drifted at {key}")
    expected_rpa_ranges = {
        "primer_each_nM": [100.0, 300.0],
        "hold_temperature_c": [34.0, 45.0],
        "hold_time_min": [10.0, 25.0],
        "bst_polymerase_U_per_uL": [0.015, 0.15],
    }
    for key, expected in expected_rpa_ranges.items():
        if ranges.get("thermo-lyo-ready-rpa", {}).get(key) != expected:
            error(f"flanking numeric: Thermo Lyo-ready RPA reviewed range drifted at {key}")
    rpa_rule_ids = {row.get("id") for row in rules.get("thermo-lyo-ready-rpa", []) if isinstance(row, dict)}
    for expected in {"rpa-multiplex-primer-start", "rpa-rna-components"}:
        if expected not in rpa_rule_ids:
            error(f"flanking numeric: Thermo Lyo-ready RPA conditional rule disappeared: {expected}")

    families = {
        "standard-pcr": ("STANDARD_PCR_PROTOCOLS", "standardPcrProtocol", "standardPcrProtocol", False),
        "qpcr-sybr": ("QPCR_PROTOCOLS", "qpcrProtocol", "qpcrProtocol", False),
        "rpa": ("RPA_PROTOCOLS", "rpaProtocol", "rpaProtocol", True),
        "long-range-pcr": ("LONG_RANGE_PROTOCOLS", "longRangeProtocol", "longRangeProtocol", True),
        "digital-pcr": ("DIGITAL_PROTOCOLS", "digitalProtocol", "digitalProtocol", False),
    }

    for assay_id, (const_name, ts_field, select_id, requires_named_ui) in families.items():
        py_values = python_protocols.get(const_name)
        if py_values is None:
            error(f"{assay_id}: Python protocol registry {const_name} disappeared")
            continue
        if len(py_values) != len(set(py_values)):
            error(f"{assay_id}: Python protocol registry contains duplicate ids")
        if "not-selected" not in py_values:
            error(f"{assay_id}: protocol registry lost the explicit not-selected sentinel")

        rust_match = re.search(
            rf"const\s+{re.escape(const_name)}\s*:\s*&\[&str\]\s*=\s*&\[(.*?)\];",
            rust_authority,
            re.S,
        )
        if not rust_match:
            error(f"{assay_id}: Rust protocol registry {const_name} disappeared")
            continue
        rust_values = tuple(re.findall(r'"([^"]+)"', rust_match.group(1)))

        ts_match = re.search(
            rf"\b{re.escape(ts_field)}\?\s*:\s*(.*?);",
            types,
            re.S,
        )
        if not ts_match:
            error(f"{assay_id}: TypeScript request union {ts_field} disappeared")
            continue
        ts_values = tuple(re.findall(r'"([^"]+)"', ts_match.group(1)))

        select_match = re.search(
            rf'<select\b(?=[^>]*\bid="{re.escape(select_id)}")[^>]*>(.*?)</select>',
            fields,
            re.S,
        )
        component_match = re.search(
            rf'<SearchableFlankingProtocolSelect\b(?:(?!/>).)*?\bid="{re.escape(select_id)}"(?:(?!/>).)*?\bmoduleId="{re.escape(assay_id)}"(?:(?!/>).)*?/>',
            fields,
            re.S,
        )
        if not select_match and not component_match:
            error(f"{assay_id}: protocol selector #{select_id} disappeared from the UI")
            continue
        if select_match:
            ui_values = tuple(value for value in re.findall(r'<option\b[^>]*\bvalue="([^"]*)"', select_match.group(1)) if value)
            opening_tag = fields[select_match.start(): fields.find(">", select_match.start()) + 1]
            ui_has_not_selected = 'value="not-selected"' in select_match.group(1)
        else:
            metadata = numeric_catalogue.get("protocol_metadata", {})
            ui_values = tuple(sorted(
                protocol_id for protocol_id, meta in metadata.items()
                if isinstance(meta, dict) and meta.get("module") == assay_id
            ))
            opening_tag = component_match.group(0) if component_match else ""
            ui_has_not_selected = 'allowNotSelected={false}' not in opening_tag

        expected = set(py_values)
        if set(rust_values) != expected:
            error(f"{assay_id}: Rust/Python protocol ids drifted: {sorted(set(rust_values) ^ expected)}")
        if set(ts_values) != expected:
            error(f"{assay_id}: TypeScript/Python protocol ids drifted: {sorted(set(ts_values) ^ expected)}")

        expected_ui = expected - {"not-selected"}
        if set(ui_values) != expected_ui:
            error(f"{assay_id}: UI/Python protocol ids drifted: {sorted(set(ui_values) ^ expected_ui)}")

        if requires_named_ui and "required" not in opening_tag:
            error(f"{assay_id}: named chemistry is mandatory but the UI selector is no longer required")
        if requires_named_ui and ui_has_not_selected:
            error(f"{assay_id}: UI regained a selectable not-selected branch despite fail-closed chemistry authority")

    # Standard-PCR is the only currently multiplex-enabled flanking assay that
    # also has a named bench chemistry. The multiplex form therefore carries
    # one shared tube-level selector whose ids must remain identical to the
    # simplex registry; per-target chemistry selection would describe an
    # impossible single-tube experiment.
    multiplex_form = (ROOT / "web/src/components/design/multiplex-form.tsx").read_text(encoding="utf-8")
    multiplex_select = re.search(
        r'<select\b(?=[^>]*\bid="multiplex-standard-pcr-protocol")[^>]*>(.*?)</select>',
        multiplex_form,
        re.S,
    )
    if multiplex_select is None:
        error("standard-pcr: shared multiplex chemistry selector disappeared")
    else:
        multiplex_values = {
            value
            for value in re.findall(r'<option\b[^>]*\bvalue="([^"]*)"', multiplex_select.group(1))
            if value
        }
        expected_standard = set(python_protocols.get("STANDARD_PCR_PROTOCOLS", ()))
        if multiplex_values != expected_standard:
            error(
                "standard-pcr: multiplex UI/Python protocol ids drifted: "
                f"{sorted(multiplex_values ^ expected_standard)}"
            )
    bench = (ROOT / "crates/pcr-server/src/bench.rs").read_text(encoding="utf-8")
    actions = (ROOT / "web/src/lib/projects/actions.ts").read_text(encoding="utf-8")
    transport = (ROOT / "web/src/lib/api/transport.ts").read_text(encoding="utf-8")
    for rel, source, marker in (
        ("crates/pcr-server/src/bench.rs", bench, 'entry.insert("standard_pcr_protocol".to_owned(), protocol.clone().into())'),
        ("crates/pcr-server/src/bench.rs", bench, 'standardPcrProtocol is only valid when multiplexing standard-pcr.'),
        ("web/src/lib/projects/actions.ts", actions, 'moduleId === "standard-pcr"'),
        ("web/src/lib/api/transport.ts", transport, 'standardPcrProtocol?: DesignPayload["standardPcrProtocol"]'),
    ):
        if marker not in source:
            error(f"standard-pcr multiplex chemistry transport lost marker in {rel}: {marker}")

    for marker in (
        "a named Standard-PCR chemistry overlay requires `standard-pcr` assay",
        "a named dye-qPCR overlay requires `qpcr-sybr` assay",
        "an RPA chemistry branch requires the `rpa` assay",
        "a named long-range PCR overlay requires `long-range-pcr` assay",
        "a named digital-PCR overlay requires `digital-pcr` assay",
    ):
        if marker not in rust:
            error(f"flanking-pair: Rust wrong-assay protocol gate lost marker {marker!r}")

    # Scientific context that is not a protocol id still crosses every public
    # layer. Guard the identifiers explicitly so provenance cannot silently
    # disappear while the request remains syntactically valid.
    context_layers = {
        "crates/pcr-core/src/engines/flanking_pair.rs": (
            "colony_protocol_provenance",
            "inclusivity_panel_provenance",
            "background_panel_provenance",
            "species_panel_selection_rationale",
            "species_panel_record_metadata_manifest",
        ),
        "tools/src/pcr_tools/pipeline.py": (
            "colony_protocol_provenance",
            "inclusivity_panel_provenance",
            "background_panel_provenance",
            "species_panel_selection_rationale",
            "species_panel_record_metadata_manifest",
        ),
        "web/src/lib/contracts/design-requests.ts": (
            "colonyProtocolProvenance",
            "inclusivityPanelProvenance",
            "backgroundPanelProvenance",
            "speciesPanelSelectionRationale",
            "speciesPanelRecordMetadataManifest",
        ),
        "web/src/lib/api/transport.ts": (
            "colonyProtocolProvenance",
            "inclusivityPanelProvenance",
            "backgroundPanelProvenance",
            "speciesPanelSelectionRationale",
            "speciesPanelRecordMetadataManifest",
        ),
        "web/src/components/design/engine-fields.tsx": (
            "colonyProtocolProvenance",
        ),
        "web/src/components/project/workspace.tsx": (
            "inclusivityPanelProvenance",
            "backgroundPanelProvenance",
            "speciesPanelSelectionRationale",
            "speciesPanelRecordMetadataManifest",
        ),
        "web/src/components/design/multiplex-form.tsx": (
            "colonyProtocolProvenance",
            "inclusivityPanelProvenance",
            "backgroundPanelProvenance",
            "speciesPanelSelectionRationale",
            "speciesPanelRecordMetadataManifest",
        ),
        "crates/pcr-server/src/bench.rs": (
            "colonyProtocolProvenance",
            "inclusivityPanelProvenance",
            "backgroundPanelProvenance",
            "speciesPanelSelectionRationale",
            "speciesPanelRecordMetadataManifest",
        ),
    }
    for rel, markers in context_layers.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                error(f"flanking-pair: cross-layer scientific provenance drifted in {rel}: {marker}")

    numeric_context_markers = {
        "crates/pcr-core/src/engines/flanking_pair.rs": (
            'rename_all(deserialize = "camelCase", serialize = "snake_case")',
            "rpa_temperature_c", "rpa_time_min", "rpa_bst_units_per_ul", "rpa_multiplex",
            "yellow-sample-buffer",
        ),
        "tools/src/pcr_tools/flanking_request.py": (
            "rpa_temperature_c", "rpa_time_min", "rpa_bst_units_per_ul", "rpa_multiplex",
            "yellow-sample-buffer",
        ),
        "tools/src/pcr_tools/pipeline.py": (
            'scenario["multiplex"]', 'scenario["temperature_c"]', 'scenario["time_min"]',
            'scenario["bst_units_per_uL"]',
        ),
        "web/src/lib/contracts/design-requests.ts": (
            "rpaTemperatureC", "rpaTimeMin", "rpaBstUnitsPerUl", "rpaMultiplex",
            "yellow-sample-buffer",
        ),
        "web/src/lib/projects/draft-codec.ts": (
            "rpaTemperatureC", "rpaTimeMin", "rpaBstUnitsPerUl", "rpaMultiplex",
            "flankingAdditive", "restoreFlankingNumericContext",
            "flankingNumericContextFromDraft",
        ),
        "web/src/lib/projects/request.ts": ("flankingNumericContextFromDraft",),
        "web/src/lib/projects/fork-settings.ts": ("restoreFlankingNumericContext",),
        "web/src/lib/flanking-contract.ts": (
            "rpaTemperatureC", "rpaTimeMin", "rpaBstUnitsPerUl", "rpaMultiplex",
            "yellow-sample-buffer",
        ),
        "web/src/components/design/engine-fields/flanking-fields.tsx": (
            "rpaTemperatureC", "rpaTimeMin", "rpaBstUnitsPerUl", "rpaMultiplex",
            "yellow-sample-buffer",
        ),
    }
    for rel, markers in numeric_context_markers.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                error(f"flanking-pair: numeric-context parity drifted in {rel}: {marker}")

    # The direct Python worker has a fail-closed request allowlist. Every
    # literal request.get("field") used by the flanking pipeline must be in
    # that allowlist or a valid Rust/UI field can be rejected before its own
    # scientific validator is reached. This caught a real provenance-transport
    # regression during the pre-Linux cold audit.
    known_request_fields: set[str] = set()
    request_get_fields: set[str] = set()
    for tree in (pipeline_tree, protocol_tree, cloning_coding_tree):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "KNOWN_REQUEST_FIELDS"
                and isinstance(node.value, ast.Call)
                and node.value.args
                and isinstance(node.value.args[0], (ast.Set, ast.List, ast.Tuple))
            ):
                for item in node.value.args[0].elts:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        known_request_fields.add(item.value)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "request"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                request_get_fields.add(node.args[0].value)
    if known_request_fields != request_get_fields:
        error(
            "flanking-pair: Python KNOWN_REQUEST_FIELDS drifted from literal request.get fields: "
            f"missing={sorted(request_get_fields - known_request_fields)}, "
            f"unused={sorted(known_request_fields - request_get_fields)}"
        )

    # Keep the Rust single-target serializer and Python worker allowlist exact.
    # A field present on only one side is either silently lost or rejected as
    # unknown before its scientific validator runs.
    to_worker_match = re.search(
        r"fn\s+to_worker\(&self\)\s*->\s*serde_json::Value\s*\{(.*?)\n\s*\}\n\}\n\n#\[cfg\(test\)\]",
        rust,
        re.S,
    )
    if to_worker_match is None:
        error("flanking-pair: Rust FlankingPairRequest::to_worker body could not be audited")
    else:
        worker_body = to_worker_match.group(1)
        rust_worker_fields = set(re.findall(r'\bput\(\s*"([^"]+)"', worker_body, re.S))
        rust_worker_fields.update(
            re.findall(r'payload\.insert\(\s*"([^"]+)"', worker_body, re.S)
        )
        internal_worker_only = {"multiplex_context"}
        expected_single_target_fields = known_request_fields - internal_worker_only
        if rust_worker_fields != expected_single_target_fields:
            error(
                "flanking-pair: Rust to_worker/Python request allowlist drifted: "
                f"rust_only={sorted(rust_worker_fields - expected_single_target_fields)}, "
                f"python_only={sorted(expected_single_target_fields - rust_worker_fields)}"
            )

    # Multiplex uses raw JSON at the HTTP boundary and therefore needs its own
    # exact fail-closed surface. Guard both the worker controls and the reduced
    # target vocabulary; tails/vector-primer/per-target chemistry are excluded
    # until the set interaction/order-sheet model can represent them honestly.
    multiplex_path = ROOT / "tools/src/pcr_tools/multiplex.py"
    multiplex_text = multiplex_path.read_text(encoding="utf-8")
    multiplex_tree = ast.parse(multiplex_text, filename=str(multiplex_path))

    def _literal_frozenset(name: str) -> set[str]:
        for node in multiplex_tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name
            ):
                value = node.value
                if isinstance(value, ast.Call) and value.args:
                    value = value.args[0]
                if isinstance(value, (ast.Set, ast.List, ast.Tuple)):
                    return {
                        item.value
                        for item in value.elts
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    }
        return set()

    multiplex_known = _literal_frozenset("KNOWN_REQUEST_FIELDS")
    multiplex_request_gets: set[str] = set()
    for node in ast.walk(multiplex_tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "request"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            multiplex_request_gets.add(node.args[0].value)
    if multiplex_known != multiplex_request_gets:
        error(
            "multiplex: worker KNOWN_REQUEST_FIELDS drifted from literal request.get fields: "
            f"missing={sorted(multiplex_request_gets - multiplex_known)}, "
            f"unused={sorted(multiplex_known - multiplex_request_gets)}"
        )

    expected_target_worker_fields = {
        "name", "template", "background", "inclusivity",
        "inclusivity_panel_provenance", "background_panel_provenance",
        "species_panel_selection_rationale", "species_target_taxid", "species_taxonomy_snapshot",
        "species_database_snapshot", "species_panel_accession_manifest", "species_panel_retrieved_date",
        "constraints", "assay", "from_rna", "standard_pcr_protocol", "multiplex_context", "colony_host_class", "colony_preparation",
        "colony_protocol_id", "colony_protocol_name", "colony_protocol_provenance", "tube",
        "primer_concentration_nm", "empirical_evidence_ref",
    }
    multiplex_target_fields = _literal_frozenset("KNOWN_TARGET_FIELDS")
    if multiplex_target_fields != expected_target_worker_fields:
        error(
            "multiplex: worker target allowlist drifted from the explicitly modelled set-level contract: "
            f"unexpected={sorted(multiplex_target_fields - expected_target_worker_fields)}, "
            f"missing={sorted(expected_target_worker_fields - multiplex_target_fields)}"
        )

    expected_public_outer_fields = {
        "readout", "readoutProfile", "fromRna", "standardPcrProtocol",
        "colonyHostClass", "colonyPreparation", "colonyProtocolId", "colonyProtocolName",
        "colonyProtocolProvenance", "targets", "candidatesPerTarget",
        "perTube", "rounds", "seed", "optimizerMode",
    }
    rust_outer_match = re.search(
        r"const\s+MULTIPLEX_PUBLIC_FIELDS\s*:\s*&\[&str\]\s*=\s*&\[(.*?)\];",
        bench,
        re.S,
    )
    if rust_outer_match is None:
        error("multiplex: Rust outer public allowlist disappeared")
    else:
        rust_outer_fields = set(re.findall(r'"([^"]+)"', rust_outer_match.group(1)))
        if rust_outer_fields != expected_public_outer_fields:
            error(
                "multiplex: Rust outer public allowlist drifted: "
                f"unexpected={sorted(rust_outer_fields - expected_public_outer_fields)}, "
                f"missing={sorted(expected_public_outer_fields - rust_outer_fields)}"
            )

    expected_public_target_fields = {
        "name", "template", "background", "inclusivity",
        "inclusivityPanelProvenance", "backgroundPanelProvenance",
        "speciesPanelSelectionRationale", "speciesTargetTaxid", "speciesTaxonomySnapshot",
        "speciesDatabaseSnapshot", "speciesPanelAccessionManifest", "speciesPanelRecordMetadataManifest", "speciesPanelRetrievedDate", "constraints", "tube",
        "primerConcentrationNm", "empiricalEvidenceRef",
    }
    rust_target_match = re.search(
        r"const\s+MULTIPLEX_TARGET_PUBLIC_FIELDS\s*:\s*&\[&str\]\s*=\s*&\[(.*?)\];",
        bench,
        re.S,
    )
    if rust_target_match is None:
        error("multiplex: Rust target-level public allowlist disappeared")
    else:
        rust_target_fields = set(re.findall(r'"([^"]+)"', rust_target_match.group(1)))
        if rust_target_fields != expected_public_target_fields:
            error(
                "multiplex: Rust public target allowlist drifted: "
                f"unexpected={sorted(rust_target_fields - expected_public_target_fields)}, "
                f"missing={sorted(expected_public_target_fields - rust_target_fields)}"
            )

    target_ts_match = re.search(r"targets:\s*\{(.*?)\}\[\];", transport, re.S)
    if target_ts_match is None:
        error("multiplex: TypeScript target request block disappeared")
    else:
        ts_target_fields = set(
            re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\??\s*:", target_ts_match.group(1), re.M)
        )
        if ts_target_fields != expected_public_target_fields:
            error(
                "multiplex: TypeScript/Rust public target fields drifted: "
                f"unexpected={sorted(ts_target_fields - expected_public_target_fields)}, "
                f"missing={sorted(expected_public_target_fields - ts_target_fields)}"
            )

    multiplex_tests = (ROOT / "tools/tests/test_multiplex.py").read_text(encoding="utf-8")
    multiplex_orchestration_tests = (ROOT / "tools/tests/test_multiplex_orchestration.py").read_text(encoding="utf-8")
    multiplex_wrapper = (ROOT / "tools/src/pcr_tools/__main__.py").read_text(encoding="utf-8")
    multiplex_schema = (ROOT / "web/src/lib/api/types.ts").read_text(encoding="utf-8")
    multiplex_ui = (ROOT / "web/src/components/design/multiplex-result.tsx").read_text(encoding="utf-8")
    multiplex_targets = (ROOT / "web/src/lib/projects/multiplex-targets.ts").read_text(encoding="utf-8")
    atlas_tools = (ROOT / "knowledge/atlas/engines/flanking-pair/01-tools.md").read_text(encoding="utf-8")
    for rel, source, marker in (
        ("tools/src/pcr_tools/multiplex.py", multiplex_text, '"constraint_scope": "shared" if constraints_are_shared else "per-target"'),
        ("tools/src/pcr_tools/multiplex.py", multiplex_text, '"constraints": dict(constraint_contract)'),
        ("tools/tests/test_multiplex.py", multiplex_tests, "test_multiplex_refuses_target_fields_the_set_optimizer_cannot_represent"),
        ("tools/tests/test_multiplex.py", multiplex_tests, "test_multiplex_preserves_target_specific_constraint_provenance"),
        ("tools/tests/test_multiplex.py", multiplex_tests, "test_multiplex_refuses_mixed_computational_provenance"),
        ("tools/tests/test_multiplex.py", multiplex_tests, "test_multiplex_reports_tube_partition_as_bounded_heuristic"),
        ("tools/src/pcr_tools/multiplex.py", multiplex_text, "same computational provenance"),
        ("tools/src/pcr_tools/multiplex.py", multiplex_text, '"pcrstudio-exact-lexicographic-branch-and-bound"'),
        ("web/src/lib/api/types.ts", multiplex_schema, 'constraint_scope: z.enum(["shared", "per-target"])'),
        ("web/src/lib/api/types.ts", multiplex_schema, '"explicit-target-tube-identities"'),
        ("web/src/components/design/multiplex-result.tsx", multiplex_ui, "target-specific constraint envelopes were preserved per target"),
        ("web/src/components/design/multiplex-result.tsx", multiplex_ui, "Per-target design constraints"),
        ("web/src/components/design/multiplex-result.tsx", multiplex_ui, "canonical worker order sheet"),
        ("web/src/components/design/multiplex-result.tsx", multiplex_ui, "No global tube-partition optimum is claimed."),
        ("web/src/components/design/multiplex-result.tsx", multiplex_ui, "Inclusivity panel provenance:"),
        ("web/src/components/design/multiplex-result.tsx", multiplex_ui, "Exclusion-panel provenance:"),
        ("tools/src/pcr_tools/__main__.py", multiplex_wrapper, "def _multiplex_assay_identity("),
        ("tools/src/pcr_tools/__main__.py", multiplex_wrapper, "same assay/module identity"),
        ("tools/src/pcr_tools/__main__.py", multiplex_wrapper, "def _multiplex_resolved_parameters("),
        ("tools/src/pcr_tools/__main__.py", multiplex_wrapper, "zip(request_targets, result_targets, strict=True)"),
        ("tools/tests/test_multiplex_orchestration.py", multiplex_orchestration_tests, "test_multiplex_wrapper_resolves_module_identity_from_target_assays"),
        ("tools/tests/test_multiplex_orchestration.py", multiplex_orchestration_tests, "test_multiplex_wrapper_refuses_mixed_target_module_identity"),
        ("tools/tests/test_multiplex_orchestration.py", multiplex_orchestration_tests, "test_multiplex_resolved_parameters_preserve_per_target_policy_provenance"),
        ("tools/tests/test_multiplex_orchestration.py", multiplex_orchestration_tests, "test_multiplex_resolved_parameters_refuses_missing_worker_contract"),
        ("crates/pcr-server/src/bench.rs", bench, "validate_multiplex_targets_shape(object)?"),
        ("web/src/lib/projects/actions.ts", actions, "fromRna must be `true` when supplied by the multiplex form."),
        ("web/src/lib/projects/multiplex-targets.ts", multiplex_targets, "must be a finite number."),
        ("knowledge/atlas/engines/flanking-pair/01-tools.md", atlas_tools, "deterministic fewest-candidates-first chunking heuristic"),
        ("crates/pcr-server/src/bench.rs", bench, "validate_multiplex_target_fields(index, entry)?"),
        ("crates/pcr-server/src/bench.rs", bench, "fromRna must be a boolean when supplied"),
    ):
        if marker not in source:
            error(f"multiplex: pre-Linux fail-closed/provenance guard lost marker in {rel}: {marker}")

    result_ui = (ROOT / "web/src/components/design/design-result.tsx").read_text(encoding="utf-8")
    if "Pair-level generic cycling is intentionally absent." not in result_ui:
        error("flanking-pair: result UI lost the no-invented-generic-cycling boundary")

