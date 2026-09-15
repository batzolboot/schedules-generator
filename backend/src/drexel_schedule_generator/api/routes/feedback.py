from fastapi import APIRouter, HTTPException, status

from drexel_schedule_generator.schemas.feedback import FeedbackRequest, FeedbackResponse
from drexel_schedule_generator.services.feedback import FeedbackDeliveryError, submit_feedback

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_200_OK)
def create_feedback(request: FeedbackRequest) -> FeedbackResponse:
    try:
        submit_feedback(request)
    except FeedbackDeliveryError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to submit feedback right now. Please try again later.",
        ) from error
    return FeedbackResponse(success=True, message="Feedback submitted successfully.")
