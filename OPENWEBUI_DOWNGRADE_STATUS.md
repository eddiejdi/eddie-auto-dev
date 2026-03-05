# 🔧 Open WebUI — Status do Downgrade (5 de março/2026)

## Problema Original
- ❌ Erro ao fazer login via Authentik: "The email or password provided is incorrect"
- 🔍 Root cause: `authlib.jose.errors.UnsupportedAlgorithmError` ao validar JWT RS256

## Ações Executadas

### 1. Diagnóstico Completo ✅
```bash
✅ OIDC Discovery — acessível
✅ JWKS (chaves públicas) — disponível
✅ Network conectando — OK
✅ Env vars configuradas — OK
❌ Validação JWT — FALHA (bug em versão main)
```

### 2. Tentativa 1: Restart
```bash
ssh 192.168.15.2 "docker restart open-webui"
```
**Resultado:** ❌ Falhou (cache não era problema)

### 3. Tentativa 2: Downgrade para v0.3.5 (EM ANDAMENTO)
```bash
docker rm -f open-webui
docker run -d \
  --name open-webui \
  --restart always \
  -p 3000:8080 \
  -e ENABLE_OAUTH_SIGNUP=true \
  -e OAUTH_PROVIDER_NAME=Authentik \
  -e OPENID_PROVIDER_URL=https://auth.rpa4all.com/application/o/openwebui/.well-known/openid-configuration \
  -e OAUTH_CLIENT_ID=authentik-openwebui \
  -e OAUTH_CLIENT_SECRET=openwebui-sso-secret-2026 \
  -e OAUTH_SCOPES='openid email profile' \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:v0.3.5
```

**Status:** 🟡 Imagem v0.3.5 está sendo baixada (~2-3GB)

---

## ⏭️ Próximas Ações (em ordem)

### Passo 1: Aguardar Download Completo
Estimado: **5-10 minutos** (depende de conexão)

```bash
ssh 192.168.15.2 "docker pull ghcr.io/open-webui/open-webui:v0.3.5 --progress && echo 'DOWNLOAD COMPLETO'"
```

### Passo 2: Verificar Status do Container
```bash
ssh 192.168.15.2 "docker ps -a | grep open-webui && docker logs open-webui --tail 20"
```

**Esperado:**
```
open-webui     ...    Up (healthy)    0.0.0.0:3000->8080
Loading WEBUI_SECRET_KEY...
Starting OpenWebUI v0.3.5...
```

### Passo 3: Testar Acesso
```bash
curl -s https://openwebui.rpa4all.com/ | grep -i "head\|authentik" | head -3
# Esperado: <head> da página (200 OK)
```

### Passo 4: Testar Login via Authentik
1. Abrir em navegador: **https://openwebui.rpa4all.com**
2. Procurar por botão: **"Sign in with Authentik"** (ou similar)
3. Clicar no botão
4. Fazer login com credenciais Authentik (`edenilson` / senha do vault)
5. ✅ Se funcionar: **sucesso resolvido!**
6. ❌ Se novo erro: ver próxima seção

### Passo 5: Validar Logs de Sucesso
```bash
ssh 192.168.15.2 'docker logs open-webui 2>&1 | grep -i "oidc\|oauth\|token\|jwt" | tail -10'
# Não deve aparecer "UnsupportedAlgorithmError"
```

---

## ❌ Se Falhar Novamente

### Opção A: Limpar Cache do Open WebUI
```bash
ssh 192.168.15.2 << 'EOF'
docker stop open-webui
docker run --rm -v open-webui:/data alpine rm -rf /data/cache/* /data/.webui_secret_key
docker start open-webui
sleep 30
docker logs open-webui --tail 20
EOF
```

### Opção B: Voltar para Latest + Ajustes
```bash
ssh 192.168.15.2 "docker run -d --name open-webui ... ghcr.io/open-webui/open-webui:latest"
# E ajustar alguma env var
```

### Opção C: Escalar para Authentik
Verificar se há problema no lado do Authentik:
```bash
ssh 192.168.15.2 "docker logs authentik-server --tail 50 | grep -i 'openwebui\|oauth\|error'"
```

---

## 📝 Referência: Backup Restaurável

Backup da data antes do downgrade foi criado em:
```
/tmp/open-webui-backup-1772738272.tar.gz  (no homelab)
```

Para restaurar (se necessário):
```bash
ssh 192.168.15.2 "docker stop open-webui && docker run --rm -v open-webui:/data alpine tar xzf /tmp/open-webui-backup-*.tar.gz -C /data && docker start open-webui"
```

---

## 🔄 Verificação de Sucesso

Quando o downgrade completar, você saberá que funcionou quando:

1. ✅ `docker ps` mostra `open-webui` com status `healthy` ou `running`
2. ✅ `curl https://openwebui.rpa4all.com/` retorna HTTP 200
3. ✅ Página carrega e mostra botão de login "Authentik" ou similar
4. ✅ Clique no botão redireciona para `auth.rpa4all.com/application/o/authorize/`
5. ✅ Após fazer login no Authentik, retorna a `openwebui.rpa4all.com` com usuário autenticado
6. ✅ Nenhuma mensagem de erro "unsupported_algorithm" nos logs

---

## 🎯 Checklist de Implementação

- [ ] Aguardar download v0.3.5 completar (~5 min)
- [ ] Verificar `docker ps` mostra container running
- [ ] Testar https://openwebui.rpa4all.com em navegador
- [ ] Confirmar botão "Sign in with Authentik" aparece
- [ ] Fazer logout e  testar fluxo completo de login
- [ ] Validar `docker logs open-webui` sem erros JWT
- [ ] Sucesso confirmado ✅

---

## 📞 Suporte Técnico

Se precisar de ajuda:
1. Compartilhar saída: `docker logs open-webui`
2. Informar qual passo está falhando
3. Usar documento [OPENWEBUI_AUTHENTIK_OAUTH_FIX.md](OPENWEBUI_AUTHENTIK_OAUTH_FIX.md) para troubleshooting detalhado

**Status Final:** 🟡 **EM PROGRESSO** — Downgrade iniciado, aguardando conclusão
