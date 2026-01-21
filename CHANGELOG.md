# Changelog

## 2026-01-21

- Fix: conversation dashboard now falls back to recent DB conversations when no in-memory active conversations exist. (`specialized_agents/conversation_monitor.py`)
- Fix: initialize interceptor and communication bus earlier to avoid undefined references from UI callbacks.
- Test: added `tests/test_interceptor_db.py` to verify interceptor DB contains conversations.
