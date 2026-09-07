"""What the thermodynamics layer promises.

The numbers asserted here are Primer3's own, checked against oligos whose
behaviour is documented rather than against whatever the code happened to
return the first time it ran.
"""

from __future__ import annotations

import primer3
import pytest

from pcr_tools.thermo import (
    SequenceError,
    analyse,
    clean,
    count_overlapping,
    gc_percent,
    melting_temperature,
    pair_dimer,
    reverse_complement,
    salt_correction_for_conditions,
)

#: The M13 forward sequencing primer. In every catalogue, and a fair check that
#: the model is wired up the way everyone else's is.
M13_FORWARD = "GTAAAACGACGGCCAGT"

#: Two oligos that are the reverse complement of each other, so they must form
#: the most stable duplex a pair can.
SELF_PAIR_A = "ATGCATGCATGCATGCATGC"
SELF_PAIR_B = "GCATGCATGCATGCATGCAT"


class TestCleaning:
    def test_digits_are_refused_at_the_thermodynamic_boundary(self):
        # GenBank coordinates must be extracted by intake before this layer;
        # dropping them here would make direct callers disagree with the main
        # parser and could change coordinates/oligo content silently.
        with pytest.raises(SequenceError, match="formatting symbols"):
            clean("  1 atgc atgc\n 9 gggg  ")

    def test_an_empty_sequence_says_so(self):
        with pytest.raises(SequenceError, match="empty"):
            clean("   \n  ")

    def test_ambiguity_codes_are_named_rather_than_silently_dropped(self):
        with pytest.raises(SequenceError) as raised:
            clean("ATGCRYKM")
        message = str(raised.value)
        # Dropping them would change the answer without telling anyone.
        for code in ("K", "M", "R", "Y"):
            assert code in message

    def test_protein_gets_a_useful_complaint(self):
        with pytest.raises(SequenceError, match="not A, C, G or T"):
            clean("MKVLAAGIVG")


class TestComposition:
    def test_gc_is_a_percentage_of_the_whole(self):
        assert gc_percent("GGCC") == 100.0
        assert gc_percent("ATAT") == 0.0
        assert gc_percent("ATGC") == 50.0






def test_low_level_primer3_controls_are_explicit_not_library_defaults(monkeypatch):
    import pcr_tools.thermo as thermo

    captured = {}

    class FakeThermoAnalysis:
        def set_thermo_args(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(thermo, "ThermoAnalysis", FakeThermoAnalysis)
    thermo._analysis({"mv_conc": 50.0, "dv_conc": 1.5, "dntp_conc": 0.8, "dna_conc": 200.0})

    assert captured["temp_c"] == 37.0
    assert captured["max_loop"] == 30
    assert captured["max_nn_length"] == 60
    assert captured["output_structure"] is False
    assert captured["temp_only"] == 0
    assert captured["dmso_conc"] == 0.0
    assert captured["formamide_conc"] == 0.0
    assert captured["annealing_temp_c"] == -10.0


class TestReverseComplement:
    def test_plain_bases_are_complemented_and_reversed(self):
        assert reverse_complement("GTAAAACGACGGCCAGT") == "ACTGGCCGTCGTTTTAC"

    def test_lowercase_survives_the_fast_path(self):
        assert reverse_complement("acgt") == "acgt"

    def test_an_ambiguity_code_becomes_the_set_it_still_could_be(self):
        # R is A or G, so on the other strand it is T or C: Y, not R.
        # Complementing only ACGTN used to leave codes untouched, so a motif
        # search across strands missed every site an input code sat in.
        assert reverse_complement("ACGTR") == "YACGT"
        assert reverse_complement("RYKMSWBDHVN") == "NBDHVWSKMRY"


class TestCounting:
    def test_overlapping_matches_are_all_counted(self):
        # str.count finds "AAAAA" twice in seven As where there are three
        # starts; counting non-overlapping runs under-reports repeated sites.
        assert count_overlapping("AAAAAAA", "AAAAA") == 3
        assert count_overlapping("ACGTACGT", "ACGT") == 2
        assert count_overlapping("ACGT", "AAAAA") == 0


class TestMeltingTemperature:
    def test_m13_lands_where_a_catalogue_puts_it(self):
        # Primer3's own model under standard conditions.
        assert 50.0 < melting_temperature(M13_FORWARD) < 60.0

    def test_gc_rich_melts_higher_than_at_rich_of_the_same_length(self):
        assert melting_temperature("GCGCGCGCGCGCGCGCGCGC") > melting_temperature(
            "ATATATATATATATATATAT"
        )

    def test_more_salt_raises_it(self):
        # Cations screen the backbone charge, so the duplex holds together
        # longer. If this ever inverts, the conditions are not being passed on.
        assert melting_temperature(M13_FORWARD, mv_conc=100.0) > melting_temperature(
            M13_FORWARD, mv_conc=20.0
        )


class TestAnalyse:
    def test_it_reports_the_oligo_it_was_given(self):
        report = analyse("  gtaaaacgacggccagt ")
        assert report.sequence == M13_FORWARD
        assert report.length == 17
        assert report.gc_percent == pytest.approx(52.9, abs=0.1)

    def test_energies_are_in_kcal_not_cal(self):
        # primer3-py reports cal/mol; a protocol quotes kcal/mol. Getting this
        # wrong makes every energy look a thousand times too stable.
        report = analyse(M13_FORWARD)
        assert -50.0 < report.self_dimer.dg < 5.0
        assert -50.0 < report.hairpin.dg < 5.0

    def test_a_designed_hairpin_is_found_and_a_flat_oligo_is_not(self):
        # A stem-loop: two arms that pair, with a loop between them.
        hairpin = analyse("GGGGCCCCTTTTTTGGGGCCCC")
        flat = analyse("ATATATATATATATATATAT")
        assert hairpin.hairpin.dg < flat.hairpin.dg


class TestPairs:
    def test_reverse_complements_bind_each_other_strongly(self):
        strong = pair_dimer(SELF_PAIR_A, SELF_PAIR_B)
        weak = pair_dimer("AAAAAAAAAAAAAAAAAAAA", "AAAAAAAAAAAAAAAAAAAA")
        assert strong.found
        assert strong.dg < weak.dg

    def test_a_bad_sequence_names_which_primer_it_was(self):
        with pytest.raises(SequenceError, match="right primer"):
            pair_dimer(M13_FORWARD, "NOTDNA")


# ── The 3' end, which decides where extension starts ───────────────────────


def test_a_gc_rich_three_prime_end_grips_harder_than_an_at_rich_one():
    """The direction, which two earlier versions of this got backwards.

    Against the primer itself it measured a self-dimer. Against the whole
    primer's complement it measured the entire duplex, which is dominated by
    overall GC content — so a primer that was GC-rich everywhere *except* its
    3' end came out looking like the one with the strongest 3' end, which is
    the opposite of true and the opposite of useful.
    """
    gc_ending = analyse("ATATATATATATATGCGCGC")
    at_ending = analyse("GCGCGCGCGCGCGCATATAT")

    assert gc_ending.three_prime_dg < at_ending.three_prime_dg


def test_it_measures_the_last_five_bases_and_nothing_else():
    """Two primers differing only outside the last five must agree.

    This is what separates measuring the 3' end from measuring the molecule.
    """
    from pcr_tools.thermo import THREE_PRIME_BASES

    assert THREE_PRIME_BASES == 5
    one = analyse("AAAAAAAAAAAAAAACTGCA")
    other = analyse("GCGCGCGCGCGCGCGCTGCA")
    assert one.sequence[-5:] == other.sequence[-5:]
    assert one.three_prime_dg == other.three_prime_dg


def test_it_ranks_primers_the_same_way_primer3_does():
    """A different reference and so a different scale, but the same ordering.

    Primer3 computes its own end stability during the search and the search
    uses it. If our number disagreed about which primer has the stickier end,
    we would be printing a contradiction of the thing that picked the primer.
    """
    import primer3
    from corpus import record

    designed = primer3.bindings.design_primers(
        {"SEQUENCE_ID": "t", "SEQUENCE_TEMPLATE": record("NM_000546.6").sequence()},
        {
            "PRIMER_NUM_RETURN": 6,
            "PRIMER_PRODUCT_SIZE_RANGE": [[200, 900]],
            "PRIMER_MIN_THREE_PRIME_DISTANCE": 20,
        },
    )

    pairs = []
    for index in range(designed["PRIMER_PAIR_NUM_RETURNED"]):
        primer = designed[f"PRIMER_LEFT_{index}_SEQUENCE"]
        pairs.append((designed[f"PRIMER_LEFT_{index}_END_STABILITY"], primer))
    assert len(pairs) >= 4, "not enough primers to compare an ordering"

    # Primer3's number rises as the end gets less stable; ours falls.
    by_primer3 = [primer for _, primer in sorted(pairs)]
    by_ours = [
        primer for _, primer in sorted(pairs, key=lambda entry: -analyse(entry[1]).three_prime_dg)
    ]
    assert by_primer3 == by_ours
