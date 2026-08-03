"""Pure, bounded conflict-free schedule generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class Meeting:
    days: frozenset[int]
    start_time: time
    end_time: time
    start_date: date | None = None
    end_date: date | None = None


@dataclass(frozen=True, slots=True)
class SectionOption:
    id: int
    term_id: int
    course_id: int
    subject: str
    course_number: str
    section_code: str
    component: str
    meetings: tuple[Meeting, ...]
    campus: str | None = None
    instructional_method: str | None = None
    instructors: tuple[str, ...] = ()
    equivalent_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class CourseOptions:
    id: int
    term_id: int
    component_groups: tuple[tuple[SectionOption, ...], ...]


@dataclass(frozen=True, slots=True)
class ScheduleMetrics:
    campus_days: int
    total_gap_minutes: int
    earliest_start: time | None
    latest_end: time | None
    total_meeting_minutes: int


@dataclass(frozen=True, slots=True)
class GeneratedSchedule:
    sections: tuple[SectionOption, ...]
    metrics: ScheduleMetrics


@dataclass(frozen=True, slots=True)
class GenerationResult:
    schedules: tuple[GeneratedSchedule, ...]
    total_valid_considered: int
    truncated: bool
    rejection_code: str | None = None
    rejection_message: str | None = None
    compatibility_limited: bool = True


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def meetings_overlap(left: Meeting, right: Meeting) -> bool:
    if not left.days.intersection(right.days):
        return False
    if (
        left.start_date is not None
        and left.end_date is not None
        and right.start_date is not None
        and right.end_date is not None
        and (left.end_date < right.start_date or right.end_date < left.start_date)
    ):
        return False
    return _minutes(left.start_time) < _minutes(right.end_time) and _minutes(right.start_time) < _minutes(left.end_time)


def sections_conflict(left: SectionOption, right: SectionOption) -> bool:
    if left.term_id != right.term_id:
        return True
    return any(meetings_overlap(a, b) for a in left.meetings for b in right.meetings)


def calculate_metrics(sections: tuple[SectionOption, ...]) -> ScheduleMetrics:
    meetings = [meeting for section in sections for meeting in section.meetings]
    earliest = min((meeting.start_time for meeting in meetings), key=_minutes) if meetings else None
    latest = max((meeting.end_time for meeting in meetings), key=_minutes) if meetings else None
    total_minutes = sum(
        (_minutes(meeting.end_time) - _minutes(meeting.start_time)) * len(meeting.days)
        for meeting in meetings
    )
    daily: dict[int, list[tuple[int, int]]] = {}
    for meeting in meetings:
        for day in meeting.days:
            daily.setdefault(day, []).append((_minutes(meeting.start_time), _minutes(meeting.end_time)))
    gap_minutes = 0
    for intervals in daily.values():
        intervals.sort()
        previous_end = intervals[0][1]
        for start, end in intervals[1:]:
            gap_minutes += max(0, start - previous_end)
            previous_end = max(previous_end, end)
    return ScheduleMetrics(
        campus_days=len(daily),
        total_gap_minutes=gap_minutes,
        earliest_start=earliest,
        latest_end=latest,
        total_meeting_minutes=total_minutes,
    )


def _ranking_key(schedule: GeneratedSchedule) -> tuple[object, ...]:
    metrics = schedule.metrics
    return (
        metrics.campus_days,
        metrics.total_gap_minutes,
        -_minutes(metrics.earliest_start) if metrics.earliest_start else 0,
        _minutes(metrics.latest_end) if metrics.latest_end else 0,
        tuple(section.id for section in schedule.sections),
    )


def _section_time_key(section: SectionOption) -> tuple[object, ...]:
    meetings = tuple(sorted(
        (
            tuple(sorted(meeting.days)),
            meeting.start_time,
            meeting.end_time,
            meeting.start_date.isoformat() if meeting.start_date else "",
            meeting.end_date.isoformat() if meeting.end_date else "",
        )
        for meeting in section.meetings
    ))
    return section.term_id, section.course_id, section.component, section.instructional_method, section.campus, meetings


def consolidate_equivalent_sections(group: tuple[SectionOption, ...]) -> tuple[SectionOption, ...]:
    """Collapse same-course/component meeting patterns before backtracking."""
    grouped: dict[tuple[object, ...], list[SectionOption]] = {}
    for section in group:
        grouped.setdefault(_section_time_key(section), []).append(section)
    consolidated: list[SectionOption] = []
    for alternatives in grouped.values():
        alternatives.sort(key=lambda section: (section.section_code, section.id))
        representative = alternatives[0]
        consolidated.append(
            SectionOption(
                id=representative.id,
                term_id=representative.term_id,
                course_id=representative.course_id,
                subject=representative.subject,
                course_number=representative.course_number,
                section_code=representative.section_code,
                component=representative.component,
                meetings=representative.meetings,
                campus=representative.campus,
                instructional_method=representative.instructional_method,
                instructors=representative.instructors,
                equivalent_ids=tuple(section.id for section in alternatives),
            )
        )
    return tuple(sorted(consolidated, key=lambda section: section.id))


def generate_schedules(
    courses: tuple[CourseOptions, ...],
    *,
    maximum_results: int | None = None,
    exploration_limit: int = 100_000,
) -> GenerationResult:
    if not courses:
        return GenerationResult((), 0, False, "empty_selection", "Select at least one course.")
    term_ids = {course.term_id for course in courses}
    if len(term_ids) != 1:
        return GenerationResult((), 0, False, "mixed_terms", "All courses must belong to one term.")
    if maximum_results is not None and maximum_results < 1:
        raise ValueError("maximum_results must be positive")
    groups = [consolidate_equivalent_sections(group) for course in courses for group in course.component_groups]
    if not groups or any(not group for group in groups):
        return GenerationResult((), 0, False, "missing_components", "At least one required component has no schedulable sections.")
    groups.sort(key=lambda group: (len(group), tuple(section.id for section in group)))
    valid: list[GeneratedSchedule] = []
    seen: set[tuple[int, ...]] = set()
    explored = 0
    limit_hit = False

    def visit(index: int, selected: tuple[SectionOption, ...]) -> None:
        nonlocal explored, limit_hit
        if explored >= exploration_limit:
            limit_hit = True
            return
        if index == len(groups):
            explored += 1
            identifier = tuple(sorted(section.id for section in selected))
            if identifier not in seen:
                seen.add(identifier)
                ordered = tuple(sorted(selected, key=lambda section: section.id))
                valid.append(GeneratedSchedule(ordered, calculate_metrics(ordered)))
            return
        for candidate in groups[index]:
            explored += 1
            if explored >= exploration_limit:
                limit_hit = True
                return
            if any(sections_conflict(candidate, existing) for existing in selected):
                continue
            visit(index + 1, (*selected, candidate))
            if limit_hit:
                return

    visit(0, ())
    valid.sort(key=_ranking_key)
    truncated = limit_hit or (maximum_results is not None and len(valid) > maximum_results)
    selected_results = tuple(valid if maximum_results is None else valid[:maximum_results])
    if not selected_results:
        return GenerationResult(
            (),
            len(valid),
            limit_hit,
            "no_conflict_free_schedule",
            "No conflict-free combination satisfies every required component.",
        )
    return GenerationResult(selected_results, len(valid), truncated)
