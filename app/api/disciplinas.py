from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import SessionDep
from app.models import Disciplina
from app.schemas import DisciplinaCreate, DisciplinaRead, DisciplinaUpdate

router = APIRouter(prefix="/disciplinas", tags=["disciplinas"])


@router.get("", response_model=list[DisciplinaRead])
async def list_disciplinas(session: SessionDep) -> list[Disciplina]:
    result = await session.execute(select(Disciplina).order_by(Disciplina.nome))
    return list(result.scalars().all())


@router.post("", response_model=DisciplinaRead, status_code=status.HTTP_201_CREATED)
async def create_disciplina(payload: DisciplinaCreate, session: SessionDep) -> Disciplina:
    obj = Disciplina(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.get("/{disciplina_id}", response_model=DisciplinaRead)
async def get_disciplina(disciplina_id: int, session: SessionDep) -> Disciplina:
    obj = await session.get(Disciplina, disciplina_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    return obj


@router.patch("/{disciplina_id}", response_model=DisciplinaRead)
async def update_disciplina(
    disciplina_id: int, payload: DisciplinaUpdate, session: SessionDep
) -> Disciplina:
    obj = await session.get(Disciplina, disciplina_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.delete("/{disciplina_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_disciplina(disciplina_id: int, session: SessionDep) -> None:
    obj = await session.get(Disciplina, disciplina_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    await session.delete(obj)
    await session.commit()
