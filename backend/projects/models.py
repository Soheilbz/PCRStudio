import uuid

from django.db import models

from workspaces.models import Membership, Workspace


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name="projects")
    name = models.CharField(max_length=160)
    description = models.TextField(max_length=4000, blank=True)
    owner_membership = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="owned_projects"
    )
    version = models.PositiveIntegerField(default=1)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "id"]


class ProjectGrant(models.Model):
    class Role(models.TextChoices):
        EDITOR = "editor"
        VIEWER = "viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="grants")
    membership = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="project_grants"
    )
    role = models.CharField(max_length=6, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "membership"], name="project_grant_unique")
        ]
