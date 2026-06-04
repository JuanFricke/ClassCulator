"""Entrada principal da aplicação FastAPI (ClassCulator)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import __version__
from app.api import api_router
from app.core.auth import RedirectError
from app.core.config import settings
from app.web import web_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="ClassCulator",
    description="Sistema de Geração Automática de Grade Horária Escolar.",
    version=__version__,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="classculator_session",
    https_only=settings.APP_ENV == "prod",
)


@app.exception_handler(RedirectError)
async def _handle_redirect(request: Request, exc: RedirectError) -> RedirectResponse:
    return RedirectResponse(url=exc.location, status_code=303)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
