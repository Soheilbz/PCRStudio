"""Reverse-transcription provenance shared by RNA-capable workers.

The generic RNA modifier records that reverse transcription is required; it is
not a chemistry selector.  It must therefore never invent one-step/two-step
identity, a hold temperature, duration, or placement.  Exact RT conditions
come only from a separately named, versioned RT-capable chemistry (for example
a named RT-LAMP kit that explicitly supplies the shared isothermal hold).

Keeping this handoff in one helper makes the policy invariant explicit across
workers: changing Scientific-Strict/development/permissive mode cannot create a
different wet-lab RT protocol.
"""

from __future__ import annotations

from typing import Any


def block(*, isothermal: bool = False, polymerase: str | None = None) -> dict[str, Any]:
    """Record an unresolved generic RT handoff without inventing chemistry.

    Policy mode must not create a different experimental protocol.  Only a
    separately named RT-capable chemistry may supply one-step/two-step
    identity, hold temperature, duration or placement.
    """
    if isothermal:
        return {
            "one_step": None,
            "hold": None,
            "before": None,
            "authority_status": "rt-isothermal-chemistry-unresolved",
            "note": (
                "The input is RNA, but the generic reverse-transcription modifier does "
                "not identify an RT-capable isothermal kit. PCRStudio therefore does "
                "not infer one-step operation, temperature or duration; select a named "
                "RT-compatible assay chemistry before using this as a bench protocol."
            ),
        }

    whose = f"{polymerase} does not set them" if polymerase else "the PCR polymerase does not set them"
    return {
        "one_step": None,
        "hold": None,
        "before": None,
        "authority_status": "rt-chemistry-unresolved",
        "note": (
            "Reverse transcription is required before PCR, but PCRStudio does not infer "
            "one-step versus two-step operation, its temperature, duration or placement "
            "from the generic RNA modifier. Select a named RT enzyme/kit and use its "
            "current instructions; " + whose + "."
        ),
    }


def wanted(request: dict[str, Any]) -> bool:
    """Whether this run was told the tube starts from RNA.

    Read in one place so the five workers cannot disagree about the spelling;
    the field is absent for the thirteen assays whose pages never ask.
    """
    return bool(request.get("from_rna"))
