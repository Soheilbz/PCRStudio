"""External topology sanity check for the Q5-style mutagenesis engine.

The Thermo Scientific Phusion SDM control happens to use a back-to-back pair on
pUC19.  It is useful as an independently published *geometry/edit* sanity
check, but it is **not** a Q5/E0554 acceptance profile: its phosphorylation,
reaction chemistry and primer windows belong to that separate kit and must not
be copied into PCRStudio's Q5 branch.

Source retained for the historical control only: Thermo Scientific Phusion
Site-Directed Mutagenesis Kit manual MAN0013377.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.mutagenic import Edit, apply_edit, design
from pcr_tools.presets import polymerase
from pcr_tools.restriction import BY_NAME, sites
from pcr_tools.thermo import reverse_complement

# The Q5 branch uses this preset only as a reproducible thermodynamic screening
# context.  The external Phusion control is never evaluated as though it ran in
# this chemistry.
CONDITIONS = polymerase("q5-sdm-screening").reaction.as_conditions()

PUBLISHED_FORWARD = "CTGCAGGCATGTAAGCTTGGCGTA"
FORWARD_AT = 434
REVERSE_AT = 410
EDIT_AT = 445
EDIT_TO = "T"


def plasmid() -> str:
    return record("L09137.2").sequence()


def published_reverse() -> str:
    return reverse_complement(plasmid()[REVERSE_AT:FORWARD_AT])


@pytest.fixture(scope="module")
def ours():
    found = design(
        plasmid(),
        Edit(kind="substitute", at=EDIT_AT, to=EDIT_TO, replacing=1),
        conditions=CONDITIONS,
        how_many=5,
    )
    assert found
    return found


def test_published_control_contains_the_declared_edit_at_the_measured_coordinate():
    here = plasmid()[FORWARD_AT : FORWARD_AT + len(PUBLISHED_FORWARD)]
    differ = [i for i, (a, b) in enumerate(zip(here, PUBLISHED_FORWARD, strict=True)) if a != b]
    assert differ == [EDIT_AT - FORWARD_AT]
    assert PUBLISHED_FORWARD[differ[0]] == EDIT_TO


def test_published_control_is_back_to_back_but_not_a_q5_chemistry_authority():
    assert REVERSE_AT + len(published_reverse()) == FORWARD_AT
    # No assertion about phosphorylation, concentration, Tm window or cycling:
    # those are Phusion-kit properties and are not Q5 evidence.


def test_requested_edit_reconstructs_exactly():
    parental = plasmid()
    edit = Edit(kind="substitute", at=EDIT_AT, to=EDIT_TO, replacing=1)
    mutant = apply_edit(parental, edit)
    assert mutant[EDIT_AT] == EDIT_TO
    assert len(mutant) == len(parental)


def test_external_edit_interpretation_is_sequence_checked():
    parental = plasmid()
    mutant = parental[:EDIT_AT] + EDIT_TO + parental[EDIT_AT + 1 :]
    assert sites(parental, BY_NAME["SphI"]) == [EDIT_AT]
    assert sites(mutant, BY_NAME["SphI"]) == []
    assert sites(parental, BY_NAME["HindIII"]) == sites(mutant, BY_NAME["HindIII"])


def test_thermodynamic_values_are_reported_as_screening_not_protocol(ours):
    for pair in ours:
        assert pair.on_template > 0
        assert pair.on_product > 0
        assert pair.reverse_tm > 0
