from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PAPEL_EMPRESA = "empresa"
PAPEL_PROFESSOR = "professor"


class Usuario(Base):
    """Conta de acesso ao sistema.

    Existe uma única conta com ``papel='empresa'`` (semeada via env) e contas
    ``papel='professor'`` criadas via auto-cadastro por link de convite.
    """

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    papel: Mapped[str] = mapped_column(String(20), nullable=False, default=PAPEL_PROFESSOR)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Usuario {self.id} {self.email!r} ({self.papel})>"
