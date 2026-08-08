from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field


class TermResponse(BaseModel):
    id: int
    source_code: str
    name: str
    active: bool
    latest_successful_import_at: datetime | None


class CourseResponse(BaseModel):
    id: int
    subject: str
    number: str
    title: str
    minimum_credits: Decimal | None
    maximum_credits: Decimal | None
    schedulable_section_count: int
    component_types: list[str]
    delivery_modes: list[str]
    has_saturday_sections: bool


class CoursePageResponse(BaseModel):
    items: list[CourseResponse]
    page: int
    page_size: int
    total: int


class MeetingResponse(BaseModel):
    days: list[int]
    start_time: time | None
    end_time: time | None
    start_date: date | None
    end_date: date | None
    meeting_type: str
    is_asynchronous: bool
    is_arranged: bool


class SectionResponse(BaseModel):
    id: int
    subject: str
    course_number: str
    crn: str
    section_number: str
    component: str
    instructors: list[str]
    meetings: list[MeetingResponse]
    campus: str | None
    instructional_method: str | None
    maximum_enrollment: int | None
    alternative_section_numbers: list[str] = Field(default_factory=list)
    alternative_crns: list[str] = Field(default_factory=list)


class FreshnessResponse(BaseModel):
    has_successful_import: bool
    latest_successful_import_at: datetime | None
    timezone: str = "America/New_York"
    term_updates: dict[str, datetime] = Field(default_factory=dict)
