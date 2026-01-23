**UI Smoke & E2E Test Results**

- **Date:** 2026-01-22
- **Host:** 192.168.15.2 (homelab)
- **Endpoints validated:** 8501 (dashboard), 8503 (API + docs), 8505 (conversation monitor)

**Summary**
- `dashboard (8501)`: renders (client-side), smoke text length 629 — screenshot attached below.
- `api_status (8503/status)`: OK (JSON content present) — screenshot attached below.
- `api_docs (8503/docs)`: OK (Swagger UI present) — screenshot attached below.
- `conversation_monitor (8505)`: OK (live conversations UI) — screenshot attached below.

**Artifacts (screenshots)**

- Dashboard (8501): [playwright_dashboard.png](../test_artifacts/playwright_dashboard.png)
- API Status (8503): [playwright_api_status.png](../test_artifacts/playwright_api_status.png)
- API Docs (8503): [playwright_api_docs.png](../test_artifacts/playwright_api_docs.png)
- Conversation Monitor (8505): [playwright_conversation_monitor.png](../test_artifacts/playwright_conversation_monitor.png)

**Notes & next steps**
- The dashboard and conversation monitor are rendered client-side by Streamlit; full element assertions are done via Playwright screenshots.
- Consider adding this Playwright run to CI or a periodic health check job.
