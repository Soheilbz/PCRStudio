"""What every engine has to work out before it can search.

Three engines now read the same kind of request: a sequence, an enzyme, a set
of constraints, and an assay whose own numbers sit underneath them. Working
that out three times would mean three chances for the layering order to drift
apart, and the layering order is an argument about what beats what -- not the
sort of thing that should exist in three copies.

So it happens once, here, and each engine takes a `Settings` and gets on with
the part that is actually its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .design import Constraints
from .intake import Target, resolve
from .presets import Polymerase, Purpose, Reaction, polymerase, purpose
from .scientific_integrity import (
    enforce_constraint_overrides,
    enforce_polymerase_identity,
    enforce_reaction_overrides,
    resolve_purpose,
)
from .thermo import DEFAULT_CONDITIONS

ENZYME_NEEDS = {
    "strand-displacing": (
        "strand_displacing",
        True,
        "the reaction has no denaturation step, so the polymerase must open the duplex",
    ),
    "thermostable": (
        "thermostable",
        True,
        "the assay repeatedly denatures at high temperature",
    ),
    "five-prime-exonuclease": (
        "five_prime_exonuclease",
        True,
        "the assay's signal depends on the polymerase cleaving through the probe",
    ),
    "no-five-prime-exonuclease": (
        "five_prime_exonuclease",
        False,
        "the assay keeps multiple primer pairs together and must not consume downstream primers",
    ),
    "proofreading": (
        "proofreading",
        True,
        "the assay requires a proofreading-capable polymerase",
    ),
    "no-proofreading": (
        "proofreading",
        False,
        "the assay relies on a deliberate 3-prime mismatch",
    ),
    "rpa-compatible": (
        "rpa_compatible",
        True,
        "RPA needs a complete recombinase-compatible chemistry",
    ),
}


def _validate_assay_contract(
    assay: dict[str, Any], preset: Polymerase, assay_name: str, request: dict[str, Any]
) -> None:
    """Enforce profile chemistry at every specialized-worker boundary."""
    raw_needs = assay.get("enzyme")
    if raw_needs is not None:
        if not isinstance(raw_needs, list) or not all(isinstance(need, str) for need in raw_needs):
            raise ValueError("`assay.enzyme` must be a list of capability names")
        needs = list(raw_needs)
        known_activity_names = {"strand-displacing", "thermostable", "rpa-compatible"}
        if not any(need in known_activity_names for need in needs):
            needs.append("thermostable")
        for need in needs:
            contract = ENZYME_NEEDS.get(need)
            if contract is None:
                known = ", ".join(sorted(ENZYME_NEEDS))
                raise ValueError(f"unknown assay enzyme capability `{need}`. Known: {known}")
            activity, wanted, why = contract
            actual = getattr(preset, activity)
            if actual != wanted:
                expected = "has" if wanted else "does not have"
                observed = "has" if actual else "does not have"
                raise ValueError(
                    f"{preset.name} cannot run {assay_name}: this assay needs an enzyme that "
                    f"{expected} `{need}` because {why}; the selected preset {observed} "
                    f"`{need}`."
                )

    requirements = assay.get("requires")
    if requirements is not None:
        if not isinstance(requirements, list) or not all(
            isinstance(requirement, str) for requirement in requirements
        ):
            raise ValueError("`assay.requires` must be a list of requirement names")
        for requirement in requirements:
            if requirement not in {"background", "inclusivity"}:
                raise ValueError(f"unknown assay requirement `{requirement}`")
            value = request.get(requirement)
            if not isinstance(value, str) or not value.strip():
                if requirement == "background":
                    raise ValueError(
                        "This assay requires a non-empty `background` exclusion panel. "
                        "Provide the sequences it must stay silent on."
                    )
                raise ValueError(
                    "This assay requires a non-empty `inclusivity` target-diversity panel. "
                    "Strict species-specific claims are not made from one representative template."
                )


@dataclass
class Settings:
    """Everything decided before the search, and how it was decided."""

    target: Target
    preset: Polymerase
    reaction: Reaction
    intent: Purpose
    limits: Constraints

    assay_id: str
    assay_name: str
    assay_engine: str
    assay_status: str
    assay_profile_authority: dict[str, Any]
    assay_constraints: dict[str, Any]
    assay_chemistry_family: str
    assay_cycling: dict[str, Any]
    assay_purposes: list[str]
    assay_modifiers: list[str]
    assay_requires: list[str]
    assay_enzyme: list[str]
    parameter_resolution: dict[str, Any]
    #: Where the assay's own number was not the one used, and why.
    overruled: list[dict[str, Any]] = field(default_factory=list)

    def assay_to_dict(self) -> dict[str, Any]:
        """The assay layer, for a result that has to explain itself."""
        return {
            "id": self.assay_id,
            "name": self.assay_name,
            "engine": self.assay_engine,
            "status": self.assay_status,
            "profile_authority": self.assay_profile_authority,
            "defaults": self.assay_constraints,
            "chemistry_family": self.assay_chemistry_family,
            "purposes": self.assay_purposes,
            "modifiers": self.assay_modifiers,
            "requires": self.assay_requires,
            "enzyme": self.assay_enzyme,
            "overruled": self.overruled,
            "parameter_resolution": self.parameter_resolution,
        }


_POLICIES = {"locked", "bounded", "recommended"}


def _profile_policy(raw: Any, *, label: str) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"`assay.defaults.{label}` must be an object")
    answer: dict[str, str] = {}
    for name, value in raw.items():
        policy = str(value).strip().lower()
        if policy not in _POLICIES:
            raise ValueError(
                f"`assay.defaults.{label}.{name}` has unknown policy {value!r}; "
                "use locked, bounded or recommended"
            )
        answer[str(name)] = policy
    return answer


def _policy_label(policy: str) -> str:
    return {
        "locked": "locked-assay-invariant",
        "bounded": "bounded-to-assay-envelope",
        "recommended": "recommended-starting-value-user-tunable",
    }[policy]


def prepare(
    request: dict[str, Any],
    *,
    constraints_key: str = "constraints",
    require_product_room: bool = True,
) -> Settings:
    """Read a request as far as every engine reads it the same way.

    Args:
        constraints_key: Which field in the request holds the constraints. The
            nested engine has two sets and names them `outer` and `inner`, so
            it asks for its own.
        require_product_room: Whether a template shorter than the shortest
            product is a refusal. False for inverse PCR, where the product is
            not made of the template at all.

    Raises:
        IntakeError: the input is not a usable template.
        ValueError: a constraint, preset, purpose or reaction that cannot hold.
    """
    raw_template = request.get("template") or ""
    masking = request.get("lowercase_masking")
    if masking is not None and not isinstance(masking, bool):
        raise ValueError("`lowercase_masking` must be true or false")
    target = resolve(
        raw_template,
        name=str(request.get("name") or ""),
        lowercase_masking=masking,
    )

    assay = request.get("assay") or {}
    if not isinstance(assay, dict):
        raise ValueError("`assay` must be an object")
    assay_defaults = assay.get("defaults") or {}
    if not isinstance(assay_defaults, dict):
        raise ValueError("`assay.defaults` must be an object")
    assay_name = assay.get("name") or assay.get("id") or "this assay"
    constraint_policy = _profile_policy(
        assay_defaults.get("constraintPolicy"), label="constraintPolicy"
    )
    constraint_envelope = assay_defaults.get("constraintEnvelope") or {}
    if not isinstance(constraint_envelope, dict):
        raise ValueError("`assay.defaults.constraintEnvelope` must be an object")
    condition_policy = _profile_policy(
        assay_defaults.get("conditionPolicy"), label="conditionPolicy"
    )
    chemistry_family = str(assay_defaults.get("chemistryFamily") or "")
    if str(assay.get("id") or "") == "kasp" and chemistry_family != "kasp-endpoint-fret":
        raise ValueError(
            "KASP requires `assay.defaults.chemistryFamily=kasp-endpoint-fret`. "
            "A qPCR/intercalating-dye alias is not a valid KASP chemistry identity."
        )

    # The assay's own enzyme, unless one was named. Long-range PCR is not
    # ordinary PCR with a bigger number in it -- it is a different enzyme, with
    # a different extension rate and, for some, a two-step programme.
    expected_preset = polymerase(assay_defaults.get("polymerase"))
    preset = polymerase(request.get("polymerase") or assay_defaults.get("polymerase"))
    _validate_assay_contract(assay, preset, str(assay_name), request)
    enforce_polymerase_identity(
        preset.id,
        expected_preset.id,
        assay_id=str(assay.get("id") or ""),
        allowed=[str(value) for value in (assay_defaults.get("allowedPolymerases") or [])],
    )

    overrides = request.get("conditions") or {}
    unknown = sorted(set(overrides) - set(DEFAULT_CONDITIONS))
    if unknown:
        raise ValueError(f"unknown reaction condition(s): {', '.join(unknown)}")
    preset_conditions = preset.reaction.as_conditions()
    enforce_reaction_overrides(
        overrides, preset_conditions, context=f"assay `{assay.get('id') or assay_name}`"
    )
    reaction = Reaction(**{**preset_conditions, **overrides})
    reaction.validate()

    # An assay that cannot serve a purpose says so before designing, rather
    # than returning something neither party wanted. A colony screen asked for
    # a three-kilobase cloning product is not a preference to be balanced.
    allowed = list(assay_defaults.get("purposes") or [])
    wanted = resolve_purpose(
        request.get("purpose"),
        assay_defaults.get("defaultPurpose"),
        allowed,
        assay_name=str(assay_name),
    )
    if wanted and allowed and wanted not in allowed:
        raise ValueError(
            f"{assay_name} cannot be used for `{wanted}`. It serves: "
            + ", ".join(sorted(allowed))
            + "."
        )
    intent = purpose(wanted)

    supplied = request.get(constraints_key) or {}
    strange = sorted(set(supplied) - set(Constraints.__dataclass_fields__))
    if strange:
        raise ValueError(f"unknown constraint(s): {', '.join(strange)}")

    constraint_defaults = dict(assay_defaults.get("constraints") or {})
    unheard = sorted(set(constraint_defaults) - set(Constraints.__dataclass_fields__))
    if unheard:
        # A profile naming a field the worker does not have is a mistake in
        # profiles.toml, and one that would otherwise be invisible: the setting
        # would simply never take effect.
        raise ValueError(
            f"the assay `{assay.get('id', '?')}` sets {', '.join(unheard)}, which "
            "is not a constraint this worker knows"
        )

    generic_defaults = {
        field: getattr(Constraints(), field) for field in Constraints.__dataclass_fields__
    }
    baseline_limits = {**generic_defaults, **intent.constraints, **constraint_defaults}
    override_classifications = enforce_constraint_overrides(
        supplied,
        baseline_limits,
        policies=constraint_policy,
        envelopes=constraint_envelope,
        context=f"assay `{assay.get('id') or assay_name}`",
    )

    # Three layers, in this order, and the order is the argument:
    #
    #   the purpose    what the product is for afterwards. Sanger wants a
    #                  length its read can cover; cloning wants the whole gene.
    #   the assay      what the reaction physically is. A colony lysate cannot
    #                  give a four-kilobase product however good the primers
    #                  are, and no downstream wish changes that -- which is why
    #                  the assay sits above the purpose rather than below it.
    #                  Where the two cannot both be served, the purposes list
    #                  above has already refused the combination outright.
    #   what was typed the caller may tune a field declared `recommended`;
    #                  `bounded`/`locked` fields retain their reviewed envelope.
    #                  Reaction chemistry remains separately identity-locked.
    layers = {**intent.constraints, **constraint_defaults, **supplied}
    overruled = [
        {
            "field": name,
            "assay_wanted": constraint_defaults[name],
            "used": layers[name],
            "because": "you set it",
        }
        for name in sorted(constraint_defaults)
        if constraint_defaults[name] != layers[name]
    ]
    limits = Constraints(**layers)

    # Record why each resolved value won.  The value alone is not a complete
    # implementation contract: a later run also needs to know whether it came
    # from a user override, an assay profile, a purpose or PCRStudio itself.
    condition_resolution = {
        name: {
            "value": getattr(reaction, name),
            "source": "policy-checked-user-override" if name in overrides else "polymerase-profile",
            "override_policy": _policy_label(condition_policy.get(name, "recommended")),
        }
        for name in DEFAULT_CONDITIONS
    }
    constraint_resolution: dict[str, dict[str, Any]] = {}
    for name in Constraints.__dataclass_fields__:
        if name in supplied:
            source = "policy-checked-user-override"
        elif name in constraint_defaults:
            source = "assay-recommended-default"
        elif name in intent.constraints:
            source = "purpose-default"
        else:
            source = "pcrstudio-default"
        constraint_resolution[name] = {
            "value": getattr(limits, name),
            "source": source,
            "override_policy": _policy_label(constraint_policy.get(name, "recommended")),
            **(
                {"qualification_envelope": constraint_envelope[name]}
                if name in constraint_envelope
                else {}
            ),
            **(
                {"change_class": override_classifications[name]}
                if name in override_classifications
                else {}
            ),
        }

    # A template of nothing but ambiguity codes is not a template. Caught here
    # so a run does not spend its time proving it.
    if len(target.ambiguous_at) == target.length:
        raise ValueError(
            "Every base of this sequence is an ambiguity code, so there is nothing "
            "to design against."
        )
    if require_product_room and target.length < limits.product_min:
        raise ValueError(
            f"The template is {target.length} bases and the shortest product asked "
            f"for is {limits.product_min}. Either the wrong sequence arrived or the "
            "product size range needs lowering."
        )

    return Settings(
        target=target,
        preset=preset,
        reaction=reaction,
        intent=intent,
        limits=limits,
        assay_id=str(assay.get("id", "")),
        assay_name=str(assay.get("name", "")),
        assay_engine=str(assay.get("engine", "")),
        assay_status=str(assay.get("status", "")),
        assay_profile_authority=dict(assay.get("profileAuthority") or {}),
        assay_constraints=constraint_defaults,
        assay_chemistry_family=chemistry_family,
        assay_cycling=dict(assay_defaults.get("cycling") or {}),
        assay_purposes=allowed,
        assay_modifiers=[str(value) for value in (assay.get("modifiers") or [])],
        assay_requires=[str(value) for value in (assay.get("requires") or [])],
        assay_enzyme=[str(value) for value in (assay.get("enzyme") or [])],
        parameter_resolution={
            "contract_version": "1.0.0",
            "reaction": condition_resolution,
            "constraints": constraint_resolution,
        },
        overruled=overruled,
    )


def how_many_from(request: dict[str, Any], most: int) -> int:
    """How many answers were asked for, refused if it could not be met.

    Raises:
        ValueError: naming the number given and the range that exists.
    """
    how_many = request.get("how_many", 5)
    if isinstance(how_many, bool) or not isinstance(how_many, int):
        raise ValueError(f"`how_many` must be an integer, not {how_many!r}")
    if not 1 <= how_many <= most:
        raise ValueError(
            f"between 1 and {most} designs can be asked for, not {how_many}. "
            "Primer3 refuses zero, and past a few dozen the answers stop being "
            "different designs."
        )
    return how_many


#: The longest oligo name to put on an order sheet.
#:
#: Synthesis vendors truncate or reject long names, and a tube label has to be
#: readable by somebody holding the tube.
MAX_OLIGO_NAME = 24

#: How much of that a caller needs for what it appends.
#:
#: `_12oF` is the longest: two digits, a round and a role.
SUFFIX_ROOM = 5


def label(name: str) -> str:
    """A name that can go on a tube and through an order form.

    A FASTA header is a sentence -- `NM_000546.6 Homo sapiens tumor protein p53
    (TP53), transcript variant 1, mRNA` -- and pasting that into an order form
    produces a name with commas and brackets in it, which is how a CSV column
    ends up in the wrong place. The first word of a header is the accession or
    the identifier, which is what somebody would have written by hand anyway.
    """
    first = name.strip().split()[0] if name.strip() else "primer"
    safe = "".join(
        character if character.isalnum() or character in "._-" else "_" for character in first
    )
    safe = safe.strip("_") or "primer"
    # Room left for what gets appended. Every caller adds an index and a role,
    # and a nested design adds a round as well, so trimming to the cap here
    # and then appending produced names longer than the cap it just applied.
    return safe[: MAX_OLIGO_NAME - SUFFIX_ROOM]


def excluded_from(request: dict[str, Any]) -> list[tuple[int, int]]:
    """Stretches no primer may overlap, as the worker's own pairs.

    Read in one place because four workers now take them and the wire shape is
    a list of two-element lists, which is easy to mis-unpack in a way that
    silently excludes the wrong stretch. A region that cannot be read is
    refused by name rather than dropped.
    """
    raw = request.get("excluded")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ValueError("`excluded` must be a list of [start, length] regions")
    regions: list[tuple[int, int]] = []
    for entry in raw:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            start, length = entry
            if isinstance(start, bool) or not isinstance(start, int) or start < 0:
                raise ValueError(f"excluded start must be a non-negative integer, not {start!r}")
            if isinstance(length, bool) or not isinstance(length, int) or length < 1:
                raise ValueError(f"excluded length must be a positive integer, not {length!r}")
            regions.append((start, length))
        else:
            raise ValueError(f"an excluded region should be a start and a length, not {entry!r}")
    return regions
