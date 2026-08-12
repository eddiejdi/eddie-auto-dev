# Incidente 2026-08-10 — WikiAgent: /wiki/publish falhando com 401 "User not found"

## Resumo

Durante o inventário e publicação em lote dos `.md` do repositório na Wiki RPA4All,
todas as chamadas a `POST /wiki/publish` falharam com **HTTP 503**:

```
{"detail":"Copilot router indisponível: OpenAI-compatible error: 401 - \
{\"error\":{\"message\":\"User not found.\",\"code\":401}}"}
```

**Causa raiz:** o `CopilotModelRouter` classifica a maioria dos documentos como
`COMPLEX` (sinais como "criar", "deploy", "arquitetura", "pipeline") e roteia
diretamente para o provedor OpenAI-compatible (OpenRouter). A chave
`OPENAI_COMPATIBLE_API_KEY` configurada no serviço `specialized-agents-api` estava
**inválida/revogada** → OpenRouter respondeu `401 User not found`. Além disso, o
`OLLAMA_HOST` apontava para `192.168.15.2:11434`, uma instância Ollama legada **sem
modelos** (`{"models":[]}`), ou seja, nem o fallback local funcionava.

**Correção:** drop-in systemd apontando o Ollama do serviço para o **modelo free do
NAS** (`192.168.15.4:11546` → `phi4-mini:latest`, RTX 2060 8GB) e desligando a rota
cloud inválida. Sem tocar na GPU0 (`trading-analyst`) nem no trading live.

---

## Contexto (topologia do cluster Ollama)

| Slot | Endpoint | Modelo residente | Uso |
|------|----------|------------------|-----|
| GPU0 (RTX 3060) | `192.168.15.2:11544` | `trading-analyst` | Intocável (nunca evictar) |
| GPU1 (GTX 1050) | `192.168.15.2:11545` | `lfm2.5-fast:gpu1` | Mídia/controllers |
| NAS (RTX 2060) | `192.168.15.4:11546` | `phi4-mini:latest` | Auxiliares — **escolhido para o lote** |
| ~~legado~~ | `192.168.15.2:11434/11435` | **nenhum modelo** | Obsoleto, não usar |

Fonte: `ollama-local_ollama_health` e `curl /api/tags` em cada porta.

## Diagnóstico

1. Health do WikiAgent reportava `copilot_router: ok`, mas `copilot_router` só testa
   HTTP 200 em `/api/tags`, não a geração real.
2. `classify_request_complexity()` (em `specialized_agents/copilot_model_router.py`)
   marca quase todo doc como `COMPLEX` → `get_available_model()` vai direto pro cloud
   **se** `openai_compat_key` estiver setada (ignora o flag `enabled`).
3. Teste direto de `/wiki/raw` (sem Ollama) funcionou (page 731) → o problema era só o
   caminho de geração, não o Wiki.js.
4. Validado que `192.168.15.4:11546/v1/chat/completions` responde com `phi4-mini:latest`
   (modelo free, presente no homelab).

## Correção aplicada

Novo drop-in `/etc/systemd/system/specialized-agents-api.service.d/wiki-local-ollama.conf`:

```ini
[Service]
Environment="OLLAMA_HOST=http://192.168.15.4:11546"
Environment="OPENAI_COMPATIBLE_ENABLED=false"
Environment="OPENAI_COMPATIBLE_API_KEY="
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart specialized-agents-api
```

**Por que zera a chave e não só `ENABLED=false`:** o `CopilotModelRouter` só verifica
`LLM_OPENAI_COMPATIBLE_CONFIG.get("api_key")` (truthy) em `get_available_model()`; ele
não lê o flag `enabled`. Zerar a chave desativa o caminho cloud de fato.

Verificação pós-fix:

```
$ curl -s http://192.168.15.2:8503/wiki/health
{"status":"ok","active_model":"phi4-mini","active_gpu":"GPU0","provider":"ollama"}

$ curl -s -X POST http://192.168.15.2:8503/wiki/publish ... (smoke)
{"ok":true,"page_id":732,"model_used":"phi4-mini","gpu":"GPU",...}
```

## Impacto / notas

- **Escopo:** afeta o serviço `specialized-agents-api` inteiro (todos os agentes que
  usam o router). Como o host antigo (`11434`) estava vazio e a chave cloud morta,
  a mudança é estritamente uma melhoria para quem dependia desses caminhos.
- **GPU0/trading:** não foi tocada; o lote usa o NAS.
- **Reversão:** `sudo rm /etc/systemd/system/specialized-agents-api.service.d/wiki-local-ollama.conf`
  + `daemon-reload` + restart restaura os valores originais
  (`OLLAMA_HOST=http://192.168.15.2:11434`, `OPENAI_COMPATIBLE_ENABLED=true`, chave
  OpenRouter original). Backup dos valores nas drop-ins
  `openrouter*.conf.bak-20260805`.

## Referências

- `specialized_agents/copilot_model_router.py` — `get_available_model()`,
  `classify_request_complexity()`
- `specialized_agents/config.py` — `LLM_OPENAI_COMPATIBLE_CONFIG`, `LLM_CONFIG`
- `specialized_agents/wiki_agent.py` — `/wiki/publish`, `_copilot_generate`
- Operação em lote: `WIKI_BATCH_PUBLISH_2026-08-10.md` (raiz do repo)
