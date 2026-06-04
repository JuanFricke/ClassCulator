# ClassCulator — Resumo da Arquitetura

Sistema de **geração automática de grade horária escolar** (EI 03 / Ciência da Computação / UNIJUÍ). O usuário cadastra turmas, professores, disciplinas e salas; o motor de otimização aloca cada aula em um slot `(dia, período)` respeitando restrições rígidas e minimizando penalidades de conforto.

---

## 1. Visão em camadas

| Camada | Responsabilidade | Tecnologias |
|--------|------------------|-------------|
| **Apresentação** | Páginas HTML (MPA), formulários, grade visual | Jinja2, Bulma 1.0, JavaScript (Fetch API) |
| **API REST** | CRUD e geração de grade (JSON) | FastAPI, Pydantic v2 |
| **Serviços** | Orquestração assíncrona da geração | `grade_service` + BackgroundTasks |
| **Domínio / Solver** | Modelo do problema, constraints, algoritmos | OR-Tools CP-SAT, backtracking + hill climbing |
| **Persistência** | Entidades escolares e grades geradas | SQLAlchemy 2.0 async, PostgreSQL 15, Alembic |
| **Infra** | Containers e migrações | Docker Compose, `uv` |

O ponto de entrada é `app/main.py`: monta estáticos, inclui `api_router` (`/api/v1`) e `web_router` (rotas SSR).

---

## 2. Deploy (Docker Compose)

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────────┐
│  PostgreSQL │ ◄── │   migrate    │     │  app (uvicorn :8000)    │
│  (db)       │     │  (alembic)   │     │  FastAPI + hot-reload   │
└─────────────┘     └──────────────┘     └─────────────────────────┘
       ▲                                          │
       └──────────────────────────────────────────┘
```

- **`db`**: Postgres 15 com volume `pgdata`.
- **`migrate`**: roda `alembic upgrade head` uma vez antes da app subir.
- **`app`**: Uvicorn com reload em `/app/app`.

Seeds: `python -m app.seed` (EFA, grade 5×6) ou `scripts/seed.sh alt` (23 turmas reais, `slots_por_dia` variável).

---

## 3. Fluxo de geração da grade

1. **UI** (`/grade/nova`) — usuário escolhe semestre, solver (`cpsat` ou `classic`), timeout (slider).
2. **`POST /api/v1/grade/gerar`** — valida configuração via `build_instance()`; se inválido → **422** imediato.
3. **`create_pending_grade()`** — insere `GradeHoraria` com `status=pending`.
4. **`BackgroundTasks`** — chama `run_grade_generation()` em sessão própria.
5. **`build_instance()`** — lê DB → monta `ProblemInstance` (turmas, professores, currículo, disponibilidade).
6. **`run_solver()`** — despacha para `solve_cpsat` ou `solve_classic`.
7. **Persistência** — grava `AlocacaoSlot` (turma, disciplina, professor, sala, dia, slot).
8. **Polling** — `grade-poll.js` consulta `GET /api/v1/grade/status/{id}` a cada 2 s até `completed` ou `failed`.
9. **Visualização** — `/grade/{id}` com grade por turma; células “off” quando `slot >= slots_por_dia[dia]`.

---

## 4. Modelo de dados (principal)

- **Professor** ↔ **Disciplina** (`ProfessorDisciplina`) — o que cada um pode lecionar.
- **DisponibilidadeProfessor** — matriz 5 dias × até 15 slots (`SLOTS_DIA_MAX`).
- **Turma** — `identificador`, `ensino`, **`slots_por_dia`** (JSONB, 5 inteiros); carga alvo = `sum(slots_por_dia)`.
- **TurmaDisciplina** — currículo: `(turma, disciplina, professor)`; **único** por `(turma_id, disciplina_id)`.
- **Disciplina** — `carga_semanal`, `ensino`, área (para SC2/SC3).
- **Sala** — tipo (sala comum / laboratório).
- **GradeHoraria** + **AlocacaoSlot** — versão da grade e alocações resultantes.

---

## 5. Modelo do problema (solver)

**Calendário:** 5 dias úteis; cada turma define quantos períodos tem por dia (`slots_por_dia`). Grade retangular padrão: `[6,6,6,6,6]` = 30 períodos/semana.

### Hard constraints (obrigatórias)

| ID | Regra |
|----|--------|
| HC1 | Carga semanal exata por disciplina no currículo |
| HC2 | Uma aula por slot por turma |
| HC3 | Professor não pode estar em duas turmas no mesmo slot |
| HC4 | Mínimo de aulas na quarta (até o expediente da turma) |
| HC5 | Respeitar disponibilidade do professor |
| HC6 | Pelo menos 1 aula em cada dia com expediente |
| HC7 | Turma ocupa exatamente `sum(slots_por_dia)` slots válidos |

### Soft constraints (penalidades)

| ID | Objetivo | Peso |
|----|----------|------|
| SC1 | Reduzir janelas vazias do professor | 100 |
| SC2 | Disciplinas da mesma área consecutivas | 30 |
| SC3 | Evitar 3+ teóricas seguidas sem lab | 50 |
| SC4 | Evitar splits professor–turma no dia | 200 |

### Solvers

| Solver | Uso |
|--------|-----|
| **CP-SAT** | Produção; suporta `slots_por_dia` irregular (dataset `seed_alt`) |
| **Clássico** | Backtracking + MRV + hill climbing; só turmas retangulares 5×6 |

---

## 6. Estrutura de pastas (`app/`)

```
main.py           → FastAPI + routers
core/             → config, database async, deps (SessionDep)
models/           → ORM (Turma, Professor, Grade, …)
schemas/          → DTOs Pydantic
api/              → REST /api/v1/*
web/routes.py     → SSR HTML + lógica de formulários
services/         → grade_service (async generation)
solver/
  domain.py       → ProblemInstance, TurmaInfo, constantes
  builder.py      → DB → instância + validações
  constraints.py  → HC/SC compartilhados
  cpsat.py        → modelo OR-Tools
  classic.py      → backtracking + hill climbing
  runner.py       → despacho cpsat | classic
templates/        → Jinja2
static/           → CSS + JS (turma-form, grade-poll, …)
seed.py / seed_alt.py
```

---

## 7. Interface web (destaques)

- **Turmas** — editor de `slots_por_dia` com total/semana em tempo real; currículo por nível (EI, EF I, EF II, EM); sem auto-preencher todas as disciplinas.
- **Professores** — grade de disponibilidade 5×15.
- **Grade** — geração com polling; detalhe com orientação H/V e células desligadas fora do expediente da turma.

---

## Imagens para slideshow

Na pasta `docs/slideshow/png/`:

| Arquivo | Conteúdo |
|---------|----------|
| `01-visao-geral.png` | Camadas do sistema |
| `02-deploy-docker.png` | Serviços Docker Compose |
| `03-fluxo-geracao.png` | Sequência POST → solver → poll |
| `04-modelo-dados.png` | Entidades e relacionamentos |
| `05-solver-constraints.png` | Pipeline do solver + HC/SC |
| `06-estrutura-pastas.png` | Mapa `app/` |

Os SVGs editáveis estão em `docs/slideshow/svg/`.
