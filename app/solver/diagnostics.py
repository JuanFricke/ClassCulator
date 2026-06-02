"""Diagnósticos de inviabilidade para enriquecer logs dos solvers."""

from __future__ import annotations

from app.solver.domain import DIAS, SLOTS_DIA_MAX, ProblemInstance

DIAS_LABELS = ["segunda", "terça", "quarta", "quinta", "sexta"]


def _candidatos_da_aula(aula) -> tuple[int, ...]:
    """Pool de professores elegíveis para a aula.

    Usa ``aula.candidatos`` (escolha automática) e, como fallback, o professor
    fixado em ``aula.professor_id`` (caminho clássico/fixado).
    """

    if aula.candidatos:
        return aula.candidatos
    if aula.professor_id is not None:
        return (aula.professor_id,)
    return ()


def necessary_condition_report(instance: ProblemInstance) -> str:
    """Retorna um relatório com violações de condições necessárias de viabilidade."""

    lines: list[str] = ["[diagnostico] análise automática de inviabilidade:"]

    # Demanda por professor distribuída uniformemente entre os candidatos de cada
    # aula (uma aula "sem preferência" reparte sua demanda entre os habilitados).
    carga_por_prof: dict[int, float] = {}
    profs_ativos: set[int] = set()
    for a in instance.aulas:
        candidatos = _candidatos_da_aula(a)
        if not candidatos:
            continue
        fracao = 1.0 / len(candidatos)
        for pid in candidatos:
            carga_por_prof[pid] = carga_por_prof.get(pid, 0.0) + fracao
            profs_ativos.add(pid)

    disponibilidade_total: dict[int, int] = {}
    indisponiveis = instance.indisponiveis

    prof_by_id = {p.id: p for p in instance.professores}
    for pid in profs_ativos:
        indisponiveis_prof = len(indisponiveis.get(pid, set()))
        disponibilidade_total[pid] = (DIAS * SLOTS_DIA_MAX) - indisponiveis_prof

    sobrecarga: list[str] = []
    for pid, carga in carga_por_prof.items():
        capacidade = disponibilidade_total.get(pid, DIAS * SLOTS_DIA_MAX)
        if carga > capacidade:
            nome = prof_by_id.get(pid).nome if pid in prof_by_id else f"id={pid}"
            sobrecarga.append(f"{nome}: carga≈{carga:.1f}, slots_disponiveis={capacidade}")
    if sobrecarga:
        lines.append(
            "[diagnostico] professores com carga acima da capacidade semanal: "
            + "; ".join(sobrecarga[:8])
        )

    # Demanda por (dia, slot) = quantidade de turmas que TÊM esse slot válido em
    # seu slots_por_dia. Slots fora do expediente de qualquer turma têm demanda 0.
    gargalos_slot: list[str] = []
    for dia in range(DIAS):
        for slot in range(SLOTS_DIA_MAX):
            demanda_por_slot = sum(
                1 for t in instance.turmas if slot < t.slots_por_dia[dia]
            )
            if demanda_por_slot == 0:
                continue
            capacidade_slot = sum(
                1 for pid in profs_ativos if (dia, slot) not in indisponiveis.get(pid, set())
            )
            if capacidade_slot < demanda_por_slot:
                gargalos_slot.append(
                    f"{DIAS_LABELS[dia]} slot {slot + 1}: capacidade={capacidade_slot}, demanda={demanda_por_slot}"
                )
    if gargalos_slot:
        lines.append(
            "[diagnostico] slots com capacidade docente abaixo da demanda de turmas: "
            + "; ".join(gargalos_slot[:10])
        )

    prof_sem_slot = []
    for pid in profs_ativos:
        if disponibilidade_total.get(pid, 0) <= 0:
            nome = prof_by_id.get(pid).nome if pid in prof_by_id else f"id={pid}"
            prof_sem_slot.append(nome)
    if prof_sem_slot:
        lines.append(
            "[diagnostico] professores sem nenhum slot disponível na semana: "
            + ", ".join(prof_sem_slot[:10])
        )

    if len(lines) == 1:
        lines.append(
            "[diagnostico] nenhuma causa necessária simples foi detectada; "
            "o conflito pode ser combinatório entre HC2/HC3/HC4/HC5/HC6/HC7."
        )

    lines.append(
        "[diagnostico] sugestões: reduzir indisponibilidades críticas, redistribuir "
        "disciplinas entre professores ou aumentar o conjunto de professores habilitados."
    )
    return "\n".join(lines)
