# Bpm Agent

## Informações Básicas
- **Tipo**: agent
- **Arquivo**: `specialized_agents/bpm_agent.py`
- **Última modificação**: 2026-02-05T00:30:08.731171
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
Agente Especializado em BPM e Desenhos Técnicos

Especialidades:
- Business Process Management (BPM/BPMN 2.0)
- Desenhos técnicos e diagramas
- Draw.io (diagrams.net) - geração de arquivos .drawio
- F

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
from specialized_agents.bpm_agent import BpmAgent

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