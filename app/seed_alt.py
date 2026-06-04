"""Dataset alternativo de testes — escola real com 23 turmas (EI/AI/AF/EM).

Cobertura:

- 14 turmas de Educação Infantil e Anos Iniciais (modelo "regente integrado"):
    * A11, A21, A31, A41 (Educação Infantil) — slots_por_dia = [5,5,5,5,0] = 20
    * B11..B52 (Anos Iniciais — EF I)        — slots_por_dia = [5,5,5,5,5] = 25
- 6 turmas de Anos Finais (EF II), C61..C91 — slots_por_dia = [6,6,6,6,4] = 28
- 3 turmas de Ensino Médio, 211/221/231     — slots_por_dia = [6,6,6,6,4] = 28

⚠️ Este dataset usa `slots_por_dia` IRREGULAR (cada turma com sua própria janela
semanal). Gere a grade com **solver=cpsat**; o solver clássico devolve erro
amigável porque ainda assume grade retangular 5×6.

Onde o dataset-fonte não traz cargas explícitas (toda a Educação Infantil/
Anos Iniciais/Anos Finais), os currículos são inferências razoáveis seguindo
BNCC e estão marcados com `# inferido`.

Uso (dentro do container):

    docker compose run --rm app python -m app.seed_alt
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.ensino import infer_disciplina_ensino
from app.core.security import hash_senha
from app.models import (
    PAPEL_EMPRESA,
    AlocacaoSlot,
    AnoLetivo,
    ConviteProfessor,
    Disciplina,
    DisponibilidadeProfessor,
    GradeHoraria,
    Professor,
    ProfessorDisciplina,
    Sala,
    Turma,
    TurmaDisciplina,
    Usuario,
)
from app.models.sala import SalaTipo
from app.solver.domain import DIAS, SLOTS_DIA_MAX

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


# --- Disciplinas ---------------------------------------------------------- #
# (nome, area, carga_semanal, requer_lab, eh_teorica)
#
# Disciplinas são separadas por nível quando a carga difere (BNCC) ou quando o
# corpo docente é distinto. Cada turma totaliza exatamente sum(slots_por_dia)
# aulas/semana (HC7).
DISCIPLINAS: list[tuple[str, str, int, bool, bool]] = [
    # --- Educação Infantil (carga total: 20) ----------------------- #
    ("Práticas Pedagógicas Integradas EI", "geral",      14, False, False),
    ("Arte EI",                            "linguagens",  1, False, False),
    ("Inglês EI",                          "linguagens",  1, False, True),
    ("Ed. Física EI",                      "geral",       2, False, False),
    ("Música EI",                          "linguagens",  2, False, False),
    # --- Anos Iniciais EF I (carga total: 25) ---------------------- #
    ("Português EF I",                     "linguagens",  6, False, True),
    ("Matemática EF I",                    "exatas",      5, False, True),
    ("Ciências EF I",                      "biologicas",  3, False, False),
    ("História EF I",                      "humanas",     2, False, True),
    ("Geografia EF I",                     "humanas",     2, False, True),
    ("Arte EF I",                          "linguagens",  1, False, False),
    ("Inglês EF I",                        "linguagens",  2, False, True),
    ("Ed. Física EF I",                    "geral",       2, False, False),
    ("Música EF I",                        "linguagens",  1, False, False),
    ("Computação EF I",                    "exatas",      1, False, False),
    # --- Anos Finais EF II (carga total: 28) ----------------------- #
    ("Português EF II",                    "linguagens",  5, False, True),
    ("Matemática EF II",                   "exatas",      5, False, True),
    ("Ciências EF II",                     "biologicas",  4, True,  False),
    ("História EF II",                     "humanas",     3, False, True),
    ("Geografia EF II",                    "humanas",     3, False, True),
    ("Inglês EF II",                       "linguagens",  2, False, True),
    ("Arte EF II",                         "linguagens",  2, False, False),
    ("Ed. Física EF II",                   "geral",       2, False, False),
    ("Filosofia EF II",                    "humanas",     1, False, True),
    ("Sociologia EF II",                   "humanas",     1, False, True),
    # --- Ensino Médio (carga total: 28) ---------------------------- #
    ("Português EM",                       "linguagens",  4, False, True),
    ("Matemática EM",                      "exatas",      4, False, True),
    ("Biologia",                           "biologicas",  3, False, False),
    ("Física",                             "exatas",      3, True,  False),
    ("Química",                            "exatas",      3, True,  False),
    ("História EM",                        "humanas",     2, False, True),
    ("Geografia EM",                       "humanas",     2, False, True),
    ("Filosofia EM",                       "humanas",     1, False, True),
    ("Sociologia EM",                      "humanas",     1, False, True),
    ("Redação",                            "linguagens",  2, False, True),
    ("Literatura",                         "linguagens",  1, False, True),
    ("Inglês EM",                          "linguagens",  1, False, True),
    ("Ed. Física EM",                      "geral",       1, False, False),
]


# --- Professores ---------------------------------------------------------- #
# (nome, email, [disciplinas que pode lecionar], [(dia, slot) indisponíveis])
#
# Dedup: mesmo primeiro nome com a mesma disciplina = mesma pessoa
# (Rosana faz Arte tanto em EM quanto em EI; Carlos faz Inglês em todos os
# níveis; Tati faz EDF em todos os níveis). Quando há homonímia entre papéis
# diferentes, distinguimos com sufixo entre parênteses no nome.
PROFESSORES: list[tuple[str, str, list[str], list[tuple[int, int]]]] = [
    # --- Especialistas EM/Anos Finais (subject-based) ------------- #
    ("Rosana",   "rosana@escola.example", [
        "Português EM", "Literatura", "Arte EF II", "Arte EF I", "Arte EI",
    ], []),
    ("Luane",    "luane@escola.example", [
        "Português EM", "Literatura", "Português EF II",
    ], []),
    ("Gabriela", "gabriela@escola.example", [
        "Redação", "Português EM", "Português EF II",
    ], []),
    ("Patrícia", "patricia@escola.example", [
        "História EM", "História EF II",
    ], []),
    ("Magnus",   "magnus@escola.example", [
        "Geografia EM", "Geografia EF II",
    ], []),
    # inferido: o dataset-fonte não traz quem leciona Filosofia/Sociologia em
    # AF; adicionamos um(a) especialista para evitar sobrecarregar Patrícia/
    # Magnus acima da capacidade semanal das turmas AF/EM (28 slots).
    ("Karen (Humanas)", "karen.humanas@escola.example", [
        "Filosofia EM", "Filosofia EF II",
        "Sociologia EM", "Sociologia EF II",
    ], []),
    ("Jader",    "jader@escola.example", [
        "Química", "Ciências EF II",
    ], []),
    ("Elis",     "elis@escola.example", [
        "Ciências EF II", "Ciências EF I",
    ], []),
    ("Murilo",   "murilo@escola.example", ["Biologia"], []),
    ("Alan",     "alan@escola.example", [
        "Matemática EM", "Matemática EF II",
    ], []),
    ("Carla",    "carla@escola.example", [
        "Matemática EM", "Matemática EF II", "Matemática EF I",
    ], []),
    ("Juliana (Física)", "juliana.fisica@escola.example", ["Física"], []),
    ("Carlos",   "carlos@escola.example", [
        "Inglês EM", "Inglês EF II", "Inglês EF I", "Inglês EI",
    ], []),
    ("Janaina",  "janaina@escola.example", [
        "Arte EF II", "Arte EF I",
    ], []),
    ("Silvana",  "silvana@escola.example", [
        "Ed. Física EM", "Ed. Física EF II", "Ed. Física EF I",
    ], []),
    ("Tatiana",  "tatiana@escola.example", [
        "Ed. Física EM", "Ed. Física EF II", "Ed. Física EF I",
    ], []),
    ("Tati",     "tati@escola.example", [
        "Ed. Física EM", "Ed. Física EF I", "Ed. Física EI",
    ], []),
    ("Ieda",     "ieda@escola.example", ["Computação EF I"], []),
    # --- Especialistas Educação Infantil/Anos Iniciais ------------ #
    ("Helena",   "helena@escola.example", [
        "Música EF I", "Música EI",
    ], []),
    ("Vivi",     "vivi@escola.example", [
        "Arte EF I", "Arte EI",
    ], []),
    ("Kemily",   "kemily@escola.example", [
        "Inglês EF I", "Inglês EI",
    ], []),
    ("William",  "william@escola.example", [
        "Ed. Física EF I", "Ed. Física EI",
    ], []),
    # --- Regentes Educação Infantil (A-classes) ------------------- #
    # Cada regente cobre integralmente a "Práticas Pedagógicas Integradas EI".
    ("Liege",                "liege@escola.example",     ["Práticas Pedagógicas Integradas EI"], []),
    ("Agnes",                "agnes@escola.example",     ["Práticas Pedagógicas Integradas EI"], []),
    ("Sônia (Anos Iniciais A)", "sonia.a@escola.example", ["Práticas Pedagógicas Integradas EI"], []),
    ("Cristiane",            "cristiane@escola.example", ["Práticas Pedagógicas Integradas EI"], []),
    # --- Regentes Anos Iniciais (B-classes) ----------------------- #
    # Cada regente cobre Português/Matemática/Ciências/História/Geografia EF I
    # da sua turma.
    ("Mª Estela",            "estela@escola.example",    [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Greise",               "greise@escola.example",    [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Sirlei",               "sirlei@escola.example",    [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Talita",               "talita@escola.example",    [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Deisi",                "deisi@escola.example",     [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Juliana (Anos Iniciais)", "juliana.ai@escola.example", [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Magda",                "magda@escola.example",     [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Raquel",               "raquel@escola.example",    [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Adriana",              "adriana@escola.example",   [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
    ("Sônia (Anos Iniciais B)", "sonia.b@escola.example", [
        "Português EF I", "Matemática EF I", "Ciências EF I",
        "História EF I", "Geografia EF I",
    ], []),
]


# --- Salas ---------------------------------------------------------------- #
SALAS: list[tuple[str, SalaTipo, int]] = [
    # Salas comuns (capacidade típica)
    ("Sala A1", SalaTipo.SALA, 25),
    ("Sala A2", SalaTipo.SALA, 25),
    ("Sala A3", SalaTipo.SALA, 25),
    ("Sala A4", SalaTipo.SALA, 25),
    ("Sala B1", SalaTipo.SALA, 30),
    ("Sala B2", SalaTipo.SALA, 30),
    ("Sala B3", SalaTipo.SALA, 30),
    ("Sala B4", SalaTipo.SALA, 30),
    ("Sala B5", SalaTipo.SALA, 30),
    ("Sala C1", SalaTipo.SALA, 32),
    ("Sala C2", SalaTipo.SALA, 32),
    ("Sala C3", SalaTipo.SALA, 32),
    ("Sala C4", SalaTipo.SALA, 32),
    ("Sala C5", SalaTipo.SALA, 32),
    ("Sala C6", SalaTipo.SALA, 32),
    ("Sala 21", SalaTipo.SALA, 32),
    ("Sala 22", SalaTipo.SALA, 32),
    ("Sala 23", SalaTipo.SALA, 32),
    # Laboratórios
    ("Lab. Ciências", SalaTipo.LAB, 28),
    ("Lab. Física",   SalaTipo.LAB, 24),
    ("Lab. Química",  SalaTipo.LAB, 24),
]


# --- Turmas --------------------------------------------------------------- #
# Cada turma vem acompanhada do seu slots_por_dia (segunda..sexta).
EI_TURMAS: list[tuple[str, list[int]]] = [
    ("A11", [5, 5, 5, 5, 0]),
    ("A21", [5, 5, 5, 5, 0]),
    ("A31", [5, 5, 5, 5, 0]),
    ("A41", [5, 5, 5, 5, 0]),
]

AI_TURMAS: list[tuple[str, list[int]]] = [
    ("B11", [5, 5, 5, 5, 5]),
    ("B12", [5, 5, 5, 5, 5]),
    ("B21", [5, 5, 5, 5, 5]),
    ("B22", [5, 5, 5, 5, 5]),
    ("B31", [5, 5, 5, 5, 5]),
    ("B32", [5, 5, 5, 5, 5]),
    ("B41", [5, 5, 5, 5, 5]),
    ("B42", [5, 5, 5, 5, 5]),
    ("B51", [5, 5, 5, 5, 5]),
    ("B52", [5, 5, 5, 5, 5]),
]

AF_TURMAS: list[tuple[str, list[int]]] = [
    ("C61", [6, 6, 6, 6, 4]),
    ("C62", [6, 6, 6, 6, 4]),
    ("C71", [6, 6, 6, 6, 4]),
    ("C81", [6, 6, 6, 6, 4]),
    ("C82", [6, 6, 6, 6, 4]),
    ("C91", [6, 6, 6, 6, 4]),
]

EM_TURMAS: list[tuple[str, list[int]]] = [
    ("211", [6, 6, 6, 6, 4]),
    ("221", [6, 6, 6, 6, 4]),
    ("231", [6, 6, 6, 6, 4]),
]


# --- Atribuições de professor por (disciplina, turma) --------------------- #
# Cada lista tem N entradas alinhadas com a respectiva lista de turmas.

# Regentes EI/AI: vêm do dataset (coluna "Main Teacher").
EI_REGENTES = ["Liege", "Agnes", "Sônia (Anos Iniciais A)", "Cristiane"]
AI_REGENTES = [
    "Mª Estela", "Greise",
    "Sirlei", "Talita",
    "Deisi", "Juliana (Anos Iniciais)",
    "Magda", "Raquel",
    "Adriana", "Sônia (Anos Iniciais B)",
]

EI_ATRIBUICAO: dict[str, list[str]] = {
    "Práticas Pedagógicas Integradas EI": EI_REGENTES,
    # inferido: especialistas distribuídos por dataset (Early Education).
    "Arte EI":         ["Vivi", "Rosana", "Vivi", "Rosana"],
    "Inglês EI":       ["Carlos", "Kemily", "Carlos", "Kemily"],
    "Ed. Física EI":   ["William", "Tati", "William", "Tati"],
    "Música EI":       ["Helena", "Helena", "Helena", "Helena"],
}

AI_ATRIBUICAO: dict[str, list[str]] = {
    # Núcleo integrado pelos regentes.
    "Português EF I":  AI_REGENTES,
    "Matemática EF I": AI_REGENTES,
    "Ciências EF I":   AI_REGENTES,
    "História EF I":   AI_REGENTES,
    "Geografia EF I":  AI_REGENTES,
    # Especialistas — distribuídos ciclicamente.
    "Arte EF I":       ["Vivi", "Janaina", "Vivi", "Janaina", "Vivi",
                        "Janaina", "Vivi", "Janaina", "Vivi", "Janaina"],
    "Inglês EF I":     ["Carlos", "Kemily", "Carlos", "Kemily", "Carlos",
                        "Kemily", "Carlos", "Kemily", "Carlos", "Kemily"],
    "Ed. Física EF I": ["Silvana", "William", "Silvana", "Tatiana", "Silvana",
                        "Tati", "William", "Tatiana", "Silvana", "Tati"],
    "Música EF I":     ["Helena"] * 10,
    "Computação EF I": ["Ieda"] * 10,
}

# Anos Finais (subject-based) — cada disciplina tem uma lista de 6 professores
# (um por turma), respeitando habilitações declaradas.
AF_ATRIBUICAO: dict[str, list[str]] = {
    "Português EF II":  ["Luane", "Luane", "Luane", "Gabriela", "Gabriela", "Gabriela"],
    "Matemática EF II": ["Alan", "Alan", "Alan", "Carla", "Carla", "Carla"],
    "Ciências EF II":   ["Elis", "Jader", "Elis", "Jader", "Elis", "Jader"],
    "História EF II":   ["Patrícia"] * 6,
    "Geografia EF II":  ["Magnus"] * 6,
    "Inglês EF II":     ["Carlos"] * 6,
    "Arte EF II":       ["Janaina", "Rosana", "Janaina", "Rosana", "Janaina", "Rosana"],
    "Ed. Física EF II": ["Silvana", "Tatiana", "Silvana", "Tatiana", "Silvana", "Tatiana"],
    "Filosofia EF II":  ["Karen (Humanas)"] * 6,
    "Sociologia EF II": ["Karen (Humanas)"] * 6,
}

# Ensino Médio.
EM_ATRIBUICAO: dict[str, list[str]] = {
    "Português EM":  ["Rosana", "Luane", "Gabriela"],
    "Matemática EM": ["Alan", "Carla", "Alan"],
    "Biologia":      ["Murilo"] * 3,
    "Física":        ["Juliana (Física)"] * 3,
    "Química":       ["Jader"] * 3,
    "História EM":   ["Patrícia"] * 3,
    "Geografia EM":  ["Magnus"] * 3,
    "Filosofia EM":  ["Karen (Humanas)"] * 3,
    "Sociologia EM": ["Karen (Humanas)"] * 3,
    "Redação":       ["Gabriela"] * 3,
    "Literatura":    ["Rosana", "Luane", "Rosana"],
    "Inglês EM":     ["Carlos"] * 3,
    "Ed. Física EM": ["Tati", "Silvana", "Tatiana"],
}


# Professor fixo (manual) × automático (None = "sem preferência").
# Para exercitar a escolha automática do professor pelo CP-SAT, a MAIORIA dos
# itens de currículo é cadastrada com ``professor_id=None`` (o solver escolhe o
# melhor professor habilitado, ciente de conflitos de horário). Mantemos um
# subconjunto de disciplinas "especialistas" com professor FIXADO, como exemplo
# de atribuição manual quando necessário. As atribuições nominais abaixo (e em
# ``_validar_dataset``) continuam servindo de fonte para fixar esses itens e
# para o sanity check de carga; o None é aplicado apenas na criação do
# ``TurmaDisciplina``.
DISCIPLINAS_PROFESSOR_FIXO: frozenset[str] = frozenset(
    {
        "Física",          # laboratório dedicado / professor(a) único(a) habilitado(a)
        "Química",
        "Biologia",
        "Computação EF I",
        "Música EI",
        "Música EF I",
    }
)


ANO_SEED = 2026


async def reset_db(session) -> None:
    await session.execute(delete(AlocacaoSlot))
    await session.execute(delete(GradeHoraria))
    await session.execute(delete(TurmaDisciplina))
    await session.execute(delete(DisponibilidadeProfessor))
    await session.execute(delete(ProfessorDisciplina))
    await session.execute(delete(Turma))
    await session.execute(delete(Disciplina))
    await session.execute(delete(Professor))
    await session.execute(delete(Sala))
    await session.execute(delete(ConviteProfessor))
    await session.execute(delete(AnoLetivo))
    await session.commit()


async def _garantir_usuario_empresa(session) -> None:
    email = settings.EMPRESA_EMAIL.strip().lower()
    existente = (
        await session.execute(select(Usuario).where(Usuario.email == email))
    ).scalar_one_or_none()
    if existente is None:
        session.add(
            Usuario(
                nome=settings.EMPRESA_NOME,
                email=email,
                senha_hash=hash_senha(settings.EMPRESA_SENHA),
                papel=PAPEL_EMPRESA,
                ativo=True,
            )
        )
        await session.commit()
        logger.info("Usuário empresa criado: %s", email)


def _ensino_para_disciplina(nome: str) -> str:
    """Decide o `ensino` de uma disciplina (`fundamental`, `medio` ou `ambos`).

    Estende o ``infer_disciplina_ensino`` para também reconhecer o sufixo
    `EI` (Educação Infantil), tratado como `fundamental` para fins de filtro
    na UI/curriculum.
    """

    inferred = infer_disciplina_ensino(nome, "ambos")
    if inferred != "ambos":
        return inferred
    return "fundamental" if " EI" in f" {nome} " else "ambos"


def _ensino_para_turma(identificador: str) -> str:
    """EM (2xx) → medio; demais (A*, B*, C*) → fundamental."""

    return "medio" if identificador and identificador[0].isdigit() else "fundamental"


def _qtd_alunos(identificador: str) -> int:
    """Tamanho típico da turma para fins do seed."""

    if identificador.startswith("A"):
        return 20
    if identificador.startswith("B"):
        return 25
    if identificador.startswith("C"):
        return 30
    return 32


def _validar_dataset() -> None:
    """Sanity checks antes de gravar nada no banco."""

    nomes_disc = {d[0] for d in DISCIPLINAS}
    cargas_disc = {nome: carga for nome, _, carga, _, _ in DISCIPLINAS}
    nomes_profs = {p[0] for p in PROFESSORES}

    # Habilitações dos professores → todas as disciplinas devem existir.
    for nome_prof, _, leciona, _ in PROFESSORES:
        for d in leciona:
            if d not in nomes_disc:
                raise RuntimeError(
                    f"Professor '{nome_prof}' habilitado para disciplina inexistente: '{d}'."
                )

    grupos: list[tuple[str, list[tuple[str, list[int]]], dict[str, list[str]]]] = [
        ("EI", EI_TURMAS, EI_ATRIBUICAO),
        ("AI", AI_TURMAS, AI_ATRIBUICAO),
        ("AF", AF_TURMAS, AF_ATRIBUICAO),
        ("EM", EM_TURMAS, EM_ATRIBUICAO),
    ]

    cargas_por_prof: dict[str, int] = {nome: 0 for nome in nomes_profs}
    habilita_de = {nome: set(leciona) for nome, _, leciona, _ in PROFESSORES}

    for rotulo, turmas, atrib in grupos:
        if not turmas:
            continue
        carga_total = sum(cargas_disc[d] for d in atrib)
        alvos = [sum(spd) for _, spd in turmas]
        if any(c != carga_total for c in alvos):
            raise RuntimeError(
                f"Grupo {rotulo}: carga somada do currículo ({carga_total}) não bate "
                f"com sum(slots_por_dia) de cada turma ({alvos})."
            )
        for spd in [s for _, s in turmas]:
            if len(spd) != DIAS:
                raise RuntimeError(
                    f"Grupo {rotulo}: slots_por_dia {spd} não tem {DIAS} valores."
                )
            if any(s < 0 or s > SLOTS_DIA_MAX for s in spd):
                raise RuntimeError(
                    f"Grupo {rotulo}: slots_por_dia {spd} fora do intervalo "
                    f"[0, {SLOTS_DIA_MAX}]."
                )
        for disc, profs in atrib.items():
            if disc not in nomes_disc:
                raise RuntimeError(
                    f"Grupo {rotulo}: disciplina '{disc}' ausente em DISCIPLINAS."
                )
            if len(profs) != len(turmas):
                raise RuntimeError(
                    f"Grupo {rotulo}, disciplina '{disc}': {len(profs)} entradas "
                    f"de professor, esperado {len(turmas)} (uma por turma)."
                )
            carga = cargas_disc[disc]
            for prof in profs:
                if prof not in nomes_profs:
                    raise RuntimeError(
                        f"Grupo {rotulo}, disciplina '{disc}': professor '{prof}' "
                        "não consta em PROFESSORES."
                    )
                if disc not in habilita_de[prof]:
                    raise RuntimeError(
                        f"Professor '{prof}' não está habilitado para '{disc}' "
                        "(adicione a disciplina ao 'leciona' do professor)."
                    )
                cargas_por_prof[prof] += carga

    capacidade_max = DIAS * SLOTS_DIA_MAX
    sobrecarga = [
        (nome, carga) for nome, carga in cargas_por_prof.items() if carga > capacidade_max
    ]
    if sobrecarga:
        detalhes = ", ".join(f"{n}={c}" for n, c in sobrecarga)
        raise RuntimeError(
            f"Professor(es) com carga > {capacidade_max} aulas/sem (excede capacidade "
            f"teórica DIAS×SLOTS_DIA_MAX): {detalhes}. Redistribua o currículo."
        )


def _verifica_carga_professores() -> None:
    """Log informativo: carga semanal por professor."""

    cargas: dict[str, int] = {}
    cargas_disc = {nome: carga for nome, _, carga, _, _ in DISCIPLINAS}
    for turmas, atrib in (
        (EI_TURMAS, EI_ATRIBUICAO),
        (AI_TURMAS, AI_ATRIBUICAO),
        (AF_TURMAS, AF_ATRIBUICAO),
        (EM_TURMAS, EM_ATRIBUICAO),
    ):
        if not turmas:
            continue
        for disc, profs_list in atrib.items():
            carga = cargas_disc[disc]
            for prof in profs_list:
                cargas[prof] = cargas.get(prof, 0) + carga
    logger.info(
        "Carga semanal por professor (limite teórico: %d):", DIAS * SLOTS_DIA_MAX
    )
    for nome, _, _, _ in PROFESSORES:
        carga = cargas.get(nome, 0)
        marker = "!" if carga > DIAS * SLOTS_DIA_MAX - 2 else " "
        logger.info("  %s %s: %d aulas/sem", marker, nome.ljust(28), carga)


async def seed() -> None:
    _validar_dataset()

    async with AsyncSessionLocal() as session:
        logger.info("Limpando tabelas…")
        await reset_db(session)

        await _garantir_usuario_empresa(session)

        logger.info("Criando ano letivo %d…", ANO_SEED)
        ano = AnoLetivo(ano=ANO_SEED)
        session.add(ano)
        await session.flush()
        ano_id = ano.id

        logger.info("Criando %d disciplinas…", len(DISCIPLINAS))
        disciplinas: dict[str, Disciplina] = {}
        for nome, area, carga, lab, teor in DISCIPLINAS:
            obj = Disciplina(
                ano_letivo_id=ano_id,
                nome=nome,
                ensino=_ensino_para_disciplina(nome),
                area=area,
                carga_semanal=carga,
                requer_lab=lab,
                eh_teorica=teor,
            )
            session.add(obj)
            disciplinas[nome] = obj
        await session.flush()

        logger.info(
            "Criando %d salas (incluindo %d laboratórios)…",
            len(SALAS),
            sum(1 for _, t, _ in SALAS if t == SalaTipo.LAB),
        )
        for nome, tipo, cap in SALAS:
            session.add(Sala(ano_letivo_id=ano_id, nome=nome, tipo=tipo, capacidade=cap))

        logger.info("Criando %d professores…", len(PROFESSORES))
        professores: dict[str, Professor] = {}
        for nome, email, leciona, indisp in PROFESSORES:
            prof = Professor(ano_letivo_id=ano_id, nome=nome, email=email)
            session.add(prof)
            await session.flush()
            for disc_nome in leciona:
                session.add(
                    ProfessorDisciplina(
                        professor_id=prof.id,
                        disciplina_id=disciplinas[disc_nome].id,
                    )
                )
            for dia, slot in indisp:
                session.add(
                    DisponibilidadeProfessor(
                        professor_id=prof.id, dia=dia, slot=slot, disponivel=False
                    )
                )
            professores[nome] = prof

        logger.info("Criando turmas + currículo…")
        for rotulo, turmas, atrib in (
            ("EI", EI_TURMAS, EI_ATRIBUICAO),
            ("AI", AI_TURMAS, AI_ATRIBUICAO),
            ("AF", AF_TURMAS, AF_ATRIBUICAO),
            ("EM", EM_TURMAS, EM_ATRIBUICAO),
        ):
            for idx, (ident, spd) in enumerate(turmas):
                turma = Turma(
                    ano_letivo_id=ano_id,
                    identificador=ident,
                    ensino=_ensino_para_turma(ident),
                    qtd_alunos=_qtd_alunos(ident),
                    slots_por_dia=list(spd),
                )
                session.add(turma)
                await session.flush()
                for disc_nome, lista_profs in atrib.items():
                    prof = professores[lista_profs[idx]]
                    disc = disciplinas[disc_nome]
                    # None = automático (sem preferência): o CP-SAT escolhe o
                    # professor habilitado ideal. Só os especialistas listados
                    # em DISCIPLINAS_PROFESSOR_FIXO permanecem fixados (manual).
                    professor_id = (
                        prof.id if disc_nome in DISCIPLINAS_PROFESSOR_FIXO else None
                    )
                    session.add(
                        TurmaDisciplina(
                            turma_id=turma.id,
                            disciplina_id=disc.id,
                            professor_id=professor_id,
                        )
                    )
            logger.info("  %s: %d turma(s) criadas.", rotulo, len(turmas))

        await session.commit()

        n_turmas = (
            len(EI_TURMAS) + len(AI_TURMAS) + len(AF_TURMAS) + len(EM_TURMAS)
        )
        cargas_disc = {nome: carga for nome, _, carga, _, _ in DISCIPLINAS}
        total_aulas = sum(
            sum(cargas_disc[d] for d in atrib) * len(turmas)
            for turmas, atrib in (
                (EI_TURMAS, EI_ATRIBUICAO),
                (AI_TURMAS, AI_ATRIBUICAO),
                (AF_TURMAS, AF_ATRIBUICAO),
                (EM_TURMAS, EM_ATRIBUICAO),
            )
        )

        logger.info("Seed alternativo concluído.")
        logger.info(
            "Resumo: %d disciplinas · %d professores · %d salas · %d turmas "
            "(EI=%d, AI=%d, AF=%d, EM=%d).",
            len(DISCIPLINAS),
            len(PROFESSORES),
            len(SALAS),
            n_turmas,
            len(EI_TURMAS),
            len(AI_TURMAS),
            len(AF_TURMAS),
            len(EM_TURMAS),
        )
        logger.info(
            "Cargas por nível (aulas/sem por turma): EI=20, AI=25, AF=28, EM=28."
        )
        logger.info("Total de aulas/semana a alocar: %d", total_aulas)
        _verifica_carga_professores()
        logger.info(
            "\nAtenção: este dataset usa slots_por_dia IRREGULAR. "
            "Gere a grade com solver='cpsat' (timeout >= 90s). "
            "O solver clássico retornará erro amigável."
        )


if __name__ == "__main__":
    asyncio.run(seed())
