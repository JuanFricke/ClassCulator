from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import SessionDep
from app.models import Sala
from app.schemas import SalaCreate, SalaRead, SalaUpdate

router = APIRouter(prefix="/salas", tags=["salas"])


@router.get("", response_model=list[SalaRead])
async def list_salas(session: SessionDep) -> list[Sala]:
    result = await session.execute(select(Sala).order_by(Sala.nome))
    return list(result.scalars().all())


@router.post("", response_model=SalaRead, status_code=status.HTTP_201_CREATED)
async def create_sala(payload: SalaCreate, session: SessionDep) -> Sala:
    obj = Sala(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.get("/{sala_id}", response_model=SalaRead)
async def get_sala(sala_id: int, session: SessionDep) -> Sala:
    obj = await session.get(Sala, sala_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Sala não encontrada")
    return obj


@router.patch("/{sala_id}", response_model=SalaRead)
async def update_sala(sala_id: int, payload: SalaUpdate, session: SessionDep) -> Sala:
    obj = await session.get(Sala, sala_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Sala não encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.delete("/{sala_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sala(sala_id: int, session: SessionDep) -> None:
    obj = await session.get(Sala, sala_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Sala não encontrada")
    await session.delete(obj)
    await session.commit()
