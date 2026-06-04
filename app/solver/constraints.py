"""Cálculo das restrições e da função de penalidade.

Soft constraints (com pesos do relatório + extensões do projeto):

- SC1: 100 × janelas vazias entre primeira e última aula do professor no dia
- SC2: 30 × pares consecutivos de disciplinas da mesma área para a mesma turma
- SC3: 50 × bloco de 3+ aulas teóricas consecutivas sem intervalo prático
- SC4: 200 × splits entre aulas do mesmo (professor, turma) no dia (alto peso —
  conta cada bloco adicional além do primeiro; obriga o professor que ministra
  múltiplas aulas em uma turma no mesmo dia a fazê-lo em períodos contíguos)
"""

from __future__ import annotations

from app.solver.domain import (
    DIAS,
    HC4_MIN_AULAS_QUARTA,
    HC6_MIN_AULAS_DIA,
    QUARTA,
    SLOTS_DIA_MAX,
    ProblemInstance,
)

PESO_SC1 = 100
PESO_SC2 = 30
PESO_SC3 = 50
PESO_SC4 = 200


def violacoes_hard(
    instance: ProblemInstance,
    assignments: dict[int, tuple[int, int]],
    professor_por_aula: dict[int, int] | None = None,
) -> list[str]:
    """Retorna a lista de descrições de violações de hard constraints (vazia → válida)."""

    violacoes: list[str] = []

    by_aula = {a.idx: a for a in instance.aulas}
    prof_map = professor_por_aula or {}

    def prof_de(idx: int) -> int | None:
        return prof_map.get(idx, by_aula[idx].professor_id)

    # HC1 — todas as aulas atribuídas
    if len(assignments) != len(instance.aulas):
        violacoes.append(
            f"HC1: {len(assignments)} alocações para {len(instance.aulas)} aulas requeridas."
        )

    # HC2 — turma exclusiva por slot
    turma_slot: dict[tuple[int, int, int], int] = {}
    for idx, (dia, slot) in assignments.items():
        a = by_aula[idx]
        chave = (a.turma_id, dia, slot)
        if chave in turma_slot:
            violacoes.append(f"HC2: turma {a.turma_id} duplicada em ({dia},{slot}).")
        else:
            turma_slot[chave] = idx

    # HC3 — professor exclusivo por slot
    prof_slot: dict[tuple[int, int, int], int] = {}
    for idx, (dia, slot) in assignments.items():
        pid = prof_de(idx)
        if pid is None:
            continue
        chave = (pid, dia, slot)
        if chave in prof_slot:
            violacoes.append(f"HC3: professor {pid} duplicado em ({dia},{slot}).")
        else:
            prof_slot[chave] = idx

    # HC4 — cada turma com >= HC4_MIN_AULAS_QUARTA aulas na quarta-feira (quando há
    # slots suficientes na quarta para acomodar o mínimo).
    aulas_quarta: dict[int, int] = {t.id: 0 for t in instance.turmas}
    for idx, (dia, _slot) in assignments.items():
        a = by_aula[idx]
        if dia == QUARTA:
            aulas_quarta[a.turma_id] = aulas_quarta.get(a.turma_id, 0) + 1
    for turma in instance.turmas:
        slots_quarta = turma.slots_por_dia[QUARTA]
        minimo = min(HC4_MIN_AULAS_QUARTA, slots_quarta)
        qtd = aulas_quarta.get(turma.id, 0)
        if qtd < minimo:
            violacoes.append(
                f"HC4: turma {turma.id} tem apenas {qtd} aula(s) na quarta-feira "
                f"(mínimo {minimo} para slots_dia[quarta]={slots_quarta})."
            )
        if qtd > slots_quarta:
            violacoes.append(
                f"HC4: turma {turma.id} tem {qtd} aulas na quarta-feira mas só "
                f"existem {slots_quarta} slots disponíveis."
            )

    # HC5 — professor disponível
    for idx, (dia, slot) in assignments.items():
        pid = prof_de(idx)
        if pid is None:
            continue
        if not instance.professor_disponivel(pid, dia, slot):
            violacoes.append(
                f"HC5: professor {pid} indisponível em ({dia},{slot})."
            )

    # HC6 — toda turma com >= HC6_MIN_AULAS_DIA aulas em cada dia útil
    # (dias com slots_por_dia[d] == 0 são "sem expediente" e ficam livres por design).
    aulas_por_dia: dict[tuple[int, int], int] = {}
    for idx, (dia, _slot) in assignments.items():
        a = by_aula[idx]
        chave = (a.turma_id, dia)
        aulas_por_dia[chave] = aulas_por_dia.get(chave, 0) + 1
    for turma in instance.turmas:
        for dia in range(DIAS):
            slots_dia = turma.slots_por_dia[dia]
            qtd = aulas_por_dia.get((turma.id, dia), 0)
            if slots_dia == 0:
                if qtd > 0:
                    violacoes.append(
                        f"HC6: turma {turma.id} recebeu {qtd} aula(s) no dia {dia}, "
                        "mas slots_por_dia[d]=0 (dia sem expediente)."
                    )
                continue
            minimo = min(HC6_MIN_AULAS_DIA, slots_dia)
            if qtd < minimo:
                violacoes.append(
                    f"HC6: turma {turma.id} sem aulas no dia {dia} "
                    f"(esperado pelo menos {minimo})."
                )
            if qtd > slots_dia:
                violacoes.append(
                    f"HC6: turma {turma.id} com {qtd} aulas no dia {dia}, "
                    f"mas só existem {slots_dia} slots."
                )

    # HC7 — cada turma deve preencher EXATAMENTE total_slots períodos (sem janelas
    # vazias dentro do expediente nem extrapolar a janela disponível).
    aulas_por_turma: dict[int, int] = {t.id: 0 for t in instance.turmas}
    for idx in assignments:
        a = by_aula[idx]
        aulas_por_turma[a.turma_id] = aulas_por_turma.get(a.turma_id, 0) + 1
    for turma in instance.turmas:
        qtd = aulas_por_turma.get(turma.id, 0)
        alvo = turma.total_slots
        if qtd != alvo:
            violacoes.append(
                f"HC7: turma {turma.id} com {qtd} aulas (esperado {alvo}). "
                "Currículo da turma deve totalizar exatamente sum(slots_por_dia) aulas."
            )

    return violacoes


def calcular_score(
    instance: ProblemInstance,
    assignments: dict[int, tuple[int, int]],
    professor_por_aula: dict[int, int] | None = None,
) -> tuple[float, dict[str, int]]:
    """Calcula a função de penalidade (Σ pesoᵢ × violaçõesᵢ).

    Retorna (score, breakdown) onde breakdown traz a contagem de violações por SC.
    """

    by_aula = {a.idx: a for a in instance.aulas}
    prof_map = professor_por_aula or {}

    def prof_de(idx: int) -> int | None:
        return prof_map.get(idx, by_aula[idx].professor_id)

    sc1 = _sc1_janelas_professor(instance, assignments, by_aula, prof_de)
    sc2 = _sc2_areas_consecutivas(instance, assignments, by_aula)
    sc3 = _sc3_blocos_teoricos(instance, assignments, by_aula)
    sc4 = _sc4_prof_turma_split(instance, assignments, by_aula, prof_de)

    score = PESO_SC1 * sc1 + PESO_SC2 * sc2 + PESO_SC3 * sc3 + PESO_SC4 * sc4
    return score, {"SC1": sc1, "SC2": sc2, "SC3": sc3, "SC4": sc4}


def _sc1_janelas_professor(
    instance: ProblemInstance,
    assignments: dict[int, tuple[int, int]],
    by_aula: dict,
    prof_de,
) -> int:
    """Conta janelas vazias entre primeira e última aula do professor em cada dia."""

    por_prof_dia: dict[tuple[int, int], list[int]] = {}
    for idx, (dia, slot) in assignments.items():
        prof = prof_de(idx)
        if prof is None:
            continue
        por_prof_dia.setdefault((prof, dia), []).append(slot)

    janelas = 0
    for slots in por_prof_dia.values():
        if len(slots) <= 1:
            continue
        slots_sorted = sorted(slots)
        intervalo = slots_sorted[-1] - slots_sorted[0] + 1
        janelas += intervalo - len(slots_sorted)
    return janelas


def _sc2_areas_consecutivas(
    instance: ProblemInstance,
    assignments: dict[int, tuple[int, int]],
    by_aula: dict,
) -> int:
    """Conta pares de slots consecutivos com disciplinas da mesma área para a mesma turma."""

    disc_by_id = {d.id: d for d in instance.disciplinas}
    grade_turma: dict[tuple[int, int], dict[int, int]] = {}
    for idx, (dia, slot) in assignments.items():
        a = by_aula[idx]
        grade_turma.setdefault((a.turma_id, dia), {})[slot] = a.disciplina_id

    pares = 0
    for slots in grade_turma.values():
        for s in range(SLOTS_DIA_MAX - 1):
            if s in slots and (s + 1) in slots:
                d1 = disc_by_id.get(slots[s])
                d2 = disc_by_id.get(slots[s + 1])
                if d1 and d2 and d1.area == d2.area and d1.id != d2.id:
                    pares += 1
    return pares


def _sc3_blocos_teoricos(
    instance: ProblemInstance,
    assignments: dict[int, tuple[int, int]],
    by_aula: dict,
) -> int:
    """Conta blocos de 3+ aulas teóricas consecutivas para a mesma turma."""

    disc_by_id = {d.id: d for d in instance.disciplinas}
    grade_turma: dict[tuple[int, int], dict[int, bool]] = {}
    for idx, (dia, slot) in assignments.items():
        a = by_aula[idx]
        disc = disc_by_id.get(a.disciplina_id)
        if disc is None:
            continue
        grade_turma.setdefault((a.turma_id, dia), {})[slot] = disc.eh_teorica

    blocos = 0
    for slots in grade_turma.values():
        run = 0
        for s in range(SLOTS_DIA_MAX):
            teorica = slots.get(s)
            if teorica is True:
                run += 1
                if run == 3:
                    blocos += 1
            else:
                run = 0
    return blocos


def _sc4_prof_turma_split(
    instance: ProblemInstance,
    assignments: dict[int, tuple[int, int]],
    by_aula: dict,
    prof_de,
) -> int:
    """Conta "splits" entre aulas do mesmo (professor, turma, dia).

    Para cada (professor, turma, dia) o ideal é todas as aulas serem contíguas
    (1 bloco). Cada bloco adicional (com algum slot vago entre eles) conta
    como um split — o que penaliza diretamente o caso "professor leciona
    duas vezes com a mesma turma em períodos separados".
    """

    grupos: dict[tuple[int, int, int], list[int]] = {}
    for idx, (dia, slot) in assignments.items():
        a = by_aula[idx]
        pid = prof_de(idx)
        if pid is None:
            continue
        grupos.setdefault((pid, a.turma_id, dia), []).append(slot)

    splits = 0
    for slots in grupos.values():
        if len(slots) <= 1:
            continue
        slots_sorted = sorted(slots)
        # nº de blocos = nº de transições "vazio → ocupado" no dia.
        blocos = 1
        for prev, cur in zip(slots_sorted, slots_sorted[1:]):
            if cur > prev + 1:
                blocos += 1
        splits += blocos - 1
    return splits


__all__ = [
    "DIAS",
    "SLOTS_DIA_MAX",
    "PESO_SC1",
    "PESO_SC2",
    "PESO_SC3",
    "PESO_SC4",
    "calcular_score",
    "violacoes_hard",
]
