from datetime import datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnoLetivo(Base):
    """Partição anual de dados. Cada ano é independente (clonado do anterior)."""

    __tablename__ = "anos_letivos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnoLetivo {self.id} {self.ano}>"
