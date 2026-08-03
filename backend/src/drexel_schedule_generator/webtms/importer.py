"""Transactional persistence for parsed WebTMS records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from drexel_schedule_generator.db.models import (
    AcademicTerm,
    CanonicalComponentKind,
    ComponentType,
    Course,
    CourseOffering,
    ImportRun,
    ImportStatus,
    Instructor,
    MeetingDay,
    MeetingTime,
    OfferingComponent,
    RelationshipDataStatus,
    Section,
    SectionInstructor,
    SectionStatus,
    Subject,
)

from .records import ParsedFixtureDataset, ParsedMeeting


@dataclass(frozen=True, slots=True)
class ImportSummary:
    run_id: int
    term_id: int
    term_code: str
    courses_seen: int
    sections_seen: int
    sections_imported: int
    sections_skipped: int
    meetings_imported: int
    malformed_records: int
    sections_deactivated: int


def _component(value: str) -> tuple[str, CanonicalComponentKind]:
    normalized = value.casefold()
    if "lab" in normalized and "lecture" not in normalized:
        return "LAB", CanonicalComponentKind.LAB
    if "recitation" in normalized or "discussion" in normalized:
        return "REC", CanonicalComponentKind.RECITATION
    if "lecture" in normalized:
        return "LEC", CanonicalComponentKind.LECTURE
    return "OTHER", CanonicalComponentKind.OTHER


def _fingerprint(meeting: ParsedMeeting) -> str:
    payload = json.dumps(
        {
            "days": sorted(meeting.days),
            "start": meeting.start_time.isoformat() if meeting.start_time else None,
            "end": meeting.end_time.isoformat() if meeting.end_time else None,
            "start_date": meeting.start_date.isoformat() if meeting.start_date else None,
            "end_date": meeting.end_date.isoformat() if meeting.end_date else None,
            "building": meeting.building,
            "room": meeting.room,
            "type": meeting.meeting_type,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def import_dataset(
    session: Session,
    dataset: ParsedFixtureDataset,
    *,
    fixture_name: str | None = "sanitized_webtms_fixtures",
    source_name: str = "sanitized_webtms_fixture",
    completed_at: datetime | None = None,
    fail_after_sections: int | None = None,
) -> ImportSummary:
    """Import one complete term dataset, preserving the last successful state on failure."""
    now = completed_at or datetime.now(UTC)
    term = session.scalar(
        select(AcademicTerm).where(AcademicTerm.source_identifier == dataset.term.source_id)
    )
    if term is None:
        term = AcademicTerm(
            source_identifier=dataset.term.source_id,
            name=dataset.term.name,
            start_date=dataset.term.start_date,
            end_date=dataset.term.end_date,
        )
        session.add(term)
        session.flush()

    run = ImportRun(
        academic_term=term,
        status=ImportStatus.RUNNING,
        source_name=source_name,
        source_term_identifier=dataset.term.source_id,
        fixture_name=fixture_name,
        started_at=now,
    )
    session.add(run)
    session.flush()

    courses_seen = dataset.courses_seen_override or len(
        {(course.subject, course.number) for course in dataset.courses}
    )
    sections_seen = dataset.sections_seen_override or len(dataset.courses)
    imported = 0
    skipped = dataset.sections_skipped_override or 0
    meetings_imported = inserted = updated = 0
    seen_crns: set[str] = set()
    warnings: list[str] = []

    try:
        with session.begin_nested():
            term.name = dataset.term.name
            term.start_date = dataset.term.start_date
            term.end_date = dataset.term.end_date
            for parsed_course in dataset.courses:
                section_record = parsed_course.section
                if not parsed_course.is_undergraduate or not section_record.meetings:
                    skipped += 1
                    continue
                subject = session.scalar(select(Subject).where(Subject.code == parsed_course.subject))
                if subject is None:
                    subject = Subject(
                        code=parsed_course.subject,
                        name=parsed_course.subject_name or parsed_course.subject,
                        source_identifier=parsed_course.subject,
                    )
                    session.add(subject)
                    session.flush()
                course = session.scalar(
                    select(Course).where(
                        Course.subject_id == subject.id,
                        Course.course_number == parsed_course.number,
                    )
                )
                if course is None:
                    course = Course(
                        subject=subject,
                        course_number=parsed_course.number,
                        title=parsed_course.title,
                        description=parsed_course.description,
                        source_identifier=parsed_course.source_id,
                    )
                    session.add(course)
                    session.flush()
                else:
                    course.title = parsed_course.title
                    course.description = parsed_course.description
                offering = session.scalar(
                    select(CourseOffering).where(
                        CourseOffering.academic_term_id == term.id,
                        CourseOffering.course_id == course.id,
                    )
                )
                if offering is None:
                    offering = CourseOffering(
                        academic_term=term,
                        course=course,
                        source_identifier=f"{term.source_identifier}:{parsed_course.subject}:{parsed_course.number}",
                        minimum_credits=parsed_course.credits_min,
                        maximum_credits=parsed_course.credits_max,
                        relationship_data_status=RelationshipDataStatus.PARTIAL,
                    )
                    session.add(offering)
                    session.flush()
                else:
                    offering.minimum_credits = parsed_course.credits_min
                    offering.maximum_credits = parsed_course.credits_max

                component_code, canonical_kind = _component(section_record.component)
                component_type = session.scalar(
                    select(ComponentType).where(ComponentType.code == component_code)
                )
                if component_type is None:
                    component_type = ComponentType(
                        code=component_code,
                        name=section_record.component,
                        canonical_kind=canonical_kind,
                    )
                    session.add(component_type)
                    session.flush()
                offering_component = session.scalar(
                    select(OfferingComponent).where(
                        OfferingComponent.course_offering_id == offering.id,
                        OfferingComponent.component_type_id == component_type.id,
                        OfferingComponent.source_code == component_code,
                    )
                )
                if offering_component is None:
                    offering_component = OfferingComponent(
                        course_offering=offering,
                        component_type=component_type,
                        source_code=component_code,
                        display_name=section_record.component,
                        minimum_required=1,
                        maximum_allowed=1,
                    )
                    session.add(offering_component)
                    session.flush()

                section = session.scalar(
                    select(Section).where(
                        Section.academic_term_id == term.id,
                        Section.crn == section_record.crn,
                    )
                )
                if section is None:
                    section = Section(
                        academic_term=term,
                        course_offering=offering,
                        offering_component=offering_component,
                        source_identifier=section_record.source_id,
                        crn=section_record.crn,
                        section_code=section_record.number,
                        first_seen_import_run=run,
                        last_seen_import_run=run,
                    )
                    session.add(section)
                    inserted += 1
                else:
                    section.course_offering = offering
                    section.offering_component = offering_component
                    section.section_code = section_record.number
                    section.last_seen_import_run = run
                    updated += 1
                section.source_component_code = component_code
                section.instruction_method = section_record.instructional_method
                section.campus = section_record.campus
                section.maximum_enrollment = section_record.maximum_enrollment
                section.status = SectionStatus.ACTIVE
                section.is_active = True
                section.inactive_at = None
                section.notes = section_record.notes
                section.meeting_times.clear()
                section.instructor_links.clear()
                session.flush()
                for parsed_meeting in section_record.meetings:
                    meeting = MeetingTime(
                        source_fingerprint=_fingerprint(parsed_meeting),
                        meeting_type=parsed_meeting.meeting_type,
                        start_date=parsed_meeting.start_date,
                        end_date=parsed_meeting.end_date,
                        start_time=parsed_meeting.start_time,
                        end_time=parsed_meeting.end_time,
                        building=parsed_meeting.building,
                        room=parsed_meeting.room,
                        is_asynchronous=parsed_meeting.is_asynchronous,
                        is_arranged=parsed_meeting.is_arranged,
                    )
                    meeting.days.extend(MeetingDay(day_of_week=day) for day in parsed_meeting.days)
                    section.meeting_times.append(meeting)
                    meetings_imported += 1
                for order, parsed_instructor in enumerate(section_record.instructors):
                    if not parsed_instructor.display_name:
                        continue
                    normalized = " ".join(parsed_instructor.display_name.casefold().split())
                    instructor = session.scalar(
                        select(Instructor).where(Instructor.normalized_name == normalized)
                    )
                    if instructor is None:
                        instructor = Instructor(
                            source_identifier=parsed_instructor.source_id,
                            display_name=parsed_instructor.display_name,
                            normalized_name=normalized,
                        )
                        session.add(instructor)
                    section.instructor_links.append(
                        SectionInstructor(instructor=instructor, is_primary=order == 0, display_order=order)
                    )
                if section_record.skipped_meeting_rows:
                    warnings.append(
                        f"CRN {section_record.crn}: skipped {section_record.skipped_meeting_rows} unusable meeting row(s)"
                    )
                seen_crns.add(section_record.crn)
                imported += 1
                session.flush()
                if fail_after_sections is not None and imported >= fail_after_sections:
                    raise RuntimeError("Injected fixture import failure")

            active_sections = session.scalars(
                select(Section).where(
                    Section.academic_term_id == term.id,
                    Section.is_active.is_(True),
                )
            ).all()
            deactivated = 0
            for section in active_sections:
                if section.crn not in seen_crns:
                    section.is_active = False
                    section.inactive_at = now
                    deactivated += 1

            run.status = ImportStatus.SUCCEEDED
            run.completed_at = now
            run.records_read = sections_seen
            run.records_inserted = inserted
            run.records_updated = updated
            run.records_deactivated = deactivated
            run.records_rejected = skipped + dataset.malformed_records
            run.courses_seen = courses_seen
            run.sections_seen = sections_seen
            run.sections_imported = imported
            run.sections_skipped = skipped
            run.meetings_imported = meetings_imported
            run.malformed_records = dataset.malformed_records
            run.warning_details = warnings or None
            term.last_successful_import_run = run
            term.is_published = True
            session.flush()
    except Exception as error:
        run.status = ImportStatus.FAILED
        run.completed_at = now
        run.error_summary = type(error).__name__
        run.courses_seen = courses_seen
        run.sections_seen = sections_seen
        run.sections_imported = 0
        run.sections_skipped = skipped
        run.meetings_imported = 0
        run.malformed_records = dataset.malformed_records
        session.flush()
        raise

    return ImportSummary(
        run_id=run.id,
        term_id=term.id,
        term_code=term.source_identifier,
        courses_seen=courses_seen,
        sections_seen=sections_seen,
        sections_imported=imported,
        sections_skipped=skipped,
        meetings_imported=meetings_imported,
        malformed_records=dataset.malformed_records,
        sections_deactivated=deactivated,
    )
