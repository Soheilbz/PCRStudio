from rest_framework.permissions import BasePermission

from accounts.policy import mfa_required, require_authenticated_mfa, verified


class VerifiedAccount(BasePermission):
    message = "Sign in with a verified email account."

    def has_permission(self, request, view):
        if not verified(request.user):
            return False
        if mfa_required(request.user):
            require_authenticated_mfa(request)
        return True
