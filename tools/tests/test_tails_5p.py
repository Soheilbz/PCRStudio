"""A 5' tail that belongs to what happens after the PCR.

Two assays here produce primers that almost never go into a tube as designed. A
tiled scheme is pooled and sequenced, so every oligo carries the platform's
adapter; a degenerate pair is usually read by Sanger off a universal primer, so
every oligo carries M13. Neither could say so.

The thing worth testing is not that the bases arrive — that is a concatenation.
It is which melting temperature the result quotes afterwards. A tail is not on
the template in the first round, so a temperature computed over the whole
molecule describes a duplex that does not exist when it matters, and it is the
number somebody sets a block from.
"""

from __future__ import annotations

import pathlib
import random
import typing

import pytest

from pcr_tools import tail_5p

CORPUS = pathlib.Path(__file__).parent / "corpus"

#: A real Nextera overhang and a real M13 forward tail, for length realism.
NEXTERA = "TCGTCGGCAGCGTCAGATGTGTATAAGAGACAG"
M13 = "TGTAAAACGACGGCCAGT"


def _corpus(accession: str, start: int, length: int) -> str:
    raw = (CORPUS / f"{accession}.fasta").read_text().splitlines()
    seq = "".join(line.strip() for line in raw if not line.startswith(">"))
    return seq[start : start + length]


TP53 = _corpus("NM_000546.6", 200, 1400)


def _family() -> str:
    generator = random.Random(9)
    base = TP53[200:900]
    return "\n".join(
        f">iso{index}\n"
        + "".join(
            generator.choice("ACGT") if generator.random() < 0.04 else letter for letter in base
        )
        for index in range(4)
    )


class TestTiling:
    BASE: typing.ClassVar = {
        "template": TP53,
        "constraints": {"product_min": 300, "product_max": 500},
    }

    def _run(self, **extra) -> dict:
        from pcr_tools.tiling import run

        return run({**self.BASE, **extra})


class TestDegenerate:
    def _run(self, **extra) -> dict:
        from pcr_tools.__main__ import run_universal

        return run_universal({"template": _family(), "how_many": 2, **extra})


@pytest.mark.parametrize("bad", ["ACGTN", "ACGU", "ACGT" * 30, "hello"])
def test_a_tail_that_is_not_dna_is_refused_by_name(bad: str):
    """Refused rather than dropped, and rather than attached.

    A degenerate base in a tail is a pool of different adapters, which is not
    what an adapter is for; a whole sequence pasted into the box is a mistake
    that would otherwise be discovered on an invoice.
    """
    with pytest.raises(tail_5p.TailError):
        tail_5p.clean(bad)


def test_whitespace_is_forgiven_because_pasted_sequence_has_it():
    assert tail_5p.clean(" tgtaaaacg acggccagt \n") == M13
