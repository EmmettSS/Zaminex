from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
@login_required
def dashboard(request):
    user = request.user
    django_role = getattr(user, "role", "")
    
    frontend_role = "admin" if django_role == "ADMIN" else "consultant"
    
    initial_data = {
        "isAuthenticated": True,
        "role": frontend_role,
        "userName": user.get_full_name() or user.username,
        "currentConsultantId": str(user.id),
        "initialPage": "admin-dashboard" if frontend_role == "admin" else "consultant-dashboard",
        "loginUrl": "/accounts/login/",
        "logoutUrl": "/accounts/logout/",
        "csrfToken": get_token(request),
        "pageProps": {},
    }

    return render(request, "dashboard.html", {
        "initial_data": initial_data,
    })
