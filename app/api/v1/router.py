"""Aggregates all v1 routes. A future v2 gets its own package and prefix,
leaving v1 clients untouched."""

from fastapi import APIRouter

from app.api.v1.routes import auth, projects, tasks, users

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(tasks.router)
