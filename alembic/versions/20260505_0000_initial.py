"""initial schema

Revision ID: 20260505_0000
Revises:
Create Date: 2026-05-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260505_0000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sala_tipo() -> postgresql.ENUM:
    return postgresql.ENUM("sala", "lab", name="sala_tipo", create_type=False)


def _grade_status() -> postgresql.ENUM:
    return postgresql.ENUM(
        "pending", "running", "done", "failed", name="grade_status", create_type=False
    )


def upgrade() -> None:
    bind = op.get_bind()

    postgresql.ENUM("sala", "lab", name="sala_tipo").create(bind, checkfirst=True)
    postgresql.ENUM(
        "pending", "running", "done", "failed", name="grade_status"
    ).create(bind, checkfirst=True)

    op.create_table(
        "professores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(120), nullable=True),
    )

    op.create_table(
        "disciplinas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(120), nullable=False, unique=True),
        sa.Column("area", sa.String(60), nullable=False, server_default="geral"),
        sa.Column("carga_semanal", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("requer_lab", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("eh_teorica", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "turmas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("identificador", sa.String(40), nullable=False, unique=True),
        sa.Column("semestre", sa.String(20), nullable=False, server_default="2026/1"),
        sa.Column("qtd_alunos", sa.Integer(), nullable=False, server_default="30"),
    )

    op.create_table(
        "salas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(80), nullable=False, unique=True),
        sa.Column("tipo", _sala_tipo(), nullable=False, server_default="sala"),
        sa.Column("capacidade", sa.Integer(), nullable=False, server_default="40"),
    )

    op.create_table(
        "professor_disciplina",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "professor_id",
            sa.Integer(),
            sa.ForeignKey("professores.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "disciplina_id",
            sa.Integer(),
            sa.ForeignKey("disciplinas.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.UniqueConstraint("professor_id", "disciplina_id", name="uq_prof_disc"),
    )

    op.create_table(
        "disponibilidade_professor",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "professor_id",
            sa.Integer(),
            sa.ForeignKey("professores.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("dia", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("disponivel", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("professor_id", "dia", "slot", name="uq_disp_prof_dia_slot"),
    )

    op.create_table(
        "turma_disciplina",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "turma_id",
            sa.Integer(),
            sa.ForeignKey("turmas.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "disciplina_id",
            sa.Integer(),
            sa.ForeignKey("disciplinas.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "professor_id",
            sa.Integer(),
            sa.ForeignKey("professores.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.UniqueConstraint("turma_id", "disciplina_id", name="uq_turma_disciplina"),
    )

    op.create_table(
        "grades_horarias",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("semestre", sa.String(20), nullable=False, server_default="2026/1"),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", _grade_status(), nullable=False, server_default="pending"),
        sa.Column("score_penalidade", sa.Float(), nullable=True),
        sa.Column("solver_usado", sa.String(20), nullable=True),
        sa.Column("tempo_segundos", sa.Float(), nullable=True),
        sa.Column("log", sa.Text(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "alocacoes_slot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "grade_id",
            sa.Integer(),
            sa.ForeignKey("grades_horarias.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "turma_id",
            sa.Integer(),
            sa.ForeignKey("turmas.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "disciplina_id",
            sa.Integer(),
            sa.ForeignKey("disciplinas.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "professor_id",
            sa.Integer(),
            sa.ForeignKey("professores.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "sala_id",
            sa.Integer(),
            sa.ForeignKey("salas.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("dia", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("alocacoes_slot")
    op.drop_table("grades_horarias")
    op.drop_table("turma_disciplina")
    op.drop_table("disponibilidade_professor")
    op.drop_table("professor_disciplina")
    op.drop_table("salas")
    op.drop_table("turmas")
    op.drop_table("disciplinas")
    op.drop_table("professores")

    postgresql.ENUM(name="grade_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="sala_tipo").drop(bind, checkfirst=True)
