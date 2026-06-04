from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SolverId = Literal["cpsat", "classic"]


class GradeGenerateRequest(BaseModel):
    solver: SolverId = "cpsat"
    timeout_s: int = Field(default=30, ge=1, le=600)


class GradeGenerateResponse(BaseModel):
    id: int
    status: str
    versao: int


class GradeStatusResponse(BaseModel):
    id: int
    status: str
    versao: int
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


class AlocacaoManualItem(BaseModel):
    turma_id: int
    disciplina_id: int
    professor_id: int
    sala_id: int | None = None
    dia: int = Field(ge=0)
    slot: int = Field(ge=0)


class GradeManualSaveRequest(BaseModel):
    alocacoes: list[AlocacaoManualItem] = Field(default_factory=list)


class GradeManualSaveResponse(BaseModel):
    id: int
    versao: int


class GradeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    versao: int
    status: str
    score_penalidade: float | None
    solver_usado: str | None
    tempo_segundos: float | None
    criado_em: datetime


class GradeDetail(GradeListItem):
    log: str | None = None
    alocacoes: list[AlocacaoRead] = Field(default_factory=list)
