"""Keep the 11-engine documentation atlas canonical and auditable."""

import re
import tomllib
from pathlib import Path

from pcr_tools.presets import PURPOSES

ROOT = Path(__file__).parents[2]
DOCS = ROOT / "knowledge" / "atlas" / "engines"
EXPECTED = {
    "consensus-pair": ("universal-primers",),
    "discriminating-pair": ("arms-pcr", "kasp", "tetra-primer-arms"),
    "flanking-pair": (
        "standard-pcr",
        "long-range-pcr",
        "colony-pcr",
        "qpcr-sybr",
        "digital-pcr",
        "species-specific-pcr",
        "rpa",
        "restriction-cloning",
    ),
    "junction-primers": ("gibson-assembly",),
    "loop-set": ("lamp",),
    "mutagenic-pair": ("site-directed-mutagenesis",),
    "nested": ("nested-pcr",),
    "outward-pair": ("inverse-pcr",),
    "pair-and-probe": ("qpcr-probe",),
    "single-primer": ("race", "sequencing-primer"),
    "tiling-scheme": ("tiled-scheme",),
}


def _module_path(engine: str, module: str) -> Path:
    matches = sorted((DOCS / engine).glob(f"*-{module}.md"))
    assert len(matches) == 1, f"{engine}/{module} must have one numbered record"
    return matches[0]


def test_engine_atlas_has_exactly_11_engines_and_21_module_records() -> None:
    assert {path.name for path in DOCS.iterdir() if path.is_dir()} == set(EXPECTED)
    assert sum(len(modules) for modules in EXPECTED.values()) == 21

    for engine, modules in EXPECTED.items():
        folder = DOCS / engine
        assert (folder / "00-engine.md").is_file(), engine
        assert (folder / "01-tools.md").is_file(), engine
        actual = {
            re.sub(r"^\d\d-", "", path.name).removesuffix(".md")
            for path in folder.glob("[0-9][0-9]-*.md")
            if path.name not in {"00-engine.md", "01-tools.md"}
        }
        assert actual == set(modules), engine


def test_module_metadata_matches_the_profile_registry() -> None:
    catalogue = ROOT / "crates" / "pcr-core" / "profiles.toml"
    profiles = tomllib.loads(catalogue.read_text(encoding="utf-8"))["profile"]
    module_ids = {module for modules in EXPECTED.values() for module in modules}

    for profile in profiles:
        profile_id = profile["id"]
        if profile_id not in module_ids:
            continue
        engine = profile["engine"]
        text = _module_path(engine, profile_id).read_text(encoding="utf-8")
        assert (
            f"| Profile ID | `{profile_id}` |" in text
            or f"| Profile | `crates/pcr-core/profiles.toml`, `{profile_id}` |" in text
            or f"| Profile | `{profile_id}` |" in text
        )
        assert f"| Runtime profile status | {profile['status']} |" in text
        assert f"| Goal | `{profile['goal']}` |" in text
        modifiers = ", ".join(f"`{modifier}`" for modifier in profile.get("modifiers", []))
        if not modifiers:
            modifiers = "none"
        assert f"| Modifiers | {modifiers} |" in text


def test_purpose_modes_are_not_falsely_narrowed_in_module_atlas() -> None:
    catalogue = ROOT / "crates" / "pcr-core" / "profiles.toml"
    profiles = tomllib.loads(catalogue.read_text(encoding="utf-8"))["profile"]
    module_ids = {module for modules in EXPECTED.values() for module in modules}
    all_purpose_ids = {purpose.id for purpose in PURPOSES}

    for profile in profiles:
        if profile["id"] not in module_ids:
            continue
        text = _module_path(profile["engine"], profile["id"]).read_text(encoding="utf-8")
        defaults = profile.get("defaults", {})
        expected_default = defaults.get("defaultPurpose") or "general"
        allowed = set(defaults.get("purposes") or all_purpose_ids)
        rows = [line for line in text.splitlines() if line.startswith("| Purpose modes |")]
        assert len(rows) == 1, f"{profile['id']} needs exactly one Purpose modes row"
        row = rows[0]
        assert f"`{expected_default}` is the default" in row
        for purpose_id in allowed:
            assert f"`{purpose_id}`" in row, f"{profile['id']} hides purpose {purpose_id}"
        for purpose_id in all_purpose_ids - allowed:
            assert f"`{purpose_id}`" not in row, f"{profile['id']} exposes purpose {purpose_id}"


def test_profile_purposes_exist_in_the_worker_purpose_catalogue() -> None:
    catalogue = ROOT / "crates" / "pcr-core" / "profiles.toml"
    profiles = tomllib.loads(catalogue.read_text(encoding="utf-8"))["profile"]
    known = {purpose.id for purpose in PURPOSES}
    unknown = {
        purpose
        for profile in profiles
        for purpose in profile.get("defaults", {}).get("purposes", [])
        if purpose not in known
    }
    assert not unknown, f"profiles name purposes absent from worker catalogue: {sorted(unknown)}"


def test_profile_default_purposes_exist_in_the_worker_purpose_catalogue() -> None:
    catalogue = ROOT / "crates" / "pcr-core" / "profiles.toml"
    profiles = tomllib.loads(catalogue.read_text(encoding="utf-8"))["profile"]
    known = {purpose.id for purpose in PURPOSES}
    unknown = {
        profile["defaults"]["defaultPurpose"]
        for profile in profiles
        if "defaultPurpose" in profile.get("defaults", {})
        and profile["defaults"]["defaultPurpose"] not in known
    }
    assert not unknown, (
        f"profiles name default purposes absent from worker catalogue: {sorted(unknown)}"
    )


def test_every_profile_default_key_is_named_in_its_module_record() -> None:
    catalogue = ROOT / "crates" / "pcr-core" / "profiles.toml"
    profiles = tomllib.loads(catalogue.read_text(encoding="utf-8"))["profile"]
    module_ids = {module for modules in EXPECTED.values() for module in modules}

    for profile in profiles:
        if profile["id"] not in module_ids:
            continue
        text = _module_path(profile["engine"], profile["id"]).read_text(encoding="utf-8")
        defaults = profile.get("defaults", {})
        if "polymerase" in defaults:
            assert f"`{defaults['polymerase']}`" in text
        for key in defaults.get("constraints", {}):
            assert re.search(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])", text), (
                f"{profile['id']} hides constraint {key}"
            )
        for key in defaults.get("cycling", {}):
            assert re.search(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])", text), (
                f"{profile['id']} hides cycling key {key}"
            )


def test_numbered_module_records_keep_the_evidence_contract() -> None:
    required = (
        "## Atlas overlay",
        "## Parameter audit",
        "## Evidence",
        "## Source-to-parameter map",
        "## Verification record",
        "`limited`",
        "implementation",
        "test",
    )
    for engine, modules in EXPECTED.items():
        for module in modules:
            text = _module_path(engine, module).read_text(encoding="utf-8")
            missing = [phrase for phrase in required if phrase.lower() not in text.lower()]
            assert not missing, f"{engine}/{module}: missing {missing}"
            assert len(re.findall(r"\]\(https?://", text)) >= 3
            assert text.count("## Runtime profile binding") == 1, (
                f"{engine}/{module}: runtime binding section must be unique"
            )


def test_tool_records_name_fields_without_resolving_module_values() -> None:
    forbidden = (
        "Resolved reaction presets",
        "product_min =",
        "product_max =",
        "length_min =",
        "length_max =",
        "tm_min =",
        "tm_max =",
        "overlap_length =",
    )
    for engine in EXPECTED:
        text = (DOCS / engine / "01-tools.md").read_text(encoding="utf-8")
        assert "vocabulary" in text.lower()
        assert not any(phrase in text for phrase in forbidden), engine


def test_module_records_have_no_raw_urls_or_uncited_atlas_rows() -> None:
    for engine, modules in EXPECTED.items():
        for module in modules:
            path = _module_path(engine, module)
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if "http://" in line or "https://" in line:
                    assert "](" in line, f"raw URL at {path}:{lineno}"

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
                    assert "http" in line, f"uncited Atlas row at {path}:{lineno}"


def test_module_research_paragraphs_keep_an_external_reference() -> None:
    """Scientific prose must retain a nearby source instead of becoming folklore."""
    for engine, modules in EXPECTED.items():
        for module in modules:
            text = _module_path(engine, module).read_text(encoding="utf-8")
            for blockno, block in enumerate(text.split("\n\n"), start=1):
                lines = [line.strip() for line in block.splitlines() if line.strip()]
                if not lines or lines[0].startswith(("#", "|", "- ", "* ", "```")):
                    continue
                if lines[0] in {"Sources:", "Shared references:"}:
                    continue
                if lines[0].startswith(("**Engine ID", "**Internal", "**Resolved", "This file is")):
                    continue
                assert "http" in block, f"uncited prose at {engine}/{module}:block{blockno}"


def test_product_specific_protocol_overlays_keep_distinct_identifiers() -> None:
    """Vendor values must stay tied to the product that published them."""
    arms = _module_path("discriminating-pair", "arms-pcr").read_text(encoding="utf-8")
    nested = _module_path("nested", "nested-pcr").read_text(encoding="utf-8")

    assert "Platinum II Taq ARMS technical note" in arms
    assert "named `arms_protocol`" in arms
    assert "Thermolabile Exonuclease I FAQ" in nested
    assert "Msz Exonuclease I FAQ" in nested
    assert "must not be merged" in nested
    assert "exact exonuclease product/catalogue and version" in nested


def test_probe_engine_does_not_collapse_distinct_fluorescence_chemistries() -> None:
    """Hydrolysis, Scorpion and beacon mechanisms need separate contracts."""
    probe = _module_path("pair-and-probe", "qpcr-probe").read_text(encoding="utf-8")

    assert "Probe-chemistry boundary" in probe
    assert "probe_chemistry=taqman-mgb" in probe
    assert "scorpion" in probe
    assert "molecular-beacon" in probe
    assert "must be refused or" in probe
    assert "dedicated chemistry contract" in probe


def test_consensus_tool_record_keeps_alignment_and_degenerate_methods_explicit() -> None:
    """The tool atlas must name methods without hiding module-level values."""
    tools = (DOCS / "consensus-pair" / "01-tools.md").read_text(encoding="utf-8")

    for method in ("MAFFT", "MUSCLE", "Clustal Omega", "HYDEN", "DegePrime", "CODEHOP"):
        assert method in tools
    for field in (
        "alignment_strategy",
        "gap_policy",
        "max_degeneracy",
        "coverage_fraction",
        "consensus_clamp",
        "degenerate_core",
    ):
        assert f"`{field}`" in tools
    assert "numeric defaults" in tools
    assert "https://" in tools


def test_universal_tm_pair_ceiling_discloses_a_conflicting_published_criterion() -> None:
    """A permissive exploration ceiling must not masquerade as literature consensus."""
    universal = _module_path("consensus-pair", "universal-primers").read_text(encoding="utf-8")

    assert "`16 °C`" in universal
    assert "below `5 °C`" in universal
    assert "Klindworth" in universal
    assert "not an experimentally validated shared-anneal window" in universal


def test_canonical_mismatch_citation_is_not_mislabeled_as_the_arms_paper() -> None:
    """The Kwok label must not point at Newton's separate ARMS paper."""
    for path in DOCS.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "Kwok et al." in text:
            assert "[Kwok et al.](https://pubmed.ncbi.nlm.nih.gov/2259643/)" not in text, path
