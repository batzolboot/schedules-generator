from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from drexel_schedule_generator.main import app


def feedback_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Andrew",
        "email": "andrew@example.com",
        "type": ["Feature Suggestion"],
        "message": "Please add dark mode.",
    }
    payload.update(overrides)
    return payload


def test_feedback_is_validated_and_forwarded(monkeypatch) -> None:
    monkeypatch.setenv("MAKE_FEEDBACK_WEBHOOK_URL", "https://webhook.example.test/feedback")
    response = MagicMock(status=200)
    opener = MagicMock()
    opener.return_value.__enter__.return_value = response

    with patch("drexel_schedule_generator.services.feedback.urlopen", opener):
        result = TestClient(app).post("/api/v1/feedback", json=feedback_payload(name=" Andrew ", message=" Please add dark mode. "))

    assert result.status_code == 200
    assert result.json() == {"success": True, "message": "Feedback submitted successfully."}
    request = opener.call_args.args[0]
    assert json.loads(request.data) == feedback_payload(name="Andrew", message="Please add dark mode.")
    assert request.full_url == "https://webhook.example.test/feedback"


def test_feedback_preserves_multiple_types_and_accepts_blank_optional_values(monkeypatch) -> None:
    monkeypatch.setenv("MAKE_FEEDBACK_WEBHOOK_URL", "https://webhook.example.test/feedback")
    response = MagicMock(status=204)
    opener = MagicMock()
    opener.return_value.__enter__.return_value = response
    payload = feedback_payload(name="", email="", type=["Bug Report", "Usability Feedback"], message="The calendar disappears on smaller screens.")

    with patch("drexel_schedule_generator.services.feedback.urlopen", opener):
        result = TestClient(app).post("/api/v1/feedback", json=payload)

    assert result.status_code == 200
    assert json.loads(opener.call_args.args[0].data)["type"] == ["Bug Report", "Usability Feedback"]


def test_feedback_rejects_invalid_input_before_forwarding(monkeypatch) -> None:
    monkeypatch.setenv("MAKE_FEEDBACK_WEBHOOK_URL", "https://webhook.example.test/feedback")
    cases = [
        feedback_payload(type=[]),
        feedback_payload(message=""),
        feedback_payload(type=["Complaint"]),
        feedback_payload(email="not-an-email"),
    ]

    for payload in cases:
        with patch("drexel_schedule_generator.services.feedback.urlopen") as opener:
            result = TestClient(app).post("/api/v1/feedback", json=payload)
        assert result.status_code == 422
        opener.assert_not_called()


def test_feedback_hides_webhook_failures(monkeypatch) -> None:
    monkeypatch.setenv("MAKE_FEEDBACK_WEBHOOK_URL", "https://webhook.example.test/feedback")
    opener = MagicMock(side_effect=TimeoutError())

    with patch("drexel_schedule_generator.services.feedback.urlopen", opener):
        result = TestClient(app).post("/api/v1/feedback", json=feedback_payload())

    assert result.status_code == 502
    assert result.json() == {"detail": "Unable to submit feedback right now. Please try again later."}
    assert "example.test" not in result.text


def test_feedback_returns_safe_error_when_webhook_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("MAKE_FEEDBACK_WEBHOOK_URL", raising=False)

    result = TestClient(app).post("/api/v1/feedback", json=feedback_payload())

    assert result.status_code == 502
    assert result.json() == {"detail": "Unable to submit feedback right now. Please try again later."}
