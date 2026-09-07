"""The specificity scan, across every worker whose page shows the step.

Six of the twenty-one pages showed a specificity step whose answer went
nowhere: the engine behind it had no `background` field, so a pasted genome was
dropped on the way in and the result said nothing about it. That is the worst
shape a check can take — a design nobody looked at reads exactly like a design
that came back clean — and it was invisible from either side alone.

Each worker is asked the same two questions here: does a clean template come
back clean, and does a template present twice come back with the second copy
named. A test that only asked the first would pass on a worker that never
scanned anything.
"""

from __future__ import annotations

import pathlib

import pytest

CORPUS = pathlib.Path(__file__).parent / "corpus"


def _corpus(accession: str, start: int, length: int) -> str:
    raw = (CORPUS / f"{accession}.fasta").read_text().splitlines()
    seq = "".join(line.strip() for line in raw if not line.startswith(">"))
    return seq[start : start + length]


TP53 = _corpus("NM_000546.6", 200, 1400)
PUC = _corpus("L09137.2", 0, 2686)


def _run(worker: str, request: dict) -> dict:
    if worker == "flanking-pair":
        from pcr_tools.pipeline import run
    elif worker == "pair-and-probe":
        from pcr_tools.probe import run
    elif worker == "discriminating-pair":
        from pcr_tools.discriminate import run
    elif worker == "single-primer":
        from pcr_tools.single import run
    elif worker == "outward-pair":
        from pcr_tools.inverse import run
    elif worker == "loop-set":
        from pcr_tools.loop_set import run
    elif worker == "nested":
        from pcr_tools.nested import run
    else:
        raise AssertionError(worker)
    return run(request)


#: One request per worker that produces a design, and where its template lives.
WORKERS: dict[str, dict] = {
    "flanking-pair": {"template": TP53, "how_many": 2},
    "pair-and-probe": {"template": TP53, "how_many": 2},
    "discriminating-pair": {
        "template": TP53,
        "at": 700,
        "alleles": [TP53[700], "A" if TP53[700] != "A" else "G"],
        "geometry": "arms-two-tube",
    },
    "single-primer": {
        "template": TP53,
        "target_start": 600,
        "target_length": 200,
        "direction": "forward",
        "how_many": 2,
    },
    "outward-pair": {
        "template": PUC,
        "enzyme": "SpeI",
        "inverse_branch": "restriction-self-ligation",
        "left_end_phosphate": "unresolved",
        "right_end_phosphate": "unresolved",
        "circularization_provenance": "unresolved",
        "linear_control_provenance": "unresolved",
        "methylation_branch": "unresolved",
        "how_many": 2,
        "assay": {"id": "inverse-pcr", "name": "Inverse PCR", "defaults": {}},
    },
    "loop-set": {"template": TP53, "how_many": 2},
    # This engine took no background at all, and the gap was recorded rather
    # than papered over: nesting is chosen *because* the target is rare in a
    # large background, which is when a specificity check matters most.
    "nested": {
        "template": TP53,
        "how_many": 2,
        "outer": {"product_max": 1200},
        "inner": {"product_max": 700},
    },
}


def _templates(worker: str) -> str:
    return WORKERS[worker]["template"]


def _blocks(answer: dict) -> list[dict]:
    """Every off-target block in an answer, whatever this engine calls a design."""
    if "off_targets" in answer:
        return [answer["off_targets"]]
    found = []
    for key in ("pairs", "assays", "sets", "primers", "nests"):
        for entry in answer.get(key) or []:
            off = entry.get("off_targets")
            if off is None:
                continue
            # A nest reports one block per set of oligos that share a tube,
            # because that is the difference its scan is about.
            found.extend(off.values() if "checked" not in off else [off])
    return found


@pytest.mark.parametrize("background", [">relative\n", "", "   \n\t"])
def test_an_explicit_empty_background_is_refused_instead_of_falling_back_to_template(
    background: str,
):
    from pcr_tools.screen import contigs_for

    with pytest.raises(ValueError, match="no DNA sequence"):
        contigs_for(
            {"background": background},
            template=TP53,
            name="target",
        )


def test_a_mixed_background_with_an_empty_record_is_refused():
    from pcr_tools.screen import contigs_from_text

    with pytest.raises(ValueError, match=r"record.*no DNA sequence"):
        contigs_from_text(">real\nACGT\n>empty\n", label="background", default_name="background")


def test_template_only_specificity_uppercases_soft_mask_without_erasing_it():
    from pcr_tools.screen import contigs_for

    contigs, template_only, _ = contigs_for(
        {},
        template="ACGTacgtACGT",
        name="masked",
    )

    assert template_only is True
    assert contigs[0].sequence == "ACGTACGTACGT"


def test_shared_screen_records_an_explicit_assay_temperature():
    from pcr_tools.presets import polymerase
    from pcr_tools.screen import oligos
    from pcr_tools.specificity import Contig

    primer = "GCTAGCTTGACCTGAGGACA"
    result = oligos(
        {"left": primer},
        [Contig("template", primer)],
        reaction=polymerase("qpcr-dye").reaction,
        temperature_c=60.0,
    )

    assert result["temperature_c"] == 60.0
    assert result["method"]["binding_score"]["temperature_c"] == 60.0


@pytest.mark.parametrize("worker", sorted(WORKERS))
def test_the_scan_runs_and_says_how_far_it_looked(worker: str):
    answer = _run(worker, dict(WORKERS[worker]))

    background = answer["background"]
    assert background["checked"] is True
    assert background["template_only"] is True, (
        "no background was given, so the template is what should have been scanned"
    )
    # Said rather than left out: this run does not know about anywhere else.
    assert "no background was given" in background["note"].lower()

    blocks = _blocks(answer)
    assert blocks, f"{worker} produced no design to scan, so this proves nothing"
    for block in blocks:
        assert block["checked"] is True


@pytest.mark.parametrize("worker", sorted(WORKERS))
def test_a_second_copy_of_the_target_is_found_and_named(worker: str):
    """The question the whole step exists to answer.

    A background holding the target twice gives every design a real second
    site. A worker that took the background and ignored it looks identical to
    one that scanned and found nothing — which is why this asserts on what was
    found rather than on the request having been accepted.
    """
    template = _templates(worker)
    answer = _run(worker, {**WORKERS[worker], "background": f">twice\n{template}{template}"})

    background = answer["background"]
    assert background["template_only"] is False
    assert background["bases"] == 2 * len(template)
    assert background["note"] == "", "a real background has nothing to apologise for"

    blocks = _blocks(answer)
    assert blocks
    assert any(block.get("site_count", 0) >= 2 for block in blocks), (
        "every oligo sits twice on a duplicated background; none was reported"
    )


@pytest.mark.parametrize("worker", sorted(WORKERS))
def test_a_background_too_large_to_scan_is_refused_before_the_search(worker: str):
    """Refused up front rather than after a search that will be thrown away."""
    from pcr_tools.specificity import MAX_BACKGROUND_BASES, BackgroundTooLarge

    with pytest.raises(BackgroundTooLarge):
        _run(
            worker,
            {**WORKERS[worker], "background": "A" * (MAX_BACKGROUND_BASES + 1)},
        )


def test_exact_intended_product_matching_keeps_a_same_size_paralogue():
    """A size match alone must not excuse a different internal sequence."""
    from pcr_tools.screen import _without_the_intended
    from pcr_tools.specificity import Contig, OffTarget, Site

    def product(start: int, end: int) -> OffTarget:
        forward = Site("AAAA", "left", "background", start, "forward", 0, -8.0, 60.0)
        reverse = Site("TTTT", "right", "background", end, "reverse", 0, -8.0, 60.0)
        return OffTarget("background", start, end, end - start + 1, forward, reverse)

    products = [product(0, 3), product(4, 7)]
    background = [Contig("background", "ACGTGGGGTGCA")]

    remaining = _without_the_intended(
        products,
        4,
        intended_sequence="ACGT",
        contigs=background,
    )

    assert remaining == [products[1]]


def test_iupac_seed_scan_keeps_overlapping_possible_sites_and_unknown_matches():
    """Ambiguous sequence must not hide adjacent possible binding sites."""
    from pcr_tools.presets import polymerase
    from pcr_tools.specificity import Contig, sites_for

    reaction = polymerase("taq-standard").reaction
    sites = sites_for(
        "AAAA",
        "left",
        [Contig("ambiguous", "AAAAAN")],
        reaction=reaction,
        max_mismatches=1,
        min_dg=0.0,
    )
    forward = [site for site in sites if site.orientation == "forward"]

    # Starts 0, 1 and 2 are all possible: the last window contains N, which
    # is compatible with A.  A consuming regex match used to return only 0.
    assert [site.three_prime_at for site in forward] == [3, 4, 5]
    assert [site.mismatches for site in forward] == [0, 0, 0]
    assert [site.mismatch_upper_bound for site in forward] == [0, 0, 1]
    assert forward[-1].ambiguous_bases == 1


def test_terminal_review_counts_the_terminal_mismatch_but_not_the_seed():
    from pcr_tools.presets import polymerase
    from pcr_tools.specificity import Contig, sites_for

    reaction = polymerase("taq-standard").reaction
    background = [Contig("relative", "ACGA")]

    retained = sites_for(
        "ACGT",
        "left",
        background,
        reaction=reaction,
        max_mismatches=1,
        min_dg=0.0,
        include_terminal_mismatch=True,
    )
    assert next(site for site in retained if site.orientation == "forward").mismatches == 1

    rejected = sites_for(
        "ACGT",
        "left",
        background,
        reaction=reaction,
        max_mismatches=0,
        min_dg=0.0,
        include_terminal_mismatch=True,
    )
    assert not [site for site in rejected if site.orientation == "forward"]
