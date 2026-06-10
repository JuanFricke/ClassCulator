"""set turma_disciplina.professor_id FK to SET NULL

Revision ID: 20260610_0007
Revises: 20260607_0006
Create Date: 2026-06-10 00:07:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260610_0007"
down_revision: str | None = "20260607_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop existing FK constraint and recreate it with ON DELETE SET NULL
    op.drop_constraint("turma_disciplina_professor_id_fkey", "turma_disciplina", type_="foreignkey")
    op.create_foreign_key(
        "turma_disciplina_professor_id_fkey",
        "turma_disciplina",
        "professores",
        ["professor_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Revert to RESTRICT
    op.drop_constraint("turma_disciplina_professor_id_fkey", "turma_disciplina", type_="foreignkey")
    op.create_foreign_key(
        "turma_disciplina_professor_id_fkey",
        "turma_disciplina",
        "professores",
        ["professor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
