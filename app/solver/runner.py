"""Despachante de solver: roteia para `cpsat` ou `classic`."""

from __future__ import annotations

from app.solver.classic import solve_classic
from app.solver.cpsat import solve_cpsat
from app.solver.domain import ProblemInstance, SolverResult


def run_solver(
    instance: ProblemInstance,
    solver_id: str,
    *,
    timeout_s: int,
    hill_iters: int = 800,
) -> SolverResult:
    if solver_id == "cpsat":
        return solve_cpsat(instance, timeout_s=timeout_s)
    if solver_id == "classic":
        return solve_classic(instance, timeout_s=timeout_s, hill_iters=hill_iters)
    raise ValueError(f"Solver desconhecido: {solver_id!r}")
