from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

from .models import UserRole


class ArchivedConsultantSessionMiddleware:
    """Invalidate active sessions of archived consultants immediately.

    If an admin archives a consultant while the consultant is still logged
    in, the consultant is logged out on their very next request and sent to
    the login page with a notice that their account has been deactivated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and getattr(user, "role", "") == UserRole.AGENT
        ):
            profile = getattr(user, "consultant_profile", None)
            if profile is not None and not profile.is_active:
                logout(request)
                return redirect(f"{reverse('accounts:login')}?deactivated=1")
        return self.get_response(request)
