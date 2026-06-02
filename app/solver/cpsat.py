"""Solver baseado em OR-Tools CP-SAT.

Modelagem:
- Para cada aula `a`, cada professor candidato `p` e cada `(dia, slot)` válido,
  cria-se uma variável booleana `w[a,p,d,s]` = "aula `a` ministrada pelo
  professor `p` no dia `d`, slot `s`". As variáveis só existem para `p` em
  `a.candidatos`, `(d,s)` dentro do `slots_por_dia` da turma e `(d,s)`
  disponível para `p` (HC5 por construção — slots indisponíveis não geram
  variável).
- `x[a,d,s] = sum_p w[a,p,d,s]` é a ocupação da aula no slot, independente do
  professor (usada nas restrições e soft constraints que não dependem do prof).
- HC1: `sum_{p,d,s} w[a,p,d,s] == 1` (cada aula alocada exatamente uma vez).
- Professor único por item de currículo: todas as `k` aulas de uma
  (turma, disciplina) compartilham um único professor `p` (variável `y[item,p]`).
- HC2 + HC7: para cada (turma, d, s) VÁLIDO, `sum_{a in turma} x[a,d,s] == 1`.
- HC3: para cada (professor, d, s), `sum_{a com p candidato} w[a,p,d,s] <= 1`.
- HC4: para cada turma, `sum x[a,QUARTA,s] >= min(HC4_MIN, slots_quarta)`.
- HC5: slots indisponíveis ao professor não geram variável `w` (poda).
- HC6: para cada turma e dia útil, `sum x >= min(HC6_MIN, slots_dia)`.

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
from app.solver.diagnostics import necessary_condition_report
from app.solver.domain import (
    DIAS,
    HC4_MIN_AULAS_QUARTA,
    HC6_MIN_AULAS_DIA,
    QUARTA,
    SLOTS_DIA_MAX,
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

    turma_by_id = {t.id: t for t in instance.turmas}

    # w[(a.idx, p, d, s)] — aula `a` com professor `p` em (d, s).
    # x[(a.idx, d, s)] — ocupação da aula em (d, s) = sum_p w (independe do prof).
    # Variáveis criadas apenas para (d, s) válido na turma; w apenas para
    # candidatos disponíveis em (d, s) — HC5 por construção.
    w: dict[tuple[int, int, int, int], cp_model.IntVar] = {}
    x: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for a in aulas:
        turma = turma_by_id.get(a.turma_id)
        slots_por_dia = turma.slots_por_dia if turma is not None else ()
        for d in range(DIAS):
            slots_validos_no_dia = slots_por_dia[d] if d < len(slots_por_dia) else 0
            for s in range(slots_validos_no_dia):
                w_vars: list[cp_model.IntVar] = []
                for p in a.candidatos:
                    if (d, s) in instance.indisponiveis.get(p, set()):
                        continue  # HC5 — slot indisponível ao professor (poda)
                    var = model.NewBoolVar(f"w_a{a.idx}_p{p}_d{d}_s{s}")
                    w[(a.idx, p, d, s)] = var
                    w_vars.append(var)
                occ = model.NewBoolVar(f"x_a{a.idx}_d{d}_s{s}")
                x[(a.idx, d, s)] = occ
                if w_vars:
                    model.Add(occ == sum(w_vars))
                else:
                    model.Add(occ == 0)  # nenhum candidato disponível neste slot

    # HC1 — exatamente uma alocação por aula.
    for a in aulas:
        occ_terms = [x[k] for k in x if k[0] == a.idx]
        model.Add(sum(occ_terms) == 1)

    # Professor único por item de currículo (turma, disciplina): cria y[item, p]
    # com sum_p y == 1 e amarra todas as aulas do item ao professor escolhido.
    itens: dict[tuple[int, int], list] = {}
    for a in aulas:
        itens.setdefault((a.turma_id, a.disciplina_id), []).append(a)
    for item_id, (tid, did) in enumerate(itens):
        aulas_item = itens[(tid, did)]
        candidatos = aulas_item[0].candidatos
        if not candidatos:
            continue
        y_item: dict[int, cp_model.IntVar] = {}
        for p in candidatos:
            y_item[p] = model.NewBoolVar(f"y_item{item_id}_p{p}")
        model.Add(sum(y_item.values()) == 1)
        for a in aulas_item:
            for p in candidatos:
                w_ap = [
                    w[(a.idx, p, d, s)]
                    for d in range(DIAS)
                    for s in range(SLOTS_DIA_MAX)
                    if (a.idx, p, d, s) in w
                ]
                model.Add(sum(w_ap) == y_item[p])

    # HC2 + HC7 — cada (turma, dia, slot) VÁLIDO ocupado por exatamente uma aula.
    for t in instance.turmas:
        idxs = [a.idx for a in aulas if a.turma_id == t.id]
        if not idxs:
            continue
        for d in range(DIAS):
            slots_validos = t.slots_por_dia[d] if d < len(t.slots_por_dia) else 0
            for s in range(slots_validos):
                model.Add(sum(x[(i, d, s)] for i in idxs) == 1)

    # HC3 — exclusividade de professor por slot.
    profs = {p for a in aulas for p in a.candidatos}
    for pid in profs:
        for d in range(DIAS):
            for s in range(SLOTS_DIA_MAX):
                w_pds = [
                    w[(a.idx, pid, d, s)]
                    for a in aulas
                    if (a.idx, pid, d, s) in w
                ]
                if len(w_pds) > 1:
                    model.Add(sum(w_pds) <= 1)

    # HC4 — cada turma tem pelo menos min(HC4_MIN, slots_quarta) aulas na quarta.
    for t in instance.turmas:
        idxs = [a.idx for a in aulas if a.turma_id == t.id]
        if not idxs:
            continue
        slots_quarta = t.slots_por_dia[QUARTA] if QUARTA < len(t.slots_por_dia) else 0
        minimo = min(HC4_MIN_AULAS_QUARTA, slots_quarta)
        if minimo <= 0:
            continue
        model.Add(
            sum(x[(i, QUARTA, s)] for i in idxs for s in range(slots_quarta)) >= minimo
        )

    # HC6 — cada turma com pelo menos min(HC6_MIN, slots_dia) aulas em cada dia útil.
    for t in instance.turmas:
        idxs = [a.idx for a in aulas if a.turma_id == t.id]
        if not idxs:
            continue
        for d in range(DIAS):
            slots_dia = t.slots_por_dia[d] if d < len(t.slots_por_dia) else 0
            minimo = min(HC6_MIN_AULAS_DIA, slots_dia)
            if minimo <= 0:
                continue
            model.Add(
                sum(x[(i, d, s)] for i in idxs for s in range(slots_dia)) >= minimo
            )

    objective_terms = _build_objective(model, instance, w, x)
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
        professor_por_aula: dict[int, int] = {}
        for a in aulas:
            for (aidx, p, d, s), var in w.items():
                if aidx != a.idx:
                    continue
                if solver.Value(var) == 1:
                    assignments[a.idx] = (d, s)
                    professor_por_aula[a.idx] = p
                    break
        score, breakdown = calcular_score(instance, assignments, professor_por_aula)
        log_lines.append(f"[cpsat] score={score:.0f} {breakdown}.")
        return SolverResult(
            status=SolverStatus.OK,
            assignments=assignments,
            professor_por_aula=professor_por_aula,
            score=score,
            elapsed_s=elapsed,
            log="\n".join(log_lines),
        )

    if status_code == cp_model.INFEASIBLE:
        log_lines.append("[cpsat] modelo INVIÁVEL com as restrições atuais.")
        log_lines.append(necessary_condition_report(instance))
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
    w: dict[tuple[int, int, int, int], cp_model.IntVar],
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> list[cp_model.LinearExprT]:
    """Constrói os termos da função objetivo (soft constraints com pesos do relatório)."""

    terms: list[cp_model.LinearExprT] = []

    def prof_busy(pid: int, idxs: list[int], d: int, s: int) -> cp_model.LinearExprT:
        return sum(
            w[(i, pid, d, s)] for i in idxs if (i, pid, d, s) in w
        )

    # ---- SC2 — pares consecutivos da mesma área para a mesma turma -------- #
    disc_by_id = {d.id: d for d in instance.disciplinas}
    for t in instance.turmas:
        aulas_turma = [a for a in instance.aulas if a.turma_id == t.id]
        for d in range(DIAS):
            slots_dia = t.slots_por_dia[d] if d < len(t.slots_por_dia) else 0
            for s in range(max(slots_dia - 1, 0)):
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
    profs = {p for a in instance.aulas for p in a.candidatos}
    for pid in profs:
        idxs = [a.idx for a in instance.aulas if pid in a.candidatos]
        for d in range(DIAS):
            qtd = sum(prof_busy(pid, idxs, d, s) for s in range(SLOTS_DIA_MAX))

            primeiro_marks = []
            ultimo_marks = []
            for s in range(SLOTS_DIA_MAX):
                tem_aula_s = prof_busy(pid, idxs, d, s)

                e_primeiro = model.NewBoolVar(f"sc1_first_p{pid}_d{d}_s{s}")
                # e_primeiro = 1 → tem_aula_s >= 1 e nenhum slot anterior tem aula.
                model.Add(tem_aula_s >= 1).OnlyEnforceIf(e_primeiro)
                if s > 0:
                    anteriores = sum(prof_busy(pid, idxs, d, sa) for sa in range(s))
                    model.Add(anteriores == 0).OnlyEnforceIf(e_primeiro)

                e_ultimo = model.NewBoolVar(f"sc1_last_p{pid}_d{d}_s{s}")
                model.Add(tem_aula_s >= 1).OnlyEnforceIf(e_ultimo)
                if s < SLOTS_DIA_MAX - 1:
                    posteriores = sum(
                        prof_busy(pid, idxs, d, sb) for sb in range(s + 1, SLOTS_DIA_MAX)
                    )
                    model.Add(posteriores == 0).OnlyEnforceIf(e_ultimo)

                primeiro_marks.append((s, e_primeiro))
                ultimo_marks.append((s, e_ultimo))

            primeiro_idx = sum(s * marker for s, marker in primeiro_marks)
            ultimo_idx = sum(s * marker for s, marker in ultimo_marks)
            tem_aula_no_dia = model.NewBoolVar(f"sc1_any_p{pid}_d{d}")
            model.Add(qtd >= 1).OnlyEnforceIf(tem_aula_no_dia)
            model.Add(qtd == 0).OnlyEnforceIf(tem_aula_no_dia.Not())

            janelas = model.NewIntVar(0, SLOTS_DIA_MAX, f"sc1_gap_p{pid}_d{d}")
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
            slots_dia = t.slots_por_dia[d] if d < len(t.slots_por_dia) else 0
            for s in range(max(slots_dia - 2, 0)):
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
    prof_turma: dict[tuple[int, int], list[int]] = {}
    for a in instance.aulas:
        for p in a.candidatos:
            prof_turma.setdefault((p, a.turma_id), []).append(a.idx)

    for (pid, tid), idxs in prof_turma.items():
        if len(idxs) < 2:
            continue  # com no máximo 1 aula não há possibilidade de split

        def pt_busy(d: int, s: int, _pid: int = pid, _idxs: list[int] = idxs) -> cp_model.LinearExprT:
            return sum(
                w[(i, _pid, d, s)] for i in _idxs if (i, _pid, d, s) in w
            )

        for d in range(DIAS):
            blocos = []
            for s in range(SLOTS_DIA_MAX):
                tem_aula_s = pt_busy(d, s)
                bloco_s = model.NewBoolVar(f"sc4_block_p{pid}_t{tid}_d{d}_s{s}")
                if s == 0:
                    model.Add(bloco_s == tem_aula_s)
                else:
                    tem_aula_prev = pt_busy(d, s - 1)
                    # bloco_s = 1 ⇔ tem_aula_s = 1 ∧ tem_aula_prev = 0
                    model.Add(bloco_s >= tem_aula_s - tem_aula_prev)
                    model.Add(bloco_s <= tem_aula_s)
                    model.Add(bloco_s <= 1 - tem_aula_prev)
                blocos.append(bloco_s)

            qtd = sum(pt_busy(d, s) for s in range(SLOTS_DIA_MAX))
            tem_aula_no_dia = model.NewBoolVar(f"sc4_any_p{pid}_t{tid}_d{d}")
            model.Add(qtd >= 1).OnlyEnforceIf(tem_aula_no_dia)
            model.Add(qtd == 0).OnlyEnforceIf(tem_aula_no_dia.Not())

            splits = model.NewIntVar(0, SLOTS_DIA_MAX, f"sc4_splits_p{pid}_t{tid}_d{d}")
            # splits = (nº de blocos) - 1 quando há aula no dia, 0 caso contrário.
            model.Add(splits == sum(blocos) - tem_aula_no_dia)
            model.Add(splits >= 0)
            terms.append(PESO_SC4 * splits)

    return terms
