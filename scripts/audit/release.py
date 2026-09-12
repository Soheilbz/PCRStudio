"""Release static-audit checks."""
from __future__ import annotations

from .common import *  # noqa: F403

def audit_assay_page_architecture() -> None:
    """page architecture: gives every released assay a specialised page shape under one grammar."""
    page = (ROOT / "web/src/components/design/page-plan.ts").read_text(encoding="utf-8")
    workspace = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "web/src/components/project/workspace.tsx",
            "web/src/components/project/workspace-parts.tsx",
            "web/src/components/project/workspace-evidence.tsx",
        )
    )

    token_to_step = {
        "SEQUENCE": "target",
        "ASSAY_DESIGN": "design",
        "STRATEGY": "strategy",
        "NUMBERS": "constraints",
        "VECTOR": "vector",
        "TUBE": "reaction",
        "ELSEWHERE": "specificity",
        "VALIDATION": "validation",
        "CONSTRUCT": "construct",
        "LAST_LOOK": "review",
    }

    # Slice PagePlan entries by their top-level key lines instead of trying to
    # brace-balance TypeScript. Template literals and JSX-like prose can contain
    # braces that are irrelevant to the object boundary and made the older audit
    # parser merge adjacent module plans.
    plans_start = page.find("const PLANS: Record<string, PageCopy> = {")
    plan_entries: list[tuple[str, int]] = []
    if plans_start >= 0:
        for match in re.finditer(r'(?m)^  (?:"([^"]+)"|([A-Za-z_][A-Za-z0-9_-]*)): \{', page[plans_start:]):
            module_id = match.group(1) or match.group(2)
            plan_entries.append((module_id, plans_start + match.start()))

    def plan_block(module_id: str) -> str:
        for index, (candidate, start) in enumerate(plan_entries):
            if candidate != module_id:
                continue
            end = plan_entries[index + 1][1] if index + 1 < len(plan_entries) else page.find("\n};", start)
            if end < 0:
                end = len(page)
            return page[start:end]
        return ""

    expected = {
        "standard-pcr": ["target", "constraints", "reaction", "specificity", "review"],
        "long-range-pcr": ["target", "constraints", "reaction", "specificity", "review"],
        "colony-pcr": ["target", "strategy", "constraints", "reaction", "specificity", "review"],
        "nested-pcr": ["target", "design", "reaction", "specificity", "review"],
        "inverse-pcr": ["target", "strategy", "constraints", "reaction", "specificity", "review"],
        "qpcr-sybr": ["target", "constraints", "reaction", "specificity", "validation", "review"],
        "qpcr-probe": ["target", "design", "constraints", "reaction", "specificity", "review"],
        "digital-pcr": ["target", "constraints", "reaction", "specificity", "validation", "review"],
        "arms-pcr": ["target", "design", "constraints", "reaction", "specificity", "review"],
        "tetra-primer-arms": ["target", "design", "constraints", "reaction", "specificity", "validation", "review"],
        "kasp": ["target", "design", "constraints", "reaction", "specificity", "review"],
        "species-specific-pcr": ["target", "constraints", "reaction", "specificity", "review"],
        "lamp": ["target", "design", "reaction", "specificity", "validation", "review"],
        "rpa": ["target", "constraints", "reaction", "specificity", "validation", "review"],
        "universal-primers": ["target", "design", "constraints", "reaction", "review"],
        "tiled-scheme": ["target", "strategy", "design", "constraints", "reaction", "review"],
        "race": ["target", "design", "constraints", "reaction", "specificity", "review"],
        "sequencing-primer": ["target", "design", "constraints", "reaction", "specificity", "review"],
        "gibson-assembly": ["design", "constraints", "reaction", "construct", "review"],
        "restriction-cloning": ["target", "vector", "design", "reaction", "specificity", "construct", "review"],
        "site-directed-mutagenesis": ["target", "design", "reaction", "construct", "review"],
    }
    for module_id, wanted in expected.items():
        block = plan_block(module_id)
        if not block:
            error(f"page architecture: page-plan block missing for {module_id}")
            continue
        tokens = re.findall(r"step\(\s*([A-Z_]+)", block)
        actual = [token_to_step[token] for token in tokens if token in token_to_step]
        if actual != wanted:
            error(f"page architecture: {module_id} step architecture drifted: expected {wanted}, got {actual}")

    contracts = json.loads((ROOT / "knowledge/runtime/module-contracts.json").read_text(encoding="utf-8"))["modules"]
    if set(expected) != set(contracts):
        error("page architecture: page architecture does not cover the exact canonical 21-module registry")

    for step_id, component in (
        ("design", "AssayDesignStep"),
        ("strategy", "StrategyStep"),
        ("vector", "VectorStep"),
        ("validation", "ValidationEvidenceStep"),
        ("construct", "ConstructStep"),
    ):
        if f'step === "{step_id}"' not in workspace or component not in workspace:
            error(f"page architecture: workspace does not render {step_id} through {component}")
    readiness = (ROOT / "web/src/components/project/workspace-readiness.ts").read_text(encoding="utf-8")
    workspace_and_readiness = workspace + "\n" + readiness
    for marker in (
        'value="two-vector-primers" disabled',
        "unsupportedColonyStrategy",
        'moduleId === "lamp" && text(draft, "assayMode") === "evaluate"',
        "Approx. 95% occupancy interval",
        "Selected MIQE 2.0 evidence coverage",
        "Selected dMIQE run-evidence coverage",
        "LAMP target geometry",
        "Independent external confirmation · manual handoff",
    ):
        if marker not in workspace_and_readiness:
            error(f"page architecture: UI safety/wiring marker missing: {marker!r}")

    # Catalogue-wide ownership guards bind specialised pages to their canonical renderers and readiness projection. These source markers bind
    # specialised pages to their actual renderers and readiness projection.
    required_context = json.loads((ROOT / "web/src/lib/projects/required-context.generated.json").read_text(encoding="utf-8"))["modules"]
    engine_fields = (ROOT / "web/src/components/design/engine-fields.tsx").read_text(encoding="utf-8")
    ownership_expectations = {
        "nested-pcr": {"margin": "design", "shares": "design", "singleTube": "design"},
        "inverse-pcr": {"inverseBranch": "strategy", "enzyme": "strategy"},
        "tetra-primer-arms": {"tetraMinBandSeparationBp": "validation"},
        "universal-primers": {"alignmentMode": "design"},
        "gibson-assembly": {"assemblyProtocol": "reaction", "circular": "design"},
        "site-directed-mutagenesis": {"editAt": "design", "postAmplificationProtocol": "reaction"},
    }
    for module_id, expected_owners in ownership_expectations.items():
        actual = required_context.get(module_id, {}).get("field_owners", {})
        for field, owner in expected_owners.items():
            if actual.get(field) != owner:
                error(f"page architecture: generated required-context ownership drift: {module_id}.{field} expected {owner}")
    for marker in (
        'section: "strategy"',
        '<NestedFields section="design"',
        '<SchemeFields section="strategy"',
        '<AssemblyFields section="design"',
        '<VariantFields section="reaction"',
    ):
        if marker not in engine_fields:
            error(f"page architecture: engine-field ownership marker missing: {marker!r}")

    profiles = tomllib.loads((ROOT / "crates/pcr-core/profiles.toml").read_text(encoding="utf-8"))["profile"]
    digital_profile = next((row for row in profiles if row.get("id") == "digital-pcr"), None)
    if not digital_profile or digital_profile.get("name") != "Digital PCR — EvaGreen / Dye":
        error("release contract: digital-pcr profile lost its explicit dye/EvaGreen Gen1 scope")

    registry_path = ROOT / "tools/src/pcr_tools/data/restriction_enzyme_registry.json"
    if not registry_path.is_file():
        error("release contract: versioned restriction-enzyme registry is missing")
    else:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if registry.get("schema_version") != "1.0.0" or registry.get("registry_id") != "pcrstudio-gen1-restriction-enzyme-registry-v1":
            error("release contract: restriction-enzyme registry identity/schema drifted")
        enzymes = registry.get("enzymes")
        if not isinstance(enzymes, list) or not enzymes:
            error("release contract: restriction-enzyme registry contains no enzymes")
        else:
            names = []
            allowed = set("ACGTRYSWKMBDHVN")
            for row in enzymes:
                if not isinstance(row, dict):
                    error("release contract: restriction-enzyme registry contains a malformed row")
                    continue
                name = str(row.get("name") or "")
                site = str(row.get("site") or "")
                cut = row.get("cuts_after")
                names.append(name)
                if not name or not site or any(base not in allowed for base in site):
                    error(f"release contract: restriction-enzyme registry has invalid identity/site for {name!r}")
                if isinstance(cut, bool) or not isinstance(cut, int) or not 0 <= cut <= len(site):
                    error(f"release contract: restriction-enzyme registry has invalid cut coordinate for {name!r}")
            if len(set(names)) != len(names):
                error("release contract: restriction-enzyme registry contains duplicate names")
        restriction_source = (ROOT / "tools/src/pcr_tools/restriction.py").read_text(encoding="utf-8")
        pipeline = (ROOT / "tools/src/pcr_tools/pipeline.py").read_text(encoding="utf-8")
        if "RESTRICTION_REGISTRY_RESOURCE" not in restriction_source or "_load_enzyme_registry" not in restriction_source:
            error("restriction.py no longer consumes the versioned release contract: enzyme registry")
        if 'restriction_mod.RESTRICTION_REGISTRY.get("registry_id")' not in pipeline:
            error("restriction-cloning result no longer reports the canonical registry identity")

    loop = (ROOT / "tools/src/pcr_tools/loop_set.py").read_text(encoding="utf-8")
    accessibility = (ROOT / "tools/src/pcr_accessibility/__main__.py").read_text(encoding="utf-8")
    frontend_schema = (ROOT / "web/src/lib/api/types.ts").read_text(encoding="utf-8")
    for marker in (
        "_rt_lamp_accessibility",
        'molecule="RNA"',
        '"parameter_authority": "ViennaRNA Turner 2004 RNA"',
    ):
        if marker not in loop:
            error(f"RT-LAMP post-selection accessibility wiring missing {marker!r}")
    for marker in ("params_load_RNA_Turner2004", 'molecule == "RNA"'):
        if marker not in accessibility:
            error(f"RNA accessibility worker missing explicit RNA-model marker {marker!r}")
    if "rna_target_accessibility" not in frontend_schema:
        error("frontend schema can drop release contract: RT-LAMP RNA accessibility evidence")

    configure = (ROOT / "scripts/configure-specificity-database.py").read_text(encoding="utf-8")
    external = (ROOT / "tools/src/pcr_tools/external_validation.py").read_text(encoding="utf-8")
    for marker in ("--mfeprimer-k", "mfeprimer_index_k", "mfeprimer_query_k_policy"):
        if marker not in configure:
            error(f"production MFEprimer database provisioning lost release contract: index-k marker {marker!r}")
    for marker in ("mfeprimer_index_k", "omitted-auto-detect-from-index-header"):
        if marker not in external:
            error(f"MFEprimer evidence no longer preserves release contract: index-k provenance marker {marker!r}")

def audit_expert_release_artifacts() -> None:
    """Expert review artifacts are release contracts, not stale prose."""
    required = {
        "expert": ROOT / "knowledge/reviews/EXPERT-MODULE-AUDIT.json",
        "tools": ROOT / "knowledge/reviews/MODULE-TOOLCHAIN-MATRIX.json",
        "ui": ROOT / "knowledge/reviews/UI-UX-MODULE-AUDIT.json",
        "risks": ROOT / "knowledge/reviews/SCIENTIFIC-RISK-REGISTER.json",
        "backlog": ROOT / "knowledge/reviews/EXPERT-UPGRADE-BACKLOG.json",
        "numeric": ROOT / "knowledge/runtime/numeric-provenance-registry.json",
    }
    for key, path in required.items():
        if not path.is_file():
            error(f"missing expert release artifact {key}: {path.relative_to(ROOT)}")
            return

    docs = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in required.items()}
    generator = ROOT / "scripts/generate-expert-audit-artifacts.py"
    if not generator.is_file():
        error("missing expert audit artifact generator")
        return
    generator_source = generator.read_text(encoding="utf-8")
    if "for part in p.parts" in generator_source:
        error("expert artifact generator path filtering is root-location dependent; use paths relative to ROOT")
    if "p.relative_to(ROOT).parts" not in generator_source:
        error("expert artifact generator lost ROOT-relative cache/path filtering")
    generator_sha = sha256(generator)
    generator_tree = ast.parse(generator_source, filename=str(generator))
    fingerprint_inputs = None
    extra_fingerprint_inputs: tuple[str, ...] = ()
    for node in generator_tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if "FINGERPRINT_INPUTS" in names and fingerprint_inputs is None:
            fingerprint_inputs = tuple(ast.literal_eval(node.value))
        if "EXTRA_FINGERPRINT_INPUTS" in names:
            extra_fingerprint_inputs = tuple(ast.literal_eval(node.value))
    if not fingerprint_inputs:
        error("expert artifact generator no longer declares FINGERPRINT_INPUTS")
        return
    chemistry_fingerprint_inputs = tuple(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "contracts/chemistry").iterdir())
        if path.is_file() and path.suffix in {".json", ".toml"}
    )
    fingerprint_inputs = tuple(dict.fromkeys((*fingerprint_inputs, *chemistry_fingerprint_inputs, *extra_fingerprint_inputs)))
    expected_fingerprints = {rel: sha256(ROOT / rel) for rel in fingerprint_inputs}
    for key, doc in docs.items():
        if doc.get("generator_sha256") != generator_sha:
            error(f"{key} expert artifact is stale relative to its generator")
        if doc.get("source_fingerprints") != expected_fingerprints:
            error(f"{key} expert artifact is stale relative to canonical scientific inputs")

    profiles = profile_map()
    module_ids = set(profiles)
    engine_ids = {str(row["engine"]) for row in profiles.values()}
    expert = docs["expert"]
    expert_modules = expert.get("modules", {})
    if expert.get("module_count") != 21 or set(expert_modules) != module_ids:
        error("expert module audit does not cover the exact 21 canonical modules")
    if expert.get("engine_count") != len(engine_ids):
        error("expert module audit engine count drifted from canonical profiles")
    for mid in sorted(module_ids):
        row = expert_modules.get(mid, {})
        if int(row.get("test_source_count", 0)) <= 0:
            error(f"{mid}: expert audit has no source-test evidence")
        layers = set(row.get("test_layers", []))
        if not {"python-worker", "web-ui"}.issubset(layers):
            error(f"{mid}: source-test audit does not cover both scientific worker and UI layers")
        if not row.get("validation_plan_declared"):
            error(f"{mid}: expert audit has no declared wet-lab validation boundary")
        if row.get("engine") != profiles[mid].get("engine"):
            error(f"{mid}: expert audit engine drifted from canonical profile")
        if not row.get("claim_boundary"):
            error(f"{mid}: expert audit is missing a scientific claim boundary")

    # Semantic freshness: generator fingerprints alone can prove that an
    # artifact is newly generated from stale wording. Guard consequential
    # current protocol/workflow claims explicitly against the canonical authority.
    semantic_markers = {
        "standard-pcr": ("16 named executable", "KOD One", "M0284", "fail-closed"),
        "long-range-pcr": ("seven current executable", "KOD Long", "GoTaq Long", "historical-only"),
        "colony-pcr": ("Five named source-backed", "M0689", "fail closed"),
        "nested-pcr": ("Round 1 and Round 2 as independent reactions", "two-tube topologies execute", "decision_impact=none"),
        "inverse-pcr": ("full-reference outward topology", "origin-spanning reconstruction", "pydna topology evidence", "Sanger handoff"),
        "qpcr-sybr": ("13 named dye-qPCR", "PowerTrack", "QuantiNova", "SsoAdvanced", "Vazyme Q713", "decision_impact=none"),
        "qpcr-probe": ("conventional Thermo Fisher/IDT hydrolysis chemistry", "external-authority-required workflow", "candidate-set SHA-256", "combined specificity", "multiplex interaction evidence"),
        "digital-pcr": ("chemistry and platform routing explicit", "QX200 ddPCR EvaGreen chemistry", "QX Continuum is routed to Pair+Probe", "platform×consumable compatibility", "threshold, rain, partition volume and concentration never come from primer design"),
        "arms-pcr": ("SNV/MNV identity", "non-proofreading evidence model", "empirical paired-allele discrimination"),
        "tetra-primer-arms": ("four-primer SNV geometry", "band-separation review", "wet-lab evidence"),
        "kasp": ("junction-aware plus/minus branch", "FAM×HEX evidence import", "does not invent genotype thresholds"),
        "species-specific-pcr": ("per-record accession.version", "topology-aware semantics", "surveillance diff", "not whole-RefSeq"),
        "lamp": ("one canonical authority generated into Python/Rust/Web/runtime projections", "PrimerExplorer V5 automatic semantics", "Takara RR385", "Meridian MDX126", "Nippon NE6041/NE6043", "ViennaRNA Turner-2004 RNA accessibility", "decision_impact=none"),
        "rpa": ("four executable plain-ACGT", "G-Biosciences", "diversity-aware shortlist", "non-executable boundaries"),
        "universal-primers": ("alignment authority", "observed weighted/stratified coverage", "user weights never become population prevalence"),
        "tiled-scheme": ("circular scheme-create", "native visualisation evidence", "depth/dropout review", "repair handoff", "version/scheme diff"),
        "race": ("biological direction", "SOP/manual revision plus SHA-256", "nested GSP plan", "poly(A) semantics", "Candidate transcript ends remain unvalidated"),
        "sequencing-primer": ("Exact universal-primer reuse", "bidirectional planning", "primer walking", "bounded AB1/ABIF chromatogram import", "never reorders primer candidates"),
        "gibson-assembly": ("Gibson E5510 and NEBuilder HiFi", "construct graph reconstruction", "never cross-inherit"),
        "restriction-cloning": ("exact insert/circular donor reconstruction", "frame/fusion intent", "26 curated enzyme geometries", "SacI-HF close-to-end evidence", "Golden Gate stays a separate Type IIS topology"),
        "site-directed-mutagenesis": ("Q5 back-to-back", "multi-edit and amino-acid inputs", "clone evidence remains separate"),
    }
    for mid, markers in semantic_markers.items():
        boundary = str(expert_modules.get(mid, {}).get("claim_boundary", ""))
        for marker in markers:
            if marker not in boundary:
                error(f"{mid}: expert artifact lost current semantic invariant {marker!r}")

    tool_matrix = docs["tools"]
    if tool_matrix.get("module_count") != 21 or tool_matrix.get("engine_count") != len(engine_ids):
        error("module×toolchain matrix counts drifted from canonical source")
    matrix_engines = tool_matrix.get("engines", {})
    if set(matrix_engines) != engine_ids:
        error("module×toolchain matrix does not cover the exact canonical engine set")
    covered_modules: set[str] = set()
    for eid, row in matrix_engines.items():
        covered_modules.update(row.get("modules", []))
        for binding in row.get("bindings", []):
            role = binding.get("role")
            semantics = str(binding.get("strict_semantics", ""))
            if role == "OPTIONAL" and "may not change deterministic selection" not in semantics:
                error(f"{eid}/{binding.get('tool_id')}: OPTIONAL tool semantics can affect selection")
            if role == "REFERENCE" and "never runtime prerequisite" not in semantics:
                error(f"{eid}/{binding.get('tool_id')}: REFERENCE tool semantics became a runtime prerequisite")
    if covered_modules != module_ids:
        error("module×toolchain matrix does not map all and only canonical modules")

    ui = docs["ui"]
    ui_modules = ui.get("modules", {})
    if ui.get("module_count") != 21 or set(ui_modules) != module_ids:
        error("UI/UX expert audit does not cover the exact 21 canonical modules")
    for mid, row in ui_modules.items():
        if not row.get("page_plan") or not row.get("validation_visible"):
            error(f"{mid}: UI audit lost page-plan or validation visibility")
        if int(len(row.get("assay_or_engine_specific_sources", []))) <= 0:
            error(f"{mid}: UI audit has no assay/engine-specific source evidence")

    risks = docs["risks"]
    if risks.get("source_release_blockers_open") != 0:
        error("scientific risk register has open source release blockers")
    for row in risks.get("risks", []):
        if row.get("status") not in {"closed", "controlled-boundary", "open-host-gate"}:
            error(f"risk {row.get('id')}: unclassified status {row.get('status')!r}")
        if row.get("status") == "open-host-gate" and not str(row.get("id", "")).startswith("R-REL-"):
            error(f"risk {row.get('id')}: scientific source risk was incorrectly deferred to host qualification")

    backlog = docs["backlog"]
    items = backlog.get("items", [])
    if not items:
        error("expert upgrade backlog is empty")
    for row in items:
        if row.get("module") not in module_ids:
            error(f"upgrade backlog references unknown module {row.get('module')!r}")
        if row.get("status") != "not-current-capability":
            error(f"upgrade {row.get('id')}: backlog item is being represented as current capability")
        if "never approximate" not in str(row.get("admission_rule", "")):
            error(f"upgrade {row.get('id')}: admission rule can permit a weaker-engine approximation")

    numeric = docs["numeric"]
    profile_rows = numeric.get("profile_numeric_constraints", [])
    expected_profile_numeric = []
    for mid, profile in sorted(profiles.items()):
        defaults = profile.get("defaults", {})
        constraints = defaults.get("constraints", {}) if isinstance(defaults, dict) else {}
        policy = defaults.get("constraintPolicy", {}) if isinstance(defaults, dict) else {}
        for field, value in sorted(constraints.items()):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                expected_profile_numeric.append((mid, field, value, str(policy.get(field, "recommended"))))
    actual_profile_numeric = sorted((r.get("module"), r.get("field"), r.get("value"), r.get("policy")) for r in profile_rows)
    if actual_profile_numeric != sorted(expected_profile_numeric):
        error("numeric provenance registry does not exactly cover active numeric profile constraints")

    # Qualification envelopes are hard branch boundaries and therefore need a
    # separate exact inventory. A registry that sees only preferred/default
    # constraints can otherwise stay green while a new hard gate is added.
    expected_envelopes = []
    for mid, profile in sorted(profiles.items()):
        defaults = profile.get("defaults", {})
        envelope = defaults.get("constraintEnvelope", {}) if isinstance(defaults, dict) else {}
        if not isinstance(envelope, dict):
            error(f"{mid}: constraintEnvelope is not an object")
            continue
        for field, bounds in sorted(envelope.items()):
            if not isinstance(bounds, dict):
                error(f"{mid}: constraintEnvelope.{field} is not an object")
                continue
            for bound, value in sorted(bounds.items()):
                if bound not in {"min", "max"}:
                    error(f"{mid}: constraintEnvelope.{field} contains unknown bound {bound!r}")
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    expected_envelopes.append((mid, field, bound, value))
    actual_envelopes = sorted(
        (r.get("module"), r.get("field"), r.get("bound"), r.get("value"))
        for r in numeric.get("profile_qualification_envelopes", [])
    )
    if actual_envelopes != sorted(expected_envelopes):
        error("numeric provenance registry does not exactly cover active qualification-envelope bounds")

    tuning = set(numeric.get("ranking_tuning_names", []))
    if not tuning:
        error("numeric provenance registry contains no explicit ranking-tuning classification")
    tuning_rows = {r.get("name") for r in numeric.get("source_constants", []) if r.get("category") == "ranking-tuning"}
    if tuning_rows != tuning:
        error("numeric provenance registry ranking-tuning names and classified rows disagree")

    # Independently reconstruct every numeric literal that appears inside a
    # core decision comparison. The expert generator and release audit use
    # separate scanners so a generator omission cannot make the registry look
    # complete by construction.
    decision_files = None
    for node in generator_tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DECISION_FILES" for t in node.targets):
            decision_files = tuple(ast.literal_eval(node.value))
            break
    if not decision_files:
        error("expert artifact generator no longer declares DECISION_FILES")
        return
    expected_literals = []
    for filename in decision_files:
        source = f"tools/src/pcr_tools/{filename}"
        path = ROOT / source
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)):
                continue
            ancestor = parents.get(node)
            decision = False
            for _ in range(6):
                if ancestor is None:
                    break
                if isinstance(ancestor, ast.Compare):
                    decision = True
                if isinstance(ancestor, ast.If) and any(x is node for x in ast.walk(ancestor.test)):
                    decision = True
                if isinstance(ancestor, ast.Assert):
                    decision = True
                ancestor = parents.get(ancestor)
            if not decision:
                continue
            func = "module"
            ancestor = parents.get(node)
            while ancestor is not None:
                if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func = ancestor.name
                    break
                ancestor = parents.get(ancestor)
            expected_literals.append((source, node.lineno, func, node.value))
    actual_literals = sorted((r.get("file"), r.get("line"), r.get("function"), r.get("value")) for r in numeric.get("decision_numeric_literals", []))
    if actual_literals != sorted(expected_literals):
        error("numeric provenance registry does not exactly cover inline decision/comparison numeric literals")
    if any(r.get("category") == "reviewed-inline-decision-boundary" for r in numeric.get("decision_numeric_literals", [])):
        error("numeric provenance registry still contains an unclassified non-trivial inline decision boundary")

    # Static proof: a declared ranking-only constant must not appear directly in
    # an if-condition whose branch can raise. This catches promotion of tuning
    # weights/thresholds into hard scientific validity gates.
    for source in sorted({str(r.get("file")) for r in numeric.get("source_constants", []) if r.get("file")}):
        path = ROOT / source
        if not path.is_file():
            error(f"numeric provenance source disappeared: {source}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            if not any(isinstance(x, ast.Raise) for x in ast.walk(ast.Module(body=node.body, type_ignores=[]))):
                continue
            names = {x.id for x in ast.walk(node.test) if isinstance(x, ast.Name)}
            bad = sorted(names & tuning)
            if bad:
                error(f"{source}:{node.lineno}: ranking tuning entered a hard rejection condition: {bad}")

    pipeline = (ROOT / "tools/src/pcr_tools/pipeline.py").read_text(encoding="utf-8")
    if 'if assay.get("id") == "species-specific-pcr" and products:' not in pipeline:
        error("species-specific exclusivity is no longer a zero-unintended-product hard gate")
    if 'Component(name="Template accessibility"' in pipeline:
        error("optional template-accessibility evidence re-entered deterministic ranking")
    if 'scored.sort(key=lambda e: e["score"])' not in pipeline:
        error("flanking deterministic ranking source changed; re-audit tuning/quality separation")

def audit_hygiene() -> None:
    """Enforce a canonical Linux/public-source filesystem contract."""
    casefold: dict[str, str] = {}
    text_suffixes = {
        ".md", ".rs", ".py", ".ts", ".tsx", ".mjs", ".json", ".toml",
        ".yaml", ".yml", ".sql", ".sh", ".css", ".http", ".txt", ".example",
    }
    text_names = {".gitignore", ".dockerignore", ".npmrc", ".gitattributes"}
    forbidden_legacy_suffixes = {".ps1", ".bat", ".cmd"}
    for path in iter_source_files():
        rel = path.relative_to(ROOT)
        if path.is_symlink():
            error(f"symlink is not allowed in the canonical Linux public source: {rel}")
        if path.suffix.lower() in forbidden_legacy_suffixes:
            error(f"legacy non-Linux launcher/script remains in public source: {rel}")
        if "__pycache__" in rel.parts or path.suffix == ".pyc":
            error(f"cache artifact: {rel}")
        if path.is_file() and (path.suffix == ".tsbuildinfo" or path.name in {".coverage"}):
            error(f"generated build/test artifact in public source: {rel}")
        if path.is_file() and (path.suffix.lower() in text_suffixes or path.name in text_names):
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                error(f"UTF-8 BOM in current text source: {rel}")
            if b"\r\n" in raw:
                error(f"CRLF line endings are not allowed in canonical Linux text source: {rel}")
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                error(f"non-UTF-8 current text source: {rel}: {exc}")
            else:
                for line_no, line in enumerate(decoded.splitlines(), 1):
                    if line.rstrip(" \t") != line:
                        error(f"trailing whitespace: {rel}:{line_no}")
        # Linux filesystems are case-sensitive, but case-only duplicates are still
        # prohibited because they create brittle Git/archive behavior.
        key = rel.as_posix().casefold()
        if key in casefold and casefold[key] != rel.as_posix():
            error(f"case-only source collision: {casefold[key]} / {rel}")
        casefold[key] = rel.as_posix()

def audit_markdown_links() -> None:
    link = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        if is_generated(path): continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for target in link.findall(text):
            target = target.strip().split("#",1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "#")): continue
            dest = (path.parent / target).resolve()
            try: dest.relative_to(ROOT.resolve())
            except ValueError: continue
            if not dest.exists(): error(f"broken local Markdown link: {path.relative_to(ROOT)} -> {target}")

def audit_expected_files() -> None:
    for engine in sorted({p.name for p in (ROOT / "knowledge/atlas/engines").iterdir() if p.is_dir()}):
        if not (ROOT / "knowledge/atlas/engines" / engine / "01-tools.md").is_file():
            error(f"{engine}: missing 01-tools.md")
    if len(list((ROOT / "knowledge/atlas").rglob("*"))) == 0:
        error("Atlas is empty")
    for needed in (
        "run.sh",
        "scripts/start-app.mjs",
        "scripts/dev-api.mjs",
        "scripts/provision-tools.py",
        "scripts/configure-specificity-database.py",
        "scripts/configure-olivar-linux.py",
        "scripts/prepare-linux.py",
        "scripts/doctor-linux.py",
        "scripts/run-linux-qualification.py",
        "scripts/run-lamp-linux-qualification.py",
        "scripts/new-linux-acceptance-results.py",
        "scripts/record-linux-module-acceptance.py",
        "scripts/record-linux-integration-scenario.py",
        "scripts/validate-linux-acceptance-results.py",
        "scripts/run-engine-acceptance.py",
        "tools/src/pcr_tools/pydna_bridge.py",
        "tools/src/pcr_tools/pydna_validation.py",
        "tools/src/pcr_tools/primalscheme_adapter.py",
        "knowledge/runtime/linux-acceptance-matrix.json",
        "knowledge/runtime/module-rule-trace.generated.json",
        "knowledge/runtime/linux-integration-scenarios.json",
        "knowledge/runtime/linux-acceptance-results.template.json",
        "knowledge/runtime/LINUX-ACCEPTANCE-RUNBOOK.md",
        "knowledge/LINUX-RUNTIME.md",
        "contracts/engines/profiles/consensus-pair.json",
        "knowledge/runtime/engine-system.generated.json",
        "knowledge/runtime/engine-capability-matrix.generated.json",
        "knowledge/runtime/engine-transport-parity.generated.json",
        "contracts/architecture.toml",
        "docs/adr/0008-layered-modular-monolith-and-drift-guards.md",
        "docs/adr/0009-external-scientific-runner-and-linux-release-boundary.md",
        "scripts/audit/architecture.py",
        "knowledge/runtime/scientific-integrity-policy.json",
        "knowledge/runtime/SCIENTIFIC-INTEGRITY-POLICY.md",
        "tools/src/pcr_tools/scientific_integrity.py",
        "scripts/generate-expert-audit-artifacts.py",
        "scripts/generate-flanking-evidence-ledger.py",
        "release/release.toml",
        "release/current/CURRENT-LINUX-MIGRATION.md",
        "knowledge/reviews/EXPERT-MODULE-AUDIT.json",
        "knowledge/reviews/EXPERT-MODULE-AUDIT.md",
        "knowledge/reviews/MODULE-TOOLCHAIN-MATRIX.json",
        "knowledge/reviews/MODULE-TOOLCHAIN-MATRIX.md",
        "knowledge/reviews/UI-UX-MODULE-AUDIT.json",
        "knowledge/reviews/UI-UX-MODULE-AUDIT.md",
        "knowledge/reviews/SCIENTIFIC-RISK-REGISTER.json",
        "knowledge/reviews/SCIENTIFIC-RISK-REGISTER.md",
        "knowledge/reviews/EXPERT-UPGRADE-BACKLOG.json",
        "knowledge/reviews/EXPERT-UPGRADE-BACKLOG.md",
        "knowledge/runtime/numeric-provenance-registry.json",
        "knowledge/runtime/NUMERIC-PROVENANCE-REGISTRY.md",
    ):
        if not (ROOT / needed).is_file():
            error(f"missing expected implementation artifact: {needed}")

    qualification = (ROOT / "scripts/run-linux-qualification.py").read_text(encoding="utf-8")
    for token in (
        "file_manifest_sha256", "file_manifest_verified", "verified_file_count",
        "runtime_contract_manifest_sha256", "source_artifact_identity_binding", "source_identity",
        "CURRENT source qualifier (non-mutating verification)", "--full",
        "Unified engine authority projection check",
        "Unified engine contract projection check",
        "Unified engine high-risk acceptance scenarios",
        "module functional acceptance evidence",
    ):
        if token not in qualification:
            error(f"scripts/run-linux-qualification.py lost Linux qualification marker: {token}")

    bootstrap = (ROOT / "scripts/bootstrap-linux.py").read_text(encoding="utf-8")
    doctor = (ROOT / "scripts/doctor-linux.py").read_text(encoding="utf-8")
    for marker in ("preflight_disk_capacity", "reference_fasta_bytes", "DockerRootDir", "disk_preflight"):
        if marker not in bootstrap:
            error(f"Linux bootstrap lost disk-capacity fail-closed marker: {marker}")
    for marker in ("read_only", "source_manifest", "repository_disk", "allow-docker-install"):
        if marker not in doctor:
            error(f"Linux read-only doctor lost required diagnostic marker: {marker}")



def audit_current_identity_uniformity() -> None:
    """Reject active release-number/count-family abstractions and duplicate current authorities."""
    active_roots = (
        ROOT / "contracts", ROOT / "scripts", ROOT / "tools/src",
        ROOT / "web/src", ROOT / "crates", ROOT / "docker", ROOT / "release/current",
        ROOT / ".github/workflows", ROOT / "knowledge/runtime",
    )
    release_named = re.compile(r"(?:^|[-_])r\d+(?:[-_.]|$)", re.IGNORECASE)
    count_family = re.compile(r"(?:four|five|seven)[-_ ]engine", re.IGNORECASE)
    structural_release = re.compile(
        r"(?:foundation_release|release_line|contract_version|authority_id|registry_id|science)"
        r"[^\n]{0,120}[\"']?r\d+", re.IGNORECASE
    )
    active_files: list[Path] = []
    for root in active_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith("crates/pcr-storage/migrations/"):
                continue
            if rel in {
                "release/current/SOURCE-QUALIFICATION.json",
                "release/current/SOURCE-ATTESTATION.intoto.json",
                "release/current/SBOM.cdx.json",
                "web/src/lib/module-documentation.generated.json",
            }:
                # Generated release evidence and the module bibliography are
                # regenerated after source gates; their own generators/checks
                # own drift detection. Bibliography URLs may contain vendor
                # revision tokens that are not active authority identities.
                continue
            active_files.append(path)
            if release_named.search(path.name):
                error(f"CURRENT active filename is release-number-specific: {rel}")

    for path in active_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if count_family.search(text):
            error(f"CURRENT active source reintroduced count-family engine abstraction: {rel}")
        if structural_release.search(text):
            error(f"CURRENT active source reintroduced release-number-specific authority identity: {rel}")

    for rel in ("README.md", "release/PUBLIC-SOURCE.md", "release/STATUS.md", "release/INDEX.md"):
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if count_family.search(text):
            error(f"CURRENT public documentation reintroduced count-family engine abstraction: {rel}")

    types = (ROOT / "web/src/lib/api/types.ts").read_text(encoding="utf-8")
    for marker in (
        'z.enum(ENGINE_IDS)', 'z.enum(GOAL_IDS)', 'z.enum(MODIFIER_IDS)',
        'z.enum(MODULE_STATUS_IDS)', 'foundationContract.draft_schema_version',
        'foundationContract.request_schema_version', 'foundationContract.result_schema_version',
        'foundationContract.module_contract_version',
    ):
        if marker not in types:
            error(f"Web wire contract lost canonical generated authority marker: {marker}")
    for stale in ('default("R9")', 'draftSchemaVersion: z.number().int().default(1)',
                  'requestSchemaVersion: z.number().int().default(1)',
                  'resultSchemaVersion: z.number().int().default(2)'):
        if stale in types:
            error(f"Web wire contract reintroduced stale hand-written default: {stale}")

    taxonomy = (ROOT / "crates/pcr-core/src/taxonomy.rs").read_text(encoding="utf-8")
    if 'include!("../generated/engine_id.generated.rs");' not in taxonomy:
        error("Rust domain taxonomy reintroduced a hand-maintained EngineId registry")
    engine_contract = tomllib.loads((ROOT / "contracts/engines.toml").read_text(encoding="utf-8"))
    engine_rows = engine_contract.get("engine") or []
    orders = sorted(int(row.get("display_order", 0)) for row in engine_rows)
    if len(engine_rows) != 11 or orders != list(range(1, 12)):
        error("canonical engine registry lost exact 11-engine contiguous display ordering")
    for row in engine_rows:
        if not str(row.get("label") or "").strip() or not str(row.get("input") or "").strip():
            error(f"canonical engine registry lost label/input metadata for {row.get('id')!r}")

    rust_contracts = (ROOT / "crates/pcr-contracts/src/lib.rs").read_text(encoding="utf-8")
    if 'include!("../generated/foundation.generated.rs");' not in rust_contracts:
        error("Rust contract crate no longer consumes generated foundation version constants")
    for marker in (
        'pub const MODULE_CONTRACT_VERSION:', 'pub const IPC_PROTOCOL_VERSION:',
        'pub const DRAFT_SCHEMA_VERSION:', 'pub const REQUEST_SCHEMA_VERSION:',
        'pub const RESULT_SCHEMA_VERSION:',
    ):
        if marker in rust_contracts:
            error(f"Rust contract crate reintroduced hand-maintained foundation constant: {marker}")

    domain_generator = ROOT / "scripts/generate-domain-vocabulary.py"
    domain_projection = ROOT / "web/src/lib/contracts/domain-vocabulary.generated.ts"
    if not domain_generator.is_file() or not domain_projection.is_file():
        error("CURRENT generated domain-vocabulary projection/generator is missing")

    for workflow in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow_text = workflow.read_text(encoding="utf-8")
        for family in ("four", "five"):
            for suffix in ("authorities.py", "closure-contracts.py"):
                stale_script = f"generate-{family}-" + "engine-" + suffix
            if stale_script in workflow_text:
                error(f"CURRENT CI workflow reintroduced legacy count-family generator: {workflow.name}: {stale_script}")


def audit_current_release_identity() -> None:
    """CURRENT has one canonical Linux/unified-engine identity and synchronized evidence."""
    identity_path = ROOT / "release/release.toml"
    if not identity_path.is_file():
        error("CURRENT canonical release identity is missing: release/release.toml")
        return
    try:
        identity = tomllib.loads(identity_path.read_text(encoding="utf-8"))
    except Exception as exc:
        error(f"CURRENT release identity is not valid TOML: {exc}")
        return

    expected = {
        "release_id": "CURRENT",
        "public_version": "1.0.1",
        "public_tag": "v1.0.1",
        "versioning_scheme": "semver-2.0.0",
        "release_class": "generation-1-unified-engine-linux-current",
        "archive_prefix": "PCRStudio-CURRENT-PUBLIC-SOURCE",
        "baseline_release": "R15",
        "baseline_kind": "R15-final-file-manifest-authority",
        "foundation_release": "CURRENT",
        "source_qualification_label": "linux-native-unified-engine-source-qualified",
        "current_report": "release/current/ENGINEERING-CLOSURE-REPORT.md",
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            error(f"CURRENT release identity drifted for {key}: expected {value!r}, got {identity.get(key)!r}")

    report = ROOT / str(identity.get("current_report", ""))
    if not report.is_file():
        error("CURRENT canonical current report is missing")

    for rel in ("scripts/generate-release-manifests.py", "scripts/build-deterministic-zip.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "load_release_identity" not in text:
            error(f"{rel}: release tooling no longer consumes canonical release identity")

    for rel, marker in (
        ("release/INDEX.md", "PCRStudio current public source"),
        ("release/STATUS.md", "PCRStudio CURRENT public-source status"),
        ("release/RELEASE-NOTES.md", "CURRENT public source"),
        ("release/TOOLCHAIN-STATUS.md", "CURRENT toolchain status"),
        ("release/current/CURRENT-LINUX-QUALIFICATION.md", "CURRENT Linux native qualification"),
        ("release/current/CURRENT-STATIC-CONSISTENCY-AUDIT.md", "CURRENT static consistency audit"),
        ("release/current/CURRENT-ENGINE-SYSTEM.md", "unified engine system"),
    ):
        path = ROOT / rel
        if not path.is_file() or marker.lower() not in path.read_text(encoding="utf-8", errors="replace").lower():
            error(f"CURRENT authority document lost marker {marker!r}: {rel}")
    if not (ROOT / "release/baseline/R15-FILE-MANIFEST.json").is_file():
        error("immutable baseline FILE-MANIFEST authority was not preserved under release/baseline")

    qualifier = (ROOT / "scripts/qualify-source.py").read_text(encoding="utf-8")
    verifier = (ROOT / "scripts/verify-release.py").read_text(encoding="utf-8")
    if "ROOT/'.local/tmp/source-qualification'" not in qualifier and 'ROOT / ".local/tmp/source-qualification"' not in qualifier:
        error("CURRENT source qualifier scratch space is no longer project-local under .local/tmp")
    if 'dir=scratch' not in verifier or 'SCRIPT_ROOT / ".local" / "tmp"' not in verifier:
        error("CURRENT archive verifier scratch extraction is no longer project-local under .local/tmp")

    ledger_json = ROOT / "release/FLANKING-PAIR-EVIDENCE-LEDGER.json"
    ledger_md = ROOT / "release/FLANKING-PAIR-EVIDENCE-LEDGER.md"
    if not ledger_json.is_file() or not ledger_md.is_file():
        error("Flanking evidence ledger authority/projection is missing")
    else:
        try:
            ledger = json.loads(ledger_json.read_text(encoding="utf-8"))
        except Exception as exc:
            error(f"Flanking evidence ledger JSON is invalid: {exc}")
            ledger = {}
        md = ledger_md.read_text(encoding="utf-8")
        if not md.startswith("<!-- GENERATED by scripts/generate-flanking-evidence-ledger.py"):
            error("Flanking evidence ledger Markdown is no longer a generated projection")
        claims = "\n".join(str(row.get("claim", "")) for row in ledger.get("records", []))
        for token in ("16 named", "Seven current", "13 named", "platform", "surveillance", "G-Biosciences"):
            if token.lower() not in claims.lower():
                error(f"Flanking evidence ledger lost current semantic marker {token!r}")

def audit_source_release_hardening() -> None:
    """Public source is pinned, attestable and qualified through Linux-native gates."""
    required = (
        "scripts/release_utils.py", "scripts/generate-sbom.py",
        "scripts/generate-source-attestation.py", "scripts/create-archive-attestation.py",
        "scripts/build-deterministic-zip.py", "scripts/verify-release.py",
        "scripts/qualify-source.py", "scripts/run-linux-qualification.py",
        "scripts/run-engine-acceptance.py",
        "scripts/new-linux-acceptance-results.py", "scripts/record-linux-module-acceptance.py",
        "scripts/record-linux-integration-scenario.py", "scripts/validate-linux-acceptance-results.py",
        "scripts/check-scientific-toolchain.py", "scripts/configure-olivar-linux.py",
        "scripts/configure-specificity-database.py", "scripts/provision-tools.py",
        "scripts/run-native-tiling-lifecycle-acceptance.py",
        "scripts/build-public-release-evidence.py", "scripts/prepare-linux.py",
        "scripts/source_generators.py", "scripts/doctor-linux.py", "scripts/generate-current-static-audit.py",
        "scripts/benchmark-worker.py", "scripts/sign-release.sh",
        "knowledge/CACHE-POLICY.md", "knowledge/IMAGE-SUPPLY-CHAIN.md",
        "knowledge/performance/README.md", "knowledge/performance/reference-budgets.json",
    )
    for relative in required:
        if not (ROOT / relative).is_file():
            error(f"Linux source-release artifact missing: {relative}")

    # Dependency managers and scientific provisioners create platform helper
    # files inside explicitly project-local runtime state. Those files are not
    # part of the public source and must not make an otherwise clean Linux tree
    # fail the active-source platform boundary check.
    local_state_parts = {
        ".local", "node_modules", "target", ".next", ".venv", "playwright-report", "test-results",
    }
    legacy = [
        p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in {".ps1", ".bat", ".cmd"}
        and "release/baseline" not in p.relative_to(ROOT).as_posix()
        and not any(part in local_state_parts for part in p.relative_to(ROOT).parts)
    ]
    if legacy:
        error(f"legacy platform scripts remain in active public source: {legacy}")

    source_qualifier = (ROOT / "scripts/qualify-source.py").read_text(encoding="utf-8")
    generator_registry = (ROOT / "scripts/source_generators.py").read_text(encoding="utf-8")
    if (
        "CURRENT_STATIC_GENERATOR" not in source_qualifier
        or "current-static-consistency-generator-check" not in generator_registry
        or "generate-current-static-audit.py" not in generator_registry
    ):
        error("CURRENT source qualifier no longer enforces reproducible current static consistency evidence")
    prepare_linux = (ROOT / "scripts/prepare-linux.py").read_text(encoding="utf-8")
    if "SOURCE_GENERATORS" not in prepare_linux or "CURRENT_STATIC_GENERATOR" not in prepare_linux:
        error("Linux preparation no longer shares the canonical source-generator registry")

    qualification_text = (ROOT / "scripts/run-linux-qualification.py").read_text(encoding="utf-8")
    for token in (
        "CURRENT source qualifier (non-mutating verification)",
        "Unified engine authority projection check",
        "Unified engine contract projection check",
        "Unified engine differential/property contracts",
        "Unified engine high-risk acceptance scenarios",
        "web production build", "running-stack health/readiness probe",
        "CURRENT scientific toolchain identity snapshot",
        "--approve-scientific-environment", "--require-olivar",
        "--require-functional-acceptance", "module functional acceptance evidence",
        "source_identity", "Source artifact identity changed during non-mutating qualification",
    ):
        if token not in qualification_text:
            error(f"CURRENT Linux qualification lost mandatory gate/control {token!r}")

    acceptance_common = (ROOT / "scripts/acceptance_common.py").read_text(encoding="utf-8")
    for token in ("release_id", "release_class", "source_manifest", "source_sha256", "FILE-MANIFEST.json", "assert_bound"):
        if token not in acceptance_common:
            error(f"Linux acceptance evidence lost manifest-binding marker {token!r}")
    acceptance_validate = (ROOT / "scripts/validate-linux-acceptance-results.py").read_text(encoding="utf-8")
    for token in (
        "schema_version", "1.3.0", "exactly match canonical module matrix",
        "test_selector", "exit_code", "evidence SHA-256 mismatch", "assert_bound",
    ):
        if token not in acceptance_validate:
            error(f"Linux acceptance validator lost strict evidence marker {token!r}")

    engine_acceptance = (ROOT / "scripts/run-engine-acceptance.py").read_text(encoding="utf-8")
    for token in ("assert_bound(doc)", "evidence(log", "-k", "integration_scenarios", "cargo", "pnpm", "engine_differential_contract"):
        if token not in engine_acceptance:
            error(f"Unified engine Linux acceptance lost mandatory evidence marker {token!r}")

    archive_attest = (ROOT / "scripts/create-archive-attestation.py").read_text(encoding="utf-8")
    for token in (
        "--qualification-result", "--acceptance-results", "qualifiedFileManifestSha256",
        "functionalAcceptance", "pass-bound", 'acceptance.get("release_id")',
        'acceptance.get("release_class")', 'acceptance.get("source_sha256")',
    ):
        if token not in archive_attest:
            error(f"CURRENT archive attestation lost native/functional-evidence binding marker {token!r}")

    # Distribution metadata must agree with actual license texts. The root
    # package and Rust workspace are proprietary, while the Python scientific
    # worker intentionally carries a more specific GPL-2.0-or-later license.
    root_license = ROOT / "LICENSE"
    tools_license = ROOT / "tools/LICENSE"
    notice = ROOT / "NOTICE"
    if not root_license.is_file() or "PCRStudio Proprietary Source License" not in root_license.read_text(encoding="utf-8"):
        error("root proprietary license text is missing or malformed")
    if not tools_license.is_file() or "GPL-2.0-or-later" not in tools_license.read_text(encoding="utf-8"):
        error("tools GPL-2.0-or-later license boundary is missing")
    if not notice.is_file() or "external-process/IPC boundary" not in notice.read_text(encoding="utf-8"):
        error("source distribution licensing NOTICE is missing the worker boundary")
    root_package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    if root_package.get("license") != "UNLICENSED":
        error("root package.json must mark the proprietary source as UNLICENSED")
    cargo_workspace = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
    if 'license = "LicenseRef-PCRStudio-Proprietary"' not in cargo_workspace:
        error("Cargo workspace license no longer matches the root proprietary license")
    tools_project = (ROOT / "tools/pyproject.toml").read_text(encoding="utf-8")
    if 'license = { text = "GPL-2.0-or-later" }' not in tools_project:
        error("tools pyproject license no longer matches tools/LICENSE")

    # Every external Docker base/service image is immutable by manifest digest.
    # This includes local-development and CI service containers: a source release
    # should not silently exercise a different PostgreSQL image merely because
    # the caller used the dev compose file or GitHub Actions instead of the
    # production compose template.
    image_refs: list[tuple[str, str]] = []
    compose_paths = [ROOT / "compose.yaml", *sorted((ROOT / "docker").glob("*.yaml"))]
    for compose_path in compose_paths:
        compose_text = compose_path.read_text(encoding="utf-8")
        for ref in re.findall(r"(?m)^\s*image:\s*([^\s#]+)", compose_text):
            image_refs.append((compose_path.relative_to(ROOT).as_posix(), ref))
    for workflow in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow_text = workflow.read_text(encoding="utf-8")
        for ref in re.findall(r"(?m)^\s*image:\s*([^\s#]+)", workflow_text):
            image_refs.append((workflow.relative_to(ROOT).as_posix(), ref))
    for relative in ("docker/api.Dockerfile", "docker/web.Dockerfile"):
        dockerfile_text = (ROOT / relative).read_text(encoding="utf-8")
        aliases: set[str] = set()
        for match in re.finditer(r"(?mi)^FROM\s+([^\s]+)(?:\s+AS\s+([^\s]+))?", dockerfile_text):
            ref, alias = match.group(1), match.group(2)
            if ref not in aliases:
                image_refs.append((relative, ref))
            if alias:
                aliases.add(alias)
    for source, ref in image_refs:
        # Project-built images are content produced from this source tree and
        # are intentionally tagged locally before release qualification. They
        # are not external supply-chain inputs. External/base/service images
        # must remain immutable by digest.
        local_project_images = {
            "pcrstudio-api:${PCRSTUDIO_IMAGE_TAG:-local}",
            "pcrstudio-runner:${PCRSTUDIO_IMAGE_TAG:-local}",
            "pcrstudio-migrate:${PCRSTUDIO_IMAGE_TAG:-local}",
        }
        local_ci_images = {
            "pcrstudio-api:ci",
            "pcrstudio-runner:ci",
            "pcrstudio-migrate:ci",
            "pcrstudio-web:ci",
        }
        if source == "compose.yaml" and ref in local_project_images:
            compose_text = (ROOT / source).read_text(encoding="utf-8")
            if "dockerfile: docker/api.Dockerfile" not in compose_text:
                error("local PCRStudio application images lost their source-build binding")
            continue
        if source.startswith(".github/workflows/") and ref in local_ci_images:
            continue
        if not re.search(r"@sha256:[0-9a-f]{64}$", ref):
            error(f"source release hardening: external container image is not digest pinned in {source}: {ref}")

    # GitHub Actions must be immutable; package/tool updaters can move the SHA
    # only through a reviewed source change.
    for workflow in sorted((ROOT / ".github/workflows").glob("*.yml")):
        for ref in re.findall(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)", workflow.read_text(encoding="utf-8")):
            if not re.search(r"@[0-9a-f]{40}$", ref):
                error(f"source release hardening: mutable GitHub Action reference in {workflow.name}: {ref}")

    # Guard the previously identified deployment defect: Next's scratch/cache policy
    # belongs to web, never PostgreSQL.
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    if "/src/web/.next/cache" in compose:
        error("source release hardening: compose still places a Next.js cache path in a runtime service")
    for service_marker in ("read_only: true", "cap_drop:", "no-new-privileges:true", "pids_limit:"):
        if compose.count(service_marker) < 2:
            error(f"source release hardening: API/Web hardening marker missing or incomplete: {service_marker}")

    ci_text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for marker in (
        "scripts/scan-secrets.py",
        "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25",
        "image-sbom-api.cdx.json",
        "image-sbom-runner.cdx.json",
        "image-sbom-migrate.cdx.json",
        "image-sbom-web.cdx.json",
        "test ! -e /var/lib/dpkg/status",
        "--target api-runtime",
        "--target runner-runtime",
        "--target migrate-runtime",
        "PLAYWRIGHT_BROWSERS_PATH",
        "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
        "scripts/install-playwright-browser.sh",
    ):
        if marker not in ci_text:
            error(f"source release hardening: Linux image qualification lost required security/build marker: {marker}")
    api_dockerfile = (
        (ROOT / "docker/api.Dockerfile").read_text(encoding="utf-8")
        + "\n"
        + (ROOT / "docker/configure-debian-snapshot.sh").read_text(encoding="utf-8")
    )
    for marker in (
        "python:3.12-slim-trixie@sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79",
        "busybox:1.37.0-glibc@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0",
        "DEBIAN_SNAPSHOT=20260901T000000Z",
        "configure-debian-snapshot",
        "Acquire::Check-Valid-Until",
    ):
        if marker not in api_dockerfile:
            error(f"source release hardening: Docker package provenance marker missing: {marker}")
    codeql_path = ROOT / ".github/workflows/codeql.yml"
    codeql_text = codeql_path.read_text(encoding="utf-8") if codeql_path.is_file() else ""
    for marker in (
        "github/codeql-action/init@",
        "github/codeql-action/analyze@",
        "security-extended",
        "languages: ${{ matrix.language }}",
        "language: rust",
        "language: python",
        "language: javascript-typescript",
    ):
        if marker not in codeql_text:
            error(f"source release hardening: CodeQL coverage marker missing: {marker}")

    egress = (ROOT / "tools/src/pcr_tools/egress.py").read_text(encoding="utf-8")
    for marker in ("https", "eutils.ncbi.nlm.nih.gov", "ProxyHandler({})", "cross-origin redirect"):
        if marker not in egress:
            error(f"source release hardening: fail-closed egress marker missing: {marker}")


def audit_dependency_maintenance_exceptions() -> None:
    """Fail closed on temporary public-release dependency exceptions."""
    from datetime import date
    policy_path = ROOT / "contracts/maintenance-exceptions.json"
    if not policy_path.is_file():
        error("dependency maintenance exception registry is missing")
        return
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error(f"dependency maintenance exception registry is invalid: {exc}")
        return
    dependabot = ROOT / ".github/dependabot.yml"
    dependabot_text = dependabot.read_text(encoding="utf-8") if dependabot.is_file() else ""
    if "package-ecosystem: npm" not in dependabot_text or "interval: weekly" not in dependabot_text:
        error("temporary Web dependency exception requires weekly npm Dependabot monitoring")
    if "package-ecosystem: pip" not in dependabot_text or not re.search(r'directory:\s*["\']?/tools["\']?', dependabot_text):
        error("Python scientific/tooling dependencies require weekly Dependabot monitoring for /tools")
    web_package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    eslint_spec = str(web_package.get("devDependencies", {}).get("eslint", ""))
    today = date.today()
    for item in policy.get("exceptions", []):
        if item.get("id") != "web-eslint-9-peer-compatibility":
            continue
        try:
            expiry = date.fromisoformat(str(item["expires_on"]))
        except (KeyError, ValueError):
            error("ESLint maintenance exception has no valid expiry date")
            continue
        if today > expiry:
            error(f"ESLint 9 maintenance exception expired on {expiry.isoformat()}")
        if not eslint_spec.startswith("^9."):
            error("ESLint maintenance exception exists but web/package.json is no longer on ESLint 9; remove/reconcile the exception")
        if not item.get("upstream_tracking") or not item.get("resolution"):
            error("ESLint maintenance exception lacks upstream tracking or a removal condition")



def audit_capability_maturity() -> None:
    path = ROOT / "contracts/capability-maturity.json"
    if not path.is_file():
        error("capability maturity authority is missing")
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error(f"capability maturity authority is invalid: {exc}")
        return
    items = doc.get("items") or []
    if len(items) != 55 or {row.get("id") for row in items} != set(range(1, 56)):
        error("capability maturity authority must cover the exact 55 CURRENT foundation work items")
    allowed = {"wired-source-tested", "source-ready-host-gated", "schema-reserved", "debt-bounded", "deferred-by-design"}
    for row in items:
        if row.get("maturity") not in allowed:
            error(f"capability maturity item {row.get('id')} has invalid state {row.get('maturity')!r}")
    reserved = {row.get("id"): row for row in items if row.get("maturity") == "schema-reserved"}
    if set(reserved) != {44, 45} or any(row.get("public_surface") for row in reserved.values()):
        error("reserved qualification/attachment foundations must remain explicitly non-public")
    server_routes = (ROOT / "crates/pcr-server/src/projects.rs").read_text(encoding="utf-8") + (ROOT / "contracts/http-api.toml").read_text(encoding="utf-8")
    for marker in ("/attachments", "/qualifications"):
        if marker in server_routes:
            error(f"reserved CURRENT capability unexpectedly acquired a public route: {marker}")
    closure = (ROOT / "release/current/CURRENT-FOUNDATION-CLOSURE.md").read_text(encoding="utf-8")
    for marker in ("SCHEMA-RESERVED", "DEBT-BOUNDED", "contracts/capability-maturity.json"):
        if marker not in closure:
            error(f"foundation closure lost maturity marker {marker!r}")

def audit_maintainability_budgets() -> None:
    """Prevent known monoliths from silently growing in the public release line."""
    policy_path = ROOT / "contracts/maintainability-budget.json"
    if not policy_path.is_file():
        error("maintainability no-growth budget is missing")
        return
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error(f"maintainability budget is invalid: {exc}")
        return
    for relative, ceiling in policy.get("max_lines", {}).items():
        path = ROOT / relative
        if not path.is_file():
            error(f"maintainability-budget file is missing: {relative}")
            continue
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > int(ceiling):
            error(f"maintainability no-growth budget exceeded for {relative}: {count} > {ceiling}; extract a module instead of enlarging the hotspot")
    function_limit = int(policy.get("function_review_lines") or 600)
    for qualified, ceiling in policy.get("max_function_lines", {}).items():
        try:
            relative, function_name = qualified.rsplit("::", 1)
        except ValueError:
            error(f"invalid maintainability function budget key: {qualified}")
            continue
        path = ROOT / relative
        if not path.is_file():
            error(f"maintainability-budget function file is missing: {relative}")
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            error(f"maintainability function budget cannot parse {relative}: {exc}")
            continue
        found = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name and node.end_lineno is not None]
        if len(found) != 1:
            error(f"maintainability function budget must resolve exactly once: {qualified}")
            continue
        count = found[0].end_lineno - found[0].lineno + 1
        if count > int(ceiling):
            error(f"maintainability no-growth function budget exceeded for {qualified}: {count} > {ceiling}")
        if count <= function_limit:
            error(f"maintainability function exception {qualified} is no longer above the review threshold; remove the debt entry")
    for relative in policy.get("extractions", []):
        if not (ROOT / relative).is_file():
            error(f"reviewed maintainability extraction is missing: {relative}")
