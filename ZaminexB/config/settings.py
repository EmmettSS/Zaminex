import sys
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()


DEBUG = os.environ.get("DJANGO_DEBUG", "1").strip().lower() in {"1", "true", "yes", "on"}

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-only-not-for-production"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is False.")


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


sys.path.insert(0, str(BASE_DIR))


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
    'apps.tickets.apps.TicketsConfig',
    'apps.reports.apps.ReportsConfig',
    'apps.analytics.apps.AnalyticsConfig',
    'apps.activity.apps.ActivityConfig',
    'apps.notifications.apps.NotificationsConfig',
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



DATABASE_NAME = "zaminex"
DATABASE_USER = "zaminex"
DATABASE_PASSWORD = "zaminex"
DATABASE_HOST = "localhost"
DATABASE_PORT = "5432"

DATABASE_CONNECT_TIMEOUT = int(os.environ.get("DATABASE_CONNECT_TIMEOUT", "5"))

if os.environ.get("DATABASE_URL"):
    _database_default = dj_database_url.parse(
        os.environ["DATABASE_URL"],
        conn_max_age=600,
        conn_health_checks=True,
    )
    _database_default.setdefault("OPTIONS", {})["connect_timeout"] = (
        DATABASE_CONNECT_TIMEOUT
    )
    DATABASES = {"default": _database_default}
    del _database_default
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DATABASE_NAME,
            "USER": DATABASE_USER,
            "PASSWORD": DATABASE_PASSWORD,
            "HOST": DATABASE_HOST,
            "PORT": DATABASE_PORT,
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"connect_timeout": DATABASE_CONNECT_TIMEOUT},
        }
    }

if "postgresql" not in DATABASES["default"]["ENGINE"]:
    raise ImproperlyConfigured(
        "Zaminex requires PostgreSQL, but the configured engine is "
        f"'{DATABASES['default']['ENGINE']}'. Check the DATABASE_* values in "
        "config/settings.py."
    )


if "test" in sys.argv:
    DATABASES["default"].setdefault("TEST", {})
    DATABASES["default"]["TEST"]["NAME"] = "test_zaminex"



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



LANGUAGE_CODE = 'fa-ir'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True



STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = "/accounts/login/"

MEDIA_URL = "/media/"


def _resolve_media_root(value: str, base: Path) -> Path:
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else (base / candidate).resolve()



_env_media_root = os.environ.get("MEDIA_ROOT", "").strip()
MEDIA_ROOT = (
    _resolve_media_root(_env_media_root, BASE_DIR)
    if _env_media_root
    else BASE_DIR / "media"
)

os.makedirs(MEDIA_ROOT, exist_ok=True)

LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
LOGIN_LOCKOUT_SECONDS = 10 * 60

SMS_OTP_LENGTH = 6
SMS_OTP_TTL_SECONDS = 2 * 60
SMS_OTP_MAX_ATTEMPTS = 5
SMS_OTP_RESEND_COOLDOWN_SECONDS = 60
SMS_REQUEST_TIMEOUT = 10

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


def _cache_settings():
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url:
        return {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": redis_url,
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
                    "IGNORE_EXCEPTIONS": True,
                    "SOCKET_CONNECT_TIMEOUT": 0.1,
                    "SOCKET_TIMEOUT": 0.1,
                },
            }
        }
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "zaminex-default",
        }
    }


CACHES = _cache_settings()


DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True



GEOCODE_UPSTREAM = os.environ.get(
    "GEOCODE_UPSTREAM", "https://nominatim.openstreetmap.org/search"
).strip()

GEOCODE_USER_AGENT = os.environ.get(
    "GEOCODE_USER_AGENT",
    "Zaminex-CRM/1.0 (+self-hosted real-estate CRM; geocode proxy)",
).strip()

GEOCODE_TIMEOUT = float(os.environ.get("GEOCODE_TIMEOUT", "8"))
GEOCODE_MAX_QUERY_LENGTH = 200
GEOCODE_LIMIT = 1

GEOCODE_PACING_SECONDS = float(os.environ.get("GEOCODE_PACING_SECONDS", "1.1"))

GEOCODE_CACHE_TTL = 30 * 24 * 3600
GEOCODE_NEGATIVE_CACHE_TTL = 7 * 24 * 3600

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "apps.common.exceptions.persian_exception_handler",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.common.throttles.ResilientAnonRateThrottle",
        "apps.common.throttles.ResilientUserRateThrottle",
        "apps.common.throttles.ResilientScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        "password_reset": "5/hour",
        "ai": "10/hour",
        "geocode": "60/min",
        "sms_request": "10/hour",
        "sms_verify": "20/min",
    },
}

if "test" in sys.argv:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []


FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000


SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SESSION_ENGINE = "apps.common.session_backend"

CSRF_COOKIE_HTTPONLY = False

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]


def _origins_for_host(host: str) -> list[str]:
    host = host.strip()
    
    if not host or host == "*":
        return []
    
    if host.startswith("."):
        host = f"*{host}"
    return [f"https://{host}", f"http://{host}"]


def _with_host_origins(configured: list[str], hosts: list[str]) -> list[str]:
    origins = list(configured)
    for host in hosts:
        for origin in _origins_for_host(host):
            if origin not in origins:
                origins.append(origin)
    return origins


CSRF_TRUSTED_ORIGINS = _with_host_origins(CSRF_TRUSTED_ORIGINS, ALLOWED_HOSTS)

if sys.argv[1:2] == ["test"]:
    CSRF_TRUSTED_ORIGINS = _with_host_origins(CSRF_TRUSTED_ORIGINS, ["testserver"])


AI_REQUEST_TIMEOUT = int(os.environ.get("AI_REQUEST_TIMEOUT", "180"))
