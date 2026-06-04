"""curriculo professor opcional + slots_por_dia ate 15

Revision ID: 20260602_0004
Revises: 20260513_0003
Create Date: 2026-06-02 00:04:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260602_0004"
down_revision: str | None = "20260513_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "turma_disciplina",
        "professor_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    op.execute("ALTER TABLE turmas DROP CONSTRAINT IF EXISTS ck_turmas_slots_por_dia_range")
    op.execute(
        "ALTER TABLE turmas ADD CONSTRAINT ck_turmas_slots_por_dia_range "
        "CHECK ("
        "    (slots_por_dia->>0)::int BETWEEN 0 AND 15"
        " AND (slots_por_dia->>1)::int BETWEEN 0 AND 15"
        " AND (slots_por_dia->>2)::int BETWEEN 0 AND 15"
        " AND (slots_por_dia->>3)::int BETWEEN 0 AND 15"
        " AND (slots_por_dia->>4)::int BETWEEN 0 AND 15"
        ")"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE turmas DROP CONSTRAINT IF EXISTS ck_turmas_slots_por_dia_range")
    op.execute(
        "ALTER TABLE turmas ADD CONSTRAINT ck_turmas_slots_por_dia_range "
        "CHECK ("
        "    (slots_por_dia->>0)::int BETWEEN 0 AND 12"
        " AND (slots_por_dia->>1)::int BETWEEN 0 AND 12"
        " AND (slots_por_dia->>2)::int BETWEEN 0 AND 12"
        " AND (slots_por_dia->>3)::int BETWEEN 0 AND 12"
        " AND (slots_por_dia->>4)::int BETWEEN 0 AND 12"
        ")"
    )

    # Requer que não existam linhas com professor_id NULL antes do downgrade.
    op.alter_column(
        "turma_disciplina",
        "professor_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
