"""Dependências de autenticação/autorização e resolução do ano ativo.

Rotas SSR (web) usam as variantes ``*_web`` que redirecionam via
:class:`RedirectError`; rotas JSON (``/api/v1``) usam as variantes ``*_api``
que levantam ``HTTPException`` com 401/403.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from app.core.deps import SessionDep
from app.models import (
    PAPEL_EMPRESA,
    PAPEL_PROFESSOR,
    AnoLetivo,
    Professor,
    Usuario,
)

SESSION_USER_KEY = "usuario_id"
SESSION_ANO_KEY = "ano_letivo_id"


class RedirectError(Exception):
    """Sinaliza às rotas SSR que o usuário deve ser redirecionado."""

    def __init__(self, location: str) -> None:
        self.location = location
        super().__init__(location)


async def get_current_user(request: Request, session: SessionDep) -> Usuario | None:
    uid = request.session.get(SESSION_USER_KEY)
    if not uid:
        return None
    user = await session.get(Usuario, uid)
    if user is None or not user.ativo:
        return None
    return user


CurrentUserDep = Annotated[Usuario | None, Depends(get_current_user)]


async def _ano_mais_recente(session: SessionDep) -> AnoLetivo | None:
    return (
        await session.execute(select(AnoLetivo).order_by(AnoLetivo.ano.desc()).limit(1))
    ).scalar_one_or_none()


async def _resolver_ano_ativo(request: Request, session: SessionDep) -> AnoLetivo | None:
    ano_id = request.session.get(SESSION_ANO_KEY)
    ano: AnoLetivo | None = None
    if ano_id:
        ano = await session.get(AnoLetivo, ano_id)
    if ano is None:
        ano = await _ano_mais_recente(session)
        if ano is not None:
            request.session[SESSION_ANO_KEY] = ano.id
    return ano


# --- Variantes SSR (redirect) -------------------------------------------- #


async def require_empresa_web(user: CurrentUserDep) -> Usuario:
    if user is None:
        raise RedirectError("/login")
    if user.papel != PAPEL_EMPRESA:
        raise RedirectError("/professor")
    return user


async def require_professor_web(user: CurrentUserDep) -> Usuario:
    if user is None:
        raise RedirectError("/login")
    if user.papel != PAPEL_PROFESSOR:
        raise RedirectError("/anos")
    return user


async def get_ano_ativo_web(
    request: Request,
    session: SessionDep,
    _user: Annotated[Usuario, Depends(require_empresa_web)],
) -> AnoLetivo:
    ano = await _resolver_ano_ativo(request, session)
    if ano is None:
        raise RedirectError("/anos")
    return ano


EmpresaWebDep = Annotated[Usuario, Depends(require_empresa_web)]
ProfessorWebDep = Annotated[Usuario, Depends(require_professor_web)]
AnoAtivoWebDep = Annotated[AnoLetivo, Depends(get_ano_ativo_web)]


async def empresa_layout(
    session: SessionDep,
    user: EmpresaWebDep,
    ano: AnoAtivoWebDep,
) -> dict:
    """Contexto comum às páginas da empresa (usuário, ano atual e lista de anos)."""

    anos = (
        await session.execute(select(AnoLetivo).order_by(AnoLetivo.ano.desc()))
    ).scalars().all()
    return {"current_user": user, "ano_atual": ano, "anos": list(anos)}


LayoutDep = Annotated[dict, Depends(empresa_layout)]


# --- Variantes JSON (HTTPException) -------------------------------------- #


async def require_empresa_api(user: CurrentUserDep) -> Usuario:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")
    if user.papel != PAPEL_EMPRESA:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito.")
    return user


async def get_ano_ativo_api(
    request: Request,
    session: SessionDep,
    _user: Annotated[Usuario, Depends(require_empresa_api)],
) -> AnoLetivo:
    ano = await _resolver_ano_ativo(request, session)
    if ano is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nenhum ano letivo selecionado. Crie/selecione um ano antes de continuar.",
        )
    return ano


AnoAtivoApiDep = Annotated[AnoLetivo, Depends(get_ano_ativo_api)]


# --- Contexto do professor ----------------------------------------------- #


async def get_professor_contexto(
    session: SessionDep,
    user: ProfessorWebDep,
) -> tuple[Usuario, AnoLetivo, Professor]:
    """Resolve (usuário, ano mais recente, registro Professor) do professor logado.

    O ano vigente para o professor é sempre o mais recente em que ele possui um
    registro vinculado por ``usuario_id`` (o clone preserva esse vínculo).
    """

    row = (
        await session.execute(
            select(Professor, AnoLetivo)
            .join(AnoLetivo, AnoLetivo.id == Professor.ano_letivo_id)
            .where(Professor.usuario_id == user.id)
            .order_by(AnoLetivo.ano.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        raise RedirectError("/login")
    professor, ano = row
    return user, ano, professor


ProfessorContextoDep = Annotated[
    tuple[Usuario, AnoLetivo, Professor], Depends(get_professor_contexto)
]
