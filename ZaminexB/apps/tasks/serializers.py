from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.properties.models import Property

from .models import Task


User = get_user_model()


class UserMiniSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    mobile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "name", "email", "mobile", "role"]

    def get_name(self, obj):
        return obj.get_full_name().strip() or obj.username

    def get_mobile(self, obj):
        profile = getattr(obj, "consultant_profile", None)
        return profile.mobile if profile else None


class PropertyMiniSerializer(serializers.ModelSerializer):
    district = serializers.CharField(source="neighborhood", read_only=True)
    price = serializers.SerializerMethodField()

    def get_price(self, obj):
        """Derived from the property's sale listings (see metrics)."""
        from apps.common.metrics import effective_sale_price

        price = effective_sale_price(obj)
        return str(price) if price is not None else None


    class Meta:
        model = Property
        fields = ["id", "title", "district", "price", "area", "floor", "internal_code"]


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_detail = UserMiniSerializer(source="assigned_to", read_only=True)
    created_by_detail = UserMiniSerializer(source="created_by", read_only=True)
    property_detail = PropertyMiniSerializer(source="property", read_only=True)

    taskType = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    assigneeId = serializers.IntegerField(source="assigned_to_id", read_only=True)
    creator = serializers.SerializerMethodField()
    propertyId = serializers.IntegerField(source="property_id", read_only=True, allow_null=True)
    due = serializers.DateField(source="due_date", read_only=True)
    isOverdue = serializers.SerializerMethodField()
    completionDate = serializers.SerializerMethodField()
    statusLabel = serializers.SerializerMethodField()
    priorityLabel = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "note",
            "status",
            "priority",
            "task_type",
            "taskType",
            "assigned_to",
            "assigned_to_detail",
            "assignee",
            "assigneeId",
            "created_by",
            "created_by_detail",
            "creator",
            "property",
            "property_detail",
            "propertyId",
            "due_date",
            "due",
            "isOverdue",
            "completed_at",
            "completionDate",
            "created_at",
            "updated_at",
            "statusLabel",
            "priorityLabel",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at", "completed_at"]

    def get_taskType(self, obj):
        return obj.get_task_type_display()

    def get_assignee(self, obj):
        if not obj.assigned_to:
            return None
        return obj.assigned_to.get_full_name().strip() or obj.assigned_to.username

    def get_creator(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name().strip() or obj.created_by.username

    def get_isOverdue(self, obj):
        return bool(obj.is_overdue())

    def get_completionDate(self, obj):
        if not obj.completed_at:
            return None
        return obj.completed_at.date().isoformat()

    def get_statusLabel(self, obj):
        return obj.get_status_display()

    def get_priorityLabel(self, obj):
        return obj.get_priority_display()


    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            data = data.copy()

        if "taskType" in data and "task_type" not in data:
            value = str(data["taskType"]).strip()
            data["task_type"] = value.upper() if value.upper() in dict(Task.TaskType.choices) else value

        if "priority" in data:
            value = str(data["priority"]).strip()
            data["priority"] = value.upper() if value.upper() in dict(Task.Priority.choices) else value.lower()

        if "status" in data and isinstance(data["status"], str):
            data["status"] = data["status"].upper()

        if "assignee" in data and "assigned_to" not in data:
            value = data["assignee"]
            if value not in (None, "", "null"):
                data["assigned_to"] = value
            data.pop("assignee", None)

        if "propertyId" in data and "property" not in data:
            pid = data["propertyId"]
            if pid in (None, "", "null"):
                data.pop("propertyId", None)
            else:
                data["property"] = pid

        if "due" in data and "due_date" not in data:
            data["due_date"] = data["due"]

        return super().to_internal_value(data)

    def validate(self, attrs):
        from apps.common.access import can_access_property

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        prop = attrs.get("property")
        if prop is None and self.instance is not None:
            prop = self.instance.property
        if user and prop is not None and not can_access_property(user, prop):
            raise serializers.ValidationError({"property": "شما به این ملک دسترسی ندارید."})

        new_status = attrs.get("status")
        instance = self.instance
        if new_status == Task.Status.COMPLETED:
            if not instance or not instance.completed_at:
                attrs["completed_at"] = timezone.now()
        elif new_status and new_status != Task.Status.COMPLETED and instance and instance.completed_at:
            attrs["completed_at"] = None
        return attrs
