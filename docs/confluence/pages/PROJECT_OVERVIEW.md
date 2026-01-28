# Visão geral do projeto

Resumo executivo
- Objetivo: orquestrar agentes especializados, pipeline de mensagens (Agent Communication Bus), integrações com Telegram e infra local de modelos (Ollama / OpenWebUI).
- Estado atual: entrega de mensagens via bus funcionando; geração de respostas via modelos necessita correção em `192.168.15.2` (Ollama inacessível; OpenWebUI retornando 500 em rotas autenticadas).

Componentes principais
- `specialized_agents` — agentes especializados, API e orquestração (FastAPI).
- `tools/simple_vault` — cofre de segredos local (GPG) e helpers.
- `scripts` — automações e deploy helpers.
- `openwebui` / `ollama` — pontos de modelo esperados (hosts locais/remotos).

Riscos e bloqueadores
- Chaves ausentes/corrompidas em `tools/simple_vault/secrets` (ex.: `openwebui_api_key.gpg`).
- Serviços de modelos (192.168.15.2) precisam ser corrigidos antes de habilitar respostas fluídas.

Links úteis
- Arquivos de configuração: `tools/secrets_loader.py`, `tools/vault/secret_store.py`.
- Auto-responder Telegram: `specialized_agents/telegram_auto_responder.py`.
