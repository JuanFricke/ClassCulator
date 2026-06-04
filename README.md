# ClassCulator

Sistema de Geração Automática de Grade Horária Escolar — implementação do relatório técnico
**EI 03 / Ciência da Computação / UNIJUÍ**.

A grade é gerada por um motor que pode operar em dois modos:

1. **CP-SAT (OR-Tools)** — solver de produção do Google.
2. **Clássico** — Backtracking + Forward Checking + heurística MRV → Hill Climbing (800 iterações).

A interface é uma MPA renderizada com **Jinja2 + Bulma**, e a comunicação assíncrona usa
**FastAPI BackgroundTasks** + **Fetch polling** (2 s).

## Stack

- Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic
- OR-Tools CP-SAT
- PostgreSQL 15
- Jinja2 + Bulma 1.0 + Fetch API
- Empacotamento com [`uv`](https://docs.astral.sh/uv/), execução com Docker Compose

## Quickstart

Pré-requisitos: Docker e Docker Compose.

```bash
git clone <repo> ClassCulator
cd ClassCulator
cp .env.example .env

docker compose up                                   # db + migrações + app (hot-reload)

# em outra aba (opcional, popula dados de exemplo)
docker compose run --rm app python -m app.seed
```

Abra <http://localhost:8000>.

## Comandos úteis

```bash
docker compose up                 # sobe tudo
docker compose down               # para tudo
docker compose down -v            # para tudo e apaga o volume do Postgres

docker compose run --rm app python -m app.seed
docker compose run --rm app alembic revision -m "msg" --autogenerate
docker compose run --rm app alembic upgrade head
docker compose run --rm app pytest

# uso local (opcional, sem Docker):
uv sync
uv run uvicorn app.main:app --reload
```

## Arquitetura

```
app/
├── main.py                # FastAPI + Jinja2 + montagem de routers
├── core/                  # config, database, deps
├── models/                # SQLAlchemy ORM
├── schemas/               # Pydantic v2 DTOs
├── api/                   # routers REST (JSON) sob /api/v1
├── web/                   # routers SSR (HTML)
├── services/              # orquestração (grade_service)
├── solver/                # domain, builder, cpsat, classic, runner
├── templates/             # Jinja2
└── static/                # CSS + JS
```

## Endpoints REST

| Método | Endpoint                          | Descrição                                |
| ------ | --------------------------------- | ---------------------------------------- |
| `*`    | `/api/v1/professores`             | CRUD de professores                      |
| `*`    | `/api/v1/professores/{id}/disponibilidade` | matriz dia × slot                |
| `*`    | `/api/v1/turmas`                  | CRUD de turmas + currículo               |
| `*`    | `/api/v1/disciplinas`             | CRUD de disciplinas                      |
| `*`    | `/api/v1/salas`                   | CRUD de salas/laboratórios               |
| `POST` | `/api/v1/grade/gerar`             | Enfileira execução do solver             |
| `GET`  | `/api/v1/grade/status/{id}`       | Status atual (poll a cada 2 s)           |
| `GET`  | `/api/v1/grade/{id}`              | Grade completa                            |

## Modelo do problema

Calendário: **5 dias úteis (segunda a sexta)**. Cada turma tem seu próprio
`slots_por_dia` (vetor de 5 inteiros entre 0 e `SLOTS_DIA_MAX = 15`); a carga
semanal alvo da turma é `sum(slots_por_dia)`. O dataset padrão (`app.seed`,
EFA Francisco de Assis) usa `[6,6,6,6,6] = 30` em todas as turmas — caso
retangular, ainda suportado pelo solver clássico. Datasets com janela
semanal irregular (ex.: `app.seed_alt`) devem ser resolvidos com o
**solver CP-SAT**; o solver clássico devolve erro amigável nesse caso.

### Hard constraints (HC)

- **HC1** — carga horária semanal exata por disciplina.
- **HC2** — exclusividade de turma.
- **HC3** — exclusividade de professor.
- **HC4** — cada turma tem **≥ min(3, slots_por_dia[quarta]) aulas na
  quarta-feira** (condicional ao próprio expediente da turma).
- **HC5** — slots indisponíveis do professor não podem receber alocação.
- **HC6** — toda turma tem **≥ 1 aula em cada dia útil com expediente**
  (dias com `slots_por_dia[d] = 0` ficam vazios por design).
- **HC7** — toda turma ocupa **exatamente `sum(slots_por_dia)` períodos**
  da semana (nenhum horário vazio dentro da janela e nenhuma sobra).
  Validação prévia: se o currículo somado de uma turma não totalizar
  `sum(slots_por_dia)`, o endpoint `POST /api/v1/grade/gerar` retorna
  **422** com a lista de turmas problemáticas, sem chegar a invocar o
  solver.

### Soft constraints (SC) — função de penalidade

| SC  | Descrição                                                                                            | Peso |
| --- | ---------------------------------------------------------------------------------------------------- | ---- |
| SC1 | janelas vazias entre aulas do mesmo professor no dia                                                 | 100  |
| SC2 | pares consecutivos de disciplinas da mesma área para a mesma turma                                   | 30   |
| SC3 | bloco de 3+ aulas teóricas consecutivas sem laboratório                                              | 50   |
| SC4 | splits (blocos não contíguos) entre aulas do mesmo `(professor, turma)` no dia                      | 200  |

A função objetivo é minimizar Σ pesoᵢ × violaçõesᵢ.
