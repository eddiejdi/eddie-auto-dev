# Content Automation

Pipeline modular para geração, vídeo, agenda e publicação de conteúdo curto (mock E2E).

## Auditoria do repositório (resumo)

| Área existente | Papel | Relação com este módulo |
|----------------|-------|-------------------------|
| `tools/run_daily_agenda_broadcast.py` | Agenda + TTS + Telegram | TTS avançado (Piper/Kokoro) — reutilizável depois |
| `tools/youtube_agenda_publisher.py` | Publicação YouTube + ffmpeg | Padrão de render vídeo reaproveitado |
| `marketing/x_post_scheduler.py` | Scheduler X/Twitter + PostgreSQL | Modelo de fila similar; este módulo usa SQLite |
| `scripts/kwai/` | Viewer/rewards Kwai | Alvo futuro do `publisher` real |

**Código morto/duplicado observado:** schedulers dispersos (`validation_scheduler`, `x_post_scheduler`, agenda) sem camada unificada. Este pacote centraliza generator/scheduler/publisher para conteúdo viral.

## Estrutura

```
content_automation/
  main.py              # loop contínuo do scheduler
  scheduler.py           # agenda + fila + retry
  generator.py           # roteiro via prompts YAML
  trends.py              # tendências mock + score
  video_pipeline.py      # TTS + MP4 + legendas
  publisher.py           # mock (extensível)
  storage.py             # SQLite queue
  settings.yaml
  data/prompts/*.yaml
```

## Execução

```bash
# Instalar dependência
pip install -r content_automation/requirements.txt

# Um ciclo completo (planeja + processa fila)
python3 -m content_automation.main --once --force

# Apenas planejar slots do dia
python3 -m content_automation.main --plan-only

# Daemon (loop a cada poll_interval_seconds)
python3 -m content_automation.main
```

## Testes

```bash
python3 -m pytest tests/unit/test_content_automation.py -q
```

## Estados da fila

`pending` → `posted` (ou `failed` com retry até `max_retries`)

## Próximos passos

- Integrar LLM real no `generator.py`
- Publisher Kwai/YouTube/TikTok
- Trends via API (Google Trends, X, etc.)
- TTS Piper/Kokoro do homelab quando ffmpeg disponível