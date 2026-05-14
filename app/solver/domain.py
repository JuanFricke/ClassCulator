"""Estruturas in-memory consumidas pelos solvers (sem dependência de SQLAlchemy)."""

from __future__ import annotations

import enum
from collections.abc import Iterator
from dataclasses import dataclass, field

DIAS = 5  # 0=segunda ... 4=sexta
SLOTS_DIA_LEGACY = 6  # tamanho retangular usado pelo dataset EFA e pelo solver clássico
SLOTS_DIA_MAX = 8  # limite superior para alocação de variáveis CP-SAT e para o grid da UI
SLOTS_DIA = SLOTS_DIA_LEGACY  # alias de compat: usado pelo solver clássico e diagnósticos
QUARTA = 2  # índice da quarta-feira
HC4_MIN_AULAS_QUARTA = 3
HC6_MIN_AULAS_DIA = 1  # toda turma precisa ter ao menos 1 aula em cada dia
SLOTS_POR_TURMA = DIAS * SLOTS_DIA_LEGACY  # carga semanal alvo no caso retangular (30)
SLOTS_POR_DIA_DEFAULT: tuple[int, ...] = (SLOTS_DIA_LEGACY,) * DIAS


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
    slots_por_dia: tuple[int, ...] = SLOTS_POR_DIA_DEFAULT

    @property
    def total_slots(self) -> int:
        return sum(self.slots_por_dia)

    @property
    def is_retangular(self) -> bool:
        """True quando a turma usa a grade clássica 5 × SLOTS_DIA_LEGACY."""

        return tuple(self.slots_por_dia) == SLOTS_POR_DIA_DEFAULT

    def slots_validos(self) -> Iterator[tuple[int, int]]:
        for d, n in enumerate(self.slots_por_dia):
            for s in range(n):
                yield d, s

    def slot_valido(self, dia: int, slot: int) -> bool:
        if not (0 <= dia < len(self.slots_por_dia)):
            return False
        return 0 <= slot < self.slots_por_dia[dia]


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
    warnings: list[str] = field(default_factory=list)

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
