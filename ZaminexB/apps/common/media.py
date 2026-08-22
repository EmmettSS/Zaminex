"""Serve uploaded media only to authenticated users who may access it.

The media root contains consultant avatars and property images. The previous
implementation only checked authentication, which let any logged-in consultant
download every uploaded file by guessing its name. This module adds:

* path traversal protection (``..`` and absolute paths are rejected);
* property images are readable by every authenticated user — they follow the
  read access of the consultant "همه املاک" tab, where every consultant may
  view the details (including the gallery) of every property in the system.
  Only registered ``PropertyImage`` files are served, so arbitrary files under
  MEDIA_ROOT can still not be downloaded by guessing a name, and mutating the
  gallery (upload/delete/reorder) stays owner/admin-only in the API views;
* per-entity ownership checks for profile avatars (users see only their own).
"""

from __future__ import annotations

import posixpath
from pathlib import PurePosixPath

from django.conf import settings
from django.http import Http404, HttpResponseForbidden
from django.views.static import serve

from apps.accounts.models import AdminProfile, ConsultantProfile
from apps.properties.models import PropertyImage


def _safe_relative_path(path: str) -> str | None:
    """Return a safe path relative to MEDIA_ROOT or None if it is not."""
    if not path:
        return None
    # Reject absolute Windows/Unix paths and NUL bytes outright.
    if "\x00" in path or path.startswith(("/", "\\")) or ":\\" in path:
        return None
    normalized = posixpath.normpath(path).replace("\\", "/")
    if normalized in (".", "..") or normalized.startswith("../") or "/../" in normalized:
        return None
    return normalized


def _can_access_media(user, rel_path: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    # Admins can read every uploaded file.
    if getattr(user, "role", "") == "ADMIN":
        return True
    parts = PurePosixPath(rel_path).parts
    if not parts:
        return False
    # Property images: readable by every authenticated user, mirroring the
    # read access of the consultant "همه املاک" tab (a consultant may view the
    # details of every property, so the gallery must render there too). The
    # file must still belong to a registered PropertyImage row, which keeps
    # arbitrary MEDIA_ROOT files from being downloadable by name. Mutating
    # the gallery stays owner/admin-only and is enforced by the API views.
    if parts[0] == "properties":
        return PropertyImage.objects.filter(image=rel_path).exists()
    # Consultant avatars: consultants may see their own avatar only. We do
    # not expose other consultants' profile photos to non-admins.
    if parts[0] == "consultants":
        return ConsultantProfile.objects.filter(user=user, profile_image=rel_path).exists()
    if parts[0] == "admins":
        # Admin avatars are never exposed to consultants; admins already
        # passed the role check above.
        return AdminProfile.objects.filter(user=user, profile_image=rel_path).exists()
    # Unknown media path: deny by default.
    return False


def serve_media(request, path):
    rel_path = _safe_relative_path(path)
    if rel_path is None:
        raise Http404("مسیر فایل نامعتبر است.")
    if not _can_access_media(request.user, rel_path):
        return HttpResponseForbidden("شما به این فایل دسترسی ندارید.")
    return serve(request, rel_path, document_root=settings.MEDIA_ROOT)
