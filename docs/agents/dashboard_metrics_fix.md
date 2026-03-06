# Dashboard Metrics Fix

## Informações Básicas
- **Tipo**: specialized_agent
- **Arquivo**: `specialized_agents/dashboard_metrics_fix.py`
- **Última modificação**: 2026-02-14T12:10:54.673973
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Fix para métricas do dashboard - adiciona agent_active_count e agent_message_rate_per_second
Roda como endpoint adicional no agent-network-exporter

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
from specialized_agents.dashboard_metrics_fix import DashboardMetricsFix

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