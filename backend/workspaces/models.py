import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Workspace(models.Model):
    class Kind(models.TextChoices):
        PERSONAL = "personal"
        ORGANIZATION = "organization"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    personal_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="personal_workspace",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(kind="personal", personal_user__isnull=False)
                    | Q(kind="organization", personal_user__isnull=True)
                ),
                name="workspace_personal_identity",
            )
        ]


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner"
        MEMBER = "member"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships"
    )
    role = models.CharField(max_length=6, choices=Role.choices)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                condition=Q(active=True),
                name="membership_one_active_identity",
            )
        ]
        ordering = ["created_at", "id"]


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name="invitations")
    inviter = models.ForeignKey(Membership, on_delete=models.PROTECT)
    email = models.EmailField()
    role = models.CharField(max_length=6, choices=Membership.Role.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]
