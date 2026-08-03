from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import inspect, select
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
    RelationshipRuleType,
    Section,
    SectionInstructor,
    SectionRelationshipOption,
    SectionRelationshipRule,
    SectionStatus,
    Subject,
)


def test_initial_migration_created_mvp_tables(db_session: Session) -> None:
    table_names = set(inspect(db_session.get_bind()).get_table_names())

    assert {
        "academic_terms",
        "component_types",
        "course_offerings",
        "courses",
        "import_runs",
        "instructors",
        "meeting_days",
        "meeting_times",
        "offering_components",
        "section_instructors",
        "section_relationship_options",
        "section_relationship_rules",
        "sections",
        "subjects",
    } <= table_names


def test_course_section_meeting_and_instructor_relationships(db_session: Session) -> None:
    term = AcademicTerm(source_identifier="202645", name="Fall Quarter 2026")
    subject = Subject(code="CHEM", name="Chemistry")
    course = Course(
        subject=subject,
        course_number="101",
        title="General Chemistry I",
        source_identifier="CHEM-101",
    )
    offering = CourseOffering(
        academic_term=term,
        course=course,
        relationship_data_status=RelationshipDataStatus.COMPLETE,
    )
    lecture_type = ComponentType(
        code="LEC", name="Lecture", canonical_kind=CanonicalComponentKind.LECTURE
    )
    lecture_component = OfferingComponent(
        course_offering=offering,
        component_type=lecture_type,
        source_code="LEC",
        minimum_required=1,
        maximum_allowed=1,
    )
    lab_type = ComponentType(
        code="LAB", name="Laboratory", canonical_kind=CanonicalComponentKind.LAB
    )
    lab_component = OfferingComponent(
        course_offering=offering,
        component_type=lab_type,
        source_code="LAB",
        minimum_required=1,
        maximum_allowed=1,
        selection_order=1,
    )
    db_session.add_all([term, subject, lecture_type, lab_type])
    db_session.flush()

    import_run = ImportRun(
        academic_term=term,
        status=ImportStatus.SUCCEEDED,
        source_name="synthetic_fixture",
        source_term_identifier=term.source_identifier,
        completed_at=datetime.now(UTC),
    )
    db_session.add(import_run)
    db_session.flush()
    term.last_successful_import_run = import_run
    term.is_published = True

    section = Section(
        academic_term=term,
        course_offering=offering,
        offering_component=lecture_component,
        source_identifier="section-12345",
        crn="12345",
        section_code="001",
        status=SectionStatus.ACTIVE,
        first_seen_import_run=import_run,
        last_seen_import_run=import_run,
    )
    meeting = MeetingTime(
        section=section,
        source_fingerprint="a" * 64,
        start_date=date(2026, 9, 21),
        end_date=date(2026, 12, 12),
        start_time=time(9, 0),
        end_time=time(9, 50),
        building="Stratton",
        room="113",
    )
    meeting.days.extend([MeetingDay(day_of_week=1), MeetingDay(day_of_week=3)])
    instructor = Instructor(
        source_identifier="instructor-1",
        display_name="Ada Lovelace",
        normalized_name="ada lovelace",
    )
    section.instructor_links.append(
        SectionInstructor(instructor=instructor, is_primary=True)
    )
    lab_section = Section(
        academic_term=term,
        course_offering=offering,
        offering_component=lab_component,
        source_identifier="section-12401",
        crn="12401",
        section_code="061",
        status=SectionStatus.ACTIVE,
        first_seen_import_run=import_run,
        last_seen_import_run=import_run,
    )
    compatibility_rule = SectionRelationshipRule(
        course_offering=offering,
        source_section=section,
        target_component=lab_component,
        rule_type=RelationshipRuleType.COMPATIBLE_ONLY,
        source_identifier="lecture-001-labs",
    )
    compatibility_rule.options.append(
        SectionRelationshipOption(target_section=lab_section)
    )
    db_session.add_all([section, lab_section, compatibility_rule])
    db_session.flush()
    db_session.expire_all()

    stored = db_session.scalar(select(Section).where(Section.crn == "12345"))

    assert stored is not None
    assert stored.course_offering.course.course_number == "101"
    assert stored.offering_component.component_type.code == "LEC"
    assert {day.day_of_week for day in stored.meeting_times[0].days} == {1, 3}
    assert stored.meeting_times[0].start_time == time(9, 0)
    assert stored.instructor_links[0].instructor.display_name == "Ada Lovelace"
    assert stored.relationship_rules[0].options[0].target_section.crn == "12401"
    assert stored.created_at.tzinfo is not None


def test_failed_import_does_not_change_section_activity(db_session: Session) -> None:
    term = AcademicTerm(source_identifier="202655", name="Winter Quarter 2027")
    subject = Subject(code="CS", name="Computer Science")
    course = Course(subject=subject, course_number="171", title="Programming I")
    offering = CourseOffering(academic_term=term, course=course)
    component_type = ComponentType(
        code="LAB", name="Laboratory", canonical_kind=CanonicalComponentKind.LAB
    )
    component = OfferingComponent(
        course_offering=offering,
        component_type=component_type,
        source_code="LAB",
    )
    db_session.add_all([term, subject, component_type])
    db_session.flush()
    successful_run = ImportRun(
        academic_term=term,
        status=ImportStatus.SUCCEEDED,
        source_name="synthetic_fixture",
        source_term_identifier=term.source_identifier,
        completed_at=datetime.now(UTC),
    )
    db_session.add(successful_run)
    db_session.flush()
    section = Section(
        academic_term=term,
        course_offering=offering,
        offering_component=component,
        crn="54321",
        section_code="061",
        status=SectionStatus.ACTIVE,
        first_seen_import_run=successful_run,
        last_seen_import_run=successful_run,
    )
    db_session.add(section)
    db_session.flush()

    failed_run = ImportRun(
        academic_term=term,
        status=ImportStatus.FAILED,
        source_name="synthetic_fixture",
        source_term_identifier=term.source_identifier,
        completed_at=datetime.now(UTC),
        error_summary="Fixture validation failed",
    )
    db_session.add(failed_run)
    db_session.flush()
    db_session.refresh(section)

    assert section.is_active is True
    assert section.inactive_at is None
    assert section.last_seen_import_run_id == successful_run.id

    later_successful_run = ImportRun(
        academic_term=term,
        status=ImportStatus.SUCCEEDED,
        source_name="synthetic_fixture",
        source_term_identifier=term.source_identifier,
        completed_at=datetime.now(UTC),
    )
    db_session.add(later_successful_run)
    db_session.flush()

    # A future importer performs this transition only after its import succeeds.
    section.is_active = False
    section.inactive_at = datetime.now(UTC)
    term.last_successful_import_run = later_successful_run
    db_session.flush()
    db_session.refresh(section)

    assert section.is_active is False
    assert section.inactive_at is not None
    assert section.inactive_at.tzinfo is not None
    assert section.last_seen_import_run_id == successful_run.id
