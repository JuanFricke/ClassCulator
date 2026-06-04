"""Criação e clonagem de anos letivos.

Cada ano letivo é uma partição independente dos dados. Ao criar um novo ano a
partir de outro, copiamos a configuração (disciplinas, salas, professores e seus
vínculos, turmas e currículos) remapeando os ids antigos para os novos. As
grades horárias (resultados do solver) NÃO são copiadas — cada ano começa sem
grades.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnoLetivo,
    Disciplina,
    DisponibilidadeProfessor,
    Professor,
    ProfessorDisciplina,
    Sala,
    Turma,
    TurmaDisciplina,
)


class AnoJaExisteError(ValueError):
    """Levantado ao tentar criar um ano letivo que já existe."""


async def criar_ano(
    session: AsyncSession,
    novo_ano: int,
    *,
    source_ano_id: int | None = None,
) -> AnoLetivo:
    """Cria um ano letivo, opcionalmente clonando os dados de ``source_ano_id``.

    Se ``source_ano_id`` for ``None``, cria um ano vazio.
    """

    existente = (
        await session.execute(select(AnoLetivo).where(AnoLetivo.ano == novo_ano))
    ).scalar_one_or_none()
    if existente is not None:
        raise AnoJaExisteError(f"O ano letivo {novo_ano} já existe.")

    ano = AnoLetivo(ano=novo_ano)
    session.add(ano)
    await session.flush()

    if source_ano_id is not None:
        await _clonar_dados(session, source_ano_id, ano.id)

    await session.commit()
    await session.refresh(ano)
    return ano


async def _clonar_dados(session: AsyncSession, source_ano_id: int, novo_ano_id: int) -> None:
    # Disciplinas
    disc_map: dict[int, int] = {}
    disciplinas = (
        await session.execute(select(Disciplina).where(Disciplina.ano_letivo_id == source_ano_id))
    ).scalars().all()
    for d in disciplinas:
        nova = Disciplina(
            ano_letivo_id=novo_ano_id,
            nome=d.nome,
            ensino=d.ensino,
            area=d.area,
            carga_semanal=d.carga_semanal,
            requer_lab=d.requer_lab,
            eh_teorica=d.eh_teorica,
        )
        session.add(nova)
        await session.flush()
        disc_map[d.id] = nova.id

    # Salas
    salas = (
        await session.execute(select(Sala).where(Sala.ano_letivo_id == source_ano_id))
    ).scalars().all()
    for s in salas:
        session.add(
            Sala(
                ano_letivo_id=novo_ano_id,
                nome=s.nome,
                tipo=s.tipo,
                capacidade=s.capacidade,
            )
        )

    # Professores (preserva o vínculo de conta usuario_id)
    prof_map: dict[int, int] = {}
    professores = (
        await session.execute(select(Professor).where(Professor.ano_letivo_id == source_ano_id))
    ).scalars().all()
    for p in professores:
        novo = Professor(
            ano_letivo_id=novo_ano_id,
            usuario_id=p.usuario_id,
            nome=p.nome,
            email=p.email,
        )
        session.add(novo)
        await session.flush()
        prof_map[p.id] = novo.id

    # Vínculos professor-disciplina
    pd_rows = (
        await session.execute(
            select(ProfessorDisciplina).where(
                ProfessorDisciplina.professor_id.in_(prof_map.keys() or [-1])
            )
        )
    ).scalars().all()
    for pd in pd_rows:
        if pd.professor_id in prof_map and pd.disciplina_id in disc_map:
            session.add(
                ProfessorDisciplina(
                    professor_id=prof_map[pd.professor_id],
                    disciplina_id=disc_map[pd.disciplina_id],
                )
            )

    # Disponibilidade dos professores
    disp_rows = (
        await session.execute(
            select(DisponibilidadeProfessor).where(
                DisponibilidadeProfessor.professor_id.in_(prof_map.keys() or [-1])
            )
        )
    ).scalars().all()
    for disp in disp_rows:
        if disp.professor_id in prof_map:
            session.add(
                DisponibilidadeProfessor(
                    professor_id=prof_map[disp.professor_id],
                    dia=disp.dia,
                    slot=disp.slot,
                    disponivel=disp.disponivel,
                )
            )

    # Turmas
    turma_map: dict[int, int] = {}
    turmas = (
        await session.execute(select(Turma).where(Turma.ano_letivo_id == source_ano_id))
    ).scalars().all()
    for t in turmas:
        nova = Turma(
            ano_letivo_id=novo_ano_id,
            identificador=t.identificador,
            ensino=t.ensino,
            qtd_alunos=t.qtd_alunos,
            slots_por_dia=list(t.slots_por_dia or []),
        )
        session.add(nova)
        await session.flush()
        turma_map[t.id] = nova.id

    # Currículo (turma-disciplina)
    td_rows = (
        await session.execute(
            select(TurmaDisciplina).where(
                TurmaDisciplina.turma_id.in_(turma_map.keys() or [-1])
            )
        )
    ).scalars().all()
    for td in td_rows:
        if td.turma_id in turma_map and td.disciplina_id in disc_map:
            session.add(
                TurmaDisciplina(
                    turma_id=turma_map[td.turma_id],
                    disciplina_id=disc_map[td.disciplina_id],
                    professor_id=prof_map.get(td.professor_id) if td.professor_id else None,
                )
            )
