from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.properties.models import Property
from .models import FollowUp, FollowUpStatus, FollowUpType

User = get_user_model()


class FollowUpListSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="follow_up_type", read_only=True)
    contact = serializers.CharField(source="contact_name", read_only=True)
    date = serializers.DateTimeField(source="scheduled_at", read_only=True)
    consultant = serializers.CharField(source="consultant_name", read_only=True)
    consultantId = serializers.PrimaryKeyRelatedField(source="consultant", read_only=True)
    propertyId = serializers.PrimaryKeyRelatedField(source="property", read_only=True)
    property = serializers.CharField(source="property_title", read_only=True)
    isOverdue = serializers.SerializerMethodField()
    # Recency fields: the frontend orders lists and dashboard widgets by the
    # newest activity (created or edited) using these.
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = FollowUp
        fields = [
            "id",
            "title",
            "type",
            "contact",
            "date",
            "consultant",
            "consultantId",
            "property",
            "propertyId",
            "outcome",
            "status",
            "probability",
            "notes",
            "is_archived",
            "isOverdue",
            "createdAt",
            "updatedAt",
        ]

    def get_isOverdue(self, obj):
        return bool(obj.is_overdue())


class FollowUpWriteSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=FollowUpType.choices,
        source="follow_up_type",
        required=True,
    )
    contact = serializers.CharField(
        source="contact_name",
        required=True,
        allow_blank=False,
        max_length=255,
    )
    date = serializers.DateTimeField(
        source="scheduled_at",
        required=True,
    )
    
    consultantId = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="AGENT"),
        source="consultant",
        required=True,
    )
    propertyId = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(),
        source="property",
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    outcome = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    probability = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=FollowUpStatus.choices,
        required=False,
        default=FollowUpStatus.SCHEDULED,
    )

    class Meta:
        model = FollowUp
        fields = [
            "id",
            "title",
            "type",
            "contact",
            "date",
            "consultantId",
            "propertyId",
            "notes",
            "outcome",
            "status",
            "probability",
        ]

    def validate_probability(self, value):
        if value is None:
            return value
        if value < 0 or value > 100:
            raise serializers.ValidationError("احتمال موفقیت باید عددی بین ۰ تا ۱۰۰ باشد.")
        return value

    def validate(self, attrs):
        from apps.common.access import can_access_property

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if user and getattr(user, "is_authenticated", False) and getattr(user, "role", "") != "ADMIN":
            attrs["consultant"] = user

        prop = attrs.get("property")
        if prop is None and self.instance is not None:
            prop = self.instance.property
        if user and prop is not None and not can_access_property(user, prop):
            raise serializers.ValidationError({"propertyId": "شما به این ملک دسترسی ندارید."})

        status_value = attrs.get("status")
        outcome_value = attrs.get("outcome", None)

        if status_value == FollowUpStatus.COMPLETED and not outcome_value:
            raise serializers.ValidationError(
                {"outcome": "ثبت نتیجه برای پیگیری تکمیل‌شده الزامی است."}
            )

        return attrs

class FollowUpArchiveSerializer(serializers.Serializer):
    is_archived = serializers.BooleanField(read_only=True)
