# Agent Openwebui Bridge

## Informações Básicas
- **Tipo**: agent
- **Arquivo**: `specialized_agents/agent_openwebui_bridge.py`
- **Última modificação**: 2026-02-01T19:00:26.274177
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Agent bridge: consume LLM requests from the Agent Communication Bus and
call OpenWebUI (fallback to Ollama when configured). Publishes LLM responses
back to the bus.

## Funcionalidades
- _(Listar funcionalidades principais)_

## Configuração
### Variáveis de Ambiente
```bash
# Configure as variáveis necessárias
export AGENT_CONFIG="value"
```

### Parâmetros
_(Documente os parâmetros de entrada/saída)_

## Uso
```python
from specialized_agents.agent_openwebui_bridge import AgentOpenwebuiBridge

# Exemplo de uso
```

## Secrets/Credenciais

Nenhum secret detectado automaticamente.

## Integração com Message Bus
_(Documente como este agente se comunica com o message bus)_

```python
# Publicar mensagem
self.bus.publish('agent_name', 'channel', {'data': 'value'})

# Escutar mensagens
self.bus.register_listener('agent_name', self.on_message)
```

## Troubleshooting
_(Soluções para problemas comuns)_

## Referências
- [Agent Communication Bus](../ARCHITECTURE.md#message-bus)
- [Secrets Agent](../SECRETS_MANAGEMENT.md)