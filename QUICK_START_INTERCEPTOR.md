# ⚡ Guia Rápido: Interceptação de Conversas

## 🎯 O que você pode fazer?

```bash
# Dashboard em tempo real
./start_interceptor_dashboard.sh
# Abre em https://heights-treasure-auto-phones.trycloudflare.com

# Visualizar conversas ativas
./interceptor conversations active

# Analisar conversa específica
./interceptor conversations analyze conv_202501151430_a1b2c3d4

# Monitor em tempo real
./interceptor monitor --interval 2

# Buscar por conteúdo
./interceptor search content "erro"

# Estatísticas por agente
./interceptor stats by-agent

# Exportar conversa
./interceptor conversations export conv_id --format markdown
---

## 📦 Instalação Rápida (2 minutos)

```bash
# 1. Executar setup
bash setup_interceptor.sh

# 2. Verificar instalação
./interceptor stats overview

# 3. Iniciar dashboard
./start_interceptor_dashboard.sh
---

## 🔌 Integração com API Existente

**Arquivo:** `specialized_agents/api.py`

Adicione no topo do arquivo:
from .interceptor_routes import router as interceptor_router
Adicione antes do `if __name__ == "__main__"`:
# Incluir rotas do interceptador
app.include_router(interceptor_router)

# No evento de startup
@app.on_event("startup")
async def startup_interceptor():
    from .agent_interceptor import get_agent_interceptor
    interceptor = get_agent_interceptor()
    logger.info("🔍 Interceptador inicializado")
---

## 🔗 Endpoints da API

### Conversas Ativas
```bash
curl http://localhost:8503/interceptor/conversations/active
curl http://localhost:8503/interceptor/conversations/active?agent=PythonAgent
### Estatísticas
```bash
curl http://localhost:8503/interceptor/stats
curl http://localhost:8503/interceptor/stats/by-phase
curl http://localhost:8503/interceptor/stats/by-agent
### Histórico
```bash
curl http://localhost:8503/interceptor/conversations/history?limit=50
curl http://localhost:8503/interceptor/conversations/history?since_hours=24
---

## 💻 Uso Programático

### Capturar Conversa
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

bus = get_communication_bus()

# Publicar mensagem (será interceptada automaticamente)
bus.publish(
    message_type=MessageType.REQUEST,
    source="MyAgent",
    target="OtherAgent",
    content="Conteúdo da mensagem",
    metadata={"conversation_id": "my_conv"}
)
### Acessar Conversas Interceptadas
from specialized_agents.agent_interceptor import get_agent_interceptor

interceptor = get_agent_interceptor()

# Listar ativas
active = interceptor.list_active_conversations()

# Obter conversa
conv = interceptor.get_conversation("conv_id")

# Analisar
analysis = interceptor.analyze_conversation("conv_id")

# Exportar
exported = interceptor.export_conversation("conv_id", format="json")
### Monitor em Tempo Real
interceptor = get_agent_interceptor()

def on_event(event):
    print(f"Nova mensagem: {event['message']['content']}")

interceptor.subscribe_conversation_events(on_event)

# Agora recebe notificações em tempo real
---

## 📊 Dashboard Streamlit

### Abas Disponíveis

1. **🔴 Conversas Ativas** - Monitorar em tempo real
2. **📊 Análise** - Análise detalhada de conversa
3. **💬 Histórico** - Conversas passadas
4. **📈 Métricas** - Gráficos e estatísticas
5. **⚡ Tempo Real** - Monitor contínuo

### Recursos

- 🔄 Auto-refresh configurável
- 🔍 Filtros por agente e fase
- 📈 Gráficos interativos
- 💾 Exportação de dados

---

## 🖥️ CLI - Comandos Principais

```bash
# Grupos de comandos
./interceptor conversations    # Gerenciar conversas
./interceptor stats            # Ver estatísticas
./interceptor search           # Buscar conversas
./interceptor control          # Controlar gravação
./interceptor monitor          # Monitor tempo real

# Exemplos
./interceptor conversations active
./interceptor conversations info conv_id
./interceptor conversations messages conv_id --limit 20
./interceptor conversations analyze conv_id
./interceptor conversations history --hours 24
./interceptor conversations export conv_id --format markdown

./interceptor stats overview
./interceptor stats by-phase
./interceptor stats by-agent

./interceptor search content "erro"
./interceptor search agent PythonAgent
./interceptor search phase coding

./interceptor control pause
./interceptor control resume
./interceptor control clear

./interceptor monitor --interval 2
---

## 🚀 Casos de Uso

### 1. Debugar Comunicação Entre Agentes
```bash
# Ver conversa específica
./interceptor conversations analyze conv_id

# Buscar erros
./interceptor search content "ERROR"

# Exportar para análise
./interceptor conversations export conv_id --format markdown > debug.md
### 2. Monitorar Performance
```bash
# Ver estatísticas
./interceptor stats overview

# Por agente
./interceptor stats by-agent

# Monitor em tempo real
./interceptor monitor
### 3. Auditar Desenvolvimento
```bash
# Histórico de 24h
./interceptor conversations history --hours 24

# Por fase
./interceptor search phase coding

# Por agente
./interceptor search agent PythonAgent
### 4. Análise de Padrões
```bash
# Conversas completadas
./interceptor search phase completed

# Análise detalhada
./interceptor conversations analyze conv_id
---

## 🔍 WebSocket Tempo Real

### JavaScript
```javascript
// Atualizações de conversas
const ws = new WebSocket("ws://localhost:8503/interceptor/ws/conversations")

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  console.log("Novo evento:", data)
}

// Atualizações de mensagens
const ws2 = new WebSocket("ws://localhost:8503/interceptor/ws/messages")

ws2.onmessage = (event) => {
  const msg = JSON.parse(event.data)
  console.log("Nova mensagem:", msg)
}
### Python
import asyncio
import websockets
import json

async def monitor():
    uri = "ws://localhost:8503/interceptor/ws/conversations"
    async with websockets.connect(uri) as websocket:
        while True:
            msg = await websocket.recv()
            event = json.loads(msg)
            print(f"Evento: {event}")

asyncio.run(monitor())
---

## 🛠️ Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| Nenhuma mensagem aparece | Verificar se agentes estão publicando no bus |
| Dashboard não carrega | Verificar porta 8501, iniciar com: `streamlit run ...` |
| API retorna 404 | Verificar se incluiu `interceptor_router` em `api.py` |
| Banco de dados corrompido | Remover `interceptor_data/conversations.db` |
| CLI não encontra API | Verificar se API está rodando em `localhost:8503` |

---

## 📈 Arquitetura

Agentes → Bus → Interceptador → Persistência
                      ↓
                ┌─────┼─────┐
                ↓     ↓     ↓
              API   Dashboard  CLI
---

## 🎓 Recursos

- 📖 [Documentação Completa](INTERCEPTOR_README.md)
- 🔧 [Code Source](specialized_agents/agent_interceptor.py)
- 💬 [Communication Bus](specialized_agents/agent_communication_bus.py)
- 🌐 [API Routes](specialized_agents/interceptor_routes.py)

---

## 🆘 Suporte

Verificar logs:
```bash
# API
tail -f /var/log/shared-api.log

# Dashboard
# Vê logs no terminal onde foi iniciado

# CLI
# Adicionar `-v` para verbose
./interceptor -v conversations active
---

**🎉 Pronto! Comece agora:**
```bash
bash setup_interceptor.sh
./start_interceptor_dashboard.sh
