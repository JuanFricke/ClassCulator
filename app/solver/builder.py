"""Constrói uma `ProblemInstance` a partir do estado atual do banco."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Disciplina,
    DisponibilidadeProfessor,
    Professor,
    ProfessorDisciplina,
    Sala,
    Turma,
    TurmaDisciplina,
)
from app.models.sala import SalaTipo
from app.solver.domain import (
    DIAS,
    SLOTS_DIA_MAX,
    SLOTS_POR_DIA_DEFAULT,
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

    turmas = [
        TurmaInfo(
            id=t.id,
            identificador=t.identificador,
            slots_por_dia=_coerce_slots_por_dia(t.slots_por_dia, t.identificador),
        )
        for t in turmas_rows
    ]
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

    indisp_rows = (
        await session.execute(
            select(DisponibilidadeProfessor).where(DisponibilidadeProfessor.disponivel.is_(False))
        )
    ).scalars().all()
    indisponiveis: dict[int, set[tuple[int, int]]] = {}
    for d in indisp_rows:
        indisponiveis.setdefault(d.professor_id, set()).add((d.dia, d.slot))

    prof_disc_rows = (
        await session.execute(select(ProfessorDisciplina))
    ).scalars().all()
    professores_por_disciplina: dict[int, list[int]] = {}
    for row in prof_disc_rows:
        professores_por_disciplina.setdefault(row.disciplina_id, []).append(row.professor_id)

    turma_ids = [t.id for t in turmas]
    curriculo_rows = (
        await session.execute(
            select(TurmaDisciplina).where(TurmaDisciplina.turma_id.in_(turma_ids))
        )
    ).scalars().all()
    if not curriculo_rows:
        raise ValueError("Nenhum currículo cadastrado para as turmas do semestre.")

    disc_by_id = {d.id: d for d in disciplinas}
    prof_by_id = {p.id: p for p in professores}
    capacidade_por_prof: dict[int, int] = {}
    carga_por_prof: dict[int, int] = {}
    for pid in prof_by_id:
        capacidade_por_prof[pid] = (DIAS * SLOTS_DIA_MAX) - len(indisponiveis.get(pid, set()))
        carga_por_prof[pid] = 0

    warnings: list[str] = []
    aulas: list[Aula] = []
    idx = 0
    for td in curriculo_rows:
        disc = disc_by_id.get(td.disciplina_id)
        if disc is None:
            continue
        professor_id = _resolve_professor_for_curriculo_item(
            td,
            disc,
            professores_por_disciplina,
            capacidade_por_prof,
            carga_por_prof,
            prof_by_id,
            warnings,
        )
        for k in range(disc.carga_semanal):
            aulas.append(
                Aula(
                    idx=idx,
                    turma_id=td.turma_id,
                    disciplina_id=td.disciplina_id,
                    professor_id=professor_id,
                    k=k,
                )
            )
            idx += 1

    if not aulas:
        raise ValueError("Currículo das turmas não gera aulas (carga semanal zerada?).")

    _validar_cobertura_turmas(turmas, aulas)

    return ProblemInstance(
        turmas=turmas,
        disciplinas=disciplinas,
        professores=professores,
        salas=salas,
        aulas=aulas,
        indisponiveis=indisponiveis,
        warnings=warnings,
    )


def _validar_cobertura_turmas(
    turmas: list[TurmaInfo], aulas: list[Aula]
) -> None:
    """Garante que cada turma tem aulas suficientes para preencher exatamente os
    `turma.total_slots` períodos da sua semana — caso contrário, a grade ficaria
    com horários vazios ou excedentes e a geração deve ser abortada.
    """

    contagens: dict[int, int] = {t.id: 0 for t in turmas}
    for a in aulas:
        contagens[a.turma_id] = contagens.get(a.turma_id, 0) + 1

    faltantes: list[str] = []
    excedentes: list[str] = []
    for t in turmas:
        carga = contagens.get(t.id, 0)
        alvo = t.total_slots
        if carga < alvo:
            faltantes.append(
                f"{t.identificador} (carga={carga}, faltam {alvo - carga} aulas, alvo={alvo})"
            )
        elif carga > alvo:
            excedentes.append(
                f"{t.identificador} (carga={carga}, excede {carga - alvo} aulas, alvo={alvo})"
            )

    if faltantes or excedentes:
        partes: list[str] = []
        if faltantes:
            partes.append(
                "Turmas com currículo insuficiente para preencher os períodos semanais: "
                + ", ".join(faltantes)
            )
        if excedentes:
            partes.append(
                "Turmas com currículo acima da capacidade semanal: "
                + ", ".join(excedentes)
            )
        raise InstanceConfigurationError(
            " | ".join(partes)
            + ". Revise as disciplinas/professores atribuídos para que cada "
            "turma totalize exatamente sum(slots_por_dia) aulas/semana."
        )


def _coerce_slots_por_dia(raw: object, identificador: str) -> tuple[int, ...]:
    """Normaliza o JSON vindo do banco para um tuple de inteiros de tamanho DIAS.

    Falha cedo via :class:`InstanceConfigurationError` se o valor estiver
    corrompido (tamanho errado ou tipo inválido), em vez de deixar o solver
    falhar mais à frente com um erro críptico.
    """

    if raw is None:
        return SLOTS_POR_DIA_DEFAULT
    if not isinstance(raw, (list, tuple)):
        raise InstanceConfigurationError(
            f"Turma {identificador!r}: slots_por_dia deveria ser uma lista de "
            f"{DIAS} inteiros, recebido {type(raw).__name__}."
        )
    if len(raw) != DIAS:
        raise InstanceConfigurationError(
            f"Turma {identificador!r}: slots_por_dia tem {len(raw)} entradas; "
            f"esperado {DIAS} (um valor por dia útil)."
        )
    valores: list[int] = []
    for i, v in enumerate(raw):
        if not isinstance(v, int) or isinstance(v, bool):
            raise InstanceConfigurationError(
                f"Turma {identificador!r}: slots_por_dia[{i}]={v!r} não é inteiro."
            )
        if v < 0 or v > SLOTS_DIA_MAX:
            raise InstanceConfigurationError(
                f"Turma {identificador!r}: slots_por_dia[{i}]={v} fora do "
                f"intervalo permitido [0, {SLOTS_DIA_MAX}]."
            )
        valores.append(v)
    return tuple(valores)


def _resolve_professor_for_curriculo_item(
    td: TurmaDisciplina,
    disciplina: DisciplinaInfo,
    professores_por_disciplina: dict[int, list[int]],
    capacidade_por_prof: dict[int, int],
    carga_por_prof: dict[int, int],
    prof_by_id: dict[int, ProfessorInfo],
    warnings: list[str],
) -> int:
    candidatos = professores_por_disciplina.get(td.disciplina_id, [])
    professor_atual = td.professor_id
    carga_disc = disciplina.carga_semanal

    def restante(pid: int) -> int:
        return capacidade_por_prof.get(pid, 0) - carga_por_prof.get(pid, 0)

    escolhido = professor_atual
    if candidatos:
        if professor_atual not in candidatos:
            alt = _pick_best_professor(candidatos, capacidade_por_prof, carga_por_prof, carga_disc)
            if alt is not None:
                escolhido = alt
                warnings.append(
                    "[autoajuste] "
                    f"Turma {td.turma_id}, disciplina '{disciplina.nome}': "
                    f"professor {professor_atual} não é habilitado; "
                    f"substituído por {prof_by_id.get(alt).nome if alt in prof_by_id else alt}."
                )
        elif restante(professor_atual) < carga_disc:
            alt = _pick_best_professor(candidatos, capacidade_por_prof, carga_por_prof, carga_disc)
            if alt is not None and alt != professor_atual:
                warnings.append(
                    "[autoajuste] "
                    f"Turma {td.turma_id}, disciplina '{disciplina.nome}': "
                    f"{prof_by_id.get(professor_atual).nome if professor_atual in prof_by_id else professor_atual} "
                    f"sem capacidade suficiente ({restante(professor_atual)} slots restantes); "
                    f"substituído por {prof_by_id.get(alt).nome if alt in prof_by_id else alt}."
                )
                escolhido = alt

    carga_por_prof[escolhido] = carga_por_prof.get(escolhido, 0) + carga_disc
    return escolhido


def _pick_best_professor(
    candidatos: list[int],
    capacidade_por_prof: dict[int, int],
    carga_por_prof: dict[int, int],
    carga_disc: int,
) -> int | None:
    with_capacity = [
        pid
        for pid in candidatos
        if (capacidade_por_prof.get(pid, 0) - carga_por_prof.get(pid, 0)) >= carga_disc
    ]
    pool = with_capacity if with_capacity else candidatos
    if not pool:
        return None
    return max(pool, key=lambda pid: capacidade_por_prof.get(pid, 0) - carga_por_prof.get(pid, 0))
