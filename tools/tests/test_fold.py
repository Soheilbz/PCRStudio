"""Folding an oligo of any length, and what Gibson does with the answer.

Primer3's aligner refuses anything past sixty bases. The original Gibson
protocol specifies forty to a hundred and twenty, so most of that chemistry's
own range was longer than the check could see — and every overlap in it came
back reporting a hairpin temperature of zero, which a reader has to already
know to distinguish from "nothing was found".

ViennaRNA folds any length. It answers over the same process boundary the
template-accessibility check uses, and for the same licensing reason: this
package imports Primer3, which is GPLv2, and ViennaRNA carries conditions the
GPL does not allow to be added.
"""

from __future__ import annotations

import pathlib
import subprocess
from types import SimpleNamespace

import pytest

from pcr_accessibility.__main__ import (
    DANGLES,
    NO_CLOSING_GU,
    NO_GU,
    NO_LONELY_PAIRS,
    SALT_M,
    SPECIAL_HAIRPINS,
    TETRA_LOOP,
    _configure_dna_model,
)
from pcr_accessibility.__main__ import folds as worker_folds
from pcr_accessibility.__main__ import profile as worker_profile
from pcr_tools.accessibility import fold_oligos
from pcr_tools.junction import MOST_FOLDED, run

CORPUS = pathlib.Path(__file__).parent / "corpus"

ASSEMBLY_CELSIUS = 50.0


def _corpus(accession: str) -> str:
    raw = (CORPUS / f"{accession}.fasta").read_text().splitlines()
    return "".join(line.strip() for line in raw if not line.startswith(">"))


PUC = _corpus("L09137.2")


def reverse_complement(sequence: str) -> str:
    return sequence[::-1].translate(str.maketrans("ACGT", "TGCA"))


def test_worker_pins_viennarna_model_switches_instead_of_using_process_defaults():
    class CVar:
        temperature = None

    class FakeRNA:
        cvar = CVar()
        loaded = False

        @staticmethod
        def params_load_DNA_Mathews2004():
            FakeRNA.loaded = True

    _configure_dna_model(FakeRNA, 58.0)

    assert FakeRNA.loaded is True
    assert FakeRNA.cvar.temperature == 58.0
    assert FakeRNA.cvar.dangles == DANGLES == 2
    assert FakeRNA.cvar.noGU == NO_GU == 0
    assert FakeRNA.cvar.no_closingGU == NO_CLOSING_GU == 0
    assert FakeRNA.cvar.noLonelyPairs == NO_LONELY_PAIRS == 0
    assert FakeRNA.cvar.tetra_loop == TETRA_LOOP == 1
    assert FakeRNA.cvar.special_hp == SPECIAL_HAIRPINS == 1
    assert FakeRNA.cvar.salt == SALT_M == 1.021
    assert FakeRNA.cvar.circ == 0


class TestTheBoundary:
    """What comes back over the pipe, before anything uses it."""

    def test_an_oligo_far_past_primer3s_limit_is_folded(self):
        """The whole point. A hundred and twenty bases is inside Gibson's range."""
        long = PUC[:120]
        answer = fold_oligos({"long": long}, ASSEMBLY_CELSIUS)

        assert answer.checked, answer.note
        fold = answer.folds["long"]
        assert fold.length == 120
        assert len(fold.structure) == 120
        assert fold.duplex_dg < 0, "a hundred and twenty perfect base pairs is stable"

    def test_a_planted_stem_folds_and_a_plain_sequence_does_not(self):
        """Measured against a case built to have an answer.

        Not a threshold — see `FOLD_IS_A_RANKING` — but the two have to come out
        in the right order or the number is measuring nothing.
        """
        stem = "GCGCGGCGCGGCGCGC"
        answer = fold_oligos(
            {
                "plain": PUC[200:250],
                "hairpin": PUC[200:217] + stem + "TTTT" + reverse_complement(stem),
            },
            ASSEMBLY_CELSIUS,
        )
        assert answer.checked, answer.note
        assert answer.folds["hairpin"].fraction > answer.folds["plain"].fraction * 3

    def test_no_fraction_is_ever_negative(self):
        """An oligo with no structure folds at exactly zero.

        Divided by a negative duplex energy that reads as `-0.0`, which looks
        like a measurement rather than the absence of one.
        """
        answer = fold_oligos({"open": "ATATATATATATATATATATATATATATAT"}, ASSEMBLY_CELSIUS)
        assert answer.checked, answer.note
        assert answer.folds["open"].fraction >= 0.0

    def test_it_folds_at_the_temperature_it_was_asked_to(self):
        """A structure that melts at 45 is not one the assembly meets.

        Folding at ViennaRNA's own 37 degrees would report it anyway, which is
        the mistake the accessibility check had to be corrected for once.
        """
        stem = "GCGCGGCGCGGCGCGC"
        oligo = PUC[200:217] + stem + "TTTT" + reverse_complement(stem)

        cool = fold_oligos({"one": oligo}, 37.0).folds["one"]
        warm = fold_oligos({"one": oligo}, 70.0).folds["one"]
        assert cool.dg < warm.dg, "everything folds harder when it is colder"

    def test_malformed_profile_output_is_reported_not_raised(self, monkeypatch):
        """An optional worker must not turn a design into a transport traceback."""
        import pcr_tools.accessibility as accessibility

        monkeypatch.setattr(
            accessibility,
            "run_bounded_text",
            lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="[1, 2]"),
        )

        answer = accessibility.profile("ACGTACGT", {"left": (0, 4)})

        assert not answer.checked
        assert "JSON value" in answer.note

    @pytest.mark.parametrize(
        "output",
        [
            '{"checked":true,"model":"test","celsius":50,"openings":{"other":{"start":1,"length":4,"unpaired":0.5}}}',
            '{"checked":true,"model":"test","celsius":50,"openings":{"left":{"start":2,"length":4,"unpaired":0.5}}}',
        ],
    )
    def test_partial_or_relabelled_profile_output_is_not_reported_as_checked(
        self, monkeypatch, output
    ):
        import pcr_tools.accessibility as accessibility

        monkeypatch.setattr(
            accessibility,
            "run_bounded_text",
            lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output),
        )

        answer = accessibility.profile("ACGTACGT", {"left": (0, 4), "right": (4, 4)})

        assert not answer.checked
        assert "exactly the requested windows" in answer.note

    def test_checked_profile_without_temperature_is_not_reported_as_checked(self, monkeypatch):
        import pcr_tools.accessibility as accessibility

        monkeypatch.setattr(
            accessibility,
            "run_bounded_text",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=0,
                stdout='{"checked":true,"model":"test","openings":{"left":{"start":1,"length":4,"unpaired":0.5}}}',
            ),
        )

        answer = accessibility.profile("ACGTACGT", {"left": (0, 4)})

        assert not answer.checked
        assert "finite temperature" in answer.note

    @pytest.mark.parametrize(
        "output",
        [
            '{"checked":true,"model":"test","celsius":50,"folds":{"one":{"length":4,"dg":-1,"duplex_dg":-2,"fraction":0.5}}}',
            '{"checked":true,"model":"test","celsius":50,"folds":{"other":{"length":4,"dg":-1,"duplex_dg":-2,"fraction":0.5}}}',
        ],
    )
    def test_partial_or_relabelled_oligo_fold_is_not_reported_as_checked(self, monkeypatch, output):
        import pcr_tools.accessibility as accessibility

        monkeypatch.setattr(
            accessibility,
            "run_bounded_text",
            lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output),
        )

        answer = accessibility.fold_oligos({"one": "ACGT", "two": "TGCA"}, 50.0)

        assert not answer.checked
        assert "exactly the requested oligos" in answer.note

    def test_checked_oligo_fold_without_temperature_is_not_reported_as_checked(self, monkeypatch):
        import pcr_tools.accessibility as accessibility

        monkeypatch.setattr(
            accessibility,
            "run_bounded_text",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=0,
                stdout='{"checked":true,"model":"test","folds":{"one":{"length":4,"dg":-1,"duplex_dg":-2,"fraction":0.5}}}',
            ),
        )

        answer = accessibility.fold_oligos({"one": "ACGT"}, 50.0)

        assert not answer.checked
        assert "finite temperature" in answer.note

    def test_malformed_fold_record_is_reported_not_raised(self, monkeypatch):
        """Bad numeric data is a failed optional check, never a raw ValueError."""
        import pcr_tools.accessibility as accessibility

        monkeypatch.setattr(
            accessibility,
            "run_bounded_text",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=0,
                stdout='{"checked":true,"model":"test","celsius":50,"folds":{"one":{"length":4,"dg":"bad"}}}',
            ),
        )

        answer = accessibility.fold_oligos({"one": "ACGT"}, 50.0)

        assert not answer.checked
        assert "invalid data" in answer.note

    def test_profile_subprocess_failure_is_reported_not_raised(self, monkeypatch):
        import pcr_tools.accessibility as accessibility

        def fail(*args, **kwargs):
            raise subprocess.SubprocessError("worker transport failed")

        monkeypatch.setattr(accessibility, "run_bounded_text", fail)

        answer = accessibility.profile("ACGTACGT", {"left": (0, 4)})

        assert not answer.checked
        assert "failed to run" in answer.note

    def test_fold_subprocess_failure_is_reported_not_raised(self, monkeypatch):
        import pcr_tools.accessibility as accessibility

        def fail(*args, **kwargs):
            raise subprocess.SubprocessError("worker transport failed")

        monkeypatch.setattr(accessibility, "run_bounded_text", fail)

        answer = accessibility.fold_oligos({"one": "ACGT"}, 50.0)

        assert not answer.checked
        assert "failed to run" in answer.note

    def test_unrepresentably_large_fold_number_is_reported_not_raised(self, monkeypatch):
        """A huge JSON integer must not escape as an OverflowError."""
        import pcr_tools.accessibility as accessibility

        monkeypatch.setattr(
            accessibility,
            "run_bounded_text",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=0,
                stdout='{"checked":true,"model":"test","celsius":50,"folds":{"one":{"length":4,"dg":1e1000,"duplex_dg":-1,"fraction":0}}}',
            ),
        )

        answer = accessibility.fold_oligos({"one": "ACGT"}, 50.0)

        assert not answer.checked
        assert "invalid data" in answer.note

    def test_the_worker_rejects_fractional_window_coordinates(self):
        with pytest.raises(ValueError, match="integer"):
            worker_profile("ACGT" * 30, {"left": [1.5, 20]})

    def test_the_worker_rejects_a_window_outside_the_sequence(self):
        with pytest.raises(ValueError, match="falls outside"):
            worker_profile("ACGT" * 5, {"left": [10, 20]})

    def test_the_worker_does_not_drop_invalid_oligo_symbols(self):
        with pytest.raises(ValueError, match="only A, C, G and T"):
            worker_folds({"bad": "ACGT-ACGT"}, 50.0)


class TestGibson:
    """What the engine does with the answer."""

    def _assemble(self, vector: str, insert: str, how: str = "gibson") -> dict:
        return run(
            {
                "segments": [
                    {"name": "vector", "kind": "amplified", "sequence": vector},
                    {"name": "insert", "kind": "amplified", "sequence": insert},
                ],
                "circular": False,
                "method": how,
            }
        )
