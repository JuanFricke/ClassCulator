"""add slots_por_dia to turmas

Revision ID: 20260513_0003
Revises: 20260512_0002
Create Date: 2026-05-13 00:03:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260513_0003"
down_revision: str | None = "20260512_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "turmas",
        sa.Column(
            "slots_por_dia",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[6,6,6,6,6]'::jsonb"),
        ),
    )
    op.execute(
        "ALTER TABLE turmas ADD CONSTRAINT ck_turmas_slots_por_dia_length "
        "CHECK (jsonb_array_length(slots_por_dia) = 5)"
    )
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

    op.alter_column("turmas", "slots_por_dia", server_default=None)


def downgrade() -> None:
    op.execute("ALTER TABLE turmas DROP CONSTRAINT IF EXISTS ck_turmas_slots_por_dia_range")
    op.execute("ALTER TABLE turmas DROP CONSTRAINT IF EXISTS ck_turmas_slots_por_dia_length")
    op.drop_column("turmas", "slots_por_dia")
