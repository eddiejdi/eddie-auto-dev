# Agents Webui Bridge

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/agents_webui_bridge.py`
- **Última modificação**: 2026-02-27T16:56:35.525367
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Ponte de integração entre Agentes Especializados e OpenWebUI
Expõe todos os agentes como modelos disponíveis no WebUI
Permite que o WebUI chame agentes via API compatível com Ollama

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
from specialized_agents.agents_webui_bridge import AgentsWebuiBridge

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