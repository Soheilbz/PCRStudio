"""Source-scoped conditional numeric reaction resolver for LAMP/RT-LAMP.

The resolver is deliberately separate from sequence ranking. It answers a
narrow question: given an exact reviewed product/protocol plus an explicit
bench scenario, which numerical reaction values are publicly supported?
Missing public amounts remain unresolved. No value in this module is allowed
to change primer sequence ranking (`sequence_decision_impact = none`).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .numeric_recipe import Quantity, dilution_volume
from .numeric_recipe.resolver import resolve as resolve_generic_numeric_recipe
from .registries.lamp import (
    LAMP_ACCELERATION_ADDITIVES,
    LAMP_CARRYOVER_STRATEGIES,
    LAMP_INSTRUMENT_PROFILES,
    LAMP_PREINCUBATION_STRATEGIES,
    LAMP_PRIMER_KINETICS_PROFILES,
    LAMP_PROTOCOL_REGISTRY,
    LAMP_RECONSTITUTION_OPTIONS,
    LAMP_SAMPLE_BUFFER_TYPES,
    LAMP_SPECIFICITY_ADDITIVES,
)

__all__ = [
    "LAMP_ACCELERATION_ADDITIVES",
    "LAMP_CARRYOVER_STRATEGIES",
    "LAMP_INSTRUMENT_PROFILES",
    "LAMP_NUMERIC_OPTIMIZATION_ENVELOPES",
    "LAMP_PREINCUBATION_STRATEGIES",
    "LAMP_PRIMER_KINETICS_PROFILES",
    "LAMP_RECONSTITUTION_OPTIONS",
    "LAMP_SAMPLE_BUFFER_TYPES",
    "LAMP_SPECIFICITY_ADDITIVES",
    "resolve_numeric_recipe",
]

LAMP_NUMERIC_SCHEMA_VERSION = "1.2.0"

# Source-scoped public limits that are easy to accidentally turn into magic
# numbers. Keeping them named lets the provenance generator and static audit
# fingerprint them independently.
NEB_PH_COLORIMETRIC_REVIEWED_SAMPLE_PH = (7.0, 8.5)
NEB_PH_COLORIMETRIC_CONSERVATIVE_BUFFER_PERCENT_MAX = 10.0
NEB_PH_COLORIMETRIC_TE_CAUTION_PERCENT_MAX = 20.0
NEB_PH_COLORIMETRIC_GUANIDINE_TOTAL_MM_MAX = 60.0

# Only genuinely reviewed public optimization envelopes belong here. A fixed
# baseline is not an optimization range. Legacy ranges for MDX126 and RR385 were
# intentionally removed because the exact-product manuals do not publish those
# generic envelopes.
LAMP_NUMERIC_OPTIMIZATION_ENVELOPES: dict[str, dict[str, list[float]]] = {
    "neb-m9204": {
        "magnesium_mM": [6.0, 8.0],
        "polymerase_units": [8.0, 15.0],
        "hold_temperature_c": [50.0, 70.0],
        "fluorescent_dye_x": [0.1, 1.0],
    },
    "neb-m9205": {
        "magnesium_mM": [6.0, 8.0],
        "polymerase_units": [8.0, 15.0],
        "hold_temperature_c": [50.0, 70.0],
        "fluorescent_dye_x": [0.1, 1.0],
    },
    "thermo-a56656": {
        "polymerase_units": [1.0, 6.0],
        "hold_temperature_c": [35.0, 75.0],
    },
    "vazyme-rp711": {
        "hold_temperature_c": [60.0, 65.0],
        "hold_time_min": [30.0, 60.0],
        "fluorescent_dye_x": [0.1, 1.0],
    },
    "hyasen-hyb413": {"hold_temperature_c": [62.0, 68.0]},
    "hyasen-hyb414": {"hold_temperature_c": [62.0, 68.0]},
    "hyasen-hyb315": {"hold_temperature_c": [62.0, 68.0]},
}

# Explicit baselines supplement the values already present in the protocol
# registry. They are especially useful for products whose public handling guide
# exposes exact reagent arithmetic not represented by the generic registry
# shape.
LAMP_NUMERIC_BASELINES: dict[str, dict[str, Any]] = {
    "agdia-lmx54700": {
        "f3_b3_uM": 0.2,
        "fip_bip_uM": 1.6,
        "loop_uM": 0.4,
        "master_mix_uL": 12.5,
        "primer_mix_uL": 2.5,
    },
    "jena-pcr387": {
        "hold_temperature_max_c": 65.0,
        "hold_temperature_min_c": 60.0,
        "hold_time_min": 30.0,
        "master_mix_x_final": 1.0,
    },
    "jena-pcr393": {
        "hold_temperature_max_c": 65.0,
        "hold_temperature_min_c": 60.0,
        "hold_time_min": 30.0,
        "master_mix_x_final": 1.0,
    },
    "jena-pcr395": {
        "hold_temperature_max_c": 65.0,
        "hold_temperature_min_c": 60.0,
        "hold_time_min": 30.0,
        "master_mix_x_final": 1.0,
    },
    "jena-pcr398": {
        "hold_temperature_max_c": 65.0,
        "hold_temperature_min_c": 60.0,
        "hold_time_min": 30.0,
        "master_mix_x_final": 1.0,
    },
    "jena-pcr540": {
        "buffer_x_final": 1.0,
        "enzyme_mix_x_final": 1.0,
        "fluorescent_dye_x": 1.0,
        "hold_temperature_max_c": 65.0,
        "hold_temperature_min_c": 60.0,
        "hold_time_min": 30.0,
    },
    "jena-pcr541": {
        "hold_temperature_max_c": 65.0,
        "hold_temperature_min_c": 60.0,
        "master_mix_x_final": 1.0,
    },
    "meridian-mdx135": {
        "f3_b3_uM": 0.2,
        "fip_bip_uM": 1.6,
        "hold_temperature_c": 65.0,
        "hold_time_min": 60.0,
        "loop_uM": 0.8,
        "magnesium_mM": 4.0,
        "master_mix_x_final": 1.0,
        "reaction_volume_uL": 20.0,
    },
    "nippon-dr0401": {"reaction_volume_uL": 25.0},
    "nippon-dr0701": {"reaction_volume_uL": 25.0},
    "nippon-heatact-fluorescence": {"reaction_volume_uL": 25.0},
    "nippon-heatact-turbidity": {"reaction_volume_uL": 25.0},
    "nippon-heatact-turbidity-visible": {"reaction_volume_uL": 25.0},
    "nzy-md0696": {"hold_temperature_max_c": 70.0, "hold_temperature_min_c": 65.0},
    "nzy-md0697": {"hold_temperature_max_c": 70.0, "hold_temperature_min_c": 65.0},
    "thermo-a5180x": {"hold_time_min": 30.0},
    "vazyme-rp711": {
        "f3_b3_uM": 0.2,
        "fip_bip_uM": 1.6,
        "fluorescent_dye_uL_per_25uL": 0.5,
        "loop_uM": 0.8,
    },
}

# Conditional rules are exact-product / exact-scenario overlays. `unset`
# removes a baseline that becomes non-authoritative under the selected branch.
LAMP_NUMERIC_CONDITIONAL_RULES: dict[str, list[dict[str, Any]]] = {
    "neb-e1700": [
        {
            "id": "neb-e1700-tte-uvrd",
            "when": {"specificity_additive": "tte-uvrd-reviewed"},
            "set": {"tte_uvrd_ng_per_25uL": 10.0},
            "authority": "NEB E1700 Tte UvrD FAQ starting example",
        },
    ],
    "neb-m1712": [
        {
            "id": "m1712-calcein",
            "when": {"chemistry": "calcein"},
            "set": {"calcein_uM": 25.0, "mncl2_mM": 0.5},
            "authority": "NEB M1712 readout guidance",
        },
        {
            "id": "m1712-ebt",
            "when": {"chemistry": "eriochrome-black-t"},
            "set": {"eriochrome_black_t_uM": 60.0},
            "authority": "NEB M1712 readout guidance",
        },
    ],
    "thermo-a5180x": [
        {
            "id": "thermo-a5180x-syto9",
            "when": {"chemistry": "syto9"},
            "set": {"syto9_uM": 5.0},
            "authority": "Thermo SuperScript IV RT-LAMP Quick Reference",
        },
        {
            "id": "thermo-a5180x-calcein",
            "when": {"chemistry": "calcein"},
            "set": {"calcein_uM": 80.0, "mncl2_mM": 0.25},
            "authority": "Thermo SuperScript IV RT-LAMP calcein guidance",
        },
    ],
    "neb-m9204": [
        {
            "id": "m9204-rna-rt",
            "when": {"from_rna": True},
            "set": {"rt_units": 7.5},
            "authority": "NEB M9204 RT-LAMP protocol",
        },
        {
            "id": "m9204-dutp-udg",
            "when": {"carryover_strategy": "reviewed-dutp-udg"},
            "set": {"dutp_mM": 0.7, "thermolabile_udg_u_per_ml": 20.0},
            "authority": "NEB M9204 optional carry-over branch",
        },
    ],
    "neb-m9205": [
        {
            "id": "m9205-rna-rt",
            "when": {"from_rna": True},
            "set": {"rt_units": 7.5},
            "authority": "NEB M9205 RT-LAMP protocol",
        },
        {
            "id": "m9205-dutp-udg",
            "when": {"carryover_strategy": "reviewed-dutp-udg"},
            "set": {"dutp_mM": 0.7, "thermolabile_udg_u_per_ml": 20.0},
            "authority": "NEB M9205 optional carry-over branch",
        },
    ],
    "optigene-iso004-lnl": [
        {
            "id": "optigene-iso004-lnl-koh",
            "when": {"preparation": "koh-lyse-and-lamp"},
            "set": {"koh_mM": 60.0},
            "authority": "OptiGene Lyse & LAMP guidance",
        },
    ],
    "optigene-iso001-lnl": [
        {
            "id": "optigene-iso001-lnl-koh",
            "when": {"preparation": "koh-lyse-and-lamp"},
            "set": {"koh_mM": 60.0},
            "authority": "OptiGene Lyse & LAMP guidance",
        },
    ],
    "optigene-dr001-lnl": [
        {
            "id": "optigene-dr001-lnl-koh",
            "when": {"preparation": "koh-lyse-and-lamp"},
            "set": {"koh_mM": 60.0},
            "authority": "OptiGene Lyse & LAMP guidance",
        },
    ],
    "takara-rr385": [
        {
            "id": "takara-rr385-preincubation",
            "when": {"preincubation_strategy": "takara-ung-25c-10min"},
            "set": {"preincubation_temperature_c": 25.0, "preincubation_time_min": 10.0},
            "authority": "Takara RR385 manual",
        },
    ],
    "eiken-lmp204": [
        {
            "id": "eiken-lmp221-reagent",
            "when": {"chemistry": "eiken-fd-lmp221"},
            "set": {"eiken_lmp221_uL_per_reaction": 1.0},
            "authority": "Eiken LMP221 insert",
        },
    ],
    "eiken-lmp207": [
        {
            "id": "eiken-lmp221-reagent",
            "when": {"chemistry": "eiken-fd-lmp221"},
            "set": {"eiken_lmp221_uL_per_reaction": 1.0},
            "authority": "Eiken LMP221 insert",
        },
    ],
    "eiken-lmp244": [
        {
            "id": "eiken-lmp221-reagent",
            "when": {"chemistry": "eiken-fd-lmp221"},
            "set": {"eiken_lmp221_uL_per_reaction": 1.0},
            "authority": "Eiken LMP221 insert",
        },
    ],
    "neb-m1800": [
        {
            "id": "neb-m1800-guanidine",
            "when": {"acceleration_additive": "guanidine-hcl-40mm"},
            "set": {"guanidine_added_mM": 40.0},
            "authority": "NEB colorimetric LAMP guanidine guidance",
        },
    ],
    "neb-m1804": [
        {
            "id": "neb-m1804-guanidine",
            "when": {"acceleration_additive": "guanidine-hcl-40mm"},
            "set": {"guanidine_added_mM": 40.0},
            "authority": "NEB colorimetric LAMP guanidine guidance",
        },
    ],
    "yeasen-16730": [
        {
            "id": "yeasen-16730-lyophilization-stabilizer",
            "when": {"formulation": "lyophilized"},
            "set": {"lyophilization_stabilizer_uL_per_25uL": 6.0},
            "authority": "Yeasen 16730 manual reviewed lyo setup",
        },
    ],
    "vazyme-rp711": [
        {
            "id": "vazyme-rp711-slan96p-dye",
            "when": {"instrument_profile": "vazyme-slan96p"},
            "set": {"fluorescent_dye_x": 0.1, "fluorescent_dye_uL_per_25uL": 0.05},
            "authority": "Vazyme RP711 V25.1/current product guidance",
        },
        *[
            {
                "id": f"vazyme-rp711-{profile}-dye",
                "when": {"instrument_profile": profile},
                "set": {"fluorescent_dye_x": 1.0, "fluorescent_dye_uL_per_25uL": 0.5},
                "authority": "Vazyme RP711 instrument-specific dye guidance",
            }
            for profile in (
                "vazyme-quantstudio3",
                "vazyme-quantstudio5",
                "vazyme-steponeplus",
                "vazyme-lightcycler96",
                "vazyme-cfx96-touch",
                "vazyme-quantgene9600",
                "vazyme-gentier96r",
            )
        ],
        {
            "id": "vazyme-rp711-other-qpcr-dye-range",
            "when": {"instrument_profile": "other-qpcr"},
            "unset": ["fluorescent_dye_x", "fluorescent_dye_uL_per_25uL"],
            "ranges": {"fluorescent_dye_x": [0.1, 1.0], "fluorescent_dye_uL_per_25uL": [0.05, 0.5]},
            "authority": "Vazyme RP711 other-instrument dye guidance",
        },
    ],
    "agdia-lmx54700": [
        {
            "id": "agdia-lmx54700-rna-external-rt",
            "when": {"from_rna": True},
            "set": {
                "external_rt_units": 50.0,
                "external_rt_stock_u_per_uL": 200.0,
                "external_rt_uL": 0.25,
            },
            "authority": "Agdia LMX 54700 User Guide m472 Rev. 2025-01-06",
        },
        {
            "id": "agdia-lmx54700-amplifire-run",
            "when": {"instrument_profile": "agdia-amplifire"},
            "set": {"hold_temperature_c": 65.0, "hold_time_min": 20.0},
            "authority": "Agdia LMX 54700 User Guide m472 Rev. 2025-01-06",
        },
    ],
}

# Primer-profile overlays are intentionally protocol-scoped in the validator.
OPTIGENE_PRIMER_PROFILES = {
    "optigene-standard": {"fip_bip_uM": 0.8, "f3_b3_uM": 0.2, "loop_uM": 0.4},
    "optigene-high": {"fip_bip_uM": 2.0, "f3_b3_uM": 0.2, "loop_uM": 1.0},
}

# Matrix limits are reported/validated only for exact products where a public
# handling guide gives a transferable final fraction. These are not inferred
# from generic inhibitor tolerance.
LAMP_SAMPLE_INPUT_LIMITS: dict[str, dict[str, float]] = {
    "meridian-mdx124": {"blood-plasma-serum": 20.0},
    "meridian-mdx125": {"blood-plasma-serum": 10.0},
    "meridian-mdx126": {"blood-plasma-serum": 10.0},
    "meridian-mdx134": {"saliva-sputum": 60.0},
    "meridian-mdx135": {"saliva-sputum": 60.0},
    "meridian-mdx144": {"stool": 20.0},
    "meridian-mdx145": {"stool": 5.0},
    "meridian-mdx154": {"urine": 20.0},
    "meridian-mdx155": {"urine": 20.0},
}

LAMP_NUMERIC_UNRESOLVED_DEPENDENCIES: dict[str, list[dict[str, str]]] = {
    "vazyme-rp712": [
        {
            "id": "vazyme-rp712-exact-recipe",
            "when": "always",
            "note": "The reviewed public product authority supports product/readout/carry-over identity and a 30-minute claim, but this release does not snapshot an exact transferable reagent-volume recipe; numeric bench recipe therefore remains unresolved/fail-closed.",
        }
    ],
    "optigene-iso004": [
        {
            "id": "optigene-turbidity-extra-mg-dntp",
            "when": "turbidity-or-gel",
            "note": "Vendor guidance indicates extra MgSO4/dNTP optimization for some non-fluorescent workflows but does not publish one transferable universal amount.",
        }
    ],
}

LAMP_NUMERIC_DEPENDENCY_AXES = [
    "protocol",
    "substrate",
    "readout",
    "exact-readout-chemistry",
    "instrument",
    "formulation",
    "reconstitution",
    "carry-over",
    "sample-matrix",
    "sample-preparation",
    "sample-input-fraction",
    "sample-buffer",
    "sample-pH",
    "transport-medium",
    "bile-salt",
    "Cary-Blair",
    "guanidine",
    "specificity-additive",
    "primer-kinetics-profile",
    "pre-incubation",
    "bench-optimization",
]


def _matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def _flatten_protocol_baseline(protocol: dict[str, Any] | None) -> dict[str, float]:
    if not protocol:
        return {}
    out: dict[str, float] = {}
    for src, dst in (
        ("reaction_volume_uL", "reaction_volume_uL"),
        ("hold_temperature_c", "hold_temperature_c"),
        ("hold_time_min", "hold_time_min"),
    ):
        value = protocol.get(src)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[dst] = float(value)
    role = protocol.get("role_concentrations_uM") or {}
    if isinstance(role, dict):
        # Legacy grouped keys and the current canonical per-role keys both map
        # to one reaction-level concentration only when the paired roles agree.
        for src, dst in (("FIP_BIP", "fip_bip_uM"), ("F3_B3", "f3_b3_uM"), ("LOOP", "loop_uM")):
            value = role.get(src)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[dst] = float(value)
        for left, right, dst in (
            ("FIP", "BIP", "fip_bip_uM"),
            ("F3", "B3", "f3_b3_uM"),
            ("LF", "LB", "loop_uM"),
        ):
            a, b = role.get(left), role.get(right)
            if all(
                isinstance(value, (int, float)) and not isinstance(value, bool) for value in (a, b)
            ):
                if float(a) != float(b):
                    raise ValueError(
                        f"{left}/{right} concentrations differ and cannot be collapsed into {dst}"
                    )
                out[dst] = float(a)
    chemistry = protocol.get("chemistry") or {}
    if isinstance(chemistry, dict):
        for key, value in chemistry.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[str(key)] = float(value)
    baseline = protocol.get("baseline_formulation") or {}
    if isinstance(baseline, dict):
        aliases = {
            "mgso4_total_mM": "magnesium_mM",
            "dntp_each_mM": "dntp_each_mM",
            "bst_xt_units_per_25uL": "polymerase_units",
            "rtx_units_per_25uL_for_rna": "rt_units",
        }
        for key, value in baseline.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[aliases.get(str(key), str(key))] = float(value)
    return out


def resolve_numeric_recipe(
    protocol_id: str,
    protocol: dict[str, Any] | None,
    scenario: dict[str, Any] | None,
    overrides: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Resolve source-backed numeric reaction values for one explicit scenario."""
    scenario = dict(scenario or {})
    baseline = _flatten_protocol_baseline(protocol)
    baseline.update(deepcopy(LAMP_NUMERIC_BASELINES.get(protocol_id, {})))
    generic = resolve_generic_numeric_recipe(
        baseline=baseline,
        overlays=LAMP_NUMERIC_CONDITIONAL_RULES.get(protocol_id, []),
        ranges=LAMP_NUMERIC_OPTIMIZATION_ENVELOPES.get(protocol_id, {}),
        scenario=scenario,
        overrides=overrides,
        subject=protocol_id,
    )
    values = generic.values
    origins = generic.origins
    ranges = generic.ranges
    applied = generic.applied_overlays
    warnings = generic.warnings

    # Protocol-scoped primer concentration profiles.
    profile = scenario.get("primer_kinetics_profile")
    if profile in OPTIGENE_PRIMER_PROFILES:
        for key, value in OPTIGENE_PRIMER_PROFILES[str(profile)].items():
            values[key] = float(value)
            origins[key] = f"automatic:{profile}"
        applied.append({"id": str(profile), "authority": "reviewed OptiGene primer profile"})

    # Product-scoped direct specimen limits.
    matrix = str(scenario.get("matrix") or "")
    if scenario.get("sample_input_percent") is not None and not (
        protocol_id in LAMP_SAMPLE_INPUT_LIMITS and matrix in LAMP_SAMPLE_INPUT_LIMITS[protocol_id]
    ):
        raise ValueError(
            "sample_input_percent has no reviewed exact-product numeric authority for the selected protocol/matrix."
        )
    if protocol_id in LAMP_SAMPLE_INPUT_LIMITS and matrix in LAMP_SAMPLE_INPUT_LIMITS[protocol_id]:
        limit = float(LAMP_SAMPLE_INPUT_LIMITS[protocol_id][matrix])
        ranges["sample_input_percent"] = [0.0, limit]
        actual = scenario.get("sample_input_percent")
        if actual is not None:
            actual_f = float(actual)
            if actual_f < 0 or actual_f > limit:
                raise ValueError(
                    f"sample_input_percent must be within the reviewed exact-product range 0–{limit}% for {protocol_id}/{matrix}."
                )
            values["sample_input_percent"] = actual_f
            origins["sample_input_percent"] = "user-within-source-bound"

    # NEB pH-colorimetric sample chemistry authority is intentionally scoped to
    # the exact products and readout branch where the vendor publishes it.
    if protocol_id in {"neb-m1800", "neb-m1804"} and scenario.get("readout") == "colorimetric":
        ph = scenario.get("sample_buffer_ph")
        percent = scenario.get("sample_buffer_percent")
        buffer_type = scenario.get("sample_buffer_type")
        if ph is not None:
            ph_f = float(ph)
            values["sample_buffer_ph"] = ph_f
            origins["sample_buffer_ph"] = "user-reviewed-context"
            if not NEB_PH_COLORIMETRIC_REVIEWED_SAMPLE_PH[
                0
            ] <= ph_f <= NEB_PH_COLORIMETRIC_REVIEWED_SAMPLE_PH[1] and (
                percent is not None
                and float(percent) > NEB_PH_COLORIMETRIC_CONSERVATIVE_BUFFER_PERCENT_MAX
            ):
                raise ValueError(
                    "For NEB pH-colorimetric LAMP, sample buffers outside pH 7–8.5 are not accepted above 10% final reaction fraction."
                )
        if percent is not None:
            pct = float(percent)
            if pct < 0:
                raise ValueError("sample_buffer_percent cannot be negative.")
            if buffer_type == "te" and pct >= NEB_PH_COLORIMETRIC_TE_CAUTION_PERCENT_MAX:
                raise ValueError(
                    "TE at 20% final or above is outside the reviewed NEB pH-colorimetric boundary."
                )
            values["sample_buffer_percent"] = pct
            origins["sample_buffer_percent"] = "user-reviewed-context"
            if buffer_type == "te" and pct > NEB_PH_COLORIMETRIC_CONSERVATIVE_BUFFER_PERCENT_MAX:
                warnings.append(
                    "TE between 10% and 20% final lies in a source-disagreement/caution region; validate the exact assay empirically."
                )
        upstream = float(scenario.get("upstream_guanidine_mM") or 0.0)
        added = float(values.get("guanidine_added_mM") or 0.0)
        if upstream + added >= NEB_PH_COLORIMETRIC_GUANIDINE_TOTAL_MM_MAX:
            raise ValueError(
                "Total guanidine must remain below 60 mM in the reviewed NEB pH-colorimetric branch."
            )
        if upstream:
            values["upstream_guanidine_mM"] = upstream
            values["total_guanidine_mM"] = upstream + added
            origins["upstream_guanidine_mM"] = "user-reviewed-context"
            origins["total_guanidine_mM"] = "derived-stoichiometry"

    # Eiken LMP221 + chelating buffers is a source-backed incompatibility.
    if scenario.get("chemistry") == "eiken-fd-lmp221" and scenario.get("sample_buffer_type") in {
        "te",
        "chelating-other",
    }:
        raise ValueError(
            "Eiken LMP221 is incompatible with TE/other chelating sample-buffer context because Mn chelation can release calcein and create false-positive fluorescence."
        )

    # Other matrix modifiers: preserve exact numeric evidence when the product
    # authority provides a maximum, but do not fabricate missing values.
    if scenario.get("transport_medium_percent") is not None:
        if protocol_id not in {"meridian-mdx134", "meridian-mdx135"}:
            raise ValueError(
                "transport_medium_percent has reviewed numeric authority only for Meridian MDX134/MDX135 in this catalogue."
            )
        pct = float(scenario["transport_medium_percent"])
        if not 0 <= pct <= 50.0:
            raise ValueError(
                "transport_medium_percent must remain within the reviewed 0–50% final range for the selected Meridian saliva/sputum branch."
            )
        values["transport_medium_percent"] = pct
        origins["transport_medium_percent"] = "user-reviewed-context"
    if scenario.get("bile_salt_mg_ml") is not None:
        if protocol_id != "meridian-mdx144":
            raise ValueError(
                "bile_salt_mg_ml has reviewed numeric authority only for Meridian MDX144 in this catalogue."
            )
        value = float(scenario["bile_salt_mg_ml"])
        if not 0 <= value <= 2.0:
            raise ValueError(
                "bile_salt_mg_ml must remain within the reviewed 0–2 mg/mL range for Meridian MDX144."
            )
        values["bile_salt_mg_ml"] = value
        origins["bile_salt_mg_ml"] = "user-reviewed-context"
    if scenario.get("cary_blair_percent") is not None:
        if protocol_id != "meridian-mdx144":
            raise ValueError(
                "cary_blair_percent has reviewed numeric authority only for Meridian MDX144 in this catalogue."
            )
        value = float(scenario["cary_blair_percent"])
        if not 0 <= value <= 40.0:
            raise ValueError(
                "cary_blair_percent must remain within the reviewed 0–40% range for Meridian MDX144."
            )
        values["cary_blair_percent"] = value
        origins["cary_blair_percent"] = "user-reviewed-context"

    # Derived dye volume arithmetic prevents a final-X / stock-X / volume
    # contradiction after instrument overlays or explicit bounded overrides.
    if "fluorescent_dye_x" in values and "fluorescent_dye_stock_x" in values:
        reaction = Quantity(float(values.get("reaction_volume_uL") or 25.0), "uL")
        stock = Quantity(float(values["fluorescent_dye_stock_x"]), "x")
        final = Quantity(float(values["fluorescent_dye_x"]), "x")
        key = "fluorescent_dye_uL_per_25uL"
        values[key] = dilution_volume(reaction, final, stock).value
        origins[key] = "derived-stoichiometry"

    unresolved: list[dict[str, str]] = []
    if protocol_id in LAMP_NUMERIC_UNRESOLVED_DEPENDENCIES:
        for item in LAMP_NUMERIC_UNRESOLVED_DEPENDENCIES[protocol_id]:
            if item.get("when") == "turbidity-or-gel" and scenario.get("readout") not in {
                "turbidity",
                "other-validated",
            }:
                continue
            unresolved.append(dict(item))

    thermal_stages: list[dict[str, Any]] = []
    if scenario.get("preincubation_strategy") == "takara-ung-25c-10min":
        thermal_stages.append(
            {
                "id": "carryover-preincubation",
                "temperature_c": 25.0,
                "time_min": 10.0,
                "authority": "Takara RR385 reviewed pre-incubation branch",
                "required_by_selection": True,
            }
        )
    hold_temperature = values.get("hold_temperature_c")
    hold_time = values.get("hold_time_min")
    if hold_temperature is not None or hold_time is not None:
        thermal_stages.append(
            {
                "id": "isothermal-amplification",
                "temperature_c": hold_temperature,
                "time_min": hold_time,
                "authority": origins.get("hold_temperature_c")
                or origins.get("hold_time_min")
                or "product-baseline",
                "required_by_selection": True,
            }
        )
    # Confirmation/inactivation is not synthesized from free text. A later
    # stage is present only when an exact numeric authority has been promoted.

    return {
        "schema_version": LAMP_NUMERIC_SCHEMA_VERSION,
        "protocol": protocol_id,
        "values": values,
        "origins": origins,
        "ranges": ranges,
        "applied_overlays": applied,
        "unresolved_numeric_dependencies": unresolved,
        "warnings": warnings,
        "thermal_stages": thermal_stages,
        "thermal_stage_model": "ordered-source-backed-only",
        "dependency_axes": list(LAMP_NUMERIC_DEPENDENCY_AXES),
        "sequence_decision_impact": "none",
    }


def generated_catalogue() -> dict[str, Any]:
    """Return the immutable numeric authority projection used by generators.

    This function must remain scenario-free: runtime thermal stages are resolved
    by ``resolve_numeric_recipe`` and are never synthesized into the catalogue.
    """
    effective_baselines: dict[str, dict[str, float]] = {}
    for protocol_id, protocol in LAMP_PROTOCOL_REGISTRY.items():
        baseline = _flatten_protocol_baseline(protocol)
        baseline.update(deepcopy(LAMP_NUMERIC_BASELINES.get(protocol_id, {})))
        if baseline:
            effective_baselines[protocol_id] = baseline
    return {
        "schema_version": LAMP_NUMERIC_SCHEMA_VERSION,
        "baselines": LAMP_NUMERIC_BASELINES,
        "effective_baselines": effective_baselines,
        "conditional_rules": LAMP_NUMERIC_CONDITIONAL_RULES,
        "optimization_envelopes": LAMP_NUMERIC_OPTIMIZATION_ENVELOPES,
        "sample_input_limits": LAMP_SAMPLE_INPUT_LIMITS,
        "primer_kinetics_profiles": OPTIGENE_PRIMER_PROFILES,
        "unresolved_numeric_dependencies": LAMP_NUMERIC_UNRESOLVED_DEPENDENCIES,
        "dependency_axes": LAMP_NUMERIC_DEPENDENCY_AXES,
        "instrument_profiles": list(LAMP_INSTRUMENT_PROFILES),
    }
