"""Popula o banco com um dataset realista para a EFA Francisco de Assis.

Cobertura:

- 6 turmas de Ensino Fundamental (manhã)
- 6 turmas de Ensino Médio (3 manhã + 3 tarde)
- 26 disciplinas separadas por ciclo, somando exatamente 30 aulas/sem por turma
  (HC7: nenhum horário pode ficar vazio na grade)
- 17 professores com atribuição balanceada
- 15 ambientes (12 salas comuns + 3 laboratórios)
- Indisponibilidades pontuais para realismo (sem inviabilizar)

Uso (dentro do container):

    docker compose run --rm app python -m app.seed
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.core.ensino import infer_disciplina_ensino, infer_turma_ensino
from app.models import (
    AlocacaoSlot,
    Disciplina,
    DisponibilidadeProfessor,
    GradeHoraria,
    Professor,
    ProfessorDisciplina,
    Sala,
    Turma,
    TurmaDisciplina,
)
from app.models.sala import SalaTipo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


# --- Disciplinas ---------------------------------------------------------- #
# (nome, area, carga_semanal, requer_lab, eh_teorica)
# Cada turma deve totalizar exatamente DIAS*SLOTS_DIA = 30 aulas/sem para que a
# grade não tenha horários vazios (HC7).
DISCIPLINAS: list[tuple[str, str, int, bool, bool]] = [
    # Ensino Fundamental — total carga = 30 aulas/sem
    ("Português EF",        "linguagens", 5, False, True),
    ("Matemática EF",       "exatas",     5, False, True),
    ("Ciências",            "biologicas", 3, True,  False),
    ("História EF",         "humanas",    2, False, True),
    ("Geografia EF",        "humanas",    2, False, True),
    ("Inglês EF",           "linguagens", 2, False, True),
    ("Artes EF",            "linguagens", 2, False, False),
    ("Ed. Física EF",       "geral",      2, False, False),
    ("Ensino Religioso",    "humanas",    1, False, True),
    ("Estudo Orientado",    "geral",      2, False, False),
    ("Tecnologia Digital",  "exatas",     2, False, False),
    ("Música",              "linguagens", 2, False, False),
    # Ensino Médio — total carga = 30 aulas/sem
    ("Português EM",        "linguagens", 4, False, True),
    ("Matemática EM",       "exatas",     4, False, True),
    ("Física",              "exatas",     3, True,  False),
    ("Química",             "exatas",     3, True,  False),
    ("Biologia",            "biologicas", 2, False, True),
    ("História EM",         "humanas",    2, False, True),
    ("Geografia EM",        "humanas",    2, False, True),
    ("Filosofia",           "humanas",    1, False, True),
    ("Sociologia",          "humanas",    1, False, True),
    ("Inglês EM",           "linguagens", 2, False, True),
    ("Ed. Física EM",       "geral",      2, False, False),
    ("Espanhol",            "linguagens", 2, False, True),
    ("Projeto de Vida",     "humanas",    1, False, False),
    ("Eletiva",             "geral",      1, False, False),
]


# --- Professores ---------------------------------------------------------- #
# (nome, email, [disciplinas que pode lecionar], [(dia, slot) indisponíveis])
PROFESSORES: list[tuple[str, str, list[str], list[tuple[int, int]]]] = [
    ("Ana Souza",        "ana@efa.example",      ["Português EF", "Português EM"],                  [(0, 0)]),
    ("Bruno Lima",       "bruno@efa.example",    ["Português EF", "Português EM"],                  [(4, 5)]),
    ("Carla Mendes",     "carla@efa.example",    ["Matemática EF", "Matemática EM"],                [(1, 0)]),
    ("Diego Rocha",      "diego@efa.example",    ["Matemática EF", "Matemática EM"],                [(3, 5)]),
    ("Eduarda Silva",    "eduarda@efa.example",  ["Ciências", "Biologia"],                          []),
    ("Fábio Castro",     "fabio@efa.example",    ["Biologia", "Filosofia"],                         [(2, 0)]),
    ("Gabriela Reis",    "gabi@efa.example",     ["Física"],                                        []),
    ("Henrique Alves",   "henrique@efa.example", ["Química"],                                       [(0, 5)]),
    ("Isabela Cardoso",  "isa@efa.example",      ["História EF", "História EM"],                    []),
    ("João Borges",      "joao@efa.example",     ["História EM", "Geografia EM"],                   [(4, 0)]),
    ("Karina Duarte",    "karina@efa.example",   ["Geografia EF", "Sociologia"],                    []),
    ("Lucas Faria",      "lucas@efa.example",    ["Inglês EF", "Inglês EM"],                        [(1, 5)]),
    ("Marina Galvão",    "marina@efa.example",   ["Artes EF", "Ensino Religioso"],                  []),
    ("Nelson Hoffmann",  "nelson@efa.example",   ["Ed. Física EF", "Ed. Física EM"],                []),
    ("Olga Werner",      "olga@efa.example",     ["Estudo Orientado", "Eletiva"],                   []),
    ("Paulo Gomes",      "paulo@efa.example",    ["Tecnologia Digital", "Projeto de Vida"],         []),
    ("Quitéria Almeida", "quiteria@efa.example", ["Música", "Espanhol"],                            []),
]


# --- Salas ---------------------------------------------------------------- #
SALAS: list[tuple[str, SalaTipo, int]] = [
    ("Sala 101", SalaTipo.SALA, 35),
    ("Sala 102", SalaTipo.SALA, 35),
    ("Sala 103", SalaTipo.SALA, 35),
    ("Sala 104", SalaTipo.SALA, 35),
    ("Sala 201", SalaTipo.SALA, 35),
    ("Sala 202", SalaTipo.SALA, 35),
    ("Sala 203", SalaTipo.SALA, 35),
    ("Sala 204", SalaTipo.SALA, 35),
    ("Sala 301", SalaTipo.SALA, 30),
    ("Sala 302", SalaTipo.SALA, 30),
    ("Sala 303", SalaTipo.SALA, 30),
    ("Sala 304", SalaTipo.SALA, 30),
    ("Lab. Ciências", SalaTipo.LAB, 28),
    ("Lab. Física",   SalaTipo.LAB, 24),
    ("Lab. Química",  SalaTipo.LAB, 24),
]


# --- Turmas --------------------------------------------------------------- #
EF_TURMAS = ["EF-6A", "EF-6B", "EF-7A", "EF-8A", "EF-9A", "EF-9B"]
EM_TURMAS_MANHA = ["EM-1M", "EM-2M", "EM-3M"]
EM_TURMAS_TARDE = ["EM-1T", "EM-2T", "EM-3T"]


# Atribuição de professor por (disciplina, turma).
# Cada lista tem 6 entradas alinhadas com a respectiva lista de turmas.
EF_ATRIBUICAO: dict[str, list[str]] = {
    "Português EF":       ["Ana Souza"] * 3 + ["Bruno Lima"] * 3,
    "Matemática EF":      ["Carla Mendes"] * 3 + ["Diego Rocha"] * 3,
    "Ciências":           ["Eduarda Silva"] * 6,
    "História EF":        ["Isabela Cardoso"] * 6,
    "Geografia EF":       ["Karina Duarte"] * 6,
    "Inglês EF":          ["Lucas Faria"] * 6,
    "Artes EF":           ["Marina Galvão"] * 6,
    "Ed. Física EF":      ["Nelson Hoffmann"] * 6,
    "Ensino Religioso":   ["Marina Galvão"] * 6,
    "Estudo Orientado":   ["Olga Werner"] * 6,
    "Tecnologia Digital": ["Paulo Gomes"] * 6,
    "Música":             ["Quitéria Almeida"] * 6,
}

EM_ATRIBUICAO: dict[str, list[str]] = {
    "Português EM":   ["Ana Souza"] * 3 + ["Bruno Lima"] * 3,
    "Matemática EM":  ["Carla Mendes"] * 3 + ["Diego Rocha"] * 3,
    "Física":         ["Gabriela Reis"] * 6,
    "Química":        ["Henrique Alves"] * 6,
    "Biologia":       ["Eduarda Silva"] * 3 + ["Fábio Castro"] * 3,
    "História EM":    ["Isabela Cardoso"] * 3 + ["João Borges"] * 3,
    "Geografia EM":   ["João Borges"] * 6,
    "Filosofia":      ["Fábio Castro"] * 6,
    "Sociologia":     ["Karina Duarte"] * 6,
    "Inglês EM":      ["Lucas Faria"] * 6,
    "Ed. Física EM":  ["Nelson Hoffmann"] * 6,
    "Espanhol":       ["Quitéria Almeida"] * 6,
    "Projeto de Vida":["Paulo Gomes"] * 6,
    "Eletiva":        ["Olga Werner"] * 6,
}


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
    await session.commit()


def _verifica_carga_professores() -> None:
    """Sanity check: imprime a carga semanal de cada professor."""

    cargas: dict[str, int] = {}
    cargas_disc = {nome: carga for nome, _, carga, _, _ in DISCIPLINAS}
    for atrib_set in (EF_ATRIBUICAO, EM_ATRIBUICAO):
        for disc, profs_list in atrib_set.items():
            carga = cargas_disc[disc]
            for prof in profs_list:
                cargas[prof] = cargas.get(prof, 0) + carga
    logger.info("Carga semanal por professor (limite teórico: 30):")
    for nome, _, _, _ in PROFESSORES:
        marker = "!" if cargas.get(nome, 0) > 28 else " "
        logger.info(
            "  %s %s: %d aulas/sem", marker, nome.ljust(22), cargas.get(nome, 0)
        )


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        logger.info("Limpando tabelas…")
        await reset_db(session)

        logger.info("Criando %d disciplinas…", len(DISCIPLINAS))
        disciplinas: dict[str, Disciplina] = {}
        for nome, area, carga, lab, teor in DISCIPLINAS:
            obj = Disciplina(
                nome=nome,
                ensino=infer_disciplina_ensino(nome, "ambos"),
                area=area,
                carga_semanal=carga,
                requer_lab=lab,
                eh_teorica=teor,
            )
            session.add(obj)
            disciplinas[nome] = obj
        await session.flush()

        logger.info("Criando %d salas (incluindo %d laboratórios)…",
                    len(SALAS), sum(1 for _, t, _ in SALAS if t == SalaTipo.LAB))
        for nome, tipo, cap in SALAS:
            session.add(Sala(nome=nome, tipo=tipo, capacidade=cap))

        logger.info("Criando %d professores…", len(PROFESSORES))
        professores: dict[str, Professor] = {}
        for nome, email, leciona, indisp in PROFESSORES:
            prof = Professor(nome=nome, email=email)
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
        # EF — todas no semestre "2026/1"
        for ident in EF_TURMAS:
            turma = Turma(
                identificador=ident,
                ensino=infer_turma_ensino(ident, "fundamental"),
                semestre="2026/1",
                qtd_alunos=30,
            )
            session.add(turma)
            await session.flush()
            idx = EF_TURMAS.index(ident)
            for disc_nome, lista_profs in EF_ATRIBUICAO.items():
                prof = professores[lista_profs[idx]]
                disc = disciplinas[disc_nome]
                session.add(
                    TurmaDisciplina(
                        turma_id=turma.id, disciplina_id=disc.id, professor_id=prof.id
                    )
                )

        # EM — manhã e tarde, todas no semestre "2026/1"
        em_all = EM_TURMAS_MANHA + EM_TURMAS_TARDE
        for ident in em_all:
            turma = Turma(
                identificador=ident,
                ensino=infer_turma_ensino(ident, "medio"),
                semestre="2026/1",
                qtd_alunos=32,
            )
            session.add(turma)
            await session.flush()
            idx = em_all.index(ident)
            for disc_nome, lista_profs in EM_ATRIBUICAO.items():
                prof = professores[lista_profs[idx]]
                disc = disciplinas[disc_nome]
                session.add(
                    TurmaDisciplina(
                        turma_id=turma.id, disciplina_id=disc.id, professor_id=prof.id
                    )
                )

        await session.commit()

        cargas_disc = {nome: carga for nome, _, carga, _, _ in DISCIPLINAS}
        carga_ef = sum(cargas_disc[d] for d in EF_ATRIBUICAO)
        carga_em = sum(cargas_disc[d] for d in EM_ATRIBUICAO)
        total_aulas = len(EF_TURMAS) * carga_ef + len(em_all) * carga_em

        logger.info("Seed concluído.")
        logger.info(
            "Resumo: %d disciplinas · %d professores · %d salas · %d turmas (%d EF + %d EM)",
            len(DISCIPLINAS),
            len(PROFESSORES),
            len(SALAS),
            len(EF_TURMAS) + len(em_all),
            len(EF_TURMAS),
            len(em_all),
        )
        logger.info(
            "Carga semanal por turma: EF=%d aulas, EM=%d aulas (esperado 30).",
            carga_ef,
            carga_em,
        )
        logger.info("Total de aulas/semana a alocar: %d", total_aulas)
        _verifica_carga_professores()
        logger.info(
            "\nAtenção: para 12 turmas, recomenda-se solver=cpsat com timeout >= 60 s."
        )


if __name__ == "__main__":
    asyncio.run(seed())
