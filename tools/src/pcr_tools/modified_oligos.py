"""Typed modified-oligo annotations shared by LAMP and RPA/probe workflows.

The schema is manufacturing/readout metadata.  It is deliberately orthogonal to
sequence ranking: a topology must be separately implemented and versioned before
annotations such as THF/dSpacer, fluorophore/quencher or lateral-flow labels can
make a currently non-executable chemistry executable.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_ALLOWED = {
    "role",
    "sequence",
    "fivePrimeLabel",
    "threePrimeBlock",
    "fluorophore",
    "quencher",
    "affinityLabel",
    "lateralFlowLabel",
    "cleavageSite",
    "manufacturerNotes",
    "internalModifications",
}
_MOD_ALLOWED = {"kind", "position", "identity"}
_MOD_KINDS = {"thf", "dSpacer", "fluorophore", "quencher", "other-reviewed"}


def validate_modified_oligos(value: Any) -> list[dict[str, Any]] | None:
    """Validate and normalize the shared modified-oligo annotation block."""
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 24:
        raise ValueError(
            "modified_oligos must be an array containing at most 24 oligo annotations."
        )
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"modified_oligos[{index}] must be an object.")
        unknown = sorted(set(raw) - _ALLOWED)
        if unknown:
            raise ValueError(
                f"modified_oligos[{index}] contains unknown field(s): {', '.join(unknown)}."
            )
        role = raw.get("role")
        if (
            not isinstance(role, str)
            or not role
            or len(role) > 40
            or not all(c.isalnum() or c in "._-" for c in role)
        ):
            raise ValueError(f"modified_oligos[{index}].role must be a 1–40 character identifier.")
        seq = raw.get("sequence")
        if seq is not None:
            if (
                not isinstance(seq, str)
                or not (1 <= len(seq) <= 500)
                or any(c.upper() not in "ACGT" for c in seq)
            ):
                raise ValueError(
                    f"modified_oligos[{index}].sequence must contain 1–500 A/C/G/T bases."
                )
        item = deepcopy(raw)
        if isinstance(seq, str):
            item["sequence"] = seq.upper()
        for key in (
            "fivePrimeLabel",
            "threePrimeBlock",
            "fluorophore",
            "quencher",
            "affinityLabel",
            "lateralFlowLabel",
        ):
            if key in raw and (not isinstance(raw[key], str) or len(raw[key]) > 80):
                raise ValueError(
                    f"modified_oligos[{index}].{key} must be text no longer than 80 characters."
                )
        notes = raw.get("manufacturerNotes")
        if notes is not None and (not isinstance(notes, str) or len(notes) > 500):
            raise ValueError(
                f"modified_oligos[{index}].manufacturerNotes must be text no longer than 500 characters."
            )
        cleavage = raw.get("cleavageSite")
        if cleavage is not None and (
            isinstance(cleavage, bool) or not isinstance(cleavage, int) or not 0 <= cleavage <= 499
        ):
            raise ValueError(
                f"modified_oligos[{index}].cleavageSite must be a non-negative integer below 500."
            )
        mods = raw.get("internalModifications")
        if mods is not None:
            if not isinstance(mods, list) or len(mods) > 12:
                raise ValueError(
                    f"modified_oligos[{index}].internalModifications must contain at most 12 entries."
                )
            for mindex, mod in enumerate(mods):
                if not isinstance(mod, dict) or set(mod) - _MOD_ALLOWED:
                    raise ValueError(
                        f"modified_oligos[{index}].internalModifications[{mindex}] has an invalid shape."
                    )
                if mod.get("kind") not in _MOD_KINDS:
                    raise ValueError(
                        f"modified_oligos[{index}].internalModifications[{mindex}].kind is not recognised."
                    )
                pos = mod.get("position")
                if isinstance(pos, bool) or not isinstance(pos, int) or not 0 <= pos <= 499:
                    raise ValueError(
                        f"modified_oligos[{index}].internalModifications[{mindex}].position must be a non-negative integer below 500."
                    )
                ident = mod.get("identity")
                if ident is not None and (not isinstance(ident, str) or len(ident) > 80):
                    raise ValueError(
                        f"modified_oligos[{index}].internalModifications[{mindex}].identity must be text no longer than 80 characters."
                    )
        out.append(item)
    return out


def provenance_block(value: Any) -> dict[str, Any] | None:
    normalized = validate_modified_oligos(value)
    if normalized is None:
        return None
    return {
        "schema": "contracts/oligos/modified-oligo.schema.json",
        "annotations": normalized,
        "decision_impact": "none",
        "note": "Manufacturing/readout annotations are recorded only; a separately implemented topology is required before they may affect sequence design.",
    }
