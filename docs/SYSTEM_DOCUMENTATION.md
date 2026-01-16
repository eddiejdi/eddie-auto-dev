# 📚 Eddie Auto-Dev - Documentação do Sistema

> **Status**: 🔄 Em Construção
> **Última Atualização**: 2025-01-16
> **Responsáveis**: ConfluenceAgent, BPMAgent, RequirementsAnalyst

---

## 📋 Índice

1. [Visão Geral do Sistema](#visão-geral-do-sistema)
2. [Arquitetura](#arquitetura)
3. [Componentes](#componentes)
4. [Agents e Responsabilidades](#agents-e-responsabilidades)
5. [Fluxos de Trabalho](#fluxos-de-trabalho)
6. [APIs e Integrações](#apis-e-integrações)
7. [Regras de Negócio](#regras-de-negócio)
8. [Runbooks Operacionais](#runbooks-operacionais)

---

## 🎯 Visão Geral do Sistema

### Propósito
Eddie Auto-Dev é um sistema de desenvolvimento automatizado baseado em múltiplos agents de IA especializados, organizados em squads seguindo Team Topologies.

### Missão
Automatizar o ciclo completo de desenvolvimento de software: análise de requisitos, design, codificação, testes e deploy.

---

## 🏗️ Arquitetura

> 🔄 _Seção será preenchida pelo BPMAgent com diagramas_

### Diagrama de Arquitetura
📊 [Ver Diagrama no Draw.io](../diagrams/arquitetura_eddie_auto_dev.drawio)

### Componentes Principais
| Componente | Descrição | Porta |
|------------|-----------|-------|
| Telegram Bot | Interface principal com usuário | - |
| FastAPI | API dos agents especializados | 8503 |
| Ollama | LLM local | 11434 |
| RAG (ChromaDB) | Base de conhecimento | - |
| Streamlit | Dashboards | 8501-8502 |

---

## 🤖 Agents e Responsabilidades

> 🔄 _Seção será preenchida após entrevistas com cada agent_

### Entrevistas Pendentes

- [ ] PythonAgent
- [ ] JavaScriptAgent
- [ ] TypeScriptAgent
- [ ] GoAgent
- [ ] RustAgent
- [ ] JavaAgent
- [ ] CSharpAgent
- [ ] PHPAgent
- [ ] TestAgent
- [ ] RequirementsAnalyst
- [ ] ConfluenceAgent
- [ ] BPMAgent
- [ ] InstructorAgent
- [ ] OperationsAgent
- [ ] SecurityAgent
- [ ] GitHubAgent
- [ ] DataAgent
- [ ] PerformanceAgent

---

## 🔄 Fluxos de Trabalho

> 🔄 _Seção será preenchida pelo BPMAgent_

### Fluxo Principal
📊 [Ver Diagrama BPMN](../diagrams/fluxo_principal_eddie.drawio)

### Fluxos por Squad
- [ ] Development Flow
- [ ] Quality Flow
- [ ] Operations Flow
- [ ] Documentation Flow

---

## 🔌 APIs e Integrações

> 🔄 _Seção será preenchida após análise de código_

### Endpoints Disponíveis
| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/health` | GET | Health check |
| `/agents` | GET | Lista agents |
| `/generate_code` | POST | Gera código |
| `/security/scan` | POST | Scan de segurança |
| `/data/pipeline` | POST | Pipeline de dados |
| `/performance/load-test` | POST | Teste de carga |

---

## 📜 Regras de Negócio

### Regras Globais (0-8)
| Regra | Nome | Descrição |
|-------|------|-----------|
| 0 | Pipeline | Análise → Design → Código → Testes → Deploy |
| 0.1 | Economia de Tokens | Preferir Ollama local |
| 0.2 | Validação | Sempre testar antes de entregar |
| 1 | Commit | Obrigatório após testes |
| 2 | Deploy Diário | 23:00 UTC versão estável |
| 3 | Fluxo Completo | Cada agent completa sua fase |
| 4 | Sinergia | Comunicação via Bus |
| 5 | Especialização | Team Topologies |
| 6 | Auto-Scaling | CPU-based scaling |
| 7 | Herança | Novos agents herdam regras |
| 8 | Sync Nuvem | Draw.io e Confluence na nuvem |

---

## 📖 Runbooks Operacionais

> 🔄 _Seção será preenchida pelo OperationsAgent_

### Runbooks Pendentes
- [ ] Deploy Manual
- [ ] Rollback de Emergência
- [ ] Restart de Serviços
- [ ] Troubleshooting de Agents
- [ ] Backup e Recovery

---

## 📊 Métricas e KPIs

> 🔄 _Seção será preenchida após análise_

---

## 📝 Changelog

| Data | Versão | Autor | Alteração |
|------|--------|-------|-----------|
| 2025-01-16 | 0.1.0 | ConfluenceAgent | Estrutura inicial criada |

---

_Documentação gerada automaticamente por Eddie Auto-Dev_
_Sincronizado com GitHub: ✅_
