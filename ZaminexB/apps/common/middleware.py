"""Custom request/response middleware."""

from .thread_locals import _thread_locals, set_current_user


class CurrentUserMiddleware:
    """Expose the logged-in user to code that has no request reference.

    ``log_activity`` consults this before falling back to the explicit
    ``user`` argument, so signal handlers can attribute changes without
    every caller having to thread the request through.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_current_user(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            _thread_locals.user = token


class SecurityHeadersMiddleware:
    """Add defence-in-depth HTTP security headers.

    * a strict ``Content-Security-Policy`` for production that still permits
      OpenStreetMap map tiles and the small amount of inline CSS the map
      widgets require;
    * ``Referrer-Policy`` and ``Permissions-Policy`` to limit what is
      leaked to linked third parties and which browser features pages may
      use;
    * ``Cache-Control: no-store`` on authenticated responses so sensitive
      JSON/HTML never lands in a shared browser cache.
    """

    # `same-origin` — NOT `no-referrer`.
    #
    # Both hide the referrer from third parties, but the referrer policy also
    # decides what the browser puts in the `Origin` header. Per the Fetch
    # Standard ("append a request Origin header"), for a request that is not
    # in CORS mode and whose method is neither GET nor HEAD, a policy of
    # `no-referrer` makes the browser send `Origin: null`.
    #
    # An HTML form submit is exactly such a request, and Django (>= 4.0)
    # rejects any POST whose `Origin` does not match a trusted origin. With
    # `no-referrer` the login form therefore failed with:
    #
    #     CSRF verification failed. Request aborted.
    #     Origin checking failed - null does not match any trusted origins.
    #
    # `same-origin` keeps the same privacy guarantee — the referrer is still
    # stripped for every cross-origin destination — while leaving the
    # `Origin` header intact for our own same-origin POSTs, so CSRF
    # validation can do its job instead of being defeated by a null value.
    REFERRER_POLICY = "same-origin"

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
        # Don't override CSP for the Django admin / static assets; its
        # tooling relies on inline scripts and its own static view.
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
            # Never store authenticated responses on disk. The CSRF/session
            # cookies are already HttpOnly/SameSite; this stops the pages
            # themselves from lingering in a public computer's cache.
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
        return response
