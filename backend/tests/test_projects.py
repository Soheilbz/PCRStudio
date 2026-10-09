import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from django.db import close_old_connections, connections

from audit.models import AuditEvent
from config.errors import DomainError
from projects import services
from projects.models import Project, ProjectGrant
from projects.serializers import ProjectSerializer
from workspaces.models import Membership
from workspaces.services import revoke_member

pytestmark = pytest.mark.django_db


def member(user_factory, organization, email):
    user = user_factory(email)
    return Membership.objects.create(user=user, workspace=organization, role="member")


def project(owner, organization):
    return services.create_project(
        owner, organization.id, "Synthetic private name", "Synthetic description"
    )


def as_user(client, user):
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    # Project-authorization tests use an MFA-authenticated but non-recent actor;
    # recovery tests must separately supply recent proof. Real missing-factor
    # sessions are covered by the allauth regressions in test_auth.py.
    from accounts.policy import mfa_enabled

    if mfa_enabled(user):
        session = client.session
        session["account_authentication_methods"] = [
            {"method": "mfa", "at": time.time() - 600, "authenticator_type": "totp"}
        ]
        session.save()


def test_personal_workspace_exists_once(owner):
    assert owner.personal_workspace.kind == "personal"
    assert owner.memberships.filter(workspace__kind="personal").count() == 1


def test_ungranted_org_owner_and_stranger_cannot_read(api, owner, organization, user_factory):
    creator = member(user_factory, organization, "creator@example.test")
    p = services.create_project(creator.user, organization.id, "Synthetic confidential")
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 404
    assert api.get(f"/api/v1/workspaces/{organization.id}/projects/").json()["results"] == []
    outsider = user_factory("outsider@example.test")
    as_user(api, outsider)
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 404
    assert api.get(f"/api/v1/workspaces/{organization.id}/members/").status_code == 404


def test_viewer_editor_owner_permissions(api, owner, organization, user_factory):
    p = project(owner, organization)
    viewer = member(user_factory, organization, "viewer@example.test")
    editor = member(user_factory, organization, "editor@example.test")
    services.grant_access(owner, p.id, viewer.id, "viewer", 1)
    services.grant_access(owner, p.id, editor.id, "editor", 2)
    as_user(api, viewer.user)
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 200
    assert (
        api.patch(
            f"/api/v1/projects/{p.id}/", {"version": 3, "name": "Forbidden"}, format="json"
        ).status_code
        == 404
    )
    assert api.get(f"/api/v1/projects/{p.id}/access/").status_code == 404
    as_user(api, editor.user)
    response = api.patch(
        f"/api/v1/projects/{p.id}/", {"version": 3, "name": "Synthetic revised"}, format="json"
    )
    assert response.status_code == 200
    assert (
        api.patch(
            f"/api/v1/projects/{p.id}/", {"version": 4, "archived": True}, format="json"
        ).status_code
        == 404
    )
    assert (
        api.post(
            f"/api/v1/projects/{p.id}/access/",
            {"version": 4, "membership_id": str(viewer.id), "role": "editor"},
            format="json",
        ).status_code
        == 404
    )
    as_user(api, owner)
    assert (
        api.patch(
            f"/api/v1/projects/{p.id}/", {"version": 4, "archived": True}, format="json"
        ).status_code
        == 200
    )
    assert (
        api.patch(
            f"/api/v1/projects/{p.id}/", {"version": 5, "name": "Blocked"}, format="json"
        ).status_code
        == 409
    )
    assert (
        api.patch(
            f"/api/v1/projects/{p.id}/", {"version": 5, "archived": False}, format="json"
        ).status_code
        == 200
    )


def test_cross_workspace_grant_and_move_are_denied(api, owner, organization, user_factory):
    p = project(owner, organization)
    outsider = user_factory("different@example.test")
    target = outsider.memberships.get(workspace__kind="personal")
    assert (
        api.post(
            f"/api/v1/projects/{p.id}/access/",
            {"membership_id": str(target.id), "role": "viewer", "version": 1},
            format="json",
        ).status_code
        == 404
    )
    # Immutable tenant fields cannot be included in an update.
    response = api.patch(
        f"/api/v1/projects/{p.id}/",
        {"workspace_id": str(target.workspace_id), "version": 1},
        format="json",
    )
    assert response.status_code == 400
    p.refresh_from_db()
    assert p.workspace_id == organization.id


def test_force_removal_immediate_old_grants_never_reactivate(
    api, owner, organization, user_factory
):
    p = project(owner, organization)
    target = member(user_factory, organization, "removed@example.test")
    services.grant_access(owner, p.id, target.id, "editor", 1)
    revoke_member(owner, organization.id, target.id)
    as_user(api, target.user)
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 404
    assert (
        api.patch(
            f"/api/v1/projects/{p.id}/", {"version": 2, "name": "Denied"}, format="json"
        ).status_code
        == 404
    )
    fresh = Membership.objects.create(user=target.user, workspace=organization, role="member")
    assert fresh.id != target.id
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 404
    assert not services.accessible_projects(target.user).exists()


def test_orphan_read_only_recovery_no_actor_content_grant(api, owner, organization, user_factory):
    creator = member(user_factory, organization, "project-owner@example.test")
    viewer = member(user_factory, organization, "remaining@example.test")
    p = services.create_project(creator.user, organization.id, "Synthetic confidential")
    services.grant_access(creator.user, p.id, viewer.id, "editor", 1)
    revoke_member(owner, organization.id, creator.id)
    as_user(api, viewer.user)
    assert api.get(f"/api/v1/projects/{p.id}/").json()["orphaned"] is True
    assert (
        api.patch(
            f"/api/v1/projects/{p.id}/", {"version": 2, "name": "Denied"}, format="json"
        ).status_code
        == 409
    )
    as_user(api, owner)
    body = {"membership_id": str(viewer.id), "reason": "owner_removed", "version": 2}
    assert api.post(f"/api/v1/projects/{p.id}/recover/", body, format="json").status_code == 403
    session = api.session
    import time

    session["account_authentication_methods"] = [{"method": "mfa", "at": time.time()}]
    session.save()
    response = api.post(f"/api/v1/projects/{p.id}/recover/", body, format="json")
    assert response.status_code == 200
    assert set(response.json()) == {"id", "version"}
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 404
    event = AuditEvent.objects.get(action="project.recovered")
    assert event.metadata["reason"] == "owner_removed"
    assert not ProjectGrant.objects.filter(project=p, membership__user=owner).exists()


def test_orphan_inventory_is_neutral(api, owner, organization, user_factory):
    creator = member(user_factory, organization, "orphan@example.test")
    p = services.create_project(creator.user, organization.id, "DO-NOT-DISCLOSE", "DO-NOT-DISCLOSE")
    revoke_member(owner, organization.id, creator.id)
    response = api.get(f"/api/v1/workspaces/{organization.id}/orphaned-projects/")
    assert response.json()["results"] == [{"id": str(p.id), "version": 1}]
    assert "DO-NOT-DISCLOSE" not in response.content.decode()


def test_project_handover_and_voluntary_leave(api, owner, organization, user_factory):
    target = member(user_factory, organization, "handover@example.test")
    p = project(owner, organization)
    assert (
        api.post(f"/api/v1/workspaces/{organization.id}/leave/", {}, format="json").status_code
        == 409
    )
    services.grant_access(owner, p.id, target.id, "owner", 1)
    p.refresh_from_db()
    assert p.owner_membership_id == target.id
    assert ProjectGrant.objects.get(project=p, membership__user=owner).role == "editor"
    # Forced revocation still succeeds even for the final organization owner.
    response = api.delete(
        f"/api/v1/workspaces/{organization.id}/members/{owner.memberships.get(workspace=organization).id}/"
    )
    assert response.status_code == 204
    assert api.get(f"/api/v1/workspaces/{organization.id}/members/").status_code == 404


def test_audit_contains_no_content_and_is_transactional(owner, organization, monkeypatch):
    p = project(owner, organization)
    assert "Synthetic" not in json.dumps(list(AuditEvent.objects.values("metadata")))
    import projects.services as module

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(module, "record", fail)
    with pytest.raises(RuntimeError):
        services.update_project(owner, p.id, 1, {"name": "Must rollback"})
    p.refresh_from_db()
    assert p.name == "Synthetic private name"
    assert p.version == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_stale_edits_commit_exactly_once(owner, organization):
    p = project(owner, organization)
    start = Barrier(2)

    def update(name):
        close_old_connections()
        start.wait(timeout=5)
        try:
            services.update_project(owner, p.id, 1, {"name": name})
            return "ok"
        except DomainError as error:
            return error.get_codes()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(update, ["Synthetic A", "Synthetic B"]))
    assert sorted(outcomes) == ["ok", "version_conflict"]
    p.refresh_from_db()
    assert p.version == 2
    assert AuditEvent.objects.filter(subject_id=p.id, action="project.updated").count() == 1


@pytest.mark.django_db(transaction=True)
def test_revocation_wins_before_waiting_mutation(owner, organization, user_factory):
    from threading import Event

    from django.db import transaction

    p = project(owner, organization)
    target = member(user_factory, organization, "race-editor@example.test")
    services.grant_access(owner, p.id, target.id, "editor", 1)
    revoked = Event()
    writer_started = Event()
    release = Event()

    def remove():
        close_old_connections()
        try:
            with transaction.atomic():
                revoke_member(owner, organization.id, target.id)
                revoked.set()
                assert release.wait(timeout=10)
            return "revoked"
        finally:
            connections.close_all()

    def write():
        close_old_connections()
        try:
            writer_started.set()
            services.update_project(target.user, p.id, 2, {"name": "Forbidden stale access"})
            return "changed"
        except DomainError as error:
            return error.get_codes()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        removal = pool.submit(remove)
        assert revoked.wait(timeout=10)
        writer = pool.submit(write)
        assert writer_started.wait(timeout=10)
        release.set()
        assert removal.result(timeout=10) == "revoked"
        assert writer.result(timeout=10) == "not_found"
    p.refresh_from_db()
    assert p.version == 2
    assert p.name == "Synthetic private name"


def test_staff_is_not_a_project_grant(api, owner, organization, user_factory):
    p = project(owner, organization)
    operator = user_factory("operator@example.test", mfa=True, staff=True)
    as_user(api, operator)
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 404


def test_suspending_owner_preserves_read_only_records(api, owner, organization, user_factory):
    p = project(owner, organization)
    reader = member(user_factory, organization, "suspension-reader@example.test")
    services.grant_access(owner, p.id, reader.id, "editor", 1)
    owner.is_active = False
    owner.save(update_fields=["is_active"])
    as_user(api, reader.user)
    response = api.get(f"/api/v1/projects/{p.id}/")
    assert response.status_code == 200
    assert response.json()["orphaned"] is True
    assert (
        api.patch(
            f"/api/v1/projects/{p.id}/", {"version": 2, "name": "Denied"}, format="json"
        ).status_code
        == 409
    )
    assert (
        api.post(
            f"/api/v1/workspaces/{organization.id}/invitations/",
            {"email": "other@example.test"},
            format="json",
        ).status_code
        == 404
    )
    assert Project.objects.filter(id=p.id).exists()


def test_database_guards_irrevocable_identity_and_immutable_tenant(
    owner, organization, user_factory
):
    from django.db import IntegrityError, transaction

    p = project(owner, organization)
    target = member(user_factory, organization, "guard@example.test")
    revoke_member(owner, organization.id, target.id)
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.filter(id=target.id).update(active=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        Project.objects.filter(id=p.id).update(workspace=owner.personal_workspace)


def test_full_project_page_roles_serialize_in_one_query(
    owner, organization, user_factory, django_assert_num_queries
):
    reader = member(user_factory, organization, "page-reader@example.test")
    own = services.create_project(reader.user, organization.id, "Synthetic owned project")
    projects = Project.objects.bulk_create(
        [
            Project(
                workspace=organization,
                owner_membership=owner.memberships.get(workspace=organization),
                name=f"Synthetic shared project {index}",
            )
            for index in range(29)
        ]
    )
    expected = {str(own.id): "owner"}
    for index, item in enumerate(projects):
        role = "viewer" if index % 2 else "editor"
        ProjectGrant.objects.create(project=item, membership=reader, role=role)
        expected[str(item.id)] = role
    # Serializing roles and owner state must not issue a query per project.
    with django_assert_num_queries(1):
        data = ProjectSerializer(
            services.accessible_projects(reader.user, organization.id),
            many=True,
            context={"request": SimpleNamespace(user=reader.user)},
        ).data
    assert len(data) == 30
    assert {item["id"]: item["role"] for item in data} == expected


def test_delete_project_access_requires_current_query_version(
    api, owner, organization, user_factory
):
    p = project(owner, organization)
    target = member(user_factory, organization, "revoked-grant@example.test")
    services.grant_access(owner, p.id, target.id, "viewer", 1)
    path = f"/api/v1/projects/{p.id}/access/{target.id}/"
    assert api.delete(path).status_code == 400
    assert api.delete(f"{path}?version=1").status_code == 409
    assert ProjectGrant.objects.filter(project=p, membership=target).exists()
    response = api.delete(f"{path}?version=2")
    assert response.status_code == 200
    assert response.json()["version"] == 3
    as_user(api, target.user)
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_recovery_smtp_failure_preserves_committed_result(
    api, owner, organization, user_factory, monkeypatch
):
    import time
    from smtplib import SMTPException

    creator = member(user_factory, organization, "mail-owner@example.test")
    target = member(user_factory, organization, "mail-recovery@example.test")
    p = services.create_project(creator.user, organization.id, "Synthetic private name")
    revoke_member(owner, organization.id, creator.id)
    session = api.session
    session["account_authentication_methods"] = [{"method": "mfa", "at": time.time()}]
    session.save()

    def fail(*args, **kwargs):
        raise SMTPException("synthetic recipient and private SMTP payload")

    monkeypatch.setattr("config.notifications.send_mail", fail)
    response = api.post(
        f"/api/v1/projects/{p.id}/recover/",
        {"membership_id": str(target.id), "reason": "owner_removed", "version": 1},
        format="json",
    )
    assert response.status_code == 200
    assert response.json() == {"id": str(p.id), "version": 2}
    p.refresh_from_db()
    assert p.owner_membership_id == target.id
    assert AuditEvent.objects.filter(subject_id=p.id, action="project.recovered").count() == 1
    assert api.get(f"/api/v1/projects/{p.id}/").status_code == 404


@pytest.mark.parametrize("authentication_age", [301, -30])
def test_recovery_rejects_expired_or_future_mfa_authentication(
    authentication_age, api, owner, organization, user_factory
):
    import time

    creator = member(user_factory, organization, "stale-auth-owner@example.test")
    target = member(user_factory, organization, "stale-auth-target@example.test")
    p = services.create_project(creator.user, organization.id, "Synthetic private name")
    revoke_member(owner, organization.id, creator.id)
    session = api.session
    session["account_authentication_methods"] = [
        {"method": "mfa", "at": time.time() - authentication_age}
    ]
    session.save()
    response = api.post(
        f"/api/v1/projects/{p.id}/recover/",
        {"membership_id": str(target.id), "reason": "owner_removed", "version": 1},
        format="json",
    )
    assert response.status_code == 403
    expected = (
        "mfa_authentication_required" if authentication_age < 0 else "reauthentication_required"
    )
    assert response.json()["code"] == expected
    p.refresh_from_db()
    assert p.owner_membership_id == creator.id
    assert p.version == 1
    assert not AuditEvent.objects.filter(subject_id=p.id, action="project.recovered").exists()
