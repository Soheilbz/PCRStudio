"""The fixed tails a KASP reaction is read by.

A KASP assay does not report anything by itself. Each allele-specific primer
carries a 5' tail that is not on the template at all; the first round copies it
into the product, and from the second round on a fluorescent cassette anneals
to the copy and separates from its quencher. Which allele is present is read
from which of two dyes rises.

So the tails are not decoration on the order sheet, and they are not optional:
an order placed without them is an order for primers that amplify correctly and
report nothing. This engine described them in its geometry note and did not add
them — a KASP page produced bare allele-specific primers and left somebody to
remember two 21-mers.

They are also not a choice. There are two cassettes in the standard system and
each reads one fixed sequence, so the only decision is which allele gets which,
and that decision has to be written down rather than assumed.
"""

from __future__ import annotations

from typing import Any

from .registries.authorities import DISCRIMINATING_AUTHORITY, record as authority_record

#: The two standard KASP tail sequences, in the order alleles are given.
#:
#: These are the sequences the commercial cassettes anneal to; they are fixed
#: by the chemistry rather than designed here, which is why they are a constant
#: and not a search. The first allele listed takes the first tail.
_KASP_CHEMISTRY = dict(DISCRIMINATING_AUTHORITY["kasp_chemistry"])
TAILS: tuple[tuple[str, str], ...] = tuple(
    (str(item["dye"]), str(item["sequence"]))
    for item in _KASP_CHEMISTRY["reporter_tails"]
)

#: A named wet-lab overlay.  These are not geometry defaults: they are the
#: standard LGC KASP touchdown programme and 10 µL reaction guidance.  Keeping
#: them behind an explicit selector prevents a KASP calculation from being
#: mistaken for a universal genotyping protocol, or for a protocol of another
#: master-mix revision or instrument.
PROTOCOLS = ("not-selected", "lgc-kasp-tf-v5", "lgc-standard")


def protocol(
    named: str | None,
    *,
    plate_format: str | None = None,
    instrument_model: str | None = None,
    rox_policy: str | None = None,
) -> dict[str, Any] | None:
    """Return the selected LGC overlay with explicit plate/instrument context."""
    if not named or named == "not-selected":
        return None
    if named not in {"lgc-kasp-tf-v5", "lgc-standard"}:
        raise ValueError(
            f"`{named}` is not a KASP protocol this worker knows. It knows: {', '.join(PROTOCOLS)}."
        )
    if plate_format not in {"96", "384"}:
        raise ValueError("LGC KASP requires `plate_format` 96 or 384")
    if not instrument_model:
        raise ValueError("LGC KASP requires an instrument model or the explicit value `unresolved`")
    if rox_policy not in {"none", "low", "standard", "high", "unresolved"}:
        raise ValueError("LGC KASP requires an explicit ROX/reference-dye policy")
    if named == "lgc-kasp-tf-v5":
        payload = authority_record(DISCRIMINATING_AUTHORITY, named)
        cycle = payload["additional_cycle_block"]
        readout = payload["readout"]
        return {
            "selection": payload["selection"],
            "source_identity": payload["source_identity"],
            "source_url": payload["source_url"],
            "source_reviewed_date": payload["source_reviewed_date"],
            "source_revision": "V5.0",
            "plate_format": plate_format,
            "instrument_model": instrument_model,
            "rox_policy": rox_policy,
            "readout": {
                "channels": list(readout["channels"]),
                "axes": {"x": "FAM", "y": "HEX"},
                "read_below_c": readout["read_below_c"],
                "rox": readout["rox"],
            },
            "additional_cycle_block": {
                "denature_c": cycle["denaturation_c"], "denature_seconds": cycle["denaturation_s"],
                "anneal_extend_c": cycle["anneal_extend_c"], "anneal_extend_seconds": cycle["anneal_extend_s"], "cycles": cycle["cycles"],
            },
            "numeric_resolution": "source-limited",
            "unresolved": [
                "PCRStudio does not copy the historical V4 96/384 reaction-volume recipe into V5 without a matching current V5 numeric source.",
                "Use the current V5 instrument/format manual or laboratory SOP for exact dispensing and primary cycling details.",
            ],
            "note": "Current V5 readout/additional-cycle authority. Sequence ranking is unchanged; exact wet-lab values not present in the reviewed V5 authority remain unresolved rather than inherited from V4.",
        }
    payload = authority_record(DISCRIMINATING_AUTHORITY, named)
    legacy = payload["legacy_numeric"]
    plate = legacy[plate_format]
    return {
        "selection": payload["selection"],
        "source_identity": payload["source_identity"],
        "source_revision": None,
        "chemistry_identity": "KASP-TF V4.0 2X Master Mix 96/384",
        "master_mix": "KASP-TF V4.0 2X Master Mix 96/384",
        "assay_mix": "KASP Assay mix (72X)",
        "plate_format": plate_format,
        "instrument_model": instrument_model,
        "rox_policy": rox_policy,
        "reaction_volume_uL": plate["reaction_volume_uL"],
        "dna_volume_uL": plate["dna_volume_uL"],
        "master_mix_volume_uL": plate["master_mix_volume_uL"],
        "assay_mix_volume_uL": plate["assay_mix_volume_uL"],
        "dna_final_ng_per_uL": legacy["dna_final_ng_per_uL"],
        "dna_input_note": (
            "The standard branch retains the plate-specific reaction volumes. "
            "Scale DNA input to genome size and the current LGC guidance rather than treating 2.5 ng/µL as a universal sample requirement."
        ),
        "touchdown": dict(legacy["touchdown"]),
        "amplification": dict(legacy["amplification"]),
        "readout": {**dict(legacy["readout"]), "singleplex": True},
        "lifecycle": "historical-compatibility",
        "note": (
            "This overlay is the historical LGC standard compatibility branch only. Confirm the current "
            "instrument-specific ROX choice and control/cluster review before treating a run as a genotype call. "
            "This branch is the V4.0 96/384 plate workflow; Array Tape/IntelliQube V5.0 is a separate, non-executable Gen-1 branch."
        ),
    }


def attach(sequence: str, index: int) -> str:
    """One allele-specific primer with its cassette tail in front."""
    return TAILS[index][1] + sequence


def describe(index: int, annealing: str, tm: float) -> dict[str, Any]:
    """What was added, and whose melting temperature is being quoted.

    The temperature stays the annealing half's. The tail is not on the template
    in the first round — nothing for it to melt against — so a melting
    temperature computed over the whole 40-odd bases would describe a duplex
    that does not exist in the first cycle. Neither value is a substitute for
    the selected LGC cycling protocol.
    """
    dye, tail = TAILS[index]
    return {
        "dye": dye,
        "tail": tail,
        "length": len(tail),
        "annealing": annealing,
        "annealing_tm": tm,
        "note": (
            f"The {dye} cassette reads this tail. It is not on the template, so "
            f"the {tm} °C above is the annealing-half thermodynamic screening value. "
            f"Do not derive KASP block cycling from it; use the explicitly selected "
            f"LGC protocol/instrument branch. Order the whole sequence exactly as written."
        ),
    }
