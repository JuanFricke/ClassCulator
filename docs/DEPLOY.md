# Deploy em produção (Hostinger VPS)

Guia para publicar o ClassCulator em um VPS Hostinger Ubuntu 24.04 **sem SSH**, usando a API Hostinger (Docker Projects + DNS + Firewall).

Domínio de referência: `https://classculator.sampletester.xyz`

## Pré-requisitos

- VPS Hostinger ativo com Docker Projects habilitado
- Domínio `sampletester.xyz` com DNS gerenciável na Hostinger
- Repositório publicado na `master` do GitHub (`JuanFricke/ClassCulator`)
- Token da API Hostinger (**nunca commitar** — use variável de ambiente)

### Segurança do token

1. Gere o token em **hPanel → API**.
2. Se o token foi exposto, **revogue e crie outro** antes do deploy.
3. Configure no Cursor MCP ou exporte localmente:

```bash
export HOSTINGER_API_TOKEN="seu-token-aqui"
```

## Arquivos de produção

| Arquivo | Função |
|---------|--------|
| [`docker-compose.yml`](../docker-compose.yml) | Stack prod (Hostinger usa este arquivo ao clonar o repo) |
| [`docker-compose.prod.yaml`](../docker-compose.prod.yaml) | Cópia de referência do stack prod |
| [`docker-compose.dev.yml`](../docker-compose.dev.yml) | Stack local com hot-reload |
| [`deploy/Caddyfile`](../deploy/Caddyfile) | HTTPS Let's Encrypt |
| [`.env.production.example`](../.env.production.example) | Template de variáveis |

Diferenças em relação ao dev (`docker-compose.dev.yml`):

- Sem bind mount `.:/app` e sem `--reload`
- Postgres **não** exposto publicamente
- `APP_ENV=prod` (cookies seguros HTTPS)
- Caddy na frente (portas 80/443)

## Variáveis obrigatórias no Docker Project

Passe via campo `environment` em `VPS_createNewProjectV1`:

```env
APP_ENV=prod
ACME_EMAIL=admin@sampletester.xyz
SECRET_KEY=<gerar com secrets.token_urlsafe(32)>
EMPRESA_NOME=Administração
EMPRESA_EMAIL=empresa@sampletester.xyz
EMPRESA_SENHA=<senha forte>
POSTGRES_USER=classculator
POSTGRES_PASSWORD=<senha forte>
POSTGRES_DB=classculator
DATABASE_URL=postgresql+asyncpg://classculator:<POSTGRES_PASSWORD>@db:5432/classculator
SYNC_DATABASE_URL=postgresql+psycopg://classculator:<POSTGRES_PASSWORD>@db:5432/classculator
```

Gerar segredos:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Passo 1 — Descobrir o VPS

```bash
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/vps/v1/virtual-machines
```

Anote `id` (virtualMachineId) e o IP público.

## Passo 2 — DNS

Crie registro **A** `classculator` → IP do VPS na zona `sampletester.xyz`.

Via API (ajuste `domain` e zone conforme resposta da API DNS):

```bash
# Listar zonas DNS
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/dns/v1/zones
```

Aguarde propagação (5–15 min) antes de subir o Caddy (Let's Encrypt exige DNS resolvendo).

## Passo 3 — Firewall

Permitir apenas:

- TCP 22 (manutenção Hostinger)
- TCP 80, 443 (HTTP/HTTPS)

Bloquear acesso público a 5432 (Postgres) e 8000 (app direta).

Use `VPS_createNewFirewallV1`, `VPS_createFirewallRuleV1` e `VPS_activateFirewallV1` via MCP ou API.

## Passo 4 — Deploy do Docker Project

```bash
curl -s -X POST \
  -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://developers.hostinger.com/api/vps/v1/virtual-machines/{VM_ID}/docker" \
  -d '{
    "project_name": "classculator",
    "content": "https://raw.githubusercontent.com/JuanFricke/ClassCulator/master/docker-compose.prod.yaml",
    "environment": {
      "APP_ENV": "prod",
      "SECRET_KEY": "...",
      "POSTGRES_PASSWORD": "...",
      "DATABASE_URL": "postgresql+asyncpg://classculator:...@db:5432/classculator",
      "SYNC_DATABASE_URL": "postgresql+psycopg://classculator:...@db:5432/classculator",
      "EMPRESA_EMAIL": "empresa@sampletester.xyz",
      "EMPRESA_SENHA": "...",
      "EMPRESA_NOME": "Administração",
      "ACME_EMAIL": "admin@sampletester.xyz"
    }
  }'
```

## Passo 5 — Verificação

```bash
# Logs do projeto
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  "https://developers.hostinger.com/api/vps/v1/virtual-machines/{VM_ID}/docker/classculator/logs"

# Health
curl -s https://classculator.sampletester.xyz/health
```

Login empresa: `/login` com `EMPRESA_EMAIL` / `EMPRESA_SENHA`.

## Atualizar após mudanças no código

1. Push na `master`
2. Chame `VPS_updateProjectV1` no projeto `classculator`

## Seed de dados (opcional)

**Atenção:** `app.seed` **apaga** dados existentes antes de repopular.

Sem SSH, use o **terminal do browser** no hPanel do VPS:

```bash
docker compose -p classculator run --rm app python -m app.seed
```

Ou opere apenas com a conta empresa criada pela migration (sem dataset EFA demo).

## Cursor MCP (opcional)

```json
{
  "mcpServers": {
    "hostinger-vps": {
      "command": "npx",
      "args": ["hostinger-api-mcp@latest"],
      "env": {
        "API_TOKEN": "<token via env, nunca no repo>"
      }
    }
  }
}
```

Ferramentas úteis: `VPS_getVirtualMachinesV1`, `VPS_createNewProjectV1`, `VPS_getProjectLogsV1`, `DNS_*`.

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| Certificado TLS falha | DNS ainda não propagou | Aguardar; conferir registro A |
| Migrate failed | DB credentials erradas | Revisar `DATABASE_URL` / `POSTGRES_PASSWORD` |
| 502 no Caddy | App não subiu | Ver logs do container `app` |
| Login não persiste | `APP_ENV` ≠ `prod` ou HTTP | Usar HTTPS; `APP_ENV=prod` |
