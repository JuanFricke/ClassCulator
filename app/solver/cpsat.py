"""Solver baseado em OR-Tools CP-SAT.

Modelagem:
- Para cada aula `a` e cada `(dia, slot)`, cria-se uma variável booleana `x[a,d,s]`.
- HC1: `sum_{d,s} x[a,d,s] == 1` (cada aula é alocada exatamente uma vez).
- HC2: para cada (turma, d, s), `sum_{a in turma} x[a,d,s] <= 1`.
- HC3: para cada (professor, d, s), `sum_{a do prof} x[a,d,s] <= 1`.
- HC4: para cada turma, `sum_{a in turma, d=QUARTA, s} x[a,d,s] >= 3`.
- HC5: para `(d,s)` indisponíveis ao professor da aula, `x[a,d,s] = 0`.

Soft constraints expressas como variáveis auxiliares na função objetivo.
"""

from __future__ import annotations

import logging
import time

from ortools.sat.python import cp_model

from app.solver.constraints import (
    PESO_SC1,
    PESO_SC2,
    PESO_SC3,
    PESO_SC4,
    calcular_score,
)
from app.solver.domain import (
    DIAS,
    HC4_MIN_AULAS_QUARTA,
    HC6_MIN_AULAS_DIA,
    QUARTA,
    SLOTS_DIA,
    ProblemInstance,
    SolverResult,
    SolverStatus,
)

logger = logging.getLogger(__name__)


def solve_cpsat(
    instance: ProblemInstance,
    *,
    timeout_s: int = 30,
    workers: int = 4,
) -> SolverResult:
    started = time.monotonic()
    model = cp_model.CpModel()

    aulas = instance.aulas
    log_lines: list[str] = []

    x: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for a in aulas:
        prof_indisp = instance.indisponiveis.get(a.professor_id, set())
        for d in range(DIAS):
            for s in range(SLOTS_DIA):
                var = model.NewBoolVar(f"x_a{a.idx}_d{d}_s{s}")
                x[(a.idx, d, s)] = var
                if (d, s) in prof_indisp:
                    model.Add(var == 0)  # HC5

    # HC1 — exatamente uma alocação por aula (carga semanal = nº de aulas-instância).
    for a in aulas:
        model.Add(sum(x[(a.idx, d, s)] for d in range(DIAS) for s in range(SLOTS_DIA)) == 1)

    # HC2 + HC7 — cada (turma, dia, slot) ocupado por exatamente uma aula.
    # (HC2 = no máximo 1; HC7 = pelo menos 1 — combinados implicam == 1.
    # A consistência só é possível porque o builder valida que cada turma
    # tem exatamente DIAS*SLOTS_DIA aulas no currículo.)
    for t in instance.turmas:
        idxs = [a.idx for a in aulas if a.turma_id == t.id]
        if not idxs:
            continue
        for d in range(DIAS):
            for s in range(SLOTS_DIA):
                model.Add(sum(x[(i, d, s)] for i in idxs) == 1)

    # HC3 — exclusividade de professor por slot.
    profs = {a.professor_id for a in aulas}
    for pid in profs:
        idxs = [a.idx for a in aulas if a.professor_id == pid]
        for d in range(DIAS):
            for s in range(SLOTS_DIA):
                model.Add(sum(x[(i, d, s)] for i in idxs) <= 1)

    # HC4 — cada turma tem pelo menos HC4_MIN_AULAS_QUARTA aulas na quarta-feira.
    for t in instance.turmas:
        idxs = [a.idx for a in aulas if a.turma_id == t.id]
        if not idxs:
            continue
        model.Add(
            sum(x[(i, QUARTA, s)] for i in idxs for s in range(SLOTS_DIA))
            >= HC4_MIN_AULAS_QUARTA
        )

    # HC6 — cada turma com pelo menos HC6_MIN_AULAS_DIA aulas em cada dia.
    for t in instance.turmas:
        idxs = [a.idx for a in aulas if a.turma_id == t.id]
        if not idxs:
            continue
        for d in range(DIAS):
            model.Add(
                sum(x[(i, d, s)] for i in idxs for s in range(SLOTS_DIA))
                >= HC6_MIN_AULAS_DIA
            )

    objective_terms = _build_objective(model, instance, x)
    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(timeout_s)
    solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = False

    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started

    log_lines.append(
        f"[cpsat] status={solver.StatusName(status_code)} "
        f"objective={solver.ObjectiveValue() if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 'n/a'} "
        f"em {elapsed:.2f}s."
    )

    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments: dict[int, tuple[int, int]] = {}
        for a in aulas:
            for d in range(DIAS):
                for s in range(SLOTS_DIA):
                    if solver.Value(x[(a.idx, d, s)]) == 1:
                        assignments[a.idx] = (d, s)
                        break
        score, breakdown = calcular_score(instance, assignments)
        log_lines.append(f"[cpsat] score={score:.0f} {breakdown}.")
        return SolverResult(
            status=SolverStatus.OK,
            assignments=assignments,
            score=score,
            elapsed_s=elapsed,
            log="\n".join(log_lines),
        )

    if status_code == cp_model.INFEASIBLE:
        log_lines.append("[cpsat] modelo INVIÁVEL com as restrições atuais.")
        return SolverResult(
            status=SolverStatus.INFEASIBLE,
            elapsed_s=elapsed,
            log="\n".join(log_lines),
        )

    log_lines.append("[cpsat] solver não encontrou solução dentro do timeout.")
    return SolverResult(status=SolverStatus.TIMEOUT, elapsed_s=elapsed, log="\n".join(log_lines))


def _build_objective(
    model: cp_model.CpModel,
    instance: ProblemInstance,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> list[cp_model.LinearExprT]:
    """Constrói os termos da função objetivo (soft constraints com pesos do relatório)."""

    terms: list[cp_model.LinearExprT] = []

    # ---- SC2 — pares consecutivos da mesma área para a mesma turma -------- #
    disc_by_id = {d.id: d for d in instance.disciplinas}
    for t in instance.turmas:
        aulas_turma = [a for a in instance.aulas if a.turma_id == t.id]
        for d in range(DIAS):
            for s in range(SLOTS_DIA - 1):
                pair_terms: list[cp_model.IntVar] = []
                for a1 in aulas_turma:
                    d1 = disc_by_id[a1.disciplina_id]
                    for a2 in aulas_turma:
                        if a1.idx == a2.idx:
                            continue
                        d2 = disc_by_id[a2.disciplina_id]
                        if d1.area != d2.area or d1.id == d2.id:
                            continue
                        ind = model.NewBoolVar(f"sc2_t{t.id}_d{d}_s{s}_a{a1.idx}_a{a2.idx}")
                        model.AddBoolAnd(
                            [x[(a1.idx, d, s)], x[(a2.idx, d, s + 1)]]
                        ).OnlyEnforceIf(ind)
                        model.AddBoolOr(
                            [x[(a1.idx, d, s)].Not(), x[(a2.idx, d, s + 1)].Not()]
                        ).OnlyEnforceIf(ind.Not())
                        pair_terms.append(ind)
                if pair_terms:
                    terms.append(PESO_SC2 * sum(pair_terms))

    # ---- SC1 — janelas vazias do professor no dia ------------------------- #
    # SC1 = (último - primeiro + 1) - quantidade_de_aulas_do_dia, quando aulas_do_dia >= 2.
    profs = {a.professor_id for a in instance.aulas}
    for pid in profs:
        idxs = [a.idx for a in instance.aulas if a.professor_id == pid]
        for d in range(DIAS):
            qtd = sum(x[(i, d, s)] for i in idxs for s in range(SLOTS_DIA))

            primeiro_marks = []
            ultimo_marks = []
            for s in range(SLOTS_DIA):
                tem_aula_s = sum(x[(i, d, s)] for i in idxs)

                e_primeiro = model.NewBoolVar(f"sc1_first_p{pid}_d{d}_s{s}")
                # e_primeiro = 1 → tem_aula_s >= 1 e nenhum slot anterior tem aula.
                model.Add(tem_aula_s >= 1).OnlyEnforceIf(e_primeiro)
                if s > 0:
                    anteriores = sum(x[(i, d, sa)] for i in idxs for sa in range(s))
                    model.Add(anteriores == 0).OnlyEnforceIf(e_primeiro)

                e_ultimo = model.NewBoolVar(f"sc1_last_p{pid}_d{d}_s{s}")
                model.Add(tem_aula_s >= 1).OnlyEnforceIf(e_ultimo)
                if s < SLOTS_DIA - 1:
                    posteriores = sum(
                        x[(i, d, sb)] for i in idxs for sb in range(s + 1, SLOTS_DIA)
                    )
                    model.Add(posteriores == 0).OnlyEnforceIf(e_ultimo)

                primeiro_marks.append((s, e_primeiro))
                ultimo_marks.append((s, e_ultimo))

            primeiro_idx = sum(s * marker for s, marker in primeiro_marks)
            ultimo_idx = sum(s * marker for s, marker in ultimo_marks)
            tem_aula_no_dia = model.NewBoolVar(f"sc1_any_p{pid}_d{d}")
            model.Add(qtd >= 1).OnlyEnforceIf(tem_aula_no_dia)
            model.Add(qtd == 0).OnlyEnforceIf(tem_aula_no_dia.Not())

            janelas = model.NewIntVar(0, SLOTS_DIA, f"sc1_gap_p{pid}_d{d}")
            model.Add(janelas == ultimo_idx - primeiro_idx + tem_aula_no_dia - qtd)
            model.Add(janelas >= 0)
            terms.append(PESO_SC1 * janelas)

    # ---- SC3 — bloco de 3+ aulas teóricas consecutivas para a turma ------- #
    for t in instance.turmas:
        aulas_turma_teorica = [
            a for a in instance.aulas
            if a.turma_id == t.id and disc_by_id[a.disciplina_id].eh_teorica
        ]
        if not aulas_turma_teorica:
            continue
        for d in range(DIAS):
            for s in range(SLOTS_DIA - 2):
                bloco = model.NewBoolVar(f"sc3_t{t.id}_d{d}_s{s}")
                soma_3 = sum(
                    x[(a.idx, d, s + offset)]
                    for a in aulas_turma_teorica
                    for offset in range(3)
                )
                model.Add(soma_3 >= 3).OnlyEnforceIf(bloco)
                model.Add(soma_3 <= 2).OnlyEnforceIf(bloco.Not())
                terms.append(PESO_SC3 * bloco)

    # ---- SC4 — janelas entre aulas do mesmo (professor, turma) no dia ----- #
    # Conta o número de "blocos" extras — se o professor tem aulas com a turma
    # no dia, o ideal é todas em um único bloco contíguo. Cada bloco a mais
    # equivale a um "split" e penaliza com peso PESO_SC4. Formulação por
    # detecção de borda (start_s = aula em s e nenhuma em s-1).
    prof_turma: dict[tuple[int, int], list] = {}
    for a in instance.aulas:
        prof_turma.setdefault((a.professor_id, a.turma_id), []).append(a)

    for (pid, tid), aulas_pt in prof_turma.items():
        if len(aulas_pt) < 2:
            continue  # com no máximo 1 aula não há possibilidade de split

        for d in range(DIAS):
            blocos = []
            for s in range(SLOTS_DIA):
                tem_aula_s = sum(x[(a.idx, d, s)] for a in aulas_pt)
                bloco_s = model.NewBoolVar(f"sc4_block_p{pid}_t{tid}_d{d}_s{s}")
                if s == 0:
                    model.Add(bloco_s == tem_aula_s)
                else:
                    tem_aula_prev = sum(x[(a.idx, d, s - 1)] for a in aulas_pt)
                    # bloco_s = 1 ⇔ tem_aula_s = 1 ∧ tem_aula_prev = 0
                    model.Add(bloco_s >= tem_aula_s - tem_aula_prev)
                    model.Add(bloco_s <= tem_aula_s)
                    model.Add(bloco_s <= 1 - tem_aula_prev)
                blocos.append(bloco_s)

            qtd = sum(x[(a.idx, d, s)] for a in aulas_pt for s in range(SLOTS_DIA))
            tem_aula_no_dia = model.NewBoolVar(f"sc4_any_p{pid}_t{tid}_d{d}")
            model.Add(qtd >= 1).OnlyEnforceIf(tem_aula_no_dia)
            model.Add(qtd == 0).OnlyEnforceIf(tem_aula_no_dia.Not())

            splits = model.NewIntVar(0, SLOTS_DIA, f"sc4_splits_p{pid}_t{tid}_d{d}")
            # splits = (nº de blocos) - 1 quando há aula no dia, 0 caso contrário.
            model.Add(splits == sum(blocos) - tem_aula_no_dia)
            model.Add(splits >= 0)
            terms.append(PESO_SC4 * splits)

    return terms
