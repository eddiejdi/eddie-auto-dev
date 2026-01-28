# Arquitetura técnica

Resumo de alto nível
- Entrada: updates do Telegram (poller/bridge) são publicados no Agent Communication Bus.
- Processamento: agentes especializados consomem mensagens do bus e podem consultar RAG/DBs.
- Saída: mensagens de saída são publicadas no bus e um componente de bridge envia para a API do Telegram.

Fluxo detalhado
1. `telegram_poller` obtém updates e publica `MessageType.REQUEST` no Bus.
2. `specialized_agents.api` recebe requests e encaminha para agentes apropriados.
3. `telegram_auto_responder` tenta gerar texto chamando Ollama; em falha, tenta OpenWebUI; se ambos falharem, usa resposta canned.
4. Resposta final é publicada no bus e `telegram_client` envia `sendMessage` preservando `chat_id` e `message_thread_id`.

Componentes, arquivos e responsabilidades
- `specialized_agents/api.py` — endpoints HTTP do Bus.
- `specialized_agents/agent_manager.py` — lifecycle de agentes.
- `tools/secrets_loader.py` — central de segredos (obrigatório: cofre para tokens).
- `tools/simple_vault` — armazenamento local de segredos (GPG + passphrase).

Diagrama: ver `diagrams/project_architecture.drawio`.
