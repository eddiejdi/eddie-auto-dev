# Homelab Advisor Agent

Consultor especializado para o servidor homelab com integração ao Communication Bus e suporte a IPC.

## Funcionalidades

### 1. **Análise de Performance**
- Monitora CPU, memória, disco
- Identifica gargalos
- Recomenda otimizações específicas

### 2. **Análise de Segurança**
- Audita portas abertas
- Identifica riscos
- Sugere safeguards e configurações de firewall

### 3. **Revisão de Arquitetura**
- Analisa containers Docker ativos
- Revisa serviços systemd
- Sugere melhorias de arquitetura para performance, resiliência e escalabilidade

### 4. **Treinamento de Agentes Locais**
- Coleta tarefas resolvidas
- Armazena training samples em formato JSONL
- Permite retreinamento automático de agentes

### 5. **Integração com Barramento**
- Conecta ao `AgentCommunicationBus` (in-process)
- Suporta IPC via Postgres (`agent_ipc`)
- Responde a requisições de outros agentes
- Worker assíncrono processa requests IPC a cada 5s

## Instalação

```bash
cd /home/edenilson/shared-auto-dev/homelab_copilot_agent

# Criar venv (se não existir)
python3 -m venv .venv

# Instalar dependências do advisor
.venv/bin/pip install -r requirements_advisor.txt
```

## Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `OLLAMA_HOST` | URL do servidor Ollama | `http://192.168.15.2:11434` |
| `OLLAMA_MODEL` | Modelo LLM para análises | `shared-homelab:latest` |
| `DATABASE_URL` | PostgreSQL para IPC | `postgresql://...` |
| `PORT` | Porta HTTP do agente | `8085` |

### Exemplo `.env`

```bash
OLLAMA_HOST=http://192.168.15.2:11434
OLLAMA_MODEL=shared-homelab:latest
DATABASE_URL=postgresql://postgres:shared_memory_2026@192.168.15.2:5432/postgres
PORT=8085
```

## Execução

### Standalone (sem barramento)

```bash
cd /home/edenilson/shared-auto-dev/homelab_copilot_agent
OLLAMA_HOST='http://192.168.15.2:11434' OLLAMA_MODEL='llama3.2:3b' \
  .venv/bin/python advisor_agent.py
```

### Com barramento (integrado ao projeto principal)

```bash
cd /home/edenilson/shared-auto-dev/homelab_copilot_agent
source /home/edenilson/shared-auto-dev/.venv/bin/activate  # venv do projeto principal
export DATABASE_URL='postgresql://postgres:shared_memory_2026@192.168.15.2:5432/postgres'
export OLLAMA_HOST='http://192.168.15.2:11434'
export OLLAMA_MODEL='shared-homelab:latest'

python advisor_agent.py
```

## Endpoints da API

### Health Check
```bash
curl -sS http://localhost:8085/health
```

### Análise de Performance
```bash
curl -sS -X POST http://localhost:8085/analyze \
  -H 'Content-Type: application/json' \
  -d '{"scope":"performance"}'
```

### Análise de Segurança
```bash
curl -sS -X POST http://localhost:8085/analyze \
  -H 'Content-Type: application/json' \
  -d '{"scope":"security"}'
```

### Revisão de Arquitetura
```bash
curl -sS -X POST http://localhost:8085/analyze \
  -H 'Content-Type: application/json' \
  -d '{"scope":"architecture"}'
```

### Análise Combinada (Safeguards)
```bash
curl -sS -X POST http://localhost:8085/analyze \
  -H 'Content-Type: application/json' \
  -d '{"scope":"safeguards"}'
```

### Treinar Agente Local
```bash
curl -sS -X POST http://localhost:8085/train \
  -H 'Content-Type: application/json' \
  -d '{
    "agent_name": "python-agent",
    "task_description": "Otimizar query PostgreSQL lenta",
    "solution": "Adicionado índice na coluna user_id e otimizado JOIN",
    "metadata": {"execution_time_before": "2.5s", "execution_time_after": "0.3s"}
  }'
```

### Geração Genérica (compatibilidade)
```bash
curl -sS -X POST http://localhost:8085/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Como otimizar performance de um servidor homelab?","max_tokens":300}'
```

### Publicar no Bus (teste)
```bash
curl -sS -X POST http://localhost:8085/bus/publish?source=test&target=advisor&content=Teste%20de%20mensagem&message_type=REQUEST
```

## Integração com Outros Agentes

### Via Communication Bus (in-process)

```python
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

bus = get_communication_bus()
bus.publish(
    message_type=MessageType.REQUEST,
    source="python-agent",
    target="homelab-advisor",
    content="Preciso de ajuda para otimizar performance",
    metadata={"context": "high_cpu"}
)
```

### Via IPC (cross-process)

```python
from tools.agent_ipc import publish_request, poll_response

# Publicar request
req_id = publish_request(
    source="python-agent",
    target="homelab-advisor",
    content="Analisar segurança do servidor",
    metadata={"priority": "high"}
)

# Aguardar resposta
response = poll_response(req_id, timeout=60)
if response:
    print("Resposta:", response['response'])
```

## Deploy no Homelab

### Via Docker Compose

Adicionar ao `docker-compose.yml` do projeto:

```yaml
  homelab-advisor:
    build:
      context: ./homelab_copilot_agent
      dockerfile: Dockerfile.advisor
    image: homelab-advisor:latest
    container_name: homelab-advisor
    restart: unless-stopped
    ports:
      - "8085:8085"
    environment:
      - PORT=8085
      - OLLAMA_HOST=http://192.168.15.2:11434
      - OLLAMA_MODEL=shared-homelab:latest
      - DATABASE_URL=postgresql://postgres:shared_memory_2026@shared-postgres:5432/postgres
    networks:
      - shared-network
```

### Build (BuildKit / buildx recomendado) ⚠️

O builder legado está deprecado — use BuildKit quando disponível. Para builds locais no homelab prefira este script que tenta `buildx` e faz fallback seguro:

```bash
# no diretório homelab_copilot_agent/
./build.sh            # usa Docker BuildKit/buildx quando possível
./build.sh Dockerfile homelab-copilot-agent:latest
```

Se o host não tiver `buildx` instalado o script tentará `DOCKER_BUILDKIT=1 docker build` antes de usar o builder legado. Para ambientes CI/automação, instale/active `buildx` e/ou exporte `DOCKER_BUILDKIT=1` para eliminar mensagens de depreciação.
### Configurar Prometheus

Adicionar ao `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'homelab-advisor'
    static_configs:
      - targets: ['localhost:8085', '192.168.15.2:8085']
    metrics_path: '/metrics'
    scrape_interval: 15s
    scrape_timeout: 5s
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
```

### Dashboard no Grafana

1. **Importar Dashboard**:
   - Copiar `grafana_dashboard.json` para o servidor
   - Abrir `http://grafana:3000` → Dashboards → New → Import
   - Fazer upload do arquivo JSON
   - Selecionar datasource Prometheus

2. **Visualizações disponíveis**:
   - Status do agente (up/down)
   - Taxa de requisições HTTP (Req/s)
   - Taxa de erros (5xx errors)
   - Tempo de resposta mediano (p50)
   - Uso de CPU do servidor
   - Uso de memória do servidor
   - Uso de disco
   - Endpoints mais chamados (pie chart)
   - Análises completadas (24h)
   - Agentes treinados (24h)
   - Requisições IPC pendentes
   - Latência média das análises
   - Histórico de requisições HTTP (tabela)

3. **Alertas recomendados**:
   ```yaml
   - alert: HomelabAdvisorDown
     expr: up{job="homelab-advisor"} == 0
     for: 1m
     annotations:
       summary: "Homelab Advisor está offline"
   
   - alert: HomelabAdvisorHighErrorRate
     expr: rate(http_requests_total{job="homelab-advisor",status=~"5.."}[5m]) > 0.1
     for: 5m
     annotations:
       summary: "Taxa de erro alta no Advisor"
   
   - alert: HomelabAdvisorHighLatency
     expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="homelab-advisor"}[5m])) > 5
     for: 5m
     annotations:
       summary: "Latência alta no Advisor"
   ```

### Via systemd

Criar `/etc/systemd/system/homelab-advisor.service`:

```ini
[Unit]
Description=Homelab Advisor Agent
After=network.target postgresql.service

[Service]
Type=simple
User=homelab
WorkingDirectory=/home/homelab/shared-auto-dev/homelab_copilot_agent
Environment=OLLAMA_HOST=http://192.168.15.2:11434
Environment=OLLAMA_MODEL=shared-homelab:latest
Environment=DATABASE_URL=postgresql://postgres:shared_memory_2026@localhost:5432/postgres
Environment=PORT=8085
ExecStart=/home/homelab/shared-auto-dev/.venv/bin/python advisor_agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Ativar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable homelab-advisor
sudo systemctl start homelab-advisor
sudo systemctl status homelab-advisor
```

## Métricas e Monitoramento

### Prometheus Metrics

O agente expõe as seguintes métricas no endpoint `/metrics`:

**HTTP:**
- `http_requests_total` - Total de requisições por endpoint/método/status
- `http_request_duration_seconds` - Histograma de latência por endpoint/método

**Análises:**
- `advisor_analysis_total` - Total de análises completadas por scope
- `advisor_analysis_duration_seconds` - Histograma de duração das análises

**Treinamento:**
- `advisor_agents_trained_total` - Total de agentes treinados por nome

**IPC:**
- `advisor_ipc_pending_requests` - Gauge com número de IPC pendentes

**LLM:**
- `advisor_llm_calls_total` - Total de chamadas ao LLM por status
- `advisor_llm_duration_seconds` - Histograma de duração das chamadas LLM

### Dashboard Grafana

Um dashboard completo está incluído no arquivo `grafana_dashboard.json` com:
- Cards de status (up/down, Req/s, Erros, Latência p50)
- Gráficos de recursos (CPU, Memória, Disco)
- Análise de endpoints mais usados
- KPIs de análises e treinamento
- Tabela de histórico de requisições

### Verificar Métricas Localmente

```bash
# Ver todas as métricas
curl -sS http://localhost:8085/metrics | grep advisor

# Ver uma métrica específica
curl -sS http://localhost:8085/metrics | grep "http_requests_total"

# Com formatting (requer jq)
curl -sS http://localhost:8085/metrics | grep "^advisor_" | head -20

# Usar script de teste
bash test_prometheus.sh http://localhost:8085
```

### Alertas Recomendados

Configurar no Alertmanager/Prometheus:

- ⚠️ Agente offline `up{job="homelab-advisor"} == 0` por 1min
- 🔴 Taxa de erro alta `rate(http_requests_total{status=~"5.."}[5m]) > 0.1` por 5min
- 🟡 Latência alta `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5s` por 5min
- 📦 IPC backlog `advisor_ipc_pending_requests > 10` por 2min

## Modelos Ollama Recomendados

Para um advisor eficiente, use modelos especializados:

- `shared-homelab:latest` (customizado para o ambiente)
- `qwen2.5-coder:7b` (análise de código e configuração)
- `llama3.2:3b` (rápido para consultas gerais)
- `shared-assistant:latest` (assistant geral treinado)

## Logs e Monitoramento

```bash
# Logs do agente
sudo journalctl -u homelab-advisor -f

# Métricas de saúde
curl -sS http://localhost:8085/health | jq

# Verificar IPC pendente (se DATABASE_URL configurado)
psql $DATABASE_URL -c "SELECT * FROM agent_ipc WHERE target='homelab-advisor' AND status='pending';"
```

## Desenvolvimento

### Testes Locais

```bash
# Instalar dependências de dev+test
.venv/bin/pip install -r requirements_advisor.txt
.venv/bin/pip install pytest httpx pytest-asyncio

# Rodar testes (criar test_advisor.py)
.venv/bin/pytest tests/test_advisor.py -v
```

### Adicionar Nova Análise

1. Implementar método `async def analyze_X(self, context)` na classe `HomelabAdvisor`
2. Adicionar case no endpoint `/analyze`
3. Documentar no README
4. Adicionar testes

## Considerações de Segurança

- O agente tem acesso elevado ao sistema (psutil, subprocess)
- Use em rede privada ou com autenticação adequada
- Valide inputs antes de executar comandos shell
- Monitore logs para detecção de uso anômalo
- Rotacione credenciais do `DATABASE_URL` regularmente

## Licença

MIT License - Shared Homelab © 2026
