"""Scientific static-audit checks."""
from __future__ import annotations

from .common import *  # noqa: F403

def audit_toolchain_contract_parity() -> None:
    manifest = json.loads((ROOT / "knowledge/atlas/contracts/toolchain-manifest.json").read_text(encoding="utf-8"))
    tool_contract = json.loads((ROOT / "knowledge/runtime/tool-contracts.generated.json").read_text(encoding="utf-8"))
    canonical_tools = tool_contract.get("tools", {})
    manifest_by_id = {item["tool_id"]: item for item in manifest.get("tools", [])}
    expected_scopes = {
        "primer3_core": "embedded-package",
        "primer3_py": "embedded-package",
        "mfeprimer": "local",
        "ncbi_blast_plus": "local",
        "mafft": "local",
        "primerpooler": "local",
        "primalscheme3": "local",
        "viennarna": "optional-package",
        "pydna": "local",
        "primer_blast": "remote-reference",
        "nupack4": "manual-reference",
        "olivar": "external-managed",
    }
    for tool_id, scope in expected_scopes.items():
        item = manifest_by_id.get(tool_id)
        if item is None:
            error(f"toolchain manifest is missing {tool_id}")
            continue
        if item.get("execution_scope") != scope:
            error(f"toolchain manifest scope drift for {tool_id}: expected {scope}")
        runtime_row = canonical_tools.get(tool_id)
        if not isinstance(runtime_row, dict) or runtime_row.get("execution_scope") != scope:
            error(f"generated runtime ToolSpec scope/version declaration drift for {tool_id}")
        elif str(runtime_row.get("version") or "") != str((item.get("version_policy") or {}).get("version") or ""):
            error(f"generated runtime ToolSpec version drift for {tool_id}")
        canonical_requirement = str(runtime_row.get("readiness_requirement") or "")
        if not canonical_requirement:
            error(f"generated runtime ToolSpec readiness requirement missing for {tool_id}")

    provision_rows = tomllib.loads(
        (ROOT / "contracts/tools.toml").read_text(encoding="utf-8")
    ).get("tool", [])
    for row in provision_rows:
        tool_id = str(row.get("id") or "")
        if not row.get("provision_id"):
            continue
        digest = str(row.get("provision_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            error(f"provisioned tool {tool_id} must have an exact lowercase SHA-256 pin")
        urls = [str(row.get("provision_url") or ""), *map(str, row.get("provision_mirror_urls") or [])]
        if any(not url.startswith("https://") for url in urls):
            error(f"provisioned tool {tool_id} has a non-HTTPS source or mirror")
        runtime_row = canonical_tools.get(tool_id)
        if isinstance(runtime_row, dict) and runtime_row.get("provision_sha256") != digest:
            error(f"generated runtime artifact pin drifted for {tool_id}")
        if isinstance(runtime_row, dict) and runtime_row.get("provision_mirror_urls", []) != list(row.get("provision_mirror_urls") or []):
            error(f"generated runtime mirror list drifted for {tool_id}")

    science = json.loads((ROOT / "tools/scientific-tools.json").read_text(encoding="utf-8"))
    for tool_id, item in science.get("tools", {}).items():
        filename = str(item.get("wheel_filename") or "")
        digest = str(item.get("wheel_sha256") or "")
        if not filename.endswith(".whl"):
            error(f"scientific tool {tool_id} lacks an exact wheel filename")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            error(f"scientific tool {tool_id} lacks a valid wheel SHA-256")
    provision = (ROOT / "scripts/provision-tools.py").read_text(encoding="utf-8")
    for token in ("get_verified_pypi_wheel", "published_hash", "Downloaded scientific wheel", "--extra", "folding", "safe_extract_tar"):
        if token not in provision:
            error(f"scientific Python provisioning is missing fail-closed artifact check: {token}")
    runtime_tool = (ROOT / "tools/src/pcr_tools/tool_runtime.py").read_text(encoding="utf-8")
    for token in ("PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256", "approved_matches_actual", "pass Linux qualification"):
        if token not in runtime_tool:
            error(f"strict scientific environment approval guard is missing: {token}")

def audit_scientific_integrity() -> None:
    """Fail the release when convenience can silently outrank scientific meaning."""
    policy_json = ROOT / "knowledge/runtime/scientific-integrity-policy.json"
    policy_md = ROOT / "knowledge/runtime/SCIENTIFIC-INTEGRITY-POLICY.md"
    implementation = ROOT / "tools/src/pcr_tools/scientific_integrity.py"
    for path in (policy_json, policy_md, implementation):
        if not path.is_file():
            error(f"missing scientific-integrity artifact: {path.relative_to(ROOT)}")
    if not all(path.is_file() for path in (policy_json, implementation)):
        return

    policy = json.loads(policy_json.read_text(encoding="utf-8"))
    if policy.get("default_mode") != "strict" or policy.get("fail_closed") is not True:
        error("scientific-integrity policy must default to strict/fail-closed")
    integrity_text = implementation.read_text(encoding="utf-8")
    if 'os.environ.get(_ENV, "strict")' not in integrity_text:
        error("scientific-integrity runtime no longer defaults to strict")

    tool_runtime_text = (ROOT / "tools/src/pcr_tools/tool_runtime.py").read_text(encoding="utf-8")
    external_text = (ROOT / "tools/src/pcr_tools/external_validation.py").read_text(encoding="utf-8")
    align_text = (ROOT / "tools/src/pcr_tools/align.py").read_text(encoding="utf-8")
    if "if scientific_strict():\n        return \"strict\"" not in tool_runtime_text:
        error("scientific strict no longer dominates PCRSTUDIO_TOOLCHAIN_MODE")
    if "if scientific_strict():\n        return \"strict\"" not in external_text:
        error("scientific strict no longer dominates PCRSTUDIO_EXTERNAL_VALIDATION")
    if '"database_paths"' in external_text:
        error("client/persisted external-validator evidence exposes host database paths")
    alignment_guards = (
        'run_tool(',
        '"mafft",',
        'operation_id="align_panel"',
        'version_matches_contract',
        'another aligner cannot be substituted implicitly',
    )
    if any(token not in align_text for token in alignment_guards):
        error("alignment path bypasses the centralized pinned-MAFFT toolchain contract")

    policy_invariant_tokens = (
        "Executable named-assay runtime does not allow anonymous reaction-condition override",
        "This is a named-assay identity invariant, not a Strict-mode preference",
        "Resolve purpose without a hidden ``general`` fallback in any executable mode",
        "Executable worker runtime requires an explicit named `assay.id`",
        "Release orchestration requires the server-injected canonical profile authority",
    )
    if any(token not in integrity_text for token in policy_invariant_tokens):
        error("development policy can weaken a named-assay scientific identity invariant")

    active_files = [
        ROOT / "tools/src/pcr_tools/runtime_contract.py",
        ROOT / "tools/src/pcr_tools/tool_runtime.py",
        ROOT / "tools/src/pcr_tools/external_validation.py",
        ROOT / "tools/src/pcr_tools/primalscheme_adapter.py",
        ROOT / "tools/src/pcr_tools/settings.py",
        ROOT / "tools/src/pcr_tools/pipeline.py",
        ROOT / "tools/src/pcr_tools/probe.py",
    ]
    forbidden = (
        "controlled_constraint_relaxation",
        "primalscheme_to_internal_only_in_auto_mode",
        "relax_search_window_before_probe_quality",
        "validated-user-override",
        "allowed-with-validation",
        "controlled-fallback-if-needed",
    )
    for path in active_files:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                error(f"scientific shortcut vocabulary remains active in {path.relative_to(ROOT)}: {needle}")

    for path in (ROOT / "tools/src/pcr_tools").rglob("*.py"):
        if is_generated(path): continue
        if "zip(" in path.read_text(encoding="utf-8") and "strict=False" in path.read_text(encoding="utf-8"):
            error(f"silent zip truncation remains in scientific runtime: {path.relative_to(ROOT)}")

    profiles = profile_map()
    multiplex_modules = {module for module, row in profiles.items() if "multiplex" in row.get("modifiers", [])}
    if multiplex_modules != {"standard-pcr", "colony-pcr", "species-specific-pcr"}:
        error(f"multiplex capability overclaim/underclaim: {sorted(multiplex_modules)}")
    for module_id, row in profiles.items():
        defaults = row.get("defaults", {})
        if not defaults.get("polymerase"):
            error(f"{module_id}: no explicit polymerase/thermodynamic context in active profile")
        purposes = list(defaults.get("purposes", []))
        if len(purposes) > 1 and not defaults.get("defaultPurpose"):
            error(f"{module_id}: multiple purposes but no explicit defaultPurpose")
    species = profiles.get("species-specific-pcr", {})
    if species.get("requires") != ["background", "inclusivity"]:
        error("species-specific PCR must require both target inclusivity and exclusion background")

    validation_path = ROOT / "tools/src/pcr_tools/validation_plan.py"
    tree = ast.parse(validation_path.read_text(encoding="utf-8"), filename=str(validation_path))
    plan_keys: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "PLANS" and isinstance(node.value, ast.Dict):
            plan_keys = {ast.literal_eval(key) for key in node.value.keys}
    if plan_keys != set(profiles):
        error(f"wet-lab validation plans do not cover 21/21 modules: {sorted(set(profiles) ^ plan_keys)}")

    _modules, _contracts, bindings = parse_runtime_contract()
    for engine in ("junction-primers", "mutagenic-pair", "outward-pair"):
        pydna = next((row for row in bindings[engine] if row["tool_id"] == "pydna"), None)
        if not pydna or pydna["purposes"] != ["independent_pcr_product_simulation"]:
            error(f"{engine}: pydna adapter capability is overclaimed beyond current PCR-product simulation")

    fields = (ROOT / "web/src/components/design/engine-fields.tsx").read_text(encoding="utf-8")
    for tag in re.findall(r"<select\\b[^>]*>", fields, re.S):
        if "id=" not in tag and "aria-label=" not in tag and "aria-labelledby=" not in tag:
            error("engine-fields.tsx contains a select without an accessible programmatic name")
            break

    pipeline_text = (ROOT / "tools/src/pcr_tools/pipeline.py").read_text(encoding="utf-8")
    if 'Component(name="Template accessibility"' in pipeline_text:
        error("optional ViennaRNA template accessibility leaked back into deterministic flanking-pair ranking")
    if 'parts["accessibility"] = None' not in pipeline_text:
        error("template accessibility is no longer explicitly excluded from the composite quality score")
    if 'entry.pop("cycling", None)' not in pipeline_text or 'entry["annealing_temperature"] = None' not in pipeline_text:
        error("flanking pairs can regain fabricated pair-level cycling or bench annealing temperature")
    pair_schema_text = (ROOT / "web/src/lib/api/types.ts").read_text(encoding="utf-8")
    pair_schema_match = re.search(r"export const primerPairSchema = z\.object\(\{(.*?)\n\}\);", pair_schema_text, re.S)
    if pair_schema_match and re.search(r"\bcycling\s*:", pair_schema_match.group(1)):
        error("current flanking pair schema still accepts historical pair-level cycling")

    rt_text = (ROOT / "tools/src/pcr_tools/rt.py").read_text(encoding="utf-8")
    for obsolete in ("CELSIUS =", "SECONDS =", "development-only-generic-starting-point"):
        if obsolete in rt_text:
            error(f"generic RT helper regained fabricated protocol authority: {obsolete!r}")
    if '"hold": None' not in rt_text or '"one_step": None' not in rt_text:
        error("generic RT helper no longer records an unresolved chemistry handoff")

    probe_text = (ROOT / "tools/src/pcr_tools/probe.py").read_text(encoding="utf-8")
    if 'chosen.assay_id != "qpcr-probe"' not in probe_text:
        error("probe named overlay can again bypass canonical qpcr-probe assay identity")
    mgb_gate_markers = (
        'selected_protocol.get("execution_status") != "executable"',
        'selected_protocol.get("chemistry") == "mgb-nfq"',
        'selected_protocol.get("execution_status") == "external-authority-required"',
        'mode not in {"export-candidates", "import-results"}',
        'authority_id=str(protocol.get("authority_exchange_id")',
        'exchange=mgb_exchange(cands,authority_id=authority_id)',
        'apply_mgb_import(cands,request.get("probe_mgb_authority_payload"),authority_id=authority_id)',
        '"tm_source":"external-mgb-authority"',
    )
    probe_compact = re.sub(r"\s+", "", probe_text)
    if any(marker.replace(" ", "") not in probe_compact for marker in mgb_gate_markers):
        error("TaqMan MGB can again bypass the declared external-authority candidate exchange")
    if '"status": "orderable" if orderable else "research-only-unbound-probe-engine"' not in probe_text:
        error("unbound pair-and-probe research can again lose its explicit non-orderable status")
    if '"order_sheet": candidate_order_sheet if orderable else []' not in probe_text:
        error("unbound pair-and-probe research can again expose supplier order lines")
    probe_schema_text = (ROOT / "web/src/lib/api/types.ts").read_text(encoding="utf-8")
    if "orderability: orderabilitySchema.optional()" not in probe_schema_text:
        error("probe API boundary can again drop non-orderability evidence")
    probe_ui_text = (ROOT / "web/src/components/design/probe-result.tsx").read_text(encoding="utf-8")
    if "Diagnostic design — do not order" not in probe_ui_text:
        error("probe result UI can again hide the non-orderable research boundary")
    if "historical-result-orderability-not-recorded" not in probe_ui_text:
        error("historical successful probe results can again be interpreted as supplier-ready when orderability is absent")
    report_text = (ROOT / "web/src/lib/projects/report-markdown.ts").read_text(encoding="utf-8")
    if "historical-result-orderability-not-recorded" not in report_text:
        error("portable reports can again omit the fail-closed orderability boundary for historical probe results")

    discriminate_text = (ROOT / "tools/src/pcr_tools/discriminate.py").read_text(encoding="utf-8")
    if "the worker does not synthesize assay identity or numeric defaults from geometry alone" not in discriminate_text:
        error("KASP geometry can again synthesize assay/profile authority")
    if 'if geometry == "tetra":\n        if tetra_min_separation is None:' not in discriminate_text:
        error("Tetra-ARMS can again run without declared electrophoresis resolution context")

    loop_text = (ROOT / "tools/src/pcr_tools/loop_set.py").read_text(encoding="utf-8") + "\n" + (ROOT / "tools/src/pcr_tools/lamp_geometry.py").read_text(encoding="utf-8")
    if "requires a separately named, versioned LAMP profile" not in loop_text:
        error("LAMP source-envelope widening is no longer tied to separate versioned profile authority")

    fields_text = fields
    for marker in ('modules: ["long-range-pcr"]', 'id="longRangeProtocol"', 'value("longRangeProtocol")'):
        if marker not in fields_text:
            error(f"long-range protocol identity is not reachable in the assay UI: missing {marker!r}")
    result_text = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in ("web/src/components/design/design-result.tsx", "web/src/components/design/protocol-result-cards.tsx"))
    if 'protocol.kind === "long-range-pcr"' not in result_text:
        error("long-range named protocol has no dedicated result renderer")
    if "Pair-level generic cycling is intentionally absent" not in result_text:
        error("flanking result UI no longer preserves the no-fabricated-protocol boundary")
    if (ROOT / "web/src/components/design/cycling-protocol.tsx").exists():
        error("obsolete generic pair-level cycling component remains in current tree")
    order_actions = (ROOT / "web/src/components/design/order-actions.tsx").read_text(encoding="utf-8")
    if 'aria-label="Print lab protocol sheet"' in order_actions:
        error("generic order actions overclaim a lab protocol that may not have named bench authority")
    result_overview = (ROOT / "web/src/components/design/result-overview.tsx").read_text(encoding="utf-8")
    for marker in ("Recommended computational design", "not a universal guarantee of amplification", "Wet-lab evidence"):
        if marker not in result_overview:
            error(f"result overview lost scientific claim-boundary wording: {marker!r}")

    schema = (ROOT / "web/src/lib/api/types.ts").read_text(encoding="utf-8")
    for marker in ("validation: runtimeValidationPlanSchema.optional()", "scientific_integrity: scientificIntegritySchema.optional()"):
        if marker not in schema:
            error(f"frontend result schemas can drop scientific provenance: missing {marker!r}")

def audit_tool_deployment_contract() -> None:
    science = json.loads((ROOT / "tools/scientific-tools.json").read_text(encoding="utf-8"))["tools"]
    expected_science = {
        "primalscheme3": ("3.3.0", "4ac2455c6071ddef40fd5bed881ad9c129f8590b66e7bf6b73462a0ea9aad30e"),
        "pydna": ("5.5.16", "f89c0787da7f405286c5d4fa8a827bbefbb09c7da382860834d7103dddb452aa"),
    }
    for tool_id, (version, wheel_sha) in expected_science.items():
        spec = science.get(tool_id, {})
        if spec.get("version") != version:
            error(f"{tool_id} scientific pin is not {version}")
        if spec.get("wheel_sha256") != wheel_sha:
            error(f"{tool_id} wheel SHA-256 drifted from the audited upstream artifact")

    pyproject = tomllib.loads((ROOT / "tools/pyproject.toml").read_text(encoding="utf-8"))
    core_deps = "\n".join(pyproject["project"].get("dependencies", []))
    if "pydna" in core_deps.lower() or "primalscheme" in core_deps.lower():
        error("optional scientific tools leaked back into the frozen worker dependency list")
    lock = (ROOT / "tools/uv.lock").read_text(encoding="utf-8")
    if 'name = "pydna"' in lock or 'name = "primalscheme3"' in lock:
        error("worker uv.lock contains isolated scientific tools")

    provision = (ROOT / "scripts/provision-tools.py").read_text(encoding="utf-8")
    required_markers = (
        "science-venv", "PCRSTUDIO_PYDNA_PYTHON", "PCRSTUDIO_PRIMALSCHEME3",
        "toolchain.env", "get_verified_pypi_wheel", "published_hash",
        "safe_extract_tar", "mfeprimer-4.5.1-linux-amd64.gz",
        "ncbi-blast-2.17.0-x64-linux.tar.gz", "mafft-7.526-linux.tgz",
        "PrimerPooler", '"PCRSTUDIO_SCIENTIFIC_POLICY": "strict"',
        '"PCRSTUDIO_TOOLCHAIN_MODE": "strict"', '"PCRSTUDIO_EXTERNAL_VALIDATION": "strict"',
    )
    for marker in required_markers:
        if marker not in provision:
            error(f"Linux provision-tools.py is missing hardened deployment marker {marker!r}")
    if re.search(r"(?i)\b[A-Z]:[\\/][^\r\n]*PCRStudio", provision):
        error("Linux provision-tools.py contains a machine-specific drive-letter path")
    for marker in (
        "def shell_env_assignment(",
        "shlex.quote(value)",
        "def read_optional_tool_config(",
        'required = {"schema_version", "tool_id", "version", "executable", "sha256"}',
        'actual = sha256(executable)',
    ):
        if marker not in provision:
            error(f"scientific toolchain shell-environment serialization lost marker {marker!r}")
    if "read_optional_tool_env(" in provision or "olivar.env" in provision:
        error("ad-hoc Olivar env-fragment parsing was reintroduced into provisioning")
    configure_olivar = (ROOT / "scripts/configure-olivar-linux.py").read_text(encoding="utf-8")
    for marker in (
        'CONFIG = LOCAL / "olivar.json"',
        '"schema_version": SCHEMA_VERSION',
        'run_bounded_text(',
        'stdout_limit=64 * 1024',
        'temporary.replace(CONFIG)',
    ):
        if marker not in configure_olivar:
            error(f"managed Olivar binding lost structured/bounded marker {marker!r}")
    qualification = (ROOT / "scripts/run-linux-qualification.py").read_text(encoding="utf-8")
    if "olivar.env" in qualification or "olivar.json" not in qualification:
        error("Linux qualification drifted from the structured Olivar binding contract")

    tools_toml = tomllib.loads((ROOT / "contracts/tools.toml").read_text(encoding="utf-8"))
    canonical = {str(row.get("id")): row for row in tools_toml.get("tool", [])}
    expected_native = {
        "mfeprimer": ("4.5.1", "mfeprimer-4.5.1-linux-amd64.gz"),
        "ncbi_blast_plus": ("2.17.0", "x64-linux"),
        "mafft": ("7.526", "mafft-7.526-linux.tgz"),
        "primerpooler": ("1.89", "PrimerPooler"),
    }
    for tool_id, (version, artifact_marker) in expected_native.items():
        row = canonical.get(tool_id) or {}
        if str(row.get("version") or "") != version:
            error(f"Linux native tool pin drifted: {tool_id} {version}")
        joined = json.dumps(row, sort_keys=True)
        if artifact_marker not in joined:
            error(f"Linux native artifact marker drifted for {tool_id}: {artifact_marker}")

    configure = (ROOT / "scripts/configure-specificity-database.py").read_text(encoding="utf-8")
    for marker in (
        "staging-{os.getpid()}", "duplicate record identifier", "index_artifacts",
        "ambiguous_bases", "staging.rename(dest)", "backup.rename(dest)",
        "schema_version':'1.1.0",
    ):
        if marker not in configure:
            error(f"configure-specificity-database.py is missing hardened deployment marker {marker!r}")

    runtime = (ROOT / "tools/src/pcr_tools/tool_runtime.py").read_text(encoding="utf-8")
    for marker in ("manifest_schema == \"1.1.0\"", "indexed_fasta", "index_artifacts_match"):
        if marker not in runtime:
            error(f"tool_runtime database verification is missing {marker!r}")

    process_boundary = (ROOT / "tools/src/pcr_tools/process_boundary.py").read_text(encoding="utf-8")
    for marker in (
        "class ProcessOutputLimitExceeded",
        "class ProcessTransportError",
        "def _write_all(",
        "os.killpg(process.pid, signal.SIGKILL)",
        "if exceeded_event.is_set():",
        "_terminate_group(process)",
        "reader thread did not reach EOF after child termination",
    ):
        if marker not in process_boundary:
            error(f"scientific subprocess boundary lost fail-closed lifecycle marker {marker!r}")
    process_tree = ast.parse(process_boundary, filename="tools/src/pcr_tools/process_boundary.py")
    for node in ast.walk(process_tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg in {"capture_output", "shell"} and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                error("scientific process boundary regressed to unbounded/shell subprocess execution")

def audit_worker_scientific_environment_contract() -> None:
    worker = (ROOT / "crates/pcr-worker-client/src/lib.rs").read_text(encoding="utf-8")
    required = (
        "PCRSTUDIO_SCIENTIFIC_POLICY",
        "PCRSTUDIO_EXTERNAL_VALIDATION",
        "PCRSTUDIO_TOOLCHAIN_MODE",
        "PCRSTUDIO_MFEPRIMER_DATABASES_SCOPE",
        "PCRSTUDIO_MFEPRIMER_DATABASES_MANIFEST",
        "PCRSTUDIO_BLAST_DATABASE_SCOPE",
        "PCRSTUDIO_BLAST_DATABASE_MANIFEST",
        "PCRSTUDIO_PYDNA_PYTHON",
        "PCRSTUDIO_PYDNA_PYTHON_SHA256",
        "PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE",
        "PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE_SHA256",
        "PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256",
        "MPLCONFIGDIR",
    )
    for name in required:
        if f'"{name}"' not in worker:
            error(f"Rust worker drops scientific/tool provenance environment variable {name}")


def audit_scientific_authority_provenance() -> None:
    """Every canonical scientific authority must be content-addressed and run-visible."""
    manifest_path = ROOT / "contracts/scientific-authorities.json"
    if not manifest_path.is_file():
        error("missing canonical scientific-authority manifest")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chemistry_dir = ROOT / "contracts/chemistry"
    actual = sorted(
        p.name for p in chemistry_dir.iterdir()
        if p.is_file() and p.suffix in {".json", ".toml"}
    )
    declared = sorted(str(x) for x in manifest.get("chemistry_files", []))
    if declared != actual:
        error(f"scientific-authority chemistry coverage drifted: declared={len(declared)} actual={len(actual)}")
    if len(actual) != 23:
        error(f"Generation-1 chemistry authority count drifted from audited 23 to {len(actual)}")
    modules = manifest.get("modules", {})
    profiles = profile_map()
    if set(modules) != set(profiles):
        error("scientific-authority manifest does not cover the exact canonical module set")
    generated_paths = (
        ROOT / "tools/src/pcr_tools/data/scientific-authority-registry.generated.json",
        ROOT / "web/src/lib/scientific-authority-registry.generated.json",
        ROOT / "knowledge/runtime/scientific-authority-registry.generated.json",
    )
    if any(not p.is_file() for p in generated_paths):
        error("scientific-authority generated projections are incomplete")
        return
    rendered = [p.read_text(encoding="utf-8") for p in generated_paths]
    if len(set(rendered)) != 1:
        error("scientific-authority generated projections drift across worker/web/runtime")
    registry = json.loads(rendered[0])
    if registry.get("chemistry_file_count") != len(actual):
        error("scientific-authority registry does not fingerprint every chemistry/corpus file")
    for name in actual:
        row = registry.get("chemistry_files", {}).get(name, {})
        if row.get("canonical_sha256") != sha256(chemistry_dir / name):
            error(f"scientific-authority hash drift: contracts/chemistry/{name}")
    snapshots_path = ROOT / "knowledge/sources/flanking-source-snapshots.json"
    snapshots = json.loads(snapshots_path.read_text(encoding="utf-8")) if snapshots_path.is_file() else {}
    flanking = tomllib.loads((chemistry_dir / "flanking-protocols.toml").read_text(encoding="utf-8"))
    provenance = flanking.get("provenance", {})
    snapshot_rows = snapshots.get("sources", {}) if isinstance(snapshots, dict) else {}
    if len(provenance) < 61:
        error(f"flanking source provenance regressed below the audited 61-source baseline: {len(provenance)}")
    if len(snapshot_rows) != len(provenance):
        error(f"flanking source snapshot coverage is incomplete: provenance={len(provenance)} snapshots={len(snapshot_rows)}")
    for source_id, row in provenance.items():
        if row.get("snapshot_status") != "canonical-claim-snapshot-pinned":
            error(f"{source_id}: flanking source is not claim-snapshotted")
        if row.get("snapshot_registry") != "knowledge/sources/flanking-source-snapshots.json":
            error(f"{source_id}: flanking source snapshot registry is missing")
        snap = snapshot_rows.get(source_id, {})
        if row.get("claim_snapshot_sha256") != snap.get("claim_snapshot_sha256"):
            error(f"{source_id}: flanking claim snapshot digest drift")
    orchestrator = (ROOT / "tools/src/pcr_tools/orchestrator.py").read_text(encoding="utf-8")
    fingerprint = (ROOT / "tools/src/pcr_tools/fingerprints.py").read_text(encoding="utf-8")
    frontend = (ROOT / "web/src/lib/api/types.ts").read_text(encoding="utf-8")
    for marker, source, label in (
        ('provenance["scientific_authorities"] = scientific_authorities_for_module(module_id)', orchestrator, "worker orchestration"),
        ('"scientific_authorities": provenance.get("scientific_authorities")', fingerprint, "toolchain fingerprint"),
        ('scientific_authorities: z.array(scientificAuthorityIdentitySchema).optional()', frontend, "frontend provenance schema"),
    ):
        if marker not in source:
            error(f"scientific authority provenance can be dropped at {label}")


def audit_capability_truth() -> None:
    """Current documentation must agree with canonical CURRENT capabilities."""
    truth_path = ROOT / "contracts/capability-truth.json"
    if not truth_path.is_file():
        error("missing current capability truth contract")
        return
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    for check in truth.get("checks", []):
        check_id = str(check.get("id", "unknown"))
        for rel in check.get("files", []):
            path = ROOT / rel
            if not path.is_file():
                error(f"{check_id}: current truth file missing: {rel}")
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            required = [str(x) for x in check.get("required_any", [])]
            if required and not any(marker in text for marker in required):
                error(f"{check_id}: {rel} lacks every required CURRENT capability marker")
            for marker in check.get("forbidden", []):
                if str(marker) in text:
                    error(f"{check_id}: {rel} contains superseded capability claim: {marker}")
