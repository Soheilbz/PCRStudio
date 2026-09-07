"""Inverse PCR: one outward pair on a circularized restriction fragment.

Standard two-flank inverse PCR starts from a restriction fragment that contains
*all* of the known anchor sequence plus unknown DNA on one or both sides.  The
restriction enzyme used for that branch therefore must **not** cut inside the
known anchor.  After dilute intramolecular ligation, the two restriction-fragment
ends join and the unknown flanks become contiguous around that ligation junction.
Two primers bound to the known anchor and pointing away from one another then
face towards each other around the circle and amplify across the unknown flanks.

That topology matters.  An older PCRStudio implementation treated a restriction
site *inside* the known sequence as the standard branch, split the anchor into two
halves, and designed a separate circle for each half.  That is a different,
one-sided inverse-PCR strategy and must not be silently substituted for the
standard two-flank experiment.  Gen-1 Scientific-Strict therefore executes only
the standard no-internal-cut branch here.  An internal known-sequence cut is a
typed boundary until a separately named one-sided workflow is modelled.

The search representation is a rotation of the complete known sequence.  The
artificial join in that rotated string is the original known-sequence endpoint
join (last base -> first base).  An ordinary inward-facing Primer3 pair forced to
span that join maps back to an outward-facing pair on the original linear map:
the Primer3 left/forward oligo sits on the right side of the known anchor and
reads into the downstream flank, while the Primer3 right/reverse oligo sits on
the left side and reads into the upstream flank.

Primer3's ``product_size`` in this representation is only the amount of *known
anchor* on the amplicon path.  It is not the inverse-PCR amplicon length.  The
actual product additionally contains the unknown DNA between the two flanking
restriction sites.  PCRStudio therefore reports an exact product length only
when the self-ligated restriction-fragment/circle length is supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .design import CandidatePair, Constraints, DesignResult, design
from .explain import account_to_dict, parse, why_nothing
from .intake import target_to_dict
from .inverse_topology import (
    InverseTopologyError,
    exact_topology,
    public_topology,
    screen_enzyme_cohort,
)
from .presets import thermodynamic_model
from .provenance import provenance
from .registries.authorities import INVERSE_AUTHORITY
from .registries.authorities import record as authority_record
from .restriction import BY_NAME, INVERSE_FLANK, choice_to_dict, choose_enzyme, sites
from .settings import how_many_from, label, prepare
from .thermo import report_to_dict
from .workflow_evidence import evidence_block

#: The most pairs one inverse run will return.
MOST_PAIRS = 50

# Keep the enzyme cohort bounded: the default is diagnostic metadata, not an
# optimisation target, and explicit cohorts are capped to keep a request's
# topology checks predictable.
DEFAULT_ENZYME_COHORT_SIZE = 8
MIN_ENZYME_COHORT_SIZE = 1
MAX_ENZYME_COHORT_SIZE = 12


class InverseError(ValueError):
    """A request that could not describe the supported inverse-PCR branch."""


@dataclass(frozen=True)
class Circle:
    """The self-ligated restriction fragment that contains the known anchor.

    ``length`` is a fact about the digest/circularization experiment.  It is not
    inferred from the known sequence.  When absent, PCRStudio deliberately
    leaves the final amplicon length unresolved.
    """

    length: int | None = None

    def check(self, known_length: int) -> None:
        """Whether a supplied circle can contain the complete known anchor."""
        if self.length is not None and self.length < known_length:
            raise InverseError(
                f"The supplied self-ligated fragment is {self.length} bases, but the "
                f"complete known anchor is {known_length} bases. The standard two-flank "
                "inverse-PCR circle has to contain the whole known anchor, so that "
                "fragment cannot describe this experiment."
            )


def rotate(sequence: str, at: int) -> tuple[str, int]:
    """Lay ``sequence`` flat from ``at`` and return its original-endpoint join.

    For a full known anchor, rotating at the midpoint puts the original
    ``last-base -> first-base`` endpoint join near the centre of the linear
    search representation.  Requiring an ordinary Primer3 pair to span this
    join is equivalent to requiring an outward-facing pair on the unrotated
    anchor.
    """
    return sequence[at:] + sequence[:at], len(sequence) - at


def back(position: int, at: int, length: int) -> int:
    """A position on a rotated sequence, mapped to the source coordinates."""
    return (position + at) % length


def design_outward(
    known: str,
    *,
    constraints: Constraints,
    conditions: dict[str, float],
    how_many: int = 5,
    masked: bool = False,
) -> tuple[DesignResult, int, int]:
    """Design a two-flank outward pair on the complete known anchor.

    The Primer3 product-range constraints bound the *known-anchor span* carried
    on the eventual inverse-PCR product.  They do not bound the final product,
    whose unknown-flank contribution is unresolved unless the restriction-
    fragment length is supplied.
    """
    if len(known) < 2 * constraints.length_min:
        raise InverseError(
            f"The known anchor is {len(known)} bases, which is not enough for two "
            f"primers of at least {constraints.length_min} bases."
        )

    at = len(known) // 2
    rotated, join = rotate(known, at)

    # Force the pair to cross the original known-sequence endpoint join.  A
    # pair that does not cross this target is an ordinary inward-facing pair on
    # the known sequence and does not implement inverse-PCR geometry.
    result = design(
        rotated,
        target_start=join - 1,
        target_length=2,
        constraints=constraints,
        conditions=conditions,
        how_many=how_many,
        masked=masked,
    )
    return result, at, join


def pair_to_dict(
    pair: CandidatePair,
    known: str,
    rotated_at: int,
    circle_length: int | None,
    *,
    unknown_min: int | None = None,
    unknown_max: int | None = None,
) -> dict[str, Any]:
    """One outward pair in the caller's original known-sequence coordinates."""
    known_length = len(known)
    known_span = pair.product_size

    def place(at: Any) -> dict[str, int]:
        return {
            "start": back(at.start, rotated_at, known_length),
            "length": at.length,
        }

    left_at = place(pair.left_at)
    right_at = place(pair.right_at)

    # In the rotated representation Primer3's left primer lies before the
    # original endpoint join, i.e. on the right-hand side of the unrotated
    # known anchor.  Its extension therefore walks into the downstream flank.
    # Primer3's right primer maps to the left-hand side and walks upstream.
    entry: dict[str, Any] = {
        "left": report_to_dict(pair.left),
        "right": report_to_dict(pair.right),
        "left_at": left_at,
        "right_at": right_at,
        "reads": "outward-from-known-anchor",
        "left_reads_into": "downstream flank",
        "right_reads_into": "upstream flank",
        "walks_into": "both flanks across the self-ligation junction",
        "known_span": known_span,
        "tm_difference": pair.tm_difference,
        "cross_dimer_dg": pair.cross_dimer_dg,
        "penalty": pair.penalty,
    }

    if circle_length is None:
        entry["product_size"] = None
        entry["unknown_interval"] = {
            "status": "bounded"
            if unknown_min is not None or unknown_max is not None
            else "unresolved",
            "minimum": unknown_min,
            "maximum": unknown_max,
            "exact": None,
        }
        entry["product_path"] = [
            {
                "kind": "forward-primer-anchor",
                "known_side": "right",
                "reads_into": "downstream-flank",
            },
            {"kind": "combined-unknown-flanks", "minimum": unknown_min, "maximum": unknown_max},
            {"kind": "restriction-fragment-ligation-junction", "status": "predicted"},
            {"kind": "reverse-primer-anchor", "known_side": "left", "reads_into": "upstream-flank"},
        ]
        entry["product_note"] = (
            "Final product size is unresolved because the distance from the known "
            "anchor to the flanking restriction sites is not present in the pasted "
            f"sequence. Primer3 measured {known_span} bp of known-anchor path only. "
            "Supply the complete self-ligated restriction-fragment length to make "
            "the final product size arithmetic rather than an estimate."
        )
    else:
        unknown = circle_length - known_length
        entry["product_size"] = known_span + unknown
        entry["unknown_interval"] = {
            "status": "exact",
            "minimum": unknown,
            "maximum": unknown,
            "exact": unknown,
        }
        entry["product_path"] = [
            {
                "kind": "forward-primer-anchor",
                "known_side": "right",
                "reads_into": "downstream-flank",
            },
            {"kind": "combined-unknown-flanks", "minimum": unknown, "maximum": unknown},
            {"kind": "restriction-fragment-ligation-junction", "status": "predicted"},
            {"kind": "reverse-primer-anchor", "known_side": "left", "reads_into": "upstream-flank"},
        ]
        entry["product_note"] = (
            f"{known_span} bp of known-anchor path plus {unknown} bp of combined "
            f"unknown flanking sequence from a {circle_length}-bp self-ligated "
            f"restriction fragment containing the complete {known_length}-bp known anchor."
        )

    return entry


def run(request: dict[str, Any]) -> dict[str, Any]:
    """Design the supported standard two-flank restriction/self-ligation branch."""
    # The final product includes unknown sequence, so the pasted known anchor
    # need not itself be as long as the requested final PCR product.
    chosen = prepare(request, require_product_room=False)
    how_many = how_many_from(request, MOST_PAIRS)
    known = chosen.target.sequence

    branch = str(request.get("inverse_branch") or "unresolved")
    if branch not in {"restriction-self-ligation", "supplied-circular-template"}:
        raise InverseError(
            "inverse PCR executes only `restriction-self-ligation` and `supplied-circular-template`; "
            "one-sided/internal-cut strategies remain reference-only and are never approximated by the standard algorithm."
        )
    branch_authority = authority_record(INVERSE_AUTHORITY, branch)
    if branch_authority.get("execution_status") != "executable":
        raise InverseError(f"inverse-PCR branch `{branch}` is not executable")

    if request.get("cut_at") is not None:
        raise InverseError(
            "`cut_at` is not part of the current outward-pair request contract. The standard two-flank "
            "branch uses a complete intact known anchor plus an explicit enzyme identity."
        )

    named = str(request.get("enzyme") or "").strip()
    if branch == "restriction-self-ligation" and not named:
        raise InverseError(
            "restriction/self-ligation inverse PCR requires the restriction-enzyme identity explicitly; digest identity is never inferred."
        )
    if branch == "supplied-circular-template" and named:
        raise InverseError(
            "supplied-circular-template does not accept an enzyme: digestion occurred outside this branch and PCRStudio will not invent or reinterpret it."
        )

    enzyme = None
    internal_sites: list[int] = []
    if named:
        if named not in BY_NAME:
            raise InverseError(
                f"`{named}` is not an enzyme this build knows. It knows: "
                + ", ".join(sorted(BY_NAME))
                + "."
            )
        enzyme = BY_NAME[named]
        internal_sites = sites(known, enzyme)
        if internal_sites:
            raise InverseError(
                f"{named} cuts the known anchor {len(internal_sites)} time(s)"
                + (
                    f" (at {', '.join(str(at) for at in internal_sites[:6])})"
                    if internal_sites
                    else ""
                )
                + ". Standard two-flank inverse PCR needs the complete known anchor on one restriction fragment; "
                "the internal-cut one-sided strategy is reference-only."
            )

    topology = None
    full_reference = str(request.get("inverse_reference_sequence") or "").strip()
    reference_circular = bool(request.get("inverse_reference_circular", False))
    if full_reference and branch == "restriction-self-ligation":
        try:
            topology = exact_topology(full_reference, known, named, circular=reference_circular)
        except InverseTopologyError as exc:
            raise InverseError(str(exc)) from exc

    if request.get("side") not in (None, ""):
        raise InverseError(
            "`side` is not part of the current outward-pair request contract. The standard branch "
            "recovers the combined path through both flanks around one intact known anchor."
        )

    phosphate_states: dict[str, str] = {
        "left_end_phosphate": "not-applicable",
        "right_end_phosphate": "not-applicable",
    }
    if request.get("circularization_provenance") in (None, ""):
        raise InverseError("circularization_provenance is required for both inverse-PCR branches")
    if branch == "restriction-self-ligation":
        for key in ("left_end_phosphate", "right_end_phosphate"):
            if request.get(key) in (None, ""):
                raise InverseError(
                    f"{key} is required; use `unresolved` explicitly when the phosphate state is unknown"
                )
            state = str(request.get(key) or "unresolved")
            if state not in {"phosphorylated", "unphosphorylated", "unresolved"}:
                raise InverseError(f"{key} must be phosphorylated, unphosphorylated, or unresolved")
            phosphate_states[key] = state
        for key in ("linear_control_provenance", "methylation_branch"):
            if request.get(key) in (None, ""):
                raise InverseError(
                    f"{key} is required; use `unresolved` explicitly when evidence is unknown"
                )

    unknown_min = (
        int(request["unknown_flank_min"]) if request.get("unknown_flank_min") is not None else None
    )
    unknown_max = (
        int(request["unknown_flank_max"]) if request.get("unknown_flank_max") is not None else None
    )
    if unknown_min is not None and unknown_min < 0:
        raise InverseError("unknown_flank_min cannot be negative")
    if unknown_max is not None and unknown_max < 0:
        raise InverseError("unknown_flank_max cannot be negative")
    if unknown_min is not None and unknown_max is not None and unknown_min > unknown_max:
        raise InverseError("unknown_flank_min cannot exceed unknown_flank_max")

    supplied_circle_length = (
        int(request["circle_length"]) if request.get("circle_length") is not None else None
    )
    if topology is not None:
        exact_fragment_length = int(topology["fragment_length"])
        if supplied_circle_length is not None and supplied_circle_length != exact_fragment_length:
            raise InverseError(
                f"circle_length={supplied_circle_length} disagrees with the exact full-reference restriction fragment length {exact_fragment_length}"
            )
        supplied_circle_length = exact_fragment_length
    circle = Circle(length=supplied_circle_length)
    if branch == "supplied-circular-template" and circle.length is None:
        raise InverseError(
            "supplied-circular-template requires the measured/supplied circle_length"
        )
    circle.check(len(known))
    if circle.length is not None:
        exact_unknown = circle.length - len(known)
        if unknown_min is not None and exact_unknown < unknown_min:
            raise InverseError(
                f"The supplied circle implies {exact_unknown} bp of combined unknown flanks, below "
                f"unknown_flank_min={unknown_min}."
            )
        if unknown_max is not None and exact_unknown > unknown_max:
            raise InverseError(
                f"The supplied circle implies {exact_unknown} bp of combined unknown flanks, above "
                f"unknown_flank_max={unknown_max}."
            )

    try:
        result, at, _join = design_outward(
            known,
            constraints=chosen.limits,
            conditions=chosen.reaction.as_conditions(),
            how_many=how_many,
            masked=chosen.target.soft_masked,
        )
    except InverseError:
        raise

    account = parse(result.considered.get("pair", ""), stage="pairs")
    pairs = [
        pair_to_dict(
            pair,
            known,
            at,
            circle.length,
            unknown_min=unknown_min,
            unknown_max=unknown_max,
        )
        for pair in result.pairs
    ]

    # Specificity evidence is still useful on the known anchor/background, but
    # a final inverse-PCR product is not present in the known anchor itself.
    # Any product predicted there is therefore unintended; the intended product
    # traverses unknown sequence and the self-ligation junction.
    from . import screen

    contigs, template_only, fold_at = screen.contigs_for(
        request, template=known, name=chosen.target.name
    )
    for entry in pairs:
        entry["off_targets"] = screen.oligos(
            {"left": entry["left"]["sequence"], "right": entry["right"]["sequence"]},
            contigs,
            reaction=chosen.reaction,
            fold_at=fold_at,
            max_product=screen.product_ceiling(chosen.limits.product_max),
        )

    cohort_size = int(request.get("enzyme_cohort_size") or DEFAULT_ENZYME_COHORT_SIZE)
    if not MIN_ENZYME_COHORT_SIZE <= cohort_size <= MAX_ENZYME_COHORT_SIZE:
        raise InverseError(
            f"enzyme_cohort_size must be between {MIN_ENZYME_COHORT_SIZE} and {MAX_ENZYME_COHORT_SIZE}"
        )
    requested_cohort = request.get("inverse_candidate_enzymes")
    if requested_cohort not in (None, []):
        if not isinstance(requested_cohort, list):
            raise InverseError(
                "inverse_candidate_enzymes must be an array of explicit enzyme names"
            )
        if len(requested_cohort) > MAX_ENZYME_COHORT_SIZE:
            raise InverseError(
                f"inverse_candidate_enzymes may contain at most {MAX_ENZYME_COHORT_SIZE} names"
            )
        if not full_reference:
            raise InverseError(
                "inverse_candidate_enzymes requires inverse_reference_sequence; PCRStudio will not rank enzymes from an incomplete anchor"
            )
        enzyme_cohort = screen_enzyme_cohort(
            full_reference,
            known,
            [str(value) for value in requested_cohort],
            circular=reference_circular,
        )
        cohort_decision_impact = "explicit-feasibility-no-cross-enzyme-score"
    else:
        enzyme_choices = (
            choose_enzyme(known, purpose=INVERSE_FLANK)
            if branch == "restriction-self-ligation"
            else []
        )
        enzyme_cohort = [choice_to_dict(c) for c in enzyme_choices[:cohort_size]]
        cohort_decision_impact = "diagnostic-only-anchor-metadata"
    mapping_use_case = str(request.get("mapping_use_case") or "generic-flank")
    if mapping_use_case not in {"generic-flank", "transposon-insertion", "integration-site"}:
        raise InverseError(
            "mapping_use_case must be generic-flank, transposon-insertion, or integration-site"
        )
    workflow = evidence_block(
        request.get("workflow_evidence"),
        note="Digest/circularization/PCR/sequencing evidence is retained for validation and never changes the saved primer ranking.",
    )
    observed = workflow.get("observed", {}) if isinstance(workflow, dict) else {}
    if str(observed.get("inverseSequenceConfirmation") or "").strip():
        result_status = "sequence-confirmed"
    elif observed.get("inverseObservedBandBp") not in (None, ""):
        result_status = "amplified"
    else:
        result_status = "predicted"

    name = label(chosen.target.name)
    order = [
        {
            "name": f"{name}_Inv{index}{role}",
            "sequence": oligo["sequence"],
            "annealing_sequence": oligo["sequence"],
            "tail_sequence": "",
            "kind": "primer",
            "length": oligo["length"],
            "gc_percent": oligo["gc_percent"],
            "tm": oligo["tm"],
        }
        for index, entry in enumerate(pairs, start=1)
        for role, oligo in (("F", entry["left"]), ("R", entry["right"]))
    ]

    return {
        "engine": "outward-pair",
        "provenance": provenance(chosen.reaction.as_conditions()),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **chosen.reaction.as_conditions(),
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "constraints": {
            name_: getattr(chosen.limits, name_) for name_ in Constraints.__dataclass_fields__
        },
        "constraint_semantics": {
            "product_min": "known-anchor span search bound, not final inverse-PCR amplicon size",
            "product_max": "known-anchor span search bound, not final inverse-PCR amplicon size",
        },
        "experiment_contract": {
            "branch": branch,
            "left_end_phosphate": phosphate_states["left_end_phosphate"],
            "right_end_phosphate": phosphate_states["right_end_phosphate"],
            "circularization_provenance": str(
                request.get("circularization_provenance") or "unresolved"
            ),
            "linear_control_provenance": str(
                request.get("linear_control_provenance") or "not-applicable"
            ),
            "methylation_branch": str(request.get("methylation_branch") or "not-applicable"),
            "mapping_use_case": mapping_use_case,
            "authority": branch_authority,
            "result_status": result_status,
            "status_semantics": (
                "Software design only. Enzyme identity and absence of its site from the known anchor "
                "establish the modelled topology, not successful digestion, circularization, amplification, "
                "or sequence identity. Upgrade claims only from external bench evidence."
            ),
        },
        "enzymes": enzyme_cohort,
        "enzyme_cohort": {
            "requested": cohort_size,
            "returned": len(enzyme_cohort),
            "decision_impact": cohort_decision_impact,
            "note": (
                "Explicit full-reference cohorts report exact feasibility in caller order and never manufacture a universal enzyme score."
                if requested_cohort not in (None, [])
                else "Backup enzyme metadata remains diagnostic until a complete reference is supplied."
            ),
        },
        "digest": {
            "branch_identity": branch,
            "enzyme": named or None,
            "known_sites": internal_sites,
            "known_length": len(known),
            "circle_length": circle.length,
            "note": (
                "The selected restriction enzyme has no site inside the known anchor, so the complete "
                "known sequence can remain on one restriction fragment. Flanking restriction sites are "
                "not inferred from the known anchor; their positions/fragment length are experimental or "
                "larger-context evidence. The digest fragment is self-ligated and one outward pair crosses "
                "the resulting flanking-sequence junction."
            ),
        },
        "topology_validation": public_topology(topology)
        if topology is not None
        else {
            "status": "unresolved",
            "reason": "full reference sequence not supplied"
            if not full_reference
            else "not-applicable-to-supplied-circle",
            "decision_impact": "topology-validation",
        },
        "circle": {
            "known_length": len(known),
            "circle_length": circle.length,
            "unknown_interval": {
                "status": (
                    "exact"
                    if circle.length is not None
                    else "bounded"
                    if unknown_min is not None or unknown_max is not None
                    else "unresolved"
                ),
                "minimum": (
                    circle.length - len(known) if circle.length is not None else unknown_min
                ),
                "maximum": (
                    circle.length - len(known) if circle.length is not None else unknown_max
                ),
                "exact": circle.length - len(known) if circle.length is not None else None,
            },
        },
        "background": screen.summary(contigs, template_only),
        "sequencing_handoff": {
            "target_module": "sequencing-primer",
            "status": "executable-handoff",
            "prefill": {
                "module": "sequencing-primer",
                "direction": "forward",
                "sequencingBidirectional": True,
                "template_source": "inverse-product-or-user-confirmed-recovered-flank",
            },
            "note": "Sequence confirmation is routed to the single-primer engine; this result carries the handoff without duplicating Sanger ranking.",
        },
        "workflow_evidence": workflow,
        "pairs": pairs,
        "considered": [account_to_dict(account)],
        "why_nothing": "" if pairs else why_nothing([account]),
        "order_sheet": order,
    }
