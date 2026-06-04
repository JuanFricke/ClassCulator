from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Professor(Base):
    __tablename__ = "professores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ano_letivo_id: Mapped[int] = mapped_column(
        ForeignKey("anos_letivos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Professor {self.id} {self.nome!r}>"


class ProfessorDisciplina(Base):
    __tablename__ = "professor_disciplina"
    __table_args__ = (
        UniqueConstraint("professor_id", "disciplina_id", name="uq_prof_disc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    professor_id: Mapped[int] = mapped_column(
        ForeignKey("professores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("disciplinas.id", ondelete="CASCADE"), nullable=False, index=True
    )


class DisponibilidadeProfessor(Base):
    """Marca se um (dia, slot) é disponível para o professor.

    Apenas registros com `disponivel=False` são consultados pelo solver para
    encolher domínios (HC5). Ausência de registro implica disponibilidade total.
    """

    __tablename__ = "disponibilidade_professor"
    __table_args__ = (
        UniqueConstraint("professor_id", "dia", "slot", name="uq_disp_prof_dia_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    professor_id: Mapped[int] = mapped_column(
        ForeignKey("professores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dia: Mapped[int] = mapped_column(Integer, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    disponivel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
