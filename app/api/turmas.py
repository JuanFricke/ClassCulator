from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.core.deps import SessionDep
from app.core.ensino import ensino_compativel, infer_turma_ensino
from app.models import Disciplina, ProfessorDisciplina, Turma, TurmaDisciplina
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
            "ensino": turma.ensino,
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
    data = payload.model_dump()
    data["ensino"] = infer_turma_ensino(data["identificador"], data.get("ensino") or "fundamental")
    obj = Turma(**data)
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
    data = payload.model_dump(exclude_unset=True)
    if "identificador" in data:
        data["ensino"] = infer_turma_ensino(data["identificador"], data.get("ensino") or obj.ensino)
    for field, value in data.items():
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
    allowed_pairs = set(
        (
            await session.execute(
                select(
                    ProfessorDisciplina.professor_id,
                    ProfessorDisciplina.disciplina_id,
                )
            )
        ).all()
    )
    for item in payload.items:
        if (item.professor_id, item.disciplina_id) not in allowed_pairs:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Professor selecionado não pode lecionar a disciplina informada. "
                    "Atualize os vínculos de disciplinas do professor antes de salvar o currículo."
                ),
            )
    disciplina_ids = [item.disciplina_id for item in payload.items]
    disciplinas = {}
    carga_total = 0
    if disciplina_ids:
        disciplinas = {
            d.id: d
            for d in (
                await session.execute(
                    select(Disciplina).where(Disciplina.id.in_(disciplina_ids))
                )
            ).scalars().all()
        }
    for item in payload.items:
        disciplina = disciplinas.get(item.disciplina_id)
        if disciplina is None:
            raise HTTPException(status_code=404, detail="Disciplina não encontrada")
        carga_total += disciplina.carga_semanal
        if not ensino_compativel(obj.ensino, disciplina.ensino):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"A disciplina '{disciplina.nome}' é do ensino {disciplina.ensino} e "
                    f"não pode ser vinculada a uma turma do ensino {obj.ensino}."
                ),
            )
    if carga_total > 30:
        raise HTTPException(
            status_code=422,
            detail=(
                f"A carga total do currículo ficou em {carga_total} aulas/semana, "
                "acima do máximo permitido de 30."
            ),
        )

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
