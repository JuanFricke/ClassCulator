from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TurmaBase(BaseModel):
    identificador: str = Field(min_length=1, max_length=40)
    ensino: Literal["fundamental", "medio", "ambos"] = "fundamental"
    semestre: str = Field(default="2026/1", max_length=20)
    qtd_alunos: int = Field(default=30, ge=1, le=200)


class TurmaCreate(TurmaBase):
    pass


class TurmaUpdate(BaseModel):
    identificador: str | None = Field(default=None, min_length=1, max_length=40)
    ensino: Literal["fundamental", "medio", "ambos"] | None = None
    semestre: str | None = None
    qtd_alunos: int | None = Field(default=None, ge=1, le=200)


class TurmaDisciplinaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    turma_id: int
    disciplina_id: int
    professor_id: int


class TurmaRead(TurmaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    curriculo: list[TurmaDisciplinaRead] = Field(default_factory=list)


class CurriculoItem(BaseModel):
    disciplina_id: int
    professor_id: int


class TurmaCurriculoBulkUpdate(BaseModel):
    """Substitui o currículo da turma por completo."""

    items: list[CurriculoItem]
