**Homelab Agent**

Resumo de uso do agente que executa comandos remotos no homelab (SSH/API/VSCode).

O agente permite executar comandos em categorias como: `SYSTEM_INFO`, `DOCKER`, `SYSTEMD`, `NETWORK`, `FILES`, `PROCESS`, `LOGS`, `PACKAGE`, `CUSTOM`.

- **Obter instância (Python):**

```py
from specialized_agents.homelab_agent import get_homelab_agent

agent = get_homelab_agent()
# Em contexto async
result = await agent.execute("docker ps")
print(result)
health = await agent.server_health()
print(health)
```

- **Via API do serviço (porta 8503)**
  - Exemplo: executar um comando genérico via API (dependendo de como o endpoint está exposto no ambiente):

```bash
curl -X POST http://localhost:8503/homelab/execute \
  -H 'Content-Type: application/json' \
  -d '{"command":"docker ps","timeout":30}'
```

- **Comandos da extensão VS Code (`eddie-copilot`)**
  - `homelabExecute` — executar comando arbitrário
  - `homelabHealth` — checar saúde do servidor
  - `homelabDockerPs` — listar containers
  - `homelabDockerLogs` — obter logs de container
  - `homelabSystemdStatus` — checar status systemd de um serviço
  - `homelabLogs` — coletar logs do sistema

- **Variáveis de ambiente relevantes:**
  - `HOMELAB_HOST` — endereço do homelab (ex.: 192.168.15.2)
  - `HOMELAB_SSH` / `HOMELAB_SSH_KEY` — SSH user@host ou caminho para chave (quando aplicável)

- **Segurança / notas operacionais:**
  - O agente normalmente usa SSH/keys para executar comandos remotos; certifique-se de que a chave esteja autorizada no homelab.
  - Operações destrutivas (docker rm, systemctl restart) devem ser executadas com cuidado; prefira `--dry-run` quando disponível.

- **Referências no repositório:**
  - Ponto de uso e exemplos: `deploy_github_agent.sh`, `diagnose_phomemo_connection.py` e scripts que usam `HOMELAB_HOST`.

Se desejar, crio um exemplo de script `scripts/homelab_test.py` que roda checks básicos (docker ps, journalctl -n 50) e retorna um resumo.

Scripts úteis adicionados:

- `scripts/list_agents.py` — consulta `GET /agents` na API de agents e imprime a lista de agentes; use `--write` para salvar `eddie-copilot/known_agents.json` com a lista atual.
- `scripts/homelab_test.py` — executa checagens simples contra a API (`/health`, `/agents`, `/homelab/health`).

Exemplo:

```bash
# List agents and write known_agents.json
python scripts/list_agents.py --write

# Run basic homelab checks
python scripts/homelab_test.py
```
# 🖥️ Homelab Agent — Documentação Completa

Agente dedicado para execução remota de comandos no servidor homelab via SSH, com 3 camadas de segurança integradas.

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura de Segurança](#arquitetura-de-segurança)
- [Instalação e Configuração](#instalação-e-configuração)
- [Uso via Python](#uso-via-python)
- [API REST (porta 8503)](#api-rest-porta-8503)
- [VS Code Extension](#vs-code-extension)
- [Categorias de Comandos](#categorias-de-comandos)
- [Audit Log](#audit-log)
- [Testes](#testes)
- [Troubleshooting](#troubleshooting)

---

## Visão Geral

O **Homelab Agent** permite executar comandos no servidor homelab (`192.168.15.2`) de forma segura, via SSH (paramiko). Ele se integra ao ecossistema Eddie Auto-Dev através de:

- **Python API** — `get_homelab_agent()` retorna singleton do agente
- **FastAPI endpoints** — rotas `/homelab/*` na porta 8503
- **VS Code Extension** — 7 comandos no Command Palette
- **Communication Bus** — integração opcional com o barramento de mensagens

### Arquivos do projeto

| Arquivo | Descrição |
|---------|-----------|
| `specialized_agents/homelab_agent.py` | Agente principal (SSH, segurança, audit) — 784 linhas |
| `specialized_agents/homelab_routes.py` | Rotas FastAPI `/homelab/*` — 349 linhas |
| `tests/test_homelab_agent.py` | 28 testes unitários |
| `eddie-copilot/src/homelabAgentClient.ts` | Cliente TypeScript para extensão VS Code |

---

## Arquitetura de Segurança

### 3 Camadas de Proteção

```
Requisição → [1. IP Validation] → [2. Command Whitelist] → [3. Blocklist] → SSH Execute
                  │                      │                       │
                  ▼                      ▼                       ▼
            Só RFC 1918            Regex por categoria      Rejeita padrões
            + loopback             (8 categorias)           perigosos (20+)
```

#### 1. Validação de IP (RFC 1918)

Somente IPs de redes locais podem acessar:
- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`
- `127.0.0.0/8` (loopback)
- `169.254.0.0/16` (link-local)

```python
from specialized_agents.homelab_agent import is_local_ip

is_local_ip("192.168.15.100")  # True
is_local_ip("8.8.8.8")         # False
is_local_ip("127.0.0.1")       # True
```

#### 2. Whitelist de Comandos

Comandos são validados contra padrões regex agrupados por categoria. Só comandos que correspondem a pelo menos um padrão são executados.

#### 3. Blocklist Explícita

Padrões perigosos são **sempre** rejeitados, mesmo se baterem com a whitelist:
- `rm -rf /`, `rm -rf /*`
- `mkfs`, `dd if=`
- `:(){ :|:& };:` (fork bomb)
- `chmod 777 /`
- `shutdown`, `reboot`, `halt`, `poweroff`
- `> /dev/sda`, `/dev/null >`
- `curl | sh`, `wget | sh` (pipe to shell)
- E outros...

---

## Instalação e Configuração

### Pré-requisitos

1. **paramiko** instalado no venv:
   ```bash
   .venv/bin/pip install paramiko
   ```

2. **Acesso SSH** ao homelab:
   ```bash
   ssh-copy-id homelab@192.168.15.2
   # Ou garantir que ~/.ssh/id_rsa tenha acesso
   ```

3. **Serviço API** rodando:
   ```bash
   sudo systemctl start specialized-agents-api
   # Ou manualmente:
   source .venv/bin/activate
   uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503
   ```

### Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `HOMELAB_HOST` | `192.168.15.2` | IP do servidor homelab |
| `HOMELAB_USER` | `homelab` | Usuário SSH |
| `HOMELAB_SSH_KEY` | `~/.ssh/id_rsa` | Caminho da chave privada SSH |
| `DATA_DIR` | `./data` | Diretório para audit log |

Estas variáveis são lidas de `specialized_agents/config.py` → `REMOTE_ORCHESTRATOR_CONFIG`.

---

## Uso via Python

### Inicialização

```python
from specialized_agents.homelab_agent import get_homelab_agent

agent = get_homelab_agent()  # Singleton — sempre retorna a mesma instância
```

### Execução direta de comandos

```python
# Comando simples
result = await agent.execute("docker ps")
print(result.stdout)
print(result.success)       # True/False
print(result.exit_code)     # 0 = sucesso
print(result.duration_ms)   # Tempo de execução em ms

# Com timeout customizado
result = await agent.execute("docker logs my-container", timeout=60)

# Múltiplos comandos
for cmd in ["df -h", "free -m", "uptime"]:
    result = await agent.execute(cmd)
    print(f"{cmd}: {result.stdout}")
```

### Métodos de conveniência

```python
# Saúde completa do servidor
health = await agent.server_health()
# Retorna: {"hostname": "...", "uptime": "...", "cpu": "...", "memory": "...", "disk": "...", ...}

# Docker
containers = await agent.docker_ps()
logs = await agent.docker_logs("eddie-postgres", tail=100)
stats = await agent.docker_stats()

# Systemd
status = await agent.systemctl_status("eddie-telegram-bot")
result = await agent.systemctl_restart("specialized-agents-api")

# Sistema
disk = await agent.disk_usage()
memory = await agent.memory_usage()
uptime = await agent.uptime()

# Logs
logs = await agent.journalctl("eddie-telegram-bot", lines=50)
```

### Validação de comandos (sem executar)

```python
from specialized_agents.homelab_agent import classify_command

category = classify_command("docker ps")
# Retorna: CommandCategory.DOCKER

category = classify_command("rm -rf /")
# Retorna: None (bloqueado)
```

### Adicionar padrão customizado

```python
agent.add_custom_pattern(r"^my-custom-tool\s")
result = await agent.execute("my-custom-tool --status")
```

---

## API REST (porta 8503)

Todas as rotas estão sob `/homelab/*` e requerem que o caller esteja em rede local.

### Endpoints

#### Health & Info

```bash
# Health check do agente
curl http://localhost:8503/homelab/health

# Saúde completa do servidor
curl http://localhost:8503/homelab/server-health

# Comandos permitidos por categoria
curl http://localhost:8503/homelab/allowed-commands

# Últimas entradas do audit log
curl http://localhost:8503/homelab/audit?limit=20
```

#### Execução de Comandos

```bash
# Executar comando
curl -X POST http://localhost:8503/homelab/execute \
  -H 'Content-Type: application/json' \
  -d '{"command": "docker ps", "timeout": 30}'

# Validar comando (sem executar)
curl -X POST http://localhost:8503/homelab/validate-command \
  -H 'Content-Type: application/json' \
  -d '{"command": "docker ps"}'

# Adicionar padrão customizado
curl -X POST http://localhost:8503/homelab/allowed-commands/add \
  -H 'Content-Type: application/json' \
  -d '{"pattern": "^my-tool\\s", "category": "custom"}'
```

#### Docker

```bash
# Listar containers
curl http://localhost:8503/homelab/docker/ps

# Logs de container
curl -X POST http://localhost:8503/homelab/docker/logs \
  -H 'Content-Type: application/json' \
  -d '{"container": "eddie-postgres", "tail": 50}'

# Estatísticas
curl http://localhost:8503/homelab/docker/stats

# Reiniciar container
curl -X POST http://localhost:8503/homelab/docker/restart \
  -H 'Content-Type: application/json' \
  -d '{"container": "eddie-postgres"}'
```

#### Systemd

```bash
# Status de serviço
curl -X POST http://localhost:8503/homelab/systemd/status \
  -H 'Content-Type: application/json' \
  -d '{"service": "eddie-telegram-bot"}'

# Reiniciar serviço
curl -X POST http://localhost:8503/homelab/systemd/restart \
  -H 'Content-Type: application/json' \
  -d '{"service": "eddie-telegram-bot"}'

# Listar serviços ativos
curl http://localhost:8503/homelab/systemd/list

# Logs via journalctl
curl -X POST http://localhost:8503/homelab/systemd/logs \
  -H 'Content-Type: application/json' \
  -d '{"unit": "eddie-telegram-bot", "lines": 50}'
```

#### Sistema

```bash
curl http://localhost:8503/homelab/system/disk      # Uso de disco
curl http://localhost:8503/homelab/system/memory     # Uso de memória
curl http://localhost:8503/homelab/system/cpu        # Info de CPU
curl http://localhost:8503/homelab/system/network    # Interfaces de rede
curl http://localhost:8503/homelab/system/ports      # Portas abertas
```

### Modelos Pydantic

| Modelo | Campos | Uso |
|--------|--------|-----|
| `ExecuteRequest` | `command` (str), `timeout` (int, default 30) | POST /execute |
| `ExecuteResponse` | `success`, `command`, `stdout`, `stderr`, `exit_code`, `duration_ms`, `timestamp`, `error`, `category` | Resposta de /execute |
| `DockerLogsRequest` | `container` (str), `tail` (int, default 100) | POST /docker/logs |
| `ServiceRequest` | `service` (str) | POST /systemd/* |
| `JournalRequest` | `unit` (str), `lines` (int, default 50) | POST /systemd/logs |
| `ValidateCommandRequest` | `command` (str) | POST /validate-command |
| `AddPatternRequest` | `pattern` (str), `category` (str, default "custom") | POST /allowed-commands/add |

---

## VS Code Extension

### Configuração

Em `settings.json`:
```json
{
    "eddie-copilot.agentsApiUrl": "http://localhost:8503"
}
```

### Comandos disponíveis (Ctrl+Shift+P)

| Comando | ID | Descrição |
|---------|----|-----------|
| **Homelab: Executar Comando** | `eddie-copilot.homelabExecute` | Input box → executa comando → mostra resultado |
| **Homelab: Server Health** | `eddie-copilot.homelabHealth` | Exibe saúde completa do servidor |
| **Homelab: Docker PS** | `eddie-copilot.homelabDockerPs` | Lista containers Docker |
| **Homelab: Docker Logs** | `eddie-copilot.homelabDockerLogs` | Input: nome do container → mostra logs |
| **Homelab: Systemd Status** | `eddie-copilot.homelabSystemdStatus` | Input: nome do serviço → mostra status |
| **Homelab: Systemd Restart** | `eddie-copilot.homelabSystemdRestart` | Input: nome do serviço → reinicia |
| **Homelab: System Logs** | `eddie-copilot.homelabLogs` | Exibe logs recentes do sistema |

### Implementação

O cliente TypeScript (`homelabAgentClient.ts`) faz chamadas HTTP para a API na porta 8503. Resultados são exibidos no Output Channel "Eddie Homelab".

```typescript
import { HomelabAgentClient } from './homelabAgentClient';

const client = new HomelabAgentClient(config);
const health = await client.serverHealth();
const result = await client.execute("docker ps", 30);
const containers = await client.dockerPs();
```

---

## Categorias de Comandos

| Categoria | Exemplos de padrões aceitos |
|-----------|-----------------------------|
| `SYSTEM_INFO` | `uname`, `hostname`, `uptime`, `whoami`, `df`, `free`, `top -bn1`, `lscpu`, `cat /proc/*` |
| `DOCKER` | `docker ps`, `docker logs`, `docker stats`, `docker inspect`, `docker images`, `docker-compose` |
| `SYSTEMD` | `systemctl status/start/stop/restart/enable/disable`, `journalctl` |
| `NETWORK` | `ip addr`, `ss -tulnp`, `ping -c`, `curl`, `wget`, `dig`, `nslookup`, `traceroute`, `netstat` |
| `FILES` | `ls`, `cat`, `head`, `tail`, `wc`, `find`, `du`, `stat`, `file`, `md5sum`, `sha256sum` |
| `PROCESS` | `ps aux`, `pgrep`, `pidof`, `lsof`, `htop` |
| `LOGS` | `tail /var/log/*`, `cat /var/log/*`, `grep /var/log/*`, `dmesg`, `last`, `lastlog` |
| `PACKAGE` | `apt list`, `dpkg -l`, `snap list`, `pip list`, `npm list` |
| `CUSTOM` | Padrões adicionados via `add_custom_pattern()` |

---

## Audit Log

Todos os comandos (executados e bloqueados) são registrados em `DATA_DIR/homelab_audit.jsonl`:

```json
{
  "timestamp": "2026-07-15T10:30:00+00:00",
  "command": "docker ps",
  "caller_ip": "192.168.15.100",
  "success": true,
  "exit_code": 0,
  "duration_ms": 145.3,
  "blocked": false,
  "block_reason": null
}
```

Para consultar:
```bash
# Últimas 10 entradas
tail -10 data/homelab_audit.jsonl | jq .

# Via API
curl http://localhost:8503/homelab/audit?limit=10

# Apenas comandos bloqueados
cat data/homelab_audit.jsonl | jq 'select(.blocked == true)'
```

---

## Testes

### Executar testes

```bash
# Todos os testes do homelab agent (28 testes)
pytest tests/test_homelab_agent.py -v

# Apenas testes unitários (sem integration)
pytest tests/test_homelab_agent.py -v -m "not integration"

# Com cobertura
pytest tests/test_homelab_agent.py --cov=specialized_agents.homelab_agent
```

### Estrutura dos testes

| Classe | Qtd | Descrição |
|--------|-----|-----------|
| `TestIPValidation` | 9 | Validação de IPs RFC 1918, públicos, edge cases |
| `TestCommandValidation` | 11 | Whitelist, blocklist, categorias, padrões custom |
| `TestHomelabAgent` | 8 | Execução, timeout, retry, SSH mock |
| `TestHomelabAPI` | 4 | Endpoints FastAPI (marcados `@pytest.mark.integration`) |

---

## Troubleshooting

### SSH connection refused
```bash
# Verificar se sshd está rodando no homelab
ssh homelab@192.168.15.2 "echo ok"

# Testar chave SSH
ssh -i ~/.ssh/id_rsa homelab@192.168.15.2 "hostname"
```

### Comando bloqueado
```bash
# Verificar se o comando é permitido
curl -X POST http://localhost:8503/homelab/validate-command \
  -H 'Content-Type: application/json' \
  -d '{"command": "meu-comando-aqui"}'

# Se legítimo, adicionar padrão customizado
curl -X POST http://localhost:8503/homelab/allowed-commands/add \
  -H 'Content-Type: application/json' \
  -d '{"pattern": "^meu-comando", "category": "custom"}'
```

### 403 Forbidden na API
A requisição veio de IP externo (não RFC 1918). Se usando reverse proxy, garantir que os headers `X-Forwarded-For` ou `X-Real-IP` estejam configurados corretamente.

### paramiko não instalado
```bash
.venv/bin/pip install paramiko
sudo systemctl restart specialized-agents-api
```

### Audit log não registrando
Verificar que `DATA_DIR` existe e tem permissão de escrita:
```bash
mkdir -p data
ls -la data/homelab_audit.jsonl
```
