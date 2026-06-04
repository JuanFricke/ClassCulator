from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.core.auth import AnoAtivoApiDep
from app.core.deps import SessionDep
from app.models import AlocacaoSlot, GradeHoraria, GradeStatus
from app.schemas import (
    AlocacaoRead,
    GradeDetail,
    GradeGenerateRequest,
    GradeGenerateResponse,
    GradeListItem,
    GradeManualSaveRequest,
    GradeManualSaveResponse,
    GradeStatusResponse,
)
from app.services.grade_service import (
    ManualGradeConflictError,
    create_pending_grade,
    run_grade_generation,
    save_manual_grade,
)
from app.solver.builder import build_instance
from app.solver.domain import InstanceConfigurationError

router = APIRouter(prefix="/grade", tags=["grade"])


async def _get_no_ano(session: SessionDep, grade_id: int, ano_id: int) -> GradeHoraria:
    obj = await session.get(GradeHoraria, grade_id)
    if obj is None or obj.ano_letivo_id != ano_id:
        raise HTTPException(status_code=404, detail="Grade não encontrada")
    return obj


@router.get("", response_model=list[GradeListItem])
async def list_grades(session: SessionDep, ano: AnoAtivoApiDep) -> list[GradeHoraria]:
    result = await session.execute(
        select(GradeHoraria)
        .where(GradeHoraria.ano_letivo_id == ano.id)
        .order_by(GradeHoraria.criado_em.desc())
        .limit(100)
    )
    return list(result.scalars().all())


@router.post(
    "/gerar",
    response_model=GradeGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def gerar_grade(
    payload: GradeGenerateRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    ano: AnoAtivoApiDep,
) -> GradeGenerateResponse:
    # Valida o currículo antes mesmo de criar a grade — o usuário recebe um 422
    # imediato em vez de uma grade `failed` se a configuração for impossível.
    try:
        await build_instance(session, ano.id)
    except InstanceConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    grade = await create_pending_grade(session, payload, ano.id)
    background_tasks.add_task(
        run_grade_generation,
        grade_id=grade.id,
        solver_id=payload.solver,
        timeout_s=payload.timeout_s,
    )
    return GradeGenerateResponse(
        id=grade.id,
        status=grade.status.value,
        versao=grade.versao,
    )


@router.get("/status/{grade_id}", response_model=GradeStatusResponse)
async def status_grade(
    grade_id: int, session: SessionDep, ano: AnoAtivoApiDep
) -> GradeStatusResponse:
    obj = await _get_no_ano(session, grade_id, ano.id)
    mensagem = None
    if obj.status == GradeStatus.FAILED and obj.log:
        mensagem = obj.log.splitlines()[-1] if obj.log.strip() else "Falha na geração"
    return GradeStatusResponse(
        id=obj.id,
        status=obj.status.value,
        versao=obj.versao,
        solver_usado=obj.solver_usado,
        score_penalidade=obj.score_penalidade,
        tempo_segundos=obj.tempo_segundos,
        mensagem=mensagem,
    )


@router.post(
    "/{grade_id}/editar",
    response_model=GradeManualSaveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def editar_grade(
    grade_id: int,
    payload: GradeManualSaveRequest,
    session: SessionDep,
    ano: AnoAtivoApiDep,
) -> GradeManualSaveResponse:
    """Salva uma edição manual da grade como uma nova versão.

    Não roda solver/otimização; bloqueia apenas conflitos rígidos de horário.
    """

    source = await _get_no_ano(session, grade_id, ano.id)

    try:
        nova = await save_manual_grade(session, source, payload.alocacoes)
    except ManualGradeConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "A grade editada tem conflitos de horário e não pode ser salva.",
                "conflitos": exc.conflitos,
            },
        ) from exc

    return GradeManualSaveResponse(
        id=nova.id,
        versao=nova.versao,
    )


@router.get("/{grade_id}", response_model=GradeDetail)
async def detail_grade(
    grade_id: int, session: SessionDep, ano: AnoAtivoApiDep
) -> GradeDetail:
    obj = await _get_no_ano(session, grade_id, ano.id)
    result = await session.execute(
        select(AlocacaoSlot)
        .where(AlocacaoSlot.grade_id == grade_id)
        .order_by(AlocacaoSlot.turma_id, AlocacaoSlot.dia, AlocacaoSlot.slot)
    )
    alocacoes = [AlocacaoRead.model_validate(a) for a in result.scalars().all()]
    return GradeDetail(
        id=obj.id,
        versao=obj.versao,
        status=obj.status.value,
        score_penalidade=obj.score_penalidade,
        solver_usado=obj.solver_usado,
        tempo_segundos=obj.tempo_segundos,
        criado_em=obj.criado_em,
        log=obj.log,
        alocacoes=alocacoes,
    )
