from __future__ import annotations

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.orm import Session

from drexel_schedule_generator.db.config import get_database_url


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(get_database_url())
    connection: Connection = engine.connect()
    transaction = connection.begin()
    connection.execute(
        text(
            "TRUNCATE TABLE academic_terms, component_types, subjects, instructors "
            "RESTART IDENTITY CASCADE"
        )
    )
    session = Session(bind=connection, expire_on_commit=False)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
