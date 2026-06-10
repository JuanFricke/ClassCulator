from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _default_slots_por_dia() -> list[int]:
    """Default usado quando a aplicação não informa explicitamente.

    Casa com a grade retangular do dataset EFA (5 dias × 6 slots = 30 períodos),
    garantindo compatibilidade com o solver clássico.
    """

    return [6, 6, 6, 6, 6]


class Turma(Base):
    __tablename__ = "turmas"
    __table_args__ = (
        UniqueConstraint("ano_letivo_id", "identificador", name="uq_turma_ano_identificador"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ano_letivo_id: Mapped[int] = mapped_column(
        ForeignKey("anos_letivos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identificador: Mapped[str] = mapped_column(String(40), nullable=False)
    ensino: Mapped[str] = mapped_column(String(20), nullable=False, default="fundamental")
    qtd_alunos: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    slots_por_dia: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=_default_slots_por_dia
    )


class TurmaDisciplina(Base):
    """Currículo: vincula turma à disciplina e ao professor responsável."""

    __tablename__ = "turma_disciplina"
    __table_args__ = (
        UniqueConstraint("turma_id", "disciplina_id", name="uq_turma_disciplina"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turma_id: Mapped[int] = mapped_column(
        ForeignKey("turmas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("disciplinas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    professor_id: Mapped[int | None] = mapped_column(
        ForeignKey("professores.id", ondelete="SET NULL"), nullable=True, index=True
    )
