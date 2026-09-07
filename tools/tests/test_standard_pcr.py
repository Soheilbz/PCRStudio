"""Standard PCR, audited.

Every refusal here was a defect first. Primer3 raises `OSError` for each of
these and the worker reported it as "the tool failed" — a message that blames
the machine for a number the person could have changed, in wording taken from
Primer3's own source. The tests are written the way the audit found them: give
it the thing a real bench would give it, and check that what comes back is
something somebody can act on.
"""

from __future__ import annotations

import random
from itertools import pairwise

import pytest

import pcr_tools.pipeline as pipeline
from pcr_tools.design import MAX_PRIMER_LENGTH, Constraints
from pcr_tools.pipeline import MAX_PAIRS, run
from pcr_tools.presets import POLYMERASES, PURPOSES, Reaction, polymerase, purpose
from pcr_tools.settings import MAX_OLIGO_NAME


def sequence(length: int, seed: int = 3) -> str:
    generator = random.Random(seed)
    return "".join(generator.choice("ACGT") for _ in range(length))


TEMPLATE = sequence(900)


def _cloning_vector_fixture() -> str:
    """Circular recipient with exactly one HindIII and one PstI site."""
    raw = sequence(300, seed=1)
    return raw[:80] + "AAGCTT" + raw[86:180] + "CTGCAG" + raw[186:]


CLONING_VECTOR = _cloning_vector_fixture()


def refusal(request: dict) -> str:
    """Run it and return the sentence it refused with."""
    with pytest.raises(ValueError) as raised:
        run({"template": TEMPLATE, **request})
    return str(raised.value)


# ── Constraints Primer3 would refuse, refused here with a reason ──────────


COLONY_CONTEXT = {
    "colony_host_class": "bacterial",
    "colony_preparation": "water-lysate",
    "colony_protocol_id": "custom-sop",
    "colony_protocol_name": "test-SOP",
    "colony_protocol_provenance": "lab QA record / current test SOP revision",
}


def test_a_primer_longer_than_primer3_designs_names_the_limit():
    # Measured against the binary, not the manual: the manual says 35 and the
    # binary accepts 36.
    message = refusal({"constraints": {"length_max": MAX_PRIMER_LENGTH + 1}})
    assert str(MAX_PRIMER_LENGTH) in message
    assert "melting-temperature model" in message


def test_the_documented_ceiling_itself_is_accepted():
    # A longer stretch of the same seeded random sequence than the module
    # template. The ordinary-PCR SantaLucia correction keeps this in the
    # documented reaction range; the point here is that `MAX_PRIMER_LENGTH`
    # itself is accepted and yields designs, and for that the template has to
    # be big enough to hold an at-limit one.
    answer = run(
        {
            "template": sequence(2000),
            "constraints": {
                "length_min": 30,
                "length_opt": 33,
                "length_max": MAX_PRIMER_LENGTH,
            },
        }
    )
    assert answer["pairs"], "the limit itself has to be usable, not just below it"


def test_an_ideal_tm_outside_its_own_window_names_both_numbers():
    message = refusal({"constraints": {"tm_min": 55, "tm_opt": 75, "tm_max": 60}})
    assert "75" in message and "55" in message and "60" in message


def test_an_ideal_length_outside_its_own_window_names_both_numbers():
    message = refusal({"constraints": {"length_min": 18, "length_opt": 30, "length_max": 22}})
    assert "30" in message and "18" in message and "22" in message


def test_a_poly_x_ceiling_of_zero_is_refused_because_primer3_inverts_it():
    # The trap: Primer3 reads 0 as "no limit", so the strictest-looking setting
    # is the loosest one. Somebody who types it means the opposite.
    message = refusal({"constraints": {"max_poly_x": 0}})
    assert "no limit" in message


def test_a_negative_diversity_distance_is_refused():
    message = refusal({"constraints": {"min_three_prime_distance": -5}})
    assert "-1" in message


def test_a_gc_clamp_longer_than_the_primer_is_refused():
    message = refusal({"constraints": {"length_min": 18, "gc_clamp": 25}})
    assert "more than there is" in message




def test_asking_for_no_pairs_or_far_too_many_is_refused():
    assert "at least 1" in refusal({"how_many": 0})
    assert str(MAX_PAIRS) in refusal({"how_many": 1000})


def test_every_shipped_constraint_set_and_reaction_is_self_consistent():
    # The defaults have to survive their own validation, or the first run
    # anybody makes fails.
    Constraints().validate()
    for preset in POLYMERASES:
        preset.reaction.validate()
    for intent in PURPOSES:
        Constraints(**intent.constraints).validate()


# ── Templates that are not templates ──────────────────────────────────────


def test_a_template_of_pure_ambiguity_is_refused_before_the_search():
    message = refusal({"template": "N" * 900})
    assert "nothing to design against" in message


def test_a_template_shorter_than_the_product_says_which_numbers_disagree():
    message = refusal({"constraints": {"product_min": 2000, "product_max": 4000}})
    assert "2000" in message and "900" in message


def test_a_homopolymer_finds_nothing_and_says_why_rather_than_refusing():
    # Not a bad request: a valid template that happens to have no primer in it.
    answer = run({"template": "A" * 900})
    assert answer["pairs"] == []
    assert "GC" in answer["why_nothing"]


def test_a_target_region_filling_the_whole_template_leaves_no_room_for_a_primer():
    answer = run({"template": TEMPLATE, "target_start": 0, "target_length": 900})
    assert answer["pairs"] == []
    assert answer["why_nothing"]


def test_a_target_region_past_the_end_is_refused():
    message = refusal({"target_start": 880, "target_length": 200})
    assert "900" in message


# ── What the product is for ───────────────────────────────────────────────


@pytest.mark.parametrize("intent", [p.id for p in PURPOSES])
def test_every_purpose_produces_a_product_inside_its_own_range(intent: str):
    wanted = purpose(intent).constraints
    answer = run({"template": sequence(3500, seed=7), "purpose": intent, "how_many": 3})

    assert answer["pairs"], f"{intent} found nothing on 3.5 kb of ordinary sequence"
    if not {"product_min", "product_max"} <= wanted.keys():
        return
    for pair in answer["pairs"]:
        assert wanted["product_min"] <= pair["product_size"] <= wanted["product_max"]


def test_the_purpose_travels_with_the_result_and_says_what_it_set():
    answer = run({"template": TEMPLATE, "purpose": "sanger"})
    assert answer["purpose"]["id"] == "sanger"
    assert answer["purpose"]["constraints"]["product_max"] == 900
    assert answer["purpose"]["overridden"] == []


def test_amplicon_sequencing_purpose_is_explicit_without_a_fake_global_size_rule():
    answer = run(
        {
            "template": TEMPLATE,
            "purpose": "sequencing",
            "how_many": 2,
        }
    )
    assert purpose("sequencing").constraints == {}
    assert answer["purpose"]["id"] == "sequencing"
    assert answer["purpose"]["constraints"] == {}


def test_a_typed_number_beats_the_purpose_and_the_result_records_that():
    answer = run({"template": TEMPLATE, "purpose": "sanger", "constraints": {"product_max": 700}})
    assert answer["constraints"]["product_max"] == 700
    assert "product_max" in answer["purpose"]["overridden"]
    for pair in answer["pairs"]:
        assert pair["product_size"] <= 700




# ── Placement ─────────────────────────────────────────────────────────────


def test_a_required_region_falls_inside_every_product():
    start, length = 400, 120
    answer = run(
        {
            "template": TEMPLATE,
            "target_start": start,
            "target_length": length,
            "how_many": 3,
        }
    )
    assert answer["pairs"]
    for pair in answer["pairs"]:
        left = pair["left_at"]["start"]
        right = pair["right_at"]["start"]
        assert left < start and right >= start + length - 1


def test_an_excluded_region_holds_no_primer():
    forbidden_start, forbidden_length = 300, 250
    answer = run(
        {
            "template": TEMPLATE,
            "excluded": [[forbidden_start, forbidden_length]],
            "how_many": 5,
        }
    )
    assert answer["pairs"]

    forbidden = range(forbidden_start, forbidden_start + forbidden_length)
    for pair in answer["pairs"]:
        left = range(
            pair["left_at"]["start"],
            pair["left_at"]["start"] + pair["left_at"]["length"],
        )
        right_end = pair["right_at"]["start"]
        right = range(right_end - pair["right_at"]["length"] + 1, right_end + 1)
        assert not set(left) & set(forbidden)
        assert not set(right) & set(forbidden)


def test_an_excluded_region_off_the_end_is_refused():
    message = refusal({"excluded": [[880, 200]]})
    assert "falls outside the" in message


def test_a_gc_clamp_is_honoured_at_the_three_prime_end():
    answer = run({"template": TEMPLATE, "constraints": {"gc_clamp": 2}, "how_many": 3})
    assert answer["pairs"]
    for pair in answer["pairs"]:
        assert set(pair["left"]["sequence"][-2:]) <= set("GC")
        assert set(pair["right"]["sequence"][-2:]) <= set("GC")


# ── What a finished run has to carry ──────────────────────────────────────


def test_a_result_says_what_produced_it():
    # A design nobody can reproduce is a design nobody can publish.
    answer = run({"template": TEMPLATE, "how_many": 1})
    provenance = answer["provenance"]
    assert provenance["primer3_py"] != "unknown"
    assert "SantaLucia" in provenance["model"]["name"]
    assert provenance["python"]




def test_polymerase_identity_does_not_become_a_bench_protocol_by_itself():
    ordinary = run({"template": TEMPLATE, "polymerase": "taq-standard", "how_many": 1})
    assert "cycling" not in ordinary["pairs"][0]

def test_every_oligo_in_the_order_is_checked_against_every_other():
    how_many = 4
    answer = run({"template": TEMPLATE, "how_many": how_many})
    # Two oligos per pair, and the count is of oligos rather than comparisons.
    assert answer["interactions"]["checked"] == 2 * len(answer["pairs"])
    assert answer["interactions"]["note"]


def test_an_order_that_holds_a_dimer_says_which_two_oligos():
    # Every reported interaction has to name both sides, or it is a number
    # nobody can act on.
    answer = run({"template": sequence(2000, seed=11), "how_many": 6})
    for entry in answer["interactions"]["worst"]:
        assert entry["a"] and entry["b"] and entry["a"] != entry["b"]
        assert entry["dg"] <= answer["interactions"]["threshold"]


def test_order_interactions_use_the_conservative_effective_assay_temperature():
    answer = run({"template": sequence(2000, seed=11), "how_many": 6})

    assert "lower of the two candidate-specific" in answer["interactions"]["temperature_policy"]
    # The interaction matrix is allowed to have no flagged dimers, but every
    # emitted observation must retain the temperature used to calculate it.
    for entry in answer["interactions"]["worst"]:
        assert entry["temperature_c"] > 0


def test_the_order_sheet_matches_the_ranking_and_the_pairs():
    answer = run({"template": TEMPLATE, "name": "demo", "how_many": 3})
    sheet = answer["order_sheet"]
    assert len(sheet) == 2 * len(answer["pairs"])
    for index, pair in enumerate(answer["pairs"]):
        assert sheet[2 * index]["sequence"] == pair["left"]["sequence"]
        assert sheet[2 * index + 1]["sequence"] == pair["right"]["sequence"]


def test_the_amplicon_is_the_product_and_starts_and_ends_with_the_primers():
    answer = run({"template": TEMPLATE, "how_many": 3})
    for pair in answer["pairs"]:
        amplicon = pair["amplicon"]
        assert len(amplicon) == pair["product_size"]
        assert amplicon.startswith(pair["left"]["sequence"])


def test_asking_for_more_pairs_than_exist_says_so_rather_than_going_quiet():
    # A short template with a narrow product window holds only a handful of
    # designs. Coming back with fewer than were asked for is a fact, and a
    # result that does not mention it reads as though that was all there was.
    answer = run(
        {
            "template": sequence(320, seed=5),
            "constraints": {"product_min": 250, "product_max": 300},
            "how_many": MAX_PAIRS,
        }
    )
    diversify = next(stage for stage in answer["stages"] if stage["key"] == "diversify")
    assert len(answer["pairs"]) < MAX_PAIRS
    assert "fewer than" in diversify["detail"]






def test_the_funnel_still_accounts_for_the_run():
    answer = run({"template": TEMPLATE, "how_many": 3})
    keys = [stage["key"] for stage in answer["stages"]]
    assert keys[0] == "intake"
    assert "diversify" in keys
    for stage in answer["stages"]:
        if stage["kind"] == "filter" and stage["ran"]:
            assert stage["went_in"] is not None and stage["came_out"] is not None
            assert stage["dropped"] == stage["went_in"] - stage["came_out"]


def test_a_reaction_object_refuses_what_primer3_calls_illegal():
    with pytest.raises(ValueError, match="above zero"):
        Reaction(mv_conc=50.0, dv_conc=1.5, dntp_conc=0.8, dna_conc=0.0).validate()


# ── Names that can leave the screen ────────────────────────────────────────


def test_an_oligo_name_is_short_enough_and_safe_enough_to_order():
    # A FASTA header is a sentence. Pasting one into an order form produces a
    # name with commas in it, which is how a CSV column ends up in the wrong
    # place, and a tube label nobody can read.
    header = ">NM_000546.6 Homo sapiens tumor protein p53 (TP53), transcript variant 1, mRNA"
    answer = run({"template": header + "\n" + TEMPLATE, "how_many": 2})

    for oligo in answer["order_sheet"]:
        assert len(oligo["name"]) <= MAX_OLIGO_NAME + 3, oligo["name"]
        assert "," not in oligo["name"]
        assert " " not in oligo["name"]
        assert oligo["name"].startswith("NM_000546.6")


def test_the_interaction_matrix_names_the_same_oligos_as_the_order_sheet():
    # Two different names for one tube is how somebody orders the wrong thing.
    answer = run(
        {
            "template": ">a b c\n" + TEMPLATE,
            "how_many": 3,
            "background": ">bg\n" + TEMPLATE,
        }
    )
    ordered = {oligo["name"] for oligo in answer["order_sheet"]}
    for entry in answer["interactions"]["worst"]:
        assert entry["a"] in ordered and entry["b"] in ordered


# ── The shortlist ──────────────────────────────────────────────────────────


def test_more_pairs_are_scored_than_are_returned():
    # Otherwise this pipeline's own scoring can only reorder Primer3's top few,
    # and a pair Primer3 ranked below them on melting temperature alone could
    # never win on specificity.
    answer = run({"template": TEMPLATE, "how_many": 3})
    ranking = next(stage for stage in answer["stages"] if stage["key"] == "rank")
    assert ranking["went_in"] > ranking["came_out"] == 3


def test_the_funnel_never_starts_a_step_below_where_the_last_one_ended():
    # A step that begins on a smaller number than the one before it ended on
    # reads as though candidates vanished unexplained, which is the whole thing
    # this funnel exists to prevent.
    answer = run({"template": TEMPLATE, "how_many": 3})
    counted = [
        stage
        for stage in answer["stages"]
        if stage.get("went_in") is not None and stage.get("came_out") is not None
    ]
    for earlier, later in pairwise(counted):
        # Only steps counting the same thing can be compared: bases becoming
        # primers becoming pairs are conversions, not losses.
        if earlier["unit"] != later["unit"]:
            continue
        assert later["went_in"] <= earlier["came_out"], (
            f"{later['title']} starts on {later['went_in']} {later['unit']} but "
            f"{earlier['title']} ended on {earlier['came_out']}"
        )


# ── The assay's own numbers ────────────────────────────────────────────────


def test_the_assay_sets_defaults_that_the_engine_alone_would_not():
    # Several assays share one engine. Without this the engine cannot tell
    # which of them it is running, and Colony PCR is Standard PCR under a
    # second name.
    answer = run(
        {
            "template": TEMPLATE,
            **COLONY_CONTEXT,
            "how_many": 2,
            "assay": {
                "id": "colony-pcr",
                "name": "Colony PCR",
                "defaults": {"constraints": {"product_max": 600}},
            },
        }
    )
    assert answer["constraints"]["product_max"] == 600
    assert answer["assay"]["id"] == "colony-pcr"
    assert all(pair["product_size"] <= 600 for pair in answer["pairs"])


def test_what_was_typed_beats_the_assay_and_the_overruling_is_reported():
    answer = run(
        {
            "template": TEMPLATE,
            **COLONY_CONTEXT,
            "how_many": 2,
            "assay": {
                "id": "colony-pcr",
                "name": "Colony PCR",
                "defaults": {"constraints": {"product_max": 600}},
            },
            "constraints": {"product_max": 800},
        }
    )
    assert answer["constraints"]["product_max"] == 800
    overruled = answer["assay"]["overruled"]
    assert len(overruled) == 1
    assert overruled[0]["field"] == "product_max"
    assert overruled[0]["assay_wanted"] == 600
    assert overruled[0]["used"] == 800
    assert "you set it" in overruled[0]["because"]


def test_an_assay_naming_a_constraint_that_does_not_exist_is_refused():
    # Otherwise the setting simply never takes effect, and a profile that
    # quietly does nothing is the hardest kind of mistake to find.
    with pytest.raises(ValueError, match="not a constraint"):
        run(
            {
                "template": TEMPLATE,
                **COLONY_CONTEXT,
                "assay": {
                    "id": "colony-pcr",
                    "defaults": {"constraints": {"produkt_max": 600}},
                },
            }
        )


def test_an_assay_that_agrees_with_everything_reports_nothing_overruled():
    answer = run(
        {
            "template": TEMPLATE,
            "how_many": 2,
            "assay": {
                "id": "standard-pcr",
                "defaults": {"constraints": {"gc_clamp": 1}},
            },
        }
    )
    assert answer["assay"]["overruled"] == []


def test_the_assay_outranks_the_purpose_in_both_directions():
    """The assay is the reaction; the purpose is what happens to the product.

    A colony lysate cannot give a four-kilobase product however good the
    primers are, and no downstream wish changes that. So the assay sits above
    the purpose — including above the default purpose, which is not a choice at
    all but what you get for saying nothing.
    """
    for downstream_use in (None, "screen"):
        request = {
            "template": TEMPLATE,
            **COLONY_CONTEXT,
            "how_many": 2,
            "assay": {
                "id": "colony-pcr",
                "defaults": {"constraints": {"product_max": 600}},
            },
        }
        if downstream_use:
            request["purpose"] = downstream_use
        answer = run(request)
        assert answer["constraints"]["product_max"] == 600, downstream_use


def test_an_assay_refuses_a_purpose_it_cannot_serve_rather_than_compromising():
    """Some combinations are not a balance to strike.

    Asking a colony screen for a three-kilobase cloning product is a request
    the assay cannot meet. Quietly returning a 600 bp product to somebody who
    asked for 3 kb, or a 3 kb design for a reaction that will not produce one,
    are both worse than saying so.
    """
    with pytest.raises(ValueError, match="cannot be used for"):
        run(
            {
                "template": TEMPLATE,
                **COLONY_CONTEXT,
                "purpose": "cloning",
                "assay": {
                    "id": "colony-pcr",
                    "name": "Colony PCR",
                    "defaults": {"purposes": ["general", "screen"]},
                },
            }
        )






def test_species_specific_requires_a_product_across_every_inclusivity_record(monkeypatch):
    # Inclusivity and exclusivity are different claims. A pair that passes the
    # relative-organism screen must still be refused when it misses one of the
    # intended target records.
    monkeypatch.setattr(pipeline, "_pair_has_product_on_contig", lambda pair, contig, **_: False)

    answer = run(
        {
            "template": TEMPLATE,
            "background": ">near-neighbours\n" + sequence(900, seed=17),
            "inclusivity": ">strain-a\n" + TEMPLATE + "\n>strain-b\n" + TEMPLATE,
            "inclusivity_panel_provenance": "RefSeq release X; target accessions A.1/B.1",
            "background_panel_provenance": "RefSeq release X; near-neighbour accession C.1",
            "species_panel_selection_rationale": "target diversity and closest phylogenetic neighbours",
            "species_target_taxid": 562,
            "species_taxonomy_snapshot": "NCBI Taxonomy snapshot 2026-09-04",
            "species_database_snapshot": "RefSeq genomes release 232",
            "species_panel_accession_manifest": "GCF_000005845.2\nGCF_000008865.2\nGCF_000009865.1",
            "species_panel_record_metadata_manifest": "strain-a\tGCF_000005845.2\tinclusivity\tlinear\nstrain-b\tGCF_000008865.2\tinclusivity\tlinear\nnear-neighbours\tGCF_000009865.1\texclusivity\tlinear",
            "species_panel_accession_authority_manifest": "GCF_000005845.2\t562\tcurrent\nGCF_000008865.2\t562\tcurrent\nGCF_000009865.1\t562\tcurrent",
            "species_panel_retrieved_date": "2026-09-04",
            "how_many": 1,
            "assay": {
                "id": "species-specific-pcr",
                "name": "Species-specific PCR",
                "defaults": {"purposes": ["general"]},
            },
        }
    )

    assert answer["pairs"] == []
    assert answer["inclusivity"]["supplied"] is True
    assert answer["inclusivity"]["contigs"] == 2
    assert answer["inclusivity"]["pairs_rejected"] > 0
    assert answer["inclusivity"]["sequence_topology_assumption"] == "explicit-per-record-topology-from-pinned-metadata-manifest"
    assert answer["inclusivity"]["taxonomy_resolution_status"] == "not-resolved-from-fasta-labels"
    assert answer["inclusivity"]["population_frequency_status"] == "not-computed"
    assert answer["inclusivity"]["surveillance_status"] == "external-versioned-review-required"
    assert answer["background"]["sequence_topology_assumption"] == "explicit-per-record-topology-from-pinned-metadata-manifest"
    assert answer["background"]["taxonomy_resolution_status"] == "not-resolved-from-fasta-labels"
    assert answer["background"]["population_frequency_status"] == "not-computed"
    assert answer["background"]["surveillance_status"] == "external-versioned-review-required"
    assert "inclusivity panel" in answer["why_nothing"]






def test_species_circular_topology_is_explicit_and_does_not_circularize_background(monkeypatch):
    """One target-level topology flag must not leak into exclusion records."""
    monkeypatch.setattr(pipeline, "_pair_has_product_on_contig", lambda pair, contig, **_: False)

    answer = run(
        {
            "template": TEMPLATE,
            "circular": True,
            "background": ">linear-near-neighbour-fragment\n" + sequence(900, seed=23),
            "inclusivity": ">circular-target-a\n" + TEMPLATE + "\n>circular-target-b\n" + TEMPLATE,
            "inclusivity_panel_provenance": "RefSeq release X; circular target accessions A.1/B.1",
            "background_panel_provenance": "RefSeq release X; near-neighbour accession C.1",
            "species_panel_selection_rationale": "target diversity and closest phylogenetic neighbours",
            "species_target_taxid": 562,
            "species_taxonomy_snapshot": "NCBI Taxonomy snapshot 2026-09-04",
            "species_database_snapshot": "RefSeq genomes release 232",
            "species_panel_accession_manifest": "GCF_000005845.2\nGCF_000008865.2\nGCF_000009865.1",
            "species_panel_record_metadata_manifest": "circular-target-a\tGCF_000005845.2\tinclusivity\tcircular\ncircular-target-b\tGCF_000008865.2\tinclusivity\tcircular\nlinear-near-neighbour-fragment\tGCF_000009865.1\texclusivity\tfragment",
            "species_panel_accession_authority_manifest": "GCF_000005845.2\t562\tcurrent\nGCF_000008865.2\t562\tcurrent\nGCF_000009865.1\t562\tcurrent",
            "species_panel_retrieved_date": "2026-09-04",
            "how_many": 1,
            "assay": {
                "id": "species-specific-pcr",
                "name": "Species-specific PCR",
                "defaults": {"purposes": ["general"]},
            },
        }
    )

    assert answer["inclusivity"]["sequence_topology_assumption"] == "explicit-per-record-topology-from-pinned-metadata-manifest"
    assert "pinned topology" in answer["inclusivity"]["topology_note"]
    assert answer["background"]["sequence_topology_assumption"] == "explicit-per-record-topology-from-pinned-metadata-manifest"
    assert "pinned per-record topology" in answer["background"]["topology_note"]


def test_inclusivity_is_rejected_instead_of_silently_ignored_by_other_assays():
    with pytest.raises(ValueError, match="only supported by the species-specific-pcr"):
        run(
            {
                "template": TEMPLATE,
                "inclusivity": ">strain-a\n" + TEMPLATE,
                "assay": {
                    "id": "standard-pcr",
                    "name": "Standard PCR",
                    "defaults": {"purposes": ["general"]},
                },
            }
        )


def test_inclusivity_requires_an_in_window_left_right_product(monkeypatch):
    from types import SimpleNamespace

    from pcr_tools.pipeline import _pair_has_product_on_contig
    from pcr_tools.specificity import Contig, Site

    pair = SimpleNamespace(
        left=SimpleNamespace(sequence="A" * 18),
        right=SimpleNamespace(sequence="C" * 18),
    )
    contig = Contig(name="target", sequence="A" * 400)
    reaction = polymerase("taq-standard").reaction

    def sites_for(primer, role, contigs, **_):
        return [
            Site(
                primer=primer,
                role=role,
                contig=contigs[0].name,
                three_prime_at=17 if role == "left" else 317,
                orientation="forward" if role == "left" else "reverse",
                mismatches=0,
                dg=-10.0,
                tm=60.0,
            )
        ]

    monkeypatch.setattr("pcr_tools.pipeline.spec.sites_for", sites_for)
    assert not _pair_has_product_on_contig(
        pair,
        contig,
        reaction=reaction,
        max_mismatches=3,
        min_product=200,
        max_product=300,
    )
    assert _pair_has_product_on_contig(
        pair,
        contig,
        reaction=reaction,
        max_mismatches=3,
        min_product=200,
        max_product=400,
    )


def test_species_inclusivity_fails_closed_on_ambiguous_binding_sites(monkeypatch):
    """An IUPAC-compatible possibility is not an exact inclusivity claim."""
    from types import SimpleNamespace

    from pcr_tools.pipeline import _pair_has_product_on_contig
    from pcr_tools.specificity import Contig, Site

    pair = SimpleNamespace(
        left=SimpleNamespace(sequence="A" * 18),
        right=SimpleNamespace(sequence="C" * 18),
    )
    contig = Contig(name="target", sequence="A" * 400)
    reaction = polymerase("taq-standard").reaction

    def sites_for(primer, role, contigs, **_):
        return [
            Site(
                primer=primer,
                role=role,
                contig=contigs[0].name,
                three_prime_at=17 if role == "left" else 317,
                orientation="forward" if role == "left" else "reverse",
                mismatches=0,
                dg=-10.0,
                tm=60.0,
                ambiguous_bases=1 if role == "left" else 0,
                mismatch_upper_bound=1 if role == "left" else 0,
            )
        ]

    monkeypatch.setattr("pcr_tools.pipeline.spec.sites_for", sites_for)

    # Discovery semantics still recognize the possible IUPAC-compatible site.
    assert _pair_has_product_on_contig(
        pair,
        contig,
        reaction=reaction,
        max_mismatches=0,
        min_product=200,
        max_product=400,
    )
    # A species-inclusivity claim is stricter: ambiguity under either primer
    # cannot be promoted to exact target coverage.
    assert not _pair_has_product_on_contig(
        pair,
        contig,
        reaction=reaction,
        max_mismatches=0,
        min_product=200,
        max_product=400,
        require_unambiguous_sites=True,
    )


def test_restriction_end_geometry_detects_compatible_isocaudomer_like_ends():
    """Different enzyme names can still produce the same cohesive end."""
    from pcr_tools.restriction import BY_NAME
    from pcr_tools.tails import end_compatibility, end_geometry

    bamhi = BY_NAME["BamHI"]
    bglii = BY_NAME["BglII"]
    xhoi = BY_NAME["XhoI"]
    sma = BY_NAME["SmaI"]

    assert end_geometry(bamhi)["polarity"] == "5-prime"
    assert end_geometry(bamhi)["overhang"] == "GATC"
    assert end_compatibility(bamhi, bglii) is True
    assert end_compatibility(bamhi, xhoi) is False
    assert end_geometry(sma)["polarity"] == "blunt"


def test_restriction_cloning_keeps_the_full_ordered_oligo_interaction():
    answer = run(
        {
            "template": TEMPLATE,
            "how_many": 1,
            "cloning_vector": CLONING_VECTOR,
            "cloning_vector_topology": "circular",
            "restriction_digest_protocol": "neb-cutsmart-standard",
            "restriction_dephosphorylation_protocol": "none",
            "restriction_ligation_protocol": "neb-t4-dna-ligase-m0202",
            "assay": {
                "id": "restriction-cloning",
                "name": "Restriction Cloning",
                "defaults": {"polymerase": "proofreading", "purposes": ["cloning"]},
            },
            "tails": {
                "tail_protocol": "neb-general-6bp",
                "forward_enzyme": "HindIII",
                "reverse_enzyme": "PstI",
                "forward_protective_sequence": "GACTTA",
                "reverse_protective_sequence": "CAGTTA",
            },
        }
    )

    assert answer["cloning"]["insert_end_compatibility_scope"] == "insert-end-sequence-geometry-only"
    assert answer["cloning"]["ligation_product_recleavage"] == "not-modeled"
    digest = answer["cloning"]["digest_validation"]
    assert digest["methylation_sensitivity_status"] == "exact-enzyme-formulation-and-substrate-context-required"
    assert digest["star_activity_status"] == "reaction-condition-dependent-not-computed"
    assert digest["double_digest_compatibility_status"] == "exact-formulation/current-supplier-buffer-chart-required"
    assert digest["heat_inactivation_status"] == "exact-formulation/current-supplier-record-required"
    assert digest["ligation_junction_recleavage_status"] == "exact-insert-vector-junction-required"
    assert len(digest["required_records"]) >= 6
    interaction = answer["pairs"][0]["tailed"]["interaction"]
    assert set(interaction) == {"without_tails", "with_tails", "worsened_by"}
    assert interaction["worsened_by"] == pytest.approx(
        interaction["without_tails"]["dg"] - interaction["with_tails"]["dg"]
    )






def test_restriction_cloning_rejects_removed_per_end_protective_length_fields():
    with pytest.raises(ValueError, match="unknown tails field"):
        run(
            {
                "template": TEMPLATE,
                "how_many": 1,
                "cloning_vector": CLONING_VECTOR,
                "cloning_vector_topology": "circular",
                "restriction_digest_protocol": "neb-cutsmart-standard",
                "restriction_dephosphorylation_protocol": "none",
                "restriction_ligation_protocol": "neb-t4-dna-ligase-m0202",
                "assay": {
                    "id": "restriction-cloning",
                    "name": "Restriction Cloning",
                    "defaults": {"polymerase": "proofreading", "purposes": ["cloning"]},
                },
                "tails": {
                    "tail_protocol": "neb-general-6bp",
                    "forward_enzyme": "HindIII",
                    "reverse_enzyme": "PstI",
                    "forward_protective_bases": 3,
                    "forward_protective_sequence": "GACTTA",
                    "reverse_protective_sequence": "CAGTTA",
                },
            }
        )




def test_an_assay_with_no_purpose_list_serves_every_purpose():
    answer = run(
        {
            "template": TEMPLATE,
            "how_many": 2,
            "purpose": "cloning",
            "assay": {"id": "standard-pcr", "defaults": {}},
        }
    )
    assert answer["purpose"]["id"] == "cloning"


# ── Known variants under a primer ─────────────────────────────────────────
#
# `variant-masking` was declared on this assay from the beginning and read by
# nothing. These are the tests that make it a setting rather than a label.


def a_masked_run(variants: list[int], *, how_many: int = 5) -> dict:
    return run({"template": TEMPLATE, "how_many": how_many, "variants": variants})


def test_a_variant_off_the_end_of_the_template_is_refused_not_ignored():
    # Masking nothing looks exactly like masking something clean, so a
    # coordinate that cannot be placed has to be a refusal.
    message = refusal({"variants": [len(TEMPLATE) + 40]})
    assert str(len(TEMPLATE)) in message
    assert "outside" in message


@pytest.mark.parametrize("bad", [True, 1.5, "12"])
def test_a_variant_coordinate_is_not_silently_coerced(bad):
    message = refusal({"variants": [bad]})
    assert "integer" in message


def test_nobody_asking_is_reported_differently_from_nothing_found():
    clean = run({"template": TEMPLATE, "how_many": 3})
    assert clean["variants"]["checked"] is False
    assert clean["pairs"][0]["variants"] is None

    component = next(
        c for c in clean["pairs"][0]["score_components"] if c["name"] == "Known variants"
    )
    assert component["value"] == 0.0
    assert "Not assessed" in component["detail"], (
        "an unasked question and a clean answer are both zero, and they mean opposite things"
    )


def test_a_variant_on_a_forward_primers_three_prime_end_removes_that_pair():
    before = run({"template": TEMPLATE, "how_many": 5})
    best = before["pairs"][0]
    three_prime = best["left_at"]["start"] + best["left_at"]["length"] - 1

    after = a_masked_run([three_prime], how_many=5)
    assert after["variants"]["rejected"] >= 1
    assert not [
        pair for pair in after["pairs"] if pair["left"]["sequence"] == best["left"]["sequence"]
    ], "a primer whose last base is polymorphic was still offered"


def test_a_variant_on_a_reverse_primers_three_prime_end_removes_that_pair():
    # The reverse primer's 3' end is at the *low* coordinate: Primer3 reports
    # it by its highest plus-strand base and it reads back from there. Getting
    # this backwards would mask the wrong end of the primer and look like it
    # was working.
    before = run({"template": TEMPLATE, "how_many": 5})
    best = before["pairs"][0]
    three_prime = best["right_at"]["start"] - best["right_at"]["length"] + 1

    after = a_masked_run([three_prime], how_many=5)
    assert not [
        pair for pair in after["pairs"] if pair["right"]["sequence"] == best["right"]["sequence"]
    ], "a reverse primer whose last base is polymorphic was still offered"


def test_a_variant_well_back_from_the_three_prime_end_is_also_refused():
    before = run({"template": TEMPLATE, "how_many": 5})
    best = before["pairs"][0]
    start, length = best["left_at"]["start"], best["left_at"]["length"]
    back = start + 2  # near the 5' end, deliberately far from the extension end
    assert (start + length - 1) - back >= 10, "the fixture must exercise a distant overlap"

    after = a_masked_run([back], how_many=5)
    assert not [
        pair for pair in after["pairs"] if pair["left"]["sequence"] == best["left"]["sequence"]
    ], "current Gen-1 must not resurrect a terminal-distance tolerance heuristic"
    assert after["variants"]["policy"] == "avoid-any-supplied-variant-under-primer"
    assert after["variants"]["rejected"] >= 1


def test_variant_coordinates_never_become_a_ranking_penalty():
    before = run({"template": TEMPLATE, "how_many": 5})
    best = before["pairs"][0]
    back = best["left_at"]["start"] + 2

    after = a_masked_run([back], how_many=5)
    for pair in after["pairs"]:
        component = next(
            c for c in pair["score_components"] if c["name"] == "Known variants"
        )
        assert component["value"] == 0.0
        assert "No supplied variant lies" in component["detail"]


def test_the_funnel_accounts_for_what_masking_removed():
    before = run({"template": TEMPLATE, "how_many": 5})
    best = before["pairs"][0]
    three_prime = best["left_at"]["start"] + best["left_at"]["length"] - 1

    after = a_masked_run([three_prime], how_many=5)
    stage = next(s for s in after["stages"] if s["key"] == "variants")
    assert stage["kind"] == "filter", "it removes candidates, so it is not a scorer"
    assert stage["went_in"] - stage["came_out"] == after["variants"]["rejected"]
    assert stage["rejections"], "a filter that removed something has to say what"


def test_masking_is_absent_from_the_funnel_when_nobody_asked():
    clean = run({"template": TEMPLATE, "how_many": 3})
    assert not [s for s in clean["stages"] if s["key"] == "variants"], (
        "a step nobody asked for should not appear as a step that passed"
    )


# ── The pair's own dimer, scored as well as gated ─────────────────────────


def test_every_pair_is_scored_on_what_its_two_primers_do_to_each_other():
    result = run({"template": TEMPLATE, "how_many": 5})
    for pair in result["pairs"]:
        component = next(c for c in pair["score_components"] if c["name"] == "Primer-dimer")
        assert f"{pair['cross_dimer_dg']:.1f}" in component["detail"], (
            "the component should quote the number it priced"
        )


def test_pair_dimer_output_matches_the_recorded_specificity_temperature():
    from pcr_tools.thermo import pair_dimer

    result = run({"template": TEMPLATE, "how_many": 1})
    pair = result["pairs"][0]
    expected = pair_dimer(
        pair["left"]["sequence"],
        pair["right"]["sequence"],
        mv_conc=50.0,
        dv_conc=1.5,
        dntp_conc=0.8,
        dna_conc=200.0,
        temp_c=pair["specificity_temperature_c"],
    ).dg

    assert pair["cross_dimer_dg"] == expected
    assert pair["cross_dimer_temperature_c"] == pair["specificity_temperature_c"]
    component = next(c for c in pair["score_components"] if c["name"] == "Primer-dimer")
    assert f"{expected:.1f}" in component["detail"]


def test_a_pair_that_binds_itself_harder_is_marked_down_for_it():
    # The gate answers "would this fail". This answers "which of these is
    # best", and they are different questions: among pairs that all passed the
    # ceiling, nothing was preferring the ones whose primers leave each other
    # alone.
    from pcr_tools.pipeline import CROSS_PAIR_DIMER_WATCH

    result = run({"template": TEMPLATE, "how_many": MAX_PAIRS // 3})
    priced = [
        (pair["cross_dimer_dg"], comp["value"])
        for pair in result["pairs"]
        for comp in pair["score_components"]
        if comp["name"] == "Primer-dimer"
    ]
    assert priced, "no pairs to judge"

    for dg, penalty in priced:
        if dg >= CROSS_PAIR_DIMER_WATCH:
            assert penalty == 0.0, (
                f"a pair binding at {dg:.1f} was marked down, above the "
                f"{CROSS_PAIR_DIMER_WATCH} watch line"
            )
        else:
            assert penalty > 0.0, f"a pair binding at {dg:.1f} was not marked down at all"

    # And harder binding never costs less.
    ordered = sorted(priced)
    for (colder_dg, colder), (warmer_dg, warmer) in pairwise(ordered):
        assert colder >= warmer, (
            f"{colder_dg:.1f} was priced below {warmer_dg:.1f}, which is backwards"
        )


def test_the_dimer_penalty_cannot_swamp_the_rest_of_the_score():
    from pcr_tools.pipeline import CROSS_DIMER_CAP

    result = run({"template": TEMPLATE, "how_many": 5})
    for pair in result["pairs"]:
        component = next(c for c in pair["score_components"] if c["name"] == "Primer-dimer")
        assert component["value"] <= CROSS_DIMER_CAP


# ── What the product between the primers will be like ─────────────────────


def test_an_ordinary_product_is_not_called_difficult():
    # The first version of this judged the *richest window*, and the maximum of
    # many windows climbs with length whatever the sequence is made of: 10 per
    # cent of random 50%-GC products came back "hard", and a 3 kb one would
    # have almost always. The verdict comes from the whole product now, which
    # is also what the sources measured.
    from pcr_tools.amplicon import profile

    generator = random.Random(1)
    called_hard = 0
    for _ in range(200):
        product = "".join(generator.choice("ACGT") for _ in range(300))
        if profile(product).difficulty != "easy":
            called_hard += 1
    assert called_hard == 0, f"{called_hard} of 200 ordinary 50%-GC products were called difficult"


def test_a_gc_rich_product_is_called_difficult_and_says_on_whose_evidence():
    from pcr_tools.amplicon import HARD_GC, profile

    product = profile("GCGCGGCGGCGCCGCGGCGCCGGCGCGGCGCCGCGGCGGCGCGCCGGCGC" * 4)
    assert product.gc > HARD_GC
    assert product.difficulty in {"hard", "very hard"}
    assert "doi:" in product.to_dict()["note"], (
        "an additive recommendation without a citation is a guess in a lab coat"
    )


def test_the_worst_window_is_reported_but_never_sets_the_verdict():
    from pcr_tools.amplicon import HARD_GC, profile

    # An AT-rich product with one GC-rich patch: the patch is worth showing,
    # and it is not a reason to call the whole product difficult.
    product = profile(
        "AT" * 200 + "GCGCGGCGGCGCCGCGGCGCCGGCGCGGCGCCGCGGCGGCGCGCCGGCGC" + "AT" * 200
    )
    assert product.worst_window_gc > HARD_GC, "the patch should be found"
    assert product.gc < HARD_GC
    assert product.difficulty == "easy", "one patch made the whole product difficult"
    assert str(int(product.worst_window_gc)) in product.to_dict()["note"], (
        "the patch should still be pointed at"
    )


def test_every_pair_carries_a_profile_of_its_own_product():
    result = run({"template": TEMPLATE, "how_many": 3})
    for pair in result["pairs"]:
        product = pair["amplicon_profile"]
        assert product["length"] == pair["product_size"]
        assert product["difficulty"] in {"easy", "hard", "very hard"}

# ── Named Standard-PCR bench/provenance overlays ──────────────────────────


def test_named_standard_pcr_protocols_are_bench_overlays_not_ranking_models():
    expected = set(pipeline.STANDARD_PCR_PROTOCOLS) - {"not-selected"}
    assert set(pipeline.STANDARD_PCR_PROTOCOLS) == {"not-selected", *expected}
    for protocol_id in sorted(expected):
        protocol = pipeline.standard_pcr_protocol(
            protocol_id,
            assay_id="standard-pcr",
            multiplex_context=protocol_id == "neb-multiplex-pcr-m0284",
        )
        assert protocol is not None
        assert protocol["protocol_id"] == protocol_id
        assert protocol["kind"] == "standard-pcr"
        assert protocol["sequence_decision_impact"] == "none"
        assert protocol["thermodynamic_model_impact"] == "none"
        assert protocol["constraints"] == {}
        assert "Primer3" in protocol["screening_context_note"]


def test_standard_pcr_overlay_is_fail_closed_on_wrong_assay_or_unknown_id():
    with pytest.raises(ValueError, match="standard-pcr"):
        pipeline.standard_pcr_protocol("neb-q5-hot-start-m0493", assay_id="qpcr-sybr")
    with pytest.raises(ValueError, match="standard_pcr_protocol"):
        pipeline.standard_pcr_protocol("guess", assay_id="standard-pcr")


def test_q5_and_q5u_keep_uracil_and_carryover_semantics_distinct():
    q5 = pipeline.standard_pcr_protocol("neb-q5-hot-start-m0493", assay_id="standard-pcr")
    q5u = pipeline.standard_pcr_protocol("neb-q5u-hot-start-m0515", assay_id="standard-pcr")
    assert q5 and q5u
    assert q5["polymerase_properties"]["product_end"] == "blunt"
    assert q5["polymerase_properties"]["dUTP_compatible"] is False
    assert q5["polymerase_properties"]["uracil_template_compatible"] is False
    assert q5["carryover_prevention"]["dUTP_supported"] is False
    assert q5["carryover_prevention"]["UDG_built_in"] is False
    assert q5u["polymerase_properties"]["product_end"] == "blunt"
    assert q5u["polymerase_properties"]["dUTP_compatible"] is True
    assert q5u["polymerase_properties"]["uracil_template_compatible"] is True
    assert q5u["carryover_prevention"]["UDG_built_in"] is False
    assert q5u["carryover_prevention"]["optional_UDG"]


def test_taq_family_and_high_fidelity_product_end_handoffs_remain_distinct():
    taq = pipeline.standard_pcr_protocol("neb-taq-m0273", assay_id="standard-pcr")
    dream = pipeline.standard_pcr_protocol("thermo-dreamtaq-hot-start-ep170x", assay_id="standard-pcr")
    phusion = pipeline.standard_pcr_protocol("thermo-phusion-plus", assay_id="standard-pcr")
    assert taq and dream and phusion
    assert "dA" in taq["polymerase_properties"]["product_end"]
    assert "dA" in dream["polymerase_properties"]["product_end"]
    assert "blunt" in phusion["polymerase_properties"]["product_end"]
    assert phusion["polymerase_properties"]["hot_start"] is True
    assert phusion["polymerase_properties"]["dUTP_compatible"] is False
    assert phusion["carryover_prevention"]["dUTP_supported"] is False
    assert taq["carryover_prevention"]["dUTP_supported"] is True
    assert taq["cycling_model"]["cycles"] == {
        "routine_program_min": 25,
        "routine_program_max": 30,
        "general_guidance_max": 35,
        "low_copy_may_require_up_to": 45,
    }
    assert dream["carryover_prevention"]["dUTP_supported"] is True
    assert phusion["difficult_template"]["automatic_additive_selection"] is False



def test_promega_gotaq_overlay_keeps_buffer_variant_and_carryover_claims_bounded():
    gotaq = pipeline.standard_pcr_protocol("promega-gotaq-m300", assay_id="standard-pcr")
    assert gotaq
    assert gotaq["magnesium_final_mM"] == 1.5
    assert gotaq["polymerase_units_per_50uL"] == 1.25
    assert gotaq["polymerase_properties"]["hot_start"] is False
    assert "dA" in gotaq["polymerase_properties"]["product_end"]
    assert gotaq["buffer_variants"]["identity_must_be_recorded"] is True
    assert gotaq["carryover_prevention"]["dUTP_supported"] == "not-asserted-by-this-reviewed-overlay"
    assert gotaq["carryover_prevention"]["enabled_by_protocol_selection_alone"] is False

def test_shared_high_gc_diagnostic_does_not_transfer_pcr_additives_into_rpa():
    from pcr_tools.amplicon import profile

    diagnostic = profile("GCGCGGCGGCGCCGCGGCGCCGGCGCGGCGCCGCGGCGGCGCGCCGGCGC" * 4).to_dict(
        assay_id="rpa"
    )
    assert diagnostic["difficulty_scope"] == "composition-only-not-rpa-performance-threshold"
    assert "not validated RPA performance thresholds" in diagnostic["note"]
    assert "does not transfer DMSO" in diagnostic["note"]


def test_standard_pcr_hot_start_mechanisms_and_q5u_udg_pretreatment_are_vendor_bound() -> None:
    from pcr_tools.pipeline import standard_pcr_protocol

    q5 = standard_pcr_protocol("neb-q5-hot-start-m0493", assay_id="standard-pcr")
    q5u = standard_pcr_protocol("neb-q5u-hot-start-m0515", assay_id="standard-pcr")
    phusion = standard_pcr_protocol("thermo-phusion-plus", assay_id="standard-pcr")
    assert q5 and q5["polymerase_properties"]["hot_start_mechanism"] == "aptamer-based"
    assert q5u and q5u["polymerase_properties"]["hot_start_mechanism"] == "aptamer-based"
    assert q5u["carryover_prevention"]["supplier_pretreatment"] == {"temperature_c": 25, "minutes": 10}
    assert phusion and phusion["polymerase_properties"]["hot_start_mechanism"] == "antibody-molecule-mediated"
