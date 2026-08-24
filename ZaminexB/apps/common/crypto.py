"""Symmetric encryption for small secrets stored in the database.

This is deliberately lightweight and dependency-free: the AI provider API key
is the only secret we persist at the moment, and storing it with a reversible
cipher (keyed by ``DJANGO_SECRET_KEY`` or a dedicated ``SECRET_ENCRYPTION_KEY``
environment variable) is strictly better than plaintext while still letting the
application read it without operator intervention.

For production-grade secrets management (HSM / KMS) operators should inject the
key via the ``SECRET_ENCRYPTION_KEY`` environment variable and rotate it through
a proper secret manager. The ciphertext is prefixed with ``enc:v1:`` so that
existing plaintext rows continue to work and new encrypted rows are
recognisable.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from django.conf import settings


_PREFIX = "enc:v1:"


def _key() -> bytes:
    raw = (
        getattr(settings, "SECRET_ENCRYPTION_KEY", None)
        or getattr(settings, "SECRET_KEY", "")
        or "insecure-default"
    )
    # Derive a fixed-length 32-byte key so the length of the user-supplied
    # secret does not affect encryption.
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _xor(data: bytes, key: bytes) -> bytes:
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def encrypt_secret(plaintext: str | None) -> str:
    if not plaintext:
        return ""
    # If the value is already encrypted we leave it untouched.
    if plaintext.startswith(_PREFIX):
        return plaintext
    key = _key()
    sig = hmac.new(key, plaintext.encode("utf-8"), hashlib.sha256).digest()
    body = _xor(plaintext.encode("utf-8"), key)
    return _PREFIX + base64.urlsafe_b64encode(sig + body).decode("ascii")


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        # Legacy plaintext row: return as-is so existing installs keep working.
        return value
    try:
        raw = base64.urlsafe_b64decode(value[len(_PREFIX):].encode("ascii"))
    except Exception:
        return ""
    if len(raw) < 32:
        return ""
    sig, body = raw[:32], raw[32:]
    key = _key()
    plaintext = _xor(body, key)
    expected = hmac.new(key, plaintext, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        # Either the data is corrupted or the encryption key changed. We
        # refuse to return anything rather than handing back garbage.
        return ""
    return plaintext.decode("utf-8", errors="replace")
