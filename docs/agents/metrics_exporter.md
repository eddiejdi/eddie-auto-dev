# Metrics Exporter

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/metrics_exporter.py`
- **Última modificação**: 2026-02-02T11:52:54.156595
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Exportador de métricas Prometheus para o sistema de fallback distribuído.

Coleta métricas do agent communication bus, status dos agentes e recursos Docker.

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
from specialized_agents.metrics_exporter import MetricsExporter

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