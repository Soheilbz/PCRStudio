"""A pair somebody already has, put through everything a designed one gets.

The commonest question a primer-design tool is not asked is the one people
actually have: *these are the primers I was given — are they any good?* They
come from a paper, from a predecessor's notebook, from a kit. Nobody designed
them here and nobody is going to redesign them, but somebody is about to spend
a week on them.

So this is the design pipeline run backwards. Instead of generating candidates
and measuring them, it takes two sequences and measures them the same way:
melting temperatures under the reaction being used, hairpins, self-dimers, what
the two do to each other, where they sit on the template, what product they
would give, whether the template keeps those sites open, and what else in a
background they would amplify.

Two things it does that a design run does not.

It says where the pair *sits*, and refuses to guess. A primer given without a
template is two oligos and a hope; the same primer against the wrong template
looks identical until the reaction fails. So the template is required, both
primers must be found in it, and a primer that is not there — or is there more
than once — is reported as exactly that rather than as a low score.

And it does not rank. There is nothing to rank against: one pair is not a
choice. What comes back is every measurement with the number it would have to
beat, and the judgement stays where it belongs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import specificity as spec
from .design import Constraints
from .intake import target_to_dict
from .presets import thermodynamic_model
from .provenance import provenance
from .settings import prepare
from .thermo import analyse, count_overlapping, pair_dimer, report_to_dict, reverse_complement


class ValidationError(ValueError):
    """A pair that could not be checked against this template."""


def _integer(
    value: Any,
    *,
    name: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Read a discrete check control without coercing the experiment."""
    if value is None:
        value = default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"`{name}` must be an integer, not {value!r}")
    if minimum is not None and value < minimum:
        raise ValueError(f"`{name}` must be at least {minimum}, not {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"`{name}` must be at most {maximum}, not {value}")
    return value


@dataclass(frozen=True)
class Placement:
    """Where one primer sits on the template."""

    role: str
    sequence: str
    #: Zero-based, on the plus strand, or `None` when it is not there.
    at: int | None
    #: How many places it could sit, counting both strands.
    occurrences: int
    #: Which strand it reads from, when there is exactly one place.
    orientation: str


def place(primer: str, template: str, role: str) -> Placement:
    """Where this primer sits, or how many places it could.

    Both strands, because a reverse primer is written as it would be ordered
    and so appears in the template only as its own complement.
    """
    primer = primer.upper()
    forward = count_overlapping(template, primer)
    reverse = count_overlapping(template, reverse_complement(primer))
    total = forward + reverse

    if total != 1:
        return Placement(role=role, sequence=primer, at=None, occurrences=total, orientation="")

    if forward:
        return Placement(
            role=role,
            sequence=primer,
            at=template.find(primer),
            occurrences=1,
            orientation="forward",
        )
    return Placement(
        role=role,
        sequence=primer,
        at=template.find(reverse_complement(primer)),
        occurrences=1,
        orientation="reverse",
    )


def _check(name: str, value: float, low: float, high: float, unit: str) -> dict[str, Any]:
    """One measurement against the window a designed primer would have had.

    Reported as a comparison rather than a verdict: a primer outside a window
    is not thereby bad, it is outside a window somebody chose for a different
    reason, and being told which and by how much is what lets that be judged.
    """
    return {
        "name": name,
        "value": round(value, 2),
        "wanted": [low, high],
        "unit": unit,
        "inside": low <= value <= high,
        "off_by": 0.0
        if low <= value <= high
        else round(min(abs(value - low), abs(value - high)), 2),
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    """Measure a pair somebody already has against the template they have.

    Raises:
        ValidationError: for a pair that is not on this template.
        IntakeError, ValueError: as the ordinary design does.
    """
    if not isinstance(request, dict):
        raise ValueError("a pair-validation request must be a JSON object")
    left_value = request.get("left")
    right_value = request.get("right")
    if left_value is not None and not isinstance(left_value, str):
        raise ValueError(f"`left` must be text, not {left_value!r}")
    if right_value is not None and not isinstance(right_value, str):
        raise ValueError(f"`right` must be text, not {right_value!r}")
    left = (left_value or "").strip().upper()
    right = (right_value or "").strip().upper()
    if not left or not right:
        raise ValidationError(
            "Both primers are needed. One on its own has no product, no pair "
            "melting temperature and no cross-dimer, which is most of what there "
            "is to say about a pair."
        )

    chosen = prepare(request, require_product_room=False)
    template = chosen.target.sequence
    conditions = chosen.reaction.as_conditions()

    placements = [place(left, template, "left"), place(right, template, "right")]
    missing = [p for p in placements if p.occurrences == 0]
    if missing:
        raise ValidationError(
            "The "
            + " and ".join(p.role for p in missing)
            + " primer"
            + ("s are" if len(missing) > 1 else " is")
            + " not in this template, on either strand. Either this is not the "
            "sequence these primers were made for, or they carry a tail — check "
            "the 5' end first, since that is where added sequence goes."
        )

    repeated = [p for p in placements if p.occurrences > 1]
    forward = next((p for p in placements if p.orientation == "forward"), None)
    reverse = next((p for p in placements if p.orientation == "reverse"), None)

    reports = {
        "left": analyse(left, **conditions),
        "right": analyse(right, **conditions),
    }

    limits = chosen.limits

    def structure(name: str, found: Any) -> dict[str, Any]:
        """One calculated structure, without inventing a bench pass/fail threshold.

        A primer Tm does not determine the assay's annealing temperature by a
        universal fixed offset. The previous `min(primer Tm) - 5 °C` rule was
        useful as a teaching heuristic but not a valid release-grade authority.
        We therefore report the thermodynamic prediction and leave acceptability
        unresolved unless a named assay protocol supplies a sourced boundary.
        """
        return {
            "name": name,
            "value": found.tm,
            "dg": found.dg,
            "wanted": None,
            "unit": "°C",
            "inside": None,
            "off_by": None,
            "detail": (
                f"{found.dg} kcal/mol, melting at {found.tm} °C. No universal "
                "pass/fail call is made from primer Tm alone; interpret this "
                "against the named reaction/protocol actually used at the bench."
            ),
        }

    measurements: dict[str, list[dict[str, Any]]] = {}
    for role, report in reports.items():
        measurements[role] = [
            _check("Length", report.length, limits.length_min, limits.length_max, "nt"),
            _check("Melting temperature", report.tm, limits.tm_min, limits.tm_max, "°C"),
            _check("GC", report.gc_percent, limits.gc_min, limits.gc_max, "%"),
            structure("Hairpin", report.hairpin),
            structure("Self-dimer", report.self_dimer),
        ]

    cross = pair_dimer(left, right, **conditions)
    difference = abs(reports["left"].tm - reports["right"].tm)
    pair_checks = [
        _check(
            "Melting temperatures apart",
            difference,
            0.0,
            limits.tm_pair_max_difference,
            "°C",
        ),
        structure("Cross-dimer", cross),
    ]

    product: dict[str, Any] = {"exists": False}
    if repeated:
        product["note"] = (
            "Not worked out: the "
            + " and ".join(f"{p.role} primer sits in {p.occurrences} places" for p in repeated)
            + ", so which product you would get depends on which site wins."
        )
    elif forward is None or reverse is None:
        both = placements[0].orientation or "?"
        product["note"] = (
            f"Both primers read the same way ({both}), so they cannot make a product "
            "on this template. One of them has to be the reverse primer, written as "
            "it would be ordered."
        )
    elif reverse.at is None or forward.at is None or reverse.at < forward.at:
        product["note"] = (
            "The reverse primer sits before the forward one, so they point away from "
            "each other. On a circular template that is an inverse PCR; on a linear "
            "one it is nothing."
        )
    else:
        size = reverse.at + len(right) - forward.at
        product = {
            "exists": True,
            "size": size,
            "from": forward.at,
            "to": reverse.at + len(right),
            "sequence": template[forward.at : reverse.at + len(right)],
            "in_range": limits.product_min <= size <= limits.product_max,
            "wanted": [limits.product_min, limits.product_max],
        }

    # What the template does to the two sites, and what else they would find.
    # Template accessibility is temperature-dependent. Without an explicit
    # named protocol temperature, computing it at `primer Tm - 5` would invent
    # a bench condition. The check utility therefore leaves it unresolved.
    openings = None

    background_value = request.get("background")
    if background_value is not None and not isinstance(background_value, str):
        raise ValueError(f"`background` must be text, not {background_value!r}")
    background = background_value or ""
    max_mismatches = _integer(
        request.get("max_mismatches"),
        name="specificity max_mismatches",
        default=3,
        minimum=0,
        maximum=spec.MAX_MISMATCHES,
    )
    off_targets: dict[str, Any] = {"checked": False}
    if background.strip():
        found = spec.scan(
            {"left": left, "right": right},
            background,
            reaction=chosen.reaction,
            max_mismatches=max_mismatches,
            max_product=max(limits.product_max * 3, 3000),
            min_dg=None,
        )
        off_targets = {
            "checked": True,
            **spec.specificity_to_dict(found, max_products=8),
        }

    return {
        "engine": "flanking-pair",
        "mode": "check",
        "provenance": provenance(conditions),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **conditions,
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "constraints": {name: getattr(limits, name) for name in Constraints.__dataclass_fields__},
        "primers": {
            role: {
                **report_to_dict(report),
                "at": next(p.at for p in placements if p.role == role),
                "occurrences": next(p.occurrences for p in placements if p.role == role),
                "orientation": next(p.orientation for p in placements if p.role == role),
                "checks": measurements[role],
            }
            for role, report in reports.items()
        },
        "pair": {"checks": pair_checks},
        "product": product,
        "accessibility": openings,
        "off_targets": off_targets,
        "note": (
            "Nothing here is ranked, because one pair is not a choice. Each number "
            "is shown beside the window a designed primer would have been held to, "
            "and a measurement outside that window is not thereby wrong -- it is "
            "outside a window chosen for a different reaction."
        ),
    }
