"""Recorded answers on real sequences.

These exist to catch the change nobody meant to make. Five assays share two
engines; when something under them moves, the cheapest way to know whether it
moved anything visible is to have written down what visible looked like.

A failure here is not necessarily a bug. It is a change to what a user would
be handed, and it needs a sentence in the commit message either way.
"""

from __future__ import annotations

import pytest
from corpus import record
from goldens import check

from pcr_tools.pipeline import run


@pytest.mark.parametrize("accession", ["NM_000546.6", "L09137.2", "X65299.1"])
def test_the_best_pair_is_first_and_the_order_sheet_agrees(accession: str):
    """True of every result, on every template, whatever the goldens say.

    A golden records what happened; this records what must always happen, and
    the difference matters when somebody regenerates a golden without reading
    it.
    """
    answer = run({"template": record(accession).fasta(), "how_many": 4})
    scores = [pair["score"] for pair in answer["pairs"]]
    assert scores == sorted(scores)
    assert answer["order_sheet"][0]["sequence"] == answer["pairs"][0]["left"]["sequence"]


def _reduce_nested(answer: dict) -> dict:
    """A nested answer's stable core, in the same spirit as the shared one."""
    return {
        "engine": answer["engine"],
        "assay": (answer.get("assay") or {}).get("id", ""),
        "nesting": answer["nesting"],
        "outer_considered": answer["outer_considered"],
        "rejected": [entry["reason"] for entry in answer["rejected"]],
        "nests": [
            {
                "outer": [
                    nest["outer"]["left"]["sequence"],
                    nest["outer"]["right"]["sequence"],
                    nest["outer"]["product_size"],
                ],
                "inner": [
                    nest["inner"]["left"]["sequence"],
                    nest["inner"]["right"]["sequence"],
                    nest["inner"]["product_size"],
                ],
                "moved_in": nest["moved_in"],
                "tm_note": nest.get("tm_note"),
            }
            for nest in answer["nests"]
        ],
        "order_sheet": [oligo["name"] for oligo in answer["order_sheet"]],
    }


def test_inverse_pcr_reading_out_of_puc19():
    """Pin the standard two-flank/no-internal-cut branch on pUC19.

    The historical golden for this accession described the removed split-anchor
    two-circle topology.  The replacement golden must be recorded deliberately
    in a qualified pinned Primer3 runtime; this test names the current stable
    shape so that re-baselining cannot resurrect `cut`/`circles`.
    """
    from pcr_tools.inverse import run as run_inverse

    answer = run_inverse(
        {
            "template": record("L09137.2").fasta(),
            "enzyme": "SpeI",
            "inverse_branch": "restriction-self-ligation",
            "left_end_phosphate": "unresolved",
            "right_end_phosphate": "unresolved",
            "circularization_provenance": "unresolved",
            "linear_control_provenance": "unresolved",
            "methylation_branch": "unresolved",
            "how_many": 3,
            "assay": {"id": "inverse-pcr", "name": "Inverse PCR", "defaults": {}},
            "constraints": {"product_min": 200, "product_max": 900},
        }
    )
    reduced = {
        "engine": answer["engine"],
        "digest": answer["digest"],
        "circle": answer["circle"],
        "usable_enzymes": [entry["enzyme"] for entry in answer["enzymes"] if entry["usable"]],
        "pairs": [
            {
                "left": pair["left"]["sequence"],
                "right": pair["right"]["sequence"],
                "left_at": pair["left_at"]["start"],
                "right_at": pair["right_at"]["start"],
                "known_span": pair["known_span"],
                "product_size": pair["product_size"],
            }
            for pair in answer["pairs"]
        ],
        "order_sheet": [oligo["name"] for oligo in answer["order_sheet"]],
    }
    check("inverse-pcr__L09137.2__two-flank-v2", answer, reduced=reduced)
