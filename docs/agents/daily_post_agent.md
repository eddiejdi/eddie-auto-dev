# Daily Post Agent

## Informações Básicas
- **Tipo**: agent
- **Arquivo**: `estou-aqui/tests/linkedin/daily_post_agent.py`
- **Última modificação**: 2026-02-20T22:53:23.237502
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
LinkedIn daily-post agent (API-first).

- Objetivo: garantir pelo menos 1 post diário para o perfil pessoal do admin e para a Company Page (rpa4all).
- Estratégia: usar LinkedIn REST API (/v2/ugcPosts

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
from estou-aqui.tests.linkedin.daily_post_agent import DailyPostAgent

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