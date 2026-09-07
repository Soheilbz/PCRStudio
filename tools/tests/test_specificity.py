"""The two layers, and the difference between them."""

from __future__ import annotations

import pytest

from pcr_tools.presets import polymerase
from pcr_tools.specificity import (
    BackgroundTooLarge,
    Contig,
    Site,
    normalise_background,
    parse_fasta,
    products_from,
    reverse_complement,
    scan,
    sites_for,
    specificity_to_dict,
)

REACTION = polymerase("taq-standard").reaction

PRIMER = "GCTAGCTTGACCTGAGGACA"
FILLER = "ATATTAGCAATTAGCAATATTAGCAATTAGCAATATTAGCAAT"


def one_contig(sequence: str) -> list[Contig]:
    return [Contig(name="test", sequence=sequence)]


def test_a_perfect_site_is_found_on_the_strand_that_would_extend_forwards():
    contigs = one_contig(FILLER + PRIMER + FILLER)
    sites = sites_for(PRIMER, "left", contigs, reaction=REACTION)
    forwards = [s for s in sites if s.orientation == "forward"]
    assert len(forwards) == 1
    assert forwards[0].mismatches == 0
    assert forwards[0].three_prime_at == len(FILLER) + len(PRIMER) - 1


def test_the_same_primer_is_found_on_the_other_strand_too():
    contigs = one_contig(FILLER + reverse_complement(PRIMER) + FILLER)
    sites = sites_for(PRIMER, "left", contigs, reaction=REACTION)
    reverses = [s for s in sites if s.orientation == "reverse"]
    assert len(reverses) == 1
    assert reverses[0].three_prime_at == len(FILLER)


def test_a_mismatch_behind_the_clamp_is_kept_and_counted():
    middle = PRIMER[:8] + ("T" if PRIMER[8] != "T" else "G") + PRIMER[9:]
    contigs = one_contig(FILLER + middle + FILLER)

    sites = sites_for(PRIMER, "left", contigs, reaction=REACTION)
    assert len(sites) == 1
    assert sites[0].mismatches == 1


def test_binding_energy_is_evaluated_at_the_requested_reaction_temperature():
    contigs = one_contig(FILLER + PRIMER + FILLER)
    at_37 = sites_for(PRIMER, "left", contigs, reaction=REACTION, temperature_c=37.0)
    at_60 = sites_for(PRIMER, "left", contigs, reaction=REACTION, temperature_c=60.0)

    # ΔG is temperature-dependent: the same duplex is less favourable at the
    # hotter PCR hold. The temperature is part of the returned contract so a
    # fixed 37 °C default cannot masquerade as the assay's screen.
    assert at_37[0].dg < at_60[0].dg
    result = scan(
        {"left": PRIMER},
        FILLER + PRIMER + FILLER,
        reaction=REACTION,
        temperature_c=60.0,
    )
    assert result.temperature_c == 60.0
    output = specificity_to_dict(result)
    assert output["temperature_c"] == 60.0
    assert output["method"]["binding_score"]["temperature_c"] == 60.0


def test_v5_discovers_terminal_region_mismatches_within_the_whole_primer_budget():
    # A mismatch near the 3-prime end remains visible. Specificity v5 does not
    # hide it behind an exact-terminal-clamp discovery rule.
    at = len(PRIMER) - 3
    broken = PRIMER[:at] + ("T" if PRIMER[at] != "T" else "G") + PRIMER[at + 1 :]
    contigs = one_contig(FILLER + broken + FILLER)

    kept = sites_for(PRIMER, "left", contigs, reaction=REACTION, max_mismatches=3)
    assert len(kept) == 1
    assert kept[0].mismatches == 1


def test_species_review_can_retain_a_terminal_mismatch_as_a_potential_site():
    broken = PRIMER[:-1] + ("T" if PRIMER[-1] != "T" else "G")
    contigs = one_contig(FILLER + broken + FILLER)

    sites = sites_for(
        PRIMER,
        "left",
        contigs,
        reaction=REACTION,
        include_terminal_mismatch=True,
    )

    assert len(sites) == 1
    assert sites[0].mismatches == 1


def test_specificity_rejects_negative_mismatch_tolerance():
    with pytest.raises(ValueError, match="at least 0"):
        sites_for(
            PRIMER,
            "left",
            one_contig(PRIMER),
            reaction=REACTION,
            max_mismatches=-1,
        )


@pytest.mark.parametrize("primer", ["", "ACGN", "ACGU", None])
def test_specificity_rejects_empty_or_non_dna_primers(primer):
    with pytest.raises(ValueError, match="specificity primer"):
        sites_for(primer, "left", one_contig(PRIMER), reaction=REACTION)


@pytest.mark.parametrize(
    ("keyword", "value", "message"),
    (
        ("max_mismatches", True, "specificity max_mismatches.*integer"),
        ("max_product", 3000.0, "max_product.*integer"),
    ),
)
def test_specificity_controls_reject_fractional_and_boolean_values(keyword, value, message):
    kwargs = {keyword: value}
    if keyword == "max_product":
        with pytest.raises(ValueError, match=message):
            products_from([], **kwargs)
    else:
        with pytest.raises(ValueError, match=message):
            sites_for(PRIMER, "left", one_contig(PRIMER), reaction=REACTION, **kwargs)


def test_specificity_rejects_a_nonfinite_binding_cutoff():
    for value in (float("nan"), 10**1000):
        with pytest.raises(ValueError, match=r"minimum.*finite"):
            sites_for(
                PRIMER,
                "left",
                one_contig(PRIMER),
                reaction=REACTION,
                min_dg=value,
            )


def test_reverse_seed_at_contig_start_cannot_use_a_negative_window():
    # In terminal-mismatch review mode, a hit at the first base must be
    # discarded explicitly rather than reaching Python's negative slicing.
    seed = reverse_complement(PRIMER)[1:]
    sites = sites_for(
        PRIMER,
        "left",
        one_contig(seed),
        reaction=REACTION,
        include_terminal_mismatch=True,
    )
    assert sites == []


def test_an_n_in_the_background_is_retained_as_a_possible_match():
    # The fast scanners map non-ACGT to A during packing, which invents binding
    # sites in assembly gaps. Here a gap stays uncertain and is never treated
    # as an observed exact base.
    with_gap = PRIMER[:10] + "N" + PRIMER[11:]
    contigs = one_contig(FILLER + with_gap + FILLER)

    sites = sites_for(PRIMER, "left", contigs, reaction=REACTION)
    assert len(sites) == 1
    assert sites[0].mismatches == 0
    assert sites[0].mismatch_upper_bound == 1
    assert sites[0].ambiguous_bases == 1


def test_an_ambiguity_inside_the_three_prime_seed_is_retained_as_possible():
    """A consensus/assembly ambiguity must not create a specificity false negative."""
    with_seed_gap = PRIMER[:-1] + "N"
    sites = sites_for(PRIMER, "left", one_contig(with_seed_gap), reaction=REACTION)

    assert len(sites) == 1
    assert sites[0].mismatches == 0
    assert sites[0].mismatch_upper_bound == 1
    assert sites[0].ambiguous_bases == 1
    assert sites[0].ambiguous_positions_from_three_prime == (1,)


def test_mismatch_topology_is_reported_from_the_actual_primer_three_prime_end():
    """Forward and reverse sites use the same primer-oriented coordinate system."""
    forward_window = PRIMER[:-1] + ("A" if PRIMER[-1] != "A" else "C")
    forward = [
        site
        for site in sites_for(
            PRIMER,
            "left",
            one_contig(forward_window),
            reaction=REACTION,
            max_mismatches=1,
        )
        if site.orientation == "forward"
    ]
    assert len(forward) == 1
    assert forward[0].mismatch_positions_from_three_prime == (1,)
    assert forward[0].mismatch_base_pairs_from_three_prime[0][0] == 1
    assert forward[0].mismatch_base_pairs_from_three_prime[0][1] == PRIMER[-1]
    assert forward[0].mismatch_base_pairs_from_three_prime[0][3] == forward_window[-1]

    reverse_expected = reverse_complement(PRIMER)
    reverse_window = ("A" if reverse_expected[0] != "A" else "C") + reverse_expected[1:]
    reverse = [
        site
        for site in sites_for(
            PRIMER,
            "right",
            one_contig(reverse_window),
            reaction=REACTION,
            max_mismatches=1,
        )
        if site.orientation == "reverse"
    ]
    assert len(reverse) == 1
    assert reverse[0].mismatch_positions_from_three_prime == (1,)
    assert reverse[0].mismatch_base_pairs_from_three_prime[0][0] == 1
    assert reverse[0].mismatch_base_pairs_from_three_prime[0][1] == PRIMER[-1]
    assert reverse[0].mismatch_base_pairs_from_three_prime[0][3] == reverse_window[0]


def test_a_possible_iupac_site_survives_zero_known_mismatch_tolerance():
    """Unknown bases cannot be allowed to hide a possible exclusion hit."""
    sites = sites_for(
        "AAAA",
        "left",
        one_contig("AAAN"),
        reaction=REACTION,
        max_mismatches=0,
        min_dg=0.0,
    )

    forward = [site for site in sites if site.orientation == "forward"]
    assert len(forward) == 1
    assert forward[0].mismatches == 0
    assert forward[0].mismatch_upper_bound == 1
    assert forward[0].ambiguous_bases == 1


def test_an_invalid_background_is_refused_instead_of_reported_clean():
    with pytest.raises(ValueError, match="background contains"):
        parse_fasta(">relative\nACGT-not-a-protein")


def test_background_digits_are_refused_in_raw_sequence():
    with pytest.raises(ValueError, match="background contains"):
        normalise_background("ACGT 1234")


def test_background_digits_are_refused_in_fasta_sequence():
    with pytest.raises(ValueError, match="background contains"):
        parse_fasta(">relative\nACGT12")


def test_background_punctuation_is_refused_instead_of_dropped():
    with pytest.raises(ValueError, match="background contains"):
        parse_fasta(">relative\nACGT-123")


def test_an_empty_fasta_record_is_refused_instead_of_dropped():
    with pytest.raises(ValueError, match=r"record.*no DNA sequence"):
        parse_fasta(">empty\n\n>real\nACGT")


def test_duplicate_fasta_record_identifiers_are_refused():
    with pytest.raises(ValueError, match=r"duplicate FASTA record identifier"):
        parse_fasta(">same\nACGT\n>same description\nTTTT")


def test_indented_fasta_headers_are_still_headers():
    assert parse_fasta("  >relative\n  ACGT")[0].name == "relative"


def test_an_rna_background_is_normalised_to_the_coding_dna_alphabet():
    assert parse_fasta(">rna\nACGU")[0].sequence == "ACGT"


def test_two_sites_facing_each_other_make_a_product_of_the_right_length():
    left = "GCTAGCTTGACCTGAGGACA"
    right = "TTGGCATCAGGTACCTAGCA"
    spacer = "ACGT" * 40
    contigs = one_contig(FILLER + left + spacer + reverse_complement(right) + FILLER)

    sites = sites_for(left, "left", contigs, reaction=REACTION) + sites_for(
        right, "right", contigs, reaction=REACTION
    )
    products = products_from(sites, max_product=3000)

    assert len(products) == 1
    # Measured 5' end to 5' end, which is what a gel shows.
    assert products[0].size == len(left) + len(spacer) + len(right)


def test_circular_sites_facing_across_the_origin_make_a_product():
    def site(role: str, at: int, orientation: str) -> Site:
        primer = "A" * 20
        return Site(
            primer=primer,
            role=role,
            contig="circle",
            three_prime_at=at,
            orientation=orientation,
            mismatches=0,
            dg=-20.0,
            tm=60.0,
        )

    sites = [
        site("left", 199, "forward"),
        site("right", 5, "reverse"),
    ]

    assert products_from(sites, max_product=100) == []
    wrapped = products_from(sites, max_product=100, circular_length=220)

    assert len(wrapped) == 1
    assert wrapped[0].size == 65
    assert wrapped[0].reverse.three_prime_at == 225


def test_sites_pointing_away_from_each_other_make_nothing():
    left = "GCTAGCTTGACCTGAGGACA"
    right = "TTGGCATCAGGTACCTAGCA"
    spacer = "ACGT" * 40
    # Reversed arrangement: they face outwards.
    contigs = one_contig(FILLER + reverse_complement(left) + spacer + right + FILLER)

    sites = sites_for(left, "left", contigs, reaction=REACTION) + sites_for(
        right, "right", contigs, reaction=REACTION
    )
    assert products_from(sites, max_product=3000) == []


def test_fasta_with_several_contigs_keeps_them_apart():
    text = f">a desc here\n{FILLER}\n{PRIMER}\n>b\n{FILLER}\n"
    contigs = parse_fasta(text)
    assert [c.name for c in contigs] == ["a", "b"]

    sites = sites_for(PRIMER, "left", contigs, reaction=REACTION)
    assert {s.contig for s in sites} == {"a"}


def test_an_empty_background_is_reported_rather_than_treated_as_clean():
    result = scan({"left": PRIMER}, "", reaction=REACTION)
    assert not result.checked
    assert "nothing was checked" in result.note


def test_a_background_too_large_says_how_large_and_what_to_use_instead():
    """A refusal that only refuses leaves somebody with nowhere to go.

    The size is derived from the constant rather than written out, because a
    test carrying its own copy of a limit is a second place for that limit to
    be wrong.
    """
    from pcr_tools.specificity import MAX_BACKGROUND_BASES

    with pytest.raises(BackgroundTooLarge) as raised:
        scan({"left": PRIMER}, "A" * (MAX_BACKGROUND_BASES + 1), reaction=REACTION)

    message = str(raised.value)
    assert f"{MAX_BACKGROUND_BASES:,}" in message, "it says where the line is"
    assert "chromosome" in message and "transcriptome" in message


# ── Off-target products, and finding all of them ───────────────────────────


def test_a_shorter_primer_further_along_is_not_skipped():
    """The early exit has to be sorted by where products end, not where primers sit.

    Those are the same thing only when every primer is the same length. A site
    five bases further along carrying a primer twelve bases shorter gives a
    *shorter* product — and sorted the wrong way, the loop stopped before
    reaching it. A missed off-target is the one direction this scan must never
    fail in: it reports a design as specific when it is not.
    """

    def site(primer: str, at: int, orientation: str) -> Site:
        return Site(
            primer=primer,
            role="left" if orientation == "forward" else "right",
            contig="c",
            three_prime_at=at,
            orientation=orientation,
            mismatches=0,
            dg=-20.0,
            tm=60.0,
        )

    sites = [
        site("A" * 20, 100, "forward"),
        # Ends at 1029, giving a 949 bp product — too long.
        site("A" * 30, 1000, "reverse"),
        # Further along, but shorter, so it ends at 1022: a 942 bp product.
        site("A" * 18, 1005, "reverse"),
    ]

    found = products_from(sites, max_product=945)
    assert [product.size for product in found] == [942]


# ── How much background this can actually take ─────────────────────────────


def test_the_cap_is_where_a_real_genome_stops_being_practical():
    """The number is a measurement, and this keeps it one.

    Thirty primers — a fifteen-pair shortlist — over a hundred megabases takes
    about half a minute, and the background holds one byte per base. The cap
    covers every plasmid, every bacterial genome, yeast, Drosophila, a plant
    chromosome and a whole transcriptome.

    It was 50 million when the cost was assumed rather than timed; the scan
    turned out to be four times faster than the assumption. If this ever needs
    revisiting, time it again rather than guessing again.
    """
    from pcr_tools.specificity import MAX_BACKGROUND_BASES

    # Comfortably above every genome somebody would sensibly paste in.
    assert MAX_BACKGROUND_BASES >= 140_000_000, "smaller than Drosophila"
    # And below the one that would take a quarter of an hour.
    assert MAX_BACKGROUND_BASES < 3_000_000_000, "a mammalian genome is not this"


def test_the_scan_stays_linear_in_the_background():
    """What makes the cap a straight line rather than a cliff.

    If this ever stopped holding, the number above would stop meaning what it
    says — so it is measured here on two sizes rather than reasoned about.
    """
    import random
    import time

    generator = random.Random(3)
    primers = {"left": "GTAAAACGACGGCCAGT", "right": "CAGGAAACAGCTATGAC"}
    reaction = polymerase("taq-standard").reaction

    timings = []
    for size in (400_000, 1_600_000):
        background = "".join(generator.choices("ACGT", k=size))
        started = time.perf_counter()
        scan(primers, background, reaction=reaction)
        timings.append(time.perf_counter() - started)

    # Four times the sequence should cost roughly four times, not sixteen.
    # Loose, because a test that timed things tightly would fail on a busy
    # machine and teach people to ignore it.
    assert timings[1] < timings[0] * 12
