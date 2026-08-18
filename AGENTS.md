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

1. **Sem LLM chinês em PROD** (Qwen, DeepSeek, MiMo, ERNIE, ChatGLM, etc.) — política 2026-07-01. Em **DEV** (workstation, Traycer, sidequests) MiMo/DeepSeek são permitidos se funcionais. Preferir Llama, Mistral, Gemma, Phi em produção. Sidequest não-bloqueante: `tools/hooks/sidequest_nonblocking.py`.
2. **PostgreSQL** na porta **5433** (schema `btc`); SQLite proibido para trading.
2b. **Trading intocável no cluster LLM**: modelos `trading-*` nunca são evictados. Com analyst residente, a **GPU0 (3060)** ainda pode receber **só auxiliares pequenos** na VRAM livre (≤~1.8GB est., com headroom) — sem despejar trading. Modelos grandes vão para **GPU1 + NAS** (`GPU_COORD_TRADING_RESERVE_GPU0`, `GPU_COORD_AUX_MAX_VRAM_MB`).
3. **Fita LTO**: nunca `ltfsck`/`mkltfs`/`sg_raw` diretos — usar orchestrator `ltfs_recovery.py`.
4. **Sem force-push** em `main`; sem `rm -rf` / `git reset --hard` sem ordem explícita do usuário.
5. **Secrets**: vault/Authentik/env — nunca hardcode em código.
6. Rede/firewall: só com rollback `at` agendado.
7. Wiki: publicar via agent `wiki_rpa4all`, não scrape/update direto arbitrário.
8. **Internet desta workstation**: preferir **RJ45** (`enp0s31f6`) e **Wi‑Fi GVT-38AA**; SSID **TANK** só como fallback. Hook: `tools/copilot_hooks/internet_preference_context.py`.
9. **Web-agent log em tempo real**: ao chamar qualquer tool `web-agent__*`, o hook `tools/hooks/open_agent_log_terminal.py` abre (se ainda não estiver aberta) uma janela de terminal com `tail -F` do log `~/.grok/logs/mcp/web-agent.stderr.log`. Não é preciso chamar `monitor` só por causa do log.

## Layout útil

- `scripts/`, `tools/` — utilitários e hooks
- `specialized_agents/` — agentes de domínio
- `systemd/` — unidades de produção (cuidado)
- `docs/` — documentação operacional
- `tests/` — pytest

### Repos extraídos (não reintroduzir cópia completa)

| Domínio | Repo canônico | Path homelab |
|---------|---------------|--------------|
| Cloud FT / RunPod | [eddiejdi/homelab-cloud-ft](https://github.com/eddiejdi/homelab-cloud-ft) | `/home/homelab/homelab-cloud-ft` |
| Grafana dashboards | [eddiejdi/homelab-grafana-dashboards](https://github.com/eddiejdi/homelab-grafana-dashboards) | provisioning em `/home/homelab/monitoring/grafana/...` |

Painel treino cloud: https://grafana.rpa4all.com/d/cloud-ft-runpod/cloud-ft-runpod

### Agenda diária (YouTube / Telegram)

- Runbook: `docs/DAILY_AGENDA_BROADCAST.md`
- Incidente eco SEM_PAUTA (2026-07-31): `docs/INCIDENTS/2026-07-31_AGENDA_REPETITION_AND_SEM_PAUTA_CAP.md`
- Painel: `http://192.168.15.2:8093/` · LLM via coordinator `:11437`
- Orquestrador: `tools/run_daily_agenda_broadcast.py`

## Preferências de código

- Python 3.13, mudanças mínimas e focadas.
- Não commitar secrets, sessões, ou artefatos de runtime.
- Antes de mexer em trading live / LTO / rede: confirmar com o usuário.
