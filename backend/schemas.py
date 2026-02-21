from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
import re


class MeetingRequest(BaseModel):
    """
    Payload for creating a meeting.

    - date: ISO date string, e.g. "202`4-02-19"
    - time: 24h or 12h time string, e.g. "14:30" or "2:30 PM"
    - name: Attendee / requester name
    - title: Optional meeting title; defaults to "Meeting with {name}"
    """

    name: str
    date: str
    time: str
    title: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 100:
            raise ValueError("name must be 100 characters or fewer")
        return v

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        v = v.strip()
        # Accept YYYY-MM-DD only
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("date must be in YYYY-MM-DD format, e.g. '2024-08-15'")
        return v

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        v = v.strip()
        # Accept HH:MM (24h) or H:MM AM/PM
        if not re.fullmatch(r"\d{1,2}:\d{2}(\s*[APap][Mm])?", v):
            raise ValueError(
                "time must be in HH:MM (24h) or H:MM AM/PM format, e.g. '14:30' or '2:30 PM'"
            )
        return v

    @model_validator(mode="after")
    def set_default_title(self) -> "MeetingRequest":
        if not self.title or not self.title.strip():
            self.title = f"Meeting with {self.name}"
        return self


class MeetingResponse(BaseModel):
    success: bool
    event_id: str
    title: str
    start_ist: str  # ISO string in Asia/Kolkata
    end_ist: str
    calendar_link: str
    meet_link: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = []
