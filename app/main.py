"""Entrada principal da aplicação FastAPI (ClassCulator)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import api_router
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

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
