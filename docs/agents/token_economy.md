# Token Economy

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/token_economy.py`
- **Última modificação**: 2026-03-02T20:32:48.597416
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Token Economy Tracker
Rastreia economia de tokens entre Ollama LOCAL e APIs cloud.
Funciona de forma independente do bus — pode ser usado diretamente por qualquer agente
ou LLMClient, E também integra

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
from specialized_agents.token_economy import TokenEconomy

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