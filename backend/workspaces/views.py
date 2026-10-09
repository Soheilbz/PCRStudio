from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.policy import require_authenticated_mfa
from projects.models import Project
from projects.serializers import OrphanedProjectSerializer
from workspaces import services
from workspaces.models import Invitation, Membership
from workspaces.serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    MemberRoleSerializer,
    MemberSerializer,
    WorkspaceCreateSerializer,
    WorkspaceSerializer,
)


class WorkspaceListView(GenericAPIView):
    serializer_class = WorkspaceSerializer
    pagination_class = None

    @extend_schema(responses=WorkspaceSerializer(many=True))
    def get(self, request):
        members = request.user.memberships.filter(active=True).select_related("workspace")
        return Response(WorkspaceSerializer(members, many=True).data)

    @extend_schema(request=WorkspaceCreateSerializer, responses={201: WorkspaceSerializer})
    def post(self, request):
        data = WorkspaceCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        require_authenticated_mfa(request)
        membership = services.create_organization(request.user, **data.validated_data)
        return Response(WorkspaceSerializer(membership).data, status=201)


class MemberListView(GenericAPIView):
    serializer_class = MemberSerializer

    @extend_schema(responses=MemberSerializer(many=True))
    def get(self, request, workspace_id):
        services.current_membership(request.user, workspace_id)
        members = Membership.objects.filter(
            workspace_id=workspace_id, active=True, user__is_active=True
        ).select_related("user")
        return self.get_paginated_response(
            self.get_serializer(self.paginate_queryset(members), many=True).data
        )


class MemberDetailView(GenericAPIView):
    serializer_class = MemberSerializer

    @extend_schema(request=MemberRoleSerializer, responses=MemberSerializer)
    def patch(self, request, workspace_id, membership_id):
        data = MemberRoleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        member = services.change_member_role(
            request.user, workspace_id, membership_id, **data.validated_data
        )
        return Response(self.get_serializer(member).data)

    @extend_schema(responses={204: None})
    def delete(self, request, workspace_id, membership_id):
        services.revoke_member(request.user, workspace_id, membership_id)
        return Response(status=204)


class WorkspaceLeaveView(GenericAPIView):
    serializer_class = MemberSerializer

    @extend_schema(request=None, responses={204: None})
    def post(self, request, workspace_id):
        member = services.current_membership(request.user, workspace_id)
        services.revoke_member(request.user, workspace_id, member.id, voluntary=True)
        return Response(status=204)


class InvitationListView(GenericAPIView):
    serializer_class = InvitationSerializer

    @extend_schema(responses=InvitationSerializer(many=True))
    def get(self, request, workspace_id):
        services.require_admin(request.user, workspace_id)
        invitations = Invitation.objects.filter(
            workspace_id=workspace_id, accepted_at=None, revoked_at=None
        )
        return self.get_paginated_response(
            self.get_serializer(self.paginate_queryset(invitations), many=True).data
        )

    @extend_schema(request=InvitationCreateSerializer, responses={201: InvitationSerializer})
    def post(self, request, workspace_id):
        data = InvitationCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        invitation = services.create_invitation(request.user, workspace_id, **data.validated_data)
        return Response(self.get_serializer(invitation).data, status=201)


class InvitationDetailView(GenericAPIView):
    serializer_class = InvitationSerializer

    @extend_schema(responses={204: None})
    def delete(self, request, workspace_id, invitation_id):
        services.revoke_invitation(request.user, workspace_id, invitation_id)
        return Response(status=204)


class InvitationAcceptView(GenericAPIView):
    serializer_class = InvitationAcceptSerializer

    @extend_schema(responses=WorkspaceSerializer)
    def post(self, request):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        member = services.accept_invitation(request.user, **data.validated_data)
        return Response(WorkspaceSerializer(member).data)


class OrphanedProjectListView(GenericAPIView):
    serializer_class = OrphanedProjectSerializer

    @extend_schema(responses=OrphanedProjectSerializer(many=True))
    def get(self, request, workspace_id):
        services.require_admin(request.user, workspace_id)
        from django.db.models import Q

        projects = Project.objects.filter(workspace_id=workspace_id).filter(
            Q(owner_membership__active=False) | Q(owner_membership__user__is_active=False)
        )
        return self.get_paginated_response(
            self.get_serializer(self.paginate_queryset(projects), many=True).data
        )
