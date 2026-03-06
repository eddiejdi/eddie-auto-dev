# Remote Orchestrator

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/remote_orchestrator.py`
- **Última modificação**: 2026-02-22T08:05:58.742416
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Orquestrador remoto via SSH para executar containers em um host remoto (ex: homelab)

Implementação mínima compatível com DockerOrchestrator usada pelo AgentManager.

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
from specialized_agents.remote_orchestrator import RemoteOrchestrator

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