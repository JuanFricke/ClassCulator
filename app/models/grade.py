import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GradeStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class GradeHoraria(Base):
    __tablename__ = "grades_horarias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ano_letivo_id: Mapped[int] = mapped_column(
        ForeignKey("anos_letivos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[GradeStatus] = mapped_column(
        PgEnum(
            GradeStatus,
            name="grade_status",
            create_type=False,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=GradeStatus.PENDING,
    )
    score_penalidade: Mapped[float | None] = mapped_column(Float, nullable=True)
    solver_usado: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tempo_segundos: Mapped[float | None] = mapped_column(Float, nullable=True)
    log: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AlocacaoSlot(Base):
    __tablename__ = "alocacoes_slot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grade_id: Mapped[int] = mapped_column(
        ForeignKey("grades_horarias.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turma_id: Mapped[int] = mapped_column(
        ForeignKey("turmas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("disciplinas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    professor_id: Mapped[int] = mapped_column(
        ForeignKey("professores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sala_id: Mapped[int | None] = mapped_column(
        ForeignKey("salas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dia: Mapped[int] = mapped_column(Integer, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
