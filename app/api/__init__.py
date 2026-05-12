from fastapi import APIRouter

from app.api import disciplinas, grade, professores, salas, turmas

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(professores.router)
api_router.include_router(disciplinas.router)
api_router.include_router(turmas.router)
api_router.include_router(salas.router)
api_router.include_router(grade.router)
