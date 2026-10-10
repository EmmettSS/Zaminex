import re

from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404

IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"

REVALIDATE_CACHE_CONTROL = "public, max-age=300, must-revalidate"

HASHED_ASSET_PREFIX = "frontend/assets/"

_HASHED_ASSET = re.compile(r"-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$")


class CachedStaticFilesHandler(StaticFilesHandler):
    def __init__(self, application):
        super().__init__(application)
        self.immutable_prefix = f"{settings.STATIC_URL}{HASHED_ASSET_PREFIX}"

    def cache_control_for(self, path):
        if path.startswith(self.immutable_prefix) and _HASHED_ASSET.search(path):
            return IMMUTABLE_CACHE_CONTROL
        return REVALIDATE_CACHE_CONTROL

    def serve(self, request):
        try:
            response = super().serve(request)
        except SuspiciousFileOperation:
            raise Http404("Static file not found.")
        response["Cache-Control"] = self.cache_control_for(request.path)
        return response


def static_files_handler(application):
    if settings.DEBUG:
        return application
    return CachedStaticFilesHandler(application)
