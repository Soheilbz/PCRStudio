"""Source-conditioned numeric reaction resolution for the flanking-pair engine.

This module generalizes the canonical LAMP numeric-recipe discipline to every
executable flanking-pair assay.  It deliberately resolves *bench* chemistry;
none of these values may silently change Primer3 candidate ranking.

Only reviewed, transferable public values are numeric authority.  Vendor text
that merely says "optimize" remains an unresolved dependency unless a bounded
public range is given.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .numeric_recipe.resolver import resolve as resolve_generic_numeric_recipe
from .registries.flanking_protocols import (
    COLONY_PROTOCOL_RECORDS,
    COLONY_PROTOCOLS,
    DIGITAL_PROTOCOLS,
    LONG_RANGE_PROTOCOLS,
    PROTOCOL_PROVENANCE,
    QPCR_PROTOCOLS,
    RPA_PROTOCOLS,
    STANDARD_PCR_PROTOCOLS,
    digital_protocol,
    long_range_protocol,
    qpcr_protocol,
    rpa_protocol,
    standard_pcr_protocol,
)

FLANKING_NUMERIC_SCHEMA_VERSION = "1.0.0"

FLANKING_NUMERIC_DEPENDENCY_AXES = [
    "module",
    "exact-product",
    "formulation",
    "template-class",
    "reaction-volume",
    "primer-concentration",
    "target-length",
    "instrument-platform",
    "cycling-branch",
    "direct-sample-preparation",
    "additive",
    "carry-over",
    "partition-format",
    "fragmentation-state",
    "bench-optimization",
]

# Exact-product numeric envelopes. A fixed baseline is not promoted to an
# optimization range.  The values below are intentionally conservative: only
# source-published transferable ranges are editable.
FLANKING_NUMERIC_OPTIMIZATION_ENVELOPES: dict[str, dict[str, list[float]]] = {
    "neb-taq-m0273": {"primer_each_uM": [0.05, 1.0]},
    "neb-onetaq-hot-start-m0484": {"primer_each_uM": [0.05, 1.0]},
    "neb-onetaq-hot-start-gc-m0485": {
        "primer_each_uM": [0.05, 1.0],
        "high_gc_enhancer_percent": [10.0, 20.0],
    },
    "neb-onetaq-hot-start-quickload-m0488": {"primer_each_uM": [0.05, 1.0]},
    "neb-onetaq-hot-start-quickload-gc-m0489": {
        "primer_each_uM": [0.05, 1.0],
        "high_gc_enhancer_percent": [10.0, 20.0],
    },
    "pcrbio-hs-taq-mix-pb10-22": {"primer_each_uM": [0.2, 0.6]},
    "qiagen-alltaq-master-mix-203144": {"primer_each_uM": [0.25, 0.25]},
    "thermo-platinum-ii-taq-hot-start": {"primer_each_uM": [0.2, 0.2]},
    "toyobo-kod-one-kmm101": {"primer_each_uM": [0.15, 0.5]},
    "neb-multiplex-pcr-m0284": {"primer_each_uM": [0.05, 0.4], "master_mix_x_final": [0.8, 1.5]},
    "neb-onetaq-hotstart-m0488-colony": {"initial_denaturation_time_min": [2.0, 5.0]},
    "pcrbio-hs-taq-pb10-22-colony": {"primer_each_uM": [0.2, 0.6]},
    "neb-onetaq-m0689-colony": {"primer_each_uM": [0.2, 0.2]},
    "thermo-dreamtaq-hot-start-ep170x": {"primer_each_uM": [0.1, 1.0]},
    "promega-gotaq-m300": {"primer_each_uM": [0.1, 1.0]},
    "bio-rad-itaq-sybr": {"primer_each_nM": [300.0, 500.0]},
    "neb-luna-universal-m3003": {"primer_each_nM": [100.0, 500.0]},
    "neb-luna-one-step-rt-qpcr-e3005": {"primer_each_nM": [100.0, 900.0]},
    "thermo-powerup-sybr-a2574x": {"primer_each_nM": [300.0, 800.0]},
    "thermo-powertrack-sybr-a46xxx": {"primer_each_nM": [300.0, 800.0]},
    "promega-gotaq-qpcr-a600x": {"primer_each_nM": [200.0, 1000.0]},
    "promega-gotaq-one-step-rt-qpcr-a6020": {"primer_each_nM": [50.0, 300.0]},
    "qiagen-quantinova-sybr-208052": {"primer_each_nM": [700.0, 700.0]},
    "bio-rad-ssoadvanced-sybr-172527x": {"primer_each_nM": [250.0, 500.0]},
    "solis-hot-firepol-evagreen-rox": {"primer_each_nM": [80.0, 250.0]},
    "solis-hot-firepol-evagreen-norox": {"primer_each_nM": [80.0, 250.0]},
    "neb-longamp-taq-m0323": {"primer_each_uM": [0.05, 1.0]},
    "neb-q5-xt-m2499": {"primer_each_uM": [0.15, 1.0]},
    "gbiosciences-rpa-786-2155": {
        "primer_each_nM": [500.0, 500.0],
        "hold_temperature_c": [37.0, 40.0],
        "hold_time_min": [20.0, 60.0],
    },
    "thermo-lyo-ready-rpa": {
        "primer_each_nM": [100.0, 300.0],
        "hold_temperature_c": [34.0, 45.0],
        "hold_time_min": [10.0, 25.0],
        "bst_polymerase_U_per_uL": [0.015, 0.15],
    },
}

# Explicit baselines for the products whose public protocol provides a stable,
# transferable starting recipe.  Existing registry records remain the richer
# prose/cycling authority; this table is the numeric projection used by Web and
# worker arithmetic.
FLANKING_NUMERIC_BASELINES: dict[str, dict[str, float]] = {
    "neb-taq-m0273": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.2,
        "magnesium_mM": 1.5,
        "dntp_each_mM": 0.2,
        "master_mix_x_final": 1.0,
    },
    "neb-q5-hot-start-m0493": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.5,
        "magnesium_mM": 2.0,
        "dntp_each_mM": 0.2,
    },
    "neb-q5u-hot-start-m0515": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.5,
        "magnesium_mM": 2.0,
        "dntp_each_mM": 0.2,
    },
    "thermo-dreamtaq-hot-start-ep170x": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.5,
        "magnesium_mM": 2.0,
        "dntp_each_mM": 0.2,
    },
    "thermo-phusion-plus": {"reaction_volume_uL": 50.0, "primer_each_uM": 0.5, "magnesium_mM": 1.7},
    "promega-gotaq-m300": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.5,
        "magnesium_mM": 1.5,
        "dntp_each_mM": 0.2,
        "polymerase_units": 1.25,
    },
    "thermo-platinum-superfi-ii": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.5,
        "magnesium_mM": 1.75,
    },
    "neb-onetaq-hot-start-m0484": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.2,
        "magnesium_mM": 1.8,
        "dntp_each_mM": 0.2,
    },
    "neb-onetaq-hot-start-gc-m0485": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.2,
        "magnesium_mM": 2.0,
        "dntp_each_mM": 0.2,
    },
    "neb-onetaq-hot-start-quickload-m0488": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.2,
        "magnesium_mM": 1.8,
        "dntp_each_mM": 0.2,
    },
    "neb-onetaq-hot-start-quickload-gc-m0489": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.2,
        "magnesium_mM": 2.0,
        "dntp_each_mM": 0.2,
    },
    "pcrbio-hs-taq-mix-pb10-22": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.4,
        "magnesium_mM": 3.0,
        "dntp_total_mM": 1.0,
    },
    "qiagen-alltaq-master-mix-203144": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 4.0,
        "primer_each_uM": 0.25,
    },
    "thermo-platinum-ii-taq-hot-start": {
        "reaction_volume_uL": 20.0,
        "buffer_x_final": 1.0,
        "buffer_stock_x": 5.0,
        "primer_each_uM": 0.2,
        "magnesium_mM": 1.5,
        "dntp_each_mM": 0.2,
        "polymerase_U_per_uL": 0.04,
    },
    "toyobo-kod-one-kmm101": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.3,
    },
    "neb-multiplex-pcr-m0284": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 5.0,
        "primer_each_uM": 0.15,
        "cycles": 35.0,
    },
    "neb-onetaq-m0482-colony": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.2,
        "initial_denaturation_temperature_c": 94.0,
        "initial_denaturation_time_min": 5.0,
        "cycles": 30.0,
    },
    "neb-onetaq-hotstart-m0488-colony": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.2,
        "initial_denaturation_temperature_c": 94.0,
        "cycles": 30.0,
    },
    "neb-insert-screening-e1202": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.3,
        "initial_denaturation_temperature_c": 94.0,
        "initial_denaturation_time_min": 2.0,
        "cycles": 30.0,
    },
    "pcrbio-hs-taq-pb10-22-colony": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.4,
        "initial_denaturation_temperature_c": 95.0,
        "initial_denaturation_time_min": 10.0,
        "cycles": 40.0,
    },
    "neb-onetaq-m0689-colony": {
        "reaction_volume_uL": 25.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.2,
        "initial_denaturation_temperature_c": 95.0,
        "initial_denaturation_time_min": 5.0,
        "cycles": 33.0,
    },
    "bio-rad-itaq-sybr": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 400.0,
    },
    "neb-luna-universal-m3003": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 250.0,
    },
    "neb-luna-one-step-rt-qpcr-e3005": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 400.0,
    },
    "thermo-powerup-sybr-a2574x": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 400.0,
        "cycles": 40.0,
    },
    # Yellow Sample Buffer is explicitly optional in MAN0018825; it is
    # therefore a conditional additive, not a PowerTrack product baseline.
    "thermo-powertrack-sybr-a46xxx": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 400.0,
        "cycles": 40.0,
    },
    "promega-gotaq-qpcr-a600x": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 200.0,
        "cycles": 40.0,
    },
    "promega-gotaq-one-step-rt-qpcr-a6020": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 200.0,
        "cycles": 40.0,
    },
    "qiagen-quantinova-sybr-208052": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 700.0,
    },
    "bio-rad-ssoadvanced-sybr-172527x": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_nM": 400.0,
    },
    "solis-hot-firepol-evagreen-rox": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 5.0,
        "primer_each_nM": 250.0,
    },
    "solis-hot-firepol-evagreen-norox": {
        "reaction_volume_uL": 20.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 5.0,
        "primer_each_nM": 250.0,
    },
    "solis-hot-firepol-evagreen-capillary": {"master_mix_x_final": 1.0, "master_mix_stock_x": 5.0},
    "vazyme-q713-suprealq-ultra-hunter-sybr": {"reaction_volume_uL": 20.0},
    "thermo-long-pcr-k018x": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.5,
        "magnesium_mM": 1.5,
        "dntp_each_mM": 0.2,
    },
    "neb-longamp-taq-m0323": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.4,
        "magnesium_mM": 2.0,
        "dntp_each_mM": 0.3,
        "polymerase_units": 5.0,
        "cycles": 30.0,
    },
    "takara-primestar-gxl-r050a-standard": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.25,
        "magnesium_mM": 1.0,
        "dntp_each_mM": 0.2,
        "polymerase_units": 1.25,
        "cycles": 30.0,
    },
    "qiagen-ultrarun-longrange-206442-206444": {
        "reaction_volume_uL": 20.0,
        "primer_each_uM": 0.5,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 4.0,
    },
    "neb-q5-xt-m2499": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.3,
        "magnesium_mM": 1.6,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
    },
    "promega-gotaq-long-m4021": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.2,
        "magnesium_mM": 2.5,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "extension_minutes_per_kb": 1.0,
    },
    "thermo-platinum-superfi-ii-longrange": {
        "reaction_volume_uL": 50.0,
        "primer_each_uM": 0.2,
        "magnesium_mM": 1.75,
    },
    "toyobo-kod-long-kml101": {
        "reaction_volume_uL": 50.0,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 2.0,
        "primer_each_uM": 0.15,
        "cycles": 30.0,
    },
    "twistamp-basic": {"reaction_volume_uL": 50.0, "primer_each_nM": 480.0},
    "twistamp-liquid-basic": {"reaction_volume_uL": 50.0, "primer_each_nM": 480.0},
    "gbiosciences-rpa-786-2155": {
        "reaction_volume_uL": 20.0,
        "primer_each_nM": 500.0,
        "magnesium_mM": 14.0,
        "enzyme_mix_x_final": 1.0,
        "enzyme_mix_stock_x": 5.0,
        "reaction_buffer_x_final": 1.0,
        "reaction_buffer_stock_x": 2.0,
        "hold_temperature_c": 37.0,
        "hold_time_min": 20.0,
    },
    "thermo-lyo-ready-rpa": {
        "reaction_volume_uL": 20.0,
        "primer_each_nM": 300.0,
        "magnesium_mM": 14.0,
        "dntp_each_mM": 0.2,
        "uvsx_mg_per_mL": 0.03,
        "uvsy_mg_per_mL": 0.03,
        "gene32_mg_per_mL": 0.4,
        "bst_polymerase_U_per_uL": 0.15,
        "hold_temperature_c": 42.0,
        "hold_time_min": 20.0,
    },
    "bio-rad-qx200-evagreen": {"reaction_volume_uL": 20.0, "primer_each_nM": 200.0},
    "bio-rad-qx700-naica-evagreen": {"reaction_volume_uL": 5.0},
    "qiagen-qiacuity-eg": {
        "primer_each_uM": 0.4,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 3.0,
        "cycles": 40.0,
    },
    "qiagen-qiacuity-onestep-advanced-eg": {
        "primer_each_uM": 0.75,
        "master_mix_x_final": 1.0,
        "master_mix_stock_x": 4.0,
        "cycles": 40.0,
    },
}

FLANKING_NUMERIC_CONDITIONAL_RULES: dict[str, list[dict[str, Any]]] = {
    "neb-onetaq-hot-start-gc-m0485": [
        {
            "id": "onetaq-gc-enhancer",
            "when": {"additive": "high-gc-enhancer"},
            "set": {"high_gc_enhancer_percent": 10.0},
            "authority": "NEB M0485 protocol; 10-20% reviewed range",
        },
    ],
    "neb-onetaq-hot-start-quickload-gc-m0489": [
        {
            "id": "onetaq-quickload-gc-enhancer",
            "when": {"additive": "high-gc-enhancer"},
            "set": {"high_gc_enhancer_percent": 10.0},
            "authority": "NEB M0489 protocol; 10-20% reviewed range",
        },
    ],
    "pcrbio-hs-taq-mix-pb10-22": [
        {
            "id": "pcrbio-colony-initial-denaturation",
            "when": {"preparation": "direct-colony"},
            "set": {
                "initial_denaturation_temperature_c": 95.0,
                "initial_denaturation_time_min": 10.0,
            },
            "authority": "PCRBIO PB10.22 colony-PCR protocol",
        },
    ],
    "pcrbio-hs-taq-pb10-22-colony": [
        {
            "id": "pcrbio-overnight-culture-input",
            "when": {"preparation": "liquid-culture"},
            "set": {"liquid_culture_input_uL": 5.0},
            "authority": "PCRBIO PB10.22 colony-PCR protocol",
        },
    ],
    "thermo-powertrack-sybr-a46xxx": [
        {
            "id": "powertrack-yellow-sample-buffer",
            "when": {"additive": "yellow-sample-buffer"},
            "set": {"yellow_sample_buffer_x_final": 1.0, "yellow_sample_buffer_stock_x": 40.0},
            "authority": "Thermo MAN0018825 Rev B.0 optional Yellow Sample Buffer; 40X stock to 1X final",
        },
        {
            "id": "powertrack-fast",
            "when": {"cycling_profile": "fast"},
            "set": {
                "activation_temperature_c": 95.0,
                "activation_time_min": 2.0,
                "denaturation_temperature_c": 95.0,
                "denaturation_time_sec": 5.0,
                "anneal_extend_temperature_c": 60.0,
                "anneal_extend_time_sec": 30.0,
            },
            "authority": "Thermo MAN0018825 Rev B.0 fast protocol",
        },
        {
            "id": "powertrack-standard",
            "when": {"cycling_profile": "standard"},
            "set": {
                "activation_temperature_c": 95.0,
                "activation_time_min": 2.0,
                "denaturation_temperature_c": 95.0,
                "denaturation_time_sec": 15.0,
                "anneal_extend_temperature_c": 60.0,
                "anneal_extend_time_sec": 60.0,
            },
            "authority": "Thermo MAN0018825 Rev B.0 standard protocol",
        },
    ],
    "thermo-lyo-ready-rpa": [
        {
            "id": "rpa-multiplex-primer-start",
            "when": {"multiplex": True},
            "set": {"primer_each_nM": 100.0},
            "authority": "Thermo MAN1000697 reviewed multiplex starting primer concentration",
        },
        {
            "id": "rpa-rna-components",
            "when": {"from_rna": True},
            "set": {
                "reverse_transcriptase_U_per_uL": 2.0,
                "rnase_inhibitor_U_per_uL": 1.6,
                "rnase_h_U_per_uL": 0.1,
            },
            "authority": "Thermo MAN1000697 RT-RPA component concentrations",
        },
    ],
    "toyobo-kod-long-kml101": [
        {
            "id": "kod-long-under-10kb",
            "when": {"target_length_class": "under-10kb"},
            "set": {"extension_seconds_per_kb": 5.0},
            "authority": "TOYOBO KOD Long KML-101 manual",
        },
        {
            "id": "kod-long-10kb-or-more",
            "when": {"target_length_class": "10kb-or-more"},
            "set": {"extension_seconds_per_kb": 10.0},
            "authority": "TOYOBO KOD Long KML-101 manual",
        },
    ],
    "qiagen-qiacuity-eg": [
        {
            "id": "qiacuity-eg-26k",
            "when": {"partition_format_detail": "26k"},
            "set": {"reaction_volume_uL": 40.0},
            "authority": "QIAGEN QIAcuity EG protocol Nanoplate format",
        },
        {
            "id": "qiacuity-eg-8.5k",
            "when": {"partition_format_detail": "8.5k"},
            "set": {"reaction_volume_uL": 12.0},
            "authority": "QIAGEN QIAcuity EG protocol Nanoplate format",
        },
    ],
    "qiagen-qiacuity-onestep-advanced-eg": [
        {
            "id": "qiacuity-onestep-eg-26k",
            "when": {"partition_format_detail": "26k"},
            "set": {"reaction_volume_uL": 40.0},
            "authority": "QIAGEN QIAcuity OneStep Advanced EvaGreen protocol",
        },
        {
            "id": "qiacuity-onestep-eg-8.5k",
            "when": {"partition_format_detail": "8.5k"},
            "set": {"reaction_volume_uL": 12.0},
            "authority": "QIAGEN QIAcuity OneStep Advanced EvaGreen protocol",
        },
    ],
}

FLANKING_UNRESOLVED_NUMERIC_DEPENDENCIES: dict[str, list[dict[str, str]]] = {
    "vazyme-q713-suprealq-ultra-hunter-sybr": [
        {
            "id": "q713-exact-product-recipe",
            "note": "The current vendor page establishes a 20 uL catalogue reaction basis, SYBR Green I readout, dUTP/heat-labile UDG and included passive-reference dye, but this release does not invent primer concentration or master-mix stoichiometry without a transferable current IFU.",
        },
    ],
    "solis-hot-firepol-evagreen-capillary": [
        {
            "id": "solis-capillary-exact-reaction",
            "note": "The current catalogue establishes the dedicated capillary formulation, but this runtime snapshot does not promote a product-specific reaction volume/primer value without its exact IFU. Confirm the current capillary IFU before bench execution.",
        },
    ],
    "promega-gotaq-long-m4021": [],
    "bio-rad-qx700-evagreen-supermix": [
        {
            "id": "qx700-evagreen-exact-reaction",
            "note": "The dedicated QX700 EvaGreen chemistry is recognized; retain the current vendor/application protocol for exact loading and cycling rather than inventing values from another QX platform.",
        },
    ],
    "bio-rad-qx700-naica-evagreen": [
        {
            "id": "qx700-naica-assay-program",
            "note": "QX700/naica dye workflow requires assay-specific validated PCR-program and loading authority; a universal numeric programme is not inferred.",
        },
    ],
    "twistamp-basic": [
        {
            "id": "twistamp-basic-complete-public-formulation",
            "note": "Primer concentration is source-backed, but proprietary pellet/reagent composition is not reconstructed into invented concentrations.",
        },
    ],
}

# Publicly selectable aliases/lifecycle metadata. Package-size SKUs are aliases,
# not distinct chemistry identities when the formulation is unchanged.
FLANKING_PROTOCOL_METADATA: dict[str, dict[str, Any]] = {
    "neb-onetaq-hot-start-m0484": {
        "module": "standard-pcr",
        "label": "NEB OneTaq Hot Start 2X Master Mix · Standard Buffer · M0484",
        "vendor": "NEB",
        "status": "current",
        "source": "NEB M0484 protocol/product page",
    },
    "neb-onetaq-hot-start-gc-m0485": {
        "module": "standard-pcr",
        "label": "NEB OneTaq Hot Start 2X Master Mix · GC Buffer · M0485",
        "vendor": "NEB",
        "status": "current",
        "source": "NEB M0485 protocol/product page",
    },
    "neb-onetaq-hot-start-quickload-m0488": {
        "module": "standard-pcr",
        "label": "NEB OneTaq Hot Start Quick-Load 2X · Standard Buffer · M0488",
        "vendor": "NEB",
        "status": "current",
        "source": "NEB M0488 protocol",
    },
    "neb-onetaq-hot-start-quickload-gc-m0489": {
        "module": "standard-pcr",
        "label": "NEB OneTaq Hot Start Quick-Load 2X · GC Buffer · M0489",
        "vendor": "NEB",
        "status": "current-partial-sku",
        "source": "NEB M0489 protocol/product page",
    },
    "pcrbio-hs-taq-mix-pb10-22": {
        "module": "standard-pcr",
        "label": "PCR Biosystems PCRBIO HS Taq Mix · PB10.22",
        "vendor": "PCR Biosystems",
        "status": "current",
        "source": "PCRBIO PB10.22 manual",
    },
    "neb-onetaq-m0482-colony": {
        "module": "colony-pcr",
        "label": "NEB OneTaq M0482 · colony PCR",
        "vendor": "NEB",
        "status": "current",
        "source": "NEB M0482 current protocol",
    },
    "neb-onetaq-hotstart-m0488-colony": {
        "module": "colony-pcr",
        "label": "NEB OneTaq Hot Start Quick-Load M0488 · colony PCR",
        "vendor": "NEB",
        "status": "current",
        "source": "NEB M0488 current protocol",
    },
    "neb-insert-screening-e1202": {
        "module": "colony-pcr",
        "label": "NEB Insert Screening E1202 · colony PCR",
        "vendor": "NEB",
        "status": "current",
        "source": "NEB E1202 insert-screening protocol",
    },
    "pcrbio-hs-taq-pb10-22-colony": {
        "module": "colony-pcr",
        "label": "PCRBIO HS Taq PB10.22 · colony PCR",
        "vendor": "PCR Biosystems",
        "status": "current",
        "source": "PCRBIO PB10.22 manual v2.0",
    },
    "thermo-powertrack-sybr-a46xxx": {
        "module": "qpcr-sybr",
        "label": "Applied Biosystems PowerTrack SYBR Green Master Mix · A46012/A46109-A46113",
        "vendor": "Thermo Fisher Scientific",
        "status": "current",
        "source": "MAN0018825 Rev B.0",
    },
    "toyobo-kod-long-kml101": {
        "module": "long-range-pcr",
        "label": "TOYOBO KOD Long PCR Master Mix · KML-101",
        "vendor": "TOYOBO",
        "status": "current",
        "source": "KOD Long KML-101 manual/product page",
    },
    "qiagen-alltaq-master-mix-203144": {
        "module": "standard-pcr",
        "label": "QIAGEN AllTaq Master Mix · 203144 family",
        "vendor": "QIAGEN",
        "status": "current",
        "source": "AllTaq handbook/quick-start",
        "source_url": "https://go.qiagen.com/AllTaq",
    },
    "thermo-platinum-ii-taq-hot-start": {
        "module": "standard-pcr",
        "label": "Thermo Fisher Platinum II Taq Hot-Start",
        "vendor": "Thermo Fisher Scientific",
        "status": "current",
        "source": "Platinum II technical protocol",
        "source_url": "https://assets.thermofisher.com/TFS-Assets/BID/Application-Notes/amplify-dna-targets-dna-polymerase-app-note.pdf",
    },
    "toyobo-kod-one-kmm101": {
        "module": "standard-pcr",
        "label": "TOYOBO KOD One PCR Master Mix · KMM-101",
        "vendor": "TOYOBO",
        "status": "current",
        "source": "KMM-101_201",
        "source_url": "https://www.toyobo-global.com/sites/default/static_root/products/lifescience/support/manual/KMM-101_201.pdf",
    },
    "neb-multiplex-pcr-m0284": {
        "module": "standard-pcr",
        "label": "NEB Multiplex PCR 5X Master Mix · M0284",
        "vendor": "NEB",
        "status": "current",
        "source": "NEB M0284 protocol",
        "source_url": "https://www.neb.com/en-us/products/m0284-multiplex-pcr-5x-master-mix",
    },
    "neb-onetaq-m0689-colony": {
        "module": "colony-pcr",
        "label": "NEB M0689 supplemental colony-PCR protocol · OneTaq Hot Start Quick-Load",
        "vendor": "NEB",
        "status": "current",
        "source": "NEB M0689 Supplemental Protocol 2",
        "source_url": "https://www.neb.com/en-us/protocols/supplemental-protocol-2-using-colony-pcr-to-identify-positive-clones-neb-m0689",
    },
    "qiagen-quantinova-sybr-208052": {
        "module": "qpcr-sybr",
        "label": "QIAGEN QuantiNova SYBR Green PCR Kit · 208052 family",
        "vendor": "QIAGEN",
        "status": "current",
        "source": "QuantiNova SYBR Green PCR Handbook",
        "source_url": "https://www.qiagen.com/en-US/resources/download/KitHandbook/quantinova-sybr-green-pcr-handbook",
    },
    "bio-rad-ssoadvanced-sybr-172527x": {
        "module": "qpcr-sybr",
        "label": "Bio-Rad SsoAdvanced Universal SYBR Green Supermix · 172527x",
        "vendor": "Bio-Rad",
        "status": "current",
        "source": "Bio-Rad instruction manual",
    },
    "solis-hot-firepol-evagreen-rox": {
        "module": "qpcr-sybr",
        "label": "Solis BioDyne HOT FIREPol EvaGreen qPCR Mix Plus · ROX",
        "vendor": "Solis BioDyne",
        "status": "current",
        "source": "DS-08-24 v3",
        "source_url": "https://solisbiodyne.com/pics/9799_DS-08-24_v3_HOT_FIREPol_EvaGreen_qPCR_Mix_Plus_ROX_revised_12.04.2022.pdf",
    },
    "solis-hot-firepol-evagreen-norox": {
        "module": "qpcr-sybr",
        "label": "Solis BioDyne HOT FIREPol EvaGreen qPCR Mix Plus · no ROX",
        "vendor": "Solis BioDyne",
        "status": "current",
        "source": "Solis current product catalogue",
    },
    "solis-hot-firepol-evagreen-capillary": {
        "module": "qpcr-sybr",
        "label": "Solis BioDyne HOT FIREPol EvaGreen qPCR Mix Plus · capillary",
        "vendor": "Solis BioDyne",
        "status": "current-source-limited",
        "source": "Solis current product catalogue",
    },
    "vazyme-q713-suprealq-ultra-hunter-sybr": {
        "module": "qpcr-sybr",
        "label": "Vazyme SupRealQ Ultra Hunter SYBR qPCR Master Mix (U+) · Q713",
        "vendor": "Vazyme",
        "status": "current-source-limited",
        "source": "Vazyme Global Q713 current product page",
        "source_url": "https://www.vazymeglobal.com/product-center/dye-based-qpcr/suprealq-ultra-hunter-sybr-qpcr-master-mix-u",
    },
    "gbiosciences-rpa-786-2155": {
        "module": "rpa",
        "label": "G-Biosciences RPA Kit · 786-2155",
        "vendor": "G-Biosciences",
        "status": "current",
        "source": "G-Biosciences RPA Kit protocol",
        "source_url": "https://www.gbiosciences.com/Recombinase-Polymerase-Amplification-RPA-Kit",
    },
}


def _first_number(value: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
                return float(candidate)
    return None


def _registry_record(
    protocol_id: str, module_id: str, *, from_rna: bool = False
) -> dict[str, Any] | None:
    if module_id == "standard-pcr":
        return standard_pcr_protocol(protocol_id, assay_id=module_id)
    if module_id == "qpcr-sybr":
        return qpcr_protocol(protocol_id, assay_id=module_id, from_rna=from_rna)
    if module_id == "long-range-pcr":
        return long_range_protocol(protocol_id, assay_id=module_id)
    if module_id == "rpa":
        return rpa_protocol(protocol_id, assay_id=module_id, from_rna=from_rna)
    if module_id == "digital-pcr":
        return digital_protocol(protocol_id, assay_id=module_id, from_rna=from_rna)
    if module_id == "colony-pcr":
        return deepcopy(COLONY_PROTOCOL_RECORDS.get(protocol_id))
    return None


def _derive_recipe_volumes(values: dict[str, float], origins: dict[str, str]) -> None:
    reaction = values.get("reaction_volume_uL")
    if not reaction or reaction <= 0:
        return
    if values.get("master_mix_stock_x") and values.get("master_mix_x_final") is not None:
        values["master_mix_uL"] = (
            reaction * values["master_mix_x_final"] / values["master_mix_stock_x"]
        )
        origins["master_mix_uL"] = "derived-stoichiometry"
    if (
        values.get("yellow_sample_buffer_stock_x")
        and values.get("yellow_sample_buffer_x_final") is not None
    ):
        values["yellow_sample_buffer_uL"] = (
            reaction
            * values["yellow_sample_buffer_x_final"]
            / values["yellow_sample_buffer_stock_x"]
        )
        origins["yellow_sample_buffer_uL"] = "derived-stoichiometry"


def resolve_numeric_recipe(
    protocol_id: str,
    module_id: str,
    scenario: dict[str, Any] | None = None,
    overrides: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Resolve one exact Flanking bench recipe without changing sequence ranking."""
    scenario = dict(scenario or {})
    additive = scenario.get("additive")
    if additive not in (None, "", "none", "high-gc-enhancer", "yellow-sample-buffer"):
        raise ValueError(f"Unsupported Flanking numeric additive: {additive!r}")
    if additive == "high-gc-enhancer" and protocol_id not in {
        "neb-onetaq-hot-start-gc-m0485",
        "neb-onetaq-hot-start-quickload-gc-m0489",
    }:
        raise ValueError(
            "NEB High GC Enhancer is only source-backed for the reviewed OneTaq GC formulations."
        )
    if additive == "yellow-sample-buffer" and protocol_id != "thermo-powertrack-sybr-a46xxx":
        raise ValueError(
            "Yellow Sample Buffer is only source-backed in this catalogue for PowerTrack SYBR."
        )
    if not protocol_id or protocol_id == "not-selected":
        return {
            "schema_version": FLANKING_NUMERIC_SCHEMA_VERSION,
            "module": module_id,
            "protocol": "not-selected",
            "values": {},
            "origins": {},
            "ranges": {},
            "applied_overlays": [],
            "unresolved_numeric_dependencies": [],
            "warnings": [],
            "dependency_axes": list(FLANKING_NUMERIC_DEPENDENCY_AXES),
            "sequence_decision_impact": "none",
        }

    # Enforce protocol/module ownership by resolving the registry record where
    # one exists. New records are added to that registry before entering runtime.
    _registry_record(protocol_id, module_id, from_rna=bool(scenario.get("from_rna")))

    baseline = deepcopy(FLANKING_NUMERIC_BASELINES.get(protocol_id, {}))
    generic = resolve_generic_numeric_recipe(
        baseline=baseline,
        overlays=FLANKING_NUMERIC_CONDITIONAL_RULES.get(protocol_id, ()),
        ranges=FLANKING_NUMERIC_OPTIMIZATION_ENVELOPES.get(protocol_id, {}),
        scenario=scenario,
        overrides=overrides,
        subject=protocol_id,
    )
    values = generic.values
    origins = generic.origins

    if protocol_id == "neb-onetaq-hotstart-m0488-colony":
        denat = scenario.get("initial_denaturation_time_min")
        if denat is None:
            generic.ranges["initial_denaturation_time_min"] = [2.0, 5.0]
        else:
            denat_f = float(denat)
            if not 2.0 <= denat_f <= 5.0:
                raise ValueError(
                    "M0488 colony initial_denaturation_time_min must remain within the reviewed 2-5 minute range."
                )
            values["initial_denaturation_time_min"] = denat_f
            origins["initial_denaturation_time_min"] = "user-override-within-source-bound"

    # Reaction volume is a context choice only when the exact product publishes
    # that format. We intentionally do not accept arbitrary scaling of every kit.
    requested_volume = scenario.get("reaction_volume_uL")
    if requested_volume is not None:
        requested = float(requested_volume)
        allowed: set[float] = set()
        record = _registry_record(protocol_id, module_id, from_rna=bool(scenario.get("from_rna")))
        rv = (record or {}).get("reaction_volume_uL")
        if isinstance(rv, (int, float)):
            allowed.add(float(rv))
        elif isinstance(rv, dict):
            allowed.update(
                float(v)
                for v in rv.values()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            )
        # Public master-mix protocols added in this release explicitly support
        # the stated formats even if their richer registry record is compact.
        if protocol_id in {
            "neb-onetaq-hot-start-m0484",
            "neb-onetaq-hot-start-gc-m0485",
            "neb-onetaq-hot-start-quickload-m0488",
            "neb-onetaq-hot-start-quickload-gc-m0489",
        }:
            allowed.update({25.0, 50.0})
        if protocol_id == "thermo-powertrack-sybr-a46xxx":
            allowed.update({10.0, 20.0})
        if allowed and requested not in allowed:
            raise ValueError(
                f"reaction_volume_uL={requested:g} is not one of the reviewed exact-product formats {sorted(allowed)} for {protocol_id}."
            )
        if not allowed:
            raise ValueError(
                f"No transferable reaction-volume choices are published in the current numeric authority for {protocol_id}."
            )
        values["reaction_volume_uL"] = requested
        origins["reaction_volume_uL"] = "user-override-within-source-bound"

    _derive_recipe_volumes(values, origins)

    # Instrument/reference-dye context is a first-class qPCR dependency.
    qpcr_profile = str(scenario.get("qpcr_instrument_profile") or "").strip()
    if protocol_id == "qiagen-quantinova-sybr-208052":
        if qpcr_profile == "high-rox":
            values["rox_working_dilution_x"] = 20.0
            origins["rox_working_dilution_x"] = "automatic:quantinova-high-rox-instrument-profile"
        elif qpcr_profile == "low-rox":
            values["rox_working_dilution_x"] = 200.0
            origins["rox_working_dilution_x"] = "automatic:quantinova-low-rox-instrument-profile"
        elif qpcr_profile in {"no-rox", "capillary"}:
            origins["rox_reference_dye"] = "automatic:not-added-for-selected-instrument-profile"
        elif qpcr_profile:
            raise ValueError(
                "QuantiNova qpcr_instrument_profile must be high-rox, low-rox, no-rox, or capillary."
            )
    if protocol_id == "solis-hot-firepol-evagreen-rox" and qpcr_profile not in {
        "high-rox",
        "low-rox",
        "rox-compatible",
    }:
        if qpcr_profile:
            raise ValueError(
                "The Solis ROX formulation requires a ROX-compatible instrument profile."
            )
    if protocol_id == "solis-hot-firepol-evagreen-norox" and qpcr_profile not in {"no-rox", ""}:
        raise ValueError("The Solis no-ROX formulation requires the no-rox instrument profile.")
    if protocol_id == "solis-hot-firepol-evagreen-capillary" and qpcr_profile not in {
        "capillary",
        "",
    }:
        raise ValueError(
            "The Solis capillary formulation requires the capillary instrument profile."
        )

    # PowerTrack DNA fraction has a source-backed 10-20% recommendation in the
    # standard setup. Keep it a range; only resolve a value when the user records it.
    if protocol_id == "thermo-powertrack-sybr-a46xxx":
        generic.ranges["template_fraction_percent"] = [10.0, 20.0]
        fraction = scenario.get("template_fraction_percent")
        if fraction is not None:
            fraction_f = float(fraction)
            if not 10.0 <= fraction_f <= 20.0:
                raise ValueError(
                    "PowerTrack template_fraction_percent must remain within the reviewed 10-20% setup range."
                )
            values["template_fraction_percent"] = fraction_f
            origins["template_fraction_percent"] = "user-override-within-source-bound"

    if protocol_id == "gbiosciences-rpa-786-2155":
        for recipe_key, scenario_key, low, high in (
            ("hold_temperature_c", "temperature_c", 37.0, 40.0),
            ("hold_time_min", "time_min", 20.0, 60.0),
        ):
            raw = scenario.get(scenario_key)
            if raw is not None:
                numeric = float(raw)
                if not low <= numeric <= high:
                    raise ValueError(
                        f"G-Biosciences RPA {scenario_key} must remain within {low:g}-{high:g}."
                    )
                values[recipe_key] = numeric
                origins[recipe_key] = "user-override-within-source-bound"

    # Thermo Lyo-ready RPA publishes bounded reaction-condition windows.
    # These are bench-only overrides; they never alter candidate ranking.
    if protocol_id == "thermo-lyo-ready-rpa":
        rpa_overrides = {
            "hold_temperature_c": ("temperature_c", 34.0, 45.0),
            "hold_time_min": ("time_min", 10.0, 25.0),
            "bst_polymerase_U_per_uL": ("bst_units_per_uL", 0.015, 0.15),
        }
        for recipe_key, (scenario_key, low, high) in rpa_overrides.items():
            raw = scenario.get(scenario_key)
            if raw is None:
                continue
            numeric = float(raw)
            if not low <= numeric <= high:
                raise ValueError(
                    f"Thermo Lyo-ready RPA {scenario_key} must remain within the reviewed {low:g}-{high:g} range."
                )
            values[recipe_key] = numeric
            origins[recipe_key] = "user-override-within-source-bound"

    if protocol_id == "promega-gotaq-long-m4021" and scenario.get("target_length_kb") is not None:
        kb = float(scenario["target_length_kb"])
        template_class = str(scenario.get("template_class") or "").strip()
        ceiling = (
            30.0
            if template_class in {"genomic", "hmw-genomic"}
            else 40.0
            if template_class in {"plasmid", "lambda", "lower-complexity"}
            else 30.0
        )
        if not 5.0 <= kb <= ceiling:
            raise ValueError(
                f"GoTaq Long target_length_kb must remain within 5-{ceiling:g} kb for the selected template class."
            )
        values["target_length_kb"] = kb
        values["extension_minutes_per_kb"] = 1.0
        values["extension_time_min"] = kb
        origins["target_length_kb"] = "user-reviewed-context"
        origins["extension_time_min"] = "derived-stoichiometry"
        if kb > 15.0 and not bool(scenario.get("hmw_template_verified")):
            generic.warnings.append(
                "GoTaq Long targets >15 kb depend strongly on intact high-molecular-weight template DNA; record HMW template verification before treating the bench plan as qualified."
            )

    # KOD Long derives total extension time only from an explicit target length
    # and a source-backed length regime; it never guesses the target length.
    if protocol_id == "toyobo-kod-long-kml101" and scenario.get("target_length_kb") is not None:
        kb = float(scenario["target_length_kb"])
        if not 0 < kb <= 50.0:
            raise ValueError(
                "KOD Long target_length_kb must be >0 and <=50 kb in this source-backed branch."
            )
        sec_per_kb = 5.0 if kb < 10.0 else 10.0
        values["target_length_kb"] = kb
        values["extension_seconds_per_kb"] = sec_per_kb
        values["extension_time_sec"] = kb * sec_per_kb
        origins["target_length_kb"] = "user-reviewed-context"
        origins["extension_seconds_per_kb"] = "automatic:kod-long-length-regime"
        origins["extension_time_sec"] = "derived-stoichiometry"

    unresolved = deepcopy(FLANKING_UNRESOLVED_NUMERIC_DEPENDENCIES.get(protocol_id, []))
    if (
        protocol_id
        in {
            "qiagen-quantinova-sybr-208052",
            "solis-hot-firepol-evagreen-rox",
            "solis-hot-firepol-evagreen-norox",
            "solis-hot-firepol-evagreen-capillary",
        }
        and not qpcr_profile
    ):
        unresolved.append(
            {
                "id": "qpcr-instrument-profile",
                "note": "Choose the instrument/reference-dye profile so PCRStudio can verify ROX/no-ROX/capillary compatibility without guessing from the kit name.",
            }
        )
    if protocol_id == "promega-gotaq-long-m4021" and scenario.get("target_length_kb") is None:
        unresolved.append(
            {
                "id": "gotaq-long-target-length",
                "note": "Record target length; the exact extension time is source-conditioned at approximately 1 minute/kb.",
            }
        )
    if protocol_id == "promega-gotaq-long-m4021" and not scenario.get("template_class"):
        unresolved.append(
            {
                "id": "gotaq-long-template-class",
                "note": "Record genomic/HMW-genomic versus plasmid/lambda/lower-complexity template class because the documented reach differs (30 kb versus 40 kb).",
            }
        )
    if (
        protocol_id == "neb-onetaq-hotstart-m0488-colony"
        and scenario.get("initial_denaturation_time_min") is None
    ):
        unresolved.append(
            {
                "id": "m0488-colony-lysis-time",
                "note": "Choose a source-backed 2-5 minute initial denaturation/lysis time for the M0488 colony-PCR branch; PCRStudio does not select one endpoint silently.",
            }
        )
    if protocol_id == "thermo-powertrack-sybr-a46xxx" and scenario.get("cycling_profile") not in {
        "fast",
        "standard",
    }:
        unresolved.append(
            {
                "id": "powertrack-cycling-profile",
                "note": "Choose the source-backed fast or standard cycling branch; PCRStudio does not invent one.",
            }
        )
    if protocol_id == "toyobo-kod-long-kml101" and scenario.get("target_length_kb") is None:
        unresolved.append(
            {
                "id": "kod-long-target-length",
                "note": "Target length is required to resolve the source-backed 5 s/kb versus 10 s/kb extension branch.",
            }
        )
    if protocol_id in {
        "qiagen-qiacuity-eg",
        "qiagen-qiacuity-onestep-advanced-eg",
    } and scenario.get("partition_format_detail") not in {"8.5k", "26k"}:
        unresolved.append(
            {
                "id": "qiacuity-nanoplate-format",
                "note": "Choose 8.5k or 26k Nanoplate format before PCRStudio resolves reaction volume.",
            }
        )
    return {
        "schema_version": FLANKING_NUMERIC_SCHEMA_VERSION,
        "module": module_id,
        "protocol": protocol_id,
        "values": values,
        "origins": origins,
        "ranges": generic.ranges,
        "applied_overlays": [row["id"] for row in generic.applied_overlays],
        "unresolved_numeric_dependencies": unresolved,
        "warnings": generic.warnings,
        "dependency_axes": list(FLANKING_NUMERIC_DEPENDENCY_AXES),
        "sequence_decision_impact": "none",
    }


def _metadata_for_existing() -> dict[str, dict[str, Any]]:
    rows = deepcopy(FLANKING_PROTOCOL_METADATA)
    groups = (
        ("standard-pcr", STANDARD_PCR_PROTOCOLS, standard_pcr_protocol),
        ("qpcr-sybr", QPCR_PROTOCOLS, qpcr_protocol),
        ("long-range-pcr", LONG_RANGE_PROTOCOLS, long_range_protocol),
        ("digital-pcr", DIGITAL_PROTOCOLS, digital_protocol),
    )
    for module_id, ids, func in groups:
        for protocol_id in ids:
            if protocol_id == "not-selected" or protocol_id in rows:
                continue
            try:
                if module_id in {"qpcr-sybr", "digital-pcr"}:
                    record = func(
                        protocol_id,
                        assay_id=module_id,
                        from_rna=protocol_id
                        in {
                            "neb-luna-one-step-rt-qpcr-e3005",
                            "promega-gotaq-one-step-rt-qpcr-a6020",
                            "qiagen-qiacuity-onestep-advanced-eg",
                        },
                    )
                else:
                    record = func(protocol_id, assay_id=module_id)
            except ValueError:
                continue
            lifecycle = (record or {}).get("lifecycle") or {}
            rows[protocol_id] = {
                "module": module_id,
                "label": str((record or {}).get("selection") or protocol_id),
                "vendor": str((record or {}).get("selection") or protocol_id).split(" ", 1)[0],
                "status": str(lifecycle.get("status") or "reviewed"),
                "source": str(
                    (record or {}).get("source_publication") or "reviewed registry authority"
                ),
                "source_url": str((record or {}).get("source_url") or ""),
                "source_revision": str((record or {}).get("source_revision") or ""),
            }
    for protocol_id in COLONY_PROTOCOLS:
        if protocol_id == "custom-sop" or protocol_id in rows:
            continue
        record = COLONY_PROTOCOL_RECORDS.get(protocol_id)
        if record:
            rows[protocol_id] = {
                "module": "colony-pcr",
                "label": str(record.get("selection") or protocol_id),
                "vendor": "PCR Biosystems" if protocol_id.startswith("pcrbio") else "NEB",
                "status": "current",
                "source": str(record.get("source_publication") or "reviewed colony protocol"),
                "source_url": str(record.get("source_url") or ""),
                "source_revision": str(record.get("source_revision") or ""),
            }
    for protocol_id in RPA_PROTOCOLS:
        if protocol_id == "not-selected" or protocol_id in rows:
            continue
        executable = protocol_id in {
            "twistamp-basic",
            "twistamp-liquid-basic",
            "thermo-lyo-ready-rpa",
            "gbiosciences-rpa-786-2155",
        }
        human = {
            "twistamp-basic": "TwistDx TwistAmp Basic",
            "twistamp-liquid-basic": "TwistDx TwistAmp Liquid Basic",
            "thermo-lyo-ready-rpa": "Invitrogen Lyo-ready RPA Kit · A72127/A72128",
            "gbiosciences-rpa-786-2155": "G-Biosciences RPA Kit · 786-2155",
            "twistamp-exo": "TwistDx TwistAmp Exo · recognized, non-executable",
            "twistamp-nfo": "TwistDx TwistAmp Nfo · recognized, non-executable",
            "twistamp-fpg": "TwistDx TwistAmp Fpg · recognized, non-executable",
            "siba-reference": "SIBA reference branch · recognized, non-executable",
        }.get(protocol_id, protocol_id)
        rows[protocol_id] = {
            "module": "rpa",
            "label": human,
            "vendor": "TwistDx"
            if protocol_id.startswith("twistamp")
            else "Thermo Fisher"
            if protocol_id.startswith("thermo")
            else "G-Biosciences"
            if protocol_id.startswith("gbiosciences")
            else "reference",
            "status": "executable" if executable else "recognized-non-executable",
            "source": "reviewed RPA registry authority",
        }
    for protocol_id, meta in rows.items():
        provenance = PROTOCOL_PROVENANCE.get(protocol_id)
        if not provenance:
            continue
        meta["source_url"] = str(provenance["url"])
        meta["source_reviewed_date"] = str(provenance["reviewed_date"])
        meta["source_snapshot_status"] = str(provenance["snapshot_status"])
        meta["source_snapshot_registry"] = str(provenance.get("snapshot_registry") or "")
        meta["source_claim_snapshot_sha256"] = str(provenance.get("claim_snapshot_sha256") or "")
        meta["source_availability_scope"] = str(provenance["availability_scope"])
        meta["source_kind"] = str(provenance["kind"])
    return rows


def _reaction_volume_options() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for protocol_id, meta in _metadata_for_existing().items():
        module_id = str(meta.get("module") or "")
        values: set[float] = set()
        try:
            record = _registry_record(
                protocol_id,
                module_id,
                from_rna=protocol_id
                in {
                    "neb-luna-one-step-rt-qpcr-e3005",
                    "promega-gotaq-one-step-rt-qpcr-a6020",
                    "qiagen-qiacuity-onestep-advanced-eg",
                },
            )
        except ValueError:
            record = None
        rv = (record or {}).get("reaction_volume_uL")
        if isinstance(rv, (int, float)) and not isinstance(rv, bool):
            values.add(float(rv))
        elif isinstance(rv, dict):
            values.update(
                float(v)
                for v in rv.values()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            )
        if protocol_id in {
            "neb-onetaq-hot-start-m0484",
            "neb-onetaq-hot-start-gc-m0485",
            "neb-onetaq-hot-start-quickload-m0488",
            "neb-onetaq-hot-start-quickload-gc-m0489",
        }:
            values.update({25.0, 50.0})
        if protocol_id == "thermo-powertrack-sybr-a46xxx":
            values.update({10.0, 20.0})
        if protocol_id == "thermo-lyo-ready-rpa":
            values.update({20.0, 50.0})
        if protocol_id in {"qiagen-qiacuity-eg", "qiagen-qiacuity-onestep-advanced-eg"}:
            values.update({12.0, 40.0})
        if values:
            out[protocol_id] = sorted(values)
    return out


def generated_catalogue() -> dict[str, Any]:
    return {
        "schema_version": FLANKING_NUMERIC_SCHEMA_VERSION,
        "baselines": FLANKING_NUMERIC_BASELINES,
        "conditional_rules": FLANKING_NUMERIC_CONDITIONAL_RULES,
        "optimization_envelopes": FLANKING_NUMERIC_OPTIMIZATION_ENVELOPES,
        "unresolved_numeric_dependencies": FLANKING_UNRESOLVED_NUMERIC_DEPENDENCIES,
        "dependency_axes": FLANKING_NUMERIC_DEPENDENCY_AXES,
        "protocol_metadata": _metadata_for_existing(),
        "reaction_volume_options": _reaction_volume_options(),
    }
