from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from drexel_schedule_generator.api.routes.course_data import router as course_data_router
from drexel_schedule_generator.api.routes.feedback import router as feedback_router
from drexel_schedule_generator.api.routes.health import router as health_router
from drexel_schedule_generator.api.routes.scheduling import router as scheduling_router

app = FastAPI(title="Drexel Schedule Generator API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "https://schedules-generator.buildproject.workers.dev",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health_router)
app.include_router(course_data_router)
app.include_router(feedback_router)
app.include_router(scheduling_router)
