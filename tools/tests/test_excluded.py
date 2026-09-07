"""A stretch no primer may sit on, across every worker whose page offers one.

The region picker has offered an "avoid" box on every assay that shows it since
it was written, and only one of the engines behind those assays had a
field to put the answer in. So somebody could mark a repeat, or the variant
they are trying to type around, and be handed a primer sitting squarely on it —
with nothing in the result to say the request had been dropped.

Each worker is asked the same question here: does blocking the stretch a primer
was found in move the primer? A test that only checked the request was accepted
would pass on a worker that took the regions and ignored them.
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

#: How wide a stretch to block. Wide enough that a primer cannot simply shuffle
#: a few bases along and still overlap what was blocked.
BLOCK = 200


def _run(worker: str, request: dict) -> dict:
    if worker == "flanking-pair":
        from pcr_tools.pipeline import run
    elif worker == "pair-and-probe":
        from pcr_tools.probe import run
    elif worker == "single-primer":
        from pcr_tools.single import run
    elif worker == "nested":
        from pcr_tools.nested import run
    elif worker == "tiling-scheme":
        from pcr_tools.tiling import run
    elif worker == "loop-set":
        from pcr_tools.loop_set import run
    elif worker == "discriminating-pair":
        from pcr_tools.discriminate import run
    else:
        raise AssertionError(worker)
    return run(request)


WORKERS: dict[str, dict] = {
    "flanking-pair": {"template": TP53, "how_many": 3},
    "pair-and-probe": {"template": TP53, "how_many": 3},
    "single-primer": {
        "template": TP53,
        "target_start": 600,
        "target_length": 200,
        "direction": "forward",
        "how_many": 3,
    },
    "nested": {
        "template": TP53,
        "how_many": 3,
        "outer": {"product_max": 1200},
        "inner": {"product_max": 700},
    },
    # The three with no region to point at. A tiling scheme and a loop set both
    # cover the whole sequence, and a genotyping assay is anchored on one base —
    # so none of them was ever shown a region picker, and the exclusion box was
    # only ever inside one.
    "tiling-scheme": {
        "template": TP53,
        "constraints": {"product_min": 300, "product_max": 500},
    },
    "loop-set": {"template": TP53, "how_many": 3},
    "discriminating-pair": {
        "template": TP53,
        "at": 700,
        "alleles": [TP53[700], "A" if TP53[700] != "A" else "G"],
        "geometry": "arms-two-tube",
    },
}


def _left_edges(worker: str, answer: dict) -> list[int]:
    """Where each design's leftmost oligo begins, whatever this engine returns."""
    if worker == "flanking-pair":
        return [pair["left_at"]["start"] for pair in answer["pairs"]]
    if worker == "pair-and-probe":
        # The probe is the oligo an exclusion most often has to move.
        return [assay["probe"]["at"] for assay in answer["assays"]]
    if worker == "single-primer":
        return [primer["at"] for primer in answer["primers"]]
    if worker == "tiling-scheme":
        # Where each amplicon's left primer begins.
        return [tile["start"] for tile in answer["tiles"]]
    if worker == "loop-set":
        # All eight regions of every set: any one of the six oligos landing on
        # a blocked stretch is the failure, not just the first.
        return [region["at"] for entry in answer["sets"] for region in entry["regions"]]
    if worker == "discriminating-pair":
        # The common primer only — the allele-specific ones sit on the variant.
        return [partner["at"] for partner in answer["partners"]]
    return [nest["outer"]["left_at"]["start"] for nest in answer["nests"]]


@pytest.mark.parametrize("worker", sorted(WORKERS))
def test_blocking_a_stretch_moves_the_oligos_off_it(worker: str):
    free = _left_edges(worker, _run(worker, dict(WORKERS[worker])))
    assert free, f"{worker} produced no design, so this proves nothing"

    at = min(free)
    # The genotyping partner sits some way from the variant, so a block that
    # starts at it has to reach far enough back to matter.
    start = max(at - 20, 0)
    blocked = _run(worker, {**WORKERS[worker], "excluded": [[start, BLOCK]]})
    after = _left_edges(worker, blocked)

    assert not any(start <= edge < start + BLOCK for edge in after), (
        f"{worker} was told to avoid {start}..{start + BLOCK} and put an oligo there"
    )


@pytest.mark.parametrize("worker", sorted(WORKERS))
def test_a_region_that_is_not_a_pair_of_numbers_is_refused_by_name(worker: str):
    """Refused rather than dropped.

    The wire shape is a list of two-element lists, which is easy to get wrong
    in a way that silently excludes the wrong stretch — and a silently wrong
    exclusion is worse than none, because the result looks like it honoured it.
    """
    with pytest.raises(ValueError, match="start and a length"):
        _run(worker, {**WORKERS[worker], "excluded": [[10, 20, 30]]})
