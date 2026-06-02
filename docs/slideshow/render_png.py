#!/usr/bin/env python3
"""Render slideshow PNGs (1920x1080) from slide definitions."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = "#f5f7fb"
TITLE = "#1a1a2e"
TEXT = "#363636"
MUTED = "#5c6b7a"
OUT = Path(__file__).resolve().parent / "png"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
        "/usr/share/fonts/google-noto-sans/NotoSans-Regular.ttf",
        "/usr/share/fonts/dejavu-sans/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def new_slide() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def header(draw: ImageDraw.ImageDraw, title: str, subtitle: str | None = None) -> None:
    draw.text((W // 2, 80), title, fill=TITLE, font=font(56, True), anchor="mm")
    if subtitle:
        draw.text((W // 2, 150), subtitle, fill=MUTED, font=font(32), anchor="mm")


def box(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    label: str,
    fill: str,
    outline: str,
    sub: str | None = None,
) -> None:
    draw.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=fill, outline=outline, width=3)
    cy = y + h // 2 - (16 if sub else 0)
    draw.text((x + w // 2, cy), label, fill=TITLE, font=font(38, True), anchor="mm")
    if sub:
        draw.text((x + w // 2, cy + 44), sub, fill=TEXT, font=font(30), anchor="mm")


def slide_01() -> Image.Image:
    img, draw = new_slide()
    header(draw, "ClassCulator — Visão em camadas", "Geração automática de grade horária escolar")
    layers = [
        ("Apresentação — Jinja2 + Bulma + JavaScript (Fetch, polling 2s)", "#e8f4fd", "#3273dc"),
        ("API REST — FastAPI /api/v1 + Pydantic v2", "#fff4e6", "#ff9800"),
        ("Serviços — grade_service + BackgroundTasks", "#f3e8ff", "#9c27b0"),
        ("Solver — domain · builder · constraints · CP-SAT · clássico", "#e8f5e9", "#4caf50"),
        ("Persistência — SQLAlchemy 2.0 async + PostgreSQL 15 + Alembic", "#fce4ec", "#e91e63"),
        ("Infra — Docker Compose · uv · Uvicorn :8000", "#eceff1", "#607d8b"),
    ]
    y = 180
    for label, fill, outline in layers:
        box(draw, 120, y, 1680, 100, label, fill, outline)
        y += 130
    draw.text((W // 2, 1020), "Entrada: app/main.py — monta /static, api_router e web_router", fill=MUTED, font=font(20), anchor="mm")
    return img


def slide_02() -> Image.Image:
    img, draw = new_slide()
    header(draw, "Deploy — Docker Compose")
    box(draw, 200, 280, 420, 280, "PostgreSQL 15", "#336791", "#1e3a5f", "service: db · volume pgdata")
    box(draw, 750, 200, 420, 200, "migrate", "#ff9800", "#e65100", "alembic upgrade head")
    box(draw, 1300, 280, 420, 280, "app", "#3273dc", "#1a4a8a", "uvicorn :8000 · hot-reload")
    draw.line([(620, 420), (750, 300)], fill="#607d8b", width=3)
    draw.line([(1170, 300), (1300, 380)], fill="#607d8b", width=3)
    draw.rectangle([200, 680, 1720, 960], fill="#ffffff", outline="#dddddd", width=2)
    draw.text((960, 740), "Seeds de dados", fill=TITLE, font=font(26, True), anchor="mm")
    draw.text((960, 800), "python -m app.seed  →  EFA (5×6, clássico ou CP-SAT)", fill=TEXT, font=font(22), anchor="mm")
    draw.text((960, 850), "scripts/seed.sh alt  →  23 turmas, slots_por_dia variável", fill=TEXT, font=font(22), anchor="mm")
    draw.text((960, 920), "http://localhost:8000", fill=MUTED, font=font(20), anchor="mm")
    return img


def slide_03() -> Image.Image:
    img, draw = new_slide()
    header(draw, "Fluxo de geração da grade")
    steps = [
        (80, "UI"),
        (320, "POST /gerar"),
        (600, "build_instance"),
        (860, "pending"),
        (1100, "BackgroundTask"),
        (1360, "run_solver"),
        (1600, "AlocacaoSlot"),
    ]
    for x, label in steps:
        box(draw, x, 160, 200 if x < 1600 else 240, 80, label, "#e8f4fd", "#3273dc")
    draw.rectangle([200, 380, 1720, 700], fill="#ffffff", outline="#3273dc", width=2)
    draw.text((960, 440), "Polling (grade-poll.js)", fill=TITLE, font=font(28, True), anchor="mm")
    draw.text((960, 510), "GET /api/v1/grade/status/{id}  a cada 2 s", fill=TEXT, font=font(22), anchor="mm")
    draw.text((960, 570), "pending → running → completed | failed", fill=TEXT, font=font(22), anchor="mm")
    draw.text((960, 630), "Visualização em /grade/{id}", fill=TEXT, font=font(22), anchor="mm")
    box(draw, 200, 760, 720, 200, "CP-SAT (OR-Tools)", "#e8f5e9", "#4caf50", "slots irregulares · produção")
    box(draw, 1000, 760, 720, 200, "Clássico", "#fff4e6", "#ff9800", "5×6 retangular apenas")
    return img


def slide_04() -> Image.Image:
    img, draw = new_slide()
    header(draw, "Modelo de dados")
    entities: list[tuple] = [
        (120, 140, 280, 120, "Professor", "#e8f4fd", "#3273dc", None),
        (120, 320, 280, 100, "Disciplina", "#fff4e6", "#ff9800", None),
        (120, 480, 280, 120, "Turma", "#e8f5e9", "#4caf50", "slots_por_dia [5]"),
        (480, 380, 320, 100, "TurmaDisciplina", "#f3e8ff", "#9c27b0", "currículo"),
        (900, 200, 320, 100, "GradeHoraria", "#fce4ec", "#e91e63", None),
        (900, 360, 380, 120, "AlocacaoSlot", "#e8f4fd", "#3273dc", "dia · slot · sala"),
    ]
    for x, y, w, h, label, fill, outline, sub in entities:
        box(draw, x, y, w, h, label, fill, outline, sub)
    draw.text((960, 920), "uq (turma_id, disciplina_id) — uma disciplina por turma no currículo", fill=MUTED, font=font(22), anchor="mm")
    return img


def slide_05() -> Image.Image:
    img, draw = new_slide()
    header(draw, "Solver — constraints e pipeline")
    draw.rectangle([80, 130, 580, 510], fill="#ffffff", outline="#4caf50", width=3)
    draw.text((330, 180), "Hard (HC)", fill="#2e7d32", font=font(28, True), anchor="mm")
    hc = ["HC1 carga exata/disciplina", "HC2 1 aula/slot/turma", "HC3 professor exclusivo",
          "HC4 mín. aulas quarta", "HC5 disponibilidade", "HC6 ≥1 aula/dia", "HC7 sum(slots_por_dia)"]
    for i, line in enumerate(hc):
        draw.text((120, 230 + i * 40), line, fill=TEXT, font=font(20))
    draw.rectangle([620, 130, 1120, 510], fill="#ffffff", outline="#ff9800", width=3)
    draw.text((870, 180), "Soft (SC)", fill="#e65100", font=font(28, True), anchor="mm")
    sc = ["SC1 janelas prof (100)", "SC2 mesma área (30)", "SC3 3+ teóricas (50)", "SC4 splits (200)"]
    for i, line in enumerate(sc):
        draw.text((660, 240 + i * 50), line, fill=TEXT, font=font(22))
    draw.rectangle([1160, 130, 1840, 510], fill="#e8f4fd", outline="#3273dc", width=3)
    draw.text((1500, 180), "Pipeline", fill=TITLE, font=font(28, True), anchor="mm")
    pipe = ["1. build_instance(DB)", "2. ProblemInstance", "3. runner → cpsat|classic", "4. AlocacaoSlot"]
    for i, line in enumerate(pipe):
        draw.text((1200, 240 + i * 50), line, fill=TEXT, font=font(22))
    draw.text((960, 700), "EFA: [6,6,6,6,6]=30  ·  EM: [5,5,5,5,3]=23", fill=TEXT, font=font(24), anchor="mm")
    draw.text((960, 760), "Validação 422 se currículo ≠ sum(slots_por_dia)", fill=MUTED, font=font(22), anchor="mm")
    return img


def slide_06() -> Image.Image:
    img, draw = new_slide()
    header(draw, "Estrutura app/")
    draw.rectangle([200, 120, 1720, 1000], fill="#1e1e2e", outline="#3273dc", width=2)
    lines = [
        ("app/", "#82aaff", 26),
        ("  main.py          FastAPI + routers", "#c3e88d", 22),
        ("  core/            config · database · deps", "#ffcb6b", 22),
        ("  models/          ORM entities", "#ffcb6b", 22),
        ("  schemas/         Pydantic DTOs", "#ffcb6b", 22),
        ("  api/             REST /api/v1", "#ffcb6b", 22),
        ("  web/routes.py    SSR HTML", "#ffcb6b", 22),
        ("  services/        grade_service", "#ffcb6b", 22),
        ("  solver/          cpsat · classic · builder", "#f78c6c", 22),
        ("  templates/       Jinja2", "#ffcb6b", 22),
        ("  static/          css · js", "#ffcb6b", 22),
        ("  seed.py · seed_alt.py", "#c3e88d", 22),
        ("  alembic/         migrations", "#89ddff", 22),
    ]
    y = 180
    for text, color, size in lines:
        draw.text((240, y), text, fill=color, font=font(size))
        y += 62
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    slides = [
        ("01-visao-geral", slide_01),
        ("02-deploy-docker", slide_02),
        ("03-fluxo-geracao", slide_03),
        ("04-modelo-dados", slide_04),
        ("05-solver-constraints", slide_05),
        ("06-estrutura-pastas", slide_06),
    ]
    for name, fn in slides:
        path = OUT / f"{name}.png"
        fn().save(path, "PNG", optimize=True)
        print(f"Wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
