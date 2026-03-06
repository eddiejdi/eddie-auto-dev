# Llm Tool Schemas

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/llm_tool_schemas.py`
- **Última modificação**: 2026-03-01T20:13:03.462074
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
LLM Tool Schemas — Definições de ferramentas no formato nativo Ollama.

Fornece schemas compatíveis com o parâmetro `tools` do endpoint /api/chat
do Ollama, seguindo o padrão OpenAI Function Calling.


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
from specialized_agents.llm_tool_schemas import LlmToolSchemas

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