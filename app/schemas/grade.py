from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SolverId = Literal["cpsat", "classic"]


class GradeGenerateRequest(BaseModel):
    semestre: str = Field(default="2026/1", max_length=20)
    solver: SolverId = "cpsat"
    timeout_s: int = Field(default=30, ge=1, le=600)


class GradeGenerateResponse(BaseModel):
    id: int
    status: str
    versao: int
    semestre: str


class GradeStatusResponse(BaseModel):
    id: int
    status: str
    versao: int
    semestre: str
    solver_usado: str | None
    score_penalidade: float | None
    tempo_segundos: float | None
    mensagem: str | None = None


class AlocacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    turma_id: int
    disciplina_id: int
    professor_id: int
    sala_id: int | None
    dia: int
    slot: int


class GradeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semestre: str
    versao: int
    status: str
    score_penalidade: float | None
    solver_usado: str | None
    tempo_segundos: float | None
    criado_em: datetime


class GradeDetail(GradeListItem):
    log: str | None = None
    alocacoes: list[AlocacaoRead] = Field(default_factory=list)
