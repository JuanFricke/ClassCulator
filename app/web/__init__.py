from fastapi import APIRouter

from app.web import routes

web_router = APIRouter()
web_router.include_router(routes.router)
