from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from drexel_schedule_generator.db.models import Course, CourseOffering, MeetingTime, OfferingComponent, Section, SectionInstructor
from drexel_schedule_generator.domain.scheduling import CourseOptions, Meeting, SectionOption, generate_schedules
from drexel_schedule_generator.schemas.scheduling import GenerateScheduleResponse, GeneratedScheduleResponse, MetricsResponse

from .course_data import _delivery_mode, serialize_section

COMPATIBILITY_LIMITATION = "WebTMS does not provide authoritative component-link data for these fixtures; combinations are allowed across required component types of the same course. Verify the result in Drexel's official registration system."


class ScheduleRequestError(ValueError):
    pass


def generate_for_courses(
    session: Session,
    term_id: int,
    course_ids: list[int],
    maximum_results: int | None,
    delivery_preferences: dict[int, list[str]] | None = None,
) -> GenerateScheduleResponse:
    delivery_preferences = delivery_preferences or {}
    offerings = session.scalars(
        select(CourseOffering)
        .where(CourseOffering.academic_term_id == term_id, CourseOffering.course_id.in_(course_ids))
        .options(
            selectinload(CourseOffering.course).selectinload(Course.subject),
            selectinload(CourseOffering.sections).selectinload(Section.meeting_times).selectinload(MeetingTime.days),
            selectinload(CourseOffering.sections).selectinload(Section.offering_component).selectinload(OfferingComponent.component_type),
            selectinload(CourseOffering.sections).selectinload(Section.instructor_links).selectinload(SectionInstructor.instructor),
        )
    ).all()
    if len(offerings) != len(course_ids):
        raise ScheduleRequestError("One or more courses do not belong to the requested term.")
    if not set(delivery_preferences).issubset(course_ids):
        raise ScheduleRequestError("Delivery preferences may only reference selected courses.")
    domain_courses: list[CourseOptions] = []
    section_models: dict[int, Section] = {}
    for offering in offerings:
        grouped: dict[str, list[SectionOption]] = {}
        for section in offering.sections:
            valid_meetings = [meeting for meeting in section.meeting_times if meeting.start_time and meeting.end_time and meeting.days]
            special_meetings = [meeting for meeting in section.meeting_times if meeting.is_asynchronous or meeting.is_arranged]
            if not section.is_active or not (valid_meetings or special_meetings):
                continue
            component = section.offering_component.component_type.canonical_kind.value
            option = SectionOption(
                id=section.id,
                term_id=term_id,
                course_id=offering.course_id,
                subject=offering.course.subject.code,
                course_number=offering.course.course_number,
                section_code=section.section_code,
                component=component,
                meetings=tuple(
                    Meeting(
                        days=frozenset(day.day_of_week for day in meeting.days),
                        start_time=meeting.start_time,
                        end_time=meeting.end_time,
                        start_date=meeting.start_date,
                        end_date=meeting.end_date,
                    )
                    for meeting in valid_meetings
                ),
                campus=section.campus,
                instructional_method=section.instruction_method,
                instructors=tuple(link.instructor.display_name for link in section.instructor_links),
            )
            grouped.setdefault(component, []).append(option)
            section_models[section.id] = section
        allowed_modes = set(delivery_preferences.get(offering.course_id, ("online", "face_to_face")))
        for component, options in grouped.items():
            available_modes = {_delivery_mode(section_models[option.id]) for option in options}
            if available_modes == {"online", "face_to_face"}:
                grouped[component] = [option for option in options if _delivery_mode(section_models[option.id]) in allowed_modes]
        domain_courses.append(
            CourseOptions(
                id=offering.course_id,
                term_id=term_id,
                component_groups=tuple(tuple(sorted(options, key=lambda item: item.id)) for _, options in sorted(grouped.items())),
            )
        )
    result = generate_schedules(tuple(domain_courses), maximum_results=maximum_results)
    schedules = [
        GeneratedScheduleResponse(
            sections=[serialize_section(section_models[option.id], [section_models[item_id] for item_id in option.equivalent_ids or (option.id,)]) for option in schedule.sections],
            metrics=MetricsResponse(
                campus_days=schedule.metrics.campus_days,
                total_gap_minutes=schedule.metrics.total_gap_minutes,
                earliest_start=schedule.metrics.earliest_start,
                latest_end=schedule.metrics.latest_end,
                total_meeting_minutes=schedule.metrics.total_meeting_minutes,
            ),
        )
        for schedule in result.schedules
    ]
    no_results = None
    if result.rejection_code:
        no_results = {"code": result.rejection_code, "message": result.rejection_message or "No schedules found."}
    return GenerateScheduleResponse(
        schedules=schedules,
        total_valid_considered=result.total_valid_considered,
        truncated=result.truncated,
        no_results=no_results,
        compatibility_limitation=COMPATIBILITY_LIMITATION,
    )
