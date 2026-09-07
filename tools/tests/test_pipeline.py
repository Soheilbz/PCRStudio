"""One run, end to end, including the runs that produce nothing."""

from __future__ import annotations

import pathlib
import random
from dataclasses import replace

import pytest

from pcr_tools.pipeline import run
from pcr_tools.specificity import BackgroundTooLarge, reverse_complement

CORPUS = pathlib.Path(__file__).parent / "corpus"


def _corpus(accession: str) -> str:
    """One cached GenBank record, as bare bases."""
    raw = (CORPUS / f"{accession}.fasta").read_text().splitlines()
    return "".join(line.strip() for line in raw if not line.startswith(">"))


def sequence(length: int, seed: int) -> str:
    generator = random.Random(seed)
    return "".join(generator.choice("ACGT") for _ in range(length))


TEMPLATE = sequence(900, 3)


COLONY_CONTEXT = {
    "colony_host_class": "bacterial",
    "colony_preparation": "water-lysate",
    "colony_protocol_id": "custom-sop",
    "colony_protocol_name": "test-SOP",
    "colony_protocol_provenance": "lab QA record / current test SOP revision",
}
DIGITAL_CONTEXT = {
    "digital_partition_format": "droplet",
    "digital_platform_id": "bio-rad-qx200",
    "digital_platform_name": "Bio-Rad QX200",
    "digital_fragmentation_state": "not-assessed",
}


def test_a_plain_run_produces_ranked_pairs_and_an_order_sheet():
    answer = run({"template": TEMPLATE, "name": "demo", "how_many": 3})

    assert answer["pairs"]
    scores = [pair["score"] for pair in answer["pairs"]]
    assert scores == sorted(scores), "the best candidate has to be first"

    # Two oligos per pair, named so an order form can be filled from them.
    assert len(answer["order_sheet"]) == 2 * len(answer["pairs"])
    assert answer["order_sheet"][0]["name"] == "demo_1F"


def test_a_flanking_pair_template_must_be_one_fasta_record():
    with pytest.raises(ValueError, match="multiple FASTA records"):
        run({"template": ">first\n" + TEMPLATE + "\n>second\n" + TEMPLATE})


def test_the_direct_worker_enforces_the_same_template_ceiling_as_the_api():
    from pcr_tools.pipeline import MAX_TEMPLATE_BASES

    with pytest.raises(ValueError, match="provide a target region"):
        run({"template": "ACGT" * (MAX_TEMPLATE_BASES // 4 + 1)})


def test_an_assay_default_purpose_is_used_when_the_request_has_none():
    answer = run(
        {
            "template": TEMPLATE,
            **COLONY_CONTEXT,
            "assay": {
                "id": "colony-pcr",
                "name": "Colony PCR",
                "defaults": {
                    "defaultPurpose": "screen",
                    "purposes": ["general", "screen", "sanger"],
                },
            },
        }
    )

    assert answer["purpose"]["id"] == "screen"






def test_restriction_cloning_refuses_bare_primer_branch():
    try:
        run(
            {
                "template": TEMPLATE,
                "how_many": 1,
                "cloning_vector": "ACGT" * 200,
                "cloning_vector_topology": "circular",
                "restriction_digest_protocol": "neb-cutsmart-standard",
                "restriction_dephosphorylation_protocol": "none",
                "restriction_ligation_protocol": "neb-t4-dna-ligase-m0202",
                "assay": {
                    "id": "restriction-cloning",
                    "name": "Restriction Cloning",
                    "defaults": {"purposes": ["cloning"]},
                },
            }
        )
    except ValueError as error:
        assert "tails.tail_protocol" in str(error)
    else:
        raise AssertionError("restriction-cloning must not return supplier-orderable bare PCR primers")


def test_the_order_sheet_follows_the_ranking_not_primer3s_order():
    answer = run({"template": TEMPLATE, "how_many": 4})
    best = answer["pairs"][0]
    assert answer["order_sheet"][0]["sequence"] == best["left"]["sequence"]
    assert answer["order_sheet"][1]["sequence"] == best["right"]["sequence"]


def test_every_score_is_the_sum_of_its_stated_parts():
    # If these disagree, the breakdown is decoration rather than an account.
    answer = run({"template": TEMPLATE, "how_many": 3})
    for pair in answer["pairs"]:
        total = sum(part["value"] for part in pair["score_components"])
        assert round(total, 3) == pair["score"]






def test_result_keeps_the_executable_assay_contract_for_reproduction():
    answer = run(
        {
            "template": TEMPLATE,
            "how_many": 1,
            "assay": {
                "id": "species-specific-pcr",
                "name": "Species-specific PCR",
                "modifiers": [],
                "requires": ["background"],
                "enzyme": ["thermostable"],
            },
            "background": ">near-relative\nAAAA",
            "inclusivity": ">target-panel\n" + TEMPLATE,
            "inclusivity_panel_provenance": "RefSeq release X; target accession A.1",
            "background_panel_provenance": "RefSeq release X; near-neighbour accession B.1",
            "species_panel_selection_rationale": "target diversity and closest phylogenetic neighbours",
            "species_target_taxid": 562,
            "species_taxonomy_snapshot": "NCBI Taxonomy snapshot 2026-09-04",
            "species_database_snapshot": "RefSeq genomes release 232",
            "species_panel_accession_manifest": "GCF_000005845.2\nGCF_000008865.2",
            "species_panel_record_metadata_manifest": "target-panel\tGCF_000005845.2\tinclusivity\tlinear\nnear-relative\tGCF_000008865.2\texclusivity\tlinear",
            "species_panel_accession_authority_manifest": "GCF_000005845.2\t562\tcurrent\nGCF_000008865.2\t562\tcurrent",
            "species_panel_retrieved_date": "2026-09-04",
        }
    )

    assert answer["assay"]["modifiers"] == []
    assert answer["assay"]["requires"] == ["background"]
    assert answer["assay"]["enzyme"] == ["thermostable"]








def test_validation_contract_is_structured_for_qpcr_and_digital_pcr():
    qanswer = run({"template": TEMPLATE, "assay": {"id": "qpcr-sybr"}, "how_many": 1})
    qitems = {item["key"] for item in qanswer["validation"]["items"]}
    assert {"raw_fluorescence", "cq_method", "standard_curve", "melt_curve"} <= qitems
    assert qanswer["validation"]["status"] == "in-silico-only"
    assert "efficiency" in " ".join(qanswer["validation"]["not_computed"])

    danswer = run({"template": TEMPLATE, **DIGITAL_CONTEXT, "assay": {"id": "digital-pcr"}, "how_many": 1})
    ditems = {item["key"] for item in danswer["validation"]["items"]}
    assert {"partition_counts", "partition_volume", "threshold_and_rain_policy"} <= ditems
    assert danswer["reaction"]["model"]["oligo_concentration_parameter"] == "PRIMER_DNA_CONC"
    assert (
        danswer["reaction"]["model"]["oligo_concentration_role"]
        == "empirical_annealing_oligo_for_tm"
    )
    assert all(
        item["computable"] is False
        for item in danswer["validation"]["items"]
        if item["kind"] == "measurement"
    )




def test_bio_rad_itaq_explicit_product_override_wins_and_is_audited():
    answer = run(
        {
            "template": sequence(1800, 17),
            "assay": {"id": "qpcr-sybr"},
            "qpcr_protocol": "bio-rad-itaq-sybr",
            "constraints": {"product_min": 90, "product_max": 120},
            "how_many": 1,
        }
    )

    assert answer["constraints"]["product_min"] == 90
    assert answer["constraints"]["product_max"] == 120
    assert {"product_min", "product_max"} <= set(answer["purpose"]["overridden"])
    assert all(90 <= pair["product_size"] <= 120 for pair in answer["pairs"])




def test_flanking_pair_does_not_accept_two_named_chemistry_overlays():
    with pytest.raises(ValueError, match="only one named flanking-pair"):
        run(
            {
                "template": TEMPLATE,
                "assay": {"id": "qpcr-sybr"},
                "qpcr_protocol": "bio-rad-itaq-sybr",
                "rpa_protocol": "twistamp-basic",
            }
        )


def test_qx200_evagreen_overlay_records_partition_protocol_not_copy_number():
    answer = run(
        {
            "template": sequence(1800, 17),
            **DIGITAL_CONTEXT,
            "assay": {"id": "digital-pcr"},
            "digital_protocol": "bio-rad-qx200-evagreen",
            "how_many": 1,
        }
    )

    protocol = answer["protocol"]
    assert protocol["kind"] == "digital-pcr"
    assert protocol["reaction_volume_uL"] == 20
    assert protocol["droplets_target"] == 20000
    assert protocol["cycling"]["cycles"] == 40
    assert protocol["cycling"]["annealing_extension"] == {
        "temperature_c": 60,
        "minutes": 1,
    }
    assert "threshold" not in protocol
    assert "poisson" not in protocol
    assert answer["digital_context"]["partition_format"] == "droplet"
    assert answer["digital_context"]["threshold_status"] == "measured-run-required"
    assert answer["digital_context"]["quantification_status"] == "not-computed-from-design"


def test_named_flanking_protocol_records_keep_vendor_authority_without_reranking():
    from pcr_tools.pipeline import (
        digital_protocol,
        long_range_protocol,
        qpcr_protocol,
        standard_pcr_protocol,
    )

    records = [
        standard_pcr_protocol("thermo-platinum-superfi-ii", assay_id="standard-pcr"),
        qpcr_protocol("promega-gotaq-qpcr-a600x", assay_id="qpcr-sybr"),
        qpcr_protocol(
            "promega-gotaq-one-step-rt-qpcr-a6020",
            assay_id="qpcr-sybr",
            from_rna=True,
        ),
        long_range_protocol("neb-q5-xt-m2499", assay_id="long-range-pcr"),
        long_range_protocol("promega-gotaq-long-m4021", assay_id="long-range-pcr"),
        long_range_protocol(
            "thermo-platinum-superfi-ii-longrange", assay_id="long-range-pcr"
        ),
        digital_protocol(
            "bio-rad-qx700-evagreen-supermix", assay_id="digital-pcr"
        ),
    ]
    assert all(record and record["sequence_decision_impact"] == "none" for record in records)


def test_promega_a6020_one_step_rt_qpcr_refuses_dna_only_context():
    from pcr_tools.pipeline import qpcr_protocol

    with pytest.raises(ValueError, match="requires `from_rna=true`"):
        qpcr_protocol(
            "promega-gotaq-one-step-rt-qpcr-a6020",
            assay_id="qpcr-sybr",
            from_rna=False,
        )


def test_digital_pcr_requires_platform_partition_and_fragmentation_context():
    with pytest.raises(ValueError, match="digital_partition_format"):
        run({"template": TEMPLATE, "assay": {"id": "digital-pcr"}, "how_many": 1})


def test_qx200_overlay_refuses_non_droplet_partition():
    with pytest.raises(ValueError, match="droplet"):
        run({
            "template": TEMPLATE,
            **{**DIGITAL_CONTEXT, "digital_partition_format": "chip"},
            "assay": {"id": "digital-pcr"},
            "digital_protocol": "bio-rad-qx200-evagreen",
            "how_many": 1,
        })










def test_an_invalid_assay_cycling_programme_is_refused_before_the_search():
    with pytest.raises(ValueError, match="at least one cycle"):
        run(
            {
                "template": TEMPLATE,
                "assay": {"defaults": {"cycling": {"cycles": 0}}},
            }
        )


def test_optional_chemistry_family_is_a_valid_assay_default():
    answer = run(
        {
            "template": TEMPLATE,
            "assay": {"id": "standard-pcr", "defaults": {"chemistryFamily": None}},
        }
    )
    assert answer["assay"]["id"] == "standard-pcr"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("assay", []),
        ("constraints", []),
        ("excluded", "not-a-list"),
        ("tails", "not-an-object"),
        ("vector_primer", "not-an-object"),
    ),
)
def test_malformed_nested_request_shapes_are_refused(field, value):
    with pytest.raises(ValueError, match=r"(?:object|list)"):
        run({"template": TEMPLATE, field: value})


@pytest.mark.parametrize("field", ["howMany", "polymerse", "unexpected"])
def test_unknown_flanking_pair_request_fields_are_refused_before_search(field):
    with pytest.raises(ValueError, match="unknown flanking-pair request field"):
        run({"template": TEMPLATE, field: 1})


@pytest.mark.parametrize(
    ("assay", "message"),
    (
        ({"typo": 1}, "unknown assay field"),
        ({"defaults": {"product_mni": 200}}, "unknown assay default field"),
    ),
)
def test_unknown_assay_configuration_is_refused_before_search(assay, message):
    with pytest.raises(ValueError, match=message):
        run({"template": TEMPLATE, "assay": assay})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("tails", {"protective_bases": 3, "protective_base": 3}, "unknown tails field"),
        ("vector_primer", {"how_many": 1, "read_into": "start"}, "unknown vector_primer field"),
    ),
)
def test_unknown_nested_configuration_is_refused_before_search(field, value, message):
    with pytest.raises(ValueError, match=message):
        run({"template": TEMPLATE, field: value})




def test_internal_shortlist_limits_are_validated_before_searching():
    with pytest.raises(ValueError, match=r"most.*integer"):
        run({"template": TEMPLATE}, most=3.5)
    with pytest.raises(ValueError, match=r"pool.*at least 1"):
        run({"template": TEMPLATE}, pool=0)
    with pytest.raises(ValueError, match=r"pool.*how_many"):
        run({"template": TEMPLATE, "how_many": 2}, pool=1)




def test_a_template_shorter_than_the_product_says_which_two_numbers_disagree():
    with pytest.raises(ValueError, match="shortest product"):
        run({"template": sequence(120, 5)})


def test_an_impossible_run_explains_itself_rather_than_returning_an_empty_list():
    answer = run(
        {
            "template": TEMPLATE,
            # No twenty-mer of random sequence melts at 85 degrees.
            "constraints": {"tm_min": 84.0, "tm_opt": 85.0, "tm_max": 86.0},
        }
    )
    assert answer["pairs"] == []

    # What matters is the shape of the answer, not which filter happened to
    # take the most: it names a stage, a count and something to do about it.
    # Asserting on a particular reason made this test a hostage to the order
    # Primer3 applies its filters in.
    message = answer["why_nothing"]
    assert "survived" in message
    assert any(character.isdigit() for character in message)
    assert message.rstrip().endswith(".")


def test_without_a_background_the_result_says_which_half_was_checked():
    """The claim changed when the template began to be scanned.

    It used to say nothing had been checked, which was true and was the
    problem: `contigs` came only from the background box, so the commonest run
    — the one with that box empty — checked nothing at all, while this module's
    guidance said specificity was "judged against that template alone".

    Now the template is scanned when nothing else is, and the note says exactly
    that: a second site on your own sequence would have been found, and nothing
    here speaks for anywhere else.
    """
    answer = run({"template": TEMPLATE})

    assert answer["background"]["checked"] is True
    note = answer["background"]["note"]
    assert "Only the pasted sequence was checked" in note
    assert "no background was given" in note.lower()
    for pair in answer["pairs"]:
        assert pair["off_targets"]["checked"] is True


def test_a_second_copy_of_the_target_is_a_real_unwanted_product():
    # The background holds the target twice. One copy is what was asked for;
    # the other gives a second band of exactly the same size, which is the
    # classic way a design fails on a paralogue.
    background = (
        ">chr\n" + sequence(500, 8) + TEMPLATE + sequence(2000, 9) + TEMPLATE + sequence(500, 10)
    )
    answer = run({"template": TEMPLATE, "background": background, "how_many": 5})

    assert answer["background"]["checked"] is True
    assert all(pair["off_targets"]["product_count"] >= 1 for pair in answer["pairs"]), (
        "every pair amplifies the second copy as well as the first"
    )

    # Exactly one occurrence is excused as the intended product, never both.
    for pair in answer["pairs"]:
        same_size = [
            product
            for product in pair["off_targets"]["products"]
            if product["size"] == pair["product_size"]
        ]
        assert len(same_size) == 1


def test_a_background_that_cannot_be_scanned_refuses_before_the_search():
    """Refused up front rather than after a search that will be thrown away.

    The size comes from the scanner's own constant. Written out here, it was a
    third copy of a limit that moved once already — and the copy that noticed
    was this test failing, which is the slow way to find out.
    """
    from pcr_tools.specificity import MAX_BACKGROUND_BASES

    with pytest.raises(BackgroundTooLarge):
        run({"template": TEMPLATE, "background": "A" * (MAX_BACKGROUND_BASES + 1)})


def test_the_intake_notes_reach_the_result():
    answer = run({"template": ">from_rna\n" + TEMPLATE.replace("T", "U")})
    kinds = {note["kind"] for note in answer["target"]["notes"]}
    assert "rnaConverted" in kinds
    assert answer["target"]["name"] == "from_rna"
    assert answer["target"]["rna_input"] is True
    assert answer["reverse_transcription"] is not None


def test_rna_cannot_be_explicitly_run_as_plain_dna():
    with pytest.raises(ValueError, match="requires reverse transcription"):
        run({"template": TEMPLATE.replace("T", "U"), "from_rna": False})








def test_unknown_assay_requirements_are_refused_instead_of_ignored():
    with pytest.raises(ValueError, match="unknown assay requirement"):
        run(
            {
                "template": TEMPLATE,
                "assay": {"id": "standard-pcr", "requires": ["database"]},
            }
        )


def test_transcript_junctions_are_enforced_and_audited():
    answer = run(
        {
            "template": TEMPLATE,
            "from_rna": True,
            "exon_junctions": [450],
            "how_many": 2,
        }
    )

    assert answer["transcript"]["exon_junctions"] == [450]
    assert answer["transcript"]["junction_spanning_required"] is True
    assert answer["request"]["transcript"]["coordinate_system"] == (
        "zero-based-boundary-between-bases"
    )
    assert all(
        pair["left_at"]["start"] < 450 < pair["left_at"]["start"] + pair["left_at"]["length"]
        or pair["right_at"]["start"] - pair["right_at"]["length"] + 1
        < 450
        < pair["right_at"]["start"] + 1
        for pair in answer["pairs"]
    )
    assert any(stage["key"] == "transcript-junction" for stage in answer["stages"])


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"exon_junctions": [450]}, "from_rna"),
        ({"from_rna": True, "exon_junctions": []}, "non-empty"),
        ({"from_rna": True, "exon_junctions": [0]}, "at least"),
        ({"from_rna": True, "exon_junctions": [900]}, "at most"),
        ({"from_rna": True, "exon_junctions": [450, 450]}, "duplicate"),
    ],
)
def test_transcript_junction_input_is_not_guessed_or_clipped(payload, message):
    with pytest.raises(ValueError, match=message):
        run({"template": TEMPLATE, **payload})


def test_accessibility_either_ran_or_said_why_it_did_not():
    answer = run({"template": TEMPLATE, "how_many": 2})
    profile = answer["accessibility"]
    assert profile["checked"] or profile["note"], "a silent skip reads as nothing to report"




def test_stage_audit_follows_execution_order_for_variant_and_specificity_filters():
    answer = run(
        {
            "template": TEMPLATE,
            "variants": [20],
            "background": ">background\n" + TEMPLATE,
            "how_many": 2,
        }
    )
    keys = [stage["key"] for stage in answer["stages"]]
    assert keys.index("variants") < keys.index("specificity")
    assert keys.index("specificity") < keys.index("accessibility")


def test_a_reverse_complemented_background_still_finds_the_sites():
    background = ">rc\n" + reverse_complement(TEMPLATE)
    answer = run({"template": TEMPLATE, "background": background, "how_many": 2})
    assert answer["background"]["checked"]
    # The target is present, just on the other strand, so its own product is
    # found there too and correctly recognised as the intended one.
    assert all(
        product["size"] != pair["product_size"]
        for pair in answer["pairs"]
        for product in pair["off_targets"].get("products", [])
    )


# ── Purpose-weighted objectives ──────────────────────────────────────────────


def test_a_purpose_that_has_weights_passes_them_to_the_search(monkeypatch):
    import pcr_tools.pipeline as pipeline_mod
    from pcr_tools.pipeline import PURPOSE_WEIGHTS

    seen: list[dict | None] = []
    real_design = pipeline_mod.design

    def watched(template, **kwargs):
        seen.append(kwargs.get("weights"))
        return real_design(template, **kwargs)

    monkeypatch.setattr(pipeline_mod, "design", watched)

    run({"template": TEMPLATE, "how_many": 2, "purpose": "screen"})
    assert seen and seen[-1] == PURPOSE_WEIGHTS["screen"], (
        "a purpose with tuned objectives must reach the search carrying them"
    )


def test_the_general_purpose_adds_no_weights(monkeypatch):
    """Balanced means Primer3's own defaults, not a second opinion."""
    import pcr_tools.pipeline as pipeline_mod
    from pcr_tools.pipeline import PURPOSE_WEIGHTS

    assert PURPOSE_WEIGHTS.get("general") is None
    assert PURPOSE_WEIGHTS.get("genotyping-band") is None

    seen: list[dict | None] = []
    real_design = pipeline_mod.design

    def watched(template, **kwargs):
        seen.append(kwargs.get("weights"))
        return real_design(template, **kwargs)

    monkeypatch.setattr(pipeline_mod, "design", watched)

    run({"template": TEMPLATE, "how_many": 2})
    assert seen and seen[-1] is None


def test_rpa_neutralises_primer3_tm_ranking_without_removing_tm_guards(monkeypatch):
    import pcr_tools.pipeline as pipeline_mod
    from pcr_tools.pipeline import ISOTHERMAL_PRIMER3_WEIGHTS

    seen: list[dict | None] = []
    real_design = pipeline_mod.design

    def watched(template, **kwargs):
        seen.append(kwargs.get("weights"))
        return real_design(template, **kwargs)

    monkeypatch.setattr(pipeline_mod, "design", watched)
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "development")
    run(
        {
            "template": TEMPLATE,
            "how_many": 1,
            "assay": {"id": "rpa", "name": "RPA", "defaults": {"polymerase": "rpa"}},
            "rpa_protocol": "twistamp-basic",
        }
    )
    assert seen and seen[-1] == ISOTHERMAL_PRIMER3_WEIGHTS




def test_the_weights_a_run_used_travel_with_the_result():
    weighted = run({"template": TEMPLATE, "how_many": 2, "purpose": "screen"})
    plain = run({"template": TEMPLATE, "how_many": 2})
    from pcr_tools.pipeline import PURPOSE_WEIGHTS

    assert weighted["purpose"]["ranking_weights"] == PURPOSE_WEIGHTS["screen"]
    assert plain["purpose"]["ranking_weights"] == {}


def test_the_sanger_weights_move_which_products_rank_first():
    """Weights must move the ranking, not merely be accepted in silence.

    primer3-py accepts unknown tags without a word, so a weight that does
    nothing looks exactly like one that works -- until a run with it is put
    beside a run without on the same template. This is that comparison, on a
    real transcript with both runs held to the same product window so the only
    difference left is what the weights price. The original bug (weights named
    `PRIMER_WT_PRODUCT_SIZE`, a tag that does not exist) passes every
    error-free run and fails exactly here.
    """
    template = _corpus("NM_000546.6")
    window = {"constraints": {"product_min": 120, "product_max": 400}}
    plain = run({"template": template, "how_many": 5, **window})
    weighted = run({"template": template, "how_many": 5, "purpose": "sanger", **window})

    assert weighted["pairs"], "the transcript must give pairs either way"
    assert [pair["product_size"] for pair in weighted["pairs"]] != [
        pair["product_size"] for pair in plain["pairs"]
    ], (
        "the sanger weights changed no product size against the unweighted "
        "run, which is what an ignored weight looks like"
    )


# ── The composite quality score ──────────────────────────────────────────────


def _a_pair(cross_dimer_dg: float):
    """One measured CandidatePair on a fixed sequence, for scoring tests."""
    from pcr_tools.design import CandidatePair, Placement
    from pcr_tools.thermo import DEFAULT_CONDITIONS, analyse

    left = analyse("GCTAGCATCGACGTTACGGATCAG", **DEFAULT_CONDITIONS)
    right = analyse("CTGATCGTAACGTCGATGCTAGC", **DEFAULT_CONDITIONS)
    return CandidatePair(
        left=left,
        right=right,
        left_at=Placement(start=0, length=left.length),
        right_at=Placement(start=119, length=right.length),
        product_size=140,
        penalty=0.5,
        tm_difference=0.3,
        cross_dimer_dg=cross_dimer_dg,
        amplicon="ACGT" * 35,
    )


def test_a_clean_pair_outscores_one_with_a_flagged_dimer():
    from pcr_tools.design import Constraints
    from pcr_tools.pipeline import CROSS_PAIR_DIMER_WATCH, _quality_score

    clean_pair = _a_pair(-1.0)  # well above the watch line: no dimer to speak of
    flagged_pair = _a_pair(CROSS_PAIR_DIMER_WATCH - 1.0)  # below it: flagged

    limits = Constraints()
    clean = _quality_score(clean_pair, limits, off_target_penalty=0.0, openings=None)
    flagged = _quality_score(flagged_pair, limits, off_target_penalty=0.0, openings=None)

    assert isinstance(clean["score"], int)
    assert clean["parts"]["dimer_margin"] > flagged["parts"]["dimer_margin"]
    assert flagged["parts"]["dimer_margin"] == 0.0, "below the watch line is fully spent"
    assert clean["score"] > flagged["score"], (
        "the composite has to prefer the pair that is not spending itself on dimer"
    )


def test_pair_dimer_report_is_remeasured_at_the_effective_assay_temperature():
    from pcr_tools.pipeline import _pair_at_effective_temperature
    from pcr_tools.presets import Reaction

    pair = _a_pair(-20.58)
    reaction = Reaction(mv_conc=50.0, dv_conc=1.5, dntp_conc=0.8, dna_conc=200.0)

    low = _pair_at_effective_temperature(pair, reaction, 37.0)
    warm = _pair_at_effective_temperature(pair, reaction, 63.0)

    assert low.cross_dimer_dg < warm.cross_dimer_dg, (
        "a warmer assay hold must not reuse the colder, more stable dimer value"
    )
    assert warm.cross_dimer_dg == -6.69
    assert warm.left is pair.left and warm.right is pair.right


def test_standard_pcr_triplet_prior_preserves_all_triplets_as_a_soft_signal():
    from pcr_tools.pipeline import (
        THREE_PRIME_TRIPLET_FREQUENCIES,
        _score_three_prime_triplets,
    )
    from pcr_tools.thermo import DEFAULT_CONDITIONS, analyse

    clean = _a_pair(-1.0)
    frequent = replace(
        clean,
        left=analyse("GCTAGCATCGACGTTACAGG", **DEFAULT_CONDITIONS),
        right=analyse("CTGATCGTAACGTCGATCTG", **DEFAULT_CONDITIONS),
    )
    rare = replace(
        clean,
        left=analyse("GCTAGCATCGACGTTACATT", **DEFAULT_CONDITIONS),
        right=analyse("CTGATCGTAACGTCGATTT", **DEFAULT_CONDITIONS),
    )

    frequent_penalty, frequent_detail = _score_three_prime_triplets(frequent)
    rare_penalty, rare_detail = _score_three_prime_triplets(rare)

    assert len(THREE_PRIME_TRIPLET_FREQUENCIES) == 64
    assert frequent_penalty < rare_penalty
    assert "AGG" in frequent_detail and "TTA" not in frequent_detail
    assert "ATT" in rare_detail and "TTT" in rare_detail


def test_rpa_quality_does_not_treat_the_pcr_tm_midpoint_as_quality():
    from pcr_tools.design import Constraints
    from pcr_tools.pipeline import _quality_score

    quality = _quality_score(
        _a_pair(-1.0),
        Constraints(tm_min=50.0, tm_opt=75.0, tm_max=100.0),
        off_target_penalty=0.0,
        openings=None,
        tm_centeredness_enabled=False,
    )

    assert quality["parts"]["tm_centeredness"] is None
    assert 0 <= quality["score"] <= 100




def test_unchecked_specificity_is_not_reported_as_a_perfect_quality_component(
    monkeypatch,
):
    from pcr_tools import pipeline

    monkeypatch.setattr(
        pipeline.screen,
        "contigs_for",
        lambda request, *, template, name: ([], False, None),
    )
    answer = run({"template": TEMPLATE, "how_many": 1})

    assert answer["pairs"][0]["off_targets"]["checked"] is False
    assert answer["pairs"][0]["quality"]["parts"]["specificity"] is None


# ── Product uniformity ───────────────────────────────────────────────────────


def test_every_pair_reports_the_gc_of_its_worst_windows():
    answer = run({"template": TEMPLATE, "how_many": 3})
    for pair in answer["pairs"]:
        uniformity = pair["uniformity"]
        assert uniformity["window_bp"] == 50
        assert uniformity["min_window_gc"] <= uniformity["max_window_gc"]
        assert 0 <= uniformity["min_window_gc"] and uniformity["max_window_gc"] <= 100


def test_a_low_gc_product_is_pointed_at_and_never_removed():
    """The check reports; it does not judge.

    An AT-rich patch inside every product must show up as a window worth
    knowing about -- and must not cost the pairs their place in the result,
    because a target's composition is not something better primers can fix.
    """
    generator = random.Random(4)
    flanks = "".join(generator.choice("ACGT") for _ in range(600))
    template = flanks[:300] + "AT" * 200 + flanks[300:]

    answer = run(
        {
            "template": template,
            # Inside the AT patch, so every product has to span it.
            "target_start": 400,
            "target_length": 100,
            "how_many": 3,
        }
    )
    assert answer["pairs"]
    for pair in answer["pairs"]:
        uniformity = pair["uniformity"]
        assert uniformity["min_window_gc"] < 15.0
        assert "slip" in uniformity["note"]
        assert pair["score_components"], "the pair was still scored and offered"


def test_an_ordinary_product_carries_no_uniformity_warning():
    from pcr_tools.pipeline import _uniformity

    # 50% GC in every window, give or take the two bases a 50-base window
    # cannot fit from the period-4 pattern: nothing to point at.
    report = _uniformity("ACGT" * 100)
    assert abs(report["min_window_gc"] - 50.0) <= 2.0
    assert abs(report["max_window_gc"] - 50.0) <= 2.0
    assert report["note"] == ""


def test_a_high_gc_window_is_reported_as_likely_to_form_structures():
    from pcr_tools.pipeline import _uniformity

    generator = random.Random(9)
    at_rich = "".join(generator.choice("AT") for _ in range(200))
    gc_patch = "GCGCGGCGGCGCCGCGGCGCCGGCGCGGCGCCGCGGCGGCGCGCCGGCGC" * 5
    report = _uniformity(at_rich + gc_patch + at_rich)
    assert report["max_window_gc"] > 85.0
    assert "structures" in report["note"]


def test_a_product_shorter_than_one_window_is_read_whole():
    from pcr_tools.pipeline import _uniformity

    report = _uniformity("ACGTACGT")
    assert report["window_bp"] == 8
    assert report["min_window_gc"] == report["max_window_gc"] == 50.0


def test_the_off_target_split_tracks_how_well_a_site_matches():
    """Fixed free energies did not discriminate; fractions of the real duplex do.

    Measured, not argued: at a fixed -10 kcal/mol, perfect matches, one-mismatch
    sites and two-mismatch sites were all called serious — a three-way split
    doing the work of "everything is serious". A free energy also scales with
    length and GC, so one number cannot mean the same thing for a 35-mer at 68
    degrees and an 18-mer at 57.
    """
    import primer3

    from pcr_tools.pipeline import OFF_TARGET_SERIOUS, OFF_TARGET_WATCH
    from pcr_tools.presets import polymerase
    from pcr_tools.thermo import reverse_complement

    conditions = polymerase("taq-standard").reaction.as_conditions()
    generator = random.Random(7)

    def classify(mismatches: int) -> str:
        primer = "".join(generator.choice("ACGT") for _ in range(20))
        intended = (
            primer3.calc_heterodimer(primer, reverse_complement(primer), **conditions).dg / 1000.0
        )
        site = list(reverse_complement(primer))
        for position in generator.sample(range(20), mismatches):
            site[position] = generator.choice([base for base in "ACGT" if base != site[position]])
        found = primer3.calc_heterodimer(primer, "".join(site), **conditions).dg / 1000.0
        if found <= OFF_TARGET_SERIOUS * intended:
            return "serious"
        if found <= OFF_TARGET_WATCH * intended:
            return "watch"
        return "ignored"

    perfect = [classify(0) for _ in range(60)]
    distant = [classify(4) for _ in range(60)]

    assert perfect.count("serious") == 60, "a perfect match always competes"
    assert distant.count("serious") <= 6, "four mismatches rarely do"


def test_a_clean_scan_and_a_narrow_one_do_not_read_alike():
    """A missing penalty and a penalty of zero look identical in a total.

    They still mean different things, but the distinction has moved. Nothing is
    unchecked any more — the template is always scanned — so what has to be
    distinguishable now is "checked against a genome and found unique" from
    "checked against your own sequence and nothing else".
    """
    narrow = run({"template": TEMPLATE, "how_many": 1})
    component = next(
        part
        for part in narrow["pairs"][0]["score_components"]
        if part["name"] == "Off-target products"
    )
    assert component["value"] == 0.0

    # The score says it found nothing; the background block says how far it
    # looked. Both are needed to read the result honestly.
    assert "Only the pasted sequence was checked" in narrow["background"]["note"]

    wide = run(
        {
            "template": TEMPLATE,
            "background": ">chr\n" + sequence(3000, 21),
            "how_many": 1,
        }
    )
    assert wide["background"]["note"] == ""
    assert wide["background"]["bases"] > len(TEMPLATE)






def test_circular_template_specificity_reports_real_background_bases_not_join_scaffold():
    circular = sequence(900, seed=21)
    answer = run({"template": circular, "circular": True, "how_many": 1})

    assert answer["background"]["bases"] == len(circular)
    assert answer["pairs"][0]["off_targets"]["background_bases"] == len(circular)


def test_specificity_baseline_uses_the_actual_template_windows():
    from pcr_tools.design import CandidatePair, Placement
    from pcr_tools.pipeline import _intended_binding_dg
    from pcr_tools.presets import polymerase
    from pcr_tools.thermo import analyse, pair_dimer, reverse_complement

    left_sequence = "GCTAGCATCGACGTTACGGATCAG"
    right_sequence = "CTGATCGTAACGTCGATGCTAGC"
    left = analyse(left_sequence)
    right = analyse(right_sequence)
    # Deliberately make the intended left site differ from the primer at one
    # internal base. This is not a normal Primer3 pair; it is a regression
    # fixture proving that the baseline is the actual target duplex rather
    # than a self-duplex substituted for it.
    left_window = (
        left_sequence[:10] + ("A" if left_sequence[10] != "A" else "C") + left_sequence[11:]
    )
    right_window = reverse_complement(right_sequence)
    template = left_window + "A" * 100 + right_window
    pair = CandidatePair(
        left=left,
        right=right,
        left_at=Placement(start=0, length=left.length),
        right_at=Placement(
            start=len(left_window) + 100 + len(right_window) - 1,
            length=right.length,
        ),
        product_size=len(template),
        penalty=0.0,
        tm_difference=0.0,
        cross_dimer_dg=0.0,
        amplicon=template,
    )
    conditions = polymerase("taq-standard").reaction.as_conditions()
    actual = _intended_binding_dg(pair, template, circular=False, conditions=conditions)
    self_duplex = min(
        pair_dimer(left_sequence, reverse_complement(left_sequence), **conditions).dg,
        pair_dimer(right_sequence, reverse_complement(right_sequence), **conditions).dg,
    )

    assert actual != self_duplex
    assert actual == max(
        pair_dimer(left_sequence, reverse_complement(left_window), **conditions).dg,
        pair_dimer(right_sequence, right_window, **conditions).dg,
    )


def test_off_target_baseline_uses_the_weaker_intended_primer():
    from pcr_tools.pipeline import _score_off_targets
    from pcr_tools.specificity import OffTarget, Site

    def site(role: str, dg: float) -> Site:
        return Site(
            primer="ACGT",
            role=role,
            contig="background",
            three_prime_at=10,
            orientation="forward" if role == "left" else "reverse",
            mismatches=0,
            dg=dg,
            tm=60.0,
        )

    product = OffTarget(
        contig="background",
        start=0,
        end=20,
        size=21,
        forward=site("left", -7.0),
        reverse=site("right", -7.0),
    )
    _, _, serious = _score_off_targets([product], intended_dg=-8.0)

    # A -7.0 off-target competes with an intended pair whose limiting primer
    # is -8.0; it would not be serious if the stronger -20.0 side were used.
    assert serious == 1


def test_the_pasted_sequence_is_always_scanned_against_its_own_primers():
    """The check standard PCR's own guidance claimed and did not perform.

    `profiles.toml` says specificity "is judged against that template alone".
    Nothing judged it: `contigs` was built from `request["background"]` and
    from nothing else, so with that box empty the result reported that no
    specificity check had run — which is the default state, and therefore the
    commonest standard PCR run was the unchecked one.

    The template is the one place a primer is certain to be able to sit twice.
    """
    unit = _corpus("NM_000546.6")[200:800]
    # Two identical copies: every pair reading forwards through the repeat has
    # a genuine second product of exactly the same size.
    answer = run(
        {
            "template": ">tandem\n" + unit + unit,
            "polymerase": "taq-standard",
            "how_many": 20,
        }
    )

    warned = [pair for pair in answer["pairs"] if pair["off_targets"]["product_count"] > 0]
    assert warned, "a tandem duplication should produce pairs with a second band"

    # And it says where, rather than reporting an anonymous background.
    first = warned[0]["off_targets"]
    assert "the template itself" in first["products"][0]["contig"]
    assert first["checked"] is True
    assert "mismatch_positions_from_three_prime" in first["products"][0]["forward"]
    assert "mismatch_base_pairs_from_three_prime" in first["products"][0]["forward"]
    assert "nearest_three_prime_mismatch" in first["products"][0]["forward"]


def test_the_intended_product_is_not_reported_as_an_off_target():
    """The other half: scanning the template must not accuse the design itself.

    Every pair matches its own template exactly once by construction, so a scan
    that did not drop the intended product would report every design as having
    an off-target — which is the same as reporting none.
    """
    answer = run(
        {
            "template": ">TP53\n" + _corpus("NM_000546.6")[200:900],
            "polymerase": "taq-standard",
            "how_many": 3,
        }
    )

    for pair in answer["pairs"]:
        off = pair["off_targets"]
        assert off["checked"] is True
        assert off["site_count"] >= 2, "both primers sit on their own template"
        assert off["product_count"] == 0, (
            "an ordinary template has one product, and it is the one asked for"
        )


def test_same_size_paralogue_does_not_hide_the_intended_product():
    """The intended copy is identified by sequence, not by sorted position.

    A paralogue can preserve both primer-binding ends and the product length
    while changing its internal sequence.  Both products therefore have exact
    primer sites and identical thermodynamic scores; removing the first one
    returned would be nondeterministically capable of hiding the real
    off-target.  Only the complete intended amplicon may be excused.
    """
    from pcr_tools.design import design
    from pcr_tools.pipeline import _without_the_intended_product
    from pcr_tools.presets import polymerase
    from pcr_tools.specificity import Contig, products_from, sites_for

    candidate = design(TEMPLATE, how_many=1).pairs[0]
    intended = candidate.amplicon
    middle_start = candidate.left.length
    middle_end = len(intended) - candidate.right.length
    changed = "A" if intended[middle_start] != "A" else "C"
    paralogue = (
        intended[:middle_start]
        + changed
        + intended[middle_start + 1 : middle_end]
        + intended[middle_end:]
    )
    contigs = [Contig("background", paralogue + ("A" * 50) + intended)]
    reaction = polymerase("taq-standard").reaction
    sites = sites_for(
        candidate.left.sequence,
        "left",
        contigs,
        reaction=reaction,
    ) + sites_for(
        candidate.right.sequence,
        "right",
        contigs,
        reaction=reaction,
    )
    products = products_from(sites, max_product=3000)

    remaining = _without_the_intended_product(products, candidate, contigs)
    same_size = [product for product in remaining if product.size == candidate.product_size]
    assert len(same_size) == 1
    assert contigs[0].sequence[same_size[0].start : same_size[0].end + 1] == paralogue


def test_a_run_with_no_background_says_which_half_was_checked():
    """ "Nothing was checked" and "only the template was checked" are different.

    The first is what it used to say, and it was wrong the moment the template
    began to be scanned. The second is true and is the more useful sentence: it
    names what the run does not know.
    """
    answer = run(
        {
            "template": ">TP53\n" + _corpus("NM_000546.6")[200:900],
            "polymerase": "taq-standard",
            "how_many": 1,
        }
    )

    note = answer["background"]["note"]
    assert "Only the pasted sequence" in note
    assert "no background was given" in note.lower()


def test_a_circular_run_masks_the_origin_in_the_repeated_head(monkeypatch):
    """An excluded stretch near the origin exists twice in what Primer3 sees.

    Closing the circle repeats the first bases at the end of the searched
    string. Passing the excluded regions unchanged left that copy unmasked,
    so a primer could sit on bases somebody asked to keep out of every copy
    of the product.
    """
    import pcr_tools.pipeline as pipeline_mod

    seen: list[list[tuple[int, int]] | None] = []
    real_design = pipeline_mod.design

    def watched(template, **kwargs):
        seen.append(kwargs.get("excluded"))
        return real_design(template, **kwargs)

    monkeypatch.setattr(pipeline_mod, "design", watched)

    excluded = [[10, 20]]
    answer = run(
        {
            # Long enough that the head repeat exists: the searched string only
            # grows when the circle is bigger than the longest product asked
            # for, and the default ceiling is a thousand bases.
            "template": sequence(1200, 3),
            "circular": True,
            "excluded": excluded,
            "how_many": 2,
        }
    )

    # The original region and its translated copy both reached the search;
    # the request itself was not touched.
    assert answer["pairs"]
    assert len(seen) == 1
    passed = seen[0] or []
    assert (10, 20) in passed
    head = [region for region in passed if region[0] >= 1200]
    assert len(head) == 1, "the repeated head must carry its own masked copy"
    start, length = head[0]
    assert start == 1200 + 10
    assert length == 20


def test_a_short_circle_is_extended_so_a_product_can_cross_its_origin(monkeypatch):
    """The repeated head is needed even when the circle is below product_max."""
    from pcr_tools.design import DesignResult

    template = sequence(240, 17)
    seen: dict[str, str] = {}

    def fake_design(searched, **_kwargs):
        seen["template"] = searched
        return DesignResult(
            pairs=[],
            considered={"left": "", "right": "", "pair": ""},
            returned=0,
            examined=0,
            wanted=1,
            warning="",
            collapsed=0,
        )

    monkeypatch.setattr("pcr_tools.pipeline.design", fake_design)
    run(
        {
            "template": template,
            "circular": True,
            "how_many": 1,
            "constraints": {"product_min": 80, "product_max": 500},
        }
    )

    assert seen["template"] == template + template


def test_circle_folding_uses_the_right_primer_three_prime_coordinate():
    """A linear primer near the end must not be mistaken for a crossing one."""
    from pcr_tools.design import CandidatePair, DesignResult, Placement
    from pcr_tools.pipeline import _fold_onto_the_circle
    from pcr_tools.thermo import analyse

    left = analyse("GCTAGCATCGACGTTACGGATCAG")
    right = analyse("CTGATCGTAACGTCGATGCTAGC")

    def pair(right_start: int) -> CandidatePair:
        return CandidatePair(
            left=left,
            right=right,
            left_at=Placement(start=180, length=left.length),
            right_at=Placement(start=right_start, length=right.length),
            product_size=100,
            penalty=0.0,
            tm_difference=0.0,
            cross_dimer_dg=0.0,
            amplicon="ACGT" * 25,
        )

    result = DesignResult(
        pairs=[pair(220), pair(260)],
        considered={"left": "", "right": "", "pair": ""},
        returned=2,
        examined=2,
        wanted=2,
        warning="",
        collapsed=0,
    )
    folded = _fold_onto_the_circle(result, around=240, how_many=2)

    assert folded.pairs[0].right_at.start == 220
    assert folded.pairs[0].crosses_the_join is False
    assert folded.pairs[1].right_at.start == 20
    assert folded.pairs[1].crosses_the_join is True


def test_circular_species_inclusivity_accepts_a_pair_crossing_the_origin():
    """The inclusivity gate must use the same circular geometry as the search.

    A target panel can contain plasmids or other circular molecules. A pair
    whose product crosses the FASTA origin is a valid product on that molecule
    and must not be rejected merely because the panel check used a linear
    string.
    """
    import random

    from pcr_tools.design import CandidatePair, Placement
    from pcr_tools.pipeline import _pair_has_product_on_contig
    from pcr_tools.presets import polymerase
    from pcr_tools.specificity import Contig
    from pcr_tools.thermo import analyse, reverse_complement

    circle = "".join(random.Random(31).choices("ACGT", k=240))
    left_start = 180
    right_start = 20
    left_sequence = circle[left_start : left_start + 20]
    right_sequence = reverse_complement(circle[right_start : right_start + 20])
    product_size = 100
    amplicon = "".join(
        circle[(left_start + offset) % len(circle)] for offset in range(product_size)
    )
    left = analyse(left_sequence)
    right = analyse(right_sequence)
    pair = CandidatePair(
        left=left,
        right=right,
        left_at=Placement(start=left_start, length=left.length),
        right_at=Placement(start=right_start, length=right.length),
        product_size=product_size,
        penalty=0.0,
        tm_difference=0.0,
        cross_dimer_dg=0.0,
        amplicon=amplicon,
        crosses_the_join=True,
    )

    assert _pair_has_product_on_contig(
        pair,
        Contig("circular target", circle),
        reaction=polymerase("taq-standard").reaction,
        max_mismatches=0,
        min_product=80,
        max_product=120,
        circular=True,
        temperature_c=60.0,
    )


def test_circular_variant_filter_sees_bases_across_the_origin():
    """Any supplied variant in a primer spanning the origin invalidates it."""
    from pcr_tools.variants import under_left, under_right

    left = under_left(238, 6, [1], circular_length=240)
    right = under_right(2, 6, [238], circular_length=240)

    assert left.positions == (1,)
    assert left.from_three_prime == (2,)
    assert left.fatal
    assert right.positions == (238,)
    assert right.from_three_prime == (4,)
    assert right.fatal


def test_species_specific_refuses_identical_sequence_in_inclusivity_and_exclusion_panels():
    target = ">target\n" + "ACGT" * 120
    shared = "ACGT" * 120
    request = {
        "assay": {"id": "species-specific-pcr"},
        "background": ">excluded\n" + shared,
        "inclusivity": ">included\n" + shared,
        "inclusivity_panel_provenance": "target panel / accession set / release 1",
        "background_panel_provenance": "exclusion panel / accession set / release 1",
        "species_panel_selection_rationale": "target diversity versus declared near-neighbour exclusion set",
        "species_target_taxid": 562,
        "species_taxonomy_snapshot": "NCBI Taxonomy snapshot 2026-09-04",
        "species_database_snapshot": "RefSeq genomes release 232",
        "species_panel_accession_manifest": "GCF_000005845.2\nGCF_000008865.2",
        "species_panel_record_metadata_manifest": "included\tGCF_000005845.2\tinclusivity\tlinear\nexcluded\tGCF_000008865.2\texclusivity\tlinear",
        "species_panel_accession_authority_manifest": "GCF_000005845.2\t562\tcurrent\nGCF_000008865.2\t562\tcurrent",
        "species_panel_retrieved_date": "2026-09-04",
    }
    with pytest.raises(ValueError, match="identical sequence"):
        run({"template": target, **request})


def test_species_specific_refuses_reverse_complement_sequence_between_panels():
    target = ">target\n" + "ACGT" * 120
    shared = "AACCGTTAGCGTACGATTCG" * 24
    request = {
        "assay": {"id": "species-specific-pcr"},
        "background": ">excluded\n" + shared,
        "inclusivity": ">included_reverse_orientation\n" + reverse_complement(shared),
        "inclusivity_panel_provenance": "target panel / accession set / release 1",
        "background_panel_provenance": "exclusion panel / accession set / release 1",
        "species_panel_selection_rationale": "target diversity versus declared near-neighbour exclusion set",
        "species_target_taxid": 562,
        "species_taxonomy_snapshot": "NCBI Taxonomy snapshot 2026-09-04",
        "species_database_snapshot": "RefSeq genomes release 232",
        "species_panel_accession_manifest": "GCF_000005845.2\nGCF_000008865.2",
        "species_panel_record_metadata_manifest": "included_reverse_orientation\tGCF_000005845.2\tinclusivity\tlinear\nexcluded\tGCF_000008865.2\texclusivity\tlinear",
        "species_panel_accession_authority_manifest": "GCF_000005845.2\t562\tcurrent\nGCF_000008865.2\t562\tcurrent",
        "species_panel_retrieved_date": "2026-09-04",
    }
    with pytest.raises(ValueError, match="reverse-complement orientation"):
        run({"template": target, **request})
