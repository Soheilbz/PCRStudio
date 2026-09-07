"""Release-grade scientific-integrity invariants shared by all engines.

PCRStudio is allowed to refuse a request. It is not allowed to make the
request easier by silently changing the assay, chemistry, evidence scope or
validated parameter envelope.  Development mode exists only for explicit
engineering work and is never the default.
"""

from __future__ import annotations

import math
import os
from typing import Any

POLICY_VERSION = "1.1.0"
_ENV = "PCRSTUDIO_SCIENTIFIC_POLICY"
_POLICIES = {"strict", "development"}

# Parameters for which larger means a *narrower/safer* search envelope.
_MIN_TIGHTENS = {
    "gc_clamp",
    "min_three_prime_distance",
    "min_coverage",
    "conserved_end",
}
# Parameters for which smaller means a *narrower/safer* search envelope.
_MAX_TIGHTENS = {
    "max_end_gc",
    "max_poly_x",
    "tm_pair_max_difference",
    "max_degeneracy",
    "tm_spread_max",
}


def policy() -> str:
    """Return the active scientific policy; unknown/missing values fail strict."""
    value = os.environ.get(_ENV, "strict").strip().lower()
    return value if value in _POLICIES else "strict"


def strict() -> bool:
    return policy() == "strict"


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _change_kind(name: str, original: Any, proposed: Any, baseline: dict[str, Any]) -> str:
    """Classify a change without pretending every parameter is monotonic.

    Returns ``same``, ``tightening``, ``within-envelope-tuning`` or ``unsafe``.
    Unknown/non-monotonic changes are unsafe for executable named-assay runtime.
    That is intentional: if a parameter needs a new scientifically valid direction,
    the profile must document it rather than relying on a generic guess.
    """
    if proposed == original:
        return "same"
    before = _finite_number(original)
    after = _finite_number(proposed)
    if before is None or after is None:
        return "unsafe"

    if name.endswith("_min"):
        return "tightening" if after >= before else "unsafe"
    if name.endswith("_max"):
        return "tightening" if after <= before else "unsafe"
    if name in _MIN_TIGHTENS:
        return "tightening" if after >= before else "unsafe"
    if name in _MAX_TIGHTENS:
        return "tightening" if after <= before else "unsafe"

    # Optima influence ranking but do not widen the legal candidate envelope.
    # They are allowed only when they remain inside an explicitly represented
    # min/max interval for the same quantity.
    if name.endswith("_opt"):
        stem = name[:-4]
        low = _finite_number(baseline.get(f"{stem}_min"))
        high = _finite_number(baseline.get(f"{stem}_max"))
        if low is not None and high is not None and low <= after <= high:
            return "within-envelope-tuning"
        return "unsafe"

    return "unsafe"


def enforce_constraint_overrides(
    supplied: dict[str, Any],
    baseline: dict[str, Any],
    *,
    policies: dict[str, str] | None = None,
    envelopes: dict[str, Any] | None = None,
    context: str = "assay profile",
) -> dict[str, str]:
    """Apply the profile's declared authority to numeric design overrides.

    Policy semantics are intentionally three different things:

    ``locked``
        An assay/chemistry invariant. Any changed value is a different
        versioned profile and is refused by every executable named-assay path.
    ``bounded``
        A reviewed validity envelope. The caller may only tighten it (or move
        an optimum inside the represented bounds); widening is refused.
    ``recommended``
        A starting/tuning value, *not* scientific validity authority. An
        explicit numeric caller value may move in either direction and is
        recorded as user tuning. Structural consistency is still checked by
        the engine's Constraints.validate()/assay-specific validator.

    This distinction prevents a convenient default such as a Tm, GC or product
    window from becoming an accidental hard scientific gate merely because it
    was present in a profile. ``envelopes`` can independently bound a tunable
    default to the outer range qualified for a named/versioned branch; unlike a
    `bounded` default, that outer envelope does not become the search default.
    """
    policies = policies or {}
    envelopes = envelopes or {}
    if not isinstance(envelopes, dict):
        raise ValueError(f"constraintEnvelope for {context} must be an object")
    classifications: dict[str, str] = {}
    for name, proposed in supplied.items():
        if name not in baseline:
            classifications[name] = "unprofiled"
            raise ValueError(
                f"`{name}` is not represented in the active {context}; executable named-assay "
                "runtime will not invent an override rule. Add a versioned profile/contract first."
            )

        original = baseline[name]

        raw_envelope = envelopes.get(name)
        if raw_envelope is not None:
            if not isinstance(raw_envelope, dict):
                raise ValueError(
                    f"constraintEnvelope.{name} for {context} must be an object with optional min/max"
                )
            unknown_envelope_keys = sorted(set(raw_envelope) - {"min", "max"})
            if unknown_envelope_keys:
                raise ValueError(
                    f"constraintEnvelope.{name} for {context} has unknown key(s): "
                    + ", ".join(unknown_envelope_keys)
                )
            minimum = (
                _finite_number(raw_envelope.get("min"))
                if raw_envelope.get("min") is not None
                else None
            )
            maximum = (
                _finite_number(raw_envelope.get("max"))
                if raw_envelope.get("max") is not None
                else None
            )
            if minimum is None and maximum is None:
                raise ValueError(
                    f"constraintEnvelope.{name} for {context} must declare at least one finite min/max"
                )
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(
                    f"constraintEnvelope.{name} for {context} has min {minimum} greater than max {maximum}"
                )
            proposed_number = _finite_number(proposed)
            if proposed_number is None:
                classifications[name] = "unsafe"
                raise ValueError(
                    f"`{name}` must be a finite numeric value inside the qualified {context} envelope"
                )
            elif (minimum is not None and proposed_number < minimum) or (
                maximum is not None and proposed_number > maximum
            ):
                classifications[name] = "outside-qualified-envelope"
                rendered = []
                if minimum is not None:
                    rendered.append(f">= {minimum:g}")
                if maximum is not None:
                    rendered.append(f"<= {maximum:g}")
                raise ValueError(
                    f"`{name}`={proposed_number:g} is outside the versioned {context} qualification "
                    f"envelope ({' and '.join(rendered)}). Select/add a separately reviewed profile "
                    "instead of extrapolating this named branch."
                )

        declared = str(policies.get(name, "recommended")).strip().lower()
        if declared not in {"locked", "bounded", "recommended"}:
            raise ValueError(
                f"unknown constraint policy {declared!r} for `{name}` in {context}; "
                "expected locked, bounded or recommended"
            )

        if proposed == original:
            classifications[name] = "same"
            continue

        # A recommended value is a transparent starting point. It may be tuned
        # in either direction, but it remains a numeric design constraint and
        # the downstream validator still owns legal ranges/cross-field logic.
        if declared == "recommended":
            if _finite_number(proposed) is None:
                classifications[name] = "unsafe"
                raise ValueError(
                    f"`{name}` must be a finite numeric tuning value in {context}, not {proposed!r}."
                )
            else:
                classifications[name] = "recommended-tuning"
            continue

        kind = _change_kind(name, original, proposed, baseline)
        classifications[name] = kind
        if declared == "locked":
            raise ValueError(
                f"`{name}` is a locked {context} invariant ({original!r}); select a different "
                f"versioned profile instead of overriding it to {proposed!r}."
            )
        if kind == "unsafe":
            raise ValueError(
                f"`{name}` cannot change from {original!r} to {proposed!r} because that would "
                f"widen or leave the reviewed {context} envelope. "
                "Create/select a separately reviewed versioned profile for that condition."
            )
    return classifications


def enforce_reaction_overrides(
    supplied: dict[str, Any], baseline: dict[str, Any], *, context: str
) -> None:
    """Reaction chemistry has no generic monotonic 'safer' direction.

    Therefore a changed salt/Mg/dNTP/oligo concentration is a different
    thermodynamic context. Every executable named-assay path requires it to be
    represented by a named/versioned chemistry profile rather than an anonymous
    override; development policy cannot change the chemistry of the same assay.
    """
    changed = {name: value for name, value in supplied.items() if baseline.get(name) != value}
    if changed:
        fields = ", ".join(sorted(changed))
        raise ValueError(
            f"Executable named-assay runtime does not allow anonymous reaction-condition override(s) "
            f"({fields}) on {context}. Select or add a named, sourced and versioned chemistry profile."
        )


def enforce_polymerase_identity(
    selected: str,
    expected: str,
    *,
    assay_id: str,
    allowed: list[str] | tuple[str, ...] = (),
) -> None:
    """Prevent capability-equivalent enzymes from being treated as assay-equivalent.

    This is a named-assay identity invariant, not a Strict-mode preference.
    Development mode may expose research diagnostics but may not silently change
    the polymerase attached to the same assay identity.
    """
    valid = {expected, *(str(item) for item in allowed)}
    if selected not in valid:
        raise ValueError(
            f"assay `{assay_id or 'unprofiled'}` is scientifically bound to chemistry "
            f"{sorted(valid)!r}; `{selected}` is not a reviewed equivalent. Use a separate versioned profile."
        )


def resolve_purpose(
    requested: Any,
    default: Any,
    allowed: list[str],
    *,
    assay_name: str,
) -> str | None:
    """Resolve purpose without a hidden ``general`` fallback in any executable mode."""
    wanted = requested or default
    if not wanted and len(allowed) == 1:
        wanted = allowed[0]
    if not wanted and allowed:
        raise ValueError(
            f"{assay_name} has multiple supported purposes and no purpose was selected. "
            "Executable runtime will not silently choose `general`."
        )
    return str(wanted) if wanted else None


PROFILE_AUTHORITY_SOURCE = "pcr-core:profiles.toml"
PROFILE_AUTHORITY_TRANSPORT = "server-injected-canonical-profile"


def require_named_assay(
    request: dict[str, Any],
    *,
    command: str = "",
    require_profile_authority: bool = False,
) -> str:
    """Require an explicit named assay and, at release orchestration, its source marker.

    Low-level engine functions remain directly testable with a named assay. The
    release orchestration path is stricter: the Rust API must have injected the
    canonical profile from ``pcr-core/profiles.toml``. ``profileAuthority`` is a
    provenance/trust-boundary marker, not a cryptographic authentication token;
    it prevents accidental direct-worker payloads from being represented as
    server-resolved canonical profile runs.
    """
    assay = request.get("assay")
    module_id = str(assay.get("id") or "") if isinstance(assay, dict) else ""
    if not module_id:
        label = f" for worker command `{command}`" if command else ""
        raise ValueError(
            "Executable worker runtime requires an explicit named `assay.id`"
            + label
            + ". Unprofiled low-level helpers may be used in isolated research tests, but a worker run must not synthesize scientific identity from defaults."
        )
    if require_profile_authority:
        authority = assay.get("profileAuthority") if isinstance(assay, dict) else None
        valid = (
            isinstance(authority, dict)
            and authority.get("source") == PROFILE_AUTHORITY_SOURCE
            and authority.get("profileId") == module_id
            and authority.get("transport") == PROFILE_AUTHORITY_TRANSPORT
        )
        if not valid:
            label = f" for worker command `{command}`" if command else ""
            raise ValueError(
                "Release orchestration requires the server-injected canonical profile authority"
                + label
                + "; an assay id by itself does not prove that chemistry/defaults came from the reviewed profile registry."
            )
    return module_id


def provenance_block() -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "mode": policy(),
        "fail_closed": strict(),
        "invariants": [
            "named-assay-profile-required",
            "no-primary-backend-substitution",
            "no-hard-gate-relaxation",
            "no-anonymous-chemistry-substitution",
            "no-hidden-purpose-default",
            "no-guessed-annealing-core",
            "no-smoke-database-production-claim",
            "no-ranking-heuristic-as-scientific-gate",
            "optional-evidence-does-not-change-deterministic-selection",
            "named-bench-protocol-authority-when-protocol-specific",
            "no-wet-lab-validation-inference",
        ],
    }
