"""The tails a KASP reaction is read by, and the assays that must not have them.

A KASP primer without its cassette tail amplifies correctly and reports
nothing: the first round copies the tail into the product, and from the second
round a fluorescent cassette anneals to the copy and separates from its
quencher. The engine's own geometry note described this and nothing added the
tails, so the page produced bare primers and left somebody to remember two
21-mers.

The other half matters as much. ARMS and tetra-primer assays are read from a
gel, so a tail on their primers is 21 bases of sequence that belongs to a
chemistry they do not use.
"""

from __future__ import annotations

import pathlib

import pytest

from pcr_tools import kasp

CORPUS = pathlib.Path(__file__).parent / "corpus"


def _corpus(accession: str, start: int, length: int) -> str:
    raw = (CORPUS / f"{accession}.fasta").read_text().splitlines()
    seq = "".join(line.strip() for line in raw if not line.startswith(">"))
    return seq[start : start + length]


TP53 = _corpus("NM_000546.6", 200, 1400)

#: A site where a design comes back for every geometry, found by trying.
AT = 900


def _design(geometry: str) -> dict:
    from pcr_tools.discriminate import run

    return run(
        {
            "template": TP53,
            "at": AT,
            "alleles": [TP53[AT], "A" if TP53[AT] != "A" else "G"],
            "geometry": geometry,
        }
    )


def test_kasp_fixed_tails_are_distinct_and_attached_in_allele_order():
    assert tuple(dye for dye, _ in kasp.TAILS) == ("FAM", "HEX")
    assert len({tail for _, tail in kasp.TAILS}) == 2
    annealing = "ACGTACGTACGTACGTACGT"
    assert kasp.attach(annealing, 0) == kasp.TAILS[0][1] + annealing
    assert kasp.attach(annealing, 1) == kasp.TAILS[1][1] + annealing


def test_kasp_description_keeps_tail_and_annealing_thermodynamics_separate():
    annealing = "ACGTACGTACGTACGTACGT"
    described = kasp.describe(0, annealing, 61.5)
    assert described["dye"] == "FAM"
    assert described["tail"] == kasp.TAILS[0][1]
    assert described["annealing"] == annealing
    assert described["annealing_tm"] == 61.5
    assert "not on the template" in described["note"]


def test_lgc_standard_protocol_scales_96_and_384_well_volumes_without_changing_identity():
    p96 = kasp.protocol(
        "lgc-standard", plate_format="96", instrument_model="QuantStudio 5", rox_policy="standard"
    )
    p384 = kasp.protocol(
        "lgc-standard", plate_format="384", instrument_model="QuantStudio 5", rox_policy="standard"
    )
    assert p96 and p384
    assert p96["chemistry_identity"] == p384["chemistry_identity"]
    assert p96["reaction_volume_uL"] == 10.0
    assert p384["reaction_volume_uL"] == 5.0
    assert p96["master_mix_volume_uL"] == 5.0
    assert p384["master_mix_volume_uL"] == 2.5
    assert p96["readout"]["channels"] == ["FAM", "HEX"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"plate_format": "24", "instrument_model": "x", "rox_policy": "none"}, "plate_format"),
        ({"plate_format": "96", "instrument_model": "", "rox_policy": "none"}, "instrument model"),
        ({"plate_format": "96", "instrument_model": "x", "rox_policy": "guess"}, "ROX"),
    ],
)
def test_lgc_standard_protocol_fails_closed_when_required_context_is_unresolved(kwargs, message):
    with pytest.raises(ValueError, match=message):
        kasp.protocol("lgc-standard", **kwargs)


def test_unknown_kasp_protocol_is_never_guessed():
    with pytest.raises(ValueError, match="not a KASP protocol"):
        kasp.protocol("vendor-default", plate_format="96", instrument_model="x", rox_policy="none")
