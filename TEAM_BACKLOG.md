# 📋 Team Backlog - Eddie Auto-Dev

## 🚨 Regras Obrigatórias para TODOS os Agents

### 1. Commit Obrigatório Após Testes com Sucesso
- **SEMPRE** fazer commit imediatamente após testes passarem com sucesso
- Formato da mensagem: `feat|fix|test|refactor: descricao curta`
- Incluir arquivos modificados relevantes
- Push para o repositório remoto

### 2. Deploy Diário da Versão Estável
- **NO FIM DO DIA** (23:00 UTC), efetuar deploy da versão estável
- Verificar que todos os testes passam antes do deploy
- Sincronizar servidor de produção via `git pull`
- Reiniciar serviços afetados: `sudo systemctl restart <servico>`
- Validar endpoints de saúde após restart

### 3. Fluxo de Desenvolvimento Completo
- **SEMPRE** seguir: Análise → Design → Código → Testes → Deploy
- Cada agent completa sua fase antes de passar para o próximo
- Documentar decisões técnicas no código e commits

### 4. Máxima Sinergia Entre Agents
- **COMUNICAR** todas as ações via Communication Bus
- **COLABORAR** delegando tarefas para agents especializados
- **COMPARTILHAR** contexto e resultados entre agents
- **NÃO DUPLICAR** trabalho - verificar se outro agent já executou

### 5. Especialização
- `PythonAgent`: Python, FastAPI, Django
- `JavaScriptAgent`: Node.js, React, Express
- `TypeScriptAgent`: TypeScript, Angular, NestJS
- `GoAgent`: Go, microservices, CLI tools
- `RustAgent`: Rust, sistemas de alta performance
- `TestAgent`: testes, cobertura, validação
- `RequirementsAnalyst`: análise de requisitos
- `OperationsAgent`: deploy, monitoramento

### 6. Auto-Scaling Inteligente
- **CPU < 50%** por 1 min → aumentar workers/agents
- **CPU > 85%** → reduzir carga e serializar tarefas
- Máximo de agents: `min(CPU_cores * 2, 16)`

---

## 🔴 Alta Prioridade (Em Andamento)

### [TASK-001] Correção da Interface Inter-Agent Communication
- **Status:** 🟡 Em Progresso
- **Responsável:** Agent de Desenvolvimento
- **Sprint:** Current
- **Descrição:** Corrigir a aba "Inter-Agent" no Streamlit Dashboard (porta 8502) para exibir corretamente as mensagens de comunicação entre agentes.
- **Problemas Identificados:**
  1. ~~Streamlit e API tinham instâncias separadas do bus~~ ✅ Corrigido
  2. ~~Erro de sintaxe na indentação do else~~ ✅ Corrigido
  3. ~~Display complexo com expanders causava problemas~~ ✅ Simplificado para text_area
  4. Auto-refresh ainda recarrega página inteira (pendente otimização)
- **Critérios de Aceite:**
  - [ ] Mensagens aparecem em tempo real na aba Inter-Agent
  - [ ] Auto-refresh atualiza apenas a área de mensagens
  - [ ] Exportação de log funciona corretamente
  - [ ] Filtros por tipo funcionam
- **Arquivos Relacionados:**
  - `specialized_agents/streamlit_app.py`
  - `specialized_agents/agent_communication_bus.py`
  - `specialized_agents/api.py`

---

## 🟡 Média Prioridade (Planejado)

### [TASK-002] Aumentar Cobertura de Testes para 100%
- **Status:** 📋 Backlog
- **Responsável:** Agent de Testes
- **Descrição:** Incrementar cobertura de testes em cada execução até atingir 100%
- **Instruções de Treinamento:** Ver `dev_agent/TEST_AGENT_TRAINING.md`

### [TASK-003] Melhorar Auto-Refresh do Dashboard
- **Status:** 📋 Backlog
- **Descrição:** Implementar refresh parcial usando st.fragment ou similar para evitar reload completo da página

### [TASK-004] Validação Automática de Sintaxe Pré-Deploy
- **Status:** 📋 Backlog
- **Descrição:** Adicionar validação de sintaxe Python antes de reiniciar serviços Streamlit

---

## � Bugs Conhecidos

### [BUG-001] Conflito de Portas no Serviço eddie-coordinator
- **Status:** 🔴 Crítico
- **Detectado:** 2026-01-14
- **Descrição:** O serviço `eddie-coordinator.service` conflita com processos manuais do Streamlit na porta 8502
- **Causa Raiz:**
  - `eddie-coordinator.service` usa porta 8502 para `streamlit_app.py` (raiz)
  - `specialized-agents.service` usa porta 8501 para `specialized_agents/streamlit_app.py`
  - Processos manuais iniciados via SSH também tentam usar 8502
- **Impacto:** Serviço falha ao iniciar com "Port 8502 is already in use"
- **Workaround Atual:** Matar processos conflitantes manualmente antes de reiniciar o serviço
- **Solução Proposta:**
  1. Separar claramente as responsabilidades de cada serviço
  2. `eddie-coordinator` → porta 8502 (dashboard principal)
  3. `specialized-agents` → porta 8501 (dashboard agentes)
  4. Criar script de cleanup automático no ExecStartPre do systemd
  5. Não iniciar processos Streamlit manualmente via SSH
- **Arquivos Relacionados:**
  - `/etc/systemd/system/eddie-coordinator.service`
  - `/etc/systemd/system/specialized-agents.service`
  - `specialized_agents/streamlit_app.py`
  - `streamlit_app.py`

---

## �🟢 Baixa Prioridade (Futuro)

### [TASK-005] Dashboard de Métricas de Cobertura
- **Status:** 💭 Ideia
- **Descrição:** Criar visualização de cobertura de testes no Streamlit

### [TASK-006] Integração com GitHub Actions para CI
- **Status:** 💭 Ideia
- **Descrição:** Triggers automáticos de testes via webhooks

---

## ✅ Concluídas

### [TASK-000] Setup Inicial do Bus de Comunicação
- **Status:** ✅ Concluído
- **Data:** 2026-01-13
- **Descrição:** Implementar AgentCommunicationBus para interceptar comunicação entre agentes

---

## 📊 Métricas do Sprint

| Métrica | Valor |
|---------|-------|
| Total de Tasks | 6 |
| Em Progresso | 1 |
| Concluídas | 1 |
| Bugs Abertos | 1 |
| Cobertura de Testes | ~60% |
| Meta Cobertura | 100% |

---

*Última atualização: 2026-01-14 00:10*
