**Resumo rápido**
- Arquivo: documentação de auditoria e operação do pipeline WhatsApp → WAHA → Bot → Home Assistant.
- Objetivo: listar segredos hardcoded, mudanças aplicadas, verificações e instruções passo-a-passo para que uma IA/operador configure, teste e mantenha o fluxo com segurança.

**1. Achados principais (segredos & hardcoded)**
- tuya_test_regions.py: API_KEY, API_SECRET hardcoded.
- tuya_renew_iotcore.py / tuya_renew_uc.py: PASSWORD hardcoded (Eddie_88_tp!).
- extract_tuya_keys_cloud.py: ACCESS_SECRET hardcoded.
- extract_tuya_keys.py / extract_tuya_keys_cloud.py: possíveis tokens impressos em logs/prints.
- store_secrets.py: contém plaintext SECRETS dict — promove armazenamento (OK) mas evitar commitar valores reais.
- tuya_qr.html: QR gerado com token embutido na URL (exposição de credencial).
- setup_*_oauth.py / exchange_oauth_code.py: padrão de salvar client_secret / access_token em .env ou imprimir; gravar apenas no Secrets Agent.
- scripts que usam eddie-secrets-2026 como API key no curl (ex: exchange_oauth_code.py) — placeholder/incorreto.
- READMEs/MDs com senhas de exemplo como admin/newpassword123.

**2. Boas práticas aplicadas / correções feitas**
- Postgres: criei o DB estou_aqui e atualizei DATABASE_URL para postgresql://postgres:eddie_memory_2026@localhost:5432/estou_aqui (drop-in systemd do bot); atualizei default no whatsapp_bot.py.
- Secrets Agent: corrigi SECRETS_AGENT_API_KEY no drop-in do serviço; home_assistant_integration.py agora busca secrets quando env vars faltam.
- Whitelist: implementei OWNER_ONLY + ALLOWED_NUMBERS em whatsapp_bot.py para respostas só ao dono por padrão.

**3. Locais que precisam ser remediados (recomendado)**
- Remover/rotacionar segredos hardcoded listados em (1). Substituir por chamadas ao Secrets Agent e apagar do código.
- Limpar tuya_qr.html (remover token) e gerar QR temporário quando necessário.
- Revisar store_secrets.py para não conter valores reais commited; migrar ao Secrets Agent e limpar histórico Git se preciso.
- Substituir placeholders eddie-secrets-2026 por SECRETS_AGENT_API_KEY via env.

**4. Convenção de nomes de secrets (padrão)**
- Use eddie/<component>/<name>, ex: eddie/waha_api_key, eddie/home_assistant_token.
- Field: use 'password' para tokens/senhas.
- Env vars padrão: SECRETS_AGENT_URL, SECRETS_AGENT_API_KEY, DATABASE_URL, HOME_ASSISTANT_TOKEN, WAHA_API_KEY, GOOGLE_AI_API_KEY.

**5. Passo-a-passo operacional (IA ou humano)**
Pré-requisitos: SSH homelab (homelab@192.168.15.2), Secrets Agent rodando em http://localhost:8088, SECRETS_AGENT_API_KEY válido.

Verificações iniciais:
1) systemctl is-active eddie-whatsapp-bot secrets-agent eddie-postgres
2) curl -sf --connect-timeout 3 http://localhost:8088/secrets || echo 'Secrets Agent offline'
3) curl -s -H "X-API-KEY: $SECRETS_AGENT_API_KEY" http://localhost:8088/secrets | jq '.[] | select(.name|test("eddie/(waha_api_key|home_assistant_token|telegram_bot_token|deploy_password)"))'

Rotina segura de deploy/configuração:
1) Mover secrets hardcoded para Secrets Agent usando store_secrets.py ou curl -X POST /secrets com X-API-KEY.
2) Atualizar drop-in systemd em /etc/systemd/system/eddie-whatsapp-bot.service.d/env.conf somente com env vars (não commitar esse arquivo).
3) sudo systemctl daemon-reload && sudo systemctl restart eddie-whatsapp-bot
4) Verificar logs: journalctl -u eddie-whatsapp-bot -n 200 --no-pager | grep -iE "carregado|Schema PostgreSQL|Webhook server"
5) Teste E2E: enviar mensagem de outro número (não fromMe) ou usar WAHA API.

Instrumentação que uma IA deve executar automaticamente:
1) Scan por patterns: grep -E "API_KEY|SECRET|PASSWORD|TOKEN" -R . and report.
2) Verificar histórico Git para secrets (git log -S '<secret>' ou git-secrets).
3) Assegurar scripts gravem tokens no Secrets Agent, não em stdout/.env.

Comandos úteis:
Testar Secrets Agent: curl -sf -H "X-API-KEY: $SECRETS_AGENT_API_KEY" http://localhost:8088/secrets | head -40
Ver status bot: sudo systemctl status eddie-whatsapp-bot
Reiniciar e seguir logs: sudo systemctl restart eddie-whatsapp-bot && sudo journalctl -u eddie-whatsapp-bot -f
Enviar teste via WAHA: curl -s -X POST http://localhost:3001/api/sendText -H "Content-Type: application/json" -H "X-Api-Key: $WAHA_API_KEY" -d '{"chatId":"55119XXXXXXX@c.us","text":"/casa status","session":"default"}'

**6. Checklist final antes de abrir ao público**
- Remover segredos hardcoded do source e do histórico Git.
- Armazenar TODOS os segredos no Secrets Agent com nomes eddie/<component>/<name>.
- Rotacionar tokens/secrets usados (WAHA, Postgres, Home Assistant) após migração.
- Manter OWNER_ONLY=true por padrão e documentar procedimento de liberação.
- Auditar logs e remover prints que exfiltram tokens.

**7. Arquivos para inspeção imediata**
- whatsapp_bot.py
- home_assistant_integration.py
- tools/generate_gemini_api_key.py
- store_secrets.py
- tuya_test_regions.py
- extract_tuya_keys_cloud.py
- tuya_qr.html
- setup_waha.py

---
Próximos passos (opções):
1) Automatizar migração dos segredos detectados para o Secrets Agent (posso gerar script). 
2) Abrir PR com esta documentação e um utilitário `scripts/audit_and_migrate_secrets.sh`.

Diga 1 ou 2 para eu prosseguir com a opção desejada.
