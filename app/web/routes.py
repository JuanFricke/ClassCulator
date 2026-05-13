"""Páginas SSR renderizadas com Jinja2 + Bulma."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.core.deps import SessionDep
from app.core.ensino import infer_turma_ensino
from app.models import (
    AlocacaoSlot,
    Disciplina,
    DisponibilidadeProfessor,
    GradeHoraria,
    Professor,
    ProfessorDisciplina,
    Sala,
    Turma,
    TurmaDisciplina,
)
from app.solver.constraints import calcular_score
from app.solver.domain import DIAS, SLOTS_DIA, SLOTS_POR_TURMA

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

DIAS_LABELS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
SLOT_LABELS = [f"{7 + i}h–{8 + i}h" for i in range(SLOTS_DIA)]

router = APIRouter()


def render(request: Request, template_name: str, /, **context: Any) -> HTMLResponse:
    """Renderiza um template injetando os globais comuns ao layout."""

    payload: dict[str, Any] = {
        "DIAS": list(range(DIAS)),
        "SLOTS": list(range(SLOTS_DIA)),
        "DIAS_LABELS": DIAS_LABELS,
        "SLOT_LABELS": SLOT_LABELS,
        "active": "",
    }
    payload.update(context)
    return templates.TemplateResponse(request, template_name, payload)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, session: SessionDep):
    counts = await _contar_entidades(session)
    ultima = (
        await session.execute(
            select(GradeHoraria).order_by(GradeHoraria.criado_em.desc()).limit(1)
        )
    ).scalar_one_or_none()

    readiness = await _calcular_prontidao(session, counts)

    return render(
        request,
        "home.html",
        active="home",
        counts=counts,
        ultima=ultima,
        readiness=readiness,
        slots_por_turma=SLOTS_POR_TURMA,
    )


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding(request: Request, session: SessionDep):
    counts = await _contar_entidades(session)
    readiness = await _calcular_prontidao(session, counts)
    return render(
        request,
        "onboarding.html",
        active="onboarding",
        counts=counts,
        readiness=readiness,
    )


@router.get("/gestao", response_class=HTMLResponse)
async def gestao(request: Request, session: SessionDep):
    counts = await _contar_entidades(session)
    readiness = await _calcular_prontidao(session, counts)
    return render(
        request,
        "gestao.html",
        active="gestao",
        counts=counts,
        readiness=readiness,
    )


async def _contar_entidades(session: SessionDep) -> dict[str, int]:
    return {
        "professores": (
            await session.execute(select(func.count()).select_from(Professor))
        ).scalar_one(),
        "turmas": (await session.execute(select(func.count()).select_from(Turma))).scalar_one(),
        "disciplinas": (
            await session.execute(select(func.count()).select_from(Disciplina))
        ).scalar_one(),
        "salas": (await session.execute(select(func.count()).select_from(Sala))).scalar_one(),
        "grades": (
            await session.execute(select(func.count()).select_from(GradeHoraria))
        ).scalar_one(),
    }


async def _mapa_professores_por_disciplina(
    session: SessionDep, disciplina_ids: list[int] | None = None
) -> dict[int, list[int]]:
    stmt = select(ProfessorDisciplina.disciplina_id, ProfessorDisciplina.professor_id)
    if disciplina_ids:
        stmt = stmt.where(ProfessorDisciplina.disciplina_id.in_(disciplina_ids))
    rows = (await session.execute(stmt)).all()
    mapa: dict[int, list[int]] = {}
    for disciplina_id, professor_id in rows:
        mapa.setdefault(disciplina_id, []).append(professor_id)
    return mapa


async def _calcular_prontidao(session: SessionDep, counts: dict) -> dict:
    """Resume o estado da configuração para o painel inicial.

    Retorna uma estrutura com flags por etapa e, se houver turmas, a carga
    atual e o que falta para cada uma fechar os SLOTS_POR_TURMA períodos.
    """

    turmas_ok = True
    turmas_problema: list[dict] = []
    if counts["turmas"] > 0:
        cargas = await session.execute(
            select(
                Turma.id,
                Turma.identificador,
                func.coalesce(func.sum(Disciplina.carga_semanal), 0).label("carga"),
            )
            .join(TurmaDisciplina, TurmaDisciplina.turma_id == Turma.id, isouter=True)
            .join(Disciplina, Disciplina.id == TurmaDisciplina.disciplina_id, isouter=True)
            .group_by(Turma.id, Turma.identificador)
            .order_by(Turma.identificador)
        )
        for row in cargas.all():
            falta = SLOTS_POR_TURMA - int(row.carga)
            if falta != 0:
                turmas_ok = False
                turmas_problema.append(
                    {
                        "id": row.id,
                        "identificador": row.identificador,
                        "carga": int(row.carga),
                        "falta": falta,
                    }
                )

    etapas = [
        {
            "id": "disciplinas",
            "ok": counts["disciplinas"] > 0,
            "titulo": "Cadastrar disciplinas",
            "detalhe": (
                f"{counts['disciplinas']} disciplina(s) cadastrada(s)."
                if counts["disciplinas"] > 0
                else "Nenhuma disciplina cadastrada ainda."
            ),
            "action_url": "/disciplinas/novo" if counts["disciplinas"] == 0 else "",
            "action_label": "Cadastrar",
        },
        {
            "id": "professores",
            "ok": counts["professores"] > 0,
            "titulo": "Cadastrar professores",
            "detalhe": (
                f"{counts['professores']} professor(es) com horários definidos."
                if counts["professores"] > 0
                else "Nenhum professor cadastrado ainda."
            ),
            "action_url": "/professores/novo" if counts["professores"] == 0 else "",
            "action_label": "Cadastrar",
        },
        {
            "id": "salas",
            "ok": counts["salas"] > 0,
            "titulo": "Cadastrar salas e laboratórios",
            "detalhe": (
                f"{counts['salas']} ambiente(s) cadastrado(s)."
                if counts["salas"] > 0
                else "Nenhuma sala cadastrada ainda."
            ),
            "action_url": "/salas/novo" if counts["salas"] == 0 else "",
            "action_label": "Cadastrar",
        },
        {
            "id": "turmas",
            "ok": counts["turmas"] > 0 and turmas_ok,
            "titulo": "Definir turmas e currículos",
            "detalhe": _detalhe_turmas(counts["turmas"], turmas_problema),
            "action_url": "/turmas" if turmas_problema else ("/turmas/novo" if counts["turmas"] == 0 else ""),
            "action_label": "Ajustar" if turmas_problema else "Cadastrar",
        },
    ]
    tudo_pronto = all(e["ok"] for e in etapas)
    return {
        "etapas": etapas,
        "tudo_pronto": tudo_pronto,
        "turmas_problema": turmas_problema,
    }


def _detalhe_turmas(qtd_turmas: int, problemas: list[dict]) -> str:
    if qtd_turmas == 0:
        return "Nenhuma turma cadastrada ainda."
    if not problemas:
        return f"{qtd_turmas} turma(s) com currículo completo (30 aulas/semana)."
    nomes = ", ".join(
        f"{p['identificador']} ({p['carga']}/{SLOTS_POR_TURMA})" for p in problemas[:4]
    )
    extra = f" +{len(problemas) - 4} outras" if len(problemas) > 4 else ""
    return f"{len(problemas)} turma(s) com currículo incompleto: {nomes}{extra}."


# --- Professores ----------------------------------------------------------- #


@router.get("/professores", response_class=HTMLResponse)
async def professores_list(request: Request, session: SessionDep):
    profs = (await session.execute(select(Professor).order_by(Professor.nome))).scalars().all()
    pd_rows = (await session.execute(select(ProfessorDisciplina))).scalars().all()
    discs = {
        d.id: d for d in (await session.execute(select(Disciplina))).scalars().all()
    }
    by_prof: dict[int, list[Disciplina]] = {}
    for pd in pd_rows:
        if pd.disciplina_id in discs:
            by_prof.setdefault(pd.professor_id, []).append(discs[pd.disciplina_id])
    return render(
        request,
        "professores/list.html",
        active="professores",
        professores=profs,
        disciplinas_por_prof=by_prof,
    )


@router.get("/professores/novo", response_class=HTMLResponse)
async def professor_novo(request: Request, session: SessionDep):
    discs = (
        await session.execute(select(Disciplina).order_by(Disciplina.ensino, Disciplina.nome))
    ).scalars().all()
    return render(
        request,
        "professores/form.html",
        active="professores",
        professor=None,
        disciplinas=discs,
        disciplina_ids=[],
    )


@router.get("/professores/{professor_id}", response_class=HTMLResponse)
async def professor_edit(professor_id: int, request: Request, session: SessionDep):
    prof = await session.get(Professor, professor_id)
    if prof is None:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    discs = (
        await session.execute(select(Disciplina).order_by(Disciplina.ensino, Disciplina.nome))
    ).scalars().all()
    pd_rows = (
        await session.execute(
            select(ProfessorDisciplina.disciplina_id).where(
                ProfessorDisciplina.professor_id == professor_id
            )
        )
    ).all()
    selecionadas = [r[0] for r in pd_rows]
    indisp_rows = (
        await session.execute(
            select(DisponibilidadeProfessor).where(
                DisponibilidadeProfessor.professor_id == professor_id
            )
        )
    ).scalars().all()
    indisp = {(d.dia, d.slot): d.disponivel for d in indisp_rows}
    return render(
        request,
        "professores/form.html",
        active="professores",
        professor=prof,
        disciplinas=discs,
        disciplina_ids=selecionadas,
        disponibilidade=indisp,
    )


# --- Disciplinas ----------------------------------------------------------- #


@router.get("/disciplinas", response_class=HTMLResponse)
async def disciplinas_list(request: Request, session: SessionDep):
    disciplinas = (
        await session.execute(select(Disciplina).order_by(Disciplina.ensino, Disciplina.nome))
    ).scalars().all()
    return render(
        request, "disciplinas/list.html", active="disciplinas", disciplinas=disciplinas
    )


@router.get("/disciplinas/novo", response_class=HTMLResponse)
async def disciplina_novo(request: Request):
    return render(
        request,
        "disciplinas/form.html",
        active="disciplinas",
        disciplina=None,
        ensino_options=["fundamental", "medio", "ambos"],
    )


@router.get("/disciplinas/{disciplina_id}", response_class=HTMLResponse)
async def disciplina_edit(disciplina_id: int, request: Request, session: SessionDep):
    disc = await session.get(Disciplina, disciplina_id)
    if disc is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    return render(
        request,
        "disciplinas/form.html",
        active="disciplinas",
        disciplina=disc,
        ensino_options=["fundamental", "medio", "ambos"],
    )


# --- Salas ----------------------------------------------------------------- #


@router.get("/salas", response_class=HTMLResponse)
async def salas_list(request: Request, session: SessionDep):
    salas = (await session.execute(select(Sala).order_by(Sala.nome))).scalars().all()
    return render(request, "salas/list.html", active="salas", salas=salas)


@router.get("/salas/novo", response_class=HTMLResponse)
async def sala_novo(request: Request):
    return render(request, "salas/form.html", active="salas", sala=None)


@router.get("/salas/{sala_id}", response_class=HTMLResponse)
async def sala_edit(sala_id: int, request: Request, session: SessionDep):
    sala = await session.get(Sala, sala_id)
    if sala is None:
        raise HTTPException(status_code=404, detail="Sala não encontrada")
    return render(request, "salas/form.html", active="salas", sala=sala)


# --- Turmas ---------------------------------------------------------------- #


@router.get("/turmas", response_class=HTMLResponse)
async def turmas_list(request: Request, session: SessionDep):
    turmas = (
        await session.execute(select(Turma).order_by(Turma.identificador))
    ).scalars().all()
    cargas = await session.execute(
        select(
            Turma.id,
            func.coalesce(func.sum(Disciplina.carga_semanal), 0).label("carga"),
        )
        .join(TurmaDisciplina, TurmaDisciplina.turma_id == Turma.id, isouter=True)
        .join(Disciplina, Disciplina.id == TurmaDisciplina.disciplina_id, isouter=True)
        .group_by(Turma.id)
    )
    carga_por_turma = {row.id: int(row.carga) for row in cargas}
    return render(
        request,
        "turmas/list.html",
        active="turmas",
        turmas=turmas,
        carga_por_turma=carga_por_turma,
        carga_alvo=SLOTS_POR_TURMA,
    )


@router.get("/turmas/novo", response_class=HTMLResponse)
async def turma_novo(request: Request, session: SessionDep):
    ensino_default = "fundamental"
    discs = (
        await session.execute(
            select(Disciplina)
            .where(Disciplina.ensino.in_([ensino_default, "ambos"]))
            .order_by(Disciplina.nome)
        )
    ).scalars().all()
    profs = (
        await session.execute(select(Professor).order_by(Professor.nome))
    ).scalars().all()
    professores_por_disciplina = await _mapa_professores_por_disciplina(
        session, [d.id for d in discs]
    )
    return render(
        request,
        "turmas/form.html",
        active="turmas",
        turma=None,
        disciplinas=discs,
        professores=profs,
        curriculo=[],
        carga_atual=0,
        carga_alvo=SLOTS_POR_TURMA,
        professores_por_disciplina=professores_por_disciplina,
        ensino_options=["fundamental", "medio", "ambos"],
    )


@router.get("/turmas/{turma_id}", response_class=HTMLResponse)
async def turma_edit(turma_id: int, request: Request, session: SessionDep):
    turma = await session.get(Turma, turma_id)
    if turma is None:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    ensino_turma = infer_turma_ensino(turma.identificador, turma.ensino)
    discs = (
        await session.execute(
            select(Disciplina)
            .where(Disciplina.ensino.in_([ensino_turma, "ambos"]))
            .order_by(Disciplina.nome)
        )
    ).scalars().all()
    profs = (
        await session.execute(select(Professor).order_by(Professor.nome))
    ).scalars().all()
    professores_por_disciplina = await _mapa_professores_por_disciplina(
        session, [d.id for d in discs]
    )
    curriculo_db = (
        await session.execute(select(TurmaDisciplina).where(TurmaDisciplina.turma_id == turma_id))
    ).scalars().all()
    curriculo_por_disciplina = {c.disciplina_id: c for c in curriculo_db}
    curriculo = []
    for disciplina in discs:
        existing = curriculo_por_disciplina.get(disciplina.id)
        if existing:
            curriculo.append(existing)
            continue
        professores_ids = professores_por_disciplina.get(disciplina.id, [])
        professor_padrao = professores_ids[0] if professores_ids else 0
        curriculo.append(
            {
                "disciplina_id": disciplina.id,
                "professor_id": professor_padrao,
            }
        )
    disc_by_id = {d.id: d for d in discs}
    def _disciplina_id(item: TurmaDisciplina | dict[str, int]) -> int:
        if isinstance(item, dict):
            return item["disciplina_id"]
        return item.disciplina_id

    carga_atual = sum(
        disc_by_id[_disciplina_id(c)].carga_semanal
        for c in curriculo
        if _disciplina_id(c) in disc_by_id
    )
    return render(
        request,
        "turmas/form.html",
        active="turmas",
        turma=turma,
        disciplinas=discs,
        professores=profs,
        curriculo=curriculo,
        carga_atual=carga_atual,
        carga_alvo=SLOTS_POR_TURMA,
        professores_por_disciplina=professores_por_disciplina,
        ensino_options=["fundamental", "medio", "ambos"],
    )


# --- Grade ----------------------------------------------------------------- #


@router.get("/grade", response_class=HTMLResponse)
async def grade_list(request: Request, session: SessionDep):
    grades = (
        await session.execute(select(GradeHoraria).order_by(GradeHoraria.criado_em.desc()).limit(50))
    ).scalars().all()
    return render(request, "grade/list.html", active="grade", grades=grades)


@router.get("/grade/nova", response_class=HTMLResponse)
async def grade_nova(request: Request, session: SessionDep):
    semestres = (
        await session.execute(select(Turma.semestre).distinct().order_by(Turma.semestre))
    ).all()
    semestres_list = [s[0] for s in semestres] or ["2026/1"]

    # Pré-checagem: avisar antes de submeter se algum currículo está incompleto.
    counts = {
        "professores": (await session.execute(select(func.count()).select_from(Professor))).scalar_one(),
        "turmas": (await session.execute(select(func.count()).select_from(Turma))).scalar_one(),
        "disciplinas": (await session.execute(select(func.count()).select_from(Disciplina))).scalar_one(),
        "salas": (await session.execute(select(func.count()).select_from(Sala))).scalar_one(),
        "grades": 0,
    }
    readiness = await _calcular_prontidao(session, counts)

    return render(
        request,
        "grade/nova.html",
        active="grade",
        semestres=semestres_list,
        readiness=readiness,
    )


@router.get("/grade/{grade_id}", response_class=HTMLResponse)
async def grade_detail(grade_id: int, request: Request, session: SessionDep):
    grade = await session.get(GradeHoraria, grade_id)
    if grade is None:
        raise HTTPException(status_code=404, detail="Grade não encontrada")

    alocacoes = (
        await session.execute(
            select(AlocacaoSlot).where(AlocacaoSlot.grade_id == grade_id)
        )
    ).scalars().all()
    turmas = {
        t.id: t for t in (await session.execute(select(Turma))).scalars().all()
    }
    discs = {
        d.id: d for d in (await session.execute(select(Disciplina))).scalars().all()
    }
    profs = {
        p.id: p for p in (await session.execute(select(Professor))).scalars().all()
    }
    salas = {s.id: s for s in (await session.execute(select(Sala))).scalars().all()}

    grades_por_turma: dict[int, list[list[dict | None]]] = {}
    for tid in turmas:
        grades_por_turma[tid] = [[None for _ in range(SLOTS_DIA)] for _ in range(DIAS)]
    for a in alocacoes:
        cell = {
            "disciplina": discs.get(a.disciplina_id),
            "professor": profs.get(a.professor_id),
            "sala": salas.get(a.sala_id) if a.sala_id else None,
        }
        if a.turma_id in grades_por_turma:
            grades_por_turma[a.turma_id][a.dia][a.slot] = cell

    breakdown = None
    if alocacoes:
        from app.solver.builder import build_instance

        try:
            instance = await build_instance(session, grade.semestre)
            assignments = {}
            aulas_lookup: dict[tuple[int, int], list] = {}
            for aula in instance.aulas:
                aulas_lookup.setdefault((aula.turma_id, aula.disciplina_id), []).append(aula)
            for a in alocacoes:
                key = (a.turma_id, a.disciplina_id)
                if aulas_lookup.get(key):
                    aula = aulas_lookup[key].pop(0)
                    assignments[aula.idx] = (a.dia, a.slot)
            score, breakdown = calcular_score(instance, assignments)
        except Exception:  # noqa: BLE001
            breakdown = None

    turmas_ordenadas = sorted(turmas.values(), key=lambda t: t.identificador)

    return render(
        request,
        "grade/detail.html",
        active="grade",
        grade=grade,
        turmas=turmas,
        turmas_ordenadas=turmas_ordenadas,
        grades_por_turma=grades_por_turma,
        breakdown=breakdown,
    )
