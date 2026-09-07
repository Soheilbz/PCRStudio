"""Source-backed bench protocol registries for flanking-pair assays.

These records are chemistry/protocol data, not candidate-generation logic.  They
were split from :mod:`pcr_tools.pipeline` in Generation 1 foundation so named product
branches can evolve without turning the scientific orchestrator into a registry
monolith.  Public names are re-exported by ``pipeline`` for legacy compatibility.
"""
from __future__ import annotations

import hashlib
import json
import math

from typing import Any

# Multiplex bounds are source-backed planning boundaries, never wet-lab
# qualification claims. The canonical modality/platform registry is generated
# from contracts/multiplex-capabilities.json so Python does not maintain an
# independent platform-capability table.
DIGITAL_MULTIPLEX_SOFTWARE_MAX_TARGETS = 12
from importlib.resources import files

_MULTIPLEX_CAPABILITIES = json.loads(
    files("pcr_tools").joinpath("data/multiplex-capabilities.generated.json").read_text(encoding="utf-8")
)
DIGITAL_MULTIPLEX_PLATFORM_AUTHORITIES = dict(_MULTIPLEX_CAPABILITIES.get("platform_authorities") or {})
QIACUITY_HIGH_MULTIPLEX_MODELS = frozenset({"qiacuity-one-5plex", "qiacuity-four", "qiacuity-eight"})
QIACUITY_CHANNEL_TARGET_MAX = int(DIGITAL_MULTIPLEX_PLATFORM_AUTHORITIES["qiacuity-one-5plex"]["detection_channels"])
QIACUITY_ONE_2PLEX_CHANNEL_MAX = int(DIGITAL_MULTIPLEX_PLATFORM_AUTHORITIES["qiacuity-one-2plex"]["detection_channels"])
QIACUITY_ONE_2PLEX_MULTIPLEX_MAX = int(DIGITAL_MULTIPLEX_PLATFORM_AUTHORITIES["qiacuity-one-2plex"]["multiplex_target_bound"])
QX600_CHANNEL_TARGET_MAX = int(DIGITAL_MULTIPLEX_PLATFORM_AUTHORITIES["bio-rad-qx600"]["detection_channels"])
QX600_MULTIPLEX_MAX = int(DIGITAL_MULTIPLEX_PLATFORM_AUTHORITIES["bio-rad-qx600"]["multiplex_target_bound"])

_PROTOCOL_AUTHORITY = json.loads(
    files("pcr_tools").joinpath("data/flanking-protocol-authority.generated.json").read_text(encoding="utf-8")
)
_GROUPS = _PROTOCOL_AUTHORITY["groups"]
STANDARD_PCR_PROTOCOLS = tuple(_GROUPS["standard_pcr"])
QPCR_PROTOCOLS = tuple(_GROUPS["qpcr_sybr"])
RPA_PROTOCOLS = tuple(_GROUPS["rpa"])
RPA_EXECUTABLE_PROTOCOLS = tuple(_GROUPS["rpa_executable"])
LONG_RANGE_PROTOCOLS = tuple(_GROUPS["long_range"])
DIGITAL_PROTOCOLS = tuple(_GROUPS["digital"])
DIGITAL_PARTITION_FORMATS = set(_GROUPS["digital_partition_formats"])
DIGITAL_PLATFORM_IDS = set(_GROUPS["digital_platform_ids"])
DIGITAL_FRAGMENTATION_STATES = set(_GROUPS["digital_fragmentation_states"])
QPCR_INSTRUMENT_PROFILES = set(_GROUPS["qpcr_instrument_profiles"])
DIGITAL_CONSUMABLE_IDS = set(_GROUPS["digital_consumable_ids"])
DIGITAL_CONSUMABLE_PLATFORMS = {key: frozenset(value) for key, value in _PROTOCOL_AUTHORITY["compatibility"]["digital_consumable_platforms"].items()}
DIGITAL_PROTOCOL_PLATFORMS = {key: frozenset(value) for key, value in _PROTOCOL_AUTHORITY["compatibility"]["digital_protocol_platforms"].items()}
DIGITAL_PLATFORM_ROUTES = dict(_PROTOCOL_AUTHORITY["routing"]["digital_platforms"])
DIGITAL_PLATFORM_LABELS = dict(_PROTOCOL_AUTHORITY["labels"]["digital_platforms"])
DIGITAL_PLATFORM_NAME_ALIASES = {key: frozenset(value) for key, value in _PROTOCOL_AUTHORITY["aliases"]["digital_platform_names"].items()}
PROTOCOL_PROVENANCE = {key: dict(value) for key, value in _PROTOCOL_AUTHORITY["provenance"].items()}
COLONY_PROTOCOLS = tuple(_GROUPS["colony_protocols"])
COLONY_HOST_CLASSES = set(_GROUPS["colony_host_classes"])
COLONY_PREPARATIONS = set(_GROUPS["colony_preparations"])

COLONY_PROTOCOL_RECORDS: dict[str, dict[str, Any]] = {
    "neb-onetaq-m0482-colony": {
        "protocol_id": "neb-onetaq-m0482-colony",
        "selection": "NEB OneTaq 2X Master Mix with Standard Buffer M0482 · colony-PCR branch",
        "source_publication": "NEB M0482 current protocol",
        "source_url": "https://www.neb.com/en-us/protocols/protocol-for-onetaq-2x-master-mix-with-standard-buffer-m0482",
        "host_classes": ["bacterial"],
        "preparations": ["direct-transfer"],
        "reaction_volume_uL": {"supported_25": 25, "supported_50": 50},
        "primer_final_concentration_uM": {"starting": 0.2},
        "initial_denaturation": {"temperature_c": 94, "minutes": 5},
        "cycles": 30,
        "sequence_decision_impact": "none",
    },
    "neb-onetaq-hotstart-m0488-colony": {
        "protocol_id": "neb-onetaq-hotstart-m0488-colony",
        "selection": "NEB OneTaq Hot Start Quick-Load 2X Master Mix M0488 · colony-PCR branch",
        "source_publication": "NEB M0488 current protocol",
        "source_url": "https://www.neb.com/en/protocols/onetaq-hot-start-2x-master-mix-with-standard-buffer-m0488",
        "host_classes": ["bacterial"],
        "preparations": ["direct-transfer"],
        "reaction_volume_uL": {"supported_25": 25, "supported_50": 50},
        "primer_final_concentration_uM": {"starting": 0.2},
        "initial_denaturation": {"temperature_c": 94, "minutes_min": 2, "minutes_max": 5},
        "cycles": 30,
        "sequence_decision_impact": "none",
    },
    "neb-insert-screening-e1202": {
        "protocol_id": "neb-insert-screening-e1202",
        "selection": "NEB Insert Screening E1202 · OneTaq/LongAmp colony-PCR screening",
        "source_publication": "NEB Insert Screening Protocol E1202",
        "source_url": "https://www.neb.com/en-us/protocols/insert-screening-protocols-e1202",
        "host_classes": ["bacterial"],
        "preparations": ["direct-transfer"],
        "reaction_volume_uL": 50,
        "primer_final_concentration_uM": {"starting": 0.3},
        "initial_denaturation": {"temperature_c": 94, "minutes": 2},
        "cycles": 30,
        "sequence_decision_impact": "none",
    },
    "pcrbio-hs-taq-pb10-22-colony": {
        "protocol_id": "pcrbio-hs-taq-pb10-22-colony",
        "selection": "PCR Biosystems PCRBIO HS Taq Mix PB10.22 · colony-PCR branch",
        "source_publication": "PCRBIO HS Taq Mix PB10.22 manual v2.0",
        "source_url": "https://pcrbio.com/app/uploads/PB10.22-HS-Taq-Mix.pdf",
        "host_classes": ["bacterial"],
        "preparations": ["direct-transfer", "liquid-culture"],
        "reaction_volume_uL": 50,
        "primer_final_concentration_uM": {"starting": 0.4, "reviewed_range_min": 0.2, "reviewed_range_max": 0.6},
        "initial_denaturation": {"temperature_c": 95, "minutes": 10},
        "liquid_culture_input_uL": 5,
        "cycles": 40,
        "sequence_decision_impact": "none",
    },
    "neb-onetaq-m0689-colony": {
        "protocol_id": "neb-onetaq-m0689-colony",
        "selection": "NEB M0689 Supplemental Colony-PCR Protocol · OneTaq Hot Start Quick-Load 2X",
        "source_publication": "NEB Supplemental Protocol 2: Using colony PCR to identify positive clones (M0689/Authenticase page)",
        "source_revision": "current reviewed web protocol",
        "source_reviewed_date": "2026-09-04",
        "source_url": "https://www.neb.com/en-us/protocols/supplemental-protocol-2-using-colony-pcr-to-identify-positive-clones-neb-m0689",
        "host_classes": ["bacterial"],
        "preparations": ["direct-transfer"],
        "reaction_volume_uL": 25,
        "master_mix": {"stock_x": 2, "final_x": 1},
        "primer_final_concentration_uM": {"starting": 0.2},
        "sample_input": {"colony": "one isolated colony transferred directly with a sterile tip"},
        "initial_denaturation": {"temperature_c": 95, "minutes": 5},
        "cycles": 33,
        "cycling_model": {
            "denaturation": {"temperature_c": 95, "seconds": 15},
            "annealing": {"temperature_c_min": 55, "temperature_c_max": 64, "seconds": 15},
            "extension": {"temperature_c": 72, "seconds_min": 30, "seconds_max": 60, "amplicon_bp_context_min": 500, "amplicon_bp_context_max": 1000},
            "final_extension": {"temperature_c": 72, "minutes": 5},
        },
        "screening_followup": ["agarose gel", "Exo-CIP cleanup", "replica-plate/miniprep/Sanger confirmation"],
        "sequence_decision_impact": "none",
    },
}


# Additional exact-product records promoted from the R11 watchlist after
# vendor-protocol review.  They remain bench/provenance records: sequence
# ranking changes only where a record exposes an explicit candidate envelope.
STANDARD_PCR_ADDITIONAL_PROTOCOL_RECORDS: dict[str, dict[str, Any]] = {
    "qiagen-alltaq-master-mix-203144": {
        "selection": "QIAGEN AllTaq Master Mix (203144 family)",
        "source_publication": "AllTaq Master Mix Handbook / Quick-Start Protocol",
        "source_revision": "current reviewed 2026-09-04",
        "source_url": "https://go.qiagen.com/AllTaq",
        "lifecycle": {"status": "current"},
        "reaction_volume_uL": {"standard": 20, "384_well": 10},
        "master_mix": {"stock_x": 4, "final_x": 1},
        "primer_final_concentration_uM": {"starting": 0.25},
        "template_input": {"total_DNA_pg_min": 0.1, "total_DNA_ug_max": 1.0, "undiluted_cDNA_max_fraction": 0.10},
        "manufacturer_reach_kb_max": 9,
        "polymerase_properties": {"hot_start": True, "proofreading": False},
        "difficult_template": {"GC_rich_support": True, "Q_Solution": "kit-specific optional branch; never auto-selected"},
        "sequence_decision_impact": "none",
        "note": "AllTaq is a 4X hot-start master mix. PCRStudio records the published 20/10-uL formats and 0.25-uM primer starting point without reconstructing proprietary buffer composition.",
    },
    "thermo-platinum-ii-taq-hot-start": {
        "selection": "Thermo Fisher Platinum II Taq Hot-Start DNA Polymerase",
        "source_publication": "Thermo Fisher Platinum II Taq technical application note / current product protocol",
        "source_revision": "current reviewed 2026-09-04",
        "source_url": "https://assets.thermofisher.com/TFS-Assets/BID/Application-Notes/amplify-dna-targets-dna-polymerase-app-note.pdf",
        "lifecycle": {"status": "current"},
        "reaction_volume_uL": 20,
        "buffer": {"stock_x": 5, "final_x": 1, "magnesium_chloride_mM": 1.5},
        "primer_final_concentration_uM": {"starting": 0.2},
        "dntp_each_mM": 0.2,
        "polymerase_units_per_uL_reaction": 0.04,
        "template_examples": {"human_gDNA_ng": 50, "ecoli_gDNA_ng": 5, "plasmid_pg": 500},
        "polymerase_properties": {"hot_start": True, "proofreading": False},
        "sequence_decision_impact": "none",
    },
    "toyobo-kod-one-kmm101": {
        "selection": "TOYOBO KOD One PCR Master Mix (KMM-101)",
        "source_publication": "KOD One PCR Master Mix KMM-101 manual KMM-101_201",
        "source_revision": "current hosted manual reviewed 2026-09-04",
        "source_url": "https://www.toyobo-global.com/sites/default/static_root/products/lifescience/support/manual/KMM-101_201.pdf",
        "lifecycle": {"status": "current"},
        "reaction_volume_uL": 50,
        "master_mix": {"volume_uL": 25, "final_x": 1},
        "primer_final_concentration_uM": {"starting": 0.3, "long_target_ge_10kb": 0.15, "low_yield_trial": 0.5},
        "template_input": {"genomic_DNA_ng_max": 200, "plasmid_DNA_ng_max": 50, "cDNA_RNA_equivalent_ng_max": 750, "crude_sample_uL_max": 5},
        "manufacturer_reach_kb_approx": 40,
        "polymerase_properties": {"hot_start": True, "proofreading": True, "product_end": "blunt"},
        "sequence_decision_impact": "none",
    },
    "neb-multiplex-pcr-m0284": {
        "selection": "NEB Multiplex PCR 5X Master Mix (M0284)",
        "source_publication": "NEB M0284 Multiplex PCR 5X Master Mix protocol/guidelines",
        "source_revision": "current reviewed web protocol 2026-09-04",
        "source_url": "https://www.neb.com/en-us/products/m0284-multiplex-pcr-5x-master-mix",
        "lifecycle": {"status": "current"},
        "reaction_volume_uL": {"supported_25": 25, "supported_50": 50},
        "master_mix": {"stock_x": 5, "final_x": 1, "reviewed_optimization_x_min": 0.8, "reviewed_optimization_x_max": 1.5},
        "primer_final_concentration_uM": {"starting": 0.15, "reviewed_range_min": 0.05, "reviewed_range_max": 0.4},
        "template_input_ng_max": 1000,
        "cycling_model": {"activation": {"temperature_c": 95, "minutes": 1}, "cycles_min": 30, "cycles_max": 40, "denaturation": {"temperature_c": 95, "seconds": 20}, "annealing": {"temperature_c_min": 55, "temperature_c_max": 68, "seconds": 60}, "extension": {"temperature_c": 68, "minutes_per_kb_min": 1, "minutes_per_kb_max": 2}, "final_extension": {"temperature_c": 68, "minutes": 5}},
        "multiplex_only_chemistry": True,
        "sequence_decision_impact": "none",
    },
}

QPCR_ADDITIONAL_PROTOCOL_RECORDS: dict[str, dict[str, Any]] = {
    "vazyme-q713-suprealq-ultra-hunter-sybr": {
        "kind": "qpcr-sybr", "selection": "Vazyme SupRealQ Ultra Hunter SYBR qPCR Master Mix (U+) · Q713",
        "source_publication": "Vazyme Global Q713 current product page / Flyer Q713 V25.1", "source_revision": "current product page reviewed 2026-09-05; Flyer Q713 V25.1 listed",
        "source_url": "https://www.vazymeglobal.com/product-center/dye-based-qpcr/suprealq-ultra-hunter-sybr-qpcr-master-mix-u",
        "lifecycle": {"status": "current-source-limited"},
        "reaction_volume_uL": {"catalogue_reference": 20},
        "readout": "SYBR Green I fluorescence",
        "carryover_prevention": {"dUTP": True, "heat_labile_UDG": True},
        "passive_reference_dye": {"included": True, "vendor_claim": "broad-instrument compatibility without user ROX concentration adjustment"},
        "unresolved_numeric_dependencies": [
            "Exact product-specific primer starting concentration and master-mix stock/final stoichiometry require a transferable current IFU before PCRStudio will resolve them."
        ],
        "sequence_decision_impact": "none",
    },
    "qiagen-quantinova-sybr-208052": {
        "kind": "qpcr-sybr", "selection": "QIAGEN QuantiNova SYBR Green PCR Kit (208052 family)",
        "source_publication": "QuantiNova SYBR Green PCR Handbook", "source_revision": "current handbook reviewed 2026-09-04",
        "source_url": "https://www.qiagen.com/en-US/resources/download/KitHandbook/quantinova-sybr-green-pcr-handbook",
        "lifecycle": {"status": "current"}, "reaction_volume_uL": {"standard": 20, "384_well": 10},
        "master_mix": {"stock_x": 2, "final_x": 1}, "primer_final_concentration_nM": {"starting": 700},
        "template_input_ng_max": 100,
        "rox": {"high_rox_working_dilution_x": 20, "low_rox_working_dilution_x": 200, "no_rox_supported": True},
        "yellow_template_dilution_buffer": {"optional": True}, "sequence_decision_impact": "none",
    },
    "bio-rad-ssoadvanced-sybr-172527x": {
        "kind": "qpcr-sybr", "selection": "Bio-Rad SsoAdvanced Universal SYBR Green Supermix (172527x)",
        "source_publication": "Bio-Rad SsoAdvanced Universal SYBR Green Supermix instruction manual", "source_revision": "current reviewed 2026-09-04",
        "source_url": "https://www.bio-rad.com/webroot/web/pdf/lsr/literature/10000076346.pdf",
        "lifecycle": {"status": "current"}, "reaction_volume_uL": {"supported_10": 10, "supported_20": 20},
        "master_mix": {"stock_x": 2, "final_x": 1}, "primer_final_concentration_nM": {"reviewed_min": 250, "reviewed_max": 500, "starting": 400},
        "template_input": {"cDNA_ng_max": 100, "cDNA_fg_min": 100, "gDNA_ng_max": 50, "gDNA_pg_min": 5},
        "universal_reference_dye": True, "sequence_decision_impact": "none",
    },
    "solis-hot-firepol-evagreen-rox": {
        "kind": "qpcr-sybr", "selection": "Solis BioDyne HOT FIREPol EvaGreen qPCR Mix Plus (ROX), 5X",
        "source_publication": "DS-08-24 HOT FIREPol EvaGreen qPCR Mix Plus (ROX)", "source_revision": "revised 2022-04-12 / reviewed 2026-09-04",
        "source_url": "https://solisbiodyne.com/pics/9799_DS-08-24_v3_HOT_FIREPol_EvaGreen_qPCR_Mix_Plus_ROX_revised_12.04.2022.pdf",
        "lifecycle": {"status": "current"}, "reaction_volume_uL": 20, "master_mix": {"stock_x": 5, "final_x": 1},
        "primer_final_concentration_nM": {"reviewed_min": 80, "reviewed_max": 250, "starting": 250},
        "template_input": {"cDNA_pg_per_uL_min": 0.1, "cDNA_ng_per_uL_max": 10, "gDNA_pg_per_uL_min": 10, "gDNA_ng_per_uL_max": 4},
        "instrument_profile": "rox", "sequence_decision_impact": "none",
    },
    "solis-hot-firepol-evagreen-norox": {
        "kind": "qpcr-sybr", "selection": "Solis BioDyne HOT FIREPol EvaGreen qPCR Mix Plus (no ROX), 5X",
        "source_publication": "Solis BioDyne HOT FIREPol EvaGreen qPCR Mix Plus product catalogue", "source_revision": "current reviewed 2026-09-04",
        "source_url": "https://solisbiodyne.com/EN/product/name=HOT-FIREPol-EvaGreen-qPCR-Mix-Plus&catno=08-25-0000S",
        "lifecycle": {"status": "current"}, "reaction_volume_uL": 20, "master_mix": {"stock_x": 5, "final_x": 1},
        "primer_final_concentration_nM": {"reviewed_min": 80, "reviewed_max": 250, "starting": 250},
        "instrument_profile": "no-rox", "sequence_decision_impact": "none",
    },
    "solis-hot-firepol-evagreen-capillary": {
        "kind": "qpcr-sybr", "selection": "Solis BioDyne HOT FIREPol EvaGreen qPCR Mix Plus Capillary, 5X",
        "source_publication": "Solis BioDyne HOT FIREPol EvaGreen qPCR Mix Plus product catalogue", "source_revision": "current reviewed 2026-09-04",
        "source_url": "https://solisbiodyne.com/pics/6570_SBDproductcatalogue.pdf",
        "lifecycle": {"status": "current"}, "master_mix": {"stock_x": 5, "final_x": 1},
        "instrument_profile": "capillary", "sequence_decision_impact": "none",
        "unresolved_numeric_dependencies": ["Confirm exact current capillary-format reaction volume and primer concentration from the product-specific IFU before bench execution."],
    },
}

RPA_ADDITIONAL_PROTOCOL_RECORDS: dict[str, dict[str, Any]] = {
    "gbiosciences-rpa-786-2155": {
        "kind": "rpa", "protocol_id": "gbiosciences-rpa-786-2155",
        "selection": "G-Biosciences Recombinase Polymerase Amplification (RPA) Kit 786-2155",
        "source_publication": "G-Biosciences RPA Kit protocol", "source_revision": "current reviewed 2026-09-04",
        "source_url": "https://www.gbiosciences.com/Recombinase-Polymerase-Amplification-RPA-Kit",
        "lifecycle": {"status": "current"}, "reaction_volume_uL": 20,
        "primer_stock_uM": 10, "primer_volume_uL_each": 1, "primer_final_concentration_nM": 500,
        "enzyme_mix": {"stock_x": 5, "volume_uL": 4, "final_x": 1},
        "reaction_buffer": {"stock_x": 2, "volume_uL": 10, "final_x": 1},
        "magnesium_acetate": {"stock_mM": 280, "volume_uL": 1, "final_mM": 14},
        "template_input_ng": {"min": 1, "max": 50}, "temperature_c": {"min": 37, "max": 40},
        "incubation_minutes": {"min": 20, "max": 60}, "sequence_decision_impact": "none",
        "oligo_contract": "plain-acgt-two-primer", "modified_probe_support": False,
    },
}


def standard_pcr_protocol(named: str | None, *, assay_id: str, multiplex_context: bool = False) -> dict[str, Any] | None:
    """Return a reviewed Standard-PCR bench/provenance overlay.

    Standard PCR intentionally keeps one stable Primer3 thermodynamic screening
    context.  A selected polymerase protocol may change bench cycling, fidelity,
    uracil compatibility, difficult-template handling and product-end chemistry,
    but it must not silently re-rank primer candidates through a guessed
    proprietary buffer composition.
    """
    selected = str(named or "not-selected")
    if selected not in STANDARD_PCR_PROTOCOLS:
        raise ValueError(
            "standard_pcr_protocol must be one of: "
            + ", ".join(STANDARD_PCR_PROTOCOLS)
            + "."
        )
    if selected == "not-selected":
        return None
    if assay_id != "standard-pcr":
        raise ValueError(
            "a named Standard-PCR chemistry overlay belongs to the `standard-pcr` assay, "
            f"not `{assay_id or 'an unbound request'}`."
        )
    if selected == "neb-multiplex-pcr-m0284" and not multiplex_context:
        raise ValueError(
            "NEB Multiplex PCR 5X Master Mix M0284 is a shared-tube multiplex chemistry; "
            "use the Standard-PCR multiplex workflow rather than a simplex design request."
        )

    common = {
        "kind": "standard-pcr",
        "protocol_id": selected,
        "sequence_decision_impact": "none",
        "constraints": {},
        "thermodynamic_model_impact": "none",
        "screening_context_note": (
            "PCRStudio retains the versioned `taq-standard` Primer3 calculation context for "
            "cross-protocol sequence comparability. The named protocol below is bench/provenance "
            "authority; proprietary buffer composition is not reconstructed and does not silently "
            "change primer ranking."
        ),
    }

    if selected in STANDARD_PCR_ADDITIONAL_PROTOCOL_RECORDS:
        record = dict(STANDARD_PCR_ADDITIONAL_PROTOCOL_RECORDS[selected])
        return {**common, "protocol_id": selected, **record}

    if selected == "neb-taq-m0273":
        return {
            **common,
            "selection": "NEB Taq DNA Polymerase with Standard Taq Buffer (M0273)",
            "source_publication": "NEB M0273 PCR protocol / optimization guidance",
            "source_revision": "current reviewed web protocol",
            "reaction_volume_uL": {"supported_25": 25, "supported_50": 50},
            "primer_final_concentration_uM": {"starting": 0.2, "reviewed_range_min": 0.05, "reviewed_range_max": 1.0},
            "magnesium_final_mM": 1.5,
            "dntp_each_mM": 0.2,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 95, "seconds": 30},
                "denaturation": {"temperature_c": 95, "seconds_min": 15, "seconds_max": 30},
                "annealing": {"temperature_c_min": 45, "temperature_c_max": 68, "seconds_min": 15, "seconds_max": 60, "authority": "primer/template dependent"},
                "extension": {"temperature_c": 68, "seconds_per_kb": 60},
                "final_extension": {"temperature_c": 68, "seconds": 300},
                "cycles": {
                    "routine_program_min": 25,
                    "routine_program_max": 30,
                    "general_guidance_max": 35,
                    "low_copy_may_require_up_to": 45,
                },
            },
            "polymerase_properties": {
                "proofreading": False,
                "hot_start": False,
                "product_end": "3-prime-dA-overhang-expected-for-Taq-family",
                "dUTP_compatible": True,
                "uracil_template_compatibility": "not-promoted-to-a-universal-template claim in this overlay",
            },
            "carryover_prevention": {
                "dUTP_supported": True,
                "UDG_built_in": False,
                "optional_UDG": "Antarctic Thermolabile UDG M0372 or another explicitly validated compatible workflow",
                "enabled_by_protocol_selection_alone": False,
                "note": "NEB identifies M0273 Taq as dUTP-compatible and pairs dUTP with thermolabile UDG for carry-over prevention. PCRStudio does not infer that dUTP or UDG was actually used from the polymerase selection alone.",
            },
            "downstream_cloning": {
                "product_end": "Taq-family 3-prime-dA overhang expected",
                "ta_cloning_direct": "chemistry-compatible in principle; purify/verify the actual product and vector system",
                "blunt_end_claim": False,
            },
            "difficult_template": {
                "automatic_additive_selection": False,
                "note": "Longer initial denaturation, Mg/annealing optimization and additive trials are bench decisions; sequence GC alone does not select one rescue condition.",
            },
            "note": "This is a conventional Taq starting-point overlay, not a universal endpoint-PCR programme. Product identity, yield and specificity remain measured outcomes.",
        }

    if selected == "neb-q5-hot-start-m0493":
        return {
            **common,
            "selection": "NEB Q5 Hot Start High-Fidelity DNA Polymerase (M0493)",
            "source_publication": "NEB M0493 protocol",
            "source_revision": "current reviewed web protocol",
            "reaction_volume_uL": {"supported_25": 25, "supported_50": 50},
            "primer_final_concentration_uM": {"starting": 0.5, "long_complex_target_min": 0.2, "long_complex_target_max": 0.3},
            "magnesium_final_mM": 2.0,
            "dntp_each_mM": 0.2,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 98, "seconds": 30},
                "denaturation": {"temperature_c": 98, "seconds_min": 5, "seconds_max": 10},
                "annealing": {"temperature_c_min": 50, "temperature_c_max": 72, "seconds_min": 10, "seconds_max": 30, "authority": "NEB Tm Calculator / gradient"},
                "extension": {"temperature_c": 72, "seconds_per_kb_min": 20, "seconds_per_kb_max": 30},
                "final_extension": {"temperature_c": 72, "seconds": 120},
                "cycles": {"min": 25, "max": 35},
            },
            "polymerase_properties": {
                "proofreading": True,
                "hot_start": True,
                "hot_start_mechanism": "aptamer-based",
                "product_end": "blunt",
                "dUTP_compatible": False,
                "uracil_template_compatible": False,
            },
            "carryover_prevention": {
                "dUTP_supported": False,
                "UDG_built_in": False,
                "enabled_by_protocol_selection_alone": False,
                "note": "Standard Q5 is not the uracil/dUTP branch. Do not attach a dUTP/UDG carry-over workflow to M0493; choose an explicitly uracil-tolerant polymerase such as Q5U when that chemistry is required.",
            },
            "difficult_template": {
                "q5_high_gc_enhancer": "optional with standalone Q5 reaction buffer; not a universal additive",
                "automatic_additive_selection": False,
            },
            "downstream_cloning": {
                "ta_cloning_direct": False,
                "note": "Q5 products are blunt. Purify before a separately validated A-addition step if TA cloning is required.",
            },
            "note": "Q5 annealing and difficult-template behavior are protocol-specific. PCRStudio records them as bench authority but does not replace the shared Primer3 screening model with guessed Q5 buffer thermodynamics.",
        }

    if selected == "neb-q5u-hot-start-m0515":
        return {
            **common,
            "selection": "NEB Q5U Hot Start High-Fidelity DNA Polymerase (M0515)",
            "source_publication": "NEB M0515 protocol",
            "source_revision": "current reviewed web protocol",
            "reaction_volume_uL": {"supported_25": 25, "supported_50": 50},
            "primer_final_concentration_uM": {"starting": 0.5},
            "magnesium_final_mM": 2.0,
            "dntp_each_mM": 0.2,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 98, "seconds": 30},
                "denaturation": {"temperature_c": 98, "seconds_min": 5, "seconds_max": 10},
                "annealing": {"temperature_c_min": 55, "temperature_c_max": 72, "seconds": 20, "authority": "NEB Tm Calculator"},
                "extension": {"temperature_c": 72, "seconds_per_kb_min": 20, "seconds_per_kb_max": 30},
                "final_extension": {"temperature_c": 72, "seconds": 300},
                "cycles": {"starting": 30, "typical_max": 35},
            },
            "polymerase_properties": {
                "proofreading": True,
                "hot_start": True,
                "hot_start_mechanism": "aptamer-based",
                "product_end": "blunt",
                "dUTP_compatible": True,
                "uracil_template_compatible": True,
            },
            "difficult_template": {
                "dmso_max_percent": 2.0,
                "automatic_additive_selection": False,
                "note": "NEB permits up to 2% DMSO for certain difficult or long targets; PCRStudio does not infer that additive from sequence GC alone.",
            },
            "carryover_prevention": {
                "dUTP_supported": True,
                "UDG_built_in": False,
                "optional_UDG": "Antarctic Thermolabile UDG M0372",
                "supplier_pretreatment": {"temperature_c": 25, "minutes": 10},
                "enabled_by_protocol_selection_alone": False,
                "note": "Carry-over prevention is executable only when dUTP and compatible thermolabile UDG are actually used and recorded; it is not inferred from selecting Q5U alone.",
            },
            "downstream_cloning": {
                "product_end": "blunt",
                "ta_cloning_direct": False,
                "note": "Q5U is a proofreading blunt-end polymerase. TA cloning requires a separately validated post-PCR A-addition workflow; USER cloning is a distinct chemistry and is not inferred from primer design alone.",
            },
            "note": "Q5U is the named high-fidelity branch for uracil-containing substrates/dUTP workflows. Its damaged/bisulfite branch has separate cycling and is not silently selected by ordinary Standard PCR.",
        }

    if selected == "promega-gotaq-m300":
        return {
            **common,
            "selection": "Promega GoTaq DNA Polymerase (M3001/M3005/M3008)",
            "source_publication": "Promega 9PIM300",
            "source_revision": "Revised 10/23 / current reviewed protocol",
            "reaction_volume_uL": {"recommended": 50},
            "primer_final_concentration_uM": {"min": 0.1, "max": 1.0},
            "magnesium_final_mM": 1.5,
            "dntp_each_mM": 0.2,
            "polymerase_units_per_50uL": 1.25,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 95, "seconds": 120},
                "denaturation": {"temperature_c": 95, "seconds_min": 30, "seconds_max": 60},
                "annealing": {"temperature_c_min": 42, "temperature_c_max": 65, "seconds_min": 30, "seconds_max": 60, "authority": "primer/template dependent"},
                "extension": {"temperature_c": 72, "seconds_per_kb_min": 60},
                "final_extension": {"temperature_c": 72, "seconds": 300},
                "cycles": {"min": 25, "max": 35},
            },
            "polymerase_properties": {
                "proofreading": False,
                "hot_start": False,
                "product_end": "3-prime-dA-overhang",
                "dUTP_compatible": "not-asserted-by-this-reviewed-overlay",
                "uracil_template_compatible": "not-asserted-by-this-reviewed-overlay",
            },
            "buffer_variants": {
                "green": "contains tracking dyes and supports direct gel loading",
                "colorless": "preferred when direct fluorescence/absorbance measurements are required before purification",
                "identity_must_be_recorded": True,
            },
            "carryover_prevention": {
                "dUTP_supported": "not-asserted-by-this-reviewed-overlay",
                "UDG_built_in": False,
                "enabled_by_protocol_selection_alone": False,
                "note": "The reviewed M300 protocol does not by itself establish a dUTP/UDG carry-over workflow. Record and validate any such workflow separately rather than inheriting it from generic Taq-family knowledge.",
            },
            "downstream_cloning": {
                "product_end": "3-prime-dA-overhang",
                "ta_cloning_direct": "chemistry-compatible in principle; verify actual A-tailing and vector workflow",
                "blunt_end_claim": False,
            },
            "note": "GoTaq M300 is a conventional non-hot-start Taq bench overlay. Green versus Colorless buffer is a recorded bench choice; the proprietary formulation is not reconstructed for Primer3 ranking.",
        }

    if selected == "thermo-dreamtaq-hot-start-ep170x":
        return {
            **common,
            "selection": "Thermo Scientific DreamTaq Hot Start DNA Polymerase (EP1701-EP1704)",
            "source_publication": "MAN0015972",
            "source_revision": "Rev A.00 / current hosted product-information record",
            "reaction_volume_uL": {"recommended": 50},
            "primer_final_concentration_uM": {"min": 0.1, "max": 1.0},
            "magnesium_final_mM": 2.0,
            "dntp_each_mM": 0.2,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 95, "minutes_min": 1, "minutes_max": 3},
                "denaturation": {"temperature_c": 95, "seconds": 30},
                "annealing": {"authority": "primer Tm", "seconds": 30},
                "extension": {"temperature_c": 72, "seconds_per_kb": 60},
                "final_extension": {"temperature_c": 72, "minutes_min": 5, "minutes_max": 15},
                "cycles": {"min": 25, "max": 40},
            },
            "polymerase_properties": {
                "proofreading": False,
                "hot_start": True,
                "hot_start_mechanism": "antibody",
                "product_end": "3-prime-dA-overhang",
                "dUTP_compatible": True,
                "uracil_template_compatible": True,
                "modified_nucleotide_compatible": True,
            },
            "carryover_prevention": {
                "dUTP_supported": True,
                "UDG_built_in": False,
                "enabled_by_protocol_selection_alone": False,
                "note": "DreamTaq Hot Start can incorporate dUTP, but carry-over prevention still requires an explicitly compatible UDG workflow and recorded pretreatment; the polymerase selection alone is not a carry-over-control claim.",
            },
            "downstream_cloning": {
                "product_end": "3-prime-dA-overhang",
                "ta_cloning_direct": "chemistry-compatible in principle; verify the actual product/vector workflow",
                "blunt_end_claim": False,
            },
            "note": "DreamTaq Hot Start is a Taq-family bench overlay with an antibody hot start and TA-cloning-compatible 3-prime dA products; the proprietary buffer is not reconstructed for Primer3 ranking.",
        }

    if selected in {
        "neb-onetaq-hot-start-m0484",
        "neb-onetaq-hot-start-gc-m0485",
        "neb-onetaq-hot-start-quickload-m0488",
        "neb-onetaq-hot-start-quickload-gc-m0489",
    }:
        gc_buffer = selected in {"neb-onetaq-hot-start-gc-m0485", "neb-onetaq-hot-start-quickload-gc-m0489"}
        quick_load = "quickload" in selected
        catalogue = {
            "neb-onetaq-hot-start-m0484": ("M0484", "OneTaq Hot Start 2X Master Mix with Standard Buffer"),
            "neb-onetaq-hot-start-gc-m0485": ("M0485", "OneTaq Hot Start 2X Master Mix with GC Buffer"),
            "neb-onetaq-hot-start-quickload-m0488": ("M0488", "OneTaq Hot Start Quick-Load 2X Master Mix with Standard Buffer"),
            "neb-onetaq-hot-start-quickload-gc-m0489": ("M0489", "OneTaq Hot Start Quick-Load 2X Master Mix with GC Buffer"),
        }
        cat, label = catalogue[selected]
        return {
            **common,
            "selection": f"NEB {label} ({cat})",
            "source_publication": f"NEB {cat} protocol / current product page",
            "source_revision": "current reviewed web protocol 2026-09-04",
            "lifecycle": {"status": "current", "package_identity_is_not_chemistry_identity": True},
            "reaction_volume_uL": {"supported_25": 25, "supported_50": 50},
            "master_mix": {"stock_x": 2, "final_x": 1},
            "primer_final_concentration_uM": {"starting": 0.2, "reviewed_range_min": 0.05, "reviewed_range_max": 1.0},
            "magnesium_final_mM": 2.0 if gc_buffer else 1.8,
            "dntp_each_mM": 0.2,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 94, "seconds": 30},
                "denaturation": {"temperature_c": 94, "seconds_min": 15, "seconds_max": 30},
                "annealing": {"temperature_c_min": 45, "temperature_c_max": 68, "seconds_min": 15, "seconds_max": 60, "authority": "primer/template dependent"},
                "extension": {"temperature_c": 68, "seconds_per_kb": 60},
                "final_extension": {"temperature_c": 68, "seconds": 300},
                "cycles": {"routine": 30, "general_min": 25, "general_max": 35, "low_copy_may_require_up_to": 45},
            },
            "polymerase_properties": {
                "polymerase_blend": "Taq + Deep Vent",
                "proofreading": True,
                "hot_start": True,
                "hot_start_mechanism": "aptamer-based inhibitor",
                "separate_activation_required": False,
                "product_end": "majority-3-prime-dA-overhang",
            },
            "difficult_template": {
                "gc_buffer": gc_buffer,
                "high_gc_enhancer_percent": {"min": 10, "max": 20} if gc_buffer else None,
                "automatic_additive_selection": False,
                "note": "GC enhancer is an explicit source-bounded bench choice; PCRStudio never selects it automatically from sequence GC alone.",
            },
            "quick_load_tracking_dyes": quick_load,
            "colony_pcr_supported": True,
            "downstream_cloning": {
                "product_end": "majority-3-prime-dA-overhang",
                "ta_cloning_direct": "chemistry-compatible in principle; verify actual product/vector workflow",
                "blunt_end_claim": False,
            },
            "note": "Exact OneTaq formulation identity is retained because Standard versus GC buffer and Quick-Load tracking dyes are real formulation differences; pack size alone is not promoted to a new chemistry identity.",
        }

    if selected == "pcrbio-hs-taq-mix-pb10-22":
        return {
            **common,
            "selection": "PCR Biosystems PCRBIO HS Taq Mix (PB10.22)",
            "source_publication": "PCRBIO HS Taq Mix Manual PB10.22",
            "source_revision": "current reviewed product manual 2026-09-04",
            "lifecycle": {"status": "current"},
            "reaction_volume_uL": {"recommended": 50},
            "master_mix": {"stock_x": 2, "final_x": 1},
            "primer_final_concentration_uM": {"starting": 0.4, "min": 0.2, "max": 0.6},
            "magnesium_final_mM": 3.0,
            "dntp_total_mM": 1.0,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 95, "minutes_min": 1, "minutes_max": 2},
                "denaturation": {"temperature_c": 95, "seconds": 15},
                "annealing": {"temperature_c_min": 55, "temperature_c_max": 65, "seconds": 15, "authority": "primer dependent"},
                "extension": {"temperature_c": 72, "seconds_per_kb": 20},
                "cycles": {"max": 40},
                "colony_initial_denaturation": {"temperature_c": 95, "minutes": 10},
            },
            "direct_sample": {
                "bacterial_colony": "reviewed PB10.22 branch",
                "overnight_culture_uL_per_50uL": 5,
                "blood_or_urine_uL_per_50uL": 2,
                "automatic_matrix_selection": False,
            },
            "difficult_template": {
                "extra_magnesium_or_enhancer_recommended": False,
                "note": "The supplier recommends using the optimized mix without automatically adding extra Mg/enhancers; assay-specific troubleshooting remains a bench decision.",
            },
            "polymerase_properties": {"proofreading": False, "hot_start": True, "product_end": "Taq-family-3-prime-dA-overhang-expected"},
            "note": "This branch also carries an exact colony-PCR preparation overlay when the colony module explicitly selects it; direct-sample facts never alter primer sequence ranking.",
        }

    if selected == "thermo-platinum-superfi-ii":
        return {
            **common,
            "selection": "Thermo Fisher Platinum SuperFi II PCR Master Mix",
            "source_publication": "MAN0018860",
            "source_revision": "current reviewed user guide",
            "source_reviewed_date": "2026-09-03",
            "reaction_volume_uL": {"supported_20": 20, "supported_50": 50},
            "primer_final_concentration_uM": {"starting": 0.5, "over_5kb_genomic_or_multiplex": 0.2},
            "magnesium_final_mM": 1.75,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 98, "seconds": 30},
                "denaturation": {"temperature_c": 98, "seconds_min": 5, "seconds_max": 10},
                "three_step_annealing": {"temperature_c": 60, "seconds": 10},
                "extension": {"temperature_c": 72, "seconds_per_kb_min": 15, "seconds_per_kb_max": 30},
                "final_extension": {"temperature_c": 72, "minutes": 5},
                "cycles": {"min": 25, "max": 35},
                "two_step_for_primers_over_nt": 30,
            },
            "polymerase_properties": {
                "proofreading": True,
                "hot_start": True,
                "product_end": "blunt",
                "dUTP_compatible": "not-promoted-by-this-overlay",
                "uracil_template_compatible": "not-promoted-by-this-overlay",
            },
            "difficult_template": {
                "routine_gc_claim_percent_max": 75,
                "dmso_starting_percent_above_gc_percent_75": 5,
                "automatic_additive_selection": False,
                "note": "Thermo states that routine reactions can cover templates up to about 75% GC without a melting agent; for >75% GC, 5% DMSO is a starting recommendation. PCRStudio never activates DMSO automatically from sequence GC alone.",
            },
            "downstream_cloning": {
                "product_end": "blunt",
                "ta_cloning_direct": False,
                "note": "SuperFi II is a proofreading high-fidelity branch; treat products as blunt unless a separately validated downstream A-addition workflow is performed.",
            },
            "sequence_decision_impact": "none",
            "thermodynamic_model_impact": "none",
            "note": (
                "The current Thermo Fisher guide specifies 0.5 uM each primer as the routine starting point and "
                "0.2 uM for multiplex reactions or >5 kb genomic targets, with 98 C denaturation and 15-30 s/kb "
                "extension. This is a bench/provenance overlay only; proprietary buffer composition is not "
                "reconstructed and the shared Primer3 screening context remains unchanged."
            ),
        }

    return {
        **common,
        "selection": "Thermo Scientific Phusion Plus DNA Polymerase",
        "source_publication": "MAN0025053",
        "source_revision": "Rev B / current reviewed user guide",
        "reaction_volume_uL": {"supported_20": 20, "supported_50": 50},
        "primer_final_concentration_uM": {"starting": 0.5, "over_5kb_or_multiplex": 0.2},
        "magnesium_final_mM": 1.7,
        "cycling_model": {
            "initial_denaturation": {"temperature_c": 98, "seconds": 30},
            "denaturation": {"temperature_c": 98, "seconds_min": 5, "seconds_max": 10},
            "three_step_annealing": {"temperature_c": 60, "seconds": 10},
            "extension": {"temperature_c": 72, "seconds_per_kb_min": 15, "seconds_per_kb_max": 30},
            "final_extension": {"temperature_c": 72, "seconds": 300},
            "cycles": {"min": 25, "max": 35},
            "two_step_for_primers_over_nt": 30,
        },
        "polymerase_properties": {
            "proofreading": True,
            "hot_start": True,
            "hot_start_mechanism": "antibody-molecule-mediated",
            "product_end": "blunt",
            "dUTP_compatible": False,
            "uracil_template_compatible": False,
        },
        "carryover_prevention": {
            "dUTP_supported": False,
            "UDG_built_in": False,
            "enabled_by_protocol_selection_alone": False,
            "note": "The current Phusion Plus guide says not to use dUTP and states that uracil/dUTP-containing templates or nucleotide mixes are incompatible. Do not attach a dUTP/UDG carry-over branch to this polymerase.",
        },
        "downstream_cloning": {
            "product_end": "blunt",
            "ta_cloning_direct": False,
            "note": "Phusion Plus products are blunt. A separately validated A-addition step is required before TA cloning, and residual proofreading polymerase must not be assumed compatible with that downstream workflow.",
        },
        "difficult_template": {
            "gc_enhancer_recommended_only_above_gc_percent": 65,
            "automatic_additive_selection": False,
        },
        "note": "Phusion Plus supplies a distinct high-fidelity bench programme and optional >65% GC enhancer. The additive is not auto-selected from sequence composition and the vendor buffer is not mapped onto the shared Primer3 calculation context.",
    }


def qpcr_protocol(
    named: str | None, *, assay_id: str, from_rna: bool = False
) -> dict[str, Any] | None:
    """Return a reviewed dye-qPCR bench overlay, or no overlay.

    These records are deliberately *bench/provenance* overlays.  Primer
    candidate generation continues to use the shared ``qpcr-dye`` screening
    context so choosing a commercial mix does not silently change sequence
    ranking.  Proprietary ionic composition is never reconstructed from a kit
    name.  The returned ``sequence_decision_impact`` field makes that boundary
    machine-visible.
    """
    selected = str(named or "not-selected")
    if selected not in QPCR_PROTOCOLS:
        raise ValueError("qpcr_protocol must be one of: " + ", ".join(QPCR_PROTOCOLS) + ".")
    if selected == "not-selected":
        return None
    if assay_id != "qpcr-sybr":
        raise ValueError(
            "a named dye-qPCR overlay belongs to the `qpcr-sybr` assay, "
            f"not `{assay_id or 'an unbound request'}`."
        )

    if selected in QPCR_ADDITIONAL_PROTOCOL_RECORDS:
        if from_rna:
            raise ValueError(f"{selected} is represented as a DNA/cDNA dye-qPCR chemistry, not a one-step RT-qPCR branch")
        return {"protocol_id": selected, "constraints": {}, "thermodynamic_model_impact": "none", **dict(QPCR_ADDITIONAL_PROTOCOL_RECORDS[selected])}

    if selected == "bio-rad-itaq-sybr":
        return {
            "kind": "qpcr-sybr",
            "protocol_id": selected,
            "selection": "Bio-Rad iTaq Universal SYBR Green Supermix",
            "source_publication": "10000068167",
            "source_revision": "Ver B",
            "source_revision_date": "2019-02",
            "source_revision_date_precision": "month",
            "master_mix": "iTaq Universal SYBR Green Supermix",
            "reaction_volume_uL": {"supported_10": 10, "supported_20": 20},
            "primer_final_concentration_nM": {"optimization_min": 300, "optimization_max": 500},
            "amplicon_bp_preferred": {"min": 70, "max": 150},
            "primer_tm_c": {"target": 60},
            "cycles": {"min": 35, "max": 40},
            "anneal_extend_c": 60,
            "cycling_model": {
                "polymerase_activation_and_dna_denaturation": {
                    "temperature_c": 95,
                    "cDNA_seconds": {"min": 20, "max": 30},
                    "genomic_DNA_minutes": {"min": 2, "max": 5},
                },
                "denaturation_and_anneal_extend": "instrument-mode dependent; use the Bio-Rad table for the exact real-time platform",
                "melt_curve": {"temperature_c_min": 65, "temperature_c_max": 95, "instrument_default_permitted": True},
            },
            "readout": "SYBR Green fluorescence with a dissociation/melt-curve review",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "The current Bio-Rad insert uses 10 or 20 uL reactions and 300-500 nM each primer. "
                "The 70-150 bp range is Bio-Rad's best-efficiency design preference, not a hard "
                "iTaq validity limit. Confirm instrument-specific cycling, optics, reaction volume, "
                "reference-dye handling and melt programme against the current lot guide. Efficiency "
                "and single-product specificity remain experimental outcomes. Selecting this overlay "
                "does not alter PCRStudio's qPCR primer ranking."
            ),
        }

    if selected == "neb-luna-one-step-rt-qpcr-e3005":
        if not from_rna:
            raise ValueError(
                "NEB Luna E3005 is represented here as the named one-step RT-qPCR branch and "
                "requires `from_rna=true`. For DNA/cDNA qPCR, select a qPCR-only chemistry such "
                "as `neb-luna-universal-m3003` rather than silently omitting the RT step."
            )
        return {
            "kind": "qpcr-sybr",
            "protocol_id": selected,
            "selection": "NEB Luna Universal One-Step RT-qPCR Kit (E3005)",
            "source_publication": "manualE3005 / E3005 protocol",
            "source_revision": "5.0",
            "source_revision_date": "2025-04",
            "source_revision_date_precision": "month",
            "master_mix": "Luna Universal One-Step Reaction Mix + Luna WarmStart RT Enzyme Mix",
            "reaction_volume_uL": {"recommended_96_well": 20, "recommended_384_well": 10},
            "primer_final_concentration_nM": {
                "starting": 400,
                "optimization_min": 100,
                "optimization_max": 900,
            },
            "amplicon_bp_preferred": {"min": 70, "max": 200},
            "primer_tm_c": {"target": 60},
            "cycles": {"min": 40, "max": 45},
            "anneal_extend_c": 60,
            "cycling_model": {
                "reverse_transcription": {"temperature_c": 55, "minutes": 10},
                "initial_denaturation": {"temperature_c": 95, "seconds": 60},
                "denaturation": {"temperature_c": 95, "seconds": 10},
                "extension_read": {
                    "temperature_c": 60,
                    "seconds_default": 30,
                    "applied_biosystems_seconds": 60,
                    "plate_read": True,
                },
                "melt_curve_c": {"min": 60, "max": 95},
            },
            "reverse_transcription": {
                "mode": "one-step-rt-qpcr",
                "authority_status": "named-neb-e3005-one-step-rt-qpcr",
                "temperature_c": 55,
                "incubation_minutes": 10,
                "minimum_recommended_temperature_c": 50,
                "difficult_target_temperature_c": 60,
                "reverse_transcriptase": "Luna WarmStart Reverse Transcriptase",
                "rnase_inhibitor": "Murine RNase Inhibitor",
                "note": (
                    "The named E3005 branch owns the one-step RT hold. NEB recommends 55 C for "
                    "10 minutes, permits 60 C for difficult targets, and advises against RT below "
                    "50 C for full WarmStart activation. The default 60 C extension/read is 30 seconds; "
                    "the current NEB protocol specifies 60 seconds on Applied Biosystems real-time instruments."
                ),
            },
            "carryover_prevention": {
                "dUTP_in_master_mix": True,
                "UDG_built_in": False,
                "optional_UDG": "Antarctic Thermolabile UDG M0372; supplier starting point 0.025 U/uL",
                "optional_udg_pretreatment": {"temperature_c": 25, "minutes": 2},
            },
            "transcript_design": {
                "splice_site_spanning_recommended_when_known": True,
                "purpose": "reduce genomic-DNA amplification risk",
                "hard_requirement_for_every_transcript": False,
            },
            "genomic_dna_control": {
                "no_rt_control_recommended": True,
                "no_template_control_recommended": True,
                "dnase_treatment_if_genomic_dna_is_detected": True,
                "exon_exon_junction_design_recommended_when_annotated_and_appropriate": True,
                "note": (
                    "A named one-step RT-qPCR chemistry does not prove RNA-specific signal. "
                    "NEB recommends a no-RT control, especially when primers do not span an "
                    "exon-exon junction; DNase treatment or junction-spanning redesign are "
                    "follow-up controls when genomic-DNA amplification is observed."
                ),
            },
            "readout": "dsDNA-dye fluorescence with plate read at extension and post-run melt curve",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "E3005 is the explicitly modeled dye-based one-step RT-qPCR branch. The supplier "
                "recommends 400 nM each primer, permits 100-900 nM optimization, and typically "
                "targets 70-200 bp amplicons. Its dUTP supports optional carry-over prevention only "
                "when a compatible thermolabile UDG is added; UDG is not inferred as built in. "
                "Selecting E3005 does not alter PCRStudio's primer-ranking thermodynamic model."
            ),
        }

    if selected == "neb-luna-universal-m3003":
        return {
            "kind": "qpcr-sybr",
            "protocol_id": selected,
            "selection": "NEB Luna Universal qPCR Master Mix (M3003)",
            "source_publication": "M3003 protocol / manualM3003",
            "source_revision": "Version 3.0",
            "source_revision_date": "2020-03",
            "source_revision_date_precision": "month",
            "master_mix": "Luna Universal qPCR Master Mix",
            "reaction_volume_uL": {"recommended_96_well": 20, "recommended_384_well": 10},
            "primer_final_concentration_nM": {"starting": 250, "optimization_min": 100, "optimization_max": 500},
            "amplicon_bp_preferred": {"min": 70, "max": 200},
            "primer_tm_c": {"target": 60},
            "cycles": {"min": 40, "max": 45},
            "anneal_extend_c": 60,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 95, "seconds": 60},
                "denaturation": {"temperature_c": 95, "seconds": 15},
                "extension_read": {"temperature_c": 60, "seconds": 30},
                "melt_curve_c": {"min": 60, "max": 95},
            },
            "carryover_prevention": {
                "dUTP_in_master_mix": True,
                "UDG_built_in": False,
                "optional_UDG": "Antarctic Thermolabile UDG M0372; supplier starting point 0.025 U/uL",
                "optional_udg_pretreatment": {"temperature_c": 25, "minutes": 10},
                "enabled_by_protocol_selection_alone": False,
                "note": (
                    "Luna M3003 contains a dUTP/dTTP blend, but carry-over destruction requires an "
                    "added compatible thermolabile UDG. NEB recommends room-temperature setup or a "
                    "25 C/10 min pretreatment when Antarctic Thermolabile UDG is used; PCRStudio does "
                    "not infer that the optional enzyme was actually added from the M3003 selection."
                ),
            },
            "readout": "dsDNA-dye fluorescence with plate read at extension and post-run melt curve",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "Official Luna guidance uses 250 nM each primer as a starting point and 100-500 nM as an "
                "optimization range. The master mix contains dUTP; carry-over destruction requires an "
                "added thermolabile UDG rather than being assumed built in. Proprietary buffer composition "
                "is not inferred, and selecting this bench overlay does not alter primer ranking."
            ),
        }

    if selected == "promega-gotaq-qpcr-a600x":
        return {
            "kind": "qpcr-sybr",
            "protocol_id": selected,
            "selection": "Promega GoTaq qPCR Master Mix (A6001/A6002)",
            "source_publication": "TM318",
            "source_revision": "Revised 10/24",
            "source_revision_date": "2024-10",
            "source_revision_date_precision": "month",
            "source_reviewed_date": "2026-09-03",
            "master_mix": "GoTaq qPCR Master Mix 2X with proprietary BRYT Green dsDNA-binding dye and low CXR",
            "reaction_volume_uL": 20,
            "primer_final_concentration_nM": {"min": 200, "max": 1000},
            "cycling_model": {
                "hot_start_activation": {"temperature_c": 95, "minutes": 2, "fixed_by_supplier": True},
                "standard": {
                    "cycles": 40,
                    "denaturation": {"temperature_c": 95, "seconds": 15},
                    "annealing_extension": {"temperature_c": 60, "seconds": 60},
                },
                "fast": {
                    "cycles": 40,
                    "denaturation": {"temperature_c": 95, "seconds": 3},
                    "annealing_extension": {"temperature_c": 60, "seconds": 30},
                },
                "dissociation_curve": {"temperature_c_min": 60, "temperature_c_max": 95, "recommended": True},
            },
            "reference_dye": {
                "low_CXR_in_master_mix": True,
                "supplemental_CXR_final_nM_when_instrument_requires": 300,
                "instrument_specific": True,
            },
            "readout": "proprietary BRYT Green dsDNA-binding dye; compatible with instruments detecting SYBR Green I/FAM spectral region",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "This is a dye-qPCR branch even though the intercalating dye is Promega BRYT Green rather than "
                "SYBR Green I. The current TM318 manual specifies a 20 uL worked protocol, 200 nM-1 uM each "
                "primer, a fixed 95 C/2 min activation, and standard or fast cycling. CXR handling is instrument-specific. "
                "Efficiency, single-product specificity and melt behavior remain measured assay evidence, not sequence-only claims."
            ),
        }

    if selected == "promega-gotaq-one-step-rt-qpcr-a6020":
        if not from_rna:
            raise ValueError(
                "Promega GoTaq 1-Step RT-qPCR A6020 is represented as an RNA one-step branch and "
                "requires `from_rna=true`. For DNA/cDNA qPCR, choose the qPCR-only GoTaq A6001/A6002 branch."
            )
        return {
            "kind": "qpcr-sybr",
            "protocol_id": selected,
            "selection": "Promega GoTaq 1-Step RT-qPCR System (A6020)",
            "source_publication": "TM355",
            "source_revision": "Revised 8/23",
            "source_revision_date": "2023-08",
            "source_revision_date_precision": "month",
            "source_reviewed_date": "2026-09-03",
            "lifecycle": {"status": "current"},
            "master_mix": "GoTaq qPCR Master Mix 2X + GoScript RT Mix for 1-Step RT-qPCR; BRYT Green readout",
            "reaction_volume_uL": 20,
            "primer_final_concentration_nM": {"starting": 200, "optimization_min": 50, "optimization_max": 300},
            "rna_template": {"supplier_starting_total_rna_ng": 100, "documented_range_fg_min": 500, "documented_max_ng": 100, "note": "Template amount depends on transcript abundance; the upper value is not a universal sensitivity limit."},
            "cycling_model": {
                "reverse_transcription": {"temperature_c_min": 37, "minutes": 15},
                "rt_inactivation_and_polymerase_activation": {"temperature_c": 95, "minutes": 10},
                "qpcr": {
                    "cycles": 40,
                    "denaturation": {"temperature_c": 95, "seconds": 10},
                    "annealing_and_data_collection": {"temperature_c": 60, "seconds": 30},
                    "extension": {"temperature_c": 72, "seconds": 30},
                },
            },
            "reverse_transcription": {
                "mode": "one-step-rt-qpcr",
                "authority_status": "named-promega-a6020-one-step-rt-qpcr",
                "temperature_c": 37,
                "temperature_c_rule": ">=37",
                "incubation_minutes": 15,
                "reverse_transcriptase": "GoScript RT Mix for 1-Step RT-qPCR",
                "note": "TM355 gives a one-step RT hold of at least 37 C for 15 min, followed by 95 C/10 min RT inactivation and GoTaq activation; PCRStudio records 37 C as the minimum named starting hold rather than claiming it is optimal for every transcript."
            },
            "reference_dye": {
                "CXR_present_in_master_mix": True,
                "optional_supplemental_CXR_final_nM": 500,
                "instrument_specific": True,
            },
            "readout": "BRYT Green dsDNA-binding dye using the instrument optical settings established for SYBR Green I-compatible detection",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "Current Promega one-step RNA branch. TM355 recommends 200 nM each primer as a starting point and "
                "50-300 nM optimization, documents up to 100 ng total RNA with abundance-dependent sensitivity, and "
                "provides the named RT/qPCR cycling programme. RNA-specific signal, efficiency, melt specificity and "
                "genomic-DNA exclusion remain experimental evidence; the vendor chemistry does not silently re-rank primers."
            ),
        }

    # PowerUp has distinct fast/standard branches and a separate standard
    if selected == "thermo-powertrack-sybr-a46xxx":
        if from_rna:
            raise ValueError("PowerTrack SYBR Green is a DNA/cDNA qPCR mix in this overlay; one-step RNA requires an explicit RT-qPCR chemistry.")
        return {
            "kind": "qpcr-sybr",
            "protocol_id": selected,
            "selection": "Applied Biosystems PowerTrack SYBR Green Master Mix (A46012/A46109-A46113)",
            "source_publication": "MAN0018825",
            "source_revision": "Rev B.0 / current reviewed user guide",
            "source_revision_date": "2022-07-29",
            "source_revision_date_precision": "day",
            "lifecycle": {"status": "current", "package_sizes_are_aliases": True},
            "reaction_volume_uL": {"supported_10": 10, "supported_20": 20, "below_10_recommended": False},
            "master_mix": "PowerTrack SYBR Green Master Mix 2X; SYBR Green I + hot-start polymerase + heat-labile UDG + ROX + dUTP/dTTP blend",
            "primer_final_concentration_nM": {"starting": 400, "optimization_min": 300, "optimization_max": 800},
            "template_input": {"cDNA_ng": {"min": 1, "max": 10}, "genomic_DNA_ng": {"min": 10, "max": 100}, "recommended_reaction_fraction_percent": {"min": 10, "max": 20}},
            "tracking_system": {"yellow_sample_buffer_stock_x": 40, "final_x": 1, "optional": True},
            "carryover_prevention": {"heat_labile_UDG_built_in": True, "separate_UDG_incubation_required": False},
            "reference_dye": {"ROX_in_mix": True, "cross_vendor_instrument_use": "supplier states broad real-time-instrument compatibility; exact instrument configuration must still be recorded"},
            "cycling_model": {
                "fast": {"activation": {"temperature_c": 95, "minutes": 2}, "cycles": 40, "denaturation": {"temperature_c": 95, "seconds": 5}, "anneal_extend": {"temperature_c": 60, "seconds": 30}},
                "standard": {"activation": {"temperature_c": 95, "minutes": 2}, "cycles": 40, "denaturation": {"temperature_c": 95, "seconds": 15}, "anneal_extend": {"temperature_c": 60, "seconds": 60}},
                "dissociation_curve": {"required_immediately_after_qpcr": True},
            },
            "readout": "SYBR Green I intercalating dye; amplicon-specific melt evidence required for specificity interpretation",
            "constraints": {"length_min": 18, "length_max": 30, "tm_min": 58.0, "tm_max": 62.0, "tm_pair_max_difference": 2.0, "gc_min": 30.0, "gc_max": 70.0, "max_poly_x": 3},
            "sequence_decision_impact": "none",
            "note": "PowerTrack numeric setup is source-conditioned. Yellow tracking buffer is optional and the exact instrument/run file remains experimental provenance; neither is a Primer3 ranking parameter.",
        }

    # three-step branch for primers below 60 C.  The qPCR search window extends
    # down to 59 C, so PCRStudio records all supplier branches and deliberately
    # does not auto-select one from its own screening Tm.
    return {
        "kind": "qpcr-sybr",
        "protocol_id": selected,
        "selection": "Applied Biosystems PowerUp SYBR Green Master Mix",
        "source_publication": "MAN0013511",
        "source_revision": "G",
        "source_revision_date": "2026-03-09",
        "source_revision_date_precision": "day",
        "master_mix": "PowerUp SYBR Green Master Mix",
        "reaction_volume_uL": {"supported_10": 10, "supported_20": 20},
        "primer_final_concentration_nM": {"optimization_min": 300, "optimization_max": 800},
        "amplicon_bp_preferred": {"min": 50, "max": 150},
        "primer_tm_c": {"target": 60},
        "cycles": {"min": 40, "max": 40},
        "anneal_extend_c": 60,
        "cycling_model": {
            "branch_selection": {
                "selected_branch": "unresolved-until-primer-Tm-method-and-instrument-branch-are-confirmed",
                "screening_tm_is_not_bench_ta_authority": True,
            },
            "udg_activation": {"temperature_c": 50, "minutes": 2},
            "polymerase_activation": {"temperature_c": 95, "minutes": 2},
            "fast_tm_ge_60": {"cycles": 40, "denaturation_c": 95, "denaturation_seconds": [1, 3], "anneal_extend_c": 60, "anneal_extend_seconds": 30},
            "standard_tm_ge_60": {"cycles": 40, "denaturation_c": 95, "denaturation_seconds": 15, "anneal_extend_c": 60, "anneal_extend_seconds": 60},
            "standard_tm_lt_60": {"cycles": 40, "denaturation_c": 95, "denaturation_seconds": 15, "anneal_c": {"min": 55, "max": 60}, "anneal_seconds": 15, "extension_c": 72, "extension_seconds": 60},
        },
        "carryover_prevention": {
            "dUTP_in_master_mix": True,
            "UDG_built_in": True,
            "UDG_type": "heat-labile",
        },
        "readout": "SYBR Green fluorescence with instrument-specific passive-reference handling and dissociation curve",
        "sequence_decision_impact": "none",
        "constraints": {},
        "note": (
            "PowerUp contains heat-labile UDG and a dUTP/dTTP blend. The supplier documents separate "
            "cycling branches by primer Tm and instrument mode, so PCRStudio preserves those branches instead "
            "of converting its screening Tm into a bench-program decision. ROX handling is instrument-specific. "
            "Selecting this overlay does not alter primer ranking."
        ),
    }

def long_range_protocol(named: str | None, *, assay_id: str) -> dict[str, Any] | None:
    """Return one explicitly reviewed long-range PCR bench branch.

    Long-range cycling and formulation are chemistry-specific, so Gen-1 never
    emits a generic bench programme or silently maps one vendor recipe onto
    another.  The fixed ``long-range`` Primer3 reaction remains a cross-protocol
    thermodynamic *screening adapter* for sequence comparability. A named
    protocol may narrow the primer constraint envelope when its manufacturer
    publishes sequence-design rules; that explicit constraint effect is kept
    separate from the thermodynamic reaction model, which remains unchanged.
    Proprietary buffer composition is not reconstructed.
    """
    selected = str(named or "not-selected")
    if selected not in LONG_RANGE_PROTOCOLS:
        raise ValueError(
            "long_range_protocol must be one of: " + ", ".join(LONG_RANGE_PROTOCOLS) + "."
        )
    if selected == "not-selected":
        if assay_id == "long-range-pcr":
            raise ValueError(
                "Long-range PCR requires an explicit reviewed long-range chemistry/protocol. "
                "PCRStudio will not emit a generic long-PCR cycle programme or silently substitute "
                "one manufacturer chemistry for another."
            )
        return None
    if assay_id != "long-range-pcr":
        raise ValueError(
            "a named long-range PCR overlay belongs to the `long-range-pcr` assay, "
            f"not `{assay_id or 'an unbound request'}`."
        )
    if selected == "toyobo-kod-long-kml101":
        return {
            "kind": "long-range-pcr",
            "protocol_id": selected,
            "selection": "TOYOBO KOD Long PCR Master Mix (KML-101)",
            "source_publication": "TOYOBO KOD Long PCR Master Mix KML-101 manual / current product page",
            "source_revision": "current reviewed 2026-09-04",
            "lifecycle": {"status": "current"},
            "kit_ids": ["KML-101"],
            "reaction_volume_uL": 50,
            "master_mix": {"stock_x": 2, "final_x": 1},
            "primer_final_concentration_uM": 0.15,
            "template_input": {
                "eukaryotic_genomic_DNA_ng": {"min": 1, "max": 200},
                "prokaryotic_genomic_DNA_ng": {"min": 0.1, "max": 200},
                "plasmid_DNA_ng": {"min": 0.001, "max": 50},
                "cDNA_RNA_equivalent_ng_max": 750,
                "crude_sample_uL_per_50uL_max": 5,
            },
            "primer_design_guidance": {"length_nt_min": 25, "length_nt_max": 35, "tm_c_min": 65, "gc_percent_min": 45, "gc_percent_max": 60},
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 94, "minutes": 1},
                "denaturation": {"temperature_c": 98, "seconds": 10},
                "annealing": {"temperature_c_rule": "primer Tm - 5 C", "seconds": 5},
                "extension": {"temperature_c": 68, "under_10kb_seconds_per_kb": 5, "at_or_above_10kb_seconds_per_kb": 10},
                "cycles": {"min": 25, "max": 45},
            },
            "manufacturer_reach": {"human_genomic_DNA_kb_approx_max": 50},
            "polymerase_properties": {"proofreading": True, "hot_start": True, "hot_start_mechanism": "two anti-KOD antibodies", "product_end": "blunt"},
            "screening_thermodynamics": {"sequence_decision_impact": "none", "note": "Vendor primer-design guidance is reported but does not silently replace PCRStudio's versioned Primer3 screening model."},
            "sequence_decision_impact": "none",
            "thermodynamic_model_impact": "none",
            "note": "Length-dependent extension is resolved only when target length is explicit; PCRStudio does not infer a long-range cycling branch from a vague product label.",
        }

    if selected == "neb-longamp-taq-m0323":
        return {
            "kind": "long-range-pcr",
            "protocol_id": selected,
            "selection": "NEB LongAmp Taq DNA Polymerase (M0323)",
            "kit_ids": ["M0323"],
            "manual": "PCR Protocol for LongAmp Taq DNA Polymerase (M0323)",
            "source_publication": "M0323 official protocol",
            "source_revision": "current web protocol",
            "source_revision_date": None,
            "source_revision_date_precision": "not-stated",
            "lifecycle": {"status": "current"},
            "reaction_volume_uL": {"standard_25_uL": 25, "standard_50_uL": 50},
            "primer_final_concentration_uM": {"starting": 0.4, "min": 0.05, "max": 1.0},
            "magnesium_chloride_mM": 2.0,
            "dntp_each_mM": 0.3,
            "enzyme_units": {"per_50_uL": 5.0},
            "cycling_summary": (
                "Routine 30-cycle branch: 94 C 30 s initial; 94 C 15-30 s, 45-65 C 15-60 s, "
                "65 C 50 s/kb; final 65 C 10 min. A supplier two-step branch is available when "
                "primer annealing temperature is above 60 C."
            ),
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 94, "seconds": 30},
                "routine_three_step": {
                    "cycles": 30,
                    "denaturation": {"temperature_c": 94, "seconds": {"min": 15, "max": 30}},
                    "annealing": {"temperature_c": {"min": 45, "max": 65}, "seconds": {"min": 15, "max": 60}},
                    "extension": {"temperature_c": 65, "seconds_per_kb": 50},
                },
                "two_step_eligibility": "supplier states a two-step branch is possible above 60 C annealing temperature",
                "final_extension": {"temperature_c": 65, "minutes": 10},
            },
            "screening_thermodynamics": "shared long-range calculation adapter; proprietary LongAmp buffer ionic composition beyond the published 2 mM Mg++ is not reconstructed",
            "thermodynamic_model_impact": "none",
            "sequence_decision_impact": "constraint-envelope",
            "constraints": {
                "length_min": 20,
                "length_max": 36,
                "gc_min": 40.0,
                "gc_max": 60.0,
            },
            "note": (
                "Current manufacturer branch. NEB recommends 20-40 nt primers and 40-60% GC. Primer3 in "
                "this Gen-1 stack has an executable 36-nt primer-size ceiling, so the reviewed runtime branch "
                "uses the explicit 20-36 nt subset rather than pretending 37-40 nt are unsupported by LongAmp. "
                "For products above 20 kb NEB gives additional desirable primer properties, but PCRStudio "
                "Gen-1 remains bounded to 5-20 kb. Protocol selection can constrain primer geometry/GC; it "
                "does not change the shared thermodynamic reaction model or turn screening Tm into a bench "
                "annealing temperature."
            ),
        }

    if selected == "qiagen-ultrarun-longrange-206442-206444":
        return {
            "kind": "long-range-pcr",
            "protocol_id": selected,
            "selection": "QIAGEN UltraRun LongRange PCR Kit",
            "kit_ids": ["206442", "206444"],
            "manual": "UltraRun LongRange PCR Kit Handbook 02/2024",
            "source_publication": "HB-2686 / UltraRun LongRange PCR Kit Handbook",
            "source_revision": "02/2024",
            "source_revision_date": "2024-02",
            "source_revision_date_precision": "month",
            "lifecycle": {
                "status": "current",
                "successor_to": "QIAGEN LongRange PCR Kit 206401/206402/206403",
                "current_product_listing_reviewed": "2026-09-03",
            },
            "reaction_volume_uL": {"standard": 20, "384_well_recommended": 10},
            "primer_final_concentration_uM": 0.5,
            "template_input": {
                "total_dna_per_reaction": {"min_pg": 10, "max_ug": 1},
                "cdna_undiluted_max_fraction_of_reaction": 0.10,
            },
            "master_mix": {"stock": "4x", "final": "1x"},
            "optional_q_solution": {
                "stock": "5x",
                "final": "1x",
                "use": "parallel trial for GC-rich or structurally difficult templates",
                "automatic_activation": False,
            },
            "cycling_summary": (
                "Current UltraRun 02/2024 branches: standard 2-step uses 93 C 3 min activation; "
                "<=35 cycles of 93 C 30 s and 65 C 30 s/kb for primers in the supplier's stated "
                "58-65 C Tm context; final 72 C 10 min. The alternative 3-step branch uses "
                "93 C 30 s, 55 C 15 s (approximately 5 C below primer Tm), and 68 C 30 s/kb."
            ),
            "cycling_model": {
                "initial_activation": {"temperature_c": 93, "minutes": 3},
                "standard_two_step": {
                    "cycles_max": 35,
                    "denaturation": {"temperature_c": 93, "seconds": 30, "do_not_exceed_temperature": True},
                    "anneal_extend": {
                        "temperature_c": 65,
                        "seconds_per_kb": 30,
                        "supplier_primer_tm_context_c": {"min": 58, "max": 65},
                    },
                },
                "alternative_three_step": {
                    "cycles_max": 35,
                    "denaturation": {"temperature_c": 93, "seconds": 30, "do_not_exceed_temperature": True},
                    "annealing": {"temperature_c": 55, "seconds": 15, "supplier_rule": "approximately 5 C below primer Tm"},
                    "extension": {"temperature_c": 68, "seconds_per_kb": 30, "genomic_dna_context": True},
                },
                "final_extension": {"temperature_c": 72, "minutes": 10},
            },
            "screening_thermodynamics": (
                "shared long-range calculation adapter; proprietary UltraRun master-mix ionic composition "
                "and Q-Solution thermodynamics are not reconstructed"
            ),
            "thermodynamic_model_impact": "none",
            "sequence_decision_impact": "constraint-envelope",
            "constraints": {
                "length_min": 20,
                "length_max": 30,
                "gc_min": 40.0,
                "gc_max": 60.0,
            },
            "note": (
                "Current manufacturer branch. The UltraRun handbook gives general primer-design guidance "
                "of 18-30 nt and 40-60% GC; Generation 1 retains the conservative 20-30 nt overlap with "
                "its cross-protocol long-range search envelope rather than claiming 18-19 nt are invalid. "
                "The current product page advertises up to 30 kb while other current QIAGEN portfolio material "
                "has also stated up to 40 kb; PCRStudio does not resolve that marketing-source conflict into a "
                "new ceiling because the Generation-1 executable product window remains 5-20 kb. Q-Solution "
                "is optional and is not activated from GC percentage alone. Protocol selection constrains the "
                "candidate envelope but does not replace the shared Primer3 thermodynamic model or turn its Tm "
                "into the supplier's bench annealing authority."
            ),
        }

    if selected == "neb-q5-xt-m2499":
        return {
            "kind": "long-range-pcr",
            "protocol_id": selected,
            "selection": "NEB Q5-XT Hot Start High-Fidelity 2X Master Mix (M2499)",
            "kit_ids": ["M2499"],
            "manual": "PCR using Q5-XT Hot Start High-Fidelity 2X Master Mix",
            "source_publication": "NEB M2499 official protocol",
            "source_revision": "current reviewed web protocol",
            "source_reviewed_date": "2026-09-03",
            "lifecycle": {"status": "current"},
            "reaction_volume_uL": {"supported_25": 25, "supported_50": 50},
            "primer_final_concentration_uM": {
                "targets_under_1kb": 0.5,
                "targets_over_1kb": 0.3,
                "reviewed_general_range_min": 0.15,
                "reviewed_general_range_max": 1.0,
                "very_long_targets_may_benefit_min": 0.15,
                "very_long_targets_may_benefit_max": 0.25,
            },
            "magnesium_final_mM": 1.6,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 98, "seconds": 30},
                "cycles": {"min": 25, "max": 35},
                "denaturation": {"temperature_c": 98, "seconds": 10},
                "annealing": {"temperature_c_min": 50, "temperature_c_max": 72, "seconds": 20, "authority": "NEB Tm Calculator or gradient"},
                "extension": {"temperature_c": 72, "seconds_per_kb_min": 5, "seconds_per_kb_max": 15},
                "final_extension_required": False,
            },
            "difficult_template": {
                "q5_high_gc_enhancer": {"stock_x": 5, "final_x": 1, "recommended_above_gc_percent": 65},
                "automatic_additive_selection": False,
            },
            "polymerase_properties": {"proofreading": True, "hot_start": True, "product_end": "blunt"},
            "screening_thermodynamics": "shared long-range calculation adapter; proprietary Q5-XT formulation is not reconstructed",
            "thermodynamic_model_impact": "none",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "Q5-XT is a current fast high-fidelity bench branch. The supplier uses different primer starting "
                "concentrations below and above 1 kb and recommends optional 1X Q5 High GC Enhancer above 65% GC. "
                "PCRStudio records those as protocol guidance and does not convert them into universal primer-validity "
                "rules or silently alter the shared long-range thermodynamic screening model. Gen-1 still enforces its "
                "own 5-20 kb product support boundary even when a chemistry has broader manufacturer capability."
            ),
        }

    if selected == "promega-gotaq-long-m4021":
        return {
            "kind": "long-range-pcr",
            "protocol_id": selected,
            "selection": "Promega GoTaq Long PCR Master Mix (M4021)",
            "kit_ids": ["M4021"],
            "manual": "TM359 GoTaq Long PCR Master Mix Technical Manual",
            "source_publication": "TM359",
            "source_revision": "Revised 5/17; current product listing reviewed 2026-09-03",
            "source_reviewed_date": "2026-09-03",
            "lifecycle": {"status": "current"},
            "master_mix": "2X hot-start recombinant Taq + proofreading DNA polymerase blend",
            "reaction_volume_uL": 50,
            "master_mix_numeric": {"stock_x": 2, "volume_uL": 25, "final_x": 1},
            "primer_final_concentration_uM": {"reviewed_min": 0.1, "reviewed_max": 1.0, "control_example": 0.2},
            "template_input": {"human_genomic_DNA_ug_min": 0.1, "human_genomic_DNA_ug_max": 0.5, "less_complex_template_ng_min": 0.25, "less_complex_template_ng_max": 2.5},
            "magnesium_final_mM": {"baseline": 2.5, "reviewed_titration_max": 4.0, "titration_increment": 0.5},
            "manufacturer_reach": {"genomic_dna_kb_max": 30, "lower_complexity_target_kb_max": 40},
            "polymerase_properties": {
                "hot_start": True,
                "proofreading_blend": True,
                "note": "The formulation combines antibody-inhibited recombinant Taq with a smaller proofreading polymerase component.",
            },
            "cycling_model": {
                "initial_denaturation": {"temperature_c_min": 94, "temperature_c_max": 95, "minutes": 2},
                "two_step": {"primer_tm_above_c": 60, "denaturation_temperature_c_min": 92, "denaturation_temperature_c_max": 94, "denaturation_seconds_min": 10, "denaturation_seconds_max": 30, "anneal_extension_temperature_c": 65, "extension_minutes_per_kb": 1},
                "three_step": {"primer_tm_below_c": 60, "annealing_rule": "start 5 C below primer Tm", "annealing_seconds_min": 15, "annealing_seconds_max": 30, "extension_temperature_c_min": 65, "extension_temperature_c_max": 72, "extension_minutes_per_kb": 1},
                "cycles_min": 25, "cycles_max": 35, "final_extension": {"temperature_c": 72, "minutes": 10},
                "very_long_target_ramp": {"above_kb": 15, "add_seconds_per_cycle_min": 10, "add_seconds_per_cycle_max": 20, "after_cycle_min": 10, "after_cycle_max": 15},
            },
            "template_integrity": {"HMW_required_for_very_long_targets": True, "very_long_threshold_kb": 15},
            "product_end": "majority 3-prime overhang with some blunt fragments",
            "screening_thermodynamics": "shared long-range calculation adapter; proprietary GoTaq Long formulation is not reconstructed",
            "thermodynamic_model_impact": "none",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "Promega documents GoTaq Long as a distinct ready-to-use long-PCR chemistry capable of up to 30 kb "
                "genomic and 40 kb lower-complexity targets. It is not interchangeable with ordinary GoTaq M300. "
                "The public current manual establishes the formulation and reach, but PCRStudio does not invent "
                "unpublished sequence-ranking constraints from the kit name; Gen-1 remains limited to its 5-20 kb "
                "software support envelope and preserves exact bench-program authority in the named manual."
            ),
        }

    if selected == "thermo-platinum-superfi-ii-longrange":
        return {
            "kind": "long-range-pcr",
            "protocol_id": selected,
            "selection": "Thermo Fisher Platinum SuperFi II DNA Polymerase — long-range branch",
            "kit_ids": ["12361010", "12361050", "12361250"],
            "manual": "MAN0018859 Platinum SuperFi II DNA Polymerase User Guide",
            "source_publication": "MAN0018859",
            "source_revision": "current hosted user guide; current product portfolio reviewed 2026-09-03",
            "source_reviewed_date": "2026-09-03",
            "lifecycle": {"status": "current"},
            "manufacturer_reach": {"routine_kb_max": 20, "optimization_context_kb_max": 40},
            "reaction_volume_uL": 50,
            "primer_final_concentration_uM": {"starting": 0.5, "long_target_or_multiplex_starting": 0.2},
            "magnesium_final_mM": 1.75,
            "cycling_model": {
                "initial_denaturation": {"temperature_c": 98, "seconds": 30},
                "cycles": {"min": 25, "max": 35},
                "denaturation": {"temperature_c": 98, "seconds_min": 5, "seconds_max": 10},
                "annealing": {"temperature_c_starting": 60, "seconds": 10, "authority": "vendor isostabilized-buffer starting point; optimize by gradient when needed"},
                "extension": {
                    "temperature_c": 72,
                    "low_complexity_seconds_per_kb": 15,
                    "high_complexity_genomic_seconds_per_kb": 30,
                },
                "final_extension": {"temperature_c": 72, "minutes": 5},
            },
            "difficult_template": {
                "routine_gc_percent_max_without_melting_agent": 75,
                "dmso_starting_percent_above_gc_percent_75": 5,
                "automatic_additive_selection": False,
            },
            "screening_thermodynamics": "shared long-range calculation adapter; proprietary SuperFi II buffer/isostabilizers are not reconstructed",
            "thermodynamic_model_impact": "none",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "Thermo Fisher currently positions Platinum SuperFi II for long products up to 20 kb, with >20 kb to "
                "approximately 40 kb requiring further optimization. PCRStudio Gen-1 deliberately retains its 5-20 kb "
                "software envelope. The long-range branch records the supplier's 60 C starting annealing context, 15-30 s/kb "
                "extension and lower 0.2 uM primer starting point for long genomic/multiplex work without reconstructing the "
                "proprietary buffer or turning vendor cycling into a sequence-ranking model."
            ),
        }

    if selected == "takara-primestar-gxl-r050a-standard":
        return {
            "kind": "long-range-pcr",
            "protocol_id": selected,
            "selection": "Takara PrimeSTAR GXL DNA Polymerase R050A — Standard Protocol",
            "kit_ids": ["R050A"],
            "manual": "PrimeSTAR GXL DNA Polymerase Product Manual v201906Da",
            "source_publication": "R050A_e.v1906Da",
            "source_revision": "v201906Da",
            "source_revision_date": "2019-06",
            "source_revision_date_precision": "month",
            "lifecycle": {"status": "current", "current_product_listing_reviewed": "2026-09-03"},
            "reaction_volume_uL": 50,
            "primer_final_concentration_uM": {"starting_min": 0.2, "starting_max": 0.3, "at_or_above_10kb": 0.2},
            "magnesium_chloride_mM": 1.0,
            "dntp_each_mM": 0.2,
            "enzyme_units": {"per_50_uL": 1.25},
            "cycling_summary": (
                "Standard protocol only: for 10-30 kb, 30 cycles of 98 C 10 s and 68 C 10 min. "
                "For <=10 kb the manual provides 2-step or 3-step 1 min/kb branches. The separate "
                "Rapid PCR protocol is not silently activated."
            ),
            "cycling_model": {
                "selected_vendor_branch": "standard-not-rapid",
                "up_to_10kb": {
                    "cycles": 30,
                    "denaturation": {"temperature_c": 98, "seconds": 10},
                    "three_step_annealing": {"temperature_c": [55, 60], "seconds": 15, "vendor_tm_formula_required": True},
                    "extension": {"temperature_c": 68, "seconds_per_kb": 60},
                    "two_step_available": True,
                },
                "10_to_30kb": {
                    "cycles": 30,
                    "denaturation": {"temperature_c": 98, "seconds": 10},
                    "anneal_extend": {"temperature_c": 68, "minutes": 10},
                },
            },
            "screening_thermodynamics": "shared long-range calculation adapter; the vendor-specific primer Tm formula is retained as bench-branch authority and is not replaced by Primer3 screening Tm",
            "thermodynamic_model_impact": "none",
            "sequence_decision_impact": "constraint-envelope",
            "constraints": {
                "length_min": 25,
                "length_max": 35,
            },
            "note": (
                "The current Gen-1 product-size envelope is 5-20 kb, so only the overlapping part of the "
                "manufacturer's wider capability is executable. R050A documents 20-25-mers for <=10 kb and "
                "25-35-mers for >10 kb. Because this single runtime branch spans both product classes and the "
                "current generic constraint layer is not product-size-conditional, PCRStudio conservatively "
                "uses 25-35 nt: it remains compatible with the >10 kb branch without claiming that shorter "
                "20-24 nt primers are invalid below 10 kb. Takara's vendor-specific Tm formula and qualitative "
                "3'-GC warning are preserved as bench/manual-review authority rather than translated into "
                "Primer3 numeric gates. The separate Rapid PCR protocol is not silently activated. PrimeSTAR "
                "GXL does not accept dUTP/uracil-containing templates."
            ),
        }

    return {
        "kind": "long-range-pcr",
        "protocol_id": selected,
        "selection": "Thermo Scientific Long PCR Enzyme Mix K0181/K0182",
        "kit_ids": ["K0181", "K0182"],
        "manual": "MAN0016323 / Long PCR Enzyme Mix product information",
        "source_publication": "MAN0016323",
        "source_revision": "A.00",
        "source_revision_date": "2016-11-28",
        "lifecycle": {
            "status": "discontinued",
            "discontinued_date": "2017-05-01",
            "replacement_part": "F530S",
            "replacement_name": "Phusion High-Fidelity DNA Polymerase",
            "replacement_is_informational_only": True,
            "silent_substitution_allowed": False,
        },
        "reaction_volume_uL": 50,
        "primer_final_concentration_uM": {"min": 0.3, "max": 1.0},
        "magnesium_chloride_mM": 1.5,
        "dntp_each_mM": 0.2,
        "enzyme_units": {"up_to_20kb_min": 1.0, "up_to_20kb_max": 1.25, "at_or_above_20kb_max": 2.5},
        "cycling_model": {
            "supplier_preference": "two-step-in-most-cases",
            "branch_selection": {
                "supplier_rule": "use three-step cycling when the primer annealing temperature is below 65 C",
                "selected_branch": "unresolved-until-kit-compatible-annealing-temperature-authority",
                "screening_tm_is_not_bench_ta_authority": True,
            },
            "two_step": {
                "initial_denaturation": {"temperature_c": 94, "minutes": {"min": 1, "max": 3}},
                "phase_1": {
                    "cycles": 10,
                    "denaturation": {"temperature_c": {"min": 94, "max": 96}, "seconds": 20},
                    "anneal_extend": {"temperature_c": 68, "seconds_per_kb": {"min": 45, "max": 60}},
                },
                "phase_2": {
                    "cycles": {"min": 15, "max": 25},
                    "denaturation": {"temperature_c": 94, "seconds": 20},
                    "anneal_extend_temperature_c": 68,
                    "base_extension_seconds_per_kb": {"min": 45, "max": 60},
                    "auto_extension": "product-length-table-dependent increment per cycle from cycle 11",
                },
                "final_extension": {"temperature_c": 68, "minutes": 2},
            },
            "three_step": {
                "initial_denaturation": {"temperature_c": 94, "minutes": {"min": 1, "max": 3}},
                "phase_1": {
                    "cycles": 10,
                    "denaturation": {"temperature_c": {"min": 94, "max": 96}, "seconds": 20},
                    "annealing": {"temperature_rule": "Tm-5 C", "seconds": 30},
                    "extension": {"temperature_c": 68, "seconds_per_kb": {"min": 45, "max": 60}},
                },
                "phase_2": {
                    "cycles": {"min": 15, "max": 25},
                    "denaturation": {"temperature_c": 94, "seconds": 20},
                    "annealing": {"temperature_rule": "Tm-5 C", "seconds": 30},
                    "extension_temperature_c": 68,
                    "base_extension_seconds_per_kb": {"min": 45, "max": 60},
                    "auto_extension": "product-length-table-dependent increment per cycle from cycle 11",
                },
                "final_extension": {"temperature_c": 68, "minutes": 2},
            },
        },
        "cycling_summary": "Historical K0181/K0182 two-phase auto-extension protocol; exact branch remains unresolved until kit-compatible annealing-temperature authority is supplied.",
        "screening_thermodynamics": "shared long-range calculation adapter; proprietary buffer composition is not reconstructed",
        "thermodynamic_model_impact": "none",
        "sequence_decision_impact": "constraint-envelope",
        "constraints": {
            "length_min": 27,
            "length_max": 36,
            "tm_min": 60.0,
            "tm_max": 74.0,
            "tm_pair_max_difference": 5.0,
            "max_end_gc": 3,
        },
        "note": (
            "Historical named manufacturer branch retained for reproducibility or users who already possess the kit. "
            "K0181/K0182 were discontinued by Thermo Fisher on 2017-05-01; the listed F530S replacement is "
            "informational only and is never substituted silently because it is a different chemistry/protocol. "
            "PCRStudio Gen-1 executes only its 5-20 kb subset; that is a software-support boundary, not the "
            "manufacturer's maximum reach. The manual publishes both two-step and three-step cycling and states "
            "that the three-step branch is used when primer annealing temperature is below 65 C. PCRStudio records "
            "that supplier rule but does not convert its own Primer3 screening Tm into a bench annealing temperature; "
            "branch selection therefore remains unresolved until a kit/cycler-compatible annealing-temperature "
            "authority is supplied. The manual's product-length table and auto-extension rule remain authoritative."
        ),
    }


def rpa_protocol(
    named: str | None, *, assay_id: str, from_rna: bool = False
) -> dict[str, Any] | None:
    """Return one explicitly reviewed RPA / RT-RPA chemistry overlay.

    RPA does not use thermal denaturation, so these records preserve the
    selected supplier's isothermal, oligo and reagent context without
    pretending that PCR melting temperature predicts RPA performance.  A
    protocol may own a sequence *constraint envelope* when the manufacturer
    publishes primer/product bounds that materially differ from the shared
    search defaults.  RNA execution is permitted only for a named branch that
    also defines its reverse-transcription reagents and one-pot hold.
    """
    selected = str(named or "not-selected")
    if selected not in RPA_PROTOCOLS:
        raise ValueError("rpa_protocol must be one of: " + ", ".join(RPA_PROTOCOLS) + ".")
    if selected == "not-selected":
        if assay_id == "rpa":
            raise ValueError(
                "RPA design requires an explicit executable chemistry branch. "
                "Generation 1 supports `twistamp-basic`, `twistamp-liquid-basic` and "
                "`thermo-lyo-ready-rpa`; Exo/Nfo/Fpg/SIBA remain typed non-executable "
                "boundaries until their modified-probe/nuclease contracts are implemented."
            )
        return None
    if selected not in {"twistamp-basic", "twistamp-liquid-basic", "thermo-lyo-ready-rpa", "gbiosciences-rpa-786-2155"}:
        branch = {
            "twistamp-exo": "TwistAmp Exo",
            "twistamp-nfo": "TwistAmp Nfo",
            "twistamp-fpg": "TwistAmp Fpg",
            "siba-reference": "SIBA/reference branch",
        }.get(selected, selected)
        raise ValueError(
            f"{branch} is recognised but is not executable in the generation-1 plain-oligo contract. "
            "This branch requires a typed probe/nuclease architecture (for example THF/dSpacer, "
            "fluorophore/quencher, affinity tag and/or 3-prime block) that cannot be represented "
            "safely as an ordinary ACGT primer. Use an executable plain-primer RPA branch or keep "
            "the specialised branch as an explicit validation handoff."
        )
    if assay_id != "rpa":
        raise ValueError(
            "a named RPA overlay belongs to the `rpa` assay, "
            f"not `{assay_id or 'an unbound request'}`."
        )

    if selected == "gbiosciences-rpa-786-2155":
        return dict(RPA_ADDITIONAL_PROTOCOL_RECORDS[selected])

    if selected == "thermo-lyo-ready-rpa":
        protocol: dict[str, Any] = {
            "kind": "rpa",
            "protocol_id": selected,
            "selection": "Invitrogen Lyo-ready RPA Kit (A72127/A72128)",
            "source_publication": "MAN1000697",
            "source_revision": "Rev B",
            "source_revision_date": "2025-03-06",
            "source_revision_date_precision": "day",
            "format": "glycerol-free liquid components; lyo-ready formulation",
            "reaction_volume_uL": {"standard": 20, "source_backed_scaled": 50},
            "reaction_scaling": {"source": "Thermo Fisher Lyo-ready RPA FAQ", "supported_uL": [20, 50], "note": "Scale all reaction components proportionally; the vendor FAQ supports scaling 20-uL reactions to 50 uL."},
            "primer_length_nt": {
                "rapid_preferred_min": 30,
                "rapid_preferred_max": 35,
                "reviewed_upper_nt": 35,
                "below_preferred_note": "The supplier says (RT-)RPA primers must be at least 30 nt and gives 30-35 nt as the optimal range; Gen-1 therefore keeps this named branch inside that reviewed range.",
            },
            "amplicon_bp": {
                "preferred_rapid_min": 150,
                "preferred_rapid_max": 450,
                "supported_context_max": 450,
            },
            "constraints": {
                "length_min": 30,
                "length_max": 35,
                "gc_min": 30,
                "gc_max": 70,
                "product_min": 150,
                "product_max": 450,
            },
            "amplicon_gc_percent": {
                "min": 35,
                "max": 60,
                "status": "enforced-named-protocol-amplicon-composition-filter",
                "scope": "whole predicted amplicon GC; never substituted for primer GC",
            },
            "temperature_c": 42,
            "temperature_range_c": {"min": 34, "max": 45},
            "incubation_minutes": 20,
            "incubation_range_minutes": {"min": 10, "max": 25, "context": "template-input and multiplex dependent"},
            "mixing": {"optional_rpm": 300, "effect": "supplier says shaking during incubation may increase sensitivity"},
            "primer_final_concentration_nM": 300,
            "primer_final_concentration_nM_multiplex": {"starting": 100, "optimization_min": 100, "optimization_max": 300},
            "magnesium_chloride_mM": 14,
            "dntp_each_mM": 0.2,
            "protein_starting_points": {
                "UvsX_mg_per_mL": 0.03,
                "UvsY_mg_per_mL": 0.03,
                "Gene32_mg_per_mL": 0.4,
                "Bst_U_per_uL": 0.15,
            },
            "polymerase_optimization_U_per_uL": {"min": 0.015, "max": 0.15},
            "setup": {
                "temperature": "on ice",
                "magnesium_added_last": True,
                "note": "MgCl2 initiates the reaction; prepare NTCs before positive samples and keep endpoint product analysis physically separated from setup when tubes are opened.",
            },
            "contamination_control": {
                "carryover_risk": "high-consequence-endpoint-amplicon",
                "environment_and_carryover_false_positive_recognized": True,
                "ntc_prepared_before_positive_samples": True,
                "filtered_tips": True,
                "separate_endpoint_workspace_when_opening_tubes": True,
                "closed_tube_readout_preferred_when_available": "risk-reduction-not-a-validated-universal-readout rule",
                "note": "MAN1000697 Rev B explicitly lists environment-borne/carry-over contamination as a false-positive cause and requires cleaning, filtered tips, separated negative-control/sample handling, and a separate endpoint-analysis workspace when amplicons are opened.",
            },
            "readout": "Endpoint RPA/RT-RPA product; detection modality is not inferred from the plain-primer design request",
            "oligo_contract": "plain-acgt-two-primer",
            "modified_probe_support": False,
            "modified_probe_branch_status": "recognized-non-executable-in-flanking-pair-gen1",
            "readout_contract": "endpoint-product-detection-modality-not-inferred",
            "supports_dna": True,
            "supports_rna": True,
            "sequence_decision_impact": "constraint-envelope",
            "thermodynamic_model_impact": "none",
            "note": (
                "MAN1000697 Rev B defines a distinct Lyo-ready RPA/RT-RPA chemistry with >=30 nt primers, "
                "30-70% primer GC and 150-450 bp amplicons. PCRStudio applies only those supplier sequence "
                "bounds that map directly to the existing flanking-pair constraint contract; the separate "
                "35-60% whole-amplicon GC recommendation is enforced as its own post-search composition "
                "filter rather than being misapplied as primer GC. "
                "Conventional PCR Tm remains non-mechanistic for RPA and candidate pairs still require empirical screening."
            ),
        }
        if from_rna:
            protocol["reverse_transcription"] = {
                "mode": "one-pot-rt-rpa",
                "authority_status": "named-thermo-rt-rpa-chemistry",
                "isothermal": True,
                "temperature_c": 42,
                "incubation_minutes": 20,
                "reverse_transcriptase": "SuperScript IV Reverse Transcriptase",
                "reverse_transcriptase_final_U_per_uL": 2.0,
                "rnase_inhibitor": "RNaseOUT Recombinant Ribonuclease Inhibitor",
                "rnase_inhibitor_final_U_per_uL": 1.6,
                "rnase_h": "RNase H",
                "rnase_h_final_U_per_uL": 0.1,
                "note": "These are the MAN1000697 Rev B RT-RPA starting concentrations; other RT enzymes are not silently substituted by this named branch.",
            }
        return protocol

    if from_rna:
        raise ValueError(
            "The selected TwistAmp Basic-family branch is executed here as DNA amplification. Current TwistDx guidance permits "
            "RNA by adding a separately chosen reverse transcriptase, but this generation-1 "
            "request does not represent a named TwistDx RT-addition recipe. Choose `thermo-lyo-ready-rpa` "
            "for the explicitly modeled one-pot RT-RPA branch, or provide DNA/cDNA for the TwistAmp Basic-family branches."
        )

    if selected == "twistamp-liquid-basic":
        return {
            "kind": "rpa",
            "protocol_id": selected,
            "selection": "TwistAmp Liquid Basic (TALQBAS01; DNA)",
            "source_publication": "INLQBAS / TwistAmp Liquid Combined Instruction Manual",
            "source_revision": "INLQBAS v4.0; combined-manual Rev 1 reviewed",
            "source_revision_date": None,
            "source_revision_date_precision": None,
            "format": "liquid-flexible",
            "reaction_volume_uL": 50,
            "primer_length_nt": {
                "rapid_preferred_min": 30,
                "rapid_preferred_max": 35,
                "reviewed_upper_nt": 45,
                "below_preferred_note": "Shorter PCR-length oligos may work, but TwistDx states kinetics can be slower and primer screening remains empirical.",
            },
            "amplicon_bp": {"preferred_rapid_min": 100, "preferred_rapid_max": 200, "supported_context_max": 500},
            "temperature_c": 40,
            "temperature_range_c": {"min": 37, "max": 42},
            "incubation_minutes": 20,
            "incubation_range_minutes": {"min": 20, "max": 40},
            "agitation": {"after_minutes": 4, "action": "six inversions and brief spin for low-copy template; supplier permits assay-dependent mixing optimisation"},
            "primer_final_concentration_nM": 480,
            "magnesium_acetate_mM": 14,
            "dntp_total_mM": 1.8,
            "production_dna_warning": {
                "status": "unconditional-named-kit-warning",
                "contaminant": "supplier production-process E. coli DNA limitation",
                "production_strain": "supplier warning does not authorize organism inference from sequence",
                "supplier_boundary": "current TwistDx product notice says standard laboratory E. coli strains are not suitable without technical-support review",
                "organism_inferred_from_sequence": False,
                "action": "contact TwistDx technical support before E. coli assay development with this chemistry",
            },
            "contamination_control": {
                "carryover_risk": "high-copy-isothermal-amplicon",
                "environment_and_carryover_false_positive_recognized": True,
                "separate_pre_post_amplification_areas": True,
                "post_amplification_opening_high_risk": True,
                "high_copy_material_near_setup_avoid": True,
                "bleach_decontamination_guidance": "TwistDx FAQ recommends 10% bleach for contaminated work areas and fresh reagent aliquots",
                "closed_tube_readout_preferred_when_available": "risk-reduction-not-a-universal-readout-requirement",
                "note": "Current TwistDx contamination guidance identifies positive NTCs as commonly caused by carry-over/environmental contamination, recommends separate pre/post-amplification areas and dedicated aliquots/equipment, and treats opened endpoint reactions as a high-risk source. These are workflow controls, not sequence-derived assay guarantees.",
            },
            "readout": "Endpoint Liquid Basic reaction; purify amplicon before agarose gel or downstream analysis",
            "oligo_contract": "plain-acgt-two-primer",
            "modified_probe_support": False,
            "modified_probe_branch_status": "recognized-non-executable-in-flanking-pair-gen1",
            "readout_contract": "endpoint-product-detection-modality-not-inferred",
            "sequence_decision_impact": "none",
            "thermodynamic_model_impact": "none",
            "note": (
                "Liquid Basic is a current flexible DNA-RPA format. The quick guide gives 50 uL setup, "
                "480 nM each primer, 14 mM final MgOAc and 1.8 mM total dNTP as the suggested starting "
                "concentration, with 37-42 C for 20-40 min. Added reverse transcriptase is a separate "
                "chemistry decision and is not inferred by this DNA branch. RPA Tm remains non-mechanistic; "
                "candidate pairs require empirical screening."
            ),
        }

    return {
        "kind": "rpa",
        "protocol_id": selected,
        "selection": "TwistAmp Basic (TABAS03KIT; DNA)",
        "source_publication": "INTABAS",
        "source_revision": "v3.0",
        "source_revision_date": None,
        "source_revision_date_precision": None,
        "primer_length_nt": {
            "rapid_preferred_min": 30,
            "rapid_preferred_max": 35,
            "reviewed_upper_nt": 45,
            "below_preferred_note": "Oligos shorter than 30 nt can function, but the current TwistDx manual reports typically slower amplification kinetics; no evidence-backed hard minimum is asserted here.",
        },
        "amplicon_bp": {"preferred_rapid_min": 100, "preferred_rapid_max": 200, "supported_context_max": 500},
        "temperature_c": 39,
        "incubation_minutes": 20,
        "agitation": {"after_minutes": 4, "action": "vortex-and-brief-spin"},
        "primer_final_concentration_nM": 480,
        "magnesium_acetate_mM": 14,
        "production_dna_warning": {
            "status": "unconditional-named-kit-warning",
            "contaminant": "supplier production-process E. coli DNA limitation",
            "production_strain": "not specified by the current product notice",
            "supplier_boundary": "current TwistDx product notice says standard laboratory E. coli strains are not suitable without technical-support review",
            "organism_inferred_from_sequence": False,
            "action": "contact TwistDx technical support before E. coli assay development with this chemistry",
        },
        "contamination_control": {
            "carryover_risk": "high-copy-isothermal-amplicon",
            "environment_and_carryover_false_positive_recognized": True,
            "separate_pre_post_amplification_areas": True,
            "post_amplification_opening_high_risk": True,
            "high_copy_material_near_setup_avoid": True,
            "bleach_decontamination_guidance": "TwistDx FAQ recommends 10% bleach for contaminated work areas and fresh reagent aliquots",
            "closed_tube_readout_preferred_when_available": "risk-reduction-not-a-universal-readout-requirement",
            "note": "Current TwistDx contamination guidance identifies positive NTCs as commonly caused by carry-over/environmental contamination, recommends separate pre/post-amplification areas and dedicated aliquots/equipment, and treats opened endpoint reactions as a high-risk source. These are workflow controls, not sequence-derived assay guarantees.",
        },
        "readout": "Endpoint Basic reaction; clean amplicon before gel or downstream analysis",
        "oligo_contract": "plain-acgt-two-primer",
        "modified_probe_support": False,
        "modified_probe_branch_status": "recognized-non-executable-in-flanking-pair-gen1",
        "readout_contract": "endpoint-product-detection-modality-not-inferred",
        "sequence_decision_impact": "none",
        "thermodynamic_model_impact": "none",
        "note": (
            "Named TwistAmp Basic DNA branch. RPA primer performance is not established by "
            "PCR Tm; experimentally screen candidate primer combinations. RNA is not silently "
            "promoted to a historical Basic-RT identity: use the explicitly named Thermo Lyo-ready "
            "RT-RPA branch or provide DNA/cDNA. The lyophilised Basic quick guide does not expose a "
            "user-set dNTP concentration, so PCRStudio does not import the 1.8 mM Liquid Basic value "
            "into this bench handoff."
        ),
    }



def colony_protocol(named: str | None, *, assay_id: str, host_class: str, preparation: str) -> dict[str, Any] | None:
    selected = str(named or "").strip()
    if assay_id != "colony-pcr":
        if selected:
            raise ValueError("colony_protocol_id belongs to colony-pcr")
        return None
    if selected not in COLONY_PROTOCOLS:
        raise ValueError("colony_protocol_id must be one of: " + ", ".join(COLONY_PROTOCOLS))
    if selected == "custom-sop":
        return None
    record = dict(COLONY_PROTOCOL_RECORDS[selected])
    if host_class not in record["host_classes"]:
        raise ValueError(f"{selected} is source-backed only for host classes: {', '.join(record['host_classes'])}")
    if preparation not in record["preparations"]:
        raise ValueError(f"{selected} is source-backed only for preparations: {', '.join(record['preparations'])}")
    return record


def colony_context(request: dict[str, Any], *, assay_id: str) -> dict[str, Any] | None:
    """Resolve source-backed colony-PCR SOP identity without inventing a universal lysis programme."""
    fields = (
        "colony_host_class", "colony_preparation", "colony_protocol_id",
        "colony_protocol_name", "colony_protocol_provenance",
    )
    supplied = any(request.get(field) not in (None, "") for field in fields)
    if assay_id != "colony-pcr":
        if supplied:
            raise ValueError(
                "colony_host_class/colony_preparation/colony_protocol_id/colony_protocol_name/colony_protocol_provenance belong to colony-pcr"
            )
        return None

    host = str(request.get("colony_host_class") or "").strip()
    preparation = str(request.get("colony_preparation") or "").strip()
    protocol_id = str(request.get("colony_protocol_id") or "").strip()
    protocol_name = str(request.get("colony_protocol_name") or "").strip()
    protocol_provenance = str(request.get("colony_protocol_provenance") or "").strip()
    if host not in COLONY_HOST_CLASSES:
        raise ValueError("colony_host_class must be one of: " + ", ".join(sorted(COLONY_HOST_CLASSES)))
    if preparation not in COLONY_PREPARATIONS:
        raise ValueError("colony_preparation must be one of: " + ", ".join(sorted(COLONY_PREPARATIONS)))
    if not protocol_id:
        # Historical request compatibility: an explicit name+provenance pair is
        # treated as the custom SOP branch, never as a vendor protocol.
        if protocol_name and protocol_provenance:
            protocol_id = "custom-sop"
        else:
            raise ValueError("colony_protocol_id is required; choose a reviewed vendor branch or custom-sop")
    selected = colony_protocol(protocol_id, assay_id=assay_id, host_class=host, preparation=preparation)
    if protocol_id == "custom-sop":
        if not protocol_name:
            raise ValueError("custom-sop requires colony_protocol_name")
        if not protocol_provenance:
            raise ValueError("custom-sop requires colony_protocol_provenance with owner/source and revision/date")
        authority = {
            "protocol_id": protocol_id,
            "selection": protocol_name,
            "source_publication": protocol_provenance,
            "host_classes": [host],
            "preparations": [preparation],
            "sequence_decision_impact": "none",
        }
    else:
        authority = selected or {}
        # Vendor identity is canonical; optional free text may annotate but cannot
        # replace the source-backed authority.
        protocol_name = str(authority.get("selection") or protocol_id)
        protocol_provenance = str(authority.get("source_publication") or "reviewed vendor protocol")

    return {
        "host_class": host,
        "preparation": preparation,
        "protocol_id": protocol_id,
        "protocol_name": protocol_name,
        "protocol_provenance": protocol_provenance,
        "source_url": authority.get("source_url"),
        "source_conditioned_protocol": authority,
        "interpretation_status": "in-silico-screen-design",
        "lysis_timing_inferred": False,
        "sample_amount_inferred": False,
        "source_recovery_status": "user-managed-retained-source-required-for-recoverable-positive-screen",
        "required_observations": [
            "retained source colony/culture or patch/streak when a positive screen must remain recoverable",
            "positive PCR/process control",
            "negative host/process control",
            "empty-vector control when geometry requires it",
            "no-template control",
            "observed gel band count and size",
            "independent clone identity confirmation before a confirmed construct call",
        ],
        "sequence_decision_impact": "none",
        "note": (
            "Host, preparation and SOP identity are pre-analytical provenance. Vendor numeric values remain scoped to "
            "the selected branch; PCRStudio does not average conflicting colony-lysis protocols or promote a predicted band to a verified clone."
        ),
    }


def digital_context(request: dict[str, Any], *, assay_id: str) -> dict[str, Any] | None:
    """Preserve the run context that makes a dPCR result interpretable.

    Partition format, platform identity and fragmentation state are not primer
    ranking features. They are explicit because droplet/chip/chamber workflows
    and template-fragmentation requirements are not interchangeable. Threshold,
    rain/cluster review and Poisson estimates remain measured-run evidence.
    """
    fields = ("digital_partition_format", "digital_platform_id", "digital_platform_name", "digital_instrument_model", "digital_fragmentation_state", "digital_multiplex_mode", "digital_multiplex_panel", "digital_run_evidence")
    supplied = any(request.get(field) not in (None, "") for field in fields)
    if assay_id != "digital-pcr":
        if supplied:
            raise ValueError(
                "digital_partition_format/digital_platform_id/digital_platform_name/digital_fragmentation_state belong to digital-pcr"
            )
        return None

    partition = str(request.get("digital_partition_format") or "").strip()
    platform_id = str(request.get("digital_platform_id") or "").strip()
    platform = str(request.get("digital_platform_name") or "").strip()
    instrument_model = str(request.get("digital_instrument_model") or "").strip()
    fragmentation = str(request.get("digital_fragmentation_state") or "").strip()
    if partition not in DIGITAL_PARTITION_FORMATS:
        raise ValueError(
            "digital_partition_format must be one of: " + ", ".join(sorted(DIGITAL_PARTITION_FORMATS))
        )
    if platform_id not in DIGITAL_PLATFORM_IDS:
        raise ValueError(
            "digital_platform_id must be one of: " + ", ".join(sorted(DIGITAL_PLATFORM_IDS))
        )
    if platform_id == "other-validated":
        if not platform:
            raise ValueError(
                "digital_platform_name is required when digital_platform_id=other-validated"
            )
    else:
        canonical_name = DIGITAL_PLATFORM_LABELS.get(platform_id)
        aliases = DIGITAL_PLATFORM_NAME_ALIASES.get(platform_id, frozenset())
        if canonical_name is None or not aliases:
            raise ValueError(f"digital platform authority is incomplete for {platform_id}")
        if platform and platform.casefold() not in aliases:
            raise ValueError(
                f"digital_platform_id={platform_id} cannot be combined with a different platform name"
            )
        platform = canonical_name
    numeric_context = request.get("flanking_numeric_context") or {}
    consumable_id = str(numeric_context.get("digital_consumable_id") or "").strip() if isinstance(numeric_context, dict) else ""
    if consumable_id:
        if consumable_id not in DIGITAL_CONSUMABLE_IDS:
            raise ValueError("digital_consumable_id must be one of: " + ", ".join(sorted(DIGITAL_CONSUMABLE_IDS)))
        allowed_platforms = DIGITAL_CONSUMABLE_PLATFORMS.get(consumable_id, frozenset())
        if platform_id not in allowed_platforms:
            raise ValueError(
                f"digital_consumable_id={consumable_id} is not source-backed for digital_platform_id={platform_id}"
            )
    if fragmentation not in DIGITAL_FRAGMENTATION_STATES:
        raise ValueError(
            "digital_fragmentation_state must be one of: "
            + ", ".join(sorted(DIGITAL_FRAGMENTATION_STATES))
        )
    protocol_id = str(request.get("digital_protocol") or "").strip()
    platform_route = DIGITAL_PLATFORM_ROUTES.get(platform_id)
    if platform_route == "pair-probe":
        raise ValueError(
            "the selected digital platform is recognized, but its current validated chemistry is probe-oriented; route this assay to Pair+Probe rather than executing it in dye-based Flanking"
        )
    allowed_protocol_platforms = DIGITAL_PROTOCOL_PLATFORMS.get(protocol_id)
    if allowed_protocol_platforms is not None and platform_id not in allowed_protocol_platforms:
        raise ValueError(
            f"digital_protocol={protocol_id} is not source-backed for digital_platform_id={platform_id}"
        )
    if protocol_id == "bio-rad-qx200-evagreen":
        if partition != "droplet":
            raise ValueError(
                "bio-rad-qx200-evagreen is a droplet-dPCR overlay; digital_partition_format must be droplet"
            )
    if protocol_id in {"bio-rad-qx700-naica-evagreen", "bio-rad-qx700-evagreen-supermix"}:
        if partition != "droplet":
            raise ValueError(
                "the selected Bio-Rad EvaGreen chemistry is a droplet-dPCR overlay; digital_partition_format must be droplet"
            )
    if request.get("digital_protocol") in {
        "qiagen-qiacuity-eg",
        "qiagen-qiacuity-onestep-advanced-eg",
    }:
        if partition != "chamber":
            raise ValueError(
                "the selected QIAcuity chemistry uses fixed QIAcuity Nanoplate microchambers; digital_partition_format must be chamber"
            )
    multiplex_mode = str(request.get("digital_multiplex_mode") or "none").strip().lower()
    if multiplex_mode not in {"none", "channel", "amplitude", "hybrid", "probe-mix"}:
        raise ValueError("digital_multiplex_mode must be one of: none, channel, amplitude, hybrid, probe-mix")
    panel_raw = request.get("digital_multiplex_panel")
    if panel_raw is None:
        panel: list[dict[str, Any]] = []
    elif not isinstance(panel_raw, list):
        raise ValueError("digital_multiplex_panel must be an array")
    else:
        panel = []
        for index, raw in enumerate(panel_raw, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"digital_multiplex_panel target {index} must be an object")
            target = str(raw.get("target") or "").strip()
            reporter = str(raw.get("reporter") or "").strip() or None
            channel = str(raw.get("channel") or "").strip() or None
            amplitude = str(raw.get("amplitude_class") or raw.get("amplitudeClass") or "").strip() or None
            primer_each = raw.get("primer_each_nm", raw.get("primerEachNm"))
            probe_nm = raw.get("probe_nm", raw.get("probeNm"))
            if not target:
                raise ValueError(f"digital_multiplex_panel target {index} requires a target identity")
            values = {"target": target, "reporter": reporter, "channel": channel, "amplitude_class": amplitude}
            for key, value in (("primer_each_nm", primer_each), ("probe_nm", probe_nm)):
                if value not in (None, ""):
                    try:
                        numeric = float(value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"digital multiplex {key} must be numeric") from exc
                    if not math.isfinite(numeric) or numeric <= 0:
                        raise ValueError(f"digital multiplex {key} must be positive and finite")
                    values[key] = numeric
            panel.append(values)
    if multiplex_mode == "none" and panel:
        raise ValueError("digital_multiplex_panel requires a non-none digital_multiplex_mode")
    if multiplex_mode != "none":
        if len(panel) < 2 or len(panel) > DIGITAL_MULTIPLEX_SOFTWARE_MAX_TARGETS:
            raise ValueError("digital multiplex planning requires 2–12 targets; 12 is a software/planning bound, not a wet-lab qualification claim")
        target_ids = [row["target"] for row in panel]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("digital multiplex target identities must be unique")
        if protocol_id and protocol_id != "not-selected":
            raise ValueError(
                "digital multiplex probe/amplitude planning cannot inherit a named dye/EvaGreen chemistry. "
                "Leave digital_protocol=not-selected and bind the exact probe multiplex chemistry in the Pair+Probe/vendor run authority."
            )
        if multiplex_mode == "channel":
            channels = []
            for row in panel:
                if not row.get("reporter") or not row.get("channel"):
                    raise ValueError("channel dPCR multiplex requires reporter and channel for every target")
                channels.append(str(row["channel"]))
            if len(set(channels)) != len(channels):
                raise ValueError("channel dPCR multiplex requires unique explicit channels; use amplitude/hybrid mode for intentional channel sharing")
        if multiplex_mode in {"amplitude", "hybrid"} and any(not row.get("amplitude_class") for row in panel):
            raise ValueError("amplitude/hybrid dPCR multiplex requires amplitude_class for every target")
        authority_key = instrument_model if platform_id == "qiagen-qiacuity" else platform_id
        if platform_id == "qiagen-qiacuity" and not instrument_model:
            raise ValueError("digital_instrument_model is required for QIAcuity multiplex planning because model optical capacity differs")
        authority = DIGITAL_MULTIPLEX_PLATFORM_AUTHORITIES.get(str(authority_key or ""))
        if platform_id == "qiagen-qiacuity" and authority is None:
            raise ValueError("unsupported QIAcuity multiplex instrument model")
        if authority is not None:
            allowed_modes = {str(item) for item in authority.get("modes") or []}
            if multiplex_mode not in allowed_modes:
                raise ValueError(
                    f"{authority.get('family') or authority_key} source-backed multiplex authority does not support mode {multiplex_mode}; "
                    f"allowed modes: {', '.join(sorted(allowed_modes)) or 'none'}"
                )
            channel_max = int(authority.get("detection_channels") or 0)
            total_max = int(authority.get("multiplex_target_bound") or 0)
            if multiplex_mode == "channel" and len(panel) > channel_max:
                raise ValueError(
                    f"{authority.get('family') or authority_key} channel-per-target planning is source-backed only up to {channel_max} targets"
                )
            if len(panel) > total_max:
                raise ValueError(
                    f"{authority.get('family') or authority_key} multiplex planning is source-backed only up to {total_max} targets; "
                    "this is not a wet-lab qualification claim"
                )
    run_evidence = request.get("digital_run_evidence")
    if run_evidence is not None and not isinstance(run_evidence, dict):
        raise ValueError("digital_run_evidence must be an object when supplied")
    panel_sha256 = (
        hashlib.sha256(json.dumps(panel, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if panel else None
    )
    partition_volume_authority = (
        "record-current-nanoplate-type/lot-and-QIAcuity-volume/VPF-policy"
        if platform_id == "qiagen-qiacuity"
        else "record-platform/software-specific-partition-volume-model-or-calibration"
    )
    return {
        "platform_id": platform_id,
        "platform_name": platform,
        "instrument_model": instrument_model or None,
        "platform_route": platform_route,
        "protocol_id": protocol_id or None,
        "partition_format": partition,
        "fragmentation_state": fragmentation,
        "consumable_id": consumable_id or None,
        "multiplex": {
            "mode": multiplex_mode,
            "panel": panel,
            "panel_sha256": panel_sha256,
            "target_count": len(panel),
            "software_planning_bound": 12,
            "wet_lab_qualified_plex": None,
            "sequence_design_scope": "current-primer-pair-only; peer probe assays require Pair+Probe/vendor authority",
            "threshold_rain_cluster_inference": "forbidden-from-sequence",
            "run_evidence": run_evidence,
            "decision_impact": "planning-and-run-evidence-only",
        } if multiplex_mode != "none" else None,
        "run_status": "multiplex-planning-evidence-handoff" if multiplex_mode != "none" else "design-handoff",
        "threshold_status": "measured-run-required",
        "quantification_status": "not-computed-from-design",
        "partition_volume_authority_status": partition_volume_authority,
        "analysis_software_version_status": "record-exact-platform-analysis-software/version-required",
        "volume_precision_factor_status": (
            "record-QIAcuity-VPF/effective-volume-policy-when-applicable"
            if platform_id == "qiagen-qiacuity"
            else "platform-specific-volume-correction-not-inferred"
        ),
        "current_platform_authority_reference": (
            {
                "software_suite_reference": "QIAcuity Software Suite 3.5 (current public reference reviewed 2026-09-05)",
                "volume_precision_factor_reference": "QIAcuity VPF Version 13, July 2026",
                "authority_use": "reference-only-for-run-provenance; record the exact software/version and VPF actually used by the run",
                "inference_policy": "never-substitute-current-reference-for-measured-run-metadata",
            }
            if platform_id == "qiagen-qiacuity"
            else None
        ),
        "required_run_evidence": [
            "accepted partition count/yield",
            "threshold or cluster-classification policy",
            "positive/negative controls and rain review as applicable",
            "Poisson/occupancy estimate from the measured run",
            "exact analysis software/version and the partition-volume model/calibration used for quantification",
            *(
                ["QIAcuity Nanoplate type/lot and VPF or effective-volume policy used by the analysis"]
                if platform_id == "qiagen-qiacuity"
                else ["platform-specific droplet/partition volume source or calibration revision"]
            ),
        ],
        "note": (
            "PCRStudio records platform/partition/fragmentation provenance but does not infer "
            "accepted partitions, threshold/rain classification, partition volume or concentration from primer design. "
            "Absolute concentration must remain bound to the exact platform/software and current partition-volume authority; "
            "historical partition-volume constants are not substituted across instruments, plate lots or software revisions. "
            "When a digital multiplex panel is supplied, it is an optical/amplitude planning and measured-run evidence contract; "
            "the dye-flanking designer does not claim to have designed peer probe assays or classified partitions."
        ),
    }


def digital_protocol(
    named: str | None, *, assay_id: str, from_rna: bool = False
) -> dict[str, Any] | None:
    """Return a reviewed dye-dPCR platform/chemistry handoff, or no overlay.

    The dPCR overlay is deliberately a run handoff. Partition counts,
    thresholding and Poisson uncertainty are measured from droplets and are
    not sequence-derived primer constraints.
    """
    selected = str(named or "not-selected")
    if selected not in DIGITAL_PROTOCOLS:
        raise ValueError("digital_protocol must be one of: " + ", ".join(DIGITAL_PROTOCOLS) + ".")
    if selected == "not-selected":
        return None
    if assay_id != "digital-pcr":
        raise ValueError(
            "a named dye-dPCR overlay belongs to the `digital-pcr` assay, "
            f"not `{assay_id or 'an unbound request'}`."
        )
    if selected == "qiagen-qiacuity-onestep-advanced-eg":
        protocol: dict[str, Any] = {
            "kind": "digital-pcr",
            "protocol_id": selected,
            "selection": "QIAGEN QIAcuity OneStep Advanced EvaGreen Kit",
            "source_publication": "HB-3478-003",
            "source_revision": "03/2025",
            "source_revision_date": "2025-03",
            "source_revision_date_precision": "month",
            "supermix": "4x QIAcuity OneStep Advanced EvaGreen Master Mix",
            "reaction_volume_uL": {"nanoplate_8_5k": 12, "nanoplate_26k": 40},
            "primer_final_concentration_uM": 0.75,
            "partition_model": "QIAcuity fixed Nanoplate microchambers (8.5k or 26k format)",
            "supports_dna": True,
            "supports_rna": True,
            "constraints": {
                "length_min": 18,
                "length_max": 30,
                "tm_min": 58.0,
                "tm_max": 62.0,
                "tm_pair_max_difference": 2.0,
                "gc_min": 30.0,
                "gc_max": 70.0,
                "max_poly_x": 3,
            },
            "q_solution": {
                "strongly_recommended": True,
                "especially_useful_for": [
                    "amplicons >150 bp",
                    "GC-rich amplicons",
                    "RNA targets with challenging secondary structure",
                ],
                "not_a_sequence_validity_rule": True,
            },
            "cycling_summary": (
                "50 C 40 min RT; 95 C 2 min RT inactivation; 40-cycle two-step or three-step dPCR; "
                "58 C is the supplier starting annealing/extension temperature; 40 C 5 min cool-down"
            ),
            "cycling": {
                "reverse_transcription": {"temperature_c": 50, "minutes": 40},
                "rt_inactivation": {"temperature_c": 95, "minutes": 2},
                "cycles_starting": 40,
                "two_step": {
                    "denaturation": {"temperature_c": 95, "seconds": 10},
                    "annealing_extension": {
                        "temperature_c": {"min": 55, "max": 60, "starting": 58},
                        "seconds": 30,
                    },
                },
                "three_step": {
                    "denaturation": {"temperature_c": 95, "seconds": 15},
                    "annealing": {
                        "temperature_c": {"min": 55, "max": 60, "starting": 58},
                        "seconds": 15,
                    },
                    "extension": {"temperature_c": 72, "seconds": 15},
                },
                "cool_down": {"temperature_c": 40, "minutes": 5},
            },
            "readout": "EvaGreen endpoint imaging on QIAcuity Nanoplates",
            "quantitation": "measured QIAcuity partition counts/volume precision; not computed from primer design",
            "sequence_decision_impact": "constraint-envelope",
            "thermodynamic_model_impact": "none",
            "note": (
                "The March 2025 handbook publishes an 18-30 nt, 30-70% GC, 58-62 C primer-design "
                "envelope with <=2 C pair-Tm difference and avoidance of >=4-base homopolymers. "
                "PCRStudio applies those named-kit sequence constraints while retaining its shared dPCR "
                "thermodynamic calculation model. The kit can quantify DNA and RNA targets. Q-Solution "
                "is strongly recommended by the supplier but is not treated as a primer-validity rule."
            ),
        }
        if from_rna:
            protocol["reverse_transcription"] = {
                "mode": "one-step-rt-dpcr",
                "authority_status": "named-qiagen-qiacuity-onestep-advanced-eg",
                "temperature_c": 50,
                "incubation_minutes": 40,
                "before": "rt-enzyme-inactivation-and-dpcr-cycling",
                "note": (
                    "The named QIAcuity OneStep Advanced EvaGreen branch owns the 50 C/40 min "
                    "reverse-transcription step; it is not borrowed by other dPCR chemistries."
                ),
            }
        return protocol
    if selected == "bio-rad-qx700-evagreen-supermix":
        return {
            "kind": "digital-pcr",
            "protocol_id": selected,
            "selection": "Bio-Rad QX700 ddPCR EvaGreen Supermix",
            "catalog_ids": ["12025290", "12025474", "12025517"],
            "source_publication": "Bio-Rad QX700 ddPCR Supermixes and Kits bulletin 3882",
            "source_revision": "current portfolio bulletin reviewed 2026-09-03",
            "source_reviewed_date": "2026-09-03",
            "supermix": "QX700 ddPCR EvaGreen Supermix 5X",
            "reaction_input_volume_uL": 5,
            "partition_model": "QX700 droplet system; approximately 17,000 partitions per reaction in current platform specifications",
            "supports_dna": True,
            "supports_rna": False,
            "primer_concentration_status": (
                "assay-specific; Bio-Rad performance examples include differential primer concentrations (100 nM ACTB and 250 nM GAPDH) but these are not promoted to universal bounds"
            ),
            "readout": "EvaGreen droplet fluorescence on the QX700 seven-channel platform",
            "quantitation": "measured QX700 droplet classification and current platform/software partition-volume model; not computed from primer design",
            "sequence_decision_impact": "none",
            "constraints": {},
            "note": (
                "This is the dedicated current QX700 5X EvaGreen supermix branch, distinct from the retained naica ddPCR Mix branch. "
                "Bio-Rad lists it specifically for DNA target amplification/detection on QX700 systems. Performance-example primer "
                "concentrations are descriptive rather than universal design limits. Exact accepted droplets, threshold/rain policy, "
                "partition-volume authority and concentration remain measured run evidence."
            ),
        }

    if selected == "bio-rad-qx700-naica-evagreen":
        return {
            "kind": "digital-pcr",
            "protocol_id": selected,
            "selection": "Bio-Rad naica ddPCR Mix / EvaGreen · QX700/Nio/naica",
            "source_publication": "10000171490",
            "source_revision": "Ver D / IFU Version 1.0",
            "source_revision_date": "2025-08",
            "source_revision_date_precision": "month",
            "supermix": "naica ddPCR Mix (5x or 10x) + EvaGreen",
            "reaction_volume_uL": 5,
            "partition_model": "platform-bound droplet/chip consumable; RDG16 on QX700/Nio/naica or Sapphire Chip on naica according to the reviewed IFU",
            "amplicon_bp_preferred": {"min": 60, "max": 130},
            "primer_concentration_status": "supplier-variable; assay-specific optimization required",
            "buffer_b_final_percent": {"start": 4.0, "typical_min": 2.0, "typical_max": 5.0, "maximum": 5.0},
            "evagreen_final_x": 1.5,
            "fragmentation_guidance": {
                "supplier_trigger": "average DNA length >=10 kb",
                "reason": "improve even template distribution during partitioning; especially important for CNV/linkage contexts",
                "site_protection": "restriction enzyme must not cut within the amplified sequence",
                "not_required_examples": ["highly fragmented FFPE DNA", "circulating DNA"],
            },
            "cycling_summary": "official QX700 templates default to 45 PCR cycles with 58 C hybridization; assay-specific PCR program must be adapted and validated",
            "cycling": {
                "polymerase_activation": {"temperature_c": 95, "minutes": 3},
                "official_template_cycles": 45,
                "official_template_hybridization_temperature_c": 58,
                "assay_specific_validation_required": True,
            },
            "readout": "EvaGreen partition fluorescence on the validated naica/QX700/Nio branch; exact channel/software handling is platform-specific",
            "quantitation": "measured platform-specific partition classification and volume model; not computed from primer design",
            "sequence_decision_impact": "none",
            "note": (
                "The reviewed naica ddPCR Mix IFU supports EvaGreen workflows on QX700 with RDG16, Nio with RDG16, and the naica system with RDG16 or Sapphire Chip. "
                "The exact reaction/partition context remains platform and consumable specific; the IFU also leaves primer concentration assay-dependent. PCRStudio therefore "
                "does not promote performance-example primer concentrations into a universal design rule. The mix is DNA/intercalating-dye "
                "chemistry; probe-based and one-step RT-ddPCR kits are separate branches and are not silently substituted. Fragmentation, "
                "threshold/rain review, accepted droplets and concentration remain measured-run evidence."
            ),
        }

    if selected == "qiagen-qiacuity-eg":
        return {
            "kind": "digital-pcr",
            "protocol_id": selected,
            "selection": "QIAGEN QIAcuity EG PCR Kit",
            "source_publication": "HB-2791-003 / 1123717",
            "source_revision": "01/2021 quick-start protocol; current product listing reviewed 2026-09-03",
            "source_revision_date": "2021-01",
            "source_revision_date_precision": "month",
            "supermix": "QIAcuity 3x EvaGreen PCR Master Mix",
            "reaction_volume_uL": {"nanoplate_8_5k": 12, "nanoplate_26k": 40},
            "primer_final_concentration_uM": 0.4,
            "partition_model": "QIAcuity fixed Nanoplate microchambers (8.5k or 26k format)",
            "cycling_summary": "95 C 2 min activation; 40 cycles of 95 C 15 s, 55-62 C 15 s, 72 C 15 s; 40 C 5 min cool-down",
            "cycling": {
                "activation": {"temperature_c": 95, "minutes": 2},
                "denaturation": {"temperature_c": 95, "seconds": 15},
                "annealing": {"temperature_c": {"min": 55, "max": 62}, "seconds": 15},
                "extension": {"temperature_c": 72, "seconds": 15},
                "cycles": 40,
                "cool_down": {"temperature_c": 40, "minutes": 5},
            },
            "fragmentation_guidance": {
                "supplier_trigger": "average DNA length >=20 kb",
                "reason": "improve even distribution through Nanoplate partitions; especially relevant to linked-copy/CNV measurements",
                "site_protection": "do not choose a restriction enzyme that cuts within the amplified sequence",
                "not_required_examples": ["highly fragmented FFPE DNA", "circulating DNA", "cDNA"],
            },
            "readout": "EvaGreen FAM-channel endpoint imaging with QIAcuity partition-filling reference dye",
            "quantitation": "measured QIAcuity partition counts/volume precision; not computed from primer design",
            "sequence_decision_impact": "none",
            "note": (
                "The vendor identifies 60-150 bp as an ideal efficiency range and 0.4 uM each primer as the "
                "protocol starting point. PCRStudio's existing 60-150 bp dPCR profile already matches that "
                "range, so this overlay adds platform/run provenance without changing sequence ranking. "
                "Fragmentation state remains an explicit user/run decision; the design engine does not infer "
                "DNA molecular length, accepted partitions, threshold/rain policy or concentration."
            ),
        }

    return {
        "kind": "digital-pcr",
        "protocol_id": selected,
        "selection": "Bio-Rad QX200 ddPCR EvaGreen Supermix",
        "source_publication": "10000162845",
        "source_revision": "Ver B",
        "source_revision_date": "2023-04",
        "source_revision_date_precision": "month",
        "supermix": "QX200 ddPCR EvaGreen Supermix",
        "reaction_volume_uL": 20,
        "droplets_target": 20000,
        "primer_final_concentration_nM": {"min": 100, "max": 250},
        "amplicon_bp_preferred": {"min": 80, "max": 250},
        "template_dna_ng": {"max": 100, "restriction_digest_consider_above": 66},
        "fragmentation_guidance": {
            "supplier_trigger": "consider restriction digestion above 66 ng intact genomic DNA per 20 uL reaction and for applications where molecular linkage can bias partition independence",
            "site_protection": "the selected restriction enzyme must not cut within the target or reference amplicon",
            "methylation_guidance": "prefer an enzyme insensitive to the relevant template methylation state",
            "in_reaction_starting_units": "approximately 2-5 U per 20 uL reaction when direct digestion is used",
            "decision_status": "sample-dependent; never inferred from primer sequence alone",
        },
        "carryover_prevention": {
            "UNG_compatible": True,
            "UNG_built_in": False,
            "enabled_by_protocol_selection_alone": False,
            "note": "Bio-Rad states that the QX200 EvaGreen supermix is suitable for UNG decontamination protocols; the enzyme and actual workflow remain explicit bench choices.",
        },
        "cycling": {
            "activation": {"temperature_c": 95, "minutes": 5},
            "denaturation": {"temperature_c": 95, "seconds": 30},
            "annealing_extension": {"temperature_c": 60, "minutes": 1},
            "cycles": 40,
            "ramp_rate_c_per_s": 2,
        },
        "stabilization": [
            {"temperature_c": 4, "minutes": 5},
            {"temperature_c": 90, "minutes": 5},
            {"temperature_c": 4, "minutes": 30},
        ],
        "readout": "QX200 droplet reader; EvaGreen 1-D amplitude review",
        "quantitation": "copies per µL of the final 1× ddPCR reaction",
        "cycling_summary": "95 C 5 min activation; 40 cycles of 95 C 30 s and 60 C 1 min at 2 C/s; stabilization 4/90/4 C",
        "sequence_decision_impact": "none",
        "note": (
            "The QX200 EvaGreen guide gives 100-250 nM each primer, an 80-250 bp suggested amplicon, "
            "and up to 100 ng DNA per 20 uL reaction; it also flags restriction digestion above 66 ng "
            "and for applications affected by molecular linkage. Those are platform/bench starting points, "
            "not universal primer-ranking laws, so PCRStudio retains the cross-platform 60-150 bp design "
            "profile and records the QX200 preference separately. Droplet yield, accepted-well criteria, "
            "threshold/rain policy, restriction-digest choice and Poisson uncertainty remain measured run evidence."
        ),
    }


