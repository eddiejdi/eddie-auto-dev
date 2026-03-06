# Review Queue

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/review_queue.py`
- **Última modificação**: 2026-02-09T19:58:12.779119
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Review Queue — Fila centralizada de commits aguardando aprovação

Padrão: Agent cria trabalho → commit em branch feature → fila de review
        ReviewAgent aprova → merge automático para main

Persi

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
from specialized_agents.review_queue import ReviewQueue

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