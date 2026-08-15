"""Local-only settings to run the test suite against in-memory SQLite.

Used when the Postgres host from .env is not reachable (e.g. running tests
outside Docker). Not for production.
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
