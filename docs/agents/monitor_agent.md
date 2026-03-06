# Monitor Agent

## Informações Básicas
- **Tipo**: agent
- **Arquivo**: `btc_trading_agent/monitor_agent.py`
- **Última modificação**: 2026-02-28T09:52:46.810558
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Monitor de Status do Agente de Trading (PostgreSQL)

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
from btc_trading_agent.monitor_agent import MonitorAgent

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