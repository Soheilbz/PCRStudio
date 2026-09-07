"""Four core oligos over six required regions, optional LF/LB, and their geometry.

Almost nothing here is about melting temperatures. A LAMP set is a shape: six
required target regions in a fixed order, two composite core oligos built by
joining region-derived segments back to front, and up to one optional loop
primer on each side that must sit strictly between its neighbours. Every way this goes wrong produces oligos that look entirely
reasonable — right length, right composition, right temperature — and a reaction
that does nothing.

So what is tested is the shape: that each oligo is built from the regions it
should be, in the order it should be, on the strand it should be; that the loop
primers touch neither of their neighbours; and that the arithmetic which decides
whether a set can exist at all is checked before any search rather than
discovered by finding nothing.
"""

from __future__ import annotations

import pytest
from corpus import record

from pcr_tools.loop_set import (
    AT_RICH,
    AT_RICH_AT_OR_BELOW,
    DUPLEX_BELOW_HOLD,
    END_BASES,
    END_STABILITY,
    F2_B2_SPAN,
    GC_RICH,
    GC_RICH_AT_OR_ABOVE,
    HOLD,
    LONGEST_RUN,
    LOOP_SPAN,
    NORMAL,
    PCRSTUDIO_EVIDENCE_2026_GEOMETRY,
    PRIMEREXPLORER_V5_GEOMETRY,
    LoopSetError,
    adjust,
    candidates,
    check_geometry,
    duplex_ceiling,
    interactions,
    is_palindromic,
    longest_run,
    oligos,
    primerexplorer_v5_end_dg,
    run,
    set_to_dict,
    sets,
    smallest_amplicon,
    windows_for,
)
from pcr_tools.presets import polymerase
from pcr_tools.thermo import end_stability, gc_percent, reverse_complement

CONDITIONS = polymerase("rpa").reaction.as_conditions()


def template() -> str:
    return record("NM_000546.6").sequence()[:2000]


@pytest.fixture(scope="module")
def found():
    made, _windows, counted = sets(template(), conditions=CONDITIONS, how_many=4)
    assert made, f"no set on a 2 kb template: {counted}"
    return made


# ── The shape of the ordered LAMP oligos ──────────────────────────────────


def test_the_composite_primers_are_built_back_to_front(found):
    """FIP is 5'-F1c-F2-3', and the order is the whole mechanism.

    Only the F2 half anneals to the template. The F1c half is a tail that is
    not on the template at all and becomes a primer later, folding back against
    the F1 copy on the strand this oligo makes. Built the other way round it is
    an oligo of the right length and composition that primes nothing.
    """
    sequence = template()
    for one in found:
        made = {oligo.name: oligo for oligo in oligos(sequence, one)}

        f2 = sequence[one.forward.outer.start : one.forward.outer.end]
        f1 = sequence[one.forward.inner.start : one.forward.inner.end]
        assert made["FIP"].sequence == reverse_complement(f1) + f2
        assert made["FIP"].sequence.endswith(f2), "the annealing half must be at the 3' end"

        b1c = sequence[one.backward.inner.start : one.backward.inner.end]
        b2c = sequence[one.backward.outer.start : one.backward.outer.end]
        assert made["BIP"].sequence == b1c + reverse_complement(b2c)
        assert made["BIP"].sequence.endswith(reverse_complement(b2c))


def test_the_annealing_segment_starts_at_the_seam_not_the_midpoint(found):
    """The seam sits where F1c ends, and F1c need not be half the oligo.

    What is measured as binding has to be exactly the segment that anneals:
    FIP's tail is all of F1c and its binding segment all of F2, and nothing
    makes those two lengths equal. Slicing at the midpoint quoted a melting
    temperature for a stretch that is neither the tail nor the primer.
    """
    sequence = template()
    for one in found:
        made = {oligo.name: oligo for oligo in oligos(sequence, one)}

        f1c_length = len(
            reverse_complement(sequence[one.forward.inner.start : one.forward.inner.end])
        )
        fip = made["FIP"]
        assert fip.tail_length == f1c_length
        assert (
            fip.sequence[fip.tail_length :]
            == sequence[one.forward.outer.start : one.forward.outer.end]
        ), "past the seam there is nothing but F2"

        bip = made["BIP"]
        assert bip.tail_length == len(sequence[one.backward.inner.start : one.backward.inner.end])


def test_the_outer_primers_are_on_the_strands_that_face_each_other(found):
    """F3 reads forward and B3 reads back, which is what closes the product."""
    sequence = template()
    for one in found:
        made = {oligo.name: oligo for oligo in oligos(sequence, one)}
        assert made["F3"].sequence == sequence[one.f3.start : one.f3.end]
        assert made["B3"].sequence == reverse_complement(sequence[one.b3.start : one.b3.end])


def test_the_two_loop_primers_are_on_opposite_strands(found):
    """Derived rather than assumed, and they are not the same choice twice.

    The loop FIP makes carries plus-strand sequence and the loop BIP makes
    carries its complement, so LF is the reverse complement of its interval
    while LB is the interval as it reads.
    """
    sequence = template()
    for one in found:
        made = {oligo.name: oligo for oligo in oligos(sequence, one)}
        if one.forward.loop:
            interval = sequence[one.forward.loop.start : one.forward.loop.end]
            assert made["LF"].sequence == reverse_complement(interval)
        if one.backward.loop:
            interval = sequence[one.backward.loop.start : one.backward.loop.end]
            assert made["LB"].sequence == interval


def test_a_loop_primer_touches_neither_of_its_neighbours(found):
    """The exclusion that is structural rather than a preference.

    An LF overlapping F2 is by construction the reverse complement of FIP's own
    F2 half; one overlapping F1 is complementary to its F1c half. Either is a
    perfect dimer with FIP that the design created deliberately.
    """
    for one in found:
        if one.forward.loop:
            assert one.forward.loop.start >= one.forward.outer.end
            assert one.forward.loop.end <= one.forward.inner.start
        if one.backward.loop:
            assert one.backward.loop.start >= one.backward.inner.end
            assert one.backward.loop.end <= one.backward.outer.start


def test_a_loop_primer_is_not_a_dimer_with_its_own_composite(found):
    """The consequence of the rule above, checked as a measurement.

    Rather than trusting the coordinates, this reads the two oligos and
    requires that neither contains the other's reverse complement — which is
    what an overlap would produce.
    """
    sequence = template()
    for one in found:
        made = {oligo.name: oligo for oligo in oligos(sequence, one)}
        for loop, composite in (("LF", "FIP"), ("LB", "BIP")):
            if loop not in made:
                continue
            other = made[composite].sequence
            assert made[loop].sequence not in other
            assert reverse_complement(made[loop].sequence) not in other


def test_primerexplorer_v5_figure_1_4_coordinates_match_loop_geometry_convention():
    # PrimerExplorer V5 Figure 1.4, primer set 1 (1-based inclusive display):
    # F2 628–646, F1c 668–689, B1c 709–729, B2 751–769. Converted to
    # Python half-open coordinates, the V5 loop-distance convention is 40 bp
    # on each side. Locking an official generated set prevents strand-label
    # ambiguity from silently shifting the geometry by an inner-primer length.
    from pcr_tools.loop_set import Candidate, _backward_halves, _forward_halves

    def c(start: int, length: int, tm: float) -> Candidate:
        return Candidate(start=start, length=length, tm=tm, gc=55.0, end_dg=-5.0)

    f2 = c(627, 19, 60.88)
    f1c = c(667, 22, 65.68)
    b1c = c(708, 21, 64.31)
    b2 = c(750, 19, 59.31)

    forward, capped_f, _pruned_f = _forward_halves(
        {f2.start: [f2]}, {f1c.start: [f1c]}, {}, (40, 60), 10
    )
    backward, capped_b, _pruned_b = _backward_halves(
        {b2.start: [b2]}, {b1c.start: [b1c]}, {}, (40, 60), 10
    )
    assert capped_f is capped_b is False
    assert [half.span for half in forward] == [40]
    assert [half.span for half in backward] == [40]


def test_the_eight_regions_are_in_order_along_the_plus_strand(found):
    """The order is the design; nothing else about a set makes sense without it."""
    for one in found:
        placed = [one.f3.end, one.forward.outer.start]
        if one.forward.loop:
            placed += [one.forward.loop.start]
        placed += [
            one.forward.inner.start,
            one.backward.inner.start,
        ]
        if one.backward.loop:
            placed += [one.backward.loop.start]
        placed += [one.backward.outer.start, one.b3.start]
        assert placed == sorted(placed), placed


def test_every_set_carries_at_least_four_oligos_and_at_most_six(found):
    sequence = template()
    for one in found:
        made = oligos(sequence, one)
        assert 4 <= len(made) <= 6
        names = {oligo.name for oligo in made}
        assert {"F3", "FIP", "BIP", "B3"} <= names


# ── The arithmetic that decides whether a set could exist ──────────────────


def test_an_unreachable_amplicon_floor_is_named_before_any_search():
    """Because "no sets found" there would send somebody looking at their DNA.

    Two loops and two stems have to fit end to end, so the shortest possible
    product is fixed by arithmetic. The published 120-base minimum is not
    reachable with tight loops and long stems, and that is a contradiction in
    the numbers rather than a search that failed.
    """
    floor = smallest_amplicon(NORMAL, (40, 60))
    assert floor == 40 * 2 + NORMAL.inner.length_min * 2

    with pytest.raises(LoopSetError, match="arithmetic rather than a search"):
        check_geometry(NORMAL, (100, floor - 1), (40, 60))


def test_a_four_primer_core_is_not_refused_when_no_loop_primer_can_fit():
    # LF/LB are optional. A tight loop geometry may remove loop-primer candidates
    # but must not invalidate the four-primer LAMP core by itself.
    check_geometry(NORMAL, (120, 180), (NORMAL.outer.length_max, 60))


def test_the_shipped_numbers_describe_a_set_that_could_exist():
    """A check on the defaults themselves rather than on any request."""
    from pcr_tools.loop_set import AMPLICON

    for windows in (NORMAL, AT_RICH, GC_RICH):
        check_geometry(windows, AMPLICON, LOOP_SPAN)


# ── The parameter set, chosen and reported ─────────────────────────────────


def test_the_parameter_set_follows_the_template_rather_than_a_default():
    """One held temperature cannot serve every composition.

    An AT-rich target cannot reach the ordinary window at any sensible length
    and a GC-rich one overshoots it, so the set is picked from the template and
    said out loud — a design produced under a different set from the one
    somebody assumed has temperatures that do not mean what they think.
    """
    at_rich = "AT" * 400 + "ATTTAAATTTAAA" * 20
    gc_rich = "GC" * 400 + "GGGCCCGGGCCC" * 20

    assert gc_percent(at_rich) <= AT_RICH_AT_OR_BELOW
    assert windows_for(at_rich).id == "at-rich"
    assert gc_percent(gc_rich) >= GC_RICH_AT_OR_ABOVE
    assert windows_for(gc_rich).id == "gc-rich"
    assert windows_for(template()).id == "normal"
    assert windows_for("G" * 60 + "A" * 40).id == "gc-rich", "exactly 60% GC is GC-rich in the current V5 manual"


def test_automatic_judgment_uses_iupac_gc_interval_instead_of_counting_ambiguity_as_at():
    from pcr_tools.loop_set import target_gc_interval

    assert target_gc_interval("A" * 90 + "N" * 10) == pytest.approx((0.0, 10.0))
    assert windows_for("A" * 90 + "N" * 10).id == "at-rich"
    assert windows_for("G" * 70 + "N" * 30).id == "gc-rich"
    with pytest.raises(LoopSetError, match="Automatic Judgment is ambiguous"):
        windows_for("G" * 50 + "N" * 10 + "A" * 40)
    assert windows_for("G" * 50 + "N" * 10 + "A" * 40, "normal").id == "normal"


def test_automatic_judgment_fails_closed_when_iupac_uncertainty_crosses_a_profile_boundary():
    ambiguous = "A" * 50 + "N" * 50
    with pytest.raises(LoopSetError, match="Automatic Judgment is ambiguous"):
        windows_for(ambiguous)
    assert windows_for(ambiguous, "normal").id == "normal"


def test_a_parameter_set_this_does_not_know_lists_the_ones_it_does():
    with pytest.raises(LoopSetError, match="not a parameter set"):
        windows_for(template(), "isothermal-ish")


@pytest.mark.parametrize(
    "windows",
    [
        {"outer": {"length_min": 18.5}},
        {"outer": {"tm_min": float("nan")}},
        {"gc_min": 101.0},
        {"loop_span": [20.5, 40]},
    ],
)
def test_custom_numeric_windows_refuse_implicit_truncation_or_nonfinite_values(windows):
    with pytest.raises(LoopSetError, match=r"(integer|finite|percentage|shortest)"):
        adjust(NORMAL, windows)


@pytest.mark.parametrize("windows", [[], "normal", 42])
def test_custom_windows_must_be_an_object(windows):
    with pytest.raises(LoopSetError, match="object"):
        adjust(NORMAL, windows)


def test_asking_for_a_parameter_set_overrides_the_template():
    assert windows_for(template(), "at-rich").id == "at-rich"


def test_the_result_says_which_set_was_used_and_where_it_came_from():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "how_many": 1,
        }
    )
    chosen = out["parameter_set"]
    assert chosen["id"] == "normal"
    assert "composition" in chosen["chosen_from"]
    assert chosen["why"]


# ── What each candidate had to satisfy ─────────────────────────────────────








def test_the_end_stability_threshold_is_measured_over_six_bases_not_five():
    """The length it was published against, and the two disagree.

    Measured on one oligo: -2.93 over five bases and -4.28 over six. Checked
    against the same -4.0 threshold those give opposite answers, so a
    threshold applied to the wrong length is a different threshold.
    """
    oligo = "ACGTACGTACGTACGTACGT"
    over_five = end_stability(oligo, 5, **CONDITIONS)
    over_six = end_stability(oligo, 6, **CONDITIONS)
    assert over_five != over_six
    assert (over_five <= END_STABILITY) != (over_six <= END_STABILITY)


def test_loop_primer_uses_the_published_v5_loop_end_stability_threshold(monkeypatch):
    import pcr_tools.loop_set as lamp

    # Isolate the end-stability policy from Tm/GC so a -3 kcal/mol terminal
    # 6-mer is accepted by the V5 loop screen (-2) but rejected by the
    # regular critical-end screen (-4).
    monkeypatch.setattr(lamp, "primerexplorer_v5_tm", lambda _sequence: 60.0)
    monkeypatch.setattr(lamp, "primerexplorer_v5_end_dg", lambda _sequence: -3.0)
    neutral = lamp.Window(tm_min=None, tm_max=None, length_min=18, length_max=18)
    sequence = "ACGT" * 20

    regular = lamp.candidates(
        sequence, neutral, lamp.NORMAL, CONDITIONS, primes_from="end"
    )
    loop = lamp.candidates(
        sequence, neutral, lamp.NORMAL, CONDITIONS, primes_from="end",
        end_stability_threshold=lamp.LOOP_END_STABILITY,
    )

    assert not regular
    assert loop
    assert lamp.END_STABILITY == -4.0
    assert lamp.LOOP_END_STABILITY == -2.0


def test_primerexplorer_end_dg_api_refuses_any_window_other_than_six_bases():
    from pcr_tools.loop_set import primerexplorer_v5_end_dg

    assert primerexplorer_v5_end_dg("TGCTAA") == pytest.approx(-4.49, abs=0.005)
    with pytest.raises(LoopSetError, match="exactly 6"):
        primerexplorer_v5_end_dg("TGCTA")
    with pytest.raises(LoopSetError, match="exactly 6"):
        primerexplorer_v5_end_dg("TGCTAAC")


def test_primerexplorer_v5_end_dg_matches_manual_figure_1_10_reference_outputs():
    # PrimerExplorer V5 Manual Figure 1.10 reports 5′/3′ terminal-six-base
    # ΔG values for these six region sequences. This locks the public numeric
    # reference rather than only testing our own formula against itself.
    reference = {
        "TGCTAACGCAGTCAGGCA": (-4.49, -6.25),
        "GGGTGCGCATAGAAATTGC": (-6.85, -4.56),
        "AATGCGCTCATCGTCATCC": (-5.73, -4.76),
        "GCAGTACCGGCATAACCAAGCC": (-4.98, -5.85),
        "GCTAGCAGCACGCCATAG": (-5.23, -4.07),
        "GCCTCTTGCGGGATATCGTCC": (-5.93, -6.04),
    }
    for sequence, (expected_5p, expected_3p) in reference.items():
        assert primerexplorer_v5_end_dg(sequence[:END_BASES]) == pytest.approx(expected_5p, abs=0.005)
        assert primerexplorer_v5_end_dg(sequence[-END_BASES:]) == pytest.approx(expected_3p, abs=0.005)


def test_primerexplorer_v5_tm_matches_the_manual_figure_1_10_reference_outputs():
    from pcr_tools.loop_set import primerexplorer_v5_tm

    # PrimerExplorer V5 Manual Figure 1.10, primer set ID 1. These public
    # reference outputs constrain compatibility without pretending to know the
    # proprietary implementation.
    reference = {
        "TGCTAACGCAGTCAGGCA": 60.91,
        "GGGTGCGCATAGAAATTGC": 59.11,
        "AATGCGCTCATCGTCATCC": 59.84,
        "GCAGTACCGGCATAACCAAGCC": 65.71,
        "GCTAGCAGCACGCCATAG": 59.71,
        "GCCTCTTGCGGGATATCGTCC": 64.55,
    }
    errors = [abs(primerexplorer_v5_tm(sequence) - expected) for sequence, expected in reference.items()]
    assert max(errors) < 0.1


# ── What the result says ───────────────────────────────────────────────────


def test_a_composite_reports_its_binding_half_apart_from_the_whole_oligo(found):
    """The whole oligo's temperature describes a molecule that does not exist yet.

    FIP and BIP run near 80 °C while the reaction is held near 65, because half
    of each is a tail with nothing to bind. Quoting that as the oligo's melting
    temperature invites setting a block that no isothermal reaction has.
    """
    entry = set_to_dict(template(), found[0], NORMAL, **CONDITIONS)
    composites = [one for one in entry["oligos"] if one["composite"]]
    assert len(composites) == 2

    for oligo in composites:
        assert "anneals" in oligo
        assert oligo["anneals"]["tm"] < oligo["tm"]
        assert oligo["sequence"].endswith(oligo["anneals"]["sequence"])
        # And nearer the temperature the reaction is actually held at.
        assert abs(oligo["anneals"]["tm"] - HOLD) < abs(oligo["tm"] - HOLD)


def test_the_order_sheet_quotes_the_binding_half_for_a_composite():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "how_many": 1,
        }
    )
    by_name = {oligo["name"]: oligo for entry in out["sets"] for oligo in entry["oligos"]}
    for line in out["order_sheet"]:
        oligo = by_name[line["name"].rsplit("_", 1)[-1]]
        if oligo["composite"]:
            assert line["tm"] == oligo["anneals"]["tm"]
            assert "not the whole oligo" in line["note"]
        else:
            assert line["tm"] == oligo["tm"]




def test_a_named_lamp_kit_protocol_is_returned_as_one_bound_record():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "neb-e1700",
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert protocol["kit_id"] == "E1700"
    assert protocol["primer_concentrations_uM"] == {
        "FIP": 1.6,
        "BIP": 1.6,
        "F3": 0.2,
        "B3": 0.2,
        "LoopF": 0.4,
        "LoopB": 0.4,
    }
    assert protocol["reaction_volume_uL"] == 25
    assert protocol["hold_temperature_c"] == 65
    assert protocol["hold_time_min"] == 30
    assert protocol["sequence_decision_impact"] == "none"
    assert protocol["carryover_prevention"]["included"] is False


@pytest.mark.parametrize(
    ("protocol_id", "kit_id", "loop_uM", "hold_c", "hold_min"),
    [
        ("neb-e1708", "E1708", 0.4, 65, 30),
        ("neb-l4401", "L4401", 0.4, 65, 30),
        ("neb-m1708", "M1708", 0.4, 65, 30),
        ("neb-m1800", "M1800", 0.4, 65, 30),
        ("neb-m1804", "M1804", 0.4, 65, 30),
        ("neb-m1712", "M1712", 0.4, 65, 20),
        ("neb-m9204", "M9204", 0.4, 65, 20),
        ("neb-m9205", "M9205", 0.4, 65, 20),
    ],
)
def test_reviewed_lamp_protocols_keep_their_own_concentrations_and_hold(
    protocol_id, kit_id, loop_uM, hold_c, hold_min
):
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": protocol_id,
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert protocol["kit_id"] == kit_id
    assert protocol["primer_concentrations_uM"]["LoopF"] == loop_uM
    assert protocol["hold_temperature_c"] == hold_c
    assert protocol["hold_time_min"] == hold_min
    assert protocol["sequence_decision_impact"] == "none"


def test_thermo_superscript_iv_preserves_protocol_range_and_dual_substrate_authority():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "thermo-a5180x",
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert protocol["kit_id"] == "A51801/A51802/A51803"
    assert protocol["primer_concentrations_uM"]["LoopF"] == 0.4
    assert protocol["hold_temperature_c"] == 65
    assert protocol["hold_time_range_min"] == [15, 30]
    assert "hold_time_min" not in protocol
    assert protocol["supports_dna"] is True
    assert protocol["supports_rna"] is True
    assert protocol["carryover_prevention"]["included"] is False
    assert protocol["post_inactivation"] == "95 °C for 2 min in the cited real-time and endpoint workflows"
    assert protocol["sequence_decision_impact"] == "none"


def test_nippon_ne6041_preserves_fluorescence_only_dna_recipe_without_invented_rt():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "nippon-ne6041",
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert protocol["kit_id"] == "NE6041/NE6043"
    assert protocol["primer_concentrations_uM"]["LoopF"] == 0.8
    assert protocol["hold_temperature_range_c"] == [60, 68]
    assert protocol["hold_time_min"] == 30
    assert protocol["supports_dna"] is True
    assert protocol["supports_rna"] is False
    assert protocol["recommended_readouts"] == ["fluorescence"]
    assert any("not intended for real-time turbidity" in note for note in protocol["readout_notes"])
    assert protocol["sequence_decision_impact"] == "none"


def test_nippon_ne6041_turbidity_is_a_source_backed_hard_incompatibility():
    with pytest.raises(LoopSetError, match="conflicts with the reviewed named protocol"):
        run(
            {
                "template": template(),
                "assay": {"id": "lamp", "name": "LAMP"},
                "lamp_protocol": "nippon-ne6041",
                "lamp_readout": "turbidity",
                "how_many": 1,
            }
        )


def test_neb_m9205_preserves_glycerol_free_rt_and_optional_udg_authority():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "neb-m9205",
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert protocol["kit_id"] == "M9205"
    assert "Glycerol-free" in protocol["reverse_transcriptase"]
    assert "M0439" in protocol["reverse_transcriptase"]
    assert protocol["carryover_prevention"]["included"] is False
    assert "0.7 mM dUTP" in protocol["carryover_prevention"]["chemistry"]
    assert protocol["sequence_decision_impact"] == "none"


def test_eiken_dna_protocol_keeps_a_range_instead_of_inventing_one_hold():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "eiken-lmp204",
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert "hold_temperature_c" not in protocol
    assert "hold_time_min" not in protocol
    assert protocol["hold_temperature_range_c"] == [60, 65]
    assert protocol["hold_time_range_min"] == [30, 60]
    assert protocol["primer_concentrations_uM"]["LoopF"] == 0.8


def test_eiken_dried_dna_reagent_keeps_its_own_60_to_67_degree_range():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "eiken-lmp207",
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert protocol["kit_id"] == "LMP207"
    assert protocol["hold_temperature_range_c"] == [60, 67]
    assert protocol["hold_time_range_min"] == [30, 60]
    assert protocol["primer_concentrations_uM"]["LoopF"] == 0.8
    assert protocol["supports_rna"] is False
    assert any("separate cDNA" in note for note in protocol["sample_compatibility_notes"])


def test_eiken_dried_rna_dna_reagent_keeps_range_and_one_step_rt_authority():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "eiken-lmp247",
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert protocol["kit_id"] == "LMP247"
    assert protocol["hold_temperature_range_c"] == [60, 67]
    assert protocol["hold_time_range_min"] == [30, 60]
    assert protocol["primer_concentrations_uM"]["LoopF"] == 0.8
    assert protocol["supports_dna"] is True
    assert protocol["supports_rna"] is True
    assert protocol["carryover_prevention"]["included"] is False
    assert any("Calcein" in note for note in protocol["readout_notes"])


def test_protocol_overlay_does_not_change_the_selected_genomic_lamp_set():
    common = {"template": template(), "assay": {"id": "lamp", "name": "LAMP"}, "how_many": 1}
    baseline = run(common)

    def genomic_signature(result):
        return [
            [(oligo["name"], oligo["sequence"]) for oligo in one["oligos"]]
            for one in result["sets"]
        ]

    expected = genomic_signature(baseline)
    for protocol_id in (
        "neb-m1712",
        "neb-l4401",
        "neb-m1804",
        "neb-m9205",
        "thermo-a5180x",
        "nippon-ne6041",
        "eiken-lmp207",
        "eiken-lmp247",
    ):
        with_protocol = run({**common, "lamp_protocol": protocol_id})
        assert genomic_signature(with_protocol) == expected


def test_named_protocol_readout_compatibility_is_advisory_not_a_sequence_gate():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "neb-m1804",
            "lamp_readout": "fluorescence",
            "how_many": 1,
        }
    )
    review = out["protocol"]["readout_compatibility"]
    assert review["status"] == "review-required"
    assert out["sets"]


def test_m1712_retains_its_hnb_readout_caveat():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "neb-m1712",
            "lamp_readout": "colorimetric",
            "how_many": 1,
        }
    )
    assert any("hydroxynaphthol blue" in note.lower() for note in out["protocol"]["readout_notes"])


def test_named_protocol_diagnostics_do_not_claim_proprietary_master_mix_thermodynamics():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "neb-m1712",
            "how_many": 1,
        }
    )
    assert "generic Bst" in out["reaction"]["context_role"]
    assert "proprietary master-mix ionic composition" in out["reaction"]["context_note"]
    assert "role-specific" in out["reaction"]["oligo_concentration_model"]


def test_lamp_does_not_invent_a_kit_protocol():
    out = run({"template": template(), "assay": {"id": "lamp", "name": "LAMP"}, "how_many": 1})
    assert "protocol" not in out


def test_circular_lamp_target_is_refused_in_the_worker_contract_too():
    with pytest.raises(LoopSetError, match="circular target topology"):
        run({"template": template(), "circular": True})


def test_an_unknown_lamp_protocol_is_refused():
    with pytest.raises(ValueError, match="lamp_protocol"):
        run({"template": template(), "lamp_protocol": "guess"})


def test_every_oligo_in_a_set_works_at_one_temperature(found):
    """Which is what makes the spread matter more than any single figure."""
    for one in found:
        assert one.spread() <= 8.0, one.spread()


def test_optional_loop_primers_survive_selection_without_overriding_interaction_risk(found):
    """Loop acceleration is useful, but optional LF/LB must not outrank safety.

    The search keeps no-loop and bounded loop alternatives until set-level
    interaction ranking. Selected candidates may therefore have zero, one or
    two loops; the important invariant is that useful loop-containing designs
    remain available without becoming a pre-interaction hard preference.
    """
    assert any(one.loops() > 0 for one in found)
    assert all(0 <= one.loops() <= 2 for one in found)




# ── The selected LAMP oligos against each other ───────────────────────────


def test_a_deliberately_complementary_pair_is_flagged():
    """Two oligos that are each other's complement have nowhere else to be.

    A perfect duplex melts far above the ceiling, which sits ten degrees under
    the hold by the same argument as the pair engine's structure ceiling --
    and in a reaction with no melting step there is nothing to take it apart
    again.
    """
    assert duplex_ceiling() == HOLD - DUPLEX_BELOW_HOLD
    sequence = "ACGTCGATCGTACGTAGCTA"
    out = interactions({"F3": sequence, "B3": reverse_complement(sequence)}, **CONDITIONS)
    assert out["checked"] == 1
    assert out["found"] == 1, out["note"]
    serious = out["serious"][0]
    assert {serious["a"], serious["b"]} == {"F3", "B3"}
    assert serious["tm"] >= duplex_ceiling()




def test_the_result_carries_the_dimer_screen_next_to_its_off_target_scan():
    """Surfaced where the other screening sections live, once per set."""
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "how_many": 1,
        }
    )
    entry = out["sets"][0]
    section = entry["interactions"]
    names = {oligo["name"] for oligo in entry["oligos"]}
    flagged = {pair for one in section["serious"] for pair in (one["a"], one["b"])}
    assert flagged <= names


@pytest.mark.parametrize("policy", ["strict", "development"])
@pytest.mark.parametrize(
    "override",
    [
        {"outer": {"tm_min": NORMAL.outer.tm_min - 1}},
        {"outer": {"length_max": NORMAL.outer.length_max + 1}},
        {"gc_min": NORMAL.gc_min - 1},
        {"f2_b2_span": [F2_B2_SPAN[0] - 1, F2_B2_SPAN[1]]},
    ],
)
def test_reviewed_lamp_envelope_cannot_be_widened_by_policy_mode(monkeypatch, policy, override):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", policy)
    with pytest.raises(LoopSetError, match="cannot be widened"):
        adjust(NORMAL, override)


def test_named_e1700_preserves_its_exact_rt_lamp_hold_and_legacy_authority_label():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "neb-e1700",
            "from_rna": True,
            "how_many": 1,
        }
    )
    step = out["reverse_transcription"]
    assert step["authority_status"] == "neb-e1700-dna-rna"
    assert step["hold"] == {"celsius": 65, "seconds": 30 * 60}
    assert step["one_step"] is True


@pytest.mark.parametrize(
    ("protocol_id", "seconds"),
    [
        ("neb-e1708", 30 * 60),
        ("neb-l4401", 30 * 60),
        ("neb-m1708", 30 * 60),
        ("neb-m1800", 30 * 60),
        ("neb-m1804", 30 * 60),
        ("neb-m1712", 20 * 60),
        ("neb-m9204", 20 * 60),
        ("neb-m9205", 20 * 60),
        ("eiken-lmp244", 60 * 60),
    ],
)
def test_named_rt_lamp_protocols_supply_only_their_own_reviewed_hold(protocol_id, seconds):
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": protocol_id,
            "from_rna": True,
            "how_many": 1,
        }
    )
    step = out["reverse_transcription"]
    assert step["one_step"] is True
    assert step["hold"]["seconds"] == seconds
    assert step["authority_status"].startswith(protocol_id)


def test_thermo_rt_lamp_branch_preserves_the_reviewed_time_range_without_inventing_one_hold():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "thermo-a5180x",
            "from_rna": True,
            "how_many": 1,
        }
    )
    step = out["reverse_transcription"]
    assert step["one_step"] is True
    assert step["hold"] is None
    assert step["authority_status"] == "thermo-a5180x-rt-lamp-range-only"
    assert "range" in step["note"]


def test_nippon_ne6041_refuses_an_rna_request_before_design():
    with pytest.raises(LoopSetError, match="DNA-only"):
        run(
            {
                "template": template(),
                "assay": {"id": "lamp", "name": "LAMP"},
                "lamp_protocol": "nippon-ne6041",
                "from_rna": True,
                "how_many": 1,
            }
        )


def test_eiken_lmp244_is_rna_only_under_reviewed_vendor_authority():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "eiken-lmp244",
            "from_rna": True,
            "how_many": 1,
        }
    )
    protocol = out["protocol"]
    assert protocol["kit_id"] == "LMP244/LMP245/LMP246"
    assert protocol["supports_dna"] is False
    assert protocol["supports_rna"] is True
    assert protocol["primer_concentrations_uM"]["LoopF"] == 0.8
    assert protocol["hold_temperature_c"] == 63
    assert protocol["hold_time_min"] == 60


def test_rna_only_eiken_lmp244_refuses_a_dna_template_request_before_design():
    with pytest.raises(LoopSetError, match="RNA-only"):
        run(
            {
                "template": template(),
                "assay": {"id": "lamp", "name": "LAMP"},
                "lamp_protocol": "eiken-lmp244",
                "how_many": 1,
            }
        )


def test_eiken_lmp247_rt_branch_keeps_vendor_range_without_inventing_one_hold():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "lamp_protocol": "eiken-lmp247",
            "from_rna": True,
            "how_many": 1,
        }
    )
    step = out["reverse_transcription"]
    assert step["one_step"] is True
    assert step["hold"] is None
    assert step["authority_status"] == "eiken-lmp247-rt-lamp-range-only"
    assert "range" in step["note"]


def test_dna_only_eiken_protocol_refuses_an_rna_request_before_design():
    with pytest.raises(LoopSetError, match="DNA-only"):
        run(
            {
                "template": template(),
                "lamp_protocol": "eiken-lmp204",
                "from_rna": True,
                "how_many": 1,
            }
        )


def test_generic_rt_lamp_handoff_has_no_inferred_temperature_or_duration():
    out = run(
        {
            "template": template(),
            "assay": {"id": "lamp", "name": "LAMP"},
            "from_rna": True,
            "how_many": 1,
        }
    )
    step = out["reverse_transcription"]
    assert step["authority_status"] == "rt-isothermal-chemistry-unresolved"
    assert step["hold"] is None
    assert step["one_step"] is None

# ── Evidence-2026 profiles and LAMP-native specificity regressions ─────────


def test_unchecked_generic_specificity_cannot_rank_as_a_clean_zero_hit_scan():
    from pcr_tools.loop_set import _generic_off_target_rank

    unresolved = _generic_off_target_rank({"checked": False, "classification": "indexed-validation-required"})
    clean = _generic_off_target_rank({"checked": True, "product_count": 0, "site_count": 0})
    assert clean < unresolved


def test_large_pasted_background_is_refused_not_silently_substituted(monkeypatch):
    from pcr_tools import loop_set, screen
    from pcr_tools.specificity import Contig

    # Keep the regression tiny while exercising the raw-input scope boundary.
    monkeypatch.setattr(loop_set, "LAMP_RAW_BACKGROUND_DIRECT_MAX_BASES", 10)
    monkeypatch.setattr(
        screen,
        "contigs_for",
        lambda request, *, template, name="": ([Contig("pasted-scope", "ACGTACGTACG")], False, None),
    )

    def direct_scan_must_not_run(*args, **kwargs):
        raise AssertionError("oversized pasted LAMP background reached per-candidate direct scanning")

    monkeypatch.setattr(screen, "oligos", direct_scan_must_not_run)
    with pytest.raises(loop_set.LoopSetError, match="will not silently assume"):
        loop_set.run(
            {
                "template": template(),
                "assay": {"id": "lamp", "name": "LAMP"},
                "background": ">scope\nACGTACGTACG",
                "how_many": 1,
            }
        )


def test_lamp_generic_proxy_excuses_expected_products_only_on_template_self_scan():
    from pcr_tools.loop_set import _lamp_generic_intended_linear_products

    sequence = _unique_synthetic_template()
    one = _synthetic_set_for_topology()
    sizes, products = _lamp_generic_intended_linear_products(
        sequence, one, template_only=True
    )

    # This synthetic topology intentionally carries no loop primers. The two
    # forward-facing core sites (F3/F2) oppose the two reverse-facing core sites
    # (B2/B3), so the generic linear proxy has exactly four intended pairings.
    assert len(products) == 4
    assert sizes == [len(product) for product in products]
    assert sequence[one.start : one.end] in products
    assert len(set(products)) == len(products)

    # Public LAMP background is an exclusion scope: no target product/site is
    # silently excused in a panel the assay was explicitly asked to keep silent.
    assert _lamp_generic_intended_linear_products(
        sequence, one, template_only=False
    ) == ([], [])


def _synthetic_set_for_topology():
    from pcr_tools.loop_set import Candidate, Half, Set

    f2 = Candidate(start=35, length=18, tm=60.0, gc=50.0, end_dg=-5.0)
    f1 = Candidate(start=80, length=20, tm=65.0, gc=50.0, end_dg=-5.0)
    b1 = Candidate(start=105, length=20, tm=65.0, gc=50.0, end_dg=-5.0)
    b2 = Candidate(start=150, length=18, tm=60.0, gc=50.0, end_dg=-5.0)
    f3 = Candidate(start=10, length=18, tm=60.0, gc=50.0, end_dg=-5.0)
    b3 = Candidate(start=175, length=18, tm=60.0, gc=50.0, end_dg=-5.0)
    return Set(
        forward=Half(outer=f2, inner=f1, loop=None, span=45),
        backward=Half(outer=b2, inner=b1, loop=None, span=43),
        f3=f3,
        b3=b3,
    )


def _unique_synthetic_template():
    # Deterministic non-repetitive DNA so the six expected regions dominate the
    # finite-background topology test instead of a homopolymer creating many sites.
    bases = "ACGTGCAATGCTTAGCGTACGATCGTACCTGATCGAGTCCGATGCTAGCTACGATGGCATTCGATCGTGAACCTGCGTATCGATGCTACCGTAGCTGATCGTACGGTACATCGATGCTAGTCGATCGGATCAGTACGCTAGCATCGTACGATGCTTACGGTACGATCGTAGCTACGATCGTACCTGAGCTAGCATCGATGCTAGCAT"
    assert len(bases) >= 200
    return bases[:220]


def test_geometry_profile_is_versioned_and_does_not_silently_widen_v5():
    from pcr_tools.loop_set import (
        PCRSTUDIO_EVIDENCE_2026_GEOMETRY,
        PRIMEREXPLORER_V5_GEOMETRY,
        geometry_profile_for,
    )

    assert geometry_profile_for(None) == PRIMEREXPLORER_V5_GEOMETRY
    assert geometry_profile_for("pcrstudio-evidence-2026") == PCRSTUDIO_EVIDENCE_2026_GEOMETRY
    _used, _span, _loop, outer, _middle, _overruled = adjust(
        NORMAL, None, geometry_profile=PCRSTUDIO_EVIDENCE_2026_GEOMETRY
    )
    assert outer == (0, 60)
    with pytest.raises(LoopSetError):
        adjust(NORMAL, {"outer_gap": [0, 40]}, geometry_profile=PRIMEREXPLORER_V5_GEOMETRY)






def test_round_robin_core_partner_budget_reaches_all_jobs_before_second_pass():
    from pcr_tools.loop_set import _round_robin_partner_schedule

    jobs = [[10, 11, 12], [20, 21, 22], [30, 31, 32]]
    scheduled = list(_round_robin_partner_schedule(jobs, 5))
    assert scheduled == [(0, 10), (1, 20), (2, 30), (0, 11), (1, 21)]

def test_uncomputed_pairwise_structure_does_not_rank_as_best_evidence():
    from pcr_tools.loop_set import _thermodynamic_structure_rank

    computed = {
        "interactions": {
            "classification": "diagnostic-only-no-universal-pass-fail-threshold",
            "max_predicted_tm_c": 18.0,
            "most_favourable_dg_kcal_mol": -5.0,
        },
        "oligos": [
            {"self_dimer_tm": None, "hairpin_tm": None},
        ],
    }
    uncomputed = {
        "interactions": {
            "classification": "not-computed",
            "max_predicted_tm_c": None,
            "most_favourable_dg_kcal_mol": None,
        },
        "oligos": [
            {"self_dimer_tm": None, "hairpin_tm": None},
        ],
    }

    assert _thermodynamic_structure_rank(computed) < _thermodynamic_structure_rank(uncomputed)


def test_evidence_profile_outer_gap_preference_is_separate_from_validity():
    from pcr_tools.loop_set import PCRSTUDIO_EVIDENCE_2026_GEOMETRY

    assert PCRSTUDIO_EVIDENCE_2026_GEOMETRY.valid_outer_gap == (0, 60)
    assert PCRSTUDIO_EVIDENCE_2026_GEOMETRY.preferred_outer_gap == (40, 60)


def test_tttt_linker_is_explicit_and_kept_separate_from_target_tail():
    sequence = _unique_synthetic_template()
    one = _synthetic_set_for_topology()
    made = {item.name: item for item in oligos(sequence, one, inner_linker="TTTT")}
    fip = made["FIP"]
    bip = made["BIP"]
    assert fip.sequence == fip.target_tail_sequence + "TTTT" + sequence[35:53]
    assert bip.sequence == bip.target_tail_sequence + "TTTT" + reverse_complement(sequence[150:168])
    assert fip.tail_length == len(fip.target_tail_sequence) + 4
    assert fip.linker_sequence == "TTTT"


def test_six_region_background_topology_detects_exact_and_mismatch_tolerant_loci():
    from pcr_tools.loop_set import _lamp_background_topology_audit
    from pcr_tools.specificity import Contig

    sequence = _unique_synthetic_template()
    one = _synthetic_set_for_topology()
    exact = _lamp_background_topology_audit(
        sequence,
        one,
        [Contig("exact", sequence)],
        f2_b2_span=(120, 180),
        loop_span=(40, 60),
        outer_gap=(0, 20),
        middle_gap=(0, 100),
    )
    assert exact["risk_class"] == 3
    assert exact["exact_locus_count_lower_bound"] >= 1

    mutated = list(sequence)
    # Internal F2 substitution, away from its critical 3' terminal base.
    mutated[40] = {"A": "C", "C": "G", "G": "T", "T": "A"}[mutated[40]]
    mismatch = _lamp_background_topology_audit(
        sequence,
        one,
        [Contig("near", "".join(mutated))],
        f2_b2_span=(120, 180),
        loop_span=(40, 60),
        outer_gap=(0, 20),
        middle_gap=(0, 100),
    )
    assert mismatch["risk_class"] == 2
    assert mismatch["exact_locus_count_lower_bound"] == 0
    assert mismatch["terminal_intact_locus_count_lower_bound"] >= 1


def test_no_result_diagnostic_accepts_orientation_specific_candidate_counters():
    from pcr_tools.loop_set import _why_nothing

    counted = {
        "joined": 0,
        "forward_outer_regions": 0,
        "backward_outer_regions": 0,
        "forward_inner_regions": 3,
        "backward_inner_regions": 3,
        "forward_halves": 0,
        "backward_halves": 0,
    }
    assert "outer region" in _why_nothing(counted, NORMAL)


def test_six_region_background_topology_is_orientation_invariant():
    from pcr_tools.loop_set import _lamp_background_topology_audit
    from pcr_tools.specificity import Contig

    sequence = _unique_synthetic_template()
    one = _synthetic_set_for_topology()
    reverse_background = reverse_complement(sequence)
    out = _lamp_background_topology_audit(
        sequence,
        one,
        [Contig("reverse-copy", reverse_background)],
        f2_b2_span=(120, 180),
        loop_span=(40, 60),
        outer_gap=(0, 20),
        middle_gap=(0, 100),
    )
    assert out["risk_class"] == 3
    assert out["exact_locus_count_lower_bound"] >= 1
    assert any(locus["locus_orientation"] == "reverse" for locus in out["loci"])


def test_core_pair_expansion_pool_keeps_best_and_target_wide_diversity():
    from pcr_tools.loop_set import (
        Candidate,
        Half,
        PCRSTUDIO_EVIDENCE_2026_GEOMETRY,
        _core_pair_expansion_pool,
    )

    pairs = []
    for start in range(0, 1000, 10):
        front = Half(
            outer=Candidate(start=start, length=18, tm=60.0, gc=50.0, end_dg=-5.0),
            inner=Candidate(start=start + 45, length=20, tm=65.0, gc=50.0, end_dg=-5.0),
            loop=None,
            span=45,
        )
        # Keep F2-B2 within the advanced preferred span for every synthetic core.
        behind = Half(
            outer=Candidate(start=start + 130, length=18, tm=60.0, gc=50.0, end_dg=-5.0),
            inner=Candidate(start=start + 90, length=20, tm=65.0, gc=50.0, end_dg=-5.0),
            loop=None,
            span=40,
        )
        pairs.append((front, behind))

    selected, capped = _core_pair_expansion_pool(
        pairs, NORMAL, PCRSTUDIO_EVIDENCE_2026_GEOMETRY, 20
    )
    starts = sorted(pair[0].outer.start for pair in selected)
    assert capped is True
    assert len(selected) == 20
    assert 0 in starts  # deterministic best/tie-break candidate remains represented
    assert max(starts) >= 800  # diversity tranche reaches late target coordinates


def test_bounded_search_is_reverse_complement_invariant_for_both_geometry_profiles():
    sequence = template()
    reverse = reverse_complement(sequence)
    length = len(sequence)

    def interval(candidate):
        return None if candidate is None else (candidate.start, candidate.end)
    def mirror(candidate):
        return None if candidate is None else (length - candidate.end, length - candidate.start)
    def signature(one):
        return (
            interval(one.f3), interval(one.forward.outer), interval(one.forward.loop),
            interval(one.forward.inner), interval(one.backward.inner), interval(one.backward.loop),
            interval(one.backward.outer), interval(one.b3),
        )
    def rc_signature(one):
        return (
            mirror(one.b3), mirror(one.backward.outer), mirror(one.backward.loop),
            mirror(one.backward.inner), mirror(one.forward.inner), mirror(one.forward.loop),
            mirror(one.forward.outer), mirror(one.f3),
        )

    for profile in (PRIMEREXPLORER_V5_GEOMETRY, PCRSTUDIO_EVIDENCE_2026_GEOMETRY):
        made, _windows, _counts, search = sets(
            sequence, conditions=CONDITIONS, how_many=8,
            geometry_profile=profile, include_search_meta=True,
        )
        mirrored, _windows_rc, _counts_rc, search_rc = sets(
            reverse, conditions=CONDITIONS, how_many=8,
            geometry_profile=profile, include_search_meta=True,
        )
        assert not search["complete"] and not search_rc["complete"], "the regression must exercise bounded search"
        assert [signature(one) for one in made] == [rc_signature(one) for one in mirrored]
        assert search["orientation_policy"] == "lexicographically-canonical-target-orientation"
        assert search_rc["orientation_policy"] == search["orientation_policy"]
        assert search["orientation_canonicalized"] != search_rc["orientation_canonicalized"]


def test_bounded_search_mirrors_excluded_coordinates_with_reverse_complement_input():
    from pcr_tools.thermo import reverse_complement

    sequence = template()
    excluded = [(250, 30), (1100, 50)]
    mirrored_excluded = [
        (len(sequence) - (start + length), length)
        for start, length in excluded
    ]

    forward, _w1, _c1, meta1 = sets(
        sequence, conditions=CONDITIONS, how_many=5, excluded=excluded,
        include_search_meta=True,
    )
    reverse, _w2, _c2, meta2 = sets(
        reverse_complement(sequence), conditions=CONDITIONS, how_many=5,
        excluded=mirrored_excluded, include_search_meta=True,
    )

    def signature(one):
        return (
            one.f3.start, one.forward.outer.start, one.forward.inner.start,
            one.backward.inner.start, one.backward.outer.start, one.b3.start,
        )

    def reverse_signature(one):
        n = len(sequence)
        return (
            n - one.b3.end, n - one.backward.outer.end, n - one.backward.inner.end,
            n - one.forward.inner.end, n - one.forward.outer.end, n - one.f3.end,
        )

    assert [signature(one) for one in forward] == [reverse_signature(one) for one in reverse]
    assert meta1["complete"] == meta2["complete"]


def test_lamp_target_inclusivity_audit_is_position_and_role_aware():
    from pcr_tools.align import Aligned
    from pcr_tools.fetch import Record
    from pcr_tools.loop_set import (
        INCLUSIVITY_REFERENCE_ID,
        _target_inclusivity_audit,
    )

    sequence = _unique_synthetic_template()
    one = _synthetic_set_for_topology()
    mutated = list(sequence)
    # F2 ends at coordinate 53 and its 3' extension edge is the region's right
    # edge, so changing the last F2 base must be reported as an inner terminal
    # event rather than being flattened into an undifferentiated mismatch count.
    index = one.forward.outer.end - 1
    mutated[index] = {"A": "C", "C": "G", "G": "T", "T": "A"}[mutated[index]]
    aligned = Aligned(
        records=[
            Record(INCLUSIVITY_REFERENCE_ID, "reference", sequence),
            Record("target-variant", "variant", "".join(mutated)),
        ],
        tool="mafft",
        tool_version="7.526",
        tool_role="PRIMARY",
    )

    audit = _target_inclusivity_audit(sequence, one, aligned)
    assert audit["checked"] is True
    assert audit["records_checked"] == 1
    assert audit["event_totals"]["inner_events"] == 1
    assert audit["event_totals"]["inner_terminal_3_events"] == 1
    assert audit["event_totals"]["outer_events"] == 0
    assert audit["rank_tuple"][0] == 1
    region = audit["worst_records"][0]["regions_with_events"]["F2"]
    assert region["critical_terminal_event"] is True


def test_loop_alternatives_keep_no_loop_and_bounded_candidates_for_set_level_ranking():
    from pcr_tools.loop_set import Candidate, LOOP_ALTERNATIVES_PER_HALF, _forward_halves

    def c(start: int, tm: float = 63.0, length: int = 18) -> Candidate:
        return Candidate(start=start, length=length, tm=tm, gc=50.0, end_dg=-5.0)

    outer = {0: [c(0, 60.0)]}
    inner = {50: [c(50, 65.0, 20)]}
    loop = {
        20: [c(20, 63.0)],
        22: [c(22, 62.8)],
        24: [c(24, 63.2)],
        26: [c(26, 62.5)],
        28: [c(28, 63.5)],
    }
    halves, capped, pruned = _forward_halves(
        outer, inner, loop, (40, 60), 100, loop_target_tm=63.0
    )
    assert capped is False
    assert len([half for half in halves if half.loop is not None]) == LOOP_ALTERNATIVES_PER_HALF
    assert any(half.loop is None for half in halves)
    assert pruned == 2


def test_outer_pair_topk_truncation_is_disclosed_as_bounded_search():
    _made, _windows, _counts, search = sets(
        template()[:400],
        conditions=CONDITIONS,
        how_many=8,
        geometry_profile=PRIMEREXPLORER_V5_GEOMETRY,
        include_search_meta=True,
    )
    assert search["outer_pair_truncation_used"] is True
    assert search["complete"] is False
    assert search["claim"] == "best within the evaluated bounded search set; global optimum not claimed"


def test_repeated_bounded_search_is_deterministic_for_identical_input():
    sequence = template()
    signatures = []
    metas = []
    for _ in range(2):
        made, _windows, _counts, search = sets(
            sequence, conditions=CONDITIONS, how_many=8,
            geometry_profile=PCRSTUDIO_EVIDENCE_2026_GEOMETRY, include_search_meta=True,
        )
        signatures.append([
            (
                one.f3.start, one.forward.outer.start,
                None if one.forward.loop is None else one.forward.loop.start,
                one.forward.inner.start, one.backward.inner.start,
                None if one.backward.loop is None else one.backward.loop.start,
                one.backward.outer.start, one.b3.start,
            )
            for one in made
        ])
        metas.append(search)
    assert signatures[0] == signatures[1]
    assert metas[0] == metas[1]


def test_evidence_geometry_does_not_replace_primerexplorer_thermodynamic_metric():
    from pcr_tools.loop_set import NEB_2025_LOOP_TM_REFERENCE, PE_THERMODYNAMIC_MODEL

    assert PCRSTUDIO_EVIDENCE_2026_GEOMETRY.id == "pcrstudio-evidence-2026"
    assert PE_THERMODYNAMIC_MODEL["id"] == "primerexplorer-v5-reference-output-compatible-sl98-tm-end-dg"
    assert PE_THERMODYNAMIC_MODEL["sodium_mM"] == 50.0
    assert PE_THERMODYNAMIC_MODEL["magnesium_mM"] == 4.0
    assert PE_THERMODYNAMIC_MODEL["oligo_concentration_uM"] == 0.1
    assert "not the selected kit master-mix model" in PE_THERMODYNAMIC_MODEL["role"]
    assert NEB_2025_LOOP_TM_REFERENCE == (64.0, 66.0)
    assert PCRSTUDIO_EVIDENCE_2026_GEOMETRY.preferred_loop_tm is None


@pytest.mark.parametrize(
    "raw_panel, expected",
    [
        (123, "inclusivity must be FASTA text"),
        (">empty\n", "contains no non-empty FASTA sequence"),
        (">__PCRSTUDIO_LAMP_REFERENCE__\nACGT", "is reserved by PCRStudio"),
        (">variant\nACG-T", "remove pre-existing alignment gap characters"),
    ],
)
def test_lamp_inclusivity_malformed_inputs_fail_before_alignment(raw_panel, expected):
    from pcr_tools.loop_set import LoopSetError, _prepare_target_inclusivity

    with pytest.raises(LoopSetError, match=expected):
        _prepare_target_inclusivity("ACGTACGT", raw_panel)


def test_lamp_two_mismatch_seed_discovery_matches_bruteforce_on_random_acgt_cases():
    import random
    from pcr_tools import specificity as spec

    rng = random.Random(20260902)
    for _ in range(100):
        haystack = "".join(rng.choice("ACGT") for _ in range(rng.randint(40, 120)))
        expected = "".join(rng.choice("ACGT") for _ in range(rng.randint(12, 25)))
        if len(expected) > len(haystack):
            continue
        discovered = set()
        for start in spec._candidate_window_starts(haystack, expected, 2):
            bounds = spec._mismatch_bounds(haystack[start : start + len(expected)], expected)
            if bounds is not None and bounds[0] <= 2:
                discovered.add(start)
        brute = {
            start
            for start in range(len(haystack) - len(expected) + 1)
            if sum(
                observed != wanted
                for observed, wanted in zip(
                    haystack[start : start + len(expected)], expected, strict=True
                )
            ) <= 2
        }
        assert discovered == brute


def test_low_level_sets_omitted_geometry_follows_selected_profile():
    sequence = template()

    implicit, _w1, _c1, meta1 = sets(
        sequence, conditions=CONDITIONS, how_many=5,
        geometry_profile=PCRSTUDIO_EVIDENCE_2026_GEOMETRY, include_search_meta=True,
    )
    explicit, _w2, _c2, meta2 = sets(
        sequence, conditions=CONDITIONS, how_many=5,
        geometry_profile=PCRSTUDIO_EVIDENCE_2026_GEOMETRY,
        f2_b2_span=PCRSTUDIO_EVIDENCE_2026_GEOMETRY.valid_f2_b2_span,
        loop_span=PCRSTUDIO_EVIDENCE_2026_GEOMETRY.valid_loop_span,
        outer_gap=PCRSTUDIO_EVIDENCE_2026_GEOMETRY.valid_outer_gap,
        middle_gap=PCRSTUDIO_EVIDENCE_2026_GEOMETRY.valid_middle_gap,
        include_search_meta=True,
    )

    def sig(one):
        return (
            one.f3.start, one.forward.outer.start,
            None if one.forward.loop is None else one.forward.loop.start,
            one.forward.inner.start, one.backward.inner.start,
            None if one.backward.loop is None else one.backward.loop.start,
            one.backward.outer.start, one.b3.start,
        )

    assert [sig(one) for one in implicit] == [sig(one) for one in explicit]
    assert meta1 == meta2


def test_meridian_mdx126_preserves_air_dryable_direct_blood_authority():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY
    p = LAMP_PROTOCOL_REGISTRY["meridian-mdx126"]
    assert set(p["formats"]) == {"liquid", "air-dryable"}
    assert p["direct_sample_matrices"] == ["blood-plasma-serum"]
    assert p["reaction_volume_uL"] == 25
    assert p["hold_temperature_c"] == 65
    assert p["hold_time_min"] == 60
    assert p["chemistry"]["magnesium_mM"] == 8.0


def test_takara_rr385_preserves_dna_rna_tb_green_ung_and_melt_authority():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY
    p = LAMP_PROTOCOL_REGISTRY["takara-rr385"]
    assert p["supports_dna"] is True and p["supports_rna"] is True
    assert p["recommended_readout_chemistries"] == ["tb-green"]
    assert p["hold_temperature_c"] == 63 and p["hold_time_min"] == 20
    assert p["carryover_prevention"]["included"] is True
    assert p["recommended_confirmation_modes"] == ["melt-denaturation-curve"]


def test_takara_rr385_turbidity_is_a_source_backed_hard_incompatibility():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY, LoopSetError, _readout_compatibility
    with pytest.raises(LoopSetError, match="inorganic pyrophosphatase"):
        _readout_compatibility(LAMP_PROTOCOL_REGISTRY["takara-rr385"], "turbidity")


def test_takara_rr385_pyrophosphate_turbidity_chemistry_is_hard_incompatible():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY, LoopSetError, _readout_chemistry_compatibility
    with pytest.raises(LoopSetError, match="inorganic pyrophosphatase"):
        _readout_chemistry_compatibility(LAMP_PROTOCOL_REGISTRY["takara-rr385"], "turbidity", "turbidity-pyrophosphate")


def test_m1712_hnb_is_a_source_backed_hard_incompatibility():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY, LoopSetError, _readout_chemistry_compatibility
    with pytest.raises(LoopSetError, match="poor HNB contrast"):
        _readout_chemistry_compatibility(LAMP_PROTOCOL_REGISTRY["neb-m1712"], "colorimetric", "hydroxynaphthol-blue")


def test_direct_sample_lamp_cannot_bypass_named_matrix_authority():
    from pcr_tools.loop_set import LoopSetError, _sample_scenario_compatibility
    with pytest.raises(LoopSetError, match="named reviewed protocol"):
        _sample_scenario_compatibility(None, "blood-plasma-serum", "direct-addition")


def test_direct_sample_matrix_mismatch_fails_closed():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY, LoopSetError, _sample_scenario_compatibility
    with pytest.raises(LoopSetError, match="does not carry reviewed"):
        _sample_scenario_compatibility(LAMP_PROTOCOL_REGISTRY["meridian-mdx126"], "saliva-sputum", "direct-addition")


def test_explicit_formulation_must_match_reviewed_protocol_authority():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY, LoopSetError, _formulation_compatibility
    with pytest.raises(LoopSetError, match="does not carry reviewed"):
        _formulation_compatibility(LAMP_PROTOCOL_REGISTRY["meridian-mdx126"], "lyophilized")


def test_source_bounded_bench_optimization_rejects_unreviewed_or_out_of_range_values():
    from pcr_tools.loop_set import LoopSetError, _bench_optimization, _lamp_protocol
    # MDX126 publishes an exact 8 mM baseline, not a general optimization envelope.
    mdx126 = _lamp_protocol("meridian-mdx126")
    assert mdx126 is not None
    with pytest.raises(LoopSetError, match="reviewed optimization envelope"):
        _bench_optimization({"lamp_bench_optimization": {"magnesium_mM": 8.0}}, mdx126)
    with pytest.raises(LoopSetError, match="reviewed optimization envelope"):
        _bench_optimization({"lamp_bench_optimization": {"betaine_M": 0.5}}, mdx126)

    # M9204 does publish a reviewed Mg optimization envelope (6–8 mM).
    m9204 = _lamp_protocol("neb-m9204")
    assert m9204 is not None
    assert _bench_optimization({"lamp_bench_optimization": {"magnesium_mM": 7.0}}, m9204) == {"magnesium_mM": 7.0}
    with pytest.raises(LoopSetError, match="reviewed range"):
        _bench_optimization({"lamp_bench_optimization": {"magnesium_mM": 20.0}}, m9204)


def test_readout_chemistry_broad_branch_mismatch_fails_closed():
    from pcr_tools.loop_set import LoopSetError, _readout_chemistry_compatibility
    with pytest.raises(LoopSetError, match="belongs to"):
        _readout_chemistry_compatibility(None, "turbidity", "tb-green")


def test_lamp_protocol_registry_substrate_partition_is_complete_and_exclusive():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY

    dna_only = {
        pid for pid, protocol in LAMP_PROTOCOL_REGISTRY.items()
        if protocol.get("supports_dna") is True and protocol.get("supports_rna") is False
    }
    rna_only = {
        pid for pid, protocol in LAMP_PROTOCOL_REGISTRY.items()
        if protocol.get("supports_dna") is False and protocol.get("supports_rna") is True
    }
    dual = {
        pid for pid, protocol in LAMP_PROTOCOL_REGISTRY.items()
        if protocol.get("supports_dna") is True and protocol.get("supports_rna") is True
    }

    assert len(LAMP_PROTOCOL_REGISTRY) == 72
    assert len(dna_only) == 35
    assert rna_only == {"eiken-lmp244", "jena-pcr540", "jena-pcr541", "nippon-dr0701"}
    assert len(dual) == 33
    assert dna_only | rna_only | dual == set(LAMP_PROTOCOL_REGISTRY)
    assert not (dna_only & rna_only or dna_only & dual or rna_only & dual)
    assert {"optigene-iso004", "optigene-dr004", "optigene-iso004-lyo", "meridian-mdx118"} <= dna_only
    assert all(protocol.get("formats") for protocol in LAMP_PROTOCOL_REGISTRY.values())
    assert LAMP_PROTOCOL_REGISTRY["neb-e1700"]["formats"] == ["liquid"]
    assert LAMP_PROTOCOL_REGISTRY["neb-l4401"]["formats"] == ["lyophilized"]
    assert LAMP_PROTOCOL_REGISTRY["meridian-mdx126"]["formats"] == ["liquid", "air-dryable"]


def test_takara_confirmation_authority_is_provenance_not_sequence_validation():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY, _confirmation_compatibility

    protocol = LAMP_PROTOCOL_REGISTRY["takara-rr385"]
    reviewed = _confirmation_compatibility(protocol, "melt-denaturation-curve")
    unreviewed = _confirmation_compatibility(protocol, "gel-ladder")

    assert reviewed["reviewed_for_protocol"] is True
    assert unreviewed["reviewed_for_protocol"] is False
    assert reviewed["decision_impact"] == "none"
    assert unreviewed["decision_impact"] == "none"


def test_primerexplorer_v5_automatic_judgment_exact_gc_boundaries_are_inclusive():
    assert windows_for("G" * 9 + "A" * 11) is AT_RICH
    assert windows_for("G" * 12 + "A" * 8) is GC_RICH
    assert windows_for("G" * 10 + "A" * 10) is NORMAL


def test_fixed_primer_and_mutation_anchor_filters_are_exact_and_nonmutating():
    import pcr_tools.loop_set as lamp
    c = lambda start, length=18: lamp.Candidate(start=start, length=length, tm=60.0, gc=50.0, end_dg=-5.0)
    one = lamp.Set(
        forward=lamp.Half(outer=c(25), inner=c(70, 20), loop=c(48), span=45),
        backward=lamp.Half(outer=c(150), inner=c(105, 20), loop=c(130), span=43),
        f3=c(2), b3=c(176),
    )
    sequence = ("ACGT" * 60)[:240]
    ordered = {oligo.name: oligo.sequence for oligo in lamp.oligos(sequence, one)}
    assert lamp._matches_fixed_primers(sequence, one, {"F3": ordered["F3"], "FIP": ordered["FIP"]})
    assert not lamp._matches_fixed_primers(sequence, one, {"F3": "A" * len(ordered["F3"])})
    position = lamp._mutation_anchor_coordinate(one, "fip-3p-f2")
    assert lamp._matches_mutation_anchor(one, {"anchor": "fip-3p-f2", "position": position})
    assert not lamp._matches_mutation_anchor(one, {"anchor": "fip-3p-f2", "position": position + 1})


def test_lamp_catalogue_partition_tracks_canonical_72_protocol_authority():
    from pcr_tools.loop_set import LAMP_PROTOCOL_REGISTRY
    assert len(LAMP_PROTOCOL_REGISTRY) == 72
    assert {"vazyme-rp712", "hyasen-hyb413", "hyasen-hyb414", "hyasen-hyb315"} <= set(LAMP_PROTOCOL_REGISTRY)


def test_lamp_shared_numeric_differential_corpus_matches_python_authority():
    """The same source-backed numeric corpus is executable in Python and the browser."""
    import json
    from pathlib import Path

    from pcr_tools.lamp_numeric_recipes import resolve_numeric_recipe
    from pcr_tools.registries.lamp import LAMP_PROTOCOL_REGISTRY

    root = Path(__file__).resolve().parents[2]
    corpus = json.loads((root / "contracts/chemistry/lamp-differential-corpus.json").read_text(encoding="utf-8"))
    for case in corpus["cases"]:
        protocol = case["protocol"]
        resolved = resolve_numeric_recipe(
            protocol,
            LAMP_PROTOCOL_REGISTRY.get(protocol),
            case.get("python_scenario") or {},
        )
        for key, expected in (case.get("expected_values") or {}).items():
            assert resolved["values"][key] == pytest.approx(expected), f"{case['id']}:{key}"
        unresolved = {row["id"] for row in resolved["unresolved_numeric_dependencies"]}
        assert set(case.get("expected_unresolved") or []).issubset(unresolved), case["id"]
        assert [row["id"] for row in resolved["thermal_stages"]] == case.get("expected_thermal_stage_ids", [])
        assert resolved["thermal_stage_model"] == "ordered-source-backed-only"
        assert resolved["sequence_decision_impact"] == "none"


def test_lamp_profile_selection_is_reverse_complement_invariant():
    """Whole-target Automatic Judgment depends on composition, not orientation."""
    from pcr_tools.lamp_profiles import windows_for as profile_for

    complement = str.maketrans("ACGTRYMKBDHVN", "TGCAYRKMVHDBN")
    for sequence in (
        "A" * 55 + "G" * 45,
        "A" * 50 + "G" * 50,
        "A" * 40 + "G" * 60,
        "R" * 10 + "A" * 90,
        "S" * 10 + "G" * 90,
    ):
        reverse_complement = sequence.translate(complement)[::-1]
        assert profile_for(sequence).id == profile_for(reverse_complement).id


def test_lamp_screening_thinning_is_deterministic_and_does_not_mutate_primary_order():
    """Empirical-screening diversity selection is a separate deterministic view."""
    import pcr_tools.loop_set as lamp

    def c(start: int, length: int = 18) -> lamp.Candidate:
        return lamp.Candidate(start=start, length=length, tm=60.0, gc=50.0, end_dg=-5.0)

    def s(offset: int) -> lamp.Set:
        return lamp.Set(
            forward=lamp.Half(outer=c(offset + 25), inner=c(offset + 70, 20), loop=c(offset + 48), span=45),
            backward=lamp.Half(outer=c(offset + 150), inner=c(offset + 105, 20), loop=c(offset + 130), span=43),
            f3=c(offset + 2),
            b3=c(offset + 176),
        )

    ranked = [s(0), s(2), s(20), s(45), s(70)]
    original_starts = [one.start for one in ranked]
    first = lamp._thin(ranked, 4)
    second = lamp._thin(list(ranked), 4)
    assert [one.start for one in first] == [one.start for one in second]
    assert [one.start for one in ranked] == original_starts
    assert [one.start for one in first] == [2, 22, 47, 72]
