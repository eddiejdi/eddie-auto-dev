# X Agent

## Informações Básicas
- **Tipo**: agent
- **Arquivo**: `tools/x_agent/x_agent.py`
- **Última modificação**: 2026-02-23T23:45:05.660141
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
X Agent — serviço FastAPI para interação com X.com (Twitter).

Funcionalidades:
  - Postar tweets (texto, com imagem)
  - Ler timeline (home, user)
  - Buscar tweets por query/hashtag
  - Gerenciar in

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
from tools.x_agent.x_agent import XAgent

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