# Política global de hooks: zero erro silencioso

**Data:** 2026-07-18  
**Regra:** *Nunca permitir erros silenciosos, fallback sem comunicação de incidente e similares.*

---

## O que é proibido

| Padrão | Exemplo |
|--------|---------|
| `except` + `pass` | `except Exception: pass` |
| `except` + `return None/False/[]` sem log | engolir falha e seguir |
| `except` + `continue` sem log | pular item sem rastro |
| `|| true` / `>/dev/null 2>&1 \|\| true` em ops críticas | wiki_sync, deploy, systemctl |
| Fail-open documentado sem incidente | “non-blocking” sem notify |

## O que é obrigatório em falha

1. **stderr** imediato  
2. **Log** em `.git/hook_incidents.log`  
3. **Artifact** em `artifacts/hook_incidents/incident_*.json`  
4. **Telegram** se `TELEGRAM_BOT_TOKEN` + `ADMIN_CHAT_ID` (ou `HOOK_INCIDENT_*`) estiverem setados  

Helper: `tools/hooks/incident_notify.py`

```bash
python3 tools/hooks/incident_notify.py \
  --source "meu-hook" \
  --summary "falha X" \
  --details "stack/log" \
  --severity error
```

---

## Onde a regra é enforced

| Camada | Arquivo | Comportamento |
|--------|---------|---------------|
| **pre-commit** | `.githooks/pre-commit` check `[11/11]` | Bloqueia commit se o detector achar padrões no staged |
| **Detector** | `tools/hooks/no_silent_failure.py` | Escaneia Python/shell staged |
| **post-commit** | `.githooks/post-commit` | wiki-sync em **foreground**; falha → incidente (não `&` silencioso) |
| **wiki_sync** | `tools/hooks/wiki_sync.py` | exit 1 + incidente se publish falhar / sem token |
| **Agents** | `hooks.json` PreToolUse | Roda detector no staged após Write/Edit |

---

## Escapes (somente se intencional)

| Escape | Uso |
|--------|-----|
| `# silent-ok` ou `# incident-ok` na linha | Caso pontual auditável |
| `ALLOW_SILENT_FAILURE=1` | Sessão inteira (não recomendado) |
| `git commit --no-verify` | Último recurso |

---

## Motivação (incidente wiki 2026-07-18)

O post-commit rodava `wiki_sync` em background (`&`) e falhas (timeout 503) ficavam só em `.git/wiki_sync.log`.  
O commit “passava limpo” sem o autor saber que a Wiki RPA4All **não** recebeu o doc.

Agora: falha de wiki gera **INCIDENTE** visível no terminal + log + artifact.

---

## Testes manuais

```bash
# deve falhar (exit 2)
echo 'try:
    x()
except Exception:
    pass
' > /tmp/bad.py
python3 tools/hooks/no_silent_failure.py /tmp/bad.py; echo rc=$?

# deve passar com escape
echo 'try:
    x()
except Exception:
    pass  # silent-ok
' > /tmp/ok.py
python3 tools/hooks/no_silent_failure.py /tmp/ok.py; echo rc=$?
```

---

## Relacionado

- `docs/TRADING_SYMBOL_ISOLATION_FIX_2026-07-18.md` (wiki-sync falhou silenciosamente no primeiro commit)
- `tools/hooks/incomplete_markers.py` (detector bugs agora emitem incidente, exit 1)
