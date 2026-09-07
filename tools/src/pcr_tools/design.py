"""Candidate generation for standard PCR.

Primer3 does the search. What this module adds is the part Primer3 leaves to
the caller: asking for candidates that are actually different from each other,
and reporting why a run came back empty.

A plain Primer3 run returns its top pairs by penalty, and those are routinely
the same design shifted by a base or two — five options that are one option.
`PRIMER_MIN_THREE_PRIME_DISTANCE` pushes them apart during the search, and a
final pass here drops anything that still overlaps too closely.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import primer3

from .thermo import (
    DEFAULT_CONDITIONS,
    OligoReport,
    analyse,
    clean_template,
    pair_dimer,
    report_to_dict,
    reverse_complement,
    salt_correction_for_conditions,
)

#: The longest primer Primer3 will design.
#:
#: Measured against the pinned Primer3 picker: `PRIMER_MAX_SIZE` of 36 is
#: accepted and 37 raises its built-in maximum error. This is an implementation
#: boundary of the Primer3 candidate picker, not a biological or nearest-
#: neighbour thermodynamic claim about longer synthesized oligos.
MAX_PRIMER_LENGTH = 36

#: Primer3 defines PRIMER_MAX_END_GC over the terminal five bases.
PRIMER3_END_GC_WINDOW = 5

# primer3-py accepts unknown ``PRIMER_*`` tags without an error. Keep the
# public weight surface deliberately narrower than that permissive parser:
# these are the only ranking channels that have been verified to change the
# candidate penalty/order in this worker. Adding another Primer3 weight needs
# a behavioural regression first, otherwise a caller cannot distinguish an
# applied preference from a silently ignored spelling.
SUPPORTED_RANKING_WEIGHTS = frozenset(
    {
        "PRIMER_WT_TM_LT",
        "PRIMER_WT_TM_GT",
        "PRIMER_PAIR_WT_DIFF_TM",
        "PRIMER_PAIR_WT_PRODUCT_SIZE_LT",
        "PRIMER_PAIR_WT_PRODUCT_SIZE_GT",
    }
)

# Primer3 accepts numeric JSON values broadly, but these fields describe
# counts, lengths, or coordinates. Letting a fractional value reach the
# library invites implicit truncation or a less useful downstream error.
INTEGER_CONSTRAINTS = frozenset(
    {
        "length_min",
        "length_opt",
        "length_max",
        "product_min",
        "product_max",
        "max_poly_x",
        "min_three_prime_distance",
        "gc_clamp",
        "max_end_gc",
    }
)


@dataclass(frozen=True)
class Constraints:
    """What a primer pair has to satisfy to be considered at all."""

    length_min: int = 18
    length_opt: int = 20
    length_max: int = 25

    tm_min: float = 57.0
    tm_opt: float = 60.0
    tm_max: float = 63.0
    #: Largest pair-Tm difference allowed by the selected design profile.
    #: This is a profile/search constraint, not chemistry-independent proof
    #: that a larger difference cannot work in one experimentally optimized PCR.
    tm_pair_max_difference: float = 3.0

    gc_min: float = 40.0
    gc_max: float = 60.0

    product_min: int = 200
    product_max: int = 400

    #: Longest run of one base. Long homopolymers slip during synthesis and
    #: during extension.
    max_poly_x: int = 4

    #: How far apart two candidates' 3' ends must be before they count as
    #: different designs rather than the same one nudged over.
    min_three_prime_distance: int = 5

    #: How many of the last bases must be G or C.
    #:
    #: A G or C at the 3' end binds harder than an A or T, which is where
    #: extension starts from. One is the usual choice; two is safer and finds
    #: fewer primers; three risks a primer that sticks where it should not.
    gc_clamp: int = 1

    #: The most G and C allowed among the last five bases.
    #:
    #: The other half of the 3'-end argument, and it pulls the opposite way to
    #: `gc_clamp`. A clamp asks for enough binding at the end that extension
    #: starts cleanly; this caps it, because an end that binds too hard will
    #: also start extending from a site that is wrong everywhere else. Long-
    #: range manuals state a ceiling of three; Primer3 counts G and C anywhere
    #: in the last five bases, which is the closest constraint it has and is
    #: stricter than counting only a terminal run.
    #:
    #: Five is no limit at all, which is Primer3's own default.
    max_end_gc: int = 5

    #: The hardest a primer's last five bases may grip their target, as a
    #: positive kcal/mol magnitude.
    #:
    #: The number ceilings the duplex free energy of the five terminal 3'
    #: bases. More negative means a stronger 3' anchor: extension starts from
    #: the 3' end, so an end that grips harder than the rest of the primer
    #: extends from wherever it can hold, not only from the site that was
    #: meant -- asymmetric extension, and mispriming. The base Primer3 default
    #: is 100 (effectively no practical ceiling); Primer3Plus publishes 9 as a
    #: stricter starting value. This field stays optional because importing
    #: the Primer3Plus value as a universal hard gate would silently transfer
    #: a product-specific setting to every assay.
    #:
    #: Unset means nothing is sent and Primer3 applies its own default, so
    #: callers that never heard of this do not change behaviour.
    max_end_stability: float | None = None


    def validate(self) -> None:
        """Reject combinations Primer3 would refuse, with a reason.

        Every check here exists because Primer3 raises an `OSError` for it, and
        an exception out of a subprocess is a much worse answer than a sentence
        naming the two numbers that disagree. The wording matters as much as
        the check: "PRIMER_{OPT,DEFAULT}_SIZE > PRIMER_MAX_SIZE" is true and
        useless.
        """
        for name, value in asdict(self).items():
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"constraint `{name}` must be a finite number")
            try:
                finite = math.isfinite(float(value))
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"constraint `{name}` must be finite, not {value!r}")
            if name in INTEGER_CONSTRAINTS and not isinstance(value, int):
                raise ValueError(f"constraint `{name}` must be an integer, not {value!r}")

        if self.length_min < 1:
            raise ValueError("a primer is at least one base long")
        if self.length_min > self.length_max:
            raise ValueError(
                f"the shortest primer ({self.length_min}) is longer than the "
                f"longest ({self.length_max})"
            )
        if not self.length_min <= self.length_opt <= self.length_max:
            raise ValueError(
                f"the ideal primer length ({self.length_opt}) is outside the range "
                f"asked for, {self.length_min} to {self.length_max}"
            )
        if self.length_max > MAX_PRIMER_LENGTH:
            raise ValueError(
                f"the pinned Primer3 candidate picker will not design a primer longer than "
                f"{MAX_PRIMER_LENGTH} bases. This is a picker implementation limit, not a "
                "claim that longer oligos lack a valid melting-temperature model; use an "
                "engine whose search supports the required oligo length."
            )

        if self.tm_min > self.tm_max:
            raise ValueError(
                f"the lowest melting temperature ({self.tm_min} C) is above the "
                f"highest ({self.tm_max} C)"
            )
        if not self.tm_min <= self.tm_opt <= self.tm_max:
            raise ValueError(
                f"the ideal melting temperature ({self.tm_opt} C) is outside the range "
                f"asked for, {self.tm_min} to {self.tm_max} C"
            )
        if self.tm_pair_max_difference < 0:
            raise ValueError("two primers cannot differ by less than nothing")

        if self.gc_min > self.gc_max:
            raise ValueError(
                f"the lowest GC ({self.gc_min}%) is above the highest ({self.gc_max}%)"
            )
        if not (0 <= self.gc_min and self.gc_max <= 100):
            raise ValueError("GC content is a percentage, so it lies between 0 and 100")

        if self.product_min > self.product_max:
            raise ValueError(
                f"the shortest product ({self.product_min} bp) is longer than the "
                f"longest ({self.product_max} bp)"
            )
        if self.product_min < 2 * self.length_min:
            raise ValueError(
                f"the shortest product ({self.product_min} bp) cannot hold a primer "
                f"pair of {self.length_min} bases each"
            )
        # Do not reject a whole product window merely because its lower edge
        # cannot accommodate two *maximum-length* primers.  Primer3 is free to
        # choose shorter primers and/or a larger product within the requested
        # range; the old check turned one impossible corner of a valid search
        # space into a request-level scientific refusal.  Pair geometry remains
        # a candidate-level constraint owned by the actual search engine.

        # Zero is not "no runs allowed"; Primer3 reads it as no limit at all,
        # so a run of four comes back from a setting that looks like the
        # strictest possible. Refused rather than silently inverted.
        if self.max_poly_x < 1:
            raise ValueError(
                "the longest allowed run of one base must be at least 1. Primer3 reads "
                "0 as no limit, which is the opposite of what it looks like."
            )

        if self.min_three_prime_distance < -1:
            raise ValueError(
                "how far apart two candidates' 3-prime ends must be cannot be less than "
                "-1, which is Primer3's way of saying the check is off"
            )

        if not 0 <= self.max_end_gc <= PRIMER3_END_GC_WINDOW:
            raise ValueError(
                f"at most {self.max_end_gc} of the last five bases may be G or C, "
                f"which is not a number between 0 and {PRIMER3_END_GC_WINDOW}. {PRIMER3_END_GC_WINDOW} means no limit."
            )
        if self.max_end_stability is not None and self.max_end_stability < 0:
            raise ValueError(
                f"a 3'-end stability ceiling of {self.max_end_stability} kcal/mol is "
                "below nothing. The number is the magnitude of how hard the last five "
                "bases may grip, so zero is the strictest it can go and negative does "
                "not mean stronger."
            )
        if not 0 <= self.gc_clamp <= self.length_min:
            raise ValueError(
                f"asking for {self.gc_clamp} G or C at the 3-prime end of a primer only "
                f"{self.length_min} bases long is asking for more than there is"
            )
        if self.gc_clamp > self.max_end_gc:
            raise ValueError(
                f"a GC clamp of {self.gc_clamp} asks for that many G or C at the 3' "
                f"end while max_end_gc allows at most {self.max_end_gc} in the last "
                "five bases. Nothing can satisfy both."
            )

    def to_primer3(
        self, conditions: dict[str, float], how_many: int, *, masked: bool = False
    ) -> dict[str, Any]:
        """These constraints in the vocabulary Primer3 expects."""
        settings = {
            "PRIMER_NUM_RETURN": how_many,
            # Do not inherit the library's task/picker defaults. The shared
            # flanking-pair contract is an ordinary left+right pair with no
            # internal probe; making that explicit keeps a future Primer3
            # default change from silently changing the assay.
            "PRIMER_TASK": "generic",
            "PRIMER_PICK_LEFT_PRIMER": 1,
            "PRIMER_PICK_INTERNAL_OLIGO": 0,
            "PRIMER_PICK_RIGHT_PRIMER": 1,
            "PRIMER_PICK_ANYWAY": 0,
            # Without this Primer3 returns no account of what it rejected, and
            # an empty result becomes unexplainable.
            "PRIMER_EXPLAIN_FLAG": 1,
            # An ambiguity code under a primer is a primer that may not anneal.
            "PRIMER_MAX_NS_ACCEPTED": 0,
            # Only meaningful when the template actually arrived masked;
            # setting it otherwise would read ordinary lowercase as a repeat.
            "PRIMER_LOWERCASE_MASKING": 1 if masked else 0,
            "PRIMER_MIN_SIZE": self.length_min,
            "PRIMER_OPT_SIZE": self.length_opt,
            "PRIMER_MAX_SIZE": self.length_max,
            "PRIMER_MIN_TM": self.tm_min,
            "PRIMER_OPT_TM": self.tm_opt,
            "PRIMER_MAX_TM": self.tm_max,
            "PRIMER_PAIR_MAX_DIFF_TM": self.tm_pair_max_difference,
            "PRIMER_MIN_GC": self.gc_min,
            "PRIMER_MAX_GC": self.gc_max,
            "PRIMER_MAX_POLY_X": self.max_poly_x,
            "PRIMER_PRODUCT_SIZE_RANGE": [[self.product_min, self.product_max]],
            "PRIMER_MIN_THREE_PRIME_DISTANCE": self.min_three_prime_distance,
            "PRIMER_GC_CLAMP": self.gc_clamp,
            "PRIMER_MAX_END_GC": self.max_end_gc,
            # Secondary-structure hard ceilings are intentionally not derived
            # from the assay Tm window. The previous project rule `tm_min - 10`
            # was an unsourced heuristic that turned a ranking intuition into a
            # validity gate. The pinned Primer3 core therefore owns its native
            # thermodynamic structure defaults unless a future assay profile
            # supplies separately sourced, versioned structure limits.
            # The thermodynamic models, rather than the older approximations.
            #
            # Primer3's recommended SantaLucia salt correction is the
            # versioned default for this engine. Divalent concentration remains
            # an input to that model; PCRStudio does not switch salt-correction
            # identity at an invented Mg threshold. A different model must be
            # selected explicitly by a reviewed profile/version.
            "PRIMER_TM_FORMULA": 1,
            "PRIMER_SALT_CORRECTIONS": salt_correction_for_conditions(conditions)[1],
            "PRIMER_THERMODYNAMIC_OLIGO_ALIGNMENT": 1,
            # Background/template specificity is handled by the versioned
            # bounded scanner. Primer3's own template thermodynamic alignment
            # is therefore intentionally off rather than library-defaulted.
            "PRIMER_THERMODYNAMIC_TEMPLATE_ALIGNMENT": 0,
            "PRIMER_SALT_MONOVALENT": conditions["mv_conc"],
            "PRIMER_SALT_DIVALENT": conditions["dv_conc"],
            "PRIMER_DNTP_CONC": conditions["dntp_conc"],
            "PRIMER_DNA_CONC": conditions["dna_conc"],
        }
        if self.max_end_stability is not None:
            # Sent only when asked for: the base Primer3 default applies
            # otherwise, which is what keeps an unused field inert. The
            # stricter Primer3Plus value is not a universal assay rule.
            settings["PRIMER_MAX_END_STABILITY"] = self.max_end_stability
        return settings


@dataclass(frozen=True)
class Placement:
    """Where a primer sits on the template."""

    start: int
    length: int


@dataclass(frozen=True)
class CandidatePair:
    """One primer pair, with everything measurable about it."""

    left: OligoReport
    right: OligoReport
    left_at: Placement
    right_at: Placement
    product_size: int
    #: Primer3's own penalty. Lower is better, and it knows nothing about
    #: specificity — no genome was consulted.
    penalty: float
    tm_difference: float
    cross_dimer_dg: float
    #: The product itself. People need the sequence they are about to make,
    #: not only its length.
    amplicon: str
    #: Whether the product spans the join of a circular template.
    #:
    #: True means the right primer's coordinate is *lower* than the left's,
    #: which is true of the molecule and looks like a bug to anything that
    #: assumes otherwise — so it is said rather than left to be inferred.
    crosses_the_join: bool = False


@dataclass(frozen=True)
class DesignResult:
    """What one design run produced, and what it discarded on the way."""

    pairs: list[CandidatePair]
    #: Primer3's account of what it rejected and why. This is the difference
    #: between "no primers exist here" and "your constraints were too tight".
    considered: dict[str, str]
    #: How many pairs Primer3 handed back before we thinned them.
    returned: int
    #: How many of those we actually looked at. The search stops once
    #: enough distinct pairs are in hand, so the rest were never examined
    #: and must not be reported as though they were rejected.
    examined: int
    #: How many were asked for. Fewer coming back is a fact worth stating
    #: rather than leaving to be noticed.
    wanted: int
    #: Anything Primer3 wanted to say that was not an error.
    warning: str
    #: How many of those were the same design shifted by a base or two. A
    #: number nobody reports, and the reason five results are often one.
    collapsed: int


def _placement(raw: Any) -> Placement:
    start, length = raw
    return Placement(start=int(start), length=int(length))


def pair_at(
    raw: dict[str, Any], index: int, sequence: str, reaction: dict[str, float]
) -> CandidatePair:
    """The `index`-th pair out of a Primer3 answer, fully measured.

    Shared rather than copied: any engine that asks Primer3 for a pair gets
    the pair read out of the answer the same way. The two places this matters
    are the coordinate convention -- Primer3 reports a right primer by its 3'
    end, reading right to left -- and that every number on the pair is
    measured in the reaction rather than taken from Primer3's own estimate.
    """
    left_seq = raw[f"PRIMER_LEFT_{index}_SEQUENCE"]
    right_seq = raw[f"PRIMER_RIGHT_{index}_SEQUENCE"]
    left = analyse(left_seq, **reaction)
    right = analyse(right_seq, **reaction)

    left_at = _placement(raw[f"PRIMER_LEFT_{index}"])
    right_at = _placement(raw[f"PRIMER_RIGHT_{index}"])
    # The product runs from the left primer's 5' end to the right primer's
    # reported position, which is that primer's 3'-most base on the plus strand.
    return CandidatePair(
        left=left,
        right=right,
        left_at=left_at,
        right_at=right_at,
        amplicon=sequence[left_at.start : right_at.start + 1].upper(),
        product_size=int(raw[f"PRIMER_PAIR_{index}_PRODUCT_SIZE"]),
        penalty=round(float(raw[f"PRIMER_PAIR_{index}_PENALTY"]), 3),
        tm_difference=round(abs(left.tm - right.tm), 1),
        cross_dimer_dg=pair_dimer(left_seq, right_seq, **reaction).dg,
    )


def _too_similar(a: CandidatePair, b: CandidatePair, distance: int) -> bool:
    """Whether two pairs are the same design nudged sideways.

    A primer's 3' end is what determines where extension starts, so two primers
    whose 3' ends are within a few bases will behave the same way in the tube.
    """
    a_left_end = a.left_at.start + a.left_at.length
    b_left_end = b.left_at.start + b.left_at.length
    # Right primers are given by their 3' end already, reading right to left.
    return (
        abs(a_left_end - b_left_end) < distance
        and abs(a.right_at.start - b.right_at.start) < distance
    )


def design(
    template: str,
    *,
    target_start: int | None = None,
    target_length: int | None = None,
    excluded: list[tuple[int, int]] | None = None,
    included: tuple[int, int] | None = None,
    pinned_left: str | None = None,
    pinned_right: str | None = None,
    force_left_start: int | None = None,
    force_right_start: int | None = None,
    constraints: Constraints | None = None,
    conditions: dict[str, float] | None = None,
    how_many: int = 5,
    masked: bool = False,
    weights: dict[str, float] | None = None,
) -> DesignResult:
    """Generate distinct candidate pairs for a template.

    Args:
        template: The sequence to amplify from.
        target_start: First base that must fall inside the product.
        target_length: How many bases from `target_start` must be included.
        excluded: Stretches no primer may overlap.
        included: The only stretch primers may be picked from, as a start and a
            length. Distinct from `excluded`, which says where they may not go:
            this says where they may, and everything outside it is out of
            bounds. What a nested design needs, so the inner pair can be
            searched for inside the outer product while every coordinate stays
            in the template's own frame.
        pinned_left: A forward primer that is already decided, so only the
            reverse is searched for. What a semi-nested design needs, where the
            second round reuses one primer from the first.
        pinned_right: The same for the reverse primer. Given as it would be
            ordered, five prime to three prime on its own strand.
        force_left_start: Optional zero-based coordinate of the left primer's
            5-prime start. Used only by boundary-aware callers that must prove
            a submitted fragment is retained end to end.
        force_right_start: Optional zero-based coordinate of the right primer's
            5-prime start on the input sequence (the rightmost template base
            for an endpoint reverse primer). Primer3 exposes this separately
            from SEQUENCE_PRIMER so repeated sequence cannot relocate a pinned
            oligo silently.
        constraints: What a pair has to satisfy. Defaults are Primer3's, which
            suit a standard reaction.
        conditions: Salt and nucleotide concentrations.
        how_many: How many distinct pairs to aim for.
        weights: Extra ranking weights merged into the search settings, either
            primer-level `PRIMER_WT_*` tags or pair-level
            `PRIMER_PAIR_WT_*` ones. These bias which *valid* candidate ranks
            first; they cannot make an invalid candidate valid, because every
            hard limit in `constraints` still gates the search. A pair-level
            product-size weight prices the distance from the ideal product, so
            when one is sent and no optimum has been set otherwise,
            `PRIMER_PRODUCT_OPT_SIZE` is derived here from the middle of the
            product window -- the weight has to measure distance from
            something, and the window's midpoint is what this engine means by
            ideal.

        Raises:
            SequenceError: if the template is not unambiguous DNA, or the target
                does not lie inside it.
    """
    sequence = clean_template(template)
    limits = constraints or Constraints()
    limits.validate()
    reaction = {**DEFAULT_CONDITIONS, **(conditions or {})}

    sequence_args: dict[str, Any] = {
        "SEQUENCE_ID": "template",
        "SEQUENCE_TEMPLATE": sequence,
    }
    if target_start is not None and target_length is not None:
        if target_start < 0 or target_start + target_length > len(sequence):
            raise ValueError(
                f"the target at {target_start}..{target_start + target_length} "
                f"falls outside a template of {len(sequence)} bases"
            )
        sequence_args["SEQUENCE_TARGET"] = [target_start, target_length]

    if included is not None:
        start, length = included
        if start < 0 or length < 1 or start + length > len(sequence):
            raise ValueError(
                f"the region primers may come from, {start}..{start + length}, falls "
                f"outside a template of {len(sequence)} bases"
            )
        if target_start is not None and target_length is not None:
            # A target outside the region primers may be picked from is a
            # request for a product that must contain something no product can
            # reach. Primer3 answers it with an empty list, which reads as
            # "nothing good enough" rather than "this cannot happen".
            if target_start < start or target_start + target_length > start + length:
                raise ValueError(
                    f"the target at {target_start}..{target_start + target_length} "
                    f"lies outside {start}..{start + length}, the only stretch "
                    "primers may come from, so no product could contain it"
                )
        sequence_args["SEQUENCE_INCLUDED_REGION"] = [start, length]

    if pinned_left:
        sequence_args["SEQUENCE_PRIMER"] = pinned_left.upper()
    if force_left_start is not None:
        if force_left_start < 0 or force_left_start >= len(sequence):
            raise ValueError("force_left_start is outside the template")
        sequence_args["SEQUENCE_FORCE_LEFT_START"] = force_left_start
    if pinned_right:
        # Primer3 wants this one as it would be ordered, which is the reverse
        # complement of the template strand -- the same way we report it, so
        # nothing is flipped here that the caller would have to flip back.
        sequence_args["SEQUENCE_PRIMER_REVCOMP"] = pinned_right.upper()
    if force_right_start is not None:
        if force_right_start < 0 or force_right_start >= len(sequence):
            raise ValueError("force_right_start is outside the template")
        sequence_args["SEQUENCE_FORCE_RIGHT_START"] = force_right_start

    if excluded:
        for start, length in excluded:
            if start < 0 or length < 1 or start + length > len(sequence):
                raise ValueError(
                    f"the excluded region at {start}..{start + length} falls outside a "
                    f"template of {len(sequence)} bases"
                )
        # No primer may overlap these. What they usually are: a repeat, a
        # region of poor sequence, or a stretch somebody already knows primes
        # badly.
        sequence_args["SEQUENCE_EXCLUDED_REGION"] = [list(pair) for pair in excluded]

    # Ask for more than requested: some of what comes back will be the same
    # design twice, and the caller asked for distinct ones.
    global_args = limits.to_primer3(reaction, how_many * 4, masked=masked)
    if weights:
        # A negative weight does not reach Primer3 to be refused: its core
        # dies on an assertion (`sum >= 0.0`) rather than reporting anything.
        # And a weight channel that could rename a hard setting would let a
        # ranking hint silently override a constraint, so only PRIMER_WT_ keys
        # travel this way.
        negative = sorted(name for name, value in weights.items() if value < 0)
        if negative:
            raise ValueError(
                f"ranking weight(s) {', '.join(negative)} are below zero, and "
                "Primer3 asserts on a negative weight rather than refusing it"
            )
        strange = sorted(
            name for name in weights if not name.startswith(("PRIMER_WT_", "PRIMER_PAIR_WT_"))
        )
        if strange:
            raise ValueError(
                f"only PRIMER_WT_* and PRIMER_PAIR_WT_* ranking weights can be "
                f"merged here, not {', '.join(strange)}: weights bias which "
                "valid candidate ranks first, and these would change what "
                "counts as valid"
            )
        unsupported = sorted(set(weights) - SUPPORTED_RANKING_WEIGHTS)
        if unsupported:
            raise ValueError(
                f"ranking weight(s) {', '.join(unsupported)} are not supported by "
                "this adapter: primer3-py may accept unknown weight tags silently. "
                f"Supported verified weights are {', '.join(sorted(SUPPORTED_RANKING_WEIGHTS))}."
            )
        global_args.update(weights)
        if any(name.startswith("PRIMER_PAIR_WT_PRODUCT_SIZE") for name in weights):
            # A pair product-size weight prices how far a product sits from
            # the ideal one, and Primer3 measures that distance from
            # PRIMER_PRODUCT_OPT_SIZE. Nothing else in this engine sends an
            # optimum -- sending one unasked would quietly re-price every
            # unweighted search -- so it is derived here, from the middle of
            # the window being searched, exactly when a weight needs it.
            global_args.setdefault(
                "PRIMER_PRODUCT_OPT_SIZE",
                (limits.product_min + limits.product_max) // 2,
            )

    raw = primer3.design_primers(
        seq_args=sequence_args,
        global_args=global_args,
    )

    reported = str(raw.get("PRIMER_ERROR", "")).strip()
    if reported:
        raise ValueError(f"Primer3 refused this request: {reported}")

    found: list[CandidatePair] = []
    collapsed = 0
    examined = 0
    returned = int(raw.get("PRIMER_PAIR_NUM_RETURNED", 0))
    for index in range(returned):
        examined += 1
        candidate = pair_at(raw, index, sequence, reaction)

        if any(_too_similar(candidate, kept, limits.min_three_prime_distance) for kept in found):
            collapsed += 1
            continue
        found.append(candidate)
        if len(found) == how_many:
            break

    return DesignResult(
        pairs=found,
        returned=returned,
        examined=examined,
        wanted=how_many,
        warning=str(raw.get("PRIMER_WARNING", "")).strip(),
        collapsed=collapsed,
        considered={
            "left": str(raw.get("PRIMER_LEFT_EXPLAIN", "")),
            "right": str(raw.get("PRIMER_RIGHT_EXPLAIN", "")),
            "pair": str(raw.get("PRIMER_PAIR_EXPLAIN", "")),
        },
    )


def design_terminal_pair(
    template: str,
    *,
    constraints: Constraints | None = None,
    conditions: dict[str, float] | None = None,
    how_many: int = 1,
) -> DesignResult:
    """Design pairs whose product is exactly the supplied template.

    This is the boundary-aware variant used when a caller supplies an already
    delimited fragment rather than a longer source template. A normal search
    is allowed to move both primers inward, which would silently amplify a
    subfragment; here the forward primer must begin at base zero and the
    reverse primer must end at the final base. Primer3 still judges each pinned
    pair for its ordinary oligo, pair, structure and product constraints.

    The function deliberately tries only endpoint candidates that pass the
    explicit per-primer window before invoking the pinned Primer3 search. That
    keeps the boundary contract visible and avoids a large number of calls for
    candidates that cannot satisfy the selected profile.
    """
    sequence = clean_template(template)
    limits = constraints or Constraints()
    limits.validate()
    reaction = {**DEFAULT_CONDITIONS, **(conditions or {})}
    if how_many < 1:
        raise ValueError("how_many must be at least 1")

    if not limits.product_min <= len(sequence) <= limits.product_max:
        return DesignResult(
            pairs=[],
            considered={
                "left": f"terminal product length {len(sequence)} is outside "
                f"{limits.product_min}–{limits.product_max}",
                "right": "terminal product was not searched",
                "pair": "terminal product was not searched",
            },
            returned=0,
            examined=0,
            wanted=how_many,
            warning="",
            collapsed=0,
        )

    def candidate(sequence_: str) -> bool:
        report = analyse(sequence_, **reaction)
        return (
            limits.length_min <= report.length <= limits.length_max
            and limits.tm_min <= report.tm <= limits.tm_max
            and limits.gc_min <= report.gc_percent <= limits.gc_max
        )

    left = [
        sequence[:length]
        for length in range(limits.length_min, min(limits.length_max, len(sequence)) + 1)
        if candidate(sequence[:length])
    ]
    right = [
        reverse_complement(sequence[len(sequence) - length :])
        for length in range(limits.length_min, min(limits.length_max, len(sequence)) + 1)
        if candidate(reverse_complement(sequence[len(sequence) - length :]))
    ]

    pairs: list[CandidatePair] = []
    returned = 0
    examined = 0
    for left_sequence in left:
        for right_sequence in right:
            # Primer3 is the authority for pinned-primer structure and pair
            # checks. Invalid pinned combinations can be reported as OSError
            # by primer3-py rather than as an empty result.
            try:
                result = design(
                    sequence,
                    constraints=limits,
                    conditions=reaction,
                    how_many=1,
                    pinned_left=left_sequence,
                    pinned_right=right_sequence,
                    force_left_start=0,
                    force_right_start=len(sequence) - 1,
                )
            except (OSError, ValueError):
                continue
            examined += result.examined
            returned += result.returned
            if result.pairs:
                # Force tags are the primary boundary authority; this explicit
                # postcondition is defense in depth against adapter/version
                # drift. Primer3 reports the right primer by its rightmost
                # template coordinate, which must be the final submitted base.
                endpoint_pairs = [
                    pair
                    for pair in result.pairs
                    if pair.left_at.start == 0
                    and pair.right_at.start == len(sequence) - 1
                    and pair.product_size == len(sequence)
                ]
                pairs.extend(endpoint_pairs)
                if len(pairs) >= how_many:
                    break
        if len(pairs) >= how_many:
            break

    return DesignResult(
        pairs=pairs[:how_many],
        considered={
            "left": f"terminal candidates {len(left)}",
            "right": f"terminal candidates {len(right)}",
            "pair": "pinned endpoint pairs checked by Primer3",
        },
        returned=returned,
        examined=examined,
        wanted=how_many,
        warning="",
        collapsed=0,
    )


def result_to_dict(result: DesignResult) -> dict[str, Any]:
    """The result as plain JSON-ready data."""
    return {
        "pairs": [
            {
                **{k: v for k, v in asdict(pair).items() if k not in {"left", "right"}},
                "left": report_to_dict(pair.left),
                "right": report_to_dict(pair.right),
            }
            for pair in result.pairs
        ],
        "considered": result.considered,
        "returned": result.returned,
        "examined": result.examined,
        "wanted": result.wanted,
        "warning": result.warning,
        "collapsed": result.collapsed,
    }
