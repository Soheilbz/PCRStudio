"""Regression contract for the topology-separated mutagenesis engine.

Generation 1 keeps Q5, QuikChange Lightning single-site, Lightning Multi and
NEBuilder multi-site routing distinct. Q5 supports source-bounded split-tail
insertions through 100 nt; larger insertions route to assembly rather than being
truncated or relabelled.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.mutagenic import (
    Q5_MIN_3PRIME_COMPLEMENT,
    Edit,
    MutagenesisError,
    apply_edit,
    design,
    pair_to_dict,
)
from pcr_tools.presets import polymerase

CONDITIONS = polymerase("q5-sdm-screening").reaction.as_conditions()


def plasmid() -> str:
    return record("L09137.2").sequence()


def made(edit: Edit, *, how_many: int = 5):
    return design(plasmid(), edit, conditions=CONDITIONS, how_many=how_many)


def test_edit_reconstruction_is_exact_for_substitution_insertion_and_deletion():
    source = plasmid()
    sub = Edit(kind="substitute", at=1200, to="AT", replacing=2)
    ins = Edit(kind="insert", at=1200, to="GGG")
    delete = Edit(kind="delete", at=1200, replacing=6)
    assert apply_edit(source, sub)[1200:1202] == "AT"
    assert apply_edit(source, ins)[1200:1203] == "GGG"
    assert len(apply_edit(source, delete)) == len(source) - 6


def test_q5_substitution_keeps_at_least_ten_template_complementary_3prime_bases():
    edit = Edit(kind="substitute", at=1200, to="AT", replacing=2)
    pairs = made(edit)
    assert pairs
    for pair in pairs:
        left_match = edit.at - pair.forward_at
        right_match = len(pair.forward) - len(edit.to) - left_match
        assert right_match >= Q5_MIN_3PRIME_COMPLEMENT
        assert pair.forward_annealing == pair.forward
        assert pair.forward_tail == ""


def test_q5_substitution_ranks_the_mismatch_toward_the_primer_centre():
    edit = Edit(kind="substitute", at=1200, to="AT", replacing=2)
    pairs = made(edit, how_many=10)
    errors = [pair.centrality_error for pair in pairs]
    assert errors == sorted(errors)


def test_q5_substitution_reverse_primer_starts_back_to_back_at_forward_5prime_end():
    edit = Edit(kind="substitute", at=1200, to="A", replacing=1)
    for pair in made(edit):
        assert pair.reverse_at + len(pair.reverse_annealing) == pair.forward_at


def test_q5_deletion_uses_standard_primers_that_flank_the_deleted_interval():
    edit = Edit(kind="delete", at=1200, replacing=12)
    pairs = made(edit)
    assert pairs
    for pair in pairs:
        assert pair.forward_at == edit.at + edit.replacing
        assert pair.reverse_at + len(pair.reverse_annealing) == edit.at
        assert pair.forward_tail == pair.reverse_tail == ""


def test_q5_small_insertion_is_a_5prime_forward_tail_not_part_of_the_annealing_core():
    edit = Edit(kind="insert", at=1200, to="GGG")
    pair = made(edit)[0]
    assert pair.forward.startswith(edit.to)
    assert pair.forward_tail == edit.to
    assert pair.forward == pair.forward_tail + pair.forward_annealing
    assert len(pair.forward_annealing) >= Q5_MIN_3PRIME_COMPLEMENT
    assert pair.reverse_at + len(pair.reverse_annealing) == pair.forward_at


def test_large_q5_insertion_uses_reviewed_split_tail_topology():
    edit = Edit(kind="insert", at=1200, to="ACGTACGTACGT")
    pair = made(edit)[0]
    assert pair.forward_tail
    assert pair.reverse_tail
    assert len(pair.forward_tail) + len(pair.reverse_tail) == len(edit.to)


def test_q5_insertion_above_reviewed_100_nt_boundary_is_refused():
    edit = Edit(kind="insert", at=1200, to="A" * 101)
    with pytest.raises(MutagenesisError, match=r"100 nt|100-nt|assembly"):
        made(edit)


def test_ordered_and_annealing_molecules_are_reported_separately():
    edit = Edit(kind="insert", at=1200, to="GGG")
    pair = made(edit)[0]
    entry = pair_to_dict(pair, edit, **CONDITIONS)
    assert entry["forward"]["tail_sequence"] == "GGG"
    assert entry["forward"]["annealing_sequence"] == pair.forward_annealing
    assert entry["melting"]["authority"].startswith("Primer3 thermodynamic screening")


def test_quikchange_protocol_cannot_be_cross_wired_into_q5_topology(monkeypatch):
    from pcr_tools.mutagenic import run

    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "strict")
    with pytest.raises(MutagenesisError, match="post_amplification_protocol must be one of"):
        run(
            {
                "template": plasmid(),
                "assay": {
                    "id": "site-directed-mutagenesis",
                    "defaults": {
                        "polymerase": "q5-sdm-screening",
                        "defaultPurpose": "cloning",
                        "purposes": ["cloning"],
                    },
                },
                "edit": {"kind": "substitute", "at": 900, "to": "TTT", "replacing": 3},
                "post_amplification_protocol": "quikchange-dpni",
            }
        )
