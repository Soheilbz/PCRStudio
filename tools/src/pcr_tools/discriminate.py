"""A pair that amplifies one allele and not the other.

Allele-specific PCR puts the variant base at a primer's 3' end. On the allele
it was designed for the primer matches; on the other it ends in a mismatch whose
extension and product yield depend on the mismatch, polymerase and conditions.
The read-out is a comparison of controlled reactions, not a universal promise
that a mismatch will prevent amplification.

What makes this its own engine is that the discriminating power is not designed,
it is *dealt*. Both alleles are given, so the terminal mismatch is fixed by the
chemistry; the only lever anybody has is which strand the allele-specific primer
sits on, and that choice maps every mismatch to its complement. Enumerating it
gives a table worth stating up front, because it decides what the assay can
promise:

    alleles  kind          plus strand              minus strand
    A/C      transversion  A strongly reduced, C weak    C strongly reduced, A weak
    C/G      transversion  C strongly reduced, G context  G strongly reduced, C context
    G/T      transversion  G strongly reduced, T weak    T strongly reduced, G weak
    A/T      transversion  A reduced, T weak             T reduced, A weak
    A/G      transition    no strong class               no strong class
    C/T      transition    no strong class               no strong class

Two things follow, and both change what the engine may claim.

For a transversion, exactly one allele gets the strongest mismatch class on each strand,
and which one flips with the strand. So a geometry whose two allele-specific
primers sit on *opposite* strands can place both alleles in the strongest terminal-
mismatch class represented by the cited model at once — which is a useful
candidate-selection signal for the four-primer tetra layout, not a universal
polymerase guarantee. A geometry putting both on the same strand,
which is what KASP does, can never do better than one.

For a transition — A/G or C/T — no placement receives one of the strongest
classes in this evidence table. Every placement gives a weaker or context-
dependent mismatch class, so strand choice alone is insufficient evidence of
discrimination. The second, deliberate mismatch near the 3' end is therefore
required by this design policy, but its success remains assay-specific.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from . import kasp
from .design import Constraints, clean_template
from .thermo import DEFAULT_CONDITIONS, analyse, reverse_complement
from .registries.authorities import DISCRIMINATING_AUTHORITY, record as authority_record
from .variants import VariantError, differing_anchor, normalize_variant, parse_vcf_mask
from .workflow_evidence import evidence_block


class DiscriminationError(ValueError):
    """A genotyping assay that could not be asked for."""


COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}


# ── What a terminal mismatch is worth ──────────────────────────────────────

#: Mismatches that stop extension, as primer base against template base.
#:
#: Associated with roughly a hundredfold lower product yield in the cited
#: Taq/HIV-1 model. These are a ranking class for this evidence scope, not a
#: universal statement that extension is impossible.
_MISMATCH_AUTHORITY = dict(DISCRIMINATING_AUTHORITY["mismatch_model"])
_MISMATCH_CLASSES = dict(_MISMATCH_AUTHORITY["classes"])

def _pairs(tokens: list[str]) -> frozenset[tuple[str, str]]:
    return frozenset(tuple(token.split("/", 1)) for token in tokens)

BLOCKING = _pairs(list(_MISMATCH_CLASSES["blocks"]))

#: Associated with lower product yield in this evidence-scoped model.
SLOWING = _pairs(list(_MISMATCH_CLASSES["slows"]))

#: A mismatch whose effect depends on what surrounds it.
#:
#: Reported as its own class rather than folded into either neighbour, because
#: a design resting on it is one whose behaviour cannot be predicted from the
#: variant alone — which is a thing somebody should be told.
SEQUENCE_DEPENDENT = _pairs(list(_MISMATCH_CLASSES["depends"]))

#: What the classes are called, worst discrimination last.
STRENGTHS = ("blocks", "slows", "depends", "tolerated")


def strength(primer_base: str, template_base: str) -> str:
    """Return the evidence-scoped terminal-mismatch class."""
    pair = (primer_base.upper(), template_base.upper())
    if pair in BLOCKING:
        return "blocks"
    if pair in SLOWING:
        return "slows"
    if pair in SEQUENCE_DEPENDENT:
        return "depends"
    return "tolerated"


@dataclass(frozen=True)
class Terminus:
    """What one allele-specific primer meets at its 3' end."""

    allele: str
    strand: str
    #: The primer's own 3' base.
    primer_base: str
    #: What sits opposite it on the template carrying the *other* allele.
    template_base: str

    @property
    def strength(self) -> str:
        return strength(self.primer_base, self.template_base)

    def describe(self) -> str:
        return f"{self.primer_base}*{self.template_base}"


def terminus_for(target: str, other: str, strand: str) -> Terminus:
    """What a primer specific to `target` meets on the `other` allele.

    A plus-strand primer ends in the allele itself and anneals to the minus
    strand, so it meets the complement of the other allele. A minus-strand
    primer ends in the complement of the allele and meets the other allele
    directly. That mapping is the whole of the strand choice.
    """
    if strand == "plus":
        return Terminus(target, strand, target, COMPLEMENT[other])
    return Terminus(target, strand, COMPLEMENT[target], other)


def is_transition(one: str, other: str) -> bool:
    """Whether swapping these two bases keeps the purine or pyrimidine class."""
    return {one.upper(), other.upper()} in ({"A", "G"}, {"C", "T"})


@dataclass(frozen=True)
class Assignment:
    """One way of putting the two allele-specific primers on the template."""

    #: Which strand each allele's primer sits on.
    strands: dict[str, str]
    termini: dict[str, Terminus]

    @property
    def weakest(self) -> str:
        """The worse of the two alleles, which is what the assay is limited by."""
        return max(
            (one.strength for one in self.termini.values()),
            key=STRENGTHS.index,
        )

    @property
    def strongest_class_both(self) -> bool:
        """Whether both termini land in the strongest class of the cited model."""
        return all(one.strength == "blocks" for one in self.termini.values())


def assignments(alleles: tuple[str, str], same_strand: bool) -> list[Assignment]:
    """Every way the two allele-specific primers could be placed, best first.

    Args:
        same_strand: Whether the geometry forces both primers onto one strand.
            KASP does; the four-primer tetra layout does the opposite, and a
            two-tube assay is free because its two reactions never meet.

    Ranked by the worse of the two alleles, because an assay that discriminates
    beautifully for one allele and not at all for the other cannot genotype: a
    heterozygote and a homozygote look the same in the tube that fails.
    """
    one, other = alleles
    found: list[Assignment] = []

    if same_strand:
        for strand in ("plus", "minus"):
            found.append(
                Assignment(
                    strands={one: strand, other: strand},
                    termini={
                        one: terminus_for(one, other, strand),
                        other: terminus_for(other, one, strand),
                    },
                )
            )
    else:
        for first, second in (("plus", "minus"), ("minus", "plus")):
            found.append(
                Assignment(
                    strands={one: first, other: second},
                    termini={
                        one: terminus_for(one, other, first),
                        other: terminus_for(other, one, second),
                    },
                )
            )

    found.sort(key=lambda entry: STRENGTHS.index(entry.weakest))
    return found


# ── The second mismatch ────────────────────────────────────────────────────

#: Where a deliberate second mismatch may go, in the order to try.
#:
#: Counted back from the 3' end, so -1 is the discriminating base itself and is
#: never available. Third from the end is the usual choice; fourth is the
#: alternative when the third cannot be substituted without leaving the window.
SECOND_MISMATCH_AT = tuple(int(value) for value in _MISMATCH_AUTHORITY["secondary_mismatch_positions_from_3prime"])

#: What the second mismatch is for, said once.
#:
#: One mismatch at the 3' end slows extension. A second one nearby destabilises
#: the whole end of the duplex, so on the off-allele the primer carries two
#: mismatches and on the target allele exactly one — and it is that difference,
#: rather than either count alone, that separates them.
SECOND_MISMATCH_WHY = (
    "A deliberate near-terminal mismatch proposed by the Gen-1 candidate policy. "
    "It adds one mismatch on the target allele and an additional mismatch on the "
    "competing allele. The resulting discrimination is sequence-, mismatch-, "
    "polymerase- and condition-dependent and must be established experimentally."
)


@dataclass(frozen=True)
class Second:
    """A deliberate substitution, and what it costs."""

    #: How far back from the 3' end, negative.
    at: int
    #: What the primer says there instead of the template's base.
    base: str
    was: str
    #: The mismatch it makes against the primer's own target allele.
    against_target: str


def second_mismatches(primer: str, at: int) -> list[Second]:
    """Every substitution available at this position, strongest first.

    Strongest against the primer's own target, because that is the mismatch it
    must survive: the same substitution is present on both alleles, and it is
    the *off* allele that gets it in addition to a terminal one.
    """
    was = primer[at].upper()
    found = [
        Second(
            at=at,
            base=base,
            was=was,
            # The primer says `base` where its own target template says the
            # complement of `was` — so the pair the polymerase sees is this.
            against_target=strength(base, COMPLEMENT[was]),
        )
        for base in "ACGT"
        if base != was
    ]
    found.sort(key=lambda one: STRENGTHS.index(one.against_target), reverse=True)
    return found


def apply_second(primer: str, second: Second) -> str:
    """The primer with that substitution in it."""
    index = len(primer) + second.at
    return primer[:index] + second.base + primer[index + 1 :]


# ── The allele-specific primers ────────────────────────────────────────────


def carrying(template: str, at: int, allele: str) -> str:
    """The template as it would read if it carried this allele."""
    return template[:at] + allele.upper() + template[at + 1 :]


@dataclass(frozen=True)
class AlleleSpecific:
    """One primer that ends on the variant, and what it discriminates by."""

    allele: str
    strand: str
    sequence: str
    #: Where its 5' base sits on the plus strand.
    at: int
    length: int
    tm: float
    gc_percent: float
    terminus: Terminus
    second: Second | None = None

    @property
    def discriminates_by(self) -> str:
        """What actually separates the two alleles for this primer."""
        if self.terminus.strength in ("blocks", "slows"):
            return "terminus"
        return "second mismatch" if self.second else "nothing"


def allele_primers(
    template: str,
    at: int,
    allele: str,
    other: str,
    strand: str,
    limits: Constraints,
    conditions: dict[str, float],
) -> list[AlleleSpecific]:
    """Every primer ending on the variant, best first.

    With the 3' end fixed at the variant the only freedom left is length, so
    this enumerates lengths directly rather than asking Primer3 to search a
    space of one position. That is not only simpler — Primer3's own manual
    warns that it picks primers anyway when a forced end conflicts with a
    constraint, so a returned list would have to be re-checked here in any
    case.

    Note what is *not* applied: a GC clamp, or a limit on G and C in the last
    five bases. Both are rules about choosing where a 3' end goes, and here it
    is not being chosen — it is the variant, and the variant is wherever it is.
    """
    sequence = carrying(template, at, allele)
    terminus = terminus_for(allele, other, strand)

    found: list[AlleleSpecific] = []
    for length in range(limits.length_min, limits.length_max + 1):
        if strand == "plus":
            start = at - length + 1
            if start < 0:
                continue
            oligo = sequence[start : at + 1]
        else:
            if at + length > len(sequence):
                continue
            start = at
            oligo = reverse_complement(sequence[at : at + length])

        measured = analyse(oligo, **conditions)
        if not limits.tm_min <= measured.tm <= limits.tm_max:
            continue
        if not limits.gc_min <= measured.gc_percent <= limits.gc_max:
            continue
        found.append(
            AlleleSpecific(
                allele=allele,
                strand=strand,
                sequence=oligo,
                at=start,
                length=length,
                tm=measured.tm,
                gc_percent=measured.gc_percent,
                terminus=terminus,
            )
        )

    # Closest to the ideal temperature first: the two allele reactions have to
    # run at one annealing temperature, so agreement matters more than any
    # individual primer being warm.
    found.sort(key=lambda one: abs(one.tm - limits.tm_opt))
    return found


def with_second_mismatch(
    primer: AlleleSpecific,
    limits: Constraints,
    conditions: dict[str, float],
    positions: tuple[int, ...] = SECOND_MISMATCH_AT,
) -> AlleleSpecific | None:
    """The same primer carrying a deliberate second mismatch, or nothing.

    Tried in the order given, and the substitution has to leave the primer
    inside its own window — it changes the melting temperature and can create a
    structure that was not there, so both are measured again rather than
    assumed to have survived.
    """
    for at in positions:
        if abs(at) > primer.length:
            continue
        for candidate in second_mismatches(primer.sequence, at):
            modified = apply_second(primer.sequence, candidate)
            measured = analyse(modified, **conditions)
            if not limits.tm_min <= measured.tm <= limits.tm_max:
                continue
            return AlleleSpecific(
                allele=primer.allele,
                strand=primer.strand,
                sequence=modified,
                at=primer.at,
                length=primer.length,
                tm=measured.tm,
                gc_percent=measured.gc_percent,
                terminus=primer.terminus,
                second=candidate,
            )
    return None


# ── Named Ye/Collins-Day tetra-primer ARMS mismatch authority ─────────────
# The 2001 method is not the generalized Gen-1 mismatch heuristic above. Both
# inner primers are >=26 nt and carry a second deliberate mismatch exactly -2
# from the 3' terminus. The second-mismatch strength is selected reciprocally:
# strong terminal -> weak second, weak terminal -> strong second, medium ->
# medium. These are the published named-method rules; empirical optimisation is
# still required and no polymerase-independent success guarantee is implied.
TETRA_INNER_MIN_NT = 26
TETRA_INNER_OPT_NT = 28
TETRA_SECOND_MISMATCH_AT = -2

def _classic_tetra_mismatch_strength(primer_base: str, template_base: str) -> str:
    a, b = primer_base.upper(), template_base.upper()
    if a == b:
        return "medium"
    pair = frozenset((a, b))
    if pair in {frozenset(("G", "A")), frozenset(("C", "T"))}:
        return "strong"
    if pair in {frozenset(("C", "A")), frozenset(("G", "T"))}:
        return "weak"
    raise DiscriminationError(f"Unsupported tetra-ARMS mismatch pair {a}/{b}")

def with_tetra_second_mismatch(
    primer: AlleleSpecific, limits: Constraints, conditions: dict[str, float]
) -> AlleleSpecific | None:
    """Apply the exact public Ye/Collins-Day -2 mismatch rule."""
    if primer.length < TETRA_INNER_MIN_NT:
        return None
    terminal_class = _classic_tetra_mismatch_strength(
        primer.terminus.primer_base, primer.terminus.template_base
    )
    desired = {"strong": "weak", "weak": "strong", "medium": "medium"}[terminal_class]
    at = TETRA_SECOND_MISMATCH_AT
    for candidate in second_mismatches(primer.sequence, at):
        target_template_base = COMPLEMENT[candidate.was]
        if _classic_tetra_mismatch_strength(candidate.base, target_template_base) != desired:
            continue
        modified = apply_second(primer.sequence, candidate)
        measured = analyse(modified, **conditions)
        if not limits.tm_min <= measured.tm <= limits.tm_max:
            continue
        return AlleleSpecific(
            allele=primer.allele, strand=primer.strand, sequence=modified,
            at=primer.at, length=primer.length, tm=measured.tm,
            gc_percent=measured.gc_percent, terminus=primer.terminus, second=candidate,
        )
    return None


# ── The assay geometries ───────────────────────────────────────────────────

#: How the allele-specific primers are laid out, and what that costs.
#:
#: The distinction that matters is whether the two allele-specific primers sit
#: on the same strand. In the evidence table used by this Gen-1 candidate policy,
#: opposite-strand placement can put both transversion termini in the strongest
#: represented mismatch class. Same-strand placement cannot. This is ranking
#: evidence, not a universal extension/no-extension rule.
GEOMETRIES = {
    "arms-two-tube": {
        "name": "ARMS, two tubes",
        "same_strand": False,
        "tubes": 2,
        "note": (
            "Each allele gets its own reaction, so the two are independent and each "
            "may sit on whichever strand suits it. A genotype is read from which of "
            "the two tubes gave a band."
        ),
    },
    "tetra": {
        "name": "Tetra-primer ARMS",
        "same_strand": False,
        "tubes": 1,
        "note": (
            "Four primers in one tube: two allele-specific ones facing each other and "
            "two outer ones. Three bands are possible and the genotype is read from "
            "which appear. The two allele-specific primers face opposite ways, which "
            "puts both alleles in the strongest terminal-mismatch class represented by the cited model at once."
        ),
    },
    "kasp": {
        "name": "KASP",
        "same_strand": True,
        "tubes": 1,
        "note": (
            "Both allele-specific primers point the same way and share one common "
            "primer, each carrying a different fixed tail that a fluorescent cassette "
            "reads. Because both sit on the same strand, only one allele can have the "
            "strong terminal mismatch — the other depends on its second mismatch."
        ),
    },
}

# A KASP allele-specific primer cannot move its 3' end away from the variant;
# length is its only design lever.  Its geometry therefore needs the wider
# window used by the KASP profile, even when a caller uses this worker directly
# without sending the Rust profile envelope.  These are assay-design defaults,
# not a relaxation of a caller-supplied constraint.
#
# The values mirror `crates/pcr-core/profiles.toml`'s KASP profile.  The wide
# GC/Tm window is deliberate: LGC's public KASP material describes a proprietary
# Kraken design process and recommends assay validation, but does not publish a
# universal numeric Primer3 window.  Keeping the values in one worker-level
# fallback prevents an unprofiled KASP request from silently inheriting the
# ordinary 57–63 °C / 40–60% pair window.
KASP_CONSTRAINT_DEFAULTS: dict[str, float | int] = {
    "tm_min": 55.0,
    "tm_opt": 61.0,
    "tm_max": 68.0,
    "tm_pair_max_difference": 5.0,
    "length_min": 17,
    "length_opt": 22,
    "length_max": 30,
    "gc_min": 30.0,
    "gc_max": 75.0,
    # LGC publishes an approximate 100-bp maximum for KASP but no universal
    # lower amplicon bound.  `1` is therefore an implementation sentinel for
    # "no added KASP-specific minimum"; Primer3/pinned-primer geometry decides
    # the shortest constructible product rather than arithmetic on max primer
    # length.
    "product_min": 1,
    "product_max": 100,
}


def _constraints_for_geometry(geometry: str) -> Constraints:
    """Return low-level geometry defaults for direct engine design tests.

    Routed execution resolves a canonical assay profile before this layer; these
    values are not permission to synthesize a KASP assay identity.
    """
    if geometry == "kasp":
        return Constraints(**KASP_CONSTRAINT_DEFAULTS)
    return Constraints()


def _profile_request_for_geometry(request: dict[str, Any]) -> dict[str, Any]:
    """Enforce KASP module identity before routed worker execution.

    Geometry is not assay identity.  Current execution must carry the canonical
    ``assay.id=kasp`` profile; the worker never reconstructs that profile or its
    numeric defaults from ``geometry=kasp``.
    """
    geometry = str(request.get("geometry") or "arms-two-tube")
    if geometry != "kasp":
        return request

    supplied_assay = request.get("assay") or {}
    if not isinstance(supplied_assay, dict):
        return request
    assay_id = supplied_assay.get("id")
    if supplied_assay and assay_id not in (None, "", "kasp"):
        return request
    if not assay_id:
        raise DiscriminationError(
            "KASP execution requires the canonical `assay.id=kasp` profile; "
            "the worker does not synthesize assay identity or numeric defaults from geometry alone."
        )
    return request


@dataclass(frozen=True)
class Reason:
    """Why one allele could not be given a primer."""

    allele: str
    strand: str
    tried: int
    tm_range: str
    gc_range: str

    def describe(self, limits: Constraints) -> str:
        return (
            f"No primer for the `{self.allele}` allele. Its 3' end is the variant, so "
            f"length is the only thing that can vary — and across all {self.tried} "
            f"lengths on the {self.strand} strand it melted {self.tm_range} at "
            f"{self.gc_range} GC, against a window of {limits.tm_min}–{limits.tm_max} °C "
            f"and {limits.gc_min}–{limits.gc_max}% GC. This is the sequence around the "
            "variant rather than anything about the discrimination; widening the GC "
            "range is what usually helps."
        )


def why_none(
    template: str,
    at: int,
    allele: str,
    other: str,
    strand: str,
    limits: Constraints,
    conditions: dict[str, float],
) -> Reason:
    """What every candidate for this allele measured, when none of them fitted."""
    sequence = carrying(template, at, allele)
    tms: list[float] = []
    gcs: list[float] = []
    for length in range(limits.length_min, limits.length_max + 1):
        if strand == "plus":
            if at - length + 1 < 0:
                continue
            oligo = sequence[at - length + 1 : at + 1]
        else:
            if at + length > len(sequence):
                continue
            oligo = reverse_complement(sequence[at : at + length])
        measured = analyse(oligo, **conditions)
        tms.append(measured.tm)
        gcs.append(measured.gc_percent)

    if not tms:
        return Reason(allele, strand, 0, "nothing", "nothing")
    return Reason(
        allele=allele,
        strand=strand,
        tried=len(tms),
        tm_range=f"{min(tms):.1f}–{max(tms):.1f} °C",
        gc_range=f"{min(gcs):.0f}–{max(gcs):.0f}%",
    )


@dataclass
class Assay:
    """One genotyping design."""

    geometry: str
    alleles: tuple[str, str]
    at: int
    assignment: Assignment
    #: One allele-specific primer per allele, with any second mismatch in it.
    specific: dict[str, AlleleSpecific]
    #: The partner each allele-specific primer works against.
    common: dict[str, Any]
    #: What could not be made, per allele.
    refused: dict[str, Reason]
    #: Why the second mismatch was needed, when it was.
    mandatory_second: bool
    #: Tetra-primer three-band topology and declared resolution gate.
    band_geometry: dict[str, Any] | None = None


def design(
    template: str,
    *,
    at: int,
    alleles: tuple[str, str],
    geometry: str = "arms-two-tube",
    constraints: Constraints | None = None,
    conditions: dict[str, float] | None = None,
    excluded: list[tuple[int, int]] | None = None,
) -> Assay:
    """A design that tells these two alleles apart.

    Raises:
        DiscriminationError: for a variant this could not genotype.
        SequenceError: if the template is not unambiguous DNA.
    """
    from .design import design as design_pair

    sequence = clean_template(template)
    limits = constraints or _constraints_for_geometry(geometry)
    limits.validate()
    reaction = {**DEFAULT_CONDITIONS, **(conditions or {})}

    if geometry not in GEOMETRIES:
        raise DiscriminationError(
            f"`{geometry}` is not a layout this designs. It does: "
            + ", ".join(sorted(GEOMETRIES))
            + "."
        )
    one, other = (base.upper() for base in alleles)
    if one == other:
        raise DiscriminationError(
            f"Both alleles are given as `{one}`. There is nothing to tell apart."
        )
    for base in (one, other):
        if base not in COMPLEMENT:
            raise DiscriminationError(
                f"`{base}` is not a base. This genotypes single-base variants; an "
                "insertion or a deletion is a different assay."
            )
    if not 0 <= at < len(sequence):
        raise DiscriminationError(
            f"The variant is at base {at} of a {len(sequence)}-base sequence, which is outside it."
        )
    if sequence[at].upper() not in (one, other):
        raise DiscriminationError(
            f"The template reads `{sequence[at]}` at base {at}, which is neither of the "
            f"alleles given ({one} and {other}). Either the position is wrong or the "
            "template is a different haplotype from the one the alleles came from."
        )

    layout = GEOMETRIES[geometry]
    if geometry == "tetra":
        if limits.length_max < TETRA_INNER_MIN_NT:
            raise DiscriminationError(
                f"Named Ye/Collins-Day tetra-primer ARMS requires inner primers >= {TETRA_INNER_MIN_NT} nt; "
                f"the active profile/caller maximum is {limits.length_max} nt. PCRStudio will not relax the caller's "
                "constraint or fall back to the generalized ARMS heuristic."
            )
        inner_limits = replace(
            limits,
            length_min=max(limits.length_min, TETRA_INNER_MIN_NT),
            length_opt=max(max(limits.length_min, TETRA_INNER_MIN_NT), min(TETRA_INNER_OPT_NT, limits.length_max)),
        )
    else:
        inner_limits = limits
    plan = assignments((one, other), same_strand=bool(layout["same_strand"]))[0]

    # Under the current evidence-scoped terminal-mismatch classification a
    # transition does not receive a sufficiently blocking terminal class on
    # either strand.  Gen-1 therefore *proposes* a second mismatch as its
    # candidate-construction policy.  This is not a universal biochemical rule
    # and does not establish allele discrimination without experimental data.
    mandatory = is_transition(one, other)

    specific: dict[str, AlleleSpecific] = {}
    refused: dict[str, Reason] = {}
    for allele in (one, other):
        partner = other if allele == one else one
        strand = plan.strands[allele]
        found = allele_primers(sequence, at, allele, partner, strand, inner_limits, reaction)
        if not found:
            refused[allele] = why_none(sequence, at, allele, partner, strand, limits, reaction)
            continue

        chosen = found[0]
        if geometry == "tetra":
            improved = with_tetra_second_mismatch(chosen, inner_limits, reaction)
            if improved is None:
                raise DiscriminationError(
                    "Named Ye/Collins-Day tetra-primer ARMS could not place the required -2 deliberate mismatch "
                    f"for allele {allele} while preserving the active Tm/length constraints; no generalized fallback is used."
                )
            chosen = improved
        # Generalized ARMS/KASP candidate policy only. The named tetra branch
        # above owns its exact -2 rule and never reaches this heuristic.
        elif mandatory or chosen.terminus.strength in ("tolerated", "depends"):
            improved = with_second_mismatch(chosen, limits, reaction)
            if improved:
                chosen = improved
        specific[allele] = chosen

    # Partner geometry differs by assay. KASP requires one *shared* common
    # primer; independently selecting two good partners and merely deduplicating
    # them in the report can silently create a non-KASP three-primer topology.
    common: dict[str, Any] = {}
    if geometry == "kasp" and len(specific) == 2:
        pools = {
            allele: _partner_candidates(
                sequence, at, primer, limits, reaction, design_pair, excluded
            )
            for allele, primer in specific.items()
        }
        shared = set.intersection(
            *(set(item["sequence"] for item in pools[allele]) for allele in (one, other))
        ) if all(pools.get(allele) for allele in (one, other)) else set()
        if shared:
            # Preserve Primer3 preference across both allele-pinned searches.
            def shared_rank(seq: str) -> int:
                return sum(
                    next(i for i, item in enumerate(pools[allele]) if item["sequence"] == seq)
                    for allele in (one, other)
                )
            picked = min(shared, key=shared_rank)
            for allele in (one, other):
                common[allele] = next(
                    item for item in pools[allele] if item["sequence"] == picked
                )
    else:
        for allele, primer in specific.items():
            product = _partner_for(sequence, at, primer, limits, reaction, design_pair, excluded)
            if product:
                common[allele] = product

    band_geometry: dict[str, Any] | None = None
    if geometry == "tetra" and len(specific) == 2 and len(common) == 2:
        plus_allele = next((a for a, p in specific.items() if p.strand == "plus"), None)
        minus_allele = next((a for a, p in specific.items() if p.strand == "minus"), None)
        if plus_allele is not None and minus_allele is not None:
            outer_reverse = common[plus_allele]
            outer_forward = common[minus_allele]
            control_size = (
                outer_reverse["at"] + outer_reverse["length"] - outer_forward["at"]
            )
            allele_sizes = {allele: int(common[allele]["product_size"]) for allele in (one, other)}
            sizes = [allele_sizes[one], allele_sizes[other], control_size]
            minimum_gap = min(abs(a - b) for i, a in enumerate(sizes) for b in sizes[i + 1 :])
            band_geometry = {
                "allele_products_bp": allele_sizes,
                "outer_control_bp": control_size,
                "all_products_bp": sizes,
                "minimum_pairwise_separation_bp": minimum_gap,
                "topology_complete": control_size > max(allele_sizes.values()),
                "resolution_status": "requires-declared-electrophoresis-resolution",
            }

    return Assay(
        geometry=geometry,
        alleles=(one, other),
        at=at,
        assignment=plan,
        specific=specific,
        common=common,
        refused=refused,
        mandatory_second=(True if geometry == "tetra" else mandatory),
        band_geometry=band_geometry,
    )


#: The partner window is the *resolved assay profile*, not a second hidden
#: constant. ARMS/Tetra and KASP have different product contracts; KASP's
#: standard branch must never inherit the generic ARMS/Tetra 120–500 bp envelope.

#: How many partner candidates to look at before giving up on the 3'-end rules.
#:
#: Primer3's ordinary free-primer checks are not the authority for the pinned
#: allele-specific oligo because its 3′ end is intentionally fixed at the variant.
#: The assay-specific 3′ discrimination gates remain unchanged; several partner
#: candidates are requested and the first one satisfying those gates is retained.
MOST_PARTNERS = 8


def _partner_candidates(
    sequence: str,
    at: int,
    primer: AlleleSpecific,
    limits: Constraints,
    reaction: dict[str, float],
    design_pair: Any,
    excluded: list[tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    """Candidate primers facing one allele-specific primer, best first.

    Rather than searching a window and hoping the two oligos get on, the
    allele-specific primer is pinned and Primer3 picks its partner around it —
    so the cross-dimer between them, and the agreement of their melting
    temperatures, are part of the search instead of something checked
    afterwards and lived with.

    Two details make the pinning work. The search runs against the template as
    it would read carrying this allele, because Primer3 requires a pinned
    primer to be a substring of what it is given. And the primer pinned is the
    one *before* any deliberate second mismatch was put in it — that mismatch
    is not in the template by definition, so pinning the modified oligo would
    be pinning something that is not there.
    """
    low, high = limits.product_min, limits.product_max
    template = carrying(sequence, at, primer.allele)

    # The unmodified oligo: what the template actually says at those positions.
    if primer.strand == "plus":
        unmodified = template[primer.at : primer.at + primer.length]
        pinning = {"pinned_left": unmodified}
    else:
        unmodified = reverse_complement(template[primer.at : primer.at + primer.length])
        pinning = {"pinned_right": unmodified}

    # The 3'-end rules have to come off for this search, and putting them back
    # by hand afterwards is the point rather than an afterthought.
    #
    # Primer3 applies `PRIMER_GC_CLAMP` to every primer in the pair, including
    # the one being pinned — and an allele-specific primer's 3' end is the
    # variant, which is wherever it is. Measured on TP53: pinning a primer
    # ending ...TTA made Primer3 report "left: considered 1, GC clamp failed 1,
    # ok 0" and return nothing, so the partner search failed for a reason that
    # had nothing to do with the partner. Across 200 variant sites it failed
    # every time.
    wanted = Constraints(
        **{
            **{name: getattr(limits, name) for name in Constraints.__dataclass_fields__},
            "product_min": low,
            "product_max": high,
            "gc_clamp": 0,
            "max_end_gc": 5,
            # And the rule about two candidates being the same design nudged
            # over, which cannot mean anything here: every pair shares the
            # pinned primer, so every pair after the first has an identical 3'
            # end on that side and Primer3 discards it as a duplicate.
            # Measured at this site: 1 pair returned with the default of five,
            # 8 with the restriction lifted, from the same 297 considered.
            "min_three_prime_distance": -1,
        }
    )

    try:
        found = design_pair(
            template,
            constraints=wanted,
            conditions=reaction,
            how_many=MOST_PARTNERS,
            # The partner only. The allele-specific primer's position is not a
            # choice — it is wherever the variant is — so an exclusion that
            # covered it would be a request this assay cannot honour, and the
            # search is pinned to that primer anyway.
            excluded=excluded,
            **pinning,
        )
    except ValueError:
        return []
    if not found.pairs:
        return []

    accepted: list[dict[str, Any]] = []
    # And now the rules the pinned primer could not obey, applied to the one
    # that can. The partner's 3' end *is* chosen, so it is held to the window
    # the caller asked for.
    for pair in found.pairs:
        candidate = pair.right if primer.strand == "plus" else pair.left
        end = candidate.sequence[-5:].upper()
        clamped = sum(1 for base in candidate.sequence[-limits.gc_clamp :] if base in "GC")
        if limits.gc_clamp and clamped < limits.gc_clamp:
            continue
        if sum(1 for base in end if base in "GC") > limits.max_end_gc:
            continue
        where = pair.right_at.start if primer.strand == "plus" else pair.left_at.start
        accepted.append(
            {
                "sequence": candidate.sequence,
                "at": where,
                "strand": "minus" if primer.strand == "plus" else "plus",
                "tm": candidate.tm,
                "gc_percent": candidate.gc_percent,
                "length": candidate.length,
                "product_size": pair.product_size,
                "cross_dimer_dg": pair.cross_dimer_dg,
                "tm_difference": round(abs(candidate.tm - primer.tm), 1),
            }
        )
    return accepted


def _partner_for(
    sequence: str,
    at: int,
    primer: AlleleSpecific,
    limits: Constraints,
    reaction: dict[str, float],
    design_pair: Any,
    excluded: list[tuple[int, int]] | None = None,
) -> dict[str, Any] | None:
    candidates = _partner_candidates(
        sequence, at, primer, limits, reaction, design_pair, excluded
    )
    return candidates[0] if candidates else None


# ── Reporting ──────────────────────────────────────────────────────────────


def assay_to_dict(assay: Assay, limits: Constraints, **conditions: float) -> dict[str, Any]:
    """One genotyping design as plain data, led by what it discriminates on."""
    layout = GEOMETRIES[assay.geometry]
    one, other = assay.alleles

    return {
        "geometry": {
            "id": assay.geometry,
            "name": layout["name"],
            "tubes": layout["tubes"],
            "note": layout["note"],
        },
        "variant": {
            "at": assay.at,
            "alleles": [one, other],
            "kind": "transition" if is_transition(one, other) else "transversion",
            "note": _variant_note(assay),
        },
        "discrimination": {
            allele: {
                "strand": primer.strand,
                "terminus": primer.terminus.describe(),
                "terminus_strength": primer.terminus.strength,
                "second_mismatch": (
                    {
                        "at": primer.second.at,
                        "was": primer.second.was,
                        "now": primer.second.base,
                        "why": SECOND_MISMATCH_WHY,
                    }
                    if primer.second
                    else None
                ),
                "rests_on": primer.discriminates_by,
            }
            for allele, primer in assay.specific.items()
        },
        "primers": [
            {
                "name": f"{allele}-specific",
                "allele": allele,
                "strand": primer.strand,
                # What to order. On KASP that is the tail plus the annealing
                # half, because a KASP primer without its tail amplifies
                # correctly and reports nothing.
                "sequence": (
                    kasp.attach(primer.sequence, index)
                    if assay.geometry == "kasp"
                    else primer.sequence
                ),
                "at": primer.at,
                "length": primer.length,
                # The annealing half's, always. See kasp.describe.
                "tm": primer.tm,
                "gc_percent": primer.gc_percent,
                "cassette": (
                    kasp.describe(index, primer.sequence, primer.tm)
                    if assay.geometry == "kasp"
                    else None
                ),
                "note": _primer_note(primer),
            }
            for index, (allele, primer) in enumerate(assay.specific.items())
        ],
        "partners": _partners(assay),
        **({"band_geometry": assay.band_geometry} if assay.band_geometry is not None else {}),
        "refused": {allele: reason.describe(limits) for allele, reason in assay.refused.items()},
    }


def _partners(assay: Assay) -> list[dict[str, Any]]:
    """The common primers, listed once each rather than once per allele.

    Where both allele-specific primers sit on the same strand there is only one
    common primer — that is what KASP's single tube means — and reporting it
    twice would put an oligo on the order sheet that nobody needs to buy twice.
    Where they face opposite ways there really are two, and both are listed.
    """
    seen: dict[str, dict[str, Any]] = {}
    for allele, partner in assay.common.items():
        entry = seen.setdefault(partner["sequence"], {**partner, "for_alleles": []})
        entry["for_alleles"].append(allele)

    found = []
    for entry in seen.values():
        shared = len(entry["for_alleles"]) > 1
        found.append(
            {
                **entry,
                "note": (
                    (
                        "One common primer shared by both allele-specific reactions"
                        if shared
                        else f"The common primer for the {entry['for_alleles'][0]} reaction"
                    )
                    + f". It sits about {entry['product_size']} bases from the variant, "
                    "well clear of it, so it is the same oligo whichever allele is "
                    "present — which is what makes comparing the two fair."
                ),
            }
        )
    return found


def _variant_note(assay: Assay) -> str:
    """What this kind of variant allows, said before any oligo is read."""
    one, other = assay.alleles
    if assay.mandatory_second:
        return (
            f"{one}/{other} is a transition. Under PCRStudio Gen-1's evidence-scoped "
            "terminal-mismatch classification, no strand assignment is treated as "
            "sufficiently blocking by the variant base alone. The algorithm therefore "
            "proposes a deliberate near-terminal second mismatch. That is an experimental "
            "candidate policy, not a universal polymerase rule or a validated genotype-"
            "discrimination claim; the assay must be optimised and confirmed at the bench."
        )
    if assay.assignment.strongest_class_both:
        return (
            f"{one}/{other} is a transversion. In PCRStudio Gen-1's evidence-scoped "
            "terminal-mismatch classification, this opposite-strand layout places both "
            "alleles in the strongest represented mismatch class. That supports candidate "
            "selection but does not establish complete extension block or genotype "
            "discrimination without assay-specific validation."
        )
    return (
        f"{one}/{other} is a transversion, but with both allele-specific primers on the "
        "same strand only one allele reaches the strongest terminal-mismatch class in the "
        "current evidence table. The other therefore relies on the proposed second "
        "mismatch; actual discrimination remains experimental."
    )


def _primer_note(primer: AlleleSpecific) -> str:
    if primer.discriminates_by == "terminus":
        return (
            f"Ends on the variant. Against the other allele that 3' base makes a "
            f"{primer.terminus.describe()} pair, associated with roughly a hundred-fold "
            "lower product yield in the cited mismatch model. This is an evidence-scoped "
            "design signal, not a universal rate or an automatic genotype call."
        )
    if primer.discriminates_by == "second mismatch":
        return (
            f"Ends on the variant, but against the other allele that makes a "
            f"{primer.terminus.describe()} pair, which the current evidence-scoped "
            "model does not treat as sufficiently discriminating on its own. This "
            "candidate therefore adds a deliberate substitution further in; whether "
            "that actually separates the alleles must be established experimentally."
        )
    return (
        f"Ends on the variant, and against the other allele that makes a "
        f"{primer.terminus.describe()} pair, which the current evidence-scoped model "
        "places in its lowest-discrimination class. No second mismatch could be placed "
        "without leaving the window, so PCRStudio has no supported discrimination "
        "proposal for this primer. It is reported so the gap is visible rather than absent."
    )


def run(request: dict[str, Any]) -> dict[str, Any]:
    """One genotyping design, end to end, in the shape the interface reads.

    Raises:
        IntakeError: the input is not a usable template.
        DiscriminationError: a variant this could not genotype.
        ValueError: a constraint, preset or reaction that cannot hold.
    """
    from .intake import target_to_dict
    from .presets import thermodynamic_model
    from .provenance import provenance
    from .settings import excluded_from, label, prepare

    # The product is short and its size is not what this is about, so the usual
    # check that a template can hold one does not describe anything here.
    settings_request = _profile_request_for_geometry(request)
    chosen = prepare(settings_request, require_product_room=False)
    reaction = chosen.reaction.as_conditions()

    mismatch_evidence_model = dict(DISCRIMINATING_AUTHORITY["mismatch_model"])
    canonical_mismatch_profile = str(mismatch_evidence_model.get("model_id") or "")
    selected_mismatch_profile = str(
        request.get("mismatch_evidence_profile") or canonical_mismatch_profile
    )
    if not canonical_mismatch_profile or selected_mismatch_profile != canonical_mismatch_profile:
        raise DiscriminationError(
            "mismatch_evidence_profile is not reviewed by this authority snapshot; "
            f"expected `{canonical_mismatch_profile}` and received `{selected_mismatch_profile}`."
        )
    mismatch_evidence_model["selected_profile_id"] = selected_mismatch_profile

    try:
        normalized_variant = normalize_variant(request, chosen.target.sequence)
    except VariantError as exc:
        raise DiscriminationError(str(exc)) from exc
    anchor = differing_anchor(normalized_variant)
    if normalized_variant.kind in {"snv", "mnv"}:
        if anchor is None:
            raise DiscriminationError("The declared equal-length REF/ALT has no differing base to anchor.")
        supplied = list(anchor["alleles"])
        design_at = int(anchor["at"])
    else:
        supplied = ["REF", "ALT"]
        design_at = normalized_variant.at

    nearby_variant_records = parse_vcf_mask(
        request.get("nearby_variants_vcf"),
        reference_accession=normalized_variant.reference_accession,
    )

    # A proofreading polymerase excises the very mismatch this assay depends on.
    # The property that matters is 3'-to-5' proofreading, not the absence of a
    # 5' exonuclease — Taq has no proofreader and is exactly what this assay
    # wants, while the long-range blends carry one and would erase it.
    if getattr(chosen.preset, "proofreading", False):
        raise DiscriminationError(
            f"{getattr(chosen.preset, 'name', 'This enzyme')} proofreads. A proofreading "
            "polymerase can alter or remove the terminal mismatch that this assay relies "
            "on, collapsing the intended discrimination and risking an apparent "
            "heterozygote. Allele-specific PCR needs an enzyme without a 3'-to-5' "
            "proofreading activity, or a separately validated alternative."
        )

    expected_geometry = {
        "arms-pcr": "arms-two-tube",
        "tetra-primer-arms": "tetra",
        "kasp": "kasp",
    }.get(chosen.assay_id)
    raw_geometry = request.get("geometry")
    if expected_geometry is not None:
        if raw_geometry in (None, ""):
            raise DiscriminationError(
                f"{chosen.assay_id} requires explicit canonical geometry `{expected_geometry}`; assay topology is not inferred from omission."
            )
        if str(raw_geometry) != expected_geometry:
            raise DiscriminationError(
                f"{chosen.assay_id} is fixed to geometry `{expected_geometry}`, not `{raw_geometry}`. Choose the matching module instead of changing assay topology."
            )
    geometry = str(raw_geometry or "arms-two-tube")
    kasp_protocol = request.get("kasp_protocol")
    # Genotype-call semantics are part of the scientific question, not a
    # convenience default. Every executable KASP request must name it.
    kasp_assay_mode = request.get("kasp_assay_mode")
    if geometry == "kasp":
        if kasp_assay_mode not in {"biallelic-genotype", "plus-minus-presence-absence"}:
            raise DiscriminationError(
                "KASP requires explicit `kasp_assay_mode`: biallelic-genotype or plus-minus-presence-absence."
            )
        if kasp_assay_mode == "plus-minus-presence-absence" and normalized_variant.kind not in {
            "insertion", "deletion", "complex-replacement", "presence-absence"
        }:
            raise DiscriminationError(
                "KASP plus/minus requires an insertion, deletion, complex replacement or explicit presence/absence variant; use biallelic-genotype for SNV/MNV."
            )
    elif any(request.get(k) is not None for k in ("kasp_assay_mode", "kasp_plate_format", "kasp_instrument_model", "kasp_rox_policy")):
        raise DiscriminationError("KASP-specific fields require KASP geometry.")
    if kasp_protocol is not None and kasp_protocol not in kasp.PROTOCOLS:
        raise DiscriminationError(
            f"`{kasp_protocol}` is not a KASP protocol this worker knows. It knows: "
            f"{', '.join(kasp.PROTOCOLS)}."
        )
    if kasp_protocol in {"lgc-standard", "lgc-kasp-tf-v5"} and geometry != "kasp":
        raise DiscriminationError(
            "The LGC KASP protocol overlay can only be selected with KASP geometry."
        )
    if kasp_protocol in {"lgc-standard", "lgc-kasp-tf-v5"}:
        if chosen.limits.product_max > KASP_CONSTRAINT_DEFAULTS["product_max"]:
            raise DiscriminationError(
                f"The standard LGC KASP branch is capped at approximately {KASP_CONSTRAINT_DEFAULTS['product_max']} bp; lower product_max or leave the canonical profile unchanged."
            )
        if request.get("kasp_plate_format") not in {"96", "384"}:
            raise DiscriminationError("LGC KASP requires `kasp_plate_format` 96 or 384.")
        if not str(request.get("kasp_instrument_model") or "").strip():
            raise DiscriminationError("LGC KASP requires `kasp_instrument_model`; use `unresolved` when unknown.")
        if request.get("kasp_rox_policy") not in {"none", "low", "standard", "high", "unresolved"}:
            raise DiscriminationError("LGC KASP requires an explicit `kasp_rox_policy`.")

    tetra_min_separation = request.get("tetra_min_band_separation_bp")
    if geometry == "tetra":
        if tetra_min_separation is None:
            raise DiscriminationError(
                "Tetra-primer ARMS requires `tetra_min_band_separation_bp` from the intended "
                "electrophoresis/resolution workflow; PCRStudio will not invent a gel-resolution threshold."
            )

    # Non-SNV unequal-length variants require the explicit KASP plus/minus
    # junction topology. ARMS/Tetra remain single-terminal-base designs; PCRStudio
    # refuses to coerce an indel into those geometries.
    if normalized_variant.kind not in {"snv", "mnv"} and not (
        geometry == "kasp" and kasp_assay_mode == "plus-minus-presence-absence"
    ):
        raise DiscriminationError(
            f"{normalized_variant.kind} is normalized and retained, but the current {geometry} geometry is single-anchor. "
            "Use KASP plus/minus for an explicit reconstructed-allele junction design rather than coercing the variant to one base."
        )

    if geometry == "kasp" and kasp_assay_mode == "plus-minus-presence-absence":
        from .kasp_plus_minus import design_plus_minus
        from . import screen
        plusminus = design_plus_minus(chosen.target.sequence, normalized_variant, chosen.limits, reaction)
        named = {primer["name"]: primer["sequence"] for primer in plusminus.get("primers", [])}
        for index, partner in enumerate(plusminus.get("partners", []), start=1):
            named[f"partner {index}"] = partner["sequence"]
        contigs, template_only, fold_at = screen.contigs_for(
            request, template=chosen.target.sequence, name=chosen.target.name
        )
        off_targets = screen.oligos(
            named, contigs, reaction=chosen.reaction, fold_at=fold_at,
            max_product=screen.product_ceiling(chosen.limits.product_max), intended_sizes=[]
        ) if named else []
        from .intake import target_to_dict
        from .presets import thermodynamic_model
        from .provenance import provenance
        from .settings import label
        selected_protocol = kasp.protocol(
            kasp_protocol, plate_format=request.get("kasp_plate_format"),
            instrument_model=request.get("kasp_instrument_model"), rox_policy=request.get("kasp_rox_policy")
        )
        assay_orderable = bool(plusminus.get("orderable"))
        name = label(chosen.target.name)
        order_sheet=[]
        if assay_orderable:
            for primer in plusminus["primers"]:
                order_sheet.append({"name":f"{name}_{primer['allele']}","sequence":primer["ordered_sequence"],"annealing_sequence":primer["sequence"],"tail_sequence":primer["cassette"]["tail"],"kind":"primer","length":len(primer["ordered_sequence"]),"gc_percent":primer["gc_percent"],"tm":primer["tm"],"note":primer["note"]})
            for partner in plusminus["partners"]:
                order_sheet.append({"name":f"{name}_common","sequence":partner["sequence"],"annealing_sequence":partner["sequence"],"tail_sequence":"","kind":"primer","length":partner["length"],"gc_percent":partner["gc_percent"],"tm":partner["tm"],"note":partner["note"]})
        return {
            "engine":"discriminating-pair", "provenance":provenance(reaction), "assay":chosen.assay_to_dict(),
            "target":target_to_dict(chosen.target), "reaction":{"polymerase":chosen.preset.id,"polymerase_name":chosen.preset.name,**reaction,"model":thermodynamic_model(chosen.preset,chosen.reaction)},
            "constraints":{field_:getattr(chosen.limits,field_) for field_ in Constraints.__dataclass_fields__},
            "geometry":{"id":"kasp","name":"KASP plus/minus presence–absence","tubes":1,"note":"Two tailed allele-junction primers compete with one shared common primer."},
            "variant":{**normalized_variant.as_dict(),"anchor":None,"normalization":"exact-ref-alt-reconstructed-alleles"},
            "variant_masking":{"nearby_variants":nearby_variant_records,"source":"caller-supplied-vcf-only","population_frequency_inferred":False},
            "mismatch_evidence_model": mismatch_evidence_model,
            "kasp":{"assay_mode":kasp_assay_mode,"chemistry_family":chosen.assay_chemistry_family,"singleplex":True,"call_status":"predicted","call_model":plusminus.get("call_model"),"junction_model":plusminus.get("junction_model"),"design_authority":{"method":"PCRStudio open junction-aware KASP-compatible candidate policy","vendor_kraken_equivalent":False,"validation_required":True,"note":"This branch is not LGC Kraken-equivalent; endpoint cluster validation and controls remain required."}},
            "protocol":selected_protocol, "primers":plusminus.get("primers",[]), "partners":plusminus.get("partners",[]),
            "discrimination":{}, "refused":{}, "band_geometry":None, "background":screen.summary(contigs,template_only),
            "off_targets":off_targets, "why_nothing":str(plusminus.get("why") or ""),
            "orderability":{"orderable":assay_orderable,"status":"orderable" if assay_orderable else "not-orderable-incomplete-design","note":"Junction topology is complete." if assay_orderable else str(plusminus.get("why") or "Incomplete plus/minus design.")},
            "workflow_evidence": evidence_block(request.get("workflow_evidence")),
            "validation_contract":{
                "endpoint_channels":{"x":"FAM","y":"HEX"},
                "required_controls":["at least two NTC wells per assay per plate","positive/presence control","negative/absence control"],
                "recommended_cluster_samples":22,
                "call_states":plusminus.get("call_model",{}).get("states",[]),
                "primary_ranking_mutated_by_evidence":False,
                "source_records":["kasp-cluster-plot-guide","kasp-faq-controls"],
            },
            "order_sheet":order_sheet,
        }

    extra_excluded = list(excluded_from(request))
    if anchor is not None:
        for coordinate in anchor.get("other_differences", []):
            extra_excluded.append((int(coordinate), 1))
    for item in nearby_variant_records:
        coordinate=int(item["at"]); ref_len=max(1,len(str(item.get("ref") or "")))
        if coordinate != design_at:
            extra_excluded.append((coordinate, ref_len))

    assay = design(
        chosen.target.sequence,
        at=design_at,
        alleles=(str(supplied[0]), str(supplied[1])),
        geometry=geometry,
        constraints=chosen.limits,
        conditions=reaction,
        excluded=extra_excluded,
    )

    if geometry == "kasp" and len({p["sequence"] for p in assay.common.values()}) != 1:
        raise DiscriminationError(
            "KASP requires one shared common primer compatible with both allele-specific primers; "
            "no shared candidate was found without changing the assay geometry."
        )
    if geometry == "tetra":
        if assay.band_geometry is None or not assay.band_geometry.get("topology_complete"):
            raise DiscriminationError(
                "Tetra-primer ARMS requires two allele-specific products plus a larger outer-primer control product; "
                "the current four-primer geometry does not satisfy that topology."
            )
        if tetra_min_separation is not None:
            required_gap = int(tetra_min_separation)
            if required_gap < 1:
                raise DiscriminationError("tetra_min_band_separation_bp must be a positive integer.")
            observed_gap = int(assay.band_geometry["minimum_pairwise_separation_bp"])
            if observed_gap < required_gap:
                raise DiscriminationError(
                    f"The closest predicted Tetra-ARMS bands are {observed_gap} bp apart, below the "
                    f"declared {required_gap}-bp electrophoresis-resolution requirement."
                )
            assay.band_geometry["required_minimum_separation_bp"] = required_gap
            assay.band_geometry["resolution_status"] = "passes-declared-computational-size-gap"

    described = assay_to_dict(assay, chosen.limits, **reaction)
    name = label(chosen.target.name)

    # ── Where else these oligos could sit ───────────────────────────────────
    #
    # This page showed a specificity step and this engine had nowhere to put
    # the answer. On a genotyping assay a second site is not a cosmetic
    # problem: a band in the tube for the allele that is not there reads as a
    # heterozygote, and that is a result somebody acts on.
    #
    # Every oligo at once, both alleles' and every partner: the assay runs as
    # one experiment, and an allele-specific primer that pairs with the other
    # tube's partner is exactly the failure worth naming.
    from . import screen

    contigs, template_only, fold_at = screen.contigs_for(
        request, template=chosen.target.sequence, name=chosen.target.name
    )
    named = {f"{allele}-specific": primer.sequence for allele, primer in assay.specific.items()}
    for index, partner in enumerate(described["partners"], start=1):
        named[f"partner {index}"] = partner["sequence"]

    off_targets = screen.oligos(
        named,
        contigs,
        reaction=chosen.reaction,
        fold_at=fold_at,
        max_product=screen.product_ceiling(chosen.limits.product_max),
        # One per band this assay is meant to give. A tetra-primer tube is
        # designed to produce three, and calling all three unwanted would report
        # every design as broken — which is the same as reporting none.
        intended_sizes=(
            described.get("band_geometry", {}).get("all_products_bp", [])
            if geometry == "tetra"
            else [
                partner["product_size"]
                for partner in described["partners"]
                if partner.get("product_size")
            ]
        ),
    )

    why_nothing = _why_nothing(assay, chosen.limits)
    assay_orderable = not bool(why_nothing)
    orderability = {
        "orderable": assay_orderable,
        "status": "orderable" if assay_orderable else "not-orderable-incomplete-design",
        "note": (
            "Both allele-specific branches and their required partner geometry are represented."
            if assay_orderable
            else "The returned partial allele/partner evidence is diagnostic only; an incomplete discrimination assay must not be sent to an oligo supplier."
        ),
    }

    answer = {
        "engine": "discriminating-pair",
        "provenance": provenance(reaction),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "variant_normalized": {**normalized_variant.as_dict(), "anchor": anchor},
        "variant_masking": {
            "nearby_variants": nearby_variant_records,
            "other_variant_differences_masked_from_partner_search": (anchor or {}).get("other_differences", []),
            "source": "caller-supplied-vcf-only",
            "population_frequency_inferred": False,
        },
        "mismatch_evidence_model": mismatch_evidence_model,
        "polymerase_discrimination_scope": {
            "class": "taq-no-proofreading" if not getattr(chosen.preset, "proofreading", False) else "proofreading-prohibited",
            "claim_boundary": "Mismatch classes are evidence-scoped candidate ranking, not a polymerase-independent guarantee."
        },
        "kasp": (
            {
                "assay_mode": kasp_assay_mode,
                "chemistry_family": chosen.assay_chemistry_family,
                "singleplex": True,
                "call_status": "predicted",
                "design_authority": {
                    "method": "PCRStudio Gen-1 internal KASP-compatible candidate policy",
                    "vendor_kraken_equivalent": False,
                    "validation_required": True,
                    "note": (
                        "LGC Biosearch Technologies designs KASP assays with proprietary Kraken "
                        "software and may wet-lab validate/optimise them. PCRStudio does not "
                        "reproduce or claim equivalence to that proprietary design process."
                    ),
                },
            }
            if assay.geometry == "kasp"
            else None
        ),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **reaction,
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "constraints": {
            field_: getattr(chosen.limits, field_) for field_ in Constraints.__dataclass_fields__
        },
        **described,
        # How far the scan looked, and what it found.
        "background": screen.summary(contigs, template_only),
        "off_targets": off_targets,
        "why_nothing": why_nothing,
        "orderability": orderability,
        "workflow_evidence": evidence_block(request.get("workflow_evidence")),
        "order_sheet": ([] if not assay_orderable else [
            {
                "name": f"{name}_{allele}",
                # The whole molecule, tail included. An order sheet that
                # dropped it would be the one thing in this result somebody
                # copies straight into a supplier's form.
                "sequence": (
                    kasp.attach(primer.sequence, index)
                    if assay.geometry == "kasp"
                    else primer.sequence
                ),
                "annealing_sequence": primer.sequence,
                "tail_sequence": (
                    kasp.attach("", index) if assay.geometry == "kasp" else ""
                ),
                "kind": "primer",
                "length": (
                    len(kasp.attach(primer.sequence, index))
                    if assay.geometry == "kasp"
                    else primer.length
                ),
                "gc_percent": primer.gc_percent,
                "tm": primer.tm,
                "note": (
                    f"Allele-specific for {allele}, and it carries a deliberate "
                    f"mismatch {abs(primer.second.at)} bases from its 3' end — order it "
                    "exactly as written. It disagrees with the template on purpose."
                    if primer.second
                    else f"Allele-specific for {allele}."
                ),
            }
            for index, (allele, primer) in enumerate(assay.specific.items())
        ]
        + [
            {
                "name": f"{name}_common_{'_'.join(partner['for_alleles'])}",
                "sequence": partner["sequence"],
                "annealing_sequence": partner["sequence"],
                "tail_sequence": "",
                "kind": "primer",
                "length": partner["length"],
                "gc_percent": partner["gc_percent"],
                "tm": partner["tm"],
                "note": partner["note"],
            }
            for partner in described["partners"]
        ]),
    }
    answer["variant"] = {
        **normalized_variant.as_dict(),
        "anchor": anchor,
        "alleles": list(supplied),
        "note": "Exact REF/ALT identity is retained; single-anchor geometries report any MNV reduction explicitly.",
    }
    answer["validation_contract"] = {
        "empirical_discrimination_required": True,
        "controls": (["NTC", "positive allele A", "positive allele B", "heterozygous control when biologically applicable"] if geometry == "arms-two-tube" else ["NTC", "known genotype controls"]),
        "primary_ranking_mutated_by_evidence": False,
    }
    if geometry == "tetra" and assay.band_geometry is not None:
        assay.band_geometry["readout_context"] = {
            "medium": str(request.get("tetra_readout") or "unresolved"),
            "gel_percent": request.get("tetra_gel_percent"),
            "ladder": request.get("tetra_ladder"),
            "run_context": request.get("tetra_run_context"),
            "resolution_authority": "caller-declared assay workflow; no universal bp threshold inferred",
        }
        answer["band_geometry"] = assay.band_geometry
    if assay.geometry == "kasp":
        selected_protocol = kasp.protocol(
            kasp_protocol,
            plate_format=request.get("kasp_plate_format"),
            instrument_model=request.get("kasp_instrument_model"),
            rox_policy=request.get("kasp_rox_policy"),
        )
        if selected_protocol is not None:
            answer["protocol"] = selected_protocol
    return answer


def _why_nothing(assay: Assay, limits: Constraints) -> str:
    """What stopped this being a usable genotyping assay."""
    if len(assay.specific) < 2:
        missing = [one for one in assay.alleles if one not in assay.specific]
        first = assay.refused.get(missing[0])
        return (
            (first.describe(limits) if first else f"No primer for `{missing[0]}`.")
            + " Both alleles need one: a genotype is read by comparing the two, and a "
            "single reaction cannot tell a homozygote from a failed tube."
        )

    silent = [
        allele for allele, primer in assay.specific.items() if primer.discriminates_by == "nothing"
    ]
    if silent:
        return (
            f"The Gen-1 candidate policy could not construct a supported discrimination "
            f"proposal for `{silent[0]}`: its terminal mismatch is not classified as "
            "sufficiently blocking by the current evidence-scoped model, and no allowed "
            "second-mismatch candidate could be placed within the search window. This is "
            "a software-policy boundary, not proof that the biological assay is impossible."
        )
    if len(assay.common) < len(assay.specific):
        return (
            "One of the allele-specific primers has no partner. Nothing facing it "
            f"within the resolved {limits.product_min}–{limits.product_max} bp product "
            "window satisfied the constraints, which is about the sequence beyond the variant rather "
            "than about the variant itself."
        )
    return ""
