import math
import time

from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator

from config.errors import DomainError


def verified(user) -> bool:
    return bool(
        user
        and user.is_active
        and EmailAddress.objects.filter(user=user, verified=True, email__iexact=user.email).exists()
    )


def mfa_enabled(user) -> bool:
    return Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists()


def mfa_required(user) -> bool:
    return bool(
        user.is_staff
        or user.memberships.filter(
            active=True, role="owner", workspace__kind="organization"
        ).exists()
    )


def require_mfa(user):
    if not mfa_enabled(user):
        raise DomainError("mfa_required", "Enroll an authenticator before privileged access.", 403)


def mfa_authenticated(request) -> bool:
    from allauth.account.authentication import get_authentication_records

    now = time.time()
    return any(
        record.get("method") == "mfa"
        and isinstance(record.get("at"), (int, float))
        and not isinstance(record.get("at"), bool)
        and math.isfinite(record["at"])
        and record["at"] <= now
        for record in get_authentication_records(request)
    )


def require_authenticated_mfa(request):
    require_mfa(request.user)
    if not mfa_authenticated(request):
        raise DomainError(
            "mfa_authentication_required",
            "Confirm your authenticator in Account settings before privileged access.",
            403,
        )


def require_recent_mfa(request):
    from allauth.account.authentication import get_authentication_records

    # allauth writes these records on real password/MFA authentication and reauthentication.
    records = get_authentication_records(request)
    now = time.time()
    if not any(
        record.get("method") == "mfa" and 0 <= now - record.get("at", 0) <= 300
        for record in records
    ):
        raise DomainError(
            "reauthentication_required", "Confirm your authenticator within five minutes.", 403
        )
