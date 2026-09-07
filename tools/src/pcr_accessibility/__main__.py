"""How open a template is at each place a primer would have to bind.

    echo '{"template": "ACGT...", "windows": {"0:left": [12, 20]}}' \
        | python -m pcr_accessibility

Answers `{"checked": true, "model": ..., "openings": {...}}`, or
`{"error": {"kind": ..., "detail": ...}}` with a non-zero exit code. The error
vocabulary matches the rest of PCRStudio so the caller branches on `kind`.

The one line that matters is `params_load_DNA_Mathews2004`. Left on its
defaults ViennaRNA folds with Turner 2004 RNA parameters and reports a DNA
duplex several kcal/mol too stable — measurably worse than not asking. Loading
the DNA set also resets the model's geometric constants, so it happens before
anything folds and never again.
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any

#: How far apart two bases may be and still pair. What blocks a primer landing
#: is local structure; a pairing four kilobases away is not, and allowing it
#: makes the fold quadratic in template length for no gain.
MAX_BASE_PAIR_SPAN = 150

#: The sliding window the local fold is computed in.
WINDOW = 150

DNA_MODEL = "ViennaRNA, Mathews 2004 DNA parameters"
RNA_MODEL = "ViennaRNA, Turner 2004 RNA parameters"


def _fail(kind: str, detail: str) -> int:
    json.dump({"error": {"kind": kind, "detail": detail}}, sys.stdout)
    sys.stdout.write("\n")
    return 1


def _answer(answer: dict[str, Any]) -> int:
    """Serialised in full before anything is written. `json.dump` streams, so a
    value it cannot encode leaves half an answer on stdout followed by a
    traceback on stderr, and the reader downstream sees truncated JSON and
    blames the transport rather than the value."""
    try:
        encoded = json.dumps(answer)
    except (TypeError, ValueError) as error:
        return _fail("toolFailed", f"the answer could not be encoded as JSON: {error}")
    sys.stdout.write(encoded)
    sys.stdout.write("\n")
    return 0


#: What ViennaRNA folds at unless told otherwise, and what a PCR does not do.
DEFAULT_CELSIUS = 37.0

# Keep the model controls explicit rather than inheriting process-global
# ViennaRNA defaults.  The values are the documented defaults for the
# partition-function path, but making them part of this worker's contract
# prevents a ViennaRNA upgrade from silently changing a saved accessibility
# ranking.  `salt` is ViennaRNA's default molar salt value; it is intentionally
# not the PCR reaction's Mg/salt model, which belongs to Primer3.
DANGLES = 2
NO_GU = 0
NO_CLOSING_GU = 0
NO_LONELY_PAIRS = 0
TETRA_LOOP = 1
SPECIAL_HAIRPINS = 1
SALT_M = 1.021


def _configure_model(RNA: Any, celsius: float, molecule: str) -> str:
    """Load the explicit DNA or RNA parameter set and pin every model switch."""
    if molecule == "DNA":
        RNA.params_load_DNA_Mathews2004()
        model = DNA_MODEL
    elif molecule == "RNA":
        # ViennaRNA 2.7.2 exposes this exact SWIG entry point. Loading it also
        # resets geometric defaults to RNA, so it happens before the explicit
        # model switches below, just like the DNA branch.
        RNA.params_load_RNA_Turner2004()
        model = RNA_MODEL
    else:
        raise ValueError("`molecule` must be `DNA` or `RNA`")
    RNA.cvar.temperature = celsius
    for name, value in {
        "dangles": DANGLES,
        "noGU": NO_GU,
        "no_closingGU": NO_CLOSING_GU,
        "noLonelyPairs": NO_LONELY_PAIRS,
        "tetra_loop": TETRA_LOOP,
        "special_hp": SPECIAL_HAIRPINS,
        "salt": SALT_M,
        # Both entry points in this worker operate on linear sequences.
        "circ": 0,
    }.items():
        setattr(RNA.cvar, name, value)
    return model




def _configure_dna_model(RNA: Any, celsius: float) -> str:
    """Backward-compatible DNA-only helper used by the retained fold contract tests."""
    return _configure_model(RNA, celsius, "DNA")


DNA_BASES = frozenset("ACGT")
RNA_BASES = frozenset("ACGU")


def _temperature(value: Any) -> float:
    """Read a finite Celsius value without coercing malformed JSON."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("`celsius` must be a finite number")
    temperature = float(value)
    if not math.isfinite(temperature):
        raise ValueError(f"`celsius` must be finite, not {value!r}")
    if not 0.0 < temperature < 100.0:
        raise ValueError(f"folding at {temperature} degrees is outside anything a reaction runs at")
    return temperature


def _sequence(value: Any, *, name: str, molecule: str) -> str:
    """Return a strict DNA/RNA sequence; never drop a symbol that changes length."""
    if not isinstance(value, str):
        raise ValueError(f"`{name}` must be a {molecule} sequence")
    sequence = "".join(value.upper().split())
    if not sequence:
        raise ValueError(f"the {name} is empty")
    allowed = DNA_BASES if molecule == "DNA" else RNA_BASES
    # LAMP intake internally normalizes RNA targets to T for sequence-design
    # compatibility. The optional RNA-fold diagnostic reverses that neutral
    # representation here; explicit U input remains U.
    if molecule == "RNA":
        sequence = sequence.replace("T", "U")
    invalid = sorted(set(sequence) - allowed)
    if invalid:
        ordered = sorted(allowed)
        alphabet = (
            ordered[0]
            if len(ordered) == 1
            else ", ".join(ordered[:-1]) + " and " + ordered[-1]
        )
        raise ValueError(
            f"the {name} contains {', '.join(invalid)}, but this {molecule} folding "
            f"worker accepts only {alphabet}"
        )
    return sequence


def _windows(value: Any, *, sequence_length: int) -> dict[str, tuple[int, int]]:
    """Validate half-open [start, length] windows before folding."""
    if not isinstance(value, dict):
        raise ValueError("`windows` must be an object of name to [start, length]")

    checked: dict[str, tuple[int, int]] = {}
    for raw_name, span in value.items():
        name = str(raw_name)
        if not isinstance(span, (list, tuple)) or len(span) != 2:
            raise ValueError(f"window `{name}` is not [start, length]")
        start, length = span
        if (
            isinstance(start, bool)
            or isinstance(length, bool)
            or not isinstance(start, int)
            or not isinstance(length, int)
        ):
            raise ValueError(f"window `{name}` needs integer start and length")
        if start < 0 or length <= 0 or start + length > sequence_length:
            raise ValueError(
                f"window `{name}` at {start}..{start + length} falls outside a "
                f"sequence of {sequence_length} bases"
            )
        checked[name] = (start, length)
    return checked


def profile(
    template: str,
    windows: dict[str, tuple[int, int]],
    celsius: float = DEFAULT_CELSIUS,
    *,
    molecule: str = "DNA",
) -> dict[str, Any]:
    """Probability that each named stretch of template is entirely unpaired.

    Read the numbers as a ranking, not as probabilities to threshold. Folding
    is cooperative, so no twenty-base window is very likely to be wholly
    unpaired; what is meaningful is one site being orders of magnitude more
    open than another.
    """
    celsius = _temperature(celsius)
    molecule = str(molecule).upper()
    sequence = _sequence(template, name="template", molecule=molecule)
    windows = _windows(windows, sequence_length=len(sequence))

    import RNA  # imported here so a missing package is a clean error, not a traceback

    model = _configure_model(RNA, celsius, molecule)
    # Folded at the temperature the reaction anneals at, not at ViennaRNA's
    # own 37 degrees. A template is roughly twice as open at 58 as at 37, and
    # the primers are trying to bind it at 58.
    if not windows:
        return {
            "checked": False,
            "model": model,
            "molecule": molecule,
            "celsius": celsius,
            "openings": {},
        }

    longest = max(length for _, length in windows.values())
    # up[i][u] is the probability that the u bases ending at position i, counting
    # from one, are all unpaired.
    up = RNA.pfl_fold_up(sequence, longest, WINDOW, MAX_BASE_PAIR_SPAN)

    openings: dict[str, Any] = {}
    for name, (start, length) in windows.items():
        ending = start + length
        # `_windows` already guarantees this, and retaining the assertion here
        # protects the result if a future folding backend changes its array
        # convention.
        if ending >= len(up):
            raise ValueError(f"window `{name}` could not be represented by the fold")
        openings[name] = {
            "start": start + 1,
            "length": length,
            "unpaired": float(up[ending][length]),
        }

    return {
        "checked": True,
        "model": model,
        "molecule": molecule,
        "celsius": celsius,
        "openings": openings,
    }


def folds(oligos: dict[str, str], celsius: float) -> dict[str, Any]:
    """How hard each oligo folds on itself, against how hard it binds its partner.

    A free energy on its own says nothing here: it scales with length and GC,
    so a hundred-and-twenty-base overlap folds harder than a forty-base one
    whatever either is made of. What is comparable is the fraction — how much
    of the duplex the overlap is *meant* to form is instead spent on itself.

    Both numbers are computed at the assembly temperature rather than at
    ViennaRNA's own 37 degrees. Gibson runs at 50; a structure that melts at 45
    is not a structure the reaction ever meets.
    """
    celsius = _temperature(celsius)
    cleaned = {
        str(name): _sequence(sequence, name=f"oligo `{name}`", molecule="DNA")
        for name, sequence in oligos.items()
    }

    import RNA  # imported here so a missing package is a clean error

    model = _configure_model(RNA, celsius, "DNA")

    measured: dict[str, Any] = {}
    for name, sequence in cleaned.items():
        if len(sequence) < 4:
            continue
        structure, energy = RNA.fold(sequence)
        # Against its own perfect complement: the duplex this overlap exists to
        # make. Nothing else is the right comparison — the partner is the same
        # bases read the other way, by construction.
        partner = sequence[::-1].translate(str.maketrans("ACGT", "TGCA"))
        intended = RNA.duplexfold(sequence, partner).energy
        measured[name] = {
            "length": len(sequence),
            "dg": round(float(energy), 2),
            "duplex_dg": round(float(intended), 2),
            # Floored at zero. Both energies are negative for anything with
            # structure, so the ratio is positive; an oligo with no structure
            # at all folds at exactly 0.0 kcal/mol and would otherwise report
            # a fraction of "-0.0", which reads as a measurement rather than
            # as the absence of one.
            "fraction": (round(max(0.0, float(energy) / float(intended)), 4) if intended else 0.0),
            "structure": structure,
        }

    return {
        "checked": True,
        "model": model,
        "molecule": "DNA",
        "celsius": celsius,
        "folds": measured,
    }


def main() -> int:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        return _fail("invalidRequest", f"stdin was not valid JSON: {error}")
    if not isinstance(request, dict):
        return _fail("invalidRequest", "expected a JSON object on stdin")

    try:
        celsius = _temperature(request.get("celsius", DEFAULT_CELSIUS))
    except ValueError as error:
        return _fail("invalidRequest", str(error))

    # Which question is being asked, decided by which key arrived.
    if "oligos" in request:
        raw_oligos = request.get("oligos") or {}
        if not isinstance(raw_oligos, dict):
            return _fail("invalidRequest", "`oligos` must be an object of name to sequence")
        oligos = {}
        for name, sequence in raw_oligos.items():
            if not isinstance(sequence, str):
                return _fail("invalidRequest", f"oligo `{name}` is not a sequence")
            oligos[str(name)] = sequence
        try:
            answer = folds(oligos, celsius)
        except ImportError:
            return _fail("toolMissing", "ViennaRNA is not installed in this environment")
        except Exception as error:
            return _fail("toolFailed", f"{type(error).__name__}: {error}")
        return _answer(answer)

    template = request.get("template")
    raw_windows = request.get("windows") or {}
    if not isinstance(template, str):
        return _fail("invalidRequest", "`template` must be a sequence")
    try:
        answer = profile(template, raw_windows, celsius, molecule=str(request.get("molecule") or "DNA"))
    except ImportError:
        return _fail("toolMissing", "ViennaRNA is not installed in this environment")
    except ValueError as error:
        return _fail("invalidRequest", str(error))
    except Exception as error:
        return _fail("toolFailed", f"{type(error).__name__}: {error}")
    return _answer(answer)


if __name__ == "__main__":
    sys.exit(main())
