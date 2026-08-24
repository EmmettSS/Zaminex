from functools import wraps

from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.core.exceptions import PermissionDenied
from .models import User


from .models import UserRole


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return login_required(view_func)(request, *args, **kwargs)

            if request.user.role not in allowed_roles:
                raise PermissionDenied("شما اجازه دسترسی به این صفحه را ندارید.")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):

        if request.user.is_authenticated and request.user.role == "ADMIN":
            return view_func(request, *args, **kwargs)

        raise PermissionDenied("شما اجازه دسترسی به این صفحه را ندارید.")

    return _wrapped_view



def agent_required(view_func):
    return role_required(UserRole.AGENT)(view_func)
