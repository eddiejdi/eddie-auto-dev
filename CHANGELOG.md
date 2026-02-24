# Changelog

## 2026-02-23

- Feat: Weather Monitoring Agent — coleta meteorológica a cada 15 min via Open-Meteo API (gratuita). Grava 17 variáveis no Postgres (`weather_readings`). (`tools/weather_agent.py`, `specialized_agents/weather_routes.py`)
- Feat: rotas FastAPI `/weather/*` (current, latest, history, summary, collect) registradas em `specialized_agents/api.py`.
- Feat: serviço systemd `eddie-weather-agent.service` para execução contínua.
- Test: 15 testes unitários em `tests/test_weather_agent.py`.

## 2026-01-31

- Feat: start lightweight `agent_responder()` in API startup so coordinator broadcasts receive automated responses in the main server process; improves test determinism and CI coverage. (`specialized_agents.api`, `specialized_agents.agent_responder`)
- Test: added `tests/test_agent_responder.py` unit tests and an integration workflow to validate end-to-end responder behavior on the **homelab self-hosted runner**.

## 2026-01-21

- Fix: conversation dashboard now falls back to recent DB conversations when no in-memory active conversations exist. (`specialized_agents/conversation_monitor.py`)
- Fix: initialize interceptor and communication bus earlier to avoid undefined references from UI callbacks.
- Test: added `tests/test_interceptor_db.py` to verify interceptor DB contains conversations.
### Fixed\n- Sincronizado `DATABASE_URL` e atualizada senha do Postgres para `eddie_memory_2026` (homelab). See docs/PR_database_url_fix.md.
