"""LAMP design thermodynamics and versioned geometry policy.

Extracted from :mod:`pcr_tools.loop_set` during the CURRENT closure so geometry,
PrimerExplorer-compatible thermodynamics and caller-window validation can be
reviewed independently from candidate enumeration/search. ``loop_set``
re-exports the public names for backwards compatibility.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .lamp_errors import LoopSetError
from .lamp_profiles import Window, Windows
from .thermo import reverse_complement

# ── PrimerExplorer V5 design thermodynamics ───────────────────────────────
#
# The role-specific LAMP Tm windows are PrimerExplorer design parameters, not
# measurements in a commercial LAMP master mix. PCRStudio evaluates them under
# PrimerExplorer's documented fixed reference conditions (0.1 µM oligo, 50 mM
# Na+, 4 mM Mg2+, Mg converted to an effective Na+ term) using the
# reference-output-compatible model below. Keep that design metric separate
# from `reaction`, which describes the selected kit and is used only for
# kit-context diagnostics.
PE_OLIGO_CONC_M = 0.1e-6
PE_NA_M = 0.050
PE_MG_M = 0.004
PE_EFFECTIVE_NA_M = PE_NA_M + 4.0 * math.sqrt(PE_MG_M)
PE_GAS_CONSTANT = 1.987

# PrimerExplorer V5's public Manual Figure 1.10 provides a useful numeric
# reference-output fixture (six region sequences and their reported Tm values).
# Literal SantaLucia-1996 stack parameters do not reproduce those V5 outputs.
# The SantaLucia-1998 unified nearest-neighbour parameterization below does, to
# <0.1 °C on all six displayed regions under V5's documented reference
# conditions. This is therefore labelled *reference-output compatible*: it is
# not a claim about proprietary PrimerExplorer implementation internals.
_PE_SL98_DH_DS = {
    "AA": (-7.9, -22.2),
    "TT": (-7.9, -22.2),
    "AT": (-7.2, -20.4),
    "TA": (-7.2, -21.3),
    "CA": (-8.5, -22.7),
    "TG": (-8.5, -22.7),
    "GT": (-8.4, -22.4),
    "AC": (-8.4, -22.4),
    "CT": (-7.8, -21.0),
    "AG": (-7.8, -21.0),
    "GA": (-8.2, -22.2),
    "TC": (-8.2, -22.2),
    "CG": (-10.6, -27.2),
    "GC": (-9.8, -24.4),
    "GG": (-8.0, -19.9),
    "CC": (-8.0, -19.9),
}

# SantaLucia 1998 unified ΔG°37 parameters used by PrimerExplorer for its
# six-base primer-end stability calculation.
_PE_SL98_DG37 = {
    "AA": -1.00,
    "TT": -1.00,
    "AT": -0.88,
    "TA": -0.58,
    "CA": -1.45,
    "TG": -1.45,
    "GT": -1.44,
    "AC": -1.44,
    "CT": -1.28,
    "AG": -1.28,
    "GA": -1.30,
    "TC": -1.30,
    "CG": -2.17,
    "GC": -2.24,
    "GG": -1.84,
    "CC": -1.84,
}


def _self_complementary(sequence: str) -> bool:
    return sequence == reverse_complement(sequence)


def primerexplorer_v5_tm(sequence: str) -> float:
    """Reference-output-compatible PrimerExplorer V5 LAMP design Tm.

    The returned value intentionally retains calculation precision. Eligibility
    must not change merely because a UI rounds a value to one or two decimals.
    Public/reporting layers may round for display. This metric is deliberately
    separate from the selected kit's thermodynamic context.
    """
    seq = sequence.upper()
    if not seq or any(base not in "ACGT" for base in seq):
        raise LoopSetError("PrimerExplorer Tm requires an unambiguous DNA oligo.")
    if len(seq) < 2:
        raise LoopSetError("PrimerExplorer Tm requires at least two nucleotides.")

    # SantaLucia-1998 unified nearest-neighbour initiation and stacks.
    dh = 0.2
    ds = -5.7
    for index in range(len(seq) - 1):
        one_h, one_s = _PE_SL98_DH_DS[seq[index : index + 2]]
        dh += one_h
        ds += one_s
    for terminal in (seq[0], seq[-1]):
        if terminal in "AT":
            dh += 2.2
            ds += 6.9

    self_complementary = _self_complementary(seq)
    if self_complementary:
        ds += -1.4
    concentration_term = PE_OLIGO_CONC_M if self_complementary else PE_OLIGO_CONC_M / 4.0
    kelvin = (dh * 1000.0) / (ds + PE_GAS_CONSTANT * math.log(concentration_term))
    return kelvin - 273.15 + 16.6 * math.log10(PE_EFFECTIVE_NA_M)


def primerexplorer_v5_end_dg(sequence: str) -> float:
    """PrimerExplorer/SantaLucia-1998 ΔG°37 for one terminal six-mer duplex.

    The V5 threshold is defined on six terminal bases. Reject any other length
    so a future refactor cannot silently turn the published -4.0 kcal/mol rule
    into a different criterion.
    """
    seq = sequence.upper()
    if len(seq) != END_BASES:
        raise LoopSetError(
            f"PrimerExplorer end stability requires exactly {END_BASES} terminal bases."
        )
    if any(base not in "ACGT" for base in seq):
        raise LoopSetError("PrimerExplorer end stability requires unambiguous DNA.")
    dg = sum(_PE_SL98_DG37[seq[i : i + 2]] for i in range(len(seq) - 1))
    dg += 0.98 if seq[0] in "GC" else 1.03
    dg += 0.98 if seq[-1] in "GC" else 1.03
    if _self_complementary(seq):
        dg += 0.43
    return dg


PE_THERMODYNAMIC_MODEL = {
    "id": "primerexplorer-v5-reference-output-compatible-sl98-tm-end-dg",
    "tm_reference": "SantaLucia 1998 unified nearest-neighbour + PrimerExplorer Mg-to-Na correction; verified against V5 Manual Figure 1.10 reference outputs",
    "compatibility_claim": "reference-output-compatible; not a claim about proprietary PrimerExplorer implementation internals",
    "reference_fixture_max_abs_error_c": 0.1,
    "end_stability_reference": "SantaLucia 1998 unified ΔG37 over terminal 6 bases",
    "oligo_concentration_uM": 0.1,
    "sodium_mM": 50.0,
    "magnesium_mM": 4.0,
    "effective_sodium_mM": round(PE_EFFECTIVE_NA_M * 1000.0, 3),
    "role": "LAMP design eligibility/ranking only; not the selected kit master-mix model",
}

# ── The geometry ───────────────────────────────────────────────────────────

# Named, source-scoped numeric evidence for the opt-in Evidence-2026 profile.
# Keeping these outside the dataclass literals makes the active numbers visible
# to PCRStudio's numeric-provenance generator instead of burying them inside a
# compound object. ``EVIDENCE_2026_OUTER_GAP`` is an eligibility envelope; the
# ``*_PREFERRED`` values are ranking-only and never hard-reject a candidate.
EVIDENCE_2026_OUTER_GAP = (0, 60)
EVIDENCE_2026_F2_B2_PREFERRED = (120, 160)
EVIDENCE_2026_OUTER_GAP_PREFERRED = (40, 60)
# NEB's 64–66 °C loop-primer preference is retained as a source-scoped
# reference only. The current candidate Tm values use PrimerExplorer V5's
# published 50 mM Na+ / 4 mM Mg2+ reference model, whereas the current NEB
# design-tool note states 50 mM Na+ / 8 mM Mg2+. Do not compare temperatures
# across those models as if they were the same scale. A future named NEB Tm
# model may activate this reference explicitly.
NEB_2025_LOOP_TM_REFERENCE = (64.0, 66.0)


@dataclass(frozen=True)
class GeometryProfile:
    """Versioned LAMP geometry policy, separate from primer-region windows.

    `valid_*` fields are eligibility envelopes. `preferred_*` fields are soft
    ranking evidence only. Keeping those concepts separate prevents a newer
    empirical preference from silently rewriting PrimerExplorer-compatible
    historical designs.
    """

    id: str
    name: str
    valid_f2_b2_span: tuple[int, int]
    valid_loop_span: tuple[int, int]
    valid_outer_gap: tuple[int, int]
    valid_middle_gap: tuple[int, int]
    preferred_f2_b2_span: tuple[int, int] | None
    preferred_outer_gap: tuple[int, int] | None
    preferred_loop_tm: tuple[float, float] | None
    source: str
    claim: str


PRIMEREXPLORER_V5_GEOMETRY = GeometryProfile(
    id="primerexplorer-v5-compat",
    name="PrimerExplorer V5 public-rule geometry",
    valid_f2_b2_span=(120, 180),
    valid_loop_span=(40, 60),
    valid_outer_gap=(0, 20),
    valid_middle_gap=(0, 100),
    preferred_f2_b2_span=None,
    preferred_outer_gap=None,
    preferred_loop_tm=None,
    source="PrimerExplorer V5 manual / Eiken design guidance",
    claim=(
        "Compatibility envelope for published PrimerExplorer V5 geometry; "
        "not a claim that PCRStudio reproduces PrimerExplorer's proprietary search algorithm."
    ),
)

PCRSTUDIO_EVIDENCE_2026_GEOMETRY = GeometryProfile(
    id="pcrstudio-evidence-2026",
    name="PCRStudio evidence composite 2026",
    # NEB's current tool default allows 0-60 bases for F2-F3/B2-B3. The
    # technical note says 15-60 generally gives good results and identifies
    # 40-60 as the optimum/preferred interval. Do not turn the descriptive
    # 15-base observation into an unsourced hard rejection boundary.
    valid_f2_b2_span=(120, 180),
    valid_loop_span=(40, 60),
    valid_outer_gap=EVIDENCE_2026_OUTER_GAP,
    valid_middle_gap=(0, 100),
    preferred_f2_b2_span=EVIDENCE_2026_F2_B2_PREFERRED,
    preferred_outer_gap=EVIDENCE_2026_OUTER_GAP_PREFERRED,
    # Deliberately inactive until PCRStudio has a versioned Tm model matching
    # the NEB tool's declared ionic reference. Applying 64–66 °C to the V5
    # 4-mM-Mg Tm scale would be cross-model numeric drift.
    preferred_loop_tm=None,
    source="PrimerExplorer V5 geometry + NEB 2025/2026 robustness guidance",
    claim=(
        "Multi-source evidence profile. Wider outer spacing and geometry preference bands "
        "are active; NEB's loop-Tm preference is documentation-only until a matching "
        "versioned NEB thermodynamic model exists. No wet-lab superiority is implied."
    ),
)

GEOMETRY_PROFILES = {
    one.id: one for one in (PRIMEREXPLORER_V5_GEOMETRY, PCRSTUDIO_EVIDENCE_2026_GEOMETRY)
}
DEFAULT_GEOMETRY_PROFILE_ID = PRIMEREXPLORER_V5_GEOMETRY.id


def geometry_profile_for(named: str | None) -> GeometryProfile:
    profile_id = str(named or DEFAULT_GEOMETRY_PROFILE_ID).strip().lower()
    try:
        return GEOMETRY_PROFILES[profile_id]
    except KeyError as error:
        raise LoopSetError(
            "lamp_geometry_profile must be one of: " + ", ".join(sorted(GEOMETRY_PROFILES)) + "."
        ) from error


# Historical compatibility constants remain aliases to the default V5 profile.
F2_B2_SPAN = PRIMEREXPLORER_V5_GEOMETRY.valid_f2_b2_span
LOOP_SPAN = PRIMEREXPLORER_V5_GEOMETRY.valid_loop_span
OUTER_GAP = PRIMEREXPLORER_V5_GEOMETRY.valid_outer_gap
MIDDLE_GAP = PRIMEREXPLORER_V5_GEOMETRY.valid_middle_gap
AMPLICON = F2_B2_SPAN

INNER_LINKERS = {
    "none": "",
    "tttt": "TTTT",
}
DEFAULT_INNER_LINKER_ID = "none"


def inner_linker_for(named: str | None) -> tuple[str, str]:
    linker_id = str(named or DEFAULT_INNER_LINKER_ID).strip().lower()
    try:
        return linker_id, INNER_LINKERS[linker_id]
    except KeyError as error:
        raise LoopSetError(
            "lamp_inner_linker must be one of: " + ", ".join(sorted(INNER_LINKERS)) + "."
        ) from error


# ── Adjusting a set ────────────────────────────────────────────────────────

#: What one region's window may be told, and what each is bounded by.
#:
#: Bounds rather than opinions: a fifteen-base oligo cannot reach any LAMP
#: melting window at any composition, and a fifty-base one is a different kind
#: of molecule. They exist so a slip of a keyboard is refused with a sentence
#: rather than producing a set nothing can satisfy and a report that blames the
#: template for it.
WINDOW_BOUNDS = {
    "tm_min": (40.0, 75.0),
    "tm_max": (40.0, 75.0),
    "length_min": (15, 40),
    "length_max": (15, 40),
}

#: What the geometry of a set may be told, and within what.
#:
#: Broad implementation input bounds for custom geometry. The reviewed V5
#: release defaults are much narrower and are the authority in strict mode.
GEOMETRY_BOUNDS = {
    "f2_b2_span": (100, 400),
    "loop_span": (20, 100),
    "outer_gap": (0, 120),
    "middle_gap": (0, 200),
}

WINDOW_INTEGER_FIELDS = frozenset({"length_min", "length_max"})


def _finite_number(value: Any, *, name: str, integer: bool = False) -> float | int:
    """Validate one caller-supplied numeric field without implicit truncation."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LoopSetError(f"{name} must be a finite number, not {value!r}.")
    if not math.isfinite(float(value)):
        raise LoopSetError(f"{name} must be finite, not {value!r}.")
    if integer and not isinstance(value, int):
        raise LoopSetError(f"{name} must be an integer, not {value!r}.")
    return value


def _adjusted(base: Window, asked: dict[str, Any] | None, role: str) -> Window:
    """Apply an explicit tightening/customisation to one role window."""
    if asked is None or asked == {}:
        return base
    if not isinstance(asked, dict):
        raise LoopSetError(f"The {role} window must be an object, not {asked!r}.")

    strange = sorted(set(asked) - set(WINDOW_BOUNDS))
    if strange:
        raise LoopSetError(
            f"The {role} window does not take "
            + ", ".join(strange)
            + ". It takes: "
            + ", ".join(sorted(WINDOW_BOUNDS))
            + "."
        )

    values = {field: getattr(base, field) for field in WINDOW_BOUNDS}
    for field, given in asked.items():
        low, high = WINDOW_BOUNDS[field]
        number = _finite_number(
            given, name=f"{role}.{field}", integer=field in WINDOW_INTEGER_FIELDS
        )
        if not low <= number <= high:
            raise LoopSetError(
                f"The {role} window's {field} is {number}, and this implementation "
                f"accepts {low} to {high}. That is a software input envelope, not a "
                "claim that every value inside it is an assay-valid LAMP condition."
            )
        values[field] = number

    if (
        values["tm_min"] is not None
        and values["tm_max"] is not None
        and values["tm_min"] > values["tm_max"]
    ):
        raise LoopSetError(
            f"The {role} window melts from {values['tm_min']} to {values['tm_max']} °C, "
            "which is backwards."
        )
    if values["length_min"] > values["length_max"]:
        raise LoopSetError(
            f"The {role} window runs from {values['length_min']} to "
            f"{values['length_max']} bases, which is backwards."
        )
    widened: list[str] = []
    # A missing source bound is open, so supplying one narrows rather than widens.
    if base.tm_min is not None and values["tm_min"] is not None and values["tm_min"] < base.tm_min:
        widened.append("tm_min")
    if base.tm_max is not None and values["tm_max"] is not None and values["tm_max"] > base.tm_max:
        widened.append("tm_max")
    if values["length_min"] < base.length_min:
        widened.append("length_min")
    if values["length_max"] > base.length_max:
        widened.append("length_max")
    if widened:
        raise LoopSetError(
            f"The reviewed {role} LAMP window cannot be widened for {', '.join(widened)} "
            "under the same parameter-set identity. Tightening is allowed; a broader envelope "
            "requires a separately named, versioned LAMP profile."
        )
    return Window(**values)


def _span(asked: Any, base: tuple[int, int], name: str) -> tuple[int, int]:
    """One pair of bounds, checked against what the chemistry can hold.

    Raises:
        LoopSetError: for anything that is not two numbers in order, inside
            what this geometry allows.
    """
    if asked is None:
        return base
    try:
        low, high = (_finite_number(one, name=f"{name} bound", integer=True) for one in asked)
    except (TypeError, ValueError) as error:
        raise LoopSetError(
            f"`{name}` should be a shortest and a longest, not {asked!r}."
        ) from error
    if low > high:
        raise LoopSetError(f"`{name}` runs from {low} to {high}, which is backwards.")

    floor, ceiling = GEOMETRY_BOUNDS[name]
    if low < floor or high > ceiling:
        raise LoopSetError(
            f"`{name}` is {low} to {high}, and this implementation accepts "
            f"{floor} to {ceiling}. This is an input-sanity envelope; the selected "
            "versioned LAMP profile supplies the scientific default."
        )
    if low < base[0] or high > base[1]:
        raise LoopSetError(
            f"The reviewed LAMP `{name}` geometry cannot be widened from {base[0]}–{base[1]} "
            f"to {low}–{high} under the same parameter-set identity. Tightening is allowed; "
            "a wider geometry requires a separately named, versioned LAMP profile."
        )
    return (low, high)


def adjust(
    base: Windows,
    asked: dict[str, Any] | None,
    *,
    geometry_profile: GeometryProfile = PRIMEREXPLORER_V5_GEOMETRY,
) -> tuple[Windows, tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int], list[str]]:
    """Apply explicit overrides to a source-backed LAMP parameter set.

    Generation-1 allows tightening reviewed bounds in every policy mode. Legacy `amplicon` is
    refused because older PCRStudio builds used that name for the F3-B3 whole
    envelope, whereas PrimerExplorer defines the amplified region as F2-B2.
    Reinterpreting an old number silently would change the scientific question.
    """
    profile_defaults = (
        geometry_profile.valid_f2_b2_span,
        geometry_profile.valid_loop_span,
        geometry_profile.valid_outer_gap,
        geometry_profile.valid_middle_gap,
    )
    if asked is None or asked == {}:
        return base, *profile_defaults, []
    if not isinstance(asked, dict):
        raise LoopSetError(f"`windows` must be an object, not {asked!r}.")

    if "amplicon" in asked:
        raise LoopSetError(
            "`windows.amplicon` is a legacy ambiguous field: older builds used it for "
            "the F3-B3 envelope, but PrimerExplorer V5 defines the amplified region as "
            "F2-B2 including both primer regions. Use `f2_b2_span` explicitly."
        )

    known = {"outer", "inner", "loop", "gc_min", "gc_max", *GEOMETRY_BOUNDS}
    strange = sorted(set(asked) - known)
    if strange:
        raise LoopSetError(
            "This does not take "
            + ", ".join(strange)
            + ". It takes: "
            + ", ".join(sorted(known))
            + "."
        )

    overruled: list[str] = []
    for role in ("outer", "inner", "loop"):
        if asked.get(role):
            overruled.append(role)

    raw_gc_min = asked.get("gc_min", base.gc_min)
    raw_gc_max = asked.get("gc_max", base.gc_max)
    gc_min = None if raw_gc_min is None else float(_finite_number(raw_gc_min, name="gc_min"))
    gc_max = None if raw_gc_max is None else float(_finite_number(raw_gc_max, name="gc_max"))
    if gc_min is not None and not 0 <= gc_min <= 100:
        raise LoopSetError("GC bounds must be percentages between 0 and 100.")
    if gc_max is not None and not 0 <= gc_max <= 100:
        raise LoopSetError("GC bounds must be percentages between 0 and 100.")
    if gc_min is not None and gc_max is not None and gc_min > gc_max:
        raise LoopSetError(f"The GC range runs from {gc_min} to {gc_max}%, which is backwards.")
    widened_gc = (base.gc_min is not None and gc_min is not None and gc_min < base.gc_min) or (
        base.gc_max is not None and gc_max is not None and gc_max > base.gc_max
    )
    if widened_gc:
        raise LoopSetError(
            "The reviewed LAMP primer-GC envelope cannot be widened under the same "
            "parameter-set identity. Tightening is allowed; broader coverage requires "
            "a separately named, versioned parameter set."
        )
    if "gc_min" in asked or "gc_max" in asked:
        overruled.append("GC range")

    used = Windows(
        id=base.id,
        name=base.name,
        outer=_adjusted(base.outer, asked.get("outer"), "outer"),
        inner=_adjusted(base.inner, asked.get("inner"), "inner"),
        loop=_adjusted(base.loop, asked.get("loop"), "loop"),
        gc_min=gc_min,
        gc_max=gc_max,
        why=base.why,
    )

    f2_b2_span = _span(asked.get("f2_b2_span"), geometry_profile.valid_f2_b2_span, "f2_b2_span")
    loop_span = _span(asked.get("loop_span"), geometry_profile.valid_loop_span, "loop_span")
    outer_gap = _span(asked.get("outer_gap"), geometry_profile.valid_outer_gap, "outer_gap")
    middle_gap = _span(asked.get("middle_gap"), geometry_profile.valid_middle_gap, "middle_gap")
    for name, given, base_span in (
        ("F2-B2 span", f2_b2_span, geometry_profile.valid_f2_b2_span),
        ("loop span", loop_span, geometry_profile.valid_loop_span),
        ("outer gap", outer_gap, geometry_profile.valid_outer_gap),
        ("F1c-B1c gap", middle_gap, geometry_profile.valid_middle_gap),
    ):
        if given != base_span:
            overruled.append(name)

    return used, f2_b2_span, loop_span, outer_gap, middle_gap, overruled


#: How strongly the priming end must hold, in kcal/mol.
#:
#: Measured over the terminal six bases rather than five: six is the length the
#: isothermal literature states this threshold against, and the same oligo reads
#: -2.93 over five and -4.28 over six — the same number would decide the
#: opposite way.
# Eiken/PrimerExplorer regular-primer critical-end criterion.  This is used for
# 3' F2/B2/F3/B3 and 5' F1c/B1c in the core design path.
END_STABILITY = -4.0
# PrimerExplorer V5 designs LF/LB in a separate screen whose published default
# 3' stability threshold is -2 kcal/mol.  Reusing the regular-primer -4 cutoff
# for loop primers silently over-restricts the optional accelerator search.
LOOP_END_STABILITY = -2.0
END_BASES = 6

#: Compatibility/readability reference for the reviewed candidate report.
#: Whole-oligo homopolymer runs are surfaced diagnostically rather than used
#: as a universal hard gate because the reviewed guidance is position-specific.
LONGEST_RUN = 4

# Homopolymer/terminal-composition cautions are reported by downstream oligo
# review. There is deliberately no universal whole-oligo homopolymer hard gate
# here: published LAMP guidance is position/base-specific (for example terminal
# G/C runs), not a rule that any run of five identical bases anywhere makes an
# otherwise valid region biologically impossible.


@dataclass(frozen=True)
class Region:
    """One stretch of the plus strand that an oligo is built from."""

    name: str
    start: int
    length: int

    @property
    def end(self) -> int:
        """One past the last base."""
        return self.start + self.length

    def sequence(self, template: str) -> str:
        return template[self.start : self.end]


def smallest_f2_b2_span(windows: Windows, loop_span: tuple[int, int]) -> int:
    """Arithmetic floor for the F2-B2 span under the selected role lengths."""
    return loop_span[0] * 2 + windows.inner.length_min * 2


def smallest_amplicon(windows: Windows, loop_span: tuple[int, int]) -> int:
    """Compatibility name for the F2-B2 amplified-region floor."""
    return smallest_f2_b2_span(windows, loop_span)


def check_geometry(
    windows: Windows,
    f2_b2_span: tuple[int, int],
    loop_span: tuple[int, int],
) -> None:
    """Whether these numbers describe a set that could exist.

    Raises:
        LoopSetError: naming the two figures that contradict each other.
    """
    floor = smallest_f2_b2_span(windows, loop_span)
    if f2_b2_span[1] < floor:
        raise LoopSetError(
            f"No set can be shorter than {floor} bases with these numbers — two loops "
            f"of at least {loop_span[0]} and two stems of at least "
            f"{windows.inner.length_min} have to fit end to end — and the longest "
            f"F2-B2 span allowed is {f2_b2_span[1]}. This is arithmetic rather than a "
            "search that failed: shorten the loops, shorten the stems, or allow a "
            "longer product."
        )
    # LF/LB are optional accelerators. A geometry that leaves no legal loop-primer
    # site may still be a valid four-primer LAMP core, so loop-primer fit must not
    # become a hard assay-validity gate. The enumerator simply returns `None` for
    # that half's loop primer.
