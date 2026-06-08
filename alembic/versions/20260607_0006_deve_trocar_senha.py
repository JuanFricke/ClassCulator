"""deve_trocar_senha em usuarios

Revision ID: 20260607_0006
Revises: 20260603_0005
Create Date: 2026-06-07 00:06:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260607_0006"
down_revision: str | None = "20260603_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column(
            "deve_trocar_senha",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("usuarios", "deve_trocar_senha")
