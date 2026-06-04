"""Orquestração da geração da grade horária."""

from __future__ import annotations

import logging
import traceback

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import (
    AlocacaoSlot,
    Disciplina,
    GradeHoraria,
    GradeStatus,
    Professor,
    Sala,
    Turma,
)
from app.models.sala import SalaTipo
from app.schemas import AlocacaoManualItem, GradeGenerateRequest
from app.solver.builder import build_instance
from app.solver.domain import InstanceConfigurationError, SolverStatus
from app.solver.runner import run_solver

logger = logging.getLogger(__name__)


class ManualGradeConflictError(ValueError):
    """Conflitos rígidos de horário detectados ao salvar uma grade editada manualmente.

    Distinto de um erro genérico: carrega a lista legível de conflitos para que a
    camada de API devolva um 422 com a descrição de cada choque (mesmo professor ou
    mesma turma em dois lugares no mesmo (dia, slot)).
    """

    def __init__(self, conflitos: list[str]) -> None:
        self.conflitos = conflitos
        super().__init__("; ".join(conflitos))


async def create_pending_grade(
    session: AsyncSession, payload: GradeGenerateRequest, ano_letivo_id: int
) -> GradeHoraria:
    """Reserva uma nova versão de grade no banco com status `pending`."""

    proxima_versao = (
        await session.execute(
            select(func.coalesce(func.max(GradeHoraria.versao), 0) + 1).where(
                GradeHoraria.ano_letivo_id == ano_letivo_id
            )
        )
    ).scalar_one()

    grade = GradeHoraria(
        ano_letivo_id=ano_letivo_id,
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

            instance = await build_instance(session, grade.ano_letivo_id)
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
                professor_id=result.professor_por_aula.get(aula.idx, aula.professor_id),
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


_DIAS_LABELS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta")


def _label_dia(dia: int) -> str:
    return _DIAS_LABELS[dia] if 0 <= dia < len(_DIAS_LABELS) else f"dia {dia}"


def _quando(dia: int, slot: int) -> str:
    return f"{_label_dia(dia)}, período {slot + 1}"


def _detectar_conflitos(
    alocacoes: list[AlocacaoManualItem],
    *,
    prof_nome: dict[int, str] | None = None,
    turma_nome: dict[int, str] | None = None,
    disc_nome: dict[int, str] | None = None,
) -> list[str]:
    """Detecta apenas conflitos rígidos de horário (sem score/otimização).

    Em cada (dia, slot) o mesmo professor ou a mesma turma não podem aparecer
    duas vezes. Retorna descrições legíveis e acionáveis (com nomes, dia da
    semana, período e exatamente quais turmas/disciplinas se chocam), para que
    o usuário consiga localizar e corrigir o conflito. Lista vazia → sem conflitos.
    """

    prof_nome = prof_nome or {}
    turma_nome = turma_nome or {}
    disc_nome = disc_nome or {}

    def nome_prof(pid: int) -> str:
        return prof_nome.get(pid, f"professor #{pid}")

    def nome_turma(tid: int) -> str:
        return turma_nome.get(tid, f"turma #{tid}")

    def nome_disc(did: int) -> str:
        return disc_nome.get(did, f"disciplina #{did}")

    por_professor: dict[tuple[int, int, int], list[AlocacaoManualItem]] = {}
    por_turma: dict[tuple[int, int, int], list[AlocacaoManualItem]] = {}
    for item in alocacoes:
        por_professor.setdefault((item.professor_id, item.dia, item.slot), []).append(item)
        por_turma.setdefault((item.turma_id, item.dia, item.slot), []).append(item)

    conflitos: list[str] = []

    for (pid, dia, slot), itens in por_professor.items():
        if len(itens) > 1:
            detalhes = ", ".join(
                f"{nome_turma(it.turma_id)} ({nome_disc(it.disciplina_id)})" for it in itens
            )
            conflitos.append(
                f"{_quando(dia, slot)}: {nome_prof(pid)} está em {len(itens)} aulas ao "
                f"mesmo tempo — {detalhes}. Mantenha apenas uma dessas aulas neste horário "
                "e mova as demais para um período livre (ou troque o professor)."
            )

    for (tid, dia, slot), itens in por_turma.items():
        if len(itens) > 1:
            detalhes = ", ".join(
                f"{nome_disc(it.disciplina_id)} ({nome_prof(it.professor_id)})" for it in itens
            )
            conflitos.append(
                f"{_quando(dia, slot)}: a turma {nome_turma(tid)} tem {len(itens)} aulas no "
                f"mesmo horário — {detalhes}. Deixe apenas uma aula por período nessa turma."
            )

    return conflitos


async def _nomes_para_conflitos(
    session: AsyncSession, alocacoes: list[AlocacaoManualItem]
) -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
    """Carrega nomes (professor/turma/disciplina) apenas dos ids referenciados."""

    prof_ids = {a.professor_id for a in alocacoes}
    turma_ids = {a.turma_id for a in alocacoes}
    disc_ids = {a.disciplina_id for a in alocacoes}

    prof_nome: dict[int, str] = {}
    turma_nome: dict[int, str] = {}
    disc_nome: dict[int, str] = {}
    if prof_ids:
        rows = (
            await session.execute(
                select(Professor.id, Professor.nome).where(Professor.id.in_(prof_ids))
            )
        ).all()
        prof_nome = {pid: nome for pid, nome in rows}
    if turma_ids:
        rows = (
            await session.execute(
                select(Turma.id, Turma.identificador).where(Turma.id.in_(turma_ids))
            )
        ).all()
        turma_nome = {tid: ident for tid, ident in rows}
    if disc_ids:
        rows = (
            await session.execute(
                select(Disciplina.id, Disciplina.nome).where(Disciplina.id.in_(disc_ids))
            )
        ).all()
        disc_nome = {did: nome for did, nome in rows}
    return prof_nome, turma_nome, disc_nome


async def save_manual_grade(
    session: AsyncSession,
    source: GradeHoraria,
    alocacoes: list[AlocacaoManualItem],
) -> GradeHoraria:
    """Persiste uma grade editada manualmente como uma NOVA versão.

    Não roda solver nem calcula score. A única validação é bloquear conflitos
    rígidos de horário (mesmo professor/turma no mesmo (dia, slot)); células
    vazias são permitidas (simplesmente não geram AlocacaoSlot).
    """

    prof_nome, turma_nome, disc_nome = await _nomes_para_conflitos(session, alocacoes)
    conflitos = _detectar_conflitos(
        alocacoes,
        prof_nome=prof_nome,
        turma_nome=turma_nome,
        disc_nome=disc_nome,
    )
    if conflitos:
        raise ManualGradeConflictError(conflitos)

    proxima_versao = (
        await session.execute(
            select(func.coalesce(func.max(GradeHoraria.versao), 0) + 1).where(
                GradeHoraria.ano_letivo_id == source.ano_letivo_id
            )
        )
    ).scalar_one()

    nova = GradeHoraria(
        ano_letivo_id=source.ano_letivo_id,
        versao=int(proxima_versao),
        status=GradeStatus.DONE,
        solver_usado="manual",
        score_penalidade=None,
        tempo_segundos=None,
        log=f"Grade editada manualmente a partir da v{source.versao}.",
    )
    session.add(nova)
    await session.flush()

    for item in alocacoes:
        session.add(
            AlocacaoSlot(
                grade_id=nova.id,
                turma_id=item.turma_id,
                disciplina_id=item.disciplina_id,
                professor_id=item.professor_id,
                sala_id=item.sala_id,
                dia=item.dia,
                slot=item.slot,
            )
        )

    await session.commit()
    await session.refresh(nova)
    return nova
