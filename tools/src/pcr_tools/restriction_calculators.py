"""Fail-closed bench calculators for restriction cloning.

Calculations use user/vendor-supplied physical facts. They never infer an
enzyme's buffer, temperature, methylation sensitivity, star activity or stock
concentration from its recognition sequence.
"""

from __future__ import annotations

import math


class RestrictionCalculatorError(ValueError):
    pass


def _positive(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise RestrictionCalculatorError(f"{name} must be finite and >0")
    return value


def dna_fmol(*, mass_ng: float, length_bp: int, mean_bp_molecular_weight: float = 660.0) -> float:
    mass_ng = _positive(mass_ng, "mass_ng")
    if isinstance(length_bp, bool) or length_bp <= 0:
        raise RestrictionCalculatorError("length_bp must be a positive integer")
    mw = _positive(mean_bp_molecular_weight, "mean_bp_molecular_weight")
    # ng / (g/mol) -> mol, then *1e15 fmol/mol and 1e-9 g/ng => *1e6
    return mass_ng * 1_000_000.0 / (length_bp * mw)


def insert_mass_ng(
    *,
    vector_mass_ng: float,
    vector_length_bp: int,
    insert_length_bp: int,
    insert_to_vector_molar_ratio: float,
) -> float:
    vector_mass_ng = _positive(vector_mass_ng, "vector_mass_ng")
    if vector_length_bp <= 0 or insert_length_bp <= 0:
        raise RestrictionCalculatorError("vector_length_bp and insert_length_bp must be >0")
    ratio = _positive(insert_to_vector_molar_ratio, "insert_to_vector_molar_ratio")
    return vector_mass_ng * (insert_length_bp / vector_length_bp) * ratio


def enzyme_volume_ul(*, required_units: float, stock_units_per_ul: float) -> float:
    return _positive(required_units, "required_units") / _positive(
        stock_units_per_ul, "stock_units_per_ul"
    )


def final_glycerol_percent(
    *,
    enzyme_volumes_ul: list[float] | tuple[float, ...],
    reaction_volume_ul: float,
    enzyme_storage_glycerol_fraction: float = 0.5,
) -> float:
    reaction = _positive(reaction_volume_ul, "reaction_volume_ul")
    fraction = float(enzyme_storage_glycerol_fraction)
    if not math.isfinite(fraction) or not 0 <= fraction <= 1:
        raise RestrictionCalculatorError("enzyme_storage_glycerol_fraction must be between 0 and 1")
    total = 0.0
    for value in enzyme_volumes_ul:
        if not math.isfinite(float(value)) or float(value) < 0:
            raise RestrictionCalculatorError("enzyme volumes must be finite and >=0")
        total += float(value)
    return total * fraction / reaction * 100.0


def plan_double_digest(
    *,
    first: dict[str, object],
    second: dict[str, object],
    minimum_common_buffer_activity_percent: float = 50.0,
) -> dict[str, object]:
    """Plan only when exact-formulation facts are explicitly supplied.

    Each enzyme dict must provide ``name``, ``temperature_c`` and a ``buffers``
    mapping of buffer-id -> activity percent. Heat-inactivation information is
    optional and is never guessed.
    """
    min_activity = _positive(
        minimum_common_buffer_activity_percent, "minimum_common_buffer_activity_percent"
    )
    if min_activity > 100:
        raise RestrictionCalculatorError("minimum_common_buffer_activity_percent cannot exceed 100")
    for label, row in (("first", first), ("second", second)):
        if not str(row.get("name") or "").strip():
            raise RestrictionCalculatorError(
                f"{label} enzyme requires exact name/formulation identity"
            )
        if not isinstance(row.get("buffers"), dict) or not row["buffers"]:
            raise RestrictionCalculatorError(f"{label} enzyme requires exact buffer/activity data")
        _positive(float(row.get("temperature_c") or 0), f"{label}.temperature_c")
    a_buffers = {str(k): float(v) for k, v in first["buffers"].items()}
    b_buffers = {str(k): float(v) for k, v in second["buffers"].items()}
    common = sorted(
        (name, a_buffers[name], b_buffers[name])
        for name in a_buffers.keys() & b_buffers.keys()
        if a_buffers[name] >= min_activity and b_buffers[name] >= min_activity
    )
    same_temp = float(first["temperature_c"]) == float(second["temperature_c"])
    if common and same_temp:
        # Prefer maximum bottleneck activity, then deterministic buffer name.
        best = sorted(common, key=lambda r: (-min(r[1], r[2]), -sum(r[1:]), r[0]))[0]
        return {
            "mode": "simultaneous",
            "buffer": best[0],
            "activities_percent": [best[1], best[2]],
            "temperature_c": float(first["temperature_c"]),
            "sequence_decision_impact": "none",
        }
    return {
        "mode": "sequential-required",
        "reason": "no source-backed common buffer/temperature meeting the requested activity threshold",
        "first_heat_inactivation": first.get("heat_inactivation"),
        "second_heat_inactivation": second.get("heat_inactivation"),
        "cleanup_between_steps": "required-unless-the-exact-formulation-authority-establishes-a-compatible-transition",
        "sequence_decision_impact": "none",
    }
