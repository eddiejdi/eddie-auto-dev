# Agent Mixin

## Informações Básicas
- **Tipo**: agent
- **Arquivo**: `specialized_agents/jira/agent_mixin.py`
- **Última modificação**: 2026-02-09T14:41:59.854861
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Jira Agent Mixin — Integração dos agentes especializados com o Jira RPA4ALL.

Qualquer agente que herde este mixin ganha capacidade de:
  • Buscar seus tickets atribuídos (local + Jira Cloud)
  • Move

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
from specialized_agents.jira.agent_mixin import AgentMixin

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