# Advisor Agent

## Informações Básicas
- **Tipo**: agent
- **Arquivo**: `homelab_copilot_agent/advisor_agent.py`
- **Última modificação**: 2026-02-22T14:30:25.032801
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Homelab Advisor Agent
Consultor especialista para o servidor homelab conectado ao barramento.
Integrado com: IPC (PostgreSQL), Scheduler periódico, API principal (8503).

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
from homelab_copilot_agent.advisor_agent import AdvisorAgent

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