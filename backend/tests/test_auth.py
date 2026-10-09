import re
import time
from unittest.mock import patch

import pytest
import redis
from allauth.account.models import EmailConfirmationHMAC
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import format_hotp_value, hotp_value
from django.core.cache import cache
from django.test import Client

from accounts.adapters import MFAAdapter
from accounts.policy import mfa_enabled
from projects.services import create_project
from workspaces.models import Membership
from workspaces.services import revoke_member

pytestmark = pytest.mark.django_db


def csrf(client):
    response = client.get("/api/v1/csrf/")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def post(client, path, data, headers=None):
    return client.post(path, data, content_type="application/json", **(headers or csrf(client)))


def test_cookie_csrf_anonymous_and_unverified_denial(owner, user_factory):
    client = Client(enforce_csrf_checks=True)
    assert client.get("/api/v1/me/").status_code == 401
    client.force_login(owner)
    assert (
        client.post(
            "/api/v1/workspaces/", {"name": "Synthetic"}, content_type="application/json"
        ).status_code
        == 403
    )
    code = format_hotp_value(hotp_value("JBSWY3DPEHPK3PXP", int(time.time()) // 30))
    assert (
        post(client, "/_allauth/browser/v1/auth/2fa/reauthenticate", {"code": code}).status_code
        == 200
    )
    assert post(client, "/api/v1/workspaces/", {"name": "Synthetic"}).status_code == 201
    unverified = user_factory("unverified@example.test", verified=False)
    client.force_login(unverified)
    assert client.get("/api/v1/workspaces/").status_code == 403
    assert client.get("/api/v1/me/").status_code == 401


def test_allauth_login_verified_cookie_and_logout(user_factory):
    user = user_factory("login@example.test")
    client = Client(enforce_csrf_checks=True)
    response = post(
        client,
        "/_allauth/browser/v1/auth/login",
        {"email": user.email, "password": "Synthetic-secure-password-493!"},
    )
    assert response.status_code == 200
    assert response.json()["meta"]["is_authenticated"] is True
    assert "sessionid" in client.cookies
    assert client.cookies["sessionid"]["httponly"]
    assert client.get("/api/v1/me/").json()["id"] == str(user.id)
    headers = csrf(client)
    response = client.delete("/_allauth/browser/v1/auth/session", **headers)
    assert response.status_code in {200, 401}
    assert client.get("/api/v1/me/").status_code == 401


def test_allauth_unverified_login_then_email_verification(user_factory):
    user = user_factory("verify@example.test", verified=False)
    client = Client(enforce_csrf_checks=True)
    response = post(
        client,
        "/_allauth/browser/v1/auth/login",
        {"email": user.email, "password": "Synthetic-secure-password-493!"},
    )
    assert response.status_code == 401
    assert client.get("/api/v1/workspaces/").status_code == 403
    key = EmailConfirmationHMAC(user.emailaddress_set.get()).key
    assert post(client, "/_allauth/browser/v1/auth/email/verify", {"key": key}).status_code == 401
    assert (
        post(
            client,
            "/_allauth/browser/v1/auth/login",
            {"email": user.email, "password": "Synthetic-secure-password-493!"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/me/").status_code == 200


def test_allauth_password_reset_invalidates_sessions(user_factory, mailoutbox):
    user = user_factory("reset@example.test")
    old = Client(enforce_csrf_checks=True)
    old.force_login(user)
    reset = Client(enforce_csrf_checks=True)
    assert (
        post(reset, "/_allauth/browser/v1/auth/password/request", {"email": user.email}).status_code
        == 200
    )
    assert mailoutbox
    match = re.search(r"/account/password/reset/key/([^\s]+)", mailoutbox[-1].body)
    assert match
    key = match.group(1)
    response = post(
        reset,
        "/_allauth/browser/v1/auth/password/reset",
        {"key": key, "password": "Synthetic-new-password-594!"},
    )
    assert response.status_code in {200, 401}
    user.refresh_from_db()
    assert user.check_password("Synthetic-new-password-594!")
    assert old.get("/api/v1/me/").status_code == 401
    assert (
        post(
            reset,
            "/_allauth/browser/v1/auth/password/reset",
            {"key": key, "password": "Synthetic-reuse-password-595!"},
        ).status_code
        == 400
    )


def test_mfa_real_login_recent_recovery_and_owner_disable_gate(owner, organization, user_factory):
    removed = user_factory("removed-owner@example.test")
    creator = Membership.objects.create(user=removed, workspace=organization, role="member")
    target_user = user_factory("target@example.test")
    target = Membership.objects.create(user=target_user, workspace=organization, role="member")
    project = create_project(removed, organization.id, "Synthetic orphan")
    revoke_member(owner, organization.id, creator.id)
    cache.clear()
    client = Client(enforce_csrf_checks=True)
    response = post(
        client,
        "/_allauth/browser/v1/auth/login",
        {"email": owner.email, "password": "Synthetic-secure-password-493!"},
    )
    assert response.status_code == 401
    assert client.get("/api/v1/me/").status_code == 401
    code = format_hotp_value(hotp_value("JBSWY3DPEHPK3PXP", int(time.time()) // 30))
    response = post(client, "/_allauth/browser/v1/auth/2fa/authenticate", {"code": code})
    assert response.status_code == 200
    assert client.get("/api/v1/me/").status_code == 200
    body = {"membership_id": str(target.id), "version": 1, "reason": "owner_removed"}
    response = post(client, f"/api/v1/projects/{project.id}/recover/", body)
    assert response.status_code == 200
    assert client.get(f"/api/v1/projects/{project.id}/").status_code == 404
    response = client.delete("/_allauth/browser/v1/account/authenticators/totp", **csrf(client))
    assert response.status_code in {400, 403}
    assert mfa_enabled(owner)


def test_totp_enrollment_and_recovery_codes(user_factory):
    user = user_factory("enroll@example.test")
    client = Client(enforce_csrf_checks=True)
    cache.clear()
    assert (
        post(
            client,
            "/_allauth/browser/v1/auth/login",
            {"email": user.email, "password": "Synthetic-secure-password-493!"},
        ).status_code
        == 200
    )
    response = client.get("/_allauth/browser/v1/account/authenticators/totp")
    assert response.status_code == 404
    secret = response.json()["meta"]["secret"]
    code = format_hotp_value(hotp_value(secret, int(time.time()) // 30))
    response = post(client, "/_allauth/browser/v1/account/authenticators/totp", {"code": code})
    assert response.status_code == 200
    assert mfa_enabled(user)
    authenticator = Authenticator.objects.get(user=user, type=Authenticator.Type.TOTP)
    assert authenticator.data["secret"] != secret
    assert MFAAdapter().decrypt(authenticator.data["secret"]) == secret
    assert (
        client.get("/_allauth/browser/v1/account/authenticators/recovery-codes").status_code == 403
    )
    assert (
        post(client, "/_allauth/browser/v1/auth/2fa/reauthenticate", {"code": code}).status_code
        == 200
    )
    response = client.get("/_allauth/browser/v1/account/authenticators/recovery-codes")
    assert response.status_code == 200
    codes = response.json()["data"]["unused_codes"]
    assert codes
    logout = client.delete("/_allauth/browser/v1/auth/session", **csrf(client))
    assert logout.status_code in {200, 401}
    assert (
        post(
            client,
            "/_allauth/browser/v1/auth/login",
            {"email": user.email, "password": "Synthetic-secure-password-493!"},
        ).status_code
        == 401
    )
    assert (
        post(client, "/_allauth/browser/v1/auth/2fa/authenticate", {"code": codes[0]}).status_code
        == 200
    )


def test_session_listing_and_remote_revocation(user_factory):
    user = user_factory("sessions@example.test")
    first = Client(enforce_csrf_checks=True)
    second = Client(enforce_csrf_checks=True)
    for client in (first, second):
        assert (
            post(
                client,
                "/_allauth/browser/v1/auth/login",
                {"email": user.email, "password": "Synthetic-secure-password-493!"},
            ).status_code
            == 200
        )
    response = first.get("/_allauth/browser/v1/auth/sessions")
    assert response.status_code == 200
    sessions = response.json()["data"]
    remote = next(session for session in sessions if not session["is_current"])
    response = first.delete(
        "/_allauth/browser/v1/auth/sessions",
        {"sessions": [remote["id"]]},
        content_type="application/json",
        **csrf(first),
    )
    assert response.status_code == 200
    assert second.get("/api/v1/me/").status_code == 401


def test_auth_limiter_failure_and_shared_atomic_count(user_factory):
    client = Client(enforce_csrf_checks=True)
    headers = csrf(client)
    with patch(
        "accounts.middleware.limiter_client", side_effect=redis.ConnectionError("synthetic")
    ):
        response = post(
            client,
            "/_allauth/browser/v1/auth/login",
            {"email": "synthetic@example.test", "password": "irrelevant"},
            headers,
        )
    assert response.status_code == 503
    assert response.json()["code"] == "auth_unavailable"
    with patch("accounts.middleware.limiter_client") as fake:
        fake.return_value.eval.return_value = 31
        assert post(client, "/_allauth/browser/v1/auth/login", {}, headers).status_code == 429


def test_cookie_key_rotation_preserves_encrypted_mfa(settings):
    adapter = MFAAdapter()
    encrypted = adapter.encrypt("synthetic-private-totp-secret")
    settings.SECRET_KEY = "rotated-cookie-secret"
    assert adapter.decrypt(encrypted) == "synthetic-private-totp-secret"


def test_operator_enrollment_gate_and_required_authenticator_cannot_be_removed(user_factory):
    operator = user_factory("operator-gate@example.test", staff=True)
    client = Client(enforce_csrf_checks=True)
    client.force_login(operator)
    profile = client.get("/api/v1/me/").json()
    assert profile["mfa_required"] is True
    assert profile["mfa_enabled"] is False
    assert client.get("/api/v1/workspaces/").status_code == 403
    Authenticator.objects.create(
        user=operator,
        type=Authenticator.Type.TOTP,
        data={"secret": MFAAdapter().encrypt("JBSWY3DPEHPK3PXP")},
    )
    assert client.get("/api/v1/workspaces/").status_code == 403
    assert client.get("/api/v1/me/").json()["mfa_authenticated"] is False
    code = format_hotp_value(hotp_value("JBSWY3DPEHPK3PXP", int(time.time()) // 30))
    assert (
        post(client, "/_allauth/browser/v1/auth/2fa/reauthenticate", {"code": code}).status_code
        == 200
    )
    assert client.get("/api/v1/workspaces/").status_code == 200
    response = client.delete("/_allauth/browser/v1/account/authenticators/totp", **csrf(client))
    assert response.status_code == 403
    assert mfa_enabled(operator)


def test_real_enrollment_does_not_upgrade_old_password_session(user_factory):
    user = user_factory("old-factor-session@example.test")
    old, enrolling = Client(enforce_csrf_checks=True), Client(enforce_csrf_checks=True)
    for client in (old, enrolling):
        assert (
            post(
                client,
                "/_allauth/browser/v1/auth/login",
                {"email": user.email, "password": "Synthetic-secure-password-493!"},
            ).status_code
            == 200
        )
    setup = enrolling.get("/_allauth/browser/v1/account/authenticators/totp")
    assert setup.status_code == 404
    key = setup.json()["meta"]["secret"]
    code = format_hotp_value(hotp_value(key, int(time.time()) // 30))
    assert (
        post(
            enrolling, "/_allauth/browser/v1/account/authenticators/totp", {"code": code}
        ).status_code
        == 200
    )
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    assert [record["method"] for record in old.session["account_authentication_methods"]] == [
        "password"
    ]
    assert old.get("/api/v1/workspaces/").status_code == 403
    assert old.get("/api/v1/me/").json()["mfa_authenticated"] is False
    assert old.get("/_allauth/browser/v1/account/authenticators/recovery-codes").status_code == 403
    assert (
        post(old, "/_allauth/browser/v1/account/authenticators/recovery-codes", {}).status_code
        == 403
    )
    assert (
        post(old, "/_allauth/browser/v1/auth/2fa/reauthenticate", {"code": code}).status_code == 200
    )
    assert old.get("/api/v1/me/").json()["mfa_authenticated"] is True
    assert old.get("/api/v1/workspaces/").status_code == 200


def test_recent_password_does_not_refresh_factor_proof_for_credentials(owner):
    client = Client(enforce_csrf_checks=True)
    client.force_login(owner)
    session = client.session
    session["account_authentication_methods"] = [
        {"method": "mfa", "at": time.time() - 301, "authenticator_type": "totp"},
        {"method": "password", "at": time.time()},
    ]
    session.save()
    assert (
        client.get("/_allauth/browser/v1/account/authenticators/recovery-codes").status_code == 403
    )
    assert (
        post(client, "/_allauth/browser/v1/account/authenticators/recovery-codes", {}).status_code
        == 403
    )


def test_new_organization_requires_factor_proof_not_only_enrollment(user_factory):
    user = user_factory("new-owner-proof@example.test", mfa=True)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    assert (
        post(client, "/api/v1/workspaces/", {"name": "Synthetic proof workspace"}).status_code
        == 403
    )
    code = format_hotp_value(hotp_value("JBSWY3DPEHPK3PXP", int(time.time()) // 30))
    assert (
        post(client, "/_allauth/browser/v1/auth/2fa/reauthenticate", {"code": code}).status_code
        == 200
    )
    assert (
        post(client, "/api/v1/workspaces/", {"name": "Synthetic proof workspace"}).status_code
        == 201
    )


def test_private_cache_headers(api):
    response = api.get("/api/v1/me/")
    assert response["Cache-Control"] == "private, no-store"
    assert "Cookie" in response["Vary"]


def test_auth_limit_shared_across_workers_with_real_valkey():
    from concurrent.futures import ThreadPoolExecutor

    from django.http import HttpResponse
    from django.test import RequestFactory

    from accounts.middleware import AuthLimiterMiddleware

    workers = [AuthLimiterMiddleware(lambda _: HttpResponse(status=200)) for _ in range(2)]

    def attempt(index):
        request = RequestFactory().post("/_allauth/browser/v1/auth/login", {})
        return workers[index % 2](request).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(attempt, range(40)))
    assert responses.count(200) == 30
    assert responses.count(429) == 10
