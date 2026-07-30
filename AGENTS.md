# AGENTS.md — eddie-auto-dev / Shared Auto-Dev

Monorepo do homelab RPA4All: automação, trading, Nextcloud/LTO, wiki, agentes especializados e ops.

## Papel dos harnesses

| Ferramenta | Quando usar |
|------------|-------------|
| **Claude Code / Grok Build** | Refactors grandes, multi-file, arquitetura |
| **Codex** | Trechos com modelos OpenAI |
| **Pi + Ollama** | Coding local barato / fallback (este arquivo é lido pelo Pi) |
| **specialized_agents + systemd** | Domínio 24/7 (trading, Nextcloud, wiki, selfheal) |

Setup Pi: `docs/PI_CODING_AGENT_SETUP.md`  
Hooks Pi: `.pi/extensions/rpa4all-hooks/` (bridge para `tools/hooks` + `tools/copilot_hooks`)

## Políticas críticas (não violar)

1. **Sem LLM chinês** (Qwen, DeepSeek, ERNIE, ChatGLM, etc.) — política 2026-07-01. Preferir Llama, Mistral, Gemma, Phi.
2. **PostgreSQL** na porta **5433** (schema `btc`); SQLite proibido para trading.
3. **Fita LTO**: nunca `ltfsck`/`mkltfs`/`sg_raw` diretos — usar orchestrator `ltfs_recovery.py`.
4. **Sem force-push** em `main`; sem `rm -rf` / `git reset --hard` sem ordem explícita do usuário.
5. **Secrets**: vault/Authentik/env — nunca hardcode em código.
6. Rede/firewall: só com rollback `at` agendado.
7. Wiki: publicar via agent `wiki_rpa4all`, não scrape/update direto arbitrário.
8. **Internet desta workstation**: preferir **RJ45** (`enp0s31f6`) e **Wi‑Fi GVT-38AA**; SSID **TANK** só como fallback. Hook: `tools/copilot_hooks/internet_preference_context.py`.

## Layout útil

- `scripts/`, `tools/` — utilitários e hooks
- `specialized_agents/` — agentes de domínio
- `systemd/` — unidades de produção (cuidado)
- `docs/` — documentação operacional
- `tests/` — pytest

## Preferências de código

- Python 3.13, mudanças mínimas e focadas.
- Não commitar secrets, sessões, ou artefatos de runtime.
- Antes de mexer em trading live / LTO / rede: confirmar com o usuário.
