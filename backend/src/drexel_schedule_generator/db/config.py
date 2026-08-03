from __future__ import annotations

import os

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://drexel:local-development-only@127.0.0.1:5432/"
    "drexel_schedule_generator"
)


def get_database_url() -> str:
    """Return the configured SQLAlchemy database URL."""
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
