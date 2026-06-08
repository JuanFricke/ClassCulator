from pydantic import BaseModel, ConfigDict, Field

from app.solver.domain import SLOTS_DIA_MAX


class ProfessorBase(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=120)


class ProfessorCreate(ProfessorBase):
    disciplina_ids: list[int] = Field(default_factory=list)


class ProfessorUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=120)
    disciplina_ids: list[int] | None = None


class ProfessorRead(ProfessorBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    disciplina_ids: list[int] = Field(default_factory=list)
    senha_temporaria: str | None = Field(
        default=None,
        description="Exibida uma única vez ao criar professor com e-mail e conta de acesso.",
    )


class DisponibilidadeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    professor_id: int
    dia: int = Field(ge=0, le=4)
    slot: int = Field(ge=0, le=SLOTS_DIA_MAX - 1)
    disponivel: bool


class DisponibilidadeItem(BaseModel):
    dia: int = Field(ge=0, le=4)
    slot: int = Field(ge=0, le=SLOTS_DIA_MAX - 1)
    disponivel: bool


class DisponibilidadeBulkUpdate(BaseModel):
    """Substitui completamente a matriz de disponibilidade do professor."""

    items: list[DisponibilidadeItem]
