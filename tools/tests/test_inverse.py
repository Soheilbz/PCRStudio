"""Inverse PCR: standard two-flank restriction/self-ligation geometry.

Gen-1 Scientific-Strict executes one topology only: a named restriction enzyme
that does not cut the complete known anchor, followed by self-ligation of the
restriction fragment containing that intact anchor. One outward-facing pair on
the known anchor then amplifies through the unknown flanks and ligation
junction. Internal-cut/one-sided inverse PCR is deliberately a separate,
non-executable branch.

The tests keep three boundaries separate:
- rotation/coordinate arithmetic used to obtain an outward pair;
- the no-internal-cut topology contract;
- refusal to invent final product size or preparation evidence.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.design import Constraints
from pcr_tools.inverse import Circle, InverseError, back, design_outward, pair_to_dict, rotate, run
from pcr_tools.presets import polymerase

REACTION = polymerase("taq-standard").reaction
LIMITS = Constraints(product_min=200, product_max=900)


def known() -> str:
    return record("L09137.2").sequence()


def strict_request(**updates):
    """A fully specified current Gen-1 inverse-PCR request.

    SpeI has no recognition site inside the pUC19 known anchor used here; the
    absence is the required property for the standard two-flank branch.
    """
    request = {
        "template": record("L09137.2").fasta(),
        "enzyme": "SpeI",
        "inverse_branch": "restriction-self-ligation",
        "left_end_phosphate": "unresolved",
        "right_end_phosphate": "unresolved",
        "circularization_provenance": "unresolved",
        "linear_control_provenance": "unresolved",
        "methylation_branch": "unresolved",
        "how_many": 2,
        "constraints": {"product_min": 200, "product_max": 900},
        "assay": {"id": "inverse-pcr", "name": "Inverse PCR", "defaults": {}},
    }
    request.update(updates)
    return request


# ── Rotation / outward geometry ────────────────────────────────────────────


def test_rotating_and_mapping_back_returns_every_base_to_where_it_started():
    sequence = known()
    for at in (1, 700, 1200, len(sequence) - 1):
        rotated, _ = rotate(sequence, at)
        assert len(rotated) == len(sequence)
        for position in (0, 5, 999, len(rotated) - 1):
            assert rotated[position] == sequence[back(position, at, len(sequence))]


def test_the_artificial_join_is_the_original_endpoint_join():
    rotated, join = rotate("ABCDEFGH", 3)
    assert rotated == "DEFGHABC"
    assert join == 5
    assert rotated[join - 1 : join + 1] == "HA"


def test_every_search_pair_spans_the_original_endpoint_join():
    result, _at, join = design_outward(
        known(), constraints=LIMITS, conditions=REACTION.as_conditions(), how_many=3
    )
    assert result.pairs
    for pair in result.pairs:
        assert pair.left_at.start < join <= pair.right_at.start


def test_pair_coordinates_map_back_to_the_complete_known_anchor():
    sequence = known()
    result, at, _join = design_outward(
        sequence, constraints=LIMITS, conditions=REACTION.as_conditions(), how_many=3
    )
    for pair in result.pairs:
        entry = pair_to_dict(pair, sequence, at, None)
        start = entry["left_at"]["start"]
        length = entry["left_at"]["length"]
        assert sequence[start : start + length] == pair.left.sequence
        assert entry["reads"] == "outward-from-known-anchor"
        assert entry["left_reads_into"] == "downstream flank"
        assert entry["right_reads_into"] == "upstream flank"


# ── Product-size claim boundary ────────────────────────────────────────────


def test_no_final_product_size_is_reported_without_fragment_length():
    result, at, _ = design_outward(
        known(), constraints=LIMITS, conditions=REACTION.as_conditions(), how_many=1
    )
    entry = pair_to_dict(result.pairs[0], known(), at, None)
    assert entry["product_size"] is None
    assert entry["known_span"] > 0
    assert entry["unknown_interval"]["status"] == "unresolved"
    assert "Final product size is unresolved" in entry["product_note"]


def test_supplied_fragment_length_makes_product_size_arithmetic():
    sequence = known()
    result, at, _ = design_outward(
        sequence, constraints=LIMITS, conditions=REACTION.as_conditions(), how_many=1
    )
    circle_length = len(sequence) + 1200
    entry = pair_to_dict(result.pairs[0], sequence, at, circle_length)
    assert entry["product_size"] == entry["known_span"] + 1200
    assert entry["unknown_interval"]["exact"] == 1200


def test_self_ligated_fragment_cannot_be_smaller_than_complete_anchor():
    with pytest.raises(InverseError, match="complete known anchor"):
        Circle(length=len(known()) - 1).check(len(known()))


# ── Standard two-flank branch / restriction identity ──────────────────────


def test_standard_result_has_one_intact_anchor_circle_and_no_internal_cut():
    answer = run(strict_request(how_many=1))
    assert answer["digest"]["enzyme"] == "SpeI"
    assert answer["digest"]["known_sites"] == []
    assert answer["digest"]["known_length"] == len(known())
    assert answer["circle"]["known_length"] == len(known())
    assert "cut" not in answer
    assert "circles" not in answer
    assert answer["pairs"]
    for pair in answer["pairs"]:
        assert pair["walks_into"] == "both flanks across the self-ligation junction"


def test_inverse_flank_ranking_marks_only_no_internal_site_enzymes_usable():
    answer = run(strict_request(how_many=1))
    usable = [entry for entry in answer["enzymes"] if entry["usable"]]
    assert usable
    assert all(entry["cuts_inside"] == [] for entry in usable)


def test_an_enzyme_that_cuts_the_known_anchor_is_refused():
    with pytest.raises(InverseError, match="known anchor"):
        run(strict_request(enzyme="EcoRI"))


def test_unknown_enzyme_is_refused():
    with pytest.raises(InverseError, match="not an enzyme"):
        run(strict_request(enzyme="Nonsense"))


def test_internal_cut_coordinate_is_a_typed_topology_boundary():
    with pytest.raises(InverseError, match="not part of the current outward-pair request contract"):
        run(strict_request(cut_at=900))


def test_one_sided_selector_is_a_typed_topology_boundary():
    with pytest.raises(InverseError, match="not part of the current outward-pair request contract"):
        run(strict_request(side="downstream"))


def test_nonstandard_inverse_branch_is_not_silently_approximated():
    with pytest.raises(InverseError, match="executes only `restriction-self-ligation`"):
        run(strict_request(inverse_branch="one-sided-internal-cut"))


def test_supplied_circular_template_is_executable_without_inventing_a_digest(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "permissive")
    request = strict_request(
        inverse_branch="supplied-circular-template", circle_length=len(known()) + 1200
    )
    request.pop("enzyme")
    answer = run(request)
    assert answer["experiment_contract"]["branch"] == "supplied-circular-template"
    assert answer["digest"]["enzyme"] is None
    assert answer["circle"]["circle_length"] == len(known()) + 1200


def test_named_strict_branch_requires_enzyme_identity():
    request = strict_request()
    request.pop("enzyme")
    with pytest.raises(InverseError, match="requires the restriction-enzyme identity"):
        run(request)


@pytest.mark.parametrize(
    "missing",
    [
        "left_end_phosphate",
        "right_end_phosphate",
        "circularization_provenance",
        "linear_control_provenance",
        "methylation_branch",
    ],
)
def test_missing_preparation_evidence_is_not_reinterpreted_as_unresolved(missing: str):
    request = strict_request()
    request.pop(missing)
    with pytest.raises(InverseError, match=missing):
        run(request)
