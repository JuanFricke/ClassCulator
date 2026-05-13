"""allow ensino=ambos and infer values from names

Revision ID: 20260512_0002
Revises: 20260512_0001
Create Date: 2026-05-12 00:02:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260512_0002"
down_revision: str | None = "20260512_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE turmas DROP CONSTRAINT IF EXISTS ck_turmas_ensino")
    op.execute("ALTER TABLE disciplinas DROP CONSTRAINT IF EXISTS ck_disciplinas_ensino")

    op.execute(
        """
        UPDATE turmas
        SET ensino = CASE
            WHEN upper(identificador) LIKE 'EF%' THEN 'fundamental'
            WHEN upper(identificador) LIKE 'EM%' THEN 'medio'
            ELSE ensino
        END
        """
    )
    op.execute(
        """
        UPDATE disciplinas
        SET ensino = CASE
            WHEN upper(nome) ~ '\\mEF\\M' THEN 'fundamental'
            WHEN upper(nome) ~ '\\mEM\\M' THEN 'medio'
            ELSE 'ambos'
        END
        """
    )

    op.execute(
        "ALTER TABLE disciplinas ADD CONSTRAINT ck_disciplinas_ensino "
        "CHECK (ensino IN ('fundamental', 'medio', 'ambos'))"
    )
    op.execute(
        "ALTER TABLE turmas ADD CONSTRAINT ck_turmas_ensino "
        "CHECK (ensino IN ('fundamental', 'medio', 'ambos'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE turmas DROP CONSTRAINT IF EXISTS ck_turmas_ensino")
    op.execute("ALTER TABLE disciplinas DROP CONSTRAINT IF EXISTS ck_disciplinas_ensino")

    op.execute("UPDATE disciplinas SET ensino='fundamental' WHERE ensino='ambos'")
    op.execute("UPDATE turmas SET ensino='fundamental' WHERE ensino='ambos'")

    op.execute(
        "ALTER TABLE disciplinas ADD CONSTRAINT ck_disciplinas_ensino "
        "CHECK (ensino IN ('fundamental', 'medio'))"
    )
    op.execute(
        "ALTER TABLE turmas ADD CONSTRAINT ck_turmas_ensino "
        "CHECK (ensino IN ('fundamental', 'medio'))"
    )
