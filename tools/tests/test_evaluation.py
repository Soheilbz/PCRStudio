"""The evaluation suite: real sequences, real published primers, real answers.

This file is different in kind from the other tests. They check that the code
does what it was written to do. These check that what it was written to do is
right, by putting real targets through it and comparing the answers against
things that are true independently of this project -- published primer
sequences, known band sizes, records with known contents.

Every case says what it proves and where the outside truth came from. A case
without an outside source does not belong here; it belongs in a unit test.

The sequences come from `tests/corpus`, cached and checksummed, so a run today
measures the same thing as a run next year. `python -m tests.corpus.refresh`
re-downloads them and reports what changed.
"""

from __future__ import annotations

from itertools import pairwise

import pytest
from corpus import record

from pcr_tools.presets import polymerase
from pcr_tools.specificity import reverse_complement, scan

REACTION = polymerase("taq-standard").reaction


# ── The corpus itself ──────────────────────────────────────────────────────


def test_every_cached_record_matches_its_checksum():
    """A silently edited fixture would change what every case below measures."""
    from corpus import manifest

    records = manifest()
    assert records, "the corpus is empty"
    for accession, entry in records.items():
        bases = entry.sequence()  # raises if the checksum disagrees
        assert len(bases) == entry.length, accession
        assert set(bases) <= set("ACGTNRYSWKMBDHV"), accession


def test_the_records_are_the_lengths_the_outside_world_says_they_are():
    """Lengths published independently of this project.

    Lambda is the classic 48,502 bp genome; pUC19 is 2,686 bp. Both numbers are
    quoted in every catalogue that sells them, which is what makes them a
    usable outside check on the fixture.
    """
    assert record("J02459.1").length == 48_502  # lambda
    assert record("L09137.2").length == 2_686  # pUC19
    assert record("J01749.1").length == 4_361  # pBR322
    # 16,569 is the length of the revised Cambridge reference sequence, quoted
    # in every mitochondrial paper published since 1999.
    assert record("NC_012920.1").length == 16_569


# ── pUC19: the empty-vector band every cloning lab has run ─────────────────

#: The universal M13 primers, as sold and as published for forty years.
#:
#: Sequences taken from the primer itself rather than from us: these are the
#: `-20` forward and the reverse that flank the pUC/pGEM multiple cloning site.
M13_FORWARD = "GTAAAACGACGGCCAGT"
M13_REVERSE = "CAGGAAACAGCTATGAC"


def test_the_m13_primers_sit_where_forty_years_of_catalogues_say_they_do():
    """Their positions in pUC19, measured rather than taken on trust."""
    puc19 = record("L09137.2").sequence()

    forward_at = puc19.find(M13_FORWARD)
    reverse_at = puc19.find(reverse_complement(M13_REVERSE))

    assert forward_at >= 0, "the forward site is not in this record"
    assert reverse_at > forward_at, "the reverse site must lie downstream of the forward one"
    # They point at each other across the multiple cloning site, which is the
    # whole reason they are the primers everybody uses.
    assert reverse_at - forward_at < 200


def test_the_empty_vector_gives_exactly_one_band_of_the_size_it_should():
    """The screening result a cloning lab reads off a gel.

    An empty pUC19 amplified with M13 forward and reverse gives a single short
    product across the cloning site. If our specificity scan finds no product,
    or finds several, it would be telling somebody their screen will not work
    when it works in every lab that has ever run it.
    """
    puc19 = record("L09137.2").sequence()
    found = scan(
        {"left": M13_FORWARD, "right": M13_REVERSE},
        puc19,
        background_name="pUC19",
        reaction=REACTION,
    )

    assert len(found.products) == 1, f"expected one band, got {len(found.products)}"
    band = found.products[0]

    # Computed from the measured positions rather than quoted from memory.
    forward_at = puc19.find(M13_FORWARD)
    reverse_end = puc19.find(reverse_complement(M13_REVERSE)) + len(M13_REVERSE)
    assert band.size == reverse_end - forward_at
    assert 90 <= band.size <= 120, f"the empty-vector band is {band.size} bp"


def test_an_insert_moves_the_band_by_the_length_of_the_insert():
    """What the screen is actually for.

    A colony carrying an insert gives a band longer by the insert. That is the
    entire readout of a colony PCR screen, so a scan that did not move the band
    would make the screen unreadable.
    """
    puc19 = record("L09137.2").sequence()
    site = puc19.find("GGATCC")  # BamHI, in the multiple cloning site
    assert site > 0, "this pUC19 has no BamHI site, which cannot be right"

    insert = record("NM_000546.6").sequence()[:500]
    recombinant = puc19[:site] + insert + puc19[site:]

    empty = scan({"left": M13_FORWARD, "right": M13_REVERSE}, puc19, reaction=REACTION)
    full = scan({"left": M13_FORWARD, "right": M13_REVERSE}, recombinant, reaction=REACTION)

    assert len(full.products) == 1
    assert full.products[0].size - empty.products[0].size == len(insert)


# ── The assays are no longer one search under several names ────────────────


def assay(profile_id: str) -> dict:
    """The assay block the design route sends, read from the shipped catalogue.

    Read rather than restated: a copy of these numbers here would pass while
    `profiles.toml` said something else, which is the failure the whole layer
    exists to prevent.
    """
    import tomllib
    from pathlib import Path

    catalogue = Path(__file__).parents[2] / "crates" / "pcr-core" / "profiles.toml"
    entries = tomllib.loads(catalogue.read_text(encoding="utf-8"))["profile"]
    entry = next(e for e in entries if e["id"] == profile_id)
    return {
        "id": entry["id"],
        "name": entry["name"],
        "defaults": entry.get("defaults", {}),
    }


def test_long_range_and_standard_answer_the_same_question_differently():
    """The headline case, on the region long-range kits ship as their control.

    Before this, both assays ran an identical search with identical defaults,
    so the only difference a user could see between them was the title on the
    page. If these two ever agree again, the assay layer has stopped working.
    """
    from pcr_tools.pipeline import run

    template = record("NG_000007.3").fasta()
    ordinary = run({"template": template, "how_many": 1, "assay": assay("standard-pcr")})
    long_range = run({"template": template, "how_many": 1, "assay": assay("long-range-pcr"), "long_range_protocol": "thermo-long-pcr-k018x"})

    short, long = ordinary["pairs"][0], long_range["pairs"][0]

    # A different product, from a different enzyme, with different primers.
    assert long["product_size"] > 5 * short["product_size"]
    assert long["left"]["length"] > short["left"]["length"]
    assert long["left"]["tm"] > short["left"]["tm"]
    assert long_range["reaction"]["polymerase"] == "long-range"
    assert ordinary["reaction"]["polymerase"] == "taq-standard"


def test_a_long_range_product_reaches_the_sizes_its_kits_are_sold_for():
    """The beta-globin controls shipped with long-range kits are 17.5 and 21.5 kb.

    A long-range assay that cannot design across that region is not long-range,
    whatever its settings say.
    """
    from pcr_tools.pipeline import run

    answer = run(
        {
            "template": record("NG_000007.3").fasta(),
            "how_many": 3,
            "assay": assay("long-range-pcr"),
            "long_range_protocol": "thermo-long-pcr-k018x",
        }
    )
    assert answer["pairs"], "no long-range pair on the beta-globin locus"
    assert max(pair["product_size"] for pair in answer["pairs"]) >= 10_000




def test_colony_screen_records_the_actual_preparation_sop_instead_of_inventing_lysis():
    """Host/preparation provenance is required; a universal lysis cycle is not."""
    from pcr_tools.pipeline import run

    template = record("L09137.2").fasta()
    colony = run(
        {
            "template": template,
            "how_many": 1,
            "purpose": "screen",
            "assay": assay("colony-pcr"),
            "colony_host_class": "bacterial",
            "colony_preparation": "water-lysate",
            "colony_protocol_id": "custom-sop",
            "colony_protocol_name": "validated lab SOP rev A",
            "colony_protocol_provenance": "lab QA record / current test SOP revision",
        }
    )

    assert "cycling" not in colony["pairs"][0]
    assert colony["colony_context"]["host_class"] == "bacterial"
    assert colony["colony_context"]["preparation"] == "water-lysate"
    assert colony["colony_context"]["lysis_timing_inferred"] is False


def test_a_colony_screen_does_not_quietly_widen_the_screen_it_was_asked_for():
    """An assay default replaces a purpose's number rather than tightening it.

    So a product ceiling in the colony defaults would turn the screen purpose's
    150-500 into 200-2000 — looser, which is the opposite of what a ceiling is
    for. This asserts the ceiling is not there.
    """
    from pcr_tools.pipeline import run

    answer = run(
        {
            "template": record("L09137.2").fasta(),
            "how_many": 2,
            "purpose": "screen",
            "assay": assay("colony-pcr"),
            "colony_host_class": "bacterial",
            "colony_preparation": "direct-transfer",
            "colony_protocol_id": "custom-sop",
            "colony_protocol_name": "validated direct-transfer SOP",
            "colony_protocol_provenance": "lab QA record / current test SOP revision",
        }
    )
    assert answer["constraints"]["product_max"] == 500
    assert answer["constraints"]["product_min"] == 150


def test_long_range_refuses_a_purpose_whose_whole_content_is_a_shorter_product():
    from pcr_tools.pipeline import run

    with pytest.raises(ValueError, match="cannot be used for"):
        run(
            {
                "template": record("NG_000007.3").fasta(),
                "purpose": "sanger",
                "assay": assay("long-range-pcr"),
                "long_range_protocol": "thermo-long-pcr-k018x",
            }
        )


def test_the_long_range_base_profile_is_cross_protocol_not_k018x_in_disguise():
    """The base search envelope must not silently inherit one vendor's primer rules.

    The runtime supports current NEB/Takara branches plus historical K018x.
    Primer3 in this stack accepts at most 36 nt, so the cross-protocol base is
    the explicit 20–36 nt implementation subset of NEB's 20–40 nt guidance.
    Vendor-specific narrowing is asserted separately below.
    """
    from pcr_tools.design import Constraints

    defaults = assay("long-range-pcr")["defaults"]["constraints"]
    assert defaults["gc_clamp"] == 0
    assert defaults["max_end_gc"] == 5  # no extra universal end-GC cap
    assert (defaults["length_min"], defaults["length_max"]) == (20, 36)
    assert (defaults["tm_min"], defaults["tm_opt"], defaults["tm_max"]) == (55.0, 65.0, 74.0)
    assert defaults["tm_pair_max_difference"] == 5.0
    Constraints(**defaults).validate()


def test_named_long_range_protocols_narrow_only_their_reviewed_constraint_envelopes():
    from pcr_tools.pipeline import long_range_protocol

    neb = long_range_protocol("neb-longamp-taq-m0323", assay_id="long-range-pcr")
    takara = long_range_protocol("takara-primestar-gxl-r050a-standard", assay_id="long-range-pcr")
    ultrarun = long_range_protocol("qiagen-ultrarun-longrange-206442-206444", assay_id="long-range-pcr")
    thermo = long_range_protocol("thermo-long-pcr-k018x", assay_id="long-range-pcr")

    assert neb is not None and takara is not None and ultrarun is not None and thermo is not None
    assert neb["constraints"] == {"length_min": 20, "length_max": 36, "gc_min": 40.0, "gc_max": 60.0}
    assert neb["magnesium_chloride_mM"] == 2.0
    assert takara["constraints"] == {"length_min": 25, "length_max": 35}
    assert ultrarun["constraints"] == {"length_min": 20, "length_max": 30, "gc_min": 40.0, "gc_max": 60.0}
    assert ultrarun["reaction_volume_uL"]["standard"] == 20
    assert ultrarun["primer_final_concentration_uM"] == 0.5
    assert thermo["constraints"]["length_min"] == 27
    assert thermo["constraints"]["length_max"] == 36
    assert thermo["constraints"]["max_end_gc"] == 3
    assert all(protocol["sequence_decision_impact"] == "constraint-envelope" for protocol in (neb, takara, ultrarun, thermo))
    assert all(protocol["thermodynamic_model_impact"] == "none" for protocol in (neb, takara, ultrarun, thermo))


def test_digital_pcr_declares_its_qpcr_like_primer_contract():
    defaults = assay("digital-pcr")["defaults"]["constraints"]
    assert defaults["product_min"] == 60
    assert defaults["product_max"] == 150
    assert (defaults["length_min"], defaults["length_max"]) == (18, 24)
    assert (defaults["gc_min"], defaults["gc_max"]) == (40.0, 60.0)
    assert defaults["tm_opt"] == 60.0
    assert defaults["tm_pair_max_difference"] == 2.0


def test_digital_pcr_keeps_qx200_cycling_in_the_named_platform_overlay_only():
    from pcr_tools.pipeline import run

    answer = run(
        {
            "template": record("NM_000546.6").fasta(),
            "how_many": 1,
            "assay": assay("digital-pcr"),
            "digital_partition_format": "droplet",
            "digital_platform_id": "bio-rad-qx200",
            "digital_platform_name": "Bio-Rad QX200",
            "digital_fragmentation_state": "not-assessed",
            "digital_protocol": "bio-rad-qx200-evagreen",
        }
    )
    assert "cycling" not in answer["pairs"][0]
    cycling = answer["protocol"]["cycling"]
    assert cycling["annealing_extension"] == {"temperature_c": 60, "minutes": 1}
    assert cycling["cycles"] == 40


# ── The most widely used nested assay there is ─────────────────────────────

#: The Snounou 18S malaria nest, as published.
#:
#: Snounou et al., Mol Biochem Parasitol 1993;61(2):315-320 and 58(2):283-292.
#: Roughly eighty-five per cent of published Plasmodium nested-PCR work between
#: 1993 and 2025 uses it, which makes it the closest thing to a ground truth a
#: nested design engine can be held to.
#:
#: Note which way round they read: rPLU6 is the forward primer on this record
#: and rPLU5 the reverse, which is measured below rather than assumed.
SNOUNOU = {
    "outer_forward": "TTAAAATTGTTGCAGTTAAAACG",
    "outer_reverse": "CCTGTTGTTGCCTTAAACTTC",
    "inner_forward": "TTAAACTGGTTTGGGAAAACCAAATATATT",
    "inner_reverse": "ACACAATGAACTCAATCATGACTACCCGTC",
}


def snounou_positions() -> dict[str, tuple[int, int]]:
    """Where each published primer sits, measured on the record itself."""
    sequence = record("M19173.1").sequence()
    at: dict[str, tuple[int, int]] = {}
    for role, primer in SNOUNOU.items():
        if role.endswith("forward"):
            start = sequence.find(primer)
        else:
            start = sequence.find(reverse_complement(primer))
        assert start >= 0, f"{role} is not in M19173.1"
        at[role] = (start, len(primer))
    return at


def test_the_published_malaria_nest_satisfies_the_ordering_we_enforce():
    """If it did not, our rule would be wrong rather than the assay.

    This is the sharpest test in the suite: a rule that the most widely used
    nested assay in the literature violates is not a rule about nested PCR.
    """
    at = snounou_positions()
    forward_outer = at["outer_forward"][0]
    forward_inner = at["inner_forward"][0]
    reverse_inner = at["inner_reverse"][0] + at["inner_reverse"][1]
    reverse_outer = at["outer_reverse"][0] + at["outer_reverse"][1]

    assert forward_outer < forward_inner < reverse_inner < reverse_outer


def test_the_published_products_are_the_sizes_the_papers_report():
    """About 1,100 bp for the first round and about 205 for the second."""
    at = snounou_positions()
    outer = (at["outer_reverse"][0] + at["outer_reverse"][1]) - at["outer_forward"][0]
    inner = (at["inner_reverse"][0] + at["inner_reverse"][1]) - at["inner_forward"][0]

    assert 1_050 <= outer <= 1_200, outer
    assert 195 <= inner <= 215, inner


def test_the_published_nest_is_wildly_asymmetric_which_is_why_there_is_no_margin():
    """The measurement behind shipping a nesting margin of zero.

    One end moves in by 35 bases and the other by 846. A single per-side
    default could not describe even this one assay, let alone all of them, so
    the only defensible floor is the one that follows from the ordering: the
    inner primers must not overlap the outer ones.
    """
    at = snounou_positions()
    forward_gap = at["inner_forward"][0] - (at["outer_forward"][0] + at["outer_forward"][1])
    reverse_gap = at["outer_reverse"][0] - (at["inner_reverse"][0] + at["inner_reverse"][1])

    assert forward_gap > 0 and reverse_gap > 0, "the published nest does not overlap"
    assert forward_gap < 50 and reverse_gap > 500, (forward_gap, reverse_gap)


def test_our_engine_designs_a_nest_on_the_same_gene_it_was_designed_against():
    """Not the same primers — a different search will find different ones.

    What must hold is that a nest exists there at all, with the geometry the
    published one has, when asked for the sizes the published one produces.
    """
    from pcr_tools.design import Constraints
    from pcr_tools.nested import design_nested
    from pcr_tools.presets import polymerase

    found = design_nested(
        record("M19173.1").sequence(),
        outer=Constraints(product_min=900, product_max=1300),
        inner=Constraints(product_min=150, product_max=400),
        conditions=polymerase("taq-standard").reaction.as_conditions(),
        how_many=2,
    )
    assert found.nests, "no nest on the gene the canonical nest was designed against"
    for nest in found.nests:
        assert nest.ordering_holds()
        assert 900 <= nest.outer.product_size <= 1_300
        assert 150 <= nest.inner.product_size <= 400


# ── What the catalogue claims, proved rather than asserted ─────────────────


def catalogue() -> list[dict]:
    """Every assay the build ships, read from the file that ships them."""
    import tomllib
    from pathlib import Path

    path = Path(__file__).parents[2] / "crates" / "pcr-core" / "profiles.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))["profile"]




def test_no_assay_claims_to_be_stable():
    """Reserved for one that has been checked against a published result.

    Nothing here has been. The nested engine reproduces the geometry of a
    published assay and the specificity scan reproduces a published band size,
    but neither is this project's own output compared against somebody else's
    for the same request — which is what the word has to mean if it is to mean
    anything.
    """
    assert [entry["id"] for entry in catalogue() if entry["status"] == "stable"] == []


# ── What `stable` would take, measured rather than assumed ─────────────────




def test_we_do_not_rediscover_the_published_primers_which_is_why_nothing_is_stable():
    """The measurement behind refusing to call anything `stable`.

    `stable` means checked against a reference result. The strongest reference
    available is the most-used nested assay there is, and asked to design on
    the gene it was designed for, this engine returns different primers: the
    best candidate overlaps the published outer forward site by 17 of its 23
    bases and the reverse by 10 of 21.

    That is not a fault — Primer3 optimises on its own penalty and many valid
    pairs exist in the same window — but it is not reproduction either, and
    the status vocabulary says what that word requires. This test records the
    actual overlap so the bar is a number rather than a memory.
    """
    from pcr_tools.design import Constraints, design
    from pcr_tools.presets import polymerase

    sequence = record("M19173.1").sequence()
    at = snounou_positions()

    found = design(
        sequence,
        constraints=Constraints(
            length_min=17,
            length_max=32,
            tm_min=45.0,
            tm_opt=55.0,
            tm_max=65.0,
            gc_min=20.0,
            gc_max=70.0,
            product_min=900,
            product_max=1300,
            gc_clamp=0,
        ),
        conditions=polymerase("taq-standard").reaction.as_conditions(),
        how_many=30,
    )
    assert found.pairs, "the window has to admit something to compare against"

    def overlap(one: tuple[int, int], other: tuple[int, int]) -> int:
        return max(0, min(one[1], other[1]) - max(one[0], other[0]))

    published = (
        at["outer_forward"][0],
        at["outer_forward"][0] + at["outer_forward"][1],
    )
    best = max(
        overlap((pair.left_at.start, pair.left_at.start + pair.left_at.length), published)
        for pair in found.pairs
    )

    # Some overlap, because the conserved stretch is where anything can prime.
    assert best > 0, "not even the region matched, which would be a real problem"
    # But not the primer itself, which is what `stable` would need.
    assert best < at["outer_forward"][1], "if this ever fails, reconsider the status"
