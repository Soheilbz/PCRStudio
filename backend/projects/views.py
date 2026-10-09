from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from projects import services
from projects.models import ProjectGrant
from projects.serializers import (
    OrphanedProjectSerializer,
    ProjectAccessCreateSerializer,
    ProjectAccessSerializer,
    ProjectCreateSerializer,
    ProjectRecoverySerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
    VersionSerializer,
)
from workspaces.services import current_membership


class ProjectListView(GenericAPIView):
    serializer_class = ProjectSerializer

    @extend_schema(responses=ProjectSerializer(many=True))
    def get(self, request, workspace_id):
        current_membership(request.user, workspace_id)
        projects = services.accessible_projects(request.user, workspace_id)
        return self.get_paginated_response(
            self.get_serializer(self.paginate_queryset(projects), many=True).data
        )

    @extend_schema(request=ProjectCreateSerializer, responses={201: ProjectSerializer})
    def post(self, request, workspace_id):
        data = ProjectCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        project = services.create_project(request.user, workspace_id, **data.validated_data)
        return Response(self.get_serializer(project).data, status=201)


class ProjectDetailView(GenericAPIView):
    serializer_class = ProjectSerializer

    def get(self, request, project_id):
        return Response(
            self.get_serializer(services.readable_project(request.user, project_id)).data
        )

    @extend_schema(request=ProjectUpdateSerializer, responses=ProjectSerializer)
    def patch(self, request, project_id):
        data = ProjectUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = dict(data.validated_data)
        project = services.update_project(request.user, project_id, fields.pop("version"), fields)
        return Response(self.get_serializer(project).data)


class ProjectAccessView(GenericAPIView):
    serializer_class = ProjectAccessSerializer
    pagination_class = None

    @extend_schema(responses=ProjectAccessSerializer(many=True))
    def get(self, request, project_id):
        project = services.readable_project(request.user, project_id)
        # Access management contains member emails and is restricted to project owner.
        if services.project_role(request.user, project) != "owner":
            from workspaces.services import unavailable

            unavailable()
        entries = [
            {
                "membership_id": project.owner_membership_id,
                "email": project.owner_membership.user.email,
                "role": "owner",
            }
        ]
        entries.extend(
            {
                "membership_id": grant.membership_id,
                "email": grant.membership.user.email,
                "role": grant.role,
            }
            for grant in ProjectGrant.objects.filter(
                project=project, membership__active=True, membership__user__is_active=True
            ).select_related("membership__user")
        )
        return Response(self.get_serializer(entries, many=True).data)

    @extend_schema(request=ProjectAccessCreateSerializer, responses=ProjectSerializer)
    def post(self, request, project_id):
        data = ProjectAccessCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        project = services.grant_access(request.user, project_id, **data.validated_data)
        return Response(ProjectSerializer(project, context={"request": request}).data)


class ProjectAccessDetailView(GenericAPIView):
    serializer_class = VersionSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="version",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=True,
            )
        ],
        request=None,
        responses=ProjectSerializer,
    )
    def delete(self, request, project_id, membership_id):
        data = self.get_serializer(data=request.query_params)
        data.is_valid(raise_exception=True)
        project = services.revoke_access(
            request.user, project_id, membership_id, **data.validated_data
        )
        return Response(ProjectSerializer(project, context={"request": request}).data)


class ProjectRecoveryView(GenericAPIView):
    serializer_class = ProjectRecoverySerializer

    @extend_schema(responses=OrphanedProjectSerializer)
    def post(self, request, project_id):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(services.recover_project(request, project_id, **data.validated_data))
