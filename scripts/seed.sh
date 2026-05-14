#!/usr/bin/env bash
# Gerencia o seed do banco de dados do ClassCulator.
#
# Escolhe um entre os datasets disponíveis e executa o módulo Python
# correspondente. Por padrão usa `docker compose run --rm app`, mas
# também aceita execução local via `uv run` (--local) ou um runner
# customizado via $SEED_RUNNER.
#
# Exemplos:
#
#     scripts/seed.sh                 # interativo (lista as opções)
#     scripts/seed.sh efa             # dataset EFA Francisco de Assis
#     scripts/seed.sh alt             # dataset alternativo
#     scripts/seed.sh alt --local     # roda com `uv run` em vez do docker
#     SEED_RUNNER="python" scripts/seed.sh efa

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." &>/dev/null && pwd)"

usage() {
    cat <<'EOF'
Uso: scripts/seed.sh [DATASET] [--local|--docker] [-h|--help]

Datasets disponíveis:
  efa, default, 1   -> app.seed       (EFA Francisco de Assis)
  alt, novo, 2      -> app.seed_alt   (dataset alternativo)

Modos de execução (padrão: docker):
  --docker          docker compose run --rm app python -m <modulo>
  --local           uv run python -m <modulo>   (usa o venv local)

Variáveis de ambiente:
  SEED_RUNNER       runner customizado, ex.: "python", "poetry run python".
                    Quando definido, ignora --docker/--local.

Sem argumentos, o script pergunta interativamente qual dataset usar.
EOF
}

dataset=""
mode="docker"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help|help)
            usage
            exit 0
            ;;
        --docker)
            mode="docker"
            shift
            ;;
        --local)
            mode="local"
            shift
            ;;
        efa|default|1|alt|novo|2)
            if [[ -n "$dataset" ]]; then
                echo "Erro: dataset informado mais de uma vez ($dataset, $1)." >&2
                exit 2
            fi
            dataset="$1"
            shift
            ;;
        *)
            echo "Erro: argumento desconhecido '$1'." >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$dataset" ]]; then
    if [[ ! -t 0 ]]; then
        echo "Erro: nenhum dataset informado e stdin não é interativo." >&2
        usage >&2
        exit 2
    fi
    echo "Escolha o dataset para popular o banco:"
    echo "  1) efa  -> app.seed       (EFA Francisco de Assis, padrão)"
    echo "  2) alt  -> app.seed_alt   (dataset alternativo)"
    read -r -p "Opção [efa]: " resp
    dataset="${resp:-efa}"
fi

case "$dataset" in
    efa|default|1)
        module="app.seed"
        label="EFA Francisco de Assis (app.seed)"
        ;;
    alt|novo|2)
        module="app.seed_alt"
        label="Alternativo (app.seed_alt)"
        ;;
    *)
        echo "Erro: dataset desconhecido '$dataset'." >&2
        usage >&2
        exit 2
        ;;
esac

cd -- "$PROJECT_ROOT"

if [[ -n "${SEED_RUNNER:-}" ]]; then
    # shellcheck disable=SC2206
    cmd=(${SEED_RUNNER} -m "$module")
elif [[ "$mode" == "local" ]]; then
    if ! command -v uv >/dev/null 2>&1; then
        echo "Erro: 'uv' não encontrado no PATH (necessário para --local)." >&2
        exit 127
    fi
    cmd=(uv run python -m "$module")
else
    if ! command -v docker >/dev/null 2>&1; then
        echo "Erro: 'docker' não encontrado no PATH." >&2
        echo "Use --local para rodar via 'uv run' fora do container." >&2
        exit 127
    fi
    cmd=(docker compose run --rm app python -m "$module")
fi

echo ">> Seed: $label"
echo ">> $ ${cmd[*]}"
exec "${cmd[@]}"
