from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.core.deps import SessionDep
from app.models import Turma, TurmaDisciplina
from app.schemas import (
    TurmaCreate,
    TurmaCurriculoBulkUpdate,
    TurmaDisciplinaRead,
    TurmaRead,
    TurmaUpdate,
)

router = APIRouter(prefix="/turmas", tags=["turmas"])


async def _serialize(session, turma: Turma) -> TurmaRead:
    result = await session.execute(
        select(TurmaDisciplina).where(TurmaDisciplina.turma_id == turma.id)
    )
    curriculo = [TurmaDisciplinaRead.model_validate(td) for td in result.scalars().all()]
    return TurmaRead.model_validate(
        {
            "id": turma.id,
            "identificador": turma.identificador,
            "semestre": turma.semestre,
            "qtd_alunos": turma.qtd_alunos,
            "curriculo": [c.model_dump() for c in curriculo],
        }
    )


@router.get("", response_model=list[TurmaRead])
async def list_turmas(session: SessionDep) -> list[TurmaRead]:
    result = await session.execute(select(Turma).order_by(Turma.identificador))
    turmas = list(result.scalars().all())
    return [await _serialize(session, t) for t in turmas]


@router.post("", response_model=TurmaRead, status_code=status.HTTP_201_CREATED)
async def create_turma(payload: TurmaCreate, session: SessionDep) -> TurmaRead:
    obj = Turma(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return await _serialize(session, obj)


@router.get("/{turma_id}", response_model=TurmaRead)
async def get_turma(turma_id: int, session: SessionDep) -> TurmaRead:
    obj = await session.get(Turma, turma_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    return await _serialize(session, obj)


@router.patch("/{turma_id}", response_model=TurmaRead)
async def update_turma(turma_id: int, payload: TurmaUpdate, session: SessionDep) -> TurmaRead:
    obj = await session.get(Turma, turma_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.commit()
    await session.refresh(obj)
    return await _serialize(session, obj)


@router.delete("/{turma_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_turma(turma_id: int, session: SessionDep) -> None:
    obj = await session.get(Turma, turma_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    await session.delete(obj)
    await session.commit()


@router.put("/{turma_id}/curriculo", response_model=TurmaRead)
async def set_curriculo(
    turma_id: int, payload: TurmaCurriculoBulkUpdate, session: SessionDep
) -> TurmaRead:
    obj = await session.get(Turma, turma_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    await session.execute(delete(TurmaDisciplina).where(TurmaDisciplina.turma_id == turma_id))
    for item in payload.items:
        session.add(
            TurmaDisciplina(
                turma_id=turma_id,
                disciplina_id=item.disciplina_id,
                professor_id=item.professor_id,
            )
        )
    await session.commit()
    return await _serialize(session, obj)
