"""Non-sensitive, ignored crawl checkpoints containing normalized records only."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from .auth import ensure_safe_state_path, repository_root
from .records import ParsedCourse, ParsedInstructor, ParsedMeeting, ParsedSection

CRAWL_VERSION = 1


def default_checkpoint_path(term_code: str) -> Path:
    return repository_root() / ".private" / "webtms" / "crawls" / f"term-{term_code}.json"


def _encode(value: object) -> object:
    if isinstance(value, (date, time, Decimal)):
        return value.isoformat() if not isinstance(value, Decimal) else str(value)
    if isinstance(value, (frozenset, tuple)):
        return list(value)
    raise TypeError(f"Unsupported checkpoint value: {type(value).__name__}")


def _meeting(data: dict[str, object]) -> ParsedMeeting:
    return ParsedMeeting(
        days=frozenset(int(day) for day in data["days"]),  # type: ignore[arg-type]
        start_time=time.fromisoformat(str(data["start_time"])) if data.get("start_time") else None,
        end_time=time.fromisoformat(str(data["end_time"])) if data.get("end_time") else None,
        start_date=date.fromisoformat(str(data["start_date"])) if data.get("start_date") else None,
        end_date=date.fromisoformat(str(data["end_date"])) if data.get("end_date") else None,
        building=data.get("building"),  # type: ignore[arg-type]
        room=data.get("room"),  # type: ignore[arg-type]
        meeting_type=str(data.get("meeting_type", "class")),
        is_arranged=bool(data.get("is_arranged")),
        is_asynchronous=bool(data.get("is_asynchronous")),
    )


def _course(data: dict[str, object]) -> ParsedCourse:
    section_data = data["section"]  # type: ignore[assignment]
    section = ParsedSection(
        source_id=section_data.get("source_id"), crn=str(section_data["crn"]), number=str(section_data["number"]),
        component=str(section_data["component"]), status=section_data.get("status"),
        instructional_method=section_data.get("instructional_method"), campus=section_data.get("campus"),
        instructors=tuple(ParsedInstructor(**item) for item in section_data.get("instructors", [])),
        meetings=tuple(_meeting(item) for item in section_data.get("meetings", [])),
        notes=section_data.get("notes"), skipped_meeting_rows=int(section_data.get("skipped_meeting_rows", 0)),
        maximum_enrollment=int(section_data["maximum_enrollment"]) if section_data.get("maximum_enrollment") is not None else None,
    )
    return ParsedCourse(
        source_id=data.get("source_id"), subject=str(data["subject"]), subject_name=data.get("subject_name"),
        number=str(data["number"]), title=str(data["title"]), description=data.get("description"),
        credits_min=Decimal(str(data["credits_min"])) if data.get("credits_min") is not None else None,
        credits_max=Decimal(str(data["credits_max"])) if data.get("credits_max") is not None else None,
        is_undergraduate=bool(data["is_undergraduate"]), section=section,
    )


class CrawlCheckpoint:
    def __init__(self, path: Path, term_code: str, *, resume: bool = False) -> None:
        self.path = ensure_safe_state_path(path)
        self.term_code = term_code
        self.completed_crns: set[str] = set()
        self.courses: dict[str, ParsedCourse] = {}
        self.outcomes: dict[str, str] = {}
        self.failures: list[str] = []
        if resume and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") != CRAWL_VERSION or data.get("term_code") != term_code:
                raise ValueError("Checkpoint belongs to a different term or crawler version.")
            self.completed_crns = set(data.get("completed_crns", []))
            self.courses = {item["section"]["crn"]: _course(item) for item in data.get("courses", [])}
            self.outcomes = dict(data.get("outcomes", {}))
            self.failures = list(data.get("failures", []))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": CRAWL_VERSION, "term_code": self.term_code, "completed_crns": sorted(self.completed_crns),
                   "courses": [asdict(course) for course in self.courses.values()], "failures": self.failures[-100:]}
        payload["outcomes"] = self.outcomes
        fd, name = tempfile.mkstemp(prefix="crawl-", suffix=".tmp", dir=self.path.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            temporary.write_text(json.dumps(payload, default=_encode), encoding="utf-8")
            try: temporary.chmod(0o600)
            except OSError: pass
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def discard(self) -> bool:
        existed = self.path.exists()
        self.path.unlink(missing_ok=True)
        return existed
