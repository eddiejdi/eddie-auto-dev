# Agenda Diária Importante — runbook operacional

Canal YouTube **@AgendaDiáriaImportante** · boletim sobre a agenda e a atuação do senador Flávio Bolsonaro.

Documento de referência do pipeline de produção (coleta → LLM → TTS → prévia Telegram → aprovação → YouTube) e dos guards editoriais/técnicos em vigor desde **2026-07-31**.

---

## 1. Visão geral

```
Fontes oficiais / imprensa / Direita Já / aliados YouTube
        │
        ▼
  source.txt  (fatos do dia)
        │
        ▼
  classify_source_mode → COM_PAUTA | SEM_PAUTA
        │
        ▼
  pipeline modular (N segmentos LLM + mesa de Editor + TTS)
        │
        ▼
  cues de produção (vinheta / bed / pausas) + locution.wav
        │
        ▼
  prévia Telegram (áudio MP3 + botões)
        │
   ┌────┼────────────────┐
   ▼    ▼                ▼
Aprovar  Gerar de novo   Não publicar
   │         │               │
   ▼         ▼               ▼
YouTube   re-roda pipeline   encerra
```

| Componente | Caminho / endpoint |
|------------|--------------------|
| Orquestrador | `tools/run_daily_agenda_broadcast.py` |
| Coleta / source | `tools/build_flavio_bolsonaro_agenda_source.py` |
| Segmentos / Editor | `tools/daily_agenda_segments.py` |
| Cues de produção | `tools/daily_agenda_cues.py` |
| Editorial (aliados / hostil) | `tools/daily_agenda_editorial.py` |
| Aprovação Telegram | `tools/daily_agenda_approval.py` |
| Job status + log painel | `tools/daily_agenda_job_status.py` |
| Painel HTTP | `scripts/daily_agenda_panel_server.py` → **:8093** |
| Config persistente | `artifacts/daily_agenda/panel_config.json` |
| Artefatos do dia | `artifacts/daily_agenda/YYYY-MM-DD/` |
| Gateway de callbacks | `specialized_agents/approval_gateway.py` (systemd) |

**Produção (homelab `192.168.15.2`):**

| Unit | Função |
|------|--------|
| `daily-agenda-broadcast.service` (+ timer, se habilitado) | oneshot diário |
| `daily-agenda-panel.service` | painel `http://192.168.15.2:8093/` |
| `approval-gateway.service` | callbacks Telegram (`dag:*`) |

LLM **sempre** via ollama-gpu-coordinator (`:11437`). Não apontar OLLAMA/AGENDA para `:11434/:11435/:11436` em produção.

---

## 2. Fluxo de aprovação (Telegram)

Prévia = mensagem de resumo + **áudio** (WAV longo vira `locution.telegram.mp3` se > ~48 MiB).

### Botões (inline keyboard)

| Botão | Callback | Efeito |
|-------|----------|--------|
| ✅ Aprovar e publicar | `dag:A:YYYY-MM-DD` | publica YouTube (se habilitado) e encerra |
| 🔍 Gerar de novo | `dag:R:YYYY-MM-DD` | re-roda com busca profunda (até `max_regenerations`) |
| ⏹️ Não publicar / descartar | `dag:X:YYYY-MM-DD` | encerra **sem** YouTube |

Estado em `artifacts/daily_agenda/approval_pending.json`:

```json
{
  "date_str": "2026-07-31",
  "status": "waiting|approved|regenerate|rejected|timeout",
  "attempt": 1,
  "deep_search": true,
  "message_id": 19725,
  "audio_message_id": 19726,
  "created_at": "...",
  "decided_at": "...",
  "decided_by": "..."
}
```

- Quem processa o clique: `approval_gateway` **ou** o próprio `wait_for_decision` (poll `getUpdates`) — **só um** consome o update; em produção o gateway no homelab é a fonte principal.
- Timeout padrão: **180 min** (`panel_config.approval.timeout_minutes`).
- Regenerações máximas: **2** (`max_regenerations`).

**Não existe “rejeitar e regenerar com patch” automático** — “Gerar de novo” só reforça deep-search; melhorias de qualidade vêm do código/config.

---

## 3. Modos COM_PAUTA vs SEM_PAUTA

Classificação: `daily_agenda_segments.classify_source_mode(source_text)`.

| Sinal | Modo |
|-------|------|
| “não há compromissos formais” / similar, sem horário+comissão | **SEM_PAUTA** |
| horário (`10h`, `14:30`) + verbo de agenda (participa, comissão, sessão…) | **COM_PAUTA** |
| source curto (&lt; ~220 palavras) sem horário | **SEM_PAUTA** |

### Guards SEM_PAUTA (2026-07-31)

Problema histórico: source com **~66 palavras** virava **20+ blocos × ~3 min** + **extras** para forçar **1 h**, com **data e “sem compromissos” em todo bloco**.

| Parâmetro (`panel_config.audio`) | Default | Efeito |
|----------------------------------|--------:|--------|
| `sem_pauta_max_duration_seconds` | **720** | teto ~12 min |
| `sem_pauta_max_segments` | **6** | máx. blocos |
| `sem_pauta_allow_extras` | **false** | não gera 2ª leva “extra” para encher 1 h |

Log esperado:

```text
SEM_PAUTA: teto de duração 3600s → 720s (evita eco forçado para 1h)
Pipeline modular: mode=sem_pauta, 4 segmentos, alvo total=720s, ...
```

### Anti-eco de data e âncora

- **Data completa** só na **abertura** (`segment.index == 1` / role `abertura`).
- Prompt proíbe “para esta sexta-feira, trinta e um…” nos demais blocos.
- Pós-processo: `strip_date_echo()`, `strip_redundant_no_agenda_opener()`.
- Evitar repetir a trinca SP / Rondônia / ES em todo bloco se já foi dita.

### COM_PAUTA

- Alvo de duração continua o configurado (`min_duration_seconds`, tipicamente 3600).
- `max_length_retries` pode gerar segmentos extras se o áudio ficar abaixo do mínimo (só quando **não** for SEM_PAUTA com extras desligados).

---

## 4. Cues de produção e TTS limpo

Cues estruturados no texto (não devem ser falados):

```text
{{PAUSE:2}}  {{BED:locucao}}  {{VINHETA:open}}
```

- Parse: `daily_agenda_cues.parse_and_strip_cues` → fala limpa + timeline.
- Assets em `artifacts/daily_agenda/YYYY-MM-DD/cues/`.
- `test_cpu_tts_from_generated_text.strip_script_stage_directions` remove prosa residual (`Pause 2`, `{{`, “Som de fundo…”, etc.).

Config de pausas (mais audível após 2026-07-31):

- `segment_gap_seconds`: **1.5**
- `cues.pause_between_segments_seconds`: **2.0**

---

## 5. Painel :8093 (log ao vivo)

UI: `http://192.168.15.2:8093/`

| Endpoint | Uso |
|----------|-----|
| `GET /api/job` | status + tail do log |
| `GET /api/job/log?since=N` | poll incremental |
| `GET /api/job/stream` | SSE |
| `POST /api/run` | dispara job pelo painel |
| `POST /api/job/report` | **ingestão de job externo** (systemd / workstation / Telegram) |
| `POST /api/job/clear` | libera botão se travado |

Arquivos:

- `artifacts/daily_agenda/panel_job.json`
- `artifacts/daily_agenda/panel_job.log`

### Jobs externos

`run_daily_agenda_broadcast` usa `PanelJobReporter`:

1. Grava status/log local.
2. Se `DAILY_AGENDA_PANEL_URL` estiver setado (default `http://192.168.15.2:8093`), faz `POST /api/job/report`.

Assim regeneração via Telegram ou run na workstation aparece no painel.

Jobs com `"external": true` usam **heartbeat** (não PID local) no reconcile — evita marcar failed só porque o PID é de outra máquina. Stale se sem heartbeat &gt; ~10 min.

---

## 6. Fontes e editorial

| Fonte | Notas |
|-------|--------|
| Congresso / comissões Senado | deep-search; timeouts longos são comuns |
| **Direita Já** (`direitaja.com` WP API) | fonte oficial de verdades (não `endireitaja.com`) |
| Google Notícias / imprensa | filtro de manchetes **hostis** |
| Aliados YouTube | Kim Pain, Didi Newa, Auriverde, etc. (`panel_config.ally_youtube`) |

Editorial: `tools/daily_agenda_editorial.py` — stance pro-Bolsonaro/aliados; bypass de aliados em filtros hostis; proibido ecoar “repete o pai / ataca urnas”.

---

## 7. Artefatos do dia

```text
artifacts/daily_agenda/YYYY-MM-DD/
  source.txt              # fatos
  locution.txt            # texto com cues
  locution.spoken.txt     # só fala
  locution.script.txt     # script por bloco (## role)
  locution.wav            # áudio final
  locution.telegram.mp3   # prévia (se comprimido)
  locution.mp4            # vídeo YouTube (pós-aprovação)
  publish_meta.json       # id/url YouTube
  segments/               # drafts + edited + wavs
  segments_extra_N/       # só se extras habilitados
  cues/                   # assets de produção
  qa/                     # opcional: STT / relatório QA
```

---

## 8. Como rodar

### Produção (homelab)

```bash
sudo systemctl start daily-agenda-broadcast.service
journalctl -u daily-agenda-broadcast.service -f
```

### Manual (workstation ou homelab)

```bash
export SECRETS_AGENT_URL=http://192.168.15.2:8088
export OLLAMA_HOST=http://192.168.15.2:11437
export AGENDA_LLM_COORD_HOST=http://192.168.15.2:11437
export AGENDA_LLM_MODEL=lfm2.5-fast:gpu1
export AGENDA_LLM_FALLBACK_MODELS=gemma3-fast:gpu1,gemma3:1b,smollm2-iq3:gpu1,phi4-mini:nas
export DAILY_AGENDA_PANEL_URL=http://192.168.15.2:8093
export PYTHONUNBUFFERED=1

python3 tools/run_daily_agenda_broadcast.py \
  --mode auto \
  --date today \
  --quality balanced \
  --llm-auto-route \
  --require-approval \
  --upload-youtube \
  --deep-search \
  --timeout 45 \
  --retries 4 \
  --verbose
```

### Só texto (sem áudio / Telegram)

```bash
python3 tools/run_daily_agenda_broadcast.py --date today --dry-run --skip-audio --no-modular
```

### Deploy de código no homelab

```bash
rsync -avz tools/daily_agenda_*.py tools/run_daily_agenda_broadcast.py \
  tools/test_cpu_tts_from_generated_text.py tools/daily_agenda_job_status.py \
  tools/build_flavio_bolsonaro_agenda_source.py \
  homelab@192.168.15.2:/home/homelab/myClaude/tools/

rsync -avz scripts/daily_agenda_panel_server.py scripts/daily_agenda_panel/ \
  homelab@192.168.15.2:/home/homelab/myClaude/scripts/

sudo systemctl restart approval-gateway.service
sudo systemctl restart daily-agenda-panel.service
```

---

## 9. Config relevante (`panel_config.json`)

```json
{
  "defaults": {
    "require_approval": true,
    "upload_youtube": true,
    "deep_search": true
  },
  "approval": {
    "timeout_minutes": 180,
    "max_regenerations": 2
  },
  "audio": {
    "min_duration_seconds": 3600,
    "max_length_retries": 1,
    "sem_pauta_max_duration_seconds": 720,
    "sem_pauta_max_segments": 6,
    "sem_pauta_allow_extras": false,
    "segment_target_seconds": 180,
    "segment_gap_seconds": 1.5,
    "modular": true,
    "editor_enabled": true,
    "llm_parallel": 3,
    "cues": {
      "enabled": true,
      "pause_between_segments_seconds": 2.0,
      "bed_under_speech": true
    }
  },
  "editorial": {
    "prefer_direitaja_truths": true,
    "exclude_hostile_headlines": true
  }
}
```

---

## 10. Testes

```bash
python3 -m pytest \
  tests/test_daily_agenda_approval.py \
  tests/test_daily_agenda_segments.py \
  tests/test_daily_agenda_panel_server.py \
  tests/test_run_daily_agenda_broadcast.py \
  tests/test_cpu_tts_from_generated_text.py \
  tests/test_daily_agenda_cues.py \
  tests/test_daily_agenda_editorial.py \
  -q
```

Cobertura crítica:

- teclado com `dag:A` / `dag:R` / `dag:X`
- SEM_PAUTA com plano ≤ 6 blocos / ≤ 720 s
- `strip_date_echo` em blocos do meio
- `POST /api/job/report` no painel

---

## 11. Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| Painel `idle` com job Telegram/workstation | processo antigo sem reporter; ou painel sem `/api/job/report` | deploy reporter + restart panel; setar `DAILY_AGENDA_PANEL_URL` |
| Áudio ~1 h só ecoando data | SEM_PAUTA sem teto (código velho) | garantir segments + config com `sem_pauta_*` no host que roda |
| TTS fala “Pause 2” | cue vazado em prosa | strip em `test_cpu_tts_*`; re-gerar |
| Telegram 413 | WAV grande | `prepare_telegram_audio` → MP3 |
| Aprovação “expirada” | `approval_pending` já decidido / date mismatch | ver JSON; novo run cria waiting |
| Coleta trava em congresso.leg.br | timeout deep-search | retries; ou `--no-deep-search` para smoke |
| Job painel “travado” | external sem heartbeat | Liberar botão / `POST /api/job/clear` |
| GPU0 trading | não despejar `trading-*` | whisper/aux só na VRAM livre; LLM agenda em GPU1/NAS via coord |

---

## 12. QA de áudio (opcional)

Transcrição na GPU do server (faster-whisper, CUDA, sem despejar trading):

```bash
# no homelab, com venv + faster-whisper
ffmpeg -y -i locution.telegram.mp3 -ac 1 -ar 16000 locution_16k.wav
CUDA_VISIBLE_DEVICES=0 python transcribe_agenda_qa.py /tmp/agenda_qa_YYYY-MM-DD
```

Métricas úteis: contagem de data, “sem compromissos”, gaps VAD, n-grams repetidos.  
Exemplo de relatório: `artifacts/daily_agenda/2026-07-31/qa/qa_report.md`.

---

## 13. Histórico de correções (2026-07)

1. Filtro editorial de manchetes hostis + bypass aliados.
2. Cues de produção + strip de stage directions no TTS.
3. Direita Já (`direitaja.com`) como fonte de verdades.
4. Prévia Telegram em MP3 (evitar 413).
5. Painel log ao vivo + `POST /api/job/report` para jobs externos.
6. **SEM_PAUTA cap + anti-eco de data + botão descartar** (incidente de repetição 31/07).
7. Edição 31/07 regenerada: ~5 min, 4 blocos, data 1× → aprovada e publicada  
   https://www.youtube.com/watch?v=O6v6H28gsiU

Detalhe do incidente: `docs/INCIDENTS/2026-07-31_AGENDA_REPETITION_AND_SEM_PAUTA_CAP.md`.

---

## 14. Referências de código

| Módulo | Responsabilidade |
|--------|------------------|
| `run_daily_agenda_broadcast.py` | CLI, approval loop, extras, reporter |
| `daily_agenda_segments.py` | plan, draft, editor, TTS concat, SEM_PAUTA |
| `daily_agenda_approval.py` | keyboard, callbacks, wait, MP3 |
| `daily_agenda_job_status.py` | panel_job.json/log + remote report |
| `daily_agenda_cues.py` | timeline de produção |
| `daily_agenda_config.py` | defaults + load/save panel_config |
| `daily_agenda_editorial.py` | stance, hostil, aliados |
| `build_flavio_bolsonaro_agenda_source.py` | coleta multi-fonte |
| `scripts/daily_agenda_panel_server.py` | HTTP API painel |
| `specialized_agents/approval_gateway.py` | getUpdates → handle_telegram_callback |
