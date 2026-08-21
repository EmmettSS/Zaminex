import sys
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
#  Configuration
#
#  Settings are plain values edited directly in this file — there is no .env
#  and no dotenv dependency. Change them here for your environment.
# ---------------------------------------------------------------------------

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Generate a fresh one before deploying:
#   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# Production MUST set DJANGO_SECRET_KEY. The insecure fallback is local-only.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()

# SECURITY WARNING: don't run with debug turned on in production!
# Default stays on for a local checkout. Production must set DJANGO_DEBUG=0.
DEBUG = os.environ.get("DJANGO_DEBUG", "1").strip().lower() in {"1", "true", "yes", "on"}

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-only-not-for-production"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is False.")

# Hosts are configurable via ALLOWED_HOSTS (comma-separated). In production
# the variable is required so a missing deploy cannot accidentally serve
# arbitrary Host headers.
#
# The local default is only reached in DEBUG. This assignment must stay the
# single source of truth: a second, unconditional `ALLOWED_HOSTS = [...]`
# below would silently discard the deployment's value and make every
# non-local request fail the Host check (and, in turn, CSRF origin checks).
DEFAULT_LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

_env_hosts = os.environ.get("ALLOWED_HOSTS", "").strip()
if _env_hosts:
    ALLOWED_HOSTS = [h.strip() for h in _env_hosts.split(",") if h.strip()]
elif DEBUG:
    ALLOWED_HOSTS = list(DEFAULT_LOCAL_HOSTS)
else:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must be set when DEBUG is False (comma-separated list)."
    )

# Add project root to path (safer than adding apps/ directly)
# Rationale: INSTALLED_APPS uses package paths like 'apps.accounts...'.
# Pointing sys.path at BASE_DIR ensures Python can import the top-level
# 'apps' package without shadowing it by injecting BASE_DIR/apps directly.
sys.path.insert(0, str(BASE_DIR))


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'apps.common.apps.CommonConfig',
    'apps.basics.apps.BasicsConfig',
    'apps.accounts.apps.AccountsConfig',
    'apps.listings.apps.ListingsConfig',
    'apps.properties.apps.PropertiesConfig',
    'apps.tasks.apps.TasksConfig',
    'apps.followups.apps.FollowupsConfig',
    'apps.reports.apps.ReportsConfig',
    'rest_framework',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.accounts.middleware.ArchivedConsultantSessionMiddleware',
    'apps.common.middleware.CurrentUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.common.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# PostgreSQL is the only supported backend. The schema relies on JSONB, partial
# indexes and typed EAV columns, and the reference-data tables assume
# PostgreSQL semantics.
#
# Edit the values below to match your server. A DATABASE_URL environment
# variable, when present, still wins — that is what deployment platforms set —
# but nothing is required for a normal local checkout.
DATABASE_NAME = "zaminex"
DATABASE_USER = "zaminex"
DATABASE_PASSWORD = "zaminex"
DATABASE_HOST = "localhost"
DATABASE_PORT = "5432"

if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"],
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DATABASE_NAME,
            "USER": DATABASE_USER,
            "PASSWORD": DATABASE_PASSWORD,
            "HOST": DATABASE_HOST,
            "PORT": DATABASE_PORT,
            # Re-use connections for 10 minutes instead of opening one per
            # request; a meaningful win on PostgreSQL.
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
        }
    }

# Fail loudly rather than silently running on an unsupported backend.
if "postgresql" not in DATABASES["default"]["ENGINE"]:
    raise ImproperlyConfigured(
        "Zaminex requires PostgreSQL, but the configured engine is "
        f"'{DATABASES['default']['ENGINE']}'. Check the DATABASE_* values in "
        "config/settings.py."
    )

# Tests build a throwaway database, so behaviour that differs between backends
# (case-insensitive search, JSON handling, constraint enforcement) is exercised
# exactly as in production.
if "test" in sys.argv:
    DATABASES["default"].setdefault("TEST", {})
    DATABASES["default"]["TEST"]["NAME"] = "test_zaminex"


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'fa-ir'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Task 3: use custom user model
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = "/accounts/login/"

# Task 4: media settings
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Account-scoped login protection: 5 failed attempts in 15 minutes => 10-minute lock.
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
LOGIN_LOCKOUT_SECONDS = 10 * 60

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "apps.common.exceptions.persian_exception_handler",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        # Sensitive endpoints: a tighter scope prevents brute-forcing or
        # runaway AI / CSV export costs.
        "password_reset": "5/hour",
        "login": "10/min",
        "ai": "10/hour",
        "export": "10/hour",
        "file_upload": "20/min",
    },
}

if "test" in sys.argv:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []

# ---------------------------------------------------------------------------
# File upload hardening
# ---------------------------------------------------------------------------
# Cap request body sizes to make bulk upload attacks impractical. These are
# deliberately above the legitimate property image size (5 MB per file, up to
# 10 files per request) so the UI keeps working.
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024  # 12 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# ---------------------------------------------------------------------------
# Session hardening
# ---------------------------------------------------------------------------
# Idle timeout: the user is logged out after 12 hours of inactivity. A
# persistent cap of 7 days prevents a stolen cookie from living forever.
SESSION_COOKIE_AGE = 12 * 60 * 60  # 12 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
# CSRF cookie must be readable by JS to set the X-CSRFToken header from the
# SPA; keep it scoped to the same site and HttpOnly off (this is standard
# for a session-authenticated SPA).
CSRF_COOKIE_HTTPONLY = False

# ---------------------------------------------------------------------------
# CSRF trusted origins
# ---------------------------------------------------------------------------
# Django >= 4.0 validates the `Origin` header of every unsafe request against
# this list (falling back to the Host header only when no Origin is sent).
# Behind a reverse proxy the browser's Origin carries the *public* scheme and
# host, which is not necessarily what Django reconstructs from the request, so
# the list has to be explicit.
#
# `CSRF_TRUSTED_ORIGINS` (comma-separated, each entry including a scheme) is
# the authoritative source. On top of it, every entry of ALLOWED_HOSTS is
# registered automatically: an operator who correctly declares their hosts
# should not additionally have to restate them here to be able to log in.
# Wildcard hosts ("*" and ".example.com") are passed through in the form
# Django expects, and "*" alone is skipped because it is not a valid origin.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]


def _origins_for_host(host: str) -> list[str]:
    """Both schemes for one ALLOWED_HOSTS entry, in CSRF_TRUSTED_ORIGINS form."""
    host = host.strip()
    # "*" matches any host; there is no origin that expresses that, and
    # inventing one would trust every site on the internet.
    if not host or host == "*":
        return []
    # Django already accepts a leading dot as "this domain and subdomains";
    # the origin form of that is "https://*.example.com".
    if host.startswith("."):
        host = f"*{host}"
    return [f"https://{host}", f"http://{host}"]


def _with_host_origins(configured: list[str], hosts: list[str]) -> list[str]:
    """`configured` plus an origin for every host, without duplicates.

    Written as a function so the loop variables cannot leak into the module
    namespace and be picked up as settings.
    """
    origins = list(configured)
    for host in hosts:
        for origin in _origins_for_host(host):
            if origin not in origins:
                origins.append(origin)
    return origins


CSRF_TRUSTED_ORIGINS = _with_host_origins(CSRF_TRUSTED_ORIGINS, ALLOWED_HOSTS)
