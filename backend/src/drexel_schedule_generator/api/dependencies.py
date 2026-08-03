from collections.abc import Iterator

from sqlalchemy.orm import Session

from drexel_schedule_generator.db.session import SessionLocal


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
