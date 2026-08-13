from fastapi import APIRouter
from app.api.v1.endpoints import producers, subscribers, events, dashboard

api_router = APIRouter()

api_router.include_router(
    producers.router,
    prefix="/producers",
    tags=["producers"],
)

api_router.include_router(
    subscribers.router,
    prefix="/subscribers",
    tags=["subscribers"],
)

api_router.include_router(
    events.router,
    prefix="/events",
    tags=["events"],
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["dashboard"],
)
