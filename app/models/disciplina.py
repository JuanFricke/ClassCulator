from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Disciplina(Base):
    __tablename__ = "disciplinas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    area: Mapped[str] = mapped_column(String(60), nullable=False, default="geral")
    carga_semanal: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    requer_lab: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    eh_teorica: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Disciplina {self.id} {self.nome!r}>"
