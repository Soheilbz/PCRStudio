"""Designing one pair for a family, and the three rules that do the work."""

from __future__ import annotations

import random

import primer3
import pytest

from pcr_tools.degenerate import expand
from pcr_tools.presets import polymerase
from pcr_tools.universal import (
    MAX_EXACT_VARIANTS,
    AlignmentError,
    Limits,
    _cross_dimer_dg,
    _hairpin_dg,
    _tm_bounds,
    design,
    limits_from_request,
    read_alignment,
)

REACTION = polymerase("taq-standard").reaction


def family(count: int, length: int, rate: float, *, seed: int = 11) -> list[tuple[str, str]]:
    """A backbone with scattered substitutions, as isolates of one marker look."""
    rng = random.Random(seed)
    backbone = "".join(rng.choice("ACGT") for _ in range(length))
    members = []
    for index in range(count):
        r = random.Random(seed * 100 + index)
        members.append(
            (
                f"iso{index}",
                "".join(r.choice("ACGT") if r.random() < rate else b for b in backbone),
            )
        )
    return members


def test_unaligned_sequences_are_refused_with_what_to_do_about_it():
    with pytest.raises(AlignmentError, match="align"):
        read_alignment([("a", "ACGTACGT"), ("b", "ACGT")])


def test_one_sequence_is_not_a_family():
    with pytest.raises(AlignmentError, match="at least two"):
        read_alignment([("only", "ACGTACGT")])


def test_a_column_holds_what_every_sequence_puts_there():
    alignment = read_alignment([("a", "ACGT"), ("b", "ACGA")])
    assert alignment.columns[0] == frozenset("A")
    assert alignment.columns[3] == frozenset("AT")


def test_a_gap_marks_the_column_so_no_primer_crosses_it():
    alignment = read_alignment([("a", "AC-T"), ("b", "ACGT")])
    assert 2 in alignment.gapped


@pytest.mark.parametrize("bad", ["ACG!", "ACGE", "ACG1"])
def test_invalid_alignment_symbols_are_refused_instead_of_deleted_or_expanded(bad):
    with pytest.raises(AlignmentError, match="invalid symbol"):
        read_alignment([("a", bad), ("b", "ACGT")])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("length_min", 20.5, "integer"),
        ("conserved_end", -1, "negative"),
        ("max_poly_x", 0, "at least 1"),
        ("tm_spread_max", -1.0, "cannot be negative"),
    ],
)
def test_invalid_numeric_limits_are_refused_before_search(field, value, message):
    with pytest.raises(ValueError, match=message):
        Limits(**{field: value}).validate()


def test_degeneracy_above_exact_thermodynamic_limit_is_refused():
    with pytest.raises(ValueError, match=f"{MAX_EXACT_VARIANTS}-member exact"):
        Limits(max_degeneracy=MAX_EXACT_VARIANTS + 1).validate()




def test_large_mixtures_use_the_worst_concrete_member_for_structure_checks():
    primer = "W" * 5
    conditions = REACTION.as_conditions()
    expected_hairpin = round(
        min(primer3.calc_hairpin(variant, **conditions).dg for variant in expand(primer)) / 1000.0,
        2,
    )
    expected_dimer = round(
        min(
            primer3.calc_heterodimer(left, right, **conditions).dg
            for left in expand(primer)
            for right in expand(primer)
        )
        / 1000.0,
        2,
    )
    assert _hairpin_dg(primer, REACTION) == expected_hairpin
    assert _cross_dimer_dg(primer, primer, REACTION) == expected_dimer


def test_a_rare_base_can_be_dropped_when_covering_it_costs_more_than_it_buys():
    # Nine sequences agree and one does not. Covering the tenth doubles the
    # degeneracy of that column for one sequence's sake, which is sometimes
    # the wrong trade and sometimes exactly the point.
    rows = [("same", "ACGT")] * 9 + [("odd", "ACTT")]

    strict = read_alignment(rows, min_coverage=1.0)
    assert strict.columns[2] == frozenset("GT"), "covering everything covers the odd one out"

    # Nine of ten already accounts for 0.9 of the column, so the tenth is left.
    relaxed = read_alignment(rows, min_coverage=0.9, policy="coverage-threshold")
    assert relaxed.columns[2] == frozenset("G")


def test_an_ambiguity_code_widens_the_column_to_everything_it_could_be():
    """An R in an input row means A or G, so both count as seen there.

    Recording nothing instead left a column of nothing but R's reading as
    plain A — supported by nobody, and contradicting the promise that
    ambiguity widens rather than collapses.
    """
    mixed = read_alignment([("a", "ACGR"), ("b", "RCGT")])
    assert mixed.columns[0] == frozenset("AG")
    # The concrete T in that column stays too: widening adds, it never drops.
    assert mixed.columns[3] == frozenset("AGT")

    # And an all-R column yields A or G per the coverage rule, not A alone.
    every_r = read_alignment([("a", "RR"), ("b", "RR")])
    assert every_r.columns[0] == frozenset("AG")

    # With slack in the coverage the commonest base wins on its merits: the
    # two R rows each vote for an A and a G, and the plain A's outvote them.
    relaxed = read_alignment(
        [("a", "R"), ("b", "R"), ("c", "A"), ("d", "A")],
        min_coverage=0.5,
        policy="coverage-threshold",
    )
    assert relaxed.columns[0] == frozenset("A")


def test_an_identical_family_gives_plain_primers_with_no_degeneracy():
    # Two copies of the same sequence: there is nothing to cover, so buying
    # any degeneracy at all would be buying nothing.
    one = family(1, 700, 0.0, seed=3)[0][1]
    answer = design(
        [("a", one), ("b", one)],
        reaction=REACTION,
        limits=Limits(length_min=20, length_opt=20, length_max=20),
        how_many=3,
    )

    assert answer["pairs"], "an unvaried pair of sequences is the easiest case there is"
    for pair in answer["pairs"]:
        assert pair["degeneracy"] == 1
        assert pair["covers"] == 2


def test_a_varied_family_produces_degenerate_primers_that_cover_all_of_it():
    answer = design(family(6, 700, 0.10, seed=5), reaction=REACTION, how_many=4)
    assert answer["pairs"], "a family this size should have some design"

    for pair in answer["pairs"]:
        assert pair["covers"] == pair["of"], "a universal pair has to fit every sequence"
        assert pair["degeneracy"] >= 1


def test_the_degeneracy_budget_is_obeyed_and_reported():
    limits = Limits(max_degeneracy=4)
    answer = design(family(6, 700, 0.10, seed=5), limits=limits, reaction=REACTION)

    for pair in answer["pairs"]:
        assert pair["left"]["degeneracy"] <= 4
        assert pair["right"]["degeneracy"] <= 4

    reasons = {entry["reason"] for entry in answer["windows"]["rejections"]}
    assert "too degenerate" in reasons


def test_the_three_prime_end_is_conserved_in_every_primer_returned():
    conserved = 4
    limits = Limits(conserved_end=conserved)
    answer = design(family(6, 700, 0.10, seed=5), limits=limits, reaction=REACTION)

    plain = set("ACGT")
    for pair in answer["pairs"]:
        # A forward primer extends from its own last base; a reverse primer
        # from its last base too, once it has been reverse-complemented.
        assert set(pair["left"]["sequence"][-conserved:]) <= plain
        assert set(pair["right"]["sequence"][-conserved:]) <= plain


def test_a_wider_conserved_end_finds_fewer_primers_not_worse_ones():
    loose = design(family(6, 700, 0.10, seed=5), limits=Limits(conserved_end=2), reaction=REACTION)
    tight = design(family(6, 700, 0.10, seed=5), limits=Limits(conserved_end=6), reaction=REACTION)
    assert loose["windows"]["accepted"] >= tight["windows"]["accepted"]


def test_tm_spread_reference_is_diagnostic_not_a_candidate_validity_gate():
    records = family(6, 700, 0.10, seed=5)
    tight = design(records, limits=Limits(tm_spread_max=0.0), reaction=REACTION)
    loose = design(records, limits=Limits(tm_spread_max=100.0), reaction=REACTION)

    assert tight["windows"]["accepted"] == loose["windows"]["accepted"]
    assert tight["windows"]["above_tm_spread_reference"] >= loose["windows"]["above_tm_spread_reference"]
    assert tight["windows"]["tm_spread_reference_c"] == 0.0


def test_degenerate_family_tm_does_not_manufacture_a_bench_annealing_temperature(monkeypatch):
    for policy in ("strict", "development"):
        monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", policy)
        answer = design(family(6, 700, 0.10, seed=5), reaction=REACTION, how_many=2)
        for pair in answer["pairs"]:
            assert pair["annealing_temperature"] is None
            assert pair["annealing_temperature_role"] == "unresolved-bench-protocol"


def test_limits_that_cannot_hold_are_refused_before_searching():
    with pytest.raises(ValueError, match="conserved"):
        design(family(4, 400, 0.05), limits=Limits(conserved_end=30), reaction=REACTION)


def test_profile_defaults_are_applied_to_universal_designs():
    limits = limits_from_request(
        {
            "assay": {
                "id": "universal-primers",
                "defaults": {
                    "purposes": ["general", "sanger", "screen"],
                    "constraints": {
                        "length_min": 17,
                        "length_opt": 20,
                        "length_max": 27,
                        "product_min": 250,
                        "product_max": 1500,
                    },
                },
            }
        }
    )

    assert (limits.length_min, limits.length_opt, limits.length_max) == (17, 20, 27)
    assert (limits.product_min, limits.product_max) == (250, 1500)


def test_profile_purpose_mismatch_is_refused_for_universal_designs():
    with pytest.raises(ValueError, match="cannot be used for `cloning`"):
        limits_from_request(
            {
                "purpose": "cloning",
                "assay": {
                    "id": "universal-primers",
                    "defaults": {"purposes": ["general", "sanger", "screen"]},
                },
            }
        )


def test_the_funnel_accounts_for_every_window_it_looked_at():
    answer = design(family(6, 700, 0.10, seed=5), reaction=REACTION)
    windows = answer["windows"]
    rejected = sum(entry["count"] for entry in windows["rejections"])
    assert rejected + windows["accepted"] == windows["considered"]


def test_pairs_rejected_on_product_size_are_counted_not_merely_skipped():
    """A rejection nobody counts is a rejection nobody can be told about.

    The size test is the first thing every pairing meets and throws away most
    of them, so reporting it as zero made the funnel's first and largest step
    invisible.
    """
    # Narrow enough that most pairings cannot possibly fit.
    limits = Limits(product_min=120, product_max=160)
    answer = design(family(6, 700, 0.10, seed=5), limits=limits, reaction=REACTION)
    counts = answer["pair_counts"]
    assert counts["wrong_size"] > 0
    assert counts["wrong_size"] > counts["considered"]


def test_universal_release_wrapper_preserves_canonical_profile_authority(monkeypatch):
    """The wrapper must not strip server-injected profile provenance."""
    from pcr_tools import __main__ as cli

    marker = {
        "source": "pcr-core:profiles.toml",
        "profileId": "universal-primers",
        "transport": "server-injected-canonical-profile",
    }
    request = {
        "template": ">a\nACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT\n>b\nACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT\n",
        "lowercase_masking": False,
        "alignment_mode": "prealigned",
        "assay": {
            "id": "universal-primers",
            "name": "Universal Primers",
            "engine": "consensus-pair",
            "status": "available",
            "profileAuthority": marker,
            "defaults": {
                "polymerase": "taq-standard",
                "allowedPolymerases": [],
                "chemistryFamily": "standard-pcr",
                "constraints": {},
                "purposes": [],
            },
            "modifiers": [],
            "requires": [],
            "enzyme": [],
        },
    }

    monkeypatch.setattr(cli, "design_universal", lambda *args, **kwargs: {
        "engine": "consensus-pair",
        "alignment": {"sequences": 2, "columns": 44, "names": ["a", "b"], "gapped_columns": 0, "conserved_columns": 44},
        "pairs": [],
        "windows": {"considered": 0, "accepted": 0, "above_tm_spread_reference": 0, "tm_spread_reference_c": 5.0, "rejections": []},
        "pair_counts": {},
        "capped": {"sites": False, "pairs": False, "site_limit": 0, "measured_limit": 0, "search_complete": True, "note": "test"},
    })
    monkeypatch.setattr(cli, "provenance", lambda *_args, **_kwargs: {})

    result = cli.run_universal(request)
    assert result["assay"]["profile_authority"] == marker
    assert result["assay"]["chemistry_family"] == "standard-pcr"
