"""Seed clearly synthetic courses alongside the sanitized fixture dataset."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from pathlib import Path
import argparse

from sqlalchemy import select

from drexel_schedule_generator.db.models import Subject

from drexel_schedule_generator.db.session import session_scope
from drexel_schedule_generator.webtms.importer import import_dataset
from drexel_schedule_generator.webtms.parser import parse_fixture_directory
from drexel_schedule_generator.webtms.records import ParsedCourse, ParsedFixtureDataset, ParsedMeeting, ParsedSection


def _demo_course(number: str, title: str, crn: str, day: int, start: time) -> ParsedCourse:
    end = time(start.hour + 1, start.minute)
    meeting = ParsedMeeting(
        days=frozenset({day}),
        start_time=start,
        end_time=end,
        start_date=date(2026, 6, 22),
        end_date=date(2026, 8, 29),
        building="Synthetic Hall",
        room=number,
    )
    return ParsedCourse(
        source_id=f"SYNTHETIC-DEMO-{number}",
        subject="DEMO",
        subject_name="Synthetic Demo Courses",
        number=number,
        title=f"{title} (Synthetic Demo)",
        description="Synthetic local demonstration data; not sourced from WebTMS.",
        credits_min=Decimal("3.00"),
        credits_max=Decimal("3.00"),
        is_undergraduate=True,
        section=ParsedSection(
            source_id=f"SYNTHETIC-{crn}",
            crn=crn,
            number="001",
            component="Lecture",
            status="active",
            instructional_method="Synthetic In-Person",
            campus="Synthetic Campus",
            meetings=(meeting,),
            notes="Synthetic demo record; not real Drexel course data.",
        ),
    )


def _remove() -> int:
    with session_scope() as session:
        subject = session.scalar(select(Subject).where(Subject.code == "DEMO"))
        if subject is None:
            print("No synthetic DEMO data existed.")
            return 0
        courses = list(subject.courses)
        for course in courses:
            for offering in list(course.offerings):
                for section in list(offering.sections):
                    session.delete(section)
                session.flush()
                session.delete(offering)
            session.flush()
            session.delete(course)
        session.flush()
        session.delete(subject)
    print("Removed only synthetic DEMO courses and their dependent records.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage clearly synthetic local demo data")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args(argv)
    if args.remove:
        return _remove()
    fixtures = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "webtms"
    real = parse_fixture_directory(fixtures)
    dataset = ParsedFixtureDataset(
        term=real.term,
        courses=(
            *real.courses,
            _demo_course("101", "Schedule Design Studio", "D1001", 2, time(11)),
            _demo_course("102", "Calendar Systems Lab", "D1002", 4, time(13)),
        ),
        malformed_records=real.malformed_records,
    )
    with session_scope() as session:
        summary = import_dataset(
            session,
            dataset,
            fixture_name="sanitized fixtures plus synthetic demo records",
            source_name="local_demo_seed",
        )
    print(
        f"Seeded term {summary.term_code}: {summary.sections_imported} schedulable sections "
        f"and {summary.meetings_imported} meetings. DEMO courses are synthetic."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
