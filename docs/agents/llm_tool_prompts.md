# Llm Tool Prompts

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/llm_tool_prompts.py`
- **Última modificação**: 2026-03-01T20:13:03.450074
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
LLM Tool Prompts — System prompts que instruem o modelo Ollama
a usar ferramentas de terminal em vez de retornar instruções manuais.

Uso:
    from specialized_agents.llm_tool_prompts import get_tool_

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
from specialized_agents.llm_tool_prompts import LlmToolPrompts

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