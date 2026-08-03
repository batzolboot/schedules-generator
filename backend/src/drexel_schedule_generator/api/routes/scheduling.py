from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from drexel_schedule_generator.api.dependencies import get_session
from drexel_schedule_generator.schemas.scheduling import GenerateScheduleRequest, GenerateScheduleResponse
from drexel_schedule_generator.services.scheduling import ScheduleRequestError, generate_for_courses

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/generate", response_model=GenerateScheduleResponse)
def generate(request: GenerateScheduleRequest, session: SessionDependency) -> GenerateScheduleResponse:
    try:
        return generate_for_courses(
            session,
            request.term_id,
            request.course_ids,
            request.maximum_results,
            request.delivery_preferences,
        )
    except ScheduleRequestError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
