from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Disciplina(Base):
    __tablename__ = "disciplinas"
    __table_args__ = (
        UniqueConstraint("ano_letivo_id", "nome", name="uq_disciplina_ano_nome"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ano_letivo_id: Mapped[int] = mapped_column(
        ForeignKey("anos_letivos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    ensino: Mapped[str] = mapped_column(String(20), nullable=False, default="fundamental")
    area: Mapped[str] = mapped_column(String(60), nullable=False, default="geral")
    carga_semanal: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    requer_lab: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    eh_teorica: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Disciplina {self.id} {self.nome!r}>"
