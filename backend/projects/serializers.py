from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from config.serializers import StrictSerializer
from projects.models import Project
from projects.services import orphaned, project_role


class ProjectSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True)
    owner_membership_id = serializers.UUIDField(read_only=True)
    role = serializers.SerializerMethodField()
    orphaned = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "workspace_id",
            "name",
            "description",
            "version",
            "archived",
            "role",
            "owner_membership_id",
            "orphaned",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=["owner", "editor", "viewer"]))
    def get_role(self, obj):
        if hasattr(obj, "_actor_role"):
            return obj._actor_role
        return project_role(self.context["request"].user, obj)

    @extend_schema_field(serializers.BooleanField())
    def get_orphaned(self, obj):
        return orphaned(obj)


class ProjectCreateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(max_length=4000, allow_blank=True, default="")


class ProjectUpdateSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=160, required=False)
    description = serializers.CharField(max_length=4000, allow_blank=True, required=False)
    archived = serializers.BooleanField(required=False)


class ProjectAccessSerializer(StrictSerializer):
    membership_id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    role = serializers.ChoiceField(choices=["owner", "editor", "viewer"], read_only=True)


class ProjectAccessCreateSerializer(StrictSerializer):
    membership_id = serializers.UUIDField()
    role = serializers.ChoiceField(choices=["owner", "editor", "viewer"])
    version = serializers.IntegerField(min_value=1)


class VersionSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=1)


class OrphanedProjectSerializer(StrictSerializer):
    id = serializers.UUIDField(read_only=True)
    version = serializers.IntegerField(read_only=True)


class ProjectRecoverySerializer(StrictSerializer):
    membership_id = serializers.UUIDField()
    version = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(
        choices=["owner_removed", "owner_suspended", "security_revocation"]
    )
