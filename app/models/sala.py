import enum

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SalaTipo(str, enum.Enum):
    SALA = "sala"
    LAB = "lab"


class Sala(Base):
    __tablename__ = "salas"
    __table_args__ = (UniqueConstraint("ano_letivo_id", "nome", name="uq_sala_ano_nome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ano_letivo_id: Mapped[int] = mapped_column(
        ForeignKey("anos_letivos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    tipo: Mapped[SalaTipo] = mapped_column(
        PgEnum(
            SalaTipo,
            name="sala_tipo",
            create_type=False,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=SalaTipo.SALA,
    )
    capacidade: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
