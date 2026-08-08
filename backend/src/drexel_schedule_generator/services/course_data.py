from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from datetime import datetime

from drexel_schedule_generator.db.models import AcademicTerm, Course, CourseOffering, ImportRun, ImportStatus, MeetingTime, OfferingComponent, Section, SectionInstructor, Subject
from drexel_schedule_generator.schemas.course_data import CoursePageResponse, CourseResponse, FreshnessResponse, MeetingResponse, SectionResponse, TermResponse


def list_terms(session: Session) -> list[TermResponse]:
    terms = session.scalars(
        select(AcademicTerm)
        .where(AcademicTerm.is_published.is_(True))
        .options(selectinload(AcademicTerm.last_successful_import_run))
        .order_by(AcademicTerm.source_identifier.desc())
    ).all()
    return [
        TermResponse(
            id=term.id,
            source_code=term.source_identifier,
            name=term.name,
            active=term.is_published,
            latest_successful_import_at=term.last_successful_import_run.completed_at if term.last_successful_import_run else None,
        )
        for term in terms
    ]


def _schedulable_section_query(term_id: int):
    return (
        select(Section)
        .join(MeetingTime)
        .where(
            Section.academic_term_id == term_id,
            Section.is_active.is_(True),
            or_(
                (MeetingTime.start_time.is_not(None) & MeetingTime.end_time.is_not(None) & MeetingTime.days.any()),
                MeetingTime.is_asynchronous.is_(True),
                MeetingTime.is_arranged.is_(True),
            ),
        )
        .distinct()
    )


def search_courses(
    session: Session,
    term_id: int,
    *,
    search: str | None,
    subject: str | None,
    number: str | None,
    title: str | None,
    page: int,
    page_size: int,
) -> CoursePageResponse:
    schedulable_offering_ids = _schedulable_section_query(term_id).with_only_columns(Section.course_offering_id)
    query = (
        select(CourseOffering)
        .join(Course)
        .join(Subject)
        .where(
            CourseOffering.academic_term_id == term_id,
            CourseOffering.id.in_(schedulable_offering_ids),
        )
        .options(
            selectinload(CourseOffering.course).selectinload(Course.subject),
            selectinload(CourseOffering.sections).selectinload(Section.meeting_times).selectinload(MeetingTime.days),
            selectinload(CourseOffering.sections).selectinload(Section.offering_component).selectinload(OfferingComponent.component_type),
        )
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Subject.code.ilike(pattern),
                Course.course_number.ilike(pattern),
                Course.title.ilike(pattern),
                func.concat(Subject.code, " ", Course.course_number).ilike(pattern),
            )
        )
    if subject:
        query = query.where(Subject.code.ilike(subject.strip()))
    if number:
        query = query.where(Course.course_number.ilike(f"%{number.strip()}%"))
    if title:
        query = query.where(Course.title.ilike(f"%{title.strip()}%"))
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = session.scalar(count_query) or 0
    offerings = session.scalars(
        query.order_by(Subject.code, Course.course_number, Course.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items: list[CourseResponse] = []
    for offering in offerings:
        active = [section for section in offering.sections if section.is_active and any((meeting.start_time and meeting.end_time and meeting.days) or meeting.is_asynchronous or meeting.is_arranged for meeting in section.meeting_times)]
        components = sorted({section.offering_component.component_type.canonical_kind.value for section in active})
        delivery_modes = sorted({_delivery_mode(section) for section in active})
        items.append(
            CourseResponse(
                id=offering.course.id,
                subject=offering.course.subject.code,
                number=offering.course.course_number,
                title=offering.title_override or offering.course.title,
                minimum_credits=offering.minimum_credits,
                maximum_credits=offering.maximum_credits,
                schedulable_section_count=len(active),
                component_types=components,
                delivery_modes=delivery_modes,
                has_saturday_sections=any(
                    day.day_of_week == 6
                    for section in active
                    for meeting in section.meeting_times
                    for day in meeting.days
                ),
            )
        )
    return CoursePageResponse(items=items, page=page, page_size=page_size, total=total)


def serialize_section(section: Section, alternatives: list[Section] | None = None) -> SectionResponse:
    alternatives = alternatives or [section]
    meetings = [
        MeetingResponse(
            days=sorted(day.day_of_week for day in meeting.days),
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            start_date=meeting.start_date,
            end_date=meeting.end_date,
            meeting_type=meeting.meeting_type,
            is_asynchronous=meeting.is_asynchronous,
            is_arranged=meeting.is_arranged,
        )
        for meeting in section.meeting_times
        if (meeting.start_time is not None and meeting.end_time is not None and meeting.days) or meeting.is_asynchronous or meeting.is_arranged
    ]
    return SectionResponse(
        id=section.id,
        subject=section.course_offering.course.subject.code,
        course_number=section.course_offering.course.course_number,
        crn=section.crn or "",
        section_number=section.section_code,
        component=section.offering_component.component_type.canonical_kind.value,
        instructors=[link.instructor.display_name for link in sorted(section.instructor_links, key=lambda item: item.display_order)],
        meetings=meetings,
        campus=section.campus,
        instructional_method=section.instruction_method,
        maximum_enrollment=section.maximum_enrollment,
        alternative_section_numbers=[item.section_code for item in alternatives],
        alternative_crns=[item.crn or "" for item in alternatives],
    )


def _delivery_mode(section: Section) -> str:
    method = (section.instruction_method or "").casefold()
    campus = (section.campus or "").casefold()
    if "online" in method or "online" in campus or any(meeting.is_asynchronous for meeting in section.meeting_times):
        return "online"
    return "face_to_face"


def course_sections(session: Session, term_id: int, course_id: int) -> list[SectionResponse] | None:
    offering = session.scalar(
        select(CourseOffering).where(CourseOffering.academic_term_id == term_id, CourseOffering.course_id == course_id)
    )
    if offering is None:
        return None
    sections = session.scalars(
        _schedulable_section_query(term_id)
        .where(Section.course_offering_id == offering.id)
        .options(
            selectinload(Section.meeting_times).selectinload(MeetingTime.days),
            selectinload(Section.offering_component).selectinload(OfferingComponent.component_type),
            selectinload(Section.instructor_links).selectinload(SectionInstructor.instructor),
        )
        .order_by(Section.section_code, Section.id)
    ).all()
    return [serialize_section(section) for section in sections]


def data_freshness(session: Session) -> FreshnessResponse:
    runs = session.scalars(
        select(ImportRun)
        .where(ImportRun.status == ImportStatus.SUCCEEDED, ImportRun.completed_at.is_not(None))
        .order_by(ImportRun.completed_at.desc())
    ).all()
    term_updates: dict[str, datetime] = {}
    for run in runs:
        term_updates.setdefault(run.source_term_identifier, run.completed_at)
    return FreshnessResponse(
        has_successful_import=bool(runs),
        latest_successful_import_at=runs[0].completed_at if runs else None,
        term_updates=term_updates,
    )
