from .thread_locals import _thread_locals, set_current_user


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_current_user(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            _thread_locals.user = token


class SecurityHeadersMiddleware:
    REFERRER_POLICY = "strict-origin-when-cross-origin"

    CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https://*.tile.openstreetmap.org https://tile.openstreetmap.org; "
        "font-src 'self' data:; "
        "connect-src 'self' https://*.tile.openstreetmap.org https://tile.openstreetmap.org; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path or ""
        is_admin = path.startswith("/admin/")
        is_static = path.startswith(("/static/", "/media/"))
        if not is_admin and not is_static:
            response["Content-Security-Policy"] = self.CSP
            response["Referrer-Policy"] = self.REFERRER_POLICY
            response["Permissions-Policy"] = (
                "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
            )
            response["X-Content-Type-Options"] = "nosniff"
            response["X-Frame-Options"] = "DENY"
        if request.user.is_authenticated and not is_static:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
        return response
