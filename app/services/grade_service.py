"""Orquestração da geração da grade horária."""

from __future__ import annotations

import logging
import traceback

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import AlocacaoSlot, GradeHoraria, GradeStatus, Sala
from app.models.sala import SalaTipo
from app.schemas import GradeGenerateRequest
from app.solver.builder import build_instance
from app.solver.domain import InstanceConfigurationError, SolverStatus
from app.solver.runner import run_solver

logger = logging.getLogger(__name__)


async def create_pending_grade(
    session: AsyncSession, payload: GradeGenerateRequest
) -> GradeHoraria:
    """Reserva uma nova versão de grade no banco com status `pending`."""

    proxima_versao = (
        await session.execute(
            select(func.coalesce(func.max(GradeHoraria.versao), 0) + 1).where(
                GradeHoraria.semestre == payload.semestre
            )
        )
    ).scalar_one()

    grade = GradeHoraria(
        semestre=payload.semestre,
        versao=int(proxima_versao),
        status=GradeStatus.PENDING,
        solver_usado=payload.solver,
    )
    session.add(grade)
    await session.commit()
    await session.refresh(grade)
    return grade


async def run_grade_generation(
    grade_id: int, solver_id: str, timeout_s: int | None
) -> None:
    """Executa o solver e persiste o resultado.

    Roda como FastAPI BackgroundTask em uma sessão própria.
    """

    async with AsyncSessionLocal() as session:
        grade = await session.get(GradeHoraria, grade_id)
        if grade is None:
            logger.error("Grade %s não encontrada para execução do solver.", grade_id)
            return

        try:
            grade.status = GradeStatus.RUNNING
            await session.commit()

            instance = await build_instance(session, grade.semestre)
            solver_timeout = timeout_s if solver_id == "cpsat" else None
            result = run_solver(
                instance,
                solver_id,
                timeout_s=solver_timeout,
                hill_iters=settings.HILL_CLIMBING_ITERATIONS,
            )
            warnings_log = "\n".join(instance.warnings).strip()
        except InstanceConfigurationError as exc:
            logger.warning(
                "Configuração inválida para a grade %s: %s", grade_id, exc
            )
            grade.status = GradeStatus.FAILED
            grade.log = (
                "Configuração de currículo insuficiente para preencher todos os "
                "horários da semana sem deixar células vazias.\n\n"
                f"Detalhe: {exc}"
            )
            await session.commit()
            return
        except Exception as exc:  # noqa: BLE001 — capturamos para registrar log
            logger.exception("Falha durante a geração da grade %s", grade_id)
            grade.status = GradeStatus.FAILED
            grade.log = f"{exc.__class__.__name__}: {exc}\n\n{traceback.format_exc()}"
            await session.commit()
            return

        if result.status != SolverStatus.OK:
            grade.status = GradeStatus.FAILED
            grade.score_penalidade = None
            grade.tempo_segundos = result.elapsed_s
            solver_log = result.log or f"Solver retornou status {result.status.value}"
            grade.log = (
                f"{warnings_log}\n{solver_log}".strip() if warnings_log else solver_log
            )
            await session.commit()
            return

        salas_disponiveis = await session.execute(select(Sala))
        salas = list(salas_disponiveis.scalars().all())
        salas_normais = [s for s in salas if s.tipo == SalaTipo.SALA]
        labs = [s for s in salas if s.tipo == SalaTipo.LAB]
        disc_by_id = {d.id: d for d in instance.disciplinas}

        for aula in instance.aulas:
            if aula.idx not in result.assignments:
                continue
            dia, slot = result.assignments[aula.idx]
            disc = disc_by_id.get(aula.disciplina_id)
            sala_id: int | None = None
            if disc and disc.requer_lab and labs:
                sala_id = labs[aula.idx % len(labs)].id
            elif salas_normais:
                sala_id = salas_normais[aula.idx % len(salas_normais)].id

            session.add(
                AlocacaoSlot(
                    grade_id=grade.id,
                    turma_id=aula.turma_id,
                    disciplina_id=aula.disciplina_id,
                    professor_id=aula.professor_id,
                    sala_id=sala_id,
                    dia=dia,
                    slot=slot,
                )
            )

        grade.status = GradeStatus.DONE
        grade.score_penalidade = float(result.score)
        grade.tempo_segundos = float(result.elapsed_s)
        grade.solver_usado = solver_id
        grade.log = (
            f"{warnings_log}\n{result.log}".strip() if warnings_log else result.log
        )
        await session.commit()
