from __future__ import annotations

import re


def infer_turma_ensino(identificador: str, fallback: str = "fundamental") -> str:
    nome = (identificador or "").strip().upper()
    if nome.startswith("EF"):
        return "fundamental"
    if nome.startswith("EM"):
        return "medio"
    return fallback


def infer_disciplina_ensino(nome: str, fallback: str = "ambos") -> str:
    texto = (nome or "").strip().upper()
    if re.search(r"\bEF\b", texto):
        return "fundamental"
    if re.search(r"\bEM\b", texto):
        return "medio"
    return fallback


def ensino_compativel(ensino_turma: str, ensino_disciplina: str) -> bool:
    if ensino_turma == "ambos" or ensino_disciplina == "ambos":
        return True
    return ensino_turma == ensino_disciplina
