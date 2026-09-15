from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

FeedbackType = Literal["Bug Report", "Feature Suggestion", "Usability Feedback", "Other"]
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class FeedbackRequest(BaseModel):
    name: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=254)
    type: list[FeedbackType] = Field(min_length=1)
    message: str = Field(max_length=5000)

    @field_validator("name", "email", "message", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def valid_optional_email(cls, value: str) -> str:
        if value and not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("type")
    @classmethod
    def unique_types(cls, value: list[FeedbackType]) -> list[FeedbackType]:
        return list(dict.fromkeys(value))

    @field_validator("message")
    @classmethod
    def nonempty_message(cls, value: str) -> str:
        if not value:
            raise ValueError("Enter a feedback message.")
        return value


class FeedbackResponse(BaseModel):
    success: bool
    message: str
