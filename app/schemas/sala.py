from pydantic import BaseModel, ConfigDict, Field

from app.models.sala import SalaTipo


class SalaBase(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    tipo: SalaTipo = SalaTipo.SALA
    capacidade: int = Field(default=40, ge=1, le=300)


class SalaCreate(SalaBase):
    pass


class SalaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=80)
    tipo: SalaTipo | None = None
    capacidade: int | None = Field(default=None, ge=1, le=300)


class SalaRead(SalaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
