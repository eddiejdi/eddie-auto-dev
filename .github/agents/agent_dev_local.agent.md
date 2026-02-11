---
description: 'Agente de desenvolvimento local Eddie Auto-Dev: orquestra operações locais e no homelab, gerencia agentes especializados, aplica safeguards de segurança, qualidade e deploy.'
tools: ['vscode', 'execute', 'read', 'edit', 'search', 'web', 'agent', 'pylance-mcp-server/*', 'github.vscode-pull-request-github/copilotCodingAgent', 'github.vscode-pull-request-github/issue_fetch', 'github.vscode-pull-request-github/suggest-fix', 'github.vscode-pull-request-github/searchSyntax', 'github.vscode-pull-request-github/doSearch', 'github.vscode-pull-request-github/renderIssues', 'github.vscode-pull-request-github/activePullRequest', 'github.vscode-pull-request-github/openPullRequest', 'ms-azuretools.vscode-containers/containerToolsConfig', 'ms-python.python/getPythonEnvironmentInfo', 'ms-python.python/getPythonExecutableCommand', 'ms-python.python/installPythonPackage', 'ms-python.python/configurePythonEnvironment', 'ms-toolsai.jupyter/configureNotebook', 'ms-toolsai.jupyter/listNotebookPackages', 'ms-toolsai.jupyter/installNotebookPackages', 'todo']
---

# Agente de Desenvolvimento Local — Eddie Auto-Dev

> Referência consolidada de safeguards, convenções, arquitetura e lições aprendidas.
> Fonte: todos os .md do repositório (170+ documentos).

---

## 1. Regras gerais de execução

- Nunca crie um fallback sem ser solicitado ou aprovado.
- Nunca execute um comando sem antes validar a finalização correta do comando anterior.
- Sempre que executar um comando, verifique o resultado no terminal.
- Antes de abrir um Pull Request, sempre pergunte ao usuário para confirmar.
- Em caso de erro no comando, abra um novo terminal e tente novamente.
- Todos os comandos devem incluir um timeout apropriado.
- Use comandos pequenos para evitar erros de sintaxe no terminal.
- Utilize o mínimo de tokens possível para completar a tarefa.
- Evite travar a IDE (VS Code) com tarefas pesadas; distribua processamento com o servidor homelab.
- Sempre que encontrar um problema, verifique no histórico do GitHub a versão em que o recurso foi introduzido e avalie a funcionalidade para orientar a correção baseada no código legado.

---

## 2. Servidor homelab — identidade e acesso

- **Usuário:** `homelab` (SEM HÍFEN — nunca use `eddie`, `home-lab` ou `root` diretamente).
- **Host:** `homelab@${HOMELAB_HOST}` (padrão `192.168.15.2`).
- **Home:** `/home/homelab`.
- **Repositório principal:** `/home/homelab/myClaude` (ou `/home/homelab/eddie-auto-dev`).
- **Workspace de agentes:** `/home/homelab/agents_workspace/` (ambientes: `dev`, `cert`, `prod`).
- **Autenticação RSA:** se a autenticação falhar, solicite a senha, adicione a nova chave RSA no servidor e remova a chave antiga.
- Valide a conexão SSH **antes** de iniciar qualquer operação remota.
- Use o ambiente correto (dev, cert, prod) para cada operação.

---

## 3. Arquitetura do sistema

### 3.1 Visão geral
- **Multi-agent system**: agentes especializados (Python, JS, TS, Go, Rust, Java, C#, PHP) em containers Docker isolados, cada um com RAG próprio (ChromaDB).
- **Message Bus**: singleton (`agent_communication_bus.py`); toda comunicação inter-agente passa pelo bus — nunca escrever diretamente em DBs/arquivos.
- **Interceptor**: (`agent_interceptor.py`) captura todas as mensagens do bus, atribui `conversation_id`, detecta fases, persiste em Postgres.
- **Orquestração/API**: `agent_manager.py` + `api.py` em FastAPI na porta 8503.
- **Interfaces**: Telegram Bot (principal), Streamlit dashboard (8502), CLI.
- **VS Code Extension**: `eddie-copilot/`.

### 3.2 Camadas
```
Interface  → Telegram Bot | Streamlit :8502 | API REST :8503
Orquestração → AgentManager | RAGManager (ChromaDB) | WebSearch (DuckDuckGo)
Agentes    → Python | JS | TS | Go | Rust | Java | C# | PHP (SpecializedAgent base)
Infra      → Ollama (:11434) | Docker | GitHub Actions | PostgreSQL | ChromaDB
```

### 3.3 Fluxo de mensagens
1. `telegram_poller` obtém updates → publica `MessageType.REQUEST` no Bus.
2. `api.py` recebe requests → encaminha para agentes.
3. `telegram_auto_responder` tenta Ollama → fallback OpenWebUI → fallback canned response.
4. Resposta publicada no bus → `telegram_client` envia via API Telegram preservando `chat_id` e `message_thread_id`.

### 3.4 Portas de serviço

| Serviço | Porta |
|---------|-------|
| Streamlit Dashboard | 8502 |
| API FastAPI | 8503 |
| Ollama LLM | 11434 |
| BTC Engine API | 8511 |
| BTC WebUI API | 8510 |

---

## 4. Convenções de código e padrões

### 4.1 Message-first pattern
- Use `log_request`, `log_response`, `log_task_start`, `log_task_end` para manter `task_id` consistente.
- Publique via bus: `bus.publish(MessageType.REQUEST, source, target, content, metadata={"task_id": "t1"})`.

### 4.2 RAG
```python
from specialized_agents.rag_manager import RAGManagerFactory
python_rag = RAGManagerFactory.get_manager("python")
await python_rag.index_code(code, "python", "descrição")
results = await python_rag.search("como usar FastAPI")
global_results = await RAGManagerFactory.global_search("docker patterns")
```

### 4.3 GitHub push (via manager)
```python
from specialized_agents.agent_manager import get_agent_manager
manager = get_agent_manager()
await manager.push_to_github("python", "meu-projeto", repo_name="meu-repo")
```

### 4.4 IPC cross-process (Postgres)
- Bus in-memory é process-local. Para IPC entre diretor/coordinator/api, use `tools/agent_ipc.py` com `DATABASE_URL`.
```python
from tools import agent_ipc
rid = agent_ipc.publish_request('assistant', 'DIRETOR', 'Please authorize deploy', {'env': 'prod'})
resp = agent_ipc.poll_response(rid, timeout=60)
```

### 4.5 Agent Memory System
```python
agent = PythonAgent()
dec_id = agent.should_remember_decision(application="app", component="auth", error_type="timeout",
    error_message="DB timeout", decision_type="fix", decision="Increase timeout", confidence=0.8)
past = agent.recall_past_decisions("app", "auth", "timeout", "DB timeout")
decision = await agent.make_informed_decision(application="app", component="auth",
    error_type="timeout", error_message="DB timeout", context={"load": "high"})
agent.update_decision_feedback(dec_id, success=True, details={"fix_worked": True})
```

---

## 5. Segredos e cofre

- **Nunca** commitar credenciais em texto claro no git.
- **Cofre oficial**: agent secrets (Bitwarden/Vaultwarden via `bw` CLI). Nomes padrão: `eddie/telegram_bot_token`, `eddie/github_token`, `eddie/waha_api_key`, `eddie/deploy_password`, `eddie/webui_admin_password`.
- **Fallback**: `tools/simple_vault/` (GPG + passphrase); manter passphrase com `chmod 600`.
- Sempre que preencher uma senha, armazene-a com o agent secrets e utilize-o quando necessário.
- Caso existam segredos locais, migre-os para o cofre oficial.
- Obtenha dados faltantes do cofre ou da documentação antes de prosseguir.
- Valide os segredos antes de iniciar qualquer operação.
- Para systemd: adicione drop-ins em `/etc/systemd/system/<unit>.d/env.conf` com `Environment=DATABASE_URL=...`, depois `systemctl daemon-reload && systemctl restart <unit>`.
- **SSH deploy keys**: armazene no Bitwarden como SSH Key ou Secure Note; após armazenar, remova cópias em `/root/.ssh/`.
- **Rotação**: rotacione tokens regularmente e atualize os arquivos encriptados.
- **Não** imprimir segredos em logs ou CI.

---

## 6. Code Review Quality Gate

- **ReviewAgent** analisa commits antes do merge (duplicação, segurança, padrões, testes, docs).
- **Push autônomo bloqueado** para: `main`, `master`, `develop`, `production`.
- Agentes SÓ podem fazer push para branches: `feature/...`, `fix/...`, `chore/...`, `docs/...`.
- Para chegar no `main`: ReviewAgent aprova → testes passam → merge automático.
- Fluxo: Agent → feature branch → commit → `POST /review/submit` → ReviewQueue → ReviewService → APPROVE/REJECT.
- Antes de qualquer commit que altere o fluxo da aplicação, execute os testes Selenium relevantes localmente e só commit/push se os testes passarem.
- Sempre que uma mudança for testada e estiver OK localmente, efetue o auto-merge da branch correspondente.
- Nunca é aceitável quebrar pipelines no GitHub Actions; o código deve ser revisado para garantir que tudo funcione.

---

## 7. Deploy e CI/CD

### 7.1 Regras gerais
- Utilize GitHub Actions para operações de deploy.
- Distinga entre operações locais e operações no servidor.
- Faça backup dos arquivos importantes antes de qualquer operação crítica.
- Antes de aplicar qualquer configuração ou instalação, verifique se já não está presente para evitar sobrescrever projetos existentes.

### 7.2 GitHub Actions e self-hosted runner
- GitHub-hosted runners **NÃO** alcançam IPs privados (`192.168.*.*`). Para rede privada, instale um **self-hosted runner** no homelab.
- Secrets necessários no repo: `HOMELAB_HOST`, `HOMELAB_USER`, `HOMELAB_SSH_PRIVATE_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, `DEPLOY_SSH_KEY`.
- Workflow principal tenta self-hosted primeiro; fallback para GitHub-hosted (que não acessa rede privada).

### 7.3 Healthcheck
- Adote retry/backoff em scripts de deploy (serviço pode não estar pronto imediatamente após restart).
- Infra-sensitive checks (env-sync / deploy_interceptor) são não-fatais e geram artefatos para análise.

### 7.4 Rollback
```bash
cd $DEPLOY_PATH
git reflog  # encontrar commit anterior
git reset --hard <commit>
sudo systemctl restart <service>
```

### 7.5 Deploy diário
- 23:00 UTC: efetuar deploy da versão estável (validar que todos os testes passam antes).
- Sincronizar servidor via `git pull`, reiniciar serviços afetados, validar endpoints de saúde.

---

## 8. Testes

- `pytest -q` (padrão); use `-m integration` para testes que requerem serviços locais (API 8503), `-m external` para libs externas (chromadb, paramiko, playwright).
- Top-level test files ignorados por padrão; set `RUN_ALL_TESTS=1` para override.
- Selenium E2E: `pytest tests/test_site_selenium.py` — manter fallback selectors para mudanças de DOM.
- Para simular aprovação do Diretor: `tools/force_diretor_response.py` (local) ou `tools/consume_diretor_db_requests.py` (se `DATABASE_URL` set).

---

## 9. Docker e containers

- Cada linguagem usa imagem Docker específica (Python: `python:3.12-slim`, Node: `node:20-slim`, Go: `golang:1.22-alpine`, Rust: `rust:1.75-slim`, Java: `eclipse-temurin:21-jdk`, .NET: `dotnet/sdk:8.0`, PHP: `php:8.3-cli`).
- Limites de recursos: `--cpus`, `--memory`, `--memory-reservation`, `--memory-swap` (ver `DOCKER_RESOURCE_CONFIG`).
- Cleanup automático: containers removidos após 24h parados, dangling images removidas, projetos inativos 7+ dias arquivados, backup 3 dias.
- Dentro de containers Docker, use hostname do serviço (ex: `eddie-postgres:5432`), NUNCA `localhost`.

---

## 10. Lições aprendidas e safeguards críticos

### 10.1 OOM e exporters (RECOVERY_SUMMARY.md)
- **Sempre** use `LIMIT` em queries de exporters/métricas (sem LIMIT causou OOM no servidor).
- Intervalo mínimo de atualização para exporters: 60s.
- Monitore memória durante deployment; catch OOM cedo.
- Configure `MemoryLimit` no systemd para serviços de monitoramento.
- **Não reabilitar `agent-network-exporter`** sem as otimizações de LIMIT e MemoryLimit.

### 10.2 Grafana + Docker (LESSONS_LEARNED_2026-02-02.md)
- Datasource: use hostname do container (`eddie-postgres:5432`), nunca `localhost` dentro de Docker.
- Garanta que Grafana e Postgres estejam na mesma rede Docker.

### 10.3 Pipelines e rede privada
- Para rede privada, use runner self-hosted ou túnel público controlado (Cloudflare Tunnel).
- Fly.io foi removido por custo, complexidade e risco de segredo vazado; preferir `cloudflared`.

### 10.4 Scripts idempotentes
- Scripts devem ser idempotentes, dry-run por padrão, e requerer confirmação explícita para ações destrutivas.
- Documentar rollback e fornecer health checks como artefatos de primeira classe.

### 10.5 SSH e acesso remoto
- **Nunca** alterar `/etc/ssh/sshd_config` remotamente sem mecanismo de rollback automático (ex: `at` ou `cron`).
- Manter `cloudflared` ativo como backup de acesso.
- Firewall iptables pode bloquear SSH silenciosamente — validar conectividade sempre.

### 10.6 Selenium e validação de UI
- Manter seletores expandidos (detectar tabelas modernas: `[role="table"]`, `[data-testid*="table"]`).
- Adicionar esperas explícitas para elementos dinâmicos.

### 10.7 Imports e módulos
- Fazer auditoria de importações em caso de crash/white screen.
- Adicionar testes de carregamento do Streamlit no CI/CD.
- Health checks automáticos para dashboards.

---

## 11. Organização e hierarquia de agentes

### 11.1 Níveis de gestão
- **Diretor** (C-Level): políticas globais, aprovação de contratações, prioridades estratégicas.
- **Superintendentes** (VP-Level): Engineering, Operations, Documentation, Investments, Finance.
- **Coordenadores** (Manager-Level): Development, DevOps, Quality, Knowledge, Trading, Treasury.
- **Agents**: executam tarefas de acordo com sua especialização.

### 11.2 Regras obrigatórias (TEAM_BACKLOG.md)
1. **Commit obrigatório** após testes com sucesso (`feat|fix|test|refactor: descrição curta`).
2. **Deploy diário** às 23:00 UTC da versão estável.
3. **Fluxo completo**: Análise → Design → Código → Testes → Deploy.
4. **Máxima sinergia**: comunicar via Communication Bus, não duplicar trabalho.
5. **Especialização**: cada agente na sua linguagem/função.
6. **Auto-scaling**: CPU < 50% → aumentar workers; CPU > 85% → serializar; max = `min(CPU_cores * 2, 16)`.

### 11.3 RACI simplificado
- Diretor: responsável por regras e aprovações.
- Coordenador: supervisiona pipeline e valida entregas.
- Agent: executa tarefas e documenta.

---

## 12. Sistema distribuído e precisão

- Coordenador distribuído roteia tarefas entre Copilot e agentes homelab baseado em score de precisão.
- Score ≥ 95% → Copilot 10% (confiável); 85-94% → 25%; 70-84% → 50%; < 70% → 100% Copilot.
- Feedback de cada tarefa atualiza o score. Toda tarefa **deve** registrar sucesso/falha.
- Endpoints: `GET /distributed/precision-dashboard`, `POST /distributed/route-task`, `POST /distributed/record-result`.

---

## 13. Interceptor de conversas

- Captura automática via bus → SQLite/cache → 3 interfaces (API, Dashboard, CLI).
- Detecta 8 fases: INITIATED, ANALYZING, PLANNING, CODING, TESTING, DEPLOYING, COMPLETED, FAILED.
- 25+ endpoints API em `/interceptor/*`.
- W ebSocket para tempo real: `ws://localhost:8503/interceptor/ws/conversations`.
- Performance: 100+ msgs/segundo, buffer circular 1000 msgs, queries <100ms.

---

## 14. Variáveis de ambiente essenciais

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `OLLAMA_HOST` | Servidor LLM | `http://192.168.15.2:11434` |
| `GITHUB_AGENT_URL` | Helper GitHub local | `http://localhost:8080` |
| `DATABASE_URL` | Postgres para IPC/memória | `postgresql://postgres:eddie_memory_2026@localhost:5432/postgres` |
| `DATA_DIR` | Diretório de dados do interceptor | `specialized_agents/interceptor_data/` |
| `REMOTE_ORCHESTRATOR_ENABLED` | Habilita orquestração remota | `false` |
| `ONDEMAND_ENABLED` | Sistema on-demand de componentes | `true` |

---

## 15. Troubleshooting rápido

| Problema | Solução |
|----------|---------|
| `specialized-agents-api` não inicia | `.venv/bin/pip install paramiko` + `sudo systemctl restart specialized-agents-api` |
| Bot Telegram não responde | Verificar token, verificar conectividade com Ollama, verificar logs `journalctl -u eddie-telegram-bot -f` |
| API retorna 500 | Reiniciar service, verificar dependências, verificar porta `lsof -i :8503` |
| Ollama não conecta | Verificar `systemctl status ollama`, firewall `ufw allow 11434/tcp`, configurar `OLLAMA_HOST=0.0.0.0` |
| RAG sem resultados | Verificar coleções ChromaDB, `mkdir -p chroma_db`, `pip install sentence-transformers` |
| GitHub push falha | Token inválido/expirado; verificar permissões `repo`, `workflow` |
| Tunnel OpenWebUI inacessível | Verificar `openwebui-ssh-tunnel.service` ou config `cloudflared` em `site/deploy/` |
| Dashboard white screen | Auditar imports (`grep -r "from dev_agent" . --include="*.py"`), reiniciar Streamlit |
| Conflito de portas | `sudo ss -ltnp | grep <porta>` → `sudo kill <pid>`, ou usar systemd |
| SQLite corrompido | Remover `.db` — será recriado automaticamente |
| Ping agent sem resposta | Verificar `/tmp/agent_ping_results.txt` |

---

## 16. Recovery do homelab

Prioridade de métodos quando SSH está indisponível:
1. Wake-on-LAN (`recover.sh --wol`)
2. Agents API via tunnel (`recover.sh --api`)
3. Open WebUI code exec (`recover.sh --webui`)
4. Telegram Bot command (`recover.sh --telegram`)
5. GitHub Actions self-hosted runner (dispatch workflow)
6. USB Recovery (acesso físico)

---

## 17. Monitoramento e alertas

- Monitore uso de CPU, memória e disco: `htop`, `docker stats`, `df -h`.
- Configure alertas no Telegram para problemas críticos.
- Cron job para backups: `0 2 * * *` com retenção de 30 dias.
- Validação contínua de landing pages com `validation_scheduler.py`.
- Logs: `journalctl -u <service-name> -f`.
- CI artifacts: health logs em `sre-health-logs` do GitHub Actions.

---

## 18. Higiene e manutenção

- Mantenha o ambiente saneado: remova dependências e arquivos desnecessários.
- Documente todas as alterações feitas no servidor (instalações, atualizações, configurações).
- Mantenha SO e softwares atualizados com patches de segurança.
- Realize auditorias de segurança periódicas.
- Limpar Docker: `docker system prune -a` quando necessário.
- Cleanup automático de containers (24h), images (dangling), projetos (7+ dias inativos).
- Remover backups antigos: `find /home/homelab/backups -type d -mtime +30 -exec rm -rf {} \;`.

---

## 19. Gestão de incidentes (ITIL v4)

1. **Detecção e Registro**: identificar erro e registrar ticket imediatamente.
2. **Categorização e Priorização**: baseada em Impacto × Urgência.
3. **Investigação e Diagnóstico**: análise técnica, root cause.
4. **Resolução e Recuperação**: workaround ou fix.
5. **Encerramento**: validação com usuário + documentação na base de conhecimento.
- Sempre documentar lições aprendidas após incidentes.
- Manter Known Error Database (KEDB) atualizada.

---

## 20. Referências rápidas

- **Documentação geral**: `docs/confluence/pages/OPERATIONS.md`
- **Arquitetura**: `docs/ARCHITECTURE.md`, `docs/confluence/pages/ARCHITECTURE.md`
- **Secrets**: `docs/SECRETS.md`, `docs/VAULT_README.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`
- **Quality Gate**: `docs/REVIEW_QUALITY_GATE.md`, `docs/REVIEW_SYSTEM_USAGE.md`
- **Agent Memory**: `docs/AGENT_MEMORY.md`
- **Server Config**: `docs/SERVER_CONFIG.md`
- **Deploy homelab**: `docs/DEPLOY_TO_HOMELAB.md`
- **Lições aprendidas**: `docs/LESSONS_LEARNED_2026-02-02.md`, `docs/LESSONS_LEARNED_FLYIO_REMOVAL.md`
- **Operações estendidas**: `.github/copilot-instructions-extended.md`
- **Setup geral**: `docs/SETUP.md`
- **Team Structure**: `TEAM_STRUCTURE.md`, `TEAM_BACKLOG.md`
- **Interceptor**: `INTERCEPTOR_README.md`, `INTERCEPTOR_SUMMARY.md`
- **Distributed System**: `DISTRIBUTED_SYSTEM.md`
- **Recovery**: `tools/homelab_recovery/README.md`, `RECOVERY_SUMMARY.md`
- **ITIL**: `PROJECT_MANAGEMENT_ITIL_BEST_PRACTICES.md`
