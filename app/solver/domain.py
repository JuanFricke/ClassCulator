"""Estruturas in-memory consumidas pelos solvers (sem dependência de SQLAlchemy)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

DIAS = 5  # 0=segunda ... 4=sexta
SLOTS_DIA = 6  # 6 períodos por dia
QUARTA = 2  # índice da quarta-feira
HC4_MIN_AULAS_QUARTA = 3
HC6_MIN_AULAS_DIA = 1  # toda turma precisa ter ao menos 1 aula em cada dia
SLOTS_POR_TURMA = DIAS * SLOTS_DIA  # toda turma deve ocupar todos os 30 slots


class InstanceConfigurationError(ValueError):
    """Erro de configuração da instância (currículo / professores insuficientes).

    Levantado antes do solver rodar, para sinalizar que nenhuma grade viável
    pode existir com os dados atuais — distinto de uma falha de busca/timeout.
    """


@dataclass(frozen=True)
class ProfessorInfo:
    id: int
    nome: str


@dataclass(frozen=True)
class DisciplinaInfo:
    id: int
    nome: str
    area: str
    carga_semanal: int
    requer_lab: bool
    eh_teorica: bool


@dataclass(frozen=True)
class TurmaInfo:
    id: int
    identificador: str


@dataclass(frozen=True)
class SalaInfo:
    id: int
    nome: str
    eh_lab: bool


@dataclass(frozen=True)
class Aula:
    """Uma instância de aula a ser alocada (turma × disciplina × k-ésima ocorrência)."""

    idx: int
    turma_id: int
    disciplina_id: int
    professor_id: int
    k: int


@dataclass
class ProblemInstance:
    turmas: list[TurmaInfo]
    disciplinas: list[DisciplinaInfo]
    professores: list[ProfessorInfo]
    salas: list[SalaInfo]
    aulas: list[Aula]
    indisponiveis: dict[int, set[tuple[int, int]]] = field(default_factory=dict)

    def disciplina(self, did: int) -> DisciplinaInfo:
        return next(d for d in self.disciplinas if d.id == did)

    def aulas_por_turma(self, tid: int) -> list[Aula]:
        return [a for a in self.aulas if a.turma_id == tid]

    def aulas_por_professor(self, pid: int) -> list[Aula]:
        return [a for a in self.aulas if a.professor_id == pid]

    def professor_disponivel(self, pid: int, dia: int, slot: int) -> bool:
        return (dia, slot) not in self.indisponiveis.get(pid, set())


class SolverStatus(str, enum.Enum):
    OK = "ok"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class SolverResult:
    """Saída comum dos solvers."""

    status: SolverStatus
    assignments: dict[int, tuple[int, int]] = field(default_factory=dict)  # aula_idx -> (dia, slot)
    score: float = 0.0
    elapsed_s: float = 0.0
    log: str = ""
