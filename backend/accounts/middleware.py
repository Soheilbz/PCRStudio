import hashlib

import redis
from django.conf import settings
from django.http import JsonResponse

from accounts.policy import mfa_enabled, mfa_required, require_recent_mfa
from config.errors import DomainError

# Shared atomic counter. No payload, email, query string, or raw IP is retained.
_LIMIT_SCRIPT = """
local n=redis.call('INCR', KEYS[1])
if n==1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


def limiter_client():
    return redis.Redis.from_url(settings.VALKEY_URL, socket_connect_timeout=1, socket_timeout=1)


class AuthLimiterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/_allauth/") and request.method in {"POST", "PUT", "DELETE"}:
            # Only the private Caddy proxy can reach the API; it sanitizes this header.
            address = (
                request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "unknown"))
                .split(",")[0]
                .strip()
            )
            identity = hashlib.sha256((settings.SECRET_KEY + address).encode()).hexdigest()
            try:
                count = limiter_client().eval(_LIMIT_SCRIPT, 1, f"pcrstudio:auth:{identity}", 60)
                if count > 30:
                    return JsonResponse(
                        {"code": "rate_limited", "detail": "Wait before retrying."}, status=429
                    )
            except redis.RedisError:
                return JsonResponse(
                    {
                        "code": "auth_unavailable",
                        "detail": "Authentication is temporarily unavailable.",
                    },
                    status=503,
                )
        return self.get_response(request)


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/api/", "/_allauth/")):
            response["Cache-Control"] = "private, no-store"
            response["Pragma"] = "no-cache"
            response["Vary"] = "Cookie"
        return response


class MandatoryMFAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # allauth headless TOTP DELETE is inputless. Apply mandatory policy here as
        # well as in the adapter used by headed forms.
        if (
            request.path == "/_allauth/browser/v1/account/authenticators/totp"
            and request.method == "DELETE"
            and request.user.is_authenticated
            and mfa_required(request.user)
        ):
            return JsonResponse(
                {"code": "mfa_required", "detail": "Your role requires an authenticator."},
                status=403,
            )
        # Identity-provider credential endpoints need the same factor strength:
        # a recent password-only session must not obtain/regenerate recovery
        # codes and thereby upgrade itself to MFA-authenticated privileges.
        credential_write = request.method in {"POST", "PUT", "PATCH", "DELETE"} and (
            request.path.startswith("/_allauth/browser/v1/account/authenticators/")
            or request.path
            in {
                "/_allauth/browser/v1/account/email",
                "/_allauth/browser/v1/account/password/change",
            }
        )
        recovery_read = (
            request.path == "/_allauth/browser/v1/account/authenticators/recovery-codes"
            and request.method == "GET"
        )
        if (
            (credential_write or recovery_read)
            and request.user.is_authenticated
            and mfa_enabled(request.user)
        ):
            try:
                require_recent_mfa(request)
            except DomainError as error:
                return JsonResponse(
                    {
                        "status": 403,
                        "errors": [{"code": error.get_codes(), "message": str(error.detail)}],
                    },
                    status=403,
                )
        return self.get_response(request)
