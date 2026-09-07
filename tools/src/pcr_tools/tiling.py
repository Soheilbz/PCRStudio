"""Overlapping amplicons covering something too long for one reaction.

A whole viral genome, or a gene nobody can amplify in one piece, is sequenced
by tiling it: a series of amplicons that overlap their neighbours, so every base
is covered by something and the pieces can be put back together.

Two things make this a different engine rather than a loop around the ordinary
one.

The amplicons are not independent. Neighbours overlap, so they must go in
different tubes — two primers that overlap the same stretch would amplify each
other's short products in preference to the real ones, and the reaction would
fill up with the shortest thing it could make. Alternating pools is how that is
avoided, and it means the answer is not a list of pairs but two lists.

And there is no target. Every other engine here is given a region and asked to
amplify across it; this one is given a length and asked to cover all of it,
which turns the search into a walk with a decision at every step: where the next
amplicon starts is fixed by where the last one ended, less the overlap.

What that makes possible, and what this engine reports because of it: a gap. If
no acceptable amplicon can be placed somewhere, the scheme does not fail — it
has a hole, and saying exactly where the hole is worth more than refusing the
whole design. A tiling scheme with a known gap is usable; one that silently
skipped a region is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .design import CandidatePair, Constraints, clean_template, design
from .intake import target_to_dict
from .multiplex import badness
from .presets import thermodynamic_model
from .provenance import provenance
from .settings import excluded_from, label, prepare
from .thermo import DEFAULT_CONDITIONS


class TilingError(ValueError):
    """A scheme that could not be laid out."""


#: How much each amplicon must share with its neighbour.
#:
#: Enough that the join can be made unambiguously and that a base near an
#: amplicon's end — where coverage is always thinnest — is covered properly by
#: the next one along. A tuning parameter with a mechanism rather than a
#: citation; published schemes use tens of bases.
OVERLAP = 75

#: How far the search may slide an amplicon's start looking for a pair.
#:
#: Without this the walk is brittle: one stretch where no primer can sit stops
#: the whole scheme. With it, the walk shuffles along until it finds somewhere
#: workable and reports how far it had to move.
SLIDE = 200

# Keep the worker's direct-call contract aligned with the Rust request gate.
MAX_POOLS = 6


@dataclass(frozen=True)
class Tile:
    """One amplicon in the scheme."""

    index: int
    #: Which tube it goes in. Neighbours are never in the same one.
    pool: int
    pair: CandidatePair
    start: int
    end: int
    #: How long the circle is, for a tile laid on one. `None` for a line.
    #:
    #: Kept rather than folded away: a tile that crosses the join has an `end`
    #: past the last base, which is the only honest way to say "this one closes
    #: the circle" in two numbers.
    circle: int | None = None

    def crosses_the_join(self) -> bool:
        return self.circle is not None and self.end > self.circle

    def covers(self) -> range | list[int]:
        if not self.crosses_the_join():
            return range(self.start, self.end)
        # Two stretches, and the second is at the beginning of the sequence.
        assert self.circle is not None
        return list(range(self.start, self.circle)) + list(range(0, self.end % self.circle))


@dataclass
class Scheme:
    """A whole tiling, and what it could not cover."""

    tiles: list[Tile] = field(default_factory=list)
    #: Stretches no acceptable amplicon could be placed over.
    #:
    #: Reported rather than raised. A scheme with a known hole is usable and a
    #: scheme that silently skipped a region is not.
    gaps: list[dict[str, Any]] = field(default_factory=list)
    #: How the walk went, so the layout is not a list of numbers from nowhere.
    steps: list[str] = field(default_factory=list)

    def pools(self) -> dict[int, list[Tile]]:
        grouped: dict[int, list[Tile]] = {}
        for tile in self.tiles:
            grouped.setdefault(tile.pool, []).append(tile)
        return grouped

    def covered(self) -> int:
        """How many bases at least one amplicon reaches."""
        if not self.tiles:
            return 0
        seen: set[int] = set()
        for tile in self.tiles:
            seen.update(tile.covers())
        return len(seen)


def lay_out(
    template: str,
    *,
    constraints: Constraints | None = None,
    conditions: dict[str, float] | None = None,
    overlap: int = OVERLAP,
    slide: int = SLIDE,
    pools: int = 2,
    circular: bool = False,
    excluded: list[tuple[int, int]] | None = None,
) -> Scheme:
    """Walk the template, placing an amplicon at a time.

    Each amplicon starts where the last one ended less the overlap. Where no
    acceptable pair can be placed, the start slides forward until one can be,
    and whatever was skipped is recorded as a gap rather than passed over.

    A `circular` sequence has no last tile: the walk continues past the end
    into a repeat of the beginning, so the final amplicon closes the circle
    rather than stopping at a boundary that is only where the file happens to
    start. Leaving that join uncovered is the commonest hole in a tiling scheme
    and the hardest to notice, because every tile in the report looks correct.

    Raises:
        TilingError: for a layout that could not be attempted at all.
    """
    limits = constraints or Constraints()
    limits.validate()
    reaction = {**DEFAULT_CONDITIONS, **(conditions or {})}

    # Development-only internal-walker preconditions. These are properties of
    # this fallback algorithm, not Scientific-Strict tiled-PCR validity rules;
    # release execution is owned by PrimalScheme3 and follows its own CLI
    # contract (including n-pools >= 1 and min-overlap >= 0).
    if pools < 2:
        raise TilingError(
            "The internal development tiler requires at least two alternating pools; "
            "this is an implementation precondition, not a universal tiled-PCR rule."
        )
    if pools > MAX_POOLS:
        raise TilingError(
            f"The internal development tiler is implemented for at most {MAX_POOLS} pools; "
            "this software ceiling is not a biological validity limit."
        )
    if overlap < 1:
        raise TilingError(
            "The internal development tiler requires positive overlap to advance its "
            "coverage walk; PrimalScheme3 Scientific-Strict execution has its own input contract."
        )
    if slide < 0:
        raise TilingError(f"`slide` cannot be negative: {slide}.")
    if overlap >= limits.product_min:
        raise TilingError(
            f"An overlap of {overlap} bases is not less than the shortest amplicon "
            f"asked for, {limits.product_min}. Each amplicon would begin before the "
            "one before it ended, and the walk would never move forward."
        )
    if len(template) < limits.product_min:
        raise TilingError(
            f"The template is {len(template)} bases and the shortest amplicon asked "
            f"for is {limits.product_min}. There is nothing here to tile."
        )

    scheme = Scheme()
    at = 0
    index = 0

    # The real length, before any repeat is added to close the circle.
    around = len(template) if circular else None
    if circular:
        # Enough of the beginning for one more amplicon to be placed over the
        # join, and no more: a longer repeat would let the walk lay a second
        # lap of tiles over sequence already covered.
        template = template + template[: limits.product_max + slide]

    stop_at = around if circular else len(template) - overlap
    assert stop_at is not None
    while at < stop_at:
        # A generous window: the search needs room to find a pair, and the
        # product-size limits are what actually decide the amplicon.
        window_end = min(len(template), at + limits.product_max + slide)
        if window_end - at < limits.product_min:
            break

        placed = _place(template, at, window_end, limits, reaction, slide, excluded)
        if placed is None:
            # Nothing anywhere in reach. Record what is being skipped and jump
            # past it rather than stopping the whole scheme.
            skipped_to = min(len(template), at + limits.product_max)
            scheme.gaps.append(
                {
                    "from": at,
                    "to": skipped_to,
                    "bases": skipped_to - at,
                    "why": (
                        "No pair satisfying the constraints could be placed here, "
                        f"even sliding the start by up to {slide} bases."
                    ),
                }
            )
            at = skipped_to - overlap
            continue

        pair, window_start, slipped = placed
        start = window_start + pair.left_at.start
        end = window_start + pair.right_at.start + pair.right_at.length

        if slipped:
            scheme.gaps.append(
                {
                    "from": at,
                    "to": at + slipped,
                    "bases": slipped,
                    "why": (
                        f"The walk had to slide {slipped} bases before a pair could "
                        "be placed, so the overlap here is that much thinner."
                    ),
                }
            )

        scheme.tiles.append(
            Tile(
                index=index,
                pool=index % pools,
                pair=pair,
                start=start,
                end=end,
                circle=around,
            )
        )
        index += 1
        at = end - overlap

        # A circle is closed when the walk has come back past where the first
        # amplicon began. Stopping at the sequence's end instead placed one
        # more tile over ground the closing tile already covered — coverage
        # said 100% either way, so the redundant amplicon was an oligo pair
        # somebody would have ordered and never needed.
        if around is not None and scheme.tiles and end >= around + scheme.tiles[0].start:
            break

    length = around if around is not None else len(template)
    scheme.steps.append(
        f"{len(scheme.tiles)} amplicon(s) across {length:,} bases, in "
        f"{pools} pools, overlapping by {overlap}."
    )
    if around is not None:
        closing = [tile for tile in scheme.tiles if tile.crosses_the_join()]
        scheme.steps.append(
            f"The sequence is a circle, so the walk closed it: amplicon "
            f"{closing[0].index + 1} spans the join between the last base and "
            f"the first."
            if closing
            else (
                "The sequence is a circle and no amplicon could be placed over "
                "the join, so the base where the file begins is not covered. "
                "The gap is listed below."
            )
        )
    if scheme.gaps:
        scheme.steps.append(
            f"{len(scheme.gaps)} place(s) where the walk could not place an "
            "amplicon cleanly. Each is listed with what it covers."
        )
    return scheme


#: How much room the search is given before the base an amplicon must reach.
#:
#: Without it the left primer would have exactly one place it could start, and
#: a tiling scheme would fail wherever that one place happens to be a bad
#: primer. With it the search has a stretch to choose from and the overlap is
#: still guaranteed, because the product has to span the base at the far end of
#: that stretch.
ROOM = 120


def _place(
    template: str,
    reach: int,
    window_end: int,
    limits: Constraints,
    reaction: dict[str, float],
    slide: int,
    excluded: list[tuple[int, int]] | None = None,
) -> tuple[CandidatePair, int, int] | None:
    """A pair whose product covers `reach`, and where its window began.

    The amplicon is *required* to span `reach` rather than merely to start near
    it. Without that requirement the search places the left primer wherever it
    likes in the window, and a scheme comes back with holes between amplicons
    that are supposed to overlap -- measured on the mitochondrial genome, an
    84-base hole between two neighbours that were meant to share 75.

    Returns:
        The pair, where its window started in the template, and how far the
        base it had to reach was allowed to slide.
    """
    for slipped in range(0, slide + 1, 25):
        must_reach = reach + slipped
        window_start = max(0, must_reach - ROOM)
        if window_end - window_start < limits.product_min:
            return None
        try:
            found = design(
                template[window_start:window_end],
                # In the slice's own coordinates. The product must contain this
                # base, which is what makes the overlap real.
                target_start=must_reach - window_start,
                target_length=1,
                constraints=limits,
                conditions=reaction,
                how_many=1,
                # Translated into the slice's coordinates, and clipped to it.
                # A region that falls entirely outside this window is not this
                # amplicon's problem, and passing it as a negative start would
                # make Primer3 refuse the whole search.
                excluded=_within(excluded, window_start, window_end),
            )
        except ValueError:
            continue
        if found.pairs:
            return found.pairs[0], window_start, slipped
    return None


def _within(excluded: list[tuple[int, int]] | None, start: int, end: int) -> list[tuple[int, int]]:
    """The parts of each excluded stretch that fall inside one window.

    A tiling scheme searches a slice at a time, and Primer3 is given the slice
    rather than the whole sequence — so a region expressed against the whole
    has to be moved into the slice's coordinates and cut to fit it. A stretch
    that misses the window entirely is dropped rather than clamped to its edge,
    which would exclude sequence nobody asked to exclude.
    """
    if not excluded:
        return []
    inside: list[tuple[int, int]] = []
    for at, length in excluded:
        first = max(at, start)
        last = min(at + length, end)
        if last > first:
            inside.append((first - start, last - first))
    return inside


def interactions(scheme: Scheme) -> list[dict[str, Any]]:
    """What the oligos in each tube do to each other.

    Per pool rather than across the whole scheme, because that is what shares a
    tube. Uses the same set-level measure the multiplex engine uses, so two
    parts of this project do not disagree about what a bad interaction is.
    """
    found: list[dict[str, Any]] = []
    for pool, tiles in sorted(scheme.pools().items()):
        oligos = [(f"{tile.index}F", tile.pair.left.sequence) for tile in tiles] + [
            (f"{tile.index}R", tile.pair.right.sequence) for tile in tiles
        ]

        worst = sorted(
            (
                {
                    "a": one_name,
                    "b": other_name,
                    "badness": round(badness(one, other), 1),
                }
                for index, (one_name, one) in enumerate(oligos)
                for other_name, other in oligos[index + 1 :]
            ),
            key=lambda entry: -entry["badness"],
        )[:5]

        found.append({"pool": pool, "oligos": len(oligos), "worst": worst})
    return found


def scheme_to_dict(
    scheme: Scheme, template_length: int, *, reference_id: str = ""
) -> dict[str, Any]:
    """The whole layout as plain data."""
    covered = scheme.covered()
    return {
        "tiles": [
            {
                "index": tile.index,
                "pool": tile.pool,
                "start": tile.start,
                "end": tile.end,
                "size": tile.end - tile.start,
                # Said rather than left to be inferred from an end past the
                # last base, which reads as a bug to anybody who did not know
                # the sequence was a circle.
                "crosses_the_join": tile.crosses_the_join(),
                "left": tile.pair.left.sequence,
                "right": tile.pair.right.sequence,
                # BED-like coordinates for downstream scheme interchange. The
                # same half-open convention is used for both primer records;
                # the strand tells the consumer how to interpret the reverse
                # oligo rather than forcing it to reverse-complement the text.
                "left_start": tile.start,
                "left_end": tile.start + tile.pair.left_at.length,
                "right_start": tile.start + tile.pair.right_at.start - tile.pair.left_at.start,
                "right_end": tile.start
                + tile.pair.right_at.start
                - tile.pair.left_at.start
                + tile.pair.right_at.length,
            }
            for tile in scheme.tiles
        ],
        "reference_id": reference_id or "unnamed-reference",
        "coordinate_system": "0-based, half-open",
        "scheme_format": "pcrstudio-tiling-v1",
        "pools": {
            str(pool): [tile.index for tile in tiles]
            for pool, tiles in sorted(scheme.pools().items())
        },
        "gaps": scheme.gaps,
        "coverage": {
            "bases": covered,
            "of": template_length,
            "percent": round(100.0 * covered / max(template_length, 1), 1),
        },
        "interactions": interactions(scheme),
        "how_it_was_laid_out": scheme.steps,
        "note": (
            "Neighbouring amplicons overlap, so they are in different pools: in "
            "one tube their primers would amplify each other's short products in "
            "preference to the real ones. Run each pool as its own reaction."
        ),
    }


def _order_line(name: str, oligo: Any, pool: int, tail: str = "") -> dict[str, Any]:
    """One line of an order sheet, with the pool it belongs to.

    The annealing-core melting temperature is retained as design provenance,
    not as a bench annealing-temperature instruction. A named PCR protocol owns
    the thermal programme.

    A tail goes on the ordered sequence and *not* into the annealing-core Tm.
    Platform adapters are not template-complementary during the first round, so
    reporting a whole-oligo Tm as though it were the core design metric would mix
    two different thermodynamic questions.
    """
    return {
        "name": name,
        "sequence": tail + oligo.sequence,
        "annealing_sequence": oligo.sequence,
        "tail_sequence": tail,
        "kind": "primer",
        "length": len(tail) + oligo.length,
        "gc_percent": oligo.gc_percent,
        "tm": oligo.tm,
        "pool": pool,
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    """One tiling scheme, end to end, in the shape the interface reads.

    Raises:
        IntakeError: the input is not a usable template.
        TilingError: a layout that could not be attempted.
        ValueError: a constraint, preset or reaction that cannot hold.
    """
    chosen = prepare(request)
    sequence = clean_template(chosen.target.sequence)
    reaction = chosen.reaction.as_conditions()

    scheme = lay_out(
        sequence,
        constraints=chosen.limits,
        conditions=reaction,
        overlap=OVERLAP if request.get("overlap") is None else int(request["overlap"]),
        slide=SLIDE if request.get("slide") is None else int(request["slide"]),
        pools=2 if request.get("pools") is None else int(request["pools"]),
        circular=bool(request.get("circular")),
        excluded=excluded_from(request),
    )

    laid_out = scheme_to_dict(scheme, len(sequence), reference_id=chosen.target.name)
    name = label(chosen.target.name)

    # Tails/adapters are not part of the current tiled-scheme request contract.
    # A direct worker call that still carries them is refused rather than ignored.
    asked = request.get("tails")
    if asked not in (None, {}, ""):
        raise TilingError(
            "Generation-1 tiled-scheme has no 5-prime-tail input. Tail-aware pool assignment "
            "and revalidation are not qualified; remove the historical field and regenerate the scheme."
        )

    coverage_complete = bool(scheme.tiles) and not bool(laid_out.get("gaps"))
    # This module is the explicit internal-development walker. Canonical Gen-1
    # execution is PrimalScheme3; an internal result may be useful diagnostic
    # evidence but is never supplier authority, even when coverage is complete.
    scheme_orderable = False
    orderability = {
        "orderable": False,
        "status": "research-only-internal-development-tiler",
        "note": (
            "Internal walker output is development evidence only and must not expose supplier-orderable oligos. "
            + (
                "Coverage is complete, but canonical PrimalScheme3 execution is still required before ordering."
                if coverage_complete
                else "Coverage is also incomplete; resolve the gaps and rerun the canonical PrimalScheme3 backend."
            )
        ),
    }

    return {
        "engine": "tiling-scheme",
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
            field: getattr(chosen.limits, field) for field in Constraints.__dataclass_fields__
        },
        **laid_out,
        "why_nothing": (
            "Internal development walker only: canonical PrimalScheme3 execution is required before release or ordering."
            if coverage_complete
            else (
                "The walk could not place a single amplicon. Every start it tried failed the constraints."
                if not scheme.tiles
                else f"The internal scheme leaves {len(laid_out.get('gaps') or [])} uncovered interval(s); partial coverage is diagnostic and not releasable for ordering."
            )
        ),
        "orderability": orderability,
        "order_sheet": (
            [
                entry
                for tile, pair in zip(laid_out["tiles"], scheme.tiles, strict=True)
                for entry in (
                    _order_line(f"{name}_{tile['index']}F", pair.pair.left, tile["pool"]),
                    _order_line(f"{name}_{tile['index']}R", pair.pair.right, tile["pool"]),
                )
            ]
            if scheme_orderable
            else []
        ),
    }
