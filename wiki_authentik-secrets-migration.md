# Authentik as Secrets Backend

**Status:** ✅ Migrated (2026-05-04)  
**Previous:** Bitwarden  
**Tags:** `authentik`, `secrets`, `oidc`, `infrastructure`

---

## Overview

secrets_agent agora usa **Authentik** como backend primário, consolidando todas credenciais sob um único OIDC provider.

**Benefício:** Source of truth único; integração melhor com agentes autônomos.

---

## Arquitetura

```
┌─────────────────┐
│  Agentes        │
├─────────────────┤
│ nextcloud       │
│ wiki            │
│ trading         │
│ etc             │
└────────┬────────┘
         │
    ┌────v─────┐
    │ Authentik │  (192.168.15.200)
    │ OIDC      │
    │ OAuth2    │
    └────┬──────┘
         │
    ┌────v──────────┐
    │ Secrets Agent  │
    │ (cache layer)  │
    └────┬───────────┘
         │
    ┌────v──────┐
    │ PostgreSQL │  (DB do Authentik)
    └───────────┘
```

---

## OAuth2 Provider Creation

**Fix aplicado:** Payload estava faltando campos obrigatórios (2026-05-04)

### Correto
```json
{
  "name": "copilot-agent",
  "client_type": "confidential",
  "access_token_validity": 86400,
  "token_endpoint_auth_method": "client_secret_basic",
  "allowed_redirect_uris": [
    "http://localhost:8501/auth/callback",
    "https://api.rpa4all.com/auth/callback"
  ],
  "response_types": ["code", "token"],
  "grant_types": ["authorization_code", "refresh_token"],
  "skip_authorization": false,
  "include_claims_in_id_token": true
}
```

---

## secrets_agent Integration

### Autenticação
```bash
# Antes (Bitwarden)
curl -s -H "Auth-Token: $BW_TOKEN" https://bitwarden.com/api/accounts/profile

# Depois (Authentik)
curl -s -H "Authorization: Bearer $AUTHENTIK_TOKEN" \
  https://authentik.example.com/api/v3/credentials/
```

### Refresh Token
```python
# Authentik auto-refresh via OIDC Discovery
# secrets_agent monitora expiração e refresca transparentemente
response = client.refresh_token(
    refresh_token=stored_refresh,
    client_id="copilot-agent",
    client_secret=os.environ["AUTHENTIK_CLIENT_SECRET"]
)
```

---

## GitHub Actions Secrets Fix

**Problema:** `if: secrets.GITHUB_TOKEN` não funciona no workflow

```yaml
# ❌ Errado
jobs:
  deploy:
    if: secrets.GITHUB_TOKEN != ''
    steps:
      - run: echo "Deploy"

# ✅ Correto
env:
  DEPLOY_ENABLED: ${{ vars.DEPLOY_ENABLED }}

jobs:
  deploy:
    if: env.DEPLOY_ENABLED == 'true'
    steps:
      - run: echo "Deploy"
```

**Por quê:** GitHub Actions não permite referenciar `secrets.*` em `if` direto. Use `vars.*` ao invés (environment variables públicas).

---

## API Endpoints Utilizados

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/v3/credentials/` | GET | Listar credenciais |
| `/api/v3/credentials/{id}/` | GET | Obter credencial |
| `/token/introspect/` | POST | Validar token |
| `/token/revoke/` | POST | Revogar token |

---

## Monitoramento

### Prometheus Metrics
```
authentik_token_refresh_total{agent="nextcloud"}
authentik_token_validity_seconds{agent="..."}
authentik_credential_access_total{credential="db_password"}
authentik_secret_agent_cache_hits{...}
```

### Alertas
```yaml
- name: "Authentik Token Expiring"
  condition: "authentik_token_validity_seconds < 3600"
  severity: warning

- name: "Credential Access Denied"
  condition: "increase(authentik_credential_access_denied[1h]) > 10"
  severity: critical
```

---

## Migration Checklist

- [x] Criar OAuth2 provider em Authentik
- [x] Configurar secrets_agent para Authentik
- [x] Testar token refresh
- [x] Migrar nextcloud_agent
- [x] Migrar wiki_agent
- [x] Migrar trading_agent
- [x] Desabilitar Bitwarden integration
- [ ] Remover Bitwarden API key de todas secrets
- [ ] Validar em produção por 7 dias
- [ ] Desmantelar instância Bitwarden

---

## Troubleshooting

| Problema | Causa | Fix |
|----------|-------|-----|
| Token inválido | Expirado | Usar refresh_token |
| Credencial não encontrada | Path errado | Verificar `wikijs/api_key` path |
| OIDC discovery failed | Authentik down | Verificar health: `https://authentik/api/v3/health/` |
| Cache stale | TTL muito longo | Reduzir `CREDENTIAL_CACHE_TTL` |

---

## Próximos Passos

- [ ] Implementar audit logging de acesso a credenciais
- [ ] Criar alertas para padrões suspeitos de acesso
- [ ] Documentar Authentik disaster recovery procedure
- [ ] Testar revogação de token em cenário de compromisso

---

**Última atualização:** 2026-05-04  
**Mantido por:** Infrastructure, secrets_agent  
**Docs relacionadas:** Secrets Management, OIDC Integration
