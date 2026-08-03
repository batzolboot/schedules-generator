from pathlib import Path

import pytest

from drexel_schedule_generator.webtms.parser import (
    classify_course_number,
    parse_colleges,
    parse_course_links,
    parse_course_page,
    parse_subjects,
    parse_terms,
    sanitize_html,
    select_term_by_name,
    table_rows,
    webtms_route_paths,
)


def test_sanitizer_removes_auth_material_and_redacts_identity() -> None:
    html = """<html><body><script>secret</script><input type='hidden' name='csrf' value='abc'>
    <a href='https://example.test/page?token=abc'>Page</a>
    <span class='instructor'>Person Name</span><p>person@example.edu</p></body></html>"""
    sanitized = sanitize_html(html)
    assert "abc" not in sanitized
    assert "Person Name" not in sanitized
    assert "person@example.edu" not in sanitized
    assert "[REDACTED INSTRUCTOR]" in sanitized


def test_table_parser_preserves_all_meeting_rows() -> None:
    html = """<table><tr><th>Days</th><th>Time</th></tr>
    <tr><td>M</td><td>10:00</td></tr><tr><td>W</td><td>11:00</td></tr></table>"""
    assert table_rows(html, header_contains=("Days", "Time")) == (
        {"Days": "M", "Time": "10:00"},
        {"Days": "W", "Time": "11:00"},
    )


def test_route_extraction_ignores_query_values_and_external_paths() -> None:
    html = """<a onclick=\"go('/webtms_du/courseDetails/12345?token=bad')\">x</a>
    <a href='https://other.test/private'>other</a>"""
    assert webtms_route_paths(html) == ("/webtms_du/courseDetails/12345",)


def test_real_fixture_preserves_class_and_final_exam_meeting_rows() -> None:
    fixture = Path(__file__).parent / "fixtures" / "webtms" / "cs_172_lecture_with_final_exam.html"
    rows = table_rows(
        fixture.read_text(encoding="utf-8"),
        header_contains=("Start Date", "End Date", "Times", "Days", "Building", "Room"),
    )
    assert len(rows) == 2
    assert rows[0]["Days"] == "M"
    assert rows[1]["Times"].startswith("Final Exam:")

    _, course = parse_course_page(fixture.read_text(encoding="utf-8"))
    assert len(course.section.meetings) == 1
    assert course.section.meetings[0].meeting_type == "class"
    assert course.section.skipped_meeting_rows == 1


def test_online_asynchronous_fixture_is_preserved_without_invented_time() -> None:
    fixture = Path(__file__).parent / "fixtures" / "webtms" / "cs_504_online_asynchronous.html"
    _, course = parse_course_page(fixture.read_text(encoding="utf-8"))

    assert course.section.instructional_method == "Online-Asynchronous"
    assert course.section.campus == "Online"
    assert len(course.section.meetings) == 1
    meeting = course.section.meetings[0]
    assert meeting.is_asynchronous
    assert meeting.start_time is None
    assert meeting.end_time is None
    assert meeting.days == frozenset()
    assert course.section.skipped_meeting_rows == 0


def test_blank_meeting_row_is_not_treated_as_an_online_class() -> None:
    fixture = Path(__file__).parent / "fixtures" / "webtms" / "cs_504_online_asynchronous.html"
    html = fixture.read_text(encoding="utf-8").replace("Asynchronous", "")
    _, course = parse_course_page(html)

    assert course.section.meetings == ()
    assert course.section.skipped_meeting_rows == 1


def test_authenticated_navigation_discovery_and_required_course_query() -> None:
    html = """<a href='/webtms_du/collegesSubjects/202615'>Fall Quarter 2026–2027</a>
    <a href='/webtms_du/collegesSubjects/202616'>Fall Semester 2026-2027</a>"""
    terms = parse_terms(html)
    selected = select_term_by_name(terms, "Fall Quarter 26-27")
    assert selected.source_id == "202615"
    assert selected.calendar_type == "quarter"
    assert selected.academic_year == "2026-2027"

    college_html = "<a href='/webtms_du/collegesSubjects/202615?collCode=CI'>Computing</a>"
    assert parse_colleges(college_html, term_code="202615")[0].code == "CI"
    subject_html = "<a href='/webtms_du/courseList/CS'>Computer Science (CS)</a>"
    assert parse_subjects(subject_html, college_code="CI")[0].name == "Computer Science"

    list_html = """<table id='sortableTable'><tbody><tr>
    <td>CS</td><td>172</td><td>Lecture</td><td>Face-To-Face</td><td>A</td>
    <td><span title='Max enroll=30; Enroll=12'><a href='/webtms_du/courseDetails/40081'>40081</a></span></td><td>Programming II</td>
    </tr></tbody></table>"""
    link = parse_course_links(list_html)[0]
    assert link.path == "/webtms_du/courseDetails/40081?crseNumb=172"
    assert link.level == "undergraduate"
    assert link.maximum_enrollment == 30


def test_term_matching_rejects_absent_and_duplicate_names() -> None:
    html = """<a href='/webtms_du/collegesSubjects/1'>Fall Quarter 26-27</a>"""
    assert parse_terms(html) == ()
    with pytest.raises(ValueError, match="No authenticated"):
        select_term_by_name((), "Fall Quarter 2026-2027")
    duplicated = parse_terms("""<a href='/webtms_du/collegesSubjects/202615'>Fall Quarter 26-27</a>
    <a href='/webtms_du/collegesSubjects/202616'>Fall Quarter 2026–2027</a>""")
    with pytest.raises(ValueError, match="Multiple"):
        select_term_by_name(duplicated, "Fall Quarter 2026-2027")


def test_course_number_filter_is_conservative() -> None:
    assert classify_course_number("499") == "undergraduate"
    assert classify_course_number("500") == "graduate"
    assert classify_course_number("ABC") == "ambiguous"
