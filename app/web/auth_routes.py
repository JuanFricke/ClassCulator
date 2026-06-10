"""Rotas SSR de autenticação, seleção de ano, convites e portal do professor."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, select

from app.core.auth import (
    SESSION_ANO_KEY,
    SESSION_USER_KEY,
    EmpresaWebDep,
    ProfessorContextoDep,
    ProfessorWebDep,
    get_current_user,
)
from app.core.deps import SessionDep
from app.core.security import gerar_token, hash_senha, verificar_senha
from app.models import (
    PAPEL_EMPRESA,
    PAPEL_PROFESSOR,
    AlocacaoSlot,
    AnoLetivo,
    ConviteProfessor,
    Disciplina,
    DisponibilidadeProfessor,
    GradeHoraria,
    GradeStatus,
    Professor,
    ProfessorDisciplina,
    Sala,
    Turma,
    Usuario,
)
from app.services.admin_setup import cadastro_admin_disponivel, registrar_administradora
from app.services.ano_service import AnoJaExisteError, criar_ano
from app.solver.domain import DIAS, SLOTS_DIA_MAX
from app.web.routes import render

router = APIRouter()


def _destino_por_papel(user: Usuario) -> str:
    return "/anos" if user.papel == PAPEL_EMPRESA else "/professor"


# --- Login / Logout ------------------------------------------------------- #


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, session: SessionDep):
    user = await get_current_user(request, session)
    if user is not None:
        return RedirectResponse(_destino_por_papel(user), status_code=303)
    return render(
        request,
        "login.html",
        active="login",
        erro=None,
        cadastro_admin_disponivel=await cadastro_admin_disponivel(session),
    )


@router.post("/login")
async def login_submit(
    request: Request,
    session: SessionDep,
    email: str = Form(...),
    senha: str = Form(...),
):
    user = (
        await session.execute(select(Usuario).where(Usuario.email == email.strip().lower()))
    ).scalar_one_or_none()
    if user is None or not user.ativo or not verificar_senha(senha, user.senha_hash):
        return render(
            request,
            "login.html",
            active="login",
            erro="E-mail ou senha inválidos.",
            cadastro_admin_disponivel=await cadastro_admin_disponivel(session),
        )
    request.session[SESSION_USER_KEY] = user.id
    request.session.pop(SESSION_ANO_KEY, None)
    if user.deve_trocar_senha:
        return RedirectResponse("/trocar-senha", status_code=303)
    return RedirectResponse(_destino_por_papel(user), status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# --- Cadastro inicial da administradora ----------------------------------- #


@router.get("/registro/administradora", response_class=HTMLResponse)
async def registro_admin_form(request: Request, session: SessionDep):
    user = await get_current_user(request, session)
    if user is not None:
        return RedirectResponse(_destino_por_papel(user), status_code=303)
    if not await cadastro_admin_disponivel(session):
        return RedirectResponse("/login", status_code=303)
    return render(request, "registro/administradora.html", active="registro_admin", erro=None)


@router.post("/registro/administradora")
async def registro_admin_submit(
    request: Request,
    session: SessionDep,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    confirmar_senha: str = Form(...),
):
    if not await cadastro_admin_disponivel(session):
        return RedirectResponse("/login", status_code=303)

    def _erro(msg: str) -> HTMLResponse:
        return render(request, "registro/administradora.html", active="registro_admin", erro=msg)

    if len(senha) < 6:
        return _erro("A senha deve ter ao menos 6 caracteres.")
    if senha != confirmar_senha:
        return _erro("A confirmação não coincide com a senha.")

    try:
        usuario = await registrar_administradora(
            session, nome=nome, email=email, senha=senha
        )
    except ValueError as exc:
        return _erro(str(exc))

    request.session[SESSION_USER_KEY] = usuario.id
    request.session.pop(SESSION_ANO_KEY, None)
    return RedirectResponse("/anos", status_code=303)


# --- Troca obrigatória de senha (primeiro acesso) ----------------------- #


@router.get("/trocar-senha", response_class=HTMLResponse)
async def trocar_senha_form(request: Request, session: SessionDep, user: ProfessorWebDep):
    if not user.deve_trocar_senha:
        return RedirectResponse("/professor", status_code=303)
    return render(
        request,
        "trocar_senha.html",
        active="trocar_senha",
        current_user=user,
        erro=None,
    )


@router.post("/trocar-senha")
async def trocar_senha_submit(
    request: Request,
    session: SessionDep,
    user: ProfessorWebDep,
    senha_atual: str = Form(...),
    nova_senha: str = Form(...),
    confirmar_senha: str = Form(...),
):
    if not user.deve_trocar_senha:
        return RedirectResponse("/professor", status_code=303)

    def _erro(msg: str) -> HTMLResponse:
        return render(
            request,
            "trocar_senha.html",
            active="trocar_senha",
            current_user=user,
            erro=msg,
        )

    if not verificar_senha(senha_atual, user.senha_hash):
        return _erro("Senha atual incorreta.")
    if len(nova_senha) < 6:
        return _erro("A nova senha deve ter ao menos 6 caracteres.")
    if nova_senha != confirmar_senha:
        return _erro("A confirmação não coincide com a nova senha.")
    if verificar_senha(nova_senha, user.senha_hash):
        return _erro("A nova senha deve ser diferente da senha temporária.")

    user.senha_hash = hash_senha(nova_senha)
    user.deve_trocar_senha = False
    await session.commit()
    return RedirectResponse("/professor", status_code=303)


# --- Anos letivos --------------------------------------------------------- #


@router.get("/anos", response_class=HTMLResponse)
async def anos_list(request: Request, session: SessionDep, user: EmpresaWebDep):
    anos = (
        await session.execute(select(AnoLetivo).order_by(AnoLetivo.ano.desc()))
    ).scalars().all()
    ano_atual_id = request.session.get(SESSION_ANO_KEY)
    sugestao = (max(a.ano for a in anos) + 1) if anos else 2026
    return render(
        request,
        "anos/list.html",
        active="anos",
        current_user=user,
        anos=anos,
        ano_atual_id=ano_atual_id,
        sugestao_ano=sugestao,
        erro=None,
    )


@router.post("/anos/selecionar")
async def anos_selecionar(
    request: Request,
    session: SessionDep,
    _user: EmpresaWebDep,
    ano_id: int = Form(...),
):
    ano = await session.get(AnoLetivo, ano_id)
    if ano is None:
        raise HTTPException(status_code=404, detail="Ano letivo não encontrado")
    request.session[SESSION_ANO_KEY] = ano.id
    return RedirectResponse("/", status_code=303)


@router.post("/anos/criar")
async def anos_criar(
    request: Request,
    session: SessionDep,
    user: EmpresaWebDep,
    ano: int = Form(...),
    clonar_de: int | None = Form(default=None),
):
    try:
        novo = await criar_ano(session, ano, source_ano_id=clonar_de or None)
    except AnoJaExisteError as exc:
        anos = (
            await session.execute(select(AnoLetivo).order_by(AnoLetivo.ano.desc()))
        ).scalars().all()
        return render(
            request,
            "anos/list.html",
            active="anos",
            current_user=user,
            anos=anos,
            ano_atual_id=request.session.get(SESSION_ANO_KEY),
            sugestao_ano=(max(a.ano for a in anos) + 1) if anos else 2026,
            erro=str(exc),
        )
    request.session[SESSION_ANO_KEY] = novo.id
    return RedirectResponse("/", status_code=303)


@router.post("/anos/excluir")
async def anos_excluir(
    request: Request,
    session: SessionDep,
    user: EmpresaWebDep,
    ano_id: int = Form(...),
):
    ano = await session.get(AnoLetivo, ano_id)
    if ano is None:
        raise HTTPException(status_code=404, detail="Ano letivo não encontrado")
    # If the deleted year is the one selected in session, clear it
    if request.session.get(SESSION_ANO_KEY) == ano.id:
        request.session.pop(SESSION_ANO_KEY, None)
    await session.delete(ano)
    await session.commit()
    return RedirectResponse("/anos", status_code=303)


# --- Convites de professores --------------------------------------------- #


@router.get("/convites", response_class=HTMLResponse)
async def convites_list(request: Request, session: SessionDep, user: EmpresaWebDep):
    convites = (
        await session.execute(
            select(ConviteProfessor).order_by(ConviteProfessor.criado_em.desc())
        )
    ).scalars().all()
    base_url = str(request.base_url).rstrip("/")
    return render(
        request,
        "convites/list.html",
        active="convites",
        current_user=user,
        convites=convites,
        base_url=base_url,
    )


@router.post("/convites")
async def convites_criar(request: Request, session: SessionDep, _user: EmpresaWebDep):
    convite = ConviteProfessor(token=gerar_token(), usado=False)
    session.add(convite)
    await session.commit()
    return RedirectResponse("/convites", status_code=303)


@router.post("/convites/gerar")
async def convites_gerar(request: Request, session: SessionDep, _user: EmpresaWebDep) -> dict:
    """Gera um convite e devolve a URL em JSON (para o botão copiar em /professores)."""

    convite = ConviteProfessor(token=gerar_token(), usado=False)
    session.add(convite)
    await session.commit()
    base_url = str(request.base_url).rstrip("/")
    return {"token": convite.token, "url": f"{base_url}/convite/{convite.token}"}


@router.get("/convite/{token}", response_class=HTMLResponse)
async def convite_form(token: str, request: Request, session: SessionDep):
    convite = (
        await session.execute(select(ConviteProfessor).where(ConviteProfessor.token == token))
    ).scalar_one_or_none()
    invalido = convite is None or convite.usado
    return render(
        request,
        "convite/registro.html",
        active="convite",
        token=token,
        invalido=invalido,
        erro=None,
    )


@router.post("/convite/{token}")
async def convite_submit(
    token: str,
    request: Request,
    session: SessionDep,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
):
    convite = (
        await session.execute(select(ConviteProfessor).where(ConviteProfessor.token == token))
    ).scalar_one_or_none()
    if convite is None or convite.usado:
        return render(
            request, "convite/registro.html", active="convite", token=token, invalido=True, erro=None
        )

    email_norm = email.strip().lower()

    def _erro(msg: str) -> HTMLResponse:
        return render(
            request,
            "convite/registro.html",
            active="convite",
            token=token,
            invalido=False,
            erro=msg,
        )

    if len(senha) < 6:
        return _erro("A senha deve ter ao menos 6 caracteres.")

    existente = (
        await session.execute(select(Usuario).where(Usuario.email == email_norm))
    ).scalar_one_or_none()
    if existente is not None:
        return _erro("Já existe uma conta com este e-mail.")

    ano = (
        await session.execute(select(AnoLetivo).order_by(AnoLetivo.ano.desc()).limit(1))
    ).scalar_one_or_none()
    if ano is None:
        return _erro("Nenhum ano letivo configurado. Contate a administração.")

    usuario = Usuario(
        nome=nome.strip(),
        email=email_norm,
        senha_hash=hash_senha(senha),
        papel=PAPEL_PROFESSOR,
        ativo=True,
    )
    session.add(usuario)
    await session.flush()

    professor = Professor(
        ano_letivo_id=ano.id,
        usuario_id=usuario.id,
        nome=nome.strip(),
        email=email_norm,
    )
    session.add(professor)
    convite.usado = True
    await session.commit()

    request.session[SESSION_USER_KEY] = usuario.id
    return RedirectResponse("/professor", status_code=303)


# --- Portal do professor -------------------------------------------------- #


@router.get("/professor", response_class=HTMLResponse)
async def professor_home(
    request: Request, session: SessionDep, contexto: ProfessorContextoDep
):
    user, ano, professor = contexto

    disciplinas = (
        await session.execute(
            select(Disciplina)
            .where(Disciplina.ano_letivo_id == ano.id)
            .order_by(Disciplina.ensino, Disciplina.nome)
        )
    ).scalars().all()
    minhas_disc_ids = {
        row[0]
        for row in (
            await session.execute(
                select(ProfessorDisciplina.disciplina_id).where(
                    ProfessorDisciplina.professor_id == professor.id
                )
            )
        ).all()
    }
    indisp_rows = (
        await session.execute(
            select(DisponibilidadeProfessor).where(
                DisponibilidadeProfessor.professor_id == professor.id
            )
        )
    ).scalars().all()
    indisponivel = {(d.dia, d.slot) for d in indisp_rows if not d.disponivel}

    grade_cells, grade_info = await _grade_do_professor(session, ano.id, professor.id)

    return render(
        request,
        "professor/home.html",
        active="professor",
        current_user=user,
        ano_atual=ano,
        professor=professor,
        disciplinas=disciplinas,
        minhas_disciplinas=minhas_disc_ids,
        indisponivel=indisponivel,
        grade_cells=grade_cells,
        grade_info=grade_info,
    )


async def _grade_do_professor(session: SessionDep, ano_id: int, professor_id: int):
    """Última grade concluída do ano + alocações do professor (matriz dia x slot)."""

    grade = (
        await session.execute(
            select(GradeHoraria)
            .where(
                GradeHoraria.ano_letivo_id == ano_id,
                GradeHoraria.status == GradeStatus.DONE,
            )
            .order_by(GradeHoraria.criado_em.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if grade is None:
        return None, None

    alocacoes = (
        await session.execute(
            select(AlocacaoSlot).where(
                AlocacaoSlot.grade_id == grade.id,
                AlocacaoSlot.professor_id == professor_id,
            )
        )
    ).scalars().all()
    discs = {
        d.id: d
        for d in (
            await session.execute(select(Disciplina).where(Disciplina.ano_letivo_id == ano_id))
        ).scalars().all()
    }
    turmas = {
        t.id: t
        for t in (
            await session.execute(select(Turma).where(Turma.ano_letivo_id == ano_id))
        ).scalars().all()
    }
    salas = {
        s.id: s
        for s in (
            await session.execute(select(Sala).where(Sala.ano_letivo_id == ano_id))
        ).scalars().all()
    }
    cells: list[list[dict | None]] = [
        [None for _ in range(SLOTS_DIA_MAX)] for _ in range(DIAS)
    ]
    for a in alocacoes:
        if 0 <= a.dia < DIAS and 0 <= a.slot < SLOTS_DIA_MAX:
            cells[a.dia][a.slot] = {
                "disciplina": discs.get(a.disciplina_id),
                "turma": turmas.get(a.turma_id),
                "sala": salas.get(a.sala_id) if a.sala_id else None,
            }
    return cells, grade


@router.post("/professor/disponibilidade")
async def professor_disponibilidade(
    request: Request,
    session: SessionDep,
    contexto: ProfessorContextoDep,
):
    _user, _ano, professor = contexto
    form = await request.form()
    # Cada checkbox marcada significa "indisponível" no formato "ind-{dia}-{slot}".
    indisponiveis: list[tuple[int, int]] = []
    for key in form.keys():
        if key.startswith("ind-"):
            try:
                _, dia_s, slot_s = key.split("-")
                indisponiveis.append((int(dia_s), int(slot_s)))
            except ValueError:
                continue

    await session.execute(
        delete(DisponibilidadeProfessor).where(
            DisponibilidadeProfessor.professor_id == professor.id
        )
    )
    for dia, slot in indisponiveis:
        session.add(
            DisponibilidadeProfessor(
                professor_id=professor.id, dia=dia, slot=slot, disponivel=False
            )
        )
    await session.commit()
    return RedirectResponse("/professor?ok=disponibilidade", status_code=303)


@router.post("/professor/disciplinas")
async def professor_disciplinas(
    request: Request,
    session: SessionDep,
    contexto: ProfessorContextoDep,
):
    _user, ano, professor = contexto
    form = await request.form()
    ids = []
    for value in form.getlist("disciplina_ids"):
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    # Mantém apenas disciplinas válidas do ano do professor.
    validas = {
        row[0]
        for row in (
            await session.execute(
                select(Disciplina.id).where(
                    Disciplina.ano_letivo_id == ano.id, Disciplina.id.in_(ids or [-1])
                )
            )
        ).all()
    }
    await session.execute(
        delete(ProfessorDisciplina).where(ProfessorDisciplina.professor_id == professor.id)
    )
    for did in validas:
        session.add(ProfessorDisciplina(professor_id=professor.id, disciplina_id=did))
    await session.commit()
    return RedirectResponse("/professor?ok=disciplinas", status_code=303)
