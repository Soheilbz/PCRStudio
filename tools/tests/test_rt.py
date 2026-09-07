"""Reverse-transcription authority shared by every RNA-capable worker.

The current generic RNA modifier is a handoff, not a wet-lab protocol.  These
regressions make the key invariant explicit: changing scientific policy cannot
manufacture RT chemistry, a hold temperature, duration, or programme position.
Exact numbers belong only to a separately named RT-capable chemistry.
"""

from __future__ import annotations

import pytest

from pcr_tools import rt


@pytest.mark.parametrize("policy", ["strict", "development"])
@pytest.mark.parametrize("isothermal", [False, True])
def test_generic_rt_handoff_is_unresolved_in_every_policy(monkeypatch, policy: str, isothermal: bool):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", policy)
    step = rt.block(isothermal=isothermal, polymerase="Standard Taq")

    assert step["one_step"] is None
    assert step["hold"] is None
    assert step["before"] is None
    assert step["authority_status"] == (
        "rt-isothermal-chemistry-unresolved" if isothermal else "rt-chemistry-unresolved"
    )
    assert step["note"].strip()


def test_generic_rt_note_never_claims_the_pcr_polymerase_sets_rt_conditions():
    step = rt.block(polymerase="Standard Taq")
    assert "Standard Taq does not set them" in step["note"]
    assert "current instructions" in step["note"]

    unnamed = rt.block()
    assert "the PCR polymerase does not set them" in unnamed["note"]


def test_rna_flag_detection_is_boolean_and_centralised():
    assert rt.wanted({"from_rna": True}) is True
    assert rt.wanted({"from_rna": False}) is False
    assert rt.wanted({}) is False
