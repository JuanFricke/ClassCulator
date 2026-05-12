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

Calendário fixo: **5 dias × 6 slots = 30 períodos**.

### Hard constraints (HC)

- **HC1** — carga horária semanal exata por disciplina.
- **HC2** — exclusividade de turma.
- **HC3** — exclusividade de professor.
- **HC4** — cada turma tem **≥ 3 aulas na quarta-feira**.
- **HC5** — slots indisponíveis do professor não podem receber alocação.
- **HC6** — toda turma tem **≥ 1 aula em cada dia** (sem dias vazios).
- **HC7** — toda turma ocupa **todos os 30 períodos** da semana (nenhum horário vazio).
  Validação prévia: se o currículo somado não totalizar 30 aulas/sem, o
  endpoint `POST /api/v1/grade/gerar` retorna **422** com a lista de turmas
  problemáticas, sem chegar a invocar o solver.

### Soft constraints (SC) — função de penalidade

| SC  | Descrição                                                                                            | Peso |
| --- | ---------------------------------------------------------------------------------------------------- | ---- |
| SC1 | janelas vazias entre aulas do mesmo professor no dia                                                 | 100  |
| SC2 | pares consecutivos de disciplinas da mesma área para a mesma turma                                   | 30   |
| SC3 | bloco de 3+ aulas teóricas consecutivas sem laboratório                                              | 50   |
| SC4 | splits (blocos não contíguos) entre aulas do mesmo `(professor, turma)` no dia                      | 200  |

A função objetivo é minimizar Σ pesoᵢ × violaçõesᵢ.
