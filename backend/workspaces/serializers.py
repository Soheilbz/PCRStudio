from rest_framework import serializers

from config.serializers import StrictSerializer
from workspaces.models import Invitation, Membership, Workspace


class WorkspaceSerializer(StrictSerializer):
    id = serializers.UUIDField(source="workspace_id", read_only=True)
    name = serializers.CharField(source="workspace.name", read_only=True)
    kind = serializers.ChoiceField(
        source="workspace.kind", choices=Workspace.Kind.choices, read_only=True
    )
    role = serializers.ChoiceField(choices=Membership.Role.choices, read_only=True)


class WorkspaceCreateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=120)


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "email", "role", "active"]
        read_only_fields = fields


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "expires_at"]
        read_only_fields = fields


class InvitationCreateSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=Membership.Role.choices, default="member")


class InvitationAcceptSerializer(StrictSerializer):
    key = serializers.CharField(max_length=128, trim_whitespace=False)


class MemberRoleSerializer(StrictSerializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices)
