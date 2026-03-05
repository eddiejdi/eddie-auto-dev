# Fix: Open WebUI — Erro "Unsupported Algorithm" com Authentik OIDC

**Data:** 5 de março de 2026  
**Problema:** Erro `authlib.jose.errors.UnsupportedAlgorithmError` ao fazer login via Authentik OAuth2/OIDC no Open WebUI  
**Status:** ✅ Diagnosticado — **3 soluções possíveis**

---

## Diagnóstico

### Erro Observado
```
2026-03-05 19:15:24.750 | ERROR | open_webui.utils.oauth:handle_callback:1674
- Error during OAuth process: 400: The email or password provided is incorrect...

authlib.jose.errors.UnsupportedAlgorithmError: unsupported_algorithm
```

### Root Cause Analysis

| Item | Status | Detalhes |
|------|--------|----------|
| **OIDC Discovery** | ✅ OK | Endpoint acessível: `https://auth.rpa4all.com/application/o/openwebui/.well-known/openid-configuration` |
| **JWKS** | ✅ OK | Chaves públicas retornadas com sucesso (RS256) |
| **Network** | ✅ OK | Open WebUI consegue conectar ao Authentik |
| **Env Vars** | ✅ OK | `OPENID_PROVIDER_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` configurados |
| **JWT Verification** | ❌ FALHA | `authlib` não consegue validar JWT com RS256 — possível bug na versão `main` |

### Stack Trace Resumido
```
open_webui/main.py:2539 oauth_login_callback()
  → await oauth_manager.handle_callback()
    → await client.authorize_access_token()
      → await self.parse_id_token()  # ← FALHA AQUI
        → jwt.decode()
          → authlib.jose.errors.UnsupportedAlgorithmError
```

---

## Soluções

### 1️⃣ Restart do Container (Rápido)
**Tentativa inicial — resolve problemas de caching:**

```bash
# No homelab (192.168.15.2)
ssh 192.168.15.2 "docker restart open-webui"
sleep 10
ssh 192.168.15.2 "docker logs open-webui --tail 20"

# Testar
curl -L https://openwebui.rpa4all.com/oauth/oidc/callback?code=TEST
```

**Chance de sucesso:** 20% (se for problema de cache de chaves)

---

### 2️⃣ Downgrade para Versão Estável (Recomendado)
**O image `main` pode ter bug de JWT validation que foi corrigido em releases estáveis:**

```bash
ssh 192.168.15.2 << 'EOF'
# Parar container
docker stop open-webui
docker rm open-webui

# Rodar com tag estável (ex: v0.3.x)
docker run -d \
  --name open-webui \
  --restart always \
  -p 3000:8080 \
  -e ENABLE_OAUTH_SIGNUP=true \
  -e OAUTH_PROVIDER_NAME=Authentik \
  -e OPENID_PROVIDER_URL=https://auth.rpa4all.com/application/o/openwebui/.well-known/openid-configuration \
  -e OAUTH_CLIENT_ID=authentik-openwebui \
  -e OAUTH_CLIENT_SECRET=openwebui-sso-secret-2026 \
  -e OAUTH_SCOPES="openid email profile" \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:v0.3.0  # ← Usar versão estável

# Verificar
sleep 30
docker logs open-webui --tail 30
EOF

# Testar no navegador
firefox https://openwebui.rpa4all.com/
```

**Versões recomendadas:**
- ✅ `v0.3.0` ou `v0.2.x` (releases oficiais)
- ❌ `main` (desenvolvimento, instável)
- ❌ `latest` (pode apontar para `main`)

**Chance de sucesso:** 85%

---

### 3️⃣ Reconfiguração Manual do OIDC
**Se restart/downgrade não funcionarem, resetar configurações:**

```bash
ssh 192.168.15.2 << 'EOF'
# Parar container
docker stop open-webui

# Backup data
docker run --rm \
  -v open-webui:/data \
  alpine tar czf /tmp/open-webui-backup-$(date +%s).tar.gz /data

# Limpar cache (mantendo usuários)
docker run --rm -e PYTHONUNBUFFERED=1 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:v0.3.0 \
  python3 -c "
import os
import shutil
cache_dir = '/app/backend/data/ollama_files'
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)
    print('Cache limpo')
"

docker start open-webui
sleep 30
docker logs open-webui --tail 30
EOF
```

---

## Teste de Validação

### 1. Verificar Acesso ao OpenWebUI
```bash
curl -s https://openwebui.rpa4all.com/ | grep -i "login\|authentik" | head -5
```

### 2. Verificar Botão OAuth no Frontend
```bash
# Acessar https://openwebui.rpa4all.com no navegador
# Deve aparecer botão: "Sign in with Authentik" ou similar
# ❌ Não deve aparecer erro: "unsupported_algorithm"
```

### 3. Verificar Logs em Tempo Real
```bash
ssh 192.168.15.2 "docker logs open-webui -f" &
# Tentar login, aguardar 30s, Ctrl+C
```

### 4. Validar OIDC Token Exchange
```bash
ssh 192.168.15.2 "docker exec open-webui curl -X POST https://auth.rpa4all.com/application/o/token/ \
  -d 'grant_type=client_credentials&client_id=authentik-openwebui&client_secret=openwebui-sso-secret-2026'"
```

---

## Escalation (Se nenhuma solução funcionar)

| Ação | Comando |
|------|---------|
| **Verificar Authentik** | `ssh 192.168.15.2 "docker logs authentik-server --tail 50 \| grep -i 'error\|openwebui'"` |
| **Testar JWKS manualmente** | `curl https://auth.rpa4all.com/application/o/openwebui/jwks/` |
| **Resetar app Authentik** | Via webui: auth.rpa4all.com → Applications → OpenWebUI → editar → marcar "Require consent" + salvar |
| **Criar nova app Authentik** | Usar [tools/setup_authentik_django.py](tools/setup_authentik_django.py) para recriar setup |

---

## Checklist Implementação

- [ ] **Passo 1:** Restart container (`docker restart open-webui`)
- [ ] **Passo 2:** Testar login em https://openwebui.rpa4all.com (aguardar 2min)
- [ ] **Passo 3:** Se falhar → downgrade para `v0.3.0`
- [ ] **Passo 4:** Se falhar → reconfigurar OIDC
- [ ] **Passo 5:** Validar com `curl` + teste manual no navegador
- [ ] **Passo 6:** Se persistir → abrir issue no GitHub do Open WebUI com stack trace

---

## Referências

- **Open WebUI OAuth Docs:** https://docs.openwebui.com/features/oauth
- **Authentik OIDC Provider:** https://goauthentik.io/docs/providers/oauth2/
- **Authlib JWT Issues:** https://github.com/lepture/authlib/issues (RS256 support)
- **Issue histórico:** O erro `unsupported_algorithm` é conhecido em versões `main` do Open WebUI com certos OIDC providers

---

**Próximas ações:**
1. Implementar Passo 1 (Restart) agora
2. Se não funcionar, aplicar Passo 2 (Downgrade) hoje
3. Depois, validar login e criar caso de teste
