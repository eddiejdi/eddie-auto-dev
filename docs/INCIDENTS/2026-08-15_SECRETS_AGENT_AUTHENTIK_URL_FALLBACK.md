# Trading Agent — Fallback de Credenciais (AUTHENTIK_URL) — 2026-08-15

## Resumo

O `crypto-agent` perdeu acesso às credenciais KuCoin via Secrets Agent e
começou a fazer fallback para variáveis de ambiente. O alerta reportou:
`Agent: unknown, Pair: ?, Profile: ?, Unit: crypto-agent, Origem: env`.

Causa raiz: `AUTHENTIK_URL` no service file do Secrets Agent apontava para
a URL externa (`https://auth.rpa4all.com`) em vez da interna
(`http://192.168.15.2:9000`), tornando o backend inacessível do NAS.

## Linha do tempo

| Hora (BRT) | Evento |
|---|---|
| ~22:00 | Alerta de fallback de credenciais recebido |
| 22:03 | Investigação iniciada — Secrets Agent online mas `backend_status: unavailable` |
| 22:04 | Causa raiz identificada: `AUTHENTIK_URL` externo no service file |
| 22:05 | Intent declarado para correção (risk: medium) |
| 22:05 | Aprovado via Telegram |
| 22:06 | Drop-in override criado: `/etc/systemd/system/secrets_agent.service.d/authentik-url.conf` |
| 22:06 | Secrets Agent reiniciado — `backend_status: available` |
| 22:07 | Crypto-agent reiniciado — credenciais carregadas via `agent-secrets:kucoin/sub-btcagressive` |
| 22:09 | Commit `7999ff59` pushed + deploy no NAS |

## Causa raiz

### Arquivo com problema

**`tools/secrets_agent/secrets_agent.service:20`**
```
# ANTES (errado)
Environment=AUTHENTIK_URL=https://auth.rpa4all.com

# DEPOIS (correto)
Environment=AUTHENTIK_URL=http://192.168.15.2:9000
```

### Por que falhou

1. O Authentik core roda internamente na porta 9000 (`http://192.168.15.2:9000`)
2. A URL externa `https://auth.rpa4all.com` passa por DNS → Cloudflare → reverse proxy
3. Do NAS, essa rota externa pode falhar (DNS, TLS, proxy timeout)
4. O probe de conectividade (`/api/v3/core/tokens/`) falha → `_available = False`
5. `secrets_list` retorna only `local_vault` (funciona)
6. `secrets_get` tenta Authentik → falha → local_vault → 404 (secret não está no local_vault)
7. `crypto-agent` não obtém KuCoin credentials → fallback para env vars

### Cadeia de resolução de credenciais

```
crypto-agent
  → secrets_helper.get_kucoin_credentials_with_source()
    → Para cada nome em ("kucoin/homelab", "authentik/kucoin/homelab", ...):
      → get_secret(nome, "api_key")
        → _try_env_var()           — converte kucoin/homelab → KUCOIN_HOMELAB_API_KEY
        → _try_secrets_agent_http() — GET /secrets/local/kucoin%2Fhomelab?field=api_key
        → _try_authentik_http()     — API Authentik direta
        → _try_vault_import()       — Bitwarden/GPG
      → get_secret(nome, "api_secret")
      → get_secret(nome, "passphrase")
    → Se todos falham → fallback env: KUCOIN_API_KEY / KUCOIN_API_SECRET / KUCOIN_API_PASSPHRASE
```

## Correções aplicadas

### NAS (produção)

1. **Drop-in override** (persiste entre updates):
   ```bash
   /etc/systemd/system/secrets_agent.service.d/authentik-url.conf
   [Service]
   Environment=AUTHENTIK_URL=http://192.168.15.2:9000
   ```

2. **Service file** atualizado via deploy

3. **Backend status**: `unavailable` → `available`

### Repo (commit `7999ff59`)

| Arquivo | Mudança |
|---|---|
| `tools/secrets_agent/secrets_agent.service:20` | `AUTHENTIK_URL` → `http://192.168.15.2:9000` |
| `tools/secrets_agent/secrets_agent.py:91` | Default fallback → `http://192.168.15.2:9000` |
| `scripts/homelab_mcp_server.py:246` | `secrets_get` aceita param `field` (default: `password`) |

### Bug adicional corrigido

O MCP tool `secrets_get` usava `field=password` por padrão, mas secrets KuCoin
usam campos `api_key`, `api_secret`, `passphrase`. Isso causava 404 mesmo com
backend disponível. Corrigido para aceitar param `field` opcional.

## Verificação pós-fix

```
secrets_agent health: backend_status=available ✅
crypto-agent@BTC_USDT_aggressive: agent-secrets:kucoin/sub-btcagressive ✅
Crypto-agent logs: credenciais carregadas, trading loop ativo ✅
```

## Ações preventivas

1. **drop-in override** (`authentik-url.conf`) persiste entre atualizações do service file
2. **Default no código** (`secrets_agent.py`) agora aponta para URL interna
3. **MCP tool** aceita `field` parameter — evita 404 para secrets com campos não-padrão
4. **Monitoramento**: verificar `backend_status` no health check periodicamente
