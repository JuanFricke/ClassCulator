from fastapi import APIRouter

from app.web import auth_routes, routes

web_router = APIRouter()
web_router.include_router(auth_routes.router)
web_router.include_router(routes.router)
