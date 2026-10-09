from rest_framework import serializers


class MeSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    email_verified = serializers.BooleanField(read_only=True)
    mfa_enabled = serializers.BooleanField(read_only=True)
    mfa_required = serializers.BooleanField(read_only=True)
    mfa_authenticated = serializers.BooleanField(read_only=True)


class CSRFSerializer(serializers.Serializer):
    csrf_token = serializers.CharField(read_only=True)
