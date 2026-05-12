from app.models.disciplina import Disciplina
from app.models.grade import AlocacaoSlot, GradeHoraria, GradeStatus
from app.models.professor import DisponibilidadeProfessor, Professor, ProfessorDisciplina
from app.models.sala import Sala, SalaTipo
from app.models.turma import Turma, TurmaDisciplina

__all__ = [
    "Professor",
    "ProfessorDisciplina",
    "DisponibilidadeProfessor",
    "Disciplina",
    "Turma",
    "TurmaDisciplina",
    "Sala",
    "SalaTipo",
    "GradeHoraria",
    "GradeStatus",
    "AlocacaoSlot",
]
