"""Cadastro inicial da conta administradora (gestora)."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_senha
from app.models import PAPEL_EMPRESA, AnoLetivo, Usuario
from app.services.ano_service import criar_ano

# E-mail criado pela migration quando EMPRESA_* não é passado ao container migrate.
SEED_EMPRESA_EMAIL = "empresa@classculator.local"


async def count_empresa_admins(session: AsyncSession) -> int:
    result = await session.scalar(
        select(func.count()).select_from(Usuario).where(Usuario.papel == PAPEL_EMPRESA)
    )
    return int(result or 0)


async def list_empresa_admins(session: AsyncSession) -> list[Usuario]:
    return list(
        (
            await session.execute(
                select(Usuario).where(Usuario.papel == PAPEL_EMPRESA).order_by(Usuario.id)
            )
        ).scalars().all()
    )


async def cadastro_admin_disponivel(session: AsyncSession) -> bool:
    if settings.ADMIN_SETUP_ENABLED:
        return True
    admins = await list_empresa_admins(session)
    if not admins:
        return True
    return len(admins) == 1 and admins[0].email == SEED_EMPRESA_EMAIL


async def _substituir_contas_empresa(session: AsyncSession, admins: list[Usuario]) -> None:
    if settings.ADMIN_SETUP_ENABLED:
        await session.execute(delete(Usuario).where(Usuario.papel == PAPEL_EMPRESA))
        return
    if len(admins) == 1 and admins[0].email == SEED_EMPRESA_EMAIL:
        await session.delete(admins[0])


async def _garantir_ano_inicial(session: AsyncSession) -> AnoLetivo:
    ano = (await session.execute(select(AnoLetivo).order_by(AnoLetivo.ano.desc()))).scalar_one_or_none()
    if ano is not None:
        return ano
    return await criar_ano(session, settings.ANO_INICIAL)


async def registrar_administradora(
    session: AsyncSession,
    *,
    nome: str,
    email: str,
    senha: str,
) -> Usuario:
    """Cria a conta gestora. Substitui contas empresa existentes se setup estiver aberto."""

    if not await cadastro_admin_disponivel(session):
        raise ValueError("Cadastro de administradora indisponível.")

    email_norm = email.strip().lower()
    admins = await list_empresa_admins(session)

    existente = (
        await session.execute(select(Usuario).where(Usuario.email == email_norm))
    ).scalar_one_or_none()
    if existente is not None and existente.papel != PAPEL_EMPRESA:
        raise ValueError("Já existe uma conta com este e-mail.")

    await _substituir_contas_empresa(session, admins)

    await _garantir_ano_inicial(session)

    usuario = Usuario(
        nome=nome.strip(),
        email=email_norm,
        senha_hash=hash_senha(senha),
        papel=PAPEL_EMPRESA,
        ativo=True,
        deve_trocar_senha=False,
    )
    session.add(usuario)
    await session.commit()
    await session.refresh(usuario)
    return usuario
