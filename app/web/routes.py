"""Páginas SSR renderizadas com Jinja2 + Bulma."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.core.deps import SessionDep
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
from app.solver.domain import DIAS, SLOTS_DIA

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
    counts = {
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
    ultima = (
        await session.execute(
            select(GradeHoraria).order_by(GradeHoraria.criado_em.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return render(request, "home.html", active="home", counts=counts, ultima=ultima)


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
        await session.execute(select(Disciplina).order_by(Disciplina.nome))
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
        await session.execute(select(Disciplina).order_by(Disciplina.nome))
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
        await session.execute(select(Disciplina).order_by(Disciplina.nome))
    ).scalars().all()
    return render(
        request, "disciplinas/list.html", active="disciplinas", disciplinas=disciplinas
    )


@router.get("/disciplinas/novo", response_class=HTMLResponse)
async def disciplina_novo(request: Request):
    return render(request, "disciplinas/form.html", active="disciplinas", disciplina=None)


@router.get("/disciplinas/{disciplina_id}", response_class=HTMLResponse)
async def disciplina_edit(disciplina_id: int, request: Request, session: SessionDep):
    disc = await session.get(Disciplina, disciplina_id)
    if disc is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    return render(request, "disciplinas/form.html", active="disciplinas", disciplina=disc)


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
    return render(request, "turmas/list.html", active="turmas", turmas=turmas)


@router.get("/turmas/novo", response_class=HTMLResponse)
async def turma_novo(request: Request, session: SessionDep):
    discs = (
        await session.execute(select(Disciplina).order_by(Disciplina.nome))
    ).scalars().all()
    profs = (
        await session.execute(select(Professor).order_by(Professor.nome))
    ).scalars().all()
    return render(
        request,
        "turmas/form.html",
        active="turmas",
        turma=None,
        disciplinas=discs,
        professores=profs,
        curriculo=[],
    )


@router.get("/turmas/{turma_id}", response_class=HTMLResponse)
async def turma_edit(turma_id: int, request: Request, session: SessionDep):
    turma = await session.get(Turma, turma_id)
    if turma is None:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    discs = (
        await session.execute(select(Disciplina).order_by(Disciplina.nome))
    ).scalars().all()
    profs = (
        await session.execute(select(Professor).order_by(Professor.nome))
    ).scalars().all()
    curriculo = (
        await session.execute(select(TurmaDisciplina).where(TurmaDisciplina.turma_id == turma_id))
    ).scalars().all()
    return render(
        request,
        "turmas/form.html",
        active="turmas",
        turma=turma,
        disciplinas=discs,
        professores=profs,
        curriculo=curriculo,
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
    return render(request, "grade/nova.html", active="grade", semestres=semestres_list)


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

    return render(
        request,
        "grade/detail.html",
        active="grade",
        grade=grade,
        turmas=turmas,
        grades_por_turma=grades_por_turma,
        breakdown=breakdown,
    )
