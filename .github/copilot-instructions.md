## Copilot instructions — Eddie Auto-Dev

Purpose: give an AI coding agent the minimal, repo-specific knowledge to be productive immediately.

### Big picture (core architecture)
- **Multi-agent system**: language-specific agents (Python, JS, TS, Go, Rust, Java, C#, PHP) run in isolated Docker containers; each has its own RAG (ChromaDB). See [specialized_agents/README.md](specialized_agents/README.md).
- **Message bus**: all inter-agent activity goes through the singleton bus ([specialized_agents/agent_communication_bus.py](specialized_agents/agent_communication_bus.py)). Do not write directly to DBs/files—publish via the bus. Interceptor ([specialized_agents/agent_interceptor.py](specialized_agents/agent_interceptor.py)) subscribes, assigns `conversation_id`, tracks phases, persists to SQLite or Postgres (`DATABASE_URL`).
- **Orchestration/API**: [specialized_agents/agent_manager.py](specialized_agents/agent_manager.py) + [specialized_agents/api.py](specialized_agents/api.py) manage agent lifecycle, Docker exec, GitHub push. FastAPI on port 8503 by default.
- **Entry points**: Telegram is the main user interface ([telegram_bot.py](telegram_bot.py)); Streamlit dashboard on 8502 ([specialized_agents/conversation_monitor.py](specialized_agents/conversation_monitor.py)).
- **VS Code Extension**: [eddie-copilot/](eddie-copilot/) provides in-editor assistant integration.

### Quick developer workflows ✅
- **Install specialized agents**: `chmod +x specialized_agents/install.sh && ./specialized_agents/install.sh`
- **Start services locally**: `./specialized_agents/start.sh` (Streamlit on 8502, API on 8503)
- **Setup interceptor + test**: `bash setup_interceptor.sh && python3 test_interceptor.py`
- **Run API in dev** (venv): `source .venv/bin/activate && uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503`
- **Run tests**: `pytest -q` (use `-m integration` or `-m external` for marked tests; see [conftest.py](conftest.py))
- **VS Code extension dev**: 
  ```bash
  cd eddie-copilot
  npm install              # Install dependencies
  npm run compile          # Compile TypeScript
  npm run watch            # Watch mode for development
  # Press F5 in VS Code to launch Extension Development Host
  # Or: vsce package && code --install-extension eddie-copilot-*.vsix
  ```
- **Check systemd services**: `sudo systemctl status eddie-telegram-bot specialized-agents-api diretor coordinator`
- **View logs**: `journalctl -u <service-name> -f` (e.g., `eddie-telegram-bot`, `specialized-agents-api`)
- **Demo conversations**: `bash demo_conversations.sh`

### GitHub Copilot — Uso recomendado (essencial)

- Sempre roteie as chamadas de LLM para o proxy local do homelab (`llm-optimizer`) quando disponível. Evite chamadas diretas ao Ollama em :11434 a partir de clientes externos — use `http://192.168.15.2:8512` como endpoint canônico para o Copilot no workspace.
- Variáveis de ambiente importantes para o Copilot usar no repositório/CI:
  - `OLLAMA_HOST` — endpoint do proxy (ex: `http://192.168.15.2:8512`)
  - `OLLAMA_MODEL` — modelo padrão (ex: `qwen2.5-coder:7b-cline`)
  - `OLLAMA_KEEP_ALIVE` — tempo para manter o modelo em memória (ex: `3600` para 1h)
- Use `keep_alive` nas requisições de warmup para pré-carregar modelos (ex.: POST `/api/generate` com `{"keep_alive":"3600s","model":"qwen2.5-coder:7b-cline"}`). Isso evita swap e melhora latência.
- Prefira modelos que cabem no GPU do homelab (por ex. `qwen2.5-coder:7b-cline` para RTX 2060 8GB). Se um cliente solicitar modelos maiores, rejeite ou devolva instruções para alternar modelo/contexto.
- Política de modelos: não solicitar modelos premium pagos. Use apenas os modelos permitidos nesta documentação.
- Segurança: nunca commit keys ou secrets. Use `tools/vault/secret_store.py` para obter segredos quando necessário.
- Para forçar o Copilot (cliente VS Code) a usar a nova configuração, instrua o usuário a recarregar a extensão Cline ou reiniciar o VS Code — o estado efetivo fica em `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/state/state.json`.


**Common troubleshooting**:
- If `specialized-agents-api` fails to start → check for missing native deps: `.venv/bin/pip install paramiko` then `sudo systemctl restart specialized-agents-api`
  - Postgres setup for cross-process IPC: `docker run -d --name eddie-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres` then add `Environment=DATABASE_URL=postgresql://postgress:eddie_memory_2026@localhost:5432/postgres` to systemd drop-ins (see [tools/systemd/install_env_for_unit.sh](tools/systemd/install_env_for_unit.sh))

### Project-specific conventions & examples 📚
- **Message-first pattern**: use `log_request`, `log_response`, `log_task_start`, `log_task_end` so metadata like `task_id` is consistent across agents
- **RAG usage**: prefer `RAGManagerFactory.get_manager(language)` or `RAGManagerFactory.global_search(...)`:
  ```py
  from specialized_agents.rag_manager import RAGManagerFactory
  
  # Language-specific RAG
  python_rag = RAGManagerFactory.get_manager("python")
  await python_rag.index_code(code, "python", "descrição")
  results = await python_rag.search("como usar FastAPI")
  
  # Global search across all RAGs
  global_results = await RAGManagerFactory.global_search("docker patterns")
  ```
- **GitHub push** (via manager):
  ```py
  from specialized_agents.agent_manager import get_agent_manager
  manager = get_agent_manager()
  await manager.push_to_github("python", "meu-projeto", repo_name="meu-repo")
  ```
- **Adding a new language agent**:
  1. Add template in [specialized_agents/config.py](specialized_agents/config.py) → `LANGUAGE_DOCKER_TEMPLATES`
  2. Implement agent class in [specialized_agents/language_agents.py](specialized_agents/language_agents.py) (subclass `SpecializedAgent`)
  3. Register the class in `AGENT_CLASSES` and add unit/integration tests
  - **Agent Memory System**: persistent memory for learning from past decisions
    ```py
    from specialized_agents.language_agents import PythonAgent
  
    agent = PythonAgent()  # Memory auto-integrated if DATABASE_URL set
  
    # Record decision
    dec_id = agent.should_remember_decision(
      application="my-app", component="auth", error_type="timeout",
      error_message="DB timeout after 5s", decision_type="fix",
      decision="Increase timeout to 30s", confidence=0.8
    )
  
    # Query past decisions
    past = agent.recall_past_decisions("my-app", "auth", "timeout", "DB timeout")
  
    # Informed decision (LLM + memory)
    decision = await agent.make_informed_decision(
      application="my-app", component="auth", 
      error_type="timeout", error_message="DB timeout",
      context={"load": "high"}
    )
  
    # Update feedback after result
    agent.update_decision_feedback(dec_id, success=True, details={"fix_worked": True})
    ```
    See [docs/AGENT_MEMORY.md](docs/AGENT_MEMORY.md) for complete guide.

### Remote orchestrator notes ⚠️
- Toggle: `REMOTE_ORCHESTRATOR_ENABLED`; hosts configured in `REMOTE_ORCHESTRATOR_CONFIG['hosts']`.
- Hosts are attempted in order (e.g., `localhost` → `homelab`).
- **SSH config example** (in [specialized_agents/config.py](specialized_agents/config.py)):
  ```py
  REMOTE_ORCHESTRATOR_CONFIG = {
      "enabled": True,
      "hosts": [
          {"name": "localhost", "host": "127.0.0.1", "user": "root", "ssh_key": None},
          {"name": "homelab", "host": "192.168.15.2", "user": "homelab", "ssh_key": "~/.ssh/id_rsa"}
      ]
  }
  ```
- **Note:** GitHub-hosted runners cannot reach private networks (e.g., 192.168.*.*). For SSH-based workflows, prefer a self-hosted runner in the homelab or expose a secured endpoint.

### 🖥️ Homelab Agent — Execução remota de comandos
Agente dedicado para executar comandos no homelab via SSH com 3 camadas de segurança: restrição IP (RFC 1918), whitelist de comandos, blocklist explícita.

- **Módulos**: [specialized_agents/homelab_agent.py](specialized_agents/homelab_agent.py) (agente SSH + segurança) + [specialized_agents/homelab_routes.py](specialized_agents/homelab_routes.py) (API FastAPI `/homelab/*`).
- **Categorias de comandos**: `SYSTEM_INFO`, `DOCKER`, `SYSTEMD`, `NETWORK`, `FILES`, `PROCESS`, `LOGS`, `PACKAGE`, `CUSTOM`.
- **Testes**: [tests/test_homelab_agent.py](tests/test_homelab_agent.py) — 28 testes unitários.
- **VS Code Extension**: 7 comandos (`homelabExecute`, `homelabHealth`, `homelabDockerPs`, `homelabDockerLogs`, `homelabSystemdStatus`, `homelabSystemdRestart`, `homelabLogs`) via [eddie-copilot/src/homelabAgentClient.ts](eddie-copilot/src/homelabAgentClient.ts).

**Uso Python:**
```py
from specialized_agents.homelab_agent import get_homelab_agent

agent = get_homelab_agent()
result = await agent.execute("docker ps")            # Execução direta
health = await agent.server_health()                  # Saúde do servidor
result = await agent.systemctl_status("nginx")        # Status de serviço
result = await agent.docker_logs("eddie-postgres")    # Logs de container
```

**Uso API (porta 8503):**
```bash
# Executar comando
curl -X POST http://localhost:8503/homelab/execute \
  -H 'Content-Type: application/json' -d '{"command":"docker ps","timeout":30}'

# Saúde do servidor
curl http://localhost:8503/homelab/server-health

# Docker containers
curl http://localhost:8503/homelab/docker/ps
```

- **Config SSH**: `HOMELAB_HOST` (default `192.168.15.2`), `HOMELAB_USER` (default `homelab`), `HOMELAB_SSH_KEY` (default `~/.ssh/id_rsa`).
- **Audit log**: todos os comandos são registrados em `DATA_DIR/homelab_audit.jsonl`.
- Documentação completa: [docs/HOMELAB_AGENT.md](docs/HOMELAB_AGENT.md).

### 📈 Multi-Coin Trading (AutoCoinBot) — Regras obrigatórias

Infraestrutura de 6 moedas com exporters Prometheus e dashboard Grafana unificado. Documentação completa: [docs/MULTI_COIN_TRADING_INFRASTRUCTURE.md](docs/MULTI_COIN_TRADING_INFRASTRUCTURE.md).

**Portas**: BTC(:9092/:8511), ETH(:9098/:8512), XRP(:9094/:8513), SOL(:9095/:8514), DOGE(:9096/:8515), ADA(:9097/:8516).

**⛔ BANCO DE DADOS — REGRA CRÍTICA (NÃO NEGOCIÁVEL):**
- **USAR SOMENTE PostgreSQL** (`psycopg2`) — container `eddie-postgres`, porta `5433`, database `postgres`, schema `btc`
- **NUNCA usar SQLite** (`sqlite3`) — o arquivo `data/trading_agent.db` está **OBSOLETO** e **DESATUALIZADO**
- DSN padrão: `postgresql://postgres:eddie_memory_2026@localhost:5433/postgres`
- `conn.autocommit = True` é **OBRIGATÓRIO** (evita cascata `InFailedSqlTransaction`)
- `cursor.execute("SET search_path TO btc, public")` após conectar
- `dry_run` é **boolean** (`True/False`), não integer (`1/0`)
- Placeholders: `%s` (não `?` do SQLite)
- **TODAS** as queries DEVEM filtrar por `AND symbol=%s` — sem exceção
- Referência funcional: `btc_query.py` (usa PostgreSQL corretamente)

**Regras Grafana (CRÍTICAS — evitar erros recorrentes):**
1. **UM arquivo JSON por dashboard** na pasta de provisioning. Títulos duplicados **bloqueiam silenciosamente** todas as atualizações (Grafana não aplica nada).
2. **Todas** as expressões Prometheus DEVEM usar `{job="$coin_job"}` — nunca `{symbol="BTC-USDT"}` hardcoded.
3. **Editar APENAS o arquivo JSON** no disco — alterações pela UI do Grafana são sobrescritas a cada 30 seg.
4. **Após editar**, verificar logs: `sudo docker logs grafana --since 60s 2>&1 | grep "not unique\|no database write"`. Se aparecer = tem duplicata.
5. **Dashboard ativo**: `btc_trading_dashboard_v3_prometheus.json` (UID: `237610b0-...`). Não criar outro com mesmo título.

**Regras Exporter:**
- `/set-live` é **GET** (não POST). Cada exporter usa seu próprio `CONFIG_PATH` via env var `COIN_CONFIG_FILE`.
- Testar `/set-live` em moeda secundária → verificar que `config.json` (BTC) **NÃO** foi alterado.

### � MODELOS GRATUITOS — REGRA OBRIGATÓRIA (TODOS OS AGENTES)
**Use SOMENTE modelos base (gratuitos) do Copilot Pro+.** Modelos premium consomem requests pagos e são proibidos por padrão.
- **Permitidos (base/gratuitos)**: `GPT-4o` · `GPT-4o mini` · `GPT-4.1` · `GPT-4.1 mini` · `GPT-4.1 nano` · `GPT-5.1` · `Raptor Mini`
- **Proibidos (premium)**: `Claude Opus 4` · `Claude Sonnet 4` · `o3` · `o4-mini` · `Gemini 2.5 Pro`
- Se o usuário solicitar explicitamente um modelo premium, avise o custo antes de prosseguir.
- Para tarefas de código/análise: prefira `GPT-4.1` ou `GPT-5.1` (melhor custo-benefício).
- Para completions rápidas: prefira `GPT-4.1 nano` ou `GPT-4o mini`.
### 🧠 OLLAMA LOCAL — DUAL-GPU (OBRIGATÓRIO)
**Prefira SEMPRE o Ollama local para processamento de LLM em vez de consumir tokens cloud (Copilot/OpenAI/Anthropic).**

**Arquitetura Dual-GPU (2 instâncias Ollama independentes):**
| Instância | GPU | VRAM | Porta | Modelo padrão | Throughput | Systemd unit |
|-----------|-----|------|-------|---------------|------------|--------------|
| Principal | GPU0 — RTX 2060 SUPER | 8 GB | `:11434` | `qwen2.5-coder:7b` (Q4_K_M) | ~31 tok/s | `ollama.service` + drop-in `ollama-optimized.conf` |
| Secundária | GPU1 — GTX 1050 | 2 GB | `:11435` | `qwen3:1.7b` | ~37-47 tok/s | `ollama-gpu1.service` |

- **Configs versionados**: [systemd/ollama-optimized.conf](systemd/ollama-optimized.conf) (drop-in GPU0) · [systemd/ollama-gpu1.service](systemd/ollama-gpu1.service) (GPU1)
- **Env vars**: `OLLAMA_HOST` (default `http://192.168.15.2:11434`), `OLLAMA_HOST_GPU1` (`http://192.168.15.2:11435`), `OLLAMA_MODEL` (default `eddie-coder`)
- **KV cache**: `q4_0` em ambas (reduz VRAM ~75% vs q8_0)
- **Otimizações GPU0**: `OLLAMA_SCHED_SPREAD=true`, `OLLAMA_GPU_OVERHEAD=512MB`, `OLLAMA_FLASH_ATTENTION=true`, `CPUAffinity=2-15`
- **Otimizações GPU1**: `CUDA_VISIBLE_DEVICES=1`, `CPUAffinity=12-15`, 4 threads (não competir com principal)
- **CPU isolation**: `isolcpus` foi **removido** do GRUB em 2026-03-01. Cores 0-1 agora disponíveis ao scheduler do SO. A separação Ollama ↔ SO é garantida **apenas por `CPUAffinity`** nos drop-ins systemd (não mais por kernel isolation).

**Quando usar cada instância:**
- **GPU0 (:11434)** — tarefas complexas: análise de código, refatoração, geração de snippets, code review
- **GPU1 (:11435)** — tarefas leves/paralelas: resumos, classificação, parsing de logs, formatação, embeddings
- **Fallback chain**: Ollama GPU0 → Ollama GPU1 → OpenWebUI → Copilot API (último recurso)

**Quando usar tokens cloud (EXCEÇÃO):**
- Ambas instâncias Ollama estão offline
- Tarefa requer contexto > 32K tokens (limite Ollama)
- Usuário solicita explicitamente modelo cloud específico

**Exemplo de uso (dual-GPU):**
```py
import httpx, os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")       # GPU0 RTX 2060
OLLAMA_HOST_GPU1 = os.getenv("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")  # GPU1 GTX 1050
MODEL_HEAVY = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
MODEL_LIGHT = "qwen3:1.7b"

async def ask_ollama(prompt: str, light: bool = False) -> str:
    host = OLLAMA_HOST_GPU1 if light else OLLAMA_HOST
    model = MODEL_LIGHT if light else MODEL_HEAVY
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120.0
        )
        return resp.json().get("response", "")

# Pesado (GPU0): code review, refatoração
result = await ask_ollama("Refatore esta função...", light=False)
# Leve (GPU1): parsing, classificação
summary = await ask_ollama("Resuma este log em 1 linha", light=True)
```

**Economia estimada**: 50-80% de redução no consumo de tokens cloud ao rotear inferência para Ollama local.
### �🔴 ROTEAMENTO HOMELAB — REGRA GLOBAL E IMPERATIVA (TODOS OS AGENTES)
**SEM EXCEÇÃO:** todo agente Copilot (local, distribuído, remoto) DEVE rotear para homelab:
- **Operações para homelab via API** (`POST /distributed/route-task` na porta 8503) **OU SSH direto**:
  - Verificação de logs, status, métricas, saúde
  - Manipulação Docker/systemd/cgroups/iptables
  - BD queries, scrapin, processamento pesado
  - Execução testes, builds, compilação
  - Geração/execução scripts, análise arquivos grandes
- **Permanecer local APENAS**:
  - Análise de documentação
  - Edição de arquivos config simples
  - Orquestração UI, apresentação resultados
  - Resumos (< 100 caracteres) — nunca trazer outputs grandes
- **Benefícios**: economia de tokens Copilot (50-80% redução com Ollama local), melhor performance, recursos homelab maximizados.
- **LLM routing**: Ollama (`:11434`) é o LLM primário — usar ANTES de qualquer API cloud.
- **Exceções SSH direto**: autenticação cloudflared, conectividade crítica, fallback API.
- **Violação = desperdício de tokens.** Quando em dúvida: rotear para homelab + Ollama.

### Integration points & env vars (used across scripts)
- `OLLAMA_HOST` (default `http://192.168.15.2:11434`) — **LLM primário** (GPU0 RTX 2060 SUPER). Usar SEMPRE antes de tokens cloud.
- `OLLAMA_HOST_GPU1` (default `http://192.168.15.2:11435`) — **LLM secundário** (GPU1 GTX 1050). Tarefas leves/paralelas.
- `OLLAMA_MODEL` (default `eddie-coder`) — modelo padrão. Alternativas: `qwen2.5-coder:7b`, `qwen3:1.7b`.
- `GITHUB_AGENT_URL` (local helper at `http://localhost:8080`).
- `DATA_DIR` / `DATABASE_URL` for interceptor persistence.
- Do not log or commit secrets; use `tools/vault/secret_store.py` or `tools/simple_vault/`.

### 🎨 Cores dinâmicas da janela VS Code — REGRA OBRIGATÓRIA (TODOS OS AGENTES)
O agente DEVE sinalizar visualmente seu estado alterando as cores da janela via `python tools/vscode_window_state.py <estado> --agent-id <id>`:
- **Amarelo** (`processing`): ao INICIAR qualquer tarefa/processamento.
- **Verde** (`done`): ao CONCLUIR a tarefa com sucesso.
- **Vermelho** (`error`): ao encontrar um ERRO crítico.
- **Laranja piscante** (`prompt`): ao AGUARDAR input do usuário (traz janela ao foco).
- **Reset** (`reset`): para remover customizações de cor.
- **Cores são independentes por agente**: cada agente usa seu `--agent-id` (ex: `--agent-id copilot-1`). O estado de **maior prioridade** entre todos os agentes ativos define a cor: `error > prompt > processing > done`. Janela só fica verde quando **TODOS** os agentes estão `done`. Agentes inativos por 10+ min são removidos automaticamente.
- Fluxo típico: `processing` → trabalho → `done` (ou `error`). Antes de `ask_questions`: `prompt`.
- Ver status: `python tools/vscode_window_state.py status`.

### Testing & CI tips 🧪
- Integration tests expect running services (API + interceptor). See [test_api_integration.py](test_api_integration.py) and [conftest.py](conftest.py) for markers and skips
- Use `pytest -q`; CI toggles may enable `integration`/`external` marks explicitly
- Test markers defined in conftest.py:
  - `@pytest.mark.integration` - tests requiring local services (API on 8503)
    ```py
    @pytest.mark.integration
    def test_api_health():
        response = requests.get('http://localhost:8503/health')
        assert response.status_code == 200
    ```
  - `@pytest.mark.external` - tests using external libs (chromadb, paramiko, playwright)
    ```py
    @pytest.mark.external
    def test_chromadb_connection():
        import chromadb
        client = chromadb.Client()
        assert client.heartbeat() > 0
    ```
- Top-level tests (repo root) ignored by default; set `RUN_ALL_TESTS=1` to collect all
- Be mindful of cleanup policies (backup retention, container cleanup) during tests

---

### Essenciais operacionais ⚠️
- **DB-backed IPC** (cross-process): use Postgres + [tools/agent_ipc.py](tools/agent_ipc.py). **Defina `DATABASE_URL`** nas services (systemd drop-ins ou arquivos de ambiente) para que `diretor`, `coordinator` e `specialized-agents-api` troquem mensagens:
  ```py
  from tools import agent_ipc
  
  # Publish request (from any agent)
  rid = agent_ipc.publish_request('assistant','DIRETOR','Please authorize deploy',{'env':'prod'})
  
  # Poll for response (blocks until Diretor responds or timeout)
  resp = agent_ipc.poll_response(rid, timeout=60)
  if resp:
      print(f"Diretor says: {resp['response']}")
  else:
      print("Timeout waiting for Diretor approval")
  
  # Diretor side (or use tools/invoke_director.py)
  pending = agent_ipc.fetch_pending('DIRETOR')
  for req in pending:
      agent_ipc.respond(req['id'], 'DIRETOR', 'Approved for prod deploy')
  ```
- Se `specialized-agents-api` falhar no startup, verifique dependências nativas (ex.: `paramiko`). Exemplo de correção: `.venv/bin/pip install paramiko` && `sudo systemctl restart specialized-agents-api`
- **Systemd tips**: adicione drop-ins em `/etc/systemd/system/<unit>.d/env.conf` para exportar `DATABASE_URL`, depois `sudo systemctl daemon-reload && sudo systemctl restart <unit>`
- **Deploy do site**: veja [site/deploy/](site/deploy/) (`openwebui-ssh-tunnel.service`, nginx, `cloudflared`). Health checks verificam `http://192.168.15.2:3000/health` (resposta `000000` indica problema de rede/túnel)
- **Test collection**: Top-level test files in repo root are ignored by default to avoid import-time side effects. Set `RUN_ALL_TESTS=1` to override (see [conftest.py](conftest.py))

### Exemplos rápidos 📤
- **Publish coordinator broadcast** (API):
```bash
curl -X POST http://localhost:8503/communication/publish \
  -H 'Content-Type: application/json' \
  -d '{"message_type":"coordinator","source":"coordinator","target":"all","content":"please_respond"}'
- **Invoke Diretor** (local helper):
```bash
python3 tools/invoke_director.py "Please review my deployment plan"
> Para detalhes operacionais (comandos longos, Docker quickstart, drop-in examples), consulte [.github/copilot-instructions-extended.md](.github/copilot-instructions-extended.md).

### Minimal example (bus publish) 📤
```py
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
bus = get_communication_bus()
bus.publish(MessageType.REQUEST, "caller", "target_agent", {"op": "run"}, metadata={"task_id": "t1"})
If anything is unclear or missing, point to the section (architecture, workflows, conventions) and I will refine it. See [.github/copilot-instructions-extended.md](.github/copilot-instructions-extended.md) for expanded troubleshooting, examples, and deploy tips.