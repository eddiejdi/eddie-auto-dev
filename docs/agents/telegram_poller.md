# Telegram Poller

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/telegram_poller.py`
- **Última modificação**: 2026-02-01T19:00:26.282177
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Simple Telegram poller: periodically calls `getUpdates` on the bot,
publishes inbound messages to the Agent Communication Bus so the system
can react to messages sent to the bot.

This is intentionall

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
from specialized_agents.telegram_poller import TelegramPoller

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