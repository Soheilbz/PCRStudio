"""Nested PCR: two rounds, the second reading inside the first.

The first round amplifies from whatever is in the tube -- often very little, and
often alongside a great deal that is not the target. A little of that reaction
becomes the template for a second round whose primers sit *inside* the first
product. Anything the first round amplified by accident almost never carries
both inner sites as well, so the second round is where the specificity comes
from. It is standard wherever the target is scarce or the sample is dirty:
low-copy pathogen detection, degraded and ancient DNA, environmental samples.

One relationship defines the assay, and this module enforces it:

    forward outer  <  forward inner  <  reverse inner  <  reverse outer

Everything else about nested PCR is a preference. That ordering is not -- a
design that breaks it is not a nested design, whatever it is called.

The search is done twice with the ordinary engine rather than once with a new
one. The outer round is a normal design against the user's target. The inner
round is a normal design restricted to the stretch between the outer primers,
which is what `SEQUENCE_INCLUDED_REGION` means, so every coordinate stays in the
template's own frame and nothing has to be translated back.

Why it walks down the outer candidates rather than taking the best one: the
outer pair Primer3 ranks first can leave no room for an inner pair at all --
too short a product, or a target sitting too close to one end. Taking it and
giving up would report "no nested design exists" when several do. So each outer
candidate is tried in turn, and the ones that had no inner pair are counted and
reported rather than passed over in silence.

Each inner candidate is then held to the thing the search itself cannot see:
the outer product as a background. Whatever round one made is the most
abundant molecule in round two, so an inner primer with a second site on it
would be amplified from it faithfully.

The supported Generation-1 topology is two-tube nested PCR. Each round has
its own annealing step, so a delivered pair that melts cooler outside than in
is reported on the design (`cooler_outer_note`) rather than refused: the two
rounds may simply need independent annealing temperatures. One-tube nested PCR
is a distinct protocol topology and is not inferred or enabled by changing a
policy mode.

Semi-nested designs, where the second round reuses one primer from the first,
are the same machinery with that primer pinned. They are common where one flank
is short or badly conserved and there is only room to move one end inward.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import rt, screen
from . import specificity as spec
from .design import CandidatePair, Constraints, clean_template, design
from .intake import target_to_dict
from .presets import Reaction, thermodynamic_model
from .provenance import provenance
from .registries.authorities import NESTED_AUTHORITY
from .settings import excluded_from, how_many_from, label, prepare
from .thermo import DEFAULT_CONDITIONS, report_to_dict
from .workflow_evidence import evidence_block

#: The most nested designs one run will return.
MOST_NESTS = 20

#: How many inner candidates one outer pair is offered before it is judged.
#:
#: The first pair Primer3 returns can be the one that fails a round-two check,
#: and taking only it would report "no nest here" when the second candidate was
#: fine. Four costs almost nothing: Primer3 has already ranked them.
INNER_CANDIDATES = 4

#: Mismatch tolerance for the scan of the inner primers against the outer
#: product. The same default the standard engine scans backgrounds with, so a
#: primer cannot be clean there and dirty here.
INNER_SCREEN_MISMATCHES = 3

# Carry-over prevention is a protocol choice, not a property of every nested
# reaction. Keep the wire values deliberately small and explicit so a missing
# field cannot be mistaken for a selected chemistry.
CARRYOVER_PREVENTION = ("not-selected", "dutp-ung-strategy-only", "dUTP-UNG")
TRANSFER_MODES = tuple(NESTED_AUTHORITY["groups"]["transfer_modes"])
CLEANUP_PROTOCOLS = tuple(NESTED_AUTHORITY["groups"]["cleanup_protocols"])


class NestedError(ValueError):
    """A request that could not describe a nested design."""


#: Which primer the second round reuses from the first, if any.
SHARES = ("nothing", "forward", "reverse")


@dataclass(frozen=True)
class Nesting:
    """How the two rounds relate to each other."""

    #: Which primer the inner round reuses. `nothing` is a fully nested design.
    shares: str = "nothing"
    #: Whether both rounds happen in one tube.
    #:
    #: Generation-1 has no named, source-backed one-tube protocol contract.
    #: The field remains only as an explicit topology guard so direct callers
    #: cannot turn a two-tube design into a different assay by policy mode.
    single_tube: bool = False
    #: How far inside the outer primers the inner ones must sit.
    #
    #: Zero means only that they must not overlap, which follows from the
    #: ordering and needs no justification. Anything above zero is a
    #: preference, and there is no published number for it -- so there is no
    #: default above zero, and whoever sets one owns the reason.
    margin: int = 0

    def check(self) -> None:
        """Whether these two rounds could relate that way.

        Raises:
            NestedError: naming what was asked for and what exists.
        """
        if self.shares not in SHARES:
            raise NestedError(
                f"`{self.shares}` is not something the second round can reuse. "
                "It reuses: " + ", ".join(SHARES) + "."
            )
        if self.margin < 0:
            raise NestedError(
                f"A margin of {self.margin} would put the inner primers outside "
                "the outer ones, which is the opposite of nesting."
            )
        if self.single_tube:
            raise NestedError(
                "One-tube nested PCR is not an executable Generation-1 topology. "
                "Use the supported two-tube workflow; enabling a one-tube assay requires "
                "a separate named, sourced and versioned protocol contract."
            )


@dataclass(frozen=True)
class Nest:
    """One outer pair and the inner pair that reads inside it."""

    outer: CandidatePair
    inner: CandidatePair
    #: Set when the outer pair melts below the inner one: information, never a
    #: refusal. Two tubes run each round at its own annealing step anyway, so
    #: an inverted pair is an assay that needs two temperatures, not one that
    #: cannot be built. Absent when the practice's hotter-outside relationship
    #: happens to hold.
    tm_note: str | None = None

    def ordering_holds(self) -> bool:
        """Whether this is a nested design at all.

        The one thing that is not a preference. Checked on the way out rather
        than assumed from how it was built, because the assumption is exactly
        what a coordinate mistake would break.
        """
        return (
            self.outer.left_at.start <= self.inner.left_at.start
            and self.inner.right_at.start + self.inner.right_at.length
            <= self.outer.right_at.start + self.outer.right_at.length
            and self.inner.left_at.start < self.inner.right_at.start
        )


@dataclass(frozen=True)
class NestedResult:
    """Every nested design found, and what became of the ones that were not."""

    nests: list[Nest]
    #: How many outer candidates were looked at.
    outer_considered: int
    #: Outer pairs that held no inner pair, and why each of them did not.
    #:
    #: The interesting half of the answer when nothing comes back. "No nested
    #: design exists" and "the four outer pairs we tried were each too short by
    #: about eighty bases" send somebody to different places.
    rejected: list[dict[str, Any]]


def _room_between(
    outer: CandidatePair,
    nesting: Nesting,
) -> tuple[int, int]:
    """The stretch the inner pair may be picked from, in template coordinates.

    Bounded by the outer primers themselves rather than by the outer product:
    an inner primer overlapping an outer one would be amplified by the first
    round as part of its own primer site, which is not nesting.

    Except at the end the second round reuses. A shared primer has to be inside
    the region the search may pick from -- Primer3 refuses a pinned primer that
    is not, which is the right refusal and the wrong region -- so that end
    stretches back to include it.
    """
    if nesting.shares == "forward":
        start = outer.left_at.start
    else:
        start = outer.left_at.start + outer.left_at.length + nesting.margin

    if nesting.shares == "reverse":
        end = outer.right_at.start + outer.right_at.length
    else:
        end = outer.right_at.start - nesting.margin

    return start, end - start


def cooler_outer_note(outer: CandidatePair, inner: CandidatePair) -> str | None:
    """A note for a nest whose outer round melts below its inner one, or `None`.

    Standard two-step nested practice designs the outer primers hotter than
    the inner ones, so that both rounds can reuse one annealing temperature
    where that is convenient. Two tubes give each round its own annealing step
    regardless, so a delivered pair that came out cooler outside than in is an
    assay that needs two temperatures -- said on the design rather than
    treated as a refusal, because nothing about it stops the assay working.

    Only meaningful for fully nested rounds. A semi-nested round shares one
    primer with the outer pair, so that primer's melting temperature counts on
    both sides of the comparison; the shared primer already ties the rounds'
    temperatures together and there is nothing informative to say.
    """
    outer_cooler = min(outer.left.tm, outer.right.tm)
    inner_warmer = max(inner.left.tm, inner.right.tm)
    if outer_cooler >= inner_warmer:
        return None
    return (
        f"The outer pair melts down to {outer_cooler:.1f} C while the inner "
        f"pair reaches {inner_warmer:.1f} C: the outer round melts below the "
        "inner, so the two rounds need independent annealing temperatures "
        "rather than one shared step."
    )


def _own_site(site: spec.Site, inner: CandidatePair, offset: int) -> bool:
    """Whether a site found in the outer product is where this primer belongs.

    The inner primers sit inside the outer product by definition -- nesting is
    that -- so the intended site is not an intruder. What is left when it has
    been recognised and removed is everything an abundant round-one product
    would offer the primer besides its own place. The contig scanned is the
    outer amplicon string itself, which begins at `offset` in template
    coordinates. A right primer is reported by its highest plus-strand base
    (`Placement`, reading right to left), and the scanner reports a reverse
    site by the lowest base of the same footprint -- so the expected position
    is that footprint's far end, `length - 1` below where the placement sits.
    """
    if site.role == "left":
        expected = inner.left_at.start + inner.left_at.length - 1 - offset
        return site.orientation == "forward" and site.three_prime_at == expected
    expected = inner.right_at.start - inner.right_at.length + 1 - offset
    return site.orientation == "reverse" and site.three_prime_at == expected


def foreign_sites_in_outer_product(
    inner: CandidatePair,
    offset: int,
    outer_amplicon: str,
    reaction: Reaction,
) -> list[spec.Site]:
    """Where these inner primers would land inside the outer product uninvited.

    After the first round there are copies of the outer product everywhere the
    first pair reached. An inner primer with a second site on that molecule is
    no longer merely untidy: its unintended target now outnumbers everything
    else in the tube, and the second round faithfully amplifies from it. The
    intended sites -- one per primer, where the design put them -- are excused;
    every other binding strong enough to prime is reported, worst first.
    """
    background = [spec.Contig(name="the outer product", sequence=outer_amplicon)]
    sites = spec.sites_for(
        inner.left.sequence,
        "left",
        background,
        reaction=reaction,
        max_mismatches=INNER_SCREEN_MISMATCHES,
        min_dg=None,
    ) + spec.sites_for(
        inner.right.sequence,
        "right",
        background,
        reaction=reaction,
        max_mismatches=INNER_SCREEN_MISMATCHES,
        min_dg=None,
    )
    intruders = [site for site in sites if not _own_site(site, inner, offset)]
    intruders.sort(key=lambda site: site.dg)
    return intruders


def design_nested(
    template: str,
    *,
    outer: Constraints,
    inner: Constraints,
    nesting: Nesting | None = None,
    target_start: int | None = None,
    target_length: int | None = None,
    conditions: dict[str, float] | None = None,
    outer_conditions: dict[str, float] | None = None,
    inner_conditions: dict[str, float] | None = None,
    how_many: int = 5,
    outer_candidates: int = 10,
    #: Stretches no primer of either round may overlap.
    #:
    #: Both rounds, deliberately: excluding a stretch from the inner pair only
    #: would leave the outer round free to sit on it, and the outer product is
    #: what the inner round then reads from.
    excluded: list[tuple[int, int]] | None = None,
    masked: bool = False,
) -> NestedResult:
    """Outer and inner pairs, in that relationship, for one template.

    Args:
        outer: What the first round's pair must satisfy. Its product sizes are
            the ones a gel would show from round one.
        inner: What the second round's pair must satisfy, and the product
            people actually read.
        nesting: How the rounds relate. Fully nested with no margin by default.
        target_start: First base the *inner* product must contain. The outer
            product contains it too, necessarily.
        outer_candidates: How many outer pairs to try before giving up. More
            costs one extra Primer3 call each and is the difference between
            "no nested design exists" and "the first one had no room".

    Raises:
        NestedError: for a nesting that could not exist.
    """
    nesting = nesting or Nesting()
    nesting.check()
    outer_conditions = outer_conditions if outer_conditions is not None else conditions
    inner_conditions = inner_conditions if inner_conditions is not None else conditions

    # Cleaned once here rather than only inside `design`: the outer amplicon
    # is cut out of this string by coordinate below, and the coordinates the
    # search returns are in the cleaned string's frame.
    sequence = clean_template(template)
    if inner_conditions is None:
        scan_reaction = Reaction(**DEFAULT_CONDITIONS)
    elif isinstance(inner_conditions, Reaction):
        scan_reaction = inner_conditions
    else:
        scan_reaction = Reaction(**{**DEFAULT_CONDITIONS, **inner_conditions})

    first = design(
        template,
        target_start=target_start,
        target_length=target_length,
        constraints=outer,
        conditions=outer_conditions,
        how_many=outer_candidates,
        masked=masked,
        excluded=excluded,
    )

    nests: list[Nest] = []
    rejected: list[dict[str, Any]] = []

    for candidate in first.pairs:
        if len(nests) >= how_many:
            break

        start, length = _room_between(candidate, nesting)
        if length < inner.product_min:
            rejected.append(
                {
                    "outer_at": [candidate.left_at.start, candidate.right_at.start],
                    "outer_product": candidate.product_size,
                    "reason": "no room for an inner product",
                    "detail": (
                        f"{length} bases lie between these outer primers and the "
                        f"shortest inner product asked for is {inner.product_min}."
                    ),
                }
            )
            continue

        if (
            target_start is not None
            and target_length is not None
            and (target_start < start or target_start + target_length > start + length)
        ):
            rejected.append(
                {
                    "outer_at": [candidate.left_at.start, candidate.right_at.start],
                    "outer_product": candidate.product_size,
                    "reason": "the target does not fit inside",
                    "detail": (
                        f"the target at {target_start}..{target_start + target_length} "
                        f"is not inside {start}..{start + length}, which is all the "
                        "room these outer primers leave"
                    ),
                }
            )
            continue

        try:
            second = design(
                template,
                target_start=target_start,
                target_length=target_length,
                included=(start, length),
                pinned_left=(candidate.left.sequence if nesting.shares == "forward" else None),
                pinned_right=(candidate.right.sequence if nesting.shares == "reverse" else None),
                constraints=inner,
                conditions=inner_conditions,
                how_many=INNER_CANDIDATES,
                masked=masked,
                excluded=excluded,
            )
        except ValueError as error:
            rejected.append(
                {
                    "outer_at": [candidate.left_at.start, candidate.right_at.start],
                    "outer_product": candidate.product_size,
                    "reason": "the inner search was refused",
                    "detail": str(error),
                }
            )
            continue

        if not second.pairs:
            rejected.append(
                {
                    "outer_at": [candidate.left_at.start, candidate.right_at.start],
                    "outer_product": candidate.product_size,
                    "reason": "no inner pair survived",
                    "detail": (
                        second.considered.get("pair", "")
                        or "Primer3 found nothing acceptable in the room available."
                    ),
                }
            )
            continue

        # ── The outer product is a template now ──────────────────────────────
        #
        # Whatever these outer primers made becomes the most abundant molecule
        # in round two, so each inner candidate is checked against it: an inner
        # primer with somewhere else to sit on that molecule would amplify from
        # the very product round one made by accident.
        amplicon_offset = candidate.left_at.start
        # Through the right primer's last base: `Placement` reports a right
        # primer by its highest plus-strand base, so that base is the end.
        outer_amplicon = sequence[amplicon_offset : candidate.right_at.start + 1]

        chosen: Nest | None = None
        failures: list[dict[str, str]] = []
        for inner_candidate in second.pairs:
            nest = Nest(
                outer=candidate,
                inner=inner_candidate,
                tm_note=(
                    # A shared primer melts in both rounds, so the comparison
                    # has nothing informative to say about a semi-nested
                    # design. Generation-1 executes only the two-tube topology.
                    cooler_outer_note(candidate, inner_candidate)
                    if nesting.shares == "nothing"
                    else None
                ),
            )
            if not nest.ordering_holds():
                # Not reachable by construction, which is exactly why it is
                # checked: the construction is what a coordinate mistake breaks.
                raise NestedError(
                    "an inner pair came back outside its outer pair, which means the "
                    "region the inner search was given was wrong"
                )

            intruders = foreign_sites_in_outer_product(
                nest.inner, amplicon_offset, outer_amplicon, scan_reaction
            )
            if intruders:
                worst = intruders[0]
                failures.append(
                    {
                        "reason": "an inner primer has a second site in the outer product",
                        "detail": (
                            f"an inner {worst.role} primer also binds inside the "
                            f"outer product at position {worst.three_prime_at - amplicon_offset + 1}"
                            f"{f' with {worst.mismatches} mismatches' if worst.mismatches else ''}, "
                            f"at {worst.dg} kcal/mol. After round one that molecule "
                            "outnumbers everything else in the tube, and the second "
                            f"round would amplify from it — {len(intruders)} unwanted "
                            "site(s) found."
                        ),
                    }
                )
                continue

            chosen = nest
            break

        if chosen is None:
            rejected.append(
                {
                    "outer_at": [candidate.left_at.start, candidate.right_at.start],
                    "outer_product": candidate.product_size,
                    "reason": failures[0]["reason"],
                    "detail": " ".join(failure["detail"] for failure in failures),
                }
            )
            continue

        nests.append(chosen)

    return NestedResult(
        nests=nests,
        outer_considered=len(first.pairs),
        rejected=rejected,
    )


def nest_to_dict(nest: Nest, *, shares: str = "nothing") -> dict[str, Any]:
    """One nested design, both rounds, in the template's own coordinates."""

    def round_of(pair: CandidatePair) -> dict[str, Any]:
        return {
            "left": report_to_dict(pair.left),
            "right": report_to_dict(pair.right),
            "left_at": {"start": pair.left_at.start, "length": pair.left_at.length},
            "right_at": {"start": pair.right_at.start, "length": pair.right_at.length},
            "product_size": pair.product_size,
            "tm_difference": pair.tm_difference,
            "cross_dimer_dg": pair.cross_dimer_dg,
            "penalty": pair.penalty,
        }

    answer = {
        "outer": round_of(nest.outer),
        "inner": round_of(nest.inner),
        "shares": shares,
        # How far the second round moved in at each end. The number somebody
        # asks about when they are deciding whether a design is really nested
        # or just two pairs that happen to overlap.
        "moved_in": {
            "left": nest.inner.left_at.start - nest.outer.left_at.start,
            "right": (nest.outer.right_at.start + nest.outer.right_at.length)
            - (nest.inner.right_at.start + nest.inner.right_at.length),
        },
    }
    if nest.tm_note:
        answer["tm_note"] = nest.tm_note
    return answer


def _reaction_conditions(base: dict[str, float], supplied: Any, *, label: str) -> dict[str, float]:
    if supplied is None:
        return dict(base)
    if not isinstance(supplied, dict):
        raise NestedError(
            f"{label} must be an object of explicit thermodynamic reaction conditions"
        )
    allowed = set(Reaction.__dataclass_fields__)
    strange = sorted(set(supplied) - allowed)
    if strange:
        raise NestedError(f"unknown {label} condition(s): {', '.join(strange)}")
    merged = {**base, **supplied}
    # Construction validates physical/non-negative constraints consistently.
    return Reaction(**merged).as_conditions()


def _transfer_contract(request: dict[str, Any]) -> dict[str, Any]:
    mode = str(request.get("transfer_mode") or "direct-transfer")
    if mode not in TRANSFER_MODES:
        raise NestedError("transfer_mode must be one of: " + ", ".join(TRANSFER_MODES))
    cleanup = str(request.get("cleanup_protocol") or "not-selected")
    if cleanup not in CLEANUP_PROTOCOLS:
        raise NestedError("cleanup_protocol must be one of: " + ", ".join(CLEANUP_PROTOCOLS))
    implied = {
        "msz-exonuclease-i": "neb-msz-exonuclease-i",
        "thermolabile-exonuclease-i": "neb-thermolabile-exonuclease-i",
    }.get(mode)
    if implied and cleanup not in {"not-selected", implied}:
        raise NestedError(
            f"{mode} is incompatible with cleanup_protocol={cleanup}; choose {implied}"
        )
    if implied:
        cleanup = implied
    factor = request.get("transfer_dilution_factor")
    if mode == "diluted-transfer":
        if isinstance(factor, bool) or not isinstance(factor, (int, float)) or float(factor) <= 1:
            raise NestedError("diluted-transfer requires transfer_dilution_factor > 1")
    else:
        factor = None
    volume = request.get("transfer_volume_ul", request.get("transfer_volume_uL"))
    if volume is not None and (
        isinstance(volume, bool) or not isinstance(volume, (int, float)) or float(volume) <= 0
    ):
        raise NestedError("transfer_volume_uL must be positive when supplied")
    record = None if cleanup == "not-selected" else dict(NESTED_AUTHORITY["records"][cleanup])
    if (
        record
        and volume is not None
        and float(volume) > float(record["first_round_product_uL_max"])
    ):
        raise NestedError(
            f"transfer_volume_uL exceeds the reviewed {record['first_round_product_uL_max']} uL first-round-product boundary for {cleanup}"
        )
    return {
        "mode": mode,
        "transfer_volume_ul": float(volume) if volume is not None else None,
        "dilution_factor": float(factor) if factor is not None else None,
        "cleanup_protocol": cleanup,
        "cleanup": record,
        "custom_sop_reference": str(request.get("custom_transfer_sop") or "").strip() or None,
        "claim_boundary": "Transfer provenance is empirical workflow metadata. PCRStudio does not infer sterility, carry-over control or cleanup success from the selected label.",
    }


def _nested_false_product_graph(
    outer_scan: dict[str, Any],
    inner_named: dict[str, str],
    contigs: list[spec.Contig],
    reaction: Reaction,
) -> dict[str, Any]:
    """Rescan every reported outer off-target product for a viable inner amplicon."""
    if not outer_scan.get("checked"):
        return {
            "checked": False,
            "edges": [],
            "claim_boundary": "No finite background was supplied, so causal nested off-target propagation was not evaluated.",
        }
    by_name = {c.name: c for c in contigs}
    edges = []
    for product in outer_scan.get("products", []):
        contig = by_name.get(str(product.get("contig")))
        if contig is None:
            continue
        start = max(0, int(product.get("start", 1)) - 1)
        end = min(len(contig.sequence), int(product.get("end", 0)))
        if end <= start:
            continue
        outer_product = contig.sequence[start:end]
        local = screen.oligos(
            inner_named,
            [
                spec.Contig(
                    name=f"outer-offtarget:{contig.name}:{start + 1}-{end}", sequence=outer_product
                )
            ],
            reaction=reaction,
            max_product=max(50, len(outer_product)),
            max_products=4,
        )
        edges.append(
            {
                "outer_product": {
                    "contig": contig.name,
                    "start": start + 1,
                    "end": end,
                    "size": len(outer_product),
                },
                "inner_product_count": int(local.get("product_count", 0)),
                "inner_products": local.get("products", []),
                "risk": "nested-false-product"
                if local.get("product_count", 0)
                else "no-inner-product-detected",
            }
        )
    return {
        "checked": True,
        "edges": edges,
        "propagating_outer_products": sum(e["inner_product_count"] > 0 for e in edges),
        "method": "outer off-target product -> exact inner-primer rescan on that product sequence",
        "claim_boundary": "Finite supplied background only; absence here is not global specificity.",
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    """One nested design, end to end, in the shape the interface reads.

    The two rounds carry their own constraints, so the shared preamble is asked
    for the outer set and the inner set is layered the same way by hand -- an
    inner round with no constraints of its own inherits the assay's, which is
    what somebody means when they only fill in half the form.

    Raises:
        IntakeError: the input is not a usable template.
        NestedError: a nesting that could not exist.
        ValueError: a constraint, preset or reaction that cannot hold.
    """
    chosen = prepare(request, constraints_key="outer")
    how_many = how_many_from(request, MOST_NESTS)

    inner_supplied = request.get("inner") or {}
    strange = sorted(set(inner_supplied) - set(Constraints.__dataclass_fields__))
    if strange:
        raise ValueError(f"unknown constraint(s) for the inner round: {', '.join(strange)}")
    inner = Constraints(
        **{
            **chosen.intent.constraints,
            **chosen.assay_constraints,
            **inner_supplied,
        }
    )

    if inner.product_max >= chosen.limits.product_max:
        raise ValueError(
            f"The inner product is allowed up to {inner.product_max} bases and the "
            f"outer up to {chosen.limits.product_max}. The second round reads inside "
            "the first, so it has to be the shorter one."
        )

    if chosen.assay_id == "nested-pcr":
        for key, explicit in (
            ("shares", "nothing"),
            ("margin", "0"),
            ("single_tube", "false"),
            ("carryover_prevention", "not-selected"),
            ("transfer_mode", "direct-transfer"),
            ("cleanup_protocol", "not-selected"),
        ):
            if key not in request or request.get(key) is None:
                raise ValueError(
                    f"nested-pcr requires explicit `{key}`; use `{explicit}` when that is the intended value rather than relying on omission."
                )
        if bool(request.get("single_tube")):
            raise ValueError(
                "One-tube nested PCR is not an executable Generation-1 topology. "
                "Use the supported two-tube workflow; enabling a one-tube assay requires a separate named, sourced and versioned protocol contract."
            )

    nesting = Nesting(
        shares=str(request.get("shares") or "nothing"),
        margin=int(request.get("margin") if request.get("margin") is not None else 0),
        single_tube=bool(request.get("single_tube")),
    )
    nesting.check()

    carryover_prevention = str(request.get("carryover_prevention") or "not-selected")
    if carryover_prevention == "dutp-ung-strategy-only":
        carryover_prevention = "dutp-ung-strategy-only"
    if carryover_prevention not in CARRYOVER_PREVENTION:
        raise ValueError("carryover_prevention must be one of: " + ", ".join(CARRYOVER_PREVENTION))

    transfer = _transfer_contract(request)
    round1_conditions = _reaction_conditions(
        chosen.reaction.as_conditions(), request.get("round1_reaction"), label="round1_reaction"
    )
    round2_conditions = _reaction_conditions(
        chosen.reaction.as_conditions(), request.get("round2_reaction"), label="round2_reaction"
    )

    found = design_nested(
        chosen.target.sequence,
        outer=chosen.limits,
        inner=inner,
        nesting=nesting,
        target_start=request.get("target_start"),
        target_length=request.get("target_length"),
        outer_conditions=round1_conditions,
        inner_conditions=round2_conditions,
        how_many=how_many,
        masked=chosen.target.soft_masked,
        excluded=excluded_from(request),
    )

    designs = [nest_to_dict(nest, shares=nesting.shares) for nest in found.nests]
    name = label(chosen.target.name)

    # ── Where else these four oligos could sit ──────────────────────────────
    #
    # This engine took no background at all, and the gap was recorded rather
    # than papered over: nesting is often *chosen* because the target is rare
    # in a large background, which is exactly when a specificity check matters
    # most. The outer round can misprime, and nesting only forgives that once
    # the inner round is faithfully amplifying whatever the outer one made — so
    # an outer pair with a second site produces a second template for the inner
    # round to work on, and the second round makes it plentiful.
    #
    # Which oligos share a tube is the question, and this assay answers it
    # differently depending on how it is run. In two tubes the outer primers
    # are diluted a hundredfold into the second and only the inner pair
    # matters; in one tube all four are present throughout, and an outer primer
    # facing an inner one is a real product that a two-tube scan would be wrong
    # to report. So the scan is run the way the reaction is.
    from . import screen

    contigs, template_only, fold_at = screen.contigs_for(
        request, template=chosen.target.sequence, name=chosen.target.name
    )
    for entry, nest in zip(designs, found.nests, strict=True):
        rounds = (
            [
                (
                    "both rounds in one tube",
                    {
                        "outer left": nest.outer.left.sequence,
                        "outer right": nest.outer.right.sequence,
                        "inner left": nest.inner.left.sequence,
                        "inner right": nest.inner.right.sequence,
                    },
                    [nest.outer.product_size, nest.inner.product_size],
                    [nest.outer.amplicon, nest.inner.amplicon],
                    Reaction(**round2_conditions),
                )
            ]
            if nesting.single_tube
            else [
                (
                    "first round",
                    {
                        "left": nest.outer.left.sequence,
                        "right": nest.outer.right.sequence,
                    },
                    [nest.outer.product_size],
                    [nest.outer.amplicon],
                    Reaction(**round1_conditions),
                ),
                (
                    "second round",
                    {
                        "left": nest.inner.left.sequence,
                        "right": nest.inner.right.sequence,
                    },
                    [nest.inner.product_size],
                    [nest.inner.amplicon],
                    Reaction(**round2_conditions),
                ),
            ]
        )

        entry["off_targets"] = {
            where: screen.oligos(
                named,
                contigs,
                reaction=round_reaction,
                fold_at=fold_at,
                max_product=screen.product_ceiling(chosen.limits.product_max),
                intended_sizes=intended,
                intended_products=products,
            )
            for where, named, intended, products, round_reaction in rounds
        }
        entry["nested_false_product_graph"] = _nested_false_product_graph(
            entry["off_targets"].get("first round", {"checked": False}),
            {"left": nest.inner.left.sequence, "right": nest.inner.right.sequence},
            contigs,
            Reaction(**round2_conditions),
        )

    return {
        "engine": "nested",
        # A property of the run rather than of a design: the same hold, at the
        # same temperature, whichever candidate you pick. `None` says the
        # question was never put — this assay's page does not ask it.
        "reverse_transcription": rt.block(polymerase=chosen.preset.name)
        if rt.wanted(request)
        else None,
        "provenance": provenance(chosen.reaction.as_conditions()),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **chosen.reaction.as_conditions(),
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "round_reactions": {
            "round1": {
                "conditions": round1_conditions,
                "polymerase_identity": str(request.get("round1_polymerase") or chosen.preset.id),
                "thermal_program": request.get("round1_thermal_program") or [],
                "claim_boundary": "Caller-declared program; PCRStudio does not infer an annealing schedule from screening Tm.",
            },
            "round2": {
                "conditions": round2_conditions,
                "polymerase_identity": str(request.get("round2_polymerase") or chosen.preset.id),
                "thermal_program": request.get("round2_thermal_program") or [],
                "claim_boundary": "Caller-declared program; PCRStudio does not infer an annealing schedule from screening Tm.",
            },
        },
        "transfer": transfer,
        "workflow_evidence": evidence_block(request.get("workflow_evidence")),
        "contamination_evidence_contract": {
            "required_fields": [
                "round1_ntc",
                "round2_ntc",
                "positive_control",
                "pre_pcr_area",
                "round1_area",
                "transfer_area",
                "round2_area",
                "transfer_run_id",
            ],
            "optional_fields": [
                "operator",
                "timestamp",
                "source_tube_or_well",
                "destination_tube_or_well",
                "raw_data_reference",
            ],
            "claim_boundary": "Physical separation and controls are recorded evidence; they cannot be inferred from primer geometry or a cleanup selection.",
        },
        "constraints": {
            "outer": {
                field: getattr(chosen.limits, field) for field in Constraints.__dataclass_fields__
            },
            "inner": {field: getattr(inner, field) for field in Constraints.__dataclass_fields__},
        },
        "nesting": {
            "shares": nesting.shares,
            "margin": nesting.margin,
            "single_tube": False,
            # Diagnostic only: two tubes may use independent annealing steps,
            # so this difference is reported rather than treated as a gate.
            "tm_separation": round(chosen.limits.tm_min - inner.tm_max, 1),
            "note": (
                "Two tubes: a little of the first reaction becomes the template for "
                "the second. Each round anneals at its own temperature in its own "
                "tube, so no design is refused for the rounds' melting temperatures; "
                "where a pair came out cooler outside than in, that design says so "
                "and needs two annealing steps rather than one."
            ),
        },
        # How far the scan looked, said once rather than implied per design.
        "background": screen.summary(contigs, template_only),
        "nests": designs,
        "outer_considered": found.outer_considered,
        "rejected": found.rejected,
        # Carry-over prevention is deliberately explicit. `dUTP-UNG` is a
        # strategy identity only in Gen-1: without a named kit/SOP there is no
        # authority for substitution ratio, UNG identity/amount, incubation or
        # inactivation. Do not turn a contamination-control idea into a bench recipe.
        "protocol": {
            "selection": carryover_prevention,
            "execution_status": "strategy-only"
            if carryover_prevention == "dutp-ung-strategy-only"
            else "not-selected",
            "note": (
                "dUTP/UNG carry-over prevention was selected as a strategy, not as an executable bench protocol. "
                "PCRStudio has no named kit/SOP here for dUTP substitution ratio, UNG identity or amount, incubation/inactivation, polymerase compatibility or controls; resolve those from a named protocol before bench use."
                if carryover_prevention == "dutp-ung-strategy-only"
                else "No carry-over prevention strategy was selected. This does not imply contamination control passed; use physical separation, controls and the named assay protocol appropriate to the experiment."
            ),
        },
        "why_nothing": (
            ""
            if designs
            else (
                f"None of the {found.outer_considered} outer pairs held an inner "
                "pair. The reasons are listed above, one per outer pair."
                if found.rejected
                else "No outer pair survived, so there was nothing to nest inside."
            )
        ),
        # Both rounds, because both get ordered. Named by round so nobody puts
        # the inner pair in the first tube.
        "order_sheet": [
            {
                "name": f"{name}_{index}{round_name}{role}",
                "sequence": design[which][side]["sequence"],
                "annealing_sequence": design[which][side]["sequence"],
                "tail_sequence": "",
                "kind": "primer",
                "length": design[which][side]["length"],
                "gc_percent": design[which][side]["gc_percent"],
                "tm": design[which][side]["tm"],
            }
            for index, design in enumerate(designs, start=1)
            for which, round_name in (("outer", "o"), ("inner", "i"))
            for side, role in (("left", "F"), ("right", "R"))
        ],
    }
