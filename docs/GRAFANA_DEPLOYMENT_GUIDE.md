# Grafana Dashboards - Deployment Guide (PROD)

**Status**: ✅ Completed  
**Data**: 2026-02-02  
**Ambiente**: Homelab Production (192.168.15.2:3002)  
**Responsável**: Eddie Auto-Dev  

---

## 📋 Sumário Executivo

Deploy completo de **5 dashboards do Grafana** em ambiente de produção, incluindo:
- Provisionamento de 2 datasources (Prometheus + PostgreSQL)
- Infraestrutura PostgreSQL containerizada com dados de teste
- Automação via GitHub Actions
- Resolução de 4 bloqueadores técnicos críticos

**Resultado**: Todos os painéis estão visíveis e funcionais em http://192.168.15.2:3002

---

## 🎯 Objetivos Alcançados

| # | Objetivo | Status | Detalhes |
|---|----------|--------|----------|
| 1 | Export de dashboards de localhost | ✅ | 4 dashboards exportados como JSON |
| 2 | Deploy em PROD Grafana | ✅ | 5 dashboards visíveis (4 novos + 1 existente) |
| 3 | Provisão datasource Prometheus | ✅ | UID: dfc0w4yioe4u8e, health: OK |
| 4 | Provisão datasource PostgreSQL | ✅ | UID: cfbzi6b6m5gcgb, health: OK |
| 5 | Container eddie-postgres | ✅ | postgres:15-alpine em homelab_monitoring |
| 6 | Tabela bus_conversations | ✅ | Criada com 7 colunas + 4 índices |
| 7 | População de dados de teste | ✅ | 8 registros inseridos |

---

## 📊 Dashboards Implantados

### 1. Eddie Bus - Conversas em Tempo Real
- **ID**: 5
- **UID**: `eddie-bus-conversations`
- **Datasource**: PostgreSQL (cfbzi6b6m5gcgb)
- **Painéis**: 
  - Total de conversas
  - Conversas por tipo (request/response/error/info)
  - Timeline de conversas
  - Top sources (telegram/whatsapp/api/webhook)
- **Tags**: bus, conversations, eddie, realtime
- **URL**: http://192.168.15.2:3002/d/eddie-bus-conversations/

### 2. Eddie Bus - Monitor de Comunicação
- **ID**: 6
- **UID**: `eddie-bus-monitor`
- **Datasource**: Prometheus (dfc0w4yioe4u8e)
- **Painéis**:
  - Throughput de mensagens por segundo
  - Latência P50/P95/P99
  - Error rate
  - Active connections
- **Tags**: bus, eddie, monitoring
- **URL**: http://192.168.15.2:3002/d/eddie-bus-monitor/

### 3. Eddie Bus - Conversas PostgreSQL
- **ID**: 7
- **UID**: `f6b4a21f-0cff-4522-9bde-00ab89033d22`
- **Datasource**: PostgreSQL (cfbzi6b6m5gcgb)
- **Painéis**:
  - Conversas por target (assistant/director/coder/reviewer)
  - Distribuição temporal
  - Tabela de últimas conversas
- **Tags**: bus, conversations, postgresql
- **URL**: http://192.168.15.2:3002/d/f6b4a21f-0cff-4522-9bde-00ab89033d22/

### 4. 🚀 Bus Conversations - Live
- **ID**: 4
- **UID**: `aec37891-acec-4d66-95dc-0c95e2598cea`
- **Datasource**: PostgreSQL (cfbzi6b6m5gcgb)
- **Painéis**:
  - Live stream de conversas (auto-refresh 5s)
  - Count de conversas em tempo real
  - Status de agents
- **Tags**: bus, conversations, realtime
- **URL**: http://192.168.15.2:3002/d/aec37891-acec-4d66-95dc-0c95e2598cea/

### 5. Evolução de Aprendizado - Homelab
- **ID**: 1 (já existente)
- **UID**: `learning-evolution`
- **Datasource**: PostgreSQL + Prometheus
- **Painéis**: Métricas de aprendizado de IA, Ollama models, etc.
- **Tags**: homelab, ia, learning, ollama
- **URL**: http://192.168.15.2:3002/d/learning-evolution/

---

## 🔌 Datasources

### Prometheus
```yaml
Name: Eddie Bus Prometheus
Type: prometheus
UID: dfc0w4yioe4u8e
URL: http://prometheus:9090
Access: proxy
Health: ✅ OK
```

**Métricas disponíveis**:
- `eddie_bus_messages_total{type="request|response|error"}`
- `eddie_bus_latency_seconds{quantile="0.5|0.95|0.99"}`
- `eddie_bus_active_connections`
- `eddie_bus_errors_total`

### PostgreSQL
```yaml
Name: Eddie Bus PostgreSQL
Type: grafana-postgresql-datasource
UID: cfbzi6b6m5gcgb
URL: eddie-postgres:5432
Database: eddie_bus
User: eddie
SSL Mode: disable
PostgreSQL Version: 15
Health: ✅ OK
```

**Tabelas**:
- `bus_conversations` (principal)
  - Colunas: id, timestamp, message_type, source, target, content, created_at
  - Índices: PK (id), timestamp DESC, source, message_type

---

## 🏗️ Infraestrutura

### Container: eddie-postgres

```bash
# Detalhes do container
Name: eddie-postgres
Image: postgres:15-alpine
Network: homelab_monitoring (172.21.0.0/16)
Port: 5432 (internal)
Volume: eddie_postgres_data:/var/lib/postgresql/data

# Variáveis de ambiente
POSTGRES_DB: eddie_bus
POSTGRES_USER: eddie
POSTGRES_PASSWORD: Eddie@2026
```

### Schema da Tabela bus_conversations

```sql
CREATE TABLE IF NOT EXISTS bus_conversations (
    id VARCHAR(100) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    message_type VARCHAR(50),
    source VARCHAR(100),
    target VARCHAR(100),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_conversations_timestamp ON bus_conversations(timestamp DESC);
CREATE INDEX idx_conversations_source ON bus_conversations(source);
CREATE INDEX idx_conversations_type ON bus_conversations(message_type);
```

### Arquitetura de Rede

```
┌─────────────────────────────────────────────────────────────┐
│          homelab_monitoring (172.21.0.0/16)                 │
│                                                               │
│  ┌─────────────┐       ┌──────────────┐       ┌──────────┐ │
│  │   Grafana   │◄─────►│  Prometheus  │       │ eddie-   │ │
│  │ (127.0.0.1  │       │ :9090        │       │ postgres │ │
│  │   :3002)    │       └──────────────┘       │  :5432   │ │
│  └──────┬──────┘                              └─────▲────┘ │
│         │                                            │      │
│         └────────────────────────────────────────────┘      │
│              Query: eddie-postgres:5432/eddie_bus           │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Port forwarding
                           ▼
                  192.168.15.2:3002
                  (Acesso externo)
```

---

## 🚀 Processo de Deployment

### 1. Workflow GitHub Actions

**Arquivo**: `.github/workflows/deploy-grafana-dashboard.yml`

```yaml
name: Deploy Grafana Dashboard
on:
  workflow_dispatch:
    inputs:
      host:
        description: 'Homelab host'
        required: true
        default: '192.168.15.2'
      user:
        description: 'SSH user'
        required: true
        default: 'homelab'

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      
      - name: Setup SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.HOMELAB_SSH_PRIVATE_KEY }}" > /tmp/ssh_key
          chmod 600 /tmp/ssh_key
      
      - name: Ensure eddie-postgres
        env:
          GRAFANA_PG_USER: ${{ secrets.GRAFANA_PG_USER }}
          GRAFANA_PG_PASS: ${{ secrets.GRAFANA_PG_PASS }}
        run: |
          ssh -i /tmp/ssh_key homelab@${{ inputs.host }} \
            "docker run -d --name eddie-postgres \
             --network homelab_monitoring \
             -e POSTGRES_DB=eddie_bus \
             -e POSTGRES_USER=$GRAFANA_PG_USER \
             -e POSTGRES_PASSWORD=$GRAFANA_PG_PASS \
             -v eddie_postgres_data:/var/lib/postgresql/data \
             postgres:15-alpine || docker start eddie-postgres"
          
          # Wait for readiness
          ssh -i /tmp/ssh_key homelab@${{ inputs.host }} \
            "for i in {1..20}; do \
               docker exec eddie-postgres pg_isready -U eddie && break; \
               sleep 3; \
             done"
          
          # Create table
          ssh -i /tmp/ssh_key homelab@${{ inputs.host }} \
            "docker exec eddie-postgres psql -U eddie -d eddie_bus \
             -c 'CREATE TABLE IF NOT EXISTS bus_conversations (...)'"
      
      - name: Deploy dashboards
        env:
          GRAFANA_USER: ${{ secrets.GRAFANA_USER }}
          GRAFANA_PASS: ${{ secrets.GRAFANA_PASS }}
          GRAFANA_HOST: ${{ inputs.host }}
          GRAFANA_PORT: 3002
        run: |
          python3 populate_grafana_dashboard.py
```

### 2. Scripts Python

#### populate_grafana_dashboard.py
```python
def ensure_prometheus_datasource():
    """Cria ou atualiza datasource Prometheus"""
    payload = {
        "name": "Eddie Bus Prometheus",
        "type": "prometheus",
        "uid": "dfc0w4yioe4u8e",
        "url": "http://prometheus:9090",
        "access": "proxy",
        "isDefault": False
    }
    # POST /api/datasources
    
def ensure_postgres_datasource():
    """Cria ou atualiza datasource PostgreSQL"""
    payload = {
        "name": "Eddie Bus PostgreSQL",
        "type": "grafana-postgresql-datasource",
        "uid": "cfbzi6b6m5gcgb",
        "url": "eddie-postgres:5432",
        "database": "eddie_bus",
        "user": os.getenv("GRAFANA_PG_USER"),
        "secureJsonData": {
            "password": os.getenv("GRAFANA_PG_PASS")
        }
    }
    # POST /api/datasources
```

#### populate_bus_conversations.py
```python
def populate_conversations():
    """Insere 8 conversas de teste"""
    conversations = [
        {
            'id': 'conv_001',
            'timestamp': datetime.now().isoformat(),
            'message_type': 'request',
            'source': 'telegram',
            'target': 'assistant',
            'content': 'Sample conversation 1'
        },
        # ... mais 7 conversas
    ]
    
    # SSH exec: docker exec eddie-postgres psql ...
    # INSERT INTO bus_conversations VALUES (...)
```

---

## 🐛 Bloqueadores Resolvidos

### 1. Datasources Ausentes em PROD
**Problema**: Dashboards exportados tinham UIDs de datasources que não existiam em PROD  
**Sintoma**: Painéis vazios, API `/api/datasources` retornava `[]`  
**Causa Raiz**: Export de localhost não inclui datasources  
**Solução**: Adicionar funções `ensure_*_datasource()` ao script de deploy  
**Commits**: 946dc83, 9590f32, 276c85e  

### 2. PostgreSQL Não Conectando
**Problema**: Datasource health check falhava com timeout  
**Sintoma**: `dial tcp 172.21.0.1:5432: connection timed out`  
**Causa Raiz**: Container eddie-postgres não existia  
**Solução**: 
- Adicionar step de SSH provisioning para criar container
- Alterar datasource host de IP (172.21.0.1) para hostname (eddie-postgres)
**Commits**: e897127  

### 3. Heredocs no GitHub Actions
**Problema**: Workflow falhava ao executar SQL via SSH  
**Sintoma**: `warning: here-document at line 1 delimited by end-of-file (wanted 'EOSSH')`  
**Causa Raiz**: Nested heredocs (SSH << EOF contendo psql << SQL) confundem parser bash  
**Solução**: Consolidar em single-line SSH command usando `psql -c`  
**Commits**: 635f504, 61e2e47, e897127, 117421c  

### 4. Tabela Não Persistia
**Problema**: Workflow executava sem erro mas tabela desaparecia  
**Sintoma**: `SELECT COUNT(*) FROM bus_conversations` → `ERROR: relation does not exist`  
**Causa Raiz**: SQL não executando corretamente ou container sem persistent volume  
**Solução**: 
- Usar flag `-v ON_ERROR_STOP=1` no psql
- Consolidar commands em single SSH execution
- Garantir volume persistente: `eddie_postgres_data:/var/lib/postgresql/data`
**Run que resolveu**: 21590140630 (conclusion: success)  

---

## 📖 Comandos Úteis

### Verificar Status do Grafana
```bash
# Listar todos os dashboards
curl -s -u admin:Eddie@2026 http://localhost:3002/api/search?query= | jq

# Listar datasources
curl -s -u admin:Eddie@2026 http://localhost:3002/api/datasources | jq

# Health check de datasource específico
curl -s -u admin:Eddie@2026 \
  http://localhost:3002/api/datasources/uid/cfbzi6b6m5gcgb/health | jq
```

### Acessar PostgreSQL
```bash
# Via SSH
ssh homelab@192.168.15.2 \
  "docker exec eddie-postgres psql -U eddie -d eddie_bus"

# Listar tabelas
ssh homelab@192.168.15.2 \
  "docker exec eddie-postgres psql -U eddie -d eddie_bus -c '\dt'"

# Ver dados
ssh homelab@192.168.15.2 \
  "docker exec eddie-postgres psql -U eddie -d eddie_bus \
   -c 'SELECT * FROM bus_conversations ORDER BY timestamp DESC LIMIT 5;'"
```

### Popular Dados Manualmente
```bash
# Executar script de população
python3 populate_bus_conversations.py

# Verificar contagem
ssh homelab@192.168.15.2 \
  "docker exec eddie-postgres psql -U eddie -d eddie_bus \
   -c 'SELECT COUNT(*) FROM bus_conversations;'"
```

### Re-deploy de Dashboard
```bash
# Trigger workflow via GitHub CLI
gh workflow run deploy-grafana-dashboard.yml \
  -f host=192.168.15.2 \
  -f user=homelab

# Ver status do run
gh run list --workflow=deploy-grafana-dashboard.yml --limit 1
gh run view <run_id> --log
```

---

## 🔐 Credenciais e Acessos

### Grafana PROD
- **URL**: http://192.168.15.2:3002
- **User**: admin
- **Password**: Eddie@2026
- **Storage**: Armazenado em Bitwarden (item: "Grafana Homelab Admin")

### PostgreSQL (eddie-postgres)
- **Host**: eddie-postgres (via Docker DNS) ou 172.21.0.X
- **Port**: 5432
- **Database**: eddie_bus
- **User**: eddie
- **Password**: Eddie@2026
- **Storage**: Armazenado em Bitwarden via GitHub Secrets (GRAFANA_PG_USER/GRAFANA_PG_PASS)

### SSH Homelab
- **Host**: 192.168.15.2
- **User**: homelab
- **Key**: Armazenado em GitHub Secrets (HOMELAB_SSH_PRIVATE_KEY)

---

## 📚 Referências

### Arquivos do Projeto
- Workflow: `.github/workflows/deploy-grafana-dashboard.yml`
- Dashboards: `grafana_dashboards/*.json`
- Scripts: `populate_grafana_dashboard.py`, `populate_bus_conversations.py`
- Relatório: `GRAFANA_DEPLOY_STATUS.md`

### GitHub Actions Runs
- Run 21590140630: Deploy completo com sucesso (2026-02-02)
- Run 21589913819: SSH key provisioning
- Run 21589514705: SQL validation com ON_ERROR_STOP

### Commits Relevantes
- fa5cd91: Add script to populate bus_conversations
- 117421c: Consolidated SSH provisioning
- e897127: Use psql -c (no heredocs)
- 6adfac8: Add dashboard exports

---

## 🚀 Próximos Passos

### Curto Prazo (1-2 semanas)
- [ ] Integrar dados reais do bus de conversações (Telegram, WhatsApp)
- [ ] Configurar alertas para anomalias em conversation rates
- [ ] Adicionar painéis de response time e error rates
- [ ] Implementar data retention policy (30 dias)

### Médio Prazo (1 mês)
- [ ] Backup automático do PostgreSQL (pg_dump diário)
- [ ] Adicionar métricas de performance de agents
- [ ] Heatmaps de conversas por hora/dia da semana
- [ ] Dashboard de análise de sentimento

### Longo Prazo (3 meses)
- [ ] Migrar para HA PostgreSQL (replicação)
- [ ] Adicionar tracing distribuído (Jaeger/Tempo)
- [ ] Dashboard de custo de operação (tokens, API calls)
- [ ] Machine learning para detecção de anomalias

---

## 👥 Contatos

- **Responsável Técnico**: Eddie Auto-Dev
- **Repositório**: https://github.com/eddiejdi/eddie-auto-dev
- **Documentação**: `/docs/` no repositório

---

**Última Atualização**: 2026-02-02  
**Versão**: 1.0  
**Status**: ✅ Produção
