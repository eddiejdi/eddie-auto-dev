# Dual Model Router

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/dual_model_router.py`
- **Última modificação**: 2026-02-28T23:02:58.839273
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Dual Model Router - Controller/Expert Architecture
Similar to Grok 4.1: qwen3:0.6b (Controller) routes tasks to qwen2.5-coder:7b (Expert)

Architecture:
- Controller (GTX 1050, port 11435): qwen3:0.6b

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
from specialized_agents.dual_model_router import DualModelRouter

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