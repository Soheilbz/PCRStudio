import hashlib
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.policy import mfa_enabled
from audit.models import AuditEvent
from projects.models import ProjectGrant
from projects.services import create_project
from workspaces.models import Invitation, Membership
from workspaces.services import accept_invitation, create_invitation, revoke_member

pytestmark = pytest.mark.django_db


def test_invitation_email_boundary_rejected_before_database(api, organization):
    from workspaces.models import Invitation

    email = "a" * 64 + "@" + ".".join(["b" * 63, "c" * 63, "d" * 63, "test"])
    assert len(email) == 261
    response = api.post(
        f"/api/v1/workspaces/{organization.id}/invitations/",
        {"email": email, "role": "member"},
        format="json",
    )
    assert response.status_code == 400
    assert not Invitation.objects.exists()


def make_invitation(owner, organization, target, *, role="member", key="synthetic-invite-key"):
    return Invitation.objects.create(
        workspace=organization,
        inviter=owner.memberships.get(workspace=organization),
        email=target.email,
        role=role,
        token_hash=hashlib.sha256(key.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(days=7),
    )


def test_organization_requires_mfa(api, user_factory):
    ordinary = user_factory("ordinary@example.test")
    api.force_login(ordinary)
    assert api.post("/api/v1/workspaces/", {"name": "Synthetic"}, format="json").status_code == 403
    assert ordinary.memberships.count() == 1


def test_invite_hashed_verified_email_single_use_and_rejoin(api, owner, organization, user_factory):
    user = user_factory("invited@example.test")
    stranger = user_factory("stranger@example.test")
    invite = make_invitation(owner, organization, user)
    api.force_login(stranger)
    assert (
        api.post(
            "/api/v1/invitations/accept/", {"key": "synthetic-invite-key"}, format="json"
        ).status_code
        == 403
    )
    api.force_login(user)
    response = api.post(
        "/api/v1/invitations/accept/", {"key": "synthetic-invite-key"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["role"] == "member"
    assert (
        api.post(
            "/api/v1/invitations/accept/", {"key": "synthetic-invite-key"}, format="json"
        ).status_code
        == 400
    )
    assert invite.token_hash != "synthetic-invite-key"
    member = Membership.objects.get(user=user, workspace=organization, active=True)
    revoke_member(owner, organization.id, member.id)
    invite2 = make_invitation(owner, organization, user, key="fresh-invite-key")
    fresh = accept_invitation(user, "fresh-invite-key")
    assert fresh.id != member.id
    assert Invitation.objects.get(id=invite2.id).accepted_at is not None


def test_expiration_revocation_inviter_current_authority(api, owner, organization, user_factory):
    target = user_factory("expired@example.test")
    invite = make_invitation(owner, organization, target)
    invite.expires_at = timezone.now() - timedelta(seconds=1)
    invite.save()
    api.force_login(target)
    assert (
        api.post(
            "/api/v1/invitations/accept/", {"key": "synthetic-invite-key"}, format="json"
        ).status_code
        == 400
    )
    invite.expires_at = timezone.now() + timedelta(days=7)
    invite.save()
    revoke_member(owner, organization.id, invite.inviter_id)
    assert (
        api.post(
            "/api/v1/invitations/accept/", {"key": "synthetic-invite-key"}, format="json"
        ).status_code
        == 400
    )


def test_invitation_membership_never_implicitly_grants_project(owner, organization, user_factory):
    target = user_factory("membershiponly@example.test")
    p = create_project(owner, organization.id, "Synthetic project")
    make_invitation(owner, organization, target)
    member = accept_invitation(target, "synthetic-invite-key")
    assert not ProjectGrant.objects.filter(project=p, membership=member).exists()


def test_owner_invitation_requires_target_mfa(api, owner, organization, user_factory):
    target = user_factory("new-owner@example.test")
    make_invitation(owner, organization, target, role="owner")
    api.force_login(target)
    assert (
        api.post(
            "/api/v1/invitations/accept/", {"key": "synthetic-invite-key"}, format="json"
        ).status_code
        == 403
    )
    assert not mfa_enabled(target)


def test_owner_handover_preserves_last_owner_and_mfa(api, owner, organization, user_factory):
    target = user_factory("member@example.test", mfa=True)
    membership = Membership.objects.create(user=target, workspace=organization, role="member")
    actor = owner.memberships.get(workspace=organization)
    assert (
        api.patch(
            f"/api/v1/workspaces/{organization.id}/members/{actor.id}/",
            {"role": "member"},
            format="json",
        ).status_code
        == 409
    )
    assert (
        api.patch(
            f"/api/v1/workspaces/{organization.id}/members/{membership.id}/",
            {"role": "owner"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        api.patch(
            f"/api/v1/workspaces/{organization.id}/members/{actor.id}/",
            {"role": "member"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        api.post(f"/api/v1/workspaces/{organization.id}/leave/", {}, format="json").status_code
        == 204
    )
    assert AuditEvent.objects.filter(action="membership.role_changed").count() == 2


def test_invitations_mail_neutral_and_list_no_tokens(
    owner, organization, user_factory, django_capture_on_commit_callbacks, mailoutbox
):
    target = user_factory("recipient@example.test")
    with django_capture_on_commit_callbacks(execute=True):
        invite = create_invitation(owner, organization.id, target.email, "member")
    assert len(mailoutbox) == 1
    assert organization.name not in mailoutbox[0].body
    assert invite.token_hash not in mailoutbox[0].body
    assert (
        invite.expires_at - invite.created_at
    ).days == 6  # Exact seven-day window minus creation delta.


@pytest.mark.django_db(transaction=True)
def test_invitation_smtp_failure_preserves_committed_result(api, owner, organization, monkeypatch):
    from smtplib import SMTPException

    def fail(*args, **kwargs):
        raise SMTPException("synthetic recipient and private SMTP payload")

    monkeypatch.setattr("config.notifications.send_mail", fail)
    response = api.post(
        f"/api/v1/workspaces/{organization.id}/invitations/",
        {"email": "mail-failure@example.test", "role": "member"},
        format="json",
    )
    assert response.status_code == 201
    invitation = Invitation.objects.get(id=response.json()["id"])
    assert invitation.email == "mail-failure@example.test"
    assert AuditEvent.objects.filter(subject_id=invitation.id, action="invitation.created").exists()
