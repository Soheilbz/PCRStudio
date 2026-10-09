from django.db import transaction
from django.db.models import Case, CharField, F, OuterRef, Q, Subquery, Value, When

from accounts.policy import require_recent_mfa
from audit.services import record
from config.errors import DomainError
from config.notifications import notify_on_commit
from projects.models import Project, ProjectGrant
from workspaces.models import Membership, Workspace
from workspaces.services import current_membership, require_admin, unavailable, workspace_lock


def accessible_projects(user, workspace_id=None):
    memberships = Membership.objects.filter(user=user, user__is_active=True, active=True)
    projects = (
        Project.objects.filter(workspace_id__in=memberships.values("workspace_id"))
        .filter(
            (
                Q(owner_membership_id__in=memberships.values("id"))
                & Q(owner_membership__workspace_id=F("workspace_id"))
            )
            | (
                Q(grants__membership_id__in=memberships.values("id"))
                & Q(grants__membership__workspace_id=F("workspace_id"))
            )
        )
        .distinct()
    )
    if workspace_id:
        projects = projects.filter(workspace_id=workspace_id)
    grant_role = ProjectGrant.objects.filter(
        project_id=OuterRef("pk"),
        membership_id__in=memberships.values("id"),
        membership__workspace_id=OuterRef("workspace_id"),
    ).values("role")[:1]
    return projects.select_related("owner_membership__user").annotate(
        _actor_role=Case(
            When(
                Q(owner_membership_id__in=memberships.values("id"))
                & Q(owner_membership__workspace_id=F("workspace_id")),
                then=Value("owner"),
            ),
            default=Subquery(grant_role),
            output_field=CharField(),
        )
    )


def project_role(user, project):
    actor = current_membership(user, project.workspace_id)
    if project.owner_membership_id == actor.id:
        return "owner"
    return (
        ProjectGrant.objects.filter(project=project, membership=actor)
        .values_list("role", flat=True)
        .first()
    )


def orphaned(project):
    return not (project.owner_membership.active and project.owner_membership.user.is_active)


def readable_project(user, project_id):
    project = accessible_projects(user).filter(id=project_id).first()
    if not project:
        unavailable()
    return project


def locked_project(user, project_id, *, recovery=False):
    project = Project.objects.filter(id=project_id).first()
    if not project:
        unavailable()
    workspace_lock(project.workspace_id)
    project = (
        Project.objects.select_for_update()
        .select_related("owner_membership__user", "workspace")
        .get(id=project_id)
    )
    if not recovery and not project_role(user, project):
        unavailable()
    return project


def check_version(project, version):
    if project.version != version:
        raise DomainError(
            "version_conflict", "This project changed. Reload before applying your edits.", 409
        )


def require_mutation(user, project, *, owner_only=False):
    role = project_role(user, project)
    if role not in ({"owner"} if owner_only else {"owner", "editor"}):
        unavailable()
    if orphaned(project):
        raise DomainError(
            "ownerless_project", "Project administration must be recovered before changes.", 409
        )


def bump(project):
    project.version += 1
    project.save()


@transaction.atomic
def create_project(user, workspace_id, name, description=""):
    workspace = workspace_lock(workspace_id)
    actor = current_membership(user, workspace.id)
    project = Project.objects.create(
        workspace=workspace, owner_membership=actor, name=name, description=description
    )
    record(user, workspace, project.id, "project.created", version=project.version)
    return project


@transaction.atomic
def update_project(user, project_id, version, fields):
    project = locked_project(user, project_id)
    require_mutation(user, project, owner_only="archived" in fields)
    check_version(project, version)
    if project.archived and fields.get("archived", True):
        raise DomainError("project_archived", "Restore this project before editing.", 409)
    for field in ("name", "description", "archived"):
        if field in fields:
            setattr(project, field, fields[field])
    bump(project)
    record(user, project.workspace, project.id, "project.updated", version=project.version)
    return project


@transaction.atomic
def grant_access(user, project_id, membership_id, role, version):
    project = locked_project(user, project_id)
    require_mutation(user, project, owner_only=True)
    check_version(project, version)
    target = Membership.objects.filter(
        id=membership_id, workspace=project.workspace, active=True, user__is_active=True
    ).first()
    if not target:
        unavailable()
    if role == "owner":
        previous = project.owner_membership
        project.owner_membership = target
        ProjectGrant.objects.filter(project=project, membership=target).delete()
        if previous.id != target.id:
            ProjectGrant.objects.update_or_create(
                project=project, membership=previous, defaults={"role": "editor"}
            )
    else:
        if target.id == project.owner_membership_id:
            raise DomainError(
                "owner_handover_required",
                "Transfer ownership before changing the owner's access.",
                409,
            )
        ProjectGrant.objects.update_or_create(
            project=project, membership=target, defaults={"role": role}
        )
    bump(project)
    record(
        user,
        project.workspace,
        project.id,
        "project.access_changed",
        version=project.version,
        target_membership_id=str(target.id),
        role=role,
    )
    return project


@transaction.atomic
def revoke_access(user, project_id, membership_id, version):
    project = locked_project(user, project_id)
    require_mutation(user, project, owner_only=True)
    check_version(project, version)
    if str(project.owner_membership_id) == str(membership_id):
        raise DomainError(
            "owner_handover_required", "Transfer ownership before removing the owner.", 409
        )
    if not ProjectGrant.objects.filter(project=project, membership_id=membership_id).delete()[0]:
        unavailable()
    bump(project)
    record(
        user,
        project.workspace,
        project.id,
        "project.access_revoked",
        version=project.version,
        target_membership_id=str(membership_id),
    )
    return project


@transaction.atomic
def recover_project(request, project_id, membership_id, reason, version):
    if reason not in {"owner_removed", "owner_suspended", "security_revocation"}:
        raise DomainError("invalid_reason", "Choose an operational recovery reason.")
    project = locked_project(request.user, project_id, recovery=True)
    require_admin(request.user, project.workspace_id)
    require_recent_mfa(request)
    check_version(project, version)
    if project.workspace.kind != Workspace.Kind.ORGANIZATION or not orphaned(project):
        raise DomainError(
            "recovery_unavailable", "This project does not require organization recovery.", 409
        )
    target = (
        Membership.objects.filter(
            id=membership_id, workspace=project.workspace, active=True, user__is_active=True
        )
        .select_related("user")
        .first()
    )
    if not target:
        unavailable()
    project.owner_membership = target
    ProjectGrant.objects.filter(project=project, membership=target).delete()
    bump(project)
    record(
        request.user,
        project.workspace,
        project.id,
        "project.recovered",
        version=project.version,
        reason=reason,
        target_membership_id=str(target.id),
    )
    # Send a neutral notification after recovery and its audit commit.
    notify_on_commit(
        "project_recovery",
        "PCRStudio access administration",
        "Project administration was recovered "
        f"to your workspace membership. Reference: {project.id}. Sign in to review your access.",
        target.user.email,
    )
    return {"id": project.id, "version": project.version}
