"""Four core oligos over six core regions, plus up to two optional loop primers.

LAMP amplification proceeds without a thermal cycler and holds one temperature. There is no melting step, so nothing separates the
strands for a primer to find — the reaction makes its own single-stranded DNA by
folding into loops, and the primers are what build those loops. That makes this
a geometry problem rather than a search problem, and it is why none of the other
engines here can express it.

Six required regions and up to two optional loop-primer intervals lie in fixed order along the plus strand:

    F3 | gap | F2 | LF interval | F1 | middle | B1c | LB interval | B2c | gap | B3c

and four core oligos plus up to two optional loop oligos are built from them:

    F3   the plus-strand F3 region, priming rightward
    FIP  the reverse complement of F1, then F2 — 5'-F1c-F2-3'
    LF   the reverse complement of the LF interval
    LB   the LB interval as it reads on the plus strand
    BIP  B1c, then the reverse complement of B2c — 5'-B1c-B2-3'
    B3   the reverse complement of B3c

Two of the four core oligos are composites, and that is the fact everything follows from.
Only the F2 half of FIP anneals to the template; its F1c half is a 5' tail that
is not on the template at all and becomes a primer later, folding back against
the F1 copy on a strand that does not exist yet when the oligo is made. A pair
search cannot design that — it would be designing a product that is not there.

The loop primers are where a plausible-looking design goes wrong. LF must lie
strictly between the 3' end of F2 and the 5' end of F1, and the exclusion is
structural rather than a preference: an LF overlapping F2 is by construction the
reverse complement of FIP's own F2 half, and an LF overlapping F1 is
complementary to its F1c half. Either one is a perfect dimer with FIP that the
design created on purpose.

PrimerExplorer defines several distances separately. In particular, its
"amplified region" is F2-to-B2 including both regions; F3/B3 sit outside that
span. PCRStudio therefore keeps F2-B2, the two loop spans, F2-F3/B2-B3 gaps and
F1c-B1c middle gap as distinct geometry constraints instead of collapsing them
into one F3-to-B3 product-size surrogate.
"""

from __future__ import annotations

import hashlib
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
from typing import Any

from . import accessibility as access
from . import rt
from .lamp_errors import LoopSetError

# These imports are part of the historical public surface of ``loop_set``;
# callers and downstream tests import the reviewed profiles and geometry
# constants from this module even though their definitions live elsewhere.
from .lamp_geometry import (
    AMPLICON,
    DEFAULT_GEOMETRY_PROFILE_ID,
    DEFAULT_INNER_LINKER_ID,
    END_BASES,
    END_STABILITY,
    EVIDENCE_2026_F2_B2_PREFERRED,
    EVIDENCE_2026_OUTER_GAP,
    EVIDENCE_2026_OUTER_GAP_PREFERRED,
    F2_B2_SPAN,
    GEOMETRY_BOUNDS,
    GEOMETRY_PROFILES,
    INNER_LINKERS,
    LONGEST_RUN,
    LOOP_END_STABILITY,
    LOOP_SPAN,
    MIDDLE_GAP,
    NEB_2025_LOOP_TM_REFERENCE,
    OUTER_GAP,
    PCRSTUDIO_EVIDENCE_2026_GEOMETRY,
    PE_EFFECTIVE_NA_M,
    PE_GAS_CONSTANT,
    PE_MG_M,
    PE_NA_M,
    PE_OLIGO_CONC_M,
    PE_THERMODYNAMIC_MODEL,
    PRIMEREXPLORER_V5_GEOMETRY,
    WINDOW_BOUNDS,
    WINDOW_INTEGER_FIELDS,
    GeometryProfile,
    Region,
    adjust,
    check_geometry,
    geometry_profile_for,
    inner_linker_for,
    primerexplorer_v5_end_dg,
    primerexplorer_v5_tm,
    smallest_amplicon,
    smallest_f2_b2_span,
)
from .lamp_multiplex import resolve as resolve_lamp_multiplex
from .lamp_numeric_recipes import (
    LAMP_ACCELERATION_ADDITIVES,
    LAMP_CARRYOVER_STRATEGIES,
    LAMP_INSTRUMENT_PROFILES,
    LAMP_NUMERIC_OPTIMIZATION_ENVELOPES,
    LAMP_PREINCUBATION_STRATEGIES,
    LAMP_PRIMER_KINETICS_PROFILES,
    LAMP_RECONSTITUTION_OPTIONS,
    LAMP_SAMPLE_BUFFER_TYPES,
    LAMP_SPECIFICITY_ADDITIVES,
    resolve_numeric_recipe,
)
from .lamp_profiles import (
    AT_RICH,
    AT_RICH_AT_OR_BELOW,
    BY_ID,
    GC_RICH,
    GC_RICH_AT_OR_ABOVE,
    LOOP_GC_MAX,
    LOOP_GC_MIN,
    LOOP_PRIMER_WINDOW,
    NORMAL,
    SETS,
    Window,
    Windows,
    target_gc_interval,
    windows_for,
)
from .modified_oligos import provenance_block as modified_oligo_provenance
from .registries.lamp import (
    _READOUT_CHEMISTRY_BRANCH,
    LAMP_CONFIRMATION_MODES,
    LAMP_DESIGN_INTENTS,
    LAMP_DESIGN_STAGES,
    LAMP_DETECTION_TOPOLOGIES,
    LAMP_FIXED_PRIMER_ROLES,
    LAMP_FORMULATIONS,
    LAMP_LOOP_POLICIES,
    LAMP_MUTATION_ANCHORS,
    LAMP_PROTOCOL_REGISTRY,
    LAMP_PROTOCOLS,
    LAMP_READOUT_CHEMISTRIES,
    LAMP_READOUTS,
    LAMP_SAMPLE_MATRICES,
    LAMP_SAMPLE_PREPARATIONS,
    LAMP_SCREENING_COHORT,
)
from .specificity import BackgroundTooLarge
from .thermo import (
    DEFAULT_CONDITIONS,
    analyse,
    gc_percent,
    pair_dimer,
    reverse_complement,
)
from .workflow_evidence import WorkflowEvidenceError, validate_evidence_fields

__all__ = [
    "AMPLICON",
    "AT_RICH",
    "AT_RICH_AT_OR_BELOW",
    "BY_ID",
    "DEFAULT_GEOMETRY_PROFILE_ID",
    "DEFAULT_INNER_LINKER_ID",
    "EVIDENCE_2026_F2_B2_PREFERRED",
    "EVIDENCE_2026_OUTER_GAP",
    "EVIDENCE_2026_OUTER_GAP_PREFERRED",
    "F2_B2_SPAN",
    "GC_RICH",
    "GC_RICH_AT_OR_ABOVE",
    "GEOMETRY_BOUNDS",
    "GEOMETRY_PROFILES",
    "INNER_LINKERS",
    "LONGEST_RUN",
    "LOOP_PRIMER_WINDOW",
    "LOOP_SPAN",
    "MIDDLE_GAP",
    "NEB_2025_LOOP_TM_REFERENCE",
    "NORMAL",
    "OUTER_GAP",
    "PCRSTUDIO_EVIDENCE_2026_GEOMETRY",
    "PE_EFFECTIVE_NA_M",
    "PE_GAS_CONSTANT",
    "PE_MG_M",
    "PE_NA_M",
    "PE_OLIGO_CONC_M",
    "SETS",
    "WINDOW_BOUNDS",
    "WINDOW_INTEGER_FIELDS",
    "Region",
    "smallest_amplicon",
    "smallest_f2_b2_span",
]

# Bounded diagnostic scan: this is intentionally reported as a ceiling rather
# than presented as exhaustive thermodynamic evidence.
THREE_PRIME_SCAN_BASES = 12
THREE_PRIME_REVIEW_BASES = 4
CORE_OLIGO_NAMES = {"F3", "FIP", "BIP", "B3"}


class LoopSetBackgroundTooLarge(BackgroundTooLarge, LoopSetError):
    """A LAMP background that needs indexed validation instead of a direct scan."""


# ── Enumerating what could serve each role ─────────────────────────────────


@dataclass(frozen=True)
class Candidate:
    """One stretch of template that could serve one role."""

    start: int
    length: int
    tm: float
    gc: float
    #: Stability of the role-specific mechanistically critical terminal 6-mer.
    #: For F2/B2/F3/B3/LF/LB this is the 3' end; for F1c/B1c it is the 5' end.
    end_dg: float

    @property
    def end(self) -> int:
        return self.start + self.length


def longest_run(sequence: str) -> int:
    """The longest stretch of one repeated base."""
    longest = run = 1
    for index in range(1, len(sequence)):
        run = run + 1 if sequence[index] == sequence[index - 1] else 1
        longest = max(longest, run)
    return longest


def is_palindromic(sequence: str) -> bool:
    """Whether a sequence is its own reverse complement.

    This is exposed as a small diagnostic helper for callers inspecting a
    candidate; the current candidate policy reports such geometry rather than
    adding an unsourced universal hard gate.
    """
    return sequence.upper() == reverse_complement(sequence.upper())


def _overlaps(start: int, length: int, excluded: list[tuple[int, int]] | None) -> bool:
    """Whether a stretch touches any region that was ruled out.

    Every ordered oligo present in the selected set is checked against this, not only the ones a
    variant sits under. A LAMP set is read as turbidity or a colour change
    rather than as a band, so an oligo that fails on half the samples does not
    show up as a fainter signal — it shows up as a negative.
    """
    if not excluded:
        return False
    end = start + length
    return any(start < at + span and end > at for at, span in excluded)


def candidates(
    template: str,
    window: Window,
    windows: Windows,
    conditions: dict[str, float],
    *,
    primes_from: str,
    excluded: list[tuple[int, int]] | None = None,
    gc_bounds: tuple[float | None, float | None] | None = None,
    end_stability_threshold: float = END_STABILITY,
) -> dict[int, list[Candidate]]:
    """Every stretch that could serve a role, indexed by where it starts.

    Args:
        primes_from: Which end of the plus-strand stretch becomes the working
            3' end of the oligo built from it. `start` for a region whose oligo
            is the reverse complement — B2, B3 and the backward loop — and
            `end` for one used as it reads.

    One pass over the template serves both orientations, because a stretch and
    its reverse complement melt at the same temperature. What differs between
    them is only which end has to hold on.
    """
    found: dict[int, list[Candidate]] = {}
    gc_min, gc_max = gc_bounds if gc_bounds is not None else (windows.gc_min, windows.gc_max)

    for start in range(len(template)):
        for length in range(window.length_min, window.length_max + 1):
            if start + length > len(template):
                break
            if _overlaps(start, length, excluded):
                # Rejected here rather than after a set is assembled, because
                # a multi-region LAMP set means one blocked stretch would
                # otherwise be found and discarded thousands of times over.
                continue
            stretch = template[start : start + length].upper()
            if any(base not in "ACGT" for base in stretch):
                continue
            gc = gc_percent(stretch)
            if gc_min is not None and gc < gc_min:
                continue
            if gc_max is not None and gc > gc_max:
                continue
            tm = primerexplorer_v5_tm(stretch)
            if window.tm_min is not None and tm < window.tm_min:
                continue
            if window.tm_max is not None and tm > window.tm_max:
                continue

            # Do not reject a terminal palindrome by identity alone. PrimerExplorer
            # exposes end-stability and dimer-potential criteria; a blanket
            # self-reverse-complement rule would be an additional unsourced hard gate.
            terminal = stretch[:END_BASES] if primes_from == "start" else stretch[-END_BASES:]
            dg = primerexplorer_v5_end_dg(terminal)
            if dg > end_stability_threshold:
                continue

            found.setdefault(start, []).append(
                Candidate(start=start, length=length, tm=tm, gc=gc, end_dg=dg)
            )
    return found


# ── Putting a set together ─────────────────────────────────────────────────


@dataclass(frozen=True)
class Half:
    """One end of a set: an outer, an inner, and the loop between them."""

    outer: Candidate
    inner: Candidate
    loop: Candidate | None
    #: PrimerExplorer loop-forming distance in orientation-aware target coordinates.
    #: Forward: F1c-region start minus F2 start; backward mirror: B2-region
    #: end minus B1c-region end. These conventions reproduce V5 Figure 1.4.
    span: int

    def spread(self) -> float:
        """How far apart the melting temperatures in this half are."""
        temperatures = [self.outer.tm, self.inner.tm] + ([self.loop.tm] if self.loop else [])
        return round(max(temperatures) - min(temperatures), 1)


@dataclass(frozen=True)
class Set:
    """Four core oligos plus optional LF/LB, and where each target region sits."""

    forward: Half
    backward: Half
    #: F2, F1, B1c, B2c in plus-strand coordinates.
    f3: Candidate
    b3: Candidate

    @property
    def start(self) -> int:
        return self.f3.start

    @property
    def end(self) -> int:
        return self.b3.end

    @property
    def size(self) -> int:
        return self.end - self.start

    def loops(self) -> int:
        """How many of the two optional loop primers this set has.

        Not required — a set of four oligos works — but they roughly halve the
        time to a result, which is most of the point of running an isothermal
        reaction rather than a PCR.
        """
        return sum(1 for half in (self.forward, self.backward) if half.loop)

    @property
    def f2_b2_span(self) -> int:
        """PrimerExplorer amplified region: F2 start through B2 end."""
        return self.backward.outer.end - self.forward.outer.start

    @property
    def middle_gap(self) -> int:
        """F1c-B1c distance excluding the primer regions themselves."""
        return self.backward.inner.start - self.forward.inner.end

    def spread(self) -> float:
        """Diagnostic whole-set Tm range; not a ranking/validity target."""
        temperatures = [
            self.forward.outer.tm,
            self.forward.inner.tm,
            self.backward.outer.tm,
            self.backward.inner.tm,
        ]
        for half in (self.forward, self.backward):
            if half.loop:
                temperatures.append(half.loop.tm)
        return round(max(temperatures) - min(temperatures), 1)

    def thermal_rank(self, windows: Windows) -> tuple[float, float, float]:
        """Source-shaped ranking without turning ranking into validity.

        PrimerExplorer guidance favours ~5 °C between F2/F1c and B2/B1c,
        and matched corresponding F/B regions. Exact role-window centres are
        used only where the published preset supplies both edges.
        """
        correspondence = abs(self.forward.outer.tm - self.backward.outer.tm) + abs(
            self.forward.inner.tm - self.backward.inner.tm
        )
        offset_error = abs((self.forward.inner.tm - self.forward.outer.tm) - 5.0) + abs(
            (self.backward.inner.tm - self.backward.outer.tm) - 5.0
        )
        centre_error = 0.0
        for candidate, window in (
            (self.forward.outer, windows.outer),
            (self.backward.outer, windows.outer),
            (self.forward.inner, windows.inner),
            (self.backward.inner, windows.inner),
        ):
            if window.tm_min is not None and window.tm_max is not None:
                centre_error += abs(candidate.tm - ((window.tm_min + window.tm_max) / 2))
        if self.forward.loop and self.backward.loop:
            correspondence += abs(self.forward.loop.tm - self.backward.loop.tm)
        return (round(correspondence, 3), round(offset_error, 3), round(centre_error, 3))

    def evidence_rank(
        self, geometry_profile: GeometryProfile = PRIMEREXPLORER_V5_GEOMETRY
    ) -> tuple[float, float, float]:
        """Soft, profile-scoped geometry/loop preferences; lower is better.

        A compatibility profile has no hidden newer preference: its penalties
        are therefore zero inside its source-valid envelope. The Evidence-2026
        profile adds narrower empirical preference bands without turning them
        into eligibility gates.
        """
        span_penalty = 0.0
        if geometry_profile.preferred_f2_b2_span is not None:
            low, high = geometry_profile.preferred_f2_b2_span
            span_penalty = (
                float(low - self.f2_b2_span)
                if self.f2_b2_span < low
                else float(self.f2_b2_span - high)
                if self.f2_b2_span > high
                else 0.0
            )
        outer_gap_penalty = 0.0
        if geometry_profile.preferred_outer_gap is not None:
            low, high = geometry_profile.preferred_outer_gap
            gaps = (
                self.forward.outer.start - self.f3.end,
                self.b3.start - self.backward.outer.end,
            )
            for gap in gaps:
                if gap < low:
                    outer_gap_penalty += low - gap
                elif gap > high:
                    outer_gap_penalty += gap - high
        loop_penalty = 0.0
        if geometry_profile.preferred_loop_tm is not None:
            tm_low, tm_high = geometry_profile.preferred_loop_tm
            for half in (self.forward, self.backward):
                if not half.loop:
                    continue
                if half.loop.tm < tm_low:
                    loop_penalty += tm_low - half.loop.tm
                elif half.loop.tm > tm_high:
                    loop_penalty += half.loop.tm - tm_high
        return (round(span_penalty, 3), round(outer_gap_penalty, 3), round(loop_penalty, 3))


def _spatial_order(starts: list[int], bins: int = 64) -> list[int]:
    """Interleave coordinate quantiles so bounded search is not 5'-biased.

    When the search completes this changes no answer.  When a computational cap
    is hit, the evaluated subset now represents the full target instead of the
    earliest coordinates only.
    """
    if len(starts) <= 1 or bins <= 1:
        return starts
    bins = min(bins, len(starts))
    chunks = [
        starts[(index * len(starts)) // bins : ((index + 1) * len(starts)) // bins]
        for index in range(bins)
    ]
    ordered: list[int] = []
    depth = 0
    while len(ordered) < len(starts):
        added = False
        for chunk in chunks:
            if depth < len(chunk):
                ordered.append(chunk[depth])
                added = True
        if not added:
            break
        depth += 1
    return ordered


def _spatial_sample(values: list[Any], count: int) -> list[Any]:
    """Choose a coordinate-ordered sample that spans the full input interval.

    ``_spatial_order`` is useful when most/all of an interleaved sequence will
    be consumed, but taking a short prefix from it can still favour its earliest
    quantile bins. This sampler is for actual truncation: it selects approximately
    equally spaced ranks including both ends (or the centre for a single slot),
    so a bounded diversity tranche remains target-wide and reverse-order
    symmetric at the level of selected ranks.
    """
    if count <= 0 or not values:
        return []
    if len(values) <= count:
        return list(values)
    if count == 1:
        return [values[(len(values) - 1) // 2]]
    last = len(values) - 1
    denominator = count - 1
    indices = [(index * last + denominator // 2) // denominator for index in range(count)]
    return [values[index] for index in indices]


def _longest_extendable_3p_match(primer: str, partner: str) -> int:
    """Longest exact 3' suffix of ``primer`` that can anneal to ``partner``.

    A polymerase can extend only from the primer's 3' end, so this deliberately
    distinguishes extendable terminal complementarity from arbitrary internal
    duplex stability.  It is a sequence-level risk feature, not a kinetic model.
    """
    cap = min(THREE_PRIME_SCAN_BASES, len(primer), len(partner))
    for length in range(cap, 1, -1):
        if reverse_complement(primer[-length:]) in partner:
            return length
    return 0


def three_prime_interaction_risk(oligos_by_name: dict[str, str]) -> dict[str, Any]:
    """Mechanistic 3'-extendability screen for self- and cross-interactions.

    The result intentionally remains a risk ranking/diagnostic.  Published LAMP
    experiments support terminal complementarity as one NSA mechanism, but recent
    multi-set work shows that no sequence/thermodynamic metric alone is a reliable
    specificity oracle.
    """
    names = sorted(oligos_by_name)
    events: list[dict[str, Any]] = []
    for primer_name in names:
        primer = oligos_by_name[primer_name]
        for partner_name in names:
            # A directed event matters because only primer_name's 3' end is the
            # extending end under consideration.  Self-events cover hairpin/
            # homodimer-capable terminal complementarity.
            partner = oligos_by_name[partner_name]
            bases = _longest_extendable_3p_match(primer, partner)
            if bases < 2:
                continue
            events.append(
                {
                    "primer_3p": primer_name,
                    "partner": partner_name,
                    "bases": bases,
                    "review": bases >= THREE_PRIME_REVIEW_BASES,
                    "core_core": primer_name in CORE_OLIGO_NAMES
                    and partner_name in CORE_OLIGO_NAMES,
                }
            )

    events.sort(
        key=lambda event: (
            -event["bases"],
            not event["core_core"],
            event["primer_3p"],
            event["partner"],
        )
    )
    core = [event for event in events if event["core_core"]]
    return {
        "classification": "risk-ranking-not-pass-fail",
        "review_at_or_above_bases": THREE_PRIME_REVIEW_BASES,
        "core_core_max_bases": max((event["bases"] for event in core), default=0),
        "core_core_review_events": sum(bool(event["review"]) for event in core),
        "all_max_bases": max((event["bases"] for event in events), default=0),
        "all_review_events": sum(bool(event["review"]) for event in events),
        "events": events[:24],
        "note": (
            "Exact extendable 3'-terminal complementarity is surfaced because primer-driven "
            "nonspecific amplification has been experimentally observed in LAMP. The 4-base "
            "marker is a review trigger from published observations, not a universal rejection "
            "threshold; empirical LAMP specificity cannot be inferred from this metric alone."
        ),
    }


def _set_sequence_risk_rank(
    template: str, one: Set, *, inner_linker: str = ""
) -> tuple[int, int, int, int]:
    risk = three_prime_interaction_risk(
        {oligo.name: oligo.sequence for oligo in oligos(template, one, inner_linker=inner_linker)}
    )
    return (
        int(risk["core_core_max_bases"]),
        int(risk["core_core_review_events"]),
        int(risk["all_max_bases"]),
        int(risk["all_review_events"]),
    )


def _three_prime_gc_run(sequence: str) -> int:
    run = 0
    for base in reversed(sequence.upper()):
        if base not in "GC":
            break
        run += 1
    return run


def _three_prime_gc_count(sequence: str, bases: int = 6) -> int:
    return sum(base in "GC" for base in sequence.upper()[-bases:])


def _set_terminal_gc_rank(
    template: str, one: Set, *, inner_linker: str = ""
) -> tuple[int, int, int]:
    """NEB/Eiken terminal-composition preferences as soft evidence only.

    A GC presence within the terminal six bases is favourable, while >3
    consecutive terminal G/C bases is discouraged.  Neither is promoted to a
    universal hard gate because the cited guidance does not establish assay
    invalidity at a single sequence cutoff.
    """
    made = oligos(template, one, inner_linker=inner_linker)
    runs = [_three_prime_gc_run(oligo.sequence) for oligo in made]
    no_clamp = sum(_three_prime_gc_count(oligo.sequence) == 0 for oligo in made)
    return (
        no_clamp,
        max((max(0, run - 3) for run in runs), default=0),
        sum(run > 3 for run in runs),
    )


def _cheap_set_rank(
    windows: Windows,
    one: Set,
    *,
    geometry_profile: GeometryProfile = PRIMEREXPLORER_V5_GEOMETRY,
) -> tuple[Any, ...]:
    """Fast source-shaped rank used before sequence-interaction expansion."""
    return (
        *one.evidence_rank(geometry_profile),
        *one.thermal_rank(windows),
        -one.loops(),
        one.f2_b2_span,
        one.start,
    )


def _set_rank(
    template: str,
    windows: Windows,
    one: Set,
    *,
    geometry_profile: GeometryProfile = PRIMEREXPLORER_V5_GEOMETRY,
    inner_linker: str = "",
) -> tuple[Any, ...]:
    """Evidence-rich rank on the bounded risk-review shortlist."""
    sequence_risk = _set_sequence_risk_rank(template, one, inner_linker=inner_linker)
    return (
        *sequence_risk,
        -one.loops(),
        *one.evidence_rank(geometry_profile),
        *_set_terminal_gc_rank(template, one, inner_linker=inner_linker),
        *one.thermal_rank(windows),
        one.f2_b2_span,
    )


def _risk_rank_pool(cheap_ranked: list[Set], limit: int) -> tuple[list[Set], bool]:
    """Keep high-quality and spatially diverse sets for expensive risk ranking.

    Sixty percent of the pool is the best cheap source-shaped rank.  The rest is
    filled by coordinate-stratified sampling across the complete joined list so
    a bounded computation does not become a hidden 5'- or single-locus bias.
    """
    if len(cheap_ranked) <= limit:
        return cheap_ranked, False
    preferred_count = max(1, int(limit * 0.60))
    chosen = list(cheap_ranked[:preferred_count])
    seen = set(chosen)
    by_coordinate = sorted(cheap_ranked[preferred_count:], key=lambda one: (one.start, one.end))
    diversity_slots = limit - len(chosen)
    for one in _spatial_sample(by_coordinate, diversity_slots):
        if one in seen:
            continue
        chosen.append(one)
        seen.add(one)
        if len(chosen) >= limit:
            break
    return chosen, True


# Preserve a bounded set of loop-primer alternatives for each otherwise
# identical core half. Loop primers are optional; keeping the no-loop variant
# and several deterministic alternatives lets whole-set interaction evidence
# choose a safer LF/LB instead of committing to the locally closest Tm before
# FIP/BIP and the opposite half are known. This is a computational budget, not
# a chemistry threshold, and any pruning is surfaced in search provenance.
LOOP_ALTERNATIVES_PER_HALF = 3


def _loop_variants(
    between: list[Candidate], *, target_tm: float
) -> tuple[list[Candidate | None], int]:
    ranked = sorted(
        between,
        key=lambda one: (abs(one.tm - target_tm), one.start, one.length, one.tm),
    )
    retained = ranked[:LOOP_ALTERNATIVES_PER_HALF]
    pruned = max(0, len(ranked) - len(retained))
    if not retained:
        return [None], pruned
    # The best loop and the no-loop core both survive before lower-ranked loop
    # variants, so even a half-budget boundary does not systematically erase
    # either the acceleration option or the four-primer control alternative.
    return [retained[0], None, *retained[1:]], pruned


def _forward_halves(
    outer: dict[int, list[Candidate]],
    inner: dict[int, list[Candidate]],
    loop: dict[int, list[Candidate]],
    loop_span: tuple[int, int],
    most: int,
    *,
    loop_target_tm: float = 63.0,
) -> tuple[list[Half], bool, int]:
    """F2, F1 and the LF between them, for every workable placement.

    The loop primer is required to sit strictly between the 3' end of F2 and
    the 5' end of F1 — never overlapping either. An LF overlapping F2 is the
    reverse complement of FIP's own F2 half by construction, and one
    overlapping F1 is complementary to its F1c half: both are perfect dimers
    with the composite primer this design is about to make.
    """
    found: list[Half] = []
    loop_alternatives_pruned = 0
    inner_starts = sorted(inner)

    for f2_start in _spatial_order(sorted(outer)):
        for f2 in outer[f2_start]:
            low, high = f2_start + loop_span[0], f2_start + loop_span[1]
            left = bisect_left(inner_starts, max(low, f2.end))
            right = bisect_right(inner_starts, high)
            for f1_start in inner_starts[left:right]:
                for f1 in inner[f1_start]:
                    between = [
                        one
                        for start in range(f2.end, f1_start)
                        for one in loop.get(start, ())
                        if one.end <= f1_start
                    ]
                    variants, pruned = _loop_variants(between, target_tm=loop_target_tm)
                    loop_alternatives_pruned += pruned
                    for loop_candidate in variants:
                        if len(found) >= most:
                            # The next source-valid half exists but falls outside the
                            # bounded search budget. Report that fact rather than
                            # pretending the search was exhaustive.
                            return found, True, loop_alternatives_pruned
                        found.append(
                            Half(
                                outer=f2,
                                inner=f1,
                                loop=loop_candidate,
                                span=f1_start - f2_start,
                            )
                        )
    return found, False, loop_alternatives_pruned


def _backward_halves(
    outer: dict[int, list[Candidate]],
    inner: dict[int, list[Candidate]],
    loop: dict[int, list[Candidate]],
    loop_span: tuple[int, int],
    most: int,
    *,
    loop_target_tm: float = 63.0,
) -> tuple[list[Half], bool, int]:
    """B1c, B2c and the LB between them.

    The mirror of the forward half, and the mirroring is in the coordinates
    rather than in the sequence: B1c comes first on the plus strand and B2c
    second, but the oligos built from them read the other way, so the span that
    becomes the loop is measured between their far ends.
    """
    found: list[Half] = []
    loop_alternatives_pruned = 0
    outer_starts = sorted(outer)
    outer_lengths = [candidate.length for values in outer.values() for candidate in values]
    min_outer_length = min(outer_lengths, default=0)
    max_outer_length = max(outer_lengths, default=0)

    for b1_start in _spatial_order(sorted(inner)):
        for b1 in inner[b1_start]:
            low, high = b1.end + loop_span[0], b1.end + loop_span[1]
            earliest = max(b1.end, low - max_outer_length)
            latest = high - min_outer_length
            left = bisect_left(outer_starts, earliest)
            right = bisect_right(outer_starts, latest)
            for b2_start in outer_starts[left:right]:
                for b2 in outer[b2_start]:
                    if not low <= b2.end <= high:
                        continue
                    between = [
                        one
                        for start in range(b1.end, b2_start)
                        for one in loop.get(start, ())
                        if one.end <= b2_start
                    ]
                    variants, pruned = _loop_variants(between, target_tm=loop_target_tm)
                    loop_alternatives_pruned += pruned
                    for loop_candidate in variants:
                        if len(found) >= most:
                            return found, True, loop_alternatives_pruned
                        found.append(
                            Half(
                                outer=b2,
                                inner=b1,
                                loop=loop_candidate,
                                span=b2.end - b1.end,
                            )
                        )
    return found, False, loop_alternatives_pruned


#: How many halves of each kind to keep before joining them.
#:
#: A cap rather than a tuning parameter: the join is what costs, and a template
#: offering more placements than this offers more than anybody will read.
MOST_HALVES = 4000

# Exact directed 3'-extendability over all ordered oligos is intentionally more
# expensive than geometry/Tm ranking. Evaluate it on a transparent, spatially
# diverse shortlist rather than on every raw join. These are computational
# budgets, never chemistry thresholds, and all truncation is surfaced.
RISK_RANK_POOL_LIMIT = 2048
MOST_CORE_PAIR_EVALUATIONS = 100_000
MAX_BACKWARD_PARTNERS_PER_FORWARD = 128
OUTER_CANDIDATES_PER_SIDE = 8
OUTER_PAIRS_PER_CORE = 4
CORE_PAIR_OUTER_EXPANSION_LIMIT = 4096


def _round_robin_partner_schedule(partner_lists: list[list[int]], limit: int):
    """Yield ``(job_index, partner_index)`` fairly across bounded jobs.

    Every non-empty job receives its first partner before any job receives its
    second, then its second before any receives its third, and so on. This is a
    computational fairness rule only; it does not change LAMP geometry or claim
    that a capped search is globally exhaustive.
    """
    if limit <= 0 or not partner_lists:
        return
    emitted = 0
    max_depth = max((len(partners) for partners in partner_lists), default=0)
    for depth in range(max_depth):
        for job_index, partners in enumerate(partner_lists):
            if depth >= len(partners):
                continue
            yield job_index, partners[depth]
            emitted += 1
            if emitted >= limit:
                return


def _core_pair_rank(
    windows: Windows,
    pair: tuple[Half, Half],
    *,
    geometry_profile: GeometryProfile,
) -> tuple[Any, ...]:
    """Cheap rank before F3/B3 expansion; lower is better.

    Only evidence available from the four core regions is used here. Outer-gap
    preference is deliberately deferred until F3/B3 candidates exist.
    """
    front, behind = pair
    span = behind.outer.end - front.outer.start
    span_penalty = 0.0
    if geometry_profile.preferred_f2_b2_span is not None:
        low, high = geometry_profile.preferred_f2_b2_span
        if span < low:
            span_penalty = float(low - span)
        elif span > high:
            span_penalty = float(span - high)

    loop_penalty = 0.0
    if geometry_profile.preferred_loop_tm is not None:
        low, high = geometry_profile.preferred_loop_tm
        for half in (front, behind):
            if half.loop is None:
                continue
            if half.loop.tm < low:
                loop_penalty += low - half.loop.tm
            elif half.loop.tm > high:
                loop_penalty += half.loop.tm - high

    correspondence = abs(front.outer.tm - behind.outer.tm) + abs(front.inner.tm - behind.inner.tm)
    offset_error = abs((front.inner.tm - front.outer.tm) - 5.0) + abs(
        (behind.inner.tm - behind.outer.tm) - 5.0
    )
    return (
        round(span_penalty, 3),
        round(loop_penalty, 3),
        round(correspondence, 3),
        round(offset_error, 3),
        -(int(front.loop is not None) + int(behind.loop is not None)),
        span,
        front.outer.start,
        behind.outer.end,
    )


def _core_pair_expansion_pool(
    pairs: list[tuple[Half, Half]],
    windows: Windows,
    geometry_profile: GeometryProfile,
    limit: int,
) -> tuple[list[tuple[Half, Half]], bool]:
    """Bound expensive outer expansion while retaining rank and spatial coverage."""
    if len(pairs) <= limit:
        return pairs, False
    ranked = sorted(
        pairs,
        key=lambda pair: _core_pair_rank(windows, pair, geometry_profile=geometry_profile),
    )
    preferred_count = max(1, int(limit * 0.60))
    chosen = list(ranked[:preferred_count])
    seen = set(chosen)
    remainder = sorted(
        ranked[preferred_count:],
        key=lambda pair: (pair[0].outer.start, pair[1].outer.end),
    )
    diversity_slots = limit - len(chosen)
    for pair in _spatial_sample(remainder, diversity_slots):
        if pair in seen:
            continue
        chosen.append(pair)
        seen.add(pair)
        if len(chosen) >= limit:
            break
    return chosen, True


def _mirror_candidate(candidate: Candidate | None, template_length: int) -> Candidate | None:
    """Mirror one plus-strand interval into the caller's reverse orientation."""
    if candidate is None:
        return None
    return Candidate(
        start=template_length - candidate.end,
        length=candidate.length,
        tm=candidate.tm,
        gc=candidate.gc,
        end_dg=candidate.end_dg,
    )


def _mirror_half(half: Half, template_length: int) -> Half:
    """Swap one canonical half into the opposite F/B role on caller coordinates."""
    return Half(
        outer=_mirror_candidate(half.outer, template_length),
        inner=_mirror_candidate(half.inner, template_length),
        loop=_mirror_candidate(half.loop, template_length),
        span=half.span,
    )


def _mirror_set(one: Set, template_length: int) -> Set:
    """Return the physical same LAMP set on reverse-complement caller coordinates."""
    return Set(
        forward=_mirror_half(one.backward, template_length),
        backward=_mirror_half(one.forward, template_length),
        f3=_mirror_candidate(one.b3, template_length),
        b3=_mirror_candidate(one.f3, template_length),
    )


def _mirror_excluded(
    excluded: list[tuple[int, int]] | None, template_length: int
) -> list[tuple[int, int]] | None:
    if excluded is None:
        return None
    return sorted((template_length - (start + length), length) for start, length in excluded)


def _swap_forward_backward_counts(counted: dict[str, int]) -> dict[str, int]:
    """Present canonical-search role counts in the caller's physical orientation."""
    answer = dict(counted)
    for left, right in (
        ("forward_outer_regions", "backward_outer_regions"),
        ("forward_inner_regions", "backward_inner_regions"),
        ("forward_loop_regions", "backward_loop_regions"),
        ("forward_halves", "backward_halves"),
    ):
        if left in answer or right in answer:
            answer[left], answer[right] = answer.get(right, 0), answer.get(left, 0)
    return answer


def sets(
    template: str,
    *,
    windows: Windows | None = None,
    conditions: dict[str, float] | None = None,
    f2_b2_span: tuple[int, int] | None = None,
    loop_span: tuple[int, int] | None = None,
    outer_gap: tuple[int, int] | None = None,
    middle_gap: tuple[int, int] | None = None,
    geometry_profile: GeometryProfile = PRIMEREXPLORER_V5_GEOMETRY,
    inner_linker: str = "",
    how_many: int = 5,
    excluded: list[tuple[int, int]] | None = None,
    fixed_primers: dict[str, str] | None = None,
    mutation_anchor: dict[str, Any] | None = None,
    include_search_meta: bool = False,
) -> (
    tuple[list[Set], Windows, dict[str, int]]
    | tuple[list[Set], Windows, dict[str, int], dict[str, object]]
):
    """Whole sets, best first, with the parameter set they were found under.

    Returns three values for direct low-level callers: the sets, the windows
    in force, and a count of what each stage produced. The executable result
    path opts into the fourth search-metadata value so this diagnostic does
    not break older research helpers that unpack the original three-value
    contract.
    """
    # The selected geometry profile owns omitted low-level geometry arguments.
    # Keeping V5 tuples as Python signature defaults made a direct
    # `sets(..., geometry_profile=Evidence2026)` call look advanced while still
    # searching V5 outer spacing. Explicit tuple arguments remain supported for
    # reviewed/tightened callers; omitted arguments now follow the profile.
    f2_b2_span = f2_b2_span or geometry_profile.valid_f2_b2_span
    loop_span = loop_span or geometry_profile.valid_loop_span
    outer_gap = outer_gap or geometry_profile.valid_outer_gap
    middle_gap = middle_gap or geometry_profile.valid_middle_gap

    input_sequence = template.upper()
    sequence = input_sequence
    search_excluded = excluded
    orientation_canonicalized = False

    # Bounded search used to depend on which strand the caller happened to
    # submit: the per-forward partner cap becomes a per-backward cap after a
    # reverse complement. Search one deterministic physical orientation for
    # every geometry profile, then map selected coordinates/roles back to the
    # caller. This changes no V5/Evidence validity rule; it removes only a
    # computational artefact of an incomplete bounded search.
    reverse = reverse_complement(input_sequence)
    if reverse < input_sequence:
        sequence = reverse
        search_excluded = _mirror_excluded(excluded, len(input_sequence))
        orientation_canonicalized = True

    chosen = windows or windows_for(sequence)
    reaction = {**DEFAULT_CONDITIONS, **(conditions or {})}
    check_geometry(chosen, f2_b2_span, loop_span)

    # The priming/stability end is orientation-specific. Reusing one candidate
    # pool for both sides silently checks the wrong physical end for B2/B3,
    # B1c and LF. PrimerExplorer's end-stability rule is explicitly tied to
    # 3' F2/B2/F3/B3/LF/LB and 5' F1c/B1c, so build mirrored pools.
    outer_forward = candidates(
        sequence, chosen.outer, chosen, reaction, primes_from="end", excluded=search_excluded
    )
    outer_backward = candidates(
        sequence, chosen.outer, chosen, reaction, primes_from="start", excluded=search_excluded
    )
    inner_forward = candidates(
        sequence, chosen.inner, chosen, reaction, primes_from="end", excluded=search_excluded
    )
    inner_backward = candidates(
        sequence, chosen.inner, chosen, reaction, primes_from="start", excluded=search_excluded
    )
    loop_forward = candidates(
        sequence,
        chosen.loop,
        chosen,
        reaction,
        primes_from="start",
        excluded=search_excluded,
        gc_bounds=(LOOP_GC_MIN, LOOP_GC_MAX),
        end_stability_threshold=LOOP_END_STABILITY,
    )
    loop_backward = candidates(
        sequence,
        chosen.loop,
        chosen,
        reaction,
        primes_from="end",
        excluded=search_excluded,
        gc_bounds=(LOOP_GC_MIN, LOOP_GC_MAX),
        end_stability_threshold=LOOP_END_STABILITY,
    )

    loop_target_tm = (
        sum(geometry_profile.preferred_loop_tm) / 2.0
        if geometry_profile.preferred_loop_tm is not None
        else (
            (chosen.loop.tm_min + chosen.loop.tm_max) / 2.0
            if chosen.loop.tm_min is not None and chosen.loop.tm_max is not None
            else 63.0
        )
    )
    forward, forward_halves_capped, forward_loop_alternatives_pruned = _forward_halves(
        outer_forward,
        inner_forward,
        loop_forward,
        loop_span,
        MOST_HALVES,
        loop_target_tm=loop_target_tm,
    )
    backward, backward_halves_capped, backward_loop_alternatives_pruned = _backward_halves(
        outer_backward,
        inner_backward,
        loop_backward,
        loop_span,
        MOST_HALVES,
        loop_target_tm=loop_target_tm,
    )

    counted = {
        "forward_outer_regions": sum(len(one) for one in outer_forward.values()),
        "backward_outer_regions": sum(len(one) for one in outer_backward.values()),
        "forward_inner_regions": sum(len(one) for one in inner_forward.values()),
        "backward_inner_regions": sum(len(one) for one in inner_backward.values()),
        "forward_loop_regions": sum(len(one) for one in loop_forward.values()),
        "backward_loop_regions": sum(len(one) for one in loop_backward.values()),
        "forward_halves": len(forward),
        "backward_halves": len(backward),
        "joined": 0,
    }

    # Hierarchical bounded join.  First use the exact F1/B1c middle-gap
    # coordinate constraint to index the backward halves.  If one forward half
    # still has an unusually large feasible partner set, sample that interval
    # spatially rather than taking its earliest coordinates.  Only after a core
    # F2/F1/B1/B2 geometry survives do we expand F3/B3, and even then only the
    # best few source-shaped outer candidates are crossed.  This moves the
    # computational budget from impossible combinations to biologically valid
    # cores and materially reduces cap-driven 5' bias.
    backward.sort(key=lambda half: half.inner.start)
    backward_starts = [half.inner.start for half in backward]

    found: list[Set] = []
    core_pair_evaluations = 0
    complete_set_evaluations = 0
    core_pair_evaluation_capped = False
    backward_partner_sampling_used = False
    outer_candidate_truncation_used = False
    outer_pair_truncation_used = False

    def preferred_gap_penalty(gap: int) -> int:
        preferred = geometry_profile.preferred_outer_gap
        if preferred is None:
            return 0
        low, high = preferred
        if gap < low:
            return low - gap
        if gap > high:
            return gap - high
        return 0

    def outer_subset(
        candidates_for_side: list[Candidate], reference_tm: float, *, gap_of
    ) -> list[Candidate]:
        nonlocal outer_candidate_truncation_used
        ranked = sorted(
            candidates_for_side,
            key=lambda candidate: (
                preferred_gap_penalty(gap_of(candidate)),
                abs(candidate.tm - reference_tm),
                candidate.start,
                candidate.length,
            ),
        )
        if len(ranked) > OUTER_CANDIDATES_PER_SIDE:
            outer_candidate_truncation_used = True
        return ranked[:OUTER_CANDIDATES_PER_SIDE]

    # Build feasible partner jobs first, then consume them round-robin. A
    # single early forward half can no longer exhaust the global core-pair
    # budget before later target coordinates receive even one evaluation.
    partner_jobs: list[tuple[Half, list[int]]] = []
    partner_count_before_local_sampling = 0
    partner_count_after_local_sampling = 0
    f3_cache: dict[int, list[Candidate]] = {}
    b3_cache: dict[int, list[Candidate]] = {}

    for front in forward:
        f3_candidates = f3_cache.setdefault(
            front.outer.start,
            _outers_before(outer_forward, front.outer.start, outer_gap),
        )
        if not f3_candidates:
            continue

        low_middle = front.inner.end + middle_gap[0]
        high_middle = front.inner.end + middle_gap[1]
        left = bisect_left(backward_starts, low_middle)
        right = bisect_right(backward_starts, high_middle)
        partner_indices = [
            index
            for index in range(left, right)
            if f2_b2_span[0] <= backward[index].outer.end - front.outer.start <= f2_b2_span[1]
            and b3_cache.setdefault(
                backward[index].outer.end,
                _outers_after(outer_backward, backward[index].outer.end, outer_gap),
            )
        ]
        if not partner_indices:
            continue
        partner_count_before_local_sampling += len(partner_indices)
        if len(partner_indices) > MAX_BACKWARD_PARTNERS_PER_FORWARD:
            backward_partner_sampling_used = True
            partner_indices = _spatial_sample(partner_indices, MAX_BACKWARD_PARTNERS_PER_FORWARD)
        partner_count_after_local_sampling += len(partner_indices)
        partner_jobs.append((front, partner_indices))

    scheduled_potential = partner_count_after_local_sampling
    core_pair_evaluation_capped = scheduled_potential > MOST_CORE_PAIR_EVALUATIONS
    core_pairs: list[tuple[Half, Half]] = []
    for job_index, partner_index in _round_robin_partner_schedule(
        [indices for _, indices in partner_jobs], MOST_CORE_PAIR_EVALUATIONS
    ):
        front, _partner_indices = partner_jobs[job_index]
        behind = backward[partner_index]
        core_pair_evaluations += 1
        core_pairs.append((front, behind))

    # Branch/top-K boundary: ranking four-region cores is cheap; expanding every
    # surviving core into all F3×B3 combinations is not. Preserve both the best
    # source-shaped cores and coordinate diversity, then spend thermodynamic and
    # outer-combination work only on that explicit bounded pool.
    core_pairs, core_pair_outer_expansion_capped = _core_pair_expansion_pool(
        core_pairs, chosen, geometry_profile, CORE_PAIR_OUTER_EXPANSION_LIMIT
    )

    for front, behind in core_pairs:
        f3_candidates = f3_cache[front.outer.start]
        b3_candidates = b3_cache[behind.outer.end]
        f3_short = outer_subset(
            f3_candidates,
            front.outer.tm,
            gap_of=lambda candidate, outer_start=front.outer.start: outer_start - candidate.end,
        )
        b3_short = outer_subset(
            b3_candidates,
            behind.outer.tm,
            gap_of=lambda candidate, outer_end=behind.outer.end: candidate.start - outer_end,
        )

        combinations = [
            Set(forward=front, backward=behind, f3=f3, b3=b3) for f3 in f3_short for b3 in b3_short
        ]
        combinations.sort(
            key=lambda one: _cheap_set_rank(chosen, one, geometry_profile=geometry_profile)
        )
        if len(combinations) > OUTER_PAIRS_PER_CORE:
            outer_pair_truncation_used = True
        selected_outer_pairs = combinations[:OUTER_PAIRS_PER_CORE]
        complete_set_evaluations += len(combinations)
        found.extend(selected_outer_pairs)
        counted["joined"] += len(selected_outer_pairs)

    # First use the cheap source/thermal rank to bound the exact interaction
    # review; then let exact 3'-extendability risk outrank loop availability.
    # Loop primers remain optional acceleration elements, not an unconditional
    # quality bonus: a four-primer core can outrank a six-primer set when the
    # latter carries worse interaction risk.
    #
    # LAMP does *not* ask every region to have one Tm: F1c/B1c are intentionally
    # about 5 °C above F2/B2. Rank on corresponding-region agreement and that
    # source-backed relationship, not on minimizing the total set spread.
    # Do not run the O(set_count × oligo_pairs × terminal-suffixes) risk matrix
    # over every raw join.  First rank cheaply, then preserve both the best
    # source-shaped candidates and target-wide spatial diversity for the exact
    # 3'-extendability review.
    found.sort(key=lambda one: _cheap_set_rank(chosen, one, geometry_profile=geometry_profile))
    risk_pool, risk_ranking_capped = _risk_rank_pool(
        found, max(RISK_RANK_POOL_LIMIT, how_many * 64)
    )
    risk_pool.sort(
        key=lambda one: _set_rank(
            sequence, chosen, one, geometry_profile=geometry_profile, inner_linker=inner_linker
        )
    )
    found = risk_pool
    search = {
        "complete": not (
            forward_halves_capped
            or backward_halves_capped
            or forward_loop_alternatives_pruned > 0
            or backward_loop_alternatives_pruned > 0
            or core_pair_evaluation_capped
            or core_pair_outer_expansion_capped
            or backward_partner_sampling_used
            or outer_candidate_truncation_used
            or outer_pair_truncation_used
            or risk_ranking_capped
        ),
        "forward_halves_capped": forward_halves_capped,
        "backward_halves_capped": backward_halves_capped,
        "loop_alternatives_per_half_limit": LOOP_ALTERNATIVES_PER_HALF,
        "forward_loop_alternatives_pruned": forward_loop_alternatives_pruned,
        "backward_loop_alternatives_pruned": backward_loop_alternatives_pruned,
        "loop_alternative_policy": "best-Tm-plus-no-loop-plus-bounded-alternatives-before-set-level-interaction-ranking",
        "join_evaluation_capped": core_pair_evaluation_capped,
        "core_pair_evaluation_capped": core_pair_evaluation_capped,
        "core_pair_outer_expansion_capped": core_pair_outer_expansion_capped,
        "backward_partner_sampling_used": backward_partner_sampling_used,
        "outer_candidate_truncation_used": outer_candidate_truncation_used,
        "outer_pair_truncation_used": outer_pair_truncation_used,
        "risk_ranking_capped": risk_ranking_capped,
        "risk_rank_pool_limit": max(RISK_RANK_POOL_LIMIT, how_many * 64),
        "risk_rank_pool_evaluated": len(found),
        "risk_rank_pool_strategy": "60-percent-best-cheap-rank-plus-40-percent-spatial-stratification",
        "half_limit_per_orientation": MOST_HALVES,
        "core_pair_evaluation_limit": MOST_CORE_PAIR_EVALUATIONS,
        "core_pair_evaluations": core_pair_evaluations,
        "core_pairs_outer_expansion_limit": CORE_PAIR_OUTER_EXPANSION_LIMIT,
        "core_pairs_outer_expanded": len(core_pairs),
        "core_pair_outer_expansion_strategy": "60-percent-best-core-rank-plus-40-percent-spatial-stratification",
        "feasible_core_partners_before_local_sampling": partner_count_before_local_sampling,
        "feasible_core_partners_after_local_sampling": partner_count_after_local_sampling,
        "forward_halves_with_feasible_partners": len(partner_jobs),
        "core_pair_budget_allocation": "round-robin-across-feasible-forward-halves",
        "max_backward_partners_per_forward": MAX_BACKWARD_PARTNERS_PER_FORWARD,
        "outer_candidates_per_side": OUTER_CANDIDATES_PER_SIDE,
        "outer_pairs_retained_per_core": OUTER_PAIRS_PER_CORE,
        "complete_outer_pair_combinations_evaluated": complete_set_evaluations,
        "join_evaluation_limit": MOST_JOIN_EVALUATIONS,
        "join_evaluations": complete_set_evaluations,
        "half_enumeration": "64-bin-spatial-interleave",
        "join_strategy": "bisected-middle-gap-core-join-plus-round-robin-global-budget-plus-branch-top-k-outer-expansion",
        "ranking": [
            "core-core and loop-inclusive exact 3-prime extendability risk",
            "loop-primer availability after interaction risk",
            (
                "versioned profile soft geometry and active loop-Tm preferences"
                if geometry_profile.preferred_loop_tm is not None
                else "versioned profile soft geometry preferences; loop-Tm preference inactive on this model"
            ),
            "terminal GC-clamp / excessive-GC-run risk",
            "PrimerExplorer role-Tm agreement",
            "compactness",
        ],
        "orientation_policy": "lexicographically-canonical-target-orientation",
        "orientation_canonicalized": orientation_canonicalized,
        "orientation_note": (
            "Bounded search is performed on a deterministic target/RC orientation for both geometry profiles; "
            "returned coordinates and F/B roles are mapped back to the caller's submitted orientation. "
            "This is a computational-invariance rule, not a LAMP validity criterion."
        ),
        "claim": (
            "best within the complete source-valid search space"
            if not (
                forward_halves_capped
                or backward_halves_capped
                or forward_loop_alternatives_pruned > 0
                or backward_loop_alternatives_pruned > 0
                or core_pair_evaluation_capped
                or core_pair_outer_expansion_capped
                or backward_partner_sampling_used
                or outer_candidate_truncation_used
                or outer_pair_truncation_used
                or risk_ranking_capped
            )
            else "best within the evaluated bounded search set; global optimum not claimed"
        ),
    }
    # Constraint filters are applied to the caller-oriented candidate pool, not
    # to the canonical search orientation. Exact fixed primers and variant
    # coordinates therefore retain the semantics of the sequence the user
    # actually submitted while ranking remains orientation-invariant.
    candidate_pool = list(found)
    if orientation_canonicalized:
        candidate_pool = [_mirror_set(one, len(input_sequence)) for one in candidate_pool]
        counted = _swap_forward_backward_counts(counted)
        search["forward_halves_capped"], search["backward_halves_capped"] = (
            search["backward_halves_capped"],
            search["forward_halves_capped"],
        )
        search["forward_loop_alternatives_pruned"], search["backward_loop_alternatives_pruned"] = (
            search["backward_loop_alternatives_pruned"],
            search["forward_loop_alternatives_pruned"],
        )
    before_constraints = len(candidate_pool)
    if fixed_primers:
        candidate_pool = [
            one
            for one in candidate_pool
            if _matches_fixed_primers(input_sequence, one, fixed_primers, inner_linker=inner_linker)
        ]
    after_fixed = len(candidate_pool)
    if mutation_anchor:
        candidate_pool = [
            one for one in candidate_pool if _matches_mutation_anchor(one, mutation_anchor)
        ]
    after_mutation = len(candidate_pool)
    search["design_constraints"] = {
        "candidate_pool_before": before_constraints,
        "after_fixed_primer_filter": after_fixed,
        "after_mutation_anchor_filter": after_mutation,
        "fixed_primer_roles": sorted(fixed_primers or {}),
        "mutation_anchor": (mutation_anchor or {}).get("anchor"),
        "decision_impact": "candidate-filter" if fixed_primers or mutation_anchor else "none",
    }
    # NEB recommends empirically screening 2–4 complete sets. Keep a separate
    # deterministic diversity-aware cohort even when the caller asks to display
    # only one ranked design; this is evidence/planning, not a success claim.
    cohort_max = min(int(LAMP_SCREENING_COHORT.get("recommended_max", 4)), 4)
    screening = _thin(candidate_pool, cohort_max)
    search["screening_cohort"] = {
        "recommended_min": int(LAMP_SCREENING_COHORT.get("recommended_min", 2)),
        "recommended_max": cohort_max,
        "available": len(screening),
        "set_starts": [one.start for one in screening],
        "source_url": LAMP_SCREENING_COHORT.get("source_url"),
        "claim": "deterministic diverse candidates for empirical screening; no empirical success probability claimed",
    }
    selected = _thin(candidate_pool, how_many)
    answer = (selected, chosen, counted)
    if include_search_meta:
        return (*answer, search)
    return answer


#: How far apart two sets' regions must be before they are different designs.
#:
#: The same rule the pair engine applies to a 3' end, at the scale of a whole
#: set: two sets whose regions all sit within a few bases of each other will
#: behave identically in the tube, and offering both as choices is offering one
#: choice twice.
SETS_APART = 8


def _candidate_near(first: Candidate, second: Candidate) -> bool:
    return abs(first.start - second.start) < SETS_APART and abs(first.end - second.end) < SETS_APART


def _same_design_neighbourhood(one: Set, other: Set) -> bool:
    """Near-duplicate only when every biological region is correspondingly near."""
    required = (
        (one.f3, other.f3),
        (one.forward.outer, other.forward.outer),
        (one.forward.inner, other.forward.inner),
        (one.backward.inner, other.backward.inner),
        (one.backward.outer, other.backward.outer),
        (one.b3, other.b3),
    )
    if not all(_candidate_near(a, b) for a, b in required):
        return False
    for left, right in (
        (one.forward.loop, other.forward.loop),
        (one.backward.loop, other.backward.loop),
    ):
        if (left is None) != (right is None):
            return False
        if left is not None and right is not None and not _candidate_near(left, right):
            return False
    return True


def _thin(found: list[Set], how_many: int) -> list[Set]:
    """Drop only genuinely equivalent whole-set placements."""
    kept: list[Set] = []
    for one in found:
        if any(_same_design_neighbourhood(one, other) for other in kept):
            continue
        kept.append(one)
        if len(kept) == how_many:
            break
    return kept


def _matches_fixed_primers(
    template: str, one: Set, fixed_primers: dict[str, str], *, inner_linker: str = ""
) -> bool:
    """Exact-primer anchoring against ordered oligos for one candidate set.

    Fixed primers constrain candidate membership only. They never rewrite the
    supplied sequence or relax PrimerExplorer geometry/thermodynamic criteria.
    """
    ordered = {
        oligo.name: oligo.sequence.upper()
        for oligo in oligos(template, one, inner_linker=inner_linker)
    }
    return all(ordered.get(role) == sequence.upper() for role, sequence in fixed_primers.items())


def _mutation_anchor_coordinate(one: Set, anchor: str) -> int:
    mapping = {
        "fip-3p-f2": one.forward.outer.end - 1,
        "bip-3p-b2": one.backward.outer.start,
        "fip-5p-f1c": one.forward.inner.end - 1,
        "bip-5p-b1c": one.backward.inner.start,
    }
    if anchor not in mapping:
        raise LoopSetError("Unknown mutation-specific LAMP anchor: " + anchor)
    return mapping[anchor]


def _matches_mutation_anchor(one: Set, variant: dict[str, Any]) -> bool:
    """Whether a candidate places the submitted variant at the requested role end.

    This is positional allele-specific design support only. PCRStudio does not
    add an unsourced secondary mismatch or claim a universal discrimination
    threshold; paired WT/MUT empirical screening remains required.
    """
    return _mutation_anchor_coordinate(one, str(variant["anchor"])) == int(variant["position"])


#: Historical alias retained for downstream diagnostics. The current search
#: budgets core-pair evaluation and bounded outer expansion separately.
MOST_JOIN_EVALUATIONS = MOST_CORE_PAIR_EVALUATIONS * OUTER_PAIRS_PER_CORE


def _outers_before(
    outer: dict[int, list[Candidate]], before: int, gap: tuple[int, int]
) -> list[Candidate]:
    """Every source-valid F3 sitting the requested distance in front of F2."""
    max_length = max((one.length for values in outer.values() for one in values), default=0)
    return [
        one
        for start in range(max(0, before - gap[1] - max_length), before)
        for one in outer.get(start, ())
        if gap[0] <= before - one.end <= gap[1]
    ]


def _outers_after(
    outer: dict[int, list[Candidate]], after: int, gap: tuple[int, int]
) -> list[Candidate]:
    """Every source-valid B3c sitting the requested distance beyond B2c."""
    return [
        one
        for start in range(after, after + gap[1] + 1)
        for one in outer.get(start, ())
        if gap[0] <= one.start - after <= gap[1]
    ]


# ── The ordered oligos (four core + optional LF/LB) ─────────────────────────


@dataclass(frozen=True)
class Oligo:
    """One thing to order, and what it is made of."""

    name: str
    sequence: str
    #: The regions it is built from, in 5'-to-3' order of the oligo itself.
    from_regions: tuple[str, ...]
    #: Whether its 5' half is sequence that is not on the template.
    composite: bool
    note: str
    #: How many bases at the 5' end are tail rather than template. For a
    #: composite this is where the annealing segment begins -- F1c's length in
    #: FIP, B1c's in BIP -- and it is not generally half the oligo, because
    #: nothing makes the tail and the binding segment the same length.
    tail_length: int = 0
    #: Target-derived part of a composite 5' tail (F1c/B1c), excluding any
    #: synthetic junction linker. This is needed for LAMP-specific background
    #: topology validation and must not be conflated with an inert spacer.
    target_tail_sequence: str = ""
    linker_sequence: str = ""

    @property
    def length(self) -> int:
        return len(self.sequence)


def oligos(template: str, one: Set, *, inner_linker: str = "") -> list[Oligo]:
    """The four core oligos plus any optional LF/LB, built from the plus strand.

    Two of them are composites, and the halves are not interchangeable. FIP
    reads 5'-F1c-F2-3': the F2 half is what anneals to the template, and the
    F1c half is a tail that primes later against a copy of F1 on a strand that
    does not exist yet. Building it the other way round gives an oligo of the
    right length and composition that primes nothing.
    """
    f3 = template[one.f3.start : one.f3.end]
    f2 = template[one.forward.outer.start : one.forward.outer.end]
    f1 = template[one.forward.inner.start : one.forward.inner.end]
    b1c = template[one.backward.inner.start : one.backward.inner.end]
    b2c = template[one.backward.outer.start : one.backward.outer.end]
    b3c = template[one.b3.start : one.b3.end]
    f1c = reverse_complement(f1)
    b2 = reverse_complement(b2c)
    linker = str(inner_linker or "").upper()
    if any(base not in "ACGT" for base in linker):
        raise LoopSetError("The LAMP inner-primer linker must contain DNA bases only.")

    made = [
        Oligo(
            name="F3",
            sequence=f3,
            from_regions=("F3",),
            composite=False,
            note="Displaces the strand that FIP started, releasing the loop.",
        ),
        Oligo(
            name="FIP",
            sequence=f1c + linker + f2,
            from_regions=(("F1c", "linker", "F2") if linker else ("F1c", "F2")),
            composite=True,
            # F1c is the whole 5' tail; the annealing segment is exactly F2.
            tail_length=len(f1c) + len(linker),
            target_tail_sequence=f1c,
            linker_sequence=linker,
            note=(
                "Its F2 half anneals to the template; its F1c half is a 5' tail that "
                "is not on the template at all and becomes a primer later, folding "
                "back against the F1 copy on the strand this one makes."
            ),
        ),
        Oligo(
            name="BIP",
            sequence=b1c + linker + b2,
            from_regions=(("B1c", "linker", "B2") if linker else ("B1c", "B2")),
            composite=True,
            # B1c is the tail; the annealing segment is the B2 complement.
            tail_length=len(b1c) + len(linker),
            target_tail_sequence=b1c,
            linker_sequence=linker,
            note=(
                "The same shape as FIP from the other end: the B2 half anneals, and "
                "the B1c half is the tail that closes the loop later."
            ),
        ),
        Oligo(
            name="B3",
            sequence=reverse_complement(b3c),
            from_regions=("B3",),
            composite=False,
            note="Displaces the strand that BIP started.",
        ),
    ]

    if one.forward.loop:
        made.append(
            Oligo(
                name="LF",
                sequence=reverse_complement(
                    template[one.forward.loop.start : one.forward.loop.end]
                ),
                from_regions=("LF",),
                composite=False,
                note=(
                    "Optional loop primer: it primes inside the forward loop and can "
                    "accelerate LAMP, but the magnitude of that gain is assay- and "
                    "chemistry-dependent. It sits strictly between F2 and F1 — "
                    "overlapping either would make it a perfect dimer with FIP."
                ),
            )
        )
    if one.backward.loop:
        made.append(
            Oligo(
                name="LB",
                sequence=template[one.backward.loop.start : one.backward.loop.end],
                from_regions=("LB",),
                composite=False,
                note=(
                    "The backward loop's primer. It carries the plus-strand sequence "
                    "rather than its complement, because the loop BIP makes is the "
                    "other way round from the one FIP makes."
                ),
            )
        )
    return made


def _lamp_intended_linear_products(template: str, one: Set) -> tuple[list[int], list[str]]:
    """Linear target-locus products that are expected from a valid LAMP set.

    The shared generic specificity engine pairs every extendable forward-facing
    site with every opposing reverse-facing site. On the intended template that
    creates several legitimate linear pairings (not only F3-B3). Excusing only
    the full outer span therefore mislabels normal target-locus LAMP geometry as
    generic "off-target products". Remove exactly one copy of every expected
    target-locus pairing by sequence; duplicate/paralogous copies remain visible.
    """
    forward = [one.f3, one.forward.outer]
    if one.backward.loop is not None:  # LB uses the plus-strand sequence.
        forward.append(one.backward.loop)

    reverse = []
    if one.forward.loop is not None:  # LF is reverse-complementary to the template.
        reverse.append(one.forward.loop)
    reverse.extend([one.backward.outer, one.b3])

    products: list[str] = []
    for left in forward:
        for right in reverse:
            if left.end <= right.start:
                products.append(template[left.start : right.end])
    return [len(product) for product in products], products


def _lamp_generic_intended_linear_products(
    template: str, one: Set, *, template_only: bool
) -> tuple[list[int], list[str]]:
    """Intended-product exemptions for the shared linear proxy.

    LAMP's public `background` contract is an exclusion scope: every compatible
    site/product in a supplied panel is unwanted evidence and nothing in that
    panel is silently excused as the intended target. Only the implicit
    template-only self-scan receives target-locus exemptions.
    """
    if not template_only:
        return [], []
    return _lamp_intended_linear_products(template, one)


# ── Intended-target inclusivity across a homologous panel ───────────────────

#: Reserved row name used when PCRStudio adds the design template to an
#: optional target-diversity panel before MAFFT alignment.
INCLUSIVITY_REFERENCE_ID = "__PCRSTUDIO_LAMP_REFERENCE__"
ALIGNMENT_GAPS = frozenset("-.~")
INCLUSIVITY_WORST_RECORDS = 12


@dataclass(frozen=True)
class InclusionRegion:
    """One reference interval whose conservation matters to a LAMP set."""

    name: str
    start: int
    end: int
    group: str
    critical_side: str
    rationale: str


def _inclusion_regions(one: Set) -> list[InclusionRegion]:
    """The actual target intervals used by a set, with role-aware end semantics.

    The hierarchy is deliberately qualitative rather than a fabricated scalar
    score: the four inner regions are considered before optional loop regions,
    and the two displacement/outer regions last.  Within a region, terminal
    disruption is reported separately from total substitutions/indels.  This
    matches the direction of the LAMP mismatch literature without claiming a
    universal kinetic penalty for one particular mismatch.
    """
    regions = [
        InclusionRegion("F3", one.f3.start, one.f3.end, "outer", "right", "F3 3' extension edge"),
        InclusionRegion(
            "F2",
            one.forward.outer.start,
            one.forward.outer.end,
            "inner",
            "right",
            "FIP F2 3' annealing edge",
        ),
        InclusionRegion(
            "F1/F1c",
            one.forward.inner.start,
            one.forward.inner.end,
            "inner",
            "right",
            "FIP 5' F1c terminal maps to the F1 right edge",
        ),
        InclusionRegion(
            "B1c",
            one.backward.inner.start,
            one.backward.inner.end,
            "inner",
            "left",
            "BIP 5' B1c terminal maps to the B1c left edge",
        ),
        InclusionRegion(
            "B2c/B2",
            one.backward.outer.start,
            one.backward.outer.end,
            "inner",
            "left",
            "BIP B2 3' annealing edge maps to the B2c left edge",
        ),
        InclusionRegion(
            "B3c/B3",
            one.b3.start,
            one.b3.end,
            "outer",
            "left",
            "B3 3' extension edge maps to the B3c left edge",
        ),
    ]
    if one.forward.loop:
        regions.append(
            InclusionRegion(
                "LF",
                one.forward.loop.start,
                one.forward.loop.end,
                "loop",
                "left",
                "LF 3' edge maps to the left edge of its plus-strand interval",
            )
        )
    if one.backward.loop:
        regions.append(
            InclusionRegion(
                "LB",
                one.backward.loop.start,
                one.backward.loop.end,
                "loop",
                "right",
                "LB 3' edge maps to the right edge of its plus-strand interval",
            )
        )
    return regions


def _reference_columns(reference_aligned: str, expected_bases: int) -> list[int]:
    """Map every ungapped reference coordinate to one MSA column."""
    columns = [index for index, base in enumerate(reference_aligned) if base not in ALIGNMENT_GAPS]
    if len(columns) != expected_bases:
        raise LoopSetError(
            "The target-inclusivity alignment changed the reference length; "
            f"expected {expected_bases} bases and recovered {len(columns)}."
        )
    return columns


def _compatible_panel_base(observed: str, expected: str) -> tuple[bool, bool]:
    """Whether an aligned panel symbol can encode the reference base.

    Returns ``(compatible, ambiguous)``.  Ambiguity stays visible rather than
    being counted as a known match or silently expanded into one sequence.
    """
    from .specificity import IUPAC_BASES, UNAMBIGUOUS_BASES

    observed = observed.upper().replace("U", "T")
    expected = expected.upper().replace("U", "T")
    choices = IUPAC_BASES.get(observed)
    if choices is None:
        return False, False
    return expected in choices, observed not in UNAMBIGUOUS_BASES


def _aligned_region_events(
    reference_aligned: str,
    panel_aligned: str,
    columns: list[int],
    region: InclusionRegion,
) -> dict[str, Any]:
    """Substitution/indel and terminal evidence for one region in one MSA row."""
    if region.start < 0 or region.end > len(columns) or region.start >= region.end:
        raise LoopSetError(
            f"Invalid inclusivity interval {region.name}: {region.start}:{region.end}."
        )

    first_col = columns[region.start]
    last_col = columns[region.end - 1]
    length = region.end - region.start
    substitutions = deletions = insertions = ambiguous = 0
    terminal_3_events = 0
    critical_terminal_event = False
    seen_reference = 0
    event_positions: list[int] = []

    for column in range(first_col, last_col + 1):
        reference_base = reference_aligned[column].upper()
        observed = panel_aligned[column].upper()
        if reference_base in ALIGNMENT_GAPS:
            if observed not in ALIGNMENT_GAPS:
                insertions += 1
                near_terminal = (
                    seen_reference < 3
                    if region.critical_side == "left"
                    else (length - seen_reference) <= 3
                )
                if near_terminal:
                    terminal_3_events += 1
            continue

        relative = seen_reference
        seen_reference += 1
        event = False
        if observed in ALIGNMENT_GAPS:
            deletions += 1
            event = True
        else:
            compatible, is_ambiguous = _compatible_panel_base(observed, reference_base)
            if is_ambiguous:
                ambiguous += 1
            if not compatible:
                substitutions += 1
                event = True

        if event:
            event_positions.append(relative)
            near_terminal = (
                relative < 3 if region.critical_side == "left" else relative >= length - 3
            )
            if near_terminal:
                terminal_3_events += 1
            if relative == (0 if region.critical_side == "left" else length - 1):
                critical_terminal_event = True

    total_events = substitutions + deletions + insertions
    return {
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "ambiguous_bases": ambiguous,
        "total_events": total_events,
        "terminal_3_events": terminal_3_events,
        "critical_terminal_event": critical_terminal_event,
        "exact": total_events == 0 and ambiguous == 0,
        "event_positions_zero_based_within_region": event_positions,
        "critical_side": region.critical_side,
        "rationale": region.rationale,
    }


def _inclusivity_rank(audit: dict[str, Any] | None) -> tuple[int, int, int, int, int, int]:
    """Lexicographic target-panel rank; lower is better, no arbitrary weights."""
    if not audit or not audit.get("checked"):
        return (0, 0, 0, 0, 0, 0)
    totals = audit["event_totals"]
    return (
        int(totals["inner_terminal_3_events"]),
        int(totals["inner_events"]),
        int(totals["loop_terminal_3_events"]),
        int(totals["loop_events"]),
        int(totals["outer_terminal_3_events"]),
        int(totals["outer_events"]),
    )


def _target_inclusivity_audit(template: str, one: Set, aligned: Any) -> dict[str, Any]:
    """Audit one candidate set against every intended-target row in one MSA.

    This is an inclusivity *ranking* layer, not an empirical sensitivity model.
    It handles substitutions and alignment indels at the actual selected LAMP
    regions and separates terminal events from other changes.  It does not
    assign a universal kinetic cost to a mismatch or claim that an exact row
    guarantees amplification.
    """
    by_id = {record.id: record for record in aligned.records}
    reference = by_id.get(INCLUSIVITY_REFERENCE_ID)
    if reference is None:
        raise LoopSetError("The target-inclusivity alignment lost PCRStudio's reference row.")
    panel = [record for record in aligned.records if record.id != INCLUSIVITY_REFERENCE_ID]
    columns = _reference_columns(reference.sequence, len(template))
    regions = _inclusion_regions(one)
    core_names = {"F3", "F2", "F1/F1c", "B1c", "B2c/B2", "B3c/B3"}

    totals = {
        "inner_terminal_3_events": 0,
        "inner_events": 0,
        "loop_terminal_3_events": 0,
        "loop_events": 0,
        "outer_terminal_3_events": 0,
        "outer_events": 0,
    }
    record_summaries: list[dict[str, Any]] = []
    exact_core_records = 0
    inner_terminal_clean_records = 0
    all_selected_regions_exact_records = 0

    for record in panel:
        per_region: dict[str, dict[str, Any]] = {}
        group_events = {"inner": 0, "loop": 0, "outer": 0}
        group_terminal = {"inner": 0, "loop": 0, "outer": 0}
        for region in regions:
            evidence = _aligned_region_events(reference.sequence, record.sequence, columns, region)
            per_region[region.name] = evidence
            group_events[region.group] += int(evidence["total_events"])
            group_terminal[region.group] += int(evidence["terminal_3_events"])
            totals[f"{region.group}_events"] += int(evidence["total_events"])
            totals[f"{region.group}_terminal_3_events"] += int(evidence["terminal_3_events"])

        core_exact = all(per_region[name]["exact"] for name in core_names)
        selected_exact = all(evidence["exact"] for evidence in per_region.values())
        if core_exact:
            exact_core_records += 1
        if group_terminal["inner"] == 0:
            inner_terminal_clean_records += 1
        if selected_exact:
            all_selected_regions_exact_records += 1
        record_summaries.append(
            {
                "id": record.id,
                "core_exact": core_exact,
                "all_selected_regions_exact": selected_exact,
                "inner_terminal_3_events": group_terminal["inner"],
                "inner_events": group_events["inner"],
                "loop_terminal_3_events": group_terminal["loop"],
                "loop_events": group_events["loop"],
                "outer_terminal_3_events": group_terminal["outer"],
                "outer_events": group_events["outer"],
                "regions_with_events": {
                    name: evidence
                    for name, evidence in per_region.items()
                    if evidence["total_events"] or evidence["ambiguous_bases"]
                },
            }
        )

    # Worst rows are retained for inspection without multiplying a 500-row MSA
    # by every candidate set in the JSON result. Aggregate counts still use the
    # entire panel.
    record_summaries.sort(
        key=lambda item: (
            item["inner_terminal_3_events"],
            item["inner_events"],
            item["loop_terminal_3_events"],
            item["loop_events"],
            item["outer_events"],
        ),
        reverse=True,
    )
    checked = len(panel)
    audit = {
        "checked": True,
        "records_checked": checked,
        "exact_core_records": exact_core_records,
        "exact_core_fraction": (exact_core_records / checked if checked else None),
        "inner_terminal_clean_records": inner_terminal_clean_records,
        "inner_terminal_clean_fraction": (
            inner_terminal_clean_records / checked if checked else None
        ),
        "all_selected_regions_exact_records": all_selected_regions_exact_records,
        "all_selected_regions_exact_fraction": (
            all_selected_regions_exact_records / checked if checked else None
        ),
        "event_totals": totals,
        "worst_records": record_summaries[:INCLUSIVITY_WORST_RECORDS],
        "records_reported": min(len(record_summaries), INCLUSIVITY_WORST_RECORDS),
        "record_reporting_capped": len(record_summaries) > INCLUSIVITY_WORST_RECORDS,
        "classification": "position-aware-msa-inclusivity-soft-ranking",
        "rank_fields": [
            "inner_terminal_3_events",
            "inner_events",
            "loop_terminal_3_events",
            "loop_events",
            "outer_terminal_3_events",
            "outer_events",
        ],
        "claim": (
            "All intended-target rows in the supplied homologous panel were compared at the "
            "actual selected LAMP regions after pinned-MAFFT alignment. Inner-region terminal "
            "events rank first, then other inner changes, loop changes and outer changes. This "
            "is an evidence-informed conservation rank, not an empirical sensitivity guarantee."
        ),
        "limitations": [
            "The panel is user-supplied and cannot establish population-wide coverage by itself.",
            "Alignment uncertainty is not converted into a probability of amplification.",
            "Mismatch and indel positions are reported/ranked without a universal kinetic penalty.",
            "Experimental inclusivity across the intended biological diversity remains required.",
        ],
    }
    audit["rank_tuple"] = list(_inclusivity_rank(audit))
    return audit


def _prepare_target_inclusivity(template: str, raw_panel: Any) -> tuple[Any | None, dict[str, Any]]:
    """Align an optional homologous target panel with the design template.

    Automatic inclusivity uses the same pinned MAFFT 7.526 authority already
    present in PCRStudio. It fails closed when that artifact is unavailable or
    unverifiable; silently falling back to another aligner would change the
    scientific input on which conservation ranking depends.
    """
    if raw_panel in (None, ""):
        return None, {
            "checked": False,
            "supplied": False,
            "records": 0,
            "classification": "not-supplied-no-population-coverage-claim",
            "note": "No intended-target diversity panel was supplied; representative-template design is not population inclusivity evidence.",
        }
    if not isinstance(raw_panel, str):
        raise LoopSetError(
            "inclusivity must be FASTA text containing homologous intended-target sequences."
        )

    from .align import AlignError, align
    from .fetch import GAP_CHARACTERS, parse_fasta

    records = parse_fasta(raw_panel)
    if not records:
        raise LoopSetError("inclusivity was supplied but contains no non-empty FASTA sequence.")
    if any(record.id == INCLUSIVITY_REFERENCE_ID for record in records):
        raise LoopSetError(
            f"inclusivity record id {INCLUSIVITY_REFERENCE_ID!r} is reserved by PCRStudio."
        )
    for record in records:
        gaps = sorted(set(record.sequence) & set(GAP_CHARACTERS))
        if gaps:
            raise LoopSetError(
                "LAMP target inclusivity currently accepts unaligned homologous FASTA and aligns it "
                "with the pinned MAFFT authority; remove pre-existing alignment gap characters from "
                f"record {record.id!r}."
            )

    panel_fasta = "\n".join(f">{record.id}\n{record.sequence}" for record in records)
    combined = f">{INCLUSIVITY_REFERENCE_ID}\n{template}\n{panel_fasta}\n"
    try:
        aligned = align(combined, engine_id="loop-set", module_id="lamp")
    except AlignError as error:
        raise LoopSetError(f"Target inclusivity alignment failed closed: {error}") from error

    alignment_fasta = "\n".join(f">{record.id}\n{record.sequence}" for record in aligned.records)
    metadata = {
        "checked": True,
        "supplied": True,
        "records": len(records),
        "input_bases": sum(record.length for record in records),
        "input_sha256": hashlib.sha256(raw_panel.encode("utf-8")).hexdigest(),
        "alignment_sha256": hashlib.sha256(alignment_fasta.encode("utf-8")).hexdigest(),
        "alignment": {
            "tool": aligned.tool,
            "tool_version": aligned.tool_version,
            "tool_role": aligned.tool_role,
            "depth_including_reference": aligned.depth,
            "width": aligned.width,
            "warnings": list(aligned.warnings),
        },
        "classification": "user-supplied-homologous-target-panel-pinned-mafft",
        "note": (
            "This panel asks whether the selected LAMP regions are conserved across intended "
            "targets. It is distinct from the exclusion background, which asks what must stay silent."
        ),
    }
    return aligned, metadata


# ── Reporting ──────────────────────────────────────────────────────────────

#: Thermodynamic interaction-model reference used for LAMP oligo diagnostics.
#: It is not a bench hold unless a named protocol (for example E1700) supplies
#: the same temperature as protocol authority.
HOLD = 65.0

#: Diagnostic reference margin below the single LAMP hold temperature.
#:
#: It is retained as an inspectable contract for callers that need to compare
#: a pairwise structure with the reaction reference. The current Gen-1 result
#: remains diagnostic-only and does not turn this number into a pass/fail gate.
DUPLEX_BELOW_HOLD = 10.0


def duplex_ceiling() -> float:
    """Return the diagnostic cross-dimer reference temperature."""
    return round(HOLD - DUPLEX_BELOW_HOLD, 1)


# A LAMP temperature and six-primer geometry do not identify a commercial
# formulation. Keep named protocol overlays explicit so concentrations,
# carry-over chemistry, readout constraints and incubation are never mixed
# across Bst-family products/vendors.  These records are bench provenance and
# ordered-oligo diagnostic context; selecting one does not change the genomic
# LAMP candidate search/ranking contract.
def _lamp_protocol(protocol_id: str) -> dict[str, Any] | None:
    """Return a defensive copy of one reviewed protocol overlay."""
    if protocol_id == "not-selected":
        return None
    source = LAMP_PROTOCOL_REGISTRY[protocol_id]
    # JSON round-tripping is intentional here: these are JSON-shaped release
    # records and callers must never mutate the module-level reviewed source.
    import json

    copied = json.loads(json.dumps(source))
    copied["_protocol_id"] = protocol_id
    return copied


def _readout_compatibility(protocol: dict[str, Any], readout: str) -> dict[str, Any]:
    """Return source-scoped compatibility without turning absence of evidence into impossibility."""
    recommended = list(protocol.get("recommended_readouts") or [])
    forbidden = dict(protocol.get("forbidden_readouts") or {})
    if readout in forbidden:
        raise LoopSetError(
            f"The selected LAMP readout `{readout}` conflicts with the reviewed named protocol: {forbidden[readout]} "
            "Choose a vendor-reviewed readout or a different named protocol instead of overriding an explicit product limitation."
        )
    if readout == "not-specified":
        status = "not-assessed"
        note = "No LAMP readout was selected, so protocol/readout compatibility was not inferred."
    elif readout in recommended:
        status = "reviewed-compatible"
        note = "The selected readout is within the vendor-reviewed/readout scope recorded for this protocol."
    else:
        status = "review-required"
        note = (
            "The selected readout is not in this protocol record's reviewed starting set. "
            "PCRStudio does not call it impossible without source evidence, but it must be validated as a separate assay/SOP branch."
        )
    return {
        "selected": readout,
        "status": status,
        "reviewed_readouts": recommended,
        "forbidden_readouts": sorted(forbidden),
        "note": note,
    }


def _rt_lamp_block_for_protocol(protocol_id: str, protocol: dict[str, Any]) -> dict[str, Any]:
    """Return only RT authority that the selected named LAMP protocol actually owns."""
    if not protocol.get("supports_rna"):
        raise LoopSetError(
            f"The selected LAMP protocol {protocol_id} is DNA-only and cannot satisfy from_rna=true. "
            "Choose a reviewed RT-LAMP-capable protocol or leave lamp_protocol unselected so the "
            "generic RT handoff remains explicitly unresolved."
        )

    hold_temperature = protocol.get("hold_temperature_c")
    hold_time = protocol.get("hold_time_min")
    if hold_temperature is None or hold_time is None:
        # Keep the same scientific-strict boundary as the generic helper: a
        # vendor range is not silently converted into one bench hold.
        return {
            "one_step": True,
            "hold": None,
            "before": None,
            "authority_status": f"{protocol_id}-rt-lamp-range-only",
            "note": (
                f"{protocol['selection']} is RT-LAMP capable, but this reviewed record does not "
                "supply one exact temperature/time pair. Use the protocol range/current package "
                "insert rather than inventing a single hold."
            ),
        }

    return {
        "one_step": True,
        "hold": {"celsius": hold_temperature, "seconds": int(float(hold_time) * 60)},
        "before": None,
        "authority_status": protocol.get("rt_authority_status") or f"{protocol_id}-rt-lamp",
        "reverse_transcriptase": protocol.get("reverse_transcriptase"),
        "note": (
            f"Named protocol authority: {protocol['selection']}. Reverse transcription and LAMP "
            "occur in the same reviewed isothermal workflow; no separate generic RT hold is inferred."
        ),
    }


# ── The six against each other ─────────────────────────────────────────────

#: Pairwise ordered-oligo interaction evidence is a soft ranker, never a hard gate.
#:
#: PrimerExplorer/NEB guidance asks designers to avoid primer dimers, but the
#: literature does not supply a universal Tm or ΔG line that converts one
#: predicted heterodimer into LAMP assay invalidity. The full ordered-oligo
#: matrix therefore participates only in bounded stage-2 ranking. It can move a
#: source-valid set below a lower-risk neighbour; it never accepts/rejects a set
#: by threshold and never masquerades as empirical nonspecific-amplification
#: prediction.


def interactions(
    oligos_by_name: dict[str, str],
    *,
    role_concentrations_uM: dict[str, float] | None = None,
    **conditions: float,
) -> dict[str, Any]:
    """Every oligo measured against every other one, without a fabricated gate.

    Primer3's heterodimer call exposes one oligo-concentration parameter rather
    than two asymmetric role concentrations.  When a named LAMP protocol uses
    different FIP/BIP, F3/B3 and loop concentrations, those real concentrations
    are therefore reported next to the common screening context instead of being
    silently collapsed into a claim of kit-exact pair thermodynamics.
    """
    names = sorted(oligos_by_name)
    measured: list[dict[str, Any]] = []
    try:
        for index, first in enumerate(names):
            for second in names[index + 1 :]:
                structure = pair_dimer(
                    oligos_by_name[first],
                    oligos_by_name[second],
                    **conditions,
                    temp_c=HOLD,
                )
                measured.append({"a": first, "b": second, "dg": structure.dg, "tm": structure.tm})
    except OSError as error:
        return {
            "checked": 0,
            "found": 0,
            "serious": [],
            "model_temperature_c": HOLD,
            "classification": "not-computed",
            "role_concentrations_uM": role_concentrations_uM,
            "asymmetric_concentration_modelled_exactly": False,
            "max_predicted_tm_c": None,
            "most_favourable_dg_kcal_mol": None,
            "all_pairs": [],
            "worst": [],
            "note": (
                "The ordered-oligo interaction diagnostic could not run. No clean/unsafe "
                f"claim is made: {error}"
            ),
        }

    measured.sort(key=lambda entry: entry["dg"])
    # Keep the historical `serious` field for schema compatibility, but name
    # its semantics explicitly: this is a reference exceedance, not a validity
    # verdict.
    serious = [entry for entry in measured if entry["tm"] >= duplex_ceiling()]
    return {
        "checked": len(measured),
        "found": len(serious),
        "serious": serious,
        "reference_exceedances": serious,
        "reference_tm_c": duplex_ceiling(),
        "model_temperature_c": HOLD,
        "classification": "diagnostic-only-no-universal-pass-fail-threshold",
        "role_concentrations_uM": role_concentrations_uM,
        "common_primer3_dna_conc_nM": conditions.get("dna_conc"),
        "asymmetric_concentration_modelled_exactly": False,
        "max_predicted_tm_c": max((entry["tm"] for entry in measured), default=None),
        "most_favourable_dg_kcal_mol": min((entry["dg"] for entry in measured), default=None),
        "all_pairs": measured,
        "worst": measured[:10],
        "note": (
            "Pairwise heterodimers are reported at the declared 65 °C thermodynamic model. "
            "The historical 55 °C comparison is retained only as a reference-exceedance view. "
            "PCRStudio does not convert this predicted Tm/ΔG into a universal LAMP pass/fail "
            "gate; exact 3'-extendability contributes separately to risk ranking, and empirical "
            "assay validation remains required."
        ),
    }


def set_to_dict(
    template: str,
    one: Set,
    windows: Windows,
    *,
    role_concentrations_uM: dict[str, float] | None = None,
    geometry_profile: GeometryProfile = PRIMEREXPLORER_V5_GEOMETRY,
    inner_linker: str = "",
    **conditions: float,
) -> dict[str, Any]:
    """One set as plain data, with each oligo's parts kept apart."""
    made = oligos(template, one, inner_linker=inner_linker)
    sequence_risk = three_prime_interaction_risk({oligo.name: oligo.sequence for oligo in made})

    return {
        "at": one.start,
        "ends": one.end,
        "size": one.size,
        "f2_b2_span": one.f2_b2_span,
        "middle_gap": one.middle_gap,
        "loop_primers": one.loops(),
        "spread": one.spread(),
        "thermal_rank": {
            "corresponding_region_tm_difference": one.thermal_rank(windows)[0],
            "inner_minus_outer_5c_error": one.thermal_rank(windows)[1],
            "published_window_centre_error": one.thermal_rank(windows)[2],
        },
        "evidence_rank": {
            "preferred_f2_b2_distance_penalty": one.evidence_rank(geometry_profile)[0],
            "preferred_outer_gap_penalty": one.evidence_rank(geometry_profile)[1],
            "preferred_loop_tm_penalty": one.evidence_rank(geometry_profile)[2],
            "preferred_f2_b2_span": (
                list(geometry_profile.preferred_f2_b2_span)
                if geometry_profile.preferred_f2_b2_span is not None
                else None
            ),
            "preferred_outer_gap": (
                list(geometry_profile.preferred_outer_gap)
                if geometry_profile.preferred_outer_gap is not None
                else None
            ),
            "preferred_loop_tm": (
                list(geometry_profile.preferred_loop_tm)
                if geometry_profile.preferred_loop_tm is not None
                else None
            ),
            "geometry_profile": geometry_profile.id,
            "classification": "soft-ranking-only",
        },
        "sequence_interaction_risk": sequence_risk,
        "terminal_gc": {
            oligo.name: {
                "gc_in_last_6": _three_prime_gc_count(oligo.sequence),
                "has_gc_clamp_in_last_6": _three_prime_gc_count(oligo.sequence) > 0,
                "three_prime_gc_run": _three_prime_gc_run(oligo.sequence),
                "review": _three_prime_gc_run(oligo.sequence) > 3,
                "classification": "soft-evidence-feature",
            }
            for oligo in made
        },
        "regions": [
            {"name": "F3", "at": one.f3.start, "length": one.f3.length},
            {
                "name": "F2",
                "at": one.forward.outer.start,
                "length": one.forward.outer.length,
            },
            *(
                [
                    {
                        "name": "LF",
                        "at": one.forward.loop.start,
                        "length": one.forward.loop.length,
                    }
                ]
                if one.forward.loop
                else []
            ),
            {
                "name": "F1",
                "at": one.forward.inner.start,
                "length": one.forward.inner.length,
            },
            {
                "name": "B1c",
                "at": one.backward.inner.start,
                "length": one.backward.inner.length,
            },
            *(
                [
                    {
                        "name": "LB",
                        "at": one.backward.loop.start,
                        "length": one.backward.loop.length,
                    }
                ]
                if one.backward.loop
                else []
            ),
            {
                "name": "B2c",
                "at": one.backward.outer.start,
                "length": one.backward.outer.length,
            },
            {"name": "B3c", "at": one.b3.start, "length": one.b3.length},
        ],
        "oligos": [
            {
                "name": oligo.name,
                "sequence": oligo.sequence,
                "length": oligo.length,
                "built_from": list(oligo.from_regions),
                "composite": oligo.composite,
                "target_tail_sequence": oligo.target_tail_sequence or None,
                "linker_sequence": oligo.linker_sequence or None,
                **_measured(oligo, role_concentrations_uM=role_concentrations_uM, **conditions),
                "note": oligo.note,
            }
            for oligo in made
        ],
        "note": (
            f"{one.f2_b2_span} bases across the PrimerExplorer F2-B2 amplified region "
            f"({one.size} bases across the full F3-B3 design envelope), with {one.loops()} "
            "of the two optional loop primers. The whole-set Tm spread is diagnostic only: "
            "F1c/B1c are intentionally designed about 5 °C above F2/B2 rather than forced "
            "to share one Tm."
        ),
    }


def _measured(
    oligo: Oligo,
    *,
    role_concentrations_uM: dict[str, float] | None = None,
    **conditions: float,
) -> dict[str, Any]:
    """What this oligo does, with the composites read in their two halves.

    A composite's whole-molecule melting temperature is not a number anybody
    can set anything to: FIP and BIP run near 80 °C while the reaction is held
    near 65, because half of each is a tail that is not annealing to anything
    yet. What matters for the hold is the half that binds the template, so that
    is measured separately and labelled.
    """
    measured_conditions = dict(conditions)
    if role_concentrations_uM and oligo.name in role_concentrations_uM:
        measured_conditions["dna_conc"] = role_concentrations_uM[oligo.name] * 1000.0
    whole = analyse(oligo.sequence, **measured_conditions)
    entry: dict[str, Any] = {
        "diagnostic_dna_conc_nM": measured_conditions.get("dna_conc"),
        "tm": whole.tm,
        "gc_percent": whole.gc_percent,
        "hairpin_tm": whole.hairpin.tm if whole.hairpin.found else None,
        "self_dimer_tm": whole.self_dimer.tm if whole.self_dimer.found else None,
    }
    if not oligo.composite:
        return entry

    # The 3' segment is the part that anneals first; the 5' segment is the
    # tail. The seam sits where the parts were joined, not at the midpoint:
    # FIP is F1c then F2 and nothing says those are the same length.
    anneals = oligo.sequence[oligo.tail_length :]
    measured = analyse(anneals, **measured_conditions)
    entry["anneals"] = {
        "sequence": anneals,
        "tm": measured.tm,
        "note": (
            f"The segment that binds the template melts at {measured.tm} °C. The whole "
            f"oligo's {whole.tm} °C describes a molecule that does not exist until the "
            "reaction has run — the rest of it is a tail with nothing to bind yet."
        ),
    }
    return entry


# ── LAMP-native finite-background topology review ──────────────────────────
#
# Generic PCR-style specificity asks whether individual oligos have extra sites
# and whether opposing sites can form a linear product. LAMP needs a stricter
# set-level question: can all six core target-derived regions occur on one
# background locus in the orientation/order/spacing needed for LAMP? GLAPD uses
# this topology concept after primer-region alignment. PCRStudio implements an
# independent bounded version for supplied finite backgrounds and delegates
# larger scopes to indexed external validation.
LAMP_TOPOLOGY_MAX_MISMATCHES = 2
LAMP_TOPOLOGY_DIRECT_MAX_BASES = 5_000_000
# The generic per-set site/product proxy is also O(candidates × background).
# Keep its direct-background scope aligned with the LAMP-native topology scope
# so a genome-scale background is not silently rescanned dozens of times before
# the indexed validator is invoked by the orchestrator.
LAMP_GENERIC_DIRECT_MAX_BASES = LAMP_TOPOLOGY_DIRECT_MAX_BASES
# A pasted exclusion panel is literal user input. It must be evaluated against
# its own bases; a separately configured indexed database is never a silent
# substitute for that input. Keep the raw-input ceiling at the strictest direct
# LAMP evidence limit.
LAMP_RAW_BACKGROUND_DIRECT_MAX_BASES = min(
    LAMP_GENERIC_DIRECT_MAX_BASES, LAMP_TOPOLOGY_DIRECT_MAX_BASES
)
LAMP_TOPOLOGY_SITE_LIMIT_PER_ROLE = 5_000
LAMP_TOPOLOGY_COMBINATION_LIMIT = 100_000
LAMP_TOPOLOGY_REPORT_LIMIT = 20


def _pasted_background_base_count(value: Any) -> int:
    """Cheap LAMP raw-background size preflight before FASTA allocation.

    Header text is not sequence. For plain-sequence input, alphabetic characters
    are an upper bound until the shared parser validates the DNA/IUPAC alphabet.
    This check exists only to refuse an obviously oversized literal scope early;
    the canonical parser still performs exact syntax/alphabet validation below.
    """
    if not isinstance(value, str):
        return 0
    if value.lstrip().startswith(">"):
        return sum(
            character.isalpha()
            for line in value.splitlines()
            if not line.lstrip().startswith(">")
            for character in line
        )
    return sum(character.isalpha() for character in value)


@dataclass(frozen=True)
class LampRegionQuery:
    role: str
    sequence: str
    expected_orientation: str
    critical_end: str


@dataclass(frozen=True)
class LampPlacedSite:
    role: str
    contig: str
    start: int
    end: int
    orientation: str
    mismatches: int
    mismatch_upper_bound: int
    ambiguous_bases: int
    critical_terminal_exact: bool


def _lamp_core_region_queries(template: str, one: Set) -> tuple[LampRegionQuery, ...]:
    f3 = template[one.f3.start : one.f3.end]
    f2 = template[one.forward.outer.start : one.forward.outer.end]
    f1 = template[one.forward.inner.start : one.forward.inner.end]
    b1c = template[one.backward.inner.start : one.backward.inner.end]
    b2c = template[one.backward.outer.start : one.backward.outer.end]
    b3c = template[one.b3.start : one.b3.end]
    return (
        LampRegionQuery("F3", f3, "forward", "3"),
        LampRegionQuery("F2", f2, "forward", "3"),
        LampRegionQuery("F1c", reverse_complement(f1), "reverse", "5"),
        LampRegionQuery("B1c", b1c, "forward", "5"),
        LampRegionQuery("B2", reverse_complement(b2c), "reverse", "3"),
        LampRegionQuery("B3", reverse_complement(b3c), "reverse", "3"),
    )


def _opposite_orientation(orientation: str) -> str:
    return "reverse" if orientation == "forward" else "forward"


def _lamp_sequence_sites(
    query: LampRegionQuery,
    contigs: list[Any],
    *,
    max_mismatches: int = LAMP_TOPOLOGY_MAX_MISMATCHES,
) -> tuple[list[LampPlacedSite], bool]:
    """Mismatch-complete ungapped sites on both genomic orientations.

    A target/background locus may occur as either the reference orientation or
    its reverse complement.  Discovery therefore searches the ordered primer
    region sequence and its reverse complement independently.  Overall locus
    orientation is resolved later when the six roles are assembled.

    This deliberately reuses Specificity-v5's k+1 seed partition and IUPAC
    mismatch accounting, but omits per-site thermodynamic scoring because the
    LAMP topology question is positional. Thermodynamics remains an independent
    evidence layer rather than a discovery gate.
    """
    from . import specificity as spec

    primer = query.sequence.upper()
    found: list[LampPlacedSite] = []
    complete = True
    for contig in contigs:
        plus = contig.sequence.upper()
        for actual_orientation in ("forward", "reverse"):
            pattern = primer if actual_orientation == "forward" else reverse_complement(primer)
            for start in spec._candidate_window_starts(plus, pattern, max_mismatches):
                window = plus[start : start + len(pattern)]
                bounds = spec._mismatch_bounds(window, pattern)
                if bounds is None or bounds[0] > max_mismatches:
                    continue
                mismatch_lower, mismatch_upper = bounds
                ambiguous = sum(base not in "ACGT" for base in window)
                # The biologically critical oligo terminus maps to opposite ends
                # of the plus-strand window when the hit itself is reversed.
                critical_index = (
                    -1
                    if (query.critical_end == "3" and actual_orientation == "forward")
                    else 0
                    if query.critical_end == "3"
                    else 0
                    if actual_orientation == "forward"
                    else -1
                )
                terminal_exact = (
                    window[critical_index] in "ACGT"
                    and window[critical_index] == pattern[critical_index]
                )
                found.append(
                    LampPlacedSite(
                        role=query.role,
                        contig=contig.name,
                        start=start,
                        end=start + len(pattern),
                        orientation=actual_orientation,
                        mismatches=int(mismatch_lower),
                        mismatch_upper_bound=int(mismatch_upper),
                        ambiguous_bases=ambiguous,
                        critical_terminal_exact=terminal_exact,
                    )
                )
                if len(found) >= LAMP_TOPOLOGY_SITE_LIMIT_PER_ROLE:
                    complete = False
                    return found, complete
    return found, complete


def _canonical_lamp_site(
    site: LampPlacedSite, *, contig_length: int, locus_orientation: str
) -> LampPlacedSite:
    """Map a reverse-oriented locus into the reference coordinate direction."""
    if locus_orientation == "forward":
        return site
    return replace(
        site,
        start=contig_length - site.end,
        end=contig_length - site.start,
    )


def _physical_lamp_coordinates(
    site: LampPlacedSite, *, contig_length: int, locus_orientation: str
) -> tuple[int, int]:
    """Undo canonicalisation for reporting native contig coordinates."""
    if locus_orientation == "forward":
        return site.start, site.end
    return contig_length - site.end, contig_length - site.start


def _range_by(
    items: list[LampPlacedSite], keys: list[int], low: int, high: int
) -> list[LampPlacedSite]:
    if not items or low > high:
        return []
    return items[bisect_left(keys, low) : bisect_right(keys, high)]


def _lamp_background_topology_audit(
    template: str,
    one: Set,
    contigs: list[Any],
    *,
    f2_b2_span: tuple[int, int],
    loop_span: tuple[int, int],
    outer_gap: tuple[int, int],
    middle_gap: tuple[int, int],
) -> dict[str, Any]:
    """Find six-region background loci compatible with this selected LAMP set.

    Risk classes are epistemic, not wet-lab probabilities:
      0 complete scan in this model, no terminal-intact compatible locus;
      1 computation unresolved/truncated;
      2 <=2-mismatch six-region locus with all critical terminal bases exact;
      3 exact six-region locus.
    """
    bases = sum(len(contig.sequence) for contig in contigs)
    if bases > LAMP_TOPOLOGY_DIRECT_MAX_BASES:
        return {
            "checked": False,
            "risk_class": 1,
            "classification": "indexed-validation-required",
            "background_bases": bases,
            "direct_limit_bases": LAMP_TOPOLOGY_DIRECT_MAX_BASES,
            "claim": (
                "This background is intentionally not rescanned set-by-set with the direct "
                "six-region matcher. Genome-scale LAMP topology requires the indexed external "
                "validator; absence of a direct result is not evidence of cleanliness."
            ),
        }

    queries = _lamp_core_region_queries(template, one)
    by_role: dict[str, list[LampPlacedSite]] = {}
    site_complete = True
    for query in queries:
        sites, complete = _lamp_sequence_sites(query, contigs)
        by_role[query.role] = sites
        site_complete = site_complete and complete

    contig_names = sorted({site.contig for values in by_role.values() for site in values})
    contig_lengths = {str(contig.name): len(contig.sequence) for contig in contigs}
    query_by_role = {query.role: query for query in queries}
    loci: list[dict[str, Any]] = []
    exact_count = 0
    terminal_intact_count = 0
    compatible_count = 0
    combination_evaluations = 0
    combination_complete = True
    locus_orientations_checked: set[str] = set()

    for contig_name in contig_names:
        contig_length = contig_lengths[contig_name]
        for locus_orientation in ("forward", "reverse"):
            # For a reverse-complement genomic copy, every primer-region hit is
            # reversed and the physical role order is mirrored. Canonicalising
            # coordinates lets the exact same LAMP geometry rules be applied to
            # both locus orientations without duplicating biological logic.
            role_sites: dict[str, list[LampPlacedSite]] = {}
            for role, values in by_role.items():
                expected = query_by_role[role].expected_orientation
                required = (
                    expected if locus_orientation == "forward" else _opposite_orientation(expected)
                )
                selected = [
                    _canonical_lamp_site(
                        site,
                        contig_length=contig_length,
                        locus_orientation=locus_orientation,
                    )
                    for site in values
                    if site.contig == contig_name and site.orientation == required
                ]
                role_sites[role] = selected
            if any(not role_sites[role] for role in ("F3", "F2", "F1c", "B1c", "B2", "B3")):
                continue
            locus_orientations_checked.add(locus_orientation)
            starts: dict[str, list[int]] = {}
            for role in role_sites:
                role_sites[role].sort(key=lambda site: (site.start, site.end))
                starts[role] = [site.start for site in role_sites[role]]
            b2_by_end = sorted(role_sites["B2"], key=lambda site: (site.end, site.start))
            b2_ends = [site.end for site in b2_by_end]
            f3_by_end = sorted(role_sites["F3"], key=lambda site: (site.end, site.start))
            f3_ends = [site.end for site in f3_by_end]

            for f2 in role_sites["F2"]:
                f1_candidates = _range_by(
                    role_sites["F1c"],
                    starts["F1c"],
                    f2.start + loop_span[0],
                    f2.start + loop_span[1],
                )
                for f1c in f1_candidates:
                    b1_candidates = _range_by(
                        role_sites["B1c"],
                        starts["B1c"],
                        f1c.end + middle_gap[0],
                        f1c.end + middle_gap[1],
                    )
                    for b1c in b1_candidates:
                        b2_candidates = _range_by(
                            b2_by_end,
                            b2_ends,
                            b1c.end + loop_span[0],
                            b1c.end + loop_span[1],
                        )
                        for b2 in b2_candidates:
                            span = b2.end - f2.start
                            if not f2_b2_span[0] <= span <= f2_b2_span[1]:
                                continue
                            f3_candidates = _range_by(
                                f3_by_end,
                                f3_ends,
                                f2.start - outer_gap[1],
                                f2.start - outer_gap[0],
                            )
                            b3_candidates = _range_by(
                                role_sites["B3"],
                                starts["B3"],
                                b2.end + outer_gap[0],
                                b2.end + outer_gap[1],
                            )
                            for f3 in f3_candidates:
                                for b3 in b3_candidates:
                                    combination_evaluations += 1
                                    if combination_evaluations > LAMP_TOPOLOGY_COMBINATION_LIMIT:
                                        combination_complete = False
                                        break
                                    six = (f3, f2, f1c, b1c, b2, b3)
                                    compatible_count += 1
                                    exact = all(
                                        site.mismatches == 0
                                        and site.mismatch_upper_bound == 0
                                        and site.ambiguous_bases == 0
                                        for site in six
                                    )
                                    terminal_intact = all(
                                        site.critical_terminal_exact for site in six
                                    )
                                    if exact:
                                        exact_count += 1
                                    if terminal_intact:
                                        terminal_intact_count += 1
                                    if len(loci) < LAMP_TOPOLOGY_REPORT_LIMIT:
                                        physical = [
                                            _physical_lamp_coordinates(
                                                site,
                                                contig_length=contig_length,
                                                locus_orientation=locus_orientation,
                                            )
                                            for site in six
                                        ]
                                        loci.append(
                                            {
                                                "contig": contig_name,
                                                "locus_orientation": locus_orientation,
                                                "start": min(pair[0] for pair in physical),
                                                "end": max(pair[1] for pair in physical),
                                                "exact": exact,
                                                "critical_terminals_exact": terminal_intact,
                                                "total_mismatch_lower_bound": sum(
                                                    site.mismatches for site in six
                                                ),
                                                "total_mismatch_upper_bound": sum(
                                                    site.mismatch_upper_bound for site in six
                                                ),
                                                "regions": [
                                                    {
                                                        "role": site.role,
                                                        "start": physical[index][0],
                                                        "end": physical[index][1],
                                                        "orientation": site.orientation,
                                                        "mismatches": site.mismatches,
                                                        "mismatch_upper_bound": site.mismatch_upper_bound,
                                                        "ambiguous_bases": site.ambiguous_bases,
                                                        "critical_terminal_exact": site.critical_terminal_exact,
                                                    }
                                                    for index, site in enumerate(six)
                                                ],
                                            }
                                        )
                                if not combination_complete:
                                    break
                            if not combination_complete:
                                break
                        if not combination_complete:
                            break
                    if not combination_complete:
                        break
                if not combination_complete:
                    break
            if not combination_complete:
                break
        if not combination_complete:
            break

    complete = site_complete and combination_complete
    if exact_count:
        risk_class = 3
    elif terminal_intact_count:
        risk_class = 2
    elif complete:
        risk_class = 0
    else:
        risk_class = 1
    return {
        "checked": True,
        "complete": complete,
        "risk_class": risk_class,
        "classification": {
            0: "resolved-clean-within-declared-six-region-model",
            1: "unresolved-bounded-computation",
            2: "mismatch-tolerant-terminal-intact-compatible-locus-found",
            3: "exact-six-region-compatible-locus-found",
        }[risk_class],
        "background_bases": bases,
        "max_mismatches_per_region": LAMP_TOPOLOGY_MAX_MISMATCHES,
        "critical_terminal_policy": "F3/F2/B2/B3 3-prime and F1c/B1c 5-prime must be exact for risk class 2",
        "method": "Specificity-v5 mismatch-complete ungapped bidirectional discovery + orientation-invariant LAMP six-region coordinate assembly",
        "locus_orientations_considered": ["forward", "reverse"],
        "locus_orientations_with_complete_role_presence": sorted(locus_orientations_checked),
        "site_enumeration_complete": site_complete,
        "combination_enumeration_complete": combination_complete,
        "combination_evaluations": combination_evaluations,
        "compatible_locus_count_lower_bound": compatible_count,
        "terminal_intact_locus_count_lower_bound": terminal_intact_count,
        "exact_locus_count_lower_bound": exact_count,
        "sites_per_role": {role: len(values) for role, values in by_role.items()},
        "loci": loci,
        "claim": (
            "A zero risk class means no compatible locus was found only within the declared finite, "
            "ungapped <=2-mismatch model. It is not a proof that mismatch/indel/polymerase-mediated "
            "nonspecific LAMP cannot occur."
        ),
    }


def _lamp_topology_rank(audit: dict[str, Any] | None) -> tuple[int, int, int]:
    if not audit:
        return (1, 0, 0)
    risk_class = int(audit.get("risk_class", 1))
    return (
        risk_class,
        int(audit.get("exact_locus_count_lower_bound", 0)),
        int(audit.get("terminal_intact_locus_count_lower_bound", 0)),
    )


def _generic_off_target_rank(audit: dict[str, Any] | None) -> tuple[int, int, int]:
    """Rank direct generic specificity without promoting missing evidence.

    ``screen.oligos`` returns concrete product/site counts only when a direct
    sequence scan actually ran.  Genome-scale LAMP backgrounds are delegated
    to the indexed validator; representing that state with zero counts would
    make unresolved evidence rank as if it were clean.
    """
    if not audit or audit.get("checked") is not True:
        return (1, 0, 0)
    return (
        0,
        int(audit.get("product_count") or 0),
        int(audit.get("site_count") or 0),
    )


def _indexed_specificity_required(background_bases: int) -> dict[str, Any]:
    return {
        "checked": False,
        "classification": "indexed-validation-required",
        "background_bases": background_bases,
        "direct_limit_bases": LAMP_GENERIC_DIRECT_MAX_BASES,
        "note": (
            "The supplied LAMP exclusion background exceeds the direct per-candidate "
            "screening limit. PCRStudio intentionally did not rescan it set-by-set; "
            "the indexed external validator must supply genome-scale specificity evidence. "
            "This unresolved state is not a zero-off-target result."
        ),
    }


def _thermodynamic_structure_rank(entry: dict[str, Any]) -> tuple[int, float, float, float, float]:
    """Continuous set-level structure rank; lower is better.

    No hard threshold is implied. Pairwise interaction Tm, self-dimer Tm and
    hairpin Tm are independent soft features because LAMP publications and
    design tools consistently review these structures, while empirical work
    shows that none alone predicts nonspecific amplification reliably.

    Evidence incompleteness is explicit. Historically a failed pairwise
    calculation produced ``None`` values that were converted to ``-inf`` and
    therefore ranked *better* than a successfully computed low-risk set. That
    confuses absence of evidence with favourable evidence. A computed matrix
    now wins this tie-break layer over an uncomputed one, while no structure
    value is promoted to a universal pass/fail gate.
    """
    interactions_block = entry.get("interactions") or {}
    pair_tm = interactions_block.get("max_predicted_tm_c")
    pair_dg = interactions_block.get("most_favourable_dg_kcal_mol")
    pairwise_incomplete = (
        interactions_block.get("classification") == "not-computed"
        or pair_tm is None
        or pair_dg is None
    )
    self_tms = [
        float(oligo["self_dimer_tm"])
        for oligo in entry.get("oligos", [])
        if oligo.get("self_dimer_tm") is not None
    ]
    hairpin_tms = [
        float(oligo["hairpin_tm"])
        for oligo in entry.get("oligos", [])
        if oligo.get("hairpin_tm") is not None
    ]
    return (
        1 if pairwise_incomplete else 0,
        float(pair_tm) if pair_tm is not None else 0.0,
        max(self_tms, default=float("-inf")),
        max(hairpin_tms, default=float("-inf")),
        -float(pair_dg) if pair_dg is not None else 0.0,
    )


def _existing_lamp_text(value: Any, *, name: str, required: bool = True) -> str | None:
    if value in (None, "") and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise LoopSetError(f"existing_set.{name} must be a non-empty DNA sequence")
    sequence = "".join(value.split()).upper().replace("U", "T")
    if any(base not in "ACGT" for base in sequence):
        raise LoopSetError(f"existing_set.{name} must contain A/C/G/T bases only")
    return sequence


def _existing_lamp_integer(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LoopSetError(f"existing_set.{name} must be a positive integer")
    return value


def _unique_lamp_site(template: str, query: str, *, role: str) -> int:
    starts: list[int] = []
    cursor = template.find(query)
    while cursor >= 0:
        starts.append(cursor)
        cursor = template.find(query, cursor + 1)
    if len(starts) != 1:
        raise LoopSetError(
            f"Existing LAMP role {role} maps {len(starts)} time(s) on the submitted target; "
            "validation requires one unambiguous target locus for every role."
        )
    return starts[0]


def _existing_candidate(
    template: str,
    plus_sequence: str,
    *,
    role: str,
    window: Window,
    primes_from: str,
    gc_bounds: tuple[float | None, float | None],
    end_threshold: float,
) -> tuple[Candidate, dict[str, Any]]:
    start = _unique_lamp_site(template, plus_sequence, role=role)
    length = len(plus_sequence)
    tm = primerexplorer_v5_tm(plus_sequence)
    gc = gc_percent(plus_sequence)
    terminal = plus_sequence[:END_BASES] if primes_from == "start" else plus_sequence[-END_BASES:]
    end_dg = primerexplorer_v5_end_dg(terminal)
    issues: list[str] = []
    if not window.length_min <= length <= window.length_max:
        issues.append(f"length {length} outside {window.length_min}-{window.length_max} nt")
    if window.tm_min is not None and tm < window.tm_min:
        issues.append(f"Tm {tm:.1f} °C below {window.tm_min} °C")
    if window.tm_max is not None and tm > window.tm_max:
        issues.append(f"Tm {tm:.1f} °C above {window.tm_max} °C")
    gc_min, gc_max = gc_bounds
    if gc_min is not None and gc < gc_min:
        issues.append(f"GC {gc:.1f}% below {gc_min}%")
    if gc_max is not None and gc > gc_max:
        issues.append(f"GC {gc:.1f}% above {gc_max}%")
    if end_dg > end_threshold:
        issues.append(f"critical-end ΔG {end_dg:.2f} exceeds reviewed threshold {end_threshold}")
    return Candidate(start=start, length=length, tm=tm, gc=gc, end_dg=end_dg), {
        "role": role,
        "sequence": plus_sequence,
        "start": start,
        "length": length,
        "tm": tm,
        "gc_percent": gc,
        "critical_end_dg": end_dg,
        "within_selected_design_envelope": not issues,
        "issues": issues,
    }


def _existing_lamp_set(
    template: str,
    raw: Any,
    *,
    windows: Windows,
    inner_linker: str,
    f2_b2_span: tuple[int, int],
    loop_span: tuple[int, int],
    outer_gap: tuple[int, int],
    middle_gap: tuple[int, int],
) -> tuple[Set, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise LoopSetError("existing_set must be an object")
    allowed = {"f3", "b3", "fip", "bip", "lf", "lb", "fip_f1c_length", "bip_b1c_length"}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise LoopSetError("unknown existing_set field(s): " + ", ".join(unknown))
    f3_seq = _existing_lamp_text(raw.get("f3"), name="f3") or ""
    b3_oligo = _existing_lamp_text(raw.get("b3"), name="b3") or ""
    fip = _existing_lamp_text(raw.get("fip"), name="fip") or ""
    bip = _existing_lamp_text(raw.get("bip"), name="bip") or ""
    lf_oligo = _existing_lamp_text(raw.get("lf"), name="lf", required=False)
    lb_oligo = _existing_lamp_text(raw.get("lb"), name="lb", required=False)
    f1c_length = _existing_lamp_integer(raw.get("fip_f1c_length"), name="fip_f1c_length")
    b1c_length = _existing_lamp_integer(raw.get("bip_b1c_length"), name="bip_b1c_length")
    linker = inner_linker.upper()
    if f1c_length + len(linker) >= len(fip) or b1c_length + len(linker) >= len(bip):
        raise LoopSetError(
            "F1c/B1c split length plus linker must leave a non-empty F2/B2 annealing segment"
        )
    if linker and (
        fip[f1c_length : f1c_length + len(linker)] != linker
        or bip[b1c_length : b1c_length + len(linker)] != linker
    ):
        raise LoopSetError(
            "Existing FIP/BIP sequences do not contain the selected inner-primer linker at the declared split"
        )

    f1c = fip[:f1c_length]
    f2_seq = fip[f1c_length + len(linker) :]
    b1c_seq = bip[:b1c_length]
    b2_oligo = bip[b1c_length + len(linker) :]
    role_specs = [
        ("F3", f3_seq, windows.outer, "end", (windows.gc_min, windows.gc_max), END_STABILITY),
        ("F2", f2_seq, windows.outer, "end", (windows.gc_min, windows.gc_max), END_STABILITY),
        (
            "F1/F1c",
            reverse_complement(f1c),
            windows.inner,
            "end",
            (windows.gc_min, windows.gc_max),
            END_STABILITY,
        ),
        ("B1c", b1c_seq, windows.inner, "start", (windows.gc_min, windows.gc_max), END_STABILITY),
        (
            "B2c/B2",
            reverse_complement(b2_oligo),
            windows.outer,
            "start",
            (windows.gc_min, windows.gc_max),
            END_STABILITY,
        ),
        (
            "B3c/B3",
            reverse_complement(b3_oligo),
            windows.outer,
            "start",
            (windows.gc_min, windows.gc_max),
            END_STABILITY,
        ),
    ]
    built: dict[str, Candidate] = {}
    evidence: list[dict[str, Any]] = []
    for role, plus, window, primes_from, gc_bounds, threshold in role_specs:
        candidate, audit = _existing_candidate(
            template,
            plus,
            role=role,
            window=window,
            primes_from=primes_from,
            gc_bounds=gc_bounds,
            end_threshold=threshold,
        )
        built[role] = candidate
        evidence.append(audit)

    lf = None
    if lf_oligo:
        lf, audit = _existing_candidate(
            template,
            reverse_complement(lf_oligo),
            role="LF",
            window=windows.loop,
            primes_from="start",
            gc_bounds=(LOOP_GC_MIN, LOOP_GC_MAX),
            end_threshold=LOOP_END_STABILITY,
        )
        evidence.append(audit)
    lb = None
    if lb_oligo:
        lb, audit = _existing_candidate(
            template,
            lb_oligo,
            role="LB",
            window=windows.loop,
            primes_from="end",
            gc_bounds=(LOOP_GC_MIN, LOOP_GC_MAX),
            end_threshold=LOOP_END_STABILITY,
        )
        evidence.append(audit)

    f3 = built["F3"]
    f2 = built["F2"]
    f1 = built["F1/F1c"]
    b1 = built["B1c"]
    b2 = built["B2c/B2"]
    b3 = built["B3c/B3"]
    if not (
        f3.end
        <= f2.start
        < f2.end
        <= f1.start
        < f1.end
        <= b1.start
        < b1.end
        <= b2.start
        < b2.end
        <= b3.start
    ):
        raise LoopSetError(
            "Existing F3/F2/F1/B1c/B2c/B3c roles do not form the required non-overlapping LAMP order on the submitted target."
        )
    if lf and not (f2.end <= lf.start and lf.end <= f1.start):
        raise LoopSetError("Existing LF does not lie entirely between F2 and F1 on the target")
    if lb and not (b1.end <= lb.start and lb.end <= b2.start):
        raise LoopSetError("Existing LB does not lie entirely between B1c and B2c on the target")

    forward = Half(outer=f2, inner=f1, loop=lf, span=f1.start - f2.start)
    backward = Half(outer=b2, inner=b1, loop=lb, span=b2.end - b1.end)
    one = Set(forward=forward, backward=backward, f3=f3, b3=b3)
    actual = {
        "f2_b2_span": one.f2_b2_span,
        "forward_loop_span": f1.start - f2.end,
        "backward_loop_span": b2.start - b1.end,
        "forward_outer_gap": f2.start - f3.end,
        "backward_outer_gap": b3.start - b2.end,
        "middle_gap": one.middle_gap,
    }
    geometry_issues: list[str] = []
    checks = [
        ("f2_b2_span", actual["f2_b2_span"], f2_b2_span),
        ("forward_loop_span", actual["forward_loop_span"], loop_span),
        ("backward_loop_span", actual["backward_loop_span"], loop_span),
        ("forward_outer_gap", actual["forward_outer_gap"], outer_gap),
        ("backward_outer_gap", actual["backward_outer_gap"], outer_gap),
        ("middle_gap", actual["middle_gap"], middle_gap),
    ]
    for name, value, limits in checks:
        if not limits[0] <= value <= limits[1]:
            geometry_issues.append(f"{name}={value} outside {limits[0]}-{limits[1]}")
    return one, {
        "mode": "validate-existing",
        "mapped_unambiguously": True,
        "role_audits": evidence,
        "geometry": actual,
        "geometry_issues": geometry_issues,
        "within_selected_design_envelope": not geometry_issues
        and all(item["within_selected_design_envelope"] for item in evidence),
        "decision_impact": "no-redesign-existing-set-evidence-only",
    }


def _rt_lamp_accessibility(
    template: str,
    entry: dict[str, Any],
    *,
    wants_rna: bool,
    protocol: dict[str, Any] | None,
    fallback_temperature_c: float,
) -> dict[str, Any] | None:
    """Optional RNA-target accessibility evidence for RT-LAMP selected regions.

    This diagnostic is deliberately attached *after* set selection. ViennaRNA
    availability therefore cannot change candidate ranking, validity or which
    set is returned. The six target-derived LAMP regions are folded with Turner
    2004 RNA parameters at the named protocol hold when that authority exists.
    """
    if not wants_rna:
        return None
    regions = entry.get("regions")
    if not isinstance(regions, list):
        return {
            "checked": False,
            "decision_impact": "none",
            "note": "Selected LAMP set did not expose role regions for optional RNA accessibility review.",
        }
    windows: dict[str, tuple[int, int]] = {}
    for raw in regions:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        at = raw.get("at")
        length = raw.get("length")
        if (
            isinstance(name, str)
            and isinstance(at, int)
            and isinstance(length, int)
            and at >= 0
            and length > 0
        ):
            windows[name] = (at, length)
    hold = protocol.get("hold_temperature_c") if isinstance(protocol, dict) else None
    temperature = (
        float(hold)
        if isinstance(hold, (int, float)) and not isinstance(hold, bool)
        else float(fallback_temperature_c)
    )
    folded = access.profile(template, windows, celsius=temperature, molecule="RNA")
    report = access.accessibility_to_dict(folded)
    report.update(
        {
            "molecule": "RNA",
            "parameter_authority": "ViennaRNA Turner 2004 RNA",
            "decision_impact": "none",
            "note": (
                report.get("note")
                or "Optional RT-LAMP RNA-structure diagnostic on the selected role regions; it did not participate in set generation, hard validity or ranking."
            ),
        }
    )
    return report


def _workflow_evidence(value: Any) -> dict[str, str | int | float | bool | None] | None:
    """Validate LAMP evidence through the shared cross-engine contract."""
    try:
        return validate_evidence_fields(value)
    except WorkflowEvidenceError as exc:
        raise LoopSetError(str(exc)) from exc


def _enum_value(request: dict[str, Any], key: str, allowed: tuple[str, ...], default: str) -> str:
    value = str(request.get(key) or default)
    if value not in allowed:
        raise LoopSetError(f"{key} must be one of: " + ", ".join(allowed) + ".")
    return value


def _fixed_primer_request(request: dict[str, Any], intent: str) -> dict[str, str] | None:
    raw = request.get("lamp_fixed_primers")
    if raw is None:
        if intent == "fixed-primer-anchor":
            raise LoopSetError(
                "fixed-primer-anchor requires lamp_fixed_primers with at least one exact F3/B3/FIP/BIP/LF/LB sequence."
            )
        return None
    if intent != "fixed-primer-anchor":
        raise LoopSetError(
            "lamp_fixed_primers is accepted only with lamp_design_intent=fixed-primer-anchor."
        )
    if not isinstance(raw, dict) or not raw:
        raise LoopSetError("lamp_fixed_primers must be a non-empty object.")
    unknown = sorted(set(raw) - set(LAMP_FIXED_PRIMER_ROLES))
    if unknown:
        raise LoopSetError("Unknown fixed LAMP primer role(s): " + ", ".join(unknown))
    answer: dict[str, str] = {}
    for role, sequence in raw.items():
        text = str(sequence or "").strip().upper()
        if not text or any(base not in "ACGT" for base in text):
            raise LoopSetError(
                f"lamp_fixed_primers.{role} must be a non-empty unambiguous DNA sequence."
            )
        answer[role] = text
    return answer


def _mutation_request(request: dict[str, Any], intent: str, template: str) -> dict[str, Any] | None:
    raw = request.get("lamp_variant")
    if raw is None:
        if intent == "mutation-anchored-specific":
            raise LoopSetError(
                "mutation-anchored-specific requires lamp_variant with position/ref/alt/anchor."
            )
        return None
    if intent != "mutation-anchored-specific":
        raise LoopSetError(
            "lamp_variant is accepted only with lamp_design_intent=mutation-anchored-specific."
        )
    if not isinstance(raw, dict):
        raise LoopSetError("lamp_variant must be an object.")
    if set(raw) - {"position", "ref", "alt", "anchor"}:
        raise LoopSetError("lamp_variant accepts only position, ref, alt and anchor.")
    position = raw.get("position")
    if (
        not isinstance(position, int)
        or isinstance(position, bool)
        or not 0 <= position < len(template)
    ):
        raise LoopSetError(
            "lamp_variant.position must be a 0-based position inside the submitted target."
        )
    ref = str(raw.get("ref") or "").upper()
    alt = str(raw.get("alt") or "").upper()
    anchor = str(raw.get("anchor") or "")
    if len(ref) != 1 or len(alt) != 1 or ref not in "ACGT" or alt not in "ACGT" or ref == alt:
        raise LoopSetError("lamp_variant.ref and alt must be different single A/C/G/T bases.")
    if anchor not in LAMP_MUTATION_ANCHORS:
        raise LoopSetError(
            "lamp_variant.anchor must be one of: " + ", ".join(LAMP_MUTATION_ANCHORS)
        )
    if template[position].upper() != alt:
        raise LoopSetError(
            "mutation-specific design expects the submitted template to carry lamp_variant.alt at lamp_variant.position."
        )
    return {
        "position": position,
        "ref": ref,
        "alt": alt,
        "anchor": anchor,
        "empirical_validation_required": True,
    }


def _optional_nonnegative_numeric(request: dict[str, Any], key: str) -> float | None:
    value = request.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise LoopSetError(f"{key} must be numeric when supplied.")
    number = float(value)
    if number < 0:
        raise LoopSetError(f"{key} cannot be negative.")
    return number


def _readout_chemistry_compatibility(
    protocol: dict[str, Any] | None, readout: str, chemistry: str
) -> dict[str, Any]:
    branch = _READOUT_CHEMISTRY_BRANCH[chemistry]
    if chemistry != "not-specified" and readout != "not-specified" and branch != readout:
        raise LoopSetError(
            f"LAMP readout chemistry `{chemistry}` belongs to `{branch}`, not `{readout}`."
        )
    if protocol is not None:
        forbidden = dict(protocol.get("forbidden_readout_chemistries") or {})
        if chemistry in forbidden:
            raise LoopSetError(
                f"The selected LAMP readout chemistry `{chemistry}` conflicts with the reviewed named protocol: {forbidden[chemistry]}"
            )
    return {"selected": chemistry, "branch": branch, "decision_impact": "none"}


def _sample_scenario_compatibility(
    protocol: dict[str, Any] | None, matrix: str, preparation: str
) -> dict[str, Any]:
    direct = preparation in {"direct-addition", "koh-lyse-and-lamp"}
    if direct:
        if protocol is None:
            raise LoopSetError(
                "Direct-sample LAMP requires a named reviewed protocol; generic Bst chemistry is not a direct-matrix authority."
            )
        if matrix in {"not-specified", "crude-unspecified"}:
            raise LoopSetError("Direct-sample LAMP requires an explicit reviewed specimen matrix.")
        allowed = list(protocol.get("direct_sample_matrices") or [])
        if matrix not in allowed:
            raise LoopSetError(
                f"The selected protocol does not carry reviewed direct-sample authority for `{matrix}`."
            )
        if preparation == "koh-lyse-and-lamp" and matrix != "koh-lysate":
            raise LoopSetError("KOH Lyse & LAMP requires lamp_sample_matrix=`koh-lysate`.")
    return {
        "matrix": matrix,
        "preparation": preparation,
        "direct": direct,
        "decision_impact": "none",
    }


def _formulation_compatibility(protocol: dict[str, Any] | None, formulation: str) -> dict[str, Any]:
    if formulation != "not-specified" and protocol is None:
        raise LoopSetError(
            "An explicit LAMP formulation requires a named reviewed protocol authority."
        )
    if (
        formulation != "not-specified"
        and protocol is not None
        and formulation not in list(protocol.get("formats") or [])
    ):
        raise LoopSetError(
            f"The selected protocol does not carry reviewed `{formulation}` formulation authority."
        )
    return {"selection": formulation, "decision_impact": "none"}


def _confirmation_compatibility(
    protocol: dict[str, Any] | None, confirmation: str
) -> dict[str, Any]:
    reviewed = list((protocol or {}).get("recommended_confirmation_modes") or [])
    return {
        "selection": confirmation,
        "reviewed_for_protocol": confirmation in reviewed
        if confirmation != "not-specified"
        else None,
        "note": "Confirmation evidence is assay provenance; a melt/anneal curve does not establish sequence identity.",
        "decision_impact": "none",
    }


def _bench_optimization(
    request: dict[str, Any], protocol: dict[str, Any] | None
) -> dict[str, float] | None:
    raw = request.get("lamp_bench_optimization")
    if raw in (None, {}):
        return None
    if protocol is None:
        raise LoopSetError("LAMP bench optimization requires a named reviewed protocol authority.")
    if not isinstance(raw, dict):
        raise LoopSetError("lamp_bench_optimization must be an object.")
    protocol_id = str(protocol.get("_protocol_id") or "")
    scope = dict(LAMP_NUMERIC_OPTIMIZATION_ENVELOPES.get(protocol_id) or {})
    checked: dict[str, float] = {}
    for key, value in raw.items():
        if key not in scope:
            raise LoopSetError(
                f"The selected protocol does not publish a reviewed optimization envelope for `{key}`."
            )
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise LoopSetError(f"lamp_bench_optimization.{key} must be numeric.")
        lo, hi = scope[key]
        number = float(value)
        if not lo <= number <= hi:
            raise LoopSetError(
                f"lamp_bench_optimization.{key} must be within the reviewed range {lo}–{hi}."
            )
        checked[key] = number
    return checked


def run(request: dict[str, Any]) -> dict[str, Any]:
    """One loop-mediated design, end to end, in the shape the interface reads.

    Raises:
        IntakeError: the input is not a usable template.
        LoopSetError: a geometry or a parameter set that could not hold.
        ValueError: a constraint, preset or reaction that cannot hold.
    """
    from .intake import target_to_dict
    from .presets import thermodynamic_model
    from .provenance import provenance
    from .settings import excluded_from, how_many_from, label, prepare

    workflow_evidence = _workflow_evidence(request.get("workflow_evidence"))
    try:
        modified_oligos = modified_oligo_provenance(request.get("modified_oligos"))
    except ValueError as exc:
        raise LoopSetError(str(exc)) from exc
    circular = request.get("circular")
    if circular is not None and not isinstance(circular, bool):
        raise LoopSetError("circular must be a boolean when supplied.")
    if circular is True:
        raise LoopSetError(
            "Gen-1 LAMP loop-set does not support circular target topology. "
            "Linearizing a circular molecule can hide an origin-spanning six-region locus, "
            "so PCRStudio refuses this request instead of silently designing it as linear DNA."
        )

    # The product is not a band anybody measures — the read-out is turbidity or
    # a colour change — so the usual product-room check describes nothing here.
    chosen = prepare(request, require_product_room=False)
    how_many = how_many_from(request, MOST_SETS)
    reaction = chosen.reaction.as_conditions()
    lamp_protocol = str(request.get("lamp_protocol") or "not-selected")
    if lamp_protocol not in LAMP_PROTOCOLS:
        raise LoopSetError("lamp_protocol must be one of: " + ", ".join(LAMP_PROTOCOLS) + ".")
    lamp_readout = str(request.get("lamp_readout") or "not-specified")
    if lamp_readout not in LAMP_READOUTS:
        raise LoopSetError("lamp_readout must be one of: " + ", ".join(LAMP_READOUTS) + ".")
    protocol = _lamp_protocol(lamp_protocol)
    wants_rna = rt.wanted(request)
    if protocol is not None:
        if wants_rna and not protocol.get("supports_rna"):
            # Refuse before candidate enumeration: protocol/substrate incompatibility
            # is not a sequence-design failure and should not spend bounded search.
            _rt_lamp_block_for_protocol(lamp_protocol, protocol)
        if not wants_rna and not protocol.get("supports_dna"):
            raise LoopSetError(
                f"The selected LAMP protocol {lamp_protocol} is RNA-only under its reviewed vendor authority "
                "and cannot satisfy a DNA-template request. Choose a reviewed DNA-capable LAMP protocol "
                "or leave lamp_protocol unselected."
            )
        # Protocol/readout contradictions are chemistry-contract errors, not candidate-search failures.
        _readout_compatibility(protocol, lamp_readout)

    lamp_readout_chemistry = _enum_value(
        request, "lamp_readout_chemistry", LAMP_READOUT_CHEMISTRIES, "not-specified"
    )
    lamp_sample_matrix = _enum_value(
        request, "lamp_sample_matrix", LAMP_SAMPLE_MATRICES, "not-specified"
    )
    lamp_sample_preparation = _enum_value(
        request, "lamp_sample_preparation", LAMP_SAMPLE_PREPARATIONS, "not-specified"
    )
    lamp_formulation = _enum_value(request, "lamp_formulation", LAMP_FORMULATIONS, "not-specified")
    lamp_confirmation_mode = _enum_value(
        request, "lamp_confirmation_mode", LAMP_CONFIRMATION_MODES, "not-specified"
    )
    lamp_detection_topology = _enum_value(
        request, "lamp_detection_topology", LAMP_DETECTION_TOPOLOGIES, "nonspecific-dsdna"
    )
    lamp_design_intent = _enum_value(request, "lamp_design_intent", LAMP_DESIGN_INTENTS, "standard")
    lamp_design_stage = _enum_value(request, "lamp_design_stage", LAMP_DESIGN_STAGES, "integrated")
    lamp_loop_policy = _enum_value(request, "lamp_loop_policy", LAMP_LOOP_POLICIES, "prefer-six")
    lamp_carryover_strategy = _enum_value(
        request, "lamp_carryover_strategy", LAMP_CARRYOVER_STRATEGIES, "protocol-default"
    )
    lamp_reconstitution_x = _enum_value(
        request, "lamp_reconstitution_x", LAMP_RECONSTITUTION_OPTIONS, "protocol-default"
    )
    lamp_specificity_additive = _enum_value(
        request, "lamp_specificity_additive", LAMP_SPECIFICITY_ADDITIVES, "none"
    )
    lamp_acceleration_additive = _enum_value(
        request, "lamp_acceleration_additive", LAMP_ACCELERATION_ADDITIVES, "none"
    )
    lamp_primer_kinetics_profile = _enum_value(
        request, "lamp_primer_kinetics_profile", LAMP_PRIMER_KINETICS_PROFILES, "protocol-default"
    )
    lamp_preincubation_strategy = _enum_value(
        request, "lamp_preincubation_strategy", LAMP_PREINCUBATION_STRATEGIES, "protocol-default"
    )
    lamp_sample_buffer_type = _enum_value(
        request, "lamp_sample_buffer_type", LAMP_SAMPLE_BUFFER_TYPES, "none"
    )
    lamp_instrument_profile = _enum_value(
        request, "lamp_instrument_profile", LAMP_INSTRUMENT_PROFILES, "not-specified"
    )
    lamp_sample_input_percent = _optional_nonnegative_numeric(request, "lamp_sample_input_percent")
    lamp_sample_buffer_ph = _optional_nonnegative_numeric(request, "lamp_sample_buffer_ph")
    lamp_sample_buffer_percent = _optional_nonnegative_numeric(
        request, "lamp_sample_buffer_percent"
    )
    lamp_transport_medium_percent = _optional_nonnegative_numeric(
        request, "lamp_transport_medium_percent"
    )
    lamp_bile_salt_mg_ml = _optional_nonnegative_numeric(request, "lamp_bile_salt_mg_ml")
    lamp_cary_blair_percent = _optional_nonnegative_numeric(request, "lamp_cary_blair_percent")
    lamp_upstream_guanidine_mM = _optional_nonnegative_numeric(
        request, "lamp_upstream_guanidine_mM"
    )

    try:
        lamp_multiplex_plan = resolve_lamp_multiplex(
            request.get("lamp_multiplex_plan"), topology=lamp_detection_topology
        )
    except ValueError as exc:
        raise LoopSetError(str(exc)) from exc
    if lamp_detection_topology not in {"nonspecific-dsdna", "multiplex-modified-primer-probe"}:
        raise LoopSetError(
            "Gen-1 LAMP executes standard design plus evidence-bound multiplex modified-primer/probe planning; other modified-probe/lateral-flow topologies remain fail closed."
        )
    if (
        lamp_design_intent == "panel-conservation-aware"
        and not str(request.get("inclusivity") or "").strip()
    ):
        raise LoopSetError(
            "panel-conservation-aware LAMP design requires an explicit inclusivity panel."
        )
    if lamp_carryover_strategy != "protocol-default" and lamp_protocol not in {
        "neb-m9204",
        "neb-m9205",
    }:
        raise LoopSetError(
            "The reviewed numeric dUTP/UDG carry-over overlay is limited to the NEB M9204/M9205 standalone Bst-XT protocols."
        )
    if lamp_reconstitution_x != "protocol-default" and lamp_protocol != "neb-l4401":
        raise LoopSetError(
            "Explicit 2X/4X reconstitution authority is currently source-backed only for NEB L4401."
        )
    if lamp_specificity_additive != "none" and lamp_protocol != "neb-e1700":
        raise LoopSetError(
            "The reviewed Tte UvrD starting example is scoped to NEB E1700; it is not a universal LAMP additive amount."
        )
    if lamp_acceleration_additive != "none" and (
        lamp_protocol not in {"neb-m1800", "neb-m1804"} or lamp_readout != "colorimetric"
    ):
        raise LoopSetError(
            "The reviewed 40 mM Guanidine HCl acceleration branch is limited to NEB M1800/M1804 colorimetric LAMP."
        )
    if lamp_primer_kinetics_profile != "protocol-default" and lamp_protocol not in {
        "optigene-iso001",
        "optigene-iso001-rt",
        "optigene-iso004",
        "optigene-iso004-rt",
    }:
        raise LoopSetError(
            "The selected numeric primer-kinetics profile is source-backed only for the reviewed OptiGene ISO-001/ISO-004 liquid master-mix branches."
        )
    if lamp_preincubation_strategy != "protocol-default" and lamp_protocol != "takara-rr385":
        raise LoopSetError(
            "The reviewed carry-over pre-incubation branch is currently specific to Takara RR385."
        )
    if lamp_readout_chemistry == "eiken-fd-lmp221" and lamp_protocol not in {
        "eiken-lmp204",
        "eiken-lmp207",
        "eiken-lmp244",
    }:
        raise LoopSetError(
            "Eiken LMP221 fluorescent detection reagent is source-backed only with the reviewed Eiken DNA/RNA kit branches; LMP247 already contains its own calcein system."
        )
    if lamp_readout_chemistry == "eiken-fd-lmp221" and lamp_sample_buffer_type in {
        "te",
        "chelating-other",
    }:
        raise LoopSetError(
            "Eiken LMP221 explicitly warns against TE/other chelating sample buffers because Mn chelation can release calcein and create false-positive fluorescence."
        )
    if any(
        v is not None
        for v in (lamp_sample_buffer_ph, lamp_sample_buffer_percent, lamp_upstream_guanidine_mM)
    ) and (lamp_protocol not in {"neb-m1800", "neb-m1804"} or lamp_readout != "colorimetric"):
        raise LoopSetError(
            "Sample-buffer pH/fraction and upstream guanidine numeric authority is currently source-backed only for NEB M1800/M1804 pH-colorimetric LAMP."
        )
    if lamp_instrument_profile.startswith("vazyme-") and lamp_protocol != "vazyme-rp711":
        raise LoopSetError(
            "Vazyme instrument-conditioned dye profiles require the exact RP711 protocol authority."
        )
    if lamp_instrument_profile == "agdia-amplifire" and lamp_protocol != "agdia-lmx54700":
        raise LoopSetError(
            "The AmpliFire numeric run profile is source-backed here only for Agdia LMX 54700."
        )

    scenario_sample = _sample_scenario_compatibility(
        protocol, lamp_sample_matrix, lamp_sample_preparation
    )
    scenario_formulation = _formulation_compatibility(protocol, lamp_formulation)
    scenario_readout_chemistry = _readout_chemistry_compatibility(
        protocol, lamp_readout, lamp_readout_chemistry
    )
    scenario_confirmation = _confirmation_compatibility(protocol, lamp_confirmation_mode)
    scenario_optimization = _bench_optimization(request, protocol)
    numeric_scenario = {
        "readout": lamp_readout,
        "chemistry": lamp_readout_chemistry,
        "from_rna": wants_rna,
        "matrix": lamp_sample_matrix,
        "preparation": lamp_sample_preparation,
        "formulation": lamp_formulation,
        "carryover_strategy": lamp_carryover_strategy,
        "reconstitution_x": lamp_reconstitution_x,
        "specificity_additive": lamp_specificity_additive,
        "acceleration_additive": lamp_acceleration_additive,
        "primer_kinetics_profile": lamp_primer_kinetics_profile,
        "preincubation_strategy": lamp_preincubation_strategy,
        "sample_input_percent": lamp_sample_input_percent,
        "sample_buffer_type": lamp_sample_buffer_type,
        "instrument_profile": lamp_instrument_profile,
        "sample_buffer_ph": lamp_sample_buffer_ph,
        "sample_buffer_percent": lamp_sample_buffer_percent,
        "transport_medium_percent": lamp_transport_medium_percent,
        "bile_salt_mg_ml": lamp_bile_salt_mg_ml,
        "cary_blair_percent": lamp_cary_blair_percent,
        "upstream_guanidine_mM": lamp_upstream_guanidine_mM,
    }
    try:
        resolved_numeric_recipe = resolve_numeric_recipe(
            lamp_protocol, protocol, numeric_scenario, scenario_optimization
        )
    except ValueError as exc:
        raise LoopSetError(str(exc)) from exc
    lamp_scenario = {
        "sample": {**scenario_sample, "input_percent": lamp_sample_input_percent},
        "formulation": scenario_formulation,
        "readout_chemistry": scenario_readout_chemistry,
        "confirmation": scenario_confirmation,
        "detection_topology": {
            "selection": lamp_detection_topology,
            "decision_impact": "none",
            "multiplex_plan": lamp_multiplex_plan,
        },
        "design_intent": {
            "selection": lamp_design_intent,
            "decision_impact": "candidate-ranking"
            if lamp_design_intent == "panel-conservation-aware"
            else (
                "candidate-filter"
                if lamp_design_intent in {"fixed-primer-anchor", "mutation-anchored-specific"}
                else "standard"
            ),
        },
        "design_stage": {
            "selection": lamp_design_stage,
            "decision_impact": "candidate-architecture",
        },
        "loop_policy": {"selection": lamp_loop_policy, "decision_impact": "candidate-architecture"},
        "carryover_strategy": {"selection": lamp_carryover_strategy, "decision_impact": "none"},
        "reconstitution": {"selection": lamp_reconstitution_x, "decision_impact": "none"},
        "specificity_additive": {"selection": lamp_specificity_additive, "decision_impact": "none"},
        "acceleration_additive": {
            "selection": lamp_acceleration_additive,
            "decision_impact": "none",
        },
        "primer_kinetics_profile": {
            "selection": lamp_primer_kinetics_profile,
            "decision_impact": "none",
        },
        "preincubation_strategy": {
            "selection": lamp_preincubation_strategy,
            "decision_impact": "none",
        },
        "sample_buffer": {
            "type": lamp_sample_buffer_type,
            "ph": lamp_sample_buffer_ph,
            "percent_final": lamp_sample_buffer_percent,
            "decision_impact": "none",
        },
        "instrument_profile": {"selection": lamp_instrument_profile, "decision_impact": "none"},
        "matrix_modifiers": {
            "transport_medium_percent": lamp_transport_medium_percent,
            "bile_salt_mg_ml": lamp_bile_salt_mg_ml,
            "cary_blair_percent": lamp_cary_blair_percent,
            "upstream_guanidine_mM": lamp_upstream_guanidine_mM,
            "decision_impact": "none",
        },
        "bench_optimization": {"values": scenario_optimization or {}, "decision_impact": "none"},
        "resolved_numeric_recipe": resolved_numeric_recipe,
    }

    template = chosen.target.sequence.upper()
    fixed_primers = _fixed_primer_request(request, lamp_design_intent)
    mutation_anchor = _mutation_request(request, lamp_design_intent, template)
    if lamp_design_stage == "core-first":
        # Source-described two-step workflow: design/select a four-primer core,
        # then optionally return with add-loops to design LF/LB for that core.
        lamp_loop_policy = "core-four-only"
    elif lamp_design_stage == "add-loops":
        required_core = {"F3", "B3", "FIP", "BIP"}
        if (
            lamp_design_intent != "fixed-primer-anchor"
            or fixed_primers is None
            or not required_core.issubset(fixed_primers)
        ):
            raise LoopSetError(
                "lamp_design_stage=add-loops requires lamp_design_intent=fixed-primer-anchor and exact F3/B3/FIP/BIP sequences from the selected core set."
            )
        lamp_loop_policy = "require-six"
    geometry_profile = geometry_profile_for(request.get("lamp_geometry_profile"))
    inner_linker_id, inner_linker = inner_linker_for(request.get("lamp_inner_linker"))
    # One of the named parameter sets, then whatever this run was told on top.
    # of it. The sets are the right default and they are not the only geometry
    # anybody runs — a target that is AT-rich in one half and GC-rich in the
    # other fits none of them — and until now the only control was which of
    # three.
    windows, f2_b2_span, loop_span, outer_gap, middle_gap, overruled = adjust(
        windows_for(template, request.get("parameter_set")),
        request.get("windows"),
        geometry_profile=geometry_profile,
    )

    # Target inclusivity and exclusion specificity answer opposite questions.
    # The former aligns homologous intended-target sequences and asks whether
    # the actual selected LAMP regions survive target diversity. The latter
    # searches near-neighbours/backgrounds for places the oligos should *not*
    # bind. Neither is inferred from the other.
    target_alignment, target_panel_meta = _prepare_target_inclusivity(
        template, request.get("inclusivity")
    )

    # Resolve the finite specificity scope before down-selecting sets.  If the
    # caller supplied a real exclusion background, PCRStudio evaluates a wider
    # already-ranked candidate pool and lets background evidence participate in
    # final selection.  Without a background, no genome-wide cleanliness claim
    # is fabricated and the ordinary requested set count is used.
    from . import screen

    raw_background = request.get("background")
    if (
        isinstance(raw_background, str)
        and _pasted_background_base_count(raw_background) > LAMP_RAW_BACKGROUND_DIRECT_MAX_BASES
    ):
        raise LoopSetBackgroundTooLarge(
            f"The pasted LAMP exclusion background exceeds PCRStudio's "
            f"{LAMP_RAW_BACKGROUND_DIRECT_MAX_BASES:,}-base direct LAMP background limit. "
            "PCRSTUDIO_BLAST_DATABASE is a separate configured and versioned specificity "
            "scope; PCRStudio will not silently assume that it represents the pasted "
            "sequence. Supply a finite exclusion panel within the direct limit, or omit "
            "the pasted background and use an approved indexed database for genome-scale "
            "specificity validation."
        )

    contigs, template_only, fold_at = screen.contigs_for(
        request, template=chosen.target.sequence, name=chosen.target.name
    )
    background_bases = sum(len(contig.sequence) for contig in contigs)
    if not template_only and background_bases > LAMP_RAW_BACKGROUND_DIRECT_MAX_BASES:
        raise LoopSetBackgroundTooLarge(
            f"The pasted LAMP exclusion background contains {background_bases:,} bases, "
            f"above PCRStudio's {LAMP_RAW_BACKGROUND_DIRECT_MAX_BASES:,}-base direct "
            "LAMP background limit. PCRSTUDIO_BLAST_DATABASE is a separate configured "
            "and versioned specificity scope; PCRStudio will not silently assume that "
            "it represents the pasted sequence. Supply a finite exclusion panel within "
            "the direct limit, or omit the pasted background and use an approved indexed "
            "database for genome-scale specificity validation."
        )
    generic_direct_background_enabled = (
        template_only or background_bases <= LAMP_GENERIC_DIRECT_MAX_BASES
    )

    role_concentrations_uM = (
        dict(protocol.get("role_concentrations_uM") or {}) if protocol is not None else None
    )
    if not role_concentrations_uM:
        role_concentrations_uM = None

    mode = str(request.get("mode") or "design")
    if mode not in {"design", "validate-existing"}:
        raise LoopSetError("mode must be design or validate-existing")
    if mode == "validate-existing":
        one, existing_audit = _existing_lamp_set(
            template,
            request.get("existing_set"),
            windows=windows,
            inner_linker=inner_linker,
            f2_b2_span=f2_b2_span,
            loop_span=loop_span,
            outer_gap=outer_gap,
            middle_gap=middle_gap,
        )
        entry = set_to_dict(
            template,
            one,
            windows,
            role_concentrations_uM=role_concentrations_uM,
            geometry_profile=geometry_profile,
            inner_linker=inner_linker,
            **reaction,
        )
        if target_alignment is not None:
            entry["target_inclusivity"] = _target_inclusivity_audit(template, one, target_alignment)
        named: dict[str, str] = {}
        whole: dict[str, str] = {}
        for oligo in oligos(template, one, inner_linker=inner_linker):
            named[oligo.name] = (
                oligo.sequence[oligo.tail_length :] if oligo.composite else oligo.sequence
            )
            whole[oligo.name] = oligo.sequence
        if generic_direct_background_enabled:
            intended_sizes, intended_products = _lamp_generic_intended_linear_products(
                template, one, template_only=template_only
            )
            entry["off_targets"] = screen.oligos(
                named,
                contigs,
                reaction=chosen.reaction,
                fold_at=fold_at,
                max_product=screen.product_ceiling(one.size),
                intended_sizes=intended_sizes,
                intended_products=intended_products,
                temperature_c=(
                    chosen.preset.cycling.isothermal_c or chosen.preset.cycling.extend_c
                ),
            )
        else:
            entry["off_targets"] = _indexed_specificity_required(background_bases)
        if not template_only and background_bases <= LAMP_TOPOLOGY_DIRECT_MAX_BASES:
            entry["lamp_background_topology"] = _lamp_background_topology_audit(
                template,
                one,
                contigs,
                f2_b2_span=f2_b2_span,
                loop_span=loop_span,
                outer_gap=outer_gap,
                middle_gap=middle_gap,
            )
        elif not template_only:
            entry["lamp_background_topology"] = {
                "checked": False,
                "classification": "indexed-validation-required",
                "background_bases": background_bases,
                "direct_limit_bases": LAMP_TOPOLOGY_DIRECT_MAX_BASES,
                "claim": "Genome-scale six-region topology remains unresolved until indexed validation.",
            }
        entry["interactions"] = interactions(
            whole, role_concentrations_uM=role_concentrations_uM, **reaction
        )
        background_summary = screen.summary(contigs, template_only, fold_at=fold_at)
        background_summary["sequence_topology_assumption"] = "linear-sequence-records"
        background_summary["topology_note"] = (
            "Existing-set validation scans supplied finite background records as linear sequence records; "
            "no circular-background origin claim is inferred."
        )
        used = windows
        name = label(chosen.target.name)
        parameter_block = {
            "id": used.id,
            "name": used.name,
            "thermodynamic_model": PE_THERMODYNAMIC_MODEL,
            "chosen_from": "existing-set validation against explicit/automatic selected parameter envelope",
            "outer": {
                "tm": [used.outer.tm_min, used.outer.tm_max],
                "length": [used.outer.length_min, used.outer.length_max],
            },
            "inner": {
                "tm": [used.inner.tm_min, used.inner.tm_max],
                "length": [used.inner.length_min, used.inner.length_max],
            },
            "loop": {
                "tm": [used.loop.tm_min, used.loop.tm_max],
                "length": [used.loop.length_min, used.loop.length_max],
            },
            "gc": [used.gc_min, used.gc_max],
            "regular_primer_gc": [used.gc_min, used.gc_max],
            "loop_primer_gc": [LOOP_GC_MIN, LOOP_GC_MAX],
            "terminal_stability": {
                "window_bases": END_BASES,
                "regular_critical_max_dg_kcal_mol": END_STABILITY,
                "loop_3p_max_dg_kcal_mol": LOOP_END_STABILITY,
                "regular_scope": "F2/B2/F3/B3 3-prime and F1c/B1c 5-prime critical ends",
                "loop_scope": "LF/LB 3-prime ends",
                "classification": "validation-reference-envelope-not-redesign-gate",
            },
            "geometry_profile": {
                "id": geometry_profile.id,
                "name": geometry_profile.name,
                "source": geometry_profile.source,
                "claim": geometry_profile.claim,
                "valid_f2_b2_span": list(geometry_profile.valid_f2_b2_span),
                "valid_loop_span": list(geometry_profile.valid_loop_span),
                "valid_outer_gap": list(geometry_profile.valid_outer_gap),
                "valid_middle_gap": list(geometry_profile.valid_middle_gap),
                "preferred_f2_b2_span": list(geometry_profile.preferred_f2_b2_span)
                if geometry_profile.preferred_f2_b2_span is not None
                else None,
                "preferred_outer_gap": list(geometry_profile.preferred_outer_gap)
                if geometry_profile.preferred_outer_gap is not None
                else None,
                "preferred_loop_tm": list(geometry_profile.preferred_loop_tm)
                if geometry_profile.preferred_loop_tm is not None
                else None,
            },
            "inner_linker": {
                "id": inner_linker_id,
                "sequence": inner_linker or None,
                "classification": "explicit-existing-set-split-context",
                "claim": "The selected linker is used only to parse and validate the submitted FIP/BIP architecture.",
            },
            "preferred_f2_b2_span": list(geometry_profile.preferred_f2_b2_span)
            if geometry_profile.preferred_f2_b2_span is not None
            else None,
            "preferred_outer_gap": list(geometry_profile.preferred_outer_gap)
            if geometry_profile.preferred_outer_gap is not None
            else None,
            "preferred_loop_tm": list(geometry_profile.preferred_loop_tm)
            if geometry_profile.preferred_loop_tm is not None
            else None,
            "f2_b2_span": list(f2_b2_span),
            "loop_span": list(loop_span),
            "outer_gap": list(outer_gap),
            "middle_gap": list(middle_gap),
            "overruled": overruled,
            "why": "Existing set evaluated against this reviewed design envelope; failing an envelope is reported, not silently redesigned.",
        }
        rna_accessibility = _rt_lamp_accessibility(
            template,
            entry,
            wants_rna=wants_rna,
            protocol=protocol,
            fallback_temperature_c=(
                chosen.preset.cycling.isothermal_c or chosen.preset.cycling.extend_c
            ),
        )
        if rna_accessibility is not None:
            entry["rna_target_accessibility"] = rna_accessibility

        answer: dict[str, Any] = {
            "engine": "loop-set",
            "lamp_scenario": lamp_scenario,
            **(
                {
                    "workflow_evidence": {
                        "recorded": True,
                        "decision_impact": "none",
                        "observed": workflow_evidence,
                        "note": "Experimental validation evidence is stored for reproducibility and never changes LAMP set evaluation.",
                    }
                }
                if workflow_evidence is not None
                else {}
            ),
            "mode": "validate-existing",
            "existing_set_validation": existing_audit,
            "readout": {
                "selection": lamp_readout,
                "sequence_decision_impact": "none",
                "note": "Readout is chemistry/provenance evidence and does not alter existing-set sequence evaluation.",
            },
            "reverse_transcription": (
                _rt_lamp_block_for_protocol(lamp_protocol, protocol)
                if rt.wanted(request) and protocol is not None
                else (rt.block(isothermal=True) if rt.wanted(request) else None)
            ),
            "provenance": provenance(reaction),
            "assay": chosen.assay_to_dict(),
            "target": target_to_dict(chosen.target),
            "reaction": {
                "polymerase": chosen.preset.id,
                "polymerase_name": chosen.preset.name,
                **reaction,
                "model": thermodynamic_model(chosen.preset, chosen.reaction),
                "diagnostic_structure_temperature_c": HOLD,
                "context_role": "existing-LAMP-set thermodynamic/interaction validation context",
                "context_note": "No candidate generation occurred; thermodynamic calculations describe the submitted oligos under the declared screening context.",
            },
            **(
                {
                    "protocol": {
                        **{
                            key: value
                            for key, value in protocol.items()
                            if key
                            not in {"role_concentrations_uM", "rt_authority_status", "_protocol_id"}
                        },
                        "readout_compatibility": _readout_compatibility(protocol, lamp_readout),
                        "readout_chemistry_compatibility": _readout_chemistry_compatibility(
                            protocol, lamp_readout, lamp_readout_chemistry
                        ),
                    }
                }
                if protocol is not None
                else {}
            ),
            "parameter_set": parameter_block,
            "target_inclusivity": target_panel_meta,
            "background": background_summary,
            "sets": [entry],
            "considered": {"submitted_sets": 1, "mapped_sets": 1},
            "why_nothing": "",
            "order_sheet": [
                {
                    "name": f"{name}_1_{oligo['name']}",
                    "sequence": oligo["sequence"],
                    "annealing_sequence": oligo["anneals"]["sequence"]
                    if oligo["composite"]
                    else oligo["sequence"],
                    "tail_sequence": oligo["sequence"][: -len(oligo["anneals"]["sequence"])]
                    if oligo["composite"]
                    else "",
                    "lamp_role": oligo["name"],
                    "lamp_set_index": 1,
                    "lamp_target_tail_sequence": oligo.get("target_tail_sequence") or "",
                    "lamp_linker_sequence": oligo.get("linker_sequence") or "",
                    "kind": "primer",
                    "length": oligo["length"],
                    "gc_percent": oligo["gc_percent"],
                    "tm": oligo["anneals"]["tm"] if oligo["composite"] else oligo["tm"],
                    "note": "Existing user-supplied oligo; no redesign occurred.",
                }
                for oligo in entry["oligos"]
            ],
        }
        return answer

    # Stage 1 may use bounded implementation budgets internally, but routed
    # design now accepts results only when that search reports complete. Stage 2
    # therefore reviews every surviving candidate in the requested pool; no
    # proxy/thinned subset is allowed to change primary LAMP selection.
    candidate_pool_size = min(50, max(how_many * 5, 20))

    found, used, counted, search_meta = sets(
        template,
        windows=windows,
        conditions=reaction,
        how_many=candidate_pool_size,
        excluded=excluded_from(request),
        f2_b2_span=f2_b2_span,
        loop_span=loop_span,
        outer_gap=outer_gap,
        middle_gap=middle_gap,
        geometry_profile=geometry_profile,
        inner_linker=inner_linker,
        fixed_primers=fixed_primers,
        mutation_anchor=mutation_anchor,
        include_search_meta=True,
    )

    search_meta["boundary_note"] = (
        "LAMP exact-search boundary exceeded; the returned candidates are bounded-search evidence and "
        "must not be described as an exhaustive search or global optimum."
        if not bool(search_meta.get("complete"))
        else ""
    )

    # Loop-primer architecture is an explicit design decision. Four-primer mode
    # strips optional LF/LB from otherwise valid cores; require-six refuses
    # cores missing either loop. This is candidate architecture, not bench chemistry.
    if lamp_loop_policy == "require-six":
        found = [
            one for one in found if one.forward.loop is not None and one.backward.loop is not None
        ]
    elif lamp_loop_policy == "core-four-only":
        found = [
            replace(
                one,
                forward=replace(one.forward, loop=None),
                backward=replace(one.backward, loop=None),
            )
            for one in found
        ]
    search_meta["lamp_loop_policy"] = lamp_loop_policy
    search_meta["lamp_design_stage"] = lamp_design_stage
    search_meta["mutation_specificity_note"] = (
        "Variant placement is a positional candidate constraint only; no universal LAMP allele-discrimination threshold or secondary mismatch is inferred. Paired WT/MUT empirical validation is required."
        if mutation_anchor
        else None
    )

    described = [
        set_to_dict(
            template,
            one,
            used,
            role_concentrations_uM=role_concentrations_uM,
            geometry_profile=geometry_profile,
            inner_linker=inner_linker,
            **reaction,
        )
        for one in found
    ]
    name = label(chosen.target.name)

    # ── Where else these oligos could sit ───────────────────────────────────
    #
    # This page showed a specificity step and this engine had nowhere to put
    # the answer. LAMP has the most to lose by it: several coordinated oligos across
    # multiple regions create several opportunities to bind elsewhere; the read-out is turbidity
    # or a colour change rather than a band on a gel, and a false positive
    # therefore looks exactly like a true one.
    #
    # The composites are scanned by their 3' half only. FIP reads 5'-F1c-F2-3'
    # and only the F2 half anneals to the template — the F1c tail primes later
    # against a strand that does not exist yet. Searching for the joined
    # sequence would find nothing anywhere, which would read as a clean scan.
    for entry, one in zip(described, found, strict=True):
        named: dict[str, str] = {}
        whole: dict[str, str] = {}
        for oligo in oligos(template, one, inner_linker=inner_linker):
            named[oligo.name] = (
                # The tail is not on the template, so only the segment past it
                # can be found anywhere else.
                oligo.sequence[oligo.tail_length :] if oligo.composite else oligo.sequence
            )
            # The dimer screen measures what gets ordered, which is the whole
            # molecule: a tail that is not on the template still pairs with
            # whatever it finds in the tube.
            whole[oligo.name] = oligo.sequence
        if target_alignment is not None:
            entry["target_inclusivity"] = _target_inclusivity_audit(template, one, target_alignment)
        if generic_direct_background_enabled:
            intended_sizes, intended_products = _lamp_generic_intended_linear_products(
                template, one, template_only=template_only
            )
            entry["off_targets"] = screen.oligos(
                named,
                contigs,
                reaction=chosen.reaction,
                fold_at=fold_at,
                # The generic screen is a linear proxy, not a LAMP product model.
                # On the implicit template-only self-scan, several normal opposing
                # LAMP roles can form linear products; excuse exactly one
                # sequence-identical target-locus copy of each. A supplied LAMP
                # background is an exclusion panel, so it receives no intended
                # exemptions at all: every compatible site/product remains visible.
                max_product=screen.product_ceiling(one.size),
                intended_sizes=intended_sizes,
                intended_products=intended_products,
                temperature_c=(
                    chosen.preset.cycling.isothermal_c or chosen.preset.cycling.extend_c
                ),
            )
        else:
            entry["off_targets"] = _indexed_specificity_required(background_bases)
        entry["interactions"] = interactions(
            whole, role_concentrations_uM=role_concentrations_uM, **reaction
        )

    # Final, bounded stage-2 selection. First rank every candidate by the
    # evidence available cheaply for that already-generated set. For supplied
    # finite backgrounds small enough for direct LAMP topology review, evaluate
    # a bounded mix of the preliminary best and spatially diverse candidates,
    # then make the six-region topology risk class the primary background key.
    # For genome-scale backgrounds, do not pretend the direct matcher ran: the
    # indexed external validator is the appropriate evidence layer.
    paired = list(zip(found, described, strict=True))
    candidate_pool_evaluated = len(paired)

    def preliminary_key(pair: tuple[Set, dict[str, Any]]) -> tuple[Any, ...]:
        entry = pair[1]
        inclusivity = (
            _inclusivity_rank(entry.get("target_inclusivity"))
            if target_alignment is not None and lamp_design_intent == "panel-conservation-aware"
            else ()
        )
        return (*inclusivity, *_thermodynamic_structure_rank(entry))

    paired.sort(key=preliminary_key)
    topology_background_bases = background_bases
    topology_enabled = (
        not template_only
        and topology_background_bases <= LAMP_TOPOLOGY_DIRECT_MAX_BASES
        and bool(paired)
    )
    topology_pool_requested = 0
    topology_pool_evaluated = 0
    if topology_enabled:
        # Evaluate every surviving candidate. Earlier revisions selected a bounded
        # mix of preliminary-best and spatially diverse sets for topology review;
        # that approximation could prevent an unmeasured set from winning. The
        # stage-1 search now refuses if it had to truncate, so this bounded pool
        # is small enough to review completely.
        topology_pool_requested = len(paired)
        for one, entry in paired:
            entry["lamp_background_topology"] = _lamp_background_topology_audit(
                template,
                one,
                contigs,
                f2_b2_span=f2_b2_span,
                loop_span=loop_span,
                outer_gap=outer_gap,
                middle_gap=middle_gap,
            )
        topology_pool_evaluated = len(paired)
    elif not template_only:
        # The direct model was intentionally not applied at this scope. Preserve
        # the fact on every candidate that remains eligible for generic/external
        # ranking so a missing topology result cannot render as a clean result.
        reason = {
            "checked": False,
            "risk_class": 1,
            "classification": "indexed-validation-required",
            "background_bases": topology_background_bases,
            "direct_limit_bases": LAMP_TOPOLOGY_DIRECT_MAX_BASES,
            "claim": (
                "Genome-scale six-region topology was not evaluated by the direct matcher; "
                "indexed external validation is required before a genome-wide LAMP-specificity claim."
            ),
        }
        for _, entry in paired:
            entry["lamp_background_topology"] = dict(reason)

    def stage2_key(pair: tuple[Set, dict[str, Any]]) -> tuple[Any, ...]:
        entry = pair[1]
        inclusivity = (
            _inclusivity_rank(entry.get("target_inclusivity"))
            if target_alignment is not None and lamp_design_intent == "panel-conservation-aware"
            else ()
        )
        topology = (
            _lamp_topology_rank(entry.get("lamp_background_topology")) if not template_only else ()
        )
        return (*inclusivity, *topology, *_thermodynamic_structure_rank(entry))

    paired.sort(key=stage2_key)
    paired = paired[:how_many]
    found = [pair[0] for pair in paired]
    described = [pair[1] for pair in paired]
    if wants_rna:
        fallback_temperature_c = (
            chosen.preset.cycling.isothermal_c or chosen.preset.cycling.extend_c
        )
        for entry in described:
            entry["rna_target_accessibility"] = _rt_lamp_accessibility(
                template,
                entry,
                wants_rna=True,
                protocol=protocol,
                fallback_temperature_c=fallback_temperature_c,
            )

    search_meta["stage2_selection"] = {
        "candidate_pool_requested": candidate_pool_size,
        "candidate_pool_evaluated": candidate_pool_evaluated,
        "topology_direct_enabled": topology_enabled,
        "topology_direct_background_limit_bases": LAMP_TOPOLOGY_DIRECT_MAX_BASES,
        "topology_pool_requested": topology_pool_requested,
        "topology_pool_evaluated": topology_pool_evaluated,
        "topology_pool_strategy": (
            "all-stage1-candidates-exactly-reviewed"
            if topology_enabled
            else "not-run-use-indexed-validator-at-this-scope"
        ),
        "final_count": len(described),
        "background_aware": (
            not template_only and (topology_enabled or generic_direct_background_enabled)
        ),
        "generic_direct_background_enabled": (
            not template_only and generic_direct_background_enabled
        ),
        "generic_direct_background_limit_bases": LAMP_GENERIC_DIRECT_MAX_BASES,
        "target_inclusivity_provided": target_alignment is not None,
        "target_inclusivity_aware": target_alignment is not None
        and lamp_design_intent == "panel-conservation-aware",
        "rank_fields": (
            (
                [
                    "inner_terminal_3_events",
                    "inner_events",
                    "loop_terminal_3_events",
                    "loop_events",
                    "outer_terminal_3_events",
                    "outer_events",
                ]
                if target_alignment is not None and lamp_design_intent == "panel-conservation-aware"
                else []
            )
            + (
                [
                    "lamp_six_region_risk_class",
                    "lamp_exact_compatible_locus_count_lower_bound",
                    "lamp_terminal_intact_compatible_locus_count_lower_bound",
                ]
                if not template_only
                else []
            )
            + [
                "pairwise_structure_evidence_incomplete",
                "max_pair_interaction_tm",
                "max_self_dimer_tm",
                "max_hairpin_tm",
                "most_favourable_pair_dg",
            ]
        ),
        "classification": "hierarchical-evidence-ranking-no-universal-structure-gate",
        "claim": (
            "Target conservation, when supplied, ranks first. For finite backgrounds within the direct "
            "scope, LAMP-native six-region topology ranks candidates; the generic linear off-target screen is diagnostic-only and never changes selection. "
            "Ordered-oligo structure breaks remaining ties. Larger backgrounds are not rescanned per candidate; "
            "their direct specificity state remains unresolved until indexed validation and therefore does not "
            "participate in candidate ranking. None of these layers is an empirical assay-success probability."
        ),
    }
    # Keep the older key for consumers that already display it.
    background_rank_enabled = not template_only and topology_enabled
    search_meta["background_aware_selection"] = {
        "enabled": background_rank_enabled,
        "candidate_pool_requested": candidate_pool_size,
        "candidate_pool_evaluated": candidate_pool_evaluated,
        "topology_direct_enabled": topology_enabled,
        "generic_direct_enabled": (not template_only and generic_direct_background_enabled),
        "generic_direct_decision_impact": "diagnostic-only",
        "final_count": len(described),
        "rank_fields": (["lamp_six_region_risk_class"] if topology_enabled else []),
        "classification": (
            "lamp-six-region-background-ranking-linear-proxy-diagnostic-only"
            if background_rank_enabled
            else (
                "indexed-validation-required-before-background-aware-selection"
                if not template_only
                else "not-applicable"
            )
        ),
        "claim": (
            "Finite supplied backgrounds use a LAMP-specific six-region positional model for candidate selection; "
            "the generic linear site/product proxy is diagnostic-only. Larger backgrounds are intentionally not rescanned set-by-set: "
            "candidate selection is not genome-wide-specificity-ranked at that scope, and the indexed external "
            "validator must provide the specificity evidence without a fabricated clean result."
            if not template_only
            else "no supplied exclusion background"
        ),
    }

    background_summary = screen.summary(contigs, template_only, fold_at=fold_at)
    background_summary["sequence_topology_assumption"] = "linear-sequence-records"
    background_summary["topology_note"] = (
        "Finite FASTA/plain-sequence background records are scanned as linear records. "
        "Origin-spanning loci on circular molecules are not covered unless the supplied "
        "representation explicitly includes that junction; no circular-cleanliness claim is made."
    )

    return {
        "engine": "loop-set",
        "lamp_scenario": lamp_scenario,
        **({"modified_oligos": modified_oligos} if modified_oligos is not None else {}),
        **(
            {
                "workflow_evidence": {
                    "recorded": True,
                    "decision_impact": "none",
                    "observed": workflow_evidence,
                    "note": "Experimental validation evidence is stored for reproducibility and never changes LAMP set ranking.",
                }
            }
            if workflow_evidence is not None
            else {}
        ),
        "readout": {
            "selection": lamp_readout,
            "sequence_decision_impact": "none",
            "note": (
                "Readout is explicit provenance because fluorescence, colorimetric and turbidity "
                "chemistries have different instrumentation/control implications. It does not "
                "replace empirical positivity thresholds or target-specific validation."
            ),
        },
        # A property of the run rather than of a design: the same hold, at the
        # same temperature, whichever candidate you pick. `None` says the
        # question was never put — this assay's page does not ask it.
        "reverse_transcription": (
            _rt_lamp_block_for_protocol(lamp_protocol, protocol)
            if rt.wanted(request) and protocol is not None
            else (rt.block(isothermal=True) if rt.wanted(request) else None)
        ),
        "provenance": provenance(reaction),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **reaction,
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
            "diagnostic_structure_temperature_c": HOLD,
            "context_role": (
                "generic Bst structure-diagnostic model with named-protocol role concentrations"
                if role_concentrations_uM
                else "generic Bst structure-diagnostic model; no named protocol selected"
            ),
            "oligo_concentration_model": (
                "role-specific for single-oligo diagnostics; common-concentration for pairwise Primer3 heterodimers"
                if role_concentrations_uM
                else "single representative concentration because no named LAMP protocol was selected"
            ),
            "context_note": (
                f"{HOLD} °C and the generic Bst preset ionic conditions are used only for temperature-dependent "
                "ordered-oligo structure diagnostics. A named protocol contributes its reviewed role-specific "
                "oligo concentrations when available, but PCRStudio does not infer proprietary master-mix ionic "
                "composition. PrimerExplorer role eligibility/Tm ranking uses the separate versioned reference "
                "model reported under parameter_set. A bench hold is authoritative only when the named protocol "
                "supplies it."
            ),
        },
        **(
            {
                "protocol": {
                    **{
                        key: value
                        for key, value in protocol.items()
                        if key
                        not in {"role_concentrations_uM", "rt_authority_status", "_protocol_id"}
                    },
                    "readout_compatibility": _readout_compatibility(protocol, lamp_readout),
                    "readout_chemistry_compatibility": _readout_chemistry_compatibility(
                        protocol, lamp_readout, lamp_readout_chemistry
                    ),
                }
            }
            if protocol is not None
            else {}
        ),
        "parameter_set": {
            "id": used.id,
            "name": used.name,
            "thermodynamic_model": PE_THERMODYNAMIC_MODEL,
            "chosen_from": (
                "explicit request"
                if request.get("parameter_set")
                else (
                    "PrimerExplorer V5 Automatic Judgment from whole-target composition, "
                    + (
                        f"{target_gc_interval(template)[0]:.2f}% GC"
                        if target_gc_interval(template)[0] == target_gc_interval(template)[1]
                        else (
                            f"{target_gc_interval(template)[0]:.2f}–"
                            f"{target_gc_interval(template)[1]:.2f}% possible GC under IUPAC ambiguity"
                        )
                    )
                )
            ),
            "outer": {
                "tm": [used.outer.tm_min, used.outer.tm_max],
                "length": [used.outer.length_min, used.outer.length_max],
            },
            "inner": {
                "tm": [used.inner.tm_min, used.inner.tm_max],
                "length": [used.inner.length_min, used.inner.length_max],
            },
            "loop": {
                "tm": [used.loop.tm_min, used.loop.tm_max],
                "length": [used.loop.length_min, used.loop.length_max],
            },
            "gc": [used.gc_min, used.gc_max],
            "regular_primer_gc": [used.gc_min, used.gc_max],
            "loop_primer_gc": [LOOP_GC_MIN, LOOP_GC_MAX],
            "terminal_stability": {
                "window_bases": END_BASES,
                "regular_critical_max_dg_kcal_mol": END_STABILITY,
                "loop_3p_max_dg_kcal_mol": LOOP_END_STABILITY,
                "regular_scope": "F2/B2/F3/B3 3-prime and F1c/B1c 5-prime critical ends",
                "loop_scope": "LF/LB 3-prime ends using the separate PrimerExplorer V5 loop-primer screen",
                "classification": "source-scoped-hard-candidate-gates",
            },
            "geometry_profile": {
                "id": geometry_profile.id,
                "name": geometry_profile.name,
                "source": geometry_profile.source,
                "claim": geometry_profile.claim,
                "valid_f2_b2_span": list(geometry_profile.valid_f2_b2_span),
                "valid_loop_span": list(geometry_profile.valid_loop_span),
                "valid_outer_gap": list(geometry_profile.valid_outer_gap),
                "valid_middle_gap": list(geometry_profile.valid_middle_gap),
                "preferred_f2_b2_span": (
                    list(geometry_profile.preferred_f2_b2_span)
                    if geometry_profile.preferred_f2_b2_span is not None
                    else None
                ),
                "preferred_outer_gap": (
                    list(geometry_profile.preferred_outer_gap)
                    if geometry_profile.preferred_outer_gap is not None
                    else None
                ),
                "preferred_loop_tm": (
                    list(geometry_profile.preferred_loop_tm)
                    if geometry_profile.preferred_loop_tm is not None
                    else None
                ),
            },
            "inner_linker": {
                "id": inner_linker_id,
                "sequence": inner_linker or None,
                "classification": "explicit-design-variant-not-universal-default",
                "claim": (
                    "The TTTT option is literature-backed as a tested LAMP inner-primer junction variant, "
                    "not a universal performance guarantee."
                    if inner_linker
                    else "No synthetic FIP/BIP junction linker requested."
                ),
            },
            "preferred_f2_b2_span": (
                list(geometry_profile.preferred_f2_b2_span)
                if geometry_profile.preferred_f2_b2_span is not None
                else None
            ),
            "preferred_outer_gap": (
                list(geometry_profile.preferred_outer_gap)
                if geometry_profile.preferred_outer_gap is not None
                else None
            ),
            "preferred_loop_tm": (
                list(geometry_profile.preferred_loop_tm)
                if geometry_profile.preferred_loop_tm is not None
                else None
            ),
            "f2_b2_span": list(f2_b2_span),
            "loop_span": list(loop_span),
            "outer_gap": list(outer_gap),
            "middle_gap": list(middle_gap),
            # Which numbers above are somebody's rather than the literature's.
            # A set reported without this reads as published guidance whatever
            # was typed over it, and the temperatures in it are thermodynamic/search windows, not an automatically generated bench hold.
            "overruled": overruled,
            "why": (
                used.why
                if not overruled
                else (
                    used.why
                    + " Adjusted here: "
                    + ", ".join(overruled)
                    + ". Those are yours rather than the published set's, so the "
                    "windows quoted are not the ones the isothermal literature "
                    "states for this composition."
                )
            ),
        },
        # Intended-target conservation and exclusion specificity are reported
        # separately so one cannot be mistaken for the other.
        "target_inclusivity": target_panel_meta,
        # How far the exclusion scan looked, said once rather than implied per set.
        "background": background_summary,
        "sets": described,
        "considered": counted,
        "search": search_meta,
        "why_nothing": _why_nothing(counted, used),
        "order_sheet": [
            {
                "name": f"{name}_{index}_{oligo['name']}",
                "sequence": oligo["sequence"],
                "annealing_sequence": (
                    oligo["anneals"]["sequence"] if oligo["composite"] else oligo["sequence"]
                ),
                "tail_sequence": (
                    oligo["sequence"][: -len(oligo["anneals"]["sequence"])]
                    if oligo["composite"]
                    else ""
                ),
                "lamp_role": oligo["name"],
                "lamp_set_index": index,
                "lamp_target_tail_sequence": oligo.get("target_tail_sequence") or "",
                "lamp_linker_sequence": oligo.get("linker_sequence") or "",
                "kind": "primer",
                "length": oligo["length"],
                "gc_percent": oligo["gc_percent"],
                "tm": (oligo["anneals"]["tm"] if oligo["composite"] else oligo["tm"]),
                "note": (
                    "The temperature quoted is the template-binding half's, not the whole oligo's."
                    if oligo["composite"]
                    else ""
                ),
            }
            for index, entry in enumerate(described, start=1)
            for oligo in entry["oligos"]
        ],
    }


#: The most sets one request may ask for.
MAX_WORKFLOW_EVIDENCE_FIELDS = 64
MAX_WORKFLOW_EVIDENCE_KEY_CHARS = 80
MAX_WORKFLOW_EVIDENCE_TEXT_CHARS = 8_000

MOST_SETS = 10


def _tm_envelope(window: Window) -> str:
    if window.tm_min is None:
        return f"at or below {window.tm_max} °C"
    if window.tm_max is None:
        return f"at or above {window.tm_min} °C"
    return f"between {window.tm_min} and {window.tm_max} °C"


def _why_nothing(counted: dict[str, int], windows: Windows) -> str:
    """Which stage ran out, rather than only that something did.

    Six roles have to be filled and then fitted together, so "nothing found"
    can mean six different things. Saying which one stopped is the difference
    between a template that cannot take a LAMP set and a window that was a few
    degrees too narrow.
    """
    if counted["joined"]:
        return ""
    outer_count = counted.get("outer_regions", 0) or (
        counted.get("forward_outer_regions", 0) + counted.get("backward_outer_regions", 0)
    )
    inner_count = counted.get("inner_regions", 0) or (
        counted.get("forward_inner_regions", 0) + counted.get("backward_inner_regions", 0)
    )
    if not outer_count:
        return (
            "No stretch of this template could serve as an outer region under the "
            f"{windows.name} parameter set — nothing melted {_tm_envelope(windows.outer)} "
            "at an acceptable "
            "length with a 3' end that holds. That is the first of six roles, so "
            "nothing else was tried."
        )
    if not inner_count:
        return (
            "No stretch could serve as a stem. The stems run warmer than the outer "
            f"regions — {_tm_envelope(windows.inner)} — and this "
            "template does not reach that anywhere at an acceptable length."
        )
    if not counted["forward_halves"] or not counted["backward_halves"]:
        side = "forward" if not counted["forward_halves"] else "backward"
        return (
            f"Regions exist for every role, but none of them line up into a {side} "
            "half: no stem sits the right distance from an outer region to make a "
            "loop of the length required. The spacing rather than the sequence is "
            "what failed."
        )
    return (
        "Both halves exist but none of them fit together into a whole set — every "
        "pairing was either overlapping or outside the amplicon length allowed. "
        "Widening the product range is what usually helps."
    )
