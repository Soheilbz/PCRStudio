from django.urls import include, path
from drf_spectacular.views import SpectacularJSONAPIView

from accounts.views import CSRFView, MeView
from config.views import liveness, readiness
from projects.views import (
    ProjectAccessDetailView,
    ProjectAccessView,
    ProjectDetailView,
    ProjectListView,
    ProjectRecoveryView,
)
from workspaces.views import (
    InvitationAcceptView,
    InvitationDetailView,
    InvitationListView,
    MemberDetailView,
    MemberListView,
    OrphanedProjectListView,
    WorkspaceLeaveView,
    WorkspaceListView,
)

urlpatterns = [
    path("health/live/", liveness),
    path("health/ready/", readiness),
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path("api/v1/csrf/", CSRFView.as_view()),
    path("api/v1/me/", MeView.as_view()),
    path("api/v1/workspaces/", WorkspaceListView.as_view()),
    path("api/v1/workspaces/<uuid:workspace_id>/members/", MemberListView.as_view()),
    path(
        "api/v1/workspaces/<uuid:workspace_id>/members/<uuid:membership_id>/",
        MemberDetailView.as_view(),
    ),
    path("api/v1/workspaces/<uuid:workspace_id>/leave/", WorkspaceLeaveView.as_view()),
    path("api/v1/workspaces/<uuid:workspace_id>/invitations/", InvitationListView.as_view()),
    path(
        "api/v1/workspaces/<uuid:workspace_id>/invitations/<uuid:invitation_id>/",
        InvitationDetailView.as_view(),
    ),
    path("api/v1/invitations/accept/", InvitationAcceptView.as_view()),
    path("api/v1/workspaces/<uuid:workspace_id>/projects/", ProjectListView.as_view()),
    path(
        "api/v1/workspaces/<uuid:workspace_id>/orphaned-projects/",
        OrphanedProjectListView.as_view(),
    ),
    path("api/v1/projects/<uuid:project_id>/", ProjectDetailView.as_view()),
    path("api/v1/projects/<uuid:project_id>/access/", ProjectAccessView.as_view()),
    path(
        "api/v1/projects/<uuid:project_id>/access/<uuid:membership_id>/",
        ProjectAccessDetailView.as_view(),
    ),
    path("api/v1/projects/<uuid:project_id>/recover/", ProjectRecoveryView.as_view()),
    path("api/v1/schema/", SpectacularJSONAPIView.as_view()),
]

handler500 = "config.views.server_error"
