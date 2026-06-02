from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.solver.domain import DIAS, SLOTS_DIA_MAX, SLOTS_POR_DIA_DEFAULT


def _validate_slots_por_dia(v: list[int]) -> list[int]:
    if len(v) != DIAS:
        raise ValueError(f"slots_por_dia deve ter exatamente {DIAS} valores (um por dia útil).")
    for i, n in enumerate(v):
        if not isinstance(n, int) or isinstance(n, bool):
            raise ValueError(f"slots_por_dia[{i}] precisa ser inteiro.")
        if n < 0 or n > SLOTS_DIA_MAX:
            raise ValueError(
                f"slots_por_dia[{i}]={n} fora do intervalo permitido [0, {SLOTS_DIA_MAX}]."
            )
    return v


class TurmaBase(BaseModel):
    identificador: str = Field(min_length=1, max_length=40)
    ensino: Literal["fundamental", "medio", "ambos"] = "fundamental"
    semestre: str = Field(default="2026/1", max_length=20)
    qtd_alunos: int = Field(default=30, ge=1, le=200)
    slots_por_dia: list[int] = Field(default_factory=lambda: list(SLOTS_POR_DIA_DEFAULT))

    @field_validator("slots_por_dia")
    @classmethod
    def _val_slots_base(cls, v: list[int]) -> list[int]:
        return _validate_slots_por_dia(v)


class TurmaCreate(TurmaBase):
    pass


class TurmaUpdate(BaseModel):
    identificador: str | None = Field(default=None, min_length=1, max_length=40)
    ensino: Literal["fundamental", "medio", "ambos"] | None = None
    semestre: str | None = None
    qtd_alunos: int | None = Field(default=None, ge=1, le=200)
    slots_por_dia: list[int] | None = None

    @field_validator("slots_por_dia")
    @classmethod
    def _val_slots(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        return _validate_slots_por_dia(v)


class TurmaDisciplinaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    turma_id: int
    disciplina_id: int
    professor_id: int | None


class TurmaRead(TurmaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    curriculo: list[TurmaDisciplinaRead] = Field(default_factory=list)


class CurriculoItem(BaseModel):
    disciplina_id: int
    professor_id: int | None = None


class TurmaCurriculoBulkUpdate(BaseModel):
    """Substitui o currículo da turma por completo."""

    items: list[CurriculoItem]
