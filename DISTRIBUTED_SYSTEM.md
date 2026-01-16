# Sistema Distribuído: Copilot + Agentes Especializados

## 📋 Visão Geral

Implementação de um **coordenador distribuído** que roteia tarefas de desenvolvimento entre:
- **Copilot (GitHub)**: Para análise, design, supervisão
- **Agentes Especializados (Homelab)**: Para execução quando confiáveis

## 🎯 Objetivo

Reduzir progressivamente a dependência do Copilot à medida que os agentes especializados ganham **precisão e confiabilidade**.

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│              COORDENADOR DISTRIBUÍDO                     │
│  (distributed_coordinator.py)                           │
└─────────────────────────────────────────────────────────┘
         ↓                                    ↓
    ┌────────────┐                  ┌──────────────────┐
    │  Copilot   │                  │   Homelab        │
    │  (GitHub)  │◄────────────────►│   Agentes        │
    └────────────┘                  │ - Python Agent   │
    - Análise                       │ - JS Agent       │
    - Design                        │ - Go Agent       │
    - Supervisão                    │ - Rust Agent     │
    - Validação                     │ - TypeScript     │
                                    │ - Java           │
                                    └──────────────────┘
                                    Execução distribuída
```

## 📊 Sistema de Precisão

Cada agente tem um **score de precisão** baseado em:

```
Precisão = (Tarefas Bem-Sucedidas / Total de Tarefas) * 100
```

### Uso do Copilot por Precisão

| Precisão | Copilot | Recomendação |
|----------|---------|---|
| ≥ 95% | 10% | 🟢 Confiável - Usar agente com validação mínima |
| 85-94% | 25% | 🟡 Bom - Usar agente com validação ocasional |
| 70-84% | 50% | 🟠 Aceitável - Usar agente com validação frequente |
| < 70% | 100% | 🔴 Baixo - Usar Copilot para todas as tarefas |

## 🔄 Fluxo de Roteamento

```
1. Tarefa chega para linguagem L
   ↓
2. Buscar score de precisão de L
   ↓
3. Se precisão ≥ 70%
   → Tenta executar com Agente
   → Se sucesso: registra vitória
   → Se falha: fallback para Copilot + registra falha
   ↓
4. Se precisão < 70%
   → Executa diretamente com Copilot
   ↓
5. Feedback atualiza score de precisão
```

## 📈 Endpoints da API

### Dashboard de Precisão
```bash
GET /distributed/precision-dashboard
```

Retorna status de todos os agentes:
```json
{
  "timestamp": "2026-01-15T23:06:07...",
  "agents": [
    {
      "language": "python",
      "precision": "85.5%",
      "total_tasks": 42,
      "successful": 36,
      "failed": 6,
      "copilot_usage": "25%",
      "recommendation": "🟡 Bom - Usar agente com validação ocasional"
    }
  ]
}
```

### Rotear Tarefa
```bash
POST /distributed/route-task?language=python
Content-Type: application/json

{
  "task": "implementar função de validação",
  "type": "code"
}
```

### Registrar Resultado
```bash
POST /distributed/record-result?language=python&success=true&execution_time=2.5
```

## 📊 Monitoramento

### Verificar Status de um Agente
```bash
GET /distributed/agent-stats/python
```

### Histórico de Tarefas
```
Database: specialized_agents/agent_rag/precision_scores.db

Tabelas:
- agent_scores: Score atual de cada agente
- task_history: Histórico de todas as execuções
```

## 🔧 Integração Homelab

A API local (8503) se conecta ao homelab em **192.168.15.2:8503**

Linguagens disponíveis:
- Python
- JavaScript
- TypeScript
- Go
- Rust
- Java
- C#
- PHP

## 🚀 Estratégia de Melhoria Contínua

### Fase 1: Bootstrapping (Agora)
- Todos os agentes usam 100% Copilot
- Precisão < 70%
- Copilot avalia resultados

### Fase 2: Confiança Inicial (próximas semanas)
- Agentes com > 70% precisão começam a executar
- Copilot monitora e valida resultados
- Feedback atualiza scores

### Fase 3: Autonomia (próximos meses)
- Agentes com > 85% precisão executam com liberdade
- Copilot apenas supervisiona
- Sistema auto-aprende

### Fase 4: Mastery (longo prazo)
- Agentes > 95% precisão são totalmente autônomos
- Copilot apenas em casos complexos
- Sistema opera em auto-modo

## 📝 Exemplo de Uso

```python
from specialized_agents.distributed_coordinator import get_distributed_coordinator

coordinator = get_distributed_coordinator()

# Rotear uma tarefa
result = await coordinator.route_task(
    language="python",
    task={
        "description": "Implementar função de busca",
        "context": "Projeto X"
    }
)

# Ver dashboard
dashboard = coordinator.get_precision_dashboard()
print(dashboard)
```

## 🎯 Objetivos de Precisão

- **Python Agent**: Target 95% (crítico para projeto)
- **JavaScript Agent**: Target 90% (frontend)
- **Go Agent**: Target 85% (microserviços)
- **Rust Agent**: Target 80% (performance)

## 📌 Notas Importantes

1. **Feedback é crítico**: Toda tarefa executada deve registrar sucesso/falha
2. **Tolerância a falhas**: Agentes podem falhar, sistema fallback para Copilot
3. **Aprendizado contínuo**: Scores atualizados em tempo real
4. **Auditoria**: Histórico completo em SQLite para análise

## 🔗 Referências

- [Interceptor de Conversas](INTERCEPTOR_README.md) - Para auditar comunicações
- [Coordenador Distribuído](specialized_agents/distributed_coordinator.py) - Implementação
- [Rotas Distribuídas](specialized_agents/distributed_routes.py) - API REST
