**Agents Overview**

Este documento resume os agentes disponíveis no projeto e como inspecioná-los em tempo de execução.

- **Agentes por linguagem:** Python, JavaScript, TypeScript, Go, Rust, Java, CSharp, PHP.
  - Implementação: [specialized_agents/language_agents.py](specialized_agents/language_agents.py)
- **Agentes especializados adicionais:** BPM, Home Automation / Google Assistant (via `get_specialized_agent`).

- **Como ver agentes ativos (runtime):**
  - O `AgentManager` expõe `list_active_agents()` e `get_system_status()`.
  - Implementação e endpoints relacionados: [specialized_agents/agent_manager.py](specialized_agents/agent_manager.py)

- **Monitor / UI:**
  - Versão simples em Streamlit: [specialized_agents/conversation_monitor.py](specialized_agents/conversation_monitor.py)
  - A UI completa e a extensão VS Code (`eddie-copilot`) também possuem comandos/integrações para executar ações com agentes (veja `eddie-copilot/package.json`).

- **Como inspecionar em código (exemplo rápido):**

```py
from specialized_agents import get_agent_manager

mgr = get_agent_manager()
agents = mgr.list_active_agents()  # lista de dicionários com nome, language, capabilities, status
print(agents)
```

- **Referências rápidas:**
  - `specialized_agents/language_agents.py` — classes dos agentes por linguagem
  - `specialized_agents/agent_manager.py` — criação, listagem e status dos agentes
  - `specialized_agents/conversation_monitor.py` — monitor Streamlit simples

Se quiser, eu adiciono exemplos de queries/rotas para o interceptor API (ex.: `/interceptor/conversations/active`) ou gero um script `scripts/list_agents.py` para rodar localmente.
