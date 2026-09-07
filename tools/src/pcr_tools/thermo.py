"""Oligo thermodynamics, as Primer3 computes them.

Every number here comes from the same nearest-neighbour model Primer3 and IDT
use, so a melting temperature quoted in PCRStudio matches the one quoted by the
tool a lab already trusts.

Energies are returned in kcal/mol. `primer3-py` reports cal/mol, which is off by
a thousand from every figure printed in a protocol.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from primer3.thermoanalysis import ThermoAnalysis

#: The other strand, base by base. Plain bases only; ambiguity codes are
#: handled through degenerate's table below, which complements the set a code
#: stands for rather than the letter itself.
_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


#: How many bases at the 3' end decide whether extension starts.
#:
#: Five, which is what Primer3 uses and what the primer-design literature means
#: by 3' end stability.
THREE_PRIME_BASES = 5


def reverse_complement(sequence: str) -> str:
    """The other strand, read 5' to 3'.

    Lives here, in the module with no dependencies of its own, because three
    other modules want it and the alternative is three copies.

    IUPAC ambiguity codes are complemented as themselves — an R becomes a Y,
    not an R — so a search for a motif still finds it on the other strand
    where the input sequence carries one. The plain-base path stays on the
    translation table, which is what everything hot goes through.
    """
    if not set(sequence.upper()) - set("ACGTN"):
        return sequence.translate(_COMPLEMENT)[::-1]
    from .degenerate import COMPLEMENT_CODE

    return "".join(COMPLEMENT_CODE.get(base, "N") for base in reversed(sequence.upper()))


def count_overlapping(haystack: str, needle: str) -> int:
    """How many times `needle` appears in `haystack`, overlaps included.

    `str.count` counts non-overlapping runs only, so it finds "AAA" twice in
    "AAAAA" where there are three. The same lookahead trick the restriction
    site search uses — match without consuming — is what counts every start.
    """
    if not needle:
        return 0
    return len(re.findall(f"(?={re.escape(needle)})", haystack))


#: Reproducible calculation-reference conditions for low-level Primer3 calls.
#:
#: They are computational defaults only. They do not describe a universal
#: PCR mix and must not be surfaced as bench chemistry unless a named profile
#: or protocol independently supplies the same values.
DEFAULT_CONDITIONS: dict[str, float] = {
    "mv_conc": 50.0,  # monovalent cations, mM
    "dv_conc": 1.5,  # divalent cations (Mg2+), mM
    "dntp_conc": 0.6,  # mM
    "dna_conc": 50.0,  # nM
}

# Keep every post-search thermodynamic measurement on the same model as the
# Primer3 candidate search.  Primer3's numeric setting is exposed separately
# because the design API uses the integer form while primer3-py's
# ThermoAnalysis API uses the name form.
TM_METHOD = "santalucia"
# Generation 1 pins Primer3's recommended SantaLucia salt correction.
# Reaction concentrations are inputs to the calculation, not a trigger for a
# hidden change of model identity.
SALT_CORRECTIONS_METHOD = "santalucia"
PRIMER3_TM_FORMULA = 1
PRIMER3_SALT_CORRECTIONS = 1

# These are Primer3/primer3-py's documented low-level defaults, made explicit
# here so a library-default change cannot silently alter a saved result. The
# project has no additive-chemistry input contract, so DMSO and formamide stay
# at zero; the factor and inactive bound-fraction sentinel are still passed
# explicitly for reproducibility.
PRIMER3_TEMP_C = 37.0
PRIMER3_MAX_LOOP = 30
PRIMER3_MAX_NN_LENGTH = 60
PRIMER3_OUTPUT_STRUCTURE = False
PRIMER3_TEMP_ONLY = 0
PRIMER3_DMSO_CONC = 0.0
PRIMER3_DMSO_FACTOR = 0.6
PRIMER3_FORMAMIDE_CONC = 0.0
PRIMER3_ANNEALING_TEMP_C = -10.0

PRIMER3_LOW_LEVEL_CONTROLS = {
    "temp_c_default": PRIMER3_TEMP_C,
    "max_loop": PRIMER3_MAX_LOOP,
    "max_nn_length": PRIMER3_MAX_NN_LENGTH,
    "output_structure": PRIMER3_OUTPUT_STRUCTURE,
    "temp_only": PRIMER3_TEMP_ONLY,
    "dmso_conc": PRIMER3_DMSO_CONC,
    "dmso_fact": PRIMER3_DMSO_FACTOR,
    "formamide_conc": PRIMER3_FORMAMIDE_CONC,
    "annealing_temp_c": PRIMER3_ANNEALING_TEMP_C,
}

# A future alternative salt-correction branch must be explicit and versioned;
# there is deliberately no Mg-only threshold here.

#: The alphabet an oligo may be written in. A primer we are going to quote a
#: melting temperature for cannot contain an ambiguity code.
UNAMBIGUOUS = frozenset("ACGT")

#: What a template may contain. Ambiguity is allowed here and handled by
#: refusing to place a primer over it, which is a different thing from
#: refusing the template.
TEMPLATE_ALPHABET = frozenset("ACGTRYSWKMBDHVN")


class SequenceError(ValueError):
    """A sequence that cannot be analysed, with a reason a person can act on."""


def clean(sequence: str, *, what: str = "sequence") -> str:
    """Upper-case a sequence and reject anything that is not a real base.

    Whitespace is formatting and may be ignored. Digits and punctuation are
    refused here: GenBank coordinate extraction belongs to the intake parser,
    and dropping digits at this lower-level boundary could change an oligo or
    its thermodynamic result without leaving a trace.
    """
    invalid_symbols = sorted(
        {character for character in sequence if not character.isspace() and not character.isalpha()}
    )
    if invalid_symbols:
        raise SequenceError(
            f"the {what} contains formatting symbols "
            + ", ".join(repr(symbol) for symbol in invalid_symbols)
            + "; provide a parsed DNA sequence"
        )

    stripped = "".join(c for c in sequence.upper() if not c.isspace())
    if not stripped:
        raise SequenceError(f"the {what} is empty")

    unknown = sorted(set(stripped) - UNAMBIGUOUS)
    if unknown:
        listed = ", ".join(unknown)
        raise SequenceError(
            f"the {what} contains {listed}, which is not A, C, G or T. "
            "Ambiguity codes are not supported yet."
        )
    return stripped


def clean_template(sequence: str) -> str:
    """Tidy a template without flattening what its case and codes mean.

    Case survives, because lowercase is how a masked genome marks its repeats
    and Primer3 reads it. Ambiguity codes survive, because a template with a
    few of them is ordinary and the right answer is to keep primers off them.

    Whitespace is formatting. Coordinates are extracted only by the intake
    parser from a recognised GenBank ORIGIN block; digits in direct input are
    refused here. A dash from an alignment or an asterisk from a translated
    sequence must not disappear, because silently deleting it changes every
    downstream coordinate and can make a design appear to fit a molecule that
    was never supplied.
    """
    invalid_symbols = sorted(
        {character for character in sequence if not character.isspace() and not character.isalpha()}
    )
    if invalid_symbols:
        raise SequenceError(
            "the template contains formatting symbols "
            + ", ".join(repr(symbol) for symbol in invalid_symbols)
            + "; remove alignment gaps or punctuation and provide a DNA sequence"
        )

    stripped = "".join(c for c in sequence if c.isalpha())
    if not stripped:
        raise SequenceError("the template is empty")

    unknown = sorted(set(stripped.upper()) - TEMPLATE_ALPHABET)
    if unknown:
        raise SequenceError(
            f"the template contains {', '.join(unknown)}, which is neither a base "
            "nor an IUPAC ambiguity code"
        )
    return stripped


@dataclass(frozen=True)
class Structure:
    """One predicted secondary structure."""

    found: bool
    #: Free energy in kcal/mol. Negative means it forms; the more negative, the
    #: more stable, and the more of the primer is unavailable to the template.
    dg: float
    #: Melting temperature of the structure itself, in Celsius.
    tm: float


@dataclass(frozen=True)
class OligoReport:
    """Everything worth knowing about one oligo on its own."""

    sequence: str
    length: int
    gc_percent: float
    tm: float
    hairpin: Structure
    self_dimer: Structure
    #: How hard this primer's 3' end holds on to the sequence it is meant to
    #: bind. A 3' end that grips too well will also grip somewhere wrong, and
    #: extension starts from the 3' end, so that is where mispriming becomes a
    #: product.
    #:
    #: The last five bases against their own complement, which is what the
    #: 3' end meets on the template.
    #:
    #: Two wrong versions of this shipped before it was measured. Against the
    #: primer *itself* it was a self-dimer quantity wearing an end-stability
    #: name. Against the whole primer's complement it was the free energy of
    #: the entire duplex, which is dominated by overall GC content and ranked
    #: an AT-rich 3' end as gripping harder than a GC-rich one. Only the
    #: terminal five bases answer the question the name asks.
    #:
    #: Checked against Primer3's own `END_STABILITY`, which uses a different
    #: reference and so a different scale, but ranks primers identically.
    three_prime_dg: float


def _structure(result: Any) -> Structure:
    return Structure(
        found=bool(result.structure_found),
        dg=round(result.dg / 1000.0, 2),
        tm=round(result.tm, 1),
    )


def gc_percent(sequence: str) -> float:
    """Proportion of G and C, as a percentage."""
    return round(100.0 * sum(c in "GC" for c in sequence) / len(sequence), 1)


def melting_temperature(sequence: str, **conditions: float) -> float:
    """Melting temperature in Celsius under the given reaction conditions."""
    settings = {**DEFAULT_CONDITIONS, **conditions}
    return round(_analysis(settings).calc_tm(sequence), 1)


def salt_correction_for_conditions(settings: dict[str, float]) -> tuple[str, int]:
    """Return the versioned Primer3 salt-correction model for Gen-1.

    Gen-1 pins Primer3's recommended SantaLucia salt-correction setting
    (``PRIMER_SALT_CORRECTIONS=1``).  Divalent and dNTP concentrations remain
    explicit inputs to that model.  We deliberately do *not* switch to the
    Owczarzy model from an internal Mg-only cutoff: Owczarzy's ionic regime
    depends on the joint monovalent/divalent context, and changing the Tm model
    changes candidate validity/ranking.  A future Owczarzy branch therefore
    needs an explicit, versioned profile/model identity rather than inference
    from one concentration.
    """
    _ = settings  # concentrations are consumed by Primer3; they do not choose the model
    return SALT_CORRECTIONS_METHOD, PRIMER3_SALT_CORRECTIONS


def _analysis(settings: dict[str, float]) -> ThermoAnalysis:
    """A configured Primer3 thermodynamics worker for one reaction.

    Construct the worker explicitly so reported Tm, hairpins, dimers and end
    stabilities use the same versioned model as the candidate search. Reaction
    concentrations do not silently select a different salt-correction family.
    """
    analysis = ThermoAnalysis()
    salt_method, _ = salt_correction_for_conditions(settings)
    # `temp_c` is normally Primer3's 37 °C default.  The specificity scanner
    # supplies the actual assay anneal/hold temperature explicitly because
    # ΔG is temperature-dependent; leaving that value implicit makes a
    # 60–68 °C PCR look like it was screened at a different reaction step.
    thermo_args = dict(settings)
    thermo_args.update(
        {
            "dmso_conc": PRIMER3_DMSO_CONC,
            "dmso_fact": PRIMER3_DMSO_FACTOR,
            "formamide_conc": PRIMER3_FORMAMIDE_CONC,
            "annealing_temp_c": PRIMER3_ANNEALING_TEMP_C,
            "temp_c": settings.get("temp_c", PRIMER3_TEMP_C),
            "max_loop": PRIMER3_MAX_LOOP,
            "max_nn_length": PRIMER3_MAX_NN_LENGTH,
            "output_structure": PRIMER3_OUTPUT_STRUCTURE,
            "temp_only": PRIMER3_TEMP_ONLY,
            "tm_method": TM_METHOD,
            "salt_corrections_method": salt_method,
        }
    )
    analysis.set_thermo_args(**thermo_args)
    return analysis


#: The longest oligo primer3 will fold.
#:
#: Its thermodynamic alignment refuses anything past this with "At least one
#: sequence must be equal to or shorter than 60bp", which is a limit of the
#: implementation rather than of the chemistry. It matters because one assay
#: routinely exceeds it: the original Gibson protocol specifies overlaps of
#: forty to a hundred and twenty bases, so most of its legitimate range is
#: longer than primer3 will look at. Measured — a 61-base overlap crashed the
#: assembly engine outright.
FOLDABLE_BASES = 60

#: What a structure that was never measured looks like.
#:
#: Zeroes, and `found` false — the same shape as "looked and found nothing",
#: which is why every caller that can exceed the limit has to say which of the
#: two it means rather than reading the numbers.
UNMEASURED = Structure(found=False, dg=0.0, tm=0.0)


def analyse(sequence: str, **conditions: float) -> OligoReport:
    """Measure one oligo: composition, Tm, and what it does to itself.

    An oligo longer than `FOLDABLE_BASES` comes back with its composition and
    its melting temperature measured and its structures unmeasured, rather than
    raising: the length limit belongs to primer3's aligner, not to the
    question, and an assembly overlap of eighty bases is an ordinary thing to
    be asked about.

    Use `folded()` to tell an unmeasured structure from a clean one.

    Raises:
        SequenceError: if the sequence is empty or not unambiguous DNA.
    """
    oligo = clean(sequence, what="oligo")
    settings = {**DEFAULT_CONDITIONS, **conditions}
    foldable = len(oligo) <= FOLDABLE_BASES

    analysis = _analysis(settings)

    return OligoReport(
        sequence=oligo,
        length=len(oligo),
        gc_percent=gc_percent(oligo),
        tm=round(analysis.calc_tm(oligo), 1),
        hairpin=(_structure(analysis.calc_hairpin(oligo)) if foldable else UNMEASURED),
        self_dimer=(_structure(analysis.calc_homodimer(oligo)) if foldable else UNMEASURED),
        # The 3-prime end is five bases whatever the oligo's length, so this one
        # is always measurable.
        three_prime_dg=end_stability(oligo, THREE_PRIME_BASES, **conditions),
    )


def folded(report: OligoReport) -> bool:
    """Whether this oligo's structures were actually measured.

    False for an oligo past primer3's length limit, whose hairpin and self-dimer
    are absent rather than zero. Reading those numbers without asking this is
    how "too long to check" becomes "checked and clean".
    """
    return report.length <= FOLDABLE_BASES


def end_stability(oligo: str, bases: int, *, at: str = "3", **conditions: float) -> float:
    """How tightly the last `bases` of one end bind, in kcal/mol.

    The duplex free energy of that stretch against its own complement — how
    hard the very end of the primer holds on, which is what decides whether
    the polymerase can start there.

    Args:
        at: `3` for the 3' end, `5` for the 5' end. Both are asked for: an
            ordinary primer extends from its 3' end, but a composite oligo's
            5' half becomes a primer later, against sequence that does not
            exist yet when it is first made.

    Two different lengths are in use in this project and they are not
    interchangeable. Five bases is what the ordinary primer report quotes;
    six is what the isothermal literature states its thresholds against, and a
    threshold checked against the wrong length is checked against a different
    number — measured on one 20-mer, -3.36 over its last six and a different
    figure over its last five.
    """
    settings = {**DEFAULT_CONDITIONS, **conditions}
    end = oligo[-bases:] if at == "3" else oligo[:bases]
    analysis = _analysis(settings)
    return round(analysis.calc_end_stability(end, reverse_complement(end)).dg / 1000.0, 2)


def pair_dimer(left: str, right: str, **conditions: float) -> Structure:
    """The structure the two primers of a pair form with each other.

    ``temp_c`` is an optional Primer3 thermodynamic evaluation temperature.
    It is intentionally separate from the Tm calculation: callers that judge
    whether a duplex competes during a real hold should pass that hold, while
    legacy/general structure checks retain Primer3's 37 °C default.
    """
    settings = {**DEFAULT_CONDITIONS, **conditions}
    analysis = _analysis(settings)
    return _structure(
        analysis.calc_heterodimer(
            clean(left, what="left primer"),
            clean(right, what="right primer"),
        )
    )


def report_to_dict(report: OligoReport) -> dict[str, Any]:
    """The report as plain JSON-ready data."""
    return asdict(report)
