from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from drexel_schedule_generator.db.config import get_make_feedback_webhook_url
from drexel_schedule_generator.schemas.feedback import FeedbackRequest

logger = logging.getLogger(__name__)
WEBHOOK_TIMEOUT_SECONDS = 10


class FeedbackDeliveryError(Exception):
    """Raised when a validated feedback submission cannot reach Make.com."""


def submit_feedback(feedback: FeedbackRequest) -> None:
    webhook_url = get_make_feedback_webhook_url()
    if not webhook_url:
        logger.error("Feedback webhook is not configured.")
        raise FeedbackDeliveryError from None

    payload = json.dumps(feedback.model_dump()).encode("utf-8")
    request = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=WEBHOOK_TIMEOUT_SECONDS) as response:
            if not 200 <= response.status < 300:
                logger.error("Feedback webhook returned HTTP status %s.", response.status)
                raise FeedbackDeliveryError
    except HTTPError as error:
        logger.error("Feedback webhook returned HTTP status %s.", error.code)
        raise FeedbackDeliveryError from error
    except (URLError, TimeoutError, OSError) as error:
        logger.error("Feedback webhook request failed: %s.", type(error).__name__)
        raise FeedbackDeliveryError from error
