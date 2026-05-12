"""Constrói uma `ProblemInstance` a partir do estado atual do banco."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Disciplina,
    DisponibilidadeProfessor,
    Professor,
    Sala,
    Turma,
    TurmaDisciplina,
)
from app.models.sala import SalaTipo
from app.solver.domain import (
    SLOTS_POR_TURMA,
    Aula,
    DisciplinaInfo,
    InstanceConfigurationError,
    ProblemInstance,
    ProfessorInfo,
    SalaInfo,
    TurmaInfo,
)


async def build_instance(session: AsyncSession, semestre: str) -> ProblemInstance:
    turmas_rows = (
        await session.execute(select(Turma).where(Turma.semestre == semestre).order_by(Turma.id))
    ).scalars().all()
    if not turmas_rows:
        raise ValueError(f"Nenhuma turma encontrada para o semestre {semestre!r}.")

    disciplinas_rows = (
        await session.execute(select(Disciplina).order_by(Disciplina.id))
    ).scalars().all()
    professores_rows = (
        await session.execute(select(Professor).order_by(Professor.id))
    ).scalars().all()
    salas_rows = (await session.execute(select(Sala).order_by(Sala.id))).scalars().all()

    turmas = [TurmaInfo(id=t.id, identificador=t.identificador) for t in turmas_rows]
    disciplinas = [
        DisciplinaInfo(
            id=d.id,
            nome=d.nome,
            area=d.area,
            carga_semanal=d.carga_semanal,
            requer_lab=d.requer_lab,
            eh_teorica=d.eh_teorica,
        )
        for d in disciplinas_rows
    ]
    professores = [ProfessorInfo(id=p.id, nome=p.nome) for p in professores_rows]
    salas = [SalaInfo(id=s.id, nome=s.nome, eh_lab=s.tipo == SalaTipo.LAB) for s in salas_rows]

    turma_ids = [t.id for t in turmas]
    curriculo_rows = (
        await session.execute(
            select(TurmaDisciplina).where(TurmaDisciplina.turma_id.in_(turma_ids))
        )
    ).scalars().all()
    if not curriculo_rows:
        raise ValueError("Nenhum currículo cadastrado para as turmas do semestre.")

    disc_by_id = {d.id: d for d in disciplinas}
    aulas: list[Aula] = []
    idx = 0
    for td in curriculo_rows:
        disc = disc_by_id.get(td.disciplina_id)
        if disc is None:
            continue
        for k in range(disc.carga_semanal):
            aulas.append(
                Aula(
                    idx=idx,
                    turma_id=td.turma_id,
                    disciplina_id=td.disciplina_id,
                    professor_id=td.professor_id,
                    k=k,
                )
            )
            idx += 1

    if not aulas:
        raise ValueError("Currículo das turmas não gera aulas (carga semanal zerada?).")

    _validar_cobertura_turmas(turmas, aulas)

    indisp_rows = (
        await session.execute(
            select(DisponibilidadeProfessor).where(DisponibilidadeProfessor.disponivel.is_(False))
        )
    ).scalars().all()
    indisponiveis: dict[int, set[tuple[int, int]]] = {}
    for d in indisp_rows:
        indisponiveis.setdefault(d.professor_id, set()).add((d.dia, d.slot))

    return ProblemInstance(
        turmas=turmas,
        disciplinas=disciplinas,
        professores=professores,
        salas=salas,
        aulas=aulas,
        indisponiveis=indisponiveis,
    )


def _validar_cobertura_turmas(
    turmas: list[TurmaInfo], aulas: list[Aula]
) -> None:
    """Garante que cada turma tem aulas suficientes para preencher todos os
    `SLOTS_POR_TURMA` períodos da semana — caso contrário, a grade ficaria com
    horários vazios e a geração deve ser abortada.
    """

    contagens: dict[int, int] = {t.id: 0 for t in turmas}
    for a in aulas:
        contagens[a.turma_id] = contagens.get(a.turma_id, 0) + 1

    faltantes: list[str] = []
    excedentes: list[str] = []
    for t in turmas:
        carga = contagens.get(t.id, 0)
        if carga < SLOTS_POR_TURMA:
            faltantes.append(
                f"{t.identificador} (carga={carga}, faltam {SLOTS_POR_TURMA - carga} aulas)"
            )
        elif carga > SLOTS_POR_TURMA:
            excedentes.append(
                f"{t.identificador} (carga={carga}, excede {carga - SLOTS_POR_TURMA} aulas)"
            )

    if faltantes or excedentes:
        partes: list[str] = []
        if faltantes:
            partes.append(
                "Turmas com currículo insuficiente para preencher os "
                f"{SLOTS_POR_TURMA} períodos semanais: " + ", ".join(faltantes)
            )
        if excedentes:
            partes.append(
                "Turmas com currículo acima da capacidade semanal: "
                + ", ".join(excedentes)
            )
        raise InstanceConfigurationError(
            " | ".join(partes)
            + ". Revise as disciplinas/professores atribuídos para que cada "
            f"turma totalize exatamente {SLOTS_POR_TURMA} aulas/semana."
        )
