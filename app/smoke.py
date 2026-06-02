"""Smoke test offline: roda os dois solvers contra o dataset seedeado.

Uso (dentro do container, após `docker compose run --rm app python -m app.seed`):

    docker compose run --rm app python -m app.smoke
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.solver.builder import build_instance
from app.solver.constraints import violacoes_hard
from app.solver.runner import run_solver

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        instance = await build_instance(session, "2026/1")
        logger.info(
            "Instância construída: %d turmas · %d disciplinas · %d professores · %d aulas.",
            len(instance.turmas),
            len(instance.disciplinas),
            len(instance.professores),
            len(instance.aulas),
        )

    for solver_id in ("classic", "cpsat"):
        logger.info("\n=== Solver %s ===", solver_id)
        result = run_solver(
            instance,
            solver_id,
            timeout_s=settings.SOLVER_TIMEOUT_S,
            hill_iters=settings.HILL_CLIMBING_ITERATIONS,
        )
        logger.info("status=%s score=%.0f tempo=%.2fs", result.status.value, result.score, result.elapsed_s)
        violacoes = violacoes_hard(instance, result.assignments, result.professor_por_aula)
        if violacoes:
            logger.warning("VIOLAÇÕES de hard constraints (%d):", len(violacoes))
            for v in violacoes[:10]:
                logger.warning("  - %s", v)
        else:
            logger.info("Todas as hard constraints satisfeitas.")
        if result.log:
            logger.info("Log:\n%s", result.log)


if __name__ == "__main__":
    asyncio.run(main())
