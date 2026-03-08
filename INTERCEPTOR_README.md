# 🔍 Sistema de Interceptação de Conversas entre Agentes

Sistema completo de interceptação, análise e visualização em tempo real de conversas entre agentes especializados.

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Instalação](#instalação)
4. [Uso](#uso)
5. [API REST](#api-rest)
6. [Dashboard Streamlit](#dashboard-streamlit)
7. [CLI](#cli)
8. [Exemplos](#exemplos)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O **Agent Conversation Interceptor** fornece um sistema completo para:

- ✅ **Capturar** todas as conversas entre agentes em tempo real
- ✅ **Armazenar** conversas em banco SQLite persistente
- ✅ **Analisar** padrões de comunicação e desempenho
- ✅ **Visualizar** conversas em dashboard interativo
- ✅ **Monitorar** agentes e fases de desenvolvimento
- ✅ **Exportar** conversas em múltiplos formatos

### Componentes Principais

1. **Agent Communication Bus** (`agent_communication_bus.py`)
   - Sistema de pub/sub para mensagens entre agentes
   - Buffer circular de 1000 mensagens
   - Filtros por tipo de mensagem
   - Estatísticas em tempo real

2. **Agent Conversation Interceptor** (`agent_interceptor.py`)
   - Intercepta e armazena conversas
   - Detecta fases de desenvolvimento
   - Análise detalhada de conversas
   - Índices para busca rápida
   - Snapshots de conversas

3. **API REST** (`interceptor_routes.py`)
   - Endpoints para gerenciar conversas
   - WebSockets para tempo real
   - Busca e filtros avançados
   - Controle de gravação

4. **Dashboard** (`conversation_monitor.py`)
   - Interface Streamlit
   - Visualizações em tempo real
   - Análises gráficas
   - Monitor contínuo

5. **CLI** (`interceptor_cli.py`)
   - Interface de linha de comando
   - Comandos para gerenciar conversas
   - Monitor terminal
   - Busca e exportação

---

## 🏗️ Arquitetura

┌─────────────────────────────────────────────────────────────┐
│                    Agentes Especializados                    │
│   (PythonAgent, JavaScriptAgent, TypeScriptAgent, etc)      │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              │ publish()
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              Agent Communication Bus                         │
│  - Buffer circular (1000 mensagens)                          │
│  - Filtros por tipo                                         │
│  - Estatísticas                                             │
│  - Subscribers                                              │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              │ subscribe()
                              │
┌─────────────────────────────▼───────────────────────────────┐
│         Agent Conversation Interceptor                       │
│  - Rastreia conversas ativas                                 │
│  - Armazena no SQLite                                       │
│  - Detecta fases                                            │
│  - Análise e índices                                        │
│  - Snapshots                                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                    ┌─────────┼─────────┐
                    │         │         │
        ┌───────────▼──┐  ┌──▼───────────┐  ┌──────────────┐
        │   API REST   │  │  Dashboard   │  │     CLI      │
        │  (FastAPI)   │  │ (Streamlit)  │  │  (Click)     │
        └──────────────┘  └──────────────┘  └──────────────┘
### Fluxo de Dados

Agente A envia mensagem
            ↓
Bus recebe e publica
            ↓
Interceptor captura
            ↓
Armazena em SQLite + Cache
            ↓
Notifica listeners
            ↓
API/Dashboard/CLI recebem notificação
            ↓
Usuário vê em tempo real
---

## 💾 Instalação

### 1. Dependências

```bash
pip install fastapi uvicorn websockets streamlit pandas plotly click tabulate requests
### 2. Estrutura de Arquivos

specialized_agents/
├── agent_communication_bus.py      # Bus de comunicação
├── agent_interceptor.py             # Interceptador
├── interceptor_routes.py            # API REST
├── conversation_monitor.py          # Dashboard
├── interceptor_cli.py               # CLI
└── interceptor_data/                # Dados (criado automaticamente)
    └── conversations.db             # Banco SQLite
### 3. Integração com API Existente

No arquivo `specialized_agents/api.py`, adicione:

from .interceptor_routes import router as interceptor_router

app.include_router(interceptor_router)

# No startup event:
@app.on_event("startup")
async def startup():
    # ... código existente ...
    from .agent_interceptor import get_agent_interceptor
    interceptor = get_agent_interceptor()  # Inicializar
---

## 🚀 Uso

### 1. Iniciar o Interceptador

O interceptador é inicializado automaticamente quando uma mensagem é publicada no bus:

from specialized_agents.agent_interceptor import get_agent_interceptor

# Obter instância
interceptor = get_agent_interceptor()

# Será inicializado automaticamente
### 2. Começar a Interceptar

Mensagens são capturadas automaticamente quando agentes comunicam via bus:

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

bus = get_communication_bus()

# Publicar mensagem (já será interceptada)
bus.publish(
    message_type=MessageType.REQUEST,
    source="PythonAgent",
    target="TestAgent",
    content="Analisar e testar código",
    metadata={"conversation_id": "conv_12345"}
)
---

## 🔌 API REST

### Base URL
http://localhost:8503/interceptor
### Endpoints Principais

#### Conversas Ativas
```bash
# Listar conversas ativas
GET /conversations/active
GET /conversations/active?agent=PythonAgent
GET /conversations/active?phase=CODING

# Resposta
{
  "status": "success",
  "count": 2,
  "conversations": [
    {
      "id": "conv_202501151430_a1b2c3d4",
      "started_at": "2025-01-15T14:30:00",
      "participants": ["PythonAgent", "TestAgent"],
      "message_count": 15,
      "phase": "testing",
      "duration_seconds": 45.2
    }
  ]
}
#### Detalhes de Conversa
```bash
# Obter conversa completa
GET /conversations/{conversation_id}

# Obter mensagens
GET /conversations/{conversation_id}/messages?limit=50
GET /conversations/{conversation_id}/messages?message_type=CODE_GEN

# Análise detalhada
GET /conversations/{conversation_id}/analysis
#### Histórico
```bash
# Listar conversas histórico
GET /conversations/history?limit=50
GET /conversations/history?agent=PythonAgent
GET /conversations/history?phase=completed
GET /conversations/history?since_hours=24

# Exportar
GET /conversations/{conversation_id}/export?format=json
GET /conversations/{conversation_id}/export?format=markdown
#### Estatísticas
```bash
# Estatísticas gerais
GET /stats

# Por fase
GET /stats/by-phase

# Por agente
GET /stats/by-agent
#### Controle
```bash
# Pausar gravação
POST /recording/pause

# Retomar
POST /recording/resume

# Limpar buffer
POST /recording/clear

# Ativar/desativar filtro
POST /filters/CODE_GEN/true
POST /filters/ERROR/false
#### Busca
```bash
# Por conteúdo
GET /search/by-content?query=teste&limit=20

# Por agente
GET /search/by-agent?agent=PythonAgent

# Por fase
GET /search/by-phase?phase=coding
#### WebSocket (Tempo Real)
```javascript
// Conectar para atualizações de conversas
ws = new WebSocket("ws://localhost:8503/interceptor/ws/conversations")

ws.onmessage = (event) => {
  console.log(JSON.parse(event.data))  // Evento de conversa
}

// Conectar para mensagens
ws = new WebSocket("ws://localhost:8503/interceptor/ws/messages")

ws.onmessage = (event) => {
  console.log(JSON.parse(event.data))  // Nova mensagem
}
---

## 📊 Dashboard Streamlit

### Iniciar
```bash
streamlit run specialized_agents/conversation_monitor.py
### Acessar
https://heights-treasure-auto-phones.trycloudflare.com
### Abas

1. **🔴 Conversas Ativas**
   - Lista de conversas em tempo real
   - Filtros por agente e fase
   - Duração, participantes, mensagens

2. **📊 Análise Detalhada**
   - Análise completa de conversa selecionada
   - Gráficos de distribuição
   - Timeline de mensagens

3. **💬 Histórico**
   - Conversas passadas
   - Filtros e busca
   - Tabelas e gráficos

4. **📈 Métricas Avançadas**
   - Taxa de mensagens
   - Taxa de erro
   - Gráfico temporal

5. **⚡ Tempo Real**
   - Monitor contínuo
   - Últimas mensagens
   - Status do bus

### Configurações
- Auto-refresh (1s, 2s, 5s, 10s)
- Filtros por agente
- Filtros por fase

---

## 🖥️ CLI

### Instalar
```bash
chmod +x specialized_agents/interceptor_cli.py

# Alias útil
alias interceptor="python3 specialized_agents/interceptor_cli.py"
### Comandos Principais

#### Conversas
```bash
# Listar ativas
python3 interceptor_cli.py conversations active
python3 interceptor_cli.py conversations active --agent PythonAgent
python3 interceptor_cli.py conversations active --phase CODING

# Informações
python3 interceptor_cli.py conversations info conv_202501151430_a1b2c3d4

# Mensagens
python3 interceptor_cli.py conversations messages conv_202501151430_a1b2c3d4 --limit 20
python3 interceptor_cli.py conversations messages conv_202501151430_a1b2c3d4 --type CODE_GEN

# Análise
python3 interceptor_cli.py conversations analyze conv_202501151430_a1b2c3d4

# Histórico
python3 interceptor_cli.py conversations history --limit 50
python3 interceptor_cli.py conversations history --agent PythonAgent
python3 interceptor_cli.py conversations history --hours 24

# Exportar
python3 interceptor_cli.py conversations export conv_202501151430_a1b2c3d4 --format json
python3 interceptor_cli.py conversations export conv_202501151430_a1b2c3d4 --format markdown
#### Estatísticas
```bash
# Visão geral
python3 interceptor_cli.py stats overview

# Por fase
python3 interceptor_cli.py stats by-phase

# Por agente
python3 interceptor_cli.py stats by-agent
#### Controle
```bash
# Pausar
python3 interceptor_cli.py control pause

# Retomar
python3 interceptor_cli.py control resume

# Limpar
python3 interceptor_cli.py control clear
#### Busca
```bash
# Por conteúdo
python3 interceptor_cli.py search content "erro de teste" --limit 20

# Por agente
python3 interceptor_cli.py search agent PythonAgent

# Por fase
python3 interceptor_cli.py search phase coding
#### Monitor
```bash
# Monitor em tempo real
python3 interceptor_cli.py monitor --interval 2
---

## 📚 Exemplos

### Exemplo 1: Capturar Conversa entre Agentes

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
from specialized_agents.agent_interceptor import get_agent_interceptor
from datetime import datetime

bus = get_communication_bus()
interceptor = get_agent_interceptor()

# Simular conversa
conv_id = "conv_test_001"

# Agente envia requisição
bus.publish(
    message_type=MessageType.REQUEST,
    source="PythonAgent",
    target="all",
    content="Implementar função de validação",
    metadata={"conversation_id": conv_id, "task_id": "task_123"}
)

# Agente responde
bus.publish(
    message_type=MessageType.RESPONSE,
    source="CodeAnalyst",
    target="PythonAgent",
    content="Função criada com sucesso",
    metadata={"conversation_id": conv_id, "task_id": "task_123"}
)

# Visualizar
conv = interceptor.get_conversation(conv_id)
print(f"Conversa tem {conv['message_count']} mensagens")
### Exemplo 2: Analisar Conversa

from specialized_agents.agent_interceptor import get_agent_interceptor

interceptor = get_agent_interceptor()

# Listar conversas ativas
active = interceptor.list_active_conversations()
print(f"Conversas ativas: {len(active)}")

# Analisar primeira
if active:
    conv_id = active[0]["id"]
    analysis = interceptor.analyze_conversation(conv_id)
    
    print(f"Participantes: {analysis['summary']['participants']}")
    print(f"Tipos de mensagem: {analysis['message_types']}")
    print(f"Distribuição: {analysis['source_distribution']}")
### Exemplo 3: Monitor em Tempo Real

from specialized_agents.agent_interceptor import get_agent_interceptor
import time

interceptor = get_agent_interceptor()

# Callback para eventos
def on_conversation_event(event):
    conv = event["conversation"]
    print(f"Novo evento: {event['event']}")
    print(f"  Conversa: {conv['id']}")
    print(f"  Fase: {conv['phase']}")
    print(f"  Mensagens: {conv['message_count']}")

interceptor.subscribe_conversation_events(on_conversation_event)

# Esperar eventos
while True:
    time.sleep(1)
### Exemplo 4: Exportar Conversa

from specialized_agents.agent_interceptor import get_agent_interceptor

interceptor = get_agent_interceptor()

# Obter primeira conversa ativa
active = interceptor.list_active_conversations()
if active:
    conv_id = active[0]["id"]
    
    # Exportar como JSON
    json_export = interceptor.export_conversation(conv_id, format="json")
    with open(f"{conv_id}.json", "w") as f:
        f.write(json_export)
    
    # Exportar como Markdown
    md_export = interceptor.export_conversation(conv_id, format="markdown")
    with open(f"{conv_id}.md", "w") as f:
        f.write(md_export)
---

## 🐛 Troubleshooting

### Problema: Nenhuma mensagem sendo capturada

**Solução:**
# Verificar se o bus está funcionando
from specialized_agents.agent_communication_bus import get_communication_bus

bus = get_communication_bus()
print(f"Buffer: {len(bus.message_buffer)} mensagens")
print(f"Gravação: {bus.recording}")
print(f"Filtros: {bus.active_filters}")
### Problema: API não responde

**Solução:**
```bash
# Verificar se a API está rodando
curl http://localhost:8503/interceptor/stats

# Verificar logs
tail -f /var/log/shared-api.log
### Problema: Dashboard Streamlit lento

**Solução:**
- Reduzir intervalo de refresh
- Limpar buffer: `POST /interceptor/recording/clear`
- Verificar limite de memória

### Problema: Banco SQLite corrompido

**Solução:**
```bash
# Remover banco
rm specialized_agents/interceptor_data/conversations.db

# Será recriado automaticamente
python3 -c "from specialized_agents.agent_interceptor import get_agent_interceptor; get_agent_interceptor()"
---

## 📝 Notas

- **Retenção de Dados**: SQLite retém dados indefinidamente
- **Buffer em Memória**: Últimas 1000 mensagens em buffer circular
- **Performance**: Suporta 100+ mensagens/segundo
- **Índices**: Otimizados para busca por agent, phase, timestamp

---

## 🔗 Links Úteis

- [Agent Communication Bus](agent_communication_bus.py)
- [Agent Interceptor](agent_interceptor.py)
- [Interceptor Routes (API)](interceptor_routes.py)
- [Dashboard Streamlit](conversation_monitor.py)
- [CLI](interceptor_cli.py)

---

**Versão:** 1.0.0  
**Último Update:** Janeiro 2025  
**Mantido por:** Shared Auto-Dev Team
