import os
import sys

from django.conf import settings
from django.core.checks import Error, Warning, register

from apps.common.templatetags.vite_assets import find_missing_assets

REBUILD_HINT = (
    "Rebuild the frontend so the manifest and the hashed assets are written "
    "together: cd ZaminexF && npm ci && npm run build"
)


def _under_test_runner() -> bool:
    return "test" in sys.argv


def _command_name() -> str:
    return sys.argv[1] if len(sys.argv) > 1 else ""


def _server_identity(connection) -> tuple[str, str, str, str]:
    try:
        settings_dict = connection.settings_dict
        return (
            str(settings_dict.get("HOST") or "localhost"),
            str(settings_dict.get("PORT") or "5432"),
            str(settings_dict.get("NAME") or ""),
            str(settings_dict.get("USER") or ""),
        )
    except Exception:
        return ("", "", "", "")


def _connection_fingerprint(connection) -> str | None:
    try:
        settings_dict = connection.settings_dict
        return repr(
            tuple(
                settings_dict.get(key)
                for key in ("HOST", "PORT", "NAME", "USER", "OPTIONS")
            )
        )
    except Exception:
        return None


_probe_results: dict[str, str | None] = {}


def _probe_database() -> str | None:
    from django.db import connection

    key = _connection_fingerprint(connection)
    if key is not None and key in _probe_results:
        return _probe_results[key]

    error: str | None = None
    try:
        connection.ensure_connection()
    except Exception as exc:
        error = " ".join(str(exc).split())

    if key is not None:
        _probe_results[key] = error
    return error


@register()
def check_database_reachable(app_configs, **kwargs):
    error = _probe_database()
    if error is None:
        return []

    from django.db import connection

    host, port, name, user = _server_identity(connection)
    probe_host, probe_port = host or "localhost", port or "5432"
    source = (
        "the DATABASE_URL environment variable"
        if os.environ.get("DATABASE_URL")
        else "config/settings.py"
    )
    try:
        timeout = connection.settings_dict.get("OPTIONS", {}).get("connect_timeout")
    except Exception:
        timeout = None

    where = f"{host}:{port}" if host else "the configured server"
    who = f" (database '{name}', user '{user}')" if name else ""
    message = f"Cannot reach the PostgreSQL server at {where}{who}: {error}"
    steps = [
        "1) Is the server running? Windows: services.msc -> 'postgresql-x64-18'"
        " -> Start. Linux: sudo systemctl start postgresql.",
        f'2) Prove it by hand: psql -U postgres -h {probe_host} -p {probe_port}'
        ' -c "SELECT 1".'
        " If that hangs too, the port is held by something that is not"
        f" PostgreSQL (Windows: netstat -ano | findstr :{probe_port}; Linux:"
        f" ss -ltnp | grep :{probe_port}).",
        f"3) If psql answers but Django does not, the values read from {source}"
        " (HOST/PORT/NAME/USER/PASSWORD) do not match the server, or the role"
        " and database were never created: psql -U postgres -c \"CREATE USER"
        " zaminex WITH PASSWORD 'zaminex';\" -c \"CREATE DATABASE zaminex OWNER"
        ' zaminex;".',
    ]
    if timeout:
        steps.append(
            f"(Each attempt gives up after {timeout} s — DATABASE_CONNECT_TIMEOUT."
            " Without that bound the process waits forever and prints nothing,"
            " which is exactly what makes this failure look like a hang.)"
        )

    is_blocking = _command_name() in {"runserver", "test"}
    issue = Error if is_blocking else Warning
    return [
        issue(
            message,
            hint=" ".join(steps),
            id="database.E001" if is_blocking else "database.W001",
        )
    ]


@register()
def check_frontend_assets(app_configs, **kwargs):
    missing = find_missing_assets()

    if missing is None:
        message = (
            "The Vite manifest is missing, so no frontend assets can be "
            "resolved and every page will render blank."
        )
        if settings.DEBUG or _under_test_runner():
            return [
                Warning(
                    message,
                    hint=REBUILD_HINT,
                    id="vite_assets.W001",
                )
            ]
        return [
            Error(
                message,
                hint=REBUILD_HINT,
                id="vite_assets.E001",
            )
        ]

    if not missing:
        return []

    detail = "; ".join(
        f"{entry} -> {', '.join(paths)}" for entry, paths in sorted(missing.items())
    )
    return [
        Error(
            "The Vite manifest references frontend files that do not exist: "
            f"{detail}. The manifest and the built assets have come apart, so "
            "every page will render blank with no error to explain it.",
            hint=REBUILD_HINT,
            id="vite_assets.E002",
        )
    ]


@register()
def check_pg_trgm(app_configs, **kwargs):
    from django.db import connection

    if getattr(connection, "vendor", "") != "postgresql":
        return []

    if _probe_database() is not None:
        return []

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
            )
            installed = cursor.fetchone() is not None
            if not installed:
                return [
                    Warning(
                        "The pg_trgm extension is not installed on this "
                        "database, so fuzzy search runs the slow Python "
                        "fallback instead of using trigram indexes.",
                        hint=(
                            "Run the pending migrations (python manage.py "
                            "migrate), or have a superuser run "
                            "'CREATE EXTENSION pg_trgm;' on this database."
                        ),
                        id="pg_trgm.W001",
                    )
                ]
            
            cursor.execute("SELECT show_trgm(%s)", ["آپارتمان"])
            row = cursor.fetchone()
            usable = bool(row and row[0])
    except Exception:
        return []

    if usable:
        return []

    return [
        Warning(
            "pg_trgm is installed but cannot tokenize Persian text on this "
            "database, so fuzzy search runs the slow Python fallback. The "
            "database's LC_CTYPE is almost certainly the plain 'C' locale, "
            "where every non-ASCII letter counts as a word separator and "
            "show_trgm('آپارتمان') returns an empty array.",
            hint=(
                "Recreate the database with a UTF-8 locale (for example "
                "CREATE DATABASE ... TEMPLATE template0 LC_CTYPE 'C.UTF-8') "
                "and restore the data into it. Migrations cannot fix this."
            ),
            id="pg_trgm.W002",
        )
    ]


@register()
def check_pending_migrations(app_configs, **kwargs):
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader

    if _probe_database() is not None:
        return []

    try:
        loader = MigrationLoader(connection, ignore_no_migrations=True)
    except Exception:
        return []

    plan = []
    for leaf in loader.graph.leaf_nodes():
        for node in loader.graph.forwards_plan(leaf):
            if node not in plan:
                plan.append(node)
    pending = [
        f"{app}.{name}"
        for app, name in plan
        if (app, name) not in loader.applied_migrations
    ]
    if not pending:
        return []

    shown = ", ".join(pending[:5])
    if len(pending) > 5:
        shown += f" and {len(pending) - 5} more"
    return [
        Warning(
            f"The database is missing {len(pending)} migration(s): {shown}. "
            "Tables and columns the code expects may not exist yet, so parts "
            "of the site will fail with 'relation does not exist' until this "
            "is run.",
            hint="python manage.py migrate",
            id="migrations.W001",
        )
    ]
