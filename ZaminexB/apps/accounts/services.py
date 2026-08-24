from django.contrib.auth import get_user_model

from .models import UserRole

User = get_user_model()


def create_user_with_role(*, username, password, role=UserRole.AGENT, **extra_fields):
    user = User.objects.create_user(
        username=username,
        password=password,
        role=role,
        **extra_fields,
    )
    return user


def create_admin_user(*, username, password, **extra_fields):
    extra_fields.setdefault("is_staff", True)
    extra_fields.setdefault("is_superuser", True)
    extra_fields.setdefault("role", UserRole.ADMIN)
    return create_user_with_role(username=username, password=password, **extra_fields)
