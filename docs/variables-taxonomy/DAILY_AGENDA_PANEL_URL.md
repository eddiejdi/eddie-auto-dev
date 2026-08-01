# DAILY_AGENDA_PANEL_URL

| | |
|--|--|
| **Tipo** | URL HTTP |
| **Default** | `http://192.168.15.2:8093` (no `run_daily_agenda_broadcast`) |
| **Onde** | env do processo de broadcast / workstation |
| **Segredo** | não |

## Propósito

Base URL do painel da agenda diária. Quando definida, `PanelJobReporter` (`tools/daily_agenda_job_status.py`) envia heartbeats e chunks de log para:

```http
POST {DAILY_AGENDA_PANEL_URL}/api/job/report
```

Assim jobs disparados fora do painel (systemd, Telegram regenerate, CLI na workstation) aparecem no log ao vivo de `:8093`.

## Relacionadas

| Variável | Uso |
|----------|-----|
| `PANEL_API_KEY` | header `X-API-Key` se o painel exigir auth |
| `DAILY_AGENDA_JOB_LOG` | path do `panel_job.log` (default sob `artifacts/daily_agenda/`) |
| `DAILY_AGENDA_ARTIFACTS_DIR` | root de artefatos do painel |
| `OLLAMA_HOST` / `AGENDA_LLM_COORD_HOST` | LLM via coordinator `:11437` |
| `AGENDA_LLM_MODEL` | modelo principal (ex. `lfm2.5-fast:gpu1`) |
| `AGENDA_YOUTUBE_CHANNEL_ID` | canal de publicação |

## Config em arquivo (não env)

`artifacts/daily_agenda/panel_config.json` → `audio.sem_pauta_*`, `approval.*`, etc.  
Ver `docs/DAILY_AGENDA_BROADCAST.md`.
