"""Páginas SSR renderizadas com Jinja2 + Bulma."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.core.auth import LayoutDep
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
from app.solver.domain import DIAS, SLOTS_DIA_MAX, SLOTS_POR_DIA_DEFAULT, SLOTS_POR_TURMA

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

DIAS_LABELS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
SLOT_LABELS = [f"Período {i + 1}" for i in range(SLOTS_DIA_MAX)]

router = APIRouter()


# --- Filtragem de disciplinas por nível ---------------------------------- #
# Datasets como `app.seed_alt` separam disciplinas por nível pedagógico
# (EI / EF I / EF II / EM) mas todas com o mesmo `ensino` no banco
# (fundamental ou médio). Para evitar mostrar "Biologia" no dropdown de uma
# turma de Educação Infantil — ou "Matemática EF I" para uma C-class —
# detectamos o nível pelo identificador da turma e pelo sufixo do nome da
# disciplina. Quando o nível não pode ser detectado (datasets legados sem
# sufixo, ex.: EFA "Matemática"), a disciplina é considerada universal e
# nunca filtrada.

_REGEX_TURMA_NIVEL: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^A\d+$"), "EI"),
    (re.compile(r"^B\d+$"), "EFI"),
    (re.compile(r"^C\d+$"), "EFII"),
    (re.compile(r"^\d{3}$"), "EM"),
)


def _nivel_da_turma(identificador: str) -> str | None:
    for pattern, nivel in _REGEX_TURMA_NIVEL:
        if pattern.match(identificador or ""):
            return nivel
    return None


def _nivel_da_disciplina(nome: str) -> str | None:
    nome = (nome or "").strip()
    if nome.endswith(" EF II"):
        return "EFII"
    if nome.endswith(" EF I"):
        return "EFI"
    if nome.endswith(" EI"):
        return "EI"
    if nome.endswith(" EM"):
        return "EM"
    return None


def _disciplinas_compativeis(turma: Turma | None, todas: list[Disciplina]) -> list[Disciplina]:
    """Restringe a lista pelo nível detectado da turma; mantém disciplinas
    sem sufixo (universais)."""

    if turma is None:
        return list(todas)
    nivel_turma = _nivel_da_turma(turma.identificador)
    if nivel_turma is None:
        return list(todas)
    return [
        d for d in todas
        if _nivel_da_disciplina(d.nome) in (None, nivel_turma)
    ]


def render(request: Request, template_name: str, /, **context: Any) -> HTMLResponse:
    """Renderiza um template injetando os globais comuns ao layout."""

    payload: dict[str, Any] = {
        "DIAS": list(range(DIAS)),
        "SLOTS": list(range(SLOTS_DIA_MAX)),
        "DIAS_LABELS": DIAS_LABELS,
        "SLOT_LABELS": SLOT_LABELS,
        "SLOTS_DIA_MAX": SLOTS_DIA_MAX,
        "active": "",
    }
    payload.update(context)
    return templates.TemplateResponse(request, template_name, payload)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    counts = await _contar_entidades(session, ano_id)
    ultima = (
        await session.execute(
            select(GradeHoraria)
            .where(GradeHoraria.ano_letivo_id == ano_id)
            .order_by(GradeHoraria.criado_em.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    readiness = await _calcular_prontidao(session, counts, ano_id)

    return render(
        request,
        "home.html",
        active="home",
        counts=counts,
        ultima=ultima,
        readiness=readiness,
        slots_por_turma=SLOTS_POR_TURMA,  # valor de referência (caso retangular)
        **layout,
    )


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    counts = await _contar_entidades(session, ano_id)
    readiness = await _calcular_prontidao(session, counts, ano_id)
    return render(
        request,
        "onboarding.html",
        active="onboarding",
        counts=counts,
        readiness=readiness,
        **layout,
    )


@router.get("/gestao", response_class=HTMLResponse)
async def gestao(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    counts = await _contar_entidades(session, ano_id)
    readiness = await _calcular_prontidao(session, counts, ano_id)
    return render(
        request,
        "gestao.html",
        active="gestao",
        counts=counts,
        readiness=readiness,
        **layout,
    )


async def _contar_entidades(session: SessionDep, ano_id: int) -> dict[str, int]:
    return {
        "professores": (
            await session.execute(
                select(func.count()).select_from(Professor).where(Professor.ano_letivo_id == ano_id)
            )
        ).scalar_one(),
        "turmas": (
            await session.execute(
                select(func.count()).select_from(Turma).where(Turma.ano_letivo_id == ano_id)
            )
        ).scalar_one(),
        "disciplinas": (
            await session.execute(
                select(func.count())
                .select_from(Disciplina)
                .where(Disciplina.ano_letivo_id == ano_id)
            )
        ).scalar_one(),
        "salas": (
            await session.execute(
                select(func.count()).select_from(Sala).where(Sala.ano_letivo_id == ano_id)
            )
        ).scalar_one(),
        "grades": (
            await session.execute(
                select(func.count())
                .select_from(GradeHoraria)
                .where(GradeHoraria.ano_letivo_id == ano_id)
            )
        ).scalar_one(),
    }


async def _mapa_professores_por_disciplina(
    session: SessionDep, ano_id: int, disciplina_ids: list[int] | None = None
) -> dict[int, list[int]]:
    stmt = (
        select(ProfessorDisciplina.disciplina_id, ProfessorDisciplina.professor_id)
        .join(Professor, Professor.id == ProfessorDisciplina.professor_id)
        .where(Professor.ano_letivo_id == ano_id)
    )
    if disciplina_ids:
        stmt = stmt.where(ProfessorDisciplina.disciplina_id.in_(disciplina_ids))
    rows = (await session.execute(stmt)).all()
    mapa: dict[int, list[int]] = {}
    for disciplina_id, professor_id in rows:
        mapa.setdefault(disciplina_id, []).append(professor_id)
    return mapa


async def _calcular_prontidao(session: SessionDep, counts: dict, ano_id: int) -> dict:
    """Resume o estado da configuração para o painel inicial.

    Retorna uma estrutura com flags por etapa e, se houver turmas, a carga
    atual e o que falta para cada uma fechar o seu próprio
    ``sum(slots_por_dia)``.
    """

    turmas_ok = True
    turmas_problema: list[dict] = []
    if counts["turmas"] > 0:
        cargas = await session.execute(
            select(
                Turma.id,
                Turma.identificador,
                Turma.slots_por_dia,
                func.coalesce(func.sum(Disciplina.carga_semanal), 0).label("carga"),
            )
            .join(TurmaDisciplina, TurmaDisciplina.turma_id == Turma.id, isouter=True)
            .join(Disciplina, Disciplina.id == TurmaDisciplina.disciplina_id, isouter=True)
            .where(Turma.ano_letivo_id == ano_id)
            .group_by(Turma.id, Turma.identificador, Turma.slots_por_dia)
            .order_by(Turma.identificador)
        )
        for row in cargas.all():
            alvo = sum(row.slots_por_dia or SLOTS_POR_DIA_DEFAULT)
            carga_int = int(row.carga)
            falta = alvo - carga_int
            if falta != 0:
                turmas_ok = False
                turmas_problema.append(
                    {
                        "id": row.id,
                        "identificador": row.identificador,
                        "carga": carga_int,
                        "alvo": alvo,
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
        return f"{qtd_turmas} turma(s) com currículo completo."
    nomes = ", ".join(
        f"{p['identificador']} ({p['carga']}/{p['alvo']})" for p in problemas[:4]
    )
    extra = f" +{len(problemas) - 4} outras" if len(problemas) > 4 else ""
    return f"{len(problemas)} turma(s) com currículo incompleto: {nomes}{extra}."


# --- Professores ----------------------------------------------------------- #


@router.get("/professores", response_class=HTMLResponse)
async def professores_list(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    profs = (
        await session.execute(
            select(Professor).where(Professor.ano_letivo_id == ano_id).order_by(Professor.nome)
        )
    ).scalars().all()
    discs = {
        d.id: d
        for d in (
            await session.execute(
                select(Disciplina).where(Disciplina.ano_letivo_id == ano_id)
            )
        ).scalars().all()
    }
    pd_rows = (
        await session.execute(
            select(ProfessorDisciplina)
            .join(Professor, Professor.id == ProfessorDisciplina.professor_id)
            .where(Professor.ano_letivo_id == ano_id)
        )
    ).scalars().all()
    by_prof: dict[int, list[Disciplina]] = {}
    for pd in pd_rows:
        if pd.disciplina_id in discs:
            by_prof.setdefault(pd.professor_id, []).append(discs[pd.disciplina_id])
    return render(
        request,
        "professores/list.html",
        active="gestao",
        professores=profs,
        disciplinas_por_prof=by_prof,
        **layout,
    )


@router.get("/professores/novo", response_class=HTMLResponse)
async def professor_novo(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    discs = (
        await session.execute(
            select(Disciplina)
            .where(Disciplina.ano_letivo_id == ano_id)
            .order_by(Disciplina.ensino, Disciplina.nome)
        )
    ).scalars().all()
    return render(
        request,
        "professores/form.html",
        active="gestao",
        professor=None,
        disciplinas=discs,
        disciplina_ids=[],
        **layout,
    )


@router.get("/professores/{professor_id}", response_class=HTMLResponse)
async def professor_edit(
    professor_id: int, request: Request, session: SessionDep, layout: LayoutDep
):
    ano_id = layout["ano_atual"].id
    prof = await session.get(Professor, professor_id)
    if prof is None or prof.ano_letivo_id != ano_id:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    discs = (
        await session.execute(
            select(Disciplina)
            .where(Disciplina.ano_letivo_id == ano_id)
            .order_by(Disciplina.ensino, Disciplina.nome)
        )
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
        active="gestao",
        professor=prof,
        disciplinas=discs,
        disciplina_ids=selecionadas,
        disponibilidade=indisp,
        **layout,
    )


# --- Disciplinas ----------------------------------------------------------- #


@router.get("/disciplinas", response_class=HTMLResponse)
async def disciplinas_list(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    disciplinas = (
        await session.execute(
            select(Disciplina)
            .where(Disciplina.ano_letivo_id == ano_id)
            .order_by(Disciplina.ensino, Disciplina.nome)
        )
    ).scalars().all()
    return render(
        request,
        "disciplinas/list.html",
        active="gestao",
        disciplinas=disciplinas,
        **layout,
    )


@router.get("/disciplinas/novo", response_class=HTMLResponse)
async def disciplina_novo(request: Request, layout: LayoutDep):
    return render(
        request,
        "disciplinas/form.html",
        active="gestao",
        disciplina=None,
        ensino_options=["fundamental", "medio", "ambos"],
        **layout,
    )


@router.get("/disciplinas/{disciplina_id}", response_class=HTMLResponse)
async def disciplina_edit(
    disciplina_id: int, request: Request, session: SessionDep, layout: LayoutDep
):
    ano_id = layout["ano_atual"].id
    disc = await session.get(Disciplina, disciplina_id)
    if disc is None or disc.ano_letivo_id != ano_id:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    return render(
        request,
        "disciplinas/form.html",
        active="gestao",
        disciplina=disc,
        ensino_options=["fundamental", "medio", "ambos"],
        **layout,
    )


# --- Salas ----------------------------------------------------------------- #


@router.get("/salas", response_class=HTMLResponse)
async def salas_list(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    salas = (
        await session.execute(
            select(Sala).where(Sala.ano_letivo_id == ano_id).order_by(Sala.nome)
        )
    ).scalars().all()
    return render(request, "salas/list.html", active="gestao", salas=salas, **layout)


@router.get("/salas/novo", response_class=HTMLResponse)
async def sala_novo(request: Request, layout: LayoutDep):
    return render(request, "salas/form.html", active="gestao", sala=None, **layout)


@router.get("/salas/{sala_id}", response_class=HTMLResponse)
async def sala_edit(sala_id: int, request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    sala = await session.get(Sala, sala_id)
    if sala is None or sala.ano_letivo_id != ano_id:
        raise HTTPException(status_code=404, detail="Sala não encontrada")
    return render(request, "salas/form.html", active="gestao", sala=sala, **layout)


# --- Turmas ---------------------------------------------------------------- #


@router.get("/turmas", response_class=HTMLResponse)
async def turmas_list(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    turmas = (
        await session.execute(
            select(Turma).where(Turma.ano_letivo_id == ano_id).order_by(Turma.identificador)
        )
    ).scalars().all()
    cargas = await session.execute(
        select(
            Turma.id,
            func.coalesce(func.sum(Disciplina.carga_semanal), 0).label("carga"),
        )
        .join(TurmaDisciplina, TurmaDisciplina.turma_id == Turma.id, isouter=True)
        .join(Disciplina, Disciplina.id == TurmaDisciplina.disciplina_id, isouter=True)
        .where(Turma.ano_letivo_id == ano_id)
        .group_by(Turma.id)
    )
    carga_por_turma = {row.id: int(row.carga) for row in cargas}
    alvo_por_turma = {t.id: sum(t.slots_por_dia or SLOTS_POR_DIA_DEFAULT) for t in turmas}
    return render(
        request,
        "turmas/list.html",
        active="gestao",
        turmas=turmas,
        carga_por_turma=carga_por_turma,
        alvo_por_turma=alvo_por_turma,
        carga_alvo=SLOTS_POR_TURMA,  # mantido como fallback para o caso retangular
        **layout,
    )


@router.get("/turmas/novo", response_class=HTMLResponse)
async def turma_novo(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    ensino_default = "fundamental"
    discs = (
        await session.execute(
            select(Disciplina)
            .where(
                Disciplina.ano_letivo_id == ano_id,
                Disciplina.ensino.in_([ensino_default, "ambos"]),
            )
            .order_by(Disciplina.nome)
        )
    ).scalars().all()
    profs = (
        await session.execute(
            select(Professor).where(Professor.ano_letivo_id == ano_id).order_by(Professor.nome)
        )
    ).scalars().all()
    professores_por_disciplina = await _mapa_professores_por_disciplina(
        session, ano_id, [d.id for d in discs]
    )
    return render(
        request,
        "turmas/form.html",
        active="gestao",
        turma=None,
        disciplinas=discs,
        professores=profs,
        curriculo=[],
        carga_atual=0,
        carga_alvo=SLOTS_POR_TURMA,
        slots_por_dia=list(SLOTS_POR_DIA_DEFAULT),
        professores_por_disciplina=professores_por_disciplina,
        ensino_options=["fundamental", "medio", "ambos"],
        **layout,
    )


@router.get("/turmas/{turma_id}", response_class=HTMLResponse)
async def turma_edit(turma_id: int, request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    turma = await session.get(Turma, turma_id)
    if turma is None or turma.ano_letivo_id != ano_id:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    ensino_turma = infer_turma_ensino(turma.identificador, turma.ensino)
    discs_all = (
        await session.execute(
            select(Disciplina)
            .where(
                Disciplina.ano_letivo_id == ano_id,
                Disciplina.ensino.in_([ensino_turma, "ambos"]),
            )
            .order_by(Disciplina.nome)
        )
    ).scalars().all()
    curriculo_db = (
        await session.execute(select(TurmaDisciplina).where(TurmaDisciplina.turma_id == turma_id))
    ).scalars().all()
    # Mostra apenas as disciplinas EFETIVAMENTE atribuídas a esta turma.
    # O usuário usa "+ Adicionar disciplina" para incluir novas conforme o
    # currículo do nível da turma — antes pré-preenchíamos com TODAS as
    # disciplinas compatíveis por `ensino`, o que produzia listas absurdas
    # (>=25 disciplinas) quando o dataset combina EI/AI/AF sob o mesmo ensino.
    curriculo = list(curriculo_db)
    # Para o dropdown: filtra por nível detectado da turma, mas SEMPRE inclui
    # as disciplinas já presentes no currículo salvo (para não sumirem se
    # estiverem fora do filtro por algum motivo).
    filtradas = _disciplinas_compativeis(turma, list(discs_all))
    ids_curriculo = {c.disciplina_id for c in curriculo}
    extras = [d for d in discs_all if d.id in ids_curriculo and d not in filtradas]
    discs = sorted(filtradas + extras, key=lambda d: d.nome)
    profs = (
        await session.execute(
            select(Professor).where(Professor.ano_letivo_id == ano_id).order_by(Professor.nome)
        )
    ).scalars().all()
    professores_por_disciplina = await _mapa_professores_por_disciplina(
        session, ano_id, [d.id for d in discs]
    )
    disc_by_id = {d.id: d for d in discs}
    carga_atual = sum(
        disc_by_id[c.disciplina_id].carga_semanal
        for c in curriculo
        if c.disciplina_id in disc_by_id
    )
    slots_por_dia = list(turma.slots_por_dia or SLOTS_POR_DIA_DEFAULT)
    return render(
        request,
        "turmas/form.html",
        active="gestao",
        turma=turma,
        disciplinas=discs,
        professores=profs,
        curriculo=curriculo,
        carga_atual=carga_atual,
        carga_alvo=sum(slots_por_dia),
        slots_por_dia=slots_por_dia,
        professores_por_disciplina=professores_por_disciplina,
        ensino_options=["fundamental", "medio", "ambos"],
        **layout,
    )


# --- Grade ----------------------------------------------------------------- #


@router.get("/grade", response_class=HTMLResponse)
async def grade_list(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    grades = (
        await session.execute(
            select(GradeHoraria)
            .where(GradeHoraria.ano_letivo_id == ano_id)
            .order_by(GradeHoraria.criado_em.desc())
            .limit(50)
        )
    ).scalars().all()
    return render(request, "grade/list.html", active="gestao", grades=grades, **layout)


@router.get("/grade/nova", response_class=HTMLResponse)
async def grade_nova(request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    # Pré-checagem: avisar antes de submeter se algum currículo está incompleto.
    counts = await _contar_entidades(session, ano_id)
    counts["grades"] = 0
    readiness = await _calcular_prontidao(session, counts, ano_id)

    return render(
        request,
        "grade/nova.html",
        active="gestao",
        readiness=readiness,
        **layout,
    )


@router.get("/grade/{grade_id}", response_class=HTMLResponse)
async def grade_detail(grade_id: int, request: Request, session: SessionDep, layout: LayoutDep):
    ano_id = layout["ano_atual"].id
    grade = await session.get(GradeHoraria, grade_id)
    if grade is None or grade.ano_letivo_id != ano_id:
        raise HTTPException(status_code=404, detail="Grade não encontrada")

    alocacoes = (
        await session.execute(
            select(AlocacaoSlot).where(AlocacaoSlot.grade_id == grade_id)
        )
    ).scalars().all()
    turmas = {
        t.id: t
        for t in (
            await session.execute(select(Turma).where(Turma.ano_letivo_id == ano_id))
        ).scalars().all()
    }
    discs = {
        d.id: d
        for d in (
            await session.execute(select(Disciplina).where(Disciplina.ano_letivo_id == ano_id))
        ).scalars().all()
    }
    profs = {
        p.id: p
        for p in (
            await session.execute(select(Professor).where(Professor.ano_letivo_id == ano_id))
        ).scalars().all()
    }
    salas = {
        s.id: s
        for s in (
            await session.execute(select(Sala).where(Sala.ano_letivo_id == ano_id))
        ).scalars().all()
    }

    grades_por_turma: dict[int, list[list[dict | None]]] = {}
    slots_por_dia_turma: dict[int, list[int]] = {}
    for tid, turma in turmas.items():
        grades_por_turma[tid] = [[None for _ in range(SLOTS_DIA_MAX)] for _ in range(DIAS)]
        slots_por_dia_turma[tid] = list(turma.slots_por_dia or SLOTS_POR_DIA_DEFAULT)
    for a in alocacoes:
        cell = {
            "disciplina": discs.get(a.disciplina_id),
            "professor": profs.get(a.professor_id),
            "sala": salas.get(a.sala_id) if a.sala_id else None,
        }
        if a.turma_id in grades_por_turma:
            if 0 <= a.dia < DIAS and 0 <= a.slot < SLOTS_DIA_MAX:
                grades_por_turma[a.turma_id][a.dia][a.slot] = cell

    breakdown = None
    if alocacoes:
        from app.solver.builder import build_instance

        try:
            instance = await build_instance(session, grade.ano_letivo_id)
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

    # Dados para o editor manual (dropdowns de disciplina/professor/sala). Só
    # fazem sentido com a grade concluída; o template os embute como JSON.
    disciplinas_lista = sorted(discs.values(), key=lambda d: d.nome)
    professores_lista = sorted(profs.values(), key=lambda p: p.nome)
    salas_lista = sorted(salas.values(), key=lambda s: s.nome)
    professores_por_disciplina = await _mapa_professores_por_disciplina(session, ano_id)

    return render(
        request,
        "grade/detail.html",
        active="gestao",
        grade=grade,
        turmas=turmas,
        turmas_ordenadas=turmas_ordenadas,
        grades_por_turma=grades_por_turma,
        slots_por_dia_turma=slots_por_dia_turma,
        breakdown=breakdown,
        disciplinas_lista=disciplinas_lista,
        professores_lista=professores_lista,
        salas_lista=salas_lista,
        professores_por_disciplina=professores_por_disciplina,
        **layout,
    )
