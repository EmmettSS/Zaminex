from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.common.metrics import consultant_performance_metrics

from .models import AdminProfile, ConsultantProfile, UserRole

User = get_user_model()


class ConsultantProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        min_length=8,
        error_messages={
            "min_length": "رمز عبور باید حداقل ۸ کاراکتر باشد.",
            "blank": "رمز عبور نمی‌تواند خالی باشد.",
        },
    )

    class Meta:
        model = ConsultantProfile
        fields = [
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "password",
            "full_name",
            "mobile",
            "branch",
            "profile_image",
            "hired_at",
            "notes",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_mobile(self, value):
        if value and not value.startswith("09"):
            raise serializers.ValidationError("شماره موبایل معتبر نیست. شماره باید با ۰۹ شروع شود.")
        if value and len(value) != 11:
            raise serializers.ValidationError("شماره موبایل باید ۱۱ رقم باشد.")
        return value

    def validate(self, attrs):
        if attrs.get("mobile") == "":
            attrs["mobile"] = None

        mobile = attrs.get("mobile")
        username = attrs.get("username")

        if username and User.objects.filter(username=username).exists():
            if self.instance and self.instance.user.username == username:
                pass
            else:
                raise serializers.ValidationError({"username": "این نام کاربری قبلاً ثبت شده است."})

        if mobile and ConsultantProfile.objects.filter(mobile=mobile).exists():
            if self.instance and self.instance.mobile == mobile:
                pass
            else:
                raise serializers.ValidationError({"mobile": "این شماره موبایل قبلاً برای مشاور دیگری ثبت شده است."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")
        username = validated_data.pop("username", None) or validated_data.get("email", "")
        email = validated_data.pop("email", "")
        password = validated_data.pop("password", None)

        if not password:
            raise serializers.ValidationError({"password": "وارد کردن رمز عبور برای ایجاد مشاور الزامی است."})

        full_name = validated_data.get("full_name") or f"{first_name} {last_name}".strip()

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.AGENT,
        )

        consultant_profile = ConsultantProfile.objects.create(
            user=user,
            full_name=full_name,
            mobile=validated_data.get("mobile", ""),
            branch=validated_data.get("branch", ""),
            profile_image=validated_data.get("profile_image", None),
            hired_at=validated_data.get("hired_at") or timezone.now().date(),
            notes=validated_data.get("notes", ""),
            is_active=validated_data.get("is_active", True),
        )

        return consultant_profile

    @transaction.atomic
    def update(self, instance, validated_data):
        # Only admins may (un)archive a consultant account.
        if not self.context.get("is_admin_request"):
            validated_data.pop("is_active", None)

        first_name = validated_data.pop("first_name", None)
        last_name = validated_data.pop("last_name", None)
        username = validated_data.pop("username", None)
        email = validated_data.pop("email", None)
        # Password changes must go through the dedicated endpoints so the
        # current password is checked and other sessions are invalidated.
        validated_data.pop("password", None)

        user = instance.user
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if username and username != user.username:
            user.username = username
        if email is not None:
            user.email = email
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = instance.user

        data["user"] = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
        }
        perf = consultant_performance_metrics(instance)
        data["agentId"] = perf["agentId"]
        data["tenureDays"] = perf["tenureDays"]
        data["tasksOverdueCount"] = perf["tasksOverdueCount"]
        data["followupsOverdueCount"] = perf["followupsOverdueCount"]
        data["closedDealsCount"] = perf["closedDealsCount"]
        data["completedWorkCount"] = perf["completedWorkCount"]
        data["overdueWorkCount"] = perf["overdueWorkCount"]
        data["headlineValue"] = perf["headlineValue"]
        data["headlineLabel"] = perf["headlineLabel"]
        return data

class AdminProfileSerializer(serializers.ModelSerializer):
    """Serializer for the admin's own profile.

    Keeps exactly the same response shape as ConsultantProfileSerializer
    (profile fields + nested ``user`` object + write-only account fields)
    so the "My Profile" UI works identically for admins.
    """

    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        min_length=8,
        error_messages={
            "min_length": "رمز عبور باید حداقل ۸ کاراکتر باشد.",
            "blank": "رمز عبور نمی‌تواند خالی باشد.",
        },
    )

    class Meta:
        model = AdminProfile
        fields = [
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "password",
            "full_name",
            "mobile",
            "branch",
            "profile_image",
            "hired_at",
            "notes",
            "is_active",
        ]
        read_only_fields = ["id", "is_active"]

    def validate_mobile(self, value):
        if value and not value.startswith("09"):
            raise serializers.ValidationError("شماره موبایل معتبر نیست. شماره باید با ۰۹ شروع شود.")
        if value and len(value) != 11:
            raise serializers.ValidationError("شماره موبایل باید ۱۱ رقم باشد.")
        return value

    def validate(self, attrs):
        if attrs.get("mobile") == "":
            attrs["mobile"] = None

        username = attrs.get("username")
        if username and User.objects.filter(username=username).exists():
            if self.instance and self.instance.user.username == username:
                pass
            else:
                raise serializers.ValidationError({"username": "این نام کاربری قبلاً ثبت شده است."})

        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        first_name = validated_data.pop("first_name", None)
        last_name = validated_data.pop("last_name", None)
        username = validated_data.pop("username", None)
        email = validated_data.pop("email", None)
        validated_data.pop("password", None)

        user = instance.user
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if username and username != user.username:
            user.username = username
        if email is not None:
            user.email = email
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Keep the display name consistent when only first/last name is edited.
        if not instance.full_name:
            full = f"{user.first_name} {user.last_name}".strip()
            if full:
                instance.full_name = full

        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = instance.user
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
        }
        return data
