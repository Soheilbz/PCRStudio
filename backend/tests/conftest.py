import time

import pytest
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.core.cache import cache
from django.db import connection
from rest_framework.test import APIClient

from accounts.adapters import MFAAdapter
from accounts.models import User
from workspaces.models import Membership, Workspace


@pytest.fixture(autouse=True)
def require_postgres(settings):
    assert connection.vendor == "postgresql", "Foundation acceptance requires real PostgreSQL"
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    cache.clear()  # Dedicated test-only Valkey database, distinct from live authentication.


@pytest.fixture
def user_factory(db):
    def create(email="owner@example.test", *, mfa=False, verified=True, staff=False):
        user = User.objects.create_user(email, "Synthetic-secure-password-493!", is_staff=staff)
        EmailAddress.objects.create(user=user, email=user.email, verified=verified, primary=True)
        if mfa:
            Authenticator.objects.create(
                user=user,
                type=Authenticator.Type.TOTP,
                data={"secret": MFAAdapter().encrypt("JBSWY3DPEHPK3PXP")},
            )
        return user

    return create


@pytest.fixture
def owner(user_factory):
    return user_factory(mfa=True)


@pytest.fixture
def organization(owner):
    workspace = Workspace.objects.create(name="Synthetic organization", kind="organization")
    Membership.objects.create(workspace=workspace, user=owner, role="owner")
    return workspace


@pytest.fixture
def api(owner):
    client = APIClient()
    client.force_login(owner, backend="django.contrib.auth.backends.ModelBackend")
    # Domain-policy fixture represents an already MFA-authenticated owner. Real
    # allauth enrollment/login/old-session regressions are tested separately.
    session = client.session
    session["account_authentication_methods"] = [
        {"method": "mfa", "at": time.time(), "authenticator_type": "totp"}
    ]
    session.save()
    return client
