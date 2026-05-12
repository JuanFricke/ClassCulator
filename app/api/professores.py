from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.core.deps import SessionDep
from app.models import DisponibilidadeProfessor, Professor, ProfessorDisciplina
from app.schemas import (
    DisponibilidadeBulkUpdate,
    DisponibilidadeRead,
    ProfessorCreate,
    ProfessorRead,
    ProfessorUpdate,
)

router = APIRouter(prefix="/professores", tags=["professores"])


async def _serialize(session, professor: Professor) -> ProfessorRead:
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
        }
    )


@router.get("", response_model=list[ProfessorRead])
async def list_professores(session: SessionDep) -> list[ProfessorRead]:
    result = await session.execute(select(Professor).order_by(Professor.nome))
    professores = list(result.scalars().all())
    return [await _serialize(session, p) for p in professores]


@router.post("", response_model=ProfessorRead, status_code=status.HTTP_201_CREATED)
async def create_professor(payload: ProfessorCreate, session: SessionDep) -> ProfessorRead:
    obj = Professor(nome=payload.nome, email=payload.email)
    session.add(obj)
    await session.flush()
    for disc_id in payload.disciplina_ids:
        session.add(ProfessorDisciplina(professor_id=obj.id, disciplina_id=disc_id))
    await session.commit()
    await session.refresh(obj)
    return await _serialize(session, obj)


@router.get("/{professor_id}", response_model=ProfessorRead)
async def get_professor(professor_id: int, session: SessionDep) -> ProfessorRead:
    obj = await session.get(Professor, professor_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    return await _serialize(session, obj)


@router.patch("/{professor_id}", response_model=ProfessorRead)
async def update_professor(
    professor_id: int, payload: ProfessorUpdate, session: SessionDep
) -> ProfessorRead:
    obj = await session.get(Professor, professor_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
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
async def delete_professor(professor_id: int, session: SessionDep) -> None:
    obj = await session.get(Professor, professor_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    await session.delete(obj)
    await session.commit()


@router.get("/{professor_id}/disponibilidade", response_model=list[DisponibilidadeRead])
async def get_disponibilidade(professor_id: int, session: SessionDep) -> list[DisponibilidadeRead]:
    if await session.get(Professor, professor_id) is None:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    result = await session.execute(
        select(DisponibilidadeProfessor)
        .where(DisponibilidadeProfessor.professor_id == professor_id)
        .order_by(DisponibilidadeProfessor.dia, DisponibilidadeProfessor.slot)
    )
    return [DisponibilidadeRead.model_validate(d) for d in result.scalars().all()]


@router.put("/{professor_id}/disponibilidade", response_model=list[DisponibilidadeRead])
async def set_disponibilidade(
    professor_id: int, payload: DisponibilidadeBulkUpdate, session: SessionDep
) -> list[DisponibilidadeRead]:
    if await session.get(Professor, professor_id) is None:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    await session.execute(
        delete(DisponibilidadeProfessor).where(
            DisponibilidadeProfessor.professor_id == professor_id
        )
    )
    for item in payload.items:
        session.add(
            DisponibilidadeProfessor(
                professor_id=professor_id,
                dia=item.dia,
                slot=item.slot,
                disponivel=item.disponivel,
            )
        )
    await session.commit()
    return await get_disponibilidade(professor_id, session)
