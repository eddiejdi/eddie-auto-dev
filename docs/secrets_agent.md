# secrets_agent

**Arquivo**: `tools/secrets_agent/secrets_agent.py`

## 📋 Descrição

Secrets Agent — gateway unificado para secrets com auto-unlock Bitwarden.

## 🔧 Funções Públicas

- `audit_log()`
- `bw_get_item()`
- `bw_get_item_password()`
- `bw_list_items()`
- `bw_status_endpoint()`
- `bw_unlock_endpoint()`
- `check_rate()`
- `delete_local_secret()`
- `ensure_session()`
- `get_info()`
- `get_local_secret()`
- `get_secret()`
- `get_status()`
- `health()`
- `init_db()`
- `list_secrets()`
- `metrics()`
- `recent_audit()`
- `run_command()`
- `startup_bw_session()`

## 🚀 Execução Direta

Este agente pode ser executado diretamente:

```bash
python tools/secrets_agent/secrets_agent.py
```

## 🔐 Secrets Encontrados


### Url

- `*******` (armazenado em Secrets Agent)

## 📝 Notas
- Esta documentação foi **gerada automaticamente**
- Arquivo source: tools/secrets_agent/secrets_agent.py
- Padrão: `agent_documentation_manager.py`
- Data: 2026-03-05T17:35:08.607616