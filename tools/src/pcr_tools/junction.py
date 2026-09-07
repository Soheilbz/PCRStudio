"""Primers that carry the joins, for assembling fragments without ligation.

Gibson assembly and its relatives do not cut and paste. Each fragment is made
with ends that already match its neighbour, an exonuclease chews those ends
back, and the matching single strands find each other. The primers are what put
those matching ends there: each carries a tail that is not part of its own
template at all, but of the fragment next door.

Three things follow, and together they are why this is its own engine rather
than a flag on the ordinary one.

The unit of design is the construct, not the fragment. An overlap is a stretch
of the *finished* molecule that spans a join, so it cannot be reasoned about
from either fragment alone — and the checks that matter (does this overlap occur
anywhere else, do two overlaps anneal to each other) are statements about the
whole assembly. NEB's own manual tells people to build the final sequence in
silico first, which is the tell.

The joining chemistry decides the overlap, and there is no default. Gibson's
protocol says at least 40 bases; NEBuilder says 15 to 30; In-Fusion says exactly
15 and refuses below 12 or above 21; IVA measured a plateau above 15. These are
not four opinions about one number — they are four enzymes. An engine that
prints an overlap length without being told the method is guessing, so the
method is required.

And an ordered oligo here has three thermodynamic contexts that must never be
collapsed into one number. Its annealing portion is screened as a PCR-binding
core; its overlap is judged under the assembly method's own published metric and
reaction context; and the whole tailed oligo has a thermodynamic value of its own.
None of those values, by themselves, authorises a PCR block temperature. A named
PCR chemistry/SOP or bench optimisation has to supply that instruction.
Measured here, joining a pUC19 backbone to a TP53 insert: a 35-base primer whose
whole sequence melts at 76.4 °C and whose annealing portion melts at 60.1 —
16.3 degrees apart, because fifteen of its bases are not on the template at all
until the second cycle has made them so. A block set by the larger number
amplifies nothing in the first cycle, which is the cycle that decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import pairwise
from typing import Any

from .accessibility import fold_oligos
from .design import Constraints, DesignResult, clean_template, design_terminal_pair
from .thermo import (
    analyse,
    pair_dimer,
    reverse_complement,
)
from .registries.authorities import ASSEMBLY_AUTHORITY, record as authority_record
from .workflow_evidence import evidence_block

# NEBuilder standard quantity table scope. Above this fragment count PCRStudio
# may preserve source-backed overlap geometry, but it must not extrapolate the
# standard 4–6-fragment reaction quantities.
NEBUILDER_STANDARD_QUANTITY_MAX_FRAGMENTS = 6

#: Screening reference for overlap cross-talk at the declared assembly
#: temperature. This is diagnostic evidence, not a universal chemistry gate.
ASSEMBLY_CROSS_TALK_TM = 45.0


class JunctionError(ValueError):
    """An assembly that could not be described."""


# ── What the fragments are ─────────────────────────────────────────────────

#: What a segment of the plan can be.
#:
#: The distinction is not cosmetic: it decides which side of a join is allowed
#: to carry the tail. A fragment that is not being amplified has no primer to
#: put a tail on, so the whole overlap has to come from its neighbour.
KINDS = (
    "amplified", "fixed", "literal",  # legacy compatibility aliases
    "pcr-amplified", "restriction-digest", "synthetic-dsdna",
    "ssdna-oligo", "annealed-oligos", "existing-linear",
)
PCR_KINDS = frozenset({"amplified", "pcr-amplified"})
LITERAL_KINDS = frozenset({"literal"})


@dataclass(frozen=True)
class Segment:
    """One piece of the intended construct."""

    name: str
    kind: str
    #: The sequence this contributes to the construct.
    sequence: str
    #: For a PCR-amplified segment, the source template. Defaults to the desired
    #: segment sequence. It may differ at intended end repairs.
    template: str = ""
    orientation: str = "forward"
    concentration_ng_ul: float | None = None
    mass_ng: float | None = None
    volume_ul: float | None = None
    restriction: dict[str, Any] | None = None
    features: tuple[dict[str, Any], ...] = ()
    provenance: str | None = None

    def check(self) -> None:
        if self.kind not in KINDS:
            raise JunctionError(
                f"`{self.name}` is a `{self.kind}`, which is not a kind of fragment "
                "this assembles. It takes: " + ", ".join(KINDS) + "."
            )
        if not self.sequence:
            raise JunctionError(f"`{self.name}` has no sequence.")
        if self.orientation not in {"forward", "reverse"}:
            raise JunctionError(f"`{self.name}` orientation must be forward or reverse.")
        for label, value in (("concentration_ng_ul", self.concentration_ng_ul), ("mass_ng", self.mass_ng), ("volume_ul", self.volume_ul)):
            if value is not None and value <= 0:
                raise JunctionError(f"`{self.name}` {label} must be positive when supplied.")
        if self.kind == "restriction-digest" and not self.restriction:
            raise JunctionError(f"`{self.name}` is restriction-digest material and requires explicit restriction metadata.")

    @property
    def tailable(self) -> bool:
        """Whether a primer for this segment could carry a tail.

        Only an amplified segment has primers at all. A fixed fragment arrives
        already cut, and a literal one is not amplified — it *is* tail.
        """
        return self.kind in PCR_KINDS


# Literal/interposed sequence is constrained by the selected assembly chemistry's
# overlap envelope at the junction where it is used. There is no universal
# synthesis-provider length ceiling here: commercial oligo capabilities vary,
# and a provider/orderability limit is not a biological validity rule.


# ── What the chemistry decides ─────────────────────────────────────────────


@dataclass(frozen=True)
class Method:
    """One joining chemistry, and what it requires of an overlap."""

    id: str
    name: str
    overlap_min: int
    overlap_max: int
    #: Optional floor the overlap has to clear, in the exact metric the source
    #: published. ``None`` means this method does not expose a source-backed
    #: executable Tm gate in Gen-1; a generic Wallace/NN substitute must not be
    #: invented merely to fill the field.
    overlap_tm_min: float | None
    overlap_tm_metric: str | None
    #: In-vitro assembly incubation temperature when the named chemistry has
    #: one. ``None`` for in-vivo joining: there is no single assembly-block
    #: temperature to borrow for folding or dimer decisions.
    assembly_temperature: float | None
    note: str


#: The chemistries this knows, each with its own published figures.
#:
#: Deliberately not averaged into one set of numbers. They disagree because
#: they are different enzymes with different exonuclease doses and reaction
#: times, and picking a middle value would produce overlaps that suit none of
#: them.
METHODS = (
    Method(
        id="nebuilder",
        name="NEBuilder HiFi",
        overlap_min=15,
        overlap_max=30,
        overlap_tm_min=48.0,
        overlap_tm_metric="Wallace 2/4 rule",
        assembly_temperature=50.0,
        note=(
            "15–30 bases melting at 48 °C or above. The master mix's exonuclease dose "
            "and its fifteen-minute reaction were optimised around 15–20, so a longer "
            "overlap is not a safer one."
        ),
    ),
    Method(
        id="gibson",
        name="Gibson assembly (original protocol)",
        overlap_min=40,
        overlap_max=120,
        overlap_tm_min=48.0,
        overlap_tm_metric="Wallace 2/4 rule",
        assembly_temperature=50.0,
        note=(
            "At least 40 bases, which is what the original protocol specifies. Much "
            "longer than the modern kits ask for, and the reason to choose it is "
            "usually that the reaction is being made from its own components."
        ),
    ),
    Method(
        id="in-fusion",
        name="In-Fusion",
        overlap_min=15,
        overlap_max=21,
        overlap_tm_min=None,
        overlap_tm_metric=None,
        assembly_temperature=50.0,
        note=(
            "Takara recommends 15 bp homology for a single insert and 20 bp for "
            "multiple-fragment cloning, and recommends against <12 or >21 bp. "
            "Gen-1 does not invent a Wallace/nearest-neighbour overlap-Tm gate for "
            "In-Fusion because the reviewed vendor design rule is length-based."
        ),
    ),
    Method(
        id="iva",
        name="In-vivo assembly",
        overlap_min=15,
        overlap_max=20,
        overlap_tm_min=None,
        overlap_tm_metric=None,
        assembly_temperature=None,
        note=(
            "IVA joining occurs in vivo after transformation. The original study's "
            "optimised homologous regions were at least 15 bp with Tm about 47–52 °C "
            "(normally 15–20 bp), but Gen-1 does not substitute Wallace Tm for that "
            "published optimisation model. No fictitious 50 °C assembly temperature "
            "is assigned to an in-vivo join."
        ),
    ),
)

BY_ID = {method.id: method for method in METHODS}

ASSEMBLY_PROTOCOLS = ("not-selected", "neb-e5510", "neb-nebuilder-e2621", "neb-nebuilder-e5520", "neb-nebuilder-e2623")


def _nebuilder_numeric_projection(payload: dict[str, Any], branch: str) -> dict[str, Any]:
    """Project one reviewed NEBuilder branch without creating a second numeric authority."""
    source_branch = payload["branches"][branch]
    return {
        "overlap_bp": {"min": source_branch["overlap_bp_min"], "max": source_branch["overlap_bp_max"]},
        "total_fragment_input_pmol": {"min": source_branch["total_pmol_min"], "max": source_branch["total_pmol_max"]},
        "vector_insert_molar_ratio": source_branch["vector_insert_ratio"],
        "incubation": {"temperature_c": source_branch["incubation_c"], "minutes": source_branch["incubation_min"]},
    }


def _unresolved_nebuilder_numeric_projection() -> dict[str, Any]:
    """Represent an intentionally unresolved NEBuilder numeric branch without inheriting reviewed values."""
    return dict(
        overlap_bp=None,
        total_fragment_input_pmol=None,
        vector_insert_molar_ratio=None,
        incubation=None,
    )


def protocol(named: str | None, fragments: int) -> dict[str, Any] | None:
    """Return one canonical vendor overlay without cross-method inheritance."""
    if not named or named == "not-selected":
        return None
    if named not in ASSEMBLY_PROTOCOLS:
        raise JunctionError(
            f"`{named}` is not an assembly protocol this worker knows. It knows: {', '.join(ASSEMBLY_PROTOCOLS)}."
        )
    if named == "neb-e5510":
        if not 2 <= fragments <= 6:
            raise JunctionError("The NEB E5510 numeric overlay is published for 2–6 physical fragments.")
        payload = authority_record(ASSEMBLY_AUTHORITY, named)
        branch = "2-3-fragments" if fragments <= 3 else "4-6-fragments"
        numeric = dict(payload["branches"][branch])
        return {
            "id": named, "selection": payload["selection"],
            "source_identity": payload["source_identity"], "source_url": payload["source_url"],
            "source_reviewed_date": payload["source_reviewed_date"],
            "master_mix": "Gibson Assembly Master Mix (2X)",
            "reaction_volume_uL": numeric["reaction_volume_uL"], "fragment_count": fragments,
            "overlap_bp": {"min": numeric["overlap_bp_min"], "max": numeric["overlap_bp_max"]},
            "total_fragment_input_pmol_min": numeric["total_pmol_min"],
            "total_fragment_input_pmol_max": numeric["total_pmol_max"],
            "vector_input_ng": numeric["vector_input_ng"],
            "insert_molar_excess": numeric["insert_molar_excess"],
            "incubation": {"temperature_c": numeric["incubation_c"], "minutes": numeric["incubation_min"], "branch": branch},
            "unpurified_pcr_fraction_max": numeric["unpurified_pcr_fraction_max"],
            "after_incubation": "hold on ice or at −20 °C until transformation",
            "note": "E5510-only overlay; numeric values are authority-owned by the selected fragment-count branch.",
        }
    # Current NEBuilder branch is driven by the public protocol authority.
    if fragments < 2:
        raise JunctionError("NEBuilder requires at least two physical fragments.")
    branch = "2-3-fragments" if fragments <= 3 else "4-6-fragments" if fragments <= 6 else "7+-design-only"
    payload = authority_record(ASSEMBLY_AUTHORITY, named)
    if fragments <= 6:
        numeric = _nebuilder_numeric_projection(payload, branch)
        execution_status = "executable-protocol"
        note = "NEBuilder numeric values are authority-owned by the selected fragment-count branch."
    else:
        numeric = _unresolved_nebuilder_numeric_projection()
        execution_status = "design-only-numeric-reaction-unresolved"
        note = "Above six fragments the reviewed standard-table numeric branch is unresolved; PCRStudio does not inherit the 4–6-fragment numbers."
    return {
        "id": named, "selection": payload["selection"], "source_identity": payload["source_identity"],
        "source_url": payload["source_url"], "source_reviewed_date": payload["source_reviewed_date"],
        "fragment_count": fragments, "branch": branch, **numeric,
        "capabilities": payload.get("capabilities", []),
        "short_fragment_note": payload.get("short_fragment_note"),
        "execution_status": execution_status,
        "note": note,
    }


def method(named: str | None) -> Method:
    """The chemistry by name, refusing to guess one.

    Raises:
        JunctionError: naming what is available.

    There is deliberately no default. The four chemistries want 15, 15, 15–30
    and 40+ bases respectively, and an overlap designed for the wrong one is
    either an assembly that does not join or an oligo nobody needed to buy.
    """
    if not named:
        raise JunctionError(
            "This needs to know which assembly chemistry you are using, and there is "
            "nothing to default it to: the overlap length is a property of the enzyme "
            "rather than of your DNA. It knows "
            + ", ".join(f"`{one.id}` ({one.name})" for one in METHODS)
            + "."
        )
    if named not in BY_ID:
        raise JunctionError(
            f"`{named}` is not a chemistry this knows. It knows: " + ", ".join(sorted(BY_ID)) + "."
        )
    return BY_ID[named]


# ── The overlap ────────────────────────────────────────────────────────────


def wallace(sequence: str) -> float:
    """The 2/4 rule: two degrees per A or T, four per G or C.

    Used rather than the nearest-neighbour model, and only here. It is a poor
    model of melting and that is not the point — the vendors' 48 °C floor was
    published in this unit, so checking it in any other unit is checking a
    different number. Measured on pUC19: a nearest-neighbour gate at the same
    48 accepts an overlap shorter than fifteen bases at well over half of all
    positions, and passes GCGGCCGCGGCC — a NotI tandem repeat, and exactly the
    palindrome the manuals say costs tenfold.
    """
    upper = sequence.upper()
    return 2.0 * (upper.count("A") + upper.count("T")) + 4.0 * (upper.count("G") + upper.count("C"))


#: Diagnostic run length retained for callers that want to display the
#: historical homopolymer warning. The current engine reports terminal runs
#: and does not turn an unsourced universal run length into a hard rejection.
LONGEST_RUN_AT_AN_END = 4


def ends_badly(window: str, longest_run: int = LONGEST_RUN_AT_AN_END) -> str:
    """Describe a terminal homopolymer run, without making it an assay gate."""
    for side, end in (("start", window[: longest_run + 1]), ("end", window[-longest_run - 1 :])):
        if len(end) == longest_run + 1 and len(set(end)) == 1:
            return (
                f"its {side} is a run of {len(end)} {end[0]}s, which can anneal out of "
                "register and join the fragments at the wrong offset"
            )
    return ""


#: Terminal homopolymer geometry is reported, not hard-thresholded.
#:
#: Repetitive overlap sequence can lower assembly specificity, but the reviewed
#: vendor guidance does not define a universal rule such as "five identical
#: terminal bases makes the overlap invalid".  The previous Gen-1 implementation
#: did exactly that.  We now expose the observed terminal run lengths and leave
#: validity to sequence uniqueness plus the named method's actual constraints.

def terminal_run_length(sequence: str, *, from_start: bool) -> int:
    """Length of the identical-base run at one end of ``sequence``."""
    if not sequence:
        return 0
    view = sequence if from_start else sequence[::-1]
    first = view[0]
    run = 1
    for base in view[1:]:
        if base != first:
            break
        run += 1
    return run


@dataclass(frozen=True)
class Overlap:
    """One candidate join, and where its two halves come from."""

    #: The sequence of the finished construct that spans the join.
    sequence: str
    #: Where it sits in the construct.
    at: int
    #: How many bases come from the upstream fragment.
    from_upstream: int
    #: How many come from the downstream one.
    from_downstream: int
    wallace_tm: float
    #: Terminal homopolymer run lengths are diagnostic-only. They are reported
    #: because repetitive ends can make register ambiguous, but no universal
    #: numeric rejection threshold is asserted.
    terminal_run_start: int = 1
    terminal_run_end: int = 1
    #: Primer3's hairpin melting temperature, on the fallback path only.
    #:
    #: Zero when ViennaRNA answered instead — which is the ordinary case now,
    #: and reports a fraction rather than a temperature because a temperature
    #: is not comparable across forty to a hundred and twenty bases.
    hairpin_tm: float = 0.0
    #: How many bases in the middle are on neither fragment — a tag or a linker
    #: that both primers have to carry.
    interposed: int = 0
    #: Whether the fold check could be run at all.
    #:
    #: It used to be false for every overlap past primer3's sixty-base aligner
    #: limit — most of the original Gibson protocol's own forty-to-a-hundred-
    #: and-twenty range — so `hairpin_tm` was zero because nothing looked,
    #: which is not the same as zero because nothing was found. ViennaRNA folds
    #: any length, so this is now false only when that program is unavailable.
    folded: bool = True
    #: How much of the duplex this overlap exists to form it spends on itself.
    #:
    #: The comparable number, because a free energy scales with length and GC:
    #: a hundred-and-twenty-base overlap folds harder than a forty-base one
    #: whatever either is made of. Zero when nothing folded it.
    fold_fraction: float = 0.0
    #: Dot-bracket at the assembly temperature, so a reader can see the stem.
    fold_structure: str = ""
    #: Which program answered. Empty when none could.
    fold_model: str = ""

    @property
    def length(self) -> int:
        return len(self.sequence)


@dataclass
class Junction:
    """One place two fragments meet.

    A literal segment is not a molecule — nothing in the tube corresponds to
    it — so it does not make a junction of its own. It sits *inside* one,
    between the two real fragments either side, and the overlap has to contain
    all of it. Treating it as a fragment reports two joins where there is one,
    and understates the overlap the two products actually share: measured with
    a six-histidine tag between a pUC19 backbone and a TP53 insert, two joins
    of 30 bases were reported while the products shared 42 — which for a
    chemistry that refuses anything above 21 is a design silently out of spec.
    """

    index: int
    upstream: str
    downstream: str
    #: Where the join falls in the construct.
    #:
    #: For a junction with something interposed, this is where that interposed
    #: sequence begins — the end of the upstream fragment.
    at: int
    #: Sequence lying between the two fragments that belongs to neither, and
    #: which every acceptable overlap must therefore span.
    interposed: str = ""
    chosen: Overlap | None = None
    alternates: list[Overlap] = field(default_factory=list)
    why_nothing: str = ""
    candidate_windows_generated: int = 0
    candidate_windows_measured: int = 0
    fold_diagnostic_complete: bool = True
    candidate_search_complete: bool = True

    @property
    def carries(self) -> list[str]:
        """The literal fragments folded into this junction, for reporting."""
        return [name for name in self.interposed_names]

    interposed_names: list[str] = field(default_factory=list)


def around(construct: str, start: int, length: int, circular: bool) -> str:
    """`length` bases from `start`, wrapping if the construct is a circle.

    The join that closes a circular construct sits at its own beginning, so the
    overlap spanning it takes bases from the end of the sequence and from the
    start. Reading that as a plain slice returns a short window, and a short
    window quietly fails the length gate rather than being reported as the
    wrap it is.
    """
    if start >= 0 and start + length <= len(construct):
        return construct[start : start + length]
    if not circular:
        return ""
    doubled = construct + construct
    start %= len(construct)
    return doubled[start : start + length]


def windows_for(
    construct: str,
    at: int,
    upstream: Segment,
    downstream: Segment,
    how: Method,
    conditions: dict[str, float],
    circular: bool = True,
    interposed: int = 0,
    audit: dict[str, Any] | None = None,
) -> tuple[list[Overlap], str]:
    """Every overlap that could express this join, shortest first.

    The geometry is the whole thing. An overlap takes `a` bases from the
    upstream fragment and `b` from the downstream one; `b` is what the upstream
    fragment's reverse primer must carry as a tail, and `a` is what the
    downstream fragment's forward primer must carry. So a fragment that cannot
    take a tail forces the entire overlap onto its neighbour, and two such
    fragments meeting cannot be joined at all.

    Returns:
        The acceptable overlaps and, when there are none, why.
    """
    if not upstream.tailable and not downstream.tailable:
        return [], (
            f"Neither `{upstream.name}` nor `{downstream.name}` is being amplified, so "
            "neither has a primer that could carry the join. Two fragments that both "
            "arrive with their ends already fixed cannot be given a matching overlap — "
            "one of them has to be amplified."
        )

    # Sequence that belongs to neither fragment has to be carried by both of
    # them, because in a working assembly both products end up containing the
    # whole overlap. A fragment that arrives already cut contains only what it
    # arrived with, so it cannot hold anything interposed.
    if interposed and not (upstream.tailable and downstream.tailable):
        fixed = upstream.name if not upstream.tailable else downstream.name
        return [], (
            f"There are {interposed} bases between `{upstream.name}` and "
            f"`{downstream.name}` that are on neither of them, and `{fixed}` arrives "
            "with its ends already fixed — so it cannot be made to contain them. "
            "Sequence added at a join has to have an amplified fragment on both sides."
        )

    found: list[Overlap] = []
    refused: dict[str, int] = {}
    # Overlaps longer than primer3 will fold. Counted rather than refused: the
    # limit is the aligner's, not the chemistry's, and the original Gibson
    # protocol's own range runs past it.

    # Shortest first, and kept that way: the shortest overlap that clears the
    # gate is the one to use. Extra melting temperature buys nothing, lengthens
    # every oligo that carries it, and the kits were optimised for the short end.
    if interposed > how.overlap_max:
        return [], (
            f"The {interposed} bases sitting between `{upstream.name}` and "
            f"`{downstream.name}` are longer on their own than the {how.overlap_max}-base "
            f"overlap {how.name} allows. Sequence this long wants to be a fragment of "
            "its own rather than something carried inside a primer."
        )

    for length in range(max(how.overlap_min, interposed), how.overlap_max + 1):
        # Whatever is interposed is always in the window; the two ends are what
        # varies. `from_upstream` is taken from the upstream fragment and
        # `from_downstream` from the downstream one.
        spare = length - interposed
        # Evenest split first. At a given overlap length the split decides how
        # long each of the two oligos is and how much of each fragment the join
        # actually grips: two eight-base tails are cheaper to synthesise than
        # one of sixteen, and both primers hold their own template. Where one
        # side cannot carry a tail this is moot — the loop below rejects every
        # split but one.
        for from_upstream in sorted(range(spare + 1), key=lambda taken: abs(taken - spare / 2)):
            from_downstream = spare - from_upstream

            # A fragment that cannot carry a tail must contribute the whole
            # overlap itself, because its neighbour has nowhere to put it.
            if not upstream.tailable and from_downstream:
                continue
            if not downstream.tailable and from_upstream:
                continue

            # An overlap made entirely of interposed sequence joins nothing.
            # It appears in neither template, so if it is repetitive — and a
            # tag usually is — there is nothing holding the two fragments in
            # register. This is the poly-histidine overlap the vendors refuse
            # outright, and requiring the join to reach into both fragments is
            # the same rule stated as geometry.
            if interposed and not (from_upstream and from_downstream):
                continue

            start = at - from_upstream
            window = around(construct, start, length, circular)
            if len(window) != length:
                continue

            warmth = wallace(window)
            if how.overlap_tm_min is not None and warmth < how.overlap_tm_min:
                refused["too cool"] = refused.get("too cool", 0) + 1
                continue

            # Repetitive terminal runs are diagnostic evidence, not a fabricated
            # hard gate. Exact overlap non-uniqueness is checked at construct level
            # later, where ambiguity can actually be demonstrated.

            # Folding is asked once, below, over every candidate at a time.
            # Asking per candidate would start a process per window, and one
            # junction produces dozens of them.
            found.append(
                Overlap(
                    sequence=window,
                    at=start % len(construct),
                    from_upstream=from_upstream,
                    from_downstream=from_downstream,
                    interposed=interposed,
                    wallace_tm=warmth,
                    terminal_run_start=terminal_run_length(window, from_start=True),
                    terminal_run_end=terminal_run_length(window, from_start=False),
                )
            )

    generated_before_fold_cap = len(found)
    if audit is not None:
        audit["candidate_windows_generated"] = generated_before_fold_cap
        audit["fold_candidate_cap"] = MOST_FOLDED
        audit["fold_diagnostic_complete"] = generated_before_fold_cap <= MOST_FOLDED
        # The fold cap is diagnostic-only and does not truncate the selection set.
        audit["candidate_search_complete"] = True

    found, folded_out = _measure_folding(found, how, conditions)
    if audit is not None:
        audit["candidate_windows_measured"] = min(len(found), MOST_FOLDED)
    folded_out.pop("could not be folded", 0)
    for reason, count in folded_out.items():
        refused[reason] = refused.get(reason, 0) + count

    if found:
        return found, ""

    gate = (
        f" The source-backed Tm gate is {how.overlap_tm_min} °C in "
        f"{how.overlap_tm_metric}."
        if how.overlap_tm_min is not None and how.overlap_tm_metric
        else " No generic overlap-Tm gate was invented for this method."
    )
    details = ", ".join(
        f"{count} were {reason}" for reason, count in sorted(refused.items())
    )
    return [], (
        f"No overlap between {how.overlap_min} and {how.overlap_max} bases worked here."
        + (f" {details}." if details else "")
        + gate
    )


def _fold_note(overlap: Overlap, junction: Junction, how: Method) -> str:
    """Report overlap folding as diagnostic evidence only.

    The ViennaRNA DNA model is not calibrated to the undisclosed ionic
    composition of a Gibson/NEBuilder/In-Fusion master mix. Its fold result is
    therefore useful for exposing obvious structure and comparing what the
    model predicts, but it must not define validity or deterministic selection.
    """
    if how.assembly_temperature is None:
        return (
            "Assembly-temperature folding is not assessed for this method: the join "
            "occurs in vivo and Gen-1 does not invent a single host-cell temperature "
            "as an overlap-fold validity model."
        )
    if not overlap.folded or not overlap.fold_model:
        return (
            "Not assessed by the optional ViennaRNA DNA-fold diagnostic. This does "
            "not change overlap validity or selection."
        )

    said = (
        f"ViennaRNA predicts a self-fold/duplex energy fraction of "
        f"{overlap.fold_fraction:.1%} at {how.assembly_temperature:.0f} °C using "
        "its pinned Mathews-2004 DNA parameterization. The master-mix ionic "
        "composition is not represented by an assay-calibrated salt model here, so "
        "this is diagnostic evidence only and does not alter the chosen overlap."
    )
    measured = [one.fold_fraction for one in junction.alternates if one.fold_model]
    if measured:
        said += (
            f" Across {len(measured)} measured candidates at this junction the "
            f"model spans {min(measured):.1%} to {max(measured):.1%}."
        )
    return said


#: How many candidate overlaps per junction are folded.
#:
#: Three times `MOST_BACKTRACKS`, so a set that has to walk onto its alternates
#: to resolve a clash cannot run off the end of what was measured, with room to
#: spare for the ones the fold itself rejects.
#:
#: A cap rather than a search limit: the candidates behind it differ from the
#: ones in front by being longer, and a longer overlap buys nothing here — it
#: lengthens both oligos that carry it. What the cap actually prevents is a
#: junction with six thousand candidates timing out the fold and falling back
#: to the check this replaced.
MOST_FOLDED = 600


def _measure_folding(
    candidates: list[Overlap],
    how: Method,
    conditions: dict[str, float],
) -> tuple[list[Overlap], dict[str, int]]:
    """Attach optional DNA-fold diagnostics without changing candidate order.

    ViennaRNA uses a pinned Mathews-2004 DNA model, but its default 1.021 M salt
    is not an assay-specific representation of proprietary assembly master-mix
    conditions. Consequently the fold result is never a validity gate and never
    reorders candidates in Scientific-Strict. Only a bounded prefix is measured
    for reportability; every candidate remains available to the source-backed
    length/geometry search and clash backtracking.
    """
    if not candidates or how.assembly_temperature is None:
        return candidates, {}

    front = candidates[:MOST_FOLDED]
    named = {str(index): one.sequence for index, one in enumerate(front)}
    measured = fold_oligos(named, how.assembly_temperature)
    if not measured.checked:
        # OPTIONAL evidence must not change validity, rank, or availability.
        return candidates, {"fold diagnostic unavailable": len(front)}

    updated = list(candidates)
    for index, one in enumerate(front):
        fold = measured.folds.get(str(index))
        if fold is None:
            continue
        updated[index] = replace(
            one,
            folded=True,
            fold_fraction=fold.fraction,
            fold_structure=fold.structure,
            fold_model=measured.model,
        )
    return updated, {}


def occurrences(construct: str, window: str, circular: bool) -> list[int]:
    """Every place this sequence appears in the construct, on either strand.

    A circular construct is searched across its own join, which is done by
    scanning it with its first bases appended and discarding hits that start
    past the real end — the off-by-one there reports a phantom second copy of
    every overlap, and a phantom copy reads as a design that must be rejected.
    """
    found: list[int] = []
    for strand in (construct, reverse_complement(construct)):
        haystack = strand + strand[: len(window) - 1] if circular else strand
        start = 0
        while True:
            at = haystack.find(window, start)
            if at < 0 or at >= len(strand):
                break
            found.append(at)
            start = at + 1
    return found


# ── The whole plan ─────────────────────────────────────────────────────────


@dataclass
class Plan:
    """The construct somebody intends to build."""

    segments: list[Segment]
    circular: bool = True

    def check(self) -> None:
        if len(self.segments) < 2:
            raise JunctionError(
                "An assembly joins at least two fragments. One fragment is not an "
                "assembly, it is a PCR."
            )
        for segment in self.segments:
            segment.check()
        if not any(segment.tailable for segment in self.segments):
            raise JunctionError(
                "At least one fragment has to be made by PCR so a primer can carry the assembly junction."
            )
        names = [segment.name for segment in self.segments]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise JunctionError(
                "Two fragments share a name: "
                + ", ".join(repeated)
                + ". Every junction is reported by the fragments either side of it, so "
                "the names have to tell them apart."
            )

    def construct(self) -> str:
        """The finished molecule, which is what everything else is about."""
        return "".join(segment.sequence for segment in self.segments)

    def real(self) -> list[tuple[Segment, int, int]]:
        """The fragments that are actual molecules, with where each one sits.

        A literal is not one. Nothing in the tube corresponds to it — it is
        sequence that will be written into a primer — so it cannot be one end
        of a join.
        """
        placed: list[tuple[Segment, int, int]] = []
        at = 0
        for segment in self.segments:
            if segment.kind not in LITERAL_KINDS:
                placed.append((segment, at, at + len(segment.sequence)))
            at += len(segment.sequence)
        return placed

    def junctions(self) -> list[Junction]:
        """Where two real fragments meet, in construct coordinates.

        Anything literal between them is folded into the junction rather than
        making one of its own, because there is no molecule there to join to.
        A circular plan has one more junction than a linear one: the last
        fragment meets the first.
        """
        placed = self.real()
        if len(placed) < 2:
            return []

        by_name = {segment.name: segment for segment in self.segments}
        found: list[Junction] = []

        pairs = list(pairwise(placed))
        if self.circular:
            pairs.append((placed[-1], placed[0]))

        for index, ((upstream, _, ends), (downstream, starts, _)) in enumerate(pairs):
            # What lies between them: nothing for adjacent fragments, and the
            # literal segments otherwise. On the closing join of a circle that
            # is whatever trails the last fragment plus whatever precedes the
            # first.
            if starts >= ends:
                between = self.construct()[ends:starts]
            else:
                whole = self.construct()
                between = whole[ends:] + whole[:starts]

            found.append(
                Junction(
                    index=index,
                    upstream=upstream.name,
                    downstream=downstream.name,
                    at=ends,
                    interposed=between,
                    interposed_names=[
                        segment.name
                        for segment in self.segments
                        if segment.kind in LITERAL_KINDS and segment.sequence in between
                    ],
                )
            )
        del by_name
        return found


# ── Choosing one overlap per junction ──────────────────────────────────────


@dataclass(frozen=True)
class Clash:
    """Two overlaps that would not tell each other apart."""

    a: int
    b: int
    why: str


def clashes(chosen: dict[int, Overlap], construct: str, circular: bool) -> list[Clash]:
    """What is wrong with this set of overlaps, taken together.

    This is why the engine is one search rather than one search per junction.
    Each overlap on its own can be perfect and the set still fail, in two ways:
    an overlap that occurs twice in the construct joins the wrong pair of
    fragments, and two overlaps that anneal to each other join two fragments
    that were never meant to meet.
    """
    found: list[Clash] = []

    for index, overlap in sorted(chosen.items()):
        seen = occurrences(construct, overlap.sequence, circular)
        if len(seen) > 1:
            found.append(
                Clash(
                    a=index,
                    b=index,
                    why=(
                        f"this overlap occurs {len(seen)} times in the finished "
                        f"construct (at {', '.join(str(one) for one in seen[:4])}), so "
                        "the fragments could join in more than one arrangement"
                    ),
                )
            )

    ordered = sorted(chosen.items())
    for position, (index, one) in enumerate(ordered):
        for other_index, other in ordered[position + 1 :]:
            if one.sequence in other.sequence or other.sequence in one.sequence:
                found.append(
                    Clash(
                        a=index,
                        b=other_index,
                        why="one overlap contains the other, so both joins could be made "
                        "at the same place",
                    )
                )
                continue
            # Pairwise overlap thermodynamics are not a universal assembly
            # validity rule. Predicted heterodimer strength is reported
            # separately as diagnostic evidence; only sequence-identity
            # contradictions (duplicate occurrence/containment) are hard
            # clashes in Scientific-Strict.
    return found


def interaction_diagnostics(chosen: dict[int, Overlap], how: Method) -> list[dict[str, Any]]:
    """Pairwise overlap thermodynamics, reported without a fabricated cutoff."""
    if how.assembly_temperature is None:
        return []
    ordered = sorted(chosen.items())
    measured: list[dict[str, Any]] = []
    for position, (index, one) in enumerate(ordered):
        for other_index, other in ordered[position + 1 :]:
            structure = pair_dimer(
                one.sequence,
                reverse_complement(other.sequence),
                temp_c=how.assembly_temperature,
            )
            measured.append(
                {
                    "a": index,
                    "b": other_index,
                    "dg": structure.dg,
                    "tm": structure.tm,
                    "model_temperature_c": how.assembly_temperature,
                }
            )
    measured.sort(key=lambda entry: entry["dg"])
    return measured


def choose(
    plan: Plan,
    how: Method,
    conditions: dict[str, float],
) -> tuple[list[Junction], list[Clash], dict[str, Any]]:
    """One overlap per junction, shortest first, backing off where they clash.

    Greedy with backtracking rather than exhaustive: each overlap involves only
    its own two neighbours, so the coupling between junctions is weak and the
    shortest acceptable window is nearly always the answer. Where a set does
    clash, the offending junction moves to its next-shortest alternate rather
    than the whole search restarting.
    """
    construct = plan.construct()
    by_name = {segment.name: segment for segment in plan.segments}
    junctions = plan.junctions()
    search_meta: dict[str, Any] = {
        "fold_candidate_cap_per_junction": MOST_FOLDED,
        "backtrack_cap": MOST_BACKTRACKS,
        "backtrack_steps_used": 0,
        "backtrack_limit_hit": False,
    }

    for junction in junctions:
        audit: dict[str, Any] = {}
        found, why = windows_for(
            construct,
            junction.at,
            by_name[junction.upstream],
            by_name[junction.downstream],
            how,
            conditions,
            circular=plan.circular,
            interposed=len(junction.interposed),
            audit=audit,
        )
        junction.candidate_windows_generated = int(
            audit.get("candidate_windows_generated", len(found))
        )
        junction.candidate_windows_measured = int(
            audit.get("candidate_windows_measured", len(found))
        )
        junction.fold_diagnostic_complete = bool(
            audit.get("fold_diagnostic_complete", True)
        )
        junction.candidate_search_complete = bool(
            audit.get("candidate_search_complete", True)
        )
        junction.alternates = found
        junction.why_nothing = why
        junction.chosen = found[0] if found else None

    workable = [one for one in junctions if one.chosen]
    if not workable:
        search_meta["complete"] = all(one.candidate_search_complete for one in junctions)
        return junctions, [], search_meta

    # Try the shortest of everything, then walk one junction at a time onto its
    # next alternate until the set is clean or the alternates run out.
    for step in range(MOST_BACKTRACKS):
        search_meta["backtrack_steps_used"] = step
        chosen = {one.index: one.chosen for one in workable if one.chosen}
        found = clashes(chosen, construct, plan.circular)
        if not found:
            search_meta["complete"] = all(one.candidate_search_complete for one in junctions)
            return junctions, [], search_meta

        moved = False
        offending = {clash.a for clash in found} | {clash.b for clash in found}
        for junction in workable:
            if junction.index not in offending or not junction.chosen:
                continue
            here = junction.alternates.index(junction.chosen)
            if here + 1 < len(junction.alternates):
                junction.chosen = junction.alternates[here + 1]
                moved = True
                break
        if not moved:
            search_meta["complete"] = all(one.candidate_search_complete for one in junctions)
            return junctions, found, search_meta

    search_meta["backtrack_limit_hit"] = True
    search_meta["backtrack_steps_used"] = MOST_BACKTRACKS
    search_meta["complete"] = False
    return junctions, clashes(
        {one.index: one.chosen for one in workable if one.chosen},
        construct,
        plan.circular,
    ), search_meta


#: How many times the search may move a junction onto another overlap.
#:
#: A backstop rather than a tuning parameter. Each step fixes one clash and the
#: coupling between junctions is weak, so a set that has not settled after this
#: many moves is one whose construct repeats itself rather than one that needs
#: longer to search.
MOST_BACKTRACKS = 200


# ── The oligos ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TailedPrimer:
    """One ordered oligo: a tail that joins, and a portion that anneals.

    The two halves are kept apart on purpose. Primer3 never sees the tail,
    which keeps annealing-core thermodynamics distinct from whole-oligo
    thermodynamics. Neither number independently authorises a cycler setting;
    bench cycling belongs to a named amplification chemistry/SOP.
    """

    name: str
    #: Which fragment's reaction this goes in.
    fragment: str
    direction: str
    #: The part that is not on this template at all. May be empty at a
    #: construct's outer ends.
    tail: str
    #: The part Primer3 designed, which is what anneals during PCR.
    anneals: str

    @property
    def sequence(self) -> str:
        return self.tail + self.anneals

    @property
    def length(self) -> int:
        return len(self.sequence)


def tails_for(plan: Plan, junctions: list[Junction]) -> dict[tuple[str, str], str]:
    """Which tail each fragment's two primers must carry.

    The geometry, stated once. At a junction, the upstream fragment's reverse
    primer carries the reverse complement of whatever the downstream fragment
    contributes, and the downstream fragment's forward primer carries whatever
    the upstream one contributes. Each is the half of the overlap its own
    template does not already have.
    """
    wanted: dict[tuple[str, str], str] = {}
    for junction in junctions:
        overlap = junction.chosen
        if not overlap:
            continue
        # Each primer supplies the part of the overlap its own template does
        # not already have. Where something is interposed — a tag, a linker —
        # *both* supply it, because both products have to end up containing the
        # whole overlap and neither template holds that sequence. So the two
        # tails deliberately share those bases rather than dividing them.
        after_upstream = overlap.sequence[overlap.from_upstream :]
        before_downstream = overlap.sequence[: overlap.from_upstream + overlap.interposed]

        if after_upstream:
            wanted[(junction.upstream, "reverse")] = reverse_complement(after_upstream)
        if before_downstream:
            wanted[(junction.downstream, "forward")] = before_downstream
    return wanted


def primers_for(
    plan: Plan,
    junctions: list[Junction],
    constraints: Constraints,
    conditions: dict[str, float],
) -> tuple[list[TailedPrimer], dict[str, DesignResult], dict[str, str]]:
    """The oligos to order, one pair per amplified fragment.

    Returns:
        The primers, what the ordinary search produced for each fragment, and
        any fragment it could not design for with the reason.
    """
    wanted = tails_for(plan, junctions)
    made: list[TailedPrimer] = []
    searched: dict[str, DesignResult] = {}
    refused: dict[str, str] = {}

    for segment in plan.segments:
        if segment.kind not in PCR_KINDS:
            continue
        template = clean_template(segment.template or segment.sequence)
        try:
            found = design_terminal_pair(
                template,
                constraints=constraints,
                conditions=conditions,
                how_many=1,
            )
        except ValueError as error:
            refused[segment.name] = str(error)
            continue
        if not found.pairs:
            refused[segment.name] = (
                f"No pair could be placed on `{segment.name}`. The tails are separate "
                "from this — what failed is the ordinary search on the fragment's own "
                "sequence."
            )
            searched[segment.name] = found
            continue

        searched[segment.name] = found
        pair = found.pairs[0]
        made.append(
            TailedPrimer(
                name=f"{segment.name}_F",
                fragment=segment.name,
                direction="forward",
                tail=wanted.get((segment.name, "forward"), ""),
                anneals=pair.left.sequence,
            )
        )
        made.append(
            TailedPrimer(
                name=f"{segment.name}_R",
                fragment=segment.name,
                direction="reverse",
                tail=wanted.get((segment.name, "reverse"), ""),
                anneals=pair.right.sequence,
            )
        )
    return made, searched, refused


def tubes(primers: list[TailedPrimer]) -> dict[str, list[str]]:
    """Which reaction each oligo goes in, which is not a preference.

    One reaction per amplified fragment. The two primers that share an overlap
    sit in different tubes by construction, because they belong to different
    fragments — and that separation is what stops the two fragments amplifying
    each other instead of themselves.
    """
    grouped: dict[str, list[str]] = {}
    for primer in primers:
        grouped.setdefault(primer.fragment, []).append(primer.name)
    return grouped


# ── Reporting ──────────────────────────────────────────────────────────────


def primer_to_dict(primer: TailedPrimer, how: Method, **conditions: float) -> dict[str, Any]:
    """One oligo, measured on three scales that are never added together.

    Keeping them apart is the point of this function. The annealing portion is
    measured in the PCR thermodynamic model, but it does not by itself authorise
    a cycler setting; that still belongs to a named amplification chemistry/SOP.
    The tail is judged in the assembly method's own terms. And the whole oligo
    has a temperature that describes neither step —
    on a real join, 73.5 °C against an annealing portion of 56.2 °C, which is
    the difference between a programme that works and one that primes
    everywhere.
    """
    anneals = analyse(primer.anneals, **conditions)
    whole = analyse(primer.sequence, **conditions)

    entry: dict[str, Any] = {
        "name": primer.name,
        "fragment": primer.fragment,
        "direction": primer.direction,
        "sequence": primer.sequence,
        "length": primer.length,
        "anneals": {
            "sequence": primer.anneals,
            "length": anneals.length,
            "tm": anneals.tm,
            "gc_percent": anneals.gc_percent,
            "note": (
                f"Annealing-core screening Tm: {anneals.tm} °C. It is the only part "
                "of the oligo on the template in the first cycle, but it is not a "
                "stand-alone PCR block setting; use a named amplification chemistry/SOP."
            ),
        },
        "whole_oligo": {
            "tm": whole.tm,
            "hairpin_tm": whole.hairpin.tm if whole.hairpin.found else None,
            "note": (
                f"The whole oligo melts at {whole.tm} °C, which is not a number to set "
                "anything to — it describes the molecule after the tail has been "
                "copied into the product, not the first cycles. It is here because it "
                "is what gets synthesised, and because its own folding matters."
            ),
        },
    }

    if primer.tail:
        tail_note = (
            f"Not on this fragment's template at all — it is the join to the "
            f"neighbouring fragment. The named in-vitro assembly runs at "
            f"{how.assembly_temperature} °C; that temperature is not a PCR annealing setting."
            if how.assembly_temperature is not None
            else "Not on this fragment's template at all — it is the join to the "
            "neighbouring fragment. This method joins in vivo, so no fictitious "
            "single assembly-block temperature is attached to the tail."
        )
        entry["tail"] = {
            "sequence": primer.tail,
            "length": len(primer.tail),
            "wallace_tm": wallace(primer.tail),
            "note": tail_note,
        }
    else:
        entry["tail"] = None
    return entry


def overlap_to_dict(junction: Junction, how: Method) -> dict[str, Any]:
    """One join, with where each half of it came from."""
    overlap = junction.chosen
    entry: dict[str, Any] = {
        "index": junction.index,
        "between": [junction.upstream, junction.downstream],
        "at": junction.at,
    }
    if not overlap:
        entry["why_nothing"] = junction.why_nothing
        return entry

    entry.update(
        {
            "sequence": overlap.sequence,
            "length": overlap.length,
            "from_upstream": overlap.from_upstream,
            "from_downstream": overlap.from_downstream,
            "interposed": overlap.interposed,
            "carries": junction.interposed_names,
            "wallace_tm": overlap.wallace_tm,
            "terminal_homopolymer_runs": {
                "start": overlap.terminal_run_start,
                "end": overlap.terminal_run_end,
                "classification": "diagnostic-only-no-universal-rejection-threshold",
            },
            "hairpin_tm": overlap.hairpin_tm or None,
            # What the fold found, and by which program. `checked: false` means
            # nothing looked — which is the state every Gibson-length overlap
            # used to be in, and is not the same as nothing being found.
            "fold": {
                "checked": overlap.folded,
                "fraction": overlap.fold_fraction,
                "structure": overlap.fold_structure,
                "model": overlap.fold_model,
                # A ranking needs something to be ranked against, so the range
                # across every other overlap that would have worked here is
                # reported beside it. Without them the fraction is a number
                # with no scale, which invites somebody to invent a pass mark
                # for it — the thing the measurements refused to support.
                "of_alternates": (
                    {
                        "best": min(one.fold_fraction for one in junction.alternates),
                        "worst": max(one.fold_fraction for one in junction.alternates),
                        "count": len(junction.alternates),
                    }
                    if junction.alternates and overlap.fold_model
                    else None
                ),
                "note": (_fold_note(overlap, junction, how)),
            },
            "alternates": len(junction.alternates),
            "search": {
                "candidate_windows_generated": junction.candidate_windows_generated,
                "candidate_windows_measured": junction.candidate_windows_measured,
                "fold_diagnostic_complete": junction.fold_diagnostic_complete,
                "complete": junction.candidate_search_complete,
                "claim": (
                    "all generated candidates remained available to the source-backed validity/search path"
                    if junction.candidate_search_complete
                    else "the bounded clash/backtracking search stopped before exhaustive resolution; this is not a global optimum claim"
                ),
                "fold_claim": (
                    "ViennaRNA diagnostic was measured for all generated candidates"
                    if junction.fold_diagnostic_complete
                    else "ViennaRNA diagnostic was measured only for a bounded prefix and did not affect selection"
                ),
            },
            "note": (
                f"{overlap.length} bases spanning the join, {overlap.from_upstream} of "
                f"them from {junction.upstream} and {overlap.from_downstream} from "
                f"{junction.downstream}"
                + (
                    f", with {overlap.interposed} bases in between that are on neither "
                    "— so both primers write them in, which is why the two tails "
                    "share sequence here rather than dividing it"
                    if overlap.interposed
                    else ""
                )
                + (
                    f". Wallace Tm is {overlap.wallace_tm} °C and this method's "
                    f"source-backed executable floor is {how.overlap_tm_min} °C "
                    f"({how.overlap_tm_metric})."
                    if how.overlap_tm_min is not None and how.overlap_tm_metric
                    else f". Wallace Tm is {overlap.wallace_tm} °C, reported only as "
                    "a diagnostic because this method has no source-backed executable "
                    "Wallace-Tm gate in Gen-1."
                )
                + " This is the shortest overlap inside the reviewed length envelope "
                "that cleared the applicable source-backed gates."
            ),
        }
    )
    return entry


def run(request: dict[str, Any]) -> dict[str, Any]:
    """One assembly design, end to end, in the shape the interface reads.

    Unlike every other engine here this one is not given a template. It is
    given a plan — an ordered list of fragments — and the template it works
    against is the construct those fragments would make. So the shared preamble
    is fed that construct, which is also the sequence every check below is a
    statement about.

    Raises:
        IntakeError: a fragment that is not usable sequence.
        JunctionError: a plan or a chemistry that could not describe an assembly.
        ValueError: a constraint, preset or reaction that cannot hold.
    """
    from .intake import target_to_dict
    from .presets import thermodynamic_model
    from .provenance import provenance
    from .settings import prepare

    supplied = request.get("segments")
    if not isinstance(supplied, list) or len(supplied) < 2:
        raise JunctionError(
            "This needs a plan: the fragments to join, in the order they go in. An "
            "assembly of fewer than two fragments is a PCR."
        )

    known = {"name", "kind", "sequence", "template", "orientation", "concentration_ng_ul", "mass_ng", "volume_ul", "restriction", "features", "provenance"}
    segments: list[Segment] = []
    for index, entry in enumerate(supplied):
        if not isinstance(entry, dict):
            raise JunctionError(f"Fragment {index} is not an object.")
        strange = sorted(set(entry) - known)
        if strange:
            raise JunctionError(
                f"Fragment {index} sets {', '.join(strange)}, which is not something a "
                "fragment has. It has: " + ", ".join(sorted(known)) + "."
            )
        raw_kind = str(entry.get("kind") or "").strip()
        if not raw_kind:
            raise JunctionError(
                f"Fragment {index + 1} needs explicit `kind`: amplified, fixed, or literal. "
                "PCRStudio does not infer PCR amplification from omission."
            )
        segments.append(
            Segment(
                name=str(entry.get("name") or f"fragment {index + 1}"),
                kind=raw_kind,
                sequence=clean_template(str(entry.get("sequence") or "")),
                template=str(entry.get("template") or ""),
                orientation=str(entry.get("orientation") or "forward"),
                concentration_ng_ul=(float(entry["concentration_ng_ul"]) if entry.get("concentration_ng_ul") not in (None, "") else None),
                mass_ng=(float(entry["mass_ng"]) if entry.get("mass_ng") not in (None, "") else None),
                volume_ul=(float(entry["volume_ul"]) if entry.get("volume_ul") not in (None, "") else None),
                restriction=(dict(entry.get("restriction")) if isinstance(entry.get("restriction"), dict) else None),
                features=tuple(entry.get("features") or ()),
                provenance=(str(entry.get("provenance") or "").strip() or None),
            )
        )

    if request.get("circular") is None:
        raise JunctionError(
            "Assembly topology requires explicit `circular`: true or false; circularity changes the junction graph and is not inferred."
        )
    plan = Plan(segments=segments, circular=bool(request["circular"]))
    plan.check()
    assay = request.get("assay") or {}
    assay_id = str(assay.get("id") or "") if isinstance(assay, dict) else ""
    if assay_id == "gibson-assembly" and str(request.get("method") or "") not in {"gibson", "nebuilder"}:
        raise JunctionError(
            "The current Junction Primers surface executes the reviewed Gibson or distinct NEBuilder HiFi branch. In-Fusion/IVA remain characterization/reference branches."
        )
    how = method(request.get("method"))
    physical_fragments = len(plan.real())

    # Fragment-count branches belong to actual DNA molecules in the assembly.
    # A ``literal`` segment is sequence written into primer tails, not a tube
    # fragment, and must never push a 3-fragment reaction into a 4-fragment
    # vendor protocol branch.
    if how.id == "nebuilder":
        # The standard NEBuilder 20-uL quantity table is split into 2–3 and
        # 4–6 fragments, but that table is not an upper scientific limit on
        # sequence design. NEB describes a 4+ fragment overlap/incubation
        # branch and has tested larger assemblies. Above six fragments we may
        # design the source-backed 20–30-nt joins, but must not extrapolate the
        # 4–6-fragment reaction quantities as if they were a validated setup.
        if physical_fragments <= 3:
            how = replace(
                how,
                overlap_min=15,
                overlap_max=20,
                note=(
                    "NEBuilder HiFi 2–3-fragment branch: 15–20 bp overlaps are the "
                    "reviewed optimal design range; the ≥48 °C Wallace criterion remains."
                ),
            )
        else:
            how = replace(
                how,
                overlap_min=20,
                overlap_max=30,
                note=(
                    "NEBuilder HiFi 4+-fragment design branch: 20–30 bp overlaps are "
                    "the reviewed overlap range and the ≥48 °C Wallace criterion remains. "
                    + (
                        "For 4–6 fragments the standard NEB quantity table recommends "
                        "equimolar fragments. "
                        if physical_fragments <= NEBUILDER_STANDARD_QUANTITY_MAX_FRAGMENTS
                        else "For more than six fragments PCRStudio does not extrapolate "
                        "the standard 4–6-fragment reaction quantities; use the NEBuilder "
                        "Protocol Calculator or a separately qualified bench setup. "
                    )
                ),
            )
    elif how.id == "in-fusion":
        # Takara recommends 15 bp homology for a single insert and 20 bp for
        # multiple-fragment cloning, while advising against >21 bp. Keep the
        # source's length rule; do not add a cross-method overlap-Tm threshold.
        how = replace(
            how,
            overlap_min=15 if physical_fragments <= 2 else 20,
            overlap_max=21,
            note=(
                "In-Fusion reviewed design branch: "
                + (
                    "15 bp homology for a vector plus one insert."
                    if physical_fragments <= 2
                    else "20 bp homology for multiple-fragment cloning."
                )
                + " Takara recommends against overlaps longer than 21 bp; Gen-1 "
                "does not invent an overlap-Tm gate for this chemistry."
            ),
        )

    assembly_protocol = request.get("assembly_protocol")
    if assembly_protocol is not None and assembly_protocol not in ASSEMBLY_PROTOCOLS:
        raise JunctionError(
            f"`{assembly_protocol}` is not an assembly protocol this worker knows. It knows: "
            f"{', '.join(ASSEMBLY_PROTOCOLS)}."
        )
    if assembly_protocol == "neb-e5510" and how.id != "gibson":
        raise JunctionError(
            "The NEB E5510 overlay belongs to the Gibson Assembly chemistry; "
            "choose method `gibson` or leave the vendor overlay unselected."
        )
    if assembly_protocol in {"neb-nebuilder-e2621", "neb-nebuilder-e5520", "neb-nebuilder-e2623"} and how.id != "nebuilder":
        raise JunctionError("The selected NEBuilder kit overlay requires method `nebuilder`.")
    if how.id == "nebuilder" and assembly_protocol not in {"neb-nebuilder-e2621", "neb-nebuilder-e5520", "neb-nebuilder-e2623"}:
        raise JunctionError("Executable NEBuilder requires an explicit current NEBuilder protocol identity (E2621/E5520/E2623).")
    if how.id == "iva":
        raise JunctionError(
            "IVA is recognised but not executable in Generation-1: the original optimisation "
            "targets homologous regions of at least 15 bp at about 47–52 °C, but this worker "
            "does not yet reproduce the source-specific overlap-Tm calculation. Substituting "
            "Wallace or the PCR annealing-core model would change the scientific rule. A policy "
            "switch may not activate that approximation."
        )
    if how.id == "gibson" and assembly_protocol != "neb-e5510":
        raise JunctionError(
            "Generation-1 Gibson requires the reviewed `assembly_protocol=neb-e5510` branch. "
            "The historical generic/original Gibson recipe is reference evidence, not an "
            "executable development fallback."
        )

    selected_protocol = protocol(assembly_protocol, physical_fragments)
    if selected_protocol is not None and assembly_protocol == "neb-e5510":
        # E5510 is a named Gibson-kit branch, not the original Gibson
        # protocol's 40+ base rule.  Its own manual ties the usable overlap
        # ceiling to incubation time and fragment count.
        how = replace(
            how,
            name="NEB Gibson Assembly Cloning Kit E5510",
            overlap_min=selected_protocol["overlap_bp"]["min"],
            overlap_max=selected_protocol["overlap_bp"]["max"],
            note=(
                "E5510 overlay: use 15–25 bases for the 2–3-fragment/15-minute "
                "branch or 20–80 bases for the 4–6-fragment/60-minute branch, "
                "matching the current NEB Gibson Assembly guidance."
            ),
        )

    if selected_protocol is not None and how.id == "nebuilder":
        if selected_protocol.get("overlap_bp") is not None:
            how = replace(
                how,
                overlap_min=selected_protocol["overlap_bp"]["min"],
                overlap_max=selected_protocol["overlap_bp"]["max"],
                note=f"NEBuilder {selected_protocol['branch']} overlap geometry is owned by the selected protocol authority.",
            )
        else:
            raise JunctionError(
                "The selected NEBuilder protocol has no reviewed numeric overlap branch above six physical fragments. "
                "PCRStudio refuses to inherit the 4–6-fragment values."
            )

    # The construct is what everything here is about, so it is what the shared
    # preamble reads — the reaction and the constraints are chosen against the
    # molecule being built rather than against any one fragment of it.
    construct = plan.construct()
    chosen = prepare(
        {**request, "template": construct, "segments": None},
        require_product_room=False,
    )
    reaction = chosen.reaction.as_conditions()

    junctions, remaining, search_meta = choose(plan, how, reaction)
    primers, searched, refused = primers_for(plan, junctions, chosen.limits, reaction)

    unjoinable = [one for one in junctions if not one.chosen]

    incomplete_design = bool(unjoinable or refused or remaining)
    if incomplete_design:
        orderability = {
            "orderable": False,
            "status": "not-orderable-incomplete-design",
            "note": "At least one junction/fragment requirement is unresolved. Partial overlap/primer evidence is diagnostic only; do not order this set.",
        }
    elif primers:
        orderability = {
            "orderable": True,
            "status": "orderable",
            "note": "All required junctions are represented without unresolved set-level clashes; the order sheet contains the selected amplified-fragment primers.",
        }
    else:
        orderability = {
            "orderable": False,
            "status": "nothing-to-order-complete-plan",
            "note": "The construct plan is complete but no fragment is PCR-amplified, so PCRStudio has no oligos to order.",
        }

    answer = {
        "engine": "junction-primers",
        "provenance": provenance(reaction),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **reaction,
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "constraints": {
            field_: getattr(chosen.limits, field_) for field_ in Constraints.__dataclass_fields__
        },
        "method": {
            "id": how.id,
            "name": how.name,
            "overlap_min": how.overlap_min,
            "overlap_max": how.overlap_max,
            "overlap_tm_min": how.overlap_tm_min,
            "overlap_tm_metric": how.overlap_tm_metric,
            "assembly_temperature": how.assembly_temperature,
            "note": how.note,
        },
        "construct": {
            "length": len(construct),
            "circular": plan.circular,
            "physical_fragments": physical_fragments,
            "segments": [
                {
                    "name": segment.name,
                    "kind": segment.kind,
                    "length": len(segment.sequence),
                    "tailable": segment.tailable,
                    "orientation": segment.orientation,
                    "production_method": segment.kind,
                    "concentration_ng_ul": segment.concentration_ng_ul,
                    "mass_ng": segment.mass_ng,
                    "volume_ul": segment.volume_ul,
                    "restriction": segment.restriction,
                    "features": list(segment.features),
                    "provenance": segment.provenance,
                    "molarity": ({
                        "pmol_from_mass": round(segment.mass_ng / (0.66 * len(segment.sequence)), 6),
                        "formula": "pmol = mass_ng / (0.66 * bp) for dsDNA approximation",
                        "claim_boundary": "Approximate dsDNA mass↔mole conversion; use exact molecular weight/provider calculator when required."
                    } if segment.mass_ng is not None and segment.kind != "ssdna-oligo" else None),
                }
                for segment in plan.segments
            ],
            "note": (
                f"{len(construct):,} bases in {len(plan.segments)} fragments"
                + (", closed into a circle." if plan.circular else ", left linear.")
                + " Every overlap below is a stretch of this finished sequence rather "
                "than of any one fragment, which is why they are checked against each "
                "other as a set."
            ),
        },
        "assembly_graph": {
            "nodes": [{"id": segment.name, "kind": segment.kind, "length": len(segment.sequence)} for segment in plan.segments if segment.kind not in LITERAL_KINDS],
            "edges": [{"junction": one.index, "from": one.upstream, "to": one.downstream, "interposed": one.interposed} for one in plan.junctions()],
            "topology": "circular" if plan.circular else "linear",
            "rotation_invariance": "segment-order rotation is a representational change only for circular constructs; scientific output is compared by canonicalized graph/sequence in property tests",
        },
        "feature_integrity": {
            "features_supplied": sum(len(segment.features) for segment in plan.segments),
            "status": "reported-not-inferred",
            "warnings": [
                warning
                for segment in plan.segments
                for warning in ([f"{segment.name}: coding feature length is not divisible by 3"] if any(
                    str(feature.get("type", "")).lower() in {"cds", "orf"} and isinstance(feature.get("start"), int) and isinstance(feature.get("end"), int) and (int(feature["end"])-int(feature["start"])) % 3 != 0
                    for feature in segment.features
                ) else [])
            ],
            "claim_boundary": "PCRStudio reports declared feature/frame inconsistencies; it does not infer biological feature annotations from raw sequence.",
        },
        "search": search_meta,
        "junctions": [overlap_to_dict(one, how) for one in junctions],
        "primers": [primer_to_dict(one, how, **reaction) for one in primers],
        "tubes": tubes(primers),
        "clashes": [{"between": sorted({one.a, one.b}), "why": one.why} for one in remaining],
        "overlap_interactions": {
            "classification": "diagnostic-only-no-universal-pass-fail-threshold",
            "model_temperature_c": how.assembly_temperature,
            "pairs": interaction_diagnostics(
                {one.index: one.chosen for one in junctions if one.chosen}, how
            ),
            "note": (
                "Predicted overlap-overlap heterodimers are reported for expert review "
                "at the named in-vitro assembly temperature when one exists. For in-vivo "
                "assembly this diagnostic is intentionally omitted rather than borrowing "
                "a temperature from another chemistry. These values do not invalidate or "
                "rerank a construct without a separately validated method-specific threshold."
            ),
        },
        "considered": {
            name: result.considered.get("pair", "") for name, result in searched.items()
        },
        "why_nothing": _why_nothing(unjoinable, refused, remaining, primers),
        "orderability": orderability,
        "workflow_evidence": evidence_block(request.get("workflow_evidence")),
        "order_sheet": ([] if incomplete_design else [
            {
                "name": one.name,
                "sequence": one.sequence,
                "annealing_sequence": one.anneals,
                "tail_sequence": one.tail,
                "kind": "primer",
                "length": one.length,
                "gc_percent": analyse(one.sequence, **reaction).gc_percent,
                "tm": analyse(one.anneals, **reaction).tm,
                "tube": one.fragment,
                "note": (
                    f"The temperature here is the annealing portion's, not the whole "
                    f"oligo's — {len(one.tail)} of its {one.length} bases are the join "
                    "and are not on the template in the first cycle."
                )
                if one.tail
                else "",
            }
            for one in primers
        ]),
    }
    if selected_protocol is not None:
        answer["protocol"] = selected_protocol
    return answer


def _why_nothing(
    unjoinable: list[Junction],
    refused: dict[str, str],
    remaining: list[Clash],
    primers: list[TailedPrimer],
) -> str:
    """What stopped this being a complete design, in the order it matters."""
    if unjoinable:
        first = unjoinable[0]
        return (
            f"The join between `{first.upstream}` and `{first.downstream}` could not be "
            f"expressed. {first.why_nothing}"
        )
    if refused:
        name, why = next(iter(refused.items()))
        return f"No primers for `{name}`. {why}"
    if remaining:
        return (
            "Every join can be expressed on its own, but not all at once: "
            + remaining[0].why
            + ". Moving a junction, or amplifying a fragment that is currently fixed, "
            "is what usually resolves it."
        )
    if not primers:
        return "Nothing in this plan is being amplified, so there is nothing to order."
    return ""
