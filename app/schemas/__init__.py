from app.schemas.disciplina import DisciplinaCreate, DisciplinaRead, DisciplinaUpdate
from app.schemas.grade import (
    AlocacaoRead,
    GradeDetail,
    GradeGenerateRequest,
    GradeGenerateResponse,
    GradeListItem,
    GradeStatusResponse,
)
from app.schemas.professor import (
    DisponibilidadeBulkUpdate,
    DisponibilidadeRead,
    ProfessorCreate,
    ProfessorRead,
    ProfessorUpdate,
)
from app.schemas.sala import SalaCreate, SalaRead, SalaUpdate
from app.schemas.turma import (
    TurmaCreate,
    TurmaCurriculoBulkUpdate,
    TurmaDisciplinaRead,
    TurmaRead,
    TurmaUpdate,
)

__all__ = [
    "DisciplinaCreate",
    "DisciplinaRead",
    "DisciplinaUpdate",
    "ProfessorCreate",
    "ProfessorRead",
    "ProfessorUpdate",
    "DisponibilidadeRead",
    "DisponibilidadeBulkUpdate",
    "TurmaCreate",
    "TurmaRead",
    "TurmaUpdate",
    "TurmaDisciplinaRead",
    "TurmaCurriculoBulkUpdate",
    "SalaCreate",
    "SalaRead",
    "SalaUpdate",
    "GradeGenerateRequest",
    "GradeGenerateResponse",
    "GradeStatusResponse",
    "GradeListItem",
    "GradeDetail",
    "AlocacaoRead",
]
