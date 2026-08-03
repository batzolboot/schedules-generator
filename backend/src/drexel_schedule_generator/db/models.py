from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drexel_schedule_generator.db.base import Base


class ImportStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RelationshipDataStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class CanonicalComponentKind(StrEnum):
    LECTURE = "lecture"
    LAB = "lab"
    RECITATION = "recitation"
    OTHER = "other"


class SectionStatus(StrEnum):
    ACTIVE = "active"
    CANCELED = "canceled"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class RelationshipRuleType(StrEnum):
    REQUIRES_ONE_OF = "requires_one_of"
    COMPATIBLE_ONLY = "compatible_only"


def enum_type(enum_class: type[StrEnum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda values: [value.value for value in values],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AcademicTerm(TimestampMixin, Base):
    __tablename__ = "academic_terms"
    __table_args__ = (
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
            name="valid_date_range",
        ),
        Index(
            "ix_academic_terms_published",
            "is_published",
            postgresql_where=text("is_published = true"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_identifier: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    last_successful_import_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "import_runs.id",
            name="fk_academic_terms_last_successful_import_run_id_import_runs",
            use_alter=True,
        ),
    )

    offerings: Mapped[list[CourseOffering]] = relationship(back_populates="academic_term")
    sections: Mapped[list[Section]] = relationship(back_populates="academic_term")
    import_runs: Mapped[list[ImportRun]] = relationship(
        back_populates="academic_term",
        foreign_keys="ImportRun.academic_term_id",
    )
    last_successful_import_run: Mapped[ImportRun | None] = relationship(
        foreign_keys=[last_successful_import_run_id], post_update=True
    )


class ImportRun(Base):
    __tablename__ = "import_runs"
    __table_args__ = (
        CheckConstraint(
            "records_read IS NULL OR records_read >= 0", name="records_read_nonnegative"
        ),
        CheckConstraint(
            "records_inserted IS NULL OR records_inserted >= 0",
            name="records_inserted_nonnegative",
        ),
        CheckConstraint(
            "records_updated IS NULL OR records_updated >= 0",
            name="records_updated_nonnegative",
        ),
        CheckConstraint(
            "records_deactivated IS NULL OR records_deactivated >= 0",
            name="records_deactivated_nonnegative",
        ),
        CheckConstraint(
            "records_rejected IS NULL OR records_rejected >= 0",
            name="records_rejected_nonnegative",
        ),
        CheckConstraint(
            "status = 'running' OR completed_at IS NOT NULL",
            name="completed_when_finished",
        ),
        Index("ix_import_runs_term_started", "academic_term_id", text("started_at DESC")),
        Index(
            "ix_import_runs_term_status_completed",
            "academic_term_id",
            "status",
            text("completed_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    academic_term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id"))
    status: Mapped[ImportStatus] = mapped_column(enum_type(ImportStatus, "import_status"))
    source_name: Mapped[str] = mapped_column(String(100))
    source_term_identifier: Mapped[str] = mapped_column(String(64))
    source_data_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fixture_name: Mapped[str | None] = mapped_column(String(255))
    source_checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_read: Mapped[int | None] = mapped_column(Integer)
    records_inserted: Mapped[int | None] = mapped_column(Integer)
    records_updated: Mapped[int | None] = mapped_column(Integer)
    records_deactivated: Mapped[int | None] = mapped_column(Integer)
    records_rejected: Mapped[int | None] = mapped_column(Integer)
    courses_seen: Mapped[int | None] = mapped_column(Integer)
    sections_seen: Mapped[int | None] = mapped_column(Integer)
    sections_imported: Mapped[int | None] = mapped_column(Integer)
    sections_skipped: Mapped[int | None] = mapped_column(Integer)
    meetings_imported: Mapped[int | None] = mapped_column(Integer)
    malformed_records: Mapped[int | None] = mapped_column(Integer)
    warning_details: Mapped[dict | list | None] = mapped_column(JSONB)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    academic_term: Mapped[AcademicTerm] = relationship(
        back_populates="import_runs", foreign_keys=[academic_term_id]
    )


class Subject(TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        Index(
            "uq_subjects_source_identifier",
            "source_identifier",
            unique=True,
            postgresql_where=text("source_identifier IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str | None] = mapped_column(String(160))
    source_identifier: Mapped[str | None] = mapped_column(String(128))

    courses: Mapped[list[Course]] = relationship(back_populates="subject")


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("subject_id", "course_number"),
        Index(
            "uq_courses_source_identifier",
            "source_identifier",
            unique=True,
            postgresql_where=text("source_identifier IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    course_number: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    source_identifier: Mapped[str | None] = mapped_column(String(128))

    subject: Mapped[Subject] = relationship(back_populates="courses")
    offerings: Mapped[list[CourseOffering]] = relationship(back_populates="course")

Index("ix_courses_title_lower", func.lower(Course.title))


class CourseOffering(TimestampMixin, Base):
    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint("academic_term_id", "course_id"),
        Index(
            "uq_course_offerings_term_source",
            "academic_term_id",
            "source_identifier",
            unique=True,
            postgresql_where=text("source_identifier IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    academic_term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    source_identifier: Mapped[str | None] = mapped_column(String(128))
    title_override: Mapped[str | None] = mapped_column(String(255))
    minimum_credits: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    maximum_credits: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    relationship_data_status: Mapped[RelationshipDataStatus] = mapped_column(
        enum_type(RelationshipDataStatus, "relationship_data_status"),
        default=RelationshipDataStatus.UNKNOWN,
        server_default=RelationshipDataStatus.UNKNOWN.value,
    )

    academic_term: Mapped[AcademicTerm] = relationship(back_populates="offerings")
    course: Mapped[Course] = relationship(back_populates="offerings")
    components: Mapped[list[OfferingComponent]] = relationship(
        back_populates="course_offering", cascade="all, delete-orphan"
    )
    sections: Mapped[list[Section]] = relationship(back_populates="course_offering")
    relationship_rules: Mapped[list[SectionRelationshipRule]] = relationship(
        back_populates="course_offering", cascade="all, delete-orphan"
    )


class ComponentType(Base):
    __tablename__ = "component_types"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    canonical_kind: Mapped[CanonicalComponentKind] = mapped_column(
        enum_type(CanonicalComponentKind, "canonical_component_kind")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    offering_components: Mapped[list[OfferingComponent]] = relationship(
        back_populates="component_type"
    )


class OfferingComponent(TimestampMixin, Base):
    __tablename__ = "offering_components"
    __table_args__ = (
        UniqueConstraint("course_offering_id", "component_type_id", "source_code"),
        CheckConstraint("minimum_required >= 0", name="minimum_required_nonnegative"),
        CheckConstraint(
            "maximum_allowed >= minimum_required", name="valid_selection_range"
        ),
        CheckConstraint("selection_order >= 0", name="selection_order_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    course_offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"))
    component_type_id: Mapped[int] = mapped_column(ForeignKey("component_types.id"))
    source_code: Mapped[str | None] = mapped_column(String(40))
    display_name: Mapped[str | None] = mapped_column(String(100))
    minimum_required: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    maximum_allowed: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    selection_order: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")

    course_offering: Mapped[CourseOffering] = relationship(back_populates="components")
    component_type: Mapped[ComponentType] = relationship(back_populates="offering_components")
    sections: Mapped[list[Section]] = relationship(back_populates="offering_component")


class Section(TimestampMixin, Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint(
            "course_offering_id", "offering_component_id", "section_code"
        ),
        CheckConstraint(
            "(is_active AND inactive_at IS NULL) OR "
            "(NOT is_active AND inactive_at IS NOT NULL)",
            name="active_matches_inactive_at",
        ),
        CheckConstraint(
            "maximum_enrollment IS NULL OR maximum_enrollment >= 0",
            name="maximum_enrollment_nonnegative",
        ),
        Index(
            "uq_sections_term_source",
            "academic_term_id",
            "source_identifier",
            unique=True,
            postgresql_where=text("source_identifier IS NOT NULL"),
        ),
        Index(
            "uq_sections_term_crn",
            "academic_term_id",
            "crn",
            unique=True,
            postgresql_where=text("crn IS NOT NULL"),
        ),
        Index("ix_sections_offering_active", "course_offering_id", "is_active"),
        Index("ix_sections_component_active", "offering_component_id", "is_active"),
        Index("ix_sections_term_active", "academic_term_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    academic_term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id"))
    course_offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"))
    offering_component_id: Mapped[int] = mapped_column(ForeignKey("offering_components.id"))
    source_identifier: Mapped[str | None] = mapped_column(String(128))
    crn: Mapped[str | None] = mapped_column(String(32))
    section_code: Mapped[str] = mapped_column(String(32))
    source_component_code: Mapped[str | None] = mapped_column(String(40))
    instruction_method: Mapped[str | None] = mapped_column(String(80))
    campus: Mapped[str | None] = mapped_column(String(120))
    maximum_enrollment: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[SectionStatus] = mapped_column(
        enum_type(SectionStatus, "section_status"),
        default=SectionStatus.UNKNOWN,
        server_default=SectionStatus.UNKNOWN.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    first_seen_import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"))
    last_seen_import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"), index=True)
    inactive_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    academic_term: Mapped[AcademicTerm] = relationship(back_populates="sections")
    course_offering: Mapped[CourseOffering] = relationship(back_populates="sections")
    offering_component: Mapped[OfferingComponent] = relationship(back_populates="sections")
    first_seen_import_run: Mapped[ImportRun] = relationship(
        foreign_keys=[first_seen_import_run_id]
    )
    last_seen_import_run: Mapped[ImportRun] = relationship(
        foreign_keys=[last_seen_import_run_id]
    )
    meeting_times: Mapped[list[MeetingTime]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )
    instructor_links: Mapped[list[SectionInstructor]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )
    relationship_rules: Mapped[list[SectionRelationshipRule]] = relationship(
        back_populates="source_section",
        cascade="all, delete-orphan",
        foreign_keys="SectionRelationshipRule.source_section_id",
    )
    relationship_options: Mapped[list[SectionRelationshipOption]] = relationship(
        back_populates="target_section",
        foreign_keys="SectionRelationshipOption.target_section_id",
    )


class Instructor(TimestampMixin, Base):
    __tablename__ = "instructors"
    __table_args__ = (
        Index(
            "uq_instructors_source_identifier",
            "source_identifier",
            unique=True,
            postgresql_where=text("source_identifier IS NOT NULL"),
        ),
        Index("ix_instructors_normalized_name", "normalized_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_identifier: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255))

    section_links: Mapped[list[SectionInstructor]] = relationship(
        back_populates="instructor", cascade="all, delete-orphan"
    )


class SectionInstructor(Base):
    __tablename__ = "section_instructors"
    __table_args__ = (CheckConstraint("display_order >= 0", name="display_order_nonnegative"),)

    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), primary_key=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("instructors.id"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    display_order: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    section: Mapped[Section] = relationship(back_populates="instructor_links")
    instructor: Mapped[Instructor] = relationship(back_populates="section_links")

Index("ix_section_instructors_instructor_id", SectionInstructor.instructor_id)


class MeetingTime(TimestampMixin, Base):
    __tablename__ = "meeting_times"
    __table_args__ = (
        UniqueConstraint("section_id", "source_fingerprint"),
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
            name="valid_date_range",
        ),
        CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) OR "
            "(start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)",
            name="valid_time_range",
        ),
        CheckConstraint(
            "NOT (is_asynchronous OR is_arranged) OR "
            "(start_time IS NULL AND end_time IS NULL)",
            name="untimed_special_meeting",
        ),
        CheckConstraint(
            "NOT (is_asynchronous AND is_arranged)", name="single_special_meeting_kind"
        ),
        Index(
            "uq_meeting_times_section_source",
            "section_id",
            "source_identifier",
            unique=True,
            postgresql_where=text("source_identifier IS NOT NULL"),
        ),
        Index("ix_meeting_times_section_dates", "section_id", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"))
    source_identifier: Mapped[str | None] = mapped_column(String(128))
    source_fingerprint: Mapped[str] = mapped_column(String(64))
    meeting_type: Mapped[str] = mapped_column(String(40), default="class", server_default="class")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    end_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    timezone: Mapped[str] = mapped_column(
        String(64), default="America/New_York", server_default="America/New_York"
    )
    building: Mapped[str | None] = mapped_column(String(120))
    room: Mapped[str | None] = mapped_column(String(80))
    location_text: Mapped[str | None] = mapped_column(String(255))
    is_asynchronous: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    is_arranged: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    section: Mapped[Section] = relationship(back_populates="meeting_times")
    days: Mapped[list[MeetingDay]] = relationship(
        back_populates="meeting_time", cascade="all, delete-orphan"
    )


class MeetingDay(Base):
    __tablename__ = "meeting_days"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="valid_day_of_week"),
        Index("ix_meeting_days_day_meeting", "day_of_week", "meeting_time_id"),
    )

    meeting_time_id: Mapped[int] = mapped_column(
        ForeignKey("meeting_times.id"), primary_key=True
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, primary_key=True)

    meeting_time: Mapped[MeetingTime] = relationship(back_populates="days")


class SectionRelationshipRule(TimestampMixin, Base):
    __tablename__ = "section_relationship_rules"
    __table_args__ = (
        UniqueConstraint("source_section_id", "target_component_id", "rule_type"),
        Index(
            "uq_section_relationship_rules_offering_source",
            "course_offering_id",
            "source_identifier",
            unique=True,
            postgresql_where=text("source_identifier IS NOT NULL"),
        ),
        Index(
            "ix_section_relationship_rules_offering_section",
            "course_offering_id",
            "source_section_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    course_offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"))
    source_section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"))
    target_component_id: Mapped[int] = mapped_column(ForeignKey("offering_components.id"))
    rule_type: Mapped[RelationshipRuleType] = mapped_column(
        enum_type(RelationshipRuleType, "relationship_rule_type")
    )
    source_identifier: Mapped[str | None] = mapped_column(String(128))
    is_authoritative: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )

    course_offering: Mapped[CourseOffering] = relationship(back_populates="relationship_rules")
    source_section: Mapped[Section] = relationship(
        back_populates="relationship_rules", foreign_keys=[source_section_id]
    )
    target_component: Mapped[OfferingComponent] = relationship()
    options: Mapped[list[SectionRelationshipOption]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class SectionRelationshipOption(Base):
    __tablename__ = "section_relationship_options"

    rule_id: Mapped[int] = mapped_column(
        ForeignKey("section_relationship_rules.id"), primary_key=True
    )
    target_section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rule: Mapped[SectionRelationshipRule] = relationship(back_populates="options")
    target_section: Mapped[Section] = relationship(
        back_populates="relationship_options", foreign_keys=[target_section_id]
    )

Index(
    "ix_section_relationship_options_target_section_id",
    SectionRelationshipOption.target_section_id,
)
