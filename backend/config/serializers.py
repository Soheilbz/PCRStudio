from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and data.keys() - self.fields.keys():
            raise serializers.ValidationError({"non_field_errors": ["Unsupported fields."]})
        return super().to_internal_value(data)
