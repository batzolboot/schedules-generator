"""Typed WebTMS records shared by parsing and importing, not persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class DiscoveredTerm:
    source_id: str
    name: str
    calendar_type: Literal["quarter", "semester", "unknown"]
    academic_year: str | None
    order: int
    path: str


@dataclass(frozen=True, slots=True)
class DiscoveredCollege:
    code: str
    name: str
    path: str


@dataclass(frozen=True, slots=True)
class DiscoveredSubject:
    code: str
    name: str
    college_code: str
    path: str


@dataclass(frozen=True, slots=True)
class DiscoveredSection:
    crn: str
    subject: str
    course_number: str
    title: str
    path: str
    level: Literal["undergraduate", "graduate", "ambiguous"]
    maximum_enrollment: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedTerm:
    source_id: str
    name: str
    start_date: date | None = None
    end_date: date | None = None
    source_updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ParsedInstructor:
    source_id: str | None
    display_name: str | None


@dataclass(frozen=True, slots=True)
class ParsedMeeting:
    days: frozenset[int]
    start_time: time | None
    end_time: time | None
    start_date: date | None
    end_date: date | None
    building: str | None
    room: str | None
    meeting_type: str = "class"
    is_arranged: bool = False
    is_asynchronous: bool = False

    @property
    def is_schedulable(self) -> bool:
        return bool(self.days) and self.start_time is not None and self.end_time is not None


@dataclass(frozen=True, slots=True)
class ParsedSection:
    source_id: str | None
    crn: str
    number: str
    component: str
    status: str | None
    instructional_method: str | None
    campus: str | None
    instructors: tuple[ParsedInstructor, ...] = field(default_factory=tuple)
    meetings: tuple[ParsedMeeting, ...] = field(default_factory=tuple)
    notes: str | None = None
    skipped_meeting_rows: int = 0
    maximum_enrollment: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedCourse:
    source_id: str | None
    subject: str
    subject_name: str | None
    number: str
    title: str
    description: str | None
    credits_min: Decimal | None
    credits_max: Decimal | None
    is_undergraduate: bool
    section: ParsedSection


@dataclass(frozen=True, slots=True)
class ParsedFixtureDataset:
    term: ParsedTerm
    courses: tuple[ParsedCourse, ...]
    malformed_records: int = 0
    courses_seen_override: int | None = None
    sections_seen_override: int | None = None
    sections_skipped_override: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedCompatibilityRule:
    parent_section_source_id: str
    compatible_section_source_ids: tuple[str, ...]
    relationship: str
