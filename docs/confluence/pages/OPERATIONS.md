# Operações e Runbook

Checklist de preparação de ambiente
- Garantir `tools/simple_vault/passphrase` presente e válido.
- Inserir chaves obrigatórias no cofre: `eddie/telegram_bot_token`, `eddie/telegram_chat_id`, `openwebui/api_key`, `eddie/tunnel_api_token`.
- Verificar serviços locais: OpenWebUI container, Ollama (se usado), e Agent API (uvicorn).

Procedimentos comuns
- Atualizar segredos no cofre:
  - Local: `tools/simple_vault/add_secret.sh <name>` (cole valor e encerre).
  - CI: adicionar `OPENWEBUI_API_KEY` / `TELEGRAM_BOT_TOKEN` nos repo secrets para pipelines.
- Aplicar envs systemd para que serviços leiam `SIMPLE_VAULT_PASSPHRASE_FILE`: `tools/simple_vault/apply_systemd_envs.sh`.

Diagnóstico rápido
- Logs: `journalctl -u specialized-agents-api.service` e `docker logs <open-webui>`.
- Testes de endpoint OpenWebUI: `scripts/test_openwebui_target.sh <host>`.
