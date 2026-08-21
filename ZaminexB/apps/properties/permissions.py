
from functools import wraps
from django.shortcuts import redirect


def consultant_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if getattr(request.user, "role", None) != "AGENT":
            return redirect("accounts:login")

        return view_func(request, *args, **kwargs)

    return _wrapped_view
