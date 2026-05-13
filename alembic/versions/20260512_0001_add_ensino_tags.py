"""add ensino tags to turmas and disciplinas

Revision ID: 20260512_0001
Revises: 20260505_0000
Create Date: 2026-05-12 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_0001"
down_revision: str | None = "20260505_0000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "disciplinas",
        sa.Column("ensino", sa.String(length=20), nullable=False, server_default="fundamental"),
    )
    op.add_column(
        "turmas",
        sa.Column("ensino", sa.String(length=20), nullable=False, server_default="fundamental"),
    )

    op.execute(
        "ALTER TABLE disciplinas ADD CONSTRAINT ck_disciplinas_ensino "
        "CHECK (ensino IN ('fundamental', 'medio'))"
    )
    op.execute(
        "ALTER TABLE turmas ADD CONSTRAINT ck_turmas_ensino "
        "CHECK (ensino IN ('fundamental', 'medio'))"
    )

    op.alter_column("disciplinas", "ensino", server_default=None)
    op.alter_column("turmas", "ensino", server_default=None)


def downgrade() -> None:
    op.execute("ALTER TABLE turmas DROP CONSTRAINT IF EXISTS ck_turmas_ensino")
    op.execute("ALTER TABLE disciplinas DROP CONSTRAINT IF EXISTS ck_disciplinas_ensino")
    op.drop_column("turmas", "ensino")
    op.drop_column("disciplinas", "ensino")
