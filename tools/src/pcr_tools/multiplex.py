"""Several targets in one tube, which is not several designs in one answer.

Designing a multiplex set is not N independent searches. Every oligo in the
tube meets every other one, so choosing the best pair for each target
separately can produce a set whose members ruin each other -- and the number of
combinations makes checking them all impossible: twenty targets with a hundred
candidates each is 10^40 sets.

It is a known problem with a known shape. Nicodeme and Steyaert showed in 1997
that choosing one pair per target to minimise a sum over all oligo pairs is
NP-complete, by reduction to Multiple Choice Matching. What people do instead
is what this module does: order the targets by how little choice they have,
place each one against what is already in the tube, then try to improve the
result by swapping.

The set-level interaction objective is the published SADDLE Badness function
(Nature Communications, 2022): reverse-complementary subsequences from 4 through
8 nt contribute a term that grows with length and GC and falls with distance
from the two 3-prime ends. The 8-nt ceiling is part of SADDLE's concrete
implementation and is retained here rather than silently extending the score to
longer nested subsequences.

The optimiser in this module is *not* the SADDLE simulated-annealing optimiser.
It is a deterministic greedy placement followed by local improving swaps that
uses the SADDLE Badness objective. That distinction is carried in the result:
the chosen panel is a local search result, never a claimed global optimum or a
claim of running SADDLE itself.

Two things this module does not do.

It does not decide whether a set is acceptable. There is no published pass/fail
line, so what it reports is the badness, the worst interacting pairs by name,
and which amplicons a gel could not tell apart -- and leaves the judgement
where it belongs.

It does not constrain the melting temperatures across different pairs in the
set. The published tools disagree about whether the spread should be capped at
three degrees or five, and the kit handbook says the constraint disappears
entirely above its own threshold. The spread is reported and not enforced.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from . import screen
from . import specificity as spec
from .fingerprints import canonical_sha256
from .pipeline import run as run_single
from .presets import Reaction
from .runtime_contract import validate_required_context
from .scientific_integrity import require_named_assay, strict
from .thermo import reverse_complement

#: Complementary subsequence envelope used in SADDLE's published Badness
#: implementation. The article uses at least 4 nt and caps subsequence length
#: at 8 nt for its concrete implementation.
MIN_COMPLEMENTARY = 4
MAX_COMPLEMENTARY = 8

#: Default computational shortlist per target. This is search tuning, not a
#: published biological constant and not evidence that the global panel optimum
#: was explored. The result records the requested pool and local-search scope.
CANDIDATES_PER_TARGET = 100

# A multiplex request may split a large panel across tubes, but it must not
# turn one HTTP call into an unbounded number of independent searches. These
# are service/resource boundaries, not biological claims.
MAX_TARGETS = 32
MAX_TOTAL_INPUT_CHARS = 2_000_000
MAX_TOTAL_CANDIDATES = 3_200

#: The largest pool a set search will ask for per target.
#:
#: Larger than what a single design may return, deliberately: that limit exists
#: because a person cannot use fifty near-identical answers, and this is not an
#: answer, it is what the choosing is done from.
MAX_CANDIDATES = 200

# A larger search can be useful, but an unbounded request would let a public
# API caller turn a design endpoint into an accidental CPU denial of service.
MAX_SEARCH_ROUNDS = 10_000
MAX_TOTAL_SEARCH_ROUNDS = 100_000

# Exact Scientific-Strict selection is deliberately bounded by visited search
# states rather than silently falling back to a heuristic. The bound is a CPU
# safety limit, not a biological constant or plex validation claim.
MAX_EXACT_STATES = 750_000

# The multiplex worker accepts a JSON object directly. Keep its outer request
# surface fail-closed just like the single-target flanking worker: a misspelled
# control must never be silently ignored while the caller believes it changed
# tube composition or search effort. Shared assay/chemistry context is injected
# into each target by the Rust HTTP boundary and therefore is intentionally not
# an outer worker field.
KNOWN_REQUEST_FIELDS = frozenset(
    {
        "readout",
        "readout_profile",
        "targets",
        "candidates_per_target",
        "per_tube",
        "rounds",
        "seed",
        "optimizer_mode",
    }
)

# Multiplex targets intentionally expose only fields whose semantics survive
# set-level selection and reporting. In particular, restriction tails, vector
# primers and per-target bench chemistries are not accepted here: the current
# optimizer compares annealing primers and emits a shared-tube order sheet, so
# silently accepting those fields would misrepresent the molecules actually
# screened for interactions. Rust injects the canonical assay and shared tube
# context before the worker is called.
KNOWN_TARGET_FIELDS = frozenset(
    {
        "name",
        "template",
        "background",
        "inclusivity",
        "inclusivity_panel_provenance",
        "background_panel_provenance",
        "species_panel_selection_rationale",
        "species_target_taxid",
        "species_taxonomy_snapshot",
        "species_database_snapshot",
        "species_panel_accession_manifest",
        "species_panel_retrieved_date",
        "constraints",
        "assay",
        "from_rna",
        "standard_pcr_protocol",
        "multiplex_context",
        "colony_host_class",
        "colony_preparation",
        "colony_protocol_id",
        "colony_protocol_name",
        "colony_protocol_provenance",
        "tube",
        "primer_concentration_nm",
        "empirical_evidence_ref",
    }
)

# QIAxcel supplier-table size domains used only when the corresponding named
# cartridge profile is explicitly selected. These are readout-model boundaries,
# not generic capillary-electrophoresis limits.
QIAXCEL_REFERENCE_MAX_BP = 5_000
QIAXCEL_SMALL_BAND_MAX_BP = 500
QIAXCEL_MID_BAND_MAX_BP = 1_000


class MultiplexError(ValueError):
    """A set that could not be described."""


def _integer(
    value: Any,
    *,
    name: str,
    default: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Read one bounded integer without silently changing invalid input."""
    if value is None:
        if default is None:
            raise MultiplexError(f"`{name}` is required and must be an integer.")
        value = default
    if isinstance(value, bool):
        raise MultiplexError(f"`{name}` must be an integer, not a boolean.")
    if isinstance(value, float) and not value.is_integer():
        raise MultiplexError(f"`{name}` must be an integer, not {value!r}.")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MultiplexError(f"`{name}` must be an integer, not {value!r}.") from exc
    if minimum is not None and result < minimum:
        raise MultiplexError(f"`{name}` must be at least {minimum}, not {result}.")
    if maximum is not None and result > maximum:
        raise MultiplexError(f"`{name}` must be at most {maximum}, not {result}.")
    return result


# ── The published objective ────────────────────────────────────────────────


def badness(one: str, other: str) -> float:
    """How much these two oligos will bother each other, on SADDLE's scale.

    Sums over every reverse-complementary stretch of at least four bases. Each
    contributes a term that doubles with every extra base and with every extra
    G or C, and falls with the distance from each oligo's 3' end -- because
    extension starts at the 3' end, so a duplex that traps one makes a product
    and a duplex in the middle mostly does not.

    Nested stretches are counted through 8 nt, matching SADDLE's published
    implementation. Longer complementarity still contributes through the
    contained 4–8-nt subsequences; it is not added as a new >8-nt term.
    """
    one, other = one.upper(), other.upper()

    # Every stretch of `other`, keyed by what would pair with it.
    partners: dict[str, list[int]] = {}
    for length in range(MIN_COMPLEMENTARY, min(MAX_COMPLEMENTARY, len(other)) + 1):
        for start in range(len(other) - length + 1):
            key = reverse_complement(other[start : start + length])
            partners.setdefault(key, []).append(start)

    total = 0.0
    for length in range(MIN_COMPLEMENTARY, min(MAX_COMPLEMENTARY, len(one)) + 1):
        for start in range(len(one) - length + 1):
            stretch = one[start : start + length]
            for at in partners.get(stretch, ()):
                gc = sum(1 for base in stretch if base in "GC")
                # Bases between the duplex and each oligo's own 3' end.
                #
                # Both are measured from the right-hand end of each sequence as
                # it is written, because both are written 5' to 3'. Measuring
                # `other` from its 5' end instead inverts the whole point: a
                # dimer that traps both 3' ends, which is the one that makes a
                # product, scored as though it were harmlessly internal.
                from_one = len(one) - (start + length)
                from_other = len(other) - (at + length)
                total += (2**length) * (2**gc) / ((from_one + 1) * (from_other + 1))
    return total


def set_badness(oligos: list[str]) -> float:
    """The whole tube against itself, self-pairings included.

    An oligo interacting with a second copy of itself is a real way for a
    multiplex to fail, so the sum runs over pairs *and* over each oligo alone.
    """
    total = 0.0
    for index, one in enumerate(oligos):
        for other in oligos[index:]:
            total += badness(one, other)
    return total


# ── What a gel can tell apart ──────────────────────────────────────────────

#: How far apart two amplicons must be to be told apart on agarose, keyed on
#: the size of the largest fragment in the tube, with the gel that delivers it.
#:
#: A table rather than a number because mobility is logarithmic: twenty bases
#: separate two 200-base fragments visibly and are invisible between two of two
#: kilobases. From the multiplex kit handbook's own resolution table.
AGAROSE_SEPARATION: tuple[tuple[int, int, str], ...] = (
    (250, 20, "3.0-4.0% agarose"),
    (500, 50, "2.5-3.0% agarose"),
    (750, 100, "1.7-2.0% agarose"),
    (1000, 200, "1.4-1.6% agarose"),
    # QIAGEN's table says >200 bp at this size. Because product sizes are
    # integral base pairs, 201 bp is the smallest value that actually satisfies
    # that published relation; treating exactly 200 bp as resolved was an
    # off-by-one overclaim.
    (2000, 201, "1.3% agarose"),
)

AGAROSE_PROFILES = ("qiagen-multiplex-agarose-guideline",)

#: Named QIAxcel readout references. A generic "capillary" instrument has no
#: universal base-pair resolution, so Scientific-Strict requires one of these
#: explicit cartridge classes before making a size-spacing comparison.
CAPILLARY_PROFILES = (
    "qiagen-qiaxcel-high-resolution",
    "qiagen-qiaxcel-screening",
)

#: UI review-complexity marker only. It is not a biological plex limit and is
#: never used to decide how many tubes a Scientific-Strict request becomes.
CROWDED = 10

READOUTS = ("agarose", "capillary", "ngs")


def separation_needed(
    largest: int,
    readout: str,
    *,
    readout_profile: str | None = None,
) -> tuple[int, str]:
    """Reference spacing for the explicitly selected readout evidence.

    The returned gap is a conservative boundary from the cited supplier table,
    not a guarantee of observed resolution. Generic capillary electrophoresis
    has no single resolution number, so Scientific-Strict requires a named
    QIAxcel cartridge class instead of guessing one.
    """
    if readout not in READOUTS:
        raise MultiplexError(
            f"`{readout}` is not a readout this knows. It knows: "
            + ", ".join(READOUTS)
            + ". The readout changes how product-size collisions are interpreted."
        )

    if readout == "ngs":
        return 0, "sequencing (size spacing is not the identity criterion)"

    if readout == "capillary":
        if readout_profile not in CAPILLARY_PROFILES:
            raise MultiplexError(
                "Capillary size-resolution screening requires an explicit `readout_profile`: "
                + ", ".join(CAPILLARY_PROFILES)
                + ". A generic capillary instrument has no universal bp-resolution threshold."
            )
        if largest > QIAXCEL_REFERENCE_MAX_BP:
            raise MultiplexError(
                f"The selected QIAxcel reference table is bounded to 5 kb; the largest "
                f"product is {largest} bp. Use the actual instrument/cartridge SOP rather "
                "than extrapolating this reference."
            )
        if readout_profile == "qiagen-qiaxcel-high-resolution":
            if largest <= QIAXCEL_SMALL_BAND_MAX_BP:
                return 5, "QIAGEN QIAxcel High Resolution reference (3–5 bp at 100–500 bp)"
            if largest <= QIAXCEL_MID_BAND_MAX_BP:
                return 50, "QIAGEN QIAxcel High Resolution reference (50 bp at 500 bp–1 kb)"
            return 500, "QIAGEN QIAxcel High Resolution reference (200–500 bp at 1–5 kb)"
        if largest <= QIAXCEL_SMALL_BAND_MAX_BP:
            return 50, "QIAGEN QIAxcel Screening reference (20–50 bp at 100–500 bp)"
        if largest <= QIAXCEL_MID_BAND_MAX_BP:
            return 100, "QIAGEN QIAxcel Screening reference (50–100 bp at 500 bp–1 kb)"
        return 500, "QIAGEN QIAxcel Screening reference (500 bp at 1–5 kb)"

    # An unnamed agarose run does not determine resolution. Because this
    # reference can change which multiplex panel ranks first, Scientific-Strict
    # requires the supplier guideline to be selected explicitly rather than
    # silently importing its gel-percentage table from the word `agarose`.
    if readout_profile not in AGAROSE_PROFILES:
        raise MultiplexError(
            "Agarose size-resolution screening requires an explicit `readout_profile`: "
            + ", ".join(AGAROSE_PROFILES)
            + ". A generic agarose readout has no single bp-resolution threshold."
        )
    # Use the upper edge of each published difference band as a conservative
    # reference boundary; the final 2-kb row is strictly >200 bp, hence 201.
    for ceiling, gap, gel in AGAROSE_SEPARATION:
        if largest <= ceiling:
            return gap, f"QIAGEN agarose guideline using {gel}"
    ceiling, gap, gel = AGAROSE_SEPARATION[-1]
    return (
        gap,
        f"QIAGEN agarose guideline using {gel}; >{ceiling} bp is outside this simple spacing table",
    )


@dataclass(frozen=True)
class Collision:
    """Two products a reader could not tell apart."""

    first: str
    second: str
    sizes: tuple[int, int]
    apart: int
    needed: int


def unresolvable(
    products: dict[str, int],
    readout: str,
    *,
    readout_profile: str | None = None,
) -> tuple[list[Collision], int, str]:
    """Which pairs of products the chosen readout could not separate."""
    if not products:
        return [], 0, ""

    needed, how = separation_needed(
        max(products.values()), readout, readout_profile=readout_profile
    )
    names = sorted(products)
    clashes = [
        Collision(
            first=first,
            second=second,
            sizes=(products[first], products[second]),
            apart=abs(products[first] - products[second]),
            needed=needed,
        )
        for index, first in enumerate(names)
        for second in names[index + 1 :]
        if abs(products[first] - products[second]) < needed
    ]
    clashes.sort(key=lambda clash: clash.apart)
    return clashes, needed, how


# ── Choosing one pair per target ───────────────────────────────────────────


@dataclass
class Candidate:
    """One pair that could represent one target."""

    target: str
    left: str
    right: str
    product_size: int
    #: Where it came from, so the caller can recover the whole design.
    index: int = 0

    def oligos(self) -> list[str]:
        return [self.left, self.right]


@dataclass
class Placement:
    """One tube, and what could not go in it."""

    chosen: list[Candidate] = field(default_factory=list)
    #: Targets that could not be placed, and what stopped each of them.
    left_out: list[dict[str, Any]] = field(default_factory=list)
    badness: float = 0.0
    #: How the search got here, so the answer is not a number from nowhere.
    steps: list[str] = field(default_factory=list)


def choose(
    candidates: dict[str, list[Candidate]],
    *,
    readout: str = "ngs",
    readout_profile: str | None = None,
    rounds: int = 400,
    seed: int = 0,
) -> Placement:
    """One pair per target, chosen to keep the whole tube quiet.

    Targets are taken in order of how little choice they have, because a target
    with three candidates constrains the set far more than one with a hundred
    and placing it last means placing it into whatever is left. Then this
    implementation improves the result by swapping single choices and keeping
    only changes that improve the lexicographic readout-risk/Badness objective. This is deterministic local descent using
    SADDLE's published interaction objective, not SADDLE's simulated-annealing
    optimiser. When the selected readout distinguishes targets by product size,
    the local-search objective is lexicographic: first minimise reference-spacing
    collisions, then their total shortfall, then SADDLE Badness. This avoids an
    arbitrary numeric conversion between base-pair resolution and interaction
    Badness. Checking every combination of twenty targets with a hundred
    candidates each means 10^40 sets.

    Args:
        rounds: How many swaps to try. More is better and slower; the returned
            steps say how many actually improved anything.
        seed: Fixed so the same request gives the same tube. A search that
            answered differently each time could not be checked against a
            recorded result, and two people comparing notes would disagree.

    Raises:
        MultiplexError: if a target arrives with no candidates at all.
    """
    rounds = _integer(rounds, name="rounds", minimum=0, maximum=MAX_SEARCH_ROUNDS)
    seed = _integer(seed, name="seed")

    for target, choices in candidates.items():
        if not choices:
            raise MultiplexError(
                f"`{target}` has no candidate pairs, so there is nothing to choose "
                "from. Design for it on its own first and find out why."
            )

    order = sorted(candidates, key=lambda target: len(candidates[target]))
    placement = Placement()
    placement.steps.append(
        "Targets placed in order of how little choice each had: "
        + ", ".join(f"{target} ({len(candidates[target])})" for target in order)
    )

    def objective(picks: dict[str, Candidate]) -> tuple[int, int, float]:
        """Readout risk first, then interaction Badness, with no mixed-unit weight."""
        products = {target: pick.product_size for target, pick in picks.items()}
        clashes, needed, _ = unresolvable(products, readout, readout_profile=readout_profile)
        shortfall = sum(max(0, needed - clash.apart) for clash in clashes)
        oligos = [oligo for pick in picks.values() for oligo in pick.oligos()]
        return len(clashes), shortfall, set_badness(oligos)

    chosen: dict[str, Candidate] = {}
    for target in order:
        best: tuple[tuple[int, int, float], Candidate] | None = None
        for candidate in candidates[target]:
            trial = {**chosen, target: candidate}
            cost = objective(trial)
            if best is None or cost < best[0]:
                best = (cost, candidate)
        assert best is not None
        chosen[target] = best[1]

    current = objective(chosen)
    placement.steps.append(
        f"First pass: {current[0]} reference-spacing collision(s), "
        f"{current[1]} bp total shortfall, badness {current[2]:.0f}"
    )

    generator = random.Random(seed)
    improved = 0
    for _ in range(rounds):
        target = generator.choice(order)
        if len(candidates[target]) < 2:
            continue
        swap = generator.choice(candidates[target])
        if swap is chosen[target]:
            continue
        was = chosen[target]
        chosen[target] = swap
        after = objective(chosen)
        if after < current:
            current = after
            improved += 1
        else:
            chosen[target] = was

    placement.steps.append(
        f"{improved} swap(s) out of {rounds} tried improved the lexicographic objective, "
        f"to {current[0]} collision(s), {current[1]} bp shortfall, badness {current[2]:.0f}"
    )
    placement.chosen = [chosen[target] for target in sorted(chosen)]
    placement.badness = round(current[2], 1)
    return placement


def choose_exact(
    candidates: dict[str, list[Candidate]],
    *,
    readout: str = "ngs",
    readout_profile: str | None = None,
    max_states: int = MAX_EXACT_STATES,
) -> Placement:
    """Exactly minimise the declared lexicographic panel objective within a bounded search.

    This is PCRStudio's own fully specified exact search, not SADDLE.  The
    partial objective is a valid lower bound because spacing collisions,
    spacing shortfall and non-negative SADDLE Badness can only increase as more
    oligos are added.  If the state budget is exhausted, the caller receives a
    refusal instead of a heuristic answer carrying an exact/Scientific-Strict
    claim.
    """
    max_states = _integer(max_states, name="max_exact_states", minimum=1, maximum=MAX_EXACT_STATES)
    for target, choices in candidates.items():
        if not choices:
            raise MultiplexError(
                f"`{target}` has no candidate pairs, so exact multiplex selection cannot proceed."
            )
    order = sorted(candidates, key=lambda target: (len(candidates[target]), target))

    def objective(picks: dict[str, Candidate]) -> tuple[int, int, float]:
        products = {target: pick.product_size for target, pick in picks.items()}
        clashes, needed, _ = unresolvable(products, readout, readout_profile=readout_profile)
        shortfall = sum(max(0, needed - clash.apart) for clash in clashes)
        oligos = [oligo for pick in picks.values() for oligo in pick.oligos()]
        return len(clashes), shortfall, set_badness(oligos)

    best_cost: tuple[int, int, float] | None = None
    best: dict[str, Candidate] | None = None
    visited = 0
    pruned = 0

    def visit(at: int, picks: dict[str, Candidate]) -> None:
        nonlocal best_cost, best, visited, pruned
        visited += 1
        if visited > max_states:
            raise MultiplexError(
                "Exact multiplex search exceeded the bounded Scientific-Strict state budget "
                f"of {max_states:,}. Reduce candidates_per_target, split the panel with explicit "
                "tube assignments, or use a separately identified upstream/authority optimizer; "
                "PCRStudio will not silently substitute its local heuristic."
            )
        lower = objective(picks) if picks else (0, 0, 0.0)
        if best_cost is not None and lower >= best_cost:
            pruned += 1
            return
        if at == len(order):
            best_cost = lower
            best = dict(picks)
            return
        target = order[at]
        ranked: list[tuple[tuple[int, int, float], Candidate]] = []
        for candidate in candidates[target]:
            trial = {**picks, target: candidate}
            ranked.append((objective(trial), candidate))
        for _cost, candidate in sorted(ranked, key=lambda row: (row[0], row[1].index)):
            picks[target] = candidate
            visit(at + 1, picks)
            picks.pop(target, None)

    visit(0, {})
    if best is None or best_cost is None:
        raise MultiplexError("Exact multiplex search completed without a candidate set.")
    placement = Placement(
        chosen=[best[target] for target in sorted(best)],
        badness=round(best_cost[2], 1),
        steps=[
            "Exact lexicographic branch-and-bound over the evaluated candidate pools.",
            f"Visited {visited:,} state(s); pruned {pruned:,} state(s) using the monotone partial objective lower bound.",
            f"Optimum within the evaluated pools: {best_cost[0]} spacing collision(s), {best_cost[1]} bp shortfall, badness {best_cost[2]:.0f}.",
        ],
    )
    return placement


def _explicit_tube_groups(
    candidates: dict[str, list[Candidate]], target_tubes: dict[str, str]
) -> list[tuple[str, dict[str, list[Candidate]]]]:
    if set(target_tubes) != set(candidates):
        raise MultiplexError(
            "Scientific-Strict multi-tube multiplexing requires an explicit non-empty `tube` identity for every target."
        )
    groups: dict[str, dict[str, list[Candidate]]] = {}
    for target, choices in candidates.items():
        tube = str(target_tubes[target]).strip()
        if not tube:
            raise MultiplexError("multiplex target `tube` identities must be non-empty text")
        groups.setdefault(tube, {})[target] = choices
    return [(tube, groups[tube]) for tube in sorted(groups)]


def split_into_tubes(
    candidates: dict[str, list[Candidate]],
    *,
    per_tube: int = CROWDED,
    readout: str = "ngs",
    readout_profile: str | None = None,
    rounds: int = 400,
    seed: int = 0,
) -> list[Placement]:
    """The panel across as many tubes as it needs.

    What laboratories actually do with a panel too big for one reaction: they
    run it in several. Splitting is not a failure to be reported, it is the
    answer, and a tool that refused above some plex count would be refusing the
    normal case. The target-to-tube partition here is deliberately a bounded,
    deterministic scarcity heuristic (fewest candidate pairs first), not a
    global combinatorial optimization over every possible tube partition.
    """
    per_tube = _integer(per_tube, name="per_tube", minimum=1)
    rounds = _integer(rounds, name="rounds", minimum=0, maximum=MAX_SEARCH_ROUNDS)
    seed = _integer(seed, name="seed")

    remaining = dict(candidates)
    tubes: list[Placement] = []
    while remaining:
        take = sorted(remaining, key=lambda target: len(remaining[target]))[:per_tube]
        tubes.append(
            choose(
                {target: remaining[target] for target in take},
                readout=readout,
                readout_profile=readout_profile,
                rounds=rounds,
                seed=seed,
            )
        )
        for target in take:
            del remaining[target]
    return tubes


# ── One request, one tube ──────────────────────────────────────────────────


def run(request: dict[str, Any]) -> dict[str, Any]:
    """Design a set for several targets that will share a tube.

    Each target is designed for on its own, with a far longer shortlist than a
    single design needs, and then one pair per target is chosen for how quietly
    the whole set behaves together.

    Raises:
        MultiplexError: for a request that could not describe a set.
        IntakeError, ValueError: as the ordinary design does, per target.
    """
    if not isinstance(request, dict):
        raise MultiplexError("a multiplex request must be a JSON object")
    unknown = sorted(
        repr(key) for key in request if not isinstance(key, str) or key not in KNOWN_REQUEST_FIELDS
    )
    if unknown:
        raise MultiplexError("unknown multiplex request field(s): " + ", ".join(unknown))

    readout_value = request.get("readout")
    readout = readout_value if isinstance(readout_value, str) else ""
    if readout not in READOUTS:
        raise MultiplexError(
            "A multiplex design needs to know how the products will be read, as "
            f"`readout`: {', '.join(READOUTS)}. There is no default because readout "
            "changes how size collisions are interpreted."
        )

    profile_value = request.get("readout_profile")
    if profile_value is not None and not isinstance(profile_value, str):
        raise MultiplexError("`readout_profile` must be text when supplied.")
    readout_profile = profile_value.strip() if isinstance(profile_value, str) else None
    if readout == "ngs" and readout_profile is not None:
        raise MultiplexError(
            "`readout_profile` is only meaningful for agarose/capillary reference-spacing screens; "
            "omit it for NGS rather than attaching an unused supplier profile to the result."
        )
    if readout == "capillary" and readout_profile not in CAPILLARY_PROFILES:
        raise MultiplexError(
            "Scientific multiplex capillary screening requires a named cartridge reference: "
            + ", ".join(CAPILLARY_PROFILES)
            + ". Do not infer resolution from the word `capillary`."
        )
    if readout == "agarose" and readout_profile not in AGAROSE_PROFILES:
        raise MultiplexError(
            "Scientific multiplex agarose screening requires the named supplier reference: "
            + ", ".join(AGAROSE_PROFILES)
            + ". Do not infer gel resolution from the word `agarose`."
        )
    if readout == "ngs" and readout_profile:
        raise MultiplexError("`readout_profile` is not used for NGS readout.")

    targets_value = request.get("targets")
    if targets_value is None:
        targets: list[Any] = []
    elif not isinstance(targets_value, list):
        raise MultiplexError("`targets` must be a list of target objects.")
    else:
        targets = targets_value
    if len(targets) < 2:
        raise MultiplexError(
            f"A multiplex is more than one target in one tube; {len(targets)} was "
            "given. For a single target, design it on its own."
        )
    if len(targets) > MAX_TARGETS:
        raise MultiplexError(
            f"A multiplex request may contain at most {MAX_TARGETS} targets. "
            "Split a larger panel into separate requests so each result remains "
            "reviewable and the search has a bounded cost."
        )

    # Count the text fields that can be handed to a per-target search. This is
    # intentionally a character budget rather than a biological base limit:
    # FASTA/GenBank parsing happens in the ordinary pipeline, and the HTTP
    # layer already limits the encoded body. The budget covers target,
    # exclusion-background and inclusivity text because each can trigger a
    # substantial scan. The user-declared panel provenance/rationale strings
    # are counted too: they are not sequence, but they cross the same request
    # boundary and must not provide an unbounded text side channel.
    total_input_chars = sum(
        len(value)
        for entry in targets
        if isinstance(entry, dict)
        for field in (
            "name",
            "template",
            "background",
            "inclusivity",
            "inclusivity_panel_provenance",
            "background_panel_provenance",
            "species_panel_selection_rationale",
            "species_taxonomy_snapshot",
            "species_database_snapshot",
            "species_panel_accession_manifest",
            "species_panel_retrieved_date",
        )
        for value in [entry.get(field)]
        if isinstance(value, str)
    )
    if total_input_chars > MAX_TOTAL_INPUT_CHARS:
        raise MultiplexError(
            "The combined multiplex sequence input is too large: it must be at "
            f"most {MAX_TOTAL_INPUT_CHARS:,} characters across target names/templates, "
            "backgrounds, inclusivity records and their provenance metadata. Split the panel or provide "
            "smaller bounded sequence records."
        )

    wanted = _integer(
        request.get("candidates_per_target"),
        name="candidates_per_target",
        default=CANDIDATES_PER_TARGET,
        minimum=1,
        maximum=MAX_CANDIDATES,
    )
    # A multiplex request means one shared reaction unless the caller explicitly
    # asks to split it. The old default of ten pairs per tube was only a local
    # review heuristic and silently changed the experiment architecture.
    per_tube = _integer(
        request.get("per_tube"),
        name="per_tube",
        default=len(targets),
        minimum=1,
        maximum=MAX_TARGETS,
    )
    rounds = _integer(
        request.get("rounds"),
        name="rounds",
        default=400,
        minimum=0,
        maximum=MAX_SEARCH_ROUNDS,
    )
    seed = _integer(request.get("seed"), name="seed", default=0)
    optimizer_raw = request.get("optimizer_mode")
    optimizer_mode = str(optimizer_raw or "auto").strip().lower()
    if optimizer_mode not in {"auto", "exact", "local"}:
        raise MultiplexError("`optimizer_mode` must be one of: auto, exact, local")
    if optimizer_mode == "auto":
        optimizer_mode = "exact" if strict() else "local"
    if strict() and optimizer_mode != "exact":
        raise MultiplexError(
            "Scientific-Strict multiplex selection requires optimizer_mode=exact. "
            "The PCRStudio local optimiser is an explicitly approximate development method."
        )

    total_candidates = len(targets) * wanted
    if total_candidates > MAX_TOTAL_CANDIDATES:
        raise MultiplexError(
            "This request asks for too many candidate pairs in total: "
            f"{len(targets)} targets × {wanted} candidates exceeds the "
            f"service limit of {MAX_TOTAL_CANDIDATES:,}. Reduce "
            "`candidates_per_target` or split the panel."
        )

    tube_count = (len(targets) + per_tube - 1) // per_tube
    total_search_rounds = tube_count * rounds
    if total_search_rounds > MAX_TOTAL_SEARCH_ROUNDS:
        raise MultiplexError(
            "This request asks for too many set-search rounds in total: "
            f"{tube_count} tubes × {rounds} rounds exceeds the service limit "
            f"of {MAX_TOTAL_SEARCH_ROUNDS:,}. Increase `per_tube` or reduce "
            "`rounds`."
        )

    designs: dict[str, list[Candidate]] = {}
    per_target: list[dict[str, Any]] = []
    shared_assay: dict[str, Any] | None = None
    shared_reaction: dict[str, Any] | None = None
    shared_constraints: dict[str, Any] | None = None
    constraints_are_shared = True
    shared_provenance: dict[str, Any] | None = None
    shared_protocol: dict[str, Any] | None = None
    shared_reverse_transcription: dict[str, Any] | None = None
    shared_colony_context: dict[str, Any] | None = None
    target_tubes: dict[str, str] = {}
    target_inputs: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(targets, start=1):
        if not isinstance(entry, dict):
            raise MultiplexError(f"target {index} must be an object with a template.")
        unknown_target = sorted(
            repr(key) for key in entry if not isinstance(key, str) or key not in KNOWN_TARGET_FIELDS
        )
        if unknown_target:
            raise MultiplexError(
                f"target {index} has unsupported multiplex field(s): "
                + ", ".join(unknown_target)
                + ". Design that target separately or add an explicit set-level contract before multiplexing it."
            )
        supplied_name = entry.get("name")
        if supplied_name is not None and not isinstance(supplied_name, str):
            raise MultiplexError(f"target {index} name must be text when supplied.")
        name = (
            supplied_name.strip() if supplied_name and supplied_name.strip() else f"target_{index}"
        )
        module_id = require_named_assay(
            entry,
            command="multiplex-target",
            require_profile_authority=True,
        )
        if module_id:
            validate_required_context(entry, module_id)
        if name in designs:
            raise MultiplexError(
                f"Two targets are both called `{name}`. They have to be told apart "
                "on the order sheet and on the gel."
            )
        target_inputs[name] = dict(entry)
        primer_concentration_nm = entry.get("primer_concentration_nm")
        if primer_concentration_nm is not None:
            if (
                isinstance(primer_concentration_nm, bool)
                or not isinstance(primer_concentration_nm, (int, float))
                or not math.isfinite(float(primer_concentration_nm))
                or float(primer_concentration_nm) <= 0
            ):
                raise MultiplexError(
                    f"target {index} primer_concentration_nm must be a positive finite planned/measured concentration"
                )
            target_inputs[name]["primer_concentration_nm"] = float(primer_concentration_nm)
        empirical_evidence_ref = str(entry.get("empirical_evidence_ref") or "").strip()
        if empirical_evidence_ref:
            target_inputs[name]["empirical_evidence_ref"] = empirical_evidence_ref
        tube_value = entry.get("tube")
        if tube_value is not None:
            if not isinstance(tube_value, str) or not tube_value.strip():
                raise MultiplexError(f"target {index} `tube` must be non-empty text when supplied")
            target_tubes[name] = tube_value.strip()

        one = run_single(
            {**entry, "name": name, "how_many": wanted},
            most=MAX_CANDIDATES,
            # Without a pool of its own the ordinary shortlist cap of fifty
            # quietly halved the advertised count: this is choosing between
            # candidates, not returning them as answers.
            pool=wanted,
        )
        resolved_assay = one.get("assay")
        if not isinstance(resolved_assay, dict):
            raise MultiplexError(
                f"target {index} did not return an assay contract. A multiplex "
                "result cannot prove which chemistry its tube shares."
            )
        resolved_modifiers = resolved_assay.get("modifiers")
        if not isinstance(resolved_modifiers, list) or "multiplex" not in resolved_modifiers:
            raise MultiplexError(
                f"assay `{resolved_assay.get('id') or module_id}` does not declare the canonical `multiplex` modifier. "
                "Do not route simplex qPCR/dPCR/RPA or another non-multiplex profile through the generic endpoint multiplex orchestrator."
            )
        # A tube has one reaction and one assay claim. The HTTP route normally
        # injects the same profile into every target, but direct worker callers
        # can bypass that adapter. Refuse mixed executable contracts instead of
        # designing a set whose targets quietly use different chemistry rules.
        contract = {
            field: resolved_assay.get(field)
            for field in (
                "id",
                "name",
                "engine",
                "status",
                "profile_authority",
                "defaults",
                "purposes",
                "modifiers",
                "requires",
                "enzyme",
            )
        }
        protocol_contract = one.get("protocol") if isinstance(one.get("protocol"), dict) else None
        rt_contract = (
            one.get("reverse_transcription")
            if isinstance(one.get("reverse_transcription"), dict)
            else None
        )
        if shared_assay is None:
            shared_assay = contract
            shared_protocol = dict(protocol_contract) if protocol_contract is not None else None
            shared_reverse_transcription = dict(rt_contract) if rt_contract is not None else None
        else:
            if contract != shared_assay:
                raise MultiplexError(
                    "Every target in a multiplex tube must use the same assay "
                    "contract (profile, modifiers, requirements and enzyme "
                    "capabilities). Design different chemistries in separate tubes."
                )
            if protocol_contract != shared_protocol:
                raise MultiplexError(
                    "Every target sharing a multiplex tube must use the same named protocol/chemistry overlay. "
                    "Split targets that select different Standard-PCR, qPCR, dPCR, RPA or long-range protocols into separate requests."
                )
            if rt_contract != shared_reverse_transcription:
                raise MultiplexError(
                    "Every RNA target sharing a multiplex tube must resolve to the same reverse-transcription authority and placement. "
                    "Split one-step, two-step, unresolved or differently timed RT chemistries into separate requests."
                )
        reaction_contract = one.get("reaction") if isinstance(one.get("reaction"), dict) else {}
        constraint_contract = (
            one.get("constraints") if isinstance(one.get("constraints"), dict) else {}
        )
        provenance_contract = (
            one.get("provenance") if isinstance(one.get("provenance"), dict) else {}
        )
        assay_id = str(resolved_assay.get("id") or "")
        if assay_id == "colony-pcr":
            colony = one.get("colony_context")
            if not isinstance(colony, dict):
                raise MultiplexError(
                    f"target {index} lost required colony_context evidence during design; the multiplex result cannot omit host/preparation/SOP provenance."
                )
            if shared_colony_context is None:
                shared_colony_context = dict(colony)
            elif colony != shared_colony_context:
                raise MultiplexError(
                    "Every target in a colony-PCR multiplex tube must share the same colony preparation/SOP context."
                )
        if assay_id == "species-specific-pcr":
            inclusivity_evidence = one.get("inclusivity")
            background_evidence = one.get("background")
            if not isinstance(inclusivity_evidence, dict) or not isinstance(
                background_evidence, dict
            ):
                raise MultiplexError(
                    f"target {index} lost species-specific inclusivity/exclusion evidence during design; the panel claim cannot be aggregated without both."
                )
            for label, evidence in (
                ("inclusivity", inclusivity_evidence),
                ("exclusivity", background_evidence),
            ):
                if not evidence.get("panel_provenance") or not evidence.get(
                    "panel_selection_rationale"
                ):
                    raise MultiplexError(
                        f"target {index} lost species-specific {label} panel provenance/selection rationale during design; the multiplex result refuses an untraceable biological-panel claim."
                    )
        if shared_reaction is None:
            shared_reaction = dict(reaction_contract)
            shared_constraints = dict(constraint_contract)
            shared_provenance = dict(provenance_contract)
        else:
            if reaction_contract != shared_reaction:
                raise MultiplexError(
                    "Every target sharing a multiplex tube must resolve to the same reaction conditions. "
                    "Split targets with different chemistry or cycling requirements into separate requests."
                )
            if provenance_contract != shared_provenance:
                raise MultiplexError(
                    "Every target in one multiplex request must be produced by the same computational provenance "
                    "(worker/runtime contract, Primer3/tool identity and thermodynamic model). Refuse a mixed-version "
                    "aggregate rather than reporting the first target's provenance as if it governed all targets."
                )
            if constraint_contract != shared_constraints:
                constraints_are_shared = False
        pairs = one.get("pairs") or []
        target_summary = {
            "name": name,
            "candidates": len(pairs),
            "why_nothing": one.get("why_nothing", ""),
            "target": one.get("target", {}),
            "constraints": dict(constraint_contract),
            **(
                {"primer_concentration_nm": float(primer_concentration_nm)}
                if primer_concentration_nm is not None
                else {}
            ),
            **(
                {"empirical_evidence_ref": empirical_evidence_ref} if empirical_evidence_ref else {}
            ),
        }
        if isinstance(one.get("background"), dict):
            target_summary["background"] = one["background"]
        if isinstance(one.get("inclusivity"), dict):
            target_summary["inclusivity"] = one["inclusivity"]
        per_target.append(target_summary)
        designs[name] = [
            Candidate(
                target=name,
                left=pair["left"]["sequence"],
                right=pair["right"]["sequence"],
                product_size=pair["product_size"],
                index=at,
            )
            for at, pair in enumerate(pairs)
        ]

    empty = sorted(name for name, choices in designs.items() if not choices)
    if empty:
        raise MultiplexError(
            "No pair could be designed for "
            + ", ".join(empty)
            + ". A set cannot be chosen around a target that has no candidates; "
            "design for each of those on its own first and find out why."
        )

    explicit_assignment = bool(target_tubes)
    if explicit_assignment and len(target_tubes) != len(designs):
        raise MultiplexError(
            "When any multiplex target declares `tube`, every target must declare one so the physical reaction architecture is unambiguous."
        )
    tube_labels: list[str] = []
    tubes: list[Placement] = []
    if explicit_assignment:
        for tube_label, group in _explicit_tube_groups(designs, target_tubes):
            tube_labels.append(tube_label)
            if optimizer_mode == "exact":
                tubes.append(choose_exact(group, readout=readout, readout_profile=readout_profile))
            else:
                tubes.append(
                    choose(
                        group,
                        readout=readout,
                        readout_profile=readout_profile,
                        rounds=rounds,
                        seed=seed,
                    )
                )
    else:
        if strict() and per_tube < len(designs):
            raise MultiplexError(
                "Scientific-Strict refuses heuristic automatic tube partitioning. Supply a `tube` identity for every target, "
                "or keep all targets in one tube; external PrimerPooler pool proposals may be reviewed and then entered explicitly."
            )
        if per_tube >= len(designs):
            tube_labels = ["tube-1"]
            tubes = [
                choose_exact(designs, readout=readout, readout_profile=readout_profile)
                if optimizer_mode == "exact"
                else choose(
                    designs,
                    readout=readout,
                    readout_profile=readout_profile,
                    rounds=rounds,
                    seed=seed,
                )
            ]
        else:
            tubes = split_into_tubes(
                designs,
                per_tube=per_tube,
                readout=readout,
                readout_profile=readout_profile,
                rounds=rounds,
                seed=seed,
            )
            tube_labels = [f"tube-{index + 1}" for index in range(len(tubes))]

    tube_results = [
        {
            **_tube_to_dict(tube, index + 1, readout, readout_profile=readout_profile),
            "tube_id": tube_labels[index],
        }
        for index, tube in enumerate(tubes)
    ]
    panel_cross_product_specificity = _cross_product_specificity(
        tube_results, target_inputs=target_inputs, reaction=shared_reaction or {}
    )
    order_sheet: list[dict[str, Any]] = []
    for tube in tube_results:
        tube_number = int(tube["tube"])
        for pair in tube["pairs"]:
            for suffix, sequence in (("F", pair["left"]), ("R", pair["right"])):
                order_sheet.append(
                    {
                        "name": f"{pair['target']}_{suffix}",
                        "sequence": sequence,
                        "annealing_sequence": sequence,
                        "tail_sequence": "",
                        "kind": "primer",
                        "length": len(sequence),
                        "gc_percent": round(
                            100.0
                            * sum(base in {"G", "C"} for base in sequence.upper())
                            / max(len(sequence), 1),
                            1,
                        ),
                        "tube": f"tube-{tube_number}",
                        "pool": tube_number - 1,
                        **(
                            {
                                "planned_primer_concentration_nm": target_inputs[pair["target"]][
                                    "primer_concentration_nm"
                                ]
                            }
                            if target_inputs[pair["target"]].get("primer_concentration_nm")
                            is not None
                            else {}
                        ),
                        **(
                            {
                                "empirical_evidence_ref": target_inputs[pair["target"]][
                                    "empirical_evidence_ref"
                                ]
                            }
                            if target_inputs[pair["target"]].get("empirical_evidence_ref")
                            else {}
                        ),
                        "note": "Selected for this final multiplex tube; concentration metadata is empirical/planned formulation evidence and never alters sequence ranking. External interaction validation is evaluated tube-by-tube.",
                    }
                )

    panel_identity_payload = [
        {
            "tube_id": tube["tube_id"],
            "pairs": [
                {"target": pair["target"], "left": pair["left"], "right": pair["right"]}
                for pair in tube["pairs"]
            ],
        }
        for tube in tube_results
    ]
    formulation_payload = [
        {
            "target": name,
            "primer_concentration_nm": target_inputs[name].get("primer_concentration_nm"),
            "empirical_evidence_ref": target_inputs[name].get("empirical_evidence_ref"),
        }
        for name in sorted(target_inputs)
    ]
    panel_identity = {
        "panel_sha256": canonical_sha256(panel_identity_payload),
        "formulation_sha256": canonical_sha256(formulation_payload),
        "identity_scope": "final-selected-primer-pairs-with-explicit-physical-tube-identities",
        "formulation_identity_scope": "target-level-planned-or-measured-primer-concentration-and-empirical-evidence-references; no-sequence-ranking-impact",
        "software_target_bound": MAX_TARGETS,
        "wet_lab_qualified_plex": None,
    }

    return {
        "engine": "flanking-pair",
        "mode": "multiplex",
        "readout": readout,
        "readout_profile": readout_profile,
        # Preserve the contract that governed every per-target search. The
        # individual target summaries are intentionally compact; this shared
        # block is the reproducibility anchor for the tube as a whole.
        "assay": shared_assay or {},
        "reaction": shared_reaction or {},
        **({"constraints": shared_constraints or {}} if constraints_are_shared else {}),
        "constraint_scope": "shared" if constraints_are_shared else "per-target",
        "provenance": shared_provenance or {},
        **({"protocol": shared_protocol} if shared_protocol is not None else {}),
        **(
            {"reverse_transcription": shared_reverse_transcription}
            if shared_reverse_transcription is not None
            else {}
        ),
        **({"colony_context": shared_colony_context} if shared_colony_context is not None else {}),
        "targets": per_target,
        "crowded_above": CROWDED,
        "tubes": tube_results,
        "order_sheet": order_sheet,
        "panel_validation_scope": "final-selected-oligos-grouped-by-tube",
        "panel_identity": panel_identity,
        "panel_cross_product_specificity": panel_cross_product_specificity,
        "selection_method": {
            "objective": (
                "lexicographic reference-spacing collisions -> total spacing shortfall -> "
                "SADDLE Badness Eq. 2 implementation envelope (4-8 nt complementary subsequences)"
            ),
            "readout_in_selection": True,
            "optimizer": (
                "pcrstudio-exact-lexicographic-branch-and-bound"
                if optimizer_mode == "exact"
                else "deterministic-greedy-plus-local-improving-swaps"
            ),
            "optimizer_mode": optimizer_mode,
            "simulated_annealing": False,
            "exhaustive_within_evaluated_candidate_pools": optimizer_mode == "exact",
            "global_optimum_claimed": False,
            "candidate_pool_optimum_claimed": optimizer_mode == "exact",
            "candidates_per_target": wanted,
            "rounds_per_tube": rounds,
            "seed": seed,
            "per_tube": per_tube,
            "tube_split_explicit": request.get("per_tube") is not None,
            "tube_assignment": {
                "strategy": (
                    "explicit-target-tube-identities"
                    if explicit_assignment
                    else (
                        "single-tube"
                        if len(tube_results) == 1
                        else "deterministic-fewest-candidates-first-chunking"
                    )
                ),
                "global_partition_optimized": False,
                "explicit": explicit_assignment,
                "tube_count": len(tube_results),
                "note": (
                    "Tube identities were explicitly supplied and are treated as physical-reaction authority."
                    if explicit_assignment
                    else (
                        "All targets share one tube; no partition decision was required."
                        if len(tube_results) == 1
                        else "Development mode assigned targets by candidate scarcity. Scientific-Strict refuses this heuristic partition path."
                    )
                ),
            },
        },
        "note": (
            "One pair per target is chosen within the evaluated candidate pools using the explicitly reported optimizer. "
            "Scientific-Strict uses exact lexicographic branch-and-bound and refuses state-budget exhaustion; development mode may use the labelled local search. "
            "Neither path is SADDLE simulated annealing and no whole-biological-search-space global optimum is claimed. "
            "Scientific-Strict also refuses heuristic automatic tube partitioning. There is no published line between an "
            "acceptable set and an unacceptable one, so nothing here is a pass or "
            "a fail: the badness is a number to compare sets by, not to threshold. "
            "The final selected oligos are exposed as an order sheet so PrimerPooler, "
            "MFEprimer and BLAST can audit the actual panel rather than the pre-selection candidates."
        ),
    }


def _cross_product_specificity(
    tube_results: list[dict[str, Any]],
    *,
    target_inputs: dict[str, dict[str, Any]],
    reaction: dict[str, Any],
) -> list[dict[str, Any]]:
    """Scan every selected F/R oligo against every other selected oligo's target scope.

    This is the multiplex-specific F_i x R_j product check that N independent
    simplex designs cannot perform. When every target declares the identical
    exclusion background we scan that shared background. Otherwise we scan the
    union of the target templates and explicitly retain the narrower scope;
    per-target biological background/inclusivity evidence remains separate.
    """
    try:
        rxn = Reaction(
            mv_conc=float(reaction["mv_conc"]),
            dv_conc=float(reaction["dv_conc"]),
            dntp_conc=float(reaction["dntp_conc"]),
            dna_conc=float(reaction["dna_conc"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MultiplexError(
            "multiplex cross-product specificity lost the shared thermodynamic reaction context"
        ) from exc

    results: list[dict[str, Any]] = []
    for tube in tube_results:
        pairs = list(tube.get("pairs") or [])
        names = [str(pair.get("target") or "") for pair in pairs]
        entries = [target_inputs[name] for name in names if name in target_inputs]
        backgrounds = [str(entry.get("background") or "").strip() for entry in entries]
        shared_background = bool(backgrounds) and all(backgrounds) and len(set(backgrounds)) == 1
        if shared_background:
            contigs = screen.contigs_from_text(
                backgrounds[0],
                label="shared multiplex background",
                default_name="shared multiplex background",
            )
            scope = "shared-declared-background"
        else:
            contigs = []
            for name, entry in zip(names, entries, strict=True):
                template = str(entry.get("template") or "").strip()
                if not template:
                    continue
                parsed = screen.contigs_from_text(
                    template, label=f"multiplex target {name}", default_name=name
                )
                for idx, contig in enumerate(parsed, start=1):
                    contigs.append(
                        spec.Contig(name=f"{name}:{idx}:{contig.name}", sequence=contig.sequence)
                    )
            scope = "union-of-target-templates"
        named: dict[str, str] = {}
        intended_sizes: list[int] = []
        for pair in pairs:
            target = str(pair.get("target") or "target")
            named[f"{target}:F"] = str(pair.get("left") or "")
            named[f"{target}:R"] = str(pair.get("right") or "")
            intended_sizes.append(int(pair.get("product_size") or 0))
        longest = max(intended_sizes, default=0)
        audit = screen.oligos(
            named,
            contigs,
            reaction=rxn,
            max_mismatches=3,
            max_product=screen.product_ceiling(longest),
            intended_sizes=intended_sizes,
            max_products=50,
        )
        products = list(audit.get("products") or []) if isinstance(audit, dict) else []
        results.append(
            {
                "tube": tube.get("tube"),
                "tube_id": tube.get("tube_id"),
                "scope": scope,
                "checked": bool(audit.get("checked")) if isinstance(audit, dict) else False,
                "unintended_product_count": int(audit.get("product_count") or len(products))
                if isinstance(audit, dict)
                else 0,
                "audit": audit,
                "decision_impact": "validation-evidence",
                "note": (
                    "All selected extending primers were scanned together, so F_i x R_j cross-products are visible. "
                    "This is not a replacement for each target's broader inclusivity/exclusivity database evidence."
                ),
            }
        )
    return results


def _tube_to_dict(
    tube: Placement,
    number: int,
    readout: str,
    *,
    readout_profile: str | None = None,
) -> dict[str, Any]:
    """One tube, its interactions and reference readout-spacing risks."""
    products = {pick.target: pick.product_size for pick in tube.chosen}
    clashes, needed, how = unresolvable(products, readout, readout_profile=readout_profile)

    oligos = [(f"{pick.target}_F", pick.left) for pick in tube.chosen] + [
        (f"{pick.target}_R", pick.right) for pick in tube.chosen
    ]
    worst = sorted(
        (
            {
                "a": first_name,
                "b": second_name,
                "badness": round(badness(first, second), 1),
            }
            for index, (first_name, first) in enumerate(oligos)
            for second_name, second in oligos[index:]
        ),
        key=lambda entry: -entry["badness"],
    )[:8]

    return {
        "tube": number,
        "badness": tube.badness,
        "crowded": len(tube.chosen) > CROWDED,
        "how_it_was_chosen": tube.steps,
        "pairs": [
            {
                "target": pick.target,
                "left": pick.left,
                "right": pick.right,
                "product_size": pick.product_size,
                "candidate": pick.index,
            }
            for pick in tube.chosen
        ],
        "worst_interactions": worst,
        "separation": {
            "classification": "reference-spacing-risk-not-observed-resolution",
            "needed": needed,
            "delivered_by": how,
            "unresolvable": [
                {
                    "a": clash.first,
                    "b": clash.second,
                    "sizes": list(clash.sizes),
                    "apart": clash.apart,
                    "needed": clash.needed,
                }
                for clash in clashes
            ],
            "note": (
                f"Every product in this tube is at least {needed} bp from every "
                f"other, meeting the referenced {how} size-spacing guideline. Actual "
                "resolution remains gel/instrument- and run-specific."
                if not clashes
                else f"{len(clashes)} pair(s) of products are closer together than "
                f"the {needed} bp reference spacing associated with {how}. This flags "
                "a readout-resolution risk; it does not predict an observed band/peak "
                "without the actual gel or instrument conditions."
            ),
        },
    }
