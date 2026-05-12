from pydantic import BaseModel, ConfigDict, Field


class DisciplinaBase(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    area: str = Field(default="geral", max_length=60)
    carga_semanal: int = Field(default=2, ge=1, le=10)
    requer_lab: bool = False
    eh_teorica: bool = True


class DisciplinaCreate(DisciplinaBase):
    pass


class DisciplinaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    area: str | None = None
    carga_semanal: int | None = Field(default=None, ge=1, le=10)
    requer_lab: bool | None = None
    eh_teorica: bool | None = None


class DisciplinaRead(DisciplinaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
