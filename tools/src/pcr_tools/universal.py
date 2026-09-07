"""Designing one pair that fits a family, from an alignment of it.

Primer3 cannot do this. It searches one template for one primer, and what is
wanted here is a mixture that fits every sequence in an alignment at once. So
the search is ours, and it is a different search:

Primer3 slides a window over a sequence and scores it. This slides a window
over an **alignment column set** and asks what mixture would cover every
sequence there — then rejects the window if that mixture is too large, if its
3' end varies, or if its melting temperature spreads too far across the
variants. The thermodynamics are still Primer3's, computed on concrete members
of the mixture, so a temperature quoted here means the same thing it means
everywhere else in PCRStudio.

Three rules do most of the work, and each of them throws away far more windows
than the ordinary length and GC filters do:

- **A degeneracy budget.** Every variable position multiplies the number of
  concrete oligo members represented by an IUPAC mixture. Member abundance in
  a synthesized mixture is vendor/formulation dependent and is not inferred.
- **A conserved 3' end policy.** Terminal mismatches are especially consequential,
  so this reviewed profile avoids ambiguity at the extending end. A degenerate
  base is not itself a mismatch -- the mixture can contain a perfectly matched
  member -- and the number of conserved bases is a profile choice, not a
  universal polymerase law.
- **A melting-temperature spread.** The annealing temperature has to suit the
  whole mixture, so the gap between its coolest and warmest member matters more
  than its average does.

What comes out is reported with the coverage it actually achieves, measured
against the sequences that were supplied rather than assumed from how it was
built.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import primer3

from .consensus import GAPS
from .degenerate import (
    DEFAULT_CONSERVED_END,
    DEFAULT_MAX_DEGENERACY,
    EXPANSION,
    code_for,
    expand,
    gc_range,
    longest_run,
    matches,
    reverse_complement,
)
from .fetch import NUCLEIC_ALPHABET
from .presets import Reaction, purpose
from .scientific_integrity import enforce_constraint_overrides

#: The largest concrete mixture this worker will evaluate exactly. The profile
#: baseline is 64-fold, so this is a computational guard rather than a
#: biological recommendation. Approximate extrema are deliberately not used:
#: nearest-neighbour Tm and structure values are sequence-order dependent, and
#: a heuristic representative can understate a rejection criterion.
MAX_EXACT_VARIANTS = 4_096

#: Primer-length guard for the exact degenerate-family search. This is a
#: computational/search boundary, not a claim that longer synthesized oligos
#: are biologically invalid.
MAX_DEGENERATE_PRIMER_LENGTH = 60

#: How many alignments this will search before refusing. A hundred sequences of
#: a few kilobases is a large gene family; more than that wants an indexed
#: approach and a different conversation.
MAX_SEQUENCES = 200
MAX_COLUMNS = 20_000

#: Exact-search computational bounds. These are refusal boundaries, never
#: thinning heuristics. If an input exceeds them PCRStudio refuses the request
#: rather than silently discarding candidates with an approximate pre-score.
MAX_SITES_EACH_WAY = 1_500
MAX_EXACT_PAIR_EVALUATIONS = 100_000

UNIVERSAL_INTEGER_FIELDS = frozenset(
    {
        "length_min",
        "length_opt",
        "length_max",
        "product_min",
        "product_max",
        "max_degeneracy",
        "conserved_end",
        "max_poly_x",
        "min_three_prime_distance",
    }
)


class AlignmentError(ValueError):
    """Sequences this cannot design from, with a reason a person can act on."""


@dataclass(frozen=True)
class Limits:
    """What a degenerate primer has to satisfy."""

    length_min: int = 18
    length_opt: int = 21
    length_max: int = 26

    tm_min: float = 52.0
    tm_max: float = 66.0
    #: Reference spread for the mixture's concrete-member Tm range. This is a
    #: profile/ranking diagnostic, not a chemistry-independent validity gate.
    tm_spread_max: float = 5.0
    #: Reference gap between the two primers' coolest members. This is a
    #: ranking/search-quality reference, not a chemistry-independent validity
    #: gate: final shared-annealing suitability is protocol specific.
    tm_pair_max_difference: float = 4.0

    gc_min: float = 35.0
    gc_max: float = 70.0

    product_min: int = 200
    product_max: int = 1500

    #: Distinct molecules the mixture may hold.
    max_degeneracy: int = DEFAULT_MAX_DEGENERACY
    #: Bases at the 3' end that must be identical in every sequence.
    conserved_end: int = DEFAULT_CONSERVED_END
    #: How much of each column a mixture has to account for.
    #:
    #: One means every base seen there, whatever it costs in degeneracy. Below
    #: one, the commonest bases are taken until they add up to this share and
    #: the rest are left out — so 0.9 means "ignore a variant so rare that
    #: dropping it costs a tenth of the sequences at that position".
    #:
    #: Per column, which is not the same as per sequence: one sequence can be
    #: the odd one out in several columns at once. That is why coverage is
    #: measured on the finished primer rather than inferred from this.
    min_coverage: float = 1.0

    max_poly_x: int = 4
    #: How far apart two candidates' 3' ends must be to count as different.
    min_three_prime_distance: int = 5

    def validate(self) -> None:
        """Reject combinations that cannot hold.

        Raises:
            ValueError: naming the two numbers that disagree.
        """
        for name in self.__dataclass_fields__:
            current = getattr(self, name)
            if isinstance(current, bool) or not isinstance(current, (int, float)):
                raise ValueError(f"constraint `{name}` must be a finite number")
            if not math.isfinite(float(current)):
                raise ValueError(f"constraint `{name}` must be finite, not {current!r}")
            if name in UNIVERSAL_INTEGER_FIELDS and not isinstance(current, int):
                raise ValueError(f"constraint `{name}` must be an integer, not {current!r}")

        if self.length_min < 1:
            raise ValueError("a primer is at least one base long")
        if not self.length_min <= self.length_opt <= self.length_max:
            raise ValueError(
                f"the ideal primer length ({self.length_opt}) is outside the range "
                f"asked for, {self.length_min} to {self.length_max}"
            )
        if self.length_max > MAX_DEGENERATE_PRIMER_LENGTH:
            raise ValueError(f"a degenerate primer cannot exceed {MAX_DEGENERATE_PRIMER_LENGTH} bases in this search")
        if self.length_min > self.length_max:
            raise ValueError(
                f"the shortest primer ({self.length_min}) is longer than the "
                f"longest ({self.length_max})"
            )
        if self.tm_min > self.tm_max:
            raise ValueError(
                f"the lowest melting temperature ({self.tm_min} C) is above the "
                f"highest ({self.tm_max} C)"
            )
        if self.gc_min > self.gc_max:
            raise ValueError(
                f"the lowest GC ({self.gc_min}%) is above the highest ({self.gc_max}%)"
            )
        if self.product_min > self.product_max:
            raise ValueError(
                f"the shortest product ({self.product_min} bp) is longer than the "
                f"longest ({self.product_max} bp)"
            )
        # Do not reject a whole product window merely because its lower edge
        # cannot accommodate two *maximum-length* primers.  Primer3 is free to
        # choose shorter primers and/or a larger product within the requested
        # range; the old check turned one impossible corner of a valid search
        # space into a request-level scientific refusal.  Pair geometry remains
        # a candidate-level constraint owned by the actual search engine.
        if self.max_degeneracy < 1:
            raise ValueError("a mixture holds at least one molecule")
        if self.max_degeneracy > MAX_EXACT_VARIANTS:
            raise ValueError(
                f"a mixture of {self.max_degeneracy} molecules exceeds the "
                f"{MAX_EXACT_VARIANTS}-member exact thermodynamic limit"
            )
        if self.tm_spread_max < 0:
            raise ValueError("a melting-temperature spread cannot be negative")
        if self.tm_pair_max_difference < 0:
            raise ValueError("two degenerate primers cannot differ by less than nothing")
        if not (0 <= self.gc_min and self.gc_max <= 100):
            raise ValueError("GC content is a percentage, so it lies between 0 and 100")
        if self.conserved_end < 0:
            raise ValueError("the conserved 3-prime end cannot be negative")
        if self.conserved_end >= self.length_min:
            raise ValueError(
                f"asking for {self.conserved_end} conserved bases at the 3' end of a "
                f"primer only {self.length_min} bases long leaves nothing to vary"
            )
        if not 0 < self.min_coverage <= 1:
            raise ValueError("the coverage target is a share between zero and one")
        if self.max_poly_x < 1:
            raise ValueError("the longest allowed run of one base must be at least 1")
        if self.min_three_prime_distance < -1:
            raise ValueError(
                "the 3-prime distance cannot be less than -1, which is the "
                "tool's explicit off value"
            )


def limits_from_request(request: dict[str, Any]) -> Limits:
    """Resolve purpose, profile and caller constraints for a family design.

    Universal design has a richer constraint type than the ordinary pair
    worker, so it cannot use :func:`settings.prepare` directly. It still needs
    the same precedence rule: downstream purpose first, assay profile second,
    and explicit request values last. Without this boundary, a profiled
    ``universal-primers`` request silently fell back to ``Limits`` dataclass
    defaults while the ordinary-pair profiles received their declared values.
    """
    assay = request.get("assay") or {}
    if not isinstance(assay, dict):
        raise ValueError("`assay` must be an object")
    defaults = assay.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ValueError("`assay.defaults` must be an object")

    allowed_value = defaults.get("purposes") or []
    if not isinstance(allowed_value, list) or not all(
        isinstance(entry, str) for entry in allowed_value
    ):
        raise ValueError("`assay.defaults.purposes` must be a list of names")
    requested = request.get("purpose") or defaults.get("defaultPurpose")
    if requested and allowed_value and requested not in allowed_value:
        name = assay.get("name") or assay.get("id") or "this assay"
        raise ValueError(
            f"{name} cannot be used for `{requested}`. It serves: "
            + ", ".join(sorted(allowed_value))
            + "."
        )

    profile_constraints = defaults.get("constraints") or {}
    if not isinstance(profile_constraints, dict):
        raise ValueError("`assay.defaults.constraints` must be an object")
    supplied = request.get("constraints") or {}
    if not isinstance(supplied, dict):
        raise ValueError("`constraints` must be an object")
    known = set(Limits.__dataclass_fields__)
    unknown = sorted((set(profile_constraints) | set(supplied)) - known)
    if unknown:
        raise ValueError(f"unknown constraint(s): {', '.join(unknown)}")
    baseline = {
        **purpose(requested).constraints,
        **profile_constraints,
    }
    # Universal design has its own richer Limits type, but Scientific-Strict
    # must still enforce the same profile-envelope semantics as the shared
    # Settings path. A direct caller may tighten a reviewed envelope; widening
    # or changing an unclassified decision constant requires a new versioned
    # profile rather than an anonymous request override.
    policies = defaults.get("constraintPolicy") or {}
    if policies is not None and not isinstance(policies, dict):
        raise ValueError("`assay.defaults.constraintPolicy` must be an object")
    envelopes = defaults.get("constraintEnvelope") or {}
    if not isinstance(envelopes, dict):
        raise ValueError("`assay.defaults.constraintEnvelope` must be an object")
    enforce_constraint_overrides(
        supplied,
        baseline,
        policies=policies or {},
        envelopes=envelopes,
        context=f"{assay.get('id') or 'universal-primer'} profile",
    )
    return Limits(**{**baseline, **supplied})


@dataclass(frozen=True)
class Site:
    """One degenerate primer, and everything measured about it."""

    #: The mixture, written in IUPAC.
    sequence: str
    #: Zero-based position of its 5' base on the alignment.
    start: int
    length: int
    #: Which way it would extend.
    orientation: str
    #: How many distinct molecules it holds.
    degeneracy: int
    #: Melting temperature of the coolest and warmest members.
    tm_min: float
    tm_max: float
    gc_min: float
    gc_max: float
    #: How many of the supplied sequences it actually matches.
    covers: int
    #: Hairpin free energy of its most stable member, kcal/mol.
    hairpin_dg: float
    #: Nominal Primer3 effective concentration used for each concrete member's
    #: Tm under the equal-member screening model. This is not a measured
    #: synthesis ratio or initial bench concentration.
    tm_member_dna_conc_nM: float

    @property
    def tm_spread(self) -> float:
        return round(self.tm_max - self.tm_min, 1)

    @property
    def three_prime_at(self) -> int:
        """Zero-based position of the base extension starts from."""
        return self.start + self.length - 1 if self.orientation == "forward" else self.start


@dataclass
class Alignment:
    """The sequences, their panel weights/strata, and what the columns look like."""

    names: list[str]
    rows: list[str]
    #: Bases seen in each column, after the declared consensus policy.
    columns: list[frozenset[str]]
    #: Columns holding a gap in any sequence. No primer may cross one.
    gapped: set[int]
    #: User-declared relative weights. These are panel weights, not inferred population prevalence.
    weights: list[float] = field(default_factory=list)
    #: Optional user-declared strata used only by the explicit stratified policy.
    strata: list[str] = field(default_factory=list)
    policy: str = "strict-all-members"

    @property
    def depth(self) -> int:
        return len(self.rows)

    @property
    def width(self) -> int:
        return len(self.columns)


def read_alignment(
    records: list[tuple[str, str]],
    *,
    min_coverage: float = 1.0,
    policy: str = "strict-all-members",
    weights: dict[str, float] | None = None,
    strata: dict[str, str] | None = None,
) -> Alignment:
    """Turn records into columns, refusing anything that is not an alignment.

    Raises:
        AlignmentError: for fewer than two sequences, unequal lengths, or more
            than this is willing to search.
    """
    allowed_policies = {"strict-all-members", "coverage-threshold", "majority", "weighted", "stratified"}
    if policy not in allowed_policies:
        raise AlignmentError("consensus policy must be one of: " + ", ".join(sorted(allowed_policies)))
    supplied_weights = weights or {}
    supplied_strata = strata or {}

    rows: list[str] = []
    for index, (_, sequence) in enumerate(records, start=1):
        if not isinstance(sequence, str):
            raise AlignmentError(f"sequence {index} is not text")
        row = "".join(c for c in sequence.upper() if not c.isspace()).replace("U", "T")
        invalid = sorted(set(row) - NUCLEIC_ALPHABET)
        if invalid:
            raise AlignmentError(
                f"sequence {index} contains invalid symbol(s): "
                + ", ".join(repr(symbol) for symbol in invalid)
            )
        rows.append(row)
    names = [name for name, _ in records]
    keep = [i for i, row in enumerate(rows) if row]
    rows = [rows[i] for i in keep]
    names = [names[i] for i in keep]
    row_weights = [float(supplied_weights.get(name, 1.0)) for name in names]
    if any((not math.isfinite(weight)) or weight <= 0 for weight in row_weights):
        raise AlignmentError("all supplied panel weights must be finite positive numbers")
    row_strata = [str(supplied_strata.get(name, "unstratified")) for name in names]
    if policy == "stratified" and (not supplied_strata or any(name not in supplied_strata for name in names)):
        raise AlignmentError("stratified consensus policy requires a declared stratum for every alignment record")

    if len(rows) < 2:
        raise AlignmentError(
            "Designing one pair for a family needs at least two sequences. "
            "For a single sequence, Standard PCR is the module."
        )
    if len(rows) > MAX_SEQUENCES:
        raise AlignmentError(
            f"{len(rows)} sequences were given and this searches up to {MAX_SEQUENCES}."
        )

    lengths = {len(row) for row in rows}
    if len(lengths) > 1:
        raise AlignmentError(
            f"These {len(rows)} sequences are {min(lengths)} to {max(lengths)} bases long, "
            "so they have not been aligned. A degenerate primer is built from what sits in "
            "the same column of an alignment; without one there are no columns. Align them "
            "first — MAFFT, MUSCLE and Clustal all do it — and paste the result."
        )
    if lengths and max(lengths) > MAX_COLUMNS:
        raise AlignmentError(
            f"The alignment is {max(lengths)} columns and this searches up to {MAX_COLUMNS}."
        )

    columns: list[frozenset[str]] = []
    gapped: set[int] = set()
    depth = len(rows)

    def chosen_bases(index: int) -> frozenset[str]:
        has_gap = False
        # Each ambiguous code conservatively contributes its full row weight to
        # every concrete base it could represent. This can only widen a
        # degenerate column; it cannot create false precision.
        global_counts: dict[str, float] = {}
        strata_counts: dict[str, dict[str, float]] = {}
        strata_total: dict[str, float] = {}
        for row, weight, stratum in zip(rows, row_weights, row_strata, strict=True):
            base = row[index]
            if base in GAPS:
                has_gap = True
                continue
            expanded = base if base in "ACGT" else EXPANSION.get(base, "ACGT")
            strata_total[stratum] = strata_total.get(stratum, 0.0) + weight
            bucket = strata_counts.setdefault(stratum, {})
            for widened in expanded:
                global_counts[widened] = global_counts.get(widened, 0.0) + weight
                bucket[widened] = bucket.get(widened, 0.0) + weight
        if has_gap:
            gapped.add(index)
        if not global_counts:
            return frozenset({"A", "C", "G", "T"})
        if policy == "strict-all-members":
            return frozenset(global_counts)
        threshold = 0.5 if policy == "majority" else min_coverage
        if policy == "stratified":
            kept: set[str] = set()
            for stratum, counts in strata_counts.items():
                wanted = threshold * strata_total.get(stratum, 0.0)
                running = 0.0
                for base, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                    kept.add(base); running += count
                    if running >= wanted:
                        break
            return frozenset(kept or global_counts)
        if policy == "weighted":
            wanted = threshold * sum(row_weights)
        else:
            # coverage-threshold is deliberately record-count based.
            global_counts = {base: float(sum(1 for row in rows if base in (row[index] if row[index] in "ACGT" else EXPANSION.get(row[index], "ACGT")))) for base in global_counts}
            wanted = threshold * depth
        kept: set[str] = set(); running = 0.0
        for base, count in sorted(global_counts.items(), key=lambda item: (-item[1], item[0])):
            kept.add(base); running += count
            if running >= wanted:
                break
        return frozenset(kept or global_counts)

    for index in range(len(rows[0])):
        columns.append(chosen_bases(index))

    return Alignment(names=names, rows=rows, columns=columns, gapped=gapped, weights=row_weights, strata=row_strata, policy=policy)


@lru_cache(maxsize=4096)
def _concrete_variants(primer: str) -> tuple[str, ...]:
    """Return every concrete oligo in a bounded mixture exactly once."""
    return tuple(expand(primer.upper(), limit=MAX_EXACT_VARIANTS))


def _tm_bounds(primer: str, reaction: Reaction) -> tuple[float, float, float]:
    """Tm extrema under a disclosed nominal equal-member concentration model.

    Primer3's ``dna_conc`` is an empirical effective concentration for *each*
    annealing oligo. A degenerate IUPAC primer represents multiple concrete
    oligos, so assigning the whole pool's value to every member overstates the
    concentration model for higher-degeneracy candidates. For the screening
    calculation we divide the profile's effective pool reference equally among
    the concrete members. Standard mixed-base synthesis can deviate from equal
    composition, so this remains a calculation assumption rather than a claim
    about the delivered oligo pool.
    """
    variants = _concrete_variants(primer)
    member_conc = reaction.dna_conc / len(variants)
    conditions = reaction.as_conditions()
    conditions["dna_conc"] = member_conc
    temperatures = [primer3.calc_tm(variant, **conditions) for variant in variants]

    return round(min(temperatures), 1), round(max(temperatures), 1), round(member_conc, 6)


def _hairpin_dg(primer: str, reaction: Reaction) -> float:
    """Return the most stable hairpin member, in kcal/mol."""
    conditions = reaction.as_conditions()
    return round(
        min(
            primer3.calc_hairpin(variant, **conditions).dg for variant in _concrete_variants(primer)
        )
        / 1000.0,
        2,
    )


def _cross_dimer_dg(left: str, right: str, reaction: Reaction) -> float:
    """Return the most stable cross-dimer among all concrete members."""
    conditions = reaction.as_conditions()
    return round(
        min(
            primer3.calc_heterodimer(left_variant, right_variant, **conditions).dg
            for left_variant in _concrete_variants(left)
            for right_variant in _concrete_variants(right)
        )
        / 1000.0,
        2,
    )


def _coverage(primer: str, rows: list[str], start: int, length: int) -> int:
    """How many of the supplied sequences this mixture actually matches."""
    return sum(1 for row in rows if matches(primer, row[start : start + length]))


@dataclass
class Reasons:
    """Why windows were discarded, in the order they were tried."""

    considered: int = 0
    gapped: int = 0
    too_degenerate: int = 0
    varying_three_prime_end: int = 0
    gc_out_of_range: int = 0
    long_run: int = 0
    tm_out_of_range: int = 0
    tm_spread_above_reference: int = 0
    accepted: int = 0

    def as_rejections(self) -> list[dict[str, Any]]:
        named = [
            ("crosses a gap", self.gapped, "align without gaps in the region you want"),
            (
                "too degenerate",
                self.too_degenerate,
                "raise the degeneracy budget, or drop rare variants with the minority threshold",
            ),
            (
                "3' end varies",
                self.varying_three_prime_end,
                "use a separately reviewed profile if a different conserved-end envelope is justified",
            ),
            ("GC out of range", self.gc_out_of_range, "widen the GC range"),
            ("long run of one base", self.long_run, "allow a longer homopolymer"),
            (
                "melting temperature out of range",
                self.tm_out_of_range,
                "widen the Tm window",
            ),
        ]
        return [
            {
                "reason": reason,
                "count": count,
                "share": round(100.0 * count / self.considered, 1) if self.considered else 0.0,
                "advice": advice,
            }
            for reason, count, advice in named
            if count
        ]


def find_sites(
    alignment: Alignment,
    limits: Limits,
    reaction: Reaction,
    *,
    orientation: str,
) -> tuple[list[Site], Reasons]:
    """Every window that can carry one primer orientation.

    Forward and reverse discovery are intentionally independent.  The
    extending end of a forward primer is the right edge of an alignment
    window, while the extending end of a reverse primer is the left edge.  A
    window rejected by one directional conserved-end rule must still be
    available to the other orientation; deriving reverse candidates from the
    forward survivor list silently loses valid reverse-only windows.
    """
    if orientation not in {"forward", "reverse"}:
        raise ValueError("orientation must be `forward` or `reverse`")

    sites: list[Site] = []
    reasons = Reasons()

    # Degeneracy is multiplicative along a window, so a running product lets a
    # hopeless window be abandoned without building the primer at all.
    sizes = [len(alignment.columns[i]) for i in range(alignment.width)]

    for start in range(alignment.width):
        running = 1
        for length in range(1, limits.length_max + 1):
            end = start + length
            if end > alignment.width:
                break
            running *= sizes[end - 1]

            if length < limits.length_min:
                continue

            reasons.considered += 1

            if any(i in alignment.gapped for i in range(start, end)):
                reasons.gapped += 1
                continue
            if running > limits.max_degeneracy:
                reasons.too_degenerate += 1
                # Every longer window from here is at least this degenerate.
                break

            window_primer = "".join(code_for(alignment.columns[i]) for i in range(start, end))

            # Extension starts at opposite physical edges for the two primer
            # orientations.  This is the directional gate that must never be
            # inherited from the other orientation's survivor list.
            if orientation == "forward":
                extending_columns = range(end - limits.conserved_end, end)
                primer = window_primer
            else:
                extending_columns = range(start, start + limits.conserved_end)
                primer = reverse_complement(window_primer)
            if any(len(alignment.columns[i]) > 1 for i in extending_columns):
                reasons.varying_three_prime_end += 1
                continue

            low_gc, high_gc = gc_range(primer)
            if high_gc < limits.gc_min or low_gc > limits.gc_max:
                reasons.gc_out_of_range += 1
                continue
            if longest_run(primer) > limits.max_poly_x:
                reasons.long_run += 1
                continue

            tm_low, tm_high, member_conc = _tm_bounds(primer, reaction)
            if tm_high < limits.tm_min or tm_low > limits.tm_max:
                reasons.tm_out_of_range += 1
                continue
            if tm_high - tm_low > limits.tm_spread_max:
                # A profile-level reference for ranking/reporting only. Whether
                # a concrete degenerate mixture with this spread can share an
                # annealing regime is protocol-specific; rejecting it here
                # would promote a tuning value into a universal validity law.
                reasons.tm_spread_above_reference += 1

            reasons.accepted += 1
            sites.append(
                Site(
                    sequence=primer,
                    start=start,
                    length=length,
                    orientation=orientation,
                    degeneracy=running,
                    tm_min=tm_low,
                    tm_max=tm_high,
                    gc_min=low_gc,
                    gc_max=high_gc,
                    # Coverage is measured on the alignment-strand window. A
                    # reverse primer is its reverse complement, so the same
                    # concrete-member membership test applies to window_primer.
                    covers=_coverage(window_primer, alignment.rows, start, length),
                    hairpin_dg=_hairpin_dg(primer, reaction),
                    tm_member_dna_conc_nM=member_conc,
                )
            )

    return sites, reasons


def _combine_reasons(*items: Reasons) -> Reasons:
    """Sum directional search accounts without hiding that both were searched."""
    combined = Reasons()
    for field_name in Reasons.__dataclass_fields__:
        setattr(combined, field_name, sum(getattr(item, field_name) for item in items))
    return combined


@dataclass
class Pair:
    """Two degenerate primers with measured sequence coverage on the supplied alignment."""

    left: Site
    right: Site
    product_min: int
    product_max: int
    #: How many sequences both primers match.
    covers: int
    #: Combined degeneracy, which is what the tube actually holds.
    degeneracy: int
    cross_dimer_dg: float
    penalty: float
    coverage_score: float = 0.0
    coverage_basis: str = "record-fraction"
    components: list[dict[str, Any]] = field(default_factory=list)


def _pair_penalty(
    left: Site, right: Site, limits: Limits, depth: int, covers: int
) -> tuple[float, list[dict[str, Any]]]:
    """What is wrong with this pair, itemised.

    ``covers`` is the intersection: sequences matched by *both* primers.  The
    per-site coverage values cannot substitute for it because two primers may
    each cover N sequences while missing different members of the alignment.
    """
    parts: list[dict[str, Any]] = []

    missed = depth - covers
    parts.append(
        {
            "name": "Sequences not covered",
            "value": round(3.0 * missed, 3),
            "detail": (
                f"Both primers match all {depth} sequences."
                if not missed
                else f"{missed} of {depth} supplied sequences are not sequence-covered by both primer mixtures."
            ),
        }
    )

    # Degeneracy is a cost even when it is affordable: every doubling halves
    # the concentration of the molecule that matters.
    total = left.degeneracy * right.degeneracy
    parts.append(
        {
            "name": "Degeneracy",
            "value": round(0.35 * (total.bit_length() - 1), 3),
            "detail": (
                f"{left.degeneracy}-fold and {right.degeneracy}-fold, representing {total} concrete "
                "left/right member combinations. PCRStudio does not assume equal synthesized member abundance."
            ),
        }
    )

    spread = max(left.tm_spread, right.tm_spread)
    parts.append(
        {
            "name": "Melting-temperature spread",
            "value": round(0.3 * spread, 3),
            "detail": (
                f"The mixture melts between {min(left.tm_min, right.tm_min)} and "
                f"{max(left.tm_max, right.tm_max)} °C, so one annealing temperature has to "
                "suit all of it."
            ),
        }
    )

    difference = abs(left.tm_min - right.tm_min)
    parts.append(
        {
            "name": "Pair mismatch",
            "value": round(0.4 * difference, 3),
            "detail": f"Their coolest members differ by {round(difference, 1)} °C.",
        }
    )

    return round(sum(part["value"] for part in parts), 3), parts


def _too_similar(a: Pair, b: Pair, distance: int) -> bool:
    """Whether two pairs are the same design nudged sideways."""
    return (
        abs(a.left.three_prime_at - b.left.three_prime_at) < distance
        and abs(a.right.three_prime_at - b.right.three_prime_at) < distance
    )


def design(
    records: list[tuple[str, str]],
    *,
    limits: Limits | None = None,
    reaction: Reaction,
    how_many: int = 5,
    consensus_policy: str = "strict-all-members",
    weights: dict[str, float] | None = None,
    strata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Design degenerate pairs covering every sequence in an alignment.

    Raises:
        AlignmentError: for input that is not an alignment.
        ValueError: for limits that cannot hold.
    """
    rules = limits or Limits()
    rules.validate()

    alignment = read_alignment(records, min_coverage=rules.min_coverage, policy=consensus_policy, weights=weights, strata=strata)
    forward, forward_reasons = find_sites(
        alignment, rules, reaction, orientation="forward"
    )
    reverse, reverse_reasons = find_sites(
        alignment, rules, reaction, orientation="reverse"
    )
    reasons = _combine_reasons(forward_reasons, reverse_reasons)

    # Universal-primer ranking is exact within the declared computational
    # envelope.  Previous revisions thinned sites and measured only a cheap
    # pre-ranked subset of pairs; that surrogate could discard the eventual
    # winner before the real coverage penalty was evaluated.  Fidelity policy
    # forbids that.  Large searches now fail closed instead of approximating.
    if len(forward) > MAX_SITES_EACH_WAY or len(reverse) > MAX_SITES_EACH_WAY:
        raise AlignmentError(
            "Universal-primer exact search refused: "
            f"{len(forward)} forward and {len(reverse)} reverse valid windows exceed the "
            f"{MAX_SITES_EACH_WAY}-site per-orientation exact-search boundary. "
            "Narrow the target/product/primer constraints or use a separately named indexed/approximate workflow; "
            "PCRStudio will not thin candidates with a surrogate score in Scientific-Strict design."
        )

    considered_pairs = 0
    rejected_size = 0
    above_pair_tm_reference = 0
    exact_candidates: list[Pair] = []

    def pair_coverage_metric(left: Site, right: Site) -> tuple[int, float, str]:
        left_end = left.start + left.length
        right_end = right.start + right.length
        right_binding = reverse_complement(right.sequence)
        matched = [
            matches(left.sequence, row[left.start:left_end])
            and matches(right_binding, row[right.start:right_end])
            for row in alignment.rows
        ]
        count = sum(matched)
        if alignment.policy == "weighted":
            total = sum(alignment.weights)
            got = sum(weight for ok, weight in zip(matched, alignment.weights, strict=True) if ok)
            return count, got / total if total else 0.0, "weighted-panel-fraction"
        if alignment.policy == "stratified":
            by: dict[str, list[tuple[bool, float]]] = {}
            for ok, weight, stratum in zip(matched, alignment.weights, alignment.strata, strict=True):
                by.setdefault(stratum, []).append((ok, weight))
            fractions: list[float] = []
            for values in by.values():
                total = sum(weight for _, weight in values)
                got = sum(weight for ok, weight in values if ok)
                fractions.append(got / total if total else 0.0)
            return count, min(fractions, default=0.0), "minimum-stratum-weighted-fraction"
        return count, count / alignment.depth, "record-fraction"

    for left in forward:
        left_end = left.start + left.length
        for index, right in enumerate(reverse):
            if right.start < left_end:
                continue
            product = right.start + right.length - left.start
            if product < rules.product_min:
                rejected_size += 1
                continue
            if product > rules.product_max:
                rejected_size += len(reverse) - index
                break
            considered_pairs += 1
            if considered_pairs > MAX_EXACT_PAIR_EVALUATIONS:
                raise AlignmentError(
                    "Universal-primer exact search refused: more than "
                    f"{MAX_EXACT_PAIR_EVALUATIONS} geometrically valid pairs require full evaluation. "
                    "Narrow the product/primer windows; PCRStudio will not replace exact coverage ranking "
                    "with the former cheap stand-in."
                )
            difference = abs(left.tm_min - right.tm_min)
            if difference > rules.tm_pair_max_difference:
                above_pair_tm_reference += 1
            covers, coverage_score, coverage_basis = pair_coverage_metric(left, right)
            penalty, parts = _pair_penalty(left, right, rules, alignment.depth, covers)
            # Cross-dimer is independent evidence and is not part of the primary
            # universal-pair ranking.  Defer that expensive exact Primer3 call
            # until after the exact coverage/penalty ordering and diversity
            # selection, so no candidate is eliminated by an unvalidated proxy.
            exact_candidates.append(
                Pair(
                    left=left, right=right, product_min=product, product_max=product,
                    covers=covers, degeneracy=left.degeneracy * right.degeneracy,
                    cross_dimer_dg=0.0, penalty=penalty, coverage_score=coverage_score,
                    coverage_basis=coverage_basis, components=parts,
                )
            )

    exact_candidates.sort(key=lambda pair: (-pair.coverage_score, -pair.covers, pair.penalty))
    selected_unmeasured: list[Pair] = []
    collapsed = 0
    for candidate in exact_candidates:
        if any(_too_similar(candidate, other, rules.min_three_prime_distance) for other in selected_unmeasured):
            collapsed += 1
            continue
        selected_unmeasured.append(candidate)
        if len(selected_unmeasured) == how_many:
            break

    kept = [
        Pair(
            left=pair.left, right=pair.right, product_min=pair.product_min, product_max=pair.product_max,
            covers=pair.covers, degeneracy=pair.degeneracy,
            cross_dimer_dg=_cross_dimer_dg(pair.left.sequence, pair.right.sequence, reaction),
            penalty=pair.penalty, coverage_score=pair.coverage_score,
            coverage_basis=pair.coverage_basis, components=pair.components,
        )
        for pair in selected_unmeasured
    ]

    return {
        "engine": "consensus-pair",
        "alignment": {
            "sequences": alignment.depth,
            "columns": alignment.width,
            "names": alignment.names,
            "gapped_columns": len(alignment.gapped),
            "conserved_columns": sum(1 for column in alignment.columns if len(column) == 1),
            "consensus_policy": alignment.policy,
            "weighted": alignment.policy in {"weighted", "stratified"},
            "strata": sorted(set(alignment.strata)) if alignment.policy == "stratified" else [],
        },
        "pairs": [_pair_to_dict(pair, alignment.depth) for pair in kept],
        "windows": {
            "considered": reasons.considered,
            "accepted": reasons.accepted,
            "above_tm_spread_reference": reasons.tm_spread_above_reference,
            "tm_spread_reference_c": rules.tm_spread_max,
            "rejections": reasons.as_rejections(),
            "by_orientation": {
                "forward": {
                    "considered": forward_reasons.considered,
                    "accepted": forward_reasons.accepted,
                    "rejections": forward_reasons.as_rejections(),
                },
                "reverse": {
                    "considered": reverse_reasons.considered,
                    "accepted": reverse_reasons.accepted,
                    "rejections": reverse_reasons.as_rejections(),
                },
            },
        },
        "pair_counts": {
            "considered": considered_pairs,
            "wrong_size": rejected_size,
            "above_tm_pair_reference": above_pair_tm_reference,
            "shortlisted": len(exact_candidates),
            "measured": len(exact_candidates),
            "kept": len(kept),
            "collapsed": collapsed,
        },
        "capped": {
            "sites": False,
            "pairs": False,
            "site_limit": MAX_SITES_EACH_WAY,
            "measured_limit": MAX_EXACT_PAIR_EVALUATIONS,
            "search_complete": True,
            "selection_model": "exact-within-declared-computational-envelope",
            "note": (
                "All geometrically valid pairs inside the declared exact-search envelope received the full "
                "coverage and ranking penalty. Inputs beyond the envelope are refused rather than thinned or "
                "pre-ranked by a surrogate. Primer3 cross-dimer evidence is calculated only for returned pairs "
                "because it does not participate in primary universal-pair ranking."
            ),
        },
    }


def _site_to_dict(site: Site) -> dict[str, Any]:
    return {
        "sequence": site.sequence,
        # One-based on the way out, like every alignment viewer.
        "start": site.start + 1,
        "end": site.start + site.length,
        "length": site.length,
        "orientation": site.orientation,
        "degeneracy": site.degeneracy,
        "tm_min": site.tm_min,
        "tm_max": site.tm_max,
        "tm_spread": site.tm_spread,
        "gc_min": site.gc_min,
        "gc_max": site.gc_max,
        "covers": site.covers,
        "hairpin_dg": site.hairpin_dg,
        "tm_member_dna_conc_nM": site.tm_member_dna_conc_nM,
    }


def _pair_to_dict(pair: Pair, depth: int) -> dict[str, Any]:
    return {
        "left": _site_to_dict(pair.left),
        "right": _site_to_dict(pair.right),
        "product_size": pair.product_min,
        "covers": pair.covers,
        "of": depth,
        "coverage_score": round(pair.coverage_score, 6),
        "coverage_basis": pair.coverage_basis,
        "degeneracy": pair.degeneracy,
        "cross_dimer_dg": pair.cross_dimer_dg,
        "score": pair.penalty,
        "score_components": pair.components,
        # A degenerate-family Tm range is design evidence, not a bench Ta.
        # Generation-1 never manufactures an annealing setting from Tmin (or
        # any other member statistic) in a permissive/development policy. A
        # named PCR chemistry/SOP or experimentally resolved gradient supplies Ta.
        "annealing_temperature": None,
        "annealing_temperature_role": "unresolved-bench-protocol",
    }
