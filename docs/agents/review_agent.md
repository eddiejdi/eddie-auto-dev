# Review Agent

## Informações Básicas
- **Tipo**: agent
- **Arquivo**: `specialized_agents/review_agent.py`
- **Última modificação**: 2026-02-09T19:58:12.779119
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
ReviewAgent — Agente especializado em Quality Gate + CI/CD Review

Responsabilidades:
1. Validar código (estilo, segurança, duplicação, complexidade)
2. Executar testes (unit, E2E com Selenium, integr

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
from specialized_agents.review_agent import ReviewAgent

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