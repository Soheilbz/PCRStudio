"""Static scientific-maturity guards for deeply reviewed current engines.

This concern is deliberately narrower than general architecture linting.  It
protects assay ownership: tool roles, protocol/numeric authority, chemistry
boundaries and the fail-closed decisions that prevent one module's assumptions
from leaking into another.
"""
from __future__ import annotations

from .common import *  # noqa: F403

_DEEP_REVIEWED = {
    "flanking-pair", "loop-set", "consensus-pair", "discriminating-pair",
    "junction-primers", "mutagenic-pair", "nested",
}


def _literal_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    return None


def _flatten_lamp_protocol(row: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in ("reaction_volume_uL", "hold_temperature_c", "hold_time_min"):
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = float(value)
    role = row.get("role_concentrations_uM") or {}
    for keys, dst in ((("FIP", "BIP"), "fip_bip_uM"), (("F3", "B3"), "f3_b3_uM"), (("LF", "LB"), "loop_uM")):
        values = [role.get(key) for key in keys]
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            numeric = [float(value) for value in values]
            if len(set(numeric)) == 1:
                out[dst] = numeric[0]
    chemistry = row.get("chemistry") or {}
    if isinstance(chemistry, dict):
        for key, value in chemistry.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[str(key)] = float(value)
    formulation = row.get("baseline_formulation") or {}
    aliases = {
        "mgso4_total_mM": "magnesium_mM", "dntp_each_mM": "dntp_each_mM",
        "bst_xt_units_per_25uL": "polymerase_units", "rtx_units_per_25uL_for_rna": "rt_units",
    }
    if isinstance(formulation, dict):
        for key, value in formulation.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[aliases.get(str(key), str(key))] = float(value)
    return out


def audit_engine_maturity() -> None:
    # ---- Tool-role ownership -------------------------------------------------
    engine_rows = tomllib.loads((ROOT / "contracts/engines.toml").read_text(encoding="utf-8"))["engine"]
    engines = {row["id"]: row for row in engine_rows}
    if not _DEEP_REVIEWED.issubset(engines):
        error(f"engine maturity: engine contract missing {sorted(_DEEP_REVIEWED - set(engines))}")
        return
    bindings = {
        eid: {(b["tool_id"], b["role"], purpose) for b in engines[eid].get("binding", []) for purpose in b.get("purposes", [])}
        for eid in _DEEP_REVIEWED
    }
    required = {
        "flanking-pair": {("primer3_core", "PRIMARY", "candidate_generation"), ("mfeprimer", "VALIDATOR", "specificity"), ("ncbi_blast_plus", "VALIDATOR", "specificity")},
        "loop-set": {("pcrstudio_lamp_enumerator", "PRIMARY", "lamp_geometry"), ("primer3_core", "PRIMARY", "thermodynamics"), ("mfeprimer", "VALIDATOR", "specificity")},
        "consensus-pair": {("mafft", "PRIMARY", "alignment"), ("primer3_core", "PRIMARY", "candidate_generation"), ("mfeprimer", "VALIDATOR", "specificity")},
        "discriminating-pair": {("pcrstudio_allele_wrapper", "PRIMARY", "variant_normalization"), ("primer3_core", "PRIMARY", "candidate_generation"), ("mfeprimer", "VALIDATOR", "specificity")},
        "junction-primers": {("pcrstudio_junction_composer", "PRIMARY", "construct"), ("primer3_core", "PRIMARY", "candidate_generation"), ("pydna", "OPTIONAL", "independent_pcr_product_simulation")},
        "mutagenic-pair": {("pcrstudio_edit_normalizer", "PRIMARY", "topology"), ("primer3_core", "PRIMARY", "candidate_generation"), ("pydna", "OPTIONAL", "independent_pcr_product_simulation")},
        "nested": {("pcrstudio_nested_containment", "PRIMARY", "containment"), ("primer3_core", "PRIMARY", "candidate_generation"), ("primerpooler", "OPTIONAL", "interaction")},
    }
    for eid, expected in required.items():
        missing = expected - bindings[eid]
        if missing:
            error(f"engine maturity: {eid} lost required tool roles {sorted(missing)}")

    # MAFFT is the Universal primary; LAMP may use it only conditionally for inclusivity.
    if ("mafft", "PRIMARY", "alignment") not in bindings["consensus-pair"]:
        error("engine maturity: Consensus lost MAFFT primary alignment ownership")
    if not any(item[0] == "mafft" and item[1] == "CONDITIONAL_PRIMARY" for item in bindings["loop-set"]):
        error("engine maturity: LAMP MAFFT use must remain conditional target-inclusivity evidence")

    # ---- Flanking: protocol groups and numeric ownership --------------------
    flanking = tomllib.loads((ROOT / "contracts/chemistry/flanking-protocols.toml").read_text(encoding="utf-8"))
    fg = flanking["groups"]
    assay_groups = ["standard_pcr", "qpcr_sybr", "rpa", "long_range", "digital", "colony_protocols"]
    seen: dict[str, str] = {}
    sentinels = {"not-selected", "custom-sop", "none"}
    for group in assay_groups:
        for pid in fg.get(group, []):
            if pid in sentinels:
                continue
            if pid in seen:
                error(f"engine maturity: Flanking protocol {pid} is owned by both {seen[pid]} and {group}")
            seen[pid] = group
    # Every numeric catalogue entry must belong to exactly one protocol family.
    restriction_groups = [
        "restriction_digest_protocols",
        "restriction_dephosphorylation_protocols",
        "restriction_ligation_protocols",
    ]
    numeric_owners: dict[str, str] = {}
    for group in [*assay_groups, *restriction_groups]:
        for pid in fg.get(group, []):
            if pid in sentinels:
                continue
            if pid in numeric_owners:
                error(f"engine maturity: Flanking numeric protocol {pid} is owned by both {numeric_owners[pid]} and {group}")
            numeric_owners[pid] = group
    numeric_source = ROOT / "tools/src/pcr_tools/flanking_numeric_recipes.py"
    for table_name in (
        "FLANKING_NUMERIC_BASELINES",
        "FLANKING_NUMERIC_OPTIMIZATION_ENVELOPES",
        "FLANKING_UNRESOLVED_NUMERIC_DEPENDENCIES",
    ):
        table = _literal_assignment(numeric_source, table_name) or {}
        for pid in table:
            if pid not in numeric_owners:
                error(f"engine maturity: {table_name} contains unowned/wrong-module protocol {pid}")

    if set(fg.get("rpa_executable", [])) & {"twistamp-exo", "twistamp-nfo", "twistamp-fpg", "siba-reference"}:
        error("engine maturity: unresolved RPA reporter/SIBA branches became executable")
    flanking_worker = (ROOT / "tools/src/pcr_tools/pipeline.py").read_text(encoding="utf-8")
    if 'tm_centeredness_enabled=assay.get("id") != "rpa"' not in flanking_worker:
        error("engine maturity: RPA regained Tm-centered PCR ranking")
    if 'if assay.get("id") == "standard-pcr"' not in flanking_worker:
        error("engine maturity: Standard-PCR empirical 3-prime prior lost its assay guard")
    for marker, message in (
        ('if assay.get("id") == "species-specific-pcr" and scanning_the_template', "Species-specific exclusivity background guard disappeared"),
        ('Species-specific PCR requires an explicit intended-target inclusivity panel', "Species-specific inclusivity requirement disappeared"),
        ('`inclusivity` and species-panel provenance fields are only supported by the species-specific-pcr assay', "Species-specific request fields can leak into other assays"),
        ('restriction-cloning digest/dephosphorylation/ligation workflow fields belong only to restriction-cloning', "Restriction workflow fields can leak into other assays"),
    ):
        if marker not in flanking_worker:
            error(f"engine maturity: {message}")
    flanking_registry = (ROOT / "tools/src/pcr_tools/registries/flanking_protocols.py").read_text(encoding="utf-8")
    for marker, message in (
        ('if assay_id != "qpcr-sybr"', "qPCR named protocols lost assay ownership"),
        ('if assay_id != "long-range-pcr"', "Long-range named protocols lost assay ownership"),
        ('if assay_id != "rpa"', "RPA named protocols lost assay ownership"),
        ('if assay_id != "colony-pcr"', "Colony SOPs lost assay ownership"),
        ('sequence_decision_impact": "none"', "Colony pre-analytical context can affect sequence ranking"),
        ('if assay_id != "digital-pcr"', "dPCR run context lost assay ownership"),
    ):
        if marker not in flanking_registry:
            error(f"engine maturity: {message}")
    restriction_source = (ROOT / "tools/src/pcr_tools/registries/restriction_workflows.py").read_text(encoding="utf-8")
    if 'DECISION_IMPACT = "none-on-primer-ranking"' not in restriction_source:
        error("engine maturity: Restriction bench workflow may affect primer ranking")
    if "golden-gate" in restriction_source.lower() or "golden gate" in restriction_source.lower():
        error("engine maturity: Golden Gate leaked into the restriction-cloning workflow")

    # Generic numeric overrides may only operate inside a reviewed envelope.
    resolver = (ROOT / "tools/src/pcr_tools/numeric_recipe/resolver.py").read_text(encoding="utf-8")
    for marker in ("has no reviewed optimization envelope", "outside reviewed range", "USER_OVERRIDE_WITHIN_SOURCE_BOUND"):
        if marker not in resolver:
            error(f"engine maturity: bounded numeric override guard lost marker {marker!r}")
    provenance_labels = (ROOT / "tools/src/pcr_tools/numeric_recipe/provenance.py").read_text(encoding="utf-8")
    if 'USER_OVERRIDE_WITHIN_SOURCE_BOUND = "user-override-within-source-bound"' not in provenance_labels:
        error("engine maturity: canonical bounded-override provenance label drifted")

    # ---- LAMP: canonical protocol owns every duplicated baseline value -------
    lamp = json.loads((ROOT / "contracts/chemistry/lamp-protocols.json").read_text(encoding="utf-8"))
    for pid, row in lamp.get("protocols", {}).items():
        if row.get("sequence_decision_impact") != "none":
            error(f"engine maturity: LAMP chemistry {pid} is allowed to mutate sequence ranking")
    supplemental = _literal_assignment(ROOT / "tools/src/pcr_tools/lamp_numeric_recipes.py", "LAMP_NUMERIC_BASELINES") or {}
    for pid, values in supplemental.items():
        canonical = _flatten_lamp_protocol(lamp.get("protocols", {}).get(pid, {}))
        overlap = set(values) & set(canonical)
        if overlap:
            error(f"engine maturity: LAMP supplemental baseline duplicates canonical {pid} fields {sorted(overlap)}")
    m1712 = lamp.get("protocols", {}).get("neb-m1712", {})
    if (m1712.get("hold_temperature_c"), m1712.get("hold_time_min")) != (65, 20):
        error("engine maturity: NEB M1712 current authority must remain 65 C / 20 min")

    # ---- Consensus: alignment/version/population boundaries -----------------
    consensus = json.loads((ROOT / "contracts/chemistry/consensus-profiles.json").read_text(encoding="utf-8"))
    mafft = consensus.get("records", {}).get("mafft-7.526", {})
    if mafft.get("version") != "7.526" or mafft.get("tool_role") != "PRIMARY":
        error("engine maturity: Consensus primary MAFFT authority drifted")
    muscle = consensus.get("records", {}).get("muscle-5.3-audit", {})
    if muscle.get("execution_status") != "diagnostic-only" or muscle.get("sequence_decision_impact") != "none-on-primary-ranking":
        error("engine maturity: MUSCLE audit may not silently replace the primary alignment")
    if "Population-wide universality" not in str(consensus.get("policies", {}).get("population_claim", "")):
        error("engine maturity: Universal Primer panel coverage lost its no-population-overclaim policy")
    tools = tomllib.loads((ROOT / "contracts/tools.toml").read_text(encoding="utf-8"))["tool"]
    toolmap = {row["id"]: row for row in tools}
    mafft_tool = toolmap.get("mafft", {})
    if mafft_tool.get("version") != "7.526" or mafft_tool.get("excluded_range") != "7.463-7.486":
        error("engine maturity: MAFFT toolchain pin/known-bad exclusion drifted")

    # ---- Discriminating: one mismatch authority, KASP chemistry isolation ----
    discr = json.loads((ROOT / "contracts/chemistry/discriminating-protocols.json").read_text(encoding="utf-8"))
    disc_source = (ROOT / "tools/src/pcr_tools/discriminate.py").read_text(encoding="utf-8")
    for marker in ('_MISMATCH_AUTHORITY = dict(DISCRIMINATING_AUTHORITY["mismatch_model"])', 'SECOND_MISMATCH_AT = tuple('):
        if marker not in disc_source:
            error(f"engine maturity: ARMS/Tetra mismatch model regained a parallel truth ({marker})")
    kasp_source = (ROOT / "tools/src/pcr_tools/kasp.py").read_text(encoding="utf-8")
    if 'DISCRIMINATING_AUTHORITY["kasp_chemistry"]' not in kasp_source:
        error("engine maturity: KASP fixed reporter tails are no longer authority-owned")
    for literal in ("GAAGGTGACCAAGTTCATGCT", "GAAGGTCGGAGTCAACGGATT"):
        if literal in kasp_source:
            error("engine maturity: KASP fixed tail sequence was re-hardcoded in worker source")
    v5 = discr.get("records", {}).get("lgc-kasp-tf-v5", {})
    legacy = discr.get("records", {}).get("lgc-standard", {})
    if "legacy_numeric" in v5:
        error("engine maturity: KASP V5 inherited V4 reaction numerics")
    if legacy.get("execution_status") != "historical" or "legacy_numeric" not in legacy:
        error("engine maturity: KASP V4 reproducibility values must remain historical authority only")
    # Direct-engine fallback is allowed only as a mirror of canonical KASP profile constraints.
    kasp_defaults = _literal_assignment(ROOT / "tools/src/pcr_tools/discriminate.py", "KASP_CONSTRAINT_DEFAULTS") or {}
    profile = profile_map().get("kasp", {})
    profile_constraints = ((profile.get("defaults") or {}).get("constraints") or {}) if isinstance(profile, dict) else {}
    comparable = {key: value for key, value in profile_constraints.items() if key in kasp_defaults}
    if any(float(kasp_defaults[key]) != float(value) for key, value in comparable.items()):
        error("engine maturity: direct KASP worker fallback drifted from profiles.toml")
    endpoint = (ROOT / "web/src/lib/kasp-endpoint.ts").read_text(encoding="utf-8")
    if "provider" not in endpoint.lower():
        error("engine maturity: KASP endpoint evidence no longer preserves provider/software calls")
    if "auto-call" in endpoint.lower() or "autocall" in endpoint.lower():
        error("engine maturity: KASP endpoint workspace regained hidden automatic genotype calling")

    # ---- Junction: Gibson and NEBuilder may never share a numeric table ------
    assembly = json.loads((ROOT / "contracts/chemistry/assembly-protocols.json").read_text(encoding="utf-8"))
    records = assembly.get("records", {})
    gibson = records.get("neb-e5510", {})
    expected_gibson = {
        "2-3-fragments": (15, 25, 0.02, 0.5, 15),
        "4-6-fragments": (20, 80, 0.2, 1.0, 60),
    }
    for branch, expected in expected_gibson.items():
        row = (gibson.get("branches") or {}).get(branch, {})
        got = (row.get("overlap_bp_min"), row.get("overlap_bp_max"), row.get("total_pmol_min"), row.get("total_pmol_max"), row.get("incubation_min"))
        if got != expected:
            error(f"engine maturity: E5510 {branch} authority drifted: {got!r}")
    junction_source = (ROOT / "tools/src/pcr_tools/junction.py").read_text(encoding="utf-8")
    if 'payload["branches"][branch]' not in junction_source or 'numeric = {' in junction_source[junction_source.find('def protocol'):junction_source.find('def method')]:
        error("engine maturity: Junction protocol() regained parallel Gibson/NEBuilder numeric tables")
    for pid in ("neb-nebuilder-e2621", "neb-nebuilder-e5520", "neb-nebuilder-e2623"):
        if pid not in records or "branches" not in records[pid]:
            error(f"engine maturity: NEBuilder protocol authority missing branches for {pid}")

    # ---- Mutagenic: topology-specific vendor values must come from authority --
    mut = json.loads((ROOT / "contracts/chemistry/mutagenesis-protocols.json").read_text(encoding="utf-8"))
    q5 = mut.get("records", {}).get("neb-q5-e0554", {})
    if q5.get("routine_insertion_max_nt") != 100 or q5.get("split_insertion_per_primer_max_nt") != 50:
        error("engine maturity: Q5 split-insertion authority drifted")
    if "not a maximum" not in str(q5.get("documented_successful_plasmid_claim_boundary", "")):
        error("engine maturity: Q5 20 kb observed plasmid size was promoted to a false maximum")
    mut_source = (ROOT / "tools/src/pcr_tools/mutagenic.py").read_text(encoding="utf-8")
    if '_Q5_AUTHORITY = authority_record(MUTAGENESIS_AUTHORITY, "neb-q5-e0554")' not in mut_source:
        error("engine maturity: Q5 vendor boundaries are no longer authority-derived")
    if "search_length_is_vendor_limit\": False" not in mut_source:
        error("engine maturity: Q5 implementation search length is not explicitly separated from vendor limits")
    workflows = (ROOT / "tools/src/pcr_tools/mutagenesis_workflows.py").read_text(encoding="utf-8")
    for marker in ("_QC_SINGLE = authority_record", "_QC_MULTI = authority_record", 'terms=authority["tm_formula_parameters"]'):
        if marker not in workflows:
            error(f"engine maturity: QuikChange vendor formula/geometry regained a parallel truth ({marker})")
    if "81.5 + 0.41" in workflows:
        error("engine maturity: QuikChange Tm formula coefficients were re-hardcoded outside authority")

    # ---- Nested: two-round / cleanup / carry-over boundaries -----------------
    nested = json.loads((ROOT / "contracts/chemistry/nested-protocols.json").read_text(encoding="utf-8"))
    nr = nested.get("records", {})
    for pid, expected in {
        "neb-msz-exonuclease-i": (1, 20, 55, 15, 80, 1),
        "neb-thermolabile-exonuclease-i": (1, 20, 37, 10, 80, 1),
    }.items():
        row = nr.get(pid, {})
        got = (row.get("enzyme_uL"), row.get("first_round_product_uL_max"), row.get("incubation_c"), row.get("incubation_min"), row.get("inactivation_c"), row.get("inactivation_min"))
        if got != expected:
            error(f"engine maturity: Nested cleanup authority drifted for {pid}: {got!r}")
    nested_source = (ROOT / "tools/src/pcr_tools/nested.py").read_text(encoding="utf-8")
    if 'NESTED_AUTHORITY["records"][cleanup]' not in nested_source:
        error("engine maturity: Nested cleanup numerics are no longer authority-resolved")
    if nr.get("dutp-ung-strategy-only", {}).get("execution_status") != "strategy-only":
        error("engine maturity: generic dUTP/UNG strategy gained an invented executable recipe")
    if nr.get("one-tube-reference-only", {}).get("execution_status") != "reference-only":
        error("engine maturity: generic one-tube Nested became executable without a versioned topology")
