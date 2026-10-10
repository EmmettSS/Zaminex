from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

from .models import UserRole


class ArchivedConsultantSessionMiddleware:
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
