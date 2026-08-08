from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from drexel_schedule_generator.api.dependencies import get_session
from drexel_schedule_generator.db.models import MeetingDay, MeetingTime
from drexel_schedule_generator.main import app
from drexel_schedule_generator.webtms.importer import import_dataset
from drexel_schedule_generator.webtms.parser import parse_fixture_directory

FIXTURES = Path(__file__).parent / "fixtures" / "webtms"


def client_for(session: Session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_discovery_and_generation_flow(db_session: Session) -> None:
    completed = datetime(2026, 8, 2, 20, tzinfo=UTC)
    summary = import_dataset(db_session, parse_fixture_directory(FIXTURES), completed_at=completed)
    client = client_for(db_session)
    try:
        terms = client.get("/api/v1/terms")
        assert terms.status_code == 200
        assert terms.json()[0]["source_code"] == "202545"
        assert terms.json()[0]["latest_successful_import_at"] == "2026-08-02T20:00:00Z"

        courses = client.get(f"/api/v1/terms/{summary.term_id}/courses", params={"search": "CS 172"})
        assert courses.status_code == 200
        assert courses.json()["total"] == 1
        course = courses.json()["items"][0]
        assert course["component_types"] == ["lab", "lecture"]
        assert course["has_saturday_sections"] is False

        meeting = db_session.scalar(select(MeetingTime).limit(1))
        assert meeting is not None
        meeting.days.append(MeetingDay(day_of_week=6))
        db_session.flush()
        saturday_course = client.get(
            f"/api/v1/terms/{summary.term_id}/courses", params={"search": "CS 172"}
        ).json()["items"][0]
        assert saturday_course["has_saturday_sections"] is True

        sections = client.get(f"/api/v1/terms/{summary.term_id}/courses/{course['id']}/sections")
        assert sections.status_code == 200
        assert len(sections.json()) == 2
        assert sum(len(section["meetings"]) for section in sections.json()) == 2
        assert all(
            meeting["meeting_type"] == "class"
            for section in sections.json()
            for meeting in section["meetings"]
        )
        assert {section["maximum_enrollment"] for section in sections.json()} == {30}

        generated = client.post(
            "/api/v1/schedules/generate",
            json={"term_id": summary.term_id, "course_ids": [course["id"]], "maximum_results": 10},
        )
        assert generated.status_code == 200
        assert len(generated.json()["schedules"]) == 1
        assert len(generated.json()["schedules"][0]["sections"]) == 2
        assert generated.json()["compatibility_limitation"]

        freshness = client.get("/api/v1/data-freshness")
        assert freshness.status_code == 200
        assert freshness.json()["has_successful_import"] is True
        assert freshness.json()["latest_successful_import_at"] == "2026-08-02T20:00:00Z"
    finally:
        app.dependency_overrides.clear()


def test_invalid_schedule_requests_are_non_500(db_session: Session) -> None:
    client = client_for(db_session)
    try:
        empty = client.post("/api/v1/schedules/generate", json={"term_id": 1, "course_ids": []})
        assert empty.status_code == 422
        unknown = client.post("/api/v1/schedules/generate", json={"term_id": 999999, "course_ids": [999999]})
        assert unknown.status_code == 400
        excessive = client.post(
            "/api/v1/schedules/generate",
            json={"term_id": 1, "course_ids": list(range(1, 10))},
        )
        assert excessive.status_code == 422
        invalid_result_limit = client.post(
            "/api/v1/schedules/generate",
            json={"term_id": 1, "course_ids": [1], "maximum_results": 0},
        )
        assert invalid_result_limit.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_freshness_empty_state(db_session: Session) -> None:
    client = client_for(db_session)
    try:
        response = client.get("/api/v1/data-freshness")
        assert response.status_code == 200
        assert response.json()["has_successful_import"] is False
        assert response.json()["latest_successful_import_at"] is None
    finally:
        app.dependency_overrides.clear()
