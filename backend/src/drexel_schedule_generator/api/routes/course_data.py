from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from drexel_schedule_generator.api.dependencies import get_session
from drexel_schedule_generator.schemas.course_data import CoursePageResponse, FreshnessResponse, SectionResponse, TermResponse
from drexel_schedule_generator.services import course_data

router = APIRouter(prefix="/api/v1", tags=["course data"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/terms", response_model=list[TermResponse])
def terms(session: SessionDependency) -> list[TermResponse]:
    return course_data.list_terms(session)


@router.get("/terms/{term_id}/courses", response_model=CoursePageResponse)
def courses(
    term_id: int,
    session: SessionDependency,
    search: str | None = Query(default=None, max_length=100),
    subject: str | None = Query(default=None, max_length=16),
    number: str | None = Query(default=None, max_length=24),
    title: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CoursePageResponse:
    return course_data.search_courses(
        session,
        term_id,
        search=search,
        subject=subject,
        number=number,
        title=title,
        page=page,
        page_size=page_size,
    )


@router.get("/terms/{term_id}/courses/{course_id}/sections", response_model=list[SectionResponse])
def sections(term_id: int, course_id: int, session: SessionDependency) -> list[SectionResponse]:
    result = course_data.course_sections(session, term_id, course_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Course was not found in this term.")
    return result


@router.get("/data-freshness", response_model=FreshnessResponse)
def freshness(session: SessionDependency) -> FreshnessResponse:
    return course_data.data_freshness(session)
