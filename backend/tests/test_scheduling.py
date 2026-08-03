from __future__ import annotations

from datetime import date, time

from drexel_schedule_generator.domain.scheduling import CourseOptions, Meeting, SectionOption, generate_schedules, meetings_overlap, sections_conflict


def meeting(days: set[int], start: tuple[int, int], end: tuple[int, int]) -> Meeting:
    return Meeting(frozenset(days), time(*start), time(*end), date(2026, 9, 1), date(2026, 12, 1))


def section(identifier: int, course: int, component: str, meetings: tuple[Meeting, ...], term: int = 1) -> SectionOption:
    return SectionOption(identifier, term, course, "CS", str(course), str(identifier), component, meetings)


def course(identifier: int, *groups: tuple[SectionOption, ...], term: int = 1) -> CourseOptions:
    return CourseOptions(identifier, term, groups)


def test_overlap_rules_and_different_days() -> None:
    base = meeting({1}, (9, 0), (10, 0))
    assert not meetings_overlap(base, meeting({1}, (10, 0), (11, 0)))
    assert meetings_overlap(base, meeting({1}, (9, 30), (10, 30)))
    assert meetings_overlap(base, meeting({1}, (8, 0), (11, 0)))
    assert not meetings_overlap(base, meeting({2}, (9, 0), (10, 0)))


def test_non_overlapping_date_ranges_do_not_conflict() -> None:
    first = Meeting(frozenset({1}), time(9), time(10), date(2026, 1, 1), date(2026, 2, 1))
    second = Meeting(frozenset({1}), time(9), time(10), date(2026, 3, 1), date(2026, 4, 1))
    assert not meetings_overlap(first, second)


def test_every_meeting_row_is_checked() -> None:
    left = section(1, 1, "lecture", (meeting({1}, (8, 0), (9, 0)), meeting({3}, (11, 0), (12, 0))))
    right = section(2, 2, "lecture", (meeting({3}, (11, 30), (12, 30)),))
    assert sections_conflict(left, right)


def test_lecture_and_lab_combinations_and_duplicate_prevention() -> None:
    lecture = section(1, 1, "lecture", (meeting({1}, (9, 0), (10, 0)),))
    labs = (
        section(2, 1, "lab", (meeting({2}, (9, 0), (10, 0)),)),
        section(3, 1, "lab", (meeting({3}, (9, 0), (10, 0)),)),
    )
    result = generate_schedules((course(1, (lecture,), labs),))
    assert len(result.schedules) == 2
    assert {tuple(item.id for item in schedule.sections) for schedule in result.schedules} == {(1, 2), (1, 3)}


def test_same_component_and_meeting_pattern_is_consolidated_before_generation() -> None:
    lecture = section(1, 1, "lecture", (meeting({1}, (9, 0), (10, 0)),))
    lab_066 = section(2, 1, "lab", (meeting({2}, (11, 0), (12, 50)),))
    lab_067 = section(3, 1, "lab", (meeting({2}, (11, 0), (12, 50)),))

    result = generate_schedules((course(1, (lecture,), (lab_066, lab_067)),))

    assert len(result.schedules) == 1
    assert result.total_valid_considered == 1
    assert result.schedules[0].sections[1].equivalent_ids == (2, 3)


def test_multiple_courses_generate_only_non_conflicting_results() -> None:
    first = section(1, 1, "lecture", (meeting({1}, (9, 0), (10, 0)),))
    conflict = section(2, 2, "lecture", (meeting({1}, (9, 30), (10, 30)),))
    valid = section(3, 2, "lecture", (meeting({1}, (10, 0), (11, 0)),))
    result = generate_schedules((course(1, (first,)), course(2, (conflict, valid))))
    assert [section.id for section in result.schedules[0].sections] == [1, 3]


def test_no_valid_schedule_has_structured_reason() -> None:
    first = section(1, 1, "lecture", (meeting({1}, (9, 0), (10, 0)),))
    second = section(2, 2, "lecture", (meeting({1}, (9, 0), (10, 0)),))
    result = generate_schedules((course(1, (first,)), course(2, (second,))))
    assert result.schedules == ()
    assert result.rejection_code == "no_conflict_free_schedule"


def test_term_isolation() -> None:
    first = section(1, 1, "lecture", (meeting({1}, (9, 0), (10, 0)),), term=1)
    second = section(2, 2, "lecture", (meeting({2}, (9, 0), (10, 0)),), term=2)
    result = generate_schedules((course(1, (first,), term=1), course(2, (second,), term=2)))
    assert result.rejection_code == "mixed_terms"


def test_deterministic_ranking_prefers_days_then_gaps_then_later_start() -> None:
    spread = section(1, 1, "lecture", (meeting({1, 2}, (8, 0), (9, 0)),))
    compact = section(2, 1, "lecture", (meeting({1}, (10, 0), (11, 0)),))
    fixed = section(3, 2, "lecture", (meeting({1}, (12, 0), (13, 0)),))
    result = generate_schedules((course(1, (spread, compact)), course(2, (fixed,))))
    assert [section.id for section in result.schedules[0].sections] == [2, 3]
    assert result.schedules[0].metrics.campus_days == 1
    assert result.schedules[0].metrics.total_gap_minutes == 60


def test_maximum_result_is_enforced() -> None:
    options = tuple(section(i, 1, "lecture", (meeting({i}, (9, 0), (10, 0)),)) for i in range(1, 6))
    result = generate_schedules((course(1, options),), maximum_results=2)
    assert len(result.schedules) == 2
    assert result.total_valid_considered == 5
    assert result.truncated


def test_asynchronous_section_generates_without_time_conflicts_or_fake_metrics() -> None:
    online = section(20, 1, "lecture", ())
    result = generate_schedules((course(1, (online,)),))

    assert len(result.schedules) == 1
    assert result.schedules[0].metrics.campus_days == 0
    assert result.schedules[0].metrics.earliest_start is None
    assert result.schedules[0].metrics.latest_end is None
