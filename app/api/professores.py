from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.core.auth import AnoAtivoApiDep
from app.core.deps import SessionDep
from app.core.security import gerar_senha_temporaria, hash_senha
from app.models import (
    PAPEL_PROFESSOR,
    DisponibilidadeProfessor,
    Professor,
    ProfessorDisciplina,
    Usuario,
)
from app.schemas import (
    DisponibilidadeBulkUpdate,
    DisponibilidadeRead,
    ProfessorCreate,
    ProfessorRead,
    ProfessorUpdate,
)

router = APIRouter(prefix="/professores", tags=["professores"])


async def _get_no_ano(session: SessionDep, professor_id: int, ano_id: int) -> Professor:
    obj = await session.get(Professor, professor_id)
    if obj is None or obj.ano_letivo_id != ano_id:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    return obj


async def _serialize(
    session, professor: Professor, *, senha_temporaria: str | None = None
) -> ProfessorRead:
    result = await session.execute(
        select(ProfessorDisciplina.disciplina_id).where(
            ProfessorDisciplina.professor_id == professor.id
        )
    )
    disciplina_ids = [row[0] for row in result.all()]
    return ProfessorRead.model_validate(
        {
            "id": professor.id,
            "nome": professor.nome,
            "email": professor.email,
            "disciplina_ids": disciplina_ids,
            "senha_temporaria": senha_temporaria,
        }
    )


@router.get("", response_model=list[ProfessorRead])
async def list_professores(session: SessionDep, ano: AnoAtivoApiDep) -> list[ProfessorRead]:
    result = await session.execute(
        select(Professor).where(Professor.ano_letivo_id == ano.id).order_by(Professor.nome)
    )
    professores = list(result.scalars().all())
    return [await _serialize(session, p) for p in professores]


@router.post("", response_model=ProfessorRead, status_code=status.HTTP_201_CREATED)
async def create_professor(
    payload: ProfessorCreate, session: SessionDep, ano: AnoAtivoApiDep
) -> ProfessorRead:
    nome = payload.nome.strip()
    email_norm = payload.email.strip().lower() if payload.email and payload.email.strip() else None
    senha_temporaria: str | None = None
    usuario_id: int | None = None

    if email_norm:
        existente = (
            await session.execute(select(Usuario).where(Usuario.email == email_norm))
        ).scalar_one_or_none()
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma conta com este e-mail.",
            )
        senha_temporaria = gerar_senha_temporaria()
        usuario = Usuario(
            nome=nome,
            email=email_norm,
            senha_hash=hash_senha(senha_temporaria),
            papel=PAPEL_PROFESSOR,
            ativo=True,
            deve_trocar_senha=True,
        )
        session.add(usuario)
        await session.flush()
        usuario_id = usuario.id

    obj = Professor(
        ano_letivo_id=ano.id,
        nome=nome,
        email=email_norm,
        usuario_id=usuario_id,
    )
    session.add(obj)
    await session.flush()
    for disc_id in payload.disciplina_ids:
        session.add(ProfessorDisciplina(professor_id=obj.id, disciplina_id=disc_id))
    await session.commit()
    await session.refresh(obj)
    return await _serialize(session, obj, senha_temporaria=senha_temporaria)


@router.get("/{professor_id}", response_model=ProfessorRead)
async def get_professor(
    professor_id: int, session: SessionDep, ano: AnoAtivoApiDep
) -> ProfessorRead:
    obj = await _get_no_ano(session, professor_id, ano.id)
    return await _serialize(session, obj)


@router.patch("/{professor_id}", response_model=ProfessorRead)
async def update_professor(
    professor_id: int, payload: ProfessorUpdate, session: SessionDep, ano: AnoAtivoApiDep
) -> ProfessorRead:
    obj = await _get_no_ano(session, professor_id, ano.id)
    data = payload.model_dump(exclude_unset=True)
    disciplina_ids = data.pop("disciplina_ids", None)
    for field, value in data.items():
        setattr(obj, field, value)

    if disciplina_ids is not None:
        await session.execute(
            delete(ProfessorDisciplina).where(ProfessorDisciplina.professor_id == professor_id)
        )
        for disc_id in disciplina_ids:
            session.add(ProfessorDisciplina(professor_id=professor_id, disciplina_id=disc_id))

    await session.commit()
    await session.refresh(obj)
    return await _serialize(session, obj)


@router.delete("/{professor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_professor(
    professor_id: int, session: SessionDep, ano: AnoAtivoApiDep
) -> None:
    obj = await _get_no_ano(session, professor_id, ano.id)
    await session.delete(obj)
    await session.commit()


@router.get("/{professor_id}/disponibilidade", response_model=list[DisponibilidadeRead])
async def get_disponibilidade(
    professor_id: int, session: SessionDep, ano: AnoAtivoApiDep
) -> list[DisponibilidadeRead]:
    await _get_no_ano(session, professor_id, ano.id)
    result = await session.execute(
        select(DisponibilidadeProfessor)
        .where(DisponibilidadeProfessor.professor_id == professor_id)
        .order_by(DisponibilidadeProfessor.dia, DisponibilidadeProfessor.slot)
    )
    return [DisponibilidadeRead.model_validate(d) for d in result.scalars().all()]


@router.put("/{professor_id}/disponibilidade", response_model=list[DisponibilidadeRead])
async def set_disponibilidade(
    professor_id: int,
    payload: DisponibilidadeBulkUpdate,
    session: SessionDep,
    ano: AnoAtivoApiDep,
) -> list[DisponibilidadeRead]:
    await _get_no_ano(session, professor_id, ano.id)
    await session.execute(
        delete(DisponibilidadeProfessor).where(
            DisponibilidadeProfessor.professor_id == professor_id
        )
    )
    for item in payload.items:
        if not item.disponivel:
            session.add(
                DisponibilidadeProfessor(
                    professor_id=professor_id,
                    dia=item.dia,
                    slot=item.slot,
                    disponivel=False,
                )
            )
    await session.commit()
    return await get_disponibilidade(professor_id, session, ano)
