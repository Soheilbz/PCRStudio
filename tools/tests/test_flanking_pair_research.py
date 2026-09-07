"""The flanking-pair research record must remain auditable.

These checks do not decide whether a biological claim is true. They protect
the evidence trail: every one of the eight assay records must keep the
parameter table, source section, implementation/test trail and an explicit
limitation. A future edit that turns a documented limitation into silence
should fail before it reaches a release.
"""

import re
import tomllib
from pathlib import Path

import pytest

from pcr_tools import validation_plan
from pcr_tools.pipeline import long_range_protocol, qpcr_protocol
from pcr_tools.presets import PURPOSES
from pcr_tools.thermo import analyse
from pcr_tools.validation_plan import for_assay

ROOT = Path(__file__).parents[2]
RESEARCH = ROOT / "knowledge" / "atlas" / "engines" / "flanking-pair"
ASSAYS = (
    "standard-pcr",
    "long-range-pcr",
    "colony-pcr",
    "qpcr-sybr",
    "digital-pcr",
    "species-specific-pcr",
    "rpa",
    "restriction-cloning",
)
VALIDATION_ASSAYS = ASSAYS
RECORD_FILES = {
    "standard-pcr": "02-standard-pcr.md",
    "long-range-pcr": "03-long-range-pcr.md",
    "colony-pcr": "04-colony-pcr.md",
    "qpcr-sybr": "05-qpcr-sybr.md",
    "digital-pcr": "06-digital-pcr.md",
    "species-specific-pcr": "07-species-specific-pcr.md",
    "rpa": "08-rpa.md",
    "restriction-cloning": "09-restriction-cloning.md",
}
PROFILE_DOC_FILES = {
    "standard-pcr": "02-standard-pcr.md",
    "long-range-pcr": "03-long-range-pcr.md",
    "colony-pcr": "04-colony-pcr.md",
    "qpcr-sybr": "05-qpcr-sybr.md",
    "digital-pcr": "06-digital-pcr.md",
    "species-specific-pcr": "07-species-specific-pcr.md",
    "rpa": "08-rpa.md",
    "restriction-cloning": "09-restriction-cloning.md",
}
RPA_REFERENCE_PRIMERS = (
    "TATCCGGAAACCTCCTCGGATTCCATTGCCCAGC",
    "GTGGGATTGTGCGTCATCCCTTACGTCAGTG",
    "TAAGATTGAATCCTGTTGCCGGTCTTGCGATGA",
    "CCTAGTTTGCGCGCTATATTTTGTTTTCTATCG",
)


def _strict_runtime_context(profile_id: str) -> dict[str, object]:
    """Minimum explicit scientific context required by strict module contracts."""
    if profile_id == "long-range-pcr":
        return {"long_range_protocol": "thermo-long-pcr-k018x"}
    if profile_id == "colony-pcr":
        return {
            "colony_host_class": "bacterial",
            "colony_preparation": "direct-transfer",
            "colony_protocol_id": "custom-sop",
            "colony_protocol_name": "research-regression SOP",
            "colony_protocol_provenance": "lab QA record / current test SOP revision",
        }
    if profile_id == "digital-pcr":
        return {
            "digital_partition_format": "droplet",
            "digital_platform_id": "bio-rad-qx200",
            "digital_platform_name": "Bio-Rad QX200",
            "digital_fragmentation_state": "not-assessed",
            "digital_protocol": "bio-rad-qx200-evagreen",
        }
    if profile_id == "species-specific-pcr":
        return {
            "background": ">near-relative\nAAAA",
            "inclusivity": ">target-member\n" + "ACGT" * 300,
            "inclusivity_panel_provenance": "RefSeq release X; target accession A.1",
            "background_panel_provenance": "RefSeq release X; near-neighbour accession B.1",
            "species_panel_selection_rationale": "target diversity and closest phylogenetic neighbours",
            "species_target_taxid": 562,
            "species_taxonomy_snapshot": "NCBI Taxonomy snapshot 2026-09-04",
            "species_database_snapshot": "RefSeq genomes release 232",
            "species_panel_accession_manifest": "GCF_000005845.2\nGCF_000008865.2",
            "species_panel_record_metadata_manifest": "target-member\tGCF_000005845.2\tinclusivity\tlinear\nnear-relative\tGCF_000008865.2\texclusivity\tlinear",
            "species_panel_retrieved_date": "2026-09-04",
        }
    if profile_id == "rpa":
        return {"rpa_protocol": "twistamp-basic"}
    return {}


SYBR_REFERENCE_PRIMERS = (
    "ACCCACTCCTCCACCTTTGAC",
    "TCCACCACCCTGTTGCTGTAG",
    "GTGATAGGTGTGAGGCAGGT",
    "GTGGCCGCCTTGATTCATAG",
    "TTTCTGCAGTTTCTGCTGCTA",
    "GAGACGTGTTCCTGGGATG",
)


def test_all_eight_records_keep_their_evidence_contract() -> None:
    required = (
        "## Parameter audit",
        "## Evidence",
        "implementation",
        "test",
        "Limitation",
        "## Verification record",
        "## Source-to-parameter map",
        "`limited`",
        "Runtime profile status",
        "Goal",
        "Modifiers",
    )

    missing: list[str] = []
    for assay in ASSAYS:
        record = RESEARCH / RECORD_FILES[assay]
        text = record.read_text(encoding="utf-8")
        missing.extend(f"{assay}: {phrase}" for phrase in required if phrase not in text)
        assert len(re.findall(r"https?://[^ )>]+", text)) >= 3, (
            f"{assay} needs at least three cited sources"
        )

    assert not missing, "research evidence contract is incomplete: " + "; ".join(missing)


def test_canonical_documents_keep_distinct_ownership_boundaries() -> None:
    engine = (RESEARCH / "00-engine.md").read_text(encoding="utf-8")
    tools = (RESEARCH / "01-tools.md").read_text(encoding="utf-8")
    expected_files = {
        "00-engine.md",
        "01-tools.md",
        "02-standard-pcr.md",
        "03-long-range-pcr.md",
        "04-colony-pcr.md",
        "05-qpcr-sybr.md",
        "06-digital-pcr.md",
        "07-species-specific-pcr.md",
        "08-rpa.md",
        "09-restriction-cloning.md",
    }
    assert {path.name for path in RESEARCH.glob("*.md")} == expected_files

    assert "Document ownership" in engine
    assert "Shared execution pipeline" in engine
    assert "no defaults, ranges, thresholds, concentrations" in tools
    assert "Primer3 global field vocabulary" in tools

    # A module-specific range belongs in its module record, not in the shared
    # engine or the tool vocabulary. This prevents a refactor from recreating
    # the old profile matrix in a central document.
    assert "18–25 nt" not in engine
    assert "18–25 nt" not in tools
    assert "5000–20000 bp" not in engine
    assert "5000–20000 bp" not in tools


def test_module_purpose_modes_match_the_runtime_profile_registry() -> None:
    """Purpose availability/defaults must be visible in the module atlas."""
    catalogue = ROOT / "crates" / "pcr-core" / "profiles.toml"
    profiles = tomllib.loads(catalogue.resolve().read_text(encoding="utf-8"))["profile"]
    all_purpose_ids = {purpose.id for purpose in PURPOSES}

    for profile in profiles:
        profile_id = profile["id"]
        if profile_id not in PROFILE_DOC_FILES:
            continue

        text = (RESEARCH / PROFILE_DOC_FILES[profile_id]).read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.startswith("| Purpose modes |")]
        assert len(rows) == 1, f"{profile_id} needs exactly one Purpose modes row"
        row = rows[0]
        defaults = profile.get("defaults", {})
        expected_default = defaults.get("defaultPurpose") or "general"
        allowed = set(defaults.get("purposes") or all_purpose_ids)

        assert f"`{expected_default}` is the default" in row
        for purpose_id in allowed:
            assert f"`{purpose_id}`" in row, f"{profile_id} hides purpose {purpose_id}"
        for purpose_id in all_purpose_ids - allowed:
            assert f"`{purpose_id}`" not in row, f"{profile_id} exposes purpose {purpose_id}"


def test_profile_capability_gates_and_required_inputs_are_in_their_records() -> None:
    """Top-level profile gates must not remain registry-only facts."""
    catalogue = ROOT / "crates" / "pcr-core" / "profiles.toml"
    profiles = tomllib.loads(catalogue.resolve().read_text(encoding="utf-8"))["profile"]

    for profile in profiles:
        profile_id = profile["id"]
        if profile_id not in PROFILE_DOC_FILES:
            continue
        text = (RESEARCH / PROFILE_DOC_FILES[profile_id]).read_text(encoding="utf-8")
        for requirement in profile.get("requires", []):
            assert f"`{requirement}`" in text, f"{profile_id} hides required input {requirement}"
        for capability in profile.get("enzyme", []):
            assert f"`{capability}`" in text, f"{profile_id} hides capability gate {capability}"


def test_research_records_keep_cited_paragraphs_and_clean_markdown() -> None:
    """Keep the atlas source-linked without allowing raw or hidden references."""

    internal_prefixes = (
        ">",
        "**Internal",
        "**Resolved",
        "When a row below is applicable",
        "Remote/browser/vendor tools remain",
        "Any Primer3 call from this engine",
        "An engine may use only a subset",
        "`MFEprimer` and `BLAST+` answer",
        "For BLAST+, at minimum",
        "Every engine distinguishes these states",
        "A remote validator is opt-in",
        "The preceding sections contain",
        "In addition to the shared error vocabulary",
        "All candidate pairs are retained",
        "Maintain fixtures for:",
        "This `01-tools.md` is considered complete",
    )
    headings = {"Sources:", "Shared references:"}

    for path in sorted(RESEARCH.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert all(line.rstrip() == line for line in text.splitlines()), path.name

        for lineno, line in enumerate(text.splitlines(), start=1):
            if "http://" in line or "https://" in line:
                assert re.search(r"\]\(https?://", line), f"raw URL at {path.name}:{lineno}"

        for blockno, block in enumerate(text.split("\n\n"), start=1):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines or lines[0].startswith(("#", "|", "- ", "* ", "```")):
                continue
            if lines[0] in headings or lines[0].startswith(internal_prefixes):
                continue
            assert "http" in block, f"uncited research paragraph at {path.name}:block{blockno}"

        if path.name.startswith(("02-", "03-", "04-", "05-", "06-", "07-", "08-", "09-")):
            in_atlas = False
            for lineno, line in enumerate(text.splitlines(), start=1):
                if line == "## Atlas overlay":
                    in_atlas = True
                    continue
                if in_atlas and line.startswith("## "):
                    break
                if (
                    in_atlas
                    and line.startswith("|")
                    and not line.startswith("| ---")
                    and not line.lower().startswith("| dimension |")
                ):
                    assert "http" in line, f"uncited Atlas row at {path.name}:{lineno}"


def test_tool_vocabulary_keeps_names_without_resolved_values() -> None:
    text = (RESEARCH / "01-tools.md").read_text(encoding="utf-8")
    for phrase in (
        "Primer3 / `primer3-py`",
        "bounded specificity scanner",
        "ViennaRNA worker",
        "NEBridge Golden Gate Assembly Tool",
        "NEBridge Ligase Fidelity Viewer / GetSet / SplitSet",
        "PRIMER_MIN_SIZE",
        "SEQUENCE_TEMPLATE",
        "seed_length",
        "evaluation_temperature",
        "Field-family ownership",
    ):
        assert phrase in text, f"tool vocabulary lost {phrase}"

    for phrase in (
        "ligase_identity",
        "ligase_fidelity_dataset",
        "overhang_set",
        "fragment_order",
        "part_purity",
        "mismatch_matrix",
    ):
        assert phrase in text, f"Golden Gate field vocabulary lost {phrase}"

    for phrase in ("Resolved reaction presets", "Search envelope", "18–25", "5000–20000"):
        assert phrase not in text, f"tool vocabulary contains resolved module data: {phrase}"


def test_every_flanking_pair_assay_exposes_one_structured_validation_contract() -> None:
    for assay in VALIDATION_ASSAYS:
        plan = for_assay(assay)
        assert plan is not None, f"missing validation contract for {assay}"
        assert plan["status"] == "in-silico-only"
        assert plan["scope"] == "sequence-design-and-preflight"
        assert plan["items"]
        assert plan["required"] == [item["label"] for item in plan["items"] if item["required"]]
        assert all(item["source"] and item["why"] for item in plan["items"])

    digital = for_assay("digital-pcr")
    assert digital is not None
    digital_items = {item["key"]: item for item in digital["items"]}
    assert "reaction_and_template_provenance" in digital_items
    assert "concentration_reporting_basis" in digital_items
    assert digital_items["analytical_specificity_and_sensitivity"]["required"] is True
    assert digital_items["validated_dynamic_range"]["required"] is True
    assert digital_items["full_process_repeatability_reproducibility"]["required"] is True
    assert digital_items["lob_lod_loq_when_relevant"]["required"] is False
    assert "dynamic_range_lod_loq" not in digital_items

    qpcr = for_assay("qpcr-sybr")
    assert qpcr is not None
    qpcr_items = {item["key"]: item for item in qpcr["items"]}
    assert "quantity_model_and_uncertainty" in qpcr_items
    assert qpcr_items["rna_quality_and_rt_provenance"]["required"] is False

    colony = for_assay("colony-pcr")
    assert colony is not None
    colony_items = {item["key"]: item for item in colony["items"]}
    assert "colony_sop_provenance" in colony_items
    assert "sampling_tool_and_biomass" in colony_items
    assert "medium_carryover" in colony_items
    assert colony_items["medium_carryover"]["required"] is False

    rpa = for_assay("rpa")
    assert rpa is not None
    rpa_items = {item["key"]: item for item in rpa["items"]}
    assert "rpa_mismatch_challenge" in rpa_items
    assert rpa_items["rpa_mismatch_challenge"]["required"] is False

    assert for_assay("not-an-assay") is None


def test_reference_comparison_does_not_hide_unsupported_claims() -> None:
    text = "\n".join(
        (RESEARCH / RECORD_FILES[assay]).read_text(encoding="utf-8") for assay in ASSAYS
    )
    assert "PMC4227211" in text
    assert "PMC5540129" in text
    assert "PMC4893258" in text
    assert "PMC6653534" in text
    assert "Indel-aware homology is not inferred" in text
    assert "not a universal" in text


def test_extended_primary_evidence_remains_attached_to_the_right_module() -> None:
    long_range = (RESEARCH / RECORD_FILES["long-range-pcr"]).read_text(encoding="utf-8")
    colony = (RESEARCH / RECORD_FILES["colony-pcr"]).read_text(encoding="utf-8")
    species = (RESEARCH / RECORD_FILES["species-specific-pcr"]).read_text(encoding="utf-8")
    cloning = (RESEARCH / RECORD_FILES["restriction-cloning"]).read_text(encoding="utf-8")
    rpa = (RESEARCH / RECORD_FILES["rpa"]).read_text(encoding="utf-8")
    sybr = (RESEARCH / RECORD_FILES["qpcr-sybr"]).read_text(encoding="utf-8")

    assert all(
        marker in long_range
        for marker in (
            "Thermo K0181 protocol",
            "Takara PrimeSTAR GXL manual",
            "Roche Expand Long Template manual",
            "Processivity, fidelity and reach",
            "Difficult-template branch",
        )
    )
    assert all(
        marker in colony for marker in ("28540704", "19024172", "Host class and lysis branch")
    )
    assert all(
        marker in species
        for marker in ("27768246", "12514007", "Reference database and locus choice")
    )
    assert all(
        marker in cloning
        for marker in (
            "6323183",
            "30335370",
            "32877448",
            "37755329",
            "Overhang-set fidelity and bias",
            "Assembly complexity, purity and stoichiometry",
        )
    )
    assert all(
        marker in rpa
        for marker in (
            "tm_pair_max_difference=100.0",
            "min_three_prime_distance=1",
            "finite implementation sentinels",
        )
    )
    assert all(
        marker in sybr
        for marker in (
            "Efficiency calculation",
            "LOD/LLOQ copy-number boundary",
            "3` target copies",
        )
    )


def test_current_golden_gate_protective_base_rule_is_not_regressed() -> None:
    cloning = (RESEARCH / RECORD_FILES["restriction-cloning"]).read_text(encoding="utf-8")
    assert "current guidance" in cloning
    assert "also gives six base pairs as the Golden Gate starting recommendation" in cloning
    assert "its Golden Gate recommendation is 6–8 bp" not in cloning


def test_rpa_probe_chemistry_boundary_stays_explicit_and_cited() -> None:
    record_text = (RESEARCH / RECORD_FILES["rpa"]).read_text(encoding="utf-8")
    comparisons = record_text
    for text in (record_text, comparisons):
        assert "THF" in text
        assert "3′" in text and "block" in text
        assert "plain ACGT" in text
    assert "INASDM" in record_text
    assert "PMC8283572" in record_text
    assert "PMC8584857" in comparisons


def test_indel_specificity_limitation_and_external_handoff_stay_explicit() -> None:
    standard = (RESEARCH / RECORD_FILES["standard-pcr"]).read_text(encoding="utf-8")
    species = (RESEARCH / RECORD_FILES["species-specific-pcr"]).read_text(encoding="utf-8")
    assert "Primer-BLAST" in standard
    assert "bulge" in standard
    assert "Indel-aware homology is not inferred" in species


def test_gc_clamp_is_documented_as_profile_specific_not_universal() -> None:
    standard = (RESEARCH / RECORD_FILES["standard-pcr"]).read_text(encoding="utf-8")
    comparisons = "\n".join(
        (RESEARCH / RECORD_FILES[assay]).read_text(encoding="utf-8") for assay in ASSAYS
    )
    assert "15488375" in standard
    assert "not a universal clamp" in comparisons
    # Standard PCR deliberately replaces the shared fallback with a soft
    # empirical triplet score instead of a universal hard clamp.
    assert _assay("standard-pcr")["defaults"]["constraints"]["gc_clamp"] == 0
    assert _assay("qpcr-sybr")["defaults"]["constraints"]["gc_clamp"] == 0


def test_end_stability_scale_is_not_misattributed_to_base_primer3() -> None:
    design = (ROOT / "tools" / "src" / "pcr_tools" / "design.py").read_text(encoding="utf-8")
    pipeline = (ROOT / "tools" / "src" / "pcr_tools" / "pipeline.py").read_text(encoding="utf-8")

    # Keep the distinction in executable comments; resolved tool values are
    # intentionally not duplicated in the tool vocabulary document.
    assert "is 100 (effectively no practical ceiling)" in design
    assert "Primer3Plus" in pipeline


def test_published_rpa_primer_examples_fit_the_documented_search_envelope() -> None:
    for sequence in RPA_REFERENCE_PRIMERS:
        report = analyse(sequence)
        assert 30 <= len(sequence) <= 35
        assert 30.0 <= report.gc_percent <= 70.0


def test_published_sybr_primer_examples_fit_the_documented_qpcr_envelope() -> None:
    for sequence in SYBR_REFERENCE_PRIMERS:
        report = analyse(sequence)
        assert 18 <= len(sequence) <= 24
        assert 40.0 <= report.gc_percent <= 60.0


def _assay(profile_id: str) -> dict:
    """Read the shipped assay contract instead of copying it into a test."""
    catalogue = ROOT / "crates" / "pcr-core" / "profiles.toml"
    entries = tomllib.loads(catalogue.resolve().read_text(encoding="utf-8"))["profile"]
    entry = next(profile for profile in entries if profile["id"] == profile_id)
    return {
        "id": entry["id"],
        "name": entry["name"],
        "defaults": entry.get("defaults", {}),
    }


def test_current_flanking_protocol_registry_keeps_vendor_boundaries_explicit() -> None:
    """Protocol records are code to be exercised by the Linux suite later.

    This source regression prevents a future refactor from silently collapsing
    current/historical long-PCR, RPA, qPCR or dPCR branches back into one recipe.
    """
    from pcr_tools.pipeline import (
        digital_protocol,
        long_range_protocol,
        qpcr_protocol,
        rpa_protocol,
    )

    itaq = qpcr_protocol("bio-rad-itaq-sybr", assay_id="qpcr-sybr")
    luna = qpcr_protocol("neb-luna-universal-m3003", assay_id="qpcr-sybr")
    luna_rt = qpcr_protocol("neb-luna-one-step-rt-qpcr-e3005", assay_id="qpcr-sybr", from_rna=True)
    powerup = qpcr_protocol("thermo-powerup-sybr-a2574x", assay_id="qpcr-sybr")
    liquid = rpa_protocol("twistamp-liquid-basic", assay_id="rpa")
    longamp = long_range_protocol("neb-longamp-taq-m0323", assay_id="long-range-pcr")
    takara = long_range_protocol("takara-primestar-gxl-r050a-standard", assay_id="long-range-pcr")
    ultrarun = long_range_protocol(
        "qiagen-ultrarun-longrange-206442-206444", assay_id="long-range-pcr"
    )
    qia = digital_protocol("qiagen-qiacuity-eg", assay_id="digital-pcr")
    qia_one_step = digital_protocol(
        "qiagen-qiacuity-onestep-advanced-eg", assay_id="digital-pcr", from_rna=True
    )
    qx700 = digital_protocol("bio-rad-qx700-naica-evagreen", assay_id="digital-pcr")
    qx200 = digital_protocol("bio-rad-qx200-evagreen", assay_id="digital-pcr")

    assert itaq and itaq["reaction_volume_uL"] == {"supported_10": 10, "supported_20": 20}
    assert itaq["primer_final_concentration_nM"] == {
        "optimization_min": 300,
        "optimization_max": 500,
    }
    assert luna and luna["protocol_id"] == "neb-luna-universal-m3003"
    assert luna["amplicon_bp_preferred"] == {"min": 70, "max": 200}
    assert luna["carryover_prevention"]["optional_udg_pretreatment"] == {
        "temperature_c": 25,
        "minutes": 10,
    }
    assert luna["carryover_prevention"]["enabled_by_protocol_selection_alone"] is False
    assert luna_rt and luna_rt["protocol_id"] == "neb-luna-one-step-rt-qpcr-e3005"
    assert luna_rt["primer_final_concentration_nM"]["starting"] == 400
    assert luna_rt["reverse_transcription"]["temperature_c"] == 55
    assert luna_rt["reverse_transcription"]["incubation_minutes"] == 10
    assert luna_rt["carryover_prevention"]["dUTP_in_master_mix"] is True
    assert luna_rt["carryover_prevention"]["UDG_built_in"] is False
    assert ultrarun and ultrarun["protocol_id"] == "qiagen-ultrarun-longrange-206442-206444"
    assert ultrarun["reaction_volume_uL"]["standard"] == 20
    assert ultrarun["primer_final_concentration_uM"] == 0.5
    assert ultrarun["cycling_model"]["standard_two_step"]["anneal_extend"]["seconds_per_kb"] == 30
    assert ultrarun["optional_q_solution"]["automatic_activation"] is False
    assert luna_rt["carryover_prevention"]["optional_udg_pretreatment"] == {
        "temperature_c": 25,
        "minutes": 2,
    }
    assert luna_rt["genomic_dna_control"]["no_rt_control_recommended"] is True
    assert luna_rt["transcript_design"]["hard_requirement_for_every_transcript"] is False
    assert powerup and powerup["protocol_id"] == "thermo-powerup-sybr-a2574x"
    assert powerup["reaction_volume_uL"] == {"supported_10": 10, "supported_20": 20}
    assert powerup["primer_final_concentration_nM"] == {
        "optimization_min": 300,
        "optimization_max": 800,
    }
    assert liquid and liquid["protocol_id"] == "twistamp-liquid-basic"
    assert liquid["oligo_contract"] == "plain-acgt-two-primer"
    assert liquid["modified_probe_support"] is False
    assert liquid["readout_contract"] == "endpoint-product-detection-modality-not-inferred"
    assert liquid["contamination_control"]["separate_pre_post_amplification_areas"] is True
    assert liquid["contamination_control"]["post_amplification_opening_high_risk"] is True
    assert longamp and longamp["magnesium_chloride_mM"] == 2.0
    assert takara and takara["constraints"] == {"length_min": 25, "length_max": 35}
    assert qia and qia["protocol_id"] == "qiagen-qiacuity-eg"
    assert qia_one_step and qia_one_step["protocol_id"] == "qiagen-qiacuity-onestep-advanced-eg"
    assert qia_one_step["constraints"]["length_max"] == 30
    assert qia_one_step["constraints"]["gc_min"] == 30.0
    assert qia_one_step["constraints"]["tm_max"] == 62.0
    assert qia_one_step["reverse_transcription"]["temperature_c"] == 50
    assert qia_one_step["reverse_transcription"]["incubation_minutes"] == 40
    assert qx700 and qx700["reaction_volume_uL"] == 5
    assert qx700["amplicon_bp_preferred"] == {"min": 60, "max": 130}
    assert qx700["primer_concentration_status"].startswith("supplier-variable")
    assert qx200 and qx200["carryover_prevention"]["UNG_compatible"] is True
    assert qx200["carryover_prevention"]["enabled_by_protocol_selection_alone"] is False
    assert (
        qx200["fragmentation_guidance"]["in_reaction_starting_units"]
        == "approximately 2-5 U per 20 uL reaction when direct digestion is used"
    )


def test_dpcr_run_handoff_keeps_partition_volume_and_software_authority_explicit() -> None:
    from pcr_tools.pipeline import digital_context

    qia = digital_context(
        {
            "digital_platform_id": "qiagen-qiacuity",
            "digital_platform_name": "QIAGEN QIAcuity",
            "digital_partition_format": "chamber",
            "digital_fragmentation_state": "not-assessed",
            "digital_protocol": "qiagen-qiacuity-eg",
        },
        assay_id="digital-pcr",
    )
    assert qia is not None
    assert "VPF" in qia["volume_precision_factor_status"]
    assert "Nanoplate" in " ".join(qia["required_run_evidence"])
    assert qia["analysis_software_version_status"].startswith("record-exact")

    qx = digital_context(
        {
            "digital_platform_id": "bio-rad-qx200",
            "digital_platform_name": "Bio-Rad QX200",
            "digital_partition_format": "droplet",
            "digital_fragmentation_state": "not-assessed",
            "digital_protocol": "bio-rad-qx200-evagreen",
        },
        assay_id="digital-pcr",
    )
    assert qx is not None
    assert (
        qx["volume_precision_factor_status"] == "platform-specific-volume-correction-not-inferred"
    )
    assert "volume source" in " ".join(qx["required_run_evidence"])


def test_luna_e3005_is_not_silently_used_as_a_dna_only_qpcr_overlay() -> None:
    from pcr_tools.pipeline import qpcr_protocol

    with pytest.raises(ValueError, match="from_rna=true"):
        qpcr_protocol("neb-luna-one-step-rt-qpcr-e3005", assay_id="qpcr-sybr")


def test_thermo_lyo_ready_rpa_keeps_supplier_constraints_and_named_rt_recipe() -> None:
    from pcr_tools.pipeline import rpa_protocol

    dna = rpa_protocol("thermo-lyo-ready-rpa", assay_id="rpa", from_rna=False)
    rna = rpa_protocol("thermo-lyo-ready-rpa", assay_id="rpa", from_rna=True)
    assert dna and rna
    assert dna["reaction_volume_uL"] == {"standard": 20, "source_backed_scaled": 50}
    assert dna["reaction_scaling"]["supported_uL"] == [20, 50]
    assert rna["reaction_volume_uL"] == {"standard": 20, "source_backed_scaled": 50}
    assert rna["reaction_scaling"]["supported_uL"] == [20, 50]
    assert dna["constraints"] == {
        "length_min": 30,
        "length_max": 35,
        "gc_min": 30,
        "gc_max": 70,
        "product_min": 150,
        "product_max": 450,
    }
    assert dna["magnesium_chloride_mM"] == 14
    assert dna["dntp_each_mM"] == 0.2
    assert dna["sequence_decision_impact"] == "constraint-envelope"
    assert dna["amplicon_gc_percent"] == {
        "min": 35,
        "max": 60,
        "status": "enforced-named-protocol-amplicon-composition-filter",
        "scope": "whole predicted amplicon GC; never substituted for primer GC",
    }
    assert dna["oligo_contract"] == "plain-acgt-two-primer"
    assert dna["modified_probe_support"] is False
    assert dna["readout_contract"] == "endpoint-product-detection-modality-not-inferred"
    assert (
        dna["contamination_control"]["environment_and_carryover_false_positive_recognized"] is True
    )
    assert dna["contamination_control"]["separate_endpoint_workspace_when_opening_tubes"] is True
    assert "reverse_transcription" not in dna
    rt = rna["reverse_transcription"]
    assert rt["mode"] == "one-pot-rt-rpa"
    assert rt["reverse_transcriptase"] == "SuperScript IV Reverse Transcriptase"
    assert rt["reverse_transcriptase_final_U_per_uL"] == 2.0
    assert rt["rnase_inhibitor_final_U_per_uL"] == 1.6
    assert rt["rnase_h_final_U_per_uL"] == 0.1


def test_twistamp_basic_rna_does_not_inherit_the_thermo_rt_recipe() -> None:
    from pcr_tools.pipeline import rpa_protocol

    with pytest.raises(ValueError, match="thermo-lyo-ready-rpa"):
        rpa_protocol("twistamp-basic", assay_id="rpa", from_rna=True)


def test_twistamp_basic_and_liquid_basic_share_the_current_ecoli_supplier_boundary() -> None:
    from pcr_tools.pipeline import rpa_protocol

    basic = rpa_protocol("twistamp-basic", assay_id="rpa")
    liquid = rpa_protocol("twistamp-liquid-basic", assay_id="rpa")
    assert basic and liquid
    for protocol in (basic, liquid):
        warning = protocol["production_dna_warning"]
        assert "standard laboratory E. coli" in warning["supplier_boundary"]
        assert warning["organism_inferred_from_sequence"] is False


def test_long_range_vendor_cycling_models_keep_published_long_extensions():
    neb = long_range_protocol("neb-longamp-taq-m0323", assay_id="long-range-pcr")
    assert neb is not None
    assert neb["cycling_model"]["final_extension"] == {"temperature_c": 65, "minutes": 10}

    takara = long_range_protocol("takara-primestar-gxl-r050a-standard", assay_id="long-range-pcr")
    assert takara is not None
    assert takara["cycling_model"]["10_to_30kb"]["anneal_extend"] == {
        "temperature_c": 68,
        "minutes": 10,
    }

    ultrarun = long_range_protocol(
        "qiagen-ultrarun-longrange-206442-206444", assay_id="long-range-pcr"
    )
    assert ultrarun is not None
    assert ultrarun["cycling_model"]["standard_two_step"]["anneal_extend"]["temperature_c"] == 65
    assert ultrarun["cycling_model"]["alternative_three_step"]["extension"] == {
        "temperature_c": 68,
        "seconds_per_kb": 30,
        "genomic_dna_context": True,
    }


def test_itaq_current_reaction_and_primer_starting_points_are_preserved():
    protocol = qpcr_protocol("bio-rad-itaq-sybr", assay_id="qpcr-sybr")
    assert protocol is not None
    assert protocol["reaction_volume_uL"] == {"supported_10": 10, "supported_20": 20}
    assert protocol["primer_final_concentration_nM"] == {
        "optimization_min": 300,
        "optimization_max": 500,
    }
    assert protocol["amplicon_bp_preferred"] == {"min": 70, "max": 150}
    assert (
        protocol["cycling_model"]["polymerase_activation_and_dna_denaturation"]["temperature_c"]
        == 95
    )


def test_rna_validation_contract_promotes_rt_evidence_to_required():
    qpcr = validation_plan.for_assay("qpcr-sybr", from_rna=True)
    dpcr = validation_plan.for_assay("digital-pcr", from_rna=True)
    rpa = validation_plan.for_assay("rpa", from_rna=True)
    assert qpcr is not None and dpcr is not None and rpa is not None
    for plan, keys in (
        (qpcr, {"rt_minus_control", "rna_quality_and_rt_provenance"}),
        (dpcr, {"rt_minus_control", "rna_quality_and_rt_provenance"}),
        (rpa, {"rt_minus_control", "rna_input_and_rt_provenance"}),
    ):
        indexed = {item["key"]: item for item in plan["items"]}
        assert all(indexed[key]["required"] is True for key in keys)


def test_dna_validation_contract_keeps_rna_only_evidence_conditional():
    for assay_id, keys in (
        ("qpcr-sybr", {"rt_minus_control", "rna_quality_and_rt_provenance"}),
        ("digital-pcr", {"rt_minus_control", "rna_quality_and_rt_provenance"}),
        ("rpa", {"rt_minus_control", "rna_input_and_rt_provenance"}),
    ):
        plan = validation_plan.for_assay(assay_id, from_rna=False)
        assert plan is not None
        indexed = {item["key"]: item for item in plan["items"]}
        assert all(indexed[key]["required"] is False for key in keys)


def test_colony_validation_requires_recoverable_source_but_not_universal_orientation():
    plan = validation_plan.for_assay("colony-pcr")
    assert plan is not None
    indexed = {item["key"]: item for item in plan["items"]}
    assert indexed["retained_clone_source"]["required"] is True
    assert indexed["insert_orientation"]["required"] is False


def test_current_luna_m3003_and_thermo_rpa_revision_provenance_is_pinned():
    from pcr_tools.pipeline import qpcr_protocol, rpa_protocol

    luna = qpcr_protocol("neb-luna-universal-m3003", assay_id="qpcr-sybr")
    thermo_rpa = rpa_protocol("thermo-lyo-ready-rpa", assay_id="rpa")
    assert luna and luna["source_revision"] == "Version 3.0"
    assert luna["source_revision_date"] == "2020-03"
    assert thermo_rpa and thermo_rpa["source_revision"] == "Rev B"
    assert thermo_rpa["source_revision_date"] == "2025-03-06"


def test_species_per_record_circular_specificity_detects_origin_crossing_product_only_for_circular_record():
    from pcr_tools.specificity import Site, products_from

    def site(*, role: str, three_prime_at: int, orientation: str, contig: str = "circ") -> Site:
        return Site(
            primer="A" * 20,
            role=role,
            contig=contig,
            three_prime_at=three_prime_at,
            orientation=orientation,
            mismatches=0,
            dg=-10.0,
            tm=60.0,
        )

    sites = [
        site(role="left", three_prime_at=95, orientation="forward"),
        site(role="right", three_prime_at=8, orientation="reverse"),
    ]
    assert products_from(sites, max_product=100) == []
    circular = products_from(sites, max_product=100, circular_lengths={"circ": 100})
    assert len(circular) == 1
    assert circular[0].size <= 100
