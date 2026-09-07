"""Whether the template is open where the primer is supposed to land.

Primer3 checks a primer against itself, against its partner, and for mispriming
elsewhere. It never asks the other question: is the template folded shut at the
site we picked? A perfect primer against a closed hairpin is a reaction that
fails for a reason nothing in the design report mentions, and it is the usual
explanation when a GC-rich target refuses to amplify.

ViennaRNA can answer it. This module does not call ViennaRNA — it runs
`pcr_accessibility` in a process of its own and reads JSON back. That is a
licence boundary rather than a stylistic one: this package imports Primer3,
which is GPLv2, and ViennaRNA carries conditions the GPL does not allow to be
added. Two programs talking over a pipe keep their own terms; one process
importing both would not.

The practical consequence depends on the engine contract. ViennaRNA evidence is
OPTIONAL in Gen-1. In particular, Gibson/junction overlap folding is diagnostic
only: the pinned ViennaRNA salt model is not an assay-calibrated representation
of proprietary assembly master-mix ionic conditions, so availability or fold
score must not alter validity, deterministic ranking, or the default candidate.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from .process_boundary import ProcessOutputLimitExceeded, run_bounded_text

#: A local fold of a few kilobases is fast; this exists so a pathological input
#: cannot hold a request open.
TIMEOUT_SECONDS = 30

WORKER = "pcr_accessibility"
WORKER_STDOUT_LIMIT = 16 * 1024 * 1024
WORKER_STDERR_LIMIT = 2 * 1024 * 1024


def _worker_failure(note: str) -> Accessibility:
    return Accessibility(checked=False, model="", openings={}, note=note)


def _error_detail(answer: dict[str, Any]) -> str:
    error = answer.get("error")
    if isinstance(error, dict) and isinstance(error.get("detail"), str):
        return error["detail"] or "no reason given"
    return "no reason given"


def _temperature(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("the folding step returned an invalid temperature")
    temperature = float(value)
    if not math.isfinite(temperature):
        raise ValueError("the folding step returned a non-finite temperature")
    return temperature


def _parse_profile_answer(answer: Any, returncode: int) -> Accessibility:
    if not isinstance(answer, dict):
        return _worker_failure("The folding step answered with a JSON value, not an object.")
    if returncode != 0 or "error" in answer:
        return _worker_failure(f"Template folding was not checked: {_error_detail(answer)}")
    if not isinstance(answer.get("checked"), bool):
        return _worker_failure("The folding step returned an invalid checked flag.")
    if not isinstance(answer.get("model", ""), str):
        return _worker_failure("The folding step returned an invalid model name.")
    raw_openings = answer.get("openings", {})
    if not isinstance(raw_openings, dict):
        return _worker_failure("The folding step returned invalid opening data.")

    openings: dict[str, Opening] = {}
    try:
        for name, raw in raw_openings.items():
            if not isinstance(name, str) or not isinstance(raw, dict):
                raise ValueError("invalid opening record")
            start = raw.get("start")
            length = raw.get("length")
            unpaired = raw.get("unpaired")
            if isinstance(start, bool) or not isinstance(start, int) or start < 1:
                raise ValueError("invalid opening start")
            if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
                raise ValueError("invalid opening length")
            if isinstance(unpaired, bool) or not isinstance(unpaired, (int, float)):
                raise ValueError("invalid opening probability")
            probability = float(unpaired)
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise ValueError("invalid opening probability")
            openings[name] = Opening(start=start - 1, length=length, unpaired=probability)
        celsius = _temperature(answer.get("celsius"))
    except (ValueError, OverflowError) as error:
        return _worker_failure(f"The folding step returned invalid data: {error}.")

    return Accessibility(
        checked=answer["checked"],
        model=answer["model"],
        celsius=celsius,
        temperatures_c=(celsius,) if celsius is not None else (),
        openings=openings,
    )


def _parse_fold_answer(answer: Any, returncode: int) -> Folds:
    if not isinstance(answer, dict):
        return Folds(
            checked=False,
            model="",
            folds={},
            note="The folding step answered with a JSON value, not an object.",
        )
    if returncode != 0 or "error" in answer:
        return Folds(
            checked=False,
            model="",
            folds={},
            note=f"The folding step failed: {_error_detail(answer)}",
        )
    if not isinstance(answer.get("checked"), bool):
        return Folds(False, "", {}, note="The folding step returned an invalid checked flag.")
    if not isinstance(answer.get("model", ""), str):
        return Folds(False, "", {}, note="The folding step returned an invalid model name.")
    raw_folds = answer.get("folds", {})
    if not isinstance(raw_folds, dict):
        return Folds(False, "", {}, note="The folding step returned invalid fold data.")

    measured: dict[str, Fold] = {}
    try:
        for name, raw in raw_folds.items():
            if not isinstance(name, str) or not isinstance(raw, dict):
                raise ValueError("invalid fold record")
            length = raw.get("length")
            if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
                raise ValueError("invalid fold length")
            numbers: dict[str, float] = {}
            for field in ("dg", "duplex_dg", "fraction"):
                value = raw.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"invalid fold {field}")
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f"invalid fold {field}")
                numbers[field] = number
            if numbers["fraction"] < 0:
                raise ValueError("invalid fold fraction")
            structure = raw.get("structure", "")
            if not isinstance(structure, str):
                raise ValueError("invalid fold structure")
            measured[name] = Fold(length=length, structure=structure, **numbers)
        celsius = _temperature(answer.get("celsius"))
    except (ValueError, OverflowError) as error:
        return Folds(False, "", {}, note=f"The folding step returned invalid data: {error}.")

    return Folds(
        checked=answer["checked"],
        model=answer["model"],
        celsius=celsius,
        folds=measured,
    )


@dataclass(frozen=True)
class Opening:
    """How open one stretch of template is."""

    start: int
    length: int
    #: Probability the whole stretch is unpaired. Compare these; do not
    #: threshold them.
    unpaired: float


@dataclass
class Accessibility:
    """What the fold said about a set of candidate sites."""

    checked: bool
    model: str
    openings: dict[str, Opening]
    note: str = ""
    #: The temperature the fold was computed at.
    #:
    #: Reported because it is not obvious and it is not 37: the template is
    #: about twice as open at the temperature a reaction anneals at, and a
    #: number computed at the wrong one would be quietly answering a different
    #: question.
    celsius: float | None = None
    #: All temperatures represented by this result. The pipeline can merge
    #: worker calls when candidate pairs use different annealing temperatures.
    temperatures_c: tuple[float, ...] = ()


def available() -> bool:
    """Whether the folding program answers in this environment."""
    try:
        finished = run_bounded_text(
            [sys.executable, "-m", WORKER],
            input_text='{"template": "ACGTACGTACGTACGTACGT", "windows": {}}',
            timeout=TIMEOUT_SECONDS,
            stdout_limit=WORKER_STDOUT_LIMIT,
            stderr_limit=WORKER_STDERR_LIMIT,
        )
    except (OSError, subprocess.SubprocessError, ProcessOutputLimitExceeded):
        return False
    return finished.returncode == 0


def profile(
    template: str,
    windows: dict[str, tuple[int, int]],
    celsius: float | None = None,
    *,
    molecule: str = "DNA",
) -> Accessibility:
    """How open the template is at each named window.

    Never raises. A stage that cannot run reports why in `note`, because a
    missing section of a report reads as "nothing to report", and here that
    would be the opposite of the truth.
    """
    if not windows:
        return Accessibility(
            checked=False, model="", openings={}, note="No candidate sites to check."
        )

    request = json.dumps(
        {
            "template": template,
            "windows": {k: list(v) for k, v in windows.items()},
            "molecule": molecule,
            **({"celsius": celsius} if celsius is not None else {}),
        }
    )

    try:
        finished = run_bounded_text(
            [sys.executable, "-m", WORKER],
            input_text=request,
            timeout=TIMEOUT_SECONDS,
            stdout_limit=WORKER_STDOUT_LIMIT,
            stderr_limit=WORKER_STDERR_LIMIT,
        )
    except ProcessOutputLimitExceeded as error:
        return Accessibility(
            checked=False,
            model="",
            openings={},
            note=f"The folding step exceeded its {error.stream} output limit.",
        )
    except subprocess.TimeoutExpired:
        return Accessibility(
            checked=False,
            model="",
            openings={},
            note=f"The folding step did not finish within {TIMEOUT_SECONDS} seconds.",
        )
    except (OSError, subprocess.SubprocessError) as error:
        return Accessibility(
            checked=False,
            model="",
            openings={},
            note=f"The folding step failed to run: {error}",
        )

    try:
        answer = json.loads(finished.stdout or "{}")
    except json.JSONDecodeError:
        return Accessibility(
            checked=False,
            model="",
            openings={},
            note="The folding step answered with something that was not JSON.",
        )

    parsed = _parse_profile_answer(answer, finished.returncode)
    if not parsed.checked:
        return parsed
    if not parsed.model:
        return _worker_failure(
            "The folding step marked the profile checked without naming its model."
        )
    if parsed.celsius is None:
        return _worker_failure(
            "The folding step marked the profile checked without a finite temperature."
        )

    expected = set(windows)
    received = set(parsed.openings)
    missing = sorted(expected - received)
    extra = sorted(received - expected)
    if missing or extra:
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        return _worker_failure(
            "The folding step did not return exactly the requested windows: "
            + "; ".join(detail)
            + "."
        )
    for name, (start, length) in windows.items():
        opening = parsed.openings[name]
        if opening.start != start or opening.length != length:
            return _worker_failure(
                f"The folding step changed window `{name}` from "
                f"[{start}, {length}] to [{opening.start}, {opening.length}]."
            )
    return parsed


def accessibility_to_dict(result: Accessibility) -> dict[str, Any]:
    """The profile as plain data."""
    return {
        "checked": result.checked,
        "model": result.model,
        "celsius": result.celsius,
        "temperatures_c": list(result.temperatures_c),
        "note": result.note,
        "openings": {
            name: {
                "start": opening.start + 1,
                "length": opening.length,
                "unpaired": opening.unpaired,
            }
            for name, opening in result.openings.items()
        },
    }


# ── The other question the same boundary answers ────────────────────────────
#
# Whether an oligo folds on itself, at any length. Primer3's aligner refuses
# anything past sixty bases and the original Gibson protocol specifies forty to
# a hundred and twenty, so most of that chemistry's own range was longer than
# the check could see — and every overlap in it came back as "nothing looked",
# which a reader has to know to distinguish from "nothing found".

#: There is deliberately no threshold here. Read `fraction` as diagnostic evidence.
#:
#: A threshold was tried and the measurements refused it. Over 400 random
#: overlaps of 40 to 120 bases at 50% GC, folded at 50 °C against their own
#: perfect complements, the fraction ran to a 99th percentile of 0.103 and a
#: maximum of 0.154 — while sequences with a 10-base stem-loop deliberately
#: planted in them had a *median* of 0.158 and reached down to 0.093. The two
#: populations overlap. Free energy alone is worse, because it scales with
#: length: ordinary 120-mers reach -12.3 kcal/mol, which is where a planted
#: 12-base stem sits. Longest stacked helix is worse again — ordinary 120-mers
#: reach 19 paired bases, a planted 16-base stem starts at 15.
#:
#: The reason is not noise, it is physics: a hundred-and-twenty-base DNA
#: sequence at 50 °C genuinely has structure, and whether that structure blocks
#: an overhang from finding its partner depends on kinetics this does not
#: resolve. So the number is reported and ranked on, and nothing is refused for
#: it — the same decision, for the same reason, that the template-accessibility
#: profile records in its own docstring.
FOLD_IS_A_RANKING = True


@dataclass
class Fold:
    """How hard one oligo folds on itself, against how hard it binds its partner."""

    length: int
    #: Free energy of the fold at the assembly temperature, kcal/mol.
    dg: float
    #: Free energy of the duplex it exists to form, at the same temperature.
    duplex_dg: float
    #: The first as a fraction of the second.
    #:
    #: The comparable number — a raw free energy scales with length and GC, so
    #: it cannot be used to compare a forty-base overlap with a hundred-and-
    #: twenty-base one. Compare these; do not threshold them. See
    #: `FOLD_IS_A_RANKING` for what was measured and why.
    fraction: float
    #: Dot-bracket, so a reader can see where the stem is rather than trust it.
    structure: str


@dataclass
class Folds:
    """What the fold said about a set of oligos."""

    checked: bool
    model: str
    folds: dict[str, Fold]
    note: str = ""
    celsius: float | None = None


def fold_oligos(oligos: dict[str, str], celsius: float) -> Folds:
    """How hard each oligo folds on itself, at the temperature it has to work at.

    This boundary itself never raises; the calling engine decides whether the
    evidence is advisory or release-gating. Junction/Gibson strict mode treats
    an unchecked result as a refusal because fold evidence participates in its
    overlap ranking, while advisory consumers may retain an explicit unchecked
    record.
    """
    if not oligos:
        return Folds(checked=False, model="", folds={}, note="Nothing to fold.")

    request = json.dumps({"oligos": oligos, "celsius": celsius})
    try:
        finished = run_bounded_text(
            [sys.executable, "-m", WORKER],
            input_text=request,
            timeout=TIMEOUT_SECONDS,
            stdout_limit=WORKER_STDOUT_LIMIT,
            stderr_limit=WORKER_STDERR_LIMIT,
        )
    except ProcessOutputLimitExceeded as error:
        return Folds(
            checked=False,
            model="",
            folds={},
            note=f"The folding step exceeded its {error.stream} output limit.",
        )
    except subprocess.TimeoutExpired:
        return Folds(
            checked=False,
            model="",
            folds={},
            note=f"The folding step did not finish within {TIMEOUT_SECONDS} seconds.",
        )
    except (OSError, subprocess.SubprocessError) as error:
        return Folds(
            checked=False, model="", folds={}, note=f"The folding step failed to run: {error}"
        )

    try:
        answer = json.loads(finished.stdout or "{}")
    except json.JSONDecodeError:
        return Folds(
            checked=False,
            model="",
            folds={},
            note="The folding step answered with something that was not JSON.",
        )

    parsed = _parse_fold_answer(answer, finished.returncode)
    if not parsed.checked:
        return parsed
    if not parsed.model:
        return Folds(
            checked=False,
            model="",
            folds={},
            note="The folding step marked the oligo folds checked without naming its model.",
        )
    if parsed.celsius is None:
        return Folds(
            checked=False,
            model="",
            folds={},
            note="The folding step marked the oligo folds checked without a finite temperature.",
        )

    expected = set(oligos)
    received = set(parsed.folds)
    missing = sorted(expected - received)
    extra = sorted(received - expected)
    if missing or extra:
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        return Folds(
            checked=False,
            model="",
            folds={},
            note="The folding step did not return exactly the requested oligos: "
            + "; ".join(detail)
            + ".",
        )
    for name, sequence in oligos.items():
        expected_length = len("".join(sequence.split()))
        if parsed.folds[name].length != expected_length:
            return Folds(
                checked=False,
                model="",
                folds={},
                note=(
                    f"The folding step changed oligo `{name}` length from "
                    f"{expected_length} to {parsed.folds[name].length}."
                ),
            )
    return parsed
