"""Solver clássico: Backtracking + Forward Checking + MRV → Hill Climbing.

Algoritmo descrito em §3.2 do relatório técnico.
"""

from __future__ import annotations

import logging
import random
import time
from copy import deepcopy

from app.solver.constraints import calcular_score
from app.solver.diagnostics import necessary_condition_report
from app.solver.domain import (
    DIAS,
    SLOTS_DIA,
    Aula,
    ProblemInstance,
    SolverResult,
    SolverStatus,
)

logger = logging.getLogger(__name__)


def solve_classic(
    instance: ProblemInstance,
    *,
    timeout_s: int | None = None,
    hill_iters: int = 800,
    stop_on_first_feasible: bool = False,
    seed: int | None = None,
) -> SolverResult:
    """Resolve em duas fases: viabilidade (backtracking+FC+MRV) e otimização (hill climbing)."""

    rng = random.Random(seed)
    started = time.monotonic()
    deadline = started + timeout_s if timeout_s is not None else float("inf")

    log_lines: list[str] = []

    # Guarda: o solver clássico usa o professor fixado em cada aula
    # (aula.professor_id). Itens "sem preferência" (professor_id None) só são
    # resolvidos pelo CP-SAT, que escolhe o professor ideal.
    if any(a.professor_id is None for a in instance.aulas):
        return SolverResult(
            status=SolverStatus.ERROR,
            elapsed_s=time.monotonic() - started,
            log=(
                "O solver clássico exige um professor fixado em cada item do "
                "currículo. Há itens marcados como 'sem preferência' "
                "(professor automático). Use solver='cpsat' para que o solver "
                "escolha o professor ideal automaticamente."
            ),
        )

    # Guarda: o solver clássico ainda assume grade retangular 5 × SLOTS_DIA.
    # Para datasets com `slots_por_dia` irregular (ex.: app.seed_alt), retornamos
    # erro amigável e direcionamos o usuário ao CP-SAT.
    irregulares = [t.identificador for t in instance.turmas if not t.is_retangular]
    if irregulares:
        return SolverResult(
            status=SolverStatus.ERROR,
            elapsed_s=time.monotonic() - started,
            log=(
                "O solver clássico só suporta turmas com grade retangular "
                f"(5 dias × {SLOTS_DIA} slots = {SLOTS_DIA * DIAS} períodos/semana). "
                f"Turmas com slots_por_dia irregular detectadas: "
                f"{', '.join(irregulares[:8])}"
                f"{' (+%d outras)' % (len(irregulares) - 8) if len(irregulares) > 8 else ''}. "
                "Use solver='cpsat' para gerar a grade deste dataset."
            ),
        )

    domains = _initial_domains(instance)

    if any(len(d) == 0 for d in domains.values()):
        diag = necessary_condition_report(instance)
        return SolverResult(
            status=SolverStatus.INFEASIBLE,
            log="Domínio vazio detectado em pré-processamento (HC5/HC4 inviável).\n" + diag,
            elapsed_s=time.monotonic() - started,
        )

    assignments: dict[int, tuple[int, int]] = {}
    state = _State(
        instance=instance,
        domains=domains,
        assignments=assignments,
        deadline=deadline,
    )

    if not _backtrack(state):
        elapsed = time.monotonic() - started
        if time.monotonic() > deadline:
            return SolverResult(
                status=SolverStatus.TIMEOUT,
                log="Timeout antes de obter solução viável.",
                elapsed_s=elapsed,
            )
        return SolverResult(
            status=SolverStatus.INFEASIBLE,
            log="Backtracking não encontrou solução viável.\n" + necessary_condition_report(instance),
            elapsed_s=elapsed,
        )

    score, breakdown = calcular_score(instance, state.assignments)
    log_lines.append(
        f"[fase1] solução viável encontrada. score inicial={score:.0f} {breakdown}."
    )

    if stop_on_first_feasible:
        elapsed = time.monotonic() - started
        log_lines.append(
            f"[fase2] otimização desativada (modo checagem). retorno em {elapsed:.2f}s."
        )
        return SolverResult(
            status=SolverStatus.OK,
            assignments=dict(state.assignments),
            score=score,
            elapsed_s=elapsed,
            log="\n".join(log_lines),
        )

    state.assignments, score, breakdown = _hill_climbing(
        instance,
        state.assignments,
        max_iters=hill_iters,
        rng=rng,
        deadline=deadline,
    )
    elapsed = time.monotonic() - started
    log_lines.append(
        f"[fase2] hill climbing concluído. score final={score:.0f} {breakdown} em {elapsed:.2f}s."
    )

    return SolverResult(
        status=SolverStatus.OK,
        assignments=dict(state.assignments),
        score=score,
        elapsed_s=elapsed,
        log="\n".join(log_lines),
    )


# --------------------------------------------------------------------------- #
# Fase 1 — Backtracking + Forward Checking + MRV
# --------------------------------------------------------------------------- #


class _State:
    __slots__ = ("instance", "domains", "assignments", "deadline")

    def __init__(
        self,
        instance: ProblemInstance,
        domains: dict[int, list[tuple[int, int]]],
        assignments: dict[int, tuple[int, int]],
        deadline: float,
    ) -> None:
        self.instance = instance
        self.domains = domains
        self.assignments = assignments
        self.deadline = deadline


def _initial_domains(instance: ProblemInstance) -> dict[int, list[tuple[int, int]]]:
    todos = [(d, s) for d in range(DIAS) for s in range(SLOTS_DIA)]
    domains: dict[int, list[tuple[int, int]]] = {}
    for aula in instance.aulas:
        prof_indisp = instance.indisponiveis.get(aula.professor_id, set())
        domains[aula.idx] = [pair for pair in todos if pair not in prof_indisp]
    return domains


def _select_unassigned_var_mrv(state: _State) -> int | None:
    best_idx: int | None = None
    best_size = float("inf")
    for aula in state.instance.aulas:
        if aula.idx in state.assignments:
            continue
        size = len(state.domains[aula.idx])
        if size < best_size:
            best_idx = aula.idx
            best_size = size
            if size <= 1:
                break
    return best_idx


def _is_consistent(
    instance: ProblemInstance,
    aula: Aula,
    valor: tuple[int, int],
    assignments: dict[int, tuple[int, int]],
) -> bool:
    dia, slot = valor
    for other_idx, other_val in assignments.items():
        if other_val != valor:
            continue
        other = instance.aulas[other_idx]
        if other.turma_id == aula.turma_id:
            return False  # HC2
        if other.professor_id == aula.professor_id:
            return False  # HC3
    return True


def _forward_check(
    state: _State, aula: Aula, valor: tuple[int, int]
) -> dict[int, list[tuple[int, int]]]:
    """Remove `valor` dos domínios das variáveis que conflitam.

    Retorna o dicionário de remoções para que possam ser desfeitas em backtrack.
    """

    removidos: dict[int, list[tuple[int, int]]] = {}
    for other in state.instance.aulas:
        if other.idx == aula.idx or other.idx in state.assignments:
            continue
        if other.turma_id == aula.turma_id or other.professor_id == aula.professor_id:
            dom = state.domains[other.idx]
            if valor in dom:
                dom.remove(valor)
                removidos.setdefault(other.idx, []).append(valor)
    return removidos


def _restore(state: _State, removidos: dict[int, list[tuple[int, int]]]) -> None:
    for idx, vals in removidos.items():
        state.domains[idx].extend(vals)


def _hcs_atendivel(state: _State) -> bool:
    """Verifica que HC4/HC6/HC7 ainda são alcançáveis a partir do estado parcial.

    Pré-condição: o builder valida que cada turma tem exatamente
    DIAS*SLOTS_DIA aulas no currículo (HC7 prévia). Aqui forçamos:
    - ja_por_dia[d] <= SLOTS_DIA (impossível exceder os 6 slots disponíveis)
    - ja_por_dia[d] + possivel_por_dia[d] >= SLOTS_DIA (cada dia precisa
      poder ser totalmente preenchido)
    O bound de SLOTS_DIA já implica HC4 (quarta-feira ≥ 3) e HC6 (cada dia ≥ 1).
    """

    for turma in state.instance.turmas:
        ja_por_dia = [0] * DIAS
        possivel_por_dia = [0] * DIAS
        for aula in state.instance.aulas:
            if aula.turma_id != turma.id:
                continue
            if aula.idx in state.assignments:
                ja_por_dia[state.assignments[aula.idx][0]] += 1
            else:
                dias_no_dominio = {d for d, _ in state.domains[aula.idx]}
                for d in dias_no_dominio:
                    possivel_por_dia[d] += 1

        for d in range(DIAS):
            if ja_por_dia[d] > SLOTS_DIA:
                return False  # HC2 (mais aulas que slots no dia)
            if ja_por_dia[d] + possivel_por_dia[d] < SLOTS_DIA:
                return False  # HC7: não há aulas suficientes para preencher o dia
    return True


def _backtrack(state: _State) -> bool:
    if time.monotonic() > state.deadline:
        return False
    if len(state.assignments) == len(state.instance.aulas):
        return True

    var = _select_unassigned_var_mrv(state)
    if var is None:
        return True
    aula = state.instance.aulas[var]

    valores = list(state.domains[var])
    random.shuffle(valores)

    for valor in valores:
        if not _is_consistent(state.instance, aula, valor, state.assignments):
            continue

        state.assignments[var] = valor
        removidos = _forward_check(state, aula, valor)

        if not any(len(state.domains[i]) == 0 for i in state.domains if i not in state.assignments):
            if _hcs_atendivel(state):
                if _backtrack(state):
                    return True

        del state.assignments[var]
        _restore(state, removidos)

    return False


# --------------------------------------------------------------------------- #
# Fase 2 — Hill Climbing
# --------------------------------------------------------------------------- #


def _hill_climbing(
    instance: ProblemInstance,
    assignments: dict[int, tuple[int, int]],
    *,
    max_iters: int,
    rng: random.Random,
    deadline: float,
) -> tuple[dict[int, tuple[int, int]], float, dict[str, int]]:
    """Faz movimentos de melhoria local mantendo todas as HCs satisfeitas.

    Como HC7 obriga cada (turma, dia) a ter exatamente SLOTS_DIA aulas, o único
    movimento que preserva todas as HCs é a TROCA de duas aulas da mesma turma.
    """

    current = deepcopy(assignments)
    score, breakdown = calcular_score(instance, current)

    aulas_por_turma: dict[int, list[int]] = {}
    for aula in instance.aulas:
        aulas_por_turma.setdefault(aula.turma_id, []).append(aula.idx)

    turmas_com_aulas = [tid for tid, lst in aulas_por_turma.items() if len(lst) >= 2]
    if not turmas_com_aulas:
        return current, score, breakdown

    for _ in range(max_iters):
        if score == 0 or time.monotonic() > deadline:
            break

        tid = rng.choice(turmas_com_aulas)
        idx_a, idx_b = rng.sample(aulas_por_turma[tid], 2)
        if not _swap_preserva_hc(instance, current, idx_a, idx_b):
            continue

        slot_a = current[idx_a]
        slot_b = current[idx_b]
        current[idx_a] = slot_b
        current[idx_b] = slot_a

        novo_score, novo_breakdown = calcular_score(instance, current)
        if novo_score < score:
            score = novo_score
            breakdown = novo_breakdown
        else:
            current[idx_a] = slot_a
            current[idx_b] = slot_b

    return current, score, breakdown


def _swap_preserva_hc(
    instance: ProblemInstance,
    current: dict[int, tuple[int, int]],
    idx_a: int,
    idx_b: int,
) -> bool:
    """Verifica que a troca dos slots de `idx_a` e `idx_b` (mesma turma) é válida.

    Como ambas as aulas pertencem à mesma turma, HC2/HC4/HC6/HC7 (contagens por
    turma) ficam intactos automaticamente. Só falta:
    - HC3: nenhum outro aula do mesmo professor está no slot de destino;
    - HC5: o professor deve estar disponível no novo slot.
    """

    aula_a = instance.aulas[idx_a]
    aula_b = instance.aulas[idx_b]
    slot_a = current[idx_a]
    slot_b = current[idx_b]
    if slot_a == slot_b:
        return True

    indisp_a = instance.indisponiveis.get(aula_a.professor_id, set())
    indisp_b = instance.indisponiveis.get(aula_b.professor_id, set())
    if slot_b in indisp_a or slot_a in indisp_b:
        return False  # HC5

    # HC3: nenhum outro aula do mesmo professor já ocupa o slot de destino.
    for outro_idx, outro_val in current.items():
        if outro_idx in (idx_a, idx_b):
            continue
        outro = instance.aulas[outro_idx]
        if outro.professor_id == aula_a.professor_id and outro_val == slot_b:
            return False
        if outro.professor_id == aula_b.professor_id and outro_val == slot_a:
            return False
    return True
