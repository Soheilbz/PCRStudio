"""Screening a colony with one primer already on the bench.

Real universal primers throughout, and a real insert. The whole point of this
design is that the partner cannot move, so a made-up partner would test
nothing: it is the actual melting temperatures of the M13 and promoter primers
that make the ordinary window unusable.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from pcr_tools.backbone import BackboneError, _candidates, design, resolve_partner
from pcr_tools.design import Constraints
from pcr_tools.presets import polymerase
from pcr_tools.vectors import BY_NAME

CORPUS = pathlib.Path(__file__).parent / "corpus"


@pytest.fixture(scope="module")
def reaction() -> dict[str, float]:
    return polymerase("taq-standard").reaction.as_conditions()


@pytest.fixture(scope="module")
def insert() -> str:
    raw = (CORPUS / "NM_000546.6.fasta").read_text().splitlines()
    return "".join(line.strip() for line in raw if not line.startswith(">"))[200:900]


def test_the_partner_can_be_named_from_the_catalogue(reaction: dict[str, float]) -> None:
    partner = resolve_partner("M13 Reverse, 17-mer", None, **reaction)
    assert partner.sequence == BY_NAME["M13 Reverse, 17-mer"].sequence


def test_the_partner_can_be_a_primer_nobody_catalogued(reaction: dict[str, float]) -> None:
    # A cloning bench is full of primers that predate any catalogue, and
    # refusing them would make this feature useless to exactly the people who
    # have been cloning longest.
    partner = resolve_partner("mine", "acgtacgtacgtacgtacgt", **reaction)
    assert partner.sequence == "ACGTACGTACGTACGTACGT"
    assert partner.family == "supplied"


def test_a_partner_that_is_not_bases_is_refused(reaction: dict[str, float]) -> None:
    with pytest.raises(BackboneError, match="protein sequence"):
        resolve_partner("mine", "ACGT NOT BASES", **reaction)


def test_a_partner_with_punctuation_is_not_silently_changed(
    reaction: dict[str, float],
) -> None:
    with pytest.raises(BackboneError, match="could not be read"):
        resolve_partner("mine", "ACGT!ACGT", **reaction)


def test_an_explicitly_empty_partner_sequence_is_not_treated_as_absent(
    reaction: dict[str, float],
) -> None:
    with pytest.raises(BackboneError, match="No sequence was given"):
        resolve_partner("M13 Reverse, 17-mer", "", **reaction)


def test_backbone_picker_has_an_explicit_pair_contract(
    reaction: dict[str, float], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The colony vector-side Primer3 call must not inherit hidden defaults."""
    import primer3

    captured: dict[str, Any] = {}
    real = primer3.bindings.design_primers

    def watched(seq_args: dict[str, Any], global_args: dict[str, Any]):
        captured.update(global_args)
        return real(seq_args, global_args)

    monkeypatch.setattr(primer3.bindings, "design_primers", watched)
    _candidates("ACGT" * 120, True, Constraints(), reaction, 1)

    assert captured["PRIMER_TASK"] == "pick_primer_list"
    assert captured["PRIMER_PICK_LEFT_PRIMER"] == 1
    assert captured["PRIMER_PICK_RIGHT_PRIMER"] == 0
    assert captured["PRIMER_PICK_INTERNAL_OLIGO"] == 0
    assert captured["PRIMER_PICK_ANYWAY"] == 0
    assert captured["PRIMER_EXPLAIN_FLAG"] == 1
    assert captured["PRIMER_MAX_NS_ACCEPTED"] == 0
    assert captured["PRIMER_THERMODYNAMIC_OLIGO_ALIGNMENT"] == 1
    assert captured["PRIMER_THERMODYNAMIC_TEMPLATE_ALIGNMENT"] == 0


def test_an_unknown_name_lists_what_is_known(reaction: dict[str, float]) -> None:
    with pytest.raises(BackboneError) as raised:
        resolve_partner("M13ish", None, **reaction)

    assert "M13" in str(raised.value), "the message should name real options"


def test_the_insert_primer_is_designed_down_to_the_partner(
    insert: str, reaction: dict[str, float]
) -> None:
    """The measurement this module exists for.

    The 17-mer M13 reverse melts near 51 and the 24-mer M13 forward near 69 --
    eighteen degrees apart, and the assay's ordinary window of 57 to 63
    contains neither. A partner primer designed in that window binds nowhere
    near the same temperature as the one it has to work with.
    """
    cool = resolve_partner("M13 Reverse, 17-mer", None, **reaction)
    warm = resolve_partner("M13 Forward (-47), 24-mer", None, **reaction)

    cool_tm = cool.melting_temperature(**reaction)
    warm_tm = warm.melting_temperature(**reaction)
    assert warm_tm - cool_tm > 15, "these two really are far apart"

    for partner, expected in ((cool, cool_tm), (warm, warm_tm)):
        found = design(insert, partner, reaction=reaction, how_many=1)
        designed = found["primers"][0]["tm"]
        assert abs(designed - expected) <= 3.0, (
            f"a partner for {partner.name} ({expected:.1f} C) should melt near it, got {designed} C"
        )


def test_the_primer_reads_back_towards_the_vector(insert: str, reaction: dict[str, float]) -> None:
    # The vector primer reads into the start of the insert, so the insert
    # primer has to read back at it. Facing the same way amplifies nothing.
    partner = resolve_partner("M13 Forward (-47), 24-mer", None, **reaction)

    into_start = design(insert, partner, reads_into="start", reaction=reaction, how_many=1)
    into_end = design(insert, partner, reads_into="end", reaction=reaction, how_many=1)

    assert into_start["primers"][0]["orientation"] == "reverse"
    assert into_end["primers"][0]["orientation"] == "forward"


def test_backbone_can_use_a_shared_assay_hold_for_cross_dimer_screening(
    insert: str, reaction: dict[str, float]
) -> None:
    partner = resolve_partner("M13 Forward (-47), 24-mer", None, **reaction)

    found = design(
        insert,
        partner,
        reaction=reaction,
        how_many=1,
        temperature_c=68.0,
    )

    assert found["primers"][0]["cross_dimer_temperature_c"] == 68.0


@pytest.mark.parametrize("temperature", [True, 0.0, 100.0, float("nan"), float("inf")])
def test_backbone_rejects_an_invalid_cross_dimer_temperature(
    insert: str, reaction: dict[str, float], temperature: float
) -> None:
    partner = resolve_partner("M13 Forward (-47), 24-mer", None, **reaction)

    with pytest.raises(BackboneError, match="temperature_c"):
        design(insert, partner, reaction=reaction, how_many=1, temperature_c=temperature)


def test_no_product_length_is_invented(insert: str, reaction: dict[str, float]) -> None:
    """The honest half of the answer, when there is only half to give.

    How far the vector primer sits from the cloning site is a property of the
    plasmid. With no plasmid, quoting a total would be quoting a number short
    by however long the polylinker is.

    `known` was `None` here and is now `False`. The distinction it used to
    carry — nothing was asked, versus nothing was found — collapsed the day the
    vector could be pasted: not knowing is now a consequence of not being told,
    which the note says outright.
    """
    partner = resolve_partner("M13 Forward (-47), 24-mer", None, **reaction)
    found = design(insert, partner, reaction=reaction, how_many=1)

    assert found["product"]["known"] is False
    assert "paste the vector" in found["product"]["note"].lower()
    # What it *can* say is the part it controls.
    assert found["primers"][0]["from_the_junction"] > 0


def test_a_window_nothing_fits_says_what_to_do(reaction: dict[str, float]) -> None:
    # A short AT-rich insert cannot hold a primer that melts at 69, and the
    # message has to say which of the two things to change.
    partner = resolve_partner("M13 Forward (-47), 24-mer", None, **reaction)

    with pytest.raises(BackboneError) as raised:
        design("AT" * 60, partner, reaction=reaction)

    said = str(raised.value)
    assert "melts near" in said or "too short" in said


# ── Given the vector ────────────────────────────────────────────────────────
#
# The module's own docstring recorded this as a limit: the vector primer sits
# some distance from the cloning site, that distance belongs to a molecule this
# had never seen, and so every screen it produced reported its product as
# unknown. It is the one number somebody holds a gel up against.

NAMED = "M13/pUC Forward, 23-mer"


@pytest.fixture(scope="module")
def partner(reaction: dict[str, float]):
    return resolve_partner(NAMED, None, **reaction)


def _linearised_at_the_site(partner, after: int) -> str:
    """pUC19, rotated so the cloning site is the end of the string.

    Which is the molecule somebody has in their hand before the ligation, and
    the contract this asks for. `after` is how far past the primer the site is
    planted, so the test knows the answer it is checking.
    """
    raw = (CORPUS / "L09137.2.fasta").read_text().splitlines()
    puc = "".join(line.strip() for line in raw if not line.startswith(">"))
    at = puc.find(partner.sequence)
    assert at >= 0, "the corpus plasmid should contain this primer"
    cut = at + len(partner.sequence) + after
    return puc[cut:] + puc[:cut]


def test_without_a_vector_it_says_which_half_is_missing(insert, partner, reaction):
    """Not a number short by however long the polylinker is."""
    answer = design(insert, partner, reaction=reaction, how_many=2)

    product = answer["product"]
    assert product["known"] is False
    assert "paste the vector" in product["note"].lower()


def test_given_the_vector_it_adds_the_two_halves(insert, partner, reaction):
    vector = _linearised_at_the_site(partner, after=137)
    answer = design(insert, partner, reaction=reaction, how_many=2, vector=vector)

    product = answer["product"]
    assert product["known"] is True
    assert product["vector_bases"] == 137, "the distance this test planted"

    # And the arithmetic is the two halves, not one of them dressed up.
    for size, primer in zip(product["sizes"], answer["primers"], strict=True):
        assert size["bases"] == (137 + primer["from_the_junction"] + len(primer["sequence"]))


def test_a_primer_that_is_not_in_the_vector_is_refused(insert, partner, reaction):
    """The check this whole panel exists to do, applied to the number.

    Plasmids are edited constantly. A primer that sits in the published
    sequence may not sit in the derivative on somebody's bench, and a product
    size computed from an assumption about that is fiction.
    """
    with pytest.raises(BackboneError, match="not in the vector"):
        design(insert, partner, reaction=reaction, vector=insert)


def test_a_primer_that_sits_twice_is_refused(insert, partner, reaction):
    once = _linearised_at_the_site(partner, after=137)
    with pytest.raises(BackboneError, match="sits in 2 places"):
        design(insert, partner, reaction=reaction, vector=once + once)


def test_vector_punctuation_is_refused_instead_of_silently_removed(partner, reaction):
    from pcr_tools.backbone import _product

    with pytest.raises(BackboneError, match="could not be read"):
        _product("ACGT!ACGT", partner, [], forward=True)


def test_insert_punctuation_is_refused_before_primer_search(partner, reaction):
    with pytest.raises(BackboneError, match="could not be read"):
        design("ACGT!" * 20, partner, reaction=reaction)


def test_vector_rna_is_refused_instead_of_being_silently_converted(partner, reaction):
    from pcr_tools.backbone import _product

    with pytest.raises(BackboneError, match="contains RNA uracil"):
        _product("AUGC" * 20, partner, [], forward=True)


def test_vector_fasta_is_parsed_before_the_primer_site_is_located(partner, reaction):
    from pcr_tools.backbone import _product

    vector = _linearised_at_the_site(partner, after=137)
    answer = _product(f">linearised\n{vector}", partner, [], forward=True)

    assert answer["known"] is True
    assert answer["vector_bases"] == 137


def test_overlapping_sits_are_counted_as_several(insert, partner, reaction):
    """str.count misses overlaps: five As inside seven is three sites, not two.

    A primer repeated end to end was counted as fewer places than it really
    occupies, and the refusal this panel exists to produce never happened.
    """
    from pcr_tools.backbone import _product
    from pcr_tools.vectors import UniversalPrimer

    run = UniversalPrimer("homopolymer site", "AAAAA", "forward", "supplied")
    with pytest.raises(BackboneError, match="sits in 3 places"):
        _product("AAAAAAA", run, [], forward=True)
