from __future__ import annotations

from datetime import time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .course_data import SectionResponse


class GenerateScheduleRequest(BaseModel):
    term_id: int
    course_ids: list[int]
    maximum_results: int | None = Field(default=None, ge=1)
    delivery_preferences: dict[int, list[Literal["online", "face_to_face"]]] = Field(default_factory=dict)

    @field_validator("course_ids")
    @classmethod
    def unique_courses(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("Select at least one course.")
        if len(value) > 8:
            raise ValueError("At most eight courses may be selected.")
        if len(set(value)) != len(value):
            raise ValueError("Duplicate course IDs are not allowed.")
        return value

    @field_validator("delivery_preferences")
    @classmethod
    def valid_preferences(cls, value: dict[int, list[str]]) -> dict[int, list[str]]:
        if any(not modes for modes in value.values()):
            raise ValueError("Each delivery preference must allow at least one mode.")
        return {course_id: list(dict.fromkeys(modes)) for course_id, modes in value.items()}


class MetricsResponse(BaseModel):
    campus_days: int
    total_gap_minutes: int
    earliest_start: time | None
    latest_end: time | None
    total_meeting_minutes: int


class GeneratedScheduleResponse(BaseModel):
    sections: list[SectionResponse]
    metrics: MetricsResponse


class GenerateScheduleResponse(BaseModel):
    schedules: list[GeneratedScheduleResponse]
    total_valid_considered: int
    truncated: bool
    no_results: dict[str, str] | None = None
    compatibility_limitation: str | None = None
