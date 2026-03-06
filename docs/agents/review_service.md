# Review Service

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/review_service.py`
- **Última modificação**: 2026-02-09T19:58:12.827121
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Review Service Daemon — Processa fila de reviews continuamente

Ciclo:
1. Buscar próximos items da fila
2. Chamar ReviewAgent para análise
3. Se aprovado → executar testes automáticos (Selenium, integ

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
from specialized_agents.review_service import ReviewService

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