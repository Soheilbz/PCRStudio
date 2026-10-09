import hashlib
import secrets
from datetime import timedelta
from typing import Never

from allauth.account.models import EmailAddress
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.policy import require_mfa
from audit.services import record
from config.errors import DomainError
from config.notifications import notify_on_commit
from workspaces.models import Invitation, Membership, Workspace


def unavailable() -> Never:
    raise DomainError("not_found", "Resource unavailable.", 404)


def current_membership(user, workspace_id):
    membership = (
        Membership.objects.select_related("workspace", "user")
        .filter(user=user, user__is_active=True, workspace_id=workspace_id, active=True)
        .first()
    )
    if not membership:
        unavailable()
    return membership


def workspace_lock(workspace_id):
    workspace = Workspace.objects.select_for_update().filter(id=workspace_id).first()
    if not workspace:
        unavailable()
    return workspace


def require_admin(user, workspace_id):
    actor = current_membership(user, workspace_id)
    if actor.workspace.kind != Workspace.Kind.ORGANIZATION or actor.role != Membership.Role.OWNER:
        unavailable()
    require_mfa(user)
    return actor


@transaction.atomic
def ensure_personal_workspace(user):
    workspace, _ = Workspace.objects.get_or_create(
        personal_user=user, defaults={"kind": Workspace.Kind.PERSONAL, "name": "Personal workspace"}
    )
    Membership.objects.get_or_create(
        workspace=workspace, user=user, active=True, defaults={"role": Membership.Role.OWNER}
    )
    return workspace


@transaction.atomic
def create_organization(user, name):
    require_mfa(user)
    workspace = Workspace.objects.create(name=name, kind=Workspace.Kind.ORGANIZATION)
    membership = Membership.objects.create(
        workspace=workspace, user=user, role=Membership.Role.OWNER
    )
    record(user, workspace, workspace.id, "workspace.created")
    return membership


@transaction.atomic
def revoke_member(user, workspace_id, membership_id, *, voluntary=False):
    workspace = workspace_lock(workspace_id)
    actor = (
        current_membership(user, workspace.id) if voluntary else require_admin(user, workspace.id)
    )
    target = (
        Membership.objects.select_for_update()
        .filter(id=membership_id, workspace=workspace, active=True)
        .first()
    )
    if not target:
        unavailable()
    if workspace.kind == Workspace.Kind.PERSONAL:
        raise DomainError("personal_workspace", "Personal membership cannot be removed.")
    if voluntary:
        if actor.id != target.id:
            unavailable()
        # Voluntary exit can never strand workspace or project administration.
        owns_projects = target.owned_projects.exists()
        last_owner = (
            target.role == Membership.Role.OWNER
            and not workspace.memberships.filter(
                active=True, user__is_active=True, role=Membership.Role.OWNER
            )
            .exclude(id=target.id)
            .exists()
        )
        if owns_projects or last_owner:
            raise DomainError("handover_required", "Transfer ownership before leaving.", 409)
    target.active = False
    target.revoked_at = timezone.now()
    target.save(update_fields=["active", "revoked_at"])
    record(user, workspace, target.id, "membership.left" if voluntary else "membership.revoked")


@transaction.atomic
def create_invitation(user, workspace_id, email, role):
    workspace = workspace_lock(workspace_id)
    actor = require_admin(user, workspace.id)
    if Membership.objects.filter(
        workspace=workspace, active=True, user__email__iexact=email
    ).exists():
        raise DomainError("already_member", "This account already belongs to the workspace.", 409)
    key = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        workspace=workspace,
        inviter=actor,
        email=email.lower(),
        role=role,
        token_hash=hashlib.sha256(key.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(days=7),
    )
    record(user, workspace, invitation.id, "invitation.created", role=role)
    notify_on_commit(
        "workspace_invitation",
        "PCRStudio invitation",
        "A workspace invitation is ready.\n"
        f"Accept it at {settings.FRONTEND_URL}/invitations/accept?key={key}\n"
        "Sign in with this verified email address. This link expires in seven days.",
        email,
    )
    return invitation


@transaction.atomic
def accept_invitation(user, key):
    token_hash = hashlib.sha256(key.encode()).hexdigest()
    invitation = Invitation.objects.filter(token_hash=token_hash).first()
    if not invitation:
        unavailable()
    workspace = workspace_lock(invitation.workspace_id)
    invitation = Invitation.objects.select_for_update().get(id=invitation.id)
    if invitation.accepted_at or invitation.revoked_at or invitation.expires_at <= timezone.now():
        raise DomainError("invitation_invalid", "Invitation is expired or already used.", 400)
    if not EmailAddress.objects.filter(
        user=user, verified=True, email__iexact=invitation.email
    ).exists():
        raise DomainError(
            "invitation_email_mismatch", "Use the verified email addressed by this invitation.", 403
        )
    # Current inviter membership and owner authority are always authoritative.
    inviter = invitation.inviter
    if not inviter.active or not inviter.user.is_active or inviter.role != Membership.Role.OWNER:
        raise DomainError("invitation_invalid", "Invitation authority is no longer active.", 400)
    if invitation.role == Membership.Role.OWNER:
        require_mfa(user)
    if Membership.objects.filter(workspace=workspace, user=user, active=True).exists():
        raise DomainError("already_member", "This account already belongs to the workspace.", 409)
    membership = Membership.objects.create(workspace=workspace, user=user, role=invitation.role)
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    record(
        user,
        workspace,
        invitation.id,
        "invitation.accepted",
        target_membership_id=str(membership.id),
    )
    return membership


@transaction.atomic
def revoke_invitation(user, workspace_id, invitation_id):
    workspace_lock(workspace_id)
    require_admin(user, workspace_id)
    invitation = (
        Invitation.objects.select_for_update()
        .filter(id=invitation_id, workspace_id=workspace_id)
        .first()
    )
    if not invitation:
        unavailable()
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["revoked_at"])
    record(user, invitation.workspace, invitation.id, "invitation.revoked")


@transaction.atomic
def change_member_role(user, workspace_id, membership_id, role):
    workspace = workspace_lock(workspace_id)
    require_admin(user, workspace.id)
    target = (
        Membership.objects.select_for_update()
        .select_related("user")
        .filter(id=membership_id, workspace=workspace, active=True, user__is_active=True)
        .first()
    )
    if not target:
        unavailable()
    if role == Membership.Role.OWNER:
        require_mfa(target.user)
    elif (
        target.role == Membership.Role.OWNER
        and not workspace.memberships.filter(
            active=True, user__is_active=True, role=Membership.Role.OWNER
        )
        .exclude(id=target.id)
        .exists()
    ):
        raise DomainError(
            "handover_required", "Appoint another workspace owner before changing this role.", 409
        )
    target.role = role
    target.save(update_fields=["role"])
    record(user, workspace, target.id, "membership.role_changed", role=role)
    return target
