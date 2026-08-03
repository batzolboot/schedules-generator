from __future__ import annotations

import socket
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from drexel_schedule_generator.db.models import AcademicTerm, CourseOffering, ImportRun, ImportStatus, MeetingTime, Section
from drexel_schedule_generator.webtms.importer import import_dataset
from drexel_schedule_generator.webtms.parser import parse_fixture_directory
from drexel_schedule_generator.webtms.records import ParsedCourse, ParsedFixtureDataset, ParsedMeeting, ParsedSection, ParsedTerm

FIXTURES = Path(__file__).parent / "fixtures" / "webtms"


def fixture_dataset() -> ParsedFixtureDataset:
    return parse_fixture_directory(FIXTURES)


def synthetic_dataset(
    term_code: str,
    crn: str,
    *,
    course_number: str = "101",
    credits: Decimal | None = None,
    start: time = time(9),
) -> ParsedFixtureDataset:
    meeting = ParsedMeeting(
        days=frozenset({1, 3}),
        start_time=start,
        end_time=(datetime.combine(date.min, start) + timedelta(minutes=50)).time(),
        start_date=date(2026, 9, 1),
        end_date=date(2026, 12, 1),
        building="Main",
        room="101",
    )
    section = ParsedSection(
        source_id=crn,
        crn=crn,
        number="001",
        component="Lecture",
        status="active",
        instructional_method="Face-To-Face",
        campus="University City",
        meetings=(meeting,),
    )
    course = ParsedCourse(
        source_id=f"TEST-{course_number}",
        subject="TEST",
        subject_name="Test Studies",
        number=course_number,
        title=f"Test Course {course_number}",
        description=None,
        credits_min=credits,
        credits_max=credits,
        is_undergraduate=True,
        section=section,
    )
    return ParsedFixtureDataset(
        term=ParsedTerm(source_id=term_code, name=f"Term {term_code}"),
        courses=(course,),
    )


def test_initial_fixture_import_is_offline_and_preserves_meetings(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network used")))
    summary = import_dataset(db_session, fixture_dataset(), completed_at=datetime(2026, 8, 2, 20, tzinfo=UTC))

    assert summary.courses_seen == 2
    assert summary.sections_seen == 3
    assert summary.sections_imported == 2
    assert summary.sections_skipped == 1
    assert summary.meetings_imported == 2
    sections = db_session.scalars(select(Section).order_by(Section.crn)).all()
    assert [section.crn for section in sections] == ["40081", "40412"]
    lecture = next(section for section in sections if section.crn == "40081")
    assert len(lecture.meeting_times) == 1
    assert {meeting.meeting_type for meeting in lecture.meeting_times} == {"class"}
    assert db_session.scalar(select(func.count(MeetingTime.id))) == 2
    assert lecture.course_offering.minimum_credits == Decimal("3.00")
    assert lecture.maximum_enrollment == 30
    assert next(section for section in sections if section.crn == "40412").course_offering.minimum_credits == Decimal("3.00")


def test_repeated_import_is_idempotent_and_updates_existing_section(db_session: Session) -> None:
    dataset = synthetic_dataset("202601", "12345", credits=Decimal("3"))
    first = import_dataset(db_session, dataset)
    original_id = db_session.scalar(select(Section.id).where(Section.crn == "12345"))
    changed_meeting = replace(dataset.courses[0].section.meetings[0], start_time=time(10), end_time=time(10, 50))
    changed_section = replace(dataset.courses[0].section, meetings=(changed_meeting,), campus="Online")
    changed = replace(dataset, courses=(replace(dataset.courses[0], section=changed_section),))
    second = import_dataset(db_session, changed)

    stored = db_session.scalar(select(Section).where(Section.id == original_id))
    assert first.sections_imported == second.sections_imported == 1
    assert db_session.scalar(select(func.count(Section.id))) == 1
    assert stored is not None and stored.campus == "Online"
    assert stored.meeting_times[0].start_time == time(10)


def test_asynchronous_section_is_imported_without_fabricated_schedule_time(db_session: Session) -> None:
    dataset = synthetic_dataset("202601", "11313")
    async_meeting = replace(
        dataset.courses[0].section.meetings[0],
        days=frozenset(),
        start_time=None,
        end_time=None,
        building=None,
        room=None,
        is_asynchronous=True,
    )
    async_section = replace(
        dataset.courses[0].section,
        instructional_method="Online-Asynchronous",
        campus="Online",
        meetings=(async_meeting,),
    )
    imported = replace(dataset, courses=(replace(dataset.courses[0], section=async_section),))

    summary = import_dataset(db_session, imported)
    stored = db_session.scalar(select(Section).where(Section.crn == "11313"))

    assert summary.sections_imported == 1
    assert summary.meetings_imported == 1
    assert stored is not None
    assert stored.instruction_method == "Online-Asynchronous"
    assert stored.meeting_times[0].is_asynchronous
    assert stored.meeting_times[0].start_time is None
    assert not stored.meeting_times[0].days


def test_same_crn_is_unique_within_but_not_across_terms(db_session: Session) -> None:
    import_dataset(db_session, synthetic_dataset("202601", "77777"))
    import_dataset(db_session, synthetic_dataset("202602", "77777", course_number="102"))
    assert db_session.scalar(select(func.count(Section.id)).where(Section.crn == "77777")) == 2


def test_nullable_credits_are_preserved(db_session: Session) -> None:
    import_dataset(db_session, synthetic_dataset("202603", "88888", credits=None))
    offering = db_session.scalar(select(CourseOffering).join(Section).where(Section.crn == "88888"))
    assert offering is not None
    assert offering.minimum_credits is None
    assert offering.maximum_credits is None


def test_failed_import_rolls_back_and_preserves_previous_freshness(db_session: Session) -> None:
    first_time = datetime(2026, 8, 1, 12, tzinfo=UTC)
    import_dataset(db_session, synthetic_dataset("202604", "90001"), completed_at=first_time)
    changed = synthetic_dataset("202604", "90002", course_number="102")

    with pytest.raises(RuntimeError, match="Injected"):
        import_dataset(db_session, changed, completed_at=first_time + timedelta(days=1), fail_after_sections=1)

    term = db_session.scalar(select(AcademicTerm).where(AcademicTerm.source_identifier == "202604"))
    assert term is not None
    assert term.last_successful_import_run.completed_at == first_time
    assert db_session.scalar(select(Section).where(Section.crn == "90001")).is_active
    assert db_session.scalar(select(Section).where(Section.crn == "90002")) is None
    assert db_session.scalar(select(ImportRun).where(ImportRun.status == ImportStatus.FAILED)) is not None


def test_successful_deactivation_is_scoped_to_imported_term(db_session: Session) -> None:
    first = synthetic_dataset("202605", "91001")
    second_term = synthetic_dataset("202606", "92001")
    import_dataset(db_session, first)
    import_dataset(db_session, second_term)
    replacement = synthetic_dataset("202605", "91002", course_number="102")
    summary = import_dataset(db_session, replacement)

    old = db_session.scalar(select(Section).where(Section.crn == "91001"))
    other = db_session.scalar(select(Section).where(Section.crn == "92001"))
    assert summary.sections_deactivated == 1
    assert old is not None and not old.is_active and old.inactive_at is not None
    assert other is not None and other.is_active


def test_successful_import_advances_term_freshness(db_session: Session) -> None:
    first = datetime(2026, 8, 1, tzinfo=UTC)
    second = first + timedelta(hours=2)
    dataset = synthetic_dataset("202607", "93001")
    import_dataset(db_session, dataset, completed_at=first)
    import_dataset(db_session, dataset, completed_at=second)
    term = db_session.scalar(select(AcademicTerm).where(AcademicTerm.source_identifier == "202607"))
    assert term is not None
    assert term.last_successful_import_run.completed_at == second
