**Componentes Funcionais**

- **API Manager (FastAPI)**: `specialized_agents/api.py` — executando em http://192.168.15.2:8503. Verificado com `curl` em `/status` e `/interceptor/conversations/active` retornando JSON válido.

- **Streamlit — Main Dashboard (Chat)**: `specialized_agents/streamlit_app.py` — servindo em http://192.168.15.2:8501 (local: http://localhost:8501). Verificado via HTTP e screenshot salvo em `/tmp/streamlit_8501.png`.

- **Conversation Monitor (simplificado)**: `specialized_agents/conversation_monitor.py` — versão simplificada (read-only textarea) atualmente presente no repositório e testada localmente (serve sem erros). In production it runs on port 8505 to avoid conflict with the main dashboard.

- **E2E / Smoke utilities**: `tools/capture_streamlit_screenshot.py` (Playwright) executed successfully to capture the dashboard screenshot. Playwright environment installed and browsers available in the dev environment used for testing.

- **Systemd unit adjustments**: Service units were inspected and adjusted so no two Streamlit instances bind the same port; verified that services are listening on ports 8501 (dashboard), 8503 (API) and 8505 (monitor).

Verificações realizadas (comandos usados):

- `curl http://127.0.0.1:8503/status`
- `curl http://127.0.0.1:8503/interceptor/conversations/active`
- `curl http://localhost:8501` and Playwright screenshot `/tmp/streamlit_8501.png`
- `ss -ltnp | grep 8501 || true` (confirm listening sockets)

Observação: esta documentação lista apenas componentes confirmados funcionais; não inclui partes que não foram verificadas ou que apresentavam falha antes das correções.
