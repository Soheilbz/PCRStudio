"""Strict request-normalization helpers for the flanking-pair orchestrator.

The browser and Rust boundary reject unknown/ill-typed public fields first, but
direct worker and multiplex callers also enter Python.  These helpers keep that
secondary fail-closed boundary small and independently testable.
"""

from __future__ import annotations

import math
from typing import Any

from pcr_tools.registries.flanking_protocols import DIGITAL_CONSUMABLE_IDS, QPCR_INSTRUMENT_PROFILES
from pcr_tools.workflow_evidence import WorkflowEvidenceError, validate_evidence_fields


def _validate_assay_rna(
    assay: dict[str, Any], *, target_has_rna: bool, requested_from_rna: bool
) -> None:
    """Keep RNA/RT requests inside the profile's declared capability.

    The HTTP route rejects an explicit ``fromRna`` on an incompatible assay,
    but multiplex and direct worker callers can reach this pipeline after a
    different JSON translation. The worker must therefore enforce the same
    chemistry boundary when the profile contract is present. A bare worker
    request without an assay remains a generic design command and keeps its
    historical auto-detection behaviour.
    """
    if "modifiers" not in assay:
        return
    raw_modifiers = assay["modifiers"]
    if not isinstance(raw_modifiers, list) or not all(
        isinstance(modifier, str) for modifier in raw_modifiers
    ):
        raise ValueError("`assay.modifiers` must be a list of names")
    supports_rt = "reverse-transcription" in raw_modifiers
    if (target_has_rna or requested_from_rna) and not supports_rt:
        raise ValueError(
            "This assay does not support reverse transcription. Provide DNA/cDNA "
            "or choose an assay that declares the reverse-transcription modifier."
        )


def _reject_unknown_fields(value: dict[str, Any], *, name: str, known: frozenset[str]) -> None:
    """Refuse misspelled nested JSON instead of silently dropping it."""
    unknown = sorted(set(value) - known)
    if unknown:
        raise ValueError(f"unknown {name} field(s): " + ", ".join(unknown))


def _request_integer(
    value: Any,
    *,
    name: str,
    default: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Read a JSON integer without coercing a malformed experiment.

    The Rust HTTP boundary already deserialises these fields strictly, but the
    worker is also a public command in its own right and multiplex calls enter
    it directly. Accepting ``3.9`` as ``3`` or ``true`` as ``1`` here would
    make the recorded request and the experiment that ran disagree.
    """
    if value is None:
        if default is None:
            raise ValueError(f"`{name}` is required and must be an integer")
        value = default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"`{name}` must be an integer, not {value!r}")
    if minimum is not None and value < minimum:
        raise ValueError(f"`{name}` must be at least {minimum}, not {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"`{name}` must be at most {maximum}, not {value}")
    return value


def _request_optional_text(value: Any, *, name: str) -> str | None:
    """Accept text or absence, never an object that later fails indirectly."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"`{name}` must be text, not {value!r}")
    return value


def _workflow_evidence(value: Any) -> dict[str, str | int | float | bool | None] | None:
    """Validate assay evidence through the shared cross-engine contract."""
    try:
        return validate_evidence_fields(value)
    except WorkflowEvidenceError as exc:
        raise ValueError(str(exc)) from exc


def _exon_junctions(value: Any, *, length: int, from_rna: bool) -> tuple[int, ...]:
    """Validate transcript boundaries that a primer must span.

    Coordinates are zero-based boundaries between bases, not base positions:
    ``j`` means the junction is between ``sequence[j - 1]`` and
    ``sequence[j]``. A junction at either end cannot be spanned by a primer,
    and accepting one would turn a genomic-DNA safeguard into a label.
    """
    if value is None:
        return ()
    if not isinstance(value, list) or not value:
        raise ValueError("`exon_junctions` must be a non-empty list of boundaries")
    if not from_rna:
        raise ValueError(
            "`exon_junctions` requires `from_rna=true`; a genomic-DNA design has no transcript junction"
        )

    checked: list[int] = []
    for index, entry in enumerate(value):
        checked.append(
            _request_integer(
                entry,
                name=f"exon_junctions[{index}]",
                minimum=1,
                maximum=length - 1,
            )
        )
    if len(set(checked)) != len(checked):
        raise ValueError("`exon_junctions` must not contain duplicate boundaries")
    return tuple(sorted(checked))


def _number_map(value: Any, *, name: str) -> dict[str, float | int]:
    """Validate a numeric JSON object before it reaches a dataclass."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"`{name}` must be an object of numeric settings")
    checked: dict[str, float | int] = {}
    for key, entry in value.items():
        if not isinstance(key, str):
            raise ValueError(f"`{name}` contains a non-text setting name")
        if isinstance(entry, bool) or not isinstance(entry, (int, float)):
            raise ValueError(f"`{name}.{key}` must be a number, not {entry!r}")
        try:
            finite = math.isfinite(float(entry))
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"`{name}.{key}` must be finite, not {entry!r}")
        checked[key] = entry
    return checked


FLANKING_NUMERIC_CONTEXT_FIELDS = frozenset(
    {
        "reaction_volume_ul",
        "primer_each_um",
        "primer_each_nm",
        "gc_enhancer_percent",
        "additive",
        "cycling_profile",
        "template_fraction_percent",
        "target_length_kb",
        "partition_format_detail",
        "preparation",
        "initial_denaturation_time_min",
        "rpa_temperature_c",
        "rpa_time_min",
        "rpa_bst_units_per_ul",
        "rpa_multiplex",
        "template_input_ng",
        "template_input_ul",
        "template_class",
        "hmw_template_verified",
        "qpcr_instrument_profile",
        "digital_consumable_id",
        "effective_partition_volume_nl",
        "fragmentation_enzyme",
        "colony_sample_input_ul",
    }
)


def _flanking_numeric_context(value: Any, *, assay_id: str) -> dict[str, Any] | None:
    """Validate the source-conditioned Flanking bench context.

    This object is reaction/provenance context only; it is deliberately kept
    separate from Primer3 constraints so a bench recipe cannot silently alter
    sequence ranking.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("`flanking_numeric_context` must be an object")
    _reject_unknown_fields(
        value, name="flanking_numeric_context", known=FLANKING_NUMERIC_CONTEXT_FIELDS
    )
    checked: dict[str, Any] = {}
    numeric_fields = {
        "reaction_volume_ul",
        "primer_each_um",
        "primer_each_nm",
        "gc_enhancer_percent",
        "template_fraction_percent",
        "target_length_kb",
        "initial_denaturation_time_min",
        "rpa_temperature_c",
        "rpa_time_min",
        "rpa_bst_units_per_ul",
        "template_input_ng",
        "template_input_ul",
        "effective_partition_volume_nl",
        "colony_sample_input_ul",
    }
    for key, entry in value.items():
        if key in numeric_fields:
            if (
                isinstance(entry, bool)
                or not isinstance(entry, (int, float))
                or not math.isfinite(float(entry))
                or float(entry) <= 0
            ):
                raise ValueError(
                    f"`flanking_numeric_context.{key}` must be finite and greater than zero"
                )
            checked[key] = float(entry)
        elif key in {
            "additive",
            "cycling_profile",
            "partition_format_detail",
            "preparation",
            "template_class",
            "qpcr_instrument_profile",
            "digital_consumable_id",
            "fragmentation_enzyme",
        }:
            if not isinstance(entry, str):
                raise ValueError(f"`flanking_numeric_context.{key}` must be text")
            checked[key] = entry
        elif key in {"rpa_multiplex", "hmw_template_verified"}:
            if not isinstance(entry, bool):
                raise ValueError(f"`flanking_numeric_context.{key}` must be boolean")
            checked[key] = entry
    if "primer_each_um" in checked and "primer_each_nm" in checked:
        raise ValueError("choose only one of `primer_each_um` or `primer_each_nm`")
    if checked.get("additive") not in (None, "none", "high-gc-enhancer", "yellow-sample-buffer"):
        raise ValueError("unsupported flanking numeric additive")
    if checked.get("cycling_profile") not in (None, "protocol-default", "fast", "standard"):
        raise ValueError("unsupported flanking numeric cycling profile")
    if checked.get("partition_format_detail") not in (None, "not-specified", "8.5k", "26k"):
        raise ValueError("unsupported digital partition format detail")
    if checked.get("preparation") not in (
        None,
        "protocol-default",
        "direct-colony",
        "direct-transfer",
        "liquid-culture",
        "water-lysate",
        "buffer-lysate",
        "host-specific-lysis",
        "other",
    ):
        raise ValueError("unsupported flanking preparation")
    if checked.get("template_class") not in (
        None,
        "genomic",
        "hmw-genomic",
        "plasmid",
        "lambda",
        "lower-complexity",
        "cDNA",
        "RNA",
        "crude",
        "other",
    ):
        raise ValueError("unsupported flanking template_class")
    if (
        checked.get("qpcr_instrument_profile") is not None
        and checked.get("qpcr_instrument_profile") not in QPCR_INSTRUMENT_PROFILES
    ):
        raise ValueError("unsupported qPCR instrument/reference-dye profile")
    if (
        checked.get("digital_consumable_id") is not None
        and checked.get("digital_consumable_id") not in DIGITAL_CONSUMABLE_IDS
    ):
        raise ValueError("unsupported digital consumable id")
    if "gc_enhancer_percent" in checked and assay_id != "standard-pcr":
        raise ValueError("GC enhancer context is only valid for standard-pcr")
    if "target_length_kb" in checked and assay_id != "long-range-pcr":
        raise ValueError("target_length_kb is only valid for long-range-pcr")
    if "partition_format_detail" in checked and assay_id != "digital-pcr":
        raise ValueError("partition_format_detail is only valid for digital-pcr")
    if "preparation" in checked and assay_id != "colony-pcr":
        raise ValueError("preparation is only valid for colony-pcr")
    if "initial_denaturation_time_min" in checked and assay_id != "colony-pcr":
        raise ValueError("initial_denaturation_time_min is only valid for colony-pcr")
    if checked.get("additive") == "high-gc-enhancer" and assay_id != "standard-pcr":
        raise ValueError("high-gc-enhancer is only valid for standard-pcr")
    if checked.get("additive") == "yellow-sample-buffer" and assay_id != "qpcr-sybr":
        raise ValueError("yellow-sample-buffer is only valid for qpcr-sybr")
    if "template_fraction_percent" in checked and assay_id != "qpcr-sybr":
        raise ValueError("template_fraction_percent is only valid for qpcr-sybr")
    if "qpcr_instrument_profile" in checked and assay_id != "qpcr-sybr":
        raise ValueError("qpcr_instrument_profile is only valid for qpcr-sybr")
    if (
        any(
            key in checked
            for key in {
                "digital_consumable_id",
                "effective_partition_volume_nl",
                "fragmentation_enzyme",
            }
        )
        and assay_id != "digital-pcr"
    ):
        raise ValueError(
            "digital consumable/partition/fragmentation numeric context is only valid for digital-pcr"
        )
    if "colony_sample_input_ul" in checked and assay_id != "colony-pcr":
        raise ValueError("colony_sample_input_ul is only valid for colony-pcr")
    if "hmw_template_verified" in checked and assay_id != "long-range-pcr":
        raise ValueError("hmw_template_verified is only valid for long-range-pcr")
    if "cycling_profile" in checked and assay_id != "qpcr-sybr":
        raise ValueError("cycling_profile is only valid for qpcr-sybr")
    if (
        any(
            key in checked
            for key in {
                "rpa_temperature_c",
                "rpa_time_min",
                "rpa_bst_units_per_ul",
                "rpa_multiplex",
            }
        )
        and assay_id != "rpa"
    ):
        raise ValueError("RPA numeric context is only valid for rpa")
    if "primer_each_nm" in checked and assay_id not in {"qpcr-sybr", "rpa", "digital-pcr"}:
        raise ValueError("primer_each_nm is not valid for this flanking assay")
    return checked
