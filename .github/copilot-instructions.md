
# Eddie Auto-Dev Copilot Guide

## Team Management
- Consulte [TEAM_BACKLOG.md](TEAM_BACKLOG.md) para a lista de tarefas da equipe, prioridades e status.
- O Agent de Testes deve seguir as instruções em [dev_agent/TEST_AGENT_TRAINING.md](dev_agent/TEST_AGENT_TRAINING.md) para aumentar cobertura até 100%.

## 🚨 Regras Obrigatórias para TODOS os Agents

### 0. 🔴 REGRA SUPREMA: Sempre Obedeça o Pipeline
- **OBRIGATÓRIO**: Todo agent DEVE seguir o pipeline completo sem exceções
- **SEQUÊNCIA**: Análise → Design → Código → Testes → Deploy
- **BLOQUEIO**: Não avançar para próxima fase sem completar a anterior
- **VALIDAÇÃO**: Confirmar sucesso de cada etapa antes de prosseguir
- **ROLLBACK**: Em caso de falha, voltar à etapa anterior e corrigir
- **DOCUMENTAÇÃO**: Registrar cada transição de fase no log/commit

### 0.1 💰 REGRA DE ECONOMIA: Tokens vs Servidor Local
- **ECONOMIZAR** ao máximo os tokens do GitHub Copilot (API externa cara)
- **MAXIMIZAR** uso dos agents do servidor local homelab (recursos próprios)
- **PREFERIR** processamento local sempre que possível:
  - Usar Ollama local (http://192.168.15.2:11434) para inferência
  - Usar RAG local (ChromaDB) para busca de contexto
  - Usar agents especializados locais para tarefas de código
- **DELEGAR** para servidor local:
  - Análise de código → Ollama + RAG local
  - Geração de código → Agents especializados locais
  - Testes → pytest/jest no servidor
  - Deploy → scripts locais + systemd
- **USAR GitHub Copilot SOMENTE** para:
  - 🆕 **Problemas nunca vistos** - situações inéditas sem solução no RAG
  - 📚 **Novos assuntos** - tecnologias/conceitos não indexados localmente
  - 👁️ **Acompanhamento** - supervisão de tarefas críticas
  - 💬 **Feedback** - revisão e validação final de entregas
  - 🌐 **Contexto externo** - informações que requerem web search
- **PROIBIDO usar Copilot** para:
  - ❌ Tarefas repetitivas que o RAG local pode resolver
  - ❌ Geração de código padrão (CRUD, templates, boilerplate)
  - ❌ Debugging de erros comuns já documentados
  - ❌ Consultas que podem ser cacheadas localmente
- **BATCH** operações para reduzir chamadas de API
- **CACHE** resultados de consultas frequentes no RAG local
- **MEDIR** uso de tokens e reportar no Communication Bus

### 0.2 🧪 REGRA DE VALIDAÇÃO: Sempre Testar Antes de Entregar
- **NUNCA** considerar tarefa concluída sem validação real
- **OBRIGATÓRIO** executar testes práticos a cada etapa:
  1. **Após código**: Executar e verificar output
  2. **Após integração**: Testar endpoints/APIs reais
  3. **Após deploy**: Validar via curl/browser que funciona
- **PROIBIDO** assumir que funcionou baseado apenas em "não deu erro"
- **MOSTRAR** evidência concreta de funcionamento (screenshot, output, curl)
- **VALIDAR** passo a passo em tarefas complexas:
  - Dividir em partes menores
  - Testar cada parte individualmente
  - Só avançar após confirmação de sucesso
- **EM CASO DE DÚVIDA**: Perguntar ao usuário antes de assumir sucesso

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
- **SEMPRE** seguir o fluxo: Análise → Design → Código → Testes → Deploy
- Cada agent deve completar sua fase antes de passar para o próximo
- Documentar decisões técnicas no código e commits
- Validar cada etapa antes de prosseguir

### 4. Máxima Sinergia Entre Agents
- **COMUNICAR** todas as ações via Communication Bus
- **COLABORAR** delegando tarefas para agents especializados
- **COMPARTILHAR** contexto e resultados entre agents
- **NÃO DUPLICAR** trabalho - verificar se outro agent já executou
- Usar RAG compartilhado para conhecimento comum

### 5. Especialização e Colaboração
- Cada agent trabalha em sua **ESPECIALIDADE**:
  - `PythonAgent`: código Python, FastAPI, Django
  - `JavaScriptAgent`: Node.js, React, Express
  - `TypeScriptAgent`: TypeScript, Angular, NestJS
  - `GoAgent`: Go, microservices, CLI tools
  - `RustAgent`: Rust, sistemas de alta performance
  - `TestAgent`: testes, cobertura, validação
  - `RequirementsAnalyst`: análise de requisitos, documentação
  - `OperationsAgent`: deploy, monitoramento, troubleshooting
  - `BPMAgent`: diagramas BPMN, Draw.io, fluxogramas, arquitetura
  - `InstructorAgent`: treinamento de agents, web crawling, conhecimento
- **DELEGAR** para o agent correto quando tarefa sair da especialidade

### 6. Auto-Scaling Inteligente
- **MONITORAR** uso de CPU/memória do servidor
- Se CPU < 50% por mais de 1 minuto, **AUMENTAR** workers/agents paralelos
- Se CPU > 85%, **REDUZIR** carga e serializar tarefas
- Máximo de agents simultâneos: `min(CPU_cores * 2, 16)`
- Cada agent deve reportar sua carga no Communication Bus

### 7. 📜 REGRA DE HERANÇA: Novos Agents Herdam Regras Aplicáveis
- **OBRIGATÓRIO** ao criar/contratar novo agent:
  1. **ANALISAR** regras existentes em `base_agent.py`, `config.py` e `AGENT_RULES`
  2. **HERDAR** regras aplicáveis à especialidade do novo agent
  3. **DOCUMENTAR** quais regras foram herdadas no código do agent
  4. **IMPLEMENTAR** métodos de validação conforme Regra 0.2
  5. **INTEGRAR** com Communication Bus conforme Regra 4
- **REGRAS SEMPRE HERDADAS** (obrigatórias para todos):
  - Regra 0: Pipeline (Análise → Design → Código → Testes → Deploy)
  - Regra 0.1: Economia de Tokens (preferir Ollama local)
  - Regra 0.2: Validação obrigatória antes de entregar
  - Regra 1: Commit após testes com sucesso
  - Regra 4: Comunicação via Bus
- **REGRAS CONDICIONAIS** (conforme especialidade):
  - Agents de código: Docker, RAG, GitHub integration
  - Agents de design: Validação visual, export de arquivos
  - Agents de operações: Monitoramento, alertas, rollback
- **NÍVEIS DE GESTÃO** responsáveis pela herança:
  - **Diretor**: Define políticas globais de agents
  - **Superintendente**: Supervisiona implementação das regras
  - **Coordenador**: Garante que cada novo agent herde corretamente

## Core Architecture
- [telegram_bot.py](telegram_bot.py) concentra o loop assincrono do bot, orquestra handlers e disponibiliza AutoDeveloper para lidar com lacunas de resposta.
- AutoDeveloper em [telegram_bot.py](telegram_bot.py) encadeia analise de requisitos, busca web, agentes especializados e deploy GitHub quando padroes de incapacidade sao detectados.
- [specialized_agents/api.py](specialized_agents/api.py) publica a FastAPI em 0.0.0.0:8503 com um AgentManager singleton inicializado no evento de startup.
- [specialized_agents/agent_manager.py](specialized_agents/agent_manager.py) coordena Docker, RAG, GitHub Agent e RequirementsAnalyst para cada linguagem suportada.

## Runtime e Comandos
- Suba a API principal com [start_api.sh](start_api.sh); ela prepara variaveis de ambiente e conecta ao Ollama definido em OLLAMA_HOST.
- Inicie o bot executando python3 telegram_bot.py apos a API responder em /health.
- Ative os agentes especializados via [specialized_agents/start.sh](specialized_agents/start.sh) ou diretamente com uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503.
- Monitore servicos systemd prontos (eddie-telegram-bot, specialized-agents, specialized-agents-api) com sudo systemctl status nome-do-servico quando rodando em producao.
- Instale dependencias dos agentes com [specialized_agents/install.sh](specialized_agents/install.sh) para garantir Docker, Python 3.11 e pacotes FastAPI prontos.

## Specialized Agents
- [specialized_agents/config.py](specialized_agents/config.py) define diretorios persistentes (agent_data, dev_projects, agent_rag), modelos Ollama padrao e templates Docker por linguagem.
- [specialized_agents/language_agents.py](specialized_agents/language_agents.py) deriva cada agente da classe base e registra capabilities que aparecem em /agents.
- RAG por linguagem vive em ChromaDB via [specialized_agents/rag_manager.py](specialized_agents/rag_manager.py), com busca global em AgentManager.search_rag_all_languages.
- Integracao GitHub passa por [specialized_agents/github_client.py](specialized_agents/github_client.py) e workflows em AgentManager.push_to_github, exigindo GITHUB_TOKEN e GITHUB_AGENT_URL validos.

## Auto-Dev Flow
- Respostas frageis detectadas por INABILITY_PATTERNS em [telegram_bot.py](telegram_bot.py) disparam AutoDeveloper.auto_develop.
- analyze_request enriquece requisitos com busca web opcional (create_search_engine para http://192.168.15.2:8001) antes de consultar o modelo Ollama primario.
- develop_solution tenta primeiro a rota generate_code da API de agentes e recorre ao Ollama direto apenas em caso de falha.
- execute_and_validate chama execute_code do agente, agenda testes pos-deploy e acompanha pipelines GitHub Actions antes de notificar o usuario.

## Dados e Configuracao
- Copie .env.example para .env e preencha OLLAMA_HOST, OLLAMA_MODEL, TELEGRAM_TOKEN, GITHUB_TOKEN e URLs internos.
- Projetos gerados ficam em specialized_agents/dev_projects e backups em specialized_agents/backups; limpeza automatica roda via CleanupService.start_periodic_cleanup.
- RAG fica em specialized_agents/agent_rag e pode ser inspecionado via endpoints /rag/stats ou scripts em [index_documentation.py](index_documentation.py).
- Certifique-se de que Docker esteja acessivel ao usuario atual; AgentManager falha para funcionalidades de execucao se docker_orchestrator.is_available retornar falso.

## Integracoes e Observabilidade
- Ollama atende em http://192.168.15.2:11434; modelos fallback sao definidos em LLM_CONFIG fallback_model.
- Web search usa create_search_engine com DuckDuckGo e RAG local; configure a API em 192.168.15.2:8001 caso queira contexto adicional.
- Telemetria e estado global podem ser consultados via /status exposto por specialized_agents/api.py, retornando agentes ativos, containers e configuracao LLM.
- Para dashboards, execute specialized_agents/streamlit_app.py (porta 8502) apos garantir specialized_agents/start.sh em funcionamento.
