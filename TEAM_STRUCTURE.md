# 🏢 Shared Auto-Dev - Estrutura Organizacional

## 📊 Visão Geral da Organização

                              ┌─────────────────┐
                              │    DIRETOR      │
                              │  (Estratégico)  │
                              └────────┬────────┘
                                       │
       ┌───────────────┬───────────────┼───────────────┬───────────────┐
       │               │               │               │               │
┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
│ SUPERINTEND │ │ SUPERINTEND │ │ SUPERINTEND │ │ SUPERINTEND │ │ SUPERINTEND │
│ Engineering │ │ Operations  │ │Documentation│ │ Investments │ │   Finance   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │               │               │
┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
│ COORDENADOR │ │ COORDENADOR │ │ COORDENADOR │ │ COORDENADOR │ │ COORDENADOR │
│ Development │ │   DevOps    │ │  Knowledge  │ │   Trading   │ │  Treasury   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │               │               │
   [Squads]        [Squads]        [Squads]        [Squads]        [Squads]
---

## 🎯 Níveis de Gestão

### 👔 DIRETOR (C-Level)
**Responsabilidades:**
- Definir políticas globais de agents
- Aprovar novas contratações
- Definir prioridades estratégicas
- Garantir compliance com as Regras 0-7
- Alocação de recursos (tokens, CPU, memória)

### 📋 SUPERINTENDENTES (VP-Level)
Supervisionam áreas funcionais:

| Superintendente | Área | Responsabilidades |
|-----------------|------|-------------------|
| **Engineering** | Desenvolvimento | Qualidade de código, arquitetura, code review |
| **Operations** | Infraestrutura | Deploy, monitoramento, SRE, segurança |
| **Documentation** | Conhecimento | Documentação, treinamento, padrões |
| **Investments** | Trading/Cripto | Estratégias de trading, backtest, gestão de risco |
| **Finance** | Tesouraria | Controle de capital, relatórios, compliance |

### 🎖️ COORDENADORES (Manager-Level)
Gerenciam squads específicos:

| Coordenador | Squad | Agents Supervisionados |
|-------------|-------|------------------------|
| **Development** | Code Squad | PythonAgent, JavaScriptAgent, TypeScriptAgent, GoAgent, RustAgent |
| **DevOps** | Ops Squad | OperationsAgent, GitHubAgent, DockerOrchestrator |
| **Quality** | QA Squad | TestAgent, RequirementsAnalyst |
| **Knowledge** | Docs Squad | ConfluenceAgent, BPMAgent, InstructorAgent |
| **Trading** | Crypto Squad | AutoCoinBot, BacktestAgent, StrategyAgent, RiskManager |
| **Treasury** | Finance Squad | PortfolioAgent, ReportingAgent, ComplianceAgent |

---

## 🏗️ Estrutura por Squads (Team Topologies)

### 🟦 STREAM-ALIGNED TEAMS (Entrega de valor)

#### Squad Development (Código)
```yaml
Coordenador: Development Coordinator
Membros:
  - PythonAgent: APIs, Data Science, ML
  - JavaScriptAgent: Node.js, React, Vue
  - TypeScriptAgent: NestJS, Angular, Next.js
  - GoAgent: Microservices, CLIs
  - RustAgent: High-performance, Systems
  - JavaAgent: Spring Boot, Enterprise
  - CSharpAgent: .NET, Azure
  - PHPAgent: Laravel, WordPress
Missão: Entregar código de qualidade seguindo pipeline
#### Squad Operations (Infraestrutura)
```yaml
Coordenador: DevOps Coordinator
Membros:
  - OperationsAgent: Deploy, Monitoring, Troubleshooting
  - GitHubAgent: CI/CD, Workflows, PRs
  - DockerOrchestrator: Containers, Compose
  - SecurityAgent: ✅ SAST, Secrets, Compliance, OWASP
Missão: Garantir disponibilidade e segurança
### 🟨 ENABLING TEAMS (Capacitação)

#### Squad Knowledge (Documentação)
```yaml
Coordenador: Knowledge Coordinator
Membros:
  - ConfluenceAgent: ADRs, RFCs, Runbooks, API Docs
  - BPMAgent: Diagramas BPMN, Draw.io, Fluxogramas
  - InstructorAgent: Treinamento, Web Crawling
  - TechnicalWriterAgent: 🆕 VAGO - A CONTRATAR
Missão: Documentar e disseminar conhecimento
#### Squad Quality (Qualidade)
```yaml
Coordenador: QA Coordinator
Membros:
  - TestAgent: Testes unitários, integração, E2E
  - RequirementsAnalyst: Requisitos, User Stories, Aprovação
  - PerformanceAgent: ✅ Load Testing, Benchmarks, Profiling
Missão: Garantir qualidade e conformidade
### 🟩 PLATFORM TEAMS (Infraestrutura compartilhada)

#### Squad Platform (Plataforma)
```yaml
Coordenador: Platform Coordinator
Membros:
  - AgentManager: Orquestração de agents
  - RAGManager: Busca semântica, embeddings
  - CommunicationBus: Mensageria entre agents
  - DataAgent: ✅ ETL, Pipelines, Analytics, Qualidade
Missão: Prover infraestrutura para todos os squads
### 🟪 INVESTMENTS TEAMS (Vertical de Investimentos)

#### Squad Trading (AutoCoinBot)
```yaml
Coordenador: Trading Coordinator
Membros:
  - AutoCoinBot: 🤖 Bot de trading autônomo BTC/USDT (KuCoin)
  - BacktestAgent: 📊 Backtesting, otimização de estratégias
  - StrategyAgent: 📈 Desenvolvimento de estratégias (DCA, Flow, Scalping)
  - RiskManagerAgent: ⚠️ Gestão de risco, stop-loss, position sizing
Missão: Executar trades autônomos com máximo retorno e risco controlado
Serviço: autocoinbot.service (porta 8515)
Localização: /home/shared/AutoCoinBot/
#### Squad Finance (Tesouraria)
```yaml
Coordenador: Treasury Coordinator
Membros:
  - PortfolioAgent: 💼 Gestão de portfólio, alocação de ativos
  - ReportingAgent: 📄 Relatórios de P&L, performance
  - ComplianceAgent: ✅ Compliance tributário, auditoria
  - TaxAgent: 🧾 Cálculo de impostos sobre ganhos de capital
Missão: Gestão financeira, relatórios e compliance
Status: 🆕 EM IMPLANTAÇÃO
---

## 🆕 Vagas em Aberto (Contratações Necessárias)

| Agent | Squad | Justificativa | Prioridade |
|-------|-------|---------------|------------|
| ~~SecurityAgent~~ | ~~Operations~~ | ~~Análise de vulnerabilidades~~ | ✅ Contratado |
| ~~DataAgent~~ | ~~Platform~~ | ~~ETL, pipelines de dados~~ | ✅ Contratado |
| ~~PerformanceAgent~~ | ~~Quality~~ | ~~Load testing, profiling~~ | ✅ Contratado |
| **TechnicalWriterAgent** | Knowledge | Documentação de usuário, guides | 🟢 Baixa |

---

## 📊 Matriz de Responsabilidades (RACI)

| Atividade | Diretor | Superintendente | Coordenador | Agent |
|-----------|---------|-----------------|-------------|-------|
| Definir Regras | **R** | A | C | I |
| Aprovar Contratações | **R** | A | C | I |
| Alocar Recursos | A | **R** | C | I |
| Supervisionar Pipeline | I | A | **R** | C |
| Executar Tarefas | I | I | C | **R** |
| Validar Entregas | I | C | **R** | A |
| Documentar | I | C | A | **R** |

**Legenda:** R=Responsável, A=Aprovador, C=Consultado, I=Informado

---

## 📈 Métricas por Squad

### Engineering
- Velocity (pontos/sprint)
- Code coverage (%)
- Tech debt ratio
- PR review time

### Operations
- Uptime (%)
- MTTR (Mean Time to Recovery)
- Deploy frequency
- Incident count

### Quality
- Bug escape rate
- Test pass rate
- Requirements completion
- Acceptance rate

### Knowledge
- Documentation coverage
- Training completion
- Knowledge base growth
- Search effectiveness

---

## 🔄 Fluxo de Comunicação

┌─────────┐    Request    ┌──────────────┐    Task    ┌─────────┐
│  User   │──────────────▶│ Communication │───────────▶│  Agent  │
└─────────┘               │     Bus       │            └────┬────┘
     ▲                    └───────┬───────┘                 │
     │                            │                         │
     │     Response               │ Log                     │ Execute
     │◀───────────────────────────┼─────────────────────────┤
     │                            ▼                         │
     │                    ┌──────────────┐                  │
     │                    │  RAG Manager  │◀─────────────────┘
     │                    │  (Contexto)   │     Index
     │                    └──────────────┘
     │
     └────────────────── Feedback Loop ────────────────────┘
---

## 📅 Última Atualização
- **Data:** 2026-01-16
- **Versão:** 2.0.0
- **Autor:** Diretor Shared Auto-Dev
- **Revisado por:** Superintendente Engineering
