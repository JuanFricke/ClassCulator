"""anos letivos, autenticacao e remocao de semestre

Revision ID: 20260603_0005
Revises: 20260602_0004
Create Date: 2026-06-03 00:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.config import settings
from app.core.security import hash_senha

revision: str = "20260603_0005"
down_revision: str | None = "20260602_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANO_PADRAO = 2026
_TABELAS_ESCOPADAS = ("professores", "disciplinas", "salas", "turmas", "grades_horarias")


def upgrade() -> None:
    # --- Novas tabelas ---------------------------------------------------- #
    op.create_table(
        "anos_letivos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ano", sa.Integer(), nullable=False, unique=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_anos_letivos_ano", "anos_letivos", ["ano"])

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(160), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("papel", sa.String(20), nullable=False, server_default="professor"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"])

    op.create_table(
        "convites_professor",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("usado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_convites_professor_token", "convites_professor", ["token"])

    # --- Ano padrão + usuário empresa ------------------------------------- #
    op.execute(
        sa.text("INSERT INTO anos_letivos (ano) VALUES (:ano) ON CONFLICT (ano) DO NOTHING")
        .bindparams(ano=_ANO_PADRAO)
    )
    op.execute(
        sa.text(
            "INSERT INTO usuarios (nome, email, senha_hash, papel, ativo) "
            "VALUES (:nome, :email, :senha_hash, 'empresa', true) "
            "ON CONFLICT (email) DO NOTHING"
        ).bindparams(
            nome=settings.EMPRESA_NOME,
            email=settings.EMPRESA_EMAIL.strip().lower(),
            senha_hash=hash_senha(settings.EMPRESA_SENHA),
        )
    )

    # --- ano_letivo_id em todas as tabelas escopadas ---------------------- #
    for tabela in _TABELAS_ESCOPADAS:
        op.add_column(tabela, sa.Column("ano_letivo_id", sa.Integer(), nullable=True))
        op.execute(
            sa.text(
                f"UPDATE {tabela} SET ano_letivo_id = "
                "(SELECT id FROM anos_letivos WHERE ano = :ano)"
            ).bindparams(ano=_ANO_PADRAO)
        )
        op.alter_column(tabela, "ano_letivo_id", existing_type=sa.Integer(), nullable=False)
        op.create_index(f"ix_{tabela}_ano_letivo_id", tabela, ["ano_letivo_id"])
        op.create_foreign_key(
            f"fk_{tabela}_ano_letivo",
            tabela,
            "anos_letivos",
            ["ano_letivo_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # --- usuario_id em professores ---------------------------------------- #
    op.add_column("professores", sa.Column("usuario_id", sa.Integer(), nullable=True))
    op.create_index("ix_professores_usuario_id", "professores", ["usuario_id"])
    op.create_foreign_key(
        "fk_professores_usuario",
        "professores",
        "usuarios",
        ["usuario_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- Uniques compostas por ano ---------------------------------------- #
    op.execute("ALTER TABLE disciplinas DROP CONSTRAINT IF EXISTS disciplinas_nome_key")
    op.execute("ALTER TABLE salas DROP CONSTRAINT IF EXISTS salas_nome_key")
    op.execute("ALTER TABLE turmas DROP CONSTRAINT IF EXISTS turmas_identificador_key")
    op.create_unique_constraint(
        "uq_disciplina_ano_nome", "disciplinas", ["ano_letivo_id", "nome"]
    )
    op.create_unique_constraint("uq_sala_ano_nome", "salas", ["ano_letivo_id", "nome"])
    op.create_unique_constraint(
        "uq_turma_ano_identificador", "turmas", ["ano_letivo_id", "identificador"]
    )

    # --- Remove semestre -------------------------------------------------- #
    op.drop_column("turmas", "semestre")
    op.drop_column("grades_horarias", "semestre")


def downgrade() -> None:
    op.add_column(
        "grades_horarias",
        sa.Column("semestre", sa.String(20), nullable=False, server_default="2026/1"),
    )
    op.add_column(
        "turmas",
        sa.Column("semestre", sa.String(20), nullable=False, server_default="2026/1"),
    )

    op.drop_constraint("uq_turma_ano_identificador", "turmas", type_="unique")
    op.drop_constraint("uq_sala_ano_nome", "salas", type_="unique")
    op.drop_constraint("uq_disciplina_ano_nome", "disciplinas", type_="unique")
    op.create_unique_constraint("turmas_identificador_key", "turmas", ["identificador"])
    op.create_unique_constraint("salas_nome_key", "salas", ["nome"])
    op.create_unique_constraint("disciplinas_nome_key", "disciplinas", ["nome"])

    op.drop_constraint("fk_professores_usuario", "professores", type_="foreignkey")
    op.drop_index("ix_professores_usuario_id", table_name="professores")
    op.drop_column("professores", "usuario_id")

    for tabela in _TABELAS_ESCOPADAS:
        op.drop_constraint(f"fk_{tabela}_ano_letivo", tabela, type_="foreignkey")
        op.drop_index(f"ix_{tabela}_ano_letivo_id", table_name=tabela)
        op.drop_column(tabela, "ano_letivo_id")

    op.drop_index("ix_convites_professor_token", table_name="convites_professor")
    op.drop_table("convites_professor")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
    op.drop_index("ix_anos_letivos_ano", table_name="anos_letivos")
    op.drop_table("anos_letivos")
